import cv2
import os
import image_processing

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

    right_detetions = 0
    for i, (pos, colors) in enumerate(grouped):
        colorcode1 = ''.join(colors[:5])
        colorcode2 = ''.join(colors[5:10])
        colorcode3 = ''.join(colors[10:15])
        if(colorcode1 == colorcode2 or colorcode1 == colorcode3 or colorcode2 == colorcode3):
            right_detetions += 1

    print(f"Right detections: {right_detetions}")

if __name__ == "__main__":
    test_video_path = "../tmp_video.mp4"  # Path to the test video
    test_led_detection(test_video_path,True)