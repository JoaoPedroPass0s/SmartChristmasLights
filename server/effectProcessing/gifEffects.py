from PIL import Image, ImageSequence
import numpy as np
import json
import cv2
import os

def process_gif_effects(gif_path, resolution=300, use_gamma_correction=True, smooth_temporal=True, gamma=2.4, saturation_boost=1.2):
    """
    Process GIF frames for LED display with high-detail preservation.
    
    Improvements:
    1. Uses Gamma Correction (makes colors pop and shadows deeper).
    2. Uses Saturation Boosting (LEDs look better with high saturation).
    3. Uses Vectorized Sampling (Much faster and more precise).
    """

    # 1. Load and Normalize LED Positions
    # We assume this file exists relative to the running script
    if not os.path.exists("jsons/led_positions.json"):
        print("Error: jsons/led_positions.json not found.")
        return []

    with open("jsons/led_positions.json") as f:
        led_positions = json.load(f)
    
    # Extract just coordinates (ignore indices if present)
    coords = np.array([pos for _, pos in led_positions])
    
    # Calculate bounds
    min_x, min_y = coords.min(axis=0)
    max_x, max_y = coords.max(axis=0)
    tree_width = max_x - min_x
    tree_height = max_y - min_y
    
    # Normalize positions to 0.0 - 1.0 range
    # shape: (N, 2)
    led_positions_norm = (coords - [min_x, min_y]) / [tree_width, tree_height]

    # 2. Process GIF
    im = Image.open(gif_path)
    frames = []
    prev_frame_data = None

    for frame in ImageSequence.Iterator(im):
        frame = frame.convert("RGB")
        
        # --- High Quality Resize ---
        # We resize to a higher internal resolution for sampling if needed, 
        # but keep it manageable for performance.
        # CV2's INTER_LANCZOS4 is excellent for preserving sharpness.
        frame_np = np.array(frame)
        
        # Determine mapping coordinates for cv2.remap
        # map_x and map_y need to be float32 maps of where each LED pulls pixels from
        frame_h, frame_w = frame_np.shape[:2]
        
        # Map normalized LED positions to image coordinates
        map_x = (led_positions_norm[:, 0] * (frame_w - 1)).astype(np.float32)
        map_y = (led_positions_norm[:, 1] * (frame_h - 1)).astype(np.float32)

        # --- Vectorized Sampling (The "Detail" Fix) ---
        # cv2.remap allows us to sample the image at arbitrary sub-pixel coordinates
        # using high-quality interpolation methods in one go.
        # We reshape maps to (1, N, 2) to treat the LED string as a single row of pixels
        led_pixels = cv2.remap(
            frame_np, 
            map_x.reshape(1, -1), 
            map_y.reshape(1, -1), 
            interpolation=cv2.INTER_LANCZOS4, # High detail interpolation
            borderMode=cv2.BORDER_CONSTANT,
            borderValue=(0,0,0)
        )
        
        # Result is (1, N, 3), flatten to (N, 3)
        led_pixels = led_pixels[0]

        # --- Post-Processing for LEDs ---
        
        # 1. Saturation Boost (LEDs love saturation)
        if saturation_boost != 1.0:
            # Convert to HSV, scale S, convert back
            # This is done in float32 for precision
            hsv = cv2.cvtColor(led_pixels.reshape(1, -1, 3), cv2.COLOR_RGB2HSV).astype(np.float32)
            hsv[..., 1] *= saturation_boost # Scale Saturation
            hsv[..., 1] = np.clip(hsv[..., 1], 0, 255)
            led_pixels = cv2.cvtColor(hsv.astype(np.uint8), cv2.COLOR_HSV2RGB).reshape(-1, 3)

        # 2. Gamma Correction (Fixes "washed out" look)
        # LEDs are linear, eyes are logarithmic. We apply gamma to make shadows darker
        # and midtones richer.

        if use_gamma_correction and gamma != 1.0:
            # Normalize to 0-1, apply power, scale back
            led_pixels = led_pixels.astype(np.float32) / 255.0
            led_pixels = np.power(led_pixels, gamma)
            led_pixels = (led_pixels * 255.0)

        # 3. Temporal Smoothing (Optional)
        if smooth_temporal and prev_frame_data is not None:
            led_pixels = (0.7 * led_pixels + 0.3 * prev_frame_data)
        
        prev_frame_data = led_pixels.copy()
        
        # Final cast to uint8
        frames.append(led_pixels.astype(np.uint8).tolist())

    return frames