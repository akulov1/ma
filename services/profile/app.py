import os
import psycopg2
import requests
from flask import Flask, request, redirect, render_template_string

DB_HOST = os.getenv("DB_HOST", "postgres")
DB_PORT = int(os.getenv("DB_PORT", "5432"))
DB_NAME = os.getenv("DB_NAME", "usersdb")
DB_USER = os.getenv("DB_USER", "user")
DB_PASSWORD = os.getenv("DB_PASSWORD", "password")

AUTH_URL = os.getenv("AUTH_URL", "http://auth-service:8000")
AUTH_PUBLIC_URL = os.getenv("AUTH_PUBLIC_URL", "/")  # для редиректа на страницу логина

WELCOME_MESSAGE = os.getenv("WELCOME_MESSAGE", "Добро пожаловать в платформу")
SESSION_COOKIE = "session_token"

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

def get_user(username: str):
    with db_conn() as conn, conn.cursor() as cur:
        cur.execute("SELECT username, status, created_at FROM users WHERE username=%s", (username,))
        return cur.fetchone()

def validate_with_auth(token: str):
    if not token:
        return None
    try:
        r = requests.get(AUTH_URL.rstrip("/") + "/api/validate", params={"token": token}, timeout=2)
        if r.status_code != 200:
            return None
        data = r.json()
        return data.get("username") if data.get("valid") else None
    except Exception:
        return None

app = Flask(__name__)

PROFILE_HTML = """
<!doctype html>
<html><head><meta charset="utf-8"><title>Профиль</title></head>
<body>
  <h1>Профиль</h1>
  <p>{{welcome}}</p>
  <p><b>Логин:</b> {{username}}</p>
  <p><b>Статус:</b> {{status}}</p>
  <p><b>Создан:</b> {{created_at}}</p>
  <p><a href="{{auth_public}}/logout">Выйти</a></p>
  <p><a href="{{auth_public}}/">На главную</a></p>
</body></html>
"""

@app.get("/profile")
def profile():
    token = request.cookies.get(SESSION_COOKIE)
    username = validate_with_auth(token)
    if not username:
        return redirect(AUTH_PUBLIC_URL.rstrip("/") + "/login")

    u = get_user(username)
    if not u:
        return redirect(AUTH_PUBLIC_URL.rstrip("/") + "/login")

    username, status, created_at = u
    return render_template_string(
        PROFILE_HTML,
        welcome=WELCOME_MESSAGE,
        username=username,
        status=status,
        created_at=str(created_at),
        auth_public=AUTH_PUBLIC_URL.rstrip("/"),
    )

@app.get("/health/live")
def health_live():
    return {"status": "alive"}, 200

@app.get("/health/ready")
def health_ready():
    return ({"status": "ready"}, 200) if is_db_ready() else ({"status": "not_ready"}, 503)

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=8000)
