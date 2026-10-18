"""Day 3: input form, human approval, and the update action (with duplicate-run protection)."""
import json, sqlite3
from flask import Blueprint, request, redirect, current_app, render_template_string, abort
from db import get_db
from agent import build_proposal, ensure_tables, log, now

bp = Blueprint("agent", __name__)

STYLE = "<style>body{font-family:sans-serif;max-width:800px;margin:20px auto}td,th{border:1px solid #999;padding:4px 8px}" \
        ".ok{color:green}.bad{color:#b00}.warn{color:#b60}button{padding:6px 14px;margin-right:8px}</style>"

FORM = STYLE + """<h2>Clinic Roster Publisher</h2>
<form method=post action="/agent"><p>Paste the weekly roster / leave change:</p>
<textarea name=text rows=4 cols=70 placeholder="Dr. Mehta is on leave Friday"></textarea><br><br>
<button>Analyse</button></form><p><a href="/">Home</a> | <a href="/agent/dashboard">Dashboard</a> | <a href="/tests">Test runs</a></p>"""

PROPOSAL = STYLE + """<h2>Proposal {{p.input_id}}</h2>
<p>Status: <b>{{p.status}}</b> | Parser: {{p.parser}}</p><p>Input: <i>{{raw}}</i></p>
{% for i in p['items'] %}<div style="border:1px solid #aaa;padding:8px;margin:8px 0">
 {% if i.state=='uncertain' %}<b class=warn>UNCERTAIN</b> - {{i.reason}}
 {% else %}<b>{{i.doctor_name}}</b> - {{i.date}} - <b>{{i.action}}</b><br>{{i.reason}}
  <br>Slots: {% for s in i.slots_to_change %}{{s.time}} {% endfor %}
  {% if i.affected_bookings %}<br><b class=bad>Bookings to reschedule:</b>
  <ul>{% for b in i.affected_bookings %}<li>{{b.patient}} at {{b.time}} (booking #{{b.booking_id}})</li>{% endfor %}</ul>{% endif %}
 {% endif %}</div>{% endfor %}
{% if p.status=='awaiting_approval' %}
<form method=post action="/agent/approve/{{p.input_id}}" style="display:inline"><button>Approve and publish</button></form>
<form method=post action="/agent/reject/{{p.input_id}}" style="display:inline"><button>Reject</button></form>
{% else %}<p class=warn>Cannot be approved. Fix the input and try again.</p><a href="/agent">Back</a>{% endif %}"""

RESULT = STYLE + """<h2>Result {{input_id}}</h2><p>Overall: <b>{{status}}</b></p>
<table><tr><th>Doctor</th><th>Date</th><th>CMS</th><th>Portal</th><th>State</th><th>Rescheduling list</th></tr>
{% for r in results %}<tr><td>{{r.doctor}}</td><td>{{r.date}}</td>
<td class="{{'ok' if r.cms_ok else 'bad'}}">{{'updated' if r.cms_ok else 'FAILED'}}</td>
<td class="{{'ok' if r.portal_ok else 'bad'}}">{{'updated' if r.portal_ok else 'FAILED'}}</td>
<td><b>{{r.state}}</b></td><td>{% for b in r.reschedule %}{{b.patient}} ({{b.time}})<br>{% endfor %}</td></tr>{% endfor %}</table>
<form method=post action="/agent/verify/{{input_id}}"><button>Verify on public pages</button></form>
<p><a href="/cms?fresh=1">Public page (fresh)</a> | <a href="/portal">Portal</a> | <a href="/agent/log/{{input_id}}">Update log</a> | <a href="/agent">New input</a></p>"""


def ensure_exec(conn):
    conn.execute("""CREATE TABLE IF NOT EXISTS executions(
        input_id TEXT PRIMARY KEY, status TEXT, approved_json TEXT, result_json TEXT, executed_at TEXT)""")


@bp.route("/agent", methods=["GET", "POST"])
def agent_home():
    if request.method == "POST":
        text = request.form.get("text", "").strip()
        if not text:
            return redirect("/agent")
        return redirect(f"/agent/proposal/{build_proposal(text)['input_id']}")
    return FORM


def _load(conn, input_id):
    ensure_tables(conn)
    row = conn.execute("SELECT * FROM roster_inputs WHERE id=?", (input_id,)).fetchone()
    if not row:
        abort(404)
    return row


@bp.route("/agent/proposal/<input_id>")
def proposal_page(input_id):
    conn = get_db()
    row = _load(conn, input_id)
    p = json.loads(row["proposal_json"])
    p["status"] = row["status"]
    return render_template_string(PROPOSAL, p=p, raw=row["raw_text"])


@bp.route("/agent/reject/<input_id>", methods=["POST"])
def reject(input_id):
    conn = get_db()
    _load(conn, input_id)
    conn.execute("UPDATE roster_inputs SET status='rejected' WHERE id=?", (input_id,))
    log(conn, input_id, "rejected", {"by": "human"}, "approval screen")
    conn.commit()
    return redirect("/agent")


@bp.route("/agent/approve/<input_id>", methods=["POST"])
def approve(input_id):
    conn = get_db()
    ensure_exec(conn)
    row = _load(conn, input_id)
    if row["status"] != "awaiting_approval" and row["status"] not in ("applied", "partial", "failed"):
        return f"Cannot approve: status is {row['status']}", 400
    try:  # primary key makes a second approval (retry / double click) impossible to execute twice
        conn.execute("INSERT INTO executions(input_id,status,approved_json,executed_at) VALUES(?,?,?,?)",
                     (input_id, "running", row["proposal_json"], now()))
        conn.commit()
    except sqlite3.IntegrityError:
        log(conn, input_id, "duplicate_blocked", {"note": "already executed, not run again"}, "executions table")
        conn.commit()
        return redirect(f"/agent/result/{input_id}")

    log(conn, input_id, "approved", {"by": "human", "proposal": json.loads(row["proposal_json"])}, "approval screen")
    conn.commit()  # release the write lock before the update calls below
    proposal = json.loads(row["proposal_json"])
    client = current_app.test_client()
    results = []
    for it in proposal["items"]:
        if it["state"] != "ready":
            continue
        payload = {"doctor_id": it["doctor_id"], "date": it["date"], "available": it["action"] == "available"}
        cms = client.post("/cms/api/availability", json=payload)
        portal = client.post("/portal/api/availability", json=payload)
        cms_ok, portal_ok = cms.status_code == 200, portal.status_code == 200
        state = "applied" if cms_ok and portal_ok else ("partial" if cms_ok or portal_ok else "failed")
        if state != "failed":
            for b in it["affected_bookings"]:
                conn.execute("UPDATE bookings SET status='needs_reschedule' WHERE id=?", (b["booking_id"],))
        log(conn, input_id, "action", {"payload": payload, "cms_status": cms.status_code,
            "portal_status": portal.status_code, "state": state}, "/cms/api + /portal/api")
        results.append({"doctor": it["doctor_name"], "date": it["date"], "cms_ok": cms_ok,
                        "portal_ok": portal_ok, "state": state, "reschedule": it["affected_bookings"]})
        conn.commit()
    states = {r["state"] for r in results}
    overall = "applied" if states == {"applied"} else ("failed" if states == {"failed"} else "partial")
    conn.execute("UPDATE executions SET status=?, result_json=? WHERE input_id=?",
                 (overall, json.dumps(results), input_id))
    conn.execute("UPDATE roster_inputs SET status=? WHERE id=?", (overall, input_id))
    conn.commit()
    return redirect(f"/agent/result/{input_id}")


@bp.route("/agent/result/<input_id>")
def result_page(input_id):
    conn = get_db()
    ensure_exec(conn)
    ex = conn.execute("SELECT * FROM executions WHERE input_id=?", (input_id,)).fetchone()
    if not ex:
        abort(404)
    return render_template_string(RESULT, input_id=input_id, status=ex["status"],
                                  results=json.loads(ex["result_json"] or "[]"))    