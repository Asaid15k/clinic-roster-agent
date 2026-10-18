# Clinic Doctor Roster Publisher

An agentic AI workflow for the Ziro Agentic AI Hackathon 2026.

**Problem:** A clinic admin updates doctor availability once, and it must appear consistently on the public website (CMS) and the booking portal.

**What the agent does:** it reads a roster or leave message, finds conflicts with existing bookings, proposes the change, waits for human approval, applies the update to both systems, and then checks the public pages to confirm the result.

## Workflow

| Step | What happens | Where |
|------|--------------|-------|
| 1. Collect | Admin types a roster or leave change (for example, "Dr. Mehta is on leave Friday") | `/agent` |
| 2. Plan | Gemini extracts doctor, date and action as JSON. Plain code then checks existing bookings for conflicts. Anything unclear is marked **uncertain** and cannot be approved. | `agent.py` |
| 3. Find information | Reads doctors, slots and bookings from the mock CMS and booking portal database | `agent.py` |
| 4. Take action | **Human approval required.** After approval, updates the CMS and the booking portal and marks affected bookings for rescheduling | `actions.py` |
| 5. Check result | Separately reloads the public `/cms` and `/portal` pages, reads what visitors see, and compares it with what was intended. If the CMS page looks stale (cached), it refreshes and rechecks. | `verify.py` |
| 6. Result view | Update log, affected appointments, unresolved items, with evidence for each decision | `/agent/log/<id>`, `/agent/dashboard` |

## Key design points

- **Human approval before any change.** The proposal screen shows the exact change and the bookings it affects.
- **No duplicate execution.** Each input can be executed only once. A retry or double click is blocked and logged.
- **Honest failures.** If the portal update fails, the result is reported as `partial`, never as success. Verification then shows the mismatch as unresolved.
- **Uncertain input is not guessed.** Missing doctor, date or action returns `needs_clarification`.
- **Evidence trail.** Every step (collect, parse, conflict check, approve, action, verify) is stored in `decision_log` with its source and a timestamp.
- **Fallback parser.** If the Gemini call fails, a simple rule-based parser handles basic messages. The parser used is shown on every proposal.
- **LLM only where needed.** The LLM only turns free text into structured fields. Conflict detection, the action and verification are deterministic code.

## Setup

Requires Python 3.10+ and a Gemini API key (Google AI Studio).

```
python -m venv venv
.\venv\Scripts\activate          # Windows PowerShell
pip install -r requirements.txt
```

Create a file named `.env` next to `app.py`:

```
GEMINI_API_KEY=your_key_here
```

Then:

```
python db.py     # creates and seeds clinic.db (3 doctors, 5 days, 3 slots per day, 2 bookings)
python app.py    # http://127.0.0.1:5000
```

## Pages

| URL | Purpose |
|-----|---------|
| `/agent` | Enter a roster or leave message |
| `/agent/proposal/<id>` | Review the proposal and approve or reject |
| `/agent/result/<id>` | Result of the update (CMS, portal, state) |
| `/agent/verification/<id>` | Separate verification of the public pages |
| `/agent/log/<id>` | Update log, affected appointments, evidence |
| `/agent/dashboard` | All inputs and unresolved items |
| `/tests` | Run and view the four official test cases |
| `/cms`, `/portal` | The mock public clinic website (cached 60 s) and the booking portal |
| `POST /admin/toggle-portal-failure` | Makes portal updates fail on purpose (used for TC3) |

## Official test cases

Open `/tests` and click **Run all 4 scenarios**. Each run resets the demo data, then stores the input, expected result, actual result and evidence.

| Test | Scenario | Expected | How it is checked |
|------|----------|----------|-------------------|
| TC1 | Doctor on leave Friday | Slots removed | Public CMS and portal read back with no slots for that day |
| TC2 | Existing bookings on leave day | Listed for rescheduling | Ravi Kumar and Sana Ali are listed and marked `needs_reschedule` |
| TC3 | Portal update fails | Reported partial | CMS updated, portal failed, overall status `partial`, verification `unresolved` |
| TC4 | Public page cached | Recheck after refresh | First read of `/cms` is stale; after refresh it matches, verdict `confirmed_after_refresh` |

Last run on the development machine: 4 of 4 passed, with Gemini as the parser.

## Project structure

```
app.py        Flask app: mock CMS, mock booking portal, failure switch, page cache
db.py         SQLite schema and seed data
agent.py      Parse (Gemini + fallback), conflict detection, proposal, decision log
actions.py    Input form, approval screen, update action, duplicate protection
verify.py     Separate verification of the public pages
testruns.py   Test runner, dashboard, update log view
```

## Limitations

- The CMS and booking portal are mocks that share one SQLite file. The agent talks to them through their HTTP update endpoints, so a real CMS or portal API could replace them.
- Messages are handled one doctor and one date at a time, with several changes allowed in one message.
- The fallback parser understands only simple messages with a doctor's surname and a weekday.
- The demo covers the week of 19 to 23 October 2026.
- The development server is not meant for production use.