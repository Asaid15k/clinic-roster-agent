"""Clinic Doctor Roster Publisher - agent brain (Day 2).
Steps: collect -> parse (LLM, with rule-based fallback) -> detect conflicts -> build proposal.
Nothing is changed here. Updates happen only after human approval (Day 3).
"""
import os, re, json, uuid, datetime, sys, time, threading
from dotenv import load_dotenv
from db import get_db

load_dotenv()
MODEL = "gemini-3.8-flash"
LLM_TIMEOUT_MS = 10000      # give up on Gemini after 10 s and use the rule parser
_CACHE = {}                 # same message -> same answer (temperature 0), so repeats are instant


def ensure_tables(conn):
    conn.executescript("""
    CREATE TABLE IF NOT EXISTS roster_inputs(
        id TEXT PRIMARY KEY, raw_text TEXT, parser TEXT, status TEXT, proposal_json TEXT, created_at TEXT);
    CREATE TABLE IF NOT EXISTS decision_log(
        id INTEGER PRIMARY KEY AUTOINCREMENT, input_id TEXT, step TEXT,
        evidence TEXT, source TEXT, created_at TEXT);
    """)


def now():
    return datetime.datetime.now().isoformat(timespec="seconds")


def log(conn, input_id, step, evidence, source):
    conn.execute("INSERT INTO decision_log(input_id,step,evidence,source,created_at) VALUES(?,?,?,?,?)",
                 (input_id, step, json.dumps(evidence), source, now()))


def load_context(conn):
    doctors = [dict(r) for r in conn.execute("SELECT id,name FROM doctors")]
    dates = [r["date"] for r in conn.execute("SELECT DISTINCT date FROM slots ORDER BY date")]
    calendar = {d: datetime.date.fromisoformat(d).strftime("%A") for d in dates}
    return doctors, calendar


# ---------- parsing ----------
def llm_parse(text, doctors, calendar):
    """Returns (changes, label). Label shows how the answer was produced and how long it took."""
    key = text.strip().lower()
    if key in _CACHE:
        return _CACHE[key], "gemini (cached)"
    from google import genai
    from google.genai import types
    t0 = time.time()
    client = genai.Client(api_key=os.environ["GEMINI_API_KEY"],
                          http_options=types.HttpOptions(timeout=LLM_TIMEOUT_MS))
    system = (
        "You extract clinic roster changes from a message. Return ONLY JSON: "
        '{"changes":[{"doctor_name":string|null,"date":"YYYY-MM-DD"|null,"action":"leave"|"available"|null}]}. '
        f"Known doctors: {[d['name'] for d in doctors]}. "
        f"Calendar (date: weekday): {json.dumps(calendar)}. "
        "Use null for anything not clearly stated. Never guess. One entry per doctor per date."
    )
    base = dict(system_instruction=system, response_mime_type="application/json", temperature=0)
    try:  # low thinking = much faster for a simple extraction task
        cfg = types.GenerateContentConfig(**base, thinking_config=types.ThinkingConfig(thinking_level="low"))
        resp = client.models.generate_content(model=MODEL, contents=text, config=cfg)
    except Exception as e:
        if "thinking" not in str(e).lower():
            raise                              # timeouts and other errors go to the fallback parser
        resp = client.models.generate_content(model=MODEL, contents=text,
                                              config=types.GenerateContentConfig(**base))
    changes = json.loads(resp.text)["changes"]
    _CACHE[key] = changes
    return changes, f"gemini ({time.time() - t0:.1f}s)"


def rule_parse(text, doctors, calendar):
    """Fallback when the API key/model is unavailable. Handles simple messages only."""
    low = text.lower()
    doc = next((d["name"] for d in doctors if d["name"].lower().split()[-1] in low), None)
    date = next((d for d, wd in calendar.items() if wd.lower() in low), None)
    action = "leave" if re.search(r"leave|off|absent|unavailable|not available", low) else (
        "available" if re.search(r"available|back|return", low) else None)
    return [{"doctor_name": doc, "date": date, "action": action}]


def parse_input(text, doctors, calendar):
    try:
        raw, parser = llm_parse(text, doctors, calendar)
    except Exception as e:
        raw, parser = rule_parse(text, doctors, calendar), f"rules (LLM failed: {type(e).__name__})"
    changes = []
    for c in raw:
        doc = next((d for d in doctors if c.get("doctor_name") and
                    d["name"].lower() == str(c["doctor_name"]).lower()), None)
        missing = []
        if not doc: missing.append("doctor")
        if c.get("date") not in calendar: missing.append("date")
        if c.get("action") not in ("leave", "available"): missing.append("action")
        changes.append({"doctor_id": doc["id"] if doc else None, "doctor_name": doc["name"] if doc else None,
                        "date": c.get("date"), "action": c.get("action"), "missing": missing})
    return changes, parser


# ---------- decision rules ----------
def find_conflicts(conn, doctor_id, date):
    rows = conn.execute("""SELECT b.id booking_id, b.patient, s.time, s.id slot_id
        FROM bookings b JOIN slots s ON s.id=b.slot_id
        WHERE s.doctor_id=? AND s.date=? AND b.status='confirmed'""", (doctor_id, date)).fetchall()
    return [dict(r) for r in rows]


def slots_to_change(conn, doctor_id, date, make_available):
    target = 1 if make_available else 0
    rows = conn.execute("""SELECT id, time, cms_available, portal_available FROM slots
        WHERE doctor_id=? AND date=? AND (cms_available!=? OR portal_available!=?)""",
        (doctor_id, date, target, target)).fetchall()
    return [dict(r) for r in rows]


# ---------- main entry ----------
def build_proposal(raw_text):
    conn = get_db()
    ensure_tables(conn)
    input_id = "IN-" + uuid.uuid4().hex[:8]
    doctors, calendar = load_context(conn)
    conn.execute("INSERT INTO roster_inputs(id,raw_text,status,created_at) VALUES(?,?,?,?)",
                 (input_id, raw_text, "received", now()))
    log(conn, input_id, "collect", {"raw_text": raw_text}, "roster input form")

    changes, parser = parse_input(raw_text, doctors, calendar)
    log(conn, input_id, "parse", {"parser": parser, "changes": changes}, MODEL if parser.startswith("gemini") else "rule parser")

    items = []
    for c in changes:
        if c["missing"]:
            item = {**c, "state": "uncertain", "reason": f"Missing or invalid: {', '.join(c['missing'])}"}
        else:
            avail = c["action"] == "available"
            slots = slots_to_change(conn, c["doctor_id"], c["date"], avail)
            conflicts = [] if avail else find_conflicts(conn, c["doctor_id"], c["date"])
            item = {**c, "state": "ready", "slots_to_change": slots, "affected_bookings": conflicts,
                    "reason": f"{len(slots)} slot(s) to {'open' if avail else 'remove'}, {len(conflicts)} booking(s) need rescheduling"}
            log(conn, input_id, "conflict_check", {"doctor_id": c["doctor_id"], "date": c["date"],
                "affected_bookings": conflicts}, "db: bookings JOIN slots")
        items.append(item)

    status = "needs_clarification" if any(i["state"] == "uncertain" for i in items) else "awaiting_approval"
    proposal = {"input_id": input_id, "parser": parser, "status": status, "items": items}
    conn.execute("UPDATE roster_inputs SET parser=?, status=?, proposal_json=? WHERE id=?",
                 (parser, status, json.dumps(proposal), input_id))
    log(conn, input_id, "proposal", {"status": status}, "agent")
    conn.commit()
    conn.close()
    return proposal


def _prewarm():
    """Ask Gemini the three demo messages once at startup, so they answer instantly later."""
    try:
        conn = get_db()
        doctors, calendar = load_context(conn)
        conn.close()
        for t in ("Dr. Mehta is on leave Friday", "Dr. Khan on leave Tuesday", "Dr. Rao on leave Wednesday"):
            try:
                llm_parse(t, doctors, calendar)
            except Exception:
                pass
    except Exception:
        pass


if __name__ != "__main__":
    threading.Thread(target=_prewarm, daemon=True).start()


if __name__ == "__main__":
    msg = " ".join(sys.argv[1:]) or "Dr. Mehta is on leave Friday"
    print(json.dumps(build_proposal(msg), indent=2))