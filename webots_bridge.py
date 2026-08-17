"""
Webots Python Controller Bridge
---------------------------------
This script runs INSIDE Webots. It replaces your autonomous_vehicle.c controller.
It captures the camera feed from the Webots car and sends it to your FastAPI backend,
then receives steering commands back from your Python AI (YOLO + Edge Tracker).

INSTRUCTIONS:
1. In Webots, go to Wizards -> New Robot Controller -> Python.
2. Name it "rocar_bridge".
3. Replace the generated code with this file.
4. Assign this controller to your vehicle in the Webots Scene Tree.
5. Make sure your FastAPI backend (api.py) is running on port 8000!
"""

from vehicle import Driver
import urllib.request
import json
import time

# --- Configuration ---
BACKEND_URL = "http://127.0.0.1:8000"
CAMERA_NAME = "camera"  # Change if your webots camera is named differently
CRUISING_SPEED = 20.0   # km/h
STEERING_ANGLE = 0.3    # Radians for sharp turns

# --- Initialization ---
driver = Driver()
timestep = int(driver.getBasicTimeStep())

camera = driver.getDevice(CAMERA_NAME)
if camera:
    camera.enable(timestep)
else:
    print("⚠️ WARNING: Could not find a camera named 'camera' on this vehicle!")

print("✅ Webots Bridge Initialized! Connecting to FastAPI backend...")

# Main loop
while driver.step() != -1:
    if camera:
        # 1. Grab frame from Webots camera
        camera_data = camera.getImage()
        width = camera.getWidth()
        height = camera.getHeight()
        
        # In Webots, getImage() returns BGRA format pixels. We need to send it to the backend.
        # Since we don't assume cv2/numpy are installed in the Webots Python env, 
        # we can just send the raw bytes, OR we can save it as JPEG if cv2 is available.
        # But wait! Webots camera has a handy saveImage() method to get a JPEG easily!
        
        temp_image_path = "temp_frame.jpg"
        camera.saveImage(temp_image_path, 80) # Save as JPEG quality 80
        
        # 2. Send frame to FastAPI Backend
        try:
            with open(temp_image_path, "rb") as f:
                img_bytes = f.read()
            
            req = urllib.request.Request(f"{BACKEND_URL}/webots/frame", data=img_bytes)
            req.add_header('Content-Type', 'application/octet-stream')
            urllib.request.urlopen(req, timeout=0.5)
        except Exception as e:
            print(f"Failed to send frame to backend: {e}")

    # 3. Get Steering Command from Backend
    try:
        response = urllib.request.urlopen(f"{BACKEND_URL}/webots/command", timeout=0.5)
        data = json.loads(response.read().decode())
        cmd = data.get("command", "stop")
        
        # 4. Map string commands to Webots Ackermann Steering
        if cmd == "forward":
            driver.setCruisingSpeed(CRUISING_SPEED)
            driver.setSteeringAngle(0.0)
        elif cmd == "left":
            driver.setCruisingSpeed(CRUISING_SPEED - 5)  # Slow down slightly for turns
            driver.setSteeringAngle(-STEERING_ANGLE)
        elif cmd == "right":
            driver.setCruisingSpeed(CRUISING_SPEED - 5)
            driver.setSteeringAngle(STEERING_ANGLE)
        elif cmd == "stop":
            driver.setCruisingSpeed(0.0)
            driver.setSteeringAngle(0.0)
            
    except Exception as e:
        print(f"Backend offline or unreachable: {e}")
        driver.setCruisingSpeed(0.0) # Stop for safety if disconnected
