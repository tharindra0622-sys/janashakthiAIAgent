# =============================================================================
#  JANASHAKTHI INSURANCE — SINHALA KEYWORD CLASSIFICATION SYSTEM
#
#  PIPELINE:
#  1. Gemini OCR  → extract all raw text (Sinhala + English)
#  2. Keyword scorer → count matches per service (threshold: 10%)
#  3. Gemini verifier → confirm using classification as a strong hint
#
#  REAL LETTER EVIDENCE:
#  From B.A.N.M. Balasooriya (LI42511344, 2025/12/15, Negombo Branch):
#    Subject: "ගෙවන ගෙවීම් ශ්‍රමය LI42511344 ගැන සංශෝධ"
#    Body:    ගෙවීම, රක්ෂණ ගෙවීම, කාර්තු, ගෙවූ, ගෙවන්නේ
#    Stamps:  NEGOMBO BRANCH RECEIVED, JANASHAKTHI INSURANCE PLC
#
#  KEY FINDING: Writers use "ශ්‍රමය" instead of "ක්‍රමය" for "mode"
#               "ගෙවීම් ශ්‍රමය" = "ගෙවීම් ක්‍රමය" = PAYMENT MODE
# =============================================================================

MATCH_THRESHOLD = 0.10   # 10% of keywords must match to classify

SINHALA_KEYWORDS = {

    # =========================================================================
    #  PREMIUM MODE CHANGE  (ගෙවීම් ක්‍රමය / ගෙවීම් ශ්‍රමය)
    #
    #  EXACT PHRASES FROM REAL LETTER:
    #   - "ගෙවන ගෙවීම් ශ්‍රමය"   ← subject line (ශ්‍රමය = handwritten ක්‍රමය)
    #   - "සංශෝධ"                ← short for සංශෝධනය (amendment)
    #   - "ගැන"                  ← regarding
    #   - "කාර්තු"               ← quarterly
    #   - "රක්ෂණ ගෙවීම"         ← insurance payment
    #   - "ගෙවූ", "ගෙවන", "ගෙවන්නේ"  ← payment action words
    #   - "ජනශක්ති රක්ෂා සමාගම"  ← company (රක්ෂා not රක්ෂණ)
    #   - "කළමනාකාරතුමා"         ← Dear Manager
    #   - "දු.අංකය"              ← phone abbreviation
    # =========================================================================
    "premium_mode_change": {
        "service_label": "Change Mode of Payment",

        "keywords": [
            # ── Exact phrases from real letter ───────────────────────
            "ගෙවන ගෙවීම් ශ්‍රමය",    # subject line — strongest signal
            "ගෙවීම් ශ්‍රමය",          # core variant
            "ගෙවීමේ ශ්‍රමය",
            "ගෙවීම් ශ්‍රම",
            "ශ්‍රමය",                  # standalone — strong in payment context
            "සංශෝධ",                   # short for සංශෝධනය (seen in subject)
            "ගැන සංශෝධ",              # "regarding amendment" — subject line
            "ගෙවීම් ශ්‍රමය LI",       # policy reference in subject

            # ── Standard correct spelling ─────────────────────────────
            "ගෙවීම් ක්‍රමය",
            "ගෙවීම් ක්‍රමය වෙනස්",
            "ගෙවීම් ක්‍රමය වෙනස් කිරීම",
            "ගෙවීම් ආකාරය",
            "ගෙවීම් ක්‍රම",
            "ගෙවීමේ ක්‍රමය",
            "ගෙවීම් රටාව",

            # ── Payment action words (from letter body) ───────────────
            "ගෙවීම",
            "ගෙවීමේ",
            "ගෙවිය",
            "ගෙවිය යුතු",
            "ගෙවූ",                    # seen in real letter
            "ගෙව්ව",
            "ගෙව්වේ",
            "ගෙවන",                    # seen in real letter
            "ගෙවනවා",
            "ගෙවන්න",
            "ගෙවන්නේ",                 # seen in real letter
            "රක්ෂණ ගෙවීම",             # seen in real letter body
            "රක්ෂා ගෙවීම",
            "රක්ෂන ගෙවීම",             # informal spelling variant

            # ── Frequency / mode words ────────────────────────────────
            "කාර්තු",                  # quarterly — seen in real letter
            "කාර්තුව",
            "කාර්තුමය",
            "ත්‍රෛමාසික",
            "ත්‍රෛමාසිකව",
            "මාසික",
            "මාසිකව",
            "වාර්ෂික",
            "වාර්ෂිකව",
            "අර්ධ වාර්ෂික",
            "ද්වි වාර්ෂික",

            # ── Insurance premium words ───────────────────────────────
            "ප්‍රිමියම්",
            "රක්ෂණ වාරිකය",
            "රක්ෂා වාරිකය",
            "රක්ෂණ වාරික",
            "වාරිකය",
            "වාරික",
            "ප්‍රිමියම් ගෙවීම",

            # ── Account / bill reference ──────────────────────────────
            "ගිණුම",
            "ගිණුම් අංකය",
            "ගිණුම් 01",
            "ගිණුම් 02",
            "ගිණුම් 03",
            "QKUR",
            "රිසිට්",
            "රිසිට්පත",
            "ගෙවීමේ රිසිට්පත",
            "බිල්",

            # ── Change / amendment action ─────────────────────────────
            "සංශෝධනය",
            "සංශෝධනය කිරීම",
            "වෙනස් කිරීම",
            "වෙනස් කර",
            "වෙනස් කරන",
            "ශ්‍රමය වෙනස්",
            "ක්‍රමය වෙනස්",
            "ආකාරය වෙනස්",
            "යාවත්කාලීන",

            # ── Salutation / formal letter words ─────────────────────
            "කළමනාකාරතුමා",            # seen in real letter
            "කළමනාකාරතුමිය",
            "කළමනාකාර",
            "ගරු",
            "ගරු කළමනාකාර",
            "ඉල්ලීම",
            "ඉල්ලා සිටිමි",
            "ඉල්ලුම්පත",
            "කරුණාකර",
            "ඉල්ලා",

            # ── Insurance company (both spellings used in real letters)
            "ජනශක්ති",
            "ජනශක්ති රක්ෂා",           # actual spelling in this letter
            "ජනශක්ති රක්ෂණ",
            "ජනශක්ති රක්ෂා සමාගම",    # actual spelling in this letter
            "ජනශක්ති රක්ෂණ සමාගම",
            "රක්ෂා සමාගම",
            "රක්ෂණ සමාගම",
            "රක්ෂා",
            "රක්ෂණ",
            "NSPS",
            "LI",

            # ── Letter close / sign-off ───────────────────────────────
            "ස්තුතියි",
            "ගෞරවයෙන්",
            "ඔබගේ විශ්වාසී",
            "විශ්වාසී",
            "අත්සන",
            "දිනය",
            "දු.අංකය",                 # seen in real letter (phone abbreviation)
            "දුරකථන",
        ],

        "english_keywords": [
            "premium mode", "premium mode change", "mode of payment",
            "payment mode", "monthly", "quarterly", "annual",
            "semi annual", "life servicing", "outstanding",
            "QKUR", "account", "payment", "received",
            "negombo", "branch", "janashakthi", "insurance",
            "LI42511344",
        ]
    },

    # =========================================================================
    #  NAME CHANGE  (නම වෙනස් කිරීම)
    # =========================================================================
    "name_change": {
        "service_label": "Name Change",

        "keywords": [
            # Core words
            "නම", "නම වෙනස්", "නම වෙනස් කිරීම",
            "නම සංශෝධනය", "නම නිවැරදි", "නම නිවැරදි කිරීම",
            "නම යාවත්කාලීන", "නම වෙනස් කරන",
            "නාමය", "නාමය වෙනස්", "නාම සංශෝධනය",

            # Identity document references
            "උප්පැන්නය", "ජනන සහතිකය",
            "විවාහ සහතිකය", "ජාතික හැඳුනුම්පත",
            "හැඳුනුම්පත", "සහතිකය",

            # Action words
            "වෙනස් කර", "වෙනස් කිරීමට",
            "සංශෝධනය කර", "නිවැරදි කර", "නිවැරදි කිරීමට",

            # Formal letter
            "ඉල්ලීම", "ඉල්ලුම්පත", "ගරු",
            "කරුණාකර", "ඉල්ලා සිටිමි", "කළමනාකාරතුමා",

            # Insurance
            "රක්ෂා", "රක්ෂණ",
            "ජනශක්ති", "ජනශක්ති රක්ෂා",
            "ජනශක්ති රක්ෂා සමාගම", "ජනශක්ති රක්ෂණ සමාගම",

            # Sign-off
            "ස්තුතියි", "ගෞරවයෙන්", "ඔබගේ විශ්වාසී",
            "දිනය", "අත්සන",
        ],

        "english_keywords": [
            "name change", "name correction", "name update",
            "change of name", "name amendment",
            "miscellaneous request", "life servicing", "janashakthi",
        ]
    },

    # =========================================================================
    #  AGE ALTERATION  (වයස නිවැරදි කිරීම)
    # =========================================================================
    "age_alteration": {
        "service_label": "Age Alteration",

        "keywords": [
            # Core words
            "වයස", "වයස නිවැරදි", "වයස නිවැරදි කිරීම",
            "වයස සංශෝධනය", "වයස් නිවැරදි",
            "ජන්ම දිනය", "ජන්ම දිනය නිවැරදි",
            "උපන් දිනය", "උපන් දිනය නිවැරදි",
            "ඉපදුණු දිනය", "ඉපදුණු", "උපන්", "උපත",

            # Document references
            "උප්පැන්නය", "ජනන සහතිකය",
            "ජාතික හැඳුනුම්පත", "හැඳුනුම්පත", "සහතිකය",

            # Action words
            "නිවැරදි කර", "නිවැරදි කිරීමට",
            "සංශෝධනය කර", "යාවත්කාලීන කර", "වෙනස් කිරීමට",

            # Formal letter
            "ඉල්ලීම", "ඉල්ලුම්පත", "ගරු",
            "කරුණාකර", "ඉල්ලා සිටිමි", "කළමනාකාරතුමා",

            # Insurance
            "රක්ෂා", "රක්ෂණ",
            "ජනශක්ති", "ජනශක්ති රක්ෂා",
            "ජනශක්ති රක්ෂා සමාගම", "ජනශක්ති රක්ෂණ සමාගම",

            # Sign-off
            "ස්තුතියි", "ගෞරවයෙන්", "ඔබගේ විශ්වාසී", "අත්සන",
        ],

        "english_keywords": [
            "age alteration", "age correction", "date of birth",
            "birth date", "dob", "age amendment",
            "miscellaneous request", "life servicing", "janashakthi",
        ]
    },

    # =========================================================================
    #  INCREASE OF BENEFITS  (ප්‍රතිලාභ වැඩි කිරීම)
    # =========================================================================
    "increase_benefits": {
        "service_label": "Increase of Benefits",

        "keywords": [
            # Core benefit words
            "ප්‍රතිලාභ", "ප්‍රතිලාභ වැඩි", "ප්‍රතිලාභ වැඩි කිරීම",
            "රක්ෂා ආවරණය", "ආවරණය වැඩි", "ආවරණය වැඩි කිරීම",
            "රක්ෂිත මුදල", "රක්ෂිත", "ජීවිත ආරක්ෂාව",
            "ආශ්‍රිත ප්‍රතිලාභ",

            # Income / financial
            "ආදායම", "ශ්‍රම ආදායම", "ආදායම් සහතිකය",
            "වැටුප", "වැටුප් රිසිට්", "වැටුප් විස්තර",
            "බැංකු ප්‍රකාශය", "බැංකු", "ලාභ", "ව්‍යාපාර",

            # Amount words
            "රු.", "රුපියල්", "ලක්ෂ", "මිලියන",

            # PEP / DGF
            "PEP", "DGF", "පෝරමය", "ආකෘති පත්‍රය", "සෞඛ්‍ය",

            # Formal letter
            "ඉල්ලීම", "ඉල්ලුම්පත", "ගරු",
            "කරුණාකර", "ඉල්ලා සිටිමි", "කළමනාකාරතුමා",

            # Insurance
            "රක්ෂා", "රක්ෂණ",
            "ජනශක්ති", "ජනශක්ති රක්ෂා",
            "ජනශක්ති රක්ෂා සමාගම", "ජනශක්ති රක්ෂණ සමාගම",

            # Sign-off
            "ස්තුතියි", "ගෞරවයෙන්", "ඔබගේ විශ්වාසී",
            "අත්සන", "ඉල්ලා සිටිමි",
        ],

        "english_keywords": [
            "increase of benefits", "sum assured", "coverage increase",
            "benefit enhancement", "PEP", "DGF",
            "life servicing", "salary", "income", "bank statement",
            "miscellaneous request", "janashakthi",
        ]
    },
}


# =============================================================================
#  GENERAL LETTER KEYWORDS
#  2+ matches = this document is a Janashakthi letter
# =============================================================================

GENERAL_LETTER_KEYWORDS = [
    # Company name — both spellings used in real letters
    "ජනශක්ති",
    "ජනශක්ති රක්ෂා",
    "ජනශක්ති රක්ෂණ",
    "ජනශක්ති රක්ෂා සමාගම",
    "ජනශක්ති රක්ෂණ සමාගම",
    "රක්ෂා සමාගම",
    "රක්ෂණ සමාගම",
    "රක්ෂා",
    "රක්ෂණ",

    # Salutation / letter structure
    "ඉල්ලීම",
    "ඉල්ලීමේ ලිපිය",
    "ඉල්ලුම්පත",
    "ගරු",
    "ගරු කළමනාකාර",
    "කළමනාකාර",
    "කළමනාකාරතුමා",
    "කළමනාකාරතුමිය",

    # Policy / document references
    "LI",
    "NSPS",
    "පොලිසිය",
    "ගිවිසුම",

    # Sign-off words
    "අත්සන",
    "දිනය",
    "ස්තුතියි",
    "ගෞරවයෙන්",
    "කරුණාකර",
    "ඉල්ලා සිටිමි",
    "ඔබගේ විශ්වාසී",

    # Common abbreviations in real letters
    "දු.අංකය",
    "දුරකථන",
]


# =============================================================================
#  IDENTITY DOCUMENT KEYWORDS
# =============================================================================

IDENTITY_DOC_KEYWORDS = {
    "nic": [
        "ජාතික හැඳුනුම්පත", "හැඳුනුම්පත",
        "NIC", "national identity", "identity card",
    ],
    "birth_certificate": [
        "උප්පැන්නය", "ජනන සහතිකය",
        "birth certificate", "උපන්", "ඉපදුණු",
    ],
    "marriage_certificate": [
        "විවාහ සහතිකය", "විවාහ", "marriage certificate",
    ],
}


# =============================================================================
#  SERVICE REQUIREMENTS
# =============================================================================

SERVICE_REQUIREMENTS = {
    "name_change": {
        "label":         "Name Change",
        "category":      "non_financial",
        "mandatory":     ["request_letter"],
        "identity_docs": ["birth_certificate", "nic", "marriage_certificate"],
        "optional":      [],
    },
    "age_alteration": {
        "label":         "Age Alteration",
        "category":      "non_financial",
        "mandatory":     ["request_letter"],
        "identity_docs": ["birth_certificate", "nic", "marriage_certificate"],
        "optional":      [],
    },
    "premium_mode_change": {
        "label":         "Change Mode of Payment",
        "category":      "financial",
        "mandatory":     ["request_letter", "outstanding_payment"],
        "identity_docs": [],
        "optional":      [],
    },
    "increase_benefits": {
        "label":         "Increase of Benefits",
        "category":      "financial",
        "mandatory":     ["request_letter", "pep_dgf_form"],
        "identity_docs": [],
        "optional":      ["salary_slip", "bank_statement",
                          "income_tax_certificate", "annual_audit_report"],
    },
}

DOC_LABELS = {
    "request_letter":         "Customer Request Letter",
    "birth_certificate":      "Birth Certificate",
    "nic":                    "National Identity Card (NIC)",
    "marriage_certificate":   "Marriage Certificate",
    "outstanding_payment":    "Outstanding Payment Bill",
    "pep_dgf_form":           "PEP / DGF Form",
    "salary_slip":            "Salary Slip",
    "bank_statement":         "Bank Statement",
    "income_tax_certificate": "Income Tax Certificate",
    "annual_audit_report":    "Annual Audit Report",
}

ALLOWED_EXTENSIONS = {'pdf', 'jpg', 'jpeg', 'png'}

MIME_MAP = {
    '.jpg':  'image/jpeg',
    '.jpeg': 'image/jpeg',
    '.png':  'image/png',
    '.pdf':  'application/pdf',
}