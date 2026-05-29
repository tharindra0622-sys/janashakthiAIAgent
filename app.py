"""
╔══════════════════════════════════════════════════════════════════╗
║   Sri Lanka Document OCR  |  ශ්‍රී ලංකා ලේඛන OCR               ║
║   Auto-detects & Extracts:                                       ║
║     • NIC  - National Identity Card  (ජාතික හැඳුනුම්පත)         ║
║     • Birth Certificate  (උප්පැන්නය / பிறப்பு சான்றிதழ்)       ║
║   Engine 1: Google Gemini Vision API  (primary)                  ║
║   Engine 2: Tesseract OCR             (fallback + verification)  ║
╚══════════════════════════════════════════════════════════════════╝

Install:
    pip install opencv-python-headless pillow pytesseract numpy
    brew install tesseract tesseract-lang    (Mac)

Run:
    python document_ocr.py                        # uses default path
    python document_ocr.py /path/to/document.jpg
"""

import os, re, json, sys, base64
from pathlib import Path
import cv2
import numpy as np
from PIL import Image

# ─── CONFIGURATION ─────────────────────────────────────────────────────────────
GEMINI_API_KEY  = "AIzaSyCoM6Mo1FGu4MaH8MQfYa6vM4W8rLhyv2U"
GEMINI_MODEL    = "gemini-1.5-flash"
IMAGE_PATH      = "/Users/sathyas/Documents/Project/janashakthi/CamScanner 14-06-2025 07.33_1.jpg"
TESSERACT_PATH  = "/opt/homebrew/bin/tesseract"
SUPPORTED_FORMATS = {'.jpg', '.jpeg', '.png', '.tiff', '.bmp', '.webp'}
# ───────────────────────────────────────────────────────────────────────────────


# ══════════════════════════════════════════════════════════════════════════════
#  GEMINI PROMPTS
# ══════════════════════════════════════════════════════════════════════════════

PROMPT_DETECT = """
Look carefully at this Sri Lankan document image.

You must decide if this is a NIC card or a birth certificate.

KEY VISUAL CLUES FOR NIC CARD:
- Has a PHOTO/PORTRAIT of a person on the card
- Has a long NUMBER like "808491192V" or "123456789012" printed on it
- Has the Sri Lanka coat of arms emblem
- Has "ශ්‍රී ලංකා" or "இலங்கை" printed at the top
- Is a small card format (like a credit card)
- Has a signature and "කොමසාරිස් ජනරාල්" or "பதிவாளர் நாயகம்" text
- Has a stamp or serial number like "6" in a circle/box

KEY VISUAL CLUES FOR BIRTH CERTIFICATE:
- Is a larger paper/document (not a small card)
- Has rows/fields for name, father, mother, date of birth
- Has "ජන්ම සහතිකය" or "பிறப்பு சான்றிதழ்" title
- Has "ලියාපදිංචි" (registration) text with district info
- Does NOT have a photo of a person

IMPORTANT: If you see a PHOTO OF A PERSON and a long ID NUMBER, it is DEFINITELY a NIC card.

Reply ONLY with raw JSON, no markdown:
{
  "document_type": "nic" or "birth_certificate" or "unknown",
  "confidence": "high" or "medium" or "low",
  "has_photo": true or false,
  "has_nic_number": true or false,
  "reason": "brief explanation"
}
"""

PROMPT_NIC = """
You are an expert OCR assistant for Sri Lankan National Identity Cards (NIC).
The card is written in Sinhala (සිංහල), Tamil (தமிழ்), and English.

This is a NIC card. Extract ALL visible fields:

1. NIC Number  → the long number printed on the card
   - Old format: 9 digits + V or X  (e.g. 808491192V)
   - New format: 12 digits           (e.g. 198012345678)
   → LOOK CAREFULLY — this number is usually large and prominent on the card

2. Full Name        (නම / பெயர்)
3. Date of Birth    (උපන් දිනය / பிறந்த திகதி) → DD/MM/YYYY
4. Sex / Gender     → "Male" (පුරුෂ / ஆண்) or "Female" (ස්ත්‍රී / பெண்)
5. Address          (ලිපිනය / முகவரி)
6. Issue Date       (නිකුත් කළ දිනය) → the date at bottom left of card
7. Place of Birth   (උපන් ස්ථානය) → if visible
8. Blood Group      → if visible

How to decode Old NIC number (9 digits + V/X):
- Digits 1-2: last 2 digits of birth year  (e.g. 80 = 1980)
- Digits 3-5: day of year (001-366). If > 500, subtract 500 for females.
  e.g. 849 - 500 = 349th day of year = Female born on day 349
- Use this to cross-check date of birth and sex.

Rules:
- If a field is illegible or absent, use null.
- Return ONLY raw JSON, no markdown, no backticks.

{
  "document_type": "nic",
  "nic_number":    null,
  "full_name":     { "sinhala": null, "tamil": null, "english": null },
  "date_of_birth": "DD/MM/YYYY or null",
  "sex":           "Male or Female or null",
  "address":       { "sinhala": null, "tamil": null, "english": null },
  "issue_date":    "DD/MM/YYYY or null",
  "place_of_birth": null,
  "blood_group":   null,
  "ocr_notes":     "any observations"
}
"""

PROMPT_BIRTH_CERT = """
You are an expert OCR assistant for Sri Lankan birth certificates.
These documents are written in Sinhala (සිංහල), Tamil (தமிழ்), and/or English.
Fields may be handwritten. The document may be rotated — read it regardless of orientation.

Extract ALL of the following fields:
1. Child's Full Name     (නම / பெயர் / Name)
2. Date of Birth         (උපන් දිනය / பிறந்த திகதி)  → DD/MM/YYYY
3. Place of Birth        (උපන් ස්ථානය / பிறந்த இடம்)
4. Sex / Gender          → "Male" or "Female"
5. Father's Name         (පියාගේ නම / தந்தையின் பெயர்)
6. Mother's Name         (මාතාගේ නම / தாயின் பெயர்)
7. Registration Number   (ලියාපදිංචි අංකය / பதிவு இலக்கம்)
8. District              (දිස්ත්‍රික්කය / மாவட்டம்)
9. Date of Registration  (ලියාපදිංචි දිනය / பதிவு திகதி)

Rules:
- Read Sinhala AND Tamil handwriting carefully.
- If a field has multiple languages, return all.
- If illegible or absent, use null.
- Return ONLY raw JSON, no markdown, no backticks.

{
  "document_type": "birth_certificate",
  "full_name":            { "sinhala": null, "tamil": null, "english": null },
  "date_of_birth":        "DD/MM/YYYY or null",
  "place_of_birth":       { "sinhala": null, "tamil": null, "english": null },
  "sex":                  "Male or Female or null",
  "father_name":          { "sinhala": null, "tamil": null, "english": null },
  "mother_name":          { "sinhala": null, "tamil": null, "english": null },
  "registration_number":  null,
  "district":             { "sinhala": null, "tamil": null, "english": null },
  "date_of_registration": "DD/MM/YYYY or null",
  "ocr_notes":            "observations"
}
"""


# ══════════════════════════════════════════════════════════════════════════════
#  IMAGE PREPROCESSING
# ══════════════════════════════════════════════════════════════════════════════

def preprocess_image(image_path: str) -> np.ndarray:
    img = cv2.imread(str(image_path))
    if img is None:
        raise ValueError(f"Cannot read image: {image_path}")
    gray     = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
    filtered = cv2.bilateralFilter(gray, 11, 17, 17)
    thresh   = cv2.adaptiveThreshold(filtered, 255,
                    cv2.ADAPTIVE_THRESH_GAUSSIAN_C, cv2.THRESH_BINARY, 11, 2)
    denoised = cv2.fastNlMeansDenoising(thresh, None, 10, 7, 21)
    enhanced = cv2.convertScaleAbs(denoised, alpha=1.8, beta=10)
    return cv2.morphologyEx(enhanced, cv2.MORPH_CLOSE, np.ones((1,1), np.uint8))


def get_image_dimensions(image_path: str) -> tuple:
    """Return (width, height) of image — NIC cards are landscape/square, certs are portrait."""
    img = cv2.imread(str(image_path))
    if img is None:
        return (0, 0)
    h, w = img.shape[:2]
    return (w, h)


# ══════════════════════════════════════════════════════════════════════════════
#  STRONG NIC NUMBER DETECTOR  (regex on raw text — very reliable)
# ══════════════════════════════════════════════════════════════════════════════

def find_nic_number(text: str) -> str | None:
    """Find NIC number in raw text. Returns formatted NIC or None."""
    # Old format: 9 digits + V or X (with optional spaces/dashes)
    old = re.search(r'\b(\d[\s-]?\d[\s-]?\d[\s-]?\d[\s-]?\d[\s-]?\d[\s-]?\d[\s-]?\d[\s-]?\d[\s-]?[VvXx])\b', text)
    if old:
        return re.sub(r'[\s-]', '', old.group()).upper()

    # New format: 12 consecutive digits starting with 19xx or 20xx
    new = re.search(r'\b((?:19|20)\d{10})\b', text)
    if new:
        return new.group()

    # Fallback: any 9 digits followed by V/X
    fallback = re.search(r'(\d{9}[VvXx])', text)
    if fallback:
        return fallback.group().upper()

    return None


def decode_nic(nic_number: str) -> dict:
    """
    Decode old-format NIC to get birth year, day-of-year, and sex.
    Returns dict with decoded info, or empty dict if not decodable.
    """
    if not nic_number or len(nic_number) < 10:
        return {}

    nic_upper = nic_number.upper()

    # Old format: 9 digits + V/X
    if nic_upper[-1] in ('V', 'X') and len(nic_upper) == 10:
        try:
            year_suffix = int(nic_upper[:2])
            birth_year  = 1900 + year_suffix if year_suffix >= 0 else 2000 + year_suffix
            day_of_year = int(nic_upper[2:5])

            sex = "Male"
            if day_of_year > 500:
                day_of_year -= 500
                sex = "Female"

            # Convert day-of-year to approximate date
            import datetime
            try:
                birth_date = datetime.date(birth_year, 1, 1) + datetime.timedelta(days=day_of_year - 1)
                dob_str = birth_date.strftime("%d/%m/%Y")
            except Exception:
                dob_str = f"Day {day_of_year} of {birth_year}"

            return {
                "decoded_birth_year": birth_year,
                "decoded_sex": sex,
                "decoded_dob": dob_str
            }
        except Exception:
            return {}

    # New format: 12 digits
    if len(nic_upper) == 12 and nic_upper.isdigit():
        try:
            birth_year  = int(nic_upper[:4])
            day_of_year = int(nic_upper[4:7])
            sex = "Male"
            if day_of_year > 500:
                day_of_year -= 500
                sex = "Female"
            return {
                "decoded_birth_year": birth_year,
                "decoded_sex": sex,
            }
        except Exception:
            return {}

    return {}


# ══════════════════════════════════════════════════════════════════════════════
#  GEMINI REST API  (no SDK required)
# ══════════════════════════════════════════════════════════════════════════════

def _gemini_call(prompt: str, image_path: str) -> dict | None:
    import urllib.request, urllib.error

    with open(image_path, "rb") as f:
        img_b64 = base64.b64encode(f.read()).decode()

    mime_map = {'.jpg':'image/jpeg','.jpeg':'image/jpeg','.png':'image/png',
                '.bmp':'image/bmp','.webp':'image/webp','.tiff':'image/tiff'}
    mime = mime_map.get(Path(image_path).suffix.lower(), 'image/jpeg')

    payload = {
        "contents": [{"parts": [
            {"text": prompt},
            {"inline_data": {"mime_type": mime, "data": img_b64}}
        ]}],
        "generationConfig": {"temperature": 0.1, "maxOutputTokens": 1024}
    }
    url = (f"https://generativelanguage.googleapis.com/v1beta/models/"
           f"{GEMINI_MODEL}:generateContent?key={GEMINI_API_KEY}")

    try:
        req = urllib.request.Request(url,
              data=json.dumps(payload).encode(),
              headers={"Content-Type": "application/json"}, method="POST")
        with urllib.request.urlopen(req, timeout=60) as r:
            result = json.loads(r.read().decode())

        raw = result["candidates"][0]["content"]["parts"][0]["text"].strip()
        if "```" in raw:
            for part in raw.split("```"):
                part = part.strip().lstrip("json").strip()
                if part.startswith("{"):
                    raw = part
                    break

        return json.loads(raw)

    except urllib.error.HTTPError as e:
        print(f"  ❌ Gemini HTTP {e.code}: {e.read().decode()[:200]}")
        return None
    except urllib.error.URLError as e:
        print(f"  ❌ Network error: {e.reason}")
        return None
    except json.JSONDecodeError:
        print(f"  ❌ Gemini returned invalid JSON")
        return None
    except Exception as e:
        print(f"  ❌ Gemini error: {type(e).__name__}: {e}")
        return None


def test_gemini_connection() -> bool:
    import urllib.request, urllib.error
    print("🔑 Testing Gemini API key...")
    payload = {"contents": [{"parts": [{"text": "Reply with just: OK"}]}]}
    url = (f"https://generativelanguage.googleapis.com/v1beta/models/"
           f"{GEMINI_MODEL}:generateContent?key={GEMINI_API_KEY}")
    try:
        req = urllib.request.Request(url,
              data=json.dumps(payload).encode(),
              headers={"Content-Type": "application/json"}, method="POST")
        with urllib.request.urlopen(req, timeout=15) as r:
            res = json.loads(r.read())
        txt = res["candidates"][0]["content"]["parts"][0]["text"]
        print(f"  ✅ Gemini connected! Response: '{txt.strip()}'")
        return True
    except urllib.error.HTTPError as e:
        print(f"  ❌ API Error {e.code}: {e.read().decode()[:200]}")
        print("     → Get a valid key: https://aistudio.google.com/app/apikey")
        return False
    except Exception as e:
        print(f"  ❌ Connection error: {e}")
        return False


# ══════════════════════════════════════════════════════════════════════════════
#  STEP 1 — DETECT DOCUMENT TYPE  (3-layer approach)
# ══════════════════════════════════════════════════════════════════════════════

def detect_with_nic_regex(image_path: str) -> str | None:
    """
    Layer 1: Fastest detection — if Tesseract finds a NIC number pattern, it's a NIC.
    Returns 'nic' or None.
    """
    try:
        import pytesseract
        if os.path.exists(TESSERACT_PATH):
            pytesseract.pytesseract.tesseract_cmd = TESSERACT_PATH
        pil_img = Image.open(image_path)
        text = pytesseract.image_to_string(pil_img, lang='eng', config='--psm 6')
        nic = find_nic_number(text)
        if nic:
            print(f"  ✅ NIC number found by regex: {nic} → document is NIC")
            return "nic"
    except Exception:
        pass
    return None


def detect_with_gemini(image_path: str) -> str:
    """
    Layer 2: Gemini visual detection with strong NIC clues in prompt.
    Returns 'nic', 'birth_certificate', or 'unknown'.
    """
    print("  🤖 Asking Gemini to identify document type...")
    result = _gemini_call(PROMPT_DETECT, image_path)
    if result:
        doc_type   = result.get("document_type", "unknown")
        confidence = result.get("confidence", "?")
        has_photo  = result.get("has_photo", False)
        has_nic_no = result.get("has_nic_number", False)
        reason     = result.get("reason", "")

        print(f"  ✅ Gemini says: {doc_type.upper()} (confidence: {confidence})")
        print(f"     Has photo: {has_photo} | Has NIC number: {has_nic_no}")
        if reason:
            print(f"     Reason: {reason}")

        # Override: if Gemini sees a photo + NIC number → definitely NIC
        if has_photo and has_nic_no:
            print("  ℹ  Override: photo + NIC number detected → NIC confirmed")
            return "nic"

        return doc_type
    return "unknown"


def detect_with_keywords(image_path: str) -> tuple[str, str]:
    """
    Layer 3: Tesseract full text + keyword counting fallback.
    Returns (doc_type, raw_text).
    """
    try:
        import pytesseract
        if os.path.exists(TESSERACT_PATH):
            pytesseract.pytesseract.tesseract_cmd = TESSERACT_PATH
        pil_proc = Image.fromarray(preprocess_image(image_path))
        combined = ""
        for lang in ['eng+sin+tam', 'eng+sin', 'eng']:
            for cfg in ['--psm 6', '--psm 3']:
                try:
                    txt = pytesseract.image_to_string(pil_proc, lang=lang, config=cfg)
                    if txt and len(txt.strip()) > 30:
                        combined += txt + "\n"
                        break
                except Exception:
                    continue
            if len(combined) > 100:
                break

        text_lower = combined.lower()

        nic_keywords = [
            'identity','national','commissioner','ශ්‍රී ලංකා','ජාතික','හැඳුනුම්පත',
            'පුද්ගලයින්','කොමසාරිස්','இலங්கை','தேசிய','அடையாள','அட்டை',
        ]
        birth_keywords = [
            'birth','certificate','register','ජන්ම','සහතිකය','ලියාපදිංචිය',
            'பிறப்பு','சான்றிதழ்','பதிவு',
        ]

        nic_hits   = sum(1 for k in nic_keywords   if k.lower() in text_lower or k in combined)
        birth_hits = sum(1 for k in birth_keywords if k.lower() in text_lower or k in combined)

        # Strong NIC signal: number pattern
        if find_nic_number(combined):
            nic_hits += 5

        print(f"  📊 Keyword hits — NIC: {nic_hits}, Birth: {birth_hits}")

        if nic_hits > birth_hits:
            return "nic", combined
        elif birth_hits >= 2:
            return "birth_certificate", combined
        return "unknown", combined

    except Exception as e:
        print(f"  ⚠  Keyword detection error: {e}")
        return "unknown", ""


# ══════════════════════════════════════════════════════════════════════════════
#  STEP 2 — EXTRACT DATA
# ══════════════════════════════════════════════════════════════════════════════

def gemini_extract(image_path: str, doc_type: str) -> dict | None:
    prompt = PROMPT_NIC if doc_type == "nic" else PROMPT_BIRTH_CERT
    label  = "NIC" if doc_type == "nic" else "Birth Certificate"
    print(f"  🤖 Extracting {label} fields with Gemini...")
    result = _gemini_call(prompt, image_path)
    if result:
        print("  ✅ Gemini extraction successful.")
    return result


def tesseract_parse(raw_text: str, doc_type: str) -> dict:
    """Basic field parsing from Tesseract raw text."""
    parsed = {}

    # NIC number (most important for NIC)
    nic = find_nic_number(raw_text)
    if nic:
        parsed["nic_number"] = nic
        decoded = decode_nic(nic)
        parsed.update(decoded)

    # Dates
    for line in raw_text.split('\n'):
        if not parsed.get("date"):
            for dp in [r'\d{4}[./-]\d{1,2}[./-]\d{1,2}', r'\d{1,2}[./-]\d{1,2}[./-]\d{4}']:
                dates = re.findall(dp, line)
                if dates:
                    parsed["date"] = dates[0]
                    break

    # Sex from NIC decode first, then text
    if not parsed.get("decoded_sex"):
        tl = raw_text.lower()
        if 'female' in tl or 'ස්ත්‍රී' in raw_text or 'பெண்' in raw_text:
            parsed["sex"] = "Female"
        elif 'male' in tl or 'පුරුෂ' in raw_text or 'ஆண்' in raw_text:
            parsed["sex"] = "Male"

    return parsed


# ══════════════════════════════════════════════════════════════════════════════
#  MERGE RESULTS
# ══════════════════════════════════════════════════════════════════════════════

def merge_results(doc_type: str, gemini_data: dict | None, tess_parsed: dict) -> dict:
    def fill(gval, tval):
        return gval if gval not in (None, "", "null") else tval

    # Use NIC decoded sex/dob as extra fallback
    decoded_sex = tess_parsed.get("decoded_sex")
    decoded_dob = tess_parsed.get("decoded_dob")
    tess_date   = tess_parsed.get("date")
    tess_nic    = tess_parsed.get("nic_number")

    if gemini_data is None:
        if doc_type == "nic":
            return {
                "source":        "tesseract_only",
                "document_type": "nic",
                "nic_number":    tess_nic,
                "full_name":     {"sinhala": None, "tamil": None, "english": None},
                "date_of_birth": decoded_dob or tess_date,
                "sex":           decoded_sex or tess_parsed.get("sex"),
                "address":       {"sinhala": None, "tamil": None, "english": None},
                "issue_date":    None,
                "place_of_birth": None,
                "blood_group":   None,
                "ocr_notes":     "Gemini unavailable. Basic fields from Tesseract + NIC decode.",
                "nic_decoded":   {k: v for k, v in tess_parsed.items() if k.startswith("decoded_")}
            }
        else:
            return {
                "source":               "tesseract_only",
                "document_type":        "birth_certificate",
                "full_name":            {"sinhala": None, "tamil": None, "english": None},
                "date_of_birth":        tess_date,
                "place_of_birth":       {"sinhala": None, "tamil": None, "english": None},
                "sex":                  tess_parsed.get("sex"),
                "father_name":          {"sinhala": None, "tamil": None, "english": None},
                "mother_name":          {"sinhala": None, "tamil": None, "english": None},
                "registration_number":  None,
                "district":             {"sinhala": None, "tamil": None, "english": None},
                "date_of_registration": None,
                "ocr_notes":            "Gemini unavailable. Sinhala/Tamil fields need Gemini.",
            }

    # Gemini primary — fill gaps
    if doc_type == "nic":
        gemini_data["nic_number"]    = fill(gemini_data.get("nic_number"), tess_nic)
        gemini_data["date_of_birth"] = fill(gemini_data.get("date_of_birth"), decoded_dob or tess_date)
        gemini_data["sex"]           = fill(gemini_data.get("sex"), decoded_sex)
        # Add decoded NIC info as bonus
        decoded = {k: v for k, v in tess_parsed.items() if k.startswith("decoded_")}
        if decoded:
            gemini_data["nic_decoded"] = decoded
    else:
        gemini_data["date_of_birth"] = fill(gemini_data.get("date_of_birth"), tess_date)
        gemini_data["sex"]           = fill(gemini_data.get("sex"), tess_parsed.get("sex"))

    gemini_data["source"] = "gemini_primary"
    return gemini_data


# ══════════════════════════════════════════════════════════════════════════════
#  DISPLAY SUMMARY
# ══════════════════════════════════════════════════════════════════════════════

def display_summary(data: dict):
    def bi(field, langs=("sinhala","tamil","english")) -> str:
        if not isinstance(field, dict):
            return str(field or "N/A")
        parts = [field.get(l) for l in langs
                 if field.get(l) and str(field.get(l)).lower() not in ("null","none","")]
        return "  /  ".join(parts) if parts else "N/A"

    def v(x) -> str:
        return str(x) if x and str(x).lower() not in ("null","none","") else "N/A"

    src = "Gemini AI + Tesseract" if data.get("source") == "gemini_primary" else "⚠ Tesseract Only"

    print("\n" + "═"*65)

    if data.get("document_type") == "nic":
        print("   🇱🇰  NIC — NATIONAL IDENTITY CARD  |  ජාතික හැඳුනුම්පත")
        print("═"*65)
        print(f"  Document Type  : NIC  ✅")
        print(f"  OCR Engine     : {src}")
        print("─"*65)
        print(f"  🪪  NIC Number     : {v(data.get('nic_number'))}")
        print(f"  👤  Full Name      : {bi(data.get('full_name'))}")
        print(f"  📅  Date of Birth  : {v(data.get('date_of_birth'))}")
        print(f"  ⚧   Sex            : {v(data.get('sex'))}")
        print(f"  🏠  Address        : {bi(data.get('address'))}")
        print(f"  📋  Issue Date     : {v(data.get('issue_date'))}")
        print(f"  📍  Place of Birth : {v(data.get('place_of_birth'))}")
        print(f"  🩸  Blood Group    : {v(data.get('blood_group'))}")

        # Show NIC decoded info
        decoded = data.get("nic_decoded", {})
        if decoded:
            print("─"*65)
            print("  🔐  NIC Decoded Info:")
            if decoded.get("decoded_birth_year"):
                print(f"      Birth Year : {decoded['decoded_birth_year']}")
            if decoded.get("decoded_sex"):
                print(f"      Sex        : {decoded['decoded_sex']}")
            if decoded.get("decoded_dob"):
                print(f"      DOB (calc) : {decoded['decoded_dob']}")

    else:
        print("   🇱🇰  BIRTH CERTIFICATE  |  උප්පැන්නය  |  பிறப்பு சான்றிதழ்")
        print("═"*65)
        print(f"  Document Type  : BIRTH CERTIFICATE  ✅")
        print(f"  OCR Engine     : {src}")
        print("─"*65)
        print(f"  👤  Name              : {bi(data.get('full_name'))}")
        print(f"  📅  Date of Birth     : {v(data.get('date_of_birth'))}")
        print(f"  📍  Place of Birth    : {bi(data.get('place_of_birth'))}")
        print(f"  ⚧   Sex               : {v(data.get('sex'))}")
        print(f"  👨  Father            : {bi(data.get('father_name'))}")
        print(f"  👩  Mother            : {bi(data.get('mother_name'))}")
        print(f"  🗺   District          : {bi(data.get('district'))}")
        print(f"  🔢  Reg. Number       : {v(data.get('registration_number'))}")
        print(f"  📋  Date Registered   : {v(data.get('date_of_registration'))}")

    notes = data.get("ocr_notes")
    if notes and str(notes).lower() not in ("null","none",""):
        print(f"\n  📝  Notes: {notes}")

    print("═"*65)


# ══════════════════════════════════════════════════════════════════════════════
#  MAIN PIPELINE
# ══════════════════════════════════════════════════════════════════════════════

def process_document(image_path: str) -> dict:
    path = Path(image_path)
    if not path.exists():
        raise FileNotFoundError(f"Image not found: {image_path}")
    if path.suffix.lower() not in SUPPORTED_FORMATS:
        raise ValueError(f"Unsupported format '{path.suffix}'")

    print(f"\n📄  File : {path.name}  ({path.stat().st_size / 1024:.1f} KB)")
    print("─"*65)

    # ── Step 1: Detect document type (3 layers) ───────────────────────────────
    print("[1/3] Document Type Detection")

    # Layer 1: Fastest — NIC number regex on quick Tesseract scan
    doc_type = detect_with_nic_regex(image_path)

    # Layer 2: Gemini visual detection
    if not doc_type:
        doc_type = detect_with_gemini(image_path)

    # Layer 3: Full Tesseract keyword fallback
    raw_text = ""
    if doc_type == "unknown" or not doc_type:
        print("  🔄 Falling back to keyword detection...")
        doc_type, raw_text = detect_with_keywords(image_path)

    print(f"\n  📋 Final document type: {doc_type.upper()}")

    # ── Step 2: Run Tesseract for field parsing + NIC decode ──────────────────
    print("\n[2/3] Tesseract OCR (field parsing + NIC decode)")
    if not raw_text:
        _, raw_text = detect_with_keywords(image_path)
    tess_parsed = tesseract_parse(raw_text, doc_type)

    # ── Step 3: Gemini field extraction ───────────────────────────────────────
    print("\n[3/3] Gemini Field Extraction")
    if doc_type in ("nic", "birth_certificate"):
        gemini_data = gemini_extract(image_path, doc_type)
    else:
        print("  ⚠  Unknown document type — cannot extract fields.")
        gemini_data = None

    return merge_results(doc_type, gemini_data, tess_parsed)


# ══════════════════════════════════════════════════════════════════════════════
#  ENTRY POINT
# ══════════════════════════════════════════════════════════════════════════════

if __name__ == "__main__":
    img = sys.argv[1] if len(sys.argv) > 1 else IMAGE_PATH

    api_ok = test_gemini_connection()
    if not api_ok:
        print("\n  ⚠  Continuing in Tesseract-only mode.\n")

    try:
        result = process_document(img)
        display_summary(result)

        json_out = Path(img).with_suffix(".extracted.json")
        with open(json_out, "w", encoding="utf-8") as f:
            json.dump(result, f, ensure_ascii=False, indent=2)
        print(f"\n💾  JSON saved → {json_out}\n")

    except FileNotFoundError as e:
        print(f"\n❌  {e}")
        sys.exit(1)
    except Exception as e:
        print(f"\n❌  {type(e).__name__}: {e}")
        raise