#Created by Wassim and Fairouz on 11/05/2025.
from flask import Flask, Response, jsonify 
import threading
import cv2 
import imutils  
import numpy as np
from collections import deque
import time

app = Flask(__name__)

# --- Couleurs à détecter ---
COLOR_RANGES = {
    "bleu": {"lower": (100, 150, 0), "upper": (140, 255, 255), "bgr": (255, 0, 0)},
    "rose": {"lower": (160, 100, 100), "upper": (170, 255, 255), "bgr": (255, 0, 255)},
}

# Mémoire
trajectories = {color: deque(maxlen=64) for color in COLOR_RANGES}
latest_centers = {color: None for color in COLOR_RANGES}  # mises à jour en continu
coords_for_api = {color: None for color in COLOR_RANGES}  # mises à jour à 2 FPS

output_frame = None
lock = threading.Lock()

# Fonction principale qui capture la vidéo, détecte les objets colorés, met à jour les trajectoires et prépare l'image annotée
def video_processing():
    global output_frame, latest_centers

    cap = cv2.VideoCapture(0)
    cap.set(cv2.CAP_PROP_FRAME_WIDTH, 640)
    cap.set(cv2.CAP_PROP_FRAME_HEIGHT, 480)

    while True:
        success, frame = cap.read()
        if not success:
            continue

        frame = imutils.resize(frame, width=600)
        blurred = cv2.GaussianBlur(frame, (11, 11), 0)
        hsv = cv2.cvtColor(blurred, cv2.COLOR_BGR2HSV)

        for color_name, params in COLOR_RANGES.items():
            mask = cv2.inRange(hsv, params["lower"], params["upper"])
            mask = cv2.erode(mask, None, iterations=2)
            mask = cv2.dilate(mask, None, iterations=2)

            cnts = cv2.findContours(mask.copy(), cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
            cnts = imutils.grab_contours(cnts)
            center = None

            if len(cnts) > 0:
                c = max(cnts, key=cv2.contourArea)
                ((x, y), radius) = cv2.minEnclosingCircle(c)
                M = cv2.moments(c)

                if M["m00"] > 0 and radius > 10:
                    center = (int(M["m10"] / M["m00"]), int(M["m01"] / M["m00"]))
                    latest_centers[color_name] = center

                    color_bgr = params["bgr"]
                    cv2.circle(frame, (int(x), int(y)), int(radius), color_bgr, 2)
                    cv2.circle(frame, center, 5, color_bgr, -1)
                    text = f"{color_name.upper()} : {center}"
                    cv2.putText(frame, text, (center[0] + 10, center[1] - 10),
                                cv2.FONT_HERSHEY_SIMPLEX, 0.5, color_bgr, 2)

                    trajectories[color_name].appendleft(center)

            for i in range(1, len(trajectories[color_name])):
                if trajectories[color_name][i - 1] is None or trajectories[color_name][i] is None:
                    continue
                thickness = int(np.sqrt(64 / float(i + 1)) * 2.5)
                cv2.line(frame, trajectories[color_name][i - 1], trajectories[color_name][i], params["bgr"], thickness)

        with lock:
            output_frame = frame.copy()

        time.sleep(0.03)  # ~30 fps

# Thread qui met à jour toutes les 0.5 secondes les coordonnées des centres détectés pour l’API
def update_coords_for_api():
    global coords_for_api
    while True:
        with lock:
            coords_for_api = latest_centers.copy()
        time.sleep(0.5)  # 2 FPS

# Générateur qui encode les images annotées en JPEG et les prépare pour le streaming vidéo via Flask
def gen_frames():
    global output_frame
    while True:
        with lock:
            if output_frame is None:
                continue
            ret, buffer = cv2.imencode('.jpg', output_frame)
            if not ret:
                continue
            jpg = buffer.tobytes()
        yield (
            b'--frame\r\n'
            b'Content-Type: image/jpeg\r\n\r\n' + jpg + b'\r\n'
        )

# Route Flask qui fournit le flux vidéo en streaming multipart/x-mixed-replace
@app.route('/video_feed')
def video_feed():
    return Response(gen_frames(), mimetype='multipart/x-mixed-replace; boundary=frame')

# Route Flask qui renvoie les coordonnées actuelles des objets détectés au format JSON
@app.route('/coords')
def coords():
    return jsonify(coords_for_api)

if __name__ == '__main__':
    # Lancer les deux threads pour la détection vidéo et la mise à jour des coordonnées
    threading.Thread(target=video_processing, daemon=True).start()
    threading.Thread(target=update_coords_for_api, daemon=True).start()

    # Lancer le serveur Flask sur toutes les interfaces réseau au port 8000
    app.run(host='0.0.0.0', port=8000, debug=False)
