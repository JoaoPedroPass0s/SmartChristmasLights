from flask import Flask, request, jsonify, send_from_directory
from calibration.image_processing import analyze_video, detect_leds_in_frame
import requests, json, os, time, struct
from calibration import image_processing
from effectProcessing import gifEffects

ESP_URL = "http://192.168.1.200"  # ESP's IP

import random

elements = ['R','G','B']
led_count = 200
k = 5 # sequence length
n_sequences = 5
used = set()
led_color_mappings = []

mapping_file = "jsons/mappings.json"

def draw_unique_led_colors():
    while True:
        # pick with replacement (allows repeated letters)
        chars = tuple(random.choices(elements, k=k))
        code = ''.join(chars)
        if code not in used:
            used.add(code)
            print(f"Chosen LED colors: {code} (Total used: {len(used)})")
            return code

def generate_led_color_mappings():
    mappings = []
    for _ in range(led_count):
        # Add Random Color
        mappings.append(draw_unique_led_colors())

    # persist mappings to disk so they can be inspected or reused
    try:
        with open(mapping_file, 'w') as fh:
            json.dump(mappings, fh)
        # app may not be defined at import-time when this function is defined,
        # but it's called after `app` is created below, so logger is available.
        try:
            app.logger.info('Saved %d LED mappings to %s', len(mappings), mapping_file)
        except Exception:
            pass
    except Exception as e:
        try:
            app.logger.error('Failed to save mappings to %s: %s', mapping_file, e)
        except Exception:
            pass

    return mappings
    
app = Flask(__name__, static_folder="static")
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
    matched = image_processing.led_calibration(path)
    send_new_led_mapping(matched)
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
    
@app.route("/send_new_led_mapping", methods=["POST"])
def send_new_led_mapping(matched=None):
    if matched is None:
        return jsonify({"status": "error", "message": "No matched LEDs provided"}), 400

    # Send the new LED mapping to the ESP
    url = f"{ESP_URL}/calibrated_leds"
    assignment = ';'.join([f"{i}:{int(x)},{int(y)}" for (i, (x, y)) in matched])
    app.logger.info("Sending ledAssignment length=%d to %s", len(assignment), url)
    # retry a few times because the ESP may be briefly unavailable after calibration
    retries = 6
    for attempt in range(1, retries + 1):
        try:
            resp = requests.get(url, params={"ledsPositions": assignment}, timeout=8)
            app.logger.info("ESP responded: %s %s (attempt %d/%d)", resp.status_code, resp.text[:200], attempt, retries)
            return jsonify({"status": "ok", "esp_status": resp.status_code, "esp_text": resp.text}), 200
        except requests.RequestException as e:
            app.logger.warning("Attempt %d/%d: Failed to send to ESP %s: %s", attempt, retries, url, str(e))
            if attempt < retries:
                time.sleep(1.0)
            else:
                app.logger.error("All attempts failed to reach ESP %s", url)
                return jsonify({"status": "error", "error": str(e)}), 502

@app.route("/list_gifs", methods=["GET"])
def list_gifs():
    """List all available GIF files in the gifs directory"""
    gifs_dir = os.path.join(os.path.dirname(__file__), "gifs")
    
    if not os.path.exists(gifs_dir):
        return jsonify({"status": "error", "message": "GIFs directory not found"}), 404
    
    gif_files = [f for f in os.listdir(gifs_dir) if f.endswith('.gif')]
    gif_files.sort()
    
    return jsonify({
        "status": "ok",
        "gifs": gif_files,
        "count": len(gif_files)
    }), 200

@app.route("/send_gif", methods=["POST"])
def send_gif():
    """
    Process and send a GIF animation to the ESP
    Expects JSON: {"gif_name": "gradient.gif"} or {"gif_path": "/full/path/to/file.gif"}
    """
    data = request.json
    
    if "gif_name" in data:
        gif_name = data["gif_name"]
        gif_path = os.path.join(os.path.dirname(__file__), "gifs", gif_name)
    elif "gif_path" in data:
        gif_path = data["gif_path"]
    else:
        return jsonify({"status": "error", "message": "Missing gif_name or gif_path"}), 400
    
    if not os.path.exists(gif_path):
        return jsonify({"status": "error", "message": f"GIF not found: {gif_path}"}), 404
    
    try:
        app.logger.info(f"Processing GIF: {gif_path}")
        
        # Process the GIF
        frames = gifEffects.process_gif_effects(gif_path)
        num_frames = len(frames)
        
        app.logger.info(f"Processed {num_frames} frames")
        
        # Limit to 100 frames
        if num_frames > 100:
            app.logger.warning(f"Truncating {num_frames} frames to 100")
            frames = frames[:100]
            num_frames = 100
        
        # Build payload: [2-byte frame count][RGB data]
        payload = bytearray(struct.pack('<H', num_frames))
        
        for frame in frames:
            for led in frame:
                payload.extend(led)  # Append R, G, B bytes
        
        total_size = len(payload)
        app.logger.info(f"Payload size: {total_size} bytes ({total_size / 1024:.2f} KB)")
        
        # Send to ESP
        url = f"{ESP_URL}/gif"
        app.logger.info(f"Sending GIF to {url}")
        
        resp = requests.post(url, data=payload, timeout=30)
        app.logger.info(f"ESP response: {resp.status_code} - {resp.text}")
        
        return jsonify({
            "status": "ok",
            "gif": os.path.basename(gif_path),
            "frames": num_frames,
            "size_kb": round(total_size / 1024, 2),
            "esp_response": resp.text
        }), 200
        
    except Exception as e:
        app.logger.error(f"Error sending GIF: {str(e)}")
        return jsonify({"status": "error", "error": str(e)}), 500

@app.route("/gif_control", methods=["POST"])
def gif_control():
    """
    Control GIF playback on ESP
    Expects JSON: {"action": "play|pause|stop|speed", "value": <speed_ms>}
    """
    data = request.json
    action = data.get("action")
    
    if not action:
        return jsonify({"status": "error", "message": "Missing action parameter"}), 400
    
    url = f"{ESP_URL}/gif/control"
    params = {"action": action}
    
    if action == "speed" and "value" in data:
        params["value"] = data["value"]
    
    try:
        resp = requests.get(url, params=params, timeout=5)
        app.logger.info(f"GIF control: {action} - {resp.text}")
        
        return jsonify({
            "status": "ok",
            "action": action,
            "esp_response": resp.text
        }), 200
        
    except Exception as e:
        app.logger.error(f"Error controlling GIF: {str(e)}")
        return jsonify({"status": "error", "error": str(e)}), 500

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000)
    

