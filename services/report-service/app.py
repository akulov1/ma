import os, time
from flask import Flask, jsonify
import psycopg2

APP_NAME = "report-service"
PORT = int(os.getenv("PORT", "8080"))
DB_HOST = os.getenv("DB_HOST", "postgres")
DB_PORT = int(os.getenv("DB_PORT", "5432"))
DB_NAME = os.getenv("DB_NAME", "platform")
DB_USER = os.getenv("DB_USER", "platform")
DB_PASSWORD = os.getenv("DB_PASSWORD", "platformpass")

app = Flask(__name__)

def db_conn():
    return psycopg2.connect(
        host=DB_HOST, port=DB_PORT, dbname=DB_NAME, user=DB_USER, password=DB_PASSWORD
    )

def ensure_schema():
    # tables are created in other services too; keep ready check consistent
    with db_conn() as conn:
        with conn.cursor() as cur:
            cur.execute("SELECT 1;")
            conn.commit()

@app.get("/health/live")
def live():
    return jsonify(status="ok", service=APP_NAME, ts=int(time.time()))

@app.get("/health/ready")
def ready():
    try:
        ensure_schema()
        return jsonify(status="ready", service=APP_NAME)
    except Exception as e:
        return jsonify(status="not-ready", service=APP_NAME, error=str(e)), 503

@app.get("/report/<int:user_id>")
def user_report(user_id: int):
    with db_conn() as conn:
        with conn.cursor() as cur:
            cur.execute("SELECT email, created_at FROM users WHERE id=%s;", (user_id,))
            u = cur.fetchone()
            cur.execute("SELECT full_name, bio, updated_at FROM profiles WHERE user_id=%s;", (user_id,))
            p = cur.fetchone()
            cur.execute("SELECT COUNT(*) FROM notifications WHERE user_id=%s;", (user_id,))
            n = cur.fetchone()[0]

    if not u:
        return jsonify(error="user not found"), 404

    report = {
        "user_id": user_id,
        "email": u[0],
        "registered_at": u[1].isoformat(),
        "profile": None if not p else {"full_name": p[0], "bio": p[1], "updated_at": p[2].isoformat()},
        "notifications_count": int(n),
        "generated_at": int(time.time()),
    }
    return jsonify(report)

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=PORT)
