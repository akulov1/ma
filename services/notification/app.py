from flask import Flask, request

app = Flask(__name__)

@app.post("/api/notify/register")
def notify_register():
    data = request.get_json(silent=True) or {}
    username = data.get("username", "unknown")
    print(f"[notification-service] new registration: {username}")
    return {"ok": True}, 200

@app.get("/health/live")
def health_live():
    return {"status": "alive"}, 200

@app.get("/health/ready")
def health_ready():
    return {"status": "ready"}, 200

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=8000)
