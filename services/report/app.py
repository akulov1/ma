import os
import datetime as dt
import psycopg2
from flask import Flask

DB_HOST = os.getenv("DB_HOST", "postgres")
DB_PORT = int(os.getenv("DB_PORT", "5432"))
DB_NAME = os.getenv("DB_NAME", "usersdb")
DB_USER = os.getenv("DB_USER", "user")
DB_PASSWORD = os.getenv("DB_PASSWORD", "password")

def db_conn():
    return psycopg2.connect(
        host=DB_HOST, port=DB_PORT, dbname=DB_NAME, user=DB_USER, password=DB_PASSWORD
    )

def is_db_ready() -> bool:
    try:
        with db_conn() as conn, conn.cursor() as cur:
            cur.execute("SELECT 1;")
            cur.fetchone()
        return True
    except Exception:
        return False

def get_summary():
    now = dt.datetime.utcnow()
    since = now - dt.timedelta(hours=24)
    with db_conn() as conn, conn.cursor() as cur:
        cur.execute("SELECT COUNT(*) FROM users;")
        total = cur.fetchone()[0]

        cur.execute("SELECT status, COUNT(*) FROM users GROUP BY status;")
        by_status = {row[0]: row[1] for row in cur.fetchall()}

        cur.execute("SELECT COUNT(*) FROM users WHERE created_at >= %s;", (since,))
        new_24h = cur.fetchone()[0]

        cur.execute("SELECT COUNT(*) FROM sessions WHERE created_at >= %s;", (since,))
        sessions_24h = cur.fetchone()[0]

    return {
        "total_users": total,
        "users_by_status": by_status,
        "new_users_last_24h": new_24h,
        "sessions_last_24h": sessions_24h,
        "generated_at_utc": now.isoformat() + "Z",
    }

app = Flask(__name__)

@app.get("/reports/summary")
def reports_summary():
    return get_summary(), 200

@app.get("/health/live")
def health_live():
    return {"status": "alive"}, 200

@app.get("/health/ready")
def health_ready():
    return ({"status": "ready"}, 200) if is_db_ready() else ({"status": "not_ready"}, 503)

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=8000)
