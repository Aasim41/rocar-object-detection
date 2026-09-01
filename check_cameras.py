import cv2

def test_cameras():
    print("Scanning for connected cameras...")
    available_cameras = []
    
    # Check the first 3 indices
    for i in range(3):
        cap = cv2.VideoCapture(i)
        if cap is None or not cap.isOpened():
            print(f"Index {i}: No camera found")
        else:
            ret, frame = cap.read()
            if ret:
                print(f"Index {i}: SUCCESS! (Camera is working)")
                available_cameras.append(i)
                # Show a preview window for 2 seconds
                cv2.imshow(f"Testing Camera Index {i}", frame)
                cv2.waitKey(2000) 
                cv2.destroyAllWindows()
            else:
                print(f"Index {i}: Found, but couldn't read frame")
        
        if cap is not None:
            cap.release()

    print("\n--- Summary ---")
    if not available_cameras:
        print("No cameras found at all!")
    else:
        print(f"Working camera indices: {available_cameras}")
        print("If EpocCam is index 1, start your backend using:")
        print('$env:CAMERA_SOURCE="1"; python api.py')

if __name__ == "__main__":
    test_cameras()

