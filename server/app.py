from flask import Flask, request, jsonify, send_from_directory
from calibration.image_processing import analyze_video, detect_leds_in_frame
import requests, json, os

ESP_URL = "http://192.168.1.200"  # ESP's IP

import random

elements = ['R','G','B']
led_count = 150
k = 5 # sequence length
n_sequences = 3
used = set()
led_color_mappings = []

def draw_unique_led_colors():
    while True:
        # pick with replacement (allows repeated letters)
        chars = tuple(random.choices(elements, k=k))
        chars = chars * n_sequences  # repeat for redundancy
        code = ''.join(chars)
        if code not in used:
            used.add(code)
            print(f"Chosen LED colors: {code} (Total used: {len(used)})")
            return code

def generate_led_color_mappings():
    mappings = []
    for _ in range(150):
        # Add Random Color
        mappings.append(draw_unique_led_colors())
    return mappings

app = Flask(__name__, static_folder="static")
mapping_file = "mapping.json"
led_color_mappings = generate_led_color_mappings()

@app.route("/")
def index():
    return send_from_directory("static", "index.html")

@app.route("/calibration", methods=["GET"])
def calibration():
    return send_from_directory("static", "calibration.html")

@app.route("/upload_video", methods=["POST"])
def upload_video():
    video = request.files["video"]
    path = f"tmp_video.mp4"
    video.save(path)
    return send_from_directory("static", "index.html")

@app.route("/send_led_mapping", methods=["GET"])
def send_led_mapping():
    # Make sure the endpoint matches the one your ESP serves (main.cpp uses "/led")
    url = f"{ESP_URL}/calibrate"

    # The ESP expects a single long string (one char per LED frame).
    # `led_color_mappings` is a Python list of strings, so we must join it
    # into one string before sending. Passing the list directly as params
    # results in an encoding the ESP won't understand.
    # send all in a single code string
    assignment = ''
    for code in led_color_mappings:
        assignment += code
    app.logger.info("Sending ledAssignment length=%d to %s", len(assignment), url)
    try:
        resp = requests.get(url, params={"ledAssignment": assignment}, timeout=5)
        app.logger.info("ESP responded: %s %s", resp.status_code, resp.text[:200])
        return jsonify({"status": "ok", "esp_status": resp.status_code, "esp_text": resp.text}), 200
    except requests.RequestException as e:
        app.logger.error("Failed to send to ESP %s: %s", url, str(e))
        return jsonify({"status": "error", "error": str(e)}), 502

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000)
    

