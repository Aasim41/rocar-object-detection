import cv2
import numpy as np
from collections import deque


class LaneFollower:
    """
    Adaptive Road Surface Detector + PD Steering Controller  v3.1

    Works on ANY road — with or without lane markings.
    No camera calibration, no perspective warp, no training data.

    Pipeline:
      1. Night vision (bilateral denoise → gamma → dual CLAHE)
      2. Multi-point road color sampling (3 strips, median, EMA)
      3. Road mask (color distance with shadow recovery + texture gate)
      4. Road marking bridge (speed bumps / zebra crossings)
      5. Temporal mask blending (frame-to-frame stability)
      6. Boundary scanning (14 horizontal scan lines)
      7. Intersection detection (wide road → GPS override)
      8. PD steering with wall safety margin
    """

    def __init__(self):
        # ── Road color sampling ──────────────────────────────────
        self.sample_w = 100          # width of each sampling strip (px)
        self.sample_h = 30           # height of each sampling strip (px)
        self.color_thresh_day = 25   # tightened from 35
        self.color_thresh_night = 25 # tightened massively from 42
        self.color_thresh = 25       # active threshold (auto-adjusted)

        # ── Running-average road color ───────────────────────────
        self.road_color_history = deque(maxlen=15)
        self.road_color_ema = None
        self.color_ema_alpha = 1.0  # 100% new, no lag

        # ── Shadow recovery ──────────────────────────────────────
        self.shadow_L_weight = 0.75  # Increased from 0.20 to FORCE it to care about brightness differences
        self.active_shadow_L_weight = self.shadow_L_weight
        self.shadow_ab_thresh_pct = 0.40  # Tightened from 0.55

        # ── Texture discrimination (auto-calibrated) ─────────────
        self.texture_enabled = True
        self.texture_block = 7       # local variance kernel size
        self.texture_safety_mult = 3.0  # tightened from 4.0
        self.texture_min_thresh = 300   # floor
        self.texture_max_thresh = 1500  # ceiling

        # ── Temporal mask blending ───────────────────────────────
        self.prev_mask = None
        self.temporal_alpha = 1.0   # 100% current frame, no lag

        # ── Road marking bridge ──────────────────────────────────
        self.marking_bridge_k = 25   # horizontal closing kernel width
        self.marking_max_gap = 40    # vertical gap to fill (px)

        # ── Intersection detection ────────────────────────────────
        self.intersection_width_pct = 0.85  # tightened from 0.75
        self.is_intersection = False

        # ── Night vision ─────────────────────────────────────────
        self.clahe = cv2.createCLAHE(clipLimit=2.5, tileGridSize=(8, 8))
        self.clahe_strong = cv2.createCLAHE(clipLimit=4.0, tileGridSize=(4, 4))
        self.low_light_L_thresh = 90
        self.very_dark_L_thresh = 50

        # ── Region of interest ───────────────────────────────────
        self.roi_top_pct = 0.45      # ignore top 45%

        # ── Morphological cleanup ────────────────────────────────
        self.close_k = 15
        self.open_k = 9

        # ── Boundary scanning ────────────────────────────────────
        self.n_scans = 30            # Doubled scan lines for high precision curve tracking
        self.min_road_w_pct = 0.04   # Allow slightly thinner road sections

        # ── PD steering ──────────────────────────────────────────
        self.Kp = 0.70
        self.Kd = 0.15
        self.Kh = 0.30
        self.dead_zone = 0.04
        self.prev_err = 0.0

        # ── EMA smoothing ────────────────────────────────────────
        self.alpha = 0.80            # 80% new steering, much more responsive
        self.prev_steer = 0.0

        # ── Fallback safety ──────────────────────────────────────
        self.no_road_frames = 0
        self.max_lost = 15

        # ── Exposed state for external use ────────────────────────
        self.last_road_mask = None  # last computed road mask (for go-around checks)
        self.last_roi_y = 0        # top of the ROI in the full frame

    # ─────────────────────────────────────────────────────────────
    #  PUBLIC API
    # ─────────────────────────────────────────────────────────────
    def process_frame(self, frame):
        """
        Returns (steering_cmd, debug_msg, annotated_frame, raw_steer)
        """
        h, w = frame.shape[:2]
        roi_y = int(h * self.roi_top_pct)

        # 1 ── Night vision preprocessing ──────────────────────────
        lab, enhanced, is_night = self._preprocess_night(frame)

        if is_night:
            self.color_thresh = self.color_thresh_night
        else:
            self.color_thresh = self.color_thresh_day

        # Use enhanced frame for all downstream processing
        # (at night this is denoised+gamma+CLAHE; in day it's the original)
        annotated = enhanced.copy()

        # 2 ── Multi-point road color sampling with EMA ────────────
        road_mean = self._sample_road_color_multipoint(lab, h, w)

        # 3 ── Build road mask (color + shadow + texture) ──────────
        #      Pass enhanced (not raw frame) so texture analysis
        #      works on the same quality image as color analysis
        road_mask = self._build_road_mask(
            lab[roi_y:], road_mean, enhanced[roi_y:]
        )

        # 4 ── Bridge road markings ────────────────────────────────
        road_mask = self._bridge_road_markings(road_mask)

        # 5 ── Temporal blending ───────────────────────────────────
        road_mask = self._blend_temporal(road_mask)

        # Store for external use (go-around road checking)
        self.last_road_mask = road_mask
        self.last_roi_y = roi_y

        # 6 ── Scan boundaries ─────────────────────────────────────
        left_xs, right_xs, scan_abs_ys = self._scan_boundaries(
            road_mask, w, roi_y, h
        )
        valid = len(left_xs)

        # 7 ── Intersection detection ──────────────────────────────
        self._detect_intersection(left_xs, right_xs, w)

        # Draw scan points
        for lx, rx, ay in zip(left_xs, right_xs, scan_abs_ys):
            cv2.circle(annotated, (lx, ay), 5, (255, 0, 0), -1)
            cv2.circle(annotated, (rx, ay), 5, (0, 0, 255), -1)
            cx = (lx + rx) // 2
            cv2.circle(annotated, (cx, ay), 4, (0, 255, 255), -1)

        # 8 ── Compute steering ────────────────────────────────────
        if valid >= 3:
            if self.no_road_frames > 0:
                self.prev_steer = 0.0
                self.prev_err = 0.0
                
            raw_steer, steering_cmd, debug_msg = self._compute_steering(
                left_xs, right_xs, w
            )
            self.no_road_frames = 0

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

        # 9 ── Green overlay ───────────────────────────────────────
        overlay = annotated[roi_y:].copy()
        green = np.zeros_like(overlay)
        green[:, :, 1] = road_mask
        annotated[roi_y:] = cv2.addWeighted(overlay, 0.75, green, 0.25, 0)

        # 10 ── Thumbnail ──────────────────────────────────────────
        thumb_h = h // 5
        thumb_w = w // 5
        thumb = cv2.resize(road_mask, (thumb_w, thumb_h))
        thumb_bgr = cv2.cvtColor(thumb, cv2.COLOR_GRAY2BGR)
        annotated[5:5 + thumb_h, w - thumb_w - 5:w - 5] = thumb_bgr

        # 11 ── HUD ────────────────────────────────────────────────
        flags = []
        if is_night:
            flags.append("NIGHT")
        if self.is_intersection:
            flags.append("JUNCTION")
        flag_str = f" [{'/'.join(flags)}]" if flags else ""

        col_map = {
            "left": (255, 100, 0),
            "right": (0, 100, 255),
            "forward": (0, 200, 0),
        }
        cv2.putText(
            annotated,
            f"{steering_cmd.upper()} | {debug_msg}{flag_str}",
            (10, 28), cv2.FONT_HERSHEY_SIMPLEX, 0.45,
            col_map.get(steering_cmd, (255, 255, 255)), 2,
        )

        return steering_cmd, debug_msg, annotated, float(raw_steer)

    # ─────────────────────────────────────────────────────────────
    #  PRIVATE HELPERS
    # ─────────────────────────────────────────────────────────────

    def _preprocess_night(self, frame):
        """
        Multi-stage night vision:
          1. Bilateral denoise (kills camera grain, keeps edges)
          2. Gamma correction (brightens darks without blowing highlights)
          3. CLAHE on L-channel (local contrast enhancement)

        Returns (lab, enhanced_bgr, is_night).
        In daytime, enhanced_bgr == frame.
        """
        lab_raw = cv2.cvtColor(frame, cv2.COLOR_BGR2LAB)
        avg_L = float(np.mean(lab_raw[:, :, 0]))
        is_night = avg_L < self.low_light_L_thresh
        is_very_dark = avg_L < self.very_dark_L_thresh

        if not is_night:
            return lab_raw, frame, False

        # Stage 1: bilateral denoise
        denoised = cv2.bilateralFilter(frame, d=5, sigmaColor=50, sigmaSpace=50)

        # Stage 2: gamma correction
        # gamma < 1 brightens, gamma > 1 darkens
        # Scale linearly: avg_L=90 → gamma≈0.7 (mild), avg_L=10 → gamma≈0.3 (aggressive)
        gamma = max(0.3, min(0.85, avg_L / 128.0))
        if is_very_dark:
            gamma = 0.3  # maximum brightening
        lut = np.array([
            np.clip(pow(i / 255.0, gamma) * 255.0, 0, 255)
            for i in range(256)
        ]).astype(np.uint8)
        brightened = cv2.LUT(denoised, lut)

        # Stage 3: CLAHE on LAB L-channel
        lab = cv2.cvtColor(brightened, cv2.COLOR_BGR2LAB)
        l_ch, a_ch, b_ch = cv2.split(lab)
        l_ch = self.clahe.apply(l_ch)
        if is_very_dark:
            l_ch = self.clahe_strong.apply(l_ch)

        lab = cv2.merge([l_ch, a_ch, b_ch])
        enhanced = cv2.cvtColor(lab, cv2.COLOR_LAB2BGR)

        return lab, enhanced, True

    def _sample_road_color_multipoint(self, lab, h, w):
        """
        Sample road color from 3 strips at the bottom of the frame
        (left-quarter, center, right-quarter). Take the MEDIAN to
        reject outliers (leaf, shadow, crack on one strip).
        Blend with EMA history for smooth surface transitions.
        """
        sy1 = max(0, h - self.sample_h)
        half_sw = self.sample_w // 2

        positions = [w // 4, w // 2, 3 * w // 4]
        samples = []

        for cx in positions:
            sx1 = max(0, cx - half_sw)
            sx2 = min(w, cx + half_sw)
            strip = lab[sy1:h, sx1:sx2]
            if strip.size > 0:
                samples.append(
                    np.mean(strip.reshape(-1, 3), axis=0).astype(np.float32)
                )

        if not samples:
            return self.road_color_ema if self.road_color_ema is not None \
                else np.array([128, 128, 128], dtype=np.float32)

        current_mean = np.median(np.array(samples), axis=0).astype(np.float32)

        self.road_color_history.append(current_mean.copy())

        if self.road_color_ema is None:
            self.road_color_ema = current_mean.copy()
        else:
            self.road_color_ema = (
                self.color_ema_alpha * current_mean +
                (1.0 - self.color_ema_alpha) * self.road_color_ema
            )

        return self.road_color_ema

    def _build_road_mask(self, roi_lab, road_mean, roi_bgr):
        """
        Build road mask using 3 layers:
          1. Color distance (LAB with heavily suppressed L)
          2. Shadow recovery (pure A/B chrominance match)
          3. Texture gate (auto-calibrated local variance filter)

        Then: morphological cleanup → connected-component isolation.
        """
        diff = roi_lab.astype(np.float32) - road_mean

        # Layer 1: color distance with suppressed brightness
        diff_weighted = diff.copy()
        diff_weighted[:, :, 0] *= self.active_shadow_L_weight  
        dist = np.sqrt(np.sum(diff_weighted ** 2, axis=2))
        color_mask = (dist < self.color_thresh).astype(np.uint8) * 255

        # Layer 2: shadow recovery — A/B channels only
        # Shadows change L dramatically but barely touch A/B.
        # This recovers road pixels in deep shade / bright sun patches.
        ab_diff = diff[:, :, 1:3]
        ab_dist = np.sqrt(np.sum(ab_diff ** 2, axis=2))
        shadow_mask = (
            ab_dist < self.color_thresh * self.shadow_ab_thresh_pct
        ).astype(np.uint8) * 255

        mask = cv2.bitwise_or(color_mask, shadow_mask)

        # Layer 3: texture gate (auto-calibrated)
        if self.texture_enabled:
            texture_mask = self._compute_texture_mask(roi_bgr)
            mask = cv2.bitwise_and(mask, texture_mask)

        # Morphological cleanup
        k_close = cv2.getStructuringElement(
            cv2.MORPH_ELLIPSE, (self.close_k, self.close_k)
        )
        k_open = cv2.getStructuringElement(
            cv2.MORPH_ELLIPSE, (self.open_k, self.open_k)
        )
        mask = cv2.morphologyEx(mask, cv2.MORPH_CLOSE, k_close)
        mask = cv2.morphologyEx(mask, cv2.MORPH_OPEN, k_open)

        # Connected-component filter: keep only the region touching
        # the bottom-center (the road the cart is physically on)
        h_roi, w_roi = mask.shape[:2]
        num_labels, labels = cv2.connectedComponents(mask)
        seed_y = h_roi - 1
        seed_x = w_roi // 2
        road_label = labels[seed_y, seed_x]
        
        if road_label > 0:
            mask = ((labels == road_label) * 255).astype(np.uint8)
        else:
            # Bottom-center pixel missed — scan nearby
            found = False
            for dx in range(-40, 41, 5):
                sx = max(0, min(w_roi - 1, seed_x + dx))
                lbl = labels[seed_y, sx]
                if lbl > 0:
                    mask = ((labels == lbl) * 255).astype(np.uint8)
                    found = True
                    break
            
            if not found:
                # No seed found -> no usable road detected. 
                # Return empty mask to safely trigger _fallback()
                return np.zeros_like(mask)

        return mask

    def _compute_texture_mask(self, roi_bgr):
        """
        Auto-calibrated texture discrimination.

        Computes local variance across the ROI. Then measures the
        variance of the KNOWN road region (bottom-center strip) and
        sets the threshold relative to that. This auto-adapts to
        camera resolution, exposure, noise level, and distance.

        Roads are SMOOTH → low variance.
        Grass, gravel, brick → ROUGH → high variance.
        """
        gray = cv2.cvtColor(roi_bgr, cv2.COLOR_BGR2GRAY).astype(np.float32)
        h, w = gray.shape

        # Compute local variance across the whole ROI
        k = self.texture_block
        local_mean = cv2.blur(gray, (k, k))
        local_sq_mean = cv2.blur(gray * gray, (k, k))
        local_var = local_sq_mean - local_mean * local_mean
        local_var = np.clip(local_var, 0, None)

        # Auto-calibrate: measure the variance of the road itself
        # (bottom-center strip — we KNOW this is road)
        road_sy = max(0, h - self.sample_h)
        cx = w // 2
        half_sw = self.sample_w // 2
        road_sx1 = max(0, cx - half_sw)
        road_sx2 = min(w, cx + half_sw)
        road_var_sample = local_var[road_sy:h, road_sx1:road_sx2]

        if road_var_sample.size > 0:
            # Use the 90th percentile of road variance (not mean,
            # because a few high-variance pixels from cracks/edges
            # shouldn't drag the threshold down)
            road_var_p90 = float(np.percentile(road_var_sample, 90))
            thresh = road_var_p90 * self.texture_safety_mult
            thresh = max(self.texture_min_thresh, min(self.texture_max_thresh, thresh))
        else:
            thresh = self.texture_min_thresh

        smooth_mask = (local_var < thresh).astype(np.uint8) * 255
        return smooth_mask

    def _bridge_road_markings(self, mask):
        """
        Speed bumps, zebra crossings, and painted lines create thin
        gaps in the road mask. Bridge them with wide closing operations
        that preserve vertical road edges.
        """
        # Horizontal bridge — connects across paint stripes
        k_h = cv2.getStructuringElement(
            cv2.MORPH_RECT, (self.marking_bridge_k, 3)
        )
        bridged = cv2.morphologyEx(mask, cv2.MORPH_CLOSE, k_h)

        # Vertical bridge — connects across thin speed bumps
        k_v = cv2.getStructuringElement(
            cv2.MORPH_RECT, (3, self.marking_max_gap)
        )
        bridged = cv2.morphologyEx(bridged, cv2.MORPH_CLOSE, k_v)
        return bridged

    def _blend_temporal(self, mask):
        """
        Blend current mask with previous frame's mask.
        Eliminates frame-to-frame flicker. Re-thresholds to binary
        so the mask doesn't degrade into grayscale over time.
        """
        if self.prev_mask is not None and self.prev_mask.shape == mask.shape:
            blended = cv2.addWeighted(
                mask, self.temporal_alpha,
                self.prev_mask, 1.0 - self.temporal_alpha,
                0
            )
            _, blended = cv2.threshold(blended, 127, 255, cv2.THRESH_BINARY)
            self.prev_mask = mask.copy()
            return blended
        else:
            self.prev_mask = mask.copy()
            return mask

    def _detect_intersection(self, left_xs, right_xs, w):
        """Flag when road is very wide (junction / open area)."""
        if len(left_xs) < 3:
            self.is_intersection = False
            return

        wide_count = sum(
            1 for lx, rx in zip(left_xs, right_xs)
            if (rx - lx) > w * self.intersection_width_pct
        )
        self.is_intersection = wide_count > len(left_xs) * 0.5

    def _scan_boundaries(self, mask, w, roi_y, h):
        """Scan the road mask at 14 heights → left/right edge lists."""
        roi_h = mask.shape[0]
        scan_fracs = np.linspace(0.20, 0.95, self.n_scans)
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
        """PD controller with wall safety margin + intersection dampening."""
        n = len(left_xs)
        weights = np.linspace(0.5, 1.5, n)
        centers = [(l + r) / 2.0 for l, r in zip(left_xs, right_xs)]
        avg_center = float(np.average(centers, weights=weights))
        cam_center = w / 2.0

        # Wall safety margin — push away from edges
        avg_left = float(np.average(left_xs, weights=weights))
        avg_right = float(np.average(right_xs, weights=weights))
        road_width = avg_right - avg_left
        if road_width > 0:
            margin_px = road_width * 0.15
            if (cam_center - avg_left) < margin_px:
                avg_center += margin_px * 0.5
            elif (avg_right - cam_center) < margin_px:
                avg_center -= margin_px * 0.5

        # Cross-track error
        cte = (avg_center - cam_center) / cam_center

        # Heading error (far vs near road center)
        heading_err = 0.0
        if n >= 4:
            far_c = (left_xs[0] + right_xs[0]) / 2.0
            near_c = (left_xs[-1] + right_xs[-1]) / 2.0
            heading_err = (far_c - near_c) / cam_center

        error = cte + self.Kh * heading_err

        # PD controller
        d_err = error - self.prev_err
        self.prev_err = error
        raw = self.Kp * error + self.Kd * d_err

        # EMA smoothing
        raw = self.alpha * raw + (1.0 - self.alpha) * self.prev_steer
        self.prev_steer = raw

        # Dampen at intersections — let GPS take over
        if self.is_intersection:
            raw *= 0.3

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

        raw = self.prev_steer * 0.90
        self.prev_steer = raw
        if raw < -self.dead_zone:
            cmd = "left"
        elif raw > self.dead_zone:
            cmd = "right"
        else:
            cmd = "forward"
        return raw, cmd, f"Road fading ({self.no_road_frames}/{self.max_lost})"
