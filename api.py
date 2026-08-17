from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse, JSONResponse
from pydantic import BaseModel
import cv2
import numpy as np
import threading
import time
import json
import asyncio
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
from navigation.fnpp import to_tuple
from navigation.edge_tracker import EdgeTracker

edge_tracker = EdgeTracker()

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
stored_deliver_points = []
active_phase = "IDLE"  # IDLE, PICKUP, AWAITING_PACKING, DELIVERY
cargo_state = "OPEN"  # OPEN, LOCKED
current_mode = "autonomous"  # "autonomous" or "manual"
current_status = "INITIALIZING"
latest_log = "System starting up..."
obstacle_detected = False
current_distance_cm = 999
log_history = []
esp_commands = []

# Webots Simulation State
webots_mode = False
last_webots_cmd = "stop"

# Map State
live_location = None
source_location = None
destination_location = None

# Battery & Health Monitoring
battery_level = 100  # Percentage (0-100)
motor_current = 0.0  # Amps
robot_temperature = 25.0  # Celsius
last_gps_update = None  # datetime timestamp

# YOLO Model
model = YOLO("yolov8n.pt")

# Camera
cap = cv2.VideoCapture(0)
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
    global last_webots_cmd
    last_webots_cmd = cmd
    
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
                connect_esp32()
                
    threading.Thread(target=async_send, daemon=True).start()

def esp32_listener():
    """Background thread to listen for ESP32 messages (e.g. BLOCKED)."""
    global obstacle_detected, current_distance_cm, current_status, battery_level, motor_current, robot_temperature
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
                            current_distance_cm = int(msg.split(":")[1])
                            ts = datetime.now().strftime("%H:%M:%S")
                            esp_commands.append(f"[{ts}] RECV: {msg}")
                            if len(esp_commands) > 30: esp_commands.pop(0)
                        except ValueError:
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
    while True:
        if webots_mode:
            time.sleep(0.05)
            continue
            
        if cap.isOpened():
            ret, frame = cap.read()
            if ret:
                with frame_lock:
                    latest_frame = frame.copy()
        time.sleep(0.03)  # ~30 FPS

# ============================================================
# Background: Autonomous YOLO Loop
# ============================================================
def yolo_loop():
    """Single YOLO loop: runs inference once and caches the annotated frame."""
    global current_status, obstacle_detected, current_distance_cm, annotated_frame, current_route, destination_location, source_location, active_phase, cargo_state
    add_log("🤖 YOLO loop started")
    
    try:
        while True:
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
            
            # ALWAYS process for edge tracking so the dashboard always shows the tracking lines
            edge_cmd, edge_msg, ann = edge_tracker.process_frame(ann)
            
            # Cache the annotated frame for the video feed
            with annotated_lock:
                annotated_frame = ann
            
            # Only do navigation logic in autonomous mode
            if current_mode == "autonomous":
                height, width, _ = frame.shape
                frame_center_x = width // 2
                boxes = results[0].boxes
                
                if len(boxes) > 0:
                    # Find the largest bounding box in the frame
                    largest_box = boxes[0]
                    b0 = largest_box.xyxy[0].cpu().numpy()
                    max_area = (b0[2] - b0[0]) * (b0[3] - b0[1])
                    for box_data in boxes[1:]:
                        b = box_data.xyxy[0].cpu().numpy()
                        area = (b[2] - b[0]) * (b[3] - b[1])
                        if area > max_area:
                            max_area = area
                            largest_box = box_data
                            
                    box = largest_box.xyxy[0].cpu().numpy()
                    obj_center_x = int((box[0] + box[2]) / 2)
                    obj_area = max_area
                    bbox_height = box[3] - box[1]
                    class_id = int(largest_box.cls[0])
                    class_name = model.names[class_id]
                    confidence = float(largest_box.conf[0])
                    
                    # Check zones
                    left_zone = width * 0.35
                    right_zone = width * 0.65
                    
                    obj_left = box[0]
                    obj_right = box[2]
                    
                    if obj_right > left_zone and obj_left < right_zone:
                        # Object is overlapping the center pathway
                        current_status = f"⚠️ {class_name} IN PATH"
                        add_log(f"YOLO: {class_name} blocking -> STOP")
                        send_esp32("stop")
                        obstacle_detected = True
                    elif obj_center_x < left_zone:
                        # Object is on the left, steer right to avoid
                        current_status = "➡️ AVOIDING (STEER RIGHT)"
                        add_log(f"YOLO: {class_name} on left -> Avoiding Right")
                        send_esp32("right")
                        obstacle_detected = True
                    elif obj_center_x > right_zone:
                        # Object is on the right, steer left to avoid
                        current_status = "⬅️ AVOIDING (STEER LEFT)"
                        add_log(f"YOLO: {class_name} on right -> Avoiding Left")
                        send_esp32("left")
                        obstacle_detected = True
                    else:
                        # Object is centered but not too close yet
                        current_status = f"⬆️ MOVING FORWARD"
                        frame_area = height * width
                        area_ratio = max_area / frame_area if frame_area > 0 else 0
                        add_log(f"YOLO: {class_name} centered ({area_ratio:.0%}) -> Moving Forward")
                        send_esp32("forward")
                        obstacle_detected = False
                else:
                    # Default to Edge-Biased Navigation when path is clear
                    nav_cmd = edge_cmd
                    nav_msg = edge_msg
                    
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
                                    nav_msg = "🏪 AT SHOP -> WAITING FOR PACKING"
                                    current_status = nav_msg
                                    send_esp32("unlock")
                                    cargo_state = "OPEN"
                                    active_phase = "AWAITING_PACKING"
                                    current_route = []
                                else:
                                    nav_msg = "🎯 DESTINATION REACHED -> WAITING FOR OTP"
                                    current_status = nav_msg
                                    # Removed send_esp32("unlock") - User will unlock via OTP
                                    active_phase = "IDLE"
                                    current_route = []  # Clear route
                                    destination_location = None
                                    source_location = None
                            else:
                                nav_result = navigate(current_heading, live_location, current_route)
                                gps_cmd = nav_result.get("command", "F")
                                
                                # Map navigation commands to ESP32 commands
                                cmd_map = {"F": "forward", "L": "left", "SL": "left", "R": "right", "SR": "right"}
                                gps_cmd = cmd_map.get(gps_cmd, "forward")
                                
                                # Override Edge Tracker ONLY if GPS explicitly requires a turn at an intersection
                                if gps_cmd != "forward":
                                    nav_cmd = gps_cmd
                                    nav_msg = f"GPS Steering: {nav_cmd.upper()}"
                        except Exception as e:
                            print(f"Navigation error: {e}")
                            
                    if current_status != f"✅ PATH CLEAR -> {nav_cmd.upper()}":
                        add_log(f"✅ Path clear -> {nav_msg}")
                    current_status = f"✅ PATH CLEAR -> {nav_cmd.upper()}"
                    current_distance_cm = 999
                    send_esp32(nav_cmd)
                    obstacle_detected = False
            
            time.sleep(0.03)
    except Exception as e:
        import traceback
        add_log(f"❌ YOLO THREAD CRASHED: {e}")
        print("YOLO THREAD CRASHED:")
        traceback.print_exc()

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
    return {"command": last_webots_cmd}

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
    if cmd in ["forward", "backward", "left", "right", "stop", "lock", "unlock"]:
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
    global source_location, destination_location, current_route, current_heading, stored_deliver_points, active_phase
    
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
    
    add_log(f"📍 Routes calculated: {len(current_route)} pickup waypoints, {len(stored_deliver_points)} delivery waypoints")
    return routes

@app.post("/backend/pack_order")
async def pack_order():
    """Triggered by the shopkeeper when the order is packed and ready."""
    global current_route, stored_deliver_points, active_phase, current_status, cargo_state
    if active_phase in ["AWAITING_PACKING", "PICKUP", "IDLE"]:
        send_esp32("lock")
        cargo_state = "LOCKED"
        current_route = stored_deliver_points
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
    """Phone app sends its live GPS coordinates here."""
    global live_location, current_heading, last_gps_update
    
    body = await req.body()
    try:
        data = json.loads(body.decode("utf-8"))
    except:
        data = {}
        
    new_location = {"lat": data.get("latitude", 0), "lng": data.get("longitude", 0)}
    
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
    cargo_state = "OPEN"
    current_status = "🔓 DESTINATION REACHED -> CARGO UNLOCKED"
    active_phase = "IDLE"
    add_log("Customer unlocked cargo. Delivery completed!")
    return {"status": "success", "message": "Unlocked"}

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
    
    add_log("✅ All systems initialized!")
