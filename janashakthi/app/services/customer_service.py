from app.models.database import db_connection


def find_customer(db_path: str, nic: str = '', policy_number: str = '') -> dict | None:
    """Identify a customer by NIC and/or policy number."""
    with db_connection(db_path) as db:
        if nic and policy_number:
            row = db.execute('''
                SELECT c.*, p.policy_number, p.plan, p.branch, p.status
                FROM customers c
                JOIN policies p ON c.id = p.customer_id
                WHERE c.nic = ? AND p.policy_number = ?
            ''', (nic, policy_number)).fetchone()
        elif nic:
            row = db.execute('''
                SELECT c.*, p.policy_number, p.plan, p.branch, p.status
                FROM customers c
                JOIN policies p ON c.id = p.customer_id
                WHERE c.nic = ? LIMIT 1
            ''', (nic,)).fetchone()
        elif policy_number:
            row = db.execute('''
                SELECT c.*, p.policy_number, p.plan, p.branch, p.status
                FROM customers c
                JOIN policies p ON c.id = p.customer_id
                WHERE p.policy_number = ?
            ''', (policy_number,)).fetchone()
        else:
            return None

        if not row:
            return None

        all_policies = db.execute(
            'SELECT policy_number, plan, branch, status, premium_mode, sum_assured FROM policies WHERE customer_id = ?',
            (row['id'],)
        ).fetchall()

        return {
            "id":            row['id'],
            "nic":           row['nic'],
            "full_name":     row['full_name'],
            "phone":         row['phone'],
            "email":         row['email'],
            "address":       row['address'],
            "date_of_birth": row['date_of_birth'],
            "policies":      [dict(p) for p in all_policies],
        }
