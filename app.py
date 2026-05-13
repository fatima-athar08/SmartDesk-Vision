import os
from flask import Flask, jsonify, request, Response, render_template, send_from_directory
from flask_cors import CORS
import sqlite3
from datetime import datetime
import detect
import cv2
import glob
app = Flask(__name__)
CORS(app)
def login_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):

        if "user" not in session:
            return jsonify({"error": "Unauthorized"}), 401

        return f(*args, **kwargs)

    return decorated_function
from flask import session, redirect, url_for
from functools import wraps
app.secret_key = "smartdesk_secret_key"
# ✅ ADD THIS HERES
SCREENSHOT_FOLDER = "screenshots"
os.makedirs(SCREENSHOT_FOLDER, exist_ok=True)

DB_PATH = "detections.db"
# ============================================================
# DATABASE
# ============================================================

def init_db():

    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()

    c.execute("""
        CREATE TABLE IF NOT EXISTS detections (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            label TEXT,
            confidence REAL,
            timestamp TEXT
        )
    """)

    conn.commit()
    conn.close()

# ============================================================
# DASHBOARD
# ============================================================

@app.route("/dashboard")
def dashboard():

    if "user" not in session:
        return redirect("/")

    return render_template("dashboard.html")

# ============================================================
# VIDEO FEED
# ============================================================
@app.route('/video_feed')
@login_required    
def video_feed():

    if not detect.camera_running:
        return jsonify({"message": "Camera Off"})

    return Response(
        detect.generate_frames(),
        mimetype='multipart/x-mixed-replace; boundary=frame'
    )    
# ============================================================
# SCREENSHOT
# ============================================================
@app.route("/capture")
@login_required    
def capture():

    frame = detect.latest_frame

    if frame is None:
        return jsonify({"message": "No frame available yet"}), 400

    filename = f"screenshot_{datetime.now().strftime('%Y%m%d_%H%M%S')}.jpg"
    path = os.path.join(SCREENSHOT_FOLDER, filename)

    cv2.imwrite(path, frame)

    return jsonify({
        "message": "Screenshot Saved",
        "file": filename
    })    
    
# ============================================================
# CAMERA CONTROLS
# ============================================================

@app.route("/camera/start")
@login_required    
def start_camera():

    detect.camera_running = True

    return jsonify({
        "message": "Camera Started"
    })


@app.route("/camera/stop")
@login_required    
def stop_camera():

    detect.camera_running = False

    return jsonify({
        "message": "Camera Stopped"
    })

@app.route("/ai/pause")
@login_required    
def pause_ai():

    detect.ai_paused = not detect.ai_paused

    return jsonify({
        "paused": detect.ai_paused
    })    
# ============================================================
# SCREENSHOT GALLERY
# ============================================================

SCREENSHOT_FOLDER = "screenshots"

os.makedirs(SCREENSHOT_FOLDER, exist_ok=True)

@app.route("/screenshots")
@login_required     
def screenshots():

    files = []

    for f in os.listdir(SCREENSHOT_FOLDER):

        if f.endswith(".jpg"):
            files.append(f)

    files.sort(reverse=True)

    return jsonify(files)


@app.route("/screenshots/<filename>")
@login_required     
def screenshot_file(filename):

    return send_from_directory(SCREENSHOT_FOLDER, filename)
# ============================================================
# LOG DETECTION
# ============================================================

@app.route("/log", methods=["POST"])
def log_detection():

    data = request.get_json()

    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()

    c.execute(
        "INSERT INTO detections (label, confidence, timestamp) VALUES (?, ?, ?)",
        (data["label"], data["confidence"], data["timestamp"])
    )

    conn.commit()
    conn.close()

    return jsonify({"message": "Logged"})

# ============================================================
# GET DETECTIONS
# ============================================================

@app.route("/detections")
@login_required    
def detections():

    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()

    c.execute("SELECT * FROM detections ORDER BY id DESC")
    rows = c.fetchall()

    conn.close()

    return jsonify([
        {
            "id": r[0],
            "label": r[1],
            "confidence": r[2],
            "timestamp": r[3]
        }
        for r in rows
    ])

# ============================================================
# START (FIXED HERE)
# ============================================================
@app.route("/detections/latest")
@login_required    
def latest():
    conn = sqlite3.connect(DB_PATH)
    c    = conn.cursor()
    c.execute("SELECT * FROM detections ORDER BY id DESC LIMIT 10")
    rows = c.fetchall()
    conn.close()
    return jsonify([
        {"id":r[0],"label":r[1],"confidence":r[2],"timestamp":r[3]}
        for r in rows
    ])

@app.route("/stats")
@login_required     
def stats():
    conn = sqlite3.connect(DB_PATH)
    c    = conn.cursor()
    c.execute("SELECT label, COUNT(*) FROM detections GROUP BY label ORDER BY COUNT(*) DESC")
    rows = c.fetchall()
    conn.close()
    return jsonify([
        {"label":r[0],"count":r[1]}
        for r in rows
    ])

@app.route("/detections", methods=["DELETE"])
def clear():
    conn = sqlite3.connect(DB_PATH)
    c    = conn.cursor()
    c.execute("DELETE FROM detections")
    conn.commit()
    conn.close()
    return jsonify({"message":"Cleared!"})
@app.route("/")
def home():
    return render_template("login.html")

# ============================================================
# LOGIN API
# ============================================================

@app.route("/login", methods=["POST"])
def login_api():

    data = request.get_json()

    username = data.get("username")
    password = data.get("password")

    if username == "admin" and password == "1234":

        session["user"] = username

        return jsonify({
            "success": True
        })

    return jsonify({
        "success": False
    })  
# ============================================================
# LOGOUT
# ============================================================

@app.route("/logout")
def logout():

    session.pop("user", None)

    return redirect("/")
    
if __name__ == "__main__":

    init_db()

    print("🚀 SmartDesk Vision Running")
    print("📡 http://127.0.0.1:5000")

    # ❌ OLD: app.run(debug=True)
    # ✅ FIX: disable reloader completely

    port = int(os.environ.get("PORT", 5000))

    app.run(
        host="0.0.0.0",
        port=port,
        debug=False,
        use_reloader=False
    )