import cv2
import numpy as np

class EdgeTracker:
    def __init__(self):
        # Tuning parameters for P-controller
        self.Kp = 0.5  # Proportional gain
        
        # Target offset from the left edge (in pixels on the warped frame)
        # Assuming a warped frame width of 400
        self.target_offset_x = 100 
        
        # Perspective transform parameters (to be calibrated)
        self.M = None
        self.Minv = None
        
    def get_birds_eye_view(self, frame):
        """Warp the camera frame to a top-down view."""
        height, width = frame.shape[:2]
        
        # Define 4 source points (Trapezoid representing the path ahead)
        # These need to be tuned based on actual camera angle!
        src = np.float32([
            [width * 0.1, height * 0.9],   # Bottom Left
            [width * 0.9, height * 0.9],   # Bottom Right
            [width * 0.6, height * 0.6],   # Top Right
            [width * 0.4, height * 0.6]    # Top Left
        ])
        
        # Define 4 destination points (Rectangle for top-down view)
        dst = np.float32([
            [0, height],
            [width, height],
            [width, 0],
            [0, 0]
        ])
        
        # Calculate transform matrix if not done yet
        if self.M is None:
            self.M = cv2.getPerspectiveTransform(src, dst)
            self.Minv = cv2.getPerspectiveTransform(dst, src)
            
        warped = cv2.warpPerspective(frame, self.M, (width, height), flags=cv2.INTER_LINEAR)
        return warped, src

    def detect_left_edge(self, warped_frame):
        """Use Canny edge detection and Hough transform to find the left boundary."""
        # Convert to HSV or Grayscale
        gray = cv2.cvtColor(warped_frame, cv2.COLOR_BGR2GRAY)
        
        # Blur to reduce noise
        blur = cv2.GaussianBlur(gray, (5, 5), 0)
        
        # Canny edge detection
        edges = cv2.Canny(blur, 50, 150)
        
        # Only look at the left half of the screen to find the left edge/curb
        height, width = edges.shape
        mask = np.zeros_like(edges)
        cv2.rectangle(mask, (0, 0), (width // 2, height), 255, -1)
        masked_edges = cv2.bitwise_and(edges, mask)
        
        # Find lines
        lines = cv2.HoughLinesP(masked_edges, 1, np.pi/180, threshold=40, minLineLength=40, maxLineGap=100)
        
        if lines is None:
            return None, edges
            
        # Find the average X position of all vertical-ish lines on the left
        left_x_coords = []
        for line in lines:
            x1, y1, x2, y2 = line[0]
            # Avoid horizontal lines (where x changes drastically but y barely changes)
            if abs(y2 - y1) > 20: 
                left_x_coords.append((x1 + x2) / 2.0)
                
        if not left_x_coords:
            return None, edges
            
        # Return the median x coordinate representing the continuous left curb line
        avg_left_x = int(np.median(left_x_coords))
        return avg_left_x, edges

    def process_frame(self, frame):
        """Main pipeline combining warp, edge detection, and P-controller steering."""
        warped, src_points = self.get_birds_eye_view(frame)
        left_edge_x, edges = self.detect_left_edge(warped)
        
        steering_cmd = "forward"
        debug_msg = "Tracking: No Edge Found"
        
        if left_edge_x is not None:
            # Calculate error
            error = self.target_offset_x - left_edge_x
            
            # Simple Proportional Controller
            control_signal = self.Kp * error
            
            # Thresholds for converting continuous control signal to discrete commands
            # Because our bot currently just takes "left", "right", "forward"
            if control_signal > 30.0:
                # Edge is moving left in the frame (< target), which means the bot is drifting RIGHT.
                # So we must steer LEFT to get back to the edge.
                steering_cmd = "left"
                debug_msg = f"Tracking: Drifting right (Err: {error:.1f}) -> Steer LEFT"
            elif control_signal < -30.0:
                # Edge is moving right in the frame (> target), which means the bot is drifting LEFT towards the curb.
                # So we must steer RIGHT to avoid hitting the curb.
                steering_cmd = "right"
                debug_msg = f"Tracking: Too close to edge (Err: {error:.1f}) -> Steer RIGHT"
            else:
                steering_cmd = "forward"
                debug_msg = f"Tracking: Centered (Err: {error:.1f}) -> FORWARD"
                
        # --- Drawing for Visual Debugging (Dashboard) ---
        annotated = frame.copy()
        height, width = frame.shape[:2]
        
        # Draw perspective bounds
        pts = src_points.reshape((-1, 1, 2)).astype(np.int32)
        cv2.polylines(annotated, [pts], True, (0, 255, 255), 2)
        
        if left_edge_x is not None:
            # Unwarp the detected line back to original camera view so it looks nice on dashboard
            # We approximate the line by two points top and bottom of warped frame
            top_pt = np.array([[[left_edge_x, 0]]], dtype=np.float32)
            bot_pt = np.array([[[left_edge_x, height]]], dtype=np.float32)
            
            unwarped_top = cv2.perspectiveTransform(top_pt, self.Minv)[0][0]
            unwarped_bot = cv2.perspectiveTransform(bot_pt, self.Minv)[0][0]
            
            # Draw the detected curb line
            cv2.line(annotated, 
                     (int(unwarped_top[0]), int(unwarped_top[1])), 
                     (int(unwarped_bot[0]), int(unwarped_bot[1])), 
                     (0, 255, 0), 4)
                     
            # Draw the target offset line
            target_top = np.array([[[self.target_offset_x, 0]]], dtype=np.float32)
            target_bot = np.array([[[self.target_offset_x, height]]], dtype=np.float32)
            ut_top = cv2.perspectiveTransform(target_top, self.Minv)[0][0]
            ut_bot = cv2.perspectiveTransform(target_bot, self.Minv)[0][0]
            
            cv2.line(annotated, 
                     (int(ut_top[0]), int(ut_top[1])), 
                     (int(ut_bot[0]), int(ut_bot[1])), 
                     (255, 0, 0), 2)
                     
        return steering_cmd, debug_msg, annotated
