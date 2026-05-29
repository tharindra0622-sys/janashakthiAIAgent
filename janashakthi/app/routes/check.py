"""
╔══════════════════════════════════════════════════════════════════╗
║   🇱🇰  SRI LANKA BIRTH CERTIFICATE — STRUCTURED OCR ENGINE       ║
║   API    : Google Gemini (gemini-1.5-pro)                        ║
║   Supports: Sinhala Handwriting + Sinhala Print + English        ║
║   Method  : 3-Pass Gemini Vision OCR                             ║
╚══════════════════════════════════════════════════════════════════╝

EXACT STRUCTURE mapped from real SL birth certificate (High Reg. P & S.C.* 12/78):

  HEADER         - Registration Date, Doc Number, District, Division, Entry No.
  FIELD 1        - Date and Place of Birth
  FIELD 2        - Child's Name
  FIELD 3        - Sex
  FIELD 4        - Father's Details (name, DOB, POB, race)
  FIELD 5        - Mother's Details (name, DOB, POB, race, age)
  FIELD 6        - Were Parents Married?
  FIELD 7        - Grandfather (name, year of birth, place of birth)

Requirements:
    pip install google-generativeai pillow

Usage:
    # Set key via environment variable (recommended):
    export GEMINI_API_KEY="your-key-here"
    python birth_certificate_ocr.py

    # OR pass image directly:
    python birth_certificate_ocr.py /path/to/certificate.jpg
"""

import google.generativeai as genai
import base64
import json
import io
import os
import sys
from pathlib import Path

# ══════════════════════════════════════════════════════════════════
#  CONFIGURATION  — set your key here OR use environment variable
# ══════════════════════════════════════════════════════════════════
GEMINI_API_KEY = os.environ.get("GEMINI_API_KEY", "YOUR_NEW_API_KEY_HERE")
GEMINI_MODEL   = "gemini-1.5-pro"   # Best vision + multilingual model


# ══════════════════════════════════════════════════════════════════
#  IMAGE PRE-PROCESSING
# ══════════════════════════════════════════════════════════════════

def preprocess_image(image_path: str) -> tuple:
    """
    Enhance image quality before OCR:
    - Upscale to min 1400px wide  (reveals fine Sinhala vowel marks)
    - Boost contrast              (ink vs paper separation)
    - Sharpen                     (Sinhala curves and stacked consonants)
    Returns: (image_bytes, mime_type)
    """
    try:
        from PIL import Image, ImageEnhance, ImageFilter

        img = Image.open(image_path).convert("RGB")
        w, h = img.size

        # Upscale small images so Sinhala strokes are visible
        if w < 1400:
            scale = 1400 / w
            img = img.resize((int(w * scale), int(h * scale)), Image.LANCZOS)

        # Greyscale for cleaner ink-on-paper contrast
        img = img.convert("L").convert("RGB")

        # Boost contrast
        img = ImageEnhance.Contrast(img).enhance(1.9)

        # Sharpen — critical for Sinhala vowel marks and stacked letters
        img = img.filter(ImageFilter.SHARPEN)
        img = ImageEnhance.Sharpness(img).enhance(2.2)

        buf = io.BytesIO()
        img.save(buf, format="JPEG", quality=95)
        print(f"   Image pre-processed: {w}x{h} -> {img.size[0]}x{img.size[1]}")
        return buf.getvalue(), "image/jpeg"

    except ImportError:
        print("   Pillow not found — using raw image. (pip install pillow for better results)")
        with open(image_path, "rb") as f:
            data = f.read()
        ext = Path(image_path).suffix.lower().lstrip(".")
        mt  = {"jpg": "image/jpeg", "jpeg": "image/jpeg",
               "png": "image/png",  "webp": "image/webp"}.get(ext, "image/jpeg")
        return data, mt


# ══════════════════════════════════════════════════════════════════
#  SYSTEM / PERSONA INSTRUCTION
# ══════════════════════════════════════════════════════════════════

SYSTEM_INSTRUCTION = """You are an elite OCR engine specialised in Sri Lankan government documents.

CAPABILITIES:
1. Sinhala script — handwritten (cursive/semi-cursive) AND printed
2. English — handwritten AND printed
3. Mixed Sinhala/English documents: birth certificates, marriage certificates, NIC forms

SINHALA HANDWRITING RULES:
- Recognise all 18 vowels: අ ආ ඇ ඈ ඉ ඊ උ ඌ ඍ එ ඒ ඓ ඔ ඕ ඖ
- Recognise all dependent vowel signs: ා ැ ෑ ි ී ු ූ ෘ ෙ ේ ෛ ො ෝ ෞ ෲ ෳ ්
- Recognise all 41 consonants and stacked/joined forms
- Distinguish lookalike pairs: ල/ළ, ණ/න, ට/ත, ඩ/ද, ශ/ෂ, ස/ශ
- Handle faded ink, rushed cursive, and mixed-script lines
- Always output correct Unicode (Sinhala block U+0D80–U+0DFF)

OUTPUT RULES:
- Return ONLY valid JSON — no markdown code fences, no explanation text
- Use null for any field that is blank, missing, or completely illegible
- Preserve original script (Sinhala text stays Sinhala, English stays English)"""


# ══════════════════════════════════════════════════════════════════
#  PROMPTS
# ══════════════════════════════════════════════════════════════════

PASS1_PROMPT = """
This image is a Sri Lanka REGISTER OF BIRTHS — Form B1 (High Reg. P & S.C.* 12/78).
It is a government printed form with HANDWRITTEN entries in Sinhala and/or English.

Extract every field using this exact form structure:

HEADER SECTION:
- Top-left: registration date (e.g. "Wednesday November 27, 2019")
- Below that: document reference number (format A/XXXXX)
- Right box: Registration B1 number, Book No., Entry No.
- Left column: District (දිස්ත්‍රික්කය) — handwritten value
- Right column: Division (කොට්ඨාශය) — handwritten value

FIELD 1 — Date and Place of Birth:
  "1. උපන් දිනය හා ස්ථානය / Date and place of birth"
  Two lines: (1) date of birth, (2) place of birth

FIELD 2 — Name:
  "2. නම / Name" — child's full name

FIELD 3 — Sex:
  "3. ස්ත්‍රී පුරුෂ භාවය / Sex"
  ස්ත්‍රී (Female) or පුරුෂ (Male)

FIELD 4 — Father's Details:
  "4. පියාගේ / Father's"
  4a) සම්පූර්ණ නම / full name (may span 2 lines)
  4b) උපන් දිනය / date of birth
  4c) උපන් ස්ථානය / place of birth
  4d) ජාතිය / race

FIELD 5 — Mother's Details:
  "5. මවගේ / Mother's"
  5a) සම්පූර්ණ නම / full name (may span 2 lines)
  5b) උපන් දිනය / date of birth
  5c) උපන් ස්ථානය / place of birth
  5d) ජාතිය / race
  5e) වයස / age

FIELD 6 — Were Parents Married?:
  "6. දෙමාපියන් විවාහකද? / Were parents married?"

FIELD 7 — Grandfather (if born in Sri Lanka):
  "7. ඉපදීම ලංකාවේ නම් සීයාගේ / If grandfather born in Sri Lanka"
  7a) සම්පූර්ණ නම / full name
  7b) උපන් වර්ෂය / year of birth
  7c) උපන් ස්ථානය / place of birth

Return ONLY this JSON:
{
  "document_type": "Sri Lanka Register of Births - Form B1",
  "registration_date": "",
  "document_number": "",
  "book_number": "",
  "entry_number": "",
  "header": {
    "district_sinhala": "",
    "district_english": "",
    "division_sinhala": "",
    "division_english": ""
  },
  "field_1_birth": {
    "date_of_birth": "",
    "place_of_birth_sinhala": "",
    "place_of_birth_english": ""
  },
  "field_2_name": {
    "child_name_sinhala": "",
    "child_name_english": ""
  },
  "field_3_sex": {
    "sex_sinhala": "",
    "sex_english": ""
  },
  "field_4_father": {
    "full_name_line1_sinhala": "",
    "full_name_line2_sinhala": "",
    "full_name_english": "",
    "date_of_birth": "",
    "place_of_birth_sinhala": "",
    "place_of_birth_english": "",
    "race_sinhala": "",
    "race_english": ""
  },
  "field_5_mother": {
    "full_name_line1_sinhala": "",
    "full_name_line2_sinhala": "",
    "full_name_english": "",
    "date_of_birth": "",
    "place_of_birth_sinhala": "",
    "place_of_birth_english": "",
    "race_sinhala": "",
    "race_english": "",
    "age": ""
  },
  "field_6_parents_married": {
    "answer_sinhala": "",
    "answer_english": ""
  },
  "field_7_grandfather": {
    "full_name_sinhala": "",
    "full_name_english": "",
    "year_of_birth": "",
    "place_of_birth_sinhala": "",
    "place_of_birth_english": ""
  }
}
"""

PASS2_PROMPT = """
This is a Sri Lanka birth certificate with HANDWRITTEN Sinhala entries.

Your SOLE task: transcribe every handwritten Sinhala word on the form.
Ignore printed form labels — extract ONLY the handwritten answers.

Pay special attention to:
- Vowel diacritics: ා ැ ෑ ි ී ු ූ ෘ ෙ ේ ො ෝ ෞ ්
- Stacked consonant clusters: e.g. ත්‍ව, ශ්‍ර, න්‍ද, ක්‍ෂ
- Similar-looking letters: ල vs ළ, ණ vs න, ට vs ත, ශ vs ෂ

Return ONLY this JSON (exact Sinhala Unicode):
{
  "hw_district": "",
  "hw_division": "",
  "hw_dob": "",
  "hw_pob": "",
  "hw_child_name": "",
  "hw_sex": "",
  "hw_father_name_full": "",
  "hw_father_dob": "",
  "hw_father_pob": "",
  "hw_father_race": "",
  "hw_mother_name_full": "",
  "hw_mother_dob": "",
  "hw_mother_pob": "",
  "hw_mother_race": "",
  "hw_mother_age": "",
  "hw_parents_married": "",
  "hw_grandfather_name": "",
  "hw_grandfather_yob": "",
  "hw_grandfather_pob": "",
  "hw_notes": ""
}
"""

PASS3_PROMPT = """
You are verifying OCR results from a Sri Lanka birth certificate.

READING A (structural pass):
{pass1}

READING B (Sinhala handwriting deep-pass):
{pass2}

Compare both readings field by field and produce the most accurate final result.
Rules:
1. If both agree → use that value
2. If they disagree → pick the more complete / correct Sinhala Unicode value
3. Fill any field one pass got right but the other missed
4. Fix obvious Unicode errors (missing vowel marks, wrong diacritics)

Return ONLY this final merged JSON:
{{
  "document_type": "Sri Lanka Register of Births - Form B1",
  "registration_date": "",
  "document_number": "",
  "book_number": "",
  "entry_number": "",
  "header": {{
    "district": "",
    "division": ""
  }},
  "field_1_birth": {{
    "date_of_birth": "",
    "place_of_birth": ""
  }},
  "field_2_name": {{
    "child_name": ""
  }},
  "field_3_sex": {{
    "sex": ""
  }},
  "field_4_father": {{
    "full_name": "",
    "date_of_birth": "",
    "place_of_birth": "",
    "race": ""
  }},
  "field_5_mother": {{
    "full_name": "",
    "date_of_birth": "",
    "place_of_birth": "",
    "race": "",
    "age": ""
  }},
  "field_6_parents_married": {{
    "answer": ""
  }},
  "field_7_grandfather": {{
    "full_name": "",
    "year_of_birth": "",
    "place_of_birth": ""
  }},
  "confidence_notes": ""
}}
"""


# ══════════════════════════════════════════════════════════════════
#  GEMINI API HELPERS
# ══════════════════════════════════════════════════════════════════

def _get_model() -> genai.GenerativeModel:
    """Initialise and return the Gemini model."""
    genai.configure(api_key=GEMINI_API_KEY)
    return genai.GenerativeModel(
        model_name=GEMINI_MODEL,
        system_instruction=SYSTEM_INSTRUCTION,
        generation_config=genai.GenerationConfig(
            temperature=0.1,        # Low temp = more deterministic OCR
            top_p=0.95,
            max_output_tokens=4096,
        )
    )


def _api_call_with_image(model, image_bytes: bytes,
                         mime_type: str, prompt: str) -> str:
    """Send image + text prompt to Gemini, return raw text."""
    image_part = {
        "mime_type": mime_type,
        "data": image_bytes,
    }
    response = model.generate_content([image_part, prompt])
    return response.text


def _api_call_text_only(model, prompt: str) -> str:
    """Send text-only prompt to Gemini (for Pass 3 merge)."""
    response = model.generate_content(prompt)
    return response.text


def _parse_json(raw: str) -> dict:
    """Parse JSON from Gemini response, stripping markdown fences if present."""
    text = raw.strip()
    # Strip ```json ... ``` fences
    if text.startswith("```"):
        parts = text.split("```")
        text = parts[1]
        if text.startswith("json"):
            text = text[4:]
        text = text.strip()
    try:
        return json.loads(text)
    except json.JSONDecodeError as e:
        return {"parse_error": str(e), "raw_response": raw}


# ══════════════════════════════════════════════════════════════════
#  MAIN OCR FUNCTION — 3-pass pipeline
# ══════════════════════════════════════════════════════════════════

def ocr_birth_certificate(image_path: str) -> dict:
    """
    3-Pass OCR pipeline for Sri Lanka birth certificates using Gemini.

    Pass 1 — Full structural field extraction (Sinhala + English)
    Pass 2 — Dedicated Sinhala handwriting deep-pass
    Pass 3 — Verification & merge (Gemini compares Pass1 vs Pass2)

    Returns final verified dict with all fields.
    """
    model = _get_model()

    print("\n[Step 1/4] Pre-processing image ...")
    img_bytes, mime_type = preprocess_image(image_path)

    print("[Step 2/4] Pass 1 — Full structural extraction ...")
    raw1  = _api_call_with_image(model, img_bytes, mime_type, PASS1_PROMPT)
    pass1 = _parse_json(raw1)

    print("[Step 3/4] Pass 2 — Sinhala handwriting deep-pass ...")
    raw2  = _api_call_with_image(model, img_bytes, mime_type, PASS2_PROMPT)
    pass2 = _parse_json(raw2)

    print("[Step 4/4] Pass 3 — Verification & merge ...")
    pass3_prompt = PASS3_PROMPT.format(
        pass1=json.dumps(pass1, ensure_ascii=False, indent=2),
        pass2=json.dumps(pass2, ensure_ascii=False, indent=2),
    )
    raw3  = _api_call_text_only(model, pass3_prompt)
    final = _parse_json(raw3)

    # Attach debug info for auditing
    final["_debug"] = {
        "pass1_structural":           pass1,
        "pass2_sinhala_handwriting":  pass2,
    }
    return final


# ══════════════════════════════════════════════════════════════════
#  PRETTY PRINTER
# ══════════════════════════════════════════════════════════════════

FIELD_LABELS = {
    "header":                  "DOCUMENT HEADER",
    "field_1_birth":           "FIELD 1 — Date & Place of Birth | උපන් දිනය හා ස්ථානය",
    "field_2_name":            "FIELD 2 — Name | නම",
    "field_3_sex":             "FIELD 3 — Sex | ස්ත්‍රී පුරුෂ භාවය",
    "field_4_father":          "FIELD 4 — Father | පියාගේ",
    "field_5_mother":          "FIELD 5 — Mother | මවගේ",
    "field_6_parents_married": "FIELD 6 — Were Parents Married? | දෙමාපියන් විවාහකද?",
    "field_7_grandfather":     "FIELD 7 — Grandfather | සීයාගේ",
}

SECTION_ORDER = [
    "header", "field_1_birth", "field_2_name", "field_3_sex",
    "field_4_father", "field_5_mother",
    "field_6_parents_married", "field_7_grandfather",
]


def print_results(data: dict):
    W   = 68
    DIV = "=" * W
    SEP = "-" * W

    print(f"\n{DIV}")
    print("     SRI LANKA BIRTH CERTIFICATE — OCR RESULTS (Gemini)")
    print(f"{DIV}")

    for k in ("document_type", "registration_date", "document_number",
              "book_number", "entry_number"):
        v = data.get(k)
        if v:
            print(f"  {k.replace('_',' ').title():<28}: {v}")

    print(SEP)

    for sec in SECTION_ORDER:
        val = data.get(sec)
        if not val or not isinstance(val, dict):
            continue
        label = FIELD_LABELS.get(sec, sec)
        print(f"\n  [{label}]")
        for k, v in val.items():
            if v:
                print(f"    {k.replace('_',' ').title():<35}: {v}")

    notes = data.get("confidence_notes")
    if notes:
        print(f"\n  [Confidence Notes]\n    {notes}")

    # Show raw Sinhala handwriting pass
    hw = data.get("_debug", {}).get("pass2_sinhala_handwriting", {})
    if hw and not hw.get("parse_error"):
        print(f"\n{SEP}")
        print("  SINHALA HANDWRITING RAW PASS (Pass 2):")
        print(SEP)
        for k, v in hw.items():
            if v:
                print(f"  {k:<35}: {v}")

    print(f"\n{DIV}\n")


# ══════════════════════════════════════════════════════════════════
#  ENTRY POINT
# ══════════════════════════════════════════════════════════════════

if __name__ == "__main__":

    # ── Validate API key ──────────────────────────────────────────
    if GEMINI_API_KEY == "YOUR_NEW_API_KEY_HERE":
        print("ERROR: Set GEMINI_API_KEY environment variable or edit GEMINI_API_KEY in this script.")
        print("  export GEMINI_API_KEY='AIzaSyCoM6Mo1FGu4MaH8MQfYa6vM4W8rLhyv2U'")
        sys.exit(1)

    # ── Image path (command-line arg or default) ──────────────────
    IMAGE_PATH = sys.argv[1] if len(sys.argv) > 1 else "/Users/sathyas/Documents/Project/janashakthi/CamScanner 22-11-2025 06.24_1.jpg"

    if not Path(IMAGE_PATH).exists():
        print(f"ERROR: Image not found: {IMAGE_PATH}")
        print("  Usage: python birth_certificate_ocr.py /path/to/certificate.jpg")
        sys.exit(1)

    # ── Run 3-pass OCR ────────────────────────────────────────────
    result = ocr_birth_certificate(IMAGE_PATH)

    # ── Display ───────────────────────────────────────────────────
    print_results(result)

    stem = Path(IMAGE_PATH).stem

    # ── Save full JSON (Sinhala Unicode preserved) ────────────────
    json_out = stem + "_ocr_result.json"
    with open(json_out, "w", encoding="utf-8") as f:
        json.dump(result, f, ensure_ascii=False, indent=2)
    print(f"Full JSON saved    -> {json_out}")

    # ── Save clean Sinhala text file ──────────────────────────────
    si_out = stem + "_sinhala_text.txt"
    with open(si_out, "w", encoding="utf-8") as f:
        f.write("Sri Lanka Birth Certificate — Sinhala OCR Output\n")
        f.write("=" * 50 + "\n\n")
        for section in SECTION_ORDER:
            sec_data = result.get(section, {})
            if isinstance(sec_data, dict):
                f.write(f"\n[{FIELD_LABELS.get(section, section)}]\n")
                for k, v in sec_data.items():
                    if v:
                        f.write(f"  {k}: {v}\n")
        hw = result.get("_debug", {}).get("pass2_sinhala_handwriting", {})
        if hw and not hw.get("parse_error"):
            f.write("\n\n[RAW SINHALA HANDWRITING PASS]\n")
            for k, v in hw.items():
                if v:
                    f.write(f"  {k}: {v}\n")

    print(f"Sinhala text saved -> {si_out}")
    print("\nDone!\n")