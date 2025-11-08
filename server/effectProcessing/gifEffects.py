from PIL import Image, ImageSequence
import requests
import numpy as np
import json
import cv2
import os

def process_gif_effects(gif_path):
    with open("../jsons/led_positions.json") as f:
        led_positions = json.load(f)
    led_positions = np.array([pos for _, pos in led_positions])
    min_x, min_y = led_positions.min(axis=0)
    max_x, max_y = led_positions.max(axis=0)
    led_positions_norm = (led_positions - [min_x, min_y]) / ([max_x - min_x, max_y - min_y])

    im = Image.open(gif_path)
    frames = []
    for frame in ImageSequence.Iterator(im):
        frame = frame.convert("RGB").resize((32, 32))  # scale down if needed
        pixels = np.array(frame)
        colors = []
        for pos in led_positions_norm:
            x = int(pos[0] * (frame.width - 1))
            y = int(pos[1] * (frame.height - 1))
            r, g, b = pixels[y, x]
            colors.append((r, g, b))
        frames.append(np.array(colors, dtype=np.uint8))

    return frames