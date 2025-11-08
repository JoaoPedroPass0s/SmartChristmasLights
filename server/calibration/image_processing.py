import cv2
import numpy as np
import os
import json
from pathlib import Path

def detect_leds_in_frame(frame, step_id=0, frame_id=0, debug=False, save_dir="led_debug_frames"):
    hsv = cv2.cvtColor(frame, cv2.COLOR_BGR2HSV)
    masks = {
        'R': cv2.inRange(hsv, np.array([144, 193, 80]), np.array([179, 255, 255])), 
        'G': cv2.inRange(hsv, np.array([30, 70, 100]), np.array([90, 255, 255])),
        'B': cv2.inRange(hsv, np.array([97, 130, 154]), np.array([144, 255, 255])),
    }
    masks = {color: cv2.GaussianBlur(mask, (7,7), 0) for color, mask in masks.items()}

    detections = []
    debug_vis = frame.copy()
    os.makedirs(save_dir, exist_ok=True)

    for color, mask in masks.items():
        contours, _ = cv2.findContours(mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
        for c in contours:
            if cv2.contourArea(c) > 10:
                x, y, w, h = cv2.boundingRect(c)
                cx, cy = x + w // 2, y + h // 2
                detections.append((cx, cy, color))

                color_map = {
                    'R': (0, 0, 255),
                    'G': (0, 255, 0),
                    'B': (255, 0, 0)
                }
                cv2.circle(debug_vis, (cx, cy), 5, color_map[color], 2)
                cv2.putText(debug_vis, color, (cx + 5, cy - 5),
                            cv2.FONT_HERSHEY_SIMPLEX, 0.5, color_map[color], 1)

    # Only show live debug window if debug=True
    if debug:
        if(step_id == 0):
            cv2.imwrite(os.path.join(save_dir, f"frame_first.jpg"), frame)
        cv2.imwrite(os.path.join(save_dir, f"frame_{frame_id:04d}_detected.jpg"), debug_vis)
        cv2.imwrite(os.path.join(save_dir, f"frame_{frame_id:04d}_raw.jpg"), frame)
        #small_frame = cv2.resize(debug_vis, (640, 360))
        #cv2.imshow("Detections", small_frame)
        #cv2.waitKey(500)

    return detections

def find_sync_frames(video_path):
    cap = cv2.VideoCapture(video_path)
    brightness = []
    while True:
        ret, frame = cap.read()
        if not ret:
            break
        gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
        brightness.append(np.mean(gray))
    cap.release()

    brightness = np.array(brightness)
    # Find spikes (start/end flashes)
    threshold = brightness.mean() + 2 * brightness.std()
    sync_indices = np.where(brightness > threshold)[0]
    return sync_indices, brightness

def analyze_video(video_path, debug=False):
    sync_indices, brightness = find_sync_frames(video_path)
    start, end = sync_indices[0], sync_indices[-1]

    cap = cv2.VideoCapture(video_path)

    frame_id = 0
    step_id = 0
    results = []

    cap = cv2.VideoCapture(video_path)
    target_interval_s = 0.2
    cap.set(cv2.CAP_PROP_POS_MSEC, start)
    next_target_ms = 3600.0

    while True:
        ret, frame = cap.read()
        
        if not ret:
            break

        #if frame_id < start + 1:
        #    frame_id += 1
        #    continue

        current_ms = cap.get(cv2.CAP_PROP_POS_MSEC)  # timestamp of this frame
        # process frames when their timestamp crosses the next target time
        if current_ms >= next_target_ms:
            detections = detect_leds_in_frame(frame,step_id,frame_id,debug)
            results.append((step_id, detections))
            step_id += 1
            # handle frame
            next_target_ms += target_interval_s * 1000.0

        if step_id >= 25:
            break

        frame_id += 1

    cap.release()
    return results

def group_detections(results):
    leds_detected = []
    for i in range(len(results)):
        step_id, detections = results[i]
        if(step_id == 0):
            for (x, y, color) in detections:
                leds_detected.append(((x, y), [color]))
            continue
        for pos, colors in leds_detected:
            closest_led_idx = None
            distance_closest_led = None
            for (i, (x, y, color)) in enumerate(detections):
                distance = np.sqrt((x - pos[0]) ** 2 + (y - pos[1]) ** 2)
                if closest_led_idx is None or (distance < distance_closest_led):
                    closest_led_idx = i
                    distance_closest_led = distance
            if closest_led_idx is not None:
                colors.append(detections[closest_led_idx][2])

    # Remove entries with fewer than 15 observations.
    leds_detected = [(pos, colors) for (pos, colors) in leds_detected if len(colors) >= 15]
    return leds_detected

def match_leds(mappings, grouped, debug = False, save_dir="led_debug_frames", base_frame_path=None):
    matched = []
    for (i, mapping) in enumerate(mappings):
        code = mapping[:5]
        for (pos, colors) in grouped:
            detected_codes = [''.join(colors[j:j+5]) for j in range(0, len(colors), 5)]
            # if theres more than one equal 5-length segment
            num_found = 0
            for detected_code in detected_codes:
                if code == detected_code:
                    num_found += 1
            if num_found > 2:
                matched.append((i, pos))
                break
    return matched

def fill_missing_leds(matched, num_leds):
    matched_dict = {i: pos for (i, pos) in matched}
    for i in range(num_leds):
        if i not in matched_dict:
            # Find nearest known neighbors safely to predict a position.
            # Prefer averaging previous and next known positions when available.
            prev_idx = None
            next_idx = None
            # search backwards for previous known
            for j in range(i - 1, -1, -1):
                if j in matched_dict:
                    prev_idx = j
                    break
            # search forwards for next known
            for j in range(i + 1, num_leds):
                if j in matched_dict:
                    next_idx = j
                    break

            if prev_idx is not None and next_idx is not None:
                prev = matched_dict[prev_idx]
                nxt = matched_dict[next_idx]
                x_predicted_pos = (prev[0] + nxt[0]) / 2.0
                y_predicted_pos = (prev[1] + nxt[1]) / 2.0
            elif prev_idx is not None:
                prev = matched_dict[prev_idx]
                x_predicted_pos = prev[0]
                y_predicted_pos = prev[1]
            elif next_idx is not None:
                nxt = matched_dict[next_idx]
                x_predicted_pos = nxt[0]
                y_predicted_pos = nxt[1]
            else:
                # No known LEDs at all — fallback to (0,0)
                x_predicted_pos = 0.0
                y_predicted_pos = 0.0

            matched_dict[i] = (float(x_predicted_pos), float(y_predicted_pos))
    return [(i, matched_dict[i]) for i in range(num_leds)]
    
def correct_outliers(matched, distance_threshold_factor=2.0):
    """
    Detect and correct outlier LED positions that are too far from their neighbors.
    """
    if len(matched) < 3:
        return matched  # nothing to correct

    # Compute pairwise distances between consecutive LEDs
    distances = []
    for i in range(1, len(matched)):
        x1, y1 = matched[i-1][1]
        x2, y2 = matched[i][1]
        distances.append(np.sqrt((x2 - x1)**2 + (y2 - y1)**2))

    median_dist = np.median(distances)
    threshold = median_dist * distance_threshold_factor

    corrected = matched.copy()
    for i in range(1, len(matched) - 1):
        prev_pos = np.array(matched[i - 1][1])
        curr_pos = np.array(matched[i][1])
        next_pos = np.array(matched[i + 1][1])

        dist_prev = np.linalg.norm(curr_pos - prev_pos)
        dist_next = np.linalg.norm(curr_pos - next_pos)

        # If current point is too far from both sides, consider it an outlier
        if dist_prev > threshold and dist_next > threshold:
            print(f"Outlier detected at index {i}: {curr_pos} (prev: {prev_pos}, next: {next_pos})")
            # Replace with midpoint of neighbors
            corrected_pos = (prev_pos + next_pos) / 2.0
            corrected[i] = (matched[i][0], (float(corrected_pos[0]), float(corrected_pos[1])))

    return corrected


def draw_leds_on_frame(matched, save_dir="led_debug_frames", base_frame_path="led_debug_frames/frame_first.jpg"):
    # Try to overlay on a real frame if available; otherwise use a black frame
    os.makedirs(save_dir, exist_ok=True)
    frame = None
    # If caller provided a path to a base frame, try to load it
    if base_frame_path is not None:
        frame = cv2.imread(base_frame_path)

    # If no explicit base frame, try to find a saved raw frame from detection
    if frame is None:
        try:
            # look for files named frame_XXXX_raw.jpg in save_dir
            files = [f for f in os.listdir(save_dir) if f.startswith("frame_") and f.endswith("_raw.jpg")]
            files.sort()
            if len(files) > 0:
                frame = cv2.imread(os.path.join(save_dir, files[0]))
        except Exception:
            frame = None

    # Fallback to a black canvas with a reasonable default size
    if frame is None:
        frame = np.zeros((480, 640, 3), dtype=np.uint8)

    # Draw matched leds on the chosen frame
    for (i, pos) in matched:
        # Ensure positions are integer tuples
        p = (int(pos[0]), int(pos[1]))
        cv2.circle(frame, p, 1, (0, 255, 0), -1)
        cv2.putText(frame, str(i), (p[0] + 7, p[1] - 7),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.4, (0, 255, 0), 1)

    # Save and show
    cv2.imwrite(os.path.join(save_dir, "final_matched_frame.jpg"), frame)
    try:
        small = cv2.resize(frame, (480, 640))
        cv2.imshow("Matched LEDs", small)
        cv2.waitKey(0)
        cv2.destroyWindow("Matched LEDs")
    except Exception:
        # If running headless or on systems without GUI support, ignore
        pass

def led_calibration(video_path, debug=False):
    results = analyze_video(video_path, debug)

    grouped = group_detections(results)
    # Resolve paths relative to the server/ folder (two levels up from this file: server/calibration -> server)
    base_dir = Path(__file__).resolve().parent.parent
    jsons_dir = base_dir / 'jsons'
    mappings_path = jsons_dir / 'mappings.json'
    mappings_path_parent = mappings_path.parent
    if not mappings_path_parent.exists():
        # create folder if it doesn't exist to avoid write errors later
        mappings_path_parent.mkdir(parents=True, exist_ok=True)

    if not mappings_path.exists():
        raise FileNotFoundError(f"mappings.json not found at expected location: {mappings_path}")

    with open(mappings_path, 'r') as fh:
        mappings = json.load(fh)
    
    matched = match_leds(mappings,grouped)

    matched = fill_missing_leds(matched, len(mappings))

    corrected_matched = correct_outliers(matched)

    led_positions_path = jsons_dir / 'led_positions.json'
    with open(led_positions_path, 'w') as fh:
        json.dump(corrected_matched, fh)

    return corrected_matched
