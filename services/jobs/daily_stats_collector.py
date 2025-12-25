import os
import datetime as dt
import json
import psycopg2

DB_HOST = os.getenv("DB_HOST", "postgres")
DB_PORT = int(os.getenv("DB_PORT", "5432"))
DB_NAME = os.getenv("DB_NAME", "usersdb")
DB_USER = os.getenv("DB_USER", "user")
DB_PASSWORD = os.getenv("DB_PASSWORD", "password")

def db_conn():
    return psycopg2.connect(host=DB_HOST, port=DB_PORT, dbname=DB_NAME, user=DB_USER, password=DB_PASSWORD)

now = dt.datetime.utcnow()
since = now - dt.timedelta(hours=24)

with db_conn() as conn, conn.cursor() as cur:
    cur.execute("SELECT COUNT(*) FROM users;")
    total_users = cur.fetchone()[0]

    cur.execute("SELECT COUNT(*) FROM users WHERE created_at >= %s;", (since,))
    new_users = cur.fetchone()[0]

    cur.execute("SELECT status, COUNT(*) FROM users GROUP BY status;")
    status_counts = {r[0]: r[1] for r in cur.fetchall()}

    cur.execute("SELECT COUNT(*) FROM sessions WHERE created_at >= %s;", (since,))
    sessions_24h = cur.fetchone()[0]

payload = {
    "job": "daily-stats-collector",
    "window_hours": 24,
    "total_users": total_users,
    "new_users_last_24h": new_users,
    "sessions_last_24h": sessions_24h,
    "users_by_status": status_counts,
    "generated_at_utc": now.isoformat() + "Z",
}

print(json.dumps(payload, ensure_ascii=False))
