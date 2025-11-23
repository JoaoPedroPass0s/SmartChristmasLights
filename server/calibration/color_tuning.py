import cv2
import numpy as np
import json
from pathlib import Path
import sys

# Add parent directory to path to import image_processing
sys.path.insert(0, str(Path(__file__).parent.parent))
from calibration.image_processing import detect_leds_in_frame, analyze_video, group_detections, match_leds


def optimize_color_ranges_with_feedback(video_path, mappings_path, max_iterations=20, population_size=20):
    """
    Automatic HSV range optimization using genetic algorithm with feedback from detection quality.
    
    Strategy:
    1. Generate random HSV range variations
    2. Test each variation by running detection on video frames
    3. Score based on: number of detections, match quality, consistency
    4. Keep best performers and mutate for next generation
    5. Converge to optimal ranges
    """
    print("🧬 AUTOMATIC COLOR CALIBRATION WITH FEEDBACK LOOP")
    print("=" * 60)
    
    # Load mappings for matching validation
    with open(mappings_path, 'r') as f:
        mappings = json.load(f)
    num_leds = len(mappings)
    
    from calibration.image_processing import default_ranges
    # Initial HSV ranges (starting point - current defaults)
    base_ranges = {
        'R': {'lower': default_ranges['R'][0].tolist(), 'upper': default_ranges['R'][1].tolist()},
        'G': {'lower': default_ranges['G'][0].tolist(), 'upper': default_ranges['G'][1].tolist()},
        'B': {'lower': default_ranges['B'][0].tolist(), 'upper': default_ranges['B'][1].tolist()},
        'blur': default_ranges['blur'],
        'area': default_ranges['area']
    }
    
    print(f"🎯 Target: Detect {num_leds} LEDs reliably")
    
    def evaluate_ranges(ranges):
        """Score a set of HSV ranges based on actual LED matching quality"""
        # Convert ranges to the format expected by analyze_video
        color_ranges_formatted = {
            'R': (np.array(ranges['R']['lower']), np.array(ranges['R']['upper'])),
            'G': (np.array(ranges['G']['lower']), np.array(ranges['G']['upper'])),
            'B': (np.array(ranges['B']['lower']), np.array(ranges['B']['upper'])),
            'blur': ranges['blur'],
            'area': ranges['area']
        }
        
        # Run the actual detection pipeline with these ranges
        try:
            results = analyze_video(video_path, debug=False, color_ranges=color_ranges_formatted)
            grouped = group_detections(results)
            matched = match_leds(mappings, grouped)
            
            num_matched = len(matched)
            
            # Score based on number of matched LEDs (primary metric)
            match_ratio = num_matched / num_leds
            match_score = match_ratio * 100
            
            # Bonus for exact match
            if num_matched == num_leds:
                match_score += 10
            
            # Slight penalty for over-matching (false positives)
            if num_matched > num_leds:
                overmatch_penalty = (num_matched - num_leds) * 0.5
                match_score -= overmatch_penalty
            
            return max(0, match_score), num_matched
            
        except Exception as e:
            print(f"⚠️  Evaluation error: {e}")
            return 0, 0
    
    def mutate_ranges(ranges, mutation_rate=0.2):
        """Create a mutated copy of ranges"""
        new_ranges = {}
        for color in ['R', 'G', 'B']:
            new_ranges[color] = {
                'lower': ranges[color]['lower'].copy(),
                'upper': ranges[color]['upper'].copy()
            }
            
            if np.random.random() < mutation_rate:
                # Mutate lower bound
                idx = np.random.randint(0, 3)  # H, S, or V
                delta = np.random.randint(-15, 16)
                new_ranges[color]['lower'][idx] = np.clip(
                    new_ranges[color]['lower'][idx] + delta, 
                    0, 
                    179 if idx == 0 else 255
                )
            
            if np.random.random() < mutation_rate:
                # Mutate upper bound
                idx = np.random.randint(0, 3)
                delta = np.random.randint(-15, 16)
                new_ranges[color]['upper'][idx] = np.clip(
                    new_ranges[color]['upper'][idx] + delta, 
                    0, 
                    179 if idx == 0 else 255
                )
            
            # Ensure lower < upper
            for i in range(3):
                if new_ranges[color]['lower'][i] >= new_ranges[color]['upper'][i]:
                    new_ranges[color]['lower'][i] = max(0, new_ranges[color]['upper'][i] - 5)
        
        # Mutate blur (must be odd number between 3 and 21)
        new_ranges['blur'] = ranges['blur']
        if np.random.random() < mutation_rate:
            delta = np.random.choice([-2, 0, 2])  # Change by ±2 to keep it odd
            new_ranges['blur'] = np.clip(ranges['blur'] + delta, 3, 21)
            # Ensure it's odd
            if new_ranges['blur'] % 2 == 0:
                new_ranges['blur'] = max(3, new_ranges['blur'] - 1)
        
        # Mutate min_area (between 1 and 50)
        new_ranges['area'] = ranges['area']
        if np.random.random() < mutation_rate:
            delta = np.random.randint(-3, 4)
            new_ranges['area'] = np.clip(ranges['area'] + delta, 1, 50)
        
        return new_ranges
    
    # Genetic algorithm
    population = [base_ranges]
    
    # Generate initial population variations
    for _ in range(population_size - 1):
        population.append(mutate_ranges(base_ranges, mutation_rate=0.4))
    
    best_score = 0
    best_ranges = base_ranges
    best_detections = 0
    
    for iteration in range(max_iterations):
        # Evaluate population
        scores = []
        for candidate in population:
            score, avg_det = evaluate_ranges(candidate)
            scores.append((score, avg_det, candidate))
        
        # Sort by score
        scores.sort(reverse=True, key=lambda x: x[0])
        
        current_best_score, current_best_det, current_best_ranges = scores[0]
        
        if current_best_score > best_score:
            best_score = current_best_score
            best_ranges = current_best_ranges
            best_detections = current_best_det
            print(f"🔥 Iteration {iteration+1}: New best score={best_score:.1f}, matched={int(best_detections)}/{num_leds}")
        else:
            print(f"   Iteration {iteration+1}: score={current_best_score:.1f}, matched={int(current_best_det)}/{num_leds}")
        
        # Early stopping if we're close to target
        if abs(best_detections - num_leds) < 5 and best_score > 90:
            print(f"✅ Converged! Score={best_score:.1f}, Matched={int(best_detections)}/{num_leds}")
            break
        
        # Selection: keep top 50%
        survivors = [candidate for _, _, candidate in scores[:population_size // 2]]
        
        # Generate new population through mutation
        new_population = survivors.copy()
        while len(new_population) < population_size:
            parent = survivors[np.random.randint(0, len(survivors))]
            child = mutate_ranges(parent, mutation_rate=0.25)
            new_population.append(child)
        
        population = new_population
    
    print("\n" + "=" * 60)
    print(f"🎯 OPTIMIZATION COMPLETE")
    print(f"   Final Score: {best_score:.1f}/110")
    print(f"   LEDs Matched: {int(best_detections)}/{num_leds}")
    print(f"   Match Rate: {(best_detections/num_leds)*100:.1f}%")
    
    # Convert numpy types to native Python types for JSON serialization
    best_ranges_serializable = {}
    for color in ['R', 'G', 'B']:
        best_ranges_serializable[color] = {
            'lower': [int(x) for x in best_ranges[color]['lower']],
            'upper': [int(x) for x in best_ranges[color]['upper']]
        }
    best_ranges_serializable['blur'] = int(best_ranges['blur'])
    best_ranges_serializable['area'] = int(best_ranges['area'])
    
    # Save optimized ranges
    output_json = "color_ranges_optimized.json"
    with open(output_json, 'w') as f:
        json.dump(best_ranges_serializable, f, indent=2)
    
    print(f"\n💾 Saved optimized ranges to {output_json}")
    print("\n📋 Optimized parameters:")
    print(f"   Blur kernel: {best_ranges['blur']}")
    print(f"   Min area: {best_ranges['area']}")
    print("\n📋 Copy these to image_processing.py (line 7-15):")
    print("default_ranges = {")
    for color in ['R', 'G', 'B']:
        lower = best_ranges[color]['lower']
        upper = best_ranges[color]['upper']
        print(f"    '{color}': (np.array({lower}), np.array({upper})),")
    print(f"    'blur': {best_ranges['blur']},")
    print(f"    'area': {best_ranges['area']}")
    print("}")
    
    return best_ranges


def auto_calibrate_color_ranges(image_path, output_json="color_ranges.json"):
    """
    Interactive color calibration tool - click on LEDs of each color (R, G, B)
    and it automatically computes optimal HSV ranges with tolerance.
    """
    frame = cv2.imread(image_path)
    if frame is None:
        print("❌ Error: Could not load image.")
        return
    
    # Resize for easier viewing
    display_frame = cv2.resize(frame, (800, 600))
    scale_x = frame.shape[1] / 800
    scale_y = frame.shape[0] / 600
    
    hsv = cv2.cvtColor(frame, cv2.COLOR_BGR2HSV)
    
    # Store clicked samples for each color
    color_samples = {
        'R': [],  # Red samples
        'G': [],  # Green samples
        'B': []   # Blue samples
    }
    
    current_color = 'R'  # Start with Red
    sample_radius = 5  # Sample a small area around click point
    
    def mouse_callback(event, x, y, flags, param):
        nonlocal current_color
        
        if event == cv2.EVENT_LBUTTONDOWN:
            # Convert display coordinates to original image coordinates
            orig_x = int(x * scale_x)
            orig_y = int(y * scale_y)
            
            # Sample HSV values in a small neighborhood around the click
            samples = []
            for dx in range(-sample_radius, sample_radius + 1):
                for dy in range(-sample_radius, sample_radius + 1):
                    px = np.clip(orig_x + dx, 0, frame.shape[1] - 1)
                    py = np.clip(orig_y + dy, 0, frame.shape[0] - 1)
                    samples.append(hsv[py, px])
            
            # Use median HSV value from neighborhood
            median_hsv = np.median(samples, axis=0).astype(int)
            color_samples[current_color].append(median_hsv)
            
            # Visual feedback
            color_map = {'R': (0, 0, 255), 'G': (0, 255, 0), 'B': (255, 0, 0)}
            cv2.circle(display_frame, (x, y), 8, color_map[current_color], 2)
            cv2.putText(display_frame, current_color, (x + 10, y - 10),
                       cv2.FONT_HERSHEY_SIMPLEX, 0.6, color_map[current_color], 2)
            
            print(f"✅ {current_color}: Sampled HSV {median_hsv.tolist()} at ({orig_x}, {orig_y})")
            print(f"   Total {current_color} samples: {len(color_samples[current_color])}")
    
    cv2.namedWindow("Color Calibration - Click on LEDs")
    cv2.setMouseCallback("Color Calibration - Click on LEDs", mouse_callback)
    
    print("🎨 AUTOMATIC COLOR CALIBRATION")
    print("=" * 50)
    print("Instructions:")
    print("  1. Click on RED LEDs (press 'r' when done)")
    print("  2. Click on GREEN LEDs (press 'g' when done)")
    print("  3. Click on BLUE LEDs (press 'b' when done)")
    print("  4. Press 's' to save ranges and exit")
    print("  5. Press 'q' to quit without saving")
    print("=" * 50)
    print(f"Current color: {current_color} (RED)")
    
    while True:
        # Show current frame with samples marked
        temp_display = display_frame.copy()
        cv2.putText(temp_display, f"Sampling: {current_color} | R:{len(color_samples['R'])} G:{len(color_samples['G'])} B:{len(color_samples['B'])}", 
                   (10, 30), cv2.FONT_HERSHEY_SIMPLEX, 0.7, (255, 255, 255), 2)
        cv2.putText(temp_display, "Press 'r'/'g'/'b' to switch | 's' to save | 'q' to quit", 
                   (10, 570), cv2.FONT_HERSHEY_SIMPLEX, 0.5, (255, 255, 255), 1)
        cv2.imshow("Color Calibration - Click on LEDs", temp_display)
        
        key = cv2.waitKey(1) & 0xFF
        
        if key == ord('r'):
            current_color = 'R'
            print(f"\n🔴 Switched to RED sampling")
        elif key == ord('g'):
            current_color = 'G'
            print(f"\n🟢 Switched to GREEN sampling")
        elif key == ord('b'):
            current_color = 'B'
            print(f"\n🔵 Switched to BLUE sampling")
        elif key == ord('s'):
            # Compute ranges and save
            break
        elif key == ord('q'):
            print("❌ Calibration cancelled.")
            cv2.destroyAllWindows()
            return None
    
    cv2.destroyAllWindows()
    
    # Compute HSV ranges with tolerance
    ranges = {}
    tolerance_h = 15  # Hue tolerance
    tolerance_s = 50  # Saturation tolerance
    tolerance_v = 50  # Value tolerance
    
    for color_name, samples in color_samples.items():
        if len(samples) == 0:
            print(f"⚠️  Warning: No samples for {color_name}, using defaults")
            # Default ranges (you can adjust these)
            if color_name == 'R':
                ranges[color_name] = ([144, 193, 80], [179, 255, 255])
            elif color_name == 'G':
                ranges[color_name] = ([30, 70, 100], [90, 255, 255])
            elif color_name == 'B':
                ranges[color_name] = ([97, 130, 154], [144, 255, 255])
            continue
        
        samples_array = np.array(samples)
        
        # Compute statistics
        mean_hsv = np.mean(samples_array, axis=0)
        std_hsv = np.std(samples_array, axis=0)
        min_hsv = np.min(samples_array, axis=0)
        max_hsv = np.max(samples_array, axis=0)
        
        # Build range with tolerance (use min/max from samples + tolerance)
        h_min = max(0, int(min_hsv[0] - tolerance_h))
        h_max = min(179, int(max_hsv[0] + tolerance_h))
        s_min = max(0, int(min_hsv[1] - tolerance_s))
        s_max = min(255, int(max_hsv[1] + tolerance_s))
        v_min = max(0, int(min_hsv[2] - tolerance_v))
        v_max = min(255, int(max_hsv[2] + tolerance_v))
        
        ranges[color_name] = ([h_min, s_min, v_min], [h_max, s_max, v_max])
        
        print(f"\n{color_name} Statistics:")
        print(f"  Samples: {len(samples)}")
        print(f"  Mean HSV: {mean_hsv.astype(int).tolist()}")
        print(f"  Std HSV: {std_hsv.astype(int).tolist()}")
        print(f"  Range: {ranges[color_name][0]} → {ranges[color_name][1]}")
    
    # Save to JSON
    save_data = {
        'R': {'lower': ranges['R'][0], 'upper': ranges['R'][1]},
        'G': {'lower': ranges['G'][0], 'upper': ranges['G'][1]},
        'B': {'lower': ranges['B'][0], 'upper': ranges['B'][1]}
    }
    
    with open(output_json, 'w') as f:
        json.dump(save_data, f, indent=2)
    
    print(f"\n✅ Color ranges saved to {output_json}")
    print("\n📋 Copy these to image_processing.py:")
    print("masks = {")
    for color_name in ['R', 'G', 'B']:
        lower, upper = ranges[color_name]
        print(f"    '{color_name}': cv2.inRange(hsv, np.array({lower}), np.array({upper})),")
    print("}")
    
    return ranges


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
    test_image_path = "led_debug_frames/frame_first.jpg"
    test_video_path = "tmp_video.mp4"
    mappings_path = "jsons/mappings.json"
    
    print("Choose calibration mode:")
    print("1. Auto-optimize with feedback loop (BEST - uses video analysis)")
    print("2. Manual click calibration (click on LEDs)")
    print("3. Manual HSV slider tuning")
    print("4. White spot tuner")
    
    choice = input("Enter choice (1/2/3/4): ").strip()
    
    if choice == "1":
        # Check if files exist
        if not Path(test_video_path).exists():
            print(f"❌ Error: Video not found at {test_video_path}")
            print("   Please run a calibration first to generate tmp_video.mp4")
        elif not Path(mappings_path).exists():
            print(f"❌ Error: Mappings not found at {mappings_path}")
            print("   Please ensure mappings.json exists")
        else:
            optimize_color_ranges_with_feedback(test_video_path, mappings_path)
    elif choice == "2":
        auto_calibrate_color_ranges(test_image_path)
    elif choice == "3":
        hsv_color_tuner(test_image_path)
    elif choice == "4":
        white_spot_tuner(test_image_path)
    else:
        print("Invalid choice. Running auto-optimization by default...")
        if Path(test_video_path).exists() and Path(mappings_path).exists():
            optimize_color_ranges_with_feedback(test_video_path, mappings_path)
        else:
            print("Files missing, falling back to manual click calibration")
            auto_calibrate_color_ranges(test_image_path)

