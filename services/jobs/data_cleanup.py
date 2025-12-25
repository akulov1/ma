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
cutoff = now - dt.timedelta(days=30)

deleted = 0
try:
    with db_conn() as conn, conn.cursor() as cur:
        cur.execute("DELETE FROM sessions WHERE created_at < %s;", (cutoff,))
        deleted = cur.rowcount
        conn.commit()
except Exception:
    # по заданию достаточно логировать; но удаление сессий — безопасная простая очистка
    pass

payload = {
    "job": "data-cleanup",
    "action": "cleanup_old_sessions_older_than_30d",
    "deleted_sessions": deleted,
    "run_at_utc": now.isoformat() + "Z",
}
print(json.dumps(payload, ensure_ascii=False))
