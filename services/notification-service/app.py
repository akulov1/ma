import os, time
from flask import Flask, request, jsonify
import psycopg2

APP_NAME = "notification-service"
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
    with db_conn() as conn:
        with conn.cursor() as cur:
            cur.execute("""
                CREATE TABLE IF NOT EXISTS notifications (
                    id SERIAL PRIMARY KEY,
                    user_id INTEGER NOT NULL,
                    channel TEXT NOT NULL DEFAULT 'email',
                    message TEXT NOT NULL,
                    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
                );
            """)
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

@app.post("/notify")
def notify():
    data = request.get_json(force=True, silent=True) or {}
    user_id = data.get("user_id")
    message = (data.get("message") or "").strip()
    channel = (data.get("channel") or "email").strip()
    if user_id is None or not message:
        return jsonify(error="user_id and message are required"), 400

    ensure_schema()
    with db_conn() as conn:
        with conn.cursor() as cur:
            cur.execute("INSERT INTO notifications(user_id, channel, message) VALUES (%s, %s, %s) RETURNING id;", (user_id, channel, message))
            nid = cur.fetchone()[0]
            conn.commit()
    return jsonify(status="queued", id=nid)

@app.get("/notifications/<int:user_id>")
def list_user_notifications(user_id: int):
    ensure_schema()
    with db_conn() as conn:
        with conn.cursor() as cur:
            cur.execute("SELECT id, channel, message, created_at FROM notifications WHERE user_id=%s ORDER BY created_at DESC LIMIT 50;", (user_id,))
            rows = cur.fetchall()
    return jsonify(items=[{"id": r[0], "channel": r[1], "message": r[2], "created_at": r[3].isoformat()} for r in rows])

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=PORT)
