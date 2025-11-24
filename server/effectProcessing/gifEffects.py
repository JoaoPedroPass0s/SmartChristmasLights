from PIL import Image, ImageSequence
import requests
import numpy as np
import json
import cv2
import os

def process_gif_effects(gif_path, resolution=128, use_interpolation=True, smooth_temporal=False):

    with open("jsons/led_positions.json") as f:
        led_positions = json.load(f)
    led_positions = np.array([pos for _, pos in led_positions])
    min_x, min_y = led_positions.min(axis=0)
    max_x, max_y = led_positions.max(axis=0)
    led_positions_norm = (led_positions - [min_x, min_y]) / ([max_x - min_x, max_y - min_y])

    im = Image.open(gif_path)
    frames = []
    prev_colors = None
    
    for frame in ImageSequence.Iterator(im):
        # Use high-quality resampling (LANCZOS for downscaling, BICUBIC for upscaling)
        frame = frame.convert("RGB").resize((resolution, resolution), Image.Resampling.LANCZOS)
        pixels = np.array(frame, dtype=np.float32)
        
        colors = []
        for pos in led_positions_norm:
            if use_interpolation:
                # Use bilinear interpolation for smoother color sampling
                x = pos[0] * (frame.width - 1)
                y = pos[1] * (frame.height - 1)
                
                x0, y0 = int(np.floor(x)), int(np.floor(y))
                x1, y1 = min(x0 + 1, frame.width - 1), min(y0 + 1, frame.height - 1)
                
                # Bilinear interpolation weights
                wx = x - x0
                wy = y - y0
                
                # Interpolate color values
                c00 = pixels[y0, x0]
                c01 = pixels[y0, x1]
                c10 = pixels[y1, x0]
                c11 = pixels[y1, x1]
                
                color = (1 - wx) * (1 - wy) * c00 + wx * (1 - wy) * c01 + \
                        (1 - wx) * wy * c10 + wx * wy * c11
                
                r, g, b = color.astype(np.uint8)
            else:
                # Simple nearest neighbor sampling
                x = int(pos[0] * (frame.width - 1))
                y = int(pos[1] * (frame.height - 1))
                r, g, b = pixels[y, x].astype(np.uint8)
            
            colors.append((r, g, b))
        
        colors = np.array(colors, dtype=np.uint8)
        
        # Optional temporal smoothing to reduce flicker
        if smooth_temporal and prev_colors is not None:
            colors = (0.7 * colors + 0.3 * prev_colors).astype(np.uint8)
        
        prev_colors = colors.copy()
        frames.append(colors)

    return frames