# Janashakthi Insurance — AI-Powered Service Portal

## Project Structure

```
janashakthi/
│
├── run.py                          # ← Entry point: python run.py
├── requirements.txt
│
├── config/
│   ├── __init__.py
│   └── settings.py                 # Flask config (dev/prod), API keys, paths
│
├── app/
│   ├── __init__.py                 # App factory (create_app)
│   │
│   ├── models/
│   │   ├── __init__.py
│   │   ├── database.py             # SQLite setup, seed data, db_connection()
│   │   └── constants.py            # SERVICE_REQUIREMENTS, DOC_LABELS
│   │
│   ├── services/
│   │   ├── __init__.py
│   │   ├── ai_service.py           # Gemini: document verification + chat
│   │   ├── customer_service.py     # Customer lookup by NIC / policy number
│   │   └── request_service.py      # Create, submit, approve/reject requests
│   │
│   ├── routes/
│   │   ├── __init__.py
│   │   ├── views.py                # Serves HTML pages + uploads
│   │   ├── customer.py             # /api/identify, /api/chat, /api/request/*
│   │   ├── documents.py            # /api/document/upload
│   │   └── underwriter.py          # /api/underwriter/*
│   │
│   └── utils/
│       ├── __init__.py
│       └── helpers.py              # allowed_file(), save_uploaded_file(), success(), error()
│
├── templates/
│   ├── customer.html               # Customer chatbot portal
│   └── underwriter.html            # Underwriter dashboard
│
├── static/
│   ├── css/                        # (for future separated CSS)
│   ├── js/                         # (for future separated JS)
│   └── images/
│
├── database/
│   └── janashakthi.db              # SQLite DB (auto-created on first run)
│
└── uploads/                        # Uploaded documents (auto-created)
```

---

## Quick Start

### 1. Install dependencies
```bash
pip install -r requirements.txt
```

### 2. Run the server
```bash
python run.py
```

### 3. Access portals
| Portal | URL |
|--------|-----|
| Customer Chatbot | http://localhost:5000 |
| Underwriter Dashboard | http://localhost:5000/underwriter |

---

## API Reference

### Customer Endpoints (`/api/`)

| Method | Endpoint | Description |
|--------|----------|-------------|
| POST | `/api/identify` | Identify customer by NIC and/or policy number |
| POST | `/api/chat` | AI chat with customer (Gemini) |
| POST | `/api/request/create` | Create a new service request |
| POST | `/api/document/upload` | Upload & AI-verify a document |
| POST | `/api/request/submit` | Submit request for underwriter review |

### Underwriter Endpoints (`/api/underwriter/`)

| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/api/underwriter/requests?status=Under Review` | List requests by status |
| GET | `/api/underwriter/request/<id>` | Full request + document details |
| POST | `/api/underwriter/decide` | Approve or reject + update database |
| GET | `/api/underwriter/stats` | Dashboard statistics |

---

## Services & Document Requirements

| Service | Category | Mandatory | Identity (choose 1) | Optional |
|---------|----------|-----------|---------------------|---------|
| Name Change | Non-Financial | Request Letter | Birth Cert / NIC / Marriage Cert | — |
| Age Alteration | Non-Financial | Request Letter | Birth Cert / NIC / Marriage Cert | — |
| Change Payment Mode | Financial | Request Letter, Outstanding Bill | — | — |
| Increase of Benefits | Financial | Request Letter, PEP/DGF Form | — | Salary Slip, Bank Statement, Tax Cert, Audit Report |

---

## Test Accounts (pre-seeded)

| NIC | Full Name | Policy Numbers |
|-----|-----------|----------------|
| 881324008V | B.A.N.M. Balasooriya | LI42511344, LI44001241 |
| 971742534V | P.A.K.D. Fonseka | LI421775 |
| 756234521V | M.D. Samarawickrama | LI42514876, LI44101242 |
| 852341267V | K.L.S. Perera | LI43201234 |
| 902156789V | H.M.T. Dilrukshi | LI43301235 |
| 781234567V | R.M.N. Rathnayake | LI43401236 |
| 862345678V | S.P. Jayawardena | LI43501237 |
| 930123456V | A.B.C. Fernando | LI43601238 |
| 801234567V | D.M. Wickramasinghe | LI43701239 |
| 951234567V | N.P. Liyanage | LI43801240 |
