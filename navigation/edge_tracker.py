"""
Universal Road Follower — Works on ANY forward-facing camera.
No calibration, no perspective transform, no fragile edge detection.

Algorithm:
  1. Sample two horizontal scan lines across the image
     - Near line (~70% down): for immediate steering
     - Far line  (~50% down): for anticipating curves ahead
  2. At each scan line, find the LEFT and RIGHT boundaries of the
     dark road surface (asphalt is darker than sidewalks/grass/buildings)
  3. Calculate the road center, then offset it left for edge-biased
     navigation (Indian left-hand traffic)
  4. Feed the error into a P-controller → output left/right/forward

This works in Webots AND on the physical bot because it relies on the
fundamental property that road = dark, surroundings = lighter.
"""

import cv2
import numpy as np


class EdgeTracker:
    def __init__(self):
        # --- Tuning Parameters ---
        # PRECAUTION: If the bot wobbles/snakes, LOWER Kp (e.g., 0.3).
        # If it reacts too slowly and drifts off, RAISE Kp (e.g., 0.8).
        self.Kp = 0.5

        # How far to offset from center toward the left edge.
        # 0.0 = hug the center, 0.3 = 30% toward the left boundary.
        # For Indian roads (left-hand traffic), keep 0.2–0.3.
        self.edge_bias = 0.25

        # Minimum number of "road" pixels in a scan line to trust the reading
        self.min_road_pixels = 15

        # Dead-zone: if error is within this fraction of frame width, go straight
        self.dead_zone = 0.05

        # Smoothing: blend current reading with previous to reduce jitter
        self.prev_center = None
        self.smooth_factor = 0.4  # 0 = no smoothing, 1 = full smoothing (laggy)

    # ------------------------------------------------------------------
    # Core: find road boundaries in a single horizontal scan line
    # ------------------------------------------------------------------
    def _scan_road(self, gray_row, threshold):
        """
        Given a 1D array of grayscale values for one row of pixels,
        find the leftmost and rightmost pixel that is darker than threshold.
        Returns (left_x, right_x) or None if road not found.
        """
        road_mask = gray_row < threshold
        road_indices = np.where(road_mask)[0]

        if len(road_indices) < self.min_road_pixels:
            return None

        # Take the largest continuous dark region (ignore small dark patches)
        # Simple approach: just use the widest span
        left = int(road_indices[0])
        right = int(road_indices[-1])

        # Sanity: road should be at least 10% of frame width
        if (right - left) < len(gray_row) * 0.10:
            return None

        return (left, right)

    # ------------------------------------------------------------------
    # Main pipeline — called every frame from api.py's yolo_loop
    # ------------------------------------------------------------------
    def process_frame(self, frame):
        """
        Analyze one camera frame. Returns:
          steering_cmd: "left", "right", or "forward"
          debug_msg:    human-readable status string
          annotated:    copy of frame with debug overlays drawn
        """
        height, width = frame.shape[:2]
        gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
        blur = cv2.GaussianBlur(gray, (7, 7), 0)

        # --- Dynamic threshold ---
        # Sample the middle third of the frame (where road usually is)
        mid_strip = blur[int(height * 0.5):int(height * 0.8),
                         int(width * 0.2):int(width * 0.8)]
        avg_brightness = np.mean(mid_strip)
        # Road pixels should be darker than ~85% of the average scene brightness
        threshold = avg_brightness * 0.85

        # --- Scan Line 1: NEAR (70% down) — immediate steering ---
        near_y = int(height * 0.70)
        near_row = blur[near_y, :]
        near_road = self._scan_road(near_row, threshold)

        # --- Scan Line 2: FAR (50% down) — curve anticipation ---
        far_y = int(height * 0.50)
        far_row = blur[far_y, :]
        far_road = self._scan_road(far_row, threshold)

        # --- Calculate target position ---
        steering_cmd = "forward"
        debug_msg = "No road detected"

        annotated = frame.copy()

        if near_road is not None:
            near_left, near_right = near_road
            near_center = (near_left + near_right) / 2.0
            road_width = near_right - near_left

            # Edge-biased target: shift left from center
            target_x = near_center - (road_width * self.edge_bias)

            # If we can also see the road further ahead, blend in curve info
            if far_road is not None:
                far_left, far_right = far_road
                far_center = (far_left + far_right) / 2.0
                far_width = far_right - far_left
                far_target = far_center - (far_width * self.edge_bias)
                # Blend: 60% near + 40% far for smooth curve anticipation
                target_x = target_x * 0.6 + far_target * 0.4

            # Smooth with previous frame to reduce jitter
            if self.prev_center is not None:
                target_x = (1 - self.smooth_factor) * target_x + self.smooth_factor * self.prev_center
            self.prev_center = target_x

            # Error: how far target is from camera center (normalized -1 to +1)
            cam_center = width / 2.0
            error = (target_x - cam_center) / cam_center

            # P-controller
            if error < -self.dead_zone:
                steering_cmd = "left"
                debug_msg = f"Road offset {error:+.2f} → Steer LEFT"
            elif error > self.dead_zone:
                steering_cmd = "right"
                debug_msg = f"Road offset {error:+.2f} → Steer RIGHT"
            else:
                steering_cmd = "forward"
                debug_msg = f"Road offset {error:+.2f} → STRAIGHT"

            # --- Debug overlays ---
            # Draw near scan line and road boundaries
            cv2.line(annotated, (near_left, near_y), (near_right, near_y), (0, 255, 0), 3)
            cv2.circle(annotated, (int(target_x), near_y), 8, (0, 0, 255), -1)  # Target dot
            cv2.circle(annotated, (int(cam_center), near_y), 8, (255, 0, 0), -1)  # Center dot

            # Draw far scan line if available
            if far_road is not None:
                cv2.line(annotated, (far_road[0], far_y), (far_road[1], far_y), (0, 200, 0), 2)
                cv2.circle(annotated, (int(far_target), far_y), 6, (0, 0, 200), -1)

            # Draw a line connecting target to center showing the "pull" direction
            cv2.arrowedLine(annotated, (int(cam_center), near_y + 30),
                            (int(target_x), near_y + 30), (0, 255, 255), 2)

        else:
            # Road not visible on near line — check far line only
            if far_road is not None:
                far_center = (far_road[0] + far_road[1]) / 2.0
                cam_center = width / 2.0
                error = (far_center - cam_center) / cam_center
                if error < -self.dead_zone * 2:
                    steering_cmd = "left"
                    debug_msg = f"Road ahead is LEFT ({error:+.2f}) → Steer LEFT"
                elif error > self.dead_zone * 2:
                    steering_cmd = "right"
                    debug_msg = f"Road ahead is RIGHT ({error:+.2f}) → Steer RIGHT"
                else:
                    steering_cmd = "forward"
                    debug_msg = "Road ahead → STRAIGHT"
            else:
                self.prev_center = None
                debug_msg = "No road detected → Creeping FORWARD"

        # Status text on frame
        color = {"left": (255, 100, 0), "right": (0, 100, 255), "forward": (0, 200, 0)}
        cv2.putText(annotated, debug_msg, (10, 30),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.6, color.get(steering_cmd, (255, 255, 255)), 2)

        return steering_cmd, debug_msg, annotated
