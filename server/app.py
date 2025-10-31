from flask import Flask, request, jsonify, send_from_directory
from calibration.image_processing import detect_led_position
import requests, json, os

ESP_URL = "http://192.168.1.5"  # Change to your ESP's IP

import random

elements = ['R','G','B','V','N','M']
led_count = 150
k = 12
used = set()
led_color_mappings = []

def draw_unique_led_colors():
    while True:
        # pick with replacement (allows repeated letters)
        chars = tuple(random.choices(elements, k=k*2))
        code = ''.join(chars)
        if code not in used:
            used.add(code)
            print(f"Chosen LED colors: {code} (Total used: {len(used)}/{max_unique})")
            return code

def generate_led_color_mappings():
    mappings = []
    for _ in range(150):
        # Add Random Color
        mappings.append(draw_unique_led_colors())
    return mappings
    


elements = ['R','G','B','V','N','M']
k = 3
used = set()
max_unique = 1_000_000  # guard

app = Flask(__name__, static_folder="static")
mapping_file = "mapping.json"
led_mapping = []

@app.route("/")
def index():
    global led_color_mappings
    led_color_mappings = generate_led_color_mappings()
    return send_from_directory("static", "index.html")

@app.route("/upload_photo", methods=["POST"])
def upload_photo():
    photo = request.files["photo"]
    led_index = int(request.form["led"])
    path = f"tmp_{led_index}.jpg"
    photo.save(path)
    pos = (1, 1)
    if pos:
        led_mapping.append({"index": led_index, "x": pos[0], "y": pos[1]})
        return jsonify({"status": "ok", "pos": pos})
    return jsonify({"status": "fail"}), 400

@app.route("/set_led/<int:led>", methods=["GET"])
def set_led(led):
    # Make sure the endpoint matches the one your ESP serves (main.cpp uses "/led")
    led_mapping = ""

    for led_colors in led_color_mappings:
        led_mapping += led_colors[led]

    url = f"{ESP_URL}/calibrate"
    try:
        resp = requests.get(url, params={"ledAssignment": led_mapping}, timeout=3)
        app.logger.info("ESP responded: %s %s", resp.status_code, resp.text[:200])
        return jsonify({"status": "ok", "esp_status": resp.status_code, "esp_text": resp.text}), 200
    except requests.RequestException as e:
        app.logger.error("Failed to send to ESP %s: %s", url, str(e))
        return jsonify({"status": "error", "error": str(e)}), 502

@app.route("/save_mapping", methods=["POST"])
def save_mapping():
    with open(mapping_file, "w") as f:
        json.dump({"leds": led_mapping}, f, indent=2)
    return jsonify({"status": "saved"})


@app.route("/debug_ping_esp", methods=["GET"])
def debug_ping_esp():
    """Hit the ESP root to verify reachability and return the raw response or error."""
    url = f"{ESP_URL}/"
    app.logger.info("Pinging ESP at %s", url)
    try:
        resp = requests.get(url, timeout=3)
        return jsonify({"ok": True, "status_code": resp.status_code, "text": resp.text[:1000]}), 200
    except requests.RequestException as e:
        app.logger.error("Ping failed: %s", e)
        return jsonify({"ok": False, "error": str(e)}), 502

if __name__ == "__main__":
    os.makedirs("static", exist_ok=True)
    app.run(host="0.0.0.0", port=5000)

