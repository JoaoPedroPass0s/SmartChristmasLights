import os
from PIL import Image, ImageSequence
import numpy as np
import cv2
import json
import gifEffects
import requests

ESP_IP = "192.168.1.200"  # ESP's IP

def preview_gif_frame(frames, frame_index=0, canvas_size=None, dot_radius=4, save_path=None, show=True):
    """Render one frame from the processed GIF as a black canvas with LEDs drawn.

    - frames: processed frames from GIF
    - frame_index: which frame in the processed frames to preview (0-based)
    - canvas_size: (width, height) of the preview image. If None, auto-calculates from LED positions
    - dot_radius: radius in pixels for each LED dot
    - save_path: optional path to save the preview image
    - show: whether to open a cv2 window to display the preview

    Returns the preview image (numpy array, BGR uint8).
    """
    if len(frames) == 0:
        raise ValueError("No frames extracted from gif")
    if frame_index < 0 or frame_index >= len(frames):
        raise IndexError(f"frame_index out of range (got {frame_index}, max {len(frames)-1})")

    colors = frames[frame_index]  # shape: (num_leds, 3) in RGB

    # Load LED positions (same format used elsewhere: list of (i, (x,y)))
    mapping_file = os.path.join(os.path.dirname(__file__), '..', 'jsons', 'led_positions.json')
    mapping_file = os.path.normpath(mapping_file)
    if not os.path.exists(mapping_file):
        raise FileNotFoundError(f"LED positions file not found: {mapping_file}")

    with open(mapping_file, 'r') as fh:
        led_positions_raw = json.load(fh)

    # Extract positions into Nx2 array
    led_positions = np.array([pos for _, pos in led_positions_raw], dtype=float)
    if led_positions.size == 0:
        raise ValueError("No LED positions found in led_positions.json")

    # Auto-calculate canvas size if not provided
    if canvas_size is None:
        min_xy = led_positions.min(axis=0)
        max_xy = led_positions.max(axis=0)
        # Add padding around the LEDs
        padding = 20
        width = int(max_xy[0] - min_xy[0]) + 2 * padding
        height = int(max_xy[1] - min_xy[1]) + 2 * padding
        canvas_size = (width, height)
        print(f"Auto-calculated canvas size: {canvas_size}")
    
    # Normalize positions to canvas
    min_xy = led_positions.min(axis=0)
    max_xy = led_positions.max(axis=0)
    span = max_xy - min_xy
    # avoid division by zero
    span[span == 0] = 1.0

    width, height = canvas_size
    norm = (led_positions - min_xy) / span
    # Add small margin to prevent LEDs at edges from being cut off
    margin = 10
    xs = (norm[:, 0] * (width - 2*margin) + margin).astype(int)
    ys = (norm[:, 1] * (height - 2*margin) + margin).astype(int)

    # Create black canvas (BGR for OpenCV)
    canvas = np.zeros((height, width, 3), dtype=np.uint8)

    # Draw LEDs: convert RGB -> BGR for cv2
    num_leds = min(len(colors), len(xs))
    for i in range(num_leds):
        r, g, b = colors[i]
        cv2.circle(canvas, (int(xs[i]), int(ys[i])), dot_radius, (int(b), int(g), int(r)), -1)

    if save_path:
        cv2.imwrite(save_path, canvas)

    if show:
        try:
            cv2.imshow('GIF Frame Preview', cv2.resize(canvas, (min(width, 480), min(height, 640))))
            cv2.waitKey(0)
            cv2.destroyWindow('GIF Frame Preview')
        except Exception:
            # headless environment
            pass

    return canvas


def frames_to_video(frames, output_path, fps=15, canvas_size=None, dot_radius=4, led_positions_path=None):
    """Render a list of per-LED RGB frames to a video file (MP4).

    frames: list/array of shape (num_frames, num_leds, 3) in RGB
    output_path: destination path (e.g. ../gifs/output.mp4)
    fps: frames per second
    canvas_size: (width, height). If None, auto-calculates from LED positions
    dot_radius: LED dot radius in pixels
    led_positions_path: optional override path to led_positions.json
    """
    # Resolve led positions path if not provided
    if led_positions_path is None:
        led_positions_path = os.path.join(os.path.dirname(__file__), '..', 'jsons', 'led_positions.json')
        led_positions_path = os.path.normpath(led_positions_path)

    if not os.path.exists(led_positions_path):
        raise FileNotFoundError(f"LED positions file not found: {led_positions_path}")

    with open(led_positions_path, 'r') as fh:
        led_positions_raw = json.load(fh)

    led_positions = np.array([pos for _, pos in led_positions_raw], dtype=float)
    if led_positions.size == 0:
        raise ValueError("No LED positions found in led_positions.json")

    # Auto-calculate canvas size if not provided
    if canvas_size is None:
        min_xy = led_positions.min(axis=0)
        max_xy = led_positions.max(axis=0)
        padding = 20
        width = int(max_xy[0] - min_xy[0]) + 2 * padding
        height = int(max_xy[1] - min_xy[1]) + 2 * padding
        canvas_size = (width, height)
        print(f"Auto-calculated canvas size for video: {canvas_size}")

    min_xy = led_positions.min(axis=0)
    max_xy = led_positions.max(axis=0)
    span = max_xy - min_xy
    span[span == 0] = 1.0

    width, height = canvas_size
    norm = (led_positions - min_xy) / span
    # Add margin
    margin = 10
    xs = (norm[:, 0] * (width - 2*margin) + margin).astype(int)
    ys = (norm[:, 1] * (height - 2*margin) + margin).astype(int)

    # Ensure output directory exists
    out_dir = os.path.dirname(output_path)
    if out_dir and not os.path.exists(out_dir):
        os.makedirs(out_dir, exist_ok=True)

    fourcc = cv2.VideoWriter_fourcc(*'mp4v')
    writer = cv2.VideoWriter(output_path, fourcc, float(fps), (width, height))
    if not writer.isOpened():
        raise RuntimeError(f"Failed to open video writer for {output_path}")

    for colors in frames:
        canvas = np.zeros((height, width, 3), dtype=np.uint8)
        num_leds = min(len(colors), len(xs))
        for i in range(num_leds):
            r, g, b = colors[i]
            cv2.circle(canvas, (int(xs[i]), int(ys[i])), dot_radius, (int(b), int(g), int(r)), -1)
        writer.write(canvas)

    writer.release()
    return output_path


if __name__ == '__main__':
    gif_name = "candycanevertical"
    gif_path = "gifs/"+ gif_name +".gif"
    frames = gifEffects.process_gif_effects(gif_path)

    frames_np = np.concatenate(frames, axis=0)
    #requests.post(f"http://{ESP_IP}/gifupload", data=frames_np.tobytes())

    # Preview first frame (canvas size auto-calculated from LED positions)
    #preview_gif_frame(frames, frame_index=0, dot_radius=4,
    #                  save_path="../gifs/"+ gif_name +"_frame0_preview.png", show=False)

    # Save to video (canvas size auto-calculated from LED positions)
    output_video_path = "gifs/"+ gif_name +"_preview.mp4"
    frames_to_video(frames, output_video_path, fps=15, dot_radius=4)
    print(f"Saved preview video to {output_video_path}")