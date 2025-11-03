import cv2
import numpy as np

def hsv_color_tuner(image_path):
    # Load the image
    frame = cv2.imread(image_path)
    if frame is None:
        print("❌ Error: Could not load image.")
        return
    frame = cv2.resize(frame, (640, 480))
    
    cv2.namedWindow("Trackbars")

    # Create trackbars for color change
    def nothing(x):
        pass

    cv2.createTrackbar("H Min", "Trackbars", 0, 179, nothing)
    cv2.createTrackbar("H Max", "Trackbars", 179, 179, nothing)
    cv2.createTrackbar("S Min", "Trackbars", 0, 255, nothing)
    cv2.createTrackbar("S Max", "Trackbars", 255, 255, nothing)
    cv2.createTrackbar("V Min", "Trackbars", 0, 255, nothing)
    cv2.createTrackbar("V Max", "Trackbars", 255, 255, nothing)

    print("🎛️ Adjust the sliders to tune HSV mask. Press 'q' to quit.")

    while True:
        hsv = cv2.cvtColor(frame, cv2.COLOR_BGR2HSV)

        # Read trackbar positions
        h_min = cv2.getTrackbarPos("H Min", "Trackbars")
        h_max = cv2.getTrackbarPos("H Max", "Trackbars")
        s_min = cv2.getTrackbarPos("S Min", "Trackbars")
        s_max = cv2.getTrackbarPos("S Max", "Trackbars")
        v_min = cv2.getTrackbarPos("V Min", "Trackbars")
        v_max = cv2.getTrackbarPos("V Max", "Trackbars")

        # Create mask
        lower = np.array([h_min, s_min, v_min])
        upper = np.array([h_max, s_max, v_max])
        mask = cv2.inRange(hsv, lower, upper)

        # Apply mask
        result = cv2.bitwise_and(frame, frame, mask=mask)

        # Show images
        cv2.imshow("Original", frame)
        cv2.imshow("Mask", mask)
        cv2.imshow("Masked Result", result)

        key = cv2.waitKey(1) & 0xFF
        if key == ord('q'):
            print(f"🟢 Lower HSV: {lower.tolist()} | Upper HSV: {upper.tolist()}")
            break

    cv2.destroyAllWindows()

def white_spot_tuner(image_path):
    frame = cv2.imread(image_path)
    if frame is None:
        print("❌ Error: Could not load image.")
        return
    frame = cv2.resize(frame, (640, 480))

    hsv = cv2.cvtColor(frame, cv2.COLOR_BGR2HSV)
    cv2.namedWindow("White Spot Tuner")

    def nothing(x):
        pass

    # Create HSV range trackbars (for low saturation and high value tuning)
    cv2.createTrackbar("H Min", "White Spot Tuner", 0, 179, nothing)
    cv2.createTrackbar("H Max", "White Spot Tuner", 179, 179, nothing)
    cv2.createTrackbar("S Min", "White Spot Tuner", 0, 255, nothing)
    cv2.createTrackbar("S Max", "White Spot Tuner", 60, 255, nothing)
    cv2.createTrackbar("V Min", "White Spot Tuner", 200, 255, nothing)
    cv2.createTrackbar("V Max", "White Spot Tuner", 255, 255, nothing)
    cv2.createTrackbar("Blur Kernel", "White Spot Tuner", 5, 25, nothing)
    cv2.createTrackbar("Min Area", "White Spot Tuner", 5, 200, nothing)

    print("💡 Adjust sliders to isolate white / bright LED centers. Press 'q' to quit.")

    while True:
        h_min = cv2.getTrackbarPos("H Min", "White Spot Tuner")
        h_max = cv2.getTrackbarPos("H Max", "White Spot Tuner")
        s_min = cv2.getTrackbarPos("S Min", "White Spot Tuner")
        s_max = cv2.getTrackbarPos("S Max", "White Spot Tuner")
        v_min = cv2.getTrackbarPos("V Min", "White Spot Tuner")
        v_max = cv2.getTrackbarPos("V Max", "White Spot Tuner")
        blur_k = cv2.getTrackbarPos("Blur Kernel", "White Spot Tuner")
        blur_k = max(1, blur_k // 2 * 2 + 1)  # Ensure it's odd
        min_area = cv2.getTrackbarPos("Min Area", "White Spot Tuner")

        lower = np.array([h_min, s_min, v_min])
        upper = np.array([h_max, s_max, v_max])
        mask = cv2.inRange(hsv, lower, upper)
        mask = cv2.GaussianBlur(mask, (blur_k, blur_k), 0)

        contours, _ = cv2.findContours(mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
        vis = frame.copy()
        bright_count = 0

        for c in contours:
            area = cv2.contourArea(c)
            if area > min_area:
                bright_count += 1
                x, y, w, h = cv2.boundingRect(c)
                cx, cy = x + w // 2, y + h // 2
                cv2.circle(vis, (cx, cy), 4, (0, 255, 255), 2)
                cv2.putText(vis, f"{int(area)}", (x, y - 5),
                            cv2.FONT_HERSHEY_SIMPLEX, 0.4, (0, 255, 255), 1)

        cv2.imshow("Original", frame)
        cv2.imshow("White Mask", mask)
        cv2.imshow("Detected Spots", vis)

        key = cv2.waitKey(1) & 0xFF
        if key == ord('q'):
            print(f"✅ Lower HSV: {lower.tolist()} | Upper HSV: {upper.tolist()}")
            print(f"💡 Detected {bright_count} bright (white) spots.")
            break

    cv2.destroyAllWindows()

if __name__ == "__main__":
    test_image_path = "frame_0053_raw.jpg"  # Your test frame
    white_spot_tuner(test_image_path)
