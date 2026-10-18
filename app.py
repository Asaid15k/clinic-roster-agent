import time
from flask import Flask, jsonify, request, render_template_string
from db import get_db
from ui import HOME, install

app = Flask(__name__)
STATE = {"portal_fails": False, "cms_cache": None, "cms_cache_time": 0}
CACHE_TTL = 60  # seconds; simulates the cached public page (TC4)

PAGE = """
<h2>{{title}}</h2><p><small>Rendered at {{now}} {{note}}</small></p>
{% for d in doctors %}
  <h3>{{d.name}} ({{d.specialty}})</h3>
  <table border=1 cellpadding=4>
  {% for date, slots in d.days.items() %}
    <tr><td>{{date}}</td><td>{{ slots|join(', ') if slots else 'No availability' }}</td></tr>
  {% endfor %}
  </table>
{% endfor %}
"""

def build_view(column):
    conn = get_db()
    out = []
    for d in conn.execute("SELECT * FROM doctors"):
        days = {}
        for s in conn.execute(f"SELECT date,time FROM slots WHERE doctor_id=? AND {column}=1 ORDER BY date,time", (d["id"],)):
            days.setdefault(s["date"], []).append(s["time"])
        all_dates = [r["date"] for r in conn.execute("SELECT DISTINCT date FROM slots ORDER BY date")]
        out.append({"name": d["name"], "specialty": d["specialty"], "days": {x: days.get(x, []) for x in all_dates}})
    conn.close()
    return out

@app.route("/")
def index():
    return HOME

@app.route("/cms")
def cms():
    fresh = request.args.get("fresh") == "1"
    if not fresh and STATE["cms_cache"] and time.time() - STATE["cms_cache_time"] < CACHE_TTL:
        return STATE["cms_cache"]
    html = render_template_string(PAGE, title="Clinic Website - Doctor Availability",
        now=time.strftime("%H:%M:%S"), note="", doctors=build_view("cms_available"))
    STATE["cms_cache"], STATE["cms_cache_time"] = html, time.time()
    return html

@app.route("/portal")
def portal():
    return render_template_string(PAGE, title="Booking Portal - Available Slots",
        now=time.strftime("%H:%M:%S"), note="", doctors=build_view("portal_available"))

def _set(column, data):
    conn = get_db()
    conn.execute(f"UPDATE slots SET {column}=? WHERE doctor_id=? AND date=?",
                 (1 if data["available"] else 0, data["doctor_id"], data["date"]))
    conn.commit()
    conn.close()

@app.route("/cms/api/availability", methods=["POST"])
def cms_update():
    _set("cms_available", request.json)
    return jsonify(ok=True)

@app.route("/portal/api/availability", methods=["POST"])
def portal_update():
    if STATE["portal_fails"]:
        return jsonify(ok=False, error="Portal unavailable"), 500
    _set("portal_available", request.json)
    return jsonify(ok=True)

@app.route("/api/bookings")
def bookings():
    conn = get_db()
    rows = conn.execute("""SELECT b.id, b.patient, b.status, s.date, s.time, s.doctor_id
        FROM bookings b JOIN slots s ON s.id=b.slot_id
        WHERE s.doctor_id=? AND s.date=?""", (request.args["doctor_id"], request.args["date"])).fetchall()
    conn.close()
    return jsonify([dict(r) for r in rows])

@app.route("/admin/toggle-portal-failure", methods=["POST"])
def toggle_failure():
    STATE["portal_fails"] = not STATE["portal_fails"]
    return jsonify(portal_fails=STATE["portal_fails"])

@app.route("/api/state")
def state():
    return jsonify(portal_fails=STATE["portal_fails"], cache_age=round(time.time() - STATE["cms_cache_time"]))

from actions import bp
app.register_blueprint(bp)
from verify import bp as verify_bp
app.register_blueprint(verify_bp)
from testruns import bp as tests_bp
app.register_blueprint(tests_bp)

install(app)

if __name__ == "__main__":
    app.run(debug=True, port=5000)