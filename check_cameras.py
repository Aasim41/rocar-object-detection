import cv2
import sys
import numpy as np

def test_cameras():
    print("Scanning for connected cameras... (This may take a moment per camera)")
    available_cameras = []
    
    max_index = int(sys.argv[1]) if len(sys.argv) > 1 else 5
    
    # Check the indices
    for i in range(max_index):
        # Open with DSHOW to match typical Windows deployment
        cap = cv2.VideoCapture(i, cv2.CAP_DSHOW)
        if cap is None or not cap.isOpened():
            print(f"Index {i}: No camera found")
        else:
            ret, frame = cap.read()
            if ret and frame is not None and frame.mean() > 5:
                print(f"Index {i}: SUCCESS! (Press ANY KEY in the video window to continue...)")
                available_cameras.append(i)
                try:
                    # Show a preview window until the user hits a key
                    cv2.imshow(f"Testing Camera Index {i}", frame)
                    cv2.waitKey(0) 
                finally:
                    cv2.destroyAllWindows()
            else:
                if not ret:
                    print(f"Index {i}: Found, but couldn't read frame")
                else:
                    print(f"Index {i}: Found, but returned a blank/black frame (virtual camera?)")
        
        if cap is not None:
            cap.release()

    print("\n--- Summary ---")
    if not available_cameras:
        print("No cameras found at all!")
    else:
        print(f"Working camera indices: {available_cameras}")
        print("To start your backend using one of these cameras, run:")
        for idx in available_cameras:
            print(f'  $env:CAMERA_SOURCE="{idx}"; python api.py')

if __name__ == "__main__":
    test_cameras()

