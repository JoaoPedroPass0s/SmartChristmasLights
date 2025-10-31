import serial
import cv2

# Configure the serial port
SERIAL_PORT = "COM7"  # Replace with your actual COM port (on Windows)
BAUD_RATE = 9600

# Initialize camera
camera = cv2.VideoCapture(0)  # Use the default camera (change index for multiple cameras)

def take_photo(count):
    # Capture an image
    ret, frame = camera.read()
    if ret:
        filename = f"photos/{count}.jpg"
        cv2.imwrite(filename, frame)
        print(f"Photo saved: {filename}")

def main():
    try:
        print("Initializing camera...")

    
        
        # Open the serial connection
        while True:
            try:
                ser = serial.Serial(SERIAL_PORT, BAUD_RATE, timeout=1)
                break
            except serial.SerialException:
                print("Serial port not available, retrying...")
        print("Listening for serial messages...")

        photo_count = 0
        while True:
            if ser.in_waiting > 0:
                message = ser.readline().decode('utf-8').strip()
                if message == "LED Changed":
                    print("Trigger received, taking photo...")
                    photo_count += 1
                    take_photo(photo_count)
    except KeyboardInterrupt:
        print("Exiting...")
    finally:
        # Release resources
        camera.release()
        cv2.destroyAllWindows()
        if ser.is_open:
            ser.close()

if __name__ == "__main__":
    main()
