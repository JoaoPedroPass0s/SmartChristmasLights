import re

def process_coordinates(input_file, output_file):
    # Read and parse the input data
    with open(input_file, 'r') as file:
        data = file.read()

    # Extract tuples using regex: (index, Xcord, Ycord)
    matches = re.findall(r'\((\d+),\s*(-?\d+),\s*(-?\d+)\)', data)
    coordinates = [(int(idx), int(x), int(y)) for idx, x, y in matches]

    # Sort by index to ensure order
    coordinates.sort(key=lambda x: x[0])

    # Fill in missing indexes
    filled_coordinates = []
    for i in range(len(coordinates) - 1):
        current = coordinates[i]
        next_ = coordinates[i + 1]

        # Add the current coordinate
        filled_coordinates.append(current)

        # Check for missing indexes
        if next_[0] - current[0] > 1:
            num_missing = next_[0] - current[0] - 1
            for j in range(1, num_missing + 1):
                new_index = current[0] + j
                # Linear interpolation for X and Y coordinates
                new_x = current[1] + (next_[1] - current[1]) * j / (num_missing + 1)
                new_y = current[2] + (next_[2] - current[2]) * j / (num_missing + 1)
                filled_coordinates.append((new_index, round(new_x), round(new_y)))

    # Add the last coordinate
    filled_coordinates.append(coordinates[-1])

    # Write the output to a file
    with open(output_file, 'w') as file:
        file.write("{" + ",".join(f"{{{x},{y}}}" for _, x, y in filled_coordinates) + "}")

    print(f"Processed data has been saved to {output_file}")

# Example usage
input_file = "led_positions.txt"  # Replace with your input file name
output_file = "led_positions_processed.txt"  # Replace with your desired output file name
process_coordinates(input_file, output_file)
