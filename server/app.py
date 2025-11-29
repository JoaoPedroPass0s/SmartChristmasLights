from flask import Flask, request, jsonify, send_from_directory, send_file
from calibration.image_processing import analyze_video, detect_leds_in_frame
import requests, json, os, time, struct,io
from calibration import image_processing
from effectProcessing import gifEffects
from PIL import Image

ESP_URL = "http://192.168.1.200"  # ESP's IP

GIF_FOLDER = "gifs"

# Ensure UPLOAD_DIR is defined
UPLOAD_DIR = os.getenv("UPLOAD_DIR", "uploads")  # Default to "uploads" if not set

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

@app.route("/gif_editor", methods=["GET"])
def gif_editor():
    return send_from_directory("static", "gif_editor.html")

@app.route("/effects", methods=["GET"])
def effects_page():
    return send_from_directory("static", "effects.html")

@app.route("/get_led_positions", methods=["GET"])
def get_led_positions():
    """Serve LED positions JSON for preview"""
    led_positions_file = os.path.join(os.path.dirname(__file__), "jsons", "led_positions.json")
    
    if not os.path.exists(led_positions_file):
        return jsonify({"status": "error", "message": "LED positions not found. Please run calibration first."}), 404
    
    try:
        with open(led_positions_file, 'r') as f:
            positions = json.load(f)
        return jsonify(positions), 200
    except Exception as e:
        app.logger.error(f"Error loading LED positions: {str(e)}")
        return jsonify({"status": "error", "error": str(e)}), 500
    
@app.route('/get_gif_image/<path:filename>')
def get_gif_image(filename):
    # This assumes your GIFs are stored in a folder named 'gifs'
    # Adjust "gifs" to "uploads" if that is where you keep them
    return send_from_directory("gifs", filename)

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

@app.route("/upload_gif_editor", methods=["POST"])
def upload_gif_editor():
    """Upload a new GIF file for editing"""
    if 'gif' not in request.files:
        return jsonify({"status": "error", "message": "No file provided"}), 400
    
    file = request.files['gif']
    if file.filename == '':
        return jsonify({"status": "error", "message": "No file selected"}), 400
    
    # Save to gifs directory
    filename = file.filename
    gifs_dir = os.path.join(os.path.dirname(__file__), "uploads")
    
    # Create gifs directory if it doesn't exist
    if not os.path.exists(gifs_dir):
        os.makedirs(gifs_dir)
    
    filepath = os.path.join(gifs_dir, filename)
    file.save(filepath)
    
    return jsonify({"status": "ok", "filename": filename}), 200

@app.route('/crop_gif', methods=['POST'])
def crop_gif():
    data = request.json
    gif_name = data.get("gif_name")
    x = data.get("x")
    y = data.get("y")
    w = data.get("w")
    h = data.get("h")

    if not gif_name or None in (x, y, w, h):
        return jsonify({"status": "error", "error": "Missing required parameters"}), 400

    input_path = os.path.join(UPLOAD_DIR, gif_name)
    if not os.path.exists(input_path):
        return jsonify({"status": "error", "error": f"{gif_name} not found"}), 404

    try:
        with Image.open(input_path) as im:
            canvas_size = im.size  # Original GIF logical size
            frames = []
            durations = []

            for frame in range(im.n_frames):
                im.seek(frame)
                # Render full frame on a blank canvas
                full_frame = Image.new("RGBA", canvas_size)
                full_frame.paste(im.convert("RGBA"), (0, 0))
                # Crop using coordinates
                cropped = full_frame.crop((x, y, x + w, y + h))
                frames.append(cropped)
                durations.append(im.info.get("duration", 100))

            # Save the cropped GIF
            base, ext = os.path.splitext(gif_name)
            output_name = f"{base}_cropped.gif"
            output_path = os.path.join(UPLOAD_DIR, output_name)

            frames[0].save(
                output_path,
                save_all=True,
                append_images=frames[1:],
                duration=durations,
                loop=0,
                disposal=2
            )

        return jsonify({"status": "ok", "output": output_name})
    except Exception as e:
        return jsonify({"status": "error", "error": str(e)}), 500

# --- THE FIXED FUNCTION ---
@app.route('/get_frames/<filename>')
def get_frames(filename):
    path = os.path.join(UPLOAD_DIR, filename)
    if not os.path.exists(path):
        return jsonify({"error": "File not found"}), 404

    try:
        LED_POSITIONS_FILE = os.path.join(os.path.dirname(__file__), "jsons", "led_positions.json")
        # 1. Load LED positions
        if not os.path.exists(LED_POSITIONS_FILE):
             return jsonify({"error": "LED positions not found"}), 404
             
        with open(LED_POSITIONS_FILE) as f:
            # Expected format in JSON: [[index, [x, y]], [index, [x, y]], ...]
            raw_data = json.load(f)
            led_positions = [item[1] for item in raw_data]

        if not led_positions:
            return jsonify({"frames": []})

        # 2. Calculate LED Bounding Box (to map coordinate space)
        xs = [p[0] for p in led_positions]
        ys = [p[1] for p in led_positions]
        min_x, max_x = min(xs), max(xs)
        min_y, max_y = min(ys), max(ys)
        
        led_width = max_x - min_x if max_x != min_x else 1
        led_height = max_y - min_y if max_y != min_y else 1

        # 3. Process GIF Frames
        gif = Image.open(path)
        frames = []

        for frame_index in range(gif.n_frames):
            gif.seek(frame_index)
            frame_img = gif.convert("RGB")
            img_w, img_h = frame_img.size
            
            sampled_leds = []
            
            for (lx, ly) in led_positions:
                # Normalize LED position (0.0 to 1.0) relative to the LED cloud
                norm_x = (lx - min_x) / led_width
                norm_y = (ly - min_y) / led_height
                
                # Map normalized position to GIF pixel coordinates
                # We clamp values to be safe
                gx = int(max(0, min(1, norm_x)) * (img_w - 1))
                gy = int(max(0, min(1, norm_y)) * (img_h - 1))
                
                # Get color
                r, g, b = frame_img.getpixel((gx, gy))
                sampled_leds.append([r, g, b])

            frames.append(sampled_leds)

        return jsonify({"frames": frames})
    except Exception as e:
        app.logger.error(f"Error in get_frames: {e}")
        return jsonify({"error": str(e)}), 500
    
@app.route("/save_gif/<filename>", methods=["POST"])
def save_gif(filename):
    data = request.json
    new_name = data.get("gif_name")

    # Get Gif from uploads and save to gifs directory
    source_path = os.path.join(UPLOAD_DIR, filename)
    if not os.path.exists(source_path):
        return jsonify({"status": "error", "message": "File not found"}), 404
    dest_dir = os.path.join(os.path.dirname(__file__), "gifs")
    if not os.path.exists(dest_dir):
        os.makedirs(dest_dir)
    dest_path = os.path.join(dest_dir, new_name + ".gif")
    try:
        with open(source_path, 'rb') as src_file:
            with open(dest_path, 'wb') as dest_file:
                dest_file.write(src_file.read())
        return jsonify({"status": "ok", "message": "GIF saved"}), 200
    except Exception as e:
        return jsonify({"status": "error", "message": str(e)}), 500
    
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
    

