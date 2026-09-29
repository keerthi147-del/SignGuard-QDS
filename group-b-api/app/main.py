"""
Group B -- API for the Quantum-Inspired Cyber Threat Detection framework
(teleportation-based Quantum Digital Signatures).

Run:
    pip install -r ../requirements.txt
    python main.py

Interactive docs (hand-built, no external deps):
    http://localhost:5000/docs
"""
import hashlib, os, re, secrets, sqlite3, time, json

from flask import Flask, jsonify, request, g, send_from_directory
from werkzeug.security import generate_password_hash, check_password_hash

from qds_core import (run_protocol, sign_document, verify_document,
                      state_to_json, state_from_json)

BASE = os.path.dirname(os.path.abspath(__file__))
DB = os.path.join(BASE, "..", "signguard_qds_v2.db")
WEB = os.path.join(BASE, "..", "..", "group-c-dashboard")
SESSION_DAYS = 7
FAILS = {}  # email -> [timestamps] of recent failed logins

app = Flask(__name__)
app.config["MAX_CONTENT_LENGTH"] = 25 * 1024 * 1024  # 25 MB uploads


@app.after_request
def add_cors(resp):
    resp.headers["Access-Control-Allow-Origin"] = "*"
    resp.headers["Access-Control-Allow-Headers"] = "Content-Type, X-Token"
    resp.headers["Access-Control-Allow-Methods"] = "GET, POST, OPTIONS"
    return resp


@app.route("/api/<path:_>", methods=["OPTIONS"])
def cors_preflight(_):
    return "", 204


def db():
    c = sqlite3.connect(DB)
    c.row_factory = sqlite3.Row
    return c


with db() as c:
    c.executescript("""
    CREATE TABLE IF NOT EXISTS users(id INTEGER PRIMARY KEY AUTOINCREMENT, email TEXT UNIQUE,
        username TEXT UNIQUE, pw TEXT, created REAL);
    CREATE TABLE IF NOT EXISTS sessions(token TEXT PRIMARY KEY, user_id INTEGER, expires REAL);
    CREATE TABLE IF NOT EXISTS runs(id INTEGER PRIMARY KEY AUTOINCREMENT, ts REAL, user_id INTEGER,
        scenario TEXT, n_qubits INTEGER, threshold REAL, mismatches INTEGER, mismatch_rate REAL,
        decision TEXT, forgery_probability REAL, sample TEXT);
    CREATE TABLE IF NOT EXISTS signatures(id TEXT PRIMARY KEY, user_id INTEGER, filename TEXT,
        doc_hash TEXT, nonce TEXT, n_qubits INTEGER, threshold REAL, qubits TEXT, created REAL);
    CREATE TABLE IF NOT EXISTS verifications(id INTEGER PRIMARY KEY AUTOINCREMENT, sig_id TEXT,
        verifier_id INTEGER, filename TEXT, doc_hash TEXT, mismatch_rate REAL, decision TEXT, ts REAL);
    """)


@app.before_request
def require_token():
    open_paths = ("/api/login", "/api/signup")
    if request.method == "OPTIONS" or not request.path.startswith("/api/") or request.path in open_paths:
        return
    with db() as c:
        row = c.execute("""SELECT u.id, u.email, u.username FROM sessions s JOIN users u ON u.id=s.user_id
                           WHERE s.token=? AND s.expires>?""",
                        (request.headers.get("X-Token", ""), time.time())).fetchone()
    if not row:
        return jsonify(error="Please log in again."), 401
    g.user = dict(row)


def start_session(c, user_id):
    token = secrets.token_hex(24)
    c.execute("INSERT INTO sessions VALUES(?,?,?)", (token, user_id, time.time() + SESSION_DAYS * 86400))
    return token


@app.post("/api/signup")
def signup():
    d = request.json or {}
    email, username, pw = (d.get("email") or "").strip().lower(), (d.get("username") or "").strip(), d.get("password") or ""
    if not re.fullmatch(r"[^@\s]+@[^@\s]+\.[^@\s]+", email):
        return jsonify(error="Enter a valid email address."), 400
    if not re.fullmatch(r"[A-Za-z0-9_.]{3,20}", username):
        return jsonify(error="Username must be 3-20 letters, numbers, dots or underscores."), 400
    if len(pw) < 8:
        return jsonify(error="Password must be at least 8 characters."), 400
    try:
        with db() as c:
            cur = c.execute("INSERT INTO users(email,username,pw,created) VALUES(?,?,?,?)",
                            (email, username, generate_password_hash(pw), time.time()))
            token = start_session(c, cur.lastrowid)
    except sqlite3.IntegrityError:
        return jsonify(error="That email or username is already taken."), 409
    return jsonify(token=token, user=dict(username=username, email=email))


@app.post("/api/login")
def login():
    d = request.json or {}
    ident = (d.get("email") or "").strip().lower()  # email OR username
    now = time.time()
    FAILS[ident] = [t for t in FAILS.get(ident, []) if now - t < 300]
    if len(FAILS[ident]) >= 5:
        return jsonify(error="Too many attempts. Try again in a few minutes."), 429
    with db() as c:
        u = c.execute("SELECT * FROM users WHERE lower(email)=? OR lower(username)=?", (ident, ident)).fetchone()
        if not u or not check_password_hash(u["pw"], str(d.get("password") or "")):
            FAILS[ident].append(now)
            return jsonify(error="Wrong username or password."), 401
        token = start_session(c, u["id"])
    return jsonify(token=token, user=dict(username=u["username"], email=u["email"]))


@app.get("/api/me")
def me():
    return jsonify(user=g.user)


@app.post("/api/logout")
def logout():
    with db() as c:
        c.execute("DELETE FROM sessions WHERE token=?", (request.headers.get("X-Token"),))
    return jsonify(ok=True)


def read_upload():
    f = request.files.get("file")
    if not f or not f.filename:
        return None, None
    h = hashlib.sha256()
    for chunk in iter(lambda: f.stream.read(65536), b""):
        h.update(chunk)
    return f.filename, h.hexdigest()  # the file itself is never stored


@app.post("/api/sign")
def sign():
    name, doc_hash = read_upload()
    if not doc_hash:
        return jsonify(error="Choose a file to sign."), 400
    n, threshold = int(request.form.get("n", 32)), float(request.form.get("threshold", 0.15))
    nonce, states = sign_document(doc_hash, n=n)
    sig_id = "SG-" + secrets.token_hex(4).upper()
    with db() as c:
        c.execute("INSERT INTO signatures VALUES(?,?,?,?,?,?,?,?,?)",
                  (sig_id, g.user["id"], name, doc_hash, nonce, n, threshold,
                   json.dumps([state_to_json(s) for s in states]), time.time()))
    return jsonify(signature_id=sig_id, filename=name, doc_hash=doc_hash, n_qubits=n,
                   signer=g.user["username"])


@app.post("/api/verify")
def verify():
    name, doc_hash = read_upload()
    sig_id = (request.form.get("signature_id") or "").strip().upper()
    if not doc_hash:
        return jsonify(error="Choose the file you want to check."), 400
    with db() as c:
        sig = c.execute("""SELECT s.*, u.username FROM signatures s JOIN users u ON u.id=s.user_id
                           WHERE s.id=?""", (sig_id,)).fetchone()
        if not sig:
            return jsonify(error="No signature with that ID."), 404
        states = [state_from_json(j) for j in json.loads(sig["qubits"])]
        r = verify_document(states, doc_hash, sig["nonce"], sig["threshold"])
        c.execute("INSERT INTO verifications(sig_id,verifier_id,filename,doc_hash,mismatch_rate,decision,ts) VALUES(?,?,?,?,?,?,?)",
                  (sig_id, g.user["id"], name, doc_hash, r["mismatch_rate"], r["decision"], time.time()))
    r.update(signature_id=sig_id, signer=sig["username"], signed_filename=sig["filename"],
             signed_hash=sig["doc_hash"], uploaded_hash=doc_hash, uploaded_filename=name)
    return jsonify(r)


@app.get("/api/signatures")
def signatures():
    with db() as c:
        rows = [dict(r) for r in c.execute("""SELECT s.id, s.filename, s.doc_hash, s.n_qubits, s.created, u.username signer
            FROM signatures s JOIN users u ON u.id=s.user_id WHERE s.user_id=? ORDER BY s.created DESC LIMIT 50""",
                                           (g.user["id"],))]
        checks = [dict(r) for r in c.execute("""SELECT sig_id, filename, mismatch_rate, decision, ts FROM verifications
            WHERE verifier_id=? ORDER BY id DESC LIMIT 25""", (g.user["id"],))]
    return jsonify(signatures=rows, verifications=checks)


@app.post("/api/run/<scenario>")
def run(scenario):
    if scenario not in ("honest", "channel_manipulation", "forgery", "impersonation", "replay"):
        return jsonify(error="unknown scenario"), 404
    n = int(request.args.get("n", 32))
    threshold = float(request.args.get("threshold", 0.15))
    r = run_protocol(scenario, n=n, threshold=threshold)
    with db() as c:
        cur = c.execute(
            """INSERT INTO runs(ts,user_id,scenario,n_qubits,threshold,mismatches,mismatch_rate,decision,forgery_probability,sample)
               VALUES(?,?,?,?,?,?,?,?,?,?)""",
            (time.time(), g.user["id"], scenario, n, threshold, r["mismatches"], r["mismatch_rate"], r["decision"],
             r["forgery_probability"], json.dumps(r["sample"])))
    r["id"] = cur.lastrowid
    return jsonify(r)


@app.get("/api/dashboard")
def dashboard():
    with db() as c:
        uid = g.user["id"]
        q = lambda sql: [dict(x) for x in c.execute(sql.replace("FROM runs", f"FROM runs WHERE user_id={uid}")).fetchall()]
        history = q("SELECT * FROM runs ORDER BY id DESC LIMIT 25")
        stats = {r["decision"]: r["n"] for r in q("SELECT decision, COUNT(*) n FROM runs GROUP BY decision")}
        by_scenario = q("""SELECT scenario, COUNT(*) n, AVG(mismatch_rate) avg_mismatch,
                            SUM(CASE WHEN decision='REJECT' THEN 1 ELSE 0 END) rejected
                            FROM runs GROUP BY scenario""")
    for h in history:
        h["sample"] = json.loads(h["sample"])
    return jsonify(history=history, stats=stats, by_scenario=by_scenario,
                   timeline=[{"mismatch_rate": h["mismatch_rate"], "decision": h["decision"]} for h in history][::-1])


DOCS_HTML = """<!DOCTYPE html><html><head><meta charset="utf-8"><title>SignGuard QDS API docs</title>
<style>
body{font-family:system-ui,sans-serif;background:#0f172a;color:#e2e8f0;max-width:900px;margin:30px auto;padding:0 16px}
h1{margin-bottom:0}small{color:#94a3b8}
.ep{background:#1e293b;border-radius:8px;padding:14px;margin:14px 0}
.m{display:inline-block;background:#3b82f6;color:#fff;padding:2px 8px;border-radius:4px;font-size:12px;font-weight:700;margin-right:6px}
code{background:#0f172a;padding:2px 6px;border-radius:4px}
textarea,input{width:100%;box-sizing:border-box;background:#0f172a;color:#e2e8f0;border:1px solid #334155;border-radius:6px;padding:6px;margin:4px 0;font-family:monospace}
button{background:#3b82f6;color:#fff;border:0;border-radius:6px;padding:6px 12px;cursor:pointer;margin-top:4px}
pre{background:#0f172a;padding:10px;border-radius:6px;overflow:auto;max-height:300px}
</style></head><body>
<h1>SignGuard QDS API</h1><small>Quantum-inspired threat detection for teleportation-based Quantum Digital Signatures. Click "Try it" to call the live API.</small>

<div class="ep"><span class="m">POST</span><code>/api/login</code>
<textarea id="b-login" rows="2">{"email":"your_username","password":"your_password"}</textarea>
<button onclick="call('POST','/api/login','b-login','o-login',false)">Try it</button><pre id="o-login"></pre></div>

<div class="ep"><span class="m">POST</span><code>/api/run/&lt;scenario&gt;?n=32&amp;threshold=0.15</code>
<p>scenario is one of <code>honest</code>, <code>channel_manipulation</code>, <code>forgery</code>, <code>impersonation</code>, <code>replay</code>. Runs a real teleportation-based QDS simulation (Bell pairs, Pauli eigenstates, projective measurement) and returns the mismatch rate, ACCEPT/REJECT decision and forgery probability.</p>
<input id="b-scen" value="channel_manipulation">
<button onclick="call('POST','/api/run/'+document.getElementById('b-scen').value+'?n=32&threshold=0.15',null,'o-scen',true)">Try it</button><pre id="o-scen"></pre></div>

<div class="ep"><span class="m">GET</span><code>/api/dashboard</code>
<button onclick="call('GET','/api/dashboard',null,'o-dash',true)">Try it</button><pre id="o-dash"></pre></div>

<p><small>Token in use: <code id="tok">none yet -- try /api/login first</code></small></p>
<script>
let TOKEN = '';
async function call(method, path, bodyId, outId, useAuth) {
  const opts = { method, headers: {'Content-Type':'application/json'} };
  if (useAuth) opts.headers['X-Token'] = TOKEN;
  if (bodyId) opts.body = document.getElementById(bodyId).value;
  const res = await fetch(path, opts);
  const data = await res.json();
  document.getElementById(outId).textContent = JSON.stringify(data, null, 2);
  if (path === '/api/login' && data.token) { TOKEN = data.token; document.getElementById('tok').textContent = TOKEN; }
}
</script></body></html>"""


@app.get("/docs")
def docs():
    return DOCS_HTML


@app.get("/")
def root():
    return send_from_directory(WEB, "index.html")


if __name__ == "__main__":
    app.run(port=5000, debug=False)
