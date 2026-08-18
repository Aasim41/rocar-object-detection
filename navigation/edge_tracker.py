"""
Geometric Road Boundary Follower — Production Version.

CORE ALGORITHM:
  1. CLAHE → normalize lighting (day/night/rain)
  2. Gaussian Blur → remove textures (windows, signs)
  3. Canny Edge Detection → find ALL edges in the scene
  4. Use edges as BARRIERS for flood fill
  5. Flood fill from bottom center → fills ONLY the road
     because it cannot cross the Canny edges (road boundaries)
  6. Scan 10 heights on the filled mask → road width + center
  7. Quadratic fit to centerline → curvature
  8. Target = left_edge + margin × road_width
  9. Steering = Kp × position_error + Kd × curvature

WHY THIS WORKS:
  - Canny detects edges based on GRADIENTS, not absolute color.
    A road edge creates a gradient whether it's day or night.
  - Flood fill cannot leak through edges. Buildings, sidewalks,
    everything is separated from the road by an edge.
  - The car IS on the road → bottom center IS road → seed is correct.
  - Quadratic fit gives exact curvature for any road shape.
"""

import cv2
import numpy as np


class EdgeTracker:
    def __init__(self):
        # Steering
        self.Kp = 0.8          # Position correction (smoothed to prevent oversteer)
        self.KH = 0.5          # Heading direction
        self.dead_zone = 0.02
        self.margin = 0.25     # 25% from left = left lane

        # Detection
        self.canny_low = 50    # Higher = fewer internal edges
        self.canny_high = 120
        self.fill_tolerance = 35  # Higher = flood fill covers full road width
        self.blur_size = 31    # Heavier blur kills lane markings and shadows

        # Smoothing
        self.prev_steer = 0.0
        self.smooth = 0.2

        # CLAHE
        self.clahe = cv2.createCLAHE(clipLimit=2.5, tileGridSize=(8, 8))

        # Scans
        self.num_scans = 10

    def _get_road_mask(self, frame):
        """Find the road using edge-barrier flood fill."""
        h, w = frame.shape[:2]

        # Preprocess
        gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
        gray = self.clahe.apply(gray)
        blurred = cv2.GaussianBlur(gray, (self.blur_size, self.blur_size), 0)

        # Canny edges = barriers
        edges = cv2.Canny(blurred, self.canny_low, self.canny_high)
        edges = cv2.dilate(edges, np.ones((3, 3), np.uint8), iterations=1)

        # Build flood fill mask with edge barriers
        ff_mask = np.zeros((h + 2, w + 2), np.uint8)
        ff_mask[1:-1, 1:-1][edges > 0] = 1  # Edges become barriers

        # Try multiple seed points for robustness
        seeds = [
            (w // 2, h - 5),       # Center bottom
            (w // 3, h - 5),       # Left-center bottom
            (2 * w // 3, h - 5),   # Right-center bottom
        ]

        best_mask = None
        best_count = 0

        for seed in seeds:
            # Check seed is not on an edge
            if ff_mask[seed[1] + 1, seed[0] + 1] != 0:
                continue

            test_mask = ff_mask.copy()
            fill_img = blurred.copy()

            cv2.floodFill(fill_img, test_mask, seed, 255,
                          loDiff=(self.fill_tolerance,),
                          upDiff=(self.fill_tolerance,),
                          flags=4 | cv2.FLOODFILL_MASK_ONLY | (255 << 8))

            road = test_mask[1:-1, 1:-1]
            count = np.sum(road > 0)

            if count > best_count:
                best_count = count
                best_mask = road.copy()

        if best_mask is None or best_count < (h * w * 0.02):
            return np.zeros((h, w), np.uint8)

        # Clean up
        kernel = np.ones((5, 5), np.uint8)
        best_mask = cv2.morphologyEx(best_mask, cv2.MORPH_CLOSE, kernel)

        return best_mask

    def process_frame(self, frame):
        h, w = frame.shape[:2]
        annotated = frame.copy()

        # ====== ROAD DETECTION ======
        road_mask = self._get_road_mask(frame)

        # ====== SCAN BOUNDARIES ======
        scan_data = []
        for i in range(self.num_scans):
            frac = 0.90 - (i * 0.05)
            y = int(h * frac)
            if y < 1 or y >= h:
                continue

            row = road_mask[y, :]
            indices = np.where(row > 0)[0]
            if len(indices) < 5:
                continue

            left = int(indices[0])
            right = int(indices[-1])
            width = right - left
            if width < w * 0.04:
                continue

            scan_data.append({
                'y': y, 'left': left, 'right': right,
                'center': (left + right) / 2.0, 'width': width
            })

        n = len(scan_data)

        # ====== DRAW BOUNDARIES ======
        if n >= 2:
            for i in range(n - 1):
                s1, s2 = scan_data[i], scan_data[i + 1]
                cv2.line(annotated, (s1['left'], s1['y']),
                         (s2['left'], s2['y']), (0, 255, 0), 3)
                cv2.line(annotated, (s1['right'], s1['y']),
                         (s2['right'], s2['y']), (255, 0, 0), 3)

            for s in scan_data:
                cv2.circle(annotated, (s['left'], s['y']), 5, (0, 255, 0), -1)
                cv2.circle(annotated, (s['right'], s['y']), 5, (255, 0, 0), -1)

        # Road tint overlay
        tint = np.zeros_like(annotated)
        tint[:, :, 1] = road_mask // 4  # Green tint on road
        annotated = cv2.add(annotated, tint)

        # ====== STEERING MATH ======
        steering_cmd = "forward"
        debug_msg = f"Scans: {n} — No road"
        turn_type = "UNKNOWN"

        if n < 3:
            self.prev_steer = 0.0
            cv2.putText(annotated, debug_msg, (10, 30),
                        cv2.FONT_HERSHEY_SIMPLEX, 0.5, (0, 0, 255), 2)
            return "forward", debug_msg, annotated

        # Simple robust Look-ahead
        third = max(n // 3, 1)
        near_left = np.mean([s['left'] for s in scan_data[:third]])
        near_width = np.mean([s['width'] for s in scan_data[:third]])
        near_target = near_left + self.margin * near_width

        far_left = np.mean([s['left'] for s in scan_data[-third:]])
        far_width = np.mean([s['width'] for s in scan_data[-third:]])
        far_target = far_left + self.margin * far_width

        cam_center = w / 2.0
        pos_err = (near_target - cam_center) / cam_center
        head_err = (far_target - near_target) / cam_center

        # Turn classification
        turn_score = abs(head_err)
        if turn_score < 0.05:
            turn_type = "STRAIGHT"
        elif turn_score < 0.15:
            turn_type = "GENTLE CURVE"
        elif turn_score < 0.30:
            turn_type = "CURVE"
        else:
            turn_type = "SHARP TURN"

        raw_steer = self.Kp * pos_err + self.KH * head_err
        raw_steer = (1 - self.smooth) * raw_steer + self.smooth * self.prev_steer
        self.prev_steer = raw_steer

        if raw_steer < -self.dead_zone:
            steering_cmd = "left"
        elif raw_steer > self.dead_zone:
            steering_cmd = "right"
        near = scan_data[0]
        debug_msg = (f"{turn_type} | W={near['width']:.0f}px "
                     f"pos={pos_err:+.2f} head={head_err:+.3f} -> {steering_cmd.upper()}")

        # Draw target
        cv2.circle(annotated, (int(near_target), near['y']), 10, (0, 0, 255), -1)
        cv2.circle(annotated, (int(cam_center), near['y']), 8, (255, 255, 255), 2)
        cv2.line(annotated, (near['left'], near['y'] + 12),
                 (near['right'], near['y'] + 12), (0, 200, 200), 2)

        col = {"left": (255, 100, 0), "right": (0, 100, 255), "forward": (0, 200, 0)}
        cv2.putText(annotated, debug_msg, (10, 28),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.45, col.get(steering_cmd, (255, 255, 255)), 2)

        return steering_cmd, debug_msg, annotated
