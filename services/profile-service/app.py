import os, time
from flask import Flask, request, jsonify
import psycopg2

APP_NAME = "profile-service"
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
                CREATE TABLE IF NOT EXISTS profiles (
                    user_id INTEGER PRIMARY KEY,
                    full_name TEXT NOT NULL,
                    bio TEXT NOT NULL DEFAULT '',
                    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
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

@app.get("/profile/<int:user_id>")
def get_profile(user_id: int):
    ensure_schema()
    with db_conn() as conn:
        with conn.cursor() as cur:
            cur.execute("SELECT user_id, full_name, bio, updated_at FROM profiles WHERE user_id=%s;", (user_id,))
            row = cur.fetchone()
    if not row:
        return jsonify(error="profile not found"), 404
    return jsonify(user_id=row[0], full_name=row[1], bio=row[2], updated_at=row[3].isoformat())

@app.put("/profile/<int:user_id>")
def upsert_profile(user_id: int):
    data = request.get_json(force=True, silent=True) or {}
    full_name = (data.get("full_name") or "").strip()
    bio = (data.get("bio") or "").strip()
    if not full_name:
        return jsonify(error="full_name is required"), 400

    ensure_schema()
    with db_conn() as conn:
        with conn.cursor() as cur:
            cur.execute("""
                INSERT INTO profiles(user_id, full_name, bio)
                VALUES (%s, %s, %s)
                ON CONFLICT (user_id)
                DO UPDATE SET full_name=EXCLUDED.full_name, bio=EXCLUDED.bio, updated_at=NOW();
            """, (user_id, full_name, bio))
            conn.commit()
    return jsonify(status="ok", user_id=user_id)

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=PORT)
