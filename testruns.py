"""Day 5: result views + the 4 labelled official test runs (input, expected, actual, evidence)."""
import json
from flask import Blueprint, current_app, redirect, render_template_string, abort
from db import get_db, init_db
from agent import now, ensure_tables
from actions import ensure_exec

bp = Blueprint("tests", __name__)

SCENARIOS = [
    ("TC1", "Doctor on leave Friday", "Dr. Mehta is on leave Friday", "slots removed"),
    ("TC2", "Existing bookings on leave day", "Dr. Mehta is on leave Friday", "listed for rescheduling"),
    ("TC3", "Portal update fails", "Dr. Khan on leave Tuesday", "reported partial"),
    ("TC4", "Public page cached", "Dr. Rao on leave Wednesday", "recheck after refresh"),
]

CSS = """<style>body{font-family:sans-serif;max-width:1100px;margin:20px auto}td,th{border:1px solid #999;padding:4px 8px;vertical-align:top;font-size:14px}
.ok{color:green;font-weight:bold}.bad{color:#b00;font-weight:bold}.warn{color:#b60}pre{white-space:pre-wrap;font-size:12px;margin:0}button{padding:6px 14px}</style>"""

TESTS = CSS + """<h2>Official test runs</h2>
<form method=post action="/tests/run"><button>Run all 4 scenarios</button></form>
<p class=warn>Running resets the demo data (doctors, slots, bookings) so every run starts from the same state. Logs are kept.</p>
{% if rows %}<p>Last run: {{rows[0].run_at}} | {{passed}}/{{rows|length}} passed</p>
<table><tr><th>Test</th><th>Scenario</th><th>Input</th><th>Expected</th><th>Actual</th><th>Result</th><th>Evidence</th></tr>
{% for r in rows %}<tr><td><b>{{r.label}}</b></td><td>{{r.scenario}}</td><td>{{r.input_text}}</td><td>{{r.expected}}</td>
<td>{{r.actual}}</td><td class="{{'ok' if r.passed else 'bad'}}">{{'PASS' if r.passed else 'FAIL'}}</td>
<td>{% set i = r.input_id %}{% if i %}<a href="/agent/proposal/{{i}}">proposal</a> | <a href="/agent/result/{{i}}">result</a> |
<a href="/agent/verification/{{i}}">verification</a> | <a href="/agent/log/{{i}}">log</a>{% endif %}</td></tr>{% endfor %}</table>
{% else %}<p>No runs yet.</p>{% endif %}<p><a href="/agent">Agent</a> | <a href="/agent/dashboard">Dashboard</a></p>"""

DASH = CSS + """<h2>Dashboard - all inputs</h2><p>Unresolved items: <b class="{{'bad' if unresolved else 'ok'}}">{{unresolved}}</b></p>
<table><tr><th>Input ID</th><th>Message</th><th>Status</th><th>Verification</th><th>Created</th></tr>
{% for r in rows %}<tr><td><a href="/agent/log/{{r.id}}">{{r.id}}</a></td><td>{{r.raw_text}}</td>
<td class="{{'bad' if r.unresolved else 'ok'}}">{{r.status}}</td><td>{{r.verification or '-'}}</td><td>{{r.created_at}}</td></tr>{% endfor %}</table>
<p><a href="/agent">New input</a> | <a href="/tests">Test runs</a></p>"""

LOG = CSS + """<h2>Update log - {{inp.id}}</h2><p>Message: <i>{{inp.raw_text}}</i><br>Parser: {{inp.parser}} | Status: <b>{{inp.status}}</b> | Created {{inp.created_at}}</p>
<h3>Affected appointments</h3>
{% if affected %}<table><tr><th>Patient</th><th>Doctor</th><th>Date</th><th>Time</th><th>Booking status now</th></tr>
{% for a in affected %}<tr><td>{{a.patient}}</td><td>{{a.doctor}}</td><td>{{a.date}}</td><td>{{a.time}}</td><td>{{a.status}}</td></tr>{% endfor %}</table>
{% else %}<p>None.</p>{% endif %}
{% if unresolved %}<h3 class=bad>Unresolved items</h3><ul>{% for u in unresolved %}<li>{{u}}</li>{% endfor %}</ul>{% endif %}
<h3>Decision log (evidence for every step)</h3>
<table><tr><th>Time</th><th>Step</th><th>Source</th><th>Evidence</th></tr>
{% for l in logs %}<tr><td>{{l.created_at}}</td><td><b>{{l.step}}</b></td><td>{{l.source}}</td><td><pre>{{l.evidence}}</pre></td></tr>{% endfor %}</table>
<p><a href="/agent/proposal/{{inp.id}}">Proposal</a> | <a href="/agent/dashboard">Dashboard</a></p>"""


def ensure(conn):
    ensure_tables(conn)
    ensure_exec(conn)
    conn.executescript("""
    CREATE TABLE IF NOT EXISTS verifications(id INTEGER PRIMARY KEY AUTOINCREMENT, input_id TEXT, result_json TEXT, checked_at TEXT);
    CREATE TABLE IF NOT EXISTS test_runs(id INTEGER PRIMARY KEY AUTOINCREMENT, batch TEXT, label TEXT, scenario TEXT,
        input_text TEXT, expected TEXT, actual TEXT, passed INTEGER, input_id TEXT, evidence_json TEXT, run_at TEXT);""")


def toggle_failure(client, want):
    if client.get("/api/state").get_json()["portal_fails"] != want:
        client.post("/admin/toggle-portal-failure")


def run_one(client, label, text):
    init_db()                                  # same starting data for every run
    toggle_failure(client, False)
    client.get("/cms?fresh=1")                 # public page is now cached with the starting data
    if label == "TC3":
        toggle_failure(client, True)           # simulate the portal being down
    iid = None
    try:
        iid = client.post("/agent", data={"text": text}).headers["Location"].rsplit("/", 1)[-1]
        client.post(f"/agent/approve/{iid}")
        client.post(f"/agent/verify/{iid}")
    finally:
        toggle_failure(client, False)
    conn = get_db()
    ensure(conn)
    inp = conn.execute("SELECT * FROM roster_inputs WHERE id=?", (iid,)).fetchone()
    prop = json.loads(inp["proposal_json"])
    ex = conn.execute("SELECT status FROM executions WHERE input_id=?", (iid,)).fetchone()
    vr = conn.execute("SELECT result_json FROM verifications WHERE input_id=? ORDER BY id DESC LIMIT 1", (iid,)).fetchone()
    ver = json.loads(vr[0]) if vr else None
    bookings = [dict(r) for r in conn.execute("SELECT patient,status FROM bookings")]
    conn.close()
    status = ex["status"] if ex else f"not executed (proposal {prop['status']})"
    row = ver["rows"][0] if ver and ver["rows"] else None
    if not row:
        return dict(passed=False, actual=f"No verification. Status: {status}", input_id=iid, ver=ver, status=status, bookings=bookings)
    cms, portal = row["cms"], row["portal"]
    if label == "TC1":
        ok = status == "applied" and ver["overall"] == "verified"
        actual = f"Status {status}. Public CMS: {cms['verdict']}; portal: {portal['verdict']}; slots left on that day: none"
    elif label == "TC2":
        names = [b["patient"] for b in prop["items"][0].get("affected_bookings", [])]
        ok = set(names) == {"Ravi Kumar", "Sana Ali"} and all(b["status"] == "needs_reschedule" for b in bookings)
        actual = f"Listed for rescheduling: {', '.join(names)}. Booking statuses: " + ", ".join(f"{b['patient']}={b['status']}" for b in bookings)
    elif label == "TC3":
        ok = status == "partial"
        actual = f"Overall status: {status}. CMS updated, portal update failed. Verification: {ver['overall']} (portal: {portal['verdict']})"
    else:
        ok = "confirmed_after_refresh" in cms["verdict"]
        actual = (f"CMS first read: {', '.join(cms['first']) or 'no slots'} (page rendered {cms['rendered_at']}); "
                  f"after refresh: {', '.join(cms['refreshed'] or []) or 'no slots'}. Verdict: {cms['verdict']}")
    return dict(passed=ok, actual=actual, input_id=iid, ver=ver, status=status, bookings=bookings, parser=prop["parser"])


@bp.route("/tests/run", methods=["POST"])
def run_all():
    client = current_app.test_client()
    batch = now()
    for label, scenario, text, expected in SCENARIOS:
        res = run_one(client, label, text)
        conn = get_db()
        ensure(conn)
        conn.execute("""INSERT INTO test_runs(batch,label,scenario,input_text,expected,actual,passed,input_id,evidence_json,run_at)
            VALUES(?,?,?,?,?,?,?,?,?,?)""", (batch, label, scenario, text, expected, res["actual"], 1 if res["passed"] else 0,
            res["input_id"], json.dumps({k: res.get(k) for k in ("status", "parser", "ver", "bookings")}), now()))
        conn.commit()
        conn.close()
    return redirect("/tests")


@bp.route("/tests")
def tests_page():
    conn = get_db()
    ensure(conn)
    last = conn.execute("SELECT batch FROM test_runs ORDER BY id DESC LIMIT 1").fetchone()
    rows = []
    if last:
        rows = [dict(r) for r in conn.execute("SELECT * FROM test_runs WHERE batch=? ORDER BY label", (last["batch"],))]
    conn.close()
    return render_template_string(TESTS, rows=rows, passed=sum(r["passed"] for r in rows))


@bp.route("/agent/dashboard")
def dashboard():
    conn = get_db()
    ensure(conn)
    rows = []
    for r in conn.execute("SELECT * FROM roster_inputs ORDER BY created_at DESC, rowid DESC"):
        v = conn.execute("SELECT result_json FROM verifications WHERE input_id=? ORDER BY id DESC LIMIT 1", (r["id"],)).fetchone()
        vo = json.loads(v[0])["overall"] if v else None
        d = dict(r)
        d["verification"] = vo
        d["unresolved"] = r["status"] in ("partial", "failed", "needs_clarification") or vo == "unresolved"
        rows.append(d)
    conn.close()
    return render_template_string(DASH, rows=rows, unresolved=sum(1 for r in rows if r["unresolved"]))


@bp.route("/agent/log/<input_id>")
def update_log(input_id):
    conn = get_db()
    ensure(conn)
    inp = conn.execute("SELECT * FROM roster_inputs WHERE id=?", (input_id,)).fetchone()
    if not inp:
        abort(404)
    prop = json.loads(inp["proposal_json"] or "{}")
    affected, unresolved = [], []
    for it in prop.get("items", []):
        if it["state"] == "uncertain":
            unresolved.append(f"Could not understand the message: {it['reason']}")
            continue
        for b in it.get("affected_bookings", []):
            st = conn.execute("SELECT status FROM bookings WHERE id=?", (b["booking_id"],)).fetchone()
            affected.append({"patient": b["patient"], "doctor": it["doctor_name"], "date": it["date"],
                             "time": b["time"], "status": st["status"] if st else "?"})
    if inp["status"] in ("partial", "failed"):
        unresolved.append(f"Update was {inp['status']}: the public CMS and the booking portal may disagree.")
    v = conn.execute("SELECT result_json FROM verifications WHERE input_id=? ORDER BY id DESC LIMIT 1", (input_id,)).fetchone()
    if v and json.loads(v[0])["overall"] == "unresolved":
        unresolved.append("Verification found a mismatch on a public page.")
    logs = [{"created_at": l["created_at"], "step": l["step"], "source": l["source"],
             "evidence": json.dumps(json.loads(l["evidence"]), indent=1)[:1500]}
            for l in conn.execute("SELECT * FROM decision_log WHERE input_id=? ORDER BY id", (input_id,))]
    conn.close()
    return render_template_string(LOG, inp=inp, affected=affected, unresolved=unresolved, logs=logs)