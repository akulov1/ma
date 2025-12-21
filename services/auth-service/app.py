import os, time
from datetime import datetime, timedelta, timezone
from flask import Flask, request, jsonify
import psycopg2
import jwt
from werkzeug.security import generate_password_hash, check_password_hash

APP_NAME = "auth-service"
PORT = int(os.getenv("PORT", "8080"))
DB_HOST = os.getenv("DB_HOST", "postgres")
DB_PORT = int(os.getenv("DB_PORT", "5432"))
DB_NAME = os.getenv("DB_NAME", "platform")
DB_USER = os.getenv("DB_USER", "platform")
DB_PASSWORD = os.getenv("DB_PASSWORD", "platformpass")
JWT_SECRET = os.getenv("JWT_SECRET", "dev-secret")
JWT_ISSUER = os.getenv("JWT_ISSUER", "user-platform")
LOG_LEVEL = os.getenv("LOG_LEVEL", "INFO")

app = Flask(__name__)

def db_conn():
    return psycopg2.connect(
        host=DB_HOST, port=DB_PORT, dbname=DB_NAME, user=DB_USER, password=DB_PASSWORD
    )

def ensure_schema():
    with db_conn() as conn:
        with conn.cursor() as cur:
            cur.execute("""
                CREATE TABLE IF NOT EXISTS users (
                    id SERIAL PRIMARY KEY,
                    login TEXT UNIQUE NOT NULL,
                    password_hash TEXT NOT NULL,
                    status TEXT NOT NULL DEFAULT 'active',
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

@app.post("/register")
def register():
    data = request.get_json(force=True, silent=True) or {}
    login = (data.get("login") or "").strip().lower()
    password = (data.get("password") or "").strip()
    if not login or not password:
        return jsonify(error="login and password are required"), 400

    ensure_schema()
    try:
        pw_hash = generate_password_hash(password)
        with db_conn() as conn:
            with conn.cursor() as cur:
                cur.execute("INSERT INTO users(login, password_hash) VALUES (%s, %s) RETURNING id, status;", (login, pw_hash))
                user_id, status = cur.fetchone()
                conn.commit()
        return jsonify(id=user_id, login=login, status=status)
    except Exception as e:
        return jsonify(error="user already exists or db error", details=str(e)), 409

@app.post("/login")
def login():
    data = request.get_json(force=True, silent=True) or {}
    login = (data.get("login") or "").strip().lower()
    password = (data.get("password") or "").strip()
    if not login or not password:
        return jsonify(error="login and password are required"), 400

    ensure_schema()
    with db_conn() as conn:
        with conn.cursor() as cur:
            cur.execute("SELECT id, password_hash, status FROM users WHERE login=%s;", (login,))
            row = cur.fetchone()

    if not row:
        return jsonify(error="invalid credentials"), 401

    user_id, pw_hash, status = row[0], row[1], row[2]
    if status != "active":
        return jsonify(error="user is not active", status=status), 403

    if not check_password_hash(pw_hash, password):
        return jsonify(error="invalid credentials"), 401

    now = datetime.now(timezone.utc)
    payload = {
        "sub": str(user_id),
        "login": login,
        "status": status,
        "iss": JWT_ISSUER,
        "iat": int(now.timestamp()),
        "exp": int((now + timedelta(hours=2)).timestamp()),
    }
    token = jwt.encode(payload, JWT_SECRET, algorithm="HS256")
    return jsonify(token=token, user_id=user_id, login=login, status=status)

@app.get("/validate")
def validate():
    token = request.headers.get("Authorization", "").replace("Bearer ", "").strip()
    if not token:
        return jsonify(valid=False, error="missing token"), 401
    try:
        payload = jwt.decode(token, JWT_SECRET, algorithms=["HS256"], issuer=JWT_ISSUER)
        return jsonify(valid=True, user_id=payload.get("sub"), login=payload.get("login"), status=payload.get("status"))
    except Exception as e:
        return jsonify(valid=False, error=str(e)), 401

@app.get("/user/<int:user_id>")
def get_user(user_id: int):
    ensure_schema()
    with db_conn() as conn:
        with conn.cursor() as cur:
            cur.execute("SELECT id, login, status, created_at FROM users WHERE id=%s;", (user_id,))
            row = cur.fetchone()
    if not row:
        return jsonify(error="user not found"), 404
    return jsonify(id=row[0], login=row[1], status=row[2], created_at=row[3].isoformat())

@app.patch("/user/<int:user_id>/status")
def set_status(user_id: int):
    # demo endpoint to satisfy "optional statuses" requirement
    data = request.get_json(force=True, silent=True) or {}
    status = (data.get("status") or "").strip().lower()
    if status not in ("active", "inactive", "blocked"):
        return jsonify(error="status must be one of: active, inactive, blocked"), 400
    ensure_schema()
    with db_conn() as conn:
        with conn.cursor() as cur:
            cur.execute("UPDATE users SET status=%s WHERE id=%s;", (status, user_id))
            if cur.rowcount == 0:
                return jsonify(error="user not found"), 404
            conn.commit()
    return jsonify(status="ok", user_id=user_id, new_status=status)

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=PORT)
