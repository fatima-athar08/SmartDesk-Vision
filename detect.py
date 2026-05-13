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

THRESHOLD             = 80    # minimum confidence % to consider a detection
REQUIRED_STABLE_FRAMES = 5    # consecutive frames before confirming object
DETECTION_COOLDOWN    = 5     # seconds before re-logging same object
FRAME_SKIP            = 1     # process every 2nd frame (0 = every frame)

camera_running = True
ai_paused      = False

prev_time      = 0
latest_frame   = None
frame_count    = 0

# Detection memory
last_detected_label = None
last_detection_time = 0

# Stability buffer  — rolling window instead of simple counter
STABILITY_WINDOW = 7          # look at last N predictions
stability_buffer = []         # stores recent predicted labels

# Ghost-phone suppression — phone needs higher bar
PHONE_THRESHOLD = 88          # phone requires stricter confidence

# ============================================================
# CAMERA  (try index 0 then 1)
# ============================================================

camera = cv2.VideoCapture(0)

if not camera.isOpened():
    camera = cv2.VideoCapture(1)

if not camera.isOpened():
    print("❌ ERROR: Camera not accessible")
else:
    # Faster buffer — reduce latency
    camera.set(cv2.CAP_PROP_BUFFERSIZE, 1)
    camera.set(cv2.CAP_PROP_FRAME_WIDTH,  640)
    camera.set(cv2.CAP_PROP_FRAME_HEIGHT, 480)
    camera.set(cv2.CAP_PROP_FPS, 30)

# ============================================================
# LOAD MODEL
# ============================================================

print("🚀 Loading AI Model...")

model = tf.keras.models.load_model("model.h5")

with open("class_names.json", "r") as f:
    class_names = json.load(f)

print("✅ Model Loaded Successfully")

# ============================================================
# PREPROCESSING
# ============================================================

def preprocess_frame(frame):
    img = cv2.resize(frame, (IMG_SIZE, IMG_SIZE))
    img = img.astype("float32") / 255.0
    img = np.expand_dims(img, axis=0)
    return img

# ============================================================
# UI COLORS
# ============================================================

def get_color(label):
    colors = {
        "phone":    (0,   0,   255),
        "mouse":    (255, 0,   0  ),
        "keyboard": (0,   255, 0  ),
        "charger":  (0,   255, 255),
        "No Object":(150, 150, 150),
    }
    return colors.get(label, (255, 255, 255))

# ============================================================
# LOG DETECTION
# ============================================================

def log_detection(label, confidence):
    try:
        requests.post(
            "http://127.0.0.1:5000/log",
            json={
                "label":      label,
                "confidence": float(confidence),
                "timestamp":  datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            },
            timeout=1           # don't block the stream
        )
    except Exception:
        pass

# ============================================================
# STABILITY HELPER  — majority vote over rolling window
# ============================================================

def get_stable_label(buffer):
    """
    Returns a label only if it appears in the majority of the
    stability window, otherwise returns None.
    """
    if len(buffer) < STABILITY_WINDOW:
        return None

    from collections import Counter
    counts = Counter(buffer)
    top_label, top_count = counts.most_common(1)[0]

    # Require majority (>50 %) of recent window
    if top_count >= (STABILITY_WINDOW // 2 + 1):
        return top_label

    return None

# ============================================================
# MAIN VIDEO STREAM
# ============================================================

def generate_frames():

    global prev_time
    global camera_running
    global ai_paused
    global frame_count
    global last_detected_label
    global last_detection_time
    global stability_buffer
    global latest_frame

    while True:

        # ====================================================
        # FRAME SKIP  (keeps webcam buffer fresh)
        # ====================================================

        frame_count += 1

        if frame_count % (FRAME_SKIP + 1) != 0:
            # Still grab the frame so the camera buffer doesn't fill up
            camera.grab()
            continue

        # ====================================================
        # CAMERA OFF
        # ====================================================

        if not camera_running:
            time.sleep(0.1)
            continue

        success, frame = camera.read()

        if not success or frame is None:
            continue

        # ====================================================
        # FPS
        # ====================================================

        current_time = time.time()
        fps = 1 / (current_time - prev_time) if prev_time else 0
        prev_time = current_time

        # ====================================================
        # AI PAUSED  — stream raw frame with overlay
        # ====================================================

        if ai_paused:

            cv2.putText(
                frame, "AI DETECTION PAUSED",
                (30, 60), cv2.FONT_HERSHEY_SIMPLEX,
                1, (0, 0, 255), 3
            )

            _draw_fps_time(frame, fps)

            ret, buffer = cv2.imencode('.jpg', frame, [cv2.IMWRITE_JPEG_QUALITY, 85])
            yield _mjpeg(buffer.tobytes())
            continue

        # ====================================================
        # AI PREDICTION
        # ====================================================

        processed   = preprocess_frame(frame)
        predictions = model.predict(processed, verbose=0)[0]
        class_id    = int(np.argmax(predictions))
        confidence  = float(predictions[class_id]) * 100

        predicted_label = (
            class_names[str(class_id)]
            if isinstance(class_names, dict)
            else class_names[class_id]
        )

        # ====================================================
        # PER-CLASS THRESHOLD  (phone needs higher confidence)
        # ====================================================

        effective_threshold = (
            PHONE_THRESHOLD
            if predicted_label == "phone"
            else THRESHOLD
        )

        raw_label = (
            predicted_label
            if confidence >= effective_threshold
            else "No Object"
        )

        # ====================================================
        # ROLLING STABILITY BUFFER
        # ====================================================

        stability_buffer.append(raw_label)

        if len(stability_buffer) > STABILITY_WINDOW:
            stability_buffer.pop(0)

        stable = get_stable_label(stability_buffer)

        # Only accept a real object from the stable vote
        label = stable if (stable and stable != "No Object") else "No Object"

        # ====================================================
        # GHOST DETECTION GUARD
        # — if majority is "No Object", hard-reset
        # ====================================================

        no_obj_count = stability_buffer.count("No Object")

        if no_obj_count >= (STABILITY_WINDOW // 2 + 1):
            label = "No Object"
            last_detected_label = None   # allow fresh detection next time

        # ====================================================
        # LOG  — once per appearance, then cooldown
        # ====================================================

        if label != "No Object":

            allow_log = (
                label != last_detected_label
                or (current_time - last_detection_time) > DETECTION_COOLDOWN
            )

            if allow_log:
                log_detection(label, confidence)
                last_detected_label = label
                last_detection_time = current_time

        # ====================================================
        # DRAW UI
        # ====================================================

        h, w, _ = frame.shape
        color    = get_color(label)

        if label != "No Object":

            # Outer border
            cv2.rectangle(frame, (20, 20), (w - 20, h - 20), color, 4)

            # Label background
            cv2.rectangle(frame, (20, 20), (460, 80), color, -1)

            # Label text
            cv2.putText(
                frame,
                f"{label.upper()} ({confidence:.1f}%)",
                (30, 65),
                cv2.FONT_HERSHEY_SIMPLEX, 1, (0, 0, 0), 3
            )

        else:

            cv2.putText(
                frame, "No Object Detected",
                (30, 60), cv2.FONT_HERSHEY_SIMPLEX,
                1, (180, 180, 180), 2
            )

        _draw_fps_time(frame, fps)

        # ====================================================
        # STORE + STREAM
        # ====================================================

        latest_frame = frame.copy()

        ret, buffer = cv2.imencode('.jpg', frame, [cv2.IMWRITE_JPEG_QUALITY, 85])
        yield _mjpeg(buffer.tobytes())

# ============================================================
# HELPERS
# ============================================================

def _draw_fps_time(frame, fps):
    h, w = frame.shape[:2]

    cv2.putText(
        frame, f"FPS: {int(fps)}",
        (30, h - 20), cv2.FONT_HERSHEY_SIMPLEX,
        0.8, (255, 255, 255), 2
    )

    cv2.putText(
        frame, datetime.now().strftime("%H:%M:%S"),
        (w - 150, h - 20), cv2.FONT_HERSHEY_SIMPLEX,
        0.8, (255, 255, 255), 2
    )

    cv2.putText(
        frame, "SmartDesk Vision AI",
        (30, h - 60), cv2.FONT_HERSHEY_SIMPLEX,
        0.8, (255, 255, 255), 2
    )


def _mjpeg(frame_bytes):
    return (
        b'--frame\r\n'
        b'Content-Type: image/jpeg\r\n\r\n' +
        frame_bytes +
        b'\r\n'
    )