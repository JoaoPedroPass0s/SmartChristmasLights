"""
Send GIF animation frames to the ESP8266
"""
import requests
import struct
import sys
sys.path.append('..')
from effectProcessing import gifEffects

ESP_IP = "192.168.1.200"

def send_gif_to_esp(gif_path, esp_ip=ESP_IP):
    """
    Process a GIF and send frame data to ESP8266
    
    Format:
    - First 2 bytes: number of frames (little-endian uint16)
    - Remaining bytes: frame data (num_frames * 200 LEDs * 3 bytes RGB)
    """
    print(f"Processing GIF: {gif_path}")
    
    # Process the GIF using your existing function
    frames = gifEffects.process_gif_effects(gif_path)
    
    num_frames = len(frames)
    print(f"Number of frames: {num_frames}")
    
    if num_frames > 100:
        print(f"Warning: {num_frames} frames exceeds MAX_GIF_FRAMES (100)")
        print("Truncating to 100 frames...")
        frames = frames[:100]
        num_frames = 100
    
    # Build the data payload
    # Header: 2 bytes for frame count
    payload = bytearray(struct.pack('<H', num_frames))
    
    # Append frame data
    for frame in frames:
        # frame is shape (num_leds, 3) - RGB values
        for led in frame:
            payload.extend(led)  # Append R, G, B bytes
    
    total_size = len(payload)
    print(f"Total payload size: {total_size} bytes ({total_size / 1024:.2f} KB)")
    print(f"Expected size: {2 + num_frames * 200 * 3} bytes")
    
    # Send to ESP
    url = f"http://{esp_ip}/gif"
    print(f"Sending to {url}...")
    
    try:
        response = requests.post(url, data=payload, timeout=30)
        print(f"Response: {response.status_code} - {response.text}")
        return True
    except Exception as e:
        print(f"Error sending GIF: {e}")
        return False

def control_gif(action, value=None, esp_ip=ESP_IP):
    """
    Control GIF playback
    action: 'play', 'pause', 'stop', 'speed'
    value: for 'speed' action, the delay in ms
    """
    url = f"http://{esp_ip}/gif/control"
    params = {"action": action}
    
    if action == "speed" and value is not None:
        params["value"] = value
    
    try:
        response = requests.get(url, params=params, timeout=5)
        print(f"{action}: {response.text}")
        return True
    except Exception as e:
        print(f"Error: {e}")
        return False

if __name__ == "__main__":
    import os
    
    # Example 1: Send a GIF
    gif_path = "gifs/candycane.gif"
    
    if os.path.exists(gif_path):
        print("=== Sending GIF to ESP ===")
        if send_gif_to_esp(gif_path):
            print("\n✅ GIF uploaded successfully!")
            print("\nYou can now control playback:")
            print("  - control_gif('play')   - Start playing")
            print("  - control_gif('pause')  - Pause")
            print("  - control_gif('stop')   - Stop and reset")
            print("  - control_gif('speed', 100)  - Set frame delay to 100ms")
    else:
        print(f"GIF not found: {gif_path}")
    
    # Example 2: Control playback
    #control_gif('stop')
    control_gif('speed', 40)  # Faster playback
