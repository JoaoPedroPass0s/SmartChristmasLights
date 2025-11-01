import cv2
import numpy as np


def detect_leds_in_frame(frame):
    gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
    _, thresh = cv2.threshold(gray, 200, 255, cv2.THRESH_BINARY)
    contours, _ = cv2.findContours(thresh, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
    detections = []
    for c in contours:
        M = cv2.moments(c)
        if M["m00"] > 5:
            cx = int(M["m10"] / M["m00"])
            cy = int(M["m01"] / M["m00"])
            color = frame[cy, cx].tolist()  # BGR color at centroid
            detections.append((cx, cy, color))
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

def analyze_video(video_path):
    sync_indices, brightness = find_sync_frames(video_path)
    start, end = sync_indices[0], sync_indices[-1]

    cap = cv2.VideoCapture(video_path)
    frame_rate = cap.get(cv2.CAP_PROP_FPS)
    frames_per_step = int(frame_rate * 0.5)  # assuming 0.5s per color

    frame_id = 0
    step_id = 0
    results = []

    while True:
        ret, frame = cap.read()
        if not ret: break
        if frame_id < start: 
            frame_id += 1
            continue
        if frame_id >= end: break

        # Middle frame of each chunk
        if (frame_id - start) % frames_per_step == frames_per_step // 2:
            detections = detect_leds_in_frame(frame)
            results.append((step_id, detections))
            step_id += 1
        frame_id += 1

    cap.release()
    return results
