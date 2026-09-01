from fastapi import FastAPI, Request, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel
import cv2
import numpy as np
import threading
import time
import json
import asyncio
import traceback
from datetime import datetime
from ultralytics import YOLO

# --- Try to import websocket for ESP32 connection ---
try:
    import websocket
    WS_AVAILABLE = True
except ImportError:
    WS_AVAILABLE = False
    print("⚠️  websocket-client not installed. ESP32 connection disabled.")
    print("   Install with: pip install websocket-client")

from navigation.pipeline import fetch_routes
from navigation.navigate import navigate, calculate_bearing
from navigation.fnpp import to_tuple, calculate_distance
from navigation.lane_follower import LaneFollower
import random

lane_follower = LaneFollower()

# H1 Fix: Thread lock for shared navigation/phase state
state_lock = threading.Lock()

# C6 Fix: Reconnection lock — only one thread can reconnect at a time
esp32_reconnect_lock = threading.Lock()

# ============================================================
# App Setup
# ============================================================
app = FastAPI(title="Autonomous Cart Backend", version="2.0")
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ============================================================
# Pydantic Models
# ============================================================
class Coordinates(BaseModel):
    latitude: float
    longitude: float

class KartCoordinates(BaseModel):
    latitude: float
    longitude: float
    heading: float

class RoutesRequest(BaseModel):
    marketplace: Coordinates
    kart: KartCoordinates
    delivery_point: Coordinates

class ModeRequest(BaseModel):
    mode: str

class ControlRequest(BaseModel):
    action: str

# ============================================================
# Global State
# ============================================================
current_heading = 0.0
current_route = []
waypoint_index = 0  # Tracks which waypoint the cart is currently heading toward
stored_deliver_points = []
active_phase = "IDLE"  # IDLE, PICKUP, AWAITING_PACKING, DELIVERY
cargo_state = "OPEN"  # OPEN, LOCKED
current_mode = "autonomous"  # "autonomous" or "manual"
current_status = "INITIALIZING"
latest_log = "System starting up..."
obstacle_detected = False
prev_area_ratio = 0.0  # Tracks object size growth between frames (fast approach detection)
current_distance_cm = 999
log_history = []
esp_commands = []

# Webots Simulation State
webots_mode = False
last_webots_cmd = "stop"
last_webots_steer = 0.0

# Map State
live_location = None
source_location = None
destination_location = None

# Battery & Health Monitoring
battery_level = 100  # Percentage (0-100)
motor_current = 0.0  # Amps
robot_temperature = 25.0  # Celsius
last_gps_update = None  # datetime timestamp
gps_speed = 0.0  # km/h from phone GPS
gps_accuracy = 0.0  # meters

# GPS EMA Smoothing — reduces ±3-5m jitter to <±1m
gps_ema_alpha = 0.25  # 25% new reading, 75% history (aggressive smoothing)
gps_ema_location = None  # smoothed {lat, lng}
gps_accuracy_gate = 12.0  # ignore readings with accuracy worse than this (meters)
gps_movement_threshold = 2.0  # meters — ignore position changes smaller than this when stopped

# Smart Obstacle Behavior State
from collections import deque as _deque
ultrasonic_history = _deque(maxlen=20)  # last 20 center distance readings
obstacle_stopped_since = None
obstacle_creep_active = False
obstacle_creep_start = None
OBSTACLE_STOP_TIMEOUT = 8.0
OBSTACLE_CREEP_DURATION = 1.0

# Directional Distance (from scanning servo ultrasonic)
dist_left_cm = 999    # last reading from left scan
dist_center_cm = 999  # last reading from center scan (default)
dist_right_cm = 999   # last reading from right scan
scan_servo_angle = "scan_center"  # current servo position: "scan_left"/"scan_center"/"scan_right"

# WebSocket Client Tracking
dashboard_clients: set[WebSocket] = set()
tracking_clients: set[WebSocket] = set()
gps_app_connected = False

# YOLO Model
model = YOLO("yolov8n.pt")

import os

# Camera
CAMERA_SOURCE = os.environ.get("CAMERA_SOURCE", "0")
# If it's a digit, treat it as an integer (USB webcam index)
if CAMERA_SOURCE.isdigit():
    CAMERA_SOURCE = int(CAMERA_SOURCE)

cap = cv2.VideoCapture(CAMERA_SOURCE)
cap.set(cv2.CAP_PROP_BUFFERSIZE, 1)
latest_frame = None
annotated_frame = None
frame_lock = threading.Lock()
annotated_lock = threading.Lock()

# ============================================================
# ESP32 WebSocket Connection
# ============================================================
ws = None
ws_connected = False

def connect_esp32():
    """Connect to ESP32 WebSocket server."""
    global ws, ws_connected
    if not WS_AVAILABLE:
        return
    try:
        ws = websocket.WebSocket()
        ws.settimeout(2)
        ws.connect("ws://192.168.4.1:81/")
        ws_connected = True
        add_log("✅ Connected to ESP32 WebSocket")
        print("✅ Connected to ESP32 WebSocket")
    except Exception as e:
        ws_connected = False
        add_log(f"⚠️ ESP32 not connected: {e}")
        print(f"⚠️ ESP32 connection failed: {e}")

def send_esp32(cmd: str):
    """Send a command to ESP32 via WebSocket without blocking the AI loop."""
    global ws, ws_connected
    
    # Always log the command intent for the dashboard UI (avoid spam)
    cmd_str = f"SENT: {cmd.upper()}"
    if not esp_commands or cmd_str not in esp_commands[-1]:
        ts = datetime.now().strftime("%H:%M:%S")
        esp_commands.append(f"[{ts}] {cmd_str}")
        if len(esp_commands) > 30: esp_commands.pop(0)
    
    # Store for Webots bridge polling
    global last_webots_cmd, last_webots_steer
    last_webots_cmd = cmd
    
    # If the AI commands left/right manually (e.g. YOLO dodging), override continuous steer.
    # Forward steer is set by yolo_loop from lane_follower — do not zero it here.
    if cmd == "left":
        last_webots_steer = -0.3
    elif cmd == "right":
        last_webots_steer = 0.3
    
    if not ws_connected or ws is None:
        return
    
    def async_send():
        global ws_connected
        try:
            ws.send(cmd)
        except Exception:
            if ws_connected:
                ws_connected = False
                add_log("⚠️ ESP32 connection lost. Attempting reconnect...")
                # C6 Fix: Only ONE thread should attempt reconnect
                if esp32_reconnect_lock.acquire(blocking=False):
                    try:
                        connect_esp32()
                    finally:
                        esp32_reconnect_lock.release()
                
    threading.Thread(target=async_send, daemon=True).start()

def esp32_listener():
    """Background thread to listen for ESP32 messages."""
    global obstacle_detected, current_distance_cm, current_status, battery_level, motor_current, robot_temperature
    global dist_left_cm, dist_center_cm, dist_right_cm
    while True:
        if ws_connected and ws is not None:
            try:
                msg = ws.recv()
                if msg:
                    if msg == "BLOCKED":
                        obstacle_detected = True
                        current_status = "🚨 OBSTACLE BLOCKED"
                        add_log("🚨 ESP32 REFLEX: Obstacle within 15cm!")
                        ts = datetime.now().strftime("%H:%M:%S")
                        esp_commands.append(f"[{ts}] RECV: BLOCKED")
                        if len(esp_commands) > 30: esp_commands.pop(0)
                    elif msg.startswith("DIST:"):
                        try:
                            parts = msg.split(":")
                            dist_val = int(parts[1])
                            dir_tag = parts[2] if len(parts) > 2 else "C"
                            
                            # Store in directional slots
                            if dir_tag == "L":
                                dist_left_cm = dist_val
                            elif dir_tag == "R":
                                dist_right_cm = dist_val
                            else:
                                dist_center_cm = dist_val
                                current_distance_cm = dist_val
                                ultrasonic_history.append((time.time(), dist_val))
                            
                            ts = datetime.now().strftime("%H:%M:%S")
                            esp_commands.append(f"[{ts}] RECV: {msg}")
                            if len(esp_commands) > 30: esp_commands.pop(0)
                        except (ValueError, IndexError):
                            pass
                    elif msg.startswith("BAT:"):
                        try:
                            battery_level = int(msg.split(":")[1])
                            ts = datetime.now().strftime("%H:%M:%S")
                            esp_commands.append(f"[{ts}] RECV: {msg}")
                            if len(esp_commands) > 30: esp_commands.pop(0)
                        except ValueError:
                            pass
                    elif msg.startswith("TEMP:"):
                        try:
                            robot_temperature = float(msg.split(":")[1])
                        except ValueError:
                            pass
                    elif msg.startswith("AMP:"):
                        try:
                            motor_current = float(msg.split(":")[1])
                        except ValueError:
                            pass
            except Exception:
                pass
        time.sleep(0.05)

# ============================================================
# Logging
# ============================================================
def add_log(message: str):
    global latest_log, log_history
    timestamp = datetime.now().strftime("%H:%M:%S")
    entry = f"[{timestamp}] {message}"
    latest_log = entry
    log_history.append(entry)
    if len(log_history) > 100:
        log_history = log_history[-100:]

# ============================================================
# Background: Camera Capture
# ============================================================
def camera_loop():
    global latest_frame

    use_url = isinstance(CAMERA_SOURCE, str)

    while True:
        if webots_mode:
            time.sleep(0.05)
            continue

        if use_url:
            # ── Phone IP camera (OpenCV MJPEG with frame-skipping) ──
            stream_cap = cv2.VideoCapture(CAMERA_SOURCE)
            stream_cap.set(cv2.CAP_PROP_BUFFERSIZE, 1)
            if not stream_cap.isOpened():
                add_log("📷 Cannot open phone stream, retrying...")
                time.sleep(2.0)
                continue

            while True:
                # Grab 3 frames, only decode the last → always get the freshest
                for _ in range(3):
                    grabbed = stream_cap.grab()
                if not grabbed:
                    add_log("📷 Phone stream dropped, reconnecting...")
                    break
                ret, frame = stream_cap.retrieve()
                if ret and frame is not None:
                    frame = cv2.resize(frame, (640, 480))
                    with frame_lock:
                        latest_frame = frame.copy()
                time.sleep(0.01)

            stream_cap.release()
            time.sleep(1.0)
        else:
            # ── Local USB / laptop webcam ──
            if cap.isOpened():
                ret, frame = cap.read()
                if ret:
                    frame = cv2.resize(frame, (640, 480))
                    with frame_lock:
                        latest_frame = frame.copy()
            time.sleep(0.03)  # ~30 FPS

# ============================================================
# Background: Autonomous YOLO Loop
# ============================================================
def yolo_loop():
    """Single YOLO loop: runs inference once and caches the annotated frame."""
    global current_status, obstacle_detected, prev_area_ratio, current_distance_cm, annotated_frame, current_route, destination_location, source_location, active_phase, cargo_state, waypoint_index
    global obstacle_stopped_since, obstacle_creep_active, obstacle_creep_start, scan_servo_angle
    add_log("🤖 YOLO loop started")
    
    while True:
        try:
            with frame_lock:
                frame = latest_frame.copy() if latest_frame is not None else None
            
            if frame is None:
                time.sleep(0.05)
                continue
            
            if current_mode == "manual":
                # Skip YOLO inference in manual mode to save CPU and remove latency
                with annotated_lock:
                    annotated_frame = frame
                time.sleep(0.03)
                continue
                
            # Run YOLO once (only in autonomous mode)
            results = model(frame, conf=0.50, verbose=False)
            ann = results[0].plot()
            
            # ALWAYS process for lane tracking so the dashboard always shows the tracking lines
            lane_cmd, lane_msg, ann, lane_steer = lane_follower.process_frame(ann)
            
            global last_webots_steer
            last_webots_steer = lane_steer
            
            # Cache the annotated frame for the video feed
            with annotated_lock:
                annotated_frame = ann
            
            # Only do navigation logic in autonomous mode
            if current_mode == "autonomous":
                height, width, _ = frame.shape
                frame_area = height * width
                boxes = results[0].boxes
                
                valid_classes = {"person", "car", "motorcycle", "bus", "truck", "bicycle", "dog", "cow", "cat", "horse"}
                valid_boxes = [b for b in boxes if model.names[int(b.cls[0])] in valid_classes] if len(boxes) > 0 else []
                
                if len(valid_boxes) > 0:
                    # ─── SMART OBSTACLE AVOIDANCE ───
                    # 1) Build an occupancy map across the frame width
                    #    For each pixel column, mark if ANY bounding box covers it
                    occupancy = np.zeros(width, dtype=np.float32)
                    total_obstacle_area = 0
                    closest_name = ""
                    
                    for box_data in valid_boxes:
                        cid = int(box_data.cls[0])
                        class_name = model.names[cid]
                            
                        b = box_data.xyxy[0].cpu().numpy()
                        bx_left = max(0, int(b[0]))
                        bx_right = min(width, int(b[2]))
                        bx_height_ratio = (b[3] - b[1]) / height  # How tall (= how close)
                        
                        # Weight by closeness: taller box = closer = more dangerous
                        occupancy[bx_left:bx_right] = np.maximum(
                            occupancy[bx_left:bx_right], bx_height_ratio
                        )
                        
                        area = (b[2] - b[0]) * (b[3] - b[1])
                        total_obstacle_area += area
                        if area > 0 and (not closest_name or bx_height_ratio > 0.3):
                            closest_name = class_name
                    
                    total_area_ratio = total_obstacle_area / frame_area
                    
                    # 2) Fast approach detection: compare with previous frame
                    growth_rate = total_area_ratio - prev_area_ratio
                    prev_area_ratio = total_area_ratio
                    is_fast_approaching = growth_rate > 0.03  # Growing >3% per frame = fast
                    
                    # 3) Find the WIDEST GAP (consecutive columns with low occupancy)
                    free = (occupancy < 0.15).astype(np.uint8)  # Columns with no/small obstacle
                    
                    # Find runs of free space
                    best_gap_start = 0
                    best_gap_len = 0
                    current_gap_start = 0
                    current_gap_len = 0
                    
                    for col in range(width):
                        if free[col]:
                            if current_gap_len == 0:
                                current_gap_start = col
                            current_gap_len += 1
                        else:
                            if current_gap_len > best_gap_len:
                                best_gap_len = current_gap_len
                                best_gap_start = current_gap_start
                            current_gap_len = 0
                    if current_gap_len > best_gap_len:
                        best_gap_len = current_gap_len
                        best_gap_start = current_gap_start
                    
                    gap_center = best_gap_start + best_gap_len / 2.0
                    gap_ratio = best_gap_len / width  # How wide is the gap (0-1)
                    frame_center = width / 2.0
                    
                    # 4) AVOIDANCE-FIRST DECISION LOGIC
                    
                    # Determine if obstacle is moving away (follow-at-distance)
                    is_moving_away = False
                    if len(ultrasonic_history) >= 5:
                        recent_dists = [d for _, d in list(ultrasonic_history)[-5:]]
                        if recent_dists[-1] - recent_dists[0] > 10:
                            is_moving_away = True
                    
                    # ── Evaluate Gap (Go-Around) ──
                    steer_dir = "left" if gap_center < frame_center else "right"
                    steer_label = "LEFT" if gap_center < frame_center else "RIGHT"
                    
                    # ── Directional Scanning ──
                    # Point the ultrasonic servo towards the gap to measure true clearance
                    target_scan_angle = "scan_left" if steer_dir == "left" else "scan_right"
                    if scan_servo_angle != target_scan_angle:
                        send_esp32(target_scan_angle)
                        scan_servo_angle = target_scan_angle
                    
                    # Use the ultrasonic reading that matches where we are looking
                    if scan_servo_angle == "scan_left":
                        active_dist_cm = dist_left_cm
                    elif scan_servo_angle == "scan_right":
                        active_dist_cm = dist_right_cm
                    else:
                        active_dist_cm = dist_center_cm
                        
                    has_ultrasonic = active_dist_cm < 400
                    dist_cm = active_dist_cm if has_ultrasonic else 999
                    
                    # Check if the gap actually has ROAD under it (avoid steering into walls)
                    gap_has_road = False
                    if lane_follower.last_road_mask is not None:
                        # Check the bottom 40 rows of the gap in the road mask
                        rmask = lane_follower.last_road_mask
                        gap_start = int(best_gap_start)
                        gap_end = int(best_gap_start + best_gap_len)
                        
                        road_pixels_slice = rmask[-40:, gap_start:gap_end]
                        road_pixels = np.sum(road_pixels_slice > 0)
                        gap_area = road_pixels_slice.size
                        
                        if gap_area > 0 and (road_pixels / gap_area) > 0.30:  # 30% road coverage
                            gap_has_road = True
                    else:
                        gap_has_road = True  # Fallback if mask is missing
                    
                    can_go_around = gap_ratio > 0.20 and total_area_ratio < 0.40 and gap_has_road
                    
                    # ─── DECISION TREE ───
                    
                    if is_fast_approaching and total_area_ratio > 0.05:
                        # ── EMERGENCY: Fast Approach ──
                        current_status = f"🛑 FAST {closest_name} — EMERGENCY STOP"
                        send_esp32("beep")
                        send_esp32("stop")
                        obstacle_detected = True
                        if obstacle_stopped_since is None:
                            obstacle_stopped_since = time.time()
                            
                    elif dist_cm < 20:
                        # PHYSICAL COLLISION IMMINENT — hard stop no matter what
                        current_status = f"🛑 {closest_name} COLLISION ({dist_cm}cm) — STOP"
                        send_esp32("stop")
                        obstacle_detected = True
                        if obstacle_stopped_since is None:
                            obstacle_stopped_since = time.time()
                            
                    elif can_go_around:
                        # ── PRIMARY: Steer around the obstacle ──
                        # This is the PREFERRED behavior at ANY distance
                        obstacle_stopped_since = None
                        obstacle_creep_active = False
                        
                        if dist_cm < 80:
                            # Close — slow + hard steer
                            send_esp32("slow")
                            current_status = f"↪️ Dodging {closest_name} {steer_label} ({dist_cm}cm)"
                        elif dist_cm < 200:
                            # Medium range — slow + gentle steer
                            send_esp32("slow")
                            current_status = f"↪️ Avoiding {closest_name} {steer_label} ({dist_cm}cm)"
                        else:
                            # Far — normal speed + steer
                            current_status = f"↪️ Passing {closest_name} {steer_label}"
                        
                        add_log(f"Avoiding {closest_name} → {steer_label} (gap {gap_ratio:.0%})")
                        send_esp32(steer_dir)
                        obstacle_detected = True
                    
                    elif is_moving_away and dist_cm > 50:
                        # ── SECONDARY: Follow at distance ──
                        # Obstacle is ahead but walking away — trail behind it
                        obstacle_stopped_since = None
                        obstacle_creep_active = False
                        current_status = f"🚶 Following {closest_name} ({dist_cm}cm, moving away)"
                        send_esp32("slow")
                        obstacle_detected = True
                    
                    elif dist_cm > 250 and total_area_ratio < 0.08:
                        # Object is far and small — keep going
                        current_status = f"⬆️ {closest_name} far ({dist_cm}cm) — FORWARD"
                        send_esp32("forward")
                        obstacle_detected = False
                        obstacle_stopped_since = None
                        obstacle_creep_active = False
                    
                    else:
                        # ── LAST RESORT: No gap, can't go around ──
                        # Stop, then creep after timeout
                        obstacle_detected = True
                        
                        if obstacle_stopped_since is None:
                            obstacle_stopped_since = time.time()
                        
                        stop_duration = time.time() - obstacle_stopped_since
                        
                        if obstacle_creep_active:
                            # Currently in creep phase
                            if time.time() - obstacle_creep_start > OBSTACLE_CREEP_DURATION:
                                # Creep phase ended, back to waiting
                                obstacle_creep_active = False
                                obstacle_stopped_since = time.time()
                                current_status = f"🛑 Re-checking {closest_name}..."
                                send_esp32("stop")
                            else:
                                current_status = f"🐢 Creeping past {closest_name}..."
                                send_esp32("slow")
                        elif stop_duration > OBSTACLE_STOP_TIMEOUT:
                            # Waited long enough, try creeping
                            obstacle_creep_active = True
                            obstacle_creep_start = time.time()
                            current_status = f"🐢 Creeping past {closest_name}..."
                            add_log(f"Creeping after {OBSTACLE_STOP_TIMEOUT:.0f}s wait")
                            send_esp32("slow")
                        else:
                            remaining = int(OBSTACLE_STOP_TIMEOUT - stop_duration)
                            current_status = f"🛑 Blocked by {closest_name} ({dist_cm}cm) — creep in {remaining}s"
                            send_esp32("stop")
                
                else:
                    # ─── PATH CLEAR — FOLLOW LANE OR GPS ───
                    obstacle_stopped_since = None
                    obstacle_creep_active = False
                    
                    # 1. Start with the Lane Follower
                    nav_cmd = lane_cmd
                    nav_msg = lane_msg
                    
                    # 2. Check if GPS demands a specific intersection turn
                    if current_route and live_location and (destination_location or source_location):
                        try:
                            from navigation.fnpp import calculate_distance, to_tuple
                            
                            target_loc = source_location if active_phase == "PICKUP" and source_location else destination_location
                            if not target_loc:
                                target_loc = destination_location
                                
                            dist_to_dest = calculate_distance(to_tuple(live_location), to_tuple(target_loc))
                            
                            if dist_to_dest < 5.0:  # Within 5 meters
                                nav_cmd = "stop"
                                send_esp32("stop")
                                
                                if active_phase == "PICKUP":
                                    nav_msg = "🏪 AT SHOP → WAITING FOR PACKING"
                                    current_status = nav_msg
                                    send_esp32("unlock")
                                    cargo_state = "OPEN"
                                    active_phase = "AWAITING_PACKING"
                                    current_route = []
                                    waypoint_index = 0
                                else:
                                    nav_msg = "🎯 DESTINATION REACHED → WAITING FOR OTP"
                                    current_status = nav_msg
                                    active_phase = "IDLE"
                                    current_route = []
                                    waypoint_index = 0
                                    destination_location = None
                                    source_location = None
                            else:
                                nav_result = navigate(current_heading, live_location, current_route, waypoint_index)
                                gps_cmd = nav_result.get("command", "F")
                                waypoint_index = nav_result.get("waypoint_index", waypoint_index)
                                
                                wp_total = len(current_route)
                                if waypoint_index < wp_total:
                                    wp_dist = calculate_distance(to_tuple(live_location), to_tuple(current_route[min(waypoint_index, wp_total - 1)]))
                                    nav_msg = f"GPS WP {waypoint_index+1}/{wp_total} ({wp_dist:.0f}m) → {gps_cmd}"
                                
                                cmd_map = {"F": "forward", "L": "left", "SL": "forward", "R": "right", "SR": "forward"}
                                gps_cmd = cmd_map.get(gps_cmd, "forward")
                                
                                # At intersections, GPS ALWAYS overrides lane following
                                if lane_follower.is_intersection or gps_cmd != "forward":
                                    nav_cmd = gps_cmd
                                    junction_tag = " [JUNCTION]" if lane_follower.is_intersection else ""
                                    nav_msg = f"GPS Steering: {nav_cmd.upper()} (WP {waypoint_index+1}/{wp_total}){junction_tag}"
                        except Exception as e:
                            print(f"Navigation error: {e}")
                            
                    if current_status != f"✅ PATH CLEAR → {nav_cmd.upper()}":
                        add_log(f"✅ {nav_msg}")
                    current_status = f"✅ PATH CLEAR → {nav_cmd.upper()}"
                    current_distance_cm = 999
                    
                    # ── Scan Servo Reset ──
                    target_scan_angle = "scan_center"
                    if nav_cmd == "left": target_scan_angle = "scan_left"
                    elif nav_cmd == "right": target_scan_angle = "scan_right"
                    
                    if scan_servo_angle != target_scan_angle:
                        send_esp32(target_scan_angle)
                        scan_servo_angle = target_scan_angle
                    # ── Speed modulation: slow down on curves ──
                    if nav_cmd in ("left", "right") and abs(lane_steer) > 0.15:
                        send_esp32("slow")   # reduce speed first
                    send_esp32(nav_cmd)
                    # Keep continuous steer for Webots; send_esp32 may override for dodges/GPS turns
                    if nav_cmd == "forward":
                        last_webots_steer = lane_steer
                    obstacle_detected = False
            
            time.sleep(0.03)
        except Exception as e:
            add_log(f"⚠️ YOLO frame error: {e}")
            traceback.print_exc()
            time.sleep(0.1)
            continue

# ============================================================
# API Endpoints
# ============================================================

@app.post("/webots/frame")
async def receive_webots_frame(request: Request):
    """Receive JPEG frames from Webots simulator."""
    global latest_frame, webots_mode
    if not webots_mode:
        webots_mode = True
        add_log("🎮 Webots Simulator Connected. Real camera ignored.")
        
    data = await request.body()
    nparr = np.frombuffer(data, np.uint8)
    frame = cv2.imdecode(nparr, cv2.IMREAD_COLOR)
    
    if frame is not None:
        with frame_lock:
            latest_frame = frame
            
    return {"status": "ok"}

@app.get("/webots/command")
async def get_webots_command():
    """Webots simulator polls this to get the steering command."""
    return {"command": last_webots_cmd, "steer_angle": last_webots_steer}

@app.get("/")
def root():
    return {"message": "Autonomous Cart Backend v2.0", "status": "running"}


@app.get("/video_feed")
async def video_feed():
    """Stream pre-annotated YOLO frames as MJPEG (no extra inference)."""
    async def generate():
        while True:
            with annotated_lock:
                frame = annotated_frame.copy() if annotated_frame is not None else None
            if frame is not None:
                _, buffer = cv2.imencode('.jpg', frame, [cv2.IMWRITE_JPEG_QUALITY, 70])
                yield (b'--frame\r\n'
                       b'Content-Type: image/jpeg\r\n\r\n' + buffer.tobytes() + b'\r\n')
            await asyncio.sleep(0.03)
    
    return StreamingResponse(generate(), media_type='multipart/x-mixed-replace; boundary=frame')

from fastapi.responses import HTMLResponse

@app.get("/gps")
def get_gps_app():
    """Serves the GPS Streamer App to the phone browser."""
    try:
        with open("gps_app.html", "r", encoding="utf-8") as f:
            return HTMLResponse(content=f.read())
    except FileNotFoundError:
        return HTMLResponse(content="<h1>gps_app.html not found!</h1>", status_code=404)

@app.get("/status")
async def get_status():
    """Get current bot telemetry."""
    return {
        "status": current_status,
        "mode": current_mode,
        "active_phase": active_phase,
        "battery_level": battery_level,
        "motor_current": motor_current,
        "robot_temperature": robot_temperature,
        "last_gps_update": last_gps_update.isoformat() if last_gps_update else None,
        "cargo_state": cargo_state,
        "latestLog": latest_log,
        "obstacle_detected": obstacle_detected,
        "distance_cm": current_distance_cm,
        "esp32_connected": ws_connected,
        "gps_app_connected": gps_app_connected,
        "gps_speed": gps_speed,
        "gps_accuracy": gps_accuracy,
        "tracking_clients": len(tracking_clients),
        "camera_active": cap.isOpened() if cap else False,
        "log_history": log_history[-20:],
        "esp_commands": esp_commands[-20:],
        "map_data": {
            "live_location": live_location,
            "source": source_location,
            "destination": destination_location
        }
    }

@app.post("/set_mode")
async def set_mode(req: ModeRequest):
    """Toggle between autonomous and manual mode."""
    global current_mode, current_status
    current_mode = req.mode
    if current_mode == "manual":
        send_esp32("stop")
        current_status = "🎮 MANUAL OVERRIDE"
        add_log("🚨 Manual Override Activated")
    else:
        current_status = "🔍 SEARCHING"
        add_log("🤖 Autonomous Mode Resumed")
    return {"status": "success", "mode": current_mode}

@app.post("/backend/manual_control")
async def manual_control(req: ControlRequest):
    global cargo_state
    if current_mode != "manual":
        return JSONResponse(
            status_code=400, 
            content={"status": "ignored", "reason": "Not in manual mode"}
        )
    
    cmd = req.action.lower()
    if cmd in ["forward", "backward", "reverse", "left", "right", "stop", "lock", "unlock"]:
        send_esp32(cmd)
        if cmd == "lock":
            cargo_state = "LOCKED"
        elif cmd == "unlock":
            cargo_state = "OPEN"
        add_log(f"Manual override: {cmd.upper()}")
        return {"status": "success", "command": cmd}
    return JSONResponse(status_code=400, content={"status": "error", "message": "Invalid command"})

@app.post("/backend/coordinates/destinations")
async def get_coordinates(req: Request):
    """Calculate GPS routes (called once when a new delivery order comes in)."""
    global source_location, destination_location, current_route, current_heading, stored_deliver_points, active_phase, waypoint_index
    
    body = await req.body()
    try:
        data = json.loads(body.decode("utf-8"))
    except:
        data = {}
        
    marketplace = data.get("marketplace", {})
    kart = data.get("kart", {})
    delivery_point = data.get("delivery_point", {})
    
    source_location = {"lat": marketplace.get("latitude", 0), "lng": marketplace.get("longitude", 0)}
    destination_location = {"lat": delivery_point.get("latitude", 0), "lng": delivery_point.get("longitude", 0)}
    current_heading = kart.get("heading", 0)
    
    # Create Pydantic objects for the fetch_routes function
    kart_obj = KartCoordinates(latitude=kart.get("latitude", 0), longitude=kart.get("longitude", 0), heading=current_heading)
    market_obj = Coordinates(latitude=marketplace.get("latitude", 0), longitude=marketplace.get("longitude", 0))
    del_obj = Coordinates(latitude=delivery_point.get("latitude", 0), longitude=delivery_point.get("longitude", 0))
    
    routes = fetch_routes(kart_obj, market_obj, del_obj)
    
    current_route = routes.get('receive_points', [])
    stored_deliver_points = routes.get('deliver_points', [])
    active_phase = "PICKUP"
    waypoint_index = 0
    
    add_log(f"📍 Routes calculated: {len(current_route)} pickup waypoints, {len(stored_deliver_points)} delivery waypoints")
    return routes

@app.post("/backend/pack_order")
async def pack_order():
    """Triggered by the shopkeeper when the order is packed and ready."""
    global current_route, stored_deliver_points, active_phase, current_status, cargo_state, waypoint_index
    if active_phase in ["AWAITING_PACKING", "PICKUP", "IDLE"]:
        send_esp32("lock")
        cargo_state = "LOCKED"
        current_route = stored_deliver_points
        waypoint_index = 0
        active_phase = "DELIVERY"
        current_status = "🚚 CARGO LOCKED -> GO (DELIVERING)"
        add_log("📦 Order Packed. Locked cargo and navigating to customer.")
        return {"status": "success", "message": "Cargo locked, heading to delivery"}
    return JSONResponse(
        status_code=400,
        content={"status": "ignored", "reason": "Bot is not awaiting packing."}
    )

@app.post("/backend/coordinates/live")
async def update_live_location(req: Request):
    """React app sends its simulated live GPS coordinates here."""
    global live_location, current_heading, last_gps_update, gps_app_connected
    
    # If the real GPS phone app is connected via WebSockets, ignore the React simulation!
    if gps_app_connected:
        return {"status": "ignored", "reason": "Real GPS phone app is actively providing telemetry"}
    
    body = await req.body()
    try:
        data = json.loads(body.decode("utf-8"))
    except:
        data = {}
        
    new_location = {"lat": data.get("latitude", 0), "lng": data.get("longitude", 0)}
    
    with state_lock:
        # Calculate new heading if we have moved
        if live_location is not None:
            try:
                new_bearing = calculate_bearing(live_location, new_location)
                # Only update heading if the points are different
                if live_location != new_location:
                    current_heading = new_bearing
            except Exception:
                pass
                
        live_location = new_location
        last_gps_update = datetime.now()
    return {"status": "ok"}
    
@app.post("/backend/unlock")
async def unlock_cart(req: Request):
    """Triggered when the user enters the OTP."""
    global current_status, current_route, active_phase, cargo_state
    send_esp32("unlock")
    with state_lock:
        cargo_state = "OPEN"
        current_status = "🔓 DESTINATION REACHED -> CARGO UNLOCKED"
        active_phase = "IDLE"
    add_log("Customer unlocked cargo. Delivery completed!")
    return {"status": "success", "message": "Unlocked"}

# ============================================================
# WebSocket Broadcast Helpers
# ============================================================

async def broadcast_to_dashboard():
    """Push full telemetry to all connected dashboard clients."""
    if not dashboard_clients:
        return
    data = {
        "type": "status_update",
        "status": current_status,
        "mode": current_mode,
        "active_phase": active_phase,
        "battery_level": battery_level,
        "motor_current": motor_current,
        "robot_temperature": robot_temperature,
        "last_gps_update": last_gps_update.isoformat() if last_gps_update else None,
        "cargo_state": cargo_state,
        "latestLog": latest_log,
        "obstacle_detected": obstacle_detected,
        "distance_cm": current_distance_cm,
        "esp32_connected": ws_connected,
        "gps_app_connected": gps_app_connected,
        "gps_speed": gps_speed,
        "gps_accuracy": gps_accuracy,
        "tracking_clients": len(tracking_clients),
        "camera_active": cap.isOpened() if cap else False,
        "log_history": log_history[-20:],
        "esp_commands": esp_commands[-20:],
        "map_data": {
            "live_location": live_location,
            "source": source_location,
            "destination": destination_location
        }
    }
    msg = json.dumps(data)
    dead = set()
    for client in dashboard_clients:
        try:
            await client.send_text(msg)
        except Exception:
            dead.add(client)
    dashboard_clients.difference_update(dead)

async def broadcast_to_tracking():
    """Push cart location + order status to all delivery app clients."""
    if not tracking_clients:
        return
    
    # Calculate ETA
    eta_seconds = None
    if live_location and destination_location and gps_speed > 0.5:
        try:
            dist = calculate_distance(
                to_tuple(live_location),
                to_tuple(destination_location)
            )
            eta_seconds = int(dist / (gps_speed / 3.6))  # speed is km/h, convert to m/s
        except Exception:
            pass
    
    data = {
        "type": "location_update",
        "cart": live_location,
        "source": source_location,
        "destination": destination_location,
        "phase": active_phase,
        "cargo_state": cargo_state,
        "speed": gps_speed,
        "eta_seconds": eta_seconds,
        "route_points": [{"lat": p["latitude"], "lng": p["longitude"]} for p in current_route] if current_route else []
    }
    msg = json.dumps(data)
    dead = set()
    for client in tracking_clients:
        try:
            await client.send_text(msg)
        except Exception:
            dead.add(client)
    tracking_clients.difference_update(dead)

# ============================================================
# WebSocket Endpoints
# ============================================================

@app.websocket("/ws/gps")
async def ws_gps(websocket: WebSocket):
    """GPS phone app connects here to stream live coordinates."""
    global live_location, current_heading, last_gps_update, gps_speed, gps_accuracy, gps_app_connected
    global gps_ema_location
    
    await websocket.accept()
    gps_app_connected = True
    add_log("📱 GPS Phone App connected via WebSocket")
    
    try:
        while True:
            raw = await websocket.receive_text()
            try:
                data = json.loads(raw)
            except json.JSONDecodeError:
                continue
            
            raw_lat = data.get("lat", 0)
            raw_lng = data.get("lng", 0)
            accuracy = data.get("accuracy", 0) or 0
            speed = data.get("speed", 0) or 0
            
            gps_speed = speed
            gps_accuracy = accuracy
            
            # ── Accuracy gate: reject bad GPS readings ──
            if accuracy > gps_accuracy_gate and gps_ema_location is not None:
                # Bad signal — keep the last good reading
                last_gps_update = datetime.now()
                await websocket.send_text(json.dumps({
                    "status": "filtered", "reason": f"accuracy {accuracy:.0f}m > {gps_accuracy_gate}m",
                    "phase": active_phase, "mode": current_mode
                }))
                continue
            
            # ── Movement threshold: reject GPS jitter when stationary ──
            if gps_ema_location is not None and speed < 1.0:
                from navigation.fnpp import calculate_distance
                jitter_dist = calculate_distance(
                    (gps_ema_location["lat"], gps_ema_location["lng"]),
                    (raw_lat, raw_lng)
                )
                if jitter_dist < gps_movement_threshold:
                    # Cart isn't moving, this is just GPS noise — keep old position
                    last_gps_update = datetime.now()
                    continue
            
            # ── Adaptive EMA smoothing ──
            # At low speed: heavy smoothing (alpha=0.15) to kill jitter
            # At high speed: light smoothing (alpha=0.50) so position doesn't lag behind turns
            adaptive_alpha = min(0.50, max(0.15, speed / 10.0))
            
            if gps_ema_location is None:
                gps_ema_location = {"lat": raw_lat, "lng": raw_lng}
            else:
                gps_ema_location = {
                    "lat": adaptive_alpha * raw_lat + (1.0 - adaptive_alpha) * gps_ema_location["lat"],
                    "lng": adaptive_alpha * raw_lng + (1.0 - adaptive_alpha) * gps_ema_location["lng"],
                }
            
            new_location = gps_ema_location.copy()
            
            # ── Heading: prefer phone compass when moving ──
            if "heading" in data and data["heading"] is not None and speed > 1.0:
                current_heading = data["heading"]
            elif live_location is not None:
                try:
                    new_bearing = calculate_bearing(live_location, new_location)
                    if live_location != new_location:
                        current_heading = new_bearing
                except Exception:
                    pass
            
            live_location = new_location
            last_gps_update = datetime.now()
            
            await websocket.send_text(json.dumps({
                "status": "ok",
                "phase": active_phase,
                "mode": current_mode
            }))
            
            await broadcast_to_dashboard()
            await broadcast_to_tracking()
            
    except WebSocketDisconnect:
        gps_app_connected = False
        add_log("📱 GPS Phone App disconnected")
    except Exception as e:
        gps_app_connected = False
        add_log(f"📱 GPS Phone App error: {e}")


@app.websocket("/ws/dashboard")
async def ws_dashboard(websocket: WebSocket):
    """Streamlit dashboard (or any operator UI) connects here for live telemetry."""
    await websocket.accept()
    dashboard_clients.add(websocket)
    add_log(f"📊 Dashboard client connected ({len(dashboard_clients)} total)")
    
    try:
        # Send initial state snapshot
        await broadcast_to_dashboard()
        
        # Keep connection alive — listen for pings or commands
        while True:
            raw = await websocket.receive_text()
            # Dashboard can send commands if needed
            try:
                data = json.loads(raw)
                if data.get("type") == "ping":
                    await websocket.send_text(json.dumps({"type": "pong"}))
            except json.JSONDecodeError:
                pass
    except WebSocketDisconnect:
        dashboard_clients.discard(websocket)
        add_log(f"📊 Dashboard client disconnected ({len(dashboard_clients)} remaining)")
    except Exception:
        dashboard_clients.discard(websocket)


@app.websocket("/ws/track")
async def ws_track(websocket: WebSocket):
    """Delivery app connects here — receives cart location, can send orders."""
    global source_location, destination_location, current_route, stored_deliver_points, active_phase, current_heading, cargo_state, current_status, waypoint_index
    
    await websocket.accept()
    tracking_clients.add(websocket)
    add_log(f"📦 Delivery tracking client connected ({len(tracking_clients)} total)")
    
    # Send initial state
    try:
        await broadcast_to_tracking()
    except Exception:
        pass
    
    try:
        while True:
            raw = await websocket.receive_text()
            try:
                data = json.loads(raw)
            except json.JSONDecodeError:
                continue
            
            msg_type = data.get("type", "")
            
            if msg_type == "new_order":
                # Delivery app sends a new order with route from Google Maps
                src = data.get("source", {})
                dst = data.get("destination", {})
                route_points = data.get("route_points", [])
                
                source_location = {"lat": src.get("lat", 0), "lng": src.get("lng", 0)}
                destination_location = {"lat": dst.get("lat", 0), "lng": dst.get("lng", 0)}
                
                # Convert route_points to the format the navigation system expects
                current_route = [{"latitude": p["lat"], "longitude": p["lng"]} for p in route_points]
                stored_deliver_points = current_route.copy()
                waypoint_index = 0
                active_phase = "PICKUP"
                current_status = "📍 NEW ORDER → Navigating to shop"
                
                add_log(f"📦 New order received via delivery app: {len(route_points)} waypoints")
                
                # Acknowledge
                await websocket.send_text(json.dumps({
                    "type": "order_confirmed",
                    "message": "Order received! Cart is heading to pickup.",
                    "phase": active_phase,
                    "waypoints": len(route_points)
                }))
                
                # Broadcast to all clients
                await broadcast_to_dashboard()
                await broadcast_to_tracking()
                
            elif msg_type == "unlock":
                # Customer unlocks cargo at destination
                send_esp32("unlock")
                cargo_state = "OPEN"
                current_status = "🔓 DESTINATION REACHED -> CARGO UNLOCKED"
                active_phase = "IDLE"
                add_log("📦 Customer unlocked cargo via delivery app")
                
                await websocket.send_text(json.dumps({
                    "type": "unlock_confirmed",
                    "message": "Cargo unlocked! Please collect your delivery."
                }))
                
                await broadcast_to_dashboard()
                await broadcast_to_tracking()
            
            elif msg_type == "ping":
                await websocket.send_text(json.dumps({"type": "pong"}))
                
    except WebSocketDisconnect:
        tracking_clients.discard(websocket)
        add_log(f"📦 Delivery tracking client disconnected ({len(tracking_clients)} remaining)")
    except Exception:
        tracking_clients.discard(websocket)


# ============================================================
# Background: Dashboard Broadcast Loop
# ============================================================
async def dashboard_broadcast_loop():
    """Push telemetry to dashboard clients every second (supplements GPS-triggered broadcasts)."""
    while True:
        await asyncio.sleep(1)
        try:
            await broadcast_to_dashboard()
            await broadcast_to_tracking()
        except Exception:
            pass

# ============================================================
# Startup
# ============================================================
@app.on_event("startup")
def startup():
    add_log("🚀 Backend starting up...")
    
    # Try connecting to ESP32
    threading.Thread(target=connect_esp32, daemon=True).start()
    
    # Start camera capture thread
    threading.Thread(target=camera_loop, daemon=True).start()
    add_log("📷 Camera thread started")
    
    # Start unified YOLO loop (inference + navigation)
    threading.Thread(target=yolo_loop, daemon=True).start()
    add_log("🧠 YOLO loop started")
    
    # Start ESP32 listener thread
    threading.Thread(target=esp32_listener, daemon=True).start()
    add_log("👂 ESP32 listener thread started")
    
    # Start dashboard broadcast loop (async)
    asyncio.get_event_loop().create_task(dashboard_broadcast_loop())
    add_log("📡 WebSocket broadcast loop started")
    
    add_log("✅ All systems initialized!")

if __name__ == "__main__":
    import uvicorn
    uvicorn.run("api:app", host="0.0.0.0", port=8000, reload=True)
