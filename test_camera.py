import cv2
from navigation.movement import movement

cap = cv2.VideoCapture(0)

if not cap.isOpened():
    print("Camera open nahi hua")
    exit()

while True:

    success, frame = cap.read()

    if not success:
        print("Frame nahi mila")
        break

    command = movement(frame)

    print("COMMAND:", command)

    # Webcam screen par dikhane ke liye
    cv2.imshow("Vehicle Camera Test", frame)

    # Q press karoge toh camera band
    if cv2.waitKey(1) & 0xFF == ord("q"):
        break

cap.release()
cv2.destroyAllWindows()