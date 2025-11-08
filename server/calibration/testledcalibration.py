import json
from multiprocessing.util import debug
import cv2
import os
import image_processing
import requests, json, os

def test_led_detection(video_path, debug=False):
    # Run analysis
    results = image_processing.analyze_video(video_path, debug)

    for step_id, detections in results:
        print(f"Detections for step {step_id}: {len(detections)} LEDs detected.")
        nR = 0
        nG = 0
        nB = 0
        for (x, y, color) in detections:
            if color == 'R':
                nR += 1
            elif color == 'G':
                nG += 1
            elif color == 'B':
                nB += 1
        print(f" Step: {step_id} Colors Count: (R:{nR} G:{nG} B:{nB})")
            

    grouped = image_processing.group_detections(results)

    for i, (pos, colors) in enumerate(grouped):
        print(f"LED {i} at position {pos} has colors: {colors}")

    matching_detections = 0
    matching_detections_colors = []
    for i, (pos, colors) in enumerate(grouped):
        colorcode1 = ''.join(colors[:5])
        colorcode2 = ''.join(colors[5:10])
        colorcode3 = ''.join(colors[10:15])
        if(colorcode1 == colorcode2 or colorcode1 == colorcode3):
            matching_detections += 1
            matching_detections_colors.append(colorcode1)
        elif colorcode2 == colorcode3:
            matching_detections += 1
            matching_detections_colors.append(colorcode2)

    print(f"Matching detections: {matching_detections}")

    with open("../jsons/mappings.json", 'r') as fh:
        mappings = json.load(fh)
    
    matched = image_processing.match_leds(mappings,grouped)

    print(f"Right detections: {len(matched)} out of {len(mappings)}")

    matched = image_processing.fill_missing_leds(matched, len(mappings))

    print(f"Final matched LEDs: {len(matched)} out of {len(mappings)}")

    image_processing.draw_leds_on_frame(matched, save_dir="led_debug_frames")


ESP_URL = "http://192.168.1.200"  # ESP's IP    

def send_new_led_mapping(matched=None):
    if matched is None:
        print("No matched LED mapping provided.")
        return
    
    # Send the new LED mapping to the ESP
    url = f"{ESP_URL}/calibrated_leds"
    assignment = ';'.join([f"{i}:{int(x)},{int(y)}" for (i, (x, y)) in matched])
    print("Sending ledAssignment:", assignment)
    try:
        resp = requests.get(url, params={"ledsPositions": assignment}, timeout=5)
        print("ESP responded: %s %s", resp.status_code, resp.text[:200])
    except requests.RequestException as e:
        print("Failed to send to ESP %s: %s", url, str(e))


if __name__ == "__main__":
    test_video_path = "../tmp_video.mp4"  # Path to the test video
    #test_led_detection(test_video_path, debug=True)
    matched = image_processing.led_calibration(test_video_path, True)
    send_new_led_mapping(matched)
    image_processing.draw_leds_on_frame(matched, save_dir="led_debug_frames")