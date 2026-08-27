import cv2
import numpy as np


class LaneFollower:
    """
    Adaptive Road Surface Detector + PD Steering Controller.

    Works on ANY road — with or without lane markings.
    No camera calibration, no perspective warp, no training data.

    Algorithm:
      1. Sample the road color from the bottom-center of the frame
         (the cart is *on* the road, so those pixels are guaranteed road).
      2. Convert to CIELAB color space (robust to shadows & brightness).
      3. Build a binary mask: pixels within a color-distance threshold
         of the sampled road color = "drivable surface."
      4. Scan the mask at multiple heights to find left/right road edges.
      5. Compute cross-track error + heading error from those edges.
      6. PD controller outputs a smooth steering angle.
    """

    def __init__(self):
        # ── Road color sampling ──────────────────────────────────
        self.sample_w = 100          # width of sampling strip (px)
        self.sample_h = 25           # height of sampling strip (px)
        self.color_thresh_day = 38   # max LAB distance in daylight
        self.color_thresh_night = 52 # max LAB distance at night (more forgiving)
        self.color_thresh = 38       # active threshold (auto-adjusted)

        # ── Night vision (CLAHE) ─────────────────────────────────
        self.clahe = cv2.createCLAHE(clipLimit=3.0, tileGridSize=(8, 8))
        self.low_light_L_thresh = 90 # if avg L < this, engage night mode

        # ── Region of interest ───────────────────────────────────
        self.roi_top_pct = 0.45      # ignore the top 45 % (sky / buildings)

        # ── Morphological cleanup ────────────────────────────────
        self.close_k = 19            # closing kernel — fills small holes in road
        self.open_k = 7              # opening kernel — removes isolated noise

        # ── Boundary scanning ────────────────────────────────────
        self.n_scans = 8             # number of horizontal scan lines
        self.min_road_w_pct = 0.08   # minimum road width as fraction of frame

        # ── PD steering ──────────────────────────────────────────
        self.Kp = 0.70               # proportional gain  (cross-track error)
        self.Kd = 0.15               # derivative gain     (error rate)
        self.Kh = 0.30               # heading-error gain  (near vs far offset)
        self.dead_zone = 0.04        # steer values below this → "forward"
        self.prev_err = 0.0

        # ── Exponential-moving-average smoothing ─────────────────
        self.alpha = 0.40            # 0 = all old, 1 = all new
        self.prev_steer = 0.0

        # ── Fallback safety ──────────────────────────────────────
        self.no_road_frames = 0      # consecutive frames with no road detected
        self.max_lost = 15           # after this many → declare "lost"

    # ─────────────────────────────────────────────────────────────
    #  PUBLIC API  (same signature the rest of api.py expects)
    # ─────────────────────────────────────────────────────────────
    def process_frame(self, frame):
        """
        Parameters
        ----------
        frame : np.ndarray  BGR image from the camera.

        Returns
        -------
        steering_cmd : str   "left" | "right" | "forward"
        debug_msg    : str   human-readable diagnostics
        annotated    : np.ndarray  frame with debug overlays drawn
        raw_steer    : float  continuous steering value (–1 … +1)
        """
        h, w = frame.shape[:2]
        roi_y = int(h * self.roi_top_pct)

        # 1 ── CLAHE night-vision preprocessing ────────────────────
        #      Detect low light → boost contrast before anything else
        lab_raw = cv2.cvtColor(frame, cv2.COLOR_BGR2LAB)
        avg_L = float(np.mean(lab_raw[:, :, 0]))
        is_night = avg_L < self.low_light_L_thresh

        if is_night:
            # Apply CLAHE to the L (brightness) channel only
            l_ch, a_ch, b_ch = cv2.split(lab_raw)
            l_ch = self.clahe.apply(l_ch)
            lab = cv2.merge([l_ch, a_ch, b_ch])
            # Reconstruct a brighter BGR frame for the annotated output
            enhanced = cv2.cvtColor(lab, cv2.COLOR_LAB2BGR)
            annotated = enhanced.copy()
            # Widen color threshold — night images are noisier
            self.color_thresh = self.color_thresh_night
        else:
            lab = lab_raw
            annotated = frame.copy()
            self.color_thresh = self.color_thresh_day

        # 2 ── Sample road color from bottom-center ────────────────
        road_mean = self._sample_road_color(lab, h, w)

        # Draw the sampling rectangle (thin green box at bottom)
        sx1 = max(0, w // 2 - self.sample_w // 2)
        sx2 = min(w, w // 2 + self.sample_w // 2)
        sy1 = max(0, h - self.sample_h)
        cv2.rectangle(annotated, (sx1, sy1), (sx2, h), (0, 255, 0), 2)

        # 3 ── Build road mask for the ROI ─────────────────────────
        road_mask = self._build_road_mask(lab[roi_y:], road_mean)

        # 4 ── Scan for left / right road edges ────────────────────
        left_xs, right_xs, scan_abs_ys = self._scan_boundaries(
            road_mask, w, roi_y, h
        )
        valid = len(left_xs)

        # Draw scan points on the annotated frame
        for lx, rx, ay in zip(left_xs, right_xs, scan_abs_ys):
            cv2.circle(annotated, (lx, ay), 5, (255, 0, 0), -1)    # left  = blue
            cv2.circle(annotated, (rx, ay), 5, (0, 0, 255), -1)    # right = red
            cx = (lx + rx) // 2
            cv2.circle(annotated, (cx, ay), 4, (0, 255, 255), -1)  # center = yellow

        # 5 ── Compute steering ────────────────────────────────────
        if valid >= 3:
            raw_steer, steering_cmd, debug_msg = self._compute_steering(
                left_xs, right_xs, w
            )
            self.no_road_frames = 0

            # Draw road center guideline
            weights = np.linspace(0.5, 1.5, valid)
            avg_center = int(np.average(
                [(l + r) / 2 for l, r in zip(left_xs, right_xs)],
                weights=weights,
            ))
            cv2.line(annotated, (avg_center, roi_y), (avg_center, h),
                     (0, 255, 255), 2)
            cv2.line(annotated, (w // 2, roi_y), (w // 2, h),
                     (255, 255, 255), 1)
        else:
            raw_steer, steering_cmd, debug_msg = self._fallback()

        # 6 ── Draw semi-transparent green overlay of detected road ─
        overlay = annotated[roi_y:].copy()
        green = np.zeros_like(overlay)
        green[:, :, 1] = road_mask
        annotated[roi_y:] = cv2.addWeighted(overlay, 0.75, green, 0.25, 0)

        # 7 ── Draw a small road-mask thumbnail in the top-right ────
        thumb_h = h // 5
        thumb_w = w // 5
        thumb = cv2.resize(road_mask, (thumb_w, thumb_h))
        thumb_bgr = cv2.cvtColor(thumb, cv2.COLOR_GRAY2BGR)
        annotated[5:5 + thumb_h, w - thumb_w - 5:w - 5] = thumb_bgr

        # 8 ── HUD text ────────────────────────────────────────────
        col_map = {
            "left": (255, 100, 0),
            "right": (0, 100, 255),
            "forward": (0, 200, 0),
        }
        cv2.putText(
            annotated,
            f"{steering_cmd.upper()} | {debug_msg}",
            (10, 28),
            cv2.FONT_HERSHEY_SIMPLEX,
            0.50,
            col_map.get(steering_cmd, (255, 255, 255)),
            2,
        )

        return steering_cmd, debug_msg, annotated, float(raw_steer)

    # ─────────────────────────────────────────────────────────────
    #  PRIVATE HELPERS
    # ─────────────────────────────────────────────────────────────

    def _sample_road_color(self, lab, h, w):
        """Return the mean LAB color of the road directly under the cart."""
        cx = w // 2
        sx1 = max(0, cx - self.sample_w // 2)
        sx2 = min(w, cx + self.sample_w // 2)
        sy1 = max(0, h - self.sample_h)
        sample = lab[sy1:h, sx1:sx2]
        return np.mean(sample.reshape(-1, 3), axis=0).astype(np.float32)

    def _build_road_mask(self, roi_lab, road_mean):
        """
        Create a binary mask where white = road, black = non-road.
        Uses weighted CIELAB Euclidean distance so brightness changes
        (shadows) matter less than actual colour shifts.
        """
        diff = roi_lab.astype(np.float32) - road_mean
        # Down-weight L (brightness), full weight on A and B (chrominance)
        diff[:, :, 0] *= 0.5
        dist = np.sqrt(np.sum(diff ** 2, axis=2))

        mask = (dist < self.color_thresh).astype(np.uint8) * 255

        # Morphological cleanup
        k_close = cv2.getStructuringElement(
            cv2.MORPH_ELLIPSE, (self.close_k, self.close_k)
        )
        k_open = cv2.getStructuringElement(
            cv2.MORPH_ELLIPSE, (self.open_k, self.open_k)
        )
        mask = cv2.morphologyEx(mask, cv2.MORPH_CLOSE, k_close)
        mask = cv2.morphologyEx(mask, cv2.MORPH_OPEN, k_open)
        return mask

    def _scan_boundaries(self, mask, w, roi_y, h):
        """Scan the road mask at several heights → lists of left/right X."""
        roi_h = mask.shape[0]
        scan_fracs = np.linspace(0.25, 0.95, self.n_scans)
        min_w = int(w * self.min_road_w_pct)

        left_xs, right_xs, abs_ys = [], [], []
        for frac in scan_fracs:
            sy = int(roi_h * frac)
            if sy >= roi_h:
                continue
            row = mask[sy, :]
            road_px = np.where(row > 0)[0]
            if len(road_px) > min_w:
                left_xs.append(int(road_px[0]))
                right_xs.append(int(road_px[-1]))
                abs_ys.append(sy + roi_y)
        return left_xs, right_xs, abs_ys

    def _compute_steering(self, left_xs, right_xs, w):
        """PD controller using cross-track + heading errors."""
        n = len(left_xs)
        weights = np.linspace(0.5, 1.5, n)
        centers = [(l + r) / 2.0 for l, r in zip(left_xs, right_xs)]
        avg_center = float(np.average(centers, weights=weights))
        cam_center = w / 2.0

        # Cross-track error (positive = road center is to the right)
        cte = (avg_center - cam_center) / cam_center

        # Heading error (far road center vs near road center)
        heading_err = 0.0
        if n >= 4:
            far_c = (left_xs[0] + right_xs[0]) / 2.0
            near_c = (left_xs[-1] + right_xs[-1]) / 2.0
            heading_err = (far_c - near_c) / cam_center

        error = cte + self.Kh * heading_err

        # PD
        d_err = error - self.prev_err
        self.prev_err = error
        raw = self.Kp * error + self.Kd * d_err

        # EMA smoothing
        raw = self.alpha * raw + (1.0 - self.alpha) * self.prev_steer
        self.prev_steer = raw

        # Quantise to command
        if raw < -self.dead_zone:
            cmd = "left"
        elif raw > self.dead_zone:
            cmd = "right"
        else:
            cmd = "forward"

        msg = f"CTE={cte:+.2f} HD={heading_err:+.2f} STR={raw:+.2f}"
        return raw, cmd, msg

    def _fallback(self):
        """Called when no road surface is detected."""
        self.no_road_frames += 1
        if self.no_road_frames > self.max_lost:
            self.prev_steer = 0.0
            self.prev_err = 0.0
            return 0.0, "forward", "ROAD LOST — cruising straight"

        # Decay last-known steering for a few frames
        raw = self.prev_steer * 0.90
        self.prev_steer = raw
        if raw < -self.dead_zone:
            cmd = "left"
        elif raw > self.dead_zone:
            cmd = "right"
        else:
            cmd = "forward"
        return raw, cmd, f"Road fading ({self.no_road_frames}/{self.max_lost})"
