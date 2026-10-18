import sqlite3

DB = "clinic.db"

def get_db():
    conn = sqlite3.connect(DB)
    conn.row_factory = sqlite3.Row
    return conn

def init_db():
    conn = get_db()
    conn.executescript("""
    DROP TABLE IF EXISTS bookings;
    DROP TABLE IF EXISTS slots;
    DROP TABLE IF EXISTS doctors;
    CREATE TABLE doctors(id INTEGER PRIMARY KEY, name TEXT, specialty TEXT);
    CREATE TABLE slots(
        id INTEGER PRIMARY KEY, doctor_id INTEGER, date TEXT, time TEXT,
        cms_available INTEGER DEFAULT 1,
        portal_available INTEGER DEFAULT 1);
    CREATE TABLE bookings(
        id INTEGER PRIMARY KEY, slot_id INTEGER, patient TEXT,
        status TEXT DEFAULT 'confirmed');
    """)
    doctors = [(1, "Dr. Mehta", "General"), (2, "Dr. Khan", "Pediatrics"), (3, "Dr. Rao", "Dermatology")]
    conn.executemany("INSERT INTO doctors VALUES(?,?,?)", doctors)
    dates = ["2026-10-19", "2026-10-20", "2026-10-21", "2026-10-22", "2026-10-23"]
    times = ["09:00", "10:00", "11:00"]
    sid = 1
    for d in doctors:
        for date in dates:
            for t in times:
                conn.execute("INSERT INTO slots(id,doctor_id,date,time) VALUES(?,?,?,?)", (sid, d[0], date, t))
                sid += 1
    # Existing bookings for Dr. Mehta on Friday 23 Oct (used for TC2)
    fri = conn.execute("SELECT id FROM slots WHERE doctor_id=1 AND date='2026-10-23' AND time IN ('09:00','10:00')").fetchall()
    for row, name in zip(fri, ["Ravi Kumar", "Sana Ali"]):
        conn.execute("INSERT INTO bookings(slot_id,patient) VALUES(?,?)", (row["id"], name))
    conn.commit()
    conn.close()

if __name__ == "__main__":
    init_db()
    print("Database created and seeded.")
