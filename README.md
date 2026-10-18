# Clinic Doctor Roster Publisher

## Setup
    python -m venv venv
    venv\Scripts\activate        (Windows)
    pip install -r requirements.txt
    python db.py                 (creates + seeds clinic.db)
    python app.py                (http://127.0.0.1:5000)

## Pages
- /cms     public doctor page (cached 60s, add ?fresh=1 to bypass)
- /portal  booking portal
- POST /admin/toggle-portal-failure   makes portal updates fail (TC3)
