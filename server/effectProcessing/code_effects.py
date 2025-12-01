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
        return [
            "conical_spiral_effect",
            "waving_stripe",
            "down_to_up",
            "pulsating_glow",
            "color_waves",
            "wrapping_spiral_effect",
            "ripple_effect",
            "color_pulses",
            "radial_pulse",
            "dynamic_circular_gradient",
            "coordinate_twinkling",
            "candy_cane_effect",
            "right_to_left",
            "wave_ripple_effect",
            "fireworks",
            "falling_snow",
            "plasma_cloud",
            "radar_sweep",
            "glitter_sparkles",
            "green_glitter",
            "bouncing_balls",
            "concentric_rings",
            "dual_rotation",
            "gradient_wipe"
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

    def conical_spiral_effect(self):
        frames = []
        num_frames = 400
        
        # --- Settings ---
        spiral_loops = 4.0    # How many times it wraps around the tree
        speed = 0.2           # Rotation speed
        stripe_thickness = 40 # Thickness of the line in pixels/coords
        color_speed = 5       # How fast the rainbow cycles
        
        # 1. Analyze the Tree Shape
        min_y = np.min(self.y)
        max_y = np.max(self.y)
        tree_height = max_y - min_y
        
        min_x = np.min(self.x)
        max_x = np.max(self.x)
        tree_width = max_x - min_x
        center_x = (min_x + max_x) / 2.0

        # 2. Pre-calculate Normalized Height (0.0 at bottom, 1.0 at top)
        # Note: In many LED systems, Y=0 is top. If your Y=0 is bottom, swap logic.
        # Assuming Y increases downwards (standard image coords):
        # Bottom of tree is Max Y. Top is Min Y.
        # Let's generalize: We want 0.0 at "wide part" and 1.0 at "pointy part".
        
        # If your Top is Y=0:
        norm_height = 1.0 - (self.y - min_y) / tree_height 
        # Result: Top of tree = 0.0, Bottom = 1.0 (Wait, we want the inverse for radius)
        
        # Let's define "Taper Factor": 
        # 1.0 = Full Width (Bottom), 0.0 = No Width (Top)
        # We assume the tree is roughly centered and triangular.
        # We simply use the normalized height to scale the radius.
        
        # Normalized Y from 0 (bottom) to 1 (top)
        # We assume standard cartesian: Y is bigger at bottom? 
        # Let's look at your previous code, usually Y=0 is top.
        # If Y=0 is top (pointy), radius should be small.
        # If Y=max is bottom (wide), radius should be big.
        
        taper_factor = (self.y - min_y) / tree_height 
        # If Y=0 is top, taper_factor is 0. Radius becomes 0. Perfect.
        # If Y=Height is bottom, taper_factor is 1. Radius is Max. Perfect.

        # Max radius at the very bottom of the tree
        max_radius = tree_width / 2.0

        time = 0
        hue = 0

        for _ in range(num_frames):
            self.fill_solid([0,0,0]) # Clear background
            
            # --- 3D Projection Math ---
            
            # 1. Calculate the Angle (Theta) for every LED based on height
            # As we go up the tree, the angle increases (creating the spiral)
            theta = (taper_factor * spiral_loops * 2 * np.pi) - time
            
            # 2. Calculate the "Ideal X" for the spiral at this height
            # x = center + (radius * taper * sin(theta))
            current_radius = max_radius * taper_factor
            ideal_x = center_x + (current_radius * np.sin(theta))
            
            # 3. Calculate "Z-Depth" (Front or Back?)
            # Cosine gives us the depth. +1 is front, -1 is back.
            z_depth = np.cos(theta) 
            
            # --- Drawing Logic ---
            
            # Check distance from the ideal X line
            dist = np.abs(self.x - ideal_x)
            
            # Mask: LED is inside the stripe width
            # We scale thickness by taper too, so the line gets thinner at the top
            current_thickness = stripe_thickness * (0.3 + 0.7 * taper_factor)
            mask_hit = dist < current_thickness

            # --- Masking for "Behind the Tree" ---
            # If z_depth is negative, the spiral is on the back side.
            # We can either hide it, or dim it. 
            # Let's Keep only the Front (z > -0.2) to look like it's wrapping around.
            mask_front = z_depth > -0.2
            
            final_mask = mask_hit & mask_front
            
            # --- Coloring ---
            # Create a Rainbow
            r, g, b = colorsys.hsv_to_rgb((hue % 255) / 255.0, 1.0, 1.0)
            color = [int(r*255), int(g*255), int(b*255)]
            
            # Apply Color
            self.leds[final_mask] = color
            
            # Optional: Add a dimmer "Back" spiral for better 3D effect
            # (Uncomment this block if you want to see the back side dimly)
            """
            mask_back = mask_hit & (~mask_front)
            dim_color = [int(c * 0.2) for c in color]
            self.leds[mask_back] = dim_color
            """

            frames.append(self.record_frame())
            
            time += speed
            hue += color_speed

        return frames

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
    
    def wrapping_spiral_effect(self):
        frames = []
        num_frames = 400 # Longer animation loop
        
        # ================= PARAMETERS TO TWEAK =================
        # Speed of vertical movement/rotation
        # Positive = downwards wrapping, Negative = upwards wrapping
        speed = 0.15         
        
        # How tightly coiled the spiral is. 
        # Higher number = more wraps around the tree.
        frequency = 8.0    
        
        # Thickness of the spiral stripe in coordinate units.
        # If your coordinates are 0-600, try approx 20-40.
        stripe_thickness = 30.0    

        # Speed of the rainbow color shifting
        hue_increment = 3   
        # =======================================================


        # 1. Calculate Tree Dimensions once (Vectorized)
        # We need to know the shape of the tree to wrap around it correctly.
        min_y = np.min(self.y)
        max_y = np.max(self.y)
        tree_height = max_y - min_y
        
        min_x = np.min(self.x)
        max_x = np.max(self.x)
        tree_center_x = (min_x + max_x) / 2.0
        max_tree_width = max_x - min_x

        # 2. Pre-calculate Tapering
        # Normalize Y to 0.0-1.0 range for easier math.
        # Assuming larger Y values are lower on the tree (standard image coordinates).
        # 0.0 = Bottom of tree, 1.0 = Top of tree.
        y_norm = (self.y - min_y) / tree_height

        # Define a taper shape so the spiral gets narrower at the top.
        # 1.0 at bottom, gradually shrinking to 0.2 scale at the top.
        taper_factor = 1.0 - (y_norm * 0.8)
        
        # Calculate the maximum radius allowed at each LED's specific height
        allowed_radii_at_height = (max_tree_width / 2.0) * taper_factor
        
        time = 0
        hue = 0

        for _ in range(num_frames):
            # Background: Dim existing lights slightly for a trail effect, 
            # or use fill_solid([0,0,0]) for a clean black background.
            self.fade_to_black_by(80) 
            
            # --- The Helix Projection Math ---
            
            # 1. Calculate the sine wave based on height and time.
            # This creates the left-to-right oscillation.
            sine_wave_val = np.sin((y_norm * frequency) + time)
            
            # 2. Determine the target X position for the center of the stripe.
            # CenterX + (How wide we can go at this height * sine value)
            target_x_at_height = tree_center_x + (allowed_radii_at_height * sine_wave_val)

            # --- The Mask ---
            # Find LEDs whose real X coordinate is close to the ideal target X line.
            # We calculate absolute distance on the X axis.
            dist_from_stripe_center = np.abs(self.x - target_x_at_height)
            
            # Create boolean mask for LEDs inside the stripe thickness
            mask = dist_from_stripe_center < (stripe_thickness / 2.0)
            
            # --- Color Logic ---
            # Calculate current rainbow color
            r, g, b = colorsys.hsv_to_rgb((hue % 255) / 255.0, 1.0, 1.0)
            rainbow_color = [int(r*255), int(g*255), int(b*255)]

            # Apply color to the masked area
            self.leds[mask] = rainbow_color

            # Record and advance state
            frames.append(self.record_frame())
            time += speed
            hue += hue_increment
            
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

    def fireworks(self):
        frames = []
        num_frames = 400
        gravity = 0.5
        particles = [] 
        
        for t in range(num_frames):
            self.fade_to_black_by(30) # Trails
            
            # 1. Randomly launch (10% chance)
            if random.random() < 0.1: 
                cx = random.choice(self.x)
                cy = np.min(self.y) + (np.max(self.y) - np.min(self.y)) * 0.3 
                hue = random.random()
                
                # Spawn explosion particles
                for _ in range(20):
                    angle = random.random() * 2 * np.pi
                    speed = random.uniform(2, 6)
                    particles.append({
                        'x': cx, 'y': cy,
                        'vx': np.cos(angle) * speed,
                        'vy': np.sin(angle) * speed,
                        'hue': hue,
                        'life': 1.0
                    })
            
            # 2. Update Particles
            active_particles = []
            if particles:
                for p in particles:
                    p['x'] += p['vx']
                    p['y'] += p['vy']
                    p['vy'] += gravity
                    p['life'] -= 0.04
                    
                    if p['life'] > 0:
                        dist = np.sqrt((self.x - p['x'])**2 + (self.y - p['y'])**2)
                        mask = dist < 15 
                        
                        r,g,b = colorsys.hsv_to_rgb(p['hue'], 1.0, p['life'])
                        color = np.array([r*255, g*255, b*255])
                        
                        # Additive blending
                        current = self.leds[mask].astype(int)
                        blended = np.minimum(255, current + color).astype(np.uint8)
                        self.leds[mask] = blended
                        
                        active_particles.append(p)
            
            particles = active_particles
            frames.append(self.record_frame())
        return frames

    def falling_snow(self):
        frames = []
        num_frames = 400
        num_flakes = 50
        
        min_y, max_y = np.min(self.y), np.max(self.y)
        min_x, max_x = np.min(self.x), np.max(self.x)
        
        # Init flakes
        flake_x = np.random.uniform(min_x, max_x, num_flakes)
        flake_y = np.random.uniform(min_y, max_y, num_flakes)
        flake_speed = np.random.uniform(2, 5, num_flakes)
        
        for _ in range(num_frames):
            self.fill_solid([0, 0, 0])
            
            flake_y += flake_speed
            
            # Reset flakes at bottom
            reset_mask = flake_y > max_y
            flake_y[reset_mask] = min_y - 10
            flake_x[reset_mask] = np.random.uniform(min_x, max_x, np.sum(reset_mask))
            
            for i in range(num_flakes):
                dist = np.sqrt((self.x - flake_x[i])**2 + (self.y - flake_y[i])**2)
                mask = dist < 10 
                self.leds[mask] = [200, 200, 255]
                
            frames.append(self.record_frame())
        return frames

    def plasma_cloud(self):
        frames = []
        time = 0
        scale = 0.02 
        
        for _ in range(300):
            # Complex interference pattern
            v1 = np.sin(self.x * scale + time)
            v2 = np.sin(self.y * scale + time)
            v3 = np.sin((self.x + self.y) * scale + time)
            total_val = v1 + v2 + v3
            
            # Norm to 0-1
            norm_val = (total_val + 3) / 6.0
            
            # Fast Vectorized Color Mapping
            colors = np.zeros((self.num_leds, 3), dtype=np.uint8)
            colors[:, 0] = (np.sin(norm_val * np.pi) * 127 + 128).astype(np.uint8)
            colors[:, 1] = (np.sin(norm_val * np.pi + 2) * 127 + 128).astype(np.uint8)
            colors[:, 2] = (np.sin(norm_val * np.pi + 4) * 127 + 128).astype(np.uint8)
            
            self.leds[:] = colors
            frames.append(self.record_frame())
            time += 0.1
        return frames

    def radar_sweep(self):
        frames = []
        center_x = (np.min(self.x) + np.max(self.x)) / 2
        center_y = (np.min(self.y) + np.max(self.y)) / 2
        
        angles = np.arctan2(self.y - center_y, self.x - center_x)
        angles = (angles + 2*np.pi) % (2*np.pi)
        
        sweep_angle = 0
        speed = 0.13
        
        for _ in range(300):
            self.fade_to_black_by(40) 
            
            diff = np.abs(angles - sweep_angle)
            diff = np.minimum(diff, 2*np.pi - diff)
            
            mask = diff < 0.15
            self.leds[mask] = [0, 255, 0] # Green
            
            frames.append(self.record_frame())
            sweep_angle = (sweep_angle + speed) % (2*np.pi)
            
        return frames

    def glitter_sparkles(self):
        frames = []
        bg_color = np.array([50, 0, 0]) # Dim Red
        sparkle_color = np.array([255, 255, 200]) # Gold
        
        for _ in range(200):
            # Fade towards background color
            current = self.leds.astype(float)
            self.leds = (current * 0.9 + bg_color * 0.1).astype(np.uint8)
            
            # Ignite random LEDs
            lucky_indices = np.random.choice(self.num_leds, size=int(self.num_leds * 0.02), replace=False)
            self.leds[lucky_indices] = sparkle_color
            
            frames.append(self.record_frame())
        return frames

    def green_glitter(self):
        frames = []
        meteor_size = 80 
        offset = 0
        
        for _ in range(300):
            self.fill_solid([0, 0, 0])
            
            # Pseudo-random column offset based on X
            col_offset = (self.x * 123.45) % 800 
            pos = (self.y + offset + col_offset) % 800
            
            # Head
            mask_head = pos < 20 
            self.leds[mask_head] = [200, 255, 200]
            
            # Trail
            mask_trail = (pos >= 20) & (pos < meteor_size)
            if np.any(mask_trail):
                brightness = 1.0 - ((pos[mask_trail] - 20) / (meteor_size - 20))
                brightness = np.clip(brightness, 0, 1)
                
                green_vals = (brightness * 255).astype(np.uint8)
                self.leds[mask_trail, 1] = green_vals
                self.leds[mask_trail, 0] = 0
                self.leds[mask_trail, 2] = 0

            frames.append(self.record_frame())
            offset += 15
        return frames

    def bouncing_balls(self):
        frames = []
        num_balls = 3
        max_y, min_y = np.max(self.y), np.min(self.y)
        height = max_y - min_y
        
        ball_h = np.array([1.0, 0.8, 0.6]) 
        ball_v = np.array([0.0, 0.0, 0.0])
        gravity = -0.002
        elasticity = 0.85
        colors = [[255,0,0], [0,255,0], [0,0,255]]
        
        center_x = (np.min(self.x) + np.max(self.x)) / 2
        
        for _ in range(400):
            self.fade_to_black_by(40)
            
            ball_v += gravity
            ball_h += ball_v
            
            for i in range(num_balls):
                if ball_h[i] < 0:
                    ball_h[i] = 0
                    ball_v[i] = -ball_v[i] * elasticity
            
            for i in range(num_balls):
                real_y = max_y - (ball_h[i] * height)
                dist = np.abs(self.y - real_y)
                dist_x = np.abs(self.x - center_x)
                
                mask = (dist < 30) & (dist_x < 150)
                self.leds[mask] = colors[i]
                
            frames.append(self.record_frame())
        return frames

    def concentric_rings(self):
        frames = []
        center_x = (np.min(self.x) + np.max(self.x)) / 2
        center_y = (np.min(self.y) + np.max(self.y)) / 2
        
        dists = np.sqrt((self.x - center_x)**2 + (self.y - center_y)**2)
        offset = 0
        
        for _ in range(300):
            self.fill_solid([0,0,0])
            val = np.sin((dists / 30.0) - offset)
            mask = val > 0.8
            self.leds[mask] = [0, 100, 255] # Cyan
            
            frames.append(self.record_frame())
            offset += 0.2
        return frames

    def dual_rotation(self):
        frames = []
        center_x = (np.min(self.x) + np.max(self.x)) / 2
        center_y = (np.min(self.y) + np.max(self.y)) / 2
        
        angles = np.arctan2(self.y - center_y, self.x - center_x)
        rotation = 0
        
        for _ in range(300):
            eff_angle = (angles + rotation) % (2*np.pi)
            mask_a = eff_angle < np.pi
            
            self.leds[mask_a] = [255, 0, 0]
            self.leds[~mask_a] = [0, 0, 255]
            
            # White border
            mask_border = np.abs(eff_angle - np.pi) < 0.1
            self.leds[mask_border] = [255, 255, 255]
            
            frames.append(self.record_frame())
            rotation += 0.05
        return frames

    def gradient_wipe(self):
        frames = []
        projection = self.x + self.y
        min_p, max_p = np.min(projection), np.max(projection)
        offset = 0
        
        for _ in range(300):
            self.fill_solid([0,0,0])
            
            pos = (projection - min_p + offset) % (max_p - min_p)
            norm_pos = pos / (max_p - min_p)
            
            # Simple Rainbow Map
            colors = np.zeros((self.num_leds, 3), dtype=np.uint8)
            colors[:, 0] = (np.sin(norm_pos * 2 * np.pi) * 127 + 128).astype(np.uint8)
            colors[:, 1] = (np.sin(norm_pos * 2 * np.pi + 2) * 127 + 128).astype(np.uint8)
            colors[:, 2] = (np.sin(norm_pos * 2 * np.pi + 4) * 127 + 128).astype(np.uint8)
            
            self.leds[:] = colors
            frames.append(self.record_frame())
            offset += 10
            
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