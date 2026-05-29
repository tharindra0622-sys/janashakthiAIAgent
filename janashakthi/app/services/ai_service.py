import base64
import datetime
import json
import os
import re

from groq import Groq

from app.models.constants import MIME_MAP


# ── Groq client ─────────────────────────────────────────────────────────────

def _get_client(api_key):
    return Groq(api_key=api_key)


def _encode_file(file_path):
    ext  = os.path.splitext(file_path)[1].lower()
    mime = MIME_MAP.get(ext, "image/jpeg")
    with open(file_path, "rb") as f:
        return mime, base64.b64encode(f.read()).decode()


def _parse_json(text):
    text = text.strip()
    if "```json" in text:
        text = text.split("```json")[1].split("```")[0].strip()
    elif "```" in text:
        text = text.split("```")[1].split("```")[0].strip()
    return json.loads(text)


def _find_nic_in_text(text):
    old = re.search(r'\b(\d[\s-]?\d[\s-]?\d[\s-]?\d[\s-]?\d[\s-]?\d[\s-]?\d[\s-]?\d[\s-]?\d[\s-]?[VvXx])\b', text)
    if old:
        return re.sub(r'[\s-]', '', old.group()).upper()
    new = re.search(r'\b((?:19|20)\d{10})\b', text)
    if new:
        return new.group()
    fb = re.search(r'(\d{9}[VvXx])', text)
    if fb:
        return fb.group().upper()
    return None


def _decode_nic_number(nic):
    if not nic or len(nic) < 10:
        return {}
    n = nic.upper()
    try:
        if n[-1] in ('V', 'X') and len(n) == 10:
            year = 1900 + int(n[:2])
            days = int(n[2:5])
            sex  = "Male"
            if days > 500:
                days -= 500
                sex = "Female"
            try:
                dob = (datetime.date(year, 1, 1) + datetime.timedelta(days - 1)).strftime("%d/%m/%Y")
            except Exception:
                dob = f"Day {days} of {year}"
            return {"decoded_birth_year": year, "decoded_sex": sex, "decoded_dob": dob}
        if len(n) == 12 and n.isdigit():
            year = int(n[:4])
            days = int(n[4:7])
            sex  = "Male"
            if days > 500:
                days -= 500
                sex = "Female"
            return {"decoded_birth_year": year, "decoded_sex": sex}
    except Exception:
        pass
    return {}


# ── OCR: identity documents ──────────────────────────────────────────────────
# NOTE: Groq vision (llama-4-scout) supports image inputs via base64

def ocr_identity_document(file_path, api_key, model_name):
    try:
        mime, b64 = _encode_file(file_path)
        client    = _get_client(api_key)

        # Use llama-4-scout-17b-16e-instruct for vision tasks
        vision_model = "meta-llama/llama-4-scout-17b-16e-instruct"

        detect_prompt = """Classify this document image carefully.

NIC CARD - ALL of these must be true:
- Small card format (like a credit card or ID card size)
- Contains a PHOTO/PORTRAIT of a person on the card
- Has an identity number ending in V or X (e.g. 808491192V) or a 12-digit number
- Words like NATIONAL IDENTITY CARD

BIRTH CERTIFICATE - ANY of these apply:
- Title says BIRTH CERTIFICATE or Department of Registrar General
- Has fields: Full Name of Child, Date of Birth, Place of Birth, Father Name, Mother Name
- Has a Registration Number (e.g. NW/NEG/1988/03/2847)
- Larger paper/A4 format with rows and labels
- NO photo of a person on document
- May or may not have Sinhala or Tamil text

Reply ONLY raw JSON no markdown:
{"document_type":"birth_certificate","confidence":"high","has_photo":false,"has_nic_number":false,"reason":"brief"}

document_type must be exactly: nic OR birth_certificate OR unknown"""

        det_resp = client.chat.completions.create(
            model=vision_model,
            messages=[{
                "role": "user",
                "content": [
                    {"type": "image_url", "image_url": {"url": f"data:{mime};base64,{b64}"}},
                    {"type": "text", "text": detect_prompt}
                ]
            }],
            max_tokens=200
        )
        det = _parse_json(det_resp.choices[0].message.content)
        doc_type = det.get("document_type", "unknown")

        # Only force NIC if BOTH a photo AND a NIC number are confirmed present
        if det.get("has_photo") and det.get("has_nic_number"):
            doc_type = "nic"

        # Fallback: if still unknown, infer from the reason text
        if doc_type not in ("nic", "birth_certificate"):
            reason_lower = str(det.get("reason", "")).lower()
            bc_hits  = sum(1 for kw in ["birth", "certificate", "registrar", "father", "mother", "child", "registration", "dob"] if kw in reason_lower)
            nic_hits = sum(1 for kw in ["nic", "identity card", "national identity", "photo", "portrait"] if kw in reason_lower)
            if bc_hits > nic_hits:
                doc_type = "birth_certificate"
            elif nic_hits > bc_hits:
                doc_type = "nic"

        if doc_type not in ("nic", "birth_certificate"):
            return {"doc_type": "unknown", "verified": False, "confidence": 20,
                    "feedback": "Could not identify document as NIC or Birth Certificate. Please ensure the full document is visible and try again."}

        if doc_type == "nic":
            extract_prompt = """You are an expert OCR assistant for Sri Lankan National Identity Cards.
Extract ALL fields: NIC Number, Full Name (all languages), Date of Birth DD/MM/YYYY,
Sex (Male/Female), Address (all languages), Issue Date, Place of Birth, Blood Group.
Absent fields use null. Return ONLY raw JSON no markdown:
{"document_type":"nic","nic_number":null,"full_name":{"sinhala":null,"tamil":null,"english":null},"date_of_birth":null,"sex":null,"address":{"sinhala":null,"tamil":null,"english":null},"issue_date":null,"place_of_birth":null,"blood_group":null,"ocr_notes":null}"""
        else:
            extract_prompt = """You are an expert OCR assistant for Sri Lankan birth certificates.
Extract: Child Full Name (all languages), Date of Birth DD/MM/YYYY, Place of Birth,
Sex, Father Name, Mother Name, Registration Number, District, Date of Registration.
Absent fields use null. Return ONLY raw JSON no markdown:
{"document_type":"birth_certificate","full_name":{"sinhala":null,"tamil":null,"english":null},"date_of_birth":null,"place_of_birth":{"sinhala":null,"tamil":null,"english":null},"sex":null,"father_name":{"sinhala":null,"tamil":null,"english":null},"mother_name":{"sinhala":null,"tamil":null,"english":null},"registration_number":null,"district":{"sinhala":null,"tamil":null,"english":null},"date_of_registration":null,"ocr_notes":null}"""

        ext_resp = client.chat.completions.create(
            model=vision_model,
            messages=[{
                "role": "user",
                "content": [
                    {"type": "image_url", "image_url": {"url": f"data:{mime};base64,{b64}"}},
                    {"type": "text", "text": extract_prompt}
                ]
            }],
            max_tokens=800
        )
        data = _parse_json(ext_resp.choices[0].message.content)

        if doc_type == "nic":
            nic_num = data.get("nic_number")
            decoded = _decode_nic_number(nic_num) if nic_num else {}
            if decoded:
                data["nic_decoded"] = decoded
                if not data.get("sex"):
                    data["sex"] = decoded.get("decoded_sex")
                if not data.get("date_of_birth"):
                    data["date_of_birth"] = decoded.get("decoded_dob")

        data["doc_type"]      = doc_type
        data["document_type"] = doc_type
        data["verified"]      = True
        data["confidence"]    = 90
        data["source"]        = "groq_vision"
        data["feedback"]      = _identity_feedback(data)
        return data

    except Exception as exc:
        return {"doc_type": "unknown", "verified": False, "confidence": 0,
                "feedback": f"Could not process identity document: {str(exc)}"}


def _identity_feedback(data):
    def nm(field):
        if not field or not isinstance(field, dict): return str(field or "")
        parts = [v for v in field.values() if v and str(v).lower() not in ("null","none","")]
        return " / ".join(parts)
    def v(k):
        val = data.get(k)
        return str(val) if val and str(val).lower() not in ("null","none","") else None
    dt = data.get("doc_type", "")
    if dt == "nic":
        parts = [f"NIC: {v('nic_number') or '?'}"]
        n = nm(data.get("full_name"))
        if n: parts.append(f"Name: {n}")
        if v("date_of_birth"): parts.append(f"DOB: {v('date_of_birth')}")
        if v("sex"): parts.append(f"Sex: {v('sex')}")
        return "NIC extracted — " + " | ".join(parts)
    else:
        parts = []
        n = nm(data.get("full_name"))
        if n: parts.append(f"Name: {n}")
        if v("date_of_birth"): parts.append(f"DOB: {v('date_of_birth')}")
        if v("registration_number"): parts.append(f"Reg#: {v('registration_number')}")
        return "Birth Certificate extracted — " + (" | ".join(parts) if parts else "fields extracted")


def _classify_by_keywords(text):
    from app.models.constants import SINHALA_KEYWORDS, MATCH_THRESHOLD, GENERAL_LETTER_KEYWORDS
    t = text.lower()
    scores = {}
    for svc, kdata in SINHALA_KEYWORDS.items():
        all_kw  = kdata["keywords"] + kdata["english_keywords"]
        total   = len(all_kw)
        matched = sum(1 for kw in all_kw if kw.lower() in t)
        ratio   = matched / total if total > 0 else 0
        scores[svc] = {"matched": matched, "total": total,
                       "ratio": round(ratio, 4), "qualified": ratio >= MATCH_THRESHOLD}
    gen_matched = sum(1 for kw in GENERAL_LETTER_KEYWORDS if kw.lower() in t)
    best = max(scores, key=lambda k: scores[k]["ratio"])
    return {"scores": scores,
            "best_service": best if scores[best]["qualified"] else None,
            "best_ratio": scores[best]["ratio"],
            "is_letter": gen_matched >= 2}


def _get_name(data):
    fn = data.get("full_name")
    if isinstance(fn, dict):
        for lang in ("english", "sinhala", "tamil"):
            v = fn.get(lang)
            if v and str(v).lower() not in ("null","none",""): return str(v)
    return str(fn) if fn and str(fn).lower() not in ("null","none","") else None


def verify_document(file_path, doc_type, policy_number, customer_nic, api_key, model_name):
    if doc_type in ("nic", "birth_certificate", "marriage_certificate"):
        result = ocr_identity_document(file_path, api_key, model_name)
        return {
            "verified":         result.get("verified", False),
            "confidence":       result.get("confidence", 0),
            "doc_detected":     result.get("doc_type", doc_type),
            "service_detected": None,
            "extracted_policy": None,
            "extracted_nic":    result.get("nic_number") if isinstance(result.get("nic_number"), str) else None,
            "extracted_name":   _get_name(result),
            "has_signature":    False,
            "has_stamp":        False,
            "issues":           [],
            "feedback":         result.get("feedback", ""),
            "identity_data":    result,
        }
    try:
        mime, b64 = _encode_file(file_path)
        client    = _get_client(api_key)
        vision_model = "meta-llama/llama-4-scout-17b-16e-instruct"

        ocr_prompt = """You are an expert OCR specialist for Janashakthi Insurance PLC Sri Lanka.
Extract EVERY piece of text from this document image. Read in order:
1. Sender details (top-left): name, address, phone, date
2. Recipient details
3. Subject line: policy number + service type
4. Letter body — every line
5. Sign-off, signature, name
6. Any stamps (branch, date, RECEIVED)
Output all text including Sinhala/Tamil unicode."""

        ocr_resp = client.chat.completions.create(
            model=vision_model,
            messages=[{
                "role": "user",
                "content": [
                    {"type": "image_url", "image_url": {"url": f"data:{mime};base64,{b64}"}},
                    {"type": "text", "text": ocr_prompt}
                ]
            }],
            max_tokens=1000
        )
        ocr_text = ocr_resp.choices[0].message.content.strip()
        clf      = _classify_by_keywords(ocr_text)
        best_svc = clf["best_service"]
        scores   = clf["scores"]

        score_lines = "\n".join(
            f"  {k:25s}: {v['matched']:2d}/{v['total']:2d} ({v['ratio']*100:5.1f}%)"
            f"  {'<<< QUALIFIED' if v['qualified'] else ''}"
            for k, v in scores.items()
        )

        verify_prompt = f"""You are a document verification officer at Janashakthi Insurance PLC.
EXPECTED doc type: {doc_type}
Expected policy: {policy_number}
Expected NIC: {customer_nic}

EXTRACTED TEXT:
{ocr_text}

KEYWORD SCORES (10% threshold):
{score_lines}
Best match: {best_svc or "none"} | Is letter: {clf['is_letter']}

Reply ONLY valid JSON no markdown:
{{"verified":true,"confidence":85,"doc_detected":"<type>","service_detected":"<service>","extracted_policy":"<or null>","extracted_nic":"<or null>","extracted_name":"<or null>","has_signature":true,"has_stamp":true,"issues":[],"feedback":"<message>"}}"""

        verify_resp = client.chat.completions.create(
            model="llama-3.3-70b-versatile",
            messages=[{"role": "user", "content": verify_prompt}],
            max_tokens=500
        )
        result = _parse_json(verify_resp.choices[0].message.content)
        if best_svc and scores[best_svc]["qualified"]:
            result["confidence"] = max(result.get("confidence", 0), 80)
        if result.get("confidence", 0) >= 60 and len(result.get("issues", [])) == 0:
            result["verified"] = True
        result["keyword_scores"]          = {k: f"{v['matched']}/{v['total']} ({v['ratio']*100:.1f}%)" for k, v in scores.items()}
        result["extracted_text_preview"]  = ocr_text[:500]
        return result

    except Exception as exc:
        return {"verified": False, "confidence": 0, "doc_detected": "unknown",
                "issues": [str(exc)],
                "feedback": "Document could not be processed. Please upload a clearer image or PDF."}


def chat_with_customer(message, customer, session_data, api_key, model_name):
    try:
        client     = _get_client(api_key)
        id_context = ""

        for doc_key, doc_info in (session_data.get("uploaded_docs") or {}).items():
            idata = doc_info.get("identity_data") if isinstance(doc_info, dict) else None
            if not idata: continue
            dt = idata.get("doc_type", "")

            def nm(field):
                if not field or not isinstance(field, dict): return str(field or "unknown")
                parts = [v for v in field.values() if v and str(v).lower() not in ("null","none","")]
                return " / ".join(parts) if parts else "unknown"

            def fv(k):
                val = idata.get(k)
                return str(val) if val and str(val).lower() not in ("null","none","") else "not found"

            if dt == "nic":
                dec = idata.get("nic_decoded", {})
                id_context += f"""
NIC UPLOADED:
  NIC Number    : {fv('nic_number')}
  Full Name     : {nm(idata.get('full_name'))}
  Date of Birth : {fv('date_of_birth')}
  Sex           : {fv('sex')}
  Address       : {nm(idata.get('address'))}
  NIC Decoded   : Birth Year={dec.get('decoded_birth_year','?')} | Sex={dec.get('decoded_sex','?')} | DOB={dec.get('decoded_dob','?')}
"""
            elif dt == "birth_certificate":
                id_context += f"""
BIRTH CERTIFICATE UPLOADED:
  Full Name        : {nm(idata.get('full_name'))}
  Date of Birth    : {fv('date_of_birth')}
  Place of Birth   : {nm(idata.get('place_of_birth'))}
  Sex              : {fv('sex')}
  Father Name      : {nm(idata.get('father_name'))}
  Mother Name      : {nm(idata.get('mother_name'))}
  Registration No. : {fv('registration_number')}
"""

        system = f"""You are JanashakthiCare, a helpful AI assistant for Janashakthi Insurance PLC Sri Lanka.

CUSTOMER: {customer.get('full_name','Unknown')} | NIC: {customer.get('nic','')}
POLICIES: {json.dumps(customer.get('policies',[]))}
SERVICE: {session_data.get('service_type','not selected')} | POLICY: {session_data.get('policy_number','not selected')}
{id_context if id_context else "(No identity documents uploaded yet)"}
SERVICES AVAILABLE:
1. Name Change - request letter + NIC/Birth Cert/Marriage Cert
2. Age Alteration - request letter + NIC/Birth Cert/Marriage Cert
3. Change Mode of Payment - request letter + outstanding payment bill
4. Increase of Benefits - request letter + PEP/DGF form + optional income proof

RESPONSE RULES:
- Be friendly, professional, and concise. Respond in English.
- NEVER use markdown formatting like **, ##, or numbered lists with dots.
- Write in plain natural sentences only — like a real person talking.
- If listing policies or info, write them as short plain sentences, not bullet points or bold text.
- ONLY answer questions about Janashakthi Insurance, policies, documents, service requests.
  For ANY unrelated question reply: "I can only assist with Janashakthi Insurance matters. How can I help with your policy today?"
- If customer says they want to do a service (name change, age alteration, payment mode, increase benefits), end your reply with exactly: [ACTION:START_SERVICE]
- If asked about NIC or birth certificate details, use the extracted data above."""

        resp = client.chat.completions.create(
            model="llama-3.3-70b-versatile",
            messages=[
                {"role": "system", "content": system},
                {"role": "user",   "content": message}
            ],
            max_tokens=500
        )
        return resp.choices[0].message.content

    except Exception as exc:
        return f"I'm sorry, I encountered an error: {exc}. Please try again."