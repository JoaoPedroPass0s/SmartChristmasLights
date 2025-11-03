import cv2
import numpy as np
import os

def detect_leds_in_frame(frame, frame_id=0, debug=False, save_dir="led_debug_frames"):
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

    # Always save — even if debug=False
    cv2.imwrite(os.path.join(save_dir, f"frame_{frame_id:04d}_detected.jpg"), debug_vis)
    cv2.imwrite(os.path.join(save_dir, f"frame_{frame_id:04d}_raw.jpg"), frame)

    # Only show live debug window if debug=True
    if debug:
        small_frame = cv2.resize(debug_vis, (640, 360))
        cv2.imshow("Detections", small_frame)
        cv2.waitKey(500)

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
    print("Frame rate:", cap.get(cv2.CAP_PROP_FPS))

    frame_id = 0
    step_id = 0
    results = []

    cap = cv2.VideoCapture(video_path)
    target_interval_s = 1.0
    print("Starting analysis from ms:", start)
    cap.set(cv2.CAP_PROP_POS_MSEC, start)
    next_target_ms = 4000.0

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
            detections = detect_leds_in_frame(frame,frame_id,debug)
            results.append((step_id, detections))
            step_id += 1
            # handle frame
            next_target_ms += target_interval_s * 1000.0

        if step_id >= 15:
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



