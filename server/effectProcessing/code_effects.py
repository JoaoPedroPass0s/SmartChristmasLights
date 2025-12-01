import json
import numpy as np
import math
import random
import colorsys
import os

class LEDEffectGenerator:
    def __init__(self, json_path="jsons/led_positions.json"):
        # 1. Load and Parse Coordinates
        if not os.path.exists(json_path):
            raise FileNotFoundError(f"Could not find {json_path}")

        with open(json_path) as f:
            data = json.load(f)

        # Extract [x, y] from the JSON structure
        # Assuming format: [[index, [x, y, z]], ...] or similar
        # We convert to a NumPy array of shape (N, 2)
        try:
            self.coords = np.array([item[1][:2] for item in data], dtype=float)
        except:
            # Fallback if structure is just list of coords
            self.coords = np.array(data, dtype=float)

        self.num_leds = len(self.coords)
        
        # Create separate arrays for X and Y for fast vectorized math
        self.x = self.coords[:, 0]
        self.y = self.coords[:, 1]
        
        # The main LED buffer (N, 3) initialized to Black
        self.leds = np.zeros((self.num_leds, 3), dtype=np.uint8)

    def get_effect_names():
        """Returns a list of available effect names."""
        return [
            "waving_stripe",
            "down_to_up",
            "pulsating_glow",
            "color_waves",
            "ripple_effect",
            "color_pulses",
            "radial_pulse",
            "dynamic_circular_gradient",
            "coordinate_twinkling",
            "candy_cane_effect",
            "right_to_left",
            "wave_ripple_effect"
        ]

    # --- Helpers to mimic FastLED ---
    def fill_solid(self, color):
        """Sets all LEDs to specific [r, g, b]"""
        self.leds[:] = color

    def fade_to_black_by(self, amount):
        """Simulates leds[i].fadeToBlackBy(amount)"""
        # FastLED logic: val = (val * (255-amount)) >> 8
        # We approximate with float math
        factor = (255 - amount) / 255.0
        self.leds = (self.leds * factor).astype(np.uint8)

    def hsv_to_rgb_array(self, h, s, v):
        """Vectorized HSV to RGB conversion for arrays"""
        # If inputs are scalars, broadcast them
        # Note: Python colorsys is slow for arrays. We use a simple numpy approx or loop if needed.
        # For single colors, we use colorsys.
        r, g, b = colorsys.hsv_to_rgb(h/255.0, s/255.0, v/255.0)
        return [int(r*255), int(g*255), int(b*255)]

    def record_frame(self):
        """Returns the current state of LEDs as a standard list format"""
        return self.leds.copy().tolist()

    # ==========================================
    #               THE EFFECTS
    # ==========================================

    def waving_stripe(self):
        frames = []
        strip_width = 50
        color = [255, 0, 0] # Red

        # C++: for (int x = 0; x < 600; x += 10)
        for x in range(0, 600, 10):
            # 1. Fade entire strip
            self.fade_to_black_by(20)

            # 2. Draw Moving Stripe (Vectorized)
            # Logic: x > frame_x - width/2 AND x < frame_x + width/2
            mask = (self.x > x - strip_width/2) & (self.x < x + strip_width/2)
            self.leds[mask] = color

            frames.append(self.record_frame())
        return frames

    def down_to_up(self):
        frames = []
        color = [255, 0, 0] # Red
        bg_color = [255, 255, 255] # White (based on your 2nd version)

        # C++: fill_solid(White)
        self.fill_solid(bg_color)
        frames.append(self.record_frame())

        # C++ loops 5 times
        for _ in range(5):
            for x in range(50, 600, 20):
                # We calculate the strip on top of the existing background
                # But C++ snippet had logic: if in range RED, else WHITE.
                mask = (self.x > x - 50) & (self.x < x + 50)
                
                self.leds[mask] = color
                self.leds[~mask] = bg_color # The "else" part

                frames.append(self.record_frame())
                
                # C++ delay(100) -> 1 frame
        return frames

    def pulsating_glow(self):
        frames = []
        color = [255, 0, 0]
        max_radius = 260
        center_x = 360
        
        # Calculate distances from center X (Pre-calculated for speed)
        dists = np.abs(self.x - center_x)

        # Expand
        for radius in range(0, max_radius, 5): # Step 5 to reduce frame count
            self.fill_solid([0, 0, 255]) # Blue
            self.leds[dists < radius] = color
            frames.append(self.record_frame())

        # Contract
        for radius in range(max_radius, 0, -5):
            self.fill_solid([0, 0, 255]) # Blue
            self.leds[dists < radius] = color
            frames.append(self.record_frame())
            
        return frames

    def color_waves(self):
        frames = []
        hue = 0
        
        # C++: x from 0 to 600
        for x in range(0, 600, 10):
            self.fill_solid([0,0,0])
            
            mask = (self.x > x - 50) & (self.x < x + 50)
            
            # C++ applies CHSV(hue, 255, 255) to the band
            rgb = self.hsv_to_rgb_array(hue % 255, 255, 255)
            self.leds[mask] = rgb
            
            hue += 5
            frames.append(self.record_frame())
        return frames

    def ripple_effect(self):
        frames = []
        color = [255, 0, 0]
        max_radius = 300
        
        for _ in range(5): # Number of times
            self.fill_solid([0, 0, 0])
            frames.append(self.record_frame())
            
            # Random center
            cx = random.randint(0, 600)
            cy = random.randint(0, 400)
            
            # Pre-calculate distances for this ripple
            dists = np.sqrt((self.x - cx)**2 + (self.y - cy)**2)
            
            for radius in range(0, max_radius, 10):
                # Ring logic: dist < radius+10 AND dist > radius-10
                mask = (dists < radius + 10) & (dists > radius - 10)
                
                # C++ logic: if ring Color, else Blue
                self.leds[:] = [0, 0, 255] # Set all Blue
                self.leds[mask] = color    # Set ring Red
                
                frames.append(self.record_frame())
        return frames

    def color_pulses(self):
        frames = []
        
        # Settings
        center = [360, 250]   # Adjust to your actual center
        num_frames = 300      # How long the animation runs
        rotation_speed = 0.2  # How fast it spins
        tightness = 30.0      # Higher = "looser" spiral coils
        arm_thickness = 0.6   # How thick the spiral line is (in radians)
        hue = 0               # Starting color hue

        # 1. Pre-calculate Polar Coordinates (Vectorized)
        # We do this once outside the loop for performance
        dx = self.x - center[0]
        dy = self.y - center[1]
        
        radii = np.sqrt(dx**2 + dy**2)
        
        # Get angles and force them into 0 -> 2PI range (0 to 6.28)
        # This prevents the "cut" effect where negative angles mess up the modulo
        angles = (np.arctan2(dy, dx) + 2 * np.pi) % (2 * np.pi)

        time = 0

        for _ in range(num_frames):
            # Clear background to Black so colors pop
            self.fill_solid([0, 0, 0]) 
            
            # 2. The Spiral Math
            # We calculate a "phase" for every LED based on its angle and distance.
            # As time increases, the phase shifts, rotating the effect.
            # Formula: (Angle + Time + Distance/Tightness) % 2PI
            spiral_phase = (angles + time + (radii / tightness)) % (2 * np.pi)
            
            # 3. Create the Mask
            # Light up LEDs where the phase is inside our thickness threshold
            mask = spiral_phase < arm_thickness
            
            # 4. Calculate the Rainbow Color
            # Logic: We increment 'hue' every frame (like colorWaves)
            # hsv_to_rgb expects inputs 0.0 to 1.0, so we divide by 255.0
            r, g, b = colorsys.hsv_to_rgb((hue % 255) / 255.0, 1.0, 1.0)
            current_color = [int(r * 255), int(g * 255), int(b * 255)]
            
            # Apply color to the spiral arm
            self.leds[mask] = current_color
            
            # Record frame
            frames.append(self.record_frame())
            
            # Increment Animation State
            time -= rotation_speed # Change to += to spin the other way
            hue += 5               # Cycle through the rainbow
            
        return frames

    def radial_pulse(self):
        frames = []
        center = [360, 250]
        max_radius = 250
        
        dists = np.sqrt((self.x - center[0])**2 + (self.y - center[1])**2)
        
        # Helper to apply gradient based on distance
        def apply_gradient(radius_limit):
            self.fill_solid([0, 0, 0])
            mask = dists < radius_limit
            
            if np.any(mask):
                # Map distances to Hue (0-255)
                # mask_dists = dists[mask]
                # hues = (mask_dists / max_radius) * 255
                # This requires per-pixel color conversion which is tricky to vectorize simply 
                # without opencv, so we iterate just the active pixels for color conversion.
                
                active_indices = np.where(mask)[0]
                for idx in active_indices:
                    d = dists[idx]
                    h = int((d / max_radius) * 255)
                    self.leds[idx] = self.hsv_to_rgb_array(h, 255, 255)
                    
            frames.append(self.record_frame())

        # Expand
        for r in range(0, max_radius, 5):
            apply_gradient(r)
            
        # Contract
        for r in range(max_radius, 0, -5):
            apply_gradient(r)
            
        return frames

    def dynamic_circular_gradient(self):
        frames = []
        max_radius = 300
        cx, cy = 360, 250
        dx, dy = 2, 1
        hue_offset = 0
        
        # Simulate 300 frames (since C++ is infinite)
        for _ in range(300):
            self.fill_solid([0, 0, 255]) # Blue
            
            dists = np.sqrt((self.x - cx)**2 + (self.y - cy)**2)
            mask = dists < max_radius
            
            # Apply color gradient
            active_indices = np.where(mask)[0]
            for idx in active_indices:
                d = dists[idx]
                # map distance to 0-255, add offset, mod 255
                h = (int((d / max_radius) * 255) + hue_offset) % 255
                self.leds[idx] = self.hsv_to_rgb_array(h, 255, 255)

            frames.append(self.record_frame())
            
            # Move center
            cx += dx
            cy += dy
            if cx < 0 or cx > 720: dx = -dx
            if cy < 0 or cy > 500: dy = -dy
            hue_offset += 5
            
        return frames

    def coordinate_twinkling(self):
        frames = []
        
        # C++ loop t < 100
        for t in range(100):
            # Calculate twinkle chance vectorized
            # (x + y + t) % 100
            val = (self.x + self.y + t) % 100
            
            twinkle_mask = val < 10
            
            # If twinkle, set White
            self.leds[twinkle_mask] = [255, 255, 255]
            
            # Else fade
            # We must apply fade to ONLY non-twinkling, or all? 
            # C++: if < 10 white else fade.
            # We apply fade to everything first? No, specific indices.
            
            # Get current colors of non-twinkling LEDs
            fade_mask = ~twinkle_mask
            current_fading = self.leds[fade_mask]
            
            # Apply fade (approx 20/255 ~= 0.92 multiplier)
            self.leds[fade_mask] = (current_fading * 0.9).astype(np.uint8)
            
            frames.append(self.record_frame())
            
        return frames

    def candy_cane_effect(self):
        frames = []
        stripe_width = 150
        speed = 6
        offset = 0
        
        # C++ 200 frames
        for _ in range(200):
            self.fill_solid([0,0,0])
            
            # pos = x + y + offset
            diag = self.x + self.y + offset
            
            # (pos / width) % 2 == 0
            # np.floor to simulate integer division behavior
            mask = (np.floor(diag / stripe_width) % 2 == 0)
            
            self.leds[mask] = [255, 0, 0] # Red
            self.leds[~mask] = [255, 255, 255] # White
            
            frames.append(self.record_frame())
            offset += speed
            
        return frames

    def right_to_left(self):
        # Diagonal stripes based on X + offset
        frames = []
        stripe_width = 150
        speed = 6
        offset = 0
        
        for _ in range(200):
            diag = self.x + offset
            mask = (np.floor(diag / stripe_width) % 2 == 0)
            self.leds[mask] = [255, 0, 0]
            self.leds[~mask] = [255, 255, 255]
            frames.append(self.record_frame())
            offset += speed
        return frames

    def wave_ripple_effect(self):
        frames = []
        color = [255, 0, 0]
        max_radius = 400
        waves = [] # List of dicts {cx, cy, r}
        
        # Timing simulation
        sim_time = 0
        last_wave_time = 0
        delay_between = 1000 # ms
        frame_dt = 50 # ms per frame
        
        # Run loop (approx 50 "times" * cycles) -> lets do 500 frames
        for _ in range(500):
            # 1. Spawn Wave
            if len(waves) < 5 and (sim_time - last_wave_time > delay_between):
                waves.append({
                    'cx': random.randint(0, 600),
                    'cy': random.randint(0, 400),
                    'r': 0
                })
                last_wave_time = sim_time
            
            # 2. Reset Background
            self.fill_solid([255, 255, 255]) # White
            
            # 3. Process Waves
            active_waves = []
            for w in waves:
                w['r'] += 10
                
                # Draw Wave
                dists = np.sqrt((self.x - w['cx'])**2 + (self.y - w['cy'])**2)
                mask = (dists < w['r'] + 10) & (dists > w['r'] - 10)
                
                # Apply color (Overwriting white)
                self.leds[mask] = color
                
                if w['r'] <= max_radius:
                    active_waves.append(w)
            
            waves = active_waves
            
            frames.append(self.record_frame())
            sim_time += frame_dt
            
        return frames

# --- Usage ---
if __name__ == "__main__":
    # Example usage
    try:
        gen = LEDEffectGenerator("jsons/led_positions.json")
        
        # Generate a specific effect
        print("Generating Spiral Effect...")
        frames = gen.color_pulses()
        print(f"Generated {len(frames)} frames.")
        
        # Generate Wave Ripple
        print("Generating Wave Ripple...")
        frames2 = gen.wave_ripple_effect()
        print(f"Generated {len(frames2)} frames.")
        
        # Save to JSON (Optional)
        # with open("spiral.json", "w") as f:
        #     json.dump(frames, f)

    except Exception as e:
        print(e)