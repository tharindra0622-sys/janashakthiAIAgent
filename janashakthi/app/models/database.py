import sqlite3
from contextlib import contextmanager


def get_db(db_path):
    db = sqlite3.connect(db_path)
    db.row_factory = sqlite3.Row
    return db


@contextmanager
def db_connection(db_path):
    db = get_db(db_path)
    try:
        yield db
        db.commit()
    except Exception:
        db.rollback()
        raise
    finally:
        db.close()


def init_db(db_path):
    with db_connection(db_path) as db:
        db.executescript('''
            CREATE TABLE IF NOT EXISTS customers (
                id          TEXT PRIMARY KEY,
                nic         TEXT UNIQUE NOT NULL,
                full_name   TEXT NOT NULL,
                phone       TEXT,
                email       TEXT,
                address     TEXT,
                date_of_birth TEXT,
                created_at  TEXT DEFAULT CURRENT_TIMESTAMP
            );

            CREATE TABLE IF NOT EXISTS policies (
                id             TEXT PRIMARY KEY,
                policy_number  TEXT UNIQUE NOT NULL,
                customer_id    TEXT NOT NULL,
                plan           TEXT NOT NULL,
                branch         TEXT NOT NULL,
                status         TEXT DEFAULT "Active",
                premium_mode   TEXT DEFAULT "Monthly",
                sum_assured    REAL,
                start_date     TEXT,
                FOREIGN KEY (customer_id) REFERENCES customers(id)
            );

            CREATE TABLE IF NOT EXISTS service_requests (
                id                TEXT PRIMARY KEY,
                customer_id       TEXT,
                policy_number     TEXT,
                service_type      TEXT NOT NULL,
                status            TEXT DEFAULT "Pending",
                ai_notes          TEXT,
                underwriter_notes TEXT,
                created_at        TEXT DEFAULT CURRENT_TIMESTAMP,
                updated_at        TEXT DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (customer_id) REFERENCES customers(id)
            );

            CREATE TABLE IF NOT EXISTS documents (
                id          TEXT PRIMARY KEY,
                request_id  TEXT NOT NULL,
                doc_type    TEXT NOT NULL,
                file_path   TEXT NOT NULL,
                ai_verified INTEGER DEFAULT 0,
                ai_feedback TEXT,
                uploaded_at TEXT DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (request_id) REFERENCES service_requests(id)
            );
        ''')

        _seed_data(db)


# ─────────────────────────────────────────────────
# SEED DATA — 10 customers, 12 policies
# ─────────────────────────────────────────────────

CUSTOMERS = [
    ("C001", "881324008V", "B.A.N.M. Balasooriya",  "0712345678", "balasooriya@email.com", "No 15, Negombo",                              "1988-03-24"),
    ("C002", "971742534V", "P.A.K.D. Fonseka",      "0723456789", "fonseka@email.com",     "No 04, Meegalandiya, Makolagama, Oelgama",    "1997-06-22"),
    ("C003", "756234521V", "M.D. Samarawickrama",   "0734567890", "samara@email.com",      "No 25, 3rd Lane, Flower Road, Colombo 03",    "1975-09-15"),
    ("C004", "852341267V", "K.L.S. Perera",         "0745678901", "perera@email.com",      "No 45, Main Street, Kandy",                   "1985-11-30"),
    ("C005", "902156789V", "H.M.T. Dilrukshi",      "0756789012", "dilrukshi@email.com",   "No 328, Dambulla Road, Matale",               "1990-04-12"),
    ("C006", "781234567V", "R.M.N. Rathnayake",     "0767890123", "rathnayake@email.com",  "No 78, Galle Road, Matara",                   "1978-07-08"),
    ("C007", "862345678V", "S.P. Jayawardena",      "0778901234", "jayawardena@email.com", "No 12, Temple Road, Gampaha",                 "1986-02-19"),
    ("C008", "930123456V", "A.B.C. Fernando",       "0789012345", "fernando@email.com",    "No 90, Malabe Road, Athurugiriya",            "1993-08-25"),
    ("C009", "801234567V", "D.M. Wickramasinghe",   "0790123456", "wickrama@email.com",    "No 34, Station Road, Kurunegala",             "1980-12-05"),
    ("C010", "951234567V", "N.P. Liyanage",         "0701234567", "liyanage@email.com",    "No 56, Colombo Road, Negombo",                "1995-03-18"),
]

POLICIES = [
    ("P001", "LI42511344", "C001", "LI4", "NGHN1",      "Active", "Monthly",   500000, "2011-06-09"),
    ("P002", "LI421775",   "C002", "LI4", "HNW",        "Active", "Monthly",   300000, "2021-01-10"),
    ("P003", "LI42514876", "C003", "LI4", "Colombo",    "Active", "Quarterly", 750000, "2020-05-15"),
    ("P004", "LI43201234", "C004", "LI5", "Kandy",      "Active", "Monthly",   400000, "2019-08-20"),
    ("P005", "LI43301235", "C005", "LI4", "Matale",     "Active", "Annual",    600000, "2022-03-10"),
    ("P006", "LI43401236", "C006", "LI3", "Matara",     "Active", "Monthly",   250000, "2018-11-25"),
    ("P007", "LI43501237", "C007", "LI5", "Gampaha",    "Active", "Monthly",   550000, "2021-07-14"),
    ("P008", "LI43601238", "C008", "LI4", "Colombo",    "Active", "Quarterly", 450000, "2023-01-08"),
    ("P009", "LI43701239", "C009", "LI3", "Kurunegala", "Active", "Monthly",   350000, "2017-04-30"),
    ("P010", "LI43801240", "C010", "LI4", "Negombo",    "Active", "Monthly",   500000, "2022-09-18"),
    # Multi-policy customers
    ("P011", "LI44001241", "C001", "LI3", "NGHN1",      "Active", "Annual",    200000, "2015-03-12"),
    ("P012", "LI44101242", "C003", "LI5", "Colombo",    "Active", "Monthly",   800000, "2018-07-22"),
]


def _seed_data(db):
    for c in CUSTOMERS:
        db.execute(
            'INSERT OR IGNORE INTO customers (id,nic,full_name,phone,email,address,date_of_birth) VALUES (?,?,?,?,?,?,?)',
            c
        )
    for p in POLICIES:
        db.execute(
            'INSERT OR IGNORE INTO policies (id,policy_number,customer_id,plan,branch,status,premium_mode,sum_assured,start_date) VALUES (?,?,?,?,?,?,?,?,?)',
            p
        )
