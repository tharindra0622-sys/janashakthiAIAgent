import json
import uuid
from datetime import datetime

from app.models.database import db_connection
from app.models.constants import SERVICE_REQUIREMENTS

# ── Which services auto-apply on submission (non-financial) ──────────────────
NON_FINANCIAL_SERVICES = {"name_change", "age_alteration"}

# ── Which field each service updates in which table ─────────────────────────
#   key  → (table, column, how_to_get_value)
#   "how_to_get_value" is resolved inside _extract_update_value()
SERVICE_DB_MAP = {
    "name_change":    ("customers", "full_name",     "name"),
    "age_alteration": ("customers", "date_of_birth", "dob"),
}


def _get_name_from_field(field):
    """Extract English name string from a possibly-dict full_name field."""
    if not field:
        return None
    if isinstance(field, dict):
        for lang in ("english", "sinhala", "tamil"):
            v = field.get(lang)
            if v and str(v).lower() not in ("null", "none", ""):
                return str(v)
    v = str(field)
    return v if v.lower() not in ("null", "none", "") else None


def _extract_update_value(service_type, docs_data):
    """
    Given a list of AI-result dicts from verified docs,
    return the value to write into the database for auto-approval.

    name_change   → full name from identity doc
    age_alteration → date_of_birth from identity doc
    """
    identity_types = {"nic", "birth_certificate", "marriage_certificate"}

    for doc in docs_data:
        fb = doc.get("ai_feedback") or "{}"
        try:
            idata = json.loads(fb) if isinstance(fb, str) else fb
        except Exception:
            continue

        # identity_data may be nested under key "identity_data"
        if "identity_data" in idata:
            idata = idata["identity_data"]

        doc_type = idata.get("doc_type") or idata.get("document_type") or ""
        if doc_type not in identity_types:
            continue

        if service_type == "name_change":
            name = _get_name_from_field(idata.get("full_name"))
            if name:
                return name

        elif service_type == "age_alteration":
            dob = idata.get("date_of_birth")
            if dob and str(dob).lower() not in ("null", "none", ""):
                # Normalise to YYYY-MM-DD if possible
                raw = str(dob).strip()
                for fmt in ("%d/%m/%Y", "%d-%m-%Y", "%d %B %Y", "%dth %B %Y",
                            "%dst %B %Y", "%dnd %B %Y", "%drd %B %Y"):
                    try:
                        return datetime.strptime(raw, fmt).strftime("%Y-%m-%d")
                    except Exception:
                        pass
                return raw   # return as-is if we can't parse

    return None


def _auto_apply_non_financial(db, request_id, service_type, customer_id, policy_number, docs):
    """
    Immediately update the customers table for non-financial services.
    Returns (applied: bool, detail: str)
    """
    mapping = SERVICE_DB_MAP.get(service_type)
    if not mapping:
        return False, f"No DB mapping defined for {service_type}"

    table, column, _ = mapping
    new_value = _extract_update_value(service_type, docs)

    if not new_value:
        # Could not extract value from docs → still mark Approved but note it
        db.execute(
            'UPDATE service_requests SET status = "Auto-Approved", '
            'ai_notes = ?, updated_at = ? WHERE id = ?',
            (
                f"Auto-approved (could not extract updated {column} from documents — "
                f"manual update may be required)",
                datetime.now().isoformat(),
                request_id,
            )
        )
        return True, (
            f"Request auto-approved. Note: could not extract {column} automatically — "
            f"please verify manually."
        )

    # Apply the change
    db.execute(
        f'UPDATE {table} SET {column} = ? WHERE id = ?',
        (new_value, customer_id)
    )

    label = {
        "name_change":    f"Full name updated to: {new_value}",
        "age_alteration": f"Date of birth updated to: {new_value}",
    }.get(service_type, f"{column} updated to: {new_value}")

    db.execute(
        'UPDATE service_requests SET status = "Auto-Approved", '
        'ai_notes = ?, updated_at = ? WHERE id = ?',
        (
            f"Auto-approved & applied. {label}",
            datetime.now().isoformat(),
            request_id,
        )
    )
    return True, f"Request auto-approved. {label}"


# ─────────────────────────────────────────────────────────────────────────────

def create_request(db_path: str, customer_id: str,
                   policy_number: str, service_type: str) -> str:
    """Create a new service request and return its ID."""
    request_id = str(uuid.uuid4())[:8].upper()
    with db_connection(db_path) as db:
        db.execute(
            'INSERT INTO service_requests '
            '(id, customer_id, policy_number, service_type, status) '
            'VALUES (?,?,?,?,"Pending")',
            (request_id, customer_id, policy_number, service_type)
        )
    return request_id


def submit_request(db_path: str, request_id: str) -> tuple[bool, str]:
    """
    Validate all documents are uploaded & AI-verified, then:
      - Non-financial → auto-apply DB change, set status 'Auto-Approved'
      - Financial     → set status 'Under Review' (goes to underwriter)
    Returns (success, message).
    """
    with db_connection(db_path) as db:
        req = db.execute(
            'SELECT * FROM service_requests WHERE id = ?', (request_id,)
        ).fetchone()

        if not req:
            return False, "Request not found."

        docs = db.execute(
            'SELECT * FROM documents WHERE request_id = ?', (request_id,)
        ).fetchall()

        reqs = SERVICE_REQUIREMENTS.get(req['service_type'], {})
        uploaded_types = [d['doc_type'] for d in docs]

        # Check mandatory docs
        missing = [m for m in reqs.get('mandatory', []) if m not in uploaded_types]

        # Check identity docs (at least one)
        identity = reqs.get('identity_docs', [])
        if identity and not any(d in uploaded_types for d in identity):
            missing.append('one of: ' + ', '.join(identity))

        if missing:
            return False, f"Missing documents: {', '.join(missing)}"

        # Check AI verification
        failed = [d['doc_type'] for d in docs if not d['ai_verified']]
        if failed:
            return False, (
                f"Documents failed AI verification: {', '.join(failed)}. "
                f"Please re-upload."
            )

        service_type = req['service_type']

        # ── NON-FINANCIAL: auto-apply immediately ────────────────────
        if service_type in NON_FINANCIAL_SERVICES:
            ok, msg = _auto_apply_non_financial(
                db, request_id, service_type,
                req['customer_id'], req['policy_number'],
                [dict(d) for d in docs]
            )
            if ok:
                return True, msg
            # fallback if something goes wrong
            db.execute(
                'UPDATE service_requests SET status = "Under Review", '
                'updated_at = ? WHERE id = ?',
                (datetime.now().isoformat(), request_id)
            )
            return True, "Request submitted for review."

        # ── FINANCIAL: send to underwriter ───────────────────────────
        db.execute(
            'UPDATE service_requests SET status = "Under Review", '
            'updated_at = ? WHERE id = ?',
            (datetime.now().isoformat(), request_id)
        )

    return True, "Request submitted. An underwriter will review your documents shortly."


def get_requests_by_status(db_path: str, status: str) -> list[dict]:
    with db_connection(db_path) as db:
        rows = db.execute('''
            SELECT sr.*, c.full_name, c.nic, c.phone
            FROM service_requests sr
            JOIN customers c ON sr.customer_id = c.id
            WHERE sr.status = ?
            ORDER BY sr.created_at DESC
        ''', (status,)).fetchall()
    return [dict(r) for r in rows]


def get_request_detail(db_path: str, request_id: str) -> tuple[dict | None, list[dict]]:
    with db_connection(db_path) as db:
        req = db.execute('''
            SELECT sr.*, c.full_name, c.nic, c.phone, c.email, c.address,
                   p.plan, p.branch, p.premium_mode, p.sum_assured
            FROM service_requests sr
            JOIN customers c ON sr.customer_id = c.id
            JOIN policies p ON sr.policy_number = p.policy_number
            WHERE sr.id = ?
        ''', (request_id,)).fetchone()

        if not req:
            return None, []

        docs = db.execute(
            'SELECT * FROM documents WHERE request_id = ?', (request_id,)
        ).fetchall()

    return dict(req), [dict(d) for d in docs]


def process_decision(db_path: str, request_id: str,
                     decision: str, notes: str,
                     new_value: str = None) -> tuple[bool, str]:
    """
    Underwriter approves or rejects a financial request.
    On Approval, updates the relevant policy field.
    """
    with db_connection(db_path) as db:
        req = db.execute(
            'SELECT * FROM service_requests WHERE id = ?', (request_id,)
        ).fetchone()

        if not req:
            return False, "Request not found."

        db.execute(
            'UPDATE service_requests SET status = ?, underwriter_notes = ?, '
            'updated_at = ? WHERE id = ?',
            (decision, notes, datetime.now().isoformat(), request_id)
        )

        if decision == 'Approved':
            service_type = req['service_type']

            # ── Financial services: update policies table ─────────────
            if service_type == 'premium_mode_change' and new_value:
                db.execute(
                    'UPDATE policies SET premium_mode = ? WHERE policy_number = ?',
                    (new_value, req['policy_number'])
                )

            elif service_type == 'increase_benefits' and new_value:
                try:
                    db.execute(
                        'UPDATE policies SET sum_assured = ? WHERE policy_number = ?',
                        (float(new_value), req['policy_number'])
                    )
                except ValueError:
                    pass

            # ── Non-financial: underwriter manually approves ──────────
            # (normally auto-approved, but handle manual override)
            elif service_type in NON_FINANCIAL_SERVICES:
                docs = db.execute(
                    'SELECT * FROM documents WHERE request_id = ?', (request_id,)
                ).fetchall()
                mapping = SERVICE_DB_MAP.get(service_type)
                if mapping:
                    table, column, _ = mapping
                    value = new_value or _extract_update_value(
                        service_type, [dict(d) for d in docs]
                    )
                    if value:
                        db.execute(
                            f'UPDATE {table} SET {column} = ? WHERE id = ?',
                            (value, req['customer_id'])
                        )

    return True, f"Request {decision} successfully."


def get_stats(db_path: str) -> dict:
    with db_connection(db_path) as db:
        return {
            "pending":         db.execute("SELECT COUNT(*) FROM service_requests WHERE status='Under Review'").fetchone()[0],
            "approved":        db.execute("SELECT COUNT(*) FROM service_requests WHERE status='Approved'").fetchone()[0],
            "auto_approved":   db.execute("SELECT COUNT(*) FROM service_requests WHERE status='Auto-Approved'").fetchone()[0],
            "rejected":        db.execute("SELECT COUNT(*) FROM service_requests WHERE status='Rejected'").fetchone()[0],
            "total_customers": db.execute("SELECT COUNT(*) FROM customers").fetchone()[0],
            "total_policies":  db.execute("SELECT COUNT(*) FROM policies").fetchone()[0],
        }