import os
import requests
from flask import Flask, request, render_template, redirect, url_for, session, jsonify

APP_NAME = "ui-service"
PORT = int(os.getenv("PORT", "8080"))
FLASK_SECRET_KEY = os.getenv("FLASK_SECRET_KEY", os.getenv("JWT_SECRET", "dev-ui-secret"))

AUTH_URL = os.getenv("AUTH_URL", "http://auth-service:80")
PROFILE_URL = os.getenv("PROFILE_URL", "http://profile-service:80")
NOTIF_URL = os.getenv("NOTIF_URL", "http://notification-service:80")
REPORT_URL = os.getenv("REPORT_URL", "http://report-service:80")

LOGIN_TITLE = os.getenv("LOGIN_TITLE", "Вход в систему")
REGISTER_TITLE = os.getenv("REGISTER_TITLE", "Регистрация")
WELCOME_MESSAGE = os.getenv("WELCOME_MESSAGE", "Добро пожаловать в платформу")

app = Flask(__name__)
app.secret_key = FLASK_SECRET_KEY

def get_token():
    return session.get("token", "")

def auth_headers():
    t = get_token()
    return {"Authorization": f"Bearer {t}"} if t else {}

@app.get("/health/live")
def live():
    return jsonify(status="ok", service=APP_NAME)

@app.get("/health/ready")
def ready():
    try:
        r = requests.get(f"{AUTH_URL}/health/ready", timeout=2)
        if r.status_code == 200:
            return jsonify(status="ready", service=APP_NAME)
        return jsonify(status="not-ready", service=APP_NAME, details=r.text), 503
    except Exception as e:
        return jsonify(status="not-ready", service=APP_NAME, error=str(e)), 503

# 1) Главная страница — информация и ссылки
@app.get("/")
def index():
    return render_template(
        "index.html",
        WELCOME_MESSAGE=WELCOME_MESSAGE,
        LOGIN_TITLE=LOGIN_TITLE,
        REGISTER_TITLE=REGISTER_TITLE,
        is_auth=bool(get_token()),
    )

# 2) Окно регистрации
@app.get("/register")
def register_page():
    return render_template("register.html", REGISTER_TITLE=REGISTER_TITLE)

@app.post("/register")
def register_action():
    login = (request.form.get("login") or "").strip()
    password = (request.form.get("password") or "").strip()
    if not login or not password:
        return render_template("register.html", REGISTER_TITLE=REGISTER_TITLE, error="Введите логин и пароль"), 400

    r = requests.post(f"{AUTH_URL}/register", json={"login": login, "password": password}, timeout=5)
    if r.status_code >= 300:
        return render_template("register.html", REGISTER_TITLE=REGISTER_TITLE, error=f"Ошибка регистрации: {r.text}"), 400
    return redirect(url_for("login_page"))

# 3) Окно авторизации
@app.get("/login")
def login_page():
    return render_template("login.html", LOGIN_TITLE=LOGIN_TITLE)

@app.post("/login")
def login_action():
    login = (request.form.get("login") or "").strip()
    password = (request.form.get("password") or "").strip()
    if not login or not password:
        return render_template("login.html", LOGIN_TITLE=LOGIN_TITLE, error="Введите логин и пароль"), 400

    r = requests.post(f"{AUTH_URL}/login", json={"login": login, "password": password}, timeout=5)
    if r.status_code != 200:
        return render_template("login.html", LOGIN_TITLE=LOGIN_TITLE, error=f"Ошибка входа: {r.text}"), 401

    data = r.json()
    session["token"] = data.get("token", "")
    session["user_id"] = data.get("user_id")
    return redirect(url_for("me"))

@app.get("/logout")
def logout():
    session.clear()
    return redirect(url_for("index"))

# 4) Личная страница пользователя (после логина)
@app.get("/me")
def me():
    token = get_token()
    if not token:
        return redirect(url_for("login_page"))

    # validate session
    v = requests.get(f"{AUTH_URL}/validate", headers=auth_headers(), timeout=5)
    if v.status_code != 200:
        session.clear()
        return redirect(url_for("login_page"))

    vj = v.json()
    user_id = session.get("user_id") or int(vj.get("user_id"))
    user = requests.get(f"{AUTH_URL}/user/{user_id}", timeout=5)
    user_json = user.json() if user.status_code == 200 else {"id": user_id, "login": vj.get("login"), "status": vj.get("status")}

    # profile (может отсутствовать)
    pr = requests.get(f"{PROFILE_URL}/profile/{user_id}", timeout=5)
    profile = pr.json() if pr.status_code == 200 else {"user_id": user_id, "full_name": "", "bio": ""}

    return render_template("me.html", user=user_json, profile=profile)

@app.post("/me/profile")
def save_profile():
    token = get_token()
    if not token:
        return redirect(url_for("login_page"))
    user_id = session.get("user_id")
    full_name = (request.form.get("full_name") or "").strip()
    bio = (request.form.get("bio") or "").strip()
    if not full_name:
        return redirect(url_for("me"))

    requests.put(f"{PROFILE_URL}/profile/{user_id}", json={"full_name": full_name, "bio": bio}, timeout=5)
    return redirect(url_for("me"))

# Остались JSON API (удобно для проверки)
@app.post("/api/notify")
def api_notify():
    payload = request.get_json(force=True, silent=True) or {}
    r = requests.post(f"{NOTIF_URL}/notify", json=payload, timeout=5)
    return (r.text, r.status_code, {"Content-Type": "application/json"})

@app.get("/api/report/<int:user_id>")
def api_report(user_id: int):
    r = requests.get(f"{REPORT_URL}/report/{user_id}", timeout=5)
    return (r.text, r.status_code, {"Content-Type": "application/json"})

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=PORT)
