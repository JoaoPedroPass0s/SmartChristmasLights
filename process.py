import cv2
import numpy as np
import os
import re

def detect_brightest_spot(image_path):
    # Read the image
    img = cv2.imread(image_path)
    if img is None:
        raise ValueError("Image not found or unable to read")

    # Convert the image to grayscale
    gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)

    brightness = 255
    
    while brightness > 0:
        # Threshold the grayscale image to create a binary mask of bright areas
        _, mask = cv2.threshold(gray, brightness, 255, cv2.THRESH_BINARY)

        # Find contours in the mask
        contours, _ = cv2.findContours(mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)

        if contours:
            # Find the largest bright spot
            largest_contour = max(contours, key=cv2.contourArea)

            # Get the center of the contour (brightest spot position)
            M = cv2.moments(largest_contour)
            if M['m00'] != 0:
                cx = int(M['m10'] / M['m00'])
                cy = int(M['m01'] / M['m00'])
                return (cx, cy)  # Return the position of the brightest spot

        brightness -= 1

    return None

def generate_led_map(led_positions, img_shape):
    # Create a blank white image with the same size as the input image
    led_map = np.ones((img_shape[0], img_shape[1], 3), dtype=np.uint8) * 255  # White background
    
    # Draw the positions of the LEDs (mark with small red circles and index numbers)
    for idx, (cx, cy) in enumerate(led_positions, start=1):
        cv2.circle(led_map, (cx, cy), 5, (0, 0, 255), -1)  # Red circle for each LED
        cv2.putText(led_map, str(idx), (cx + 10, cy), cv2.FONT_HERSHEY_SIMPLEX, 0.5, (0, 0, 0), 1)  # Black index number
    
    return led_map

def save_position_data(led_positions, output_file):
    with open(output_file, 'w') as file:
        for idx, (cx, cy) in enumerate(led_positions, start=1):
            file.write(f"({idx},{cx},{cy})")

def sort_numerical_filenames(file_list):
    # Use regex to extract numeric parts from filenames for sorting
    return sorted(file_list, key=lambda x: int(re.search(r'\d+', x).group()) if re.search(r'\d+', x) else float('inf'))

def process_images_in_folder(folder_path):
    all_led_positions = []
    
    # List all files in the folder and sort them numerically
    file_list = [f for f in os.listdir(folder_path) if f.lower().endswith(('.png', '.jpg', '.jpeg'))]
    sorted_files = sort_numerical_filenames(file_list)
    
    # Process each file in numerical order
    for idx, filename in enumerate(sorted_files, start=1):
        image_path = os.path.join(folder_path, filename)
        led_position = detect_brightest_spot(image_path)
        
        if led_position:
            print(f"Found brightest spot in {filename} at position: {led_position}")
            all_led_positions.append(led_position)
        else:
            print(f"No bright spot found in {filename}")
    
    return all_led_positions

# Example usage
folder_path = "photos"  # Change this to the folder containing your images
led_positions = process_images_in_folder(folder_path)

if led_positions:
    # Get the size of the first image to create a map with the same dimensions
    sample_image = cv2.imread(os.path.join(folder_path, os.listdir(folder_path)[0]))
    img_shape = sample_image.shape  # (height, width, channels)
    
    # Generate the LED map
    led_map = generate_led_map(led_positions, img_shape)

    # Save the LED positions to a file
    save_position_data(led_positions, "led_positions.txt")
    
    # Save the LED map to a file
    cv2.imwrite("led_map.png", led_map)
    print("LED map saved as led_map.png")
else:
    print("No bright spots detected in the images.")


