import os, time
from datetime import datetime, timedelta, timezone
from flask import Flask, request, jsonify, render_template, redirect, url_for, session
import psycopg2
import jwt
from werkzeug.security import generate_password_hash, check_password_hash

APP_NAME = "monolith-app"
PORT = int(os.getenv("PORT", "8080"))

DB_HOST = os.getenv("DB_HOST", "postgres")
DB_PORT = int(os.getenv("DB_PORT", "5432"))
DB_NAME = os.getenv("DB_NAME", "platform")
DB_USER = os.getenv("DB_USER", "platform")
DB_PASSWORD = os.getenv("DB_PASSWORD", "platformpass")

JWT_SECRET = os.getenv("JWT_SECRET", "dev-secret")
JWT_ISSUER = os.getenv("JWT_ISSUER", "user-platform")
FLASK_SECRET_KEY = os.getenv("FLASK_SECRET_KEY", JWT_SECRET)

LOGIN_TITLE = os.getenv("LOGIN_TITLE", "Вход в систему")
REGISTER_TITLE = os.getenv("REGISTER_TITLE", "Регистрация")
WELCOME_MESSAGE = os.getenv("WELCOME_MESSAGE", "Добро пожаловать в платформу")

app = Flask(__name__)
app.secret_key = FLASK_SECRET_KEY

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
            cur.execute("""
                CREATE TABLE IF NOT EXISTS profiles (
                    user_id INTEGER PRIMARY KEY,
                    full_name TEXT NOT NULL,
                    bio TEXT NOT NULL DEFAULT '',
                    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
                );
            """)
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

@app.get("/")
def index():
    return render_template(
        "index.html",
        LOGIN_TITLE=LOGIN_TITLE,
        REGISTER_TITLE=REGISTER_TITLE,
        WELCOME_MESSAGE=WELCOME_MESSAGE,
        is_auth=bool(session.get("token")),
    )

@app.get("/register")
def register_page():
    return render_template("register.html", REGISTER_TITLE=REGISTER_TITLE)

@app.post("/register")
def register_action():
    login = (request.form.get("login") or "").strip().lower()
    password = (request.form.get("password") or "").strip()
    if not login or not password:
        return render_template("register.html", REGISTER_TITLE=REGISTER_TITLE, error="Введите логин и пароль"), 400

    ensure_schema()
    try:
        pw_hash = generate_password_hash(password)
        with db_conn() as conn:
            with conn.cursor() as cur:
                cur.execute("INSERT INTO users(login, password_hash) VALUES (%s, %s) RETURNING id;", (login, pw_hash))
                user_id = cur.fetchone()[0]
                conn.commit()
        return redirect(url_for("login_page"))
    except Exception as e:
        return render_template("register.html", REGISTER_TITLE=REGISTER_TITLE, error=f"Ошибка регистрации: {e}"), 409

@app.get("/login")
def login_page():
    return render_template("login.html", LOGIN_TITLE=LOGIN_TITLE)

@app.post("/login")
def login_action():
    login = (request.form.get("login") or "").strip().lower()
    password = (request.form.get("password") or "").strip()
    if not login or not password:
        return render_template("login.html", LOGIN_TITLE=LOGIN_TITLE, error="Введите логин и пароль"), 400

    ensure_schema()
    with db_conn() as conn:
        with conn.cursor() as cur:
            cur.execute("SELECT id, password_hash, status FROM users WHERE login=%s;", (login,))
            row = cur.fetchone()

    if not row:
        return render_template("login.html", LOGIN_TITLE=LOGIN_TITLE, error="Неверные учетные данные"), 401

    user_id, pw_hash, status = row[0], row[1], row[2]
    if status != "active":
        return render_template("login.html", LOGIN_TITLE=LOGIN_TITLE, error=f"Пользователь не активен: {status}"), 403

    if not check_password_hash(pw_hash, password):
        return render_template("login.html", LOGIN_TITLE=LOGIN_TITLE, error="Неверные учетные данные"), 401

    now = datetime.now(timezone.utc)
    payload = {"sub": str(user_id), "login": login, "status": status, "iss": JWT_ISSUER, "iat": int(now.timestamp()), "exp": int((now + timedelta(hours=2)).timestamp())}
    token = jwt.encode(payload, JWT_SECRET, algorithm="HS256")
    session["token"] = token
    session["user_id"] = user_id
    return redirect(url_for("me"))

@app.get("/logout")
def logout():
    session.clear()
    return redirect(url_for("index"))

@app.get("/me")
def me():
    token = session.get("token")
    if not token:
        return redirect(url_for("login_page"))
    try:
        payload = jwt.decode(token, JWT_SECRET, algorithms=["HS256"], issuer=JWT_ISSUER)
    except Exception:
        session.clear()
        return redirect(url_for("login_page"))

    user_id = int(payload.get("sub"))
    ensure_schema()
    with db_conn() as conn:
        with conn.cursor() as cur:
            cur.execute("SELECT id, login, status FROM users WHERE id=%s;", (user_id,))
            u = cur.fetchone()
            cur.execute("SELECT full_name, bio FROM profiles WHERE user_id=%s;", (user_id,))
            p = cur.fetchone()

    user = {"id": u[0], "login": u[1], "status": u[2]} if u else {"id": user_id, "login": payload.get("login"), "status": payload.get("status")}
    profile = {"full_name": "", "bio": ""} if not p else {"full_name": p[0], "bio": p[1]}

    return render_template("me.html", user=user, profile=profile)

@app.post("/me/profile")
def save_profile():
    token = session.get("token")
    if not token:
        return redirect(url_for("login_page"))
    user_id = session.get("user_id")
    full_name = (request.form.get("full_name") or "").strip()
    bio = (request.form.get("bio") or "").strip()
    if not full_name:
        return redirect(url_for("me"))

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
    return redirect(url_for("me"))

# JSON endpoints (оставлены для проверки)
@app.post("/api/notify")
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

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=PORT)
