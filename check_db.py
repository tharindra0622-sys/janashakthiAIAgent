"""
Janashakthi DB Checker
──────────────────────
Run:  python3 check_db.py
Opens a mini web UI at http://localhost:9999
showing live customers, service requests, and documents.
"""

import json
import os
import sqlite3
from http.server import BaseHTTPRequestHandler, HTTPServer
from urllib.parse import urlparse, parse_qs

# ── Auto-locate the database ─────────────────────────────────────────────────
SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
CANDIDATE_PATHS = [
    os.path.join(SCRIPT_DIR, "janashakthi", "database", "janashakthi.db"),
    os.path.join(SCRIPT_DIR, "database", "janashakthi.db"),
    os.path.join(SCRIPT_DIR, "janashakthi.db"),
]
DB_PATH = next((p for p in CANDIDATE_PATHS if os.path.exists(p)), None)
PORT = 9999


def query(sql, params=()):
    if not DB_PATH:
        return []
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    rows = conn.execute(sql, params).fetchall()
    conn.close()
    return [dict(r) for r in rows]


def get_data():
    customers = query("""
        SELECT c.id, c.nic, c.full_name, c.date_of_birth, c.phone, c.email,
               GROUP_CONCAT(p.policy_number, ', ') AS policies
        FROM customers c
        LEFT JOIN policies p ON p.customer_id = c.id
        GROUP BY c.id
        ORDER BY c.id
    """)

    requests = query("""
        SELECT sr.id, sr.service_type, sr.status,
               sr.created_at, sr.updated_at,
               sr.ai_notes, sr.underwriter_notes,
               sr.policy_number,
               c.full_name, c.nic
        FROM service_requests sr
        JOIN customers c ON c.id = sr.customer_id
        ORDER BY sr.updated_at DESC
        LIMIT 50
    """)

    docs = query("""
        SELECT d.id, d.request_id, d.doc_type, d.ai_verified,
               d.uploaded_at, d.ai_feedback
        FROM documents d
        ORDER BY d.uploaded_at DESC
        LIMIT 50
    """)

    return {"customers": customers, "requests": requests, "docs": docs}


HTML = r"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>Janashakthi — DB Checker</title>
<link href="https://fonts.googleapis.com/css2?family=JetBrains+Mono:wght@400;600&family=Syne:wght@600;800&display=swap" rel="stylesheet">
<style>
  :root {
    --bg:       #0b0f1a;
    --surface:  #111827;
    --border:   #1e2d40;
    --gold:     #c9973a;
    --gold2:    #f0c060;
    --green:    #22c55e;
    --red:      #ef4444;
    --blue:     #38bdf8;
    --muted:    #6b7280;
    --text:     #e2e8f0;
    --auto:     #a78bfa;
  }
  * { box-sizing: border-box; margin: 0; padding: 0; }
  body {
    background: var(--bg);
    color: var(--text);
    font-family: 'JetBrains Mono', monospace;
    font-size: 13px;
    min-height: 100vh;
  }

  /* ── Header ── */
  header {
    background: var(--surface);
    border-bottom: 1px solid var(--border);
    padding: 1rem 2rem;
    display: flex;
    align-items: center;
    gap: 1rem;
    position: sticky; top: 0; z-index: 100;
  }
  header h1 {
    font-family: 'Syne', sans-serif;
    font-size: 1.1rem;
    font-weight: 800;
    color: var(--gold2);
    letter-spacing: 0.05em;
  }
  .db-path {
    font-size: 0.7rem;
    color: var(--muted);
    margin-left: auto;
    max-width: 400px;
    overflow: hidden;
    text-overflow: ellipsis;
    white-space: nowrap;
  }
  .refresh-btn {
    background: var(--gold);
    color: #000;
    border: none;
    border-radius: 6px;
    padding: 6px 14px;
    font-family: 'JetBrains Mono', monospace;
    font-weight: 600;
    font-size: 0.75rem;
    cursor: pointer;
    transition: opacity 0.15s;
  }
  .refresh-btn:hover { opacity: 0.85; }

  /* ── Tabs ── */
  .tabs {
    display: flex;
    gap: 0;
    border-bottom: 1px solid var(--border);
    padding: 0 2rem;
    background: var(--surface);
  }
  .tab {
    padding: 0.7rem 1.4rem;
    cursor: pointer;
    font-size: 0.75rem;
    font-weight: 600;
    color: var(--muted);
    border-bottom: 2px solid transparent;
    transition: all 0.15s;
    letter-spacing: 0.05em;
    text-transform: uppercase;
  }
  .tab:hover { color: var(--text); }
  .tab.active { color: var(--gold2); border-bottom-color: var(--gold); }

  /* ── Content ── */
  .content { padding: 1.5rem 2rem; }
  .panel { display: none; }
  .panel.active { display: block; }

  /* ── Stats bar ── */
  .stats {
    display: flex;
    gap: 1rem;
    margin-bottom: 1.5rem;
    flex-wrap: wrap;
  }
  .stat {
    background: var(--surface);
    border: 1px solid var(--border);
    border-radius: 10px;
    padding: 0.75rem 1.2rem;
    min-width: 120px;
  }
  .stat-label { font-size: 0.65rem; color: var(--muted); text-transform: uppercase; letter-spacing: 0.08em; }
  .stat-value { font-size: 1.5rem; font-weight: 600; margin-top: 2px; }
  .stat-value.gold    { color: var(--gold2); }
  .stat-value.green   { color: var(--green); }
  .stat-value.red     { color: var(--red); }
  .stat-value.blue    { color: var(--blue); }
  .stat-value.purple  { color: var(--auto); }

  /* ── Search box ── */
  .search-wrap { margin-bottom: 1rem; }
  .search-wrap input {
    background: var(--surface);
    border: 1px solid var(--border);
    border-radius: 8px;
    color: var(--text);
    font-family: 'JetBrains Mono', monospace;
    font-size: 0.8rem;
    padding: 8px 14px;
    width: 320px;
    outline: none;
    transition: border-color 0.15s;
  }
  .search-wrap input:focus { border-color: var(--gold); }
  .search-wrap input::placeholder { color: var(--muted); }

  /* ── Table ── */
  .table-wrap { overflow-x: auto; border-radius: 10px; border: 1px solid var(--border); }
  table { width: 100%; border-collapse: collapse; }
  thead th {
    background: #161d2e;
    padding: 10px 14px;
    text-align: left;
    font-size: 0.65rem;
    text-transform: uppercase;
    letter-spacing: 0.08em;
    color: var(--muted);
    border-bottom: 1px solid var(--border);
    white-space: nowrap;
  }
  tbody tr { border-bottom: 1px solid var(--border); transition: background 0.1s; }
  tbody tr:last-child { border-bottom: none; }
  tbody tr:hover { background: rgba(201,151,58,0.04); }
  td {
    padding: 10px 14px;
    vertical-align: top;
    line-height: 1.5;
  }
  .mono { font-family: 'JetBrains Mono', monospace; }
  .dim  { color: var(--muted); font-size: 0.78rem; }

  /* ── Status badges ── */
  .badge {
    display: inline-block;
    padding: 2px 8px;
    border-radius: 20px;
    font-size: 0.65rem;
    font-weight: 700;
    text-transform: uppercase;
    letter-spacing: 0.06em;
    white-space: nowrap;
  }
  .badge-auto     { background: rgba(167,139,250,0.15); color: var(--auto);  border: 1px solid rgba(167,139,250,0.3); }
  .badge-approved { background: rgba(34,197,94,0.12);  color: var(--green); border: 1px solid rgba(34,197,94,0.25); }
  .badge-rejected { background: rgba(239,68,68,0.12);  color: var(--red);   border: 1px solid rgba(239,68,68,0.25); }
  .badge-review   { background: rgba(56,189,248,0.12); color: var(--blue);  border: 1px solid rgba(56,189,248,0.25); }
  .badge-pending  { background: rgba(107,114,128,0.15);color: var(--muted); border: 1px solid rgba(107,114,128,0.3); }
  .badge-verified   { background: rgba(34,197,94,0.12);  color: var(--green); border: 1px solid rgba(34,197,94,0.25); }
  .badge-unverified { background: rgba(239,68,68,0.12);  color: var(--red);   border: 1px solid rgba(239,68,68,0.25); }

  /* ── Highlight changed ── */
  .changed { color: var(--gold2); font-weight: 600; }

  /* ── ai_notes expand ── */
  .notes-text {
    font-size: 0.72rem;
    color: var(--auto);
    margin-top: 4px;
    line-height: 1.4;
  }

  /* ── No DB warning ── */
  .warning {
    background: rgba(239,68,68,0.1);
    border: 1px solid rgba(239,68,68,0.3);
    border-radius: 10px;
    padding: 1.5rem;
    color: #fca5a5;
    font-size: 0.85rem;
    line-height: 1.8;
    margin-bottom: 1.5rem;
  }

  /* ── Empty ── */
  .empty { text-align:center; padding: 3rem; color: var(--muted); }

  /* ── Timestamp ── */
  .ts { font-size: 0.68rem; color: var(--muted); }
</style>
</head>
<body>

<header>
  <div style="font-size:1.4rem">🗄️</div>
  <h1>JANASHAKTHI — DB CHECKER</h1>
  <span class="db-path" id="dbPath">loading...</span>
  <button class="refresh-btn" onclick="loadData()">⟳ Refresh</button>
</header>

<div class="tabs">
  <div class="tab active" onclick="showTab('customers')">👤 Customers</div>
  <div class="tab" onclick="showTab('requests')">📋 Service Requests</div>
  <div class="tab" onclick="showTab('docs')">📄 Documents</div>
</div>

<div class="content">

  <!-- CUSTOMERS -->
  <div class="panel active" id="panel-customers">
    <div class="stats" id="stats-customers"></div>
    <div class="search-wrap">
      <input type="text" placeholder="Search by name, NIC, ID..." oninput="filterTable('tbl-customers', this.value)">
    </div>
    <div class="table-wrap">
      <table id="tbl-customers">
        <thead>
          <tr>
            <th>ID</th><th>NIC</th><th>Full Name</th><th>Date of Birth</th><th>Phone</th><th>Policies</th>
          </tr>
        </thead>
        <tbody id="tbody-customers">
          <tr><td colspan="6" class="empty">Loading...</td></tr>
        </tbody>
      </table>
    </div>
  </div>

  <!-- REQUESTS -->
  <div class="panel" id="panel-requests">
    <div class="stats" id="stats-requests"></div>
    <div class="search-wrap">
      <input type="text" placeholder="Search by ID, name, service, status..." oninput="filterTable('tbl-requests', this.value)">
    </div>
    <div class="table-wrap">
      <table id="tbl-requests">
        <thead>
          <tr>
            <th>Request ID</th><th>Customer</th><th>Policy</th><th>Service</th><th>Status</th><th>DB Update / Notes</th><th>Updated</th>
          </tr>
        </thead>
        <tbody id="tbody-requests">
          <tr><td colspan="7" class="empty">Loading...</td></tr>
        </tbody>
      </table>
    </div>
  </div>

  <!-- DOCUMENTS -->
  <div class="panel" id="panel-docs">
    <div class="stats" id="stats-docs"></div>
    <div class="search-wrap">
      <input type="text" placeholder="Search by request ID, doc type..." oninput="filterTable('tbl-docs', this.value)">
    </div>
    <div class="table-wrap">
      <table id="tbl-docs">
        <thead>
          <tr>
            <th>Doc ID</th><th>Request ID</th><th>Doc Type</th><th>AI Verified</th><th>Extracted Name</th><th>Extracted DOB</th><th>Uploaded</th>
          </tr>
        </thead>
        <tbody id="tbody-docs">
          <tr><td colspan="7" class="empty">Loading...</td></tr>
        </tbody>
      </table>
    </div>
  </div>

</div>

<script>
let allData = {};

function showTab(name) {
  document.querySelectorAll('.tab').forEach((t,i) => {
    const tabs = ['customers','requests','docs'];
    t.classList.toggle('active', tabs[i] === name);
  });
  document.querySelectorAll('.panel').forEach(p => p.classList.remove('active'));
  document.getElementById('panel-' + name).classList.add('active');
}

function statusBadge(s) {
  const cls = s === 'Auto-Approved' ? 'badge-auto' :
              s === 'Approved'      ? 'badge-approved' :
              s === 'Rejected'      ? 'badge-rejected' :
              s === 'Under Review'  ? 'badge-review' : 'badge-pending';
  return `<span class="badge ${cls}">${s}</span>`;
}

function serviceLabel(s) {
  const m = {
    name_change: 'Name Change', age_alteration: 'Age Alteration',
    premium_mode_change: 'Payment Mode', increase_benefits: 'Increase Benefits'
  };
  const cat = {
    name_change:'non-fin', age_alteration:'non-fin',
    premium_mode_change:'financial', increase_benefits:'financial'
  };
  const catColor = cat[s] === 'non-fin' ? 'color:#22c55e' : 'color:#f59e0b';
  return `<div>${m[s]||s}</div><div class="dim" style="${catColor}">${cat[s]||''}</div>`;
}

function fmt(dt) {
  if (!dt) return '<span class="dim">—</span>';
  return `<span class="ts">${dt.replace('T',' ').substring(0,16)}</span>`;
}

function extractFromFeedback(fb) {
  if (!fb) return {name: null, dob: null};
  try {
    const d = typeof fb === 'string' ? JSON.parse(fb) : fb;
    const idata = d.identity_data || d;
    const fn = idata.full_name;
    let name = null;
    if (fn && typeof fn === 'object') {
      name = fn.english || fn.sinhala || fn.tamil || null;
    } else if (typeof fn === 'string') {
      name = fn;
    }
    const dob = idata.date_of_birth || null;
    return { name, dob };
  } catch { return {name:null, dob:null}; }
}

function renderCustomers(customers) {
  const tbody = document.getElementById('tbody-customers');
  if (!customers.length) { tbody.innerHTML = '<tr><td colspan="6" class="empty">No customers found.</td></tr>'; return; }

  tbody.innerHTML = customers.map(c => `
    <tr>
      <td class="mono dim">${c.id}</td>
      <td class="mono" style="color:var(--blue)">${c.nic}</td>
      <td><strong class="changed">${c.full_name}</strong></td>
      <td class="mono">${c.date_of_birth||'—'}</td>
      <td class="dim">${c.phone||'—'}</td>
      <td class="dim" style="font-size:0.75rem">${c.policies||'—'}</td>
    </tr>
  `).join('');

  document.getElementById('stats-customers').innerHTML = `
    <div class="stat"><div class="stat-label">Total Customers</div><div class="stat-value gold">${customers.length}</div></div>
  `;
}

function renderRequests(requests) {
  const tbody = document.getElementById('tbody-requests');
  if (!requests.length) { tbody.innerHTML = '<tr><td colspan="7" class="empty">No requests found.</td></tr>'; return; }

  const counts = {auto:0, approved:0, review:0, rejected:0, pending:0};
  requests.forEach(r => {
    if (r.status==='Auto-Approved') counts.auto++;
    else if (r.status==='Approved') counts.approved++;
    else if (r.status==='Under Review') counts.review++;
    else if (r.status==='Rejected') counts.rejected++;
    else counts.pending++;
  });

  tbody.innerHTML = requests.map(r => {
    const notes = r.ai_notes
      ? `<div class="notes-text">⚡ ${r.ai_notes}</div>`
      : (r.underwriter_notes ? `<div class="notes-text dim">📝 ${r.underwriter_notes}</div>` : '<span class="dim">—</span>');
    return `
      <tr>
        <td><strong style="color:var(--gold2)">#${r.id}</strong></td>
        <td>${r.full_name}<br><span class="dim">${r.nic}</span></td>
        <td class="mono dim">${r.policy_number}</td>
        <td>${serviceLabel(r.service_type)}</td>
        <td>${statusBadge(r.status)}</td>
        <td style="max-width:300px">${notes}</td>
        <td>${fmt(r.updated_at)}</td>
      </tr>
    `;
  }).join('');

  document.getElementById('stats-requests').innerHTML = `
    <div class="stat"><div class="stat-label">⚡ Auto-Approved</div><div class="stat-value purple">${counts.auto}</div></div>
    <div class="stat"><div class="stat-label">✅ Approved</div><div class="stat-value green">${counts.approved}</div></div>
    <div class="stat"><div class="stat-label">🔍 Under Review</div><div class="stat-value blue">${counts.review}</div></div>
    <div class="stat"><div class="stat-label">❌ Rejected</div><div class="stat-value red">${counts.rejected}</div></div>
    <div class="stat"><div class="stat-label">⏳ Pending</div><div class="stat-value" style="color:var(--muted)">${counts.pending}</div></div>
  `;
}

function renderDocs(docs) {
  const tbody = document.getElementById('tbody-docs');
  if (!docs.length) { tbody.innerHTML = '<tr><td colspan="7" class="empty">No documents found.</td></tr>'; return; }

  let verified = 0;
  tbody.innerHTML = docs.map(d => {
    if (d.ai_verified) verified++;
    const vBadge = d.ai_verified
      ? '<span class="badge badge-verified">✓ Verified</span>'
      : '<span class="badge badge-unverified">✗ Failed</span>';
    const ex = extractFromFeedback(d.ai_feedback);
    return `
      <tr>
        <td class="mono dim">${d.id}</td>
        <td><strong style="color:var(--gold2)">#${d.request_id}</strong></td>
        <td style="color:var(--blue)">${d.doc_type}</td>
        <td>${vBadge}</td>
        <td>${ex.name ? `<span class="changed">${ex.name}</span>` : '<span class="dim">—</span>'}</td>
        <td class="mono dim">${ex.dob||'—'}</td>
        <td>${fmt(d.uploaded_at)}</td>
      </tr>
    `;
  }).join('');

  document.getElementById('stats-docs').innerHTML = `
    <div class="stat"><div class="stat-label">Total Docs</div><div class="stat-value gold">${docs.length}</div></div>
    <div class="stat"><div class="stat-label">AI Verified</div><div class="stat-value green">${verified}</div></div>
    <div class="stat"><div class="stat-label">Failed</div><div class="stat-value red">${docs.length - verified}</div></div>
  `;
}

function filterTable(tableId, query) {
  const q = query.toLowerCase();
  document.querySelectorAll(`#${tableId} tbody tr`).forEach(tr => {
    tr.style.display = tr.textContent.toLowerCase().includes(q) ? '' : 'none';
  });
}

async function loadData() {
  try {
    const res = await fetch('/api/data');
    const data = await res.json();
    allData = data;
    document.getElementById('dbPath').textContent = data.db_path || 'DB not found';
    renderCustomers(data.customers || []);
    renderRequests(data.requests || []);
    renderDocs(data.docs || []);
  } catch(e) {
    document.getElementById('dbPath').textContent = 'Error loading data';
  }
}

loadData();
setInterval(loadData, 10000); // auto-refresh every 10s
</script>
</body>
</html>
"""


class Handler(BaseHTTPRequestHandler):
    def log_message(self, fmt, *args):
        pass  # silence request logs

    def do_GET(self):
        path = urlparse(self.path).path

        if path == "/api/data":
            data = get_data()
            data["db_path"] = DB_PATH or "NOT FOUND — place check_db.py next to janashakthi/ folder"
            body = json.dumps(data).encode()
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", len(body))
            self.end_headers()
            self.wfile.write(body)

        else:
            body = HTML.encode()
            self.send_response(200)
            self.send_header("Content-Type", "text/html; charset=utf-8")
            self.send_header("Content-Length", len(body))
            self.end_headers()
            self.wfile.write(body)


if __name__ == "__main__":
    if not DB_PATH:
        print("⚠️  Database not found. Place check_db.py next to your janashakthi/ folder.")
        print("   Searched:", CANDIDATE_PATHS)
    else:
        print(f"✅ Database found: {DB_PATH}")

    print(f"\n🚀 DB Checker running at → http://localhost:{PORT}")
    print("   Press Ctrl+C to stop\n")

    server = HTTPServer(("localhost", PORT), Handler)
    server.serve_forever()
