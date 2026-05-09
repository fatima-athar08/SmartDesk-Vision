import cv2
import numpy as np
import time
from datetime import datetime
import tensorflow as tf
import json
import requests

# ============================================================
# CONFIG
# ============================================================

IMG_SIZE = 224
CONFIDENCE_MIN = 90
THRESHOLD = 92

camera_running = True
ai_paused = False

prev_time = 0
latest_frame = None
frame_count = 0

# Detection memory
last_detected_label = None
last_detection_time = 0

DETECTION_COOLDOWN = 3

# Stability detection
stable_label = None
stable_count = 0
REQUIRED_STABLE_FRAMES = 7

# ============================================================
# CAMERA (SAFE INIT)
# ============================================================

camera = cv2.VideoCapture(0)

if not camera.isOpened():
    print("❌ ERROR: Camera not accessible")

# ============================================================
# LOAD MODEL + CLASS NAMES
# ============================================================

model = tf.keras.models.load_model("model.h5")

with open("class_names.json", "r") as f:
    class_names = json.load(f)

# ============================================================
# PREPROCESSING
# ============================================================

def preprocess_frame(frame):

    img = cv2.resize(frame, (IMG_SIZE, IMG_SIZE))
    img = img / 255.0
    img = np.expand_dims(img, axis=0)

    return img

# ============================================================
# UI COLOR
# ============================================================

def get_color(label):

    if label == "phone":
        return (0, 0, 255)

    elif label == "mouse":
        return (255, 0, 0)

    elif label == "keyboard":
        return (0, 255, 0)

    elif label == "charger":
        return (0, 255, 255)

    elif label == "No Object":
        return (150, 150, 150)

    return (255, 255, 255)

# ============================================================
# LOGGING
# ============================================================

def log_detection(label, confidence):

    try:

        requests.post(
            "http://127.0.0.1:5000/log",
            json={
                "label": label,
                "confidence": float(confidence),
                "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            }
        )

    except:
        pass

# ============================================================
# MAIN STREAM GENERATOR
# ============================================================

def generate_frames():

    global prev_time
    global camera_running
    global ai_paused
    global frame_count
    global last_detected_label
    global last_detection_time
    global stable_label
    global stable_count
    global latest_frame

    while True:

        # ====================================================
        # PROCESS EVERY 5TH FRAME
        # ====================================================

        frame_count += 1

        if frame_count % 5 != 0:
            continue

        # ====================================================
        # CAMERA OFF
        # ====================================================

        if not camera_running:
            time.sleep(0.2)
            continue

        success, frame = camera.read()

        if not success or frame is None:
            continue

        # ====================================================
        # AI PAUSED
        # ====================================================

        if ai_paused:

            cv2.putText(
                frame,
                "AI DETECTION PAUSED",
                (30, 60),
                cv2.FONT_HERSHEY_SIMPLEX,
                1,
                (0, 0, 255),
                3
            )

            ret, buffer = cv2.imencode('.jpg', frame)

            frame = buffer.tobytes()

            yield (
                b'--frame\r\n'
                b'Content-Type: image/jpeg\r\n\r\n' +
                frame +
                b'\r\n'
            )

            continue

        # ====================================================
        # AI PREDICTION
        # ====================================================

        processed = preprocess_frame(frame)

        predictions = model.predict(processed, verbose=0)[0]

        class_id = int(np.argmax(predictions))

        confidence = float(predictions[class_id]) * 100

        predicted_label = (
            class_names[str(class_id)]
            if isinstance(class_names, dict)
            else class_names[class_id]
        )

        # ====================================================
        # STABLE REAL-TIME DETECTION
        # ====================================================

        if confidence >= THRESHOLD:

            # Same object repeatedly detected
            if predicted_label == stable_label:

                stable_count += 1

            else:

                stable_label = predicted_label
                stable_count = 1

            # Detect only after stable frames
            if stable_count >= REQUIRED_STABLE_FRAMES:

                label = predicted_label

            else:

                label = "No Object"

        else:

            label = "No Object"

            stable_label = None
            stable_count = 0
            last_detected_label = None

        # ====================================================
        # UI SETTINGS
        # ====================================================

        h, w, _ = frame.shape

        color = get_color(label)

        current_time = time.time()

        fps = 1 / (current_time - prev_time) if prev_time else 0

        prev_time = current_time

        # ====================================================
        # DRAW DETECTION
        # ====================================================

        if label != "No Object":

            # Border
            cv2.rectangle(
                frame,
                (20, 20),
                (w - 20, h - 20),
                color,
                4
            )

            # Top box
            cv2.rectangle(
                frame,
                (20, 20),
                (420, 80),
                color,
                -1
            )

            # Detection text
            text = f"{label} ({confidence:.1f}%)"

            cv2.putText(
                frame,
                text,
                (30, 65),
                cv2.FONT_HERSHEY_SIMPLEX,
                1,
                (0, 0, 0),
                3
            )

            # ====================================================
            # DETECT ONLY ONCE
            # ====================================================

            allow_detection = (
                label != last_detected_label
                or (current_time - last_detection_time) > DETECTION_COOLDOWN
            )

            if allow_detection:

                log_detection(label, confidence)

                last_detected_label = label
                last_detection_time = current_time

        else:

            cv2.putText(
                frame,
                "No Object Detected",
                (30, 60),
                cv2.FONT_HERSHEY_SIMPLEX,
                1,
                (200, 200, 200),
                2
            )

        # ====================================================
        # FPS + TIME
        # ====================================================

        cv2.putText(
            frame,
            f"FPS: {int(fps)}",
            (30, h - 20),
            cv2.FONT_HERSHEY_SIMPLEX,
            0.8,
            (255, 255, 255),
            2
        )

        timestamp = datetime.now().strftime("%H:%M:%S")

        cv2.putText(
            frame,
            timestamp,
            (w - 150, h - 20),
            cv2.FONT_HERSHEY_SIMPLEX,
            0.8,
            (255, 255, 255),
            2
        )

        cv2.putText(
            frame,
            "SmartDesk Vision AI",
            (30, h - 60),
            cv2.FONT_HERSHEY_SIMPLEX,
            0.8,
            color,
            2
        )

        # ====================================================
        # STORE FRAME
        # ====================================================

        latest_frame = frame.copy()

        # ====================================================
        # STREAM OUTPUT
        # ====================================================

        ret, buffer = cv2.imencode('.jpg', frame)

        frame = buffer.tobytes()

        yield (
            b'--frame\r\n'
            b'Content-Type: image/jpeg\r\n\r\n' +
            frame +
            b'\r\n'
        )