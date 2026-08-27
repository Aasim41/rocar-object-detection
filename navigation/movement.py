from ultralytics import YOLO
model = YOLO("yolov8n.pt")
MIN_CONFIDENCE = 0.50
def movement(frame):
    if frame is None:
        return "STOP"
    frame_width = frame.shape[1]
    path_left = frame_width * 0.25
    path_right = frame_width * 0.75
    results = model(frame, verbose=False)
    for result in results:
        for box in result.boxes:
            confidence = float(box.conf[0])
            if confidence < MIN_CONFIDENCE:
                continue
            class_id = int(box.cls[0])
            class_name = model.names[class_id]
            x1, y1, x2, y2 = map(
                int,
                box.xyxy[0].tolist()
            )
            object_center_x = (x1 + x2) / 2
            print(
                f"Object: {class_name}, "
                f"Confidence: {confidence:.2f}, "
                f"Center X: {object_center_x}"
            )
            if path_left <= object_center_x <= path_right:
                print(f"{class_name} detected in pathway")
                return "STOP"
    return "MOVE"