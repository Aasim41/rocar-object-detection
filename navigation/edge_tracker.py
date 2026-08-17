"""
Road Boundary Follower — All Conditions, All Road Shapes.

Works at dawn, noon, dusk, night, rain, overcast.
Handles straights, curves, sharp turns, blind curves, cuts.

THREE independent road detection methods vote together:
  1. ADAPTIVE COLOR MATCH — learns road color from bottom of frame
  2. HSV SATURATION — roads are gray (low saturation), surroundings are colorful
  3. TEXTURE SMOOTHNESS — road surface is uniform, boundaries have sharp gradients

A pixel is "road" if at least 2 of 3 methods agree.

Steering uses Position + Heading:
  POSITION keeps the car on the road.
  HEADING anticipates curves before reaching them.

Preprocessing: CLAHE histogram equalization normalizes lighting so the
algorithm sees the same contrast whether it's noon or midnight.
"""

import cv2
import numpy as np


class EdgeTracker:
    def __init__(self):
        # --- Steering ---
        self.Kp_position = 0.4
        self.Kp_heading  = 0.6
        self.dead_zone   = 0.03
        self.num_scans   = 15

        # --- Detection thresholds ---
        self.color_tolerance = 55     # Color distance for method 1
        self.sat_threshold   = 60     # Max saturation for "road" (method 2)
        self.grad_threshold  = 25     # Max gradient for "smooth" (method 3)

        # --- Smoothing ---
        self.prev_steer = 0.0
        self.smooth = 0.3

        # --- CLAHE for lighting normalization ---
        self.clahe = cv2.createCLAHE(clipLimit=2.0, tileGridSize=(8, 8))

    def _preprocess(self, frame):
        """Normalize lighting with CLAHE so detection works day and night."""
        lab = cv2.cvtColor(frame, cv2.COLOR_BGR2LAB)
        l, a, b = cv2.split(lab)
        l = self.clahe.apply(l)
        lab = cv2.merge([l, a, b])
        return cv2.cvtColor(lab, cv2.COLOR_LAB2BGR)

    def _sample_road_color(self, frame):
        """Learn road color from bottom-center of frame."""
        h, w = frame.shape[:2]
        strip = frame[int(h * 0.90):h, int(w * 0.20):int(w * 0.80)]
        return np.mean(strip.reshape(-1, 3), axis=0).astype(np.float32)

    def _detect_road_row(self, bgr_row, hsv_row, gray_row, road_color):
        """
        Multi-method road detection for one horizontal scan line.
        Returns boolean mask: True = road pixel.
        """
        w = len(gray_row)

        # Method 1: Adaptive color match
        diff = np.abs(bgr_row.astype(np.float32) - road_color)
        color_dist = np.sqrt(np.sum(diff ** 2, axis=1))
        m1_color = color_dist < self.color_tolerance

        # Method 2: HSV saturation — road is gray (low saturation)
        m2_sat = hsv_row[:, 1] < self.sat_threshold

        # Method 3: Texture smoothness — road interior is smooth, edges have gradients
        grad = np.abs(np.diff(gray_row.astype(np.float32), prepend=gray_row[0].astype(np.float32)))
        # Smooth the gradient to avoid single-pixel noise
        if len(grad) > 5:
            kernel = np.ones(5) / 5.0
            grad = np.convolve(grad, kernel, mode='same')
        m3_smooth = grad < self.grad_threshold

        # VOTE: pixel is road if at least 2 of 3 agree
        votes = m1_color.astype(np.int8) + m2_sat.astype(np.int8) + m3_smooth.astype(np.int8)
        return votes >= 2

    def _find_boundaries(self, road_mask):
        """Find the widest continuous road segment in a boolean mask."""
        indices = np.where(road_mask)[0]
        if len(indices) < 8:
            return None

        gaps = np.diff(indices)
        big_gaps = np.where(gaps > 20)[0]

        if len(big_gaps) == 0:
            left, right = int(indices[0]), int(indices[-1])
        else:
            segments = []
            start = 0
            for g in big_gaps:
                segments.append((indices[start], indices[g]))
                start = g + 1
            segments.append((indices[start], indices[-1]))
            widest = max(segments, key=lambda s: s[1] - s[0])
            left, right = int(widest[0]), int(widest[1])

        if (right - left) < 8:
            return None
        return (left, right)

    def process_frame(self, frame):
        h, w = frame.shape[:2]

        # -------------------------------------------------------
        # PREPROCESS: normalize lighting
        # -------------------------------------------------------
        processed = self._preprocess(frame)
        hsv = cv2.cvtColor(processed, cv2.COLOR_BGR2HSV)
        gray = cv2.cvtColor(processed, cv2.COLOR_BGR2GRAY)
        road_color = self._sample_road_color(processed)

        annotated = frame.copy()

        # -------------------------------------------------------
        # SCAN: collect boundary points
        # -------------------------------------------------------
        left_points = []
        right_points = []

        for i in range(self.num_scans):
            frac = 0.88 - (i * 0.03)
            scan_y = int(h * frac)
            if scan_y < 1 or scan_y >= h:
                continue

            road_mask = self._detect_road_row(
                processed[scan_y, :],
                hsv[scan_y, :],
                gray[scan_y, :],
                road_color
            )
            bounds = self._find_boundaries(road_mask)
            if bounds is not None:
                left_points.append((bounds[0], scan_y))
                right_points.append((bounds[1], scan_y))

        # -------------------------------------------------------
        # DRAW: render boundaries
        # -------------------------------------------------------
        if len(left_points) >= 2:
            for i in range(len(left_points) - 1):
                cv2.line(annotated, left_points[i], left_points[i + 1], (0, 255, 0), 3)
                cv2.line(annotated, right_points[i], right_points[i + 1], (255, 0, 0), 3)
            for pt in left_points:
                cv2.circle(annotated, pt, 4, (0, 255, 0), -1)
            for pt in right_points:
                cv2.circle(annotated, pt, 4, (255, 0, 0), -1)

        # -------------------------------------------------------
        # STEER: Position + Heading
        # -------------------------------------------------------
        steering_cmd = "forward"
        debug_msg = "No road found"
        n = len(left_points)

        if n >= 6:
            cam_center = w / 2.0
            third = max(n // 3, 2)

            # NEAR (where we are), FAR (where road is going)
            near_lefts  = [p[0] for p in left_points[:third]]
            near_rights = [p[0] for p in right_points[:third]]
            far_lefts   = [p[0] for p in left_points[-third:]]
            far_rights  = [p[0] for p in right_points[-third:]]

            near_center = (np.mean(near_lefts) + np.mean(near_rights)) / 2.0
            far_center  = (np.mean(far_lefts) + np.mean(far_rights)) / 2.0

            # Position error
            position_err = (near_center - cam_center) / cam_center

            # Heading error (curve anticipation)
            heading_err = (far_center - near_center) / cam_center

            # Curvature estimate: how different is far from near?
            curvature = abs(heading_err)

            # Combined signal
            raw_steer = (self.Kp_position * position_err) + (self.Kp_heading * heading_err)
            raw_steer = (1 - self.smooth) * raw_steer + self.smooth * self.prev_steer
            self.prev_steer = raw_steer

            if raw_steer < -self.dead_zone:
                steering_cmd = "left"
            elif raw_steer > self.dead_zone:
                steering_cmd = "right"
            else:
                steering_cmd = "forward"

            debug_msg = (f"pos={position_err:+.2f} head={heading_err:+.2f} "
                         f"curve={curvature:.2f} -> {steering_cmd.upper()}")

            # Overlays
            near_y = left_points[third][1]
            far_y = left_points[-third][1]
            cv2.circle(annotated, (int(near_center), near_y), 8, (0, 255, 255), -1)
            cv2.circle(annotated, (int(cam_center), near_y), 8, (200, 200, 200), -1)
            cv2.arrowedLine(annotated, (int(near_center), near_y),
                            (int(far_center), far_y), (0, 255, 255), 2, tipLength=0.3)

        elif n >= 3:
            cam_center = w / 2.0
            road_center = (np.mean([p[0] for p in left_points]) +
                           np.mean([p[0] for p in right_points])) / 2.0
            err = (road_center - cam_center) / cam_center
            raw_steer = self.Kp_position * err
            raw_steer = (1 - self.smooth) * raw_steer + self.smooth * self.prev_steer
            self.prev_steer = raw_steer

            if raw_steer < -self.dead_zone:
                steering_cmd = "left"
            elif raw_steer > self.dead_zone:
                steering_cmd = "right"
            debug_msg = f"Partial ({n} pts) err={err:+.2f} -> {steering_cmd.upper()}"
        else:
            self.prev_steer = 0.0

        col = {"left": (255, 100, 0), "right": (0, 100, 255), "forward": (0, 200, 0)}
        cv2.putText(annotated, debug_msg, (10, 30),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.5, col.get(steering_cmd, (255, 255, 255)), 2)
        cv2.putText(annotated, f"Boundaries: {n}/{self.num_scans}", (10, h - 15),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.45, (200, 200, 200), 1)

        return steering_cmd, debug_msg, annotated
