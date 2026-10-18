"""Day 4: verification, deliberately separate from the action.
Reloads the PUBLIC pages (/cms, /portal), reads what visitors actually see, and compares it with what was intended.
If the public page looks stale (cached), it refreshes and rechecks (TC4)."""
import json, re
from flask import Blueprint, redirect, current_app, render_template_string, abort
from db import get_db
from agent import log, now

bp = Blueprint("verify", __name__)

PAGE = """<style>body{font-family:sans-serif;max-width:900px;margin:20px auto}td,th{border:1px solid #999;padding:4px 8px;vertical-align:top}
.ok{color:green}.bad{color:#b00}.warn{color:#b60}small{color:#555}</style>
<h2>Verification for {{input_id}}</h2><p>Checked at {{v.checked_at}} | Overall: <b class="{{'ok' if v.overall=='verified' else 'bad'}}">{{v.overall}}</b></p>
<table><tr><th>Doctor / date</th><th>Intended</th><th>Public CMS page</th><th>Booking portal</th></tr>
{% for r in v.rows %}<tr><td>{{r.doctor}}<br>{{r.date}}</td><td>{{r.intended or 'no slots'}}</td>
{% for ch in [r.cms, r.portal] %}<td><b class="{{'ok' if ch.verdict.startswith('confirmed') else 'bad'}}">{{ch.verdict}}</b><br>
<small>{{ch.url}}<br>first read: {{ch.first or 'no slots'}}{% if ch.rendered_at %} (page rendered {{ch.rendered_at}}){% endif %}
{% if ch.refreshed is not none %}<br>after refresh: {{ch.refreshed or 'no slots'}}{% endif %}</small></td>{% endfor %}</tr>{% endfor %}</table>
<p><a href="/agent/result/{{input_id}}">Back to result</a> | <a href="/agent">New input</a></p>"""


def observed(html, doctor, date):
    for sec in html.split("<h3>")[1:]:
        if sec.startswith(doctor):
            m = re.search(rf"<td>{date}</td><td>(.*?)</td>", sec)
            if not m:
                return None
            txt = m.group(1).strip()
            return [] if txt == "No availability" else sorted(t.strip() for t in txt.split(","))
    return None


def check(client, path, doctor, date, intended, allow_refresh):
    r1 = client.get(path).get_data(as_text=True)
    rendered = re.search(r"Rendered at (\S+)", r1)
    first = observed(r1, doctor, date)
    out = {"url": path, "first": first, "refreshed": None,
           "rendered_at": rendered.group(1) if rendered else None, "retrieved_at": now()}
    if first == intended:
        out["verdict"] = "confirmed"
    elif allow_refresh:  # public page may be cached: refresh and recheck
        r2 = client.get(path + "?fresh=1").get_data(as_text=True)
        out["refreshed"] = observed(r2, doctor, date)
        out["verdict"] = ("confirmed_after_refresh (page was stale)" if out["refreshed"] == intended
                          else "MISMATCH - change not visible")
    else:
        out["verdict"] = "MISMATCH - change not visible"
    return out


@bp.route("/agent/verify/<input_id>", methods=["POST"])
def run_verify(input_id):
    conn = get_db()
    conn.execute("""CREATE TABLE IF NOT EXISTS verifications(
        id INTEGER PRIMARY KEY AUTOINCREMENT, input_id TEXT, result_json TEXT, checked_at TEXT)""")
    ex = conn.execute("SELECT * FROM executions WHERE input_id=?", (input_id,)).fetchone()
    if not ex:
        abort(404)
    proposal = json.loads(ex["approved_json"])
    client = current_app.test_client()
    rows = []
    for it in proposal["items"]:
        if it["state"] != "ready":
            continue
        avail = it["action"] == "available"
        times = sorted(r["time"] for r in conn.execute(
            "SELECT time FROM slots WHERE doctor_id=? AND date=?", (it["doctor_id"], it["date"])))
        intended = times if avail else []
        row = {"doctor": it["doctor_name"], "date": it["date"], "intended": intended,
               "cms": check(client, "/cms", it["doctor_name"], it["date"], intended, True),
               "portal": check(client, "/portal", it["doctor_name"], it["date"], intended, False)}
        rows.append(row)
        log(conn, input_id, "verify", row, "GET /cms, GET /portal")
    ok = all(r["cms"]["verdict"].startswith("confirmed") and r["portal"]["verdict"].startswith("confirmed") for r in rows)
    result = {"checked_at": now(), "overall": "verified" if ok else "unresolved", "rows": rows}
    conn.execute("INSERT INTO verifications(input_id,result_json,checked_at) VALUES(?,?,?)",
                 (input_id, json.dumps(result), result["checked_at"]))
    conn.commit()
    return redirect(f"/agent/verification/{input_id}")


@bp.route("/agent/verification/<input_id>")
def show_verify(input_id):
    conn = get_db()
    row = conn.execute("SELECT * FROM verifications WHERE input_id=? ORDER BY id DESC LIMIT 1", (input_id,)).fetchone()
    if not row:
        abort(404)
    return render_template_string(PAGE, input_id=input_id, v=json.loads(row["result_json"]))