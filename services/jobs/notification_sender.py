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

with db_conn() as conn, conn.cursor() as cur:
    cur.execute("SELECT COUNT(*) FROM users WHERE status='active';")
    active_users = cur.fetchone()[0]

payload = {
    "job": "notification-sender",
    "action": "send_daily_notifications_stub",
    "active_users_targeted": active_users,
    "run_at_utc": now.isoformat() + "Z",
}

print(json.dumps(payload, ensure_ascii=False))
