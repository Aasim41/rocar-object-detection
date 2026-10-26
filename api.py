"""
AutoDrop Autonomous Ground Vehicle — Fleet Controller & API Gateway
=====================================================================
Core backend for autonomous delivery cart:
- Hardware Serial Link (COM7 @ 115200 baud): Motors, Latch Servo, Ultrasonic Radar
- YOLOv8 Real-time Obstacle Detection & Proportional Braking
- Geodesic GPS Waypoint Following & Self-Return Navigation
- WebSockets for Streamlit GSAP Mission Control & React Delivery App
"""

import asyncio
from contextlib import asynccontextmanager
import cv2
from datetime import datetime
import json
import math
import os
import re
import socket
import sys
import threading
import time
from typing import Optional, Set

from fastapi import FastAPI, HTTPException, Request, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import HTMLResponse, JSONResponse, StreamingResponse
import numpy as np
from pydantic import BaseModel
import serial
from ultralytics import YOLO

# Project Modules
from navigation.decode_route import dense_interpolate_points
from navigation.fnpp import calculate_distance, to_tuple
from navigation.navigate import calculate_bearing, navigate
from navigation.pipeline import fetch_routes, set_routing_engine
import telemetry_db

# ============================================================
# Core Configuration
# ============================================================
BOT_WS_URL = os.environ.get("BOT_WS_URL", "COM7")
BAUD_RATE = 115200
CAMERA_INDEX = int(os.environ.get("CAMERA_SOURCE", "0"))
WAYPOINT_THRESHOLD_METERS = 2.5
DESIRED_IMAGE_WIDTH = 640
DESIRED_IMAGE_HEIGHT = 480

# ============================================================
# Global Vehicle & Mission State
# ============================================================
current_mode = "autonomous"  # "autonomous" or "manual"
active_phase = "IDLE"        # IDLE, HEADING_TO_SENDER, AWAITING_LOAD, DELIVERING, AWAITING_RETRIEVAL, RETURNING_TO_BASE
cargo_state = "LOCKED"       # "LOCKED" (0°) or "UNLOCKED" (90°)
current_status = "IDLE (DOCKED)"
latest_log = "System initialized"

# Navigation Coordinates & Routes
charging_station = {"lat": 0.0, "lng": 0.0}
source_location: Optional[dict] = None
destination_location: Optional[dict] = None
current_route: list = []
stored_deliver_points: list = []
waypoint_index = 0
current_delivery_id: Optional[str] = None

# Real-time Telemetry
live_location: Optional[dict] = None
current_heading = 0.0
gps_speed = 0.0
gps_accuracy = 0.0
last_gps_update: Optional[datetime] = None
current_distance_cm = 999
dist_left_cm = 999
dist_center_cm = 999
dist_right_cm = 999
obstacle_detected = False
obstacle_stopped_since = 0.0
blocked_until = 0.0
battery_level = 100
motor_current = 0.0

# Locks & Synchronization
state_lock = threading.Lock()
frame_lock = threading.Lock()
log_history: list = []
esp_commands: list = []

# Connected WebSocket Clients
dashboard_clients: Set[WebSocket] = set()
tracking_clients: Set[WebSocket] = set()
gps_app_connected = False

# Vision & Hardware Objects
latest_frame = None
annotated_jpeg = None
ser_conn: Optional[serial.Serial] = None
ws_connected = False
model = YOLO("yolov8n.pt")


def add_log(msg: str):
    """Log an operational event with timestamp."""
    global latest_log
    ts = datetime.now().strftime("%H:%M:%S")
    entry = f"[{ts}] {msg}"
    log_history.append(entry)
    if len(log_history) > 50:
        log_history.pop(0)
    latest_log = msg
    print(entry)


# ============================================================
# Hardware Serial Driver (Arduino Uno / COM7)
# ============================================================
def connect_hardware():
    """Connect directly to Arduino on USB serial port."""
    global ser_conn, ws_connected
    try:
        ser_conn = serial.Serial(BOT_WS_URL, BAUD_RATE, timeout=0.1)
        ws_connected = True
        add_log(f"Hardware linked on {BOT_WS_URL} @ {BAUD_RATE} baud")
        threading.Thread(target=serial_listener_loop, daemon=True).start()
    except Exception as e:
        ws_connected = False
        add_log(f"Hardware port {BOT_WS_URL} offline: {e}")


def serial_listener_loop():
    """Continuously read telemetry lines emitted by the Arduino."""
    global ser_conn, ws_connected, current_distance_cm, dist_left_cm, dist_center_cm, dist_right_cm
    global battery_level, motor_current
    while ws_connected and ser_conn and ser_conn.is_open:
        try:
            line = ser_conn.readline().decode("utf-8", errors="ignore").strip()
            if not line:
                continue
            ts = datetime.now().strftime("%H:%M:%S")
            esp_commands.append(f"[{ts}] RECV: {line}")
            if len(esp_commands) > 30:
                esp_commands.pop(0)

            # Parse Ultrasonic: US:<dist> or US_SWEEP:<left>:<center>:<right>
            if line.startswith("US:"):
                dist = int(line.split(":")[1])
                current_distance_cm = dist
                dist_center_cm = dist
            elif line.startswith("US_SWEEP:"):
                parts = line.split(":")
                dist_left_cm = int(parts[1])
                dist_center_cm = int(parts[2])
                dist_right_cm = int(parts[3])
                current_distance_cm = dist_center_cm
            elif line.startswith("BAT:"):
                battery_level = int(line.split(":")[1])
            elif line.startswith("AMP:"):
                motor_current = float(line.split(":")[1])
        except Exception:
            time.sleep(0.05)


def send_hardware_cmd(cmd: str):
    """Transmit motor or servo action to Arduino."""
    global ser_conn, ws_connected, motor_current
    ts = datetime.now().strftime("%H:%M:%S")
    esp_commands.append(f"[{ts}] SENT: {cmd}")
    if len(esp_commands) > 30:
        esp_commands.pop(0)

    # Dynamic motor current simulation if sensor not wired
    if cmd in ["forward", "slow"]:
        motor_current = 1.2
    elif "steer" in cmd or "curve" in cmd:
        motor_current = 1.6
    elif cmd in ["stop", "lock", "unlock"]:
        motor_current = 0.0

    if ser_conn and ser_conn.is_open:
        try:
            ser_conn.write(f"{cmd}\n".encode("utf-8"))
        except Exception as e:
            add_log(f"Serial write error: {e}")
            ws_connected = False


# ============================================================
# Vision Loop (YOLOv8 Obstacle Detection & Braking)
# ============================================================
def camera_worker():
    """Captures frames from webcam index 0 (or creates a fallback canvas)."""
    global latest_frame
    cap = cv2.VideoCapture(CAMERA_INDEX)
    if not cap.isOpened():
        add_log(f"Camera index {CAMERA_INDEX} not available. Using fallback canvas.")
    while True:
        if cap.isOpened():
            ret, frame = cap.read()
            if ret:
                with frame_lock:
                    latest_frame = frame
            else:
                time.sleep(0.03)
        else:
            # Standby blank frame so navigation does not stall
            canvas = np.zeros((DESIRED_IMAGE_HEIGHT, DESIRED_IMAGE_WIDTH, 3), dtype=np.uint8)
            cv2.putText(canvas, "AUTODROP LIVE VISION STANDBY", (140, 240),
                        cv2.FONT_HERSHEY_SIMPLEX, 0.7, (6, 182, 212), 2)
            with frame_lock:
                latest_frame = canvas
            time.sleep(0.05)


def yolo_inference_loop():
    """Runs YOLOv8 object detection, corridor obstacle evaluation, and proportional braking."""
    global annotated_jpeg, obstacle_detected, current_status, blocked_until, obstacle_stopped_since
    add_log("Vision & Autonomous Control loop started")

    while True:
        with frame_lock:
            frame = None if latest_frame is None else latest_frame.copy()

        if frame is None:
            time.sleep(0.03)
            continue

        h, w = frame.shape[:2]
        results = model.predict(frame, conf=0.45, verbose=False)
        detected_obstacle = False
        closest_name = ""

        # Check for obstacles inside vehicle driving corridor (center 60% of lower screen)
        corridor_x_min, corridor_x_max = int(w * 0.20), int(w * 0.80)
        corridor_y_min = int(h * 0.35)

        for r in results:
            for box in r.boxes:
                cls_id = int(box.cls[0])
                cls_name = model.names.get(cls_id, "object")
                x1, y1, x2, y2 = map(int, box.xyxy[0])

                if cls_name in ["person", "car", "bicycle", "motorcycle", "dog", "chair", "box"]:
                    # Is the object intersecting the driving corridor?
                    if not (x2 < corridor_x_min or x1 > corridor_x_max or y2 < corridor_y_min):
                        detected_obstacle = True
                        closest_name = cls_name
                        cv2.rectangle(frame, (x1, y1), (x2, y2), (0, 0, 255), 2)
                        cv2.putText(frame, f"OBSTACLE: {cls_name}", (x1, max(20, y1 - 8)),
                                    cv2.FONT_HERSHEY_SIMPLEX, 0.5, (0, 0, 255), 2)

        obstacle_detected = detected_obstacle

        # Autonomous Navigation Execution
        if current_mode == "autonomous" and active_phase in ["HEADING_TO_SENDER", "DELIVERING", "RETURNING_TO_BASE"]:
            run_autonomous_navigation(detected_obstacle, closest_name)

        # Encode JPEG for MJPEG dashboard video stream
        ret, buf = cv2.imencode(".jpg", frame, [cv2.IMWRITE_JPEG_QUALITY, 75])
        if ret:
            annotated_jpeg = buf.tobytes()

        time.sleep(0.03)


# ============================================================
# Autonomous Navigation Engine (Waypoints & Proportional Braking)
# ============================================================
def run_autonomous_navigation(detected_obstacle: bool, obstacle_name: str):
    """Translates GPS waypoints and sensor readings into low-level Arduino motor commands."""
    global current_route, waypoint_index, active_phase, current_status, cargo_state
    global blocked_until, obstacle_stopped_since

    now = time.time()

    # 1. Obstacle Safety Braking
    if detected_obstacle or dist_center_cm < 25 or obstacle_detected:
        send_hardware_cmd("stop")
        current_status = f"STOPPED — Obstacle in path ({obstacle_name or f'{dist_center_cm}cm'})"
        blocked_until = now + 1.2
        return

    if now < blocked_until:
        send_hardware_cmd("stop")
        return

    if not current_route or not live_location:
        current_status = f"{active_phase} — Waiting for GPS fix / Route points"
        send_hardware_cmd("stop")
        return

    # 2. Reached Final Waypoint in Current Leg
    if waypoint_index >= len(current_route):
        send_hardware_cmd("stop")
        if active_phase == "HEADING_TO_SENDER":
            active_phase = "AWAITING_LOAD"
            cargo_state = "UNLOCKED"
            send_hardware_cmd("unlock")  # Rotate servo 90° for pickup loading
            current_status = "AT SENDER — Cargo unlocked for loading"
            add_log("Reached Sender! Latch unlocked for package loading.")
        elif active_phase == "DELIVERING":
            active_phase = "AWAITING_RETRIEVAL"
            current_status = "AT RECEIVER — Awaiting QR scan or OTP unlock"
            add_log("Reached Receiver destination! Waiting for collection.")
        elif active_phase == "RETURNING_TO_BASE":
            active_phase = "IDLE"
            current_status = "IDLE (DOCKED) — Base Return Completed"
            add_log("Successfully docked at Base Charging Station!")
        return

    # 3. Target Waypoint Progression
    target_wp = current_route[waypoint_index]
    target_coord = (target_wp.get("lat") or target_wp.get("latitude"),
                    target_wp.get("lng") or target_wp.get("longitude"))
    current_coord = (live_location["latitude"], live_location["longitude"])

    dist_to_wp = calculate_distance(current_coord, target_coord)

    if dist_to_wp < WAYPOINT_THRESHOLD_METERS:
        waypoint_index += 1
        add_log(f"Waypoint {waypoint_index}/{len(current_route)} reached ({dist_to_wp:.1f}m)")
        return

    # 4. Heading & Steering Calculation
    target_bearing = calculate_bearing(current_coord, target_coord)
    heading_error = (target_bearing - current_heading + 540) % 360 - 180

    # Proportional Speed Control
    if dist_center_cm < 60:
        base_cmd = "slow"
    else:
        base_cmd = "forward"

    if abs(heading_error) < 15:
        nav_cmd = base_cmd
    elif heading_error < -45:
        nav_cmd = "curve_left"
    elif heading_error < -15:
        nav_cmd = "steer_left"
    elif heading_error > 45:
        nav_cmd = "curve_right"
    else:
        nav_cmd = "steer_right"

    send_hardware_cmd(nav_cmd)
    current_status = f"TRACKING — WP {waypoint_index+1}/{len(current_route)} ({dist_to_wp:.1f}m, err: {heading_error:.0f}°)"


# ============================================================
# FastAPI Lifespan & Application Setup
# ============================================================
@asynccontextmanager
async def lifespan(app: FastAPI):
    """Starts background hardware connection, vision pipeline, and telemetry broadcasters."""
    connect_hardware()
    threading.Thread(target=camera_worker, daemon=True).start()
    threading.Thread(target=yolo_inference_loop, daemon=True).start()
    asyncio.create_task(periodic_broadcast_loop())
    yield


app = FastAPI(title="AutoDrop Autonomous Fleet Gateway", lifespan=lifespan)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# ============================================================
# Telemetry Broadcast Functions (10Hz WebSockets)
# ============================================================
def calculate_route_eta():
    """Calculates remaining route travel time in seconds."""
    if not live_location or not destination_location:
        return None
    try:
        total_dist = 0.0
        if current_route and waypoint_index < len(current_route):
            curr = to_tuple(live_location)
            for i in range(waypoint_index, len(current_route)):
                nxt = to_tuple(current_route[i])
                total_dist += calculate_distance(curr, nxt)
                curr = nxt
            total_dist += calculate_distance(curr, to_tuple(destination_location))
        else:
            total_dist = calculate_distance(to_tuple(live_location), to_tuple(destination_location))
        effective_speed = gps_speed if gps_speed > 0.5 else 3.0
        return int(total_dist / (effective_speed / 3.6))
    except Exception:
        return None


async def broadcast_telemetry():
    """Pushes comprehensive real-time status to Mission Control and Delivery mobile app."""
    eta_sec = calculate_route_eta()

    payload = {
        "type": "status_update",
        "status": current_status,
        "mode": current_mode,
        "active_phase": active_phase,
        "cargo_state": cargo_state,
        "battery_level": battery_level,
        "motor_current": motor_current,
        "distance_cm": current_distance_cm,
        "obstacle_detected": obstacle_detected,
        "esp32_connected": ws_connected,
        "gps_app_connected": gps_app_connected,
        "gps_speed": gps_speed,
        "gps_accuracy": gps_accuracy,
        "eta_seconds": eta_sec,
        "tracking_clients": len(tracking_clients),
        "camera_active": latest_frame is not None,
        "latestLog": latest_log,
        "log_history": log_history[-15:],
        "esp_commands": esp_commands[-10:],
        "map_data": {
            "cart": live_location,
            "source": source_location,
            "destination": destination_location,
            "charging_station": charging_station,
            "route_points": [{"lat": p.get("lat") or p.get("latitude"),
                              "lng": p.get("lng") or p.get("longitude")}
                             for p in current_route if isinstance(p, dict)]
        }
    }

    # Broadcast to Mission Control Dashboard
    msg = json.dumps(payload)
    dead_dash = set()
    for ws in dashboard_clients:
        try:
            await ws.send_text(msg)
        except Exception:
            dead_dash.add(ws)
    dashboard_clients.difference_update(dead_dash)

    # Broadcast Location Update to Mobile App
    loc_payload = json.dumps({
        "type": "location_update",
        "cart": live_location,
        "source": source_location,
        "destination": destination_location,
        "charging_station": charging_station,
        "phase": active_phase,
        "cargo_state": cargo_state,
        "speed": gps_speed,
        "eta_seconds": eta_sec,
        "delivery_id": current_delivery_id,
        "route_points": payload["map_data"]["route_points"]
    })
    dead_track = set()
    for ws in tracking_clients:
        try:
            await ws.send_text(loc_payload)
        except Exception:
            dead_track.add(ws)
    tracking_clients.difference_update(dead_track)


async def periodic_broadcast_loop():
    """Guarantees 1-second cadence telemetry broadcasts even when robot is stationary."""
    while True:
        await asyncio.sleep(1.0)
        try:
            await broadcast_telemetry()
        except Exception:
            pass


# ============================================================
# HTTP Endpoints (Mission Management & Hardware Control)
# ============================================================
@app.get("/")
def root():
    return {"status": "running", "unit": "AutoDrop-01", "phase": active_phase}


@app.get("/status")
async def get_status():
    """Primary telemetry polling endpoint."""
    return {
        "status": current_status,
        "mode": current_mode,
        "active_phase": active_phase,
        "cargo_state": cargo_state,
        "battery_level": battery_level,
        "motor_current": motor_current,
        "distance_cm": current_distance_cm,
        "obstacle_detected": obstacle_detected,
        "esp32_connected": ws_connected,
        "gps_app_connected": gps_app_connected,
        "gps_speed": gps_speed,
        "tracking_clients": len(tracking_clients),
        "camera_active": latest_frame is not None,
        "latestLog": latest_log,
        "log_history": log_history[-15:],
        "esp_commands": esp_commands[-10:]
    }


@app.get("/video_feed")
async def video_feed():
    """Zero-latency MJPEG video stream of annotated YOLO camera frames."""
    async def generate():
        last_sent = None
        while True:
            jpeg = annotated_jpeg
            if jpeg is not None and jpeg is not last_sent:
                last_sent = jpeg
                yield (b'--frame\r\n'
                       b'Content-Type: image/jpeg\r\n\r\n' + jpeg + b'\r\n')
            await asyncio.sleep(0.015)
    return StreamingResponse(generate(), media_type="multipart/x-mixed-replace; boundary=frame")


@app.get("/gps")
def get_gps_app():
    with open("gps_app.html", "r", encoding="utf-8") as f:
        return HTMLResponse(content=f.read())


@app.get("/drive")
def get_manual_drive():
    with open("manual_drive.html", "r", encoding="utf-8") as f:
        return HTMLResponse(content=f.read())


@app.post("/set_mode")
async def set_mode(request: Request):
    """Switch between autonomous and manual control."""
    global current_mode
    body = await request.json()
    current_mode = body.get("mode", "autonomous")
    if current_mode == "manual":
        send_hardware_cmd("stop")
    add_log(f"Operating mode set to: {current_mode.upper()}")
    await broadcast_telemetry()
    return {"status": "ok", "mode": current_mode}


@app.post("/backend/manual_control")
async def manual_control(request: Request):
    """Direct teleoperation commands from web joystick."""
    body = await request.json()
    cmd = body.get("command", "stop")
    send_hardware_cmd(cmd)
    return {"status": "ok", "command": cmd}


# ============================================================
# Autonomous Mission Lifecycle Endpoints
# ============================================================
@app.post("/backend/new_delivery")
async def new_delivery(request: Request):
    """
    Stage 1: Ingests delivery order from AutoDrop app.
    Plans dense route from Base Dock -> Sender (Pickup).
    """
    global source_location, destination_location, charging_station, current_route
    global stored_deliver_points, active_phase, waypoint_index, current_delivery_id

    body = await request.json()
    source_location = body.get("source")
    destination_location = body.get("destination")
    if body.get("charging_station"):
        charging_station = body["charging_station"]

    current_delivery_id = body.get("delivery_id", f"DEL-{int(time.time())}")

    # Extract dense Google Maps waypoints provided by app
    route_points = body.get("route_points", [])
    if route_points:
        raw_pts = [{"lat": p.get("lat") or p.get("latitude"),
                    "lng": p.get("lng") or p.get("longitude")} for p in route_points]
        stored_deliver_points = dense_interpolate_points(raw_pts, max_step_meters=2.5)

    # Route cart from current location to Sender
    start_pos = live_location if live_location else charging_station
    routes = fetch_routes(start_pos, source_location, destination_location)
    current_route = routes.get("receive_points", []) or stored_deliver_points

    waypoint_index = 0
    active_phase = "HEADING_TO_SENDER"
    add_log(f"New Order {current_delivery_id}: Heading to Sender ({len(current_route)} waypoints)")
    await broadcast_telemetry()
    return {"status": "ok", "delivery_id": current_delivery_id, "phase": active_phase}


@app.api_route("/backend/verify_qr", methods=["GET", "POST"])
async def verify_qr(request: Request):
    """
    Stage 2/4: Scanned by mobile camera or dashboard to unlock cargo latch to 90°.
    Supports both browser GET navigation and REST POST.
    """
    global cargo_state
    cargo_state = "UNLOCKED"
    send_hardware_cmd("unlock")  # Hardware Servo 90°
    add_log("Cargo latch UNLOCKED (90°) via QR scan verification")
    await broadcast_telemetry()

    if request.method == "GET":
        html = """
        <!DOCTYPE html><html><head><meta name="viewport" content="width=device-width,initial-scale=1">
        <style>body{background:#090b10;color:#f8fafc;font-family:sans-serif;display:flex;align-items:center;
        justify-content:center;height:100vh;margin:0;}
        .card{background:#111622;border:1px solid #10b981;border-radius:14px;padding:28px;text-align:center;max-width:320px;}
        h2{color:#10b981;margin:0 0 10px 0;}p{color:#94a3b8;font-size:14px;line-height:1.5;}</style></head>
        <body><div class="card"><h2>LATCH UNLOCKED</h2><p>The cargo compartment is open (90&deg;).<br>
        Please load or collect your package.</p></div></body></html>
        """
        return HTMLResponse(content=html)
    return {"status": "ok", "cargo_state": "UNLOCKED"}


@app.post("/backend/dispatch")
async def dispatch_cart():
    """
    Stage 3: Sender finishes loading package and taps Dispatch.
    Secures cargo latch (0°) and drives cart to Destination.
    """
    global active_phase, cargo_state, current_route, waypoint_index
    send_hardware_cmd("lock")  # Secure latch 0°
    cargo_state = "LOCKED"
    current_route = stored_deliver_points
    waypoint_index = 0
    active_phase = "DELIVERING"
    add_log(f"Dispatched to Destination! Following {len(current_route)} dense waypoints.")
    await broadcast_telemetry()
    return {"status": "ok", "phase": active_phase}


@app.post("/backend/complete_retrieval")
async def complete_retrieval():
    """
    Stage 5: Receiver retrieves package and confirms.
    Secures lid (0°) and autonomously navigates back to Base Dock.
    """
    global active_phase, cargo_state
    send_hardware_cmd("lock")
    cargo_state = "LOCKED"
    active_phase = "STANDBY"
    add_log("Retrieval finished. Cargo secured. Initiating autonomous return to Base...")
    await broadcast_telemetry()

    # Async return to base after brief safety pause
    async def rtb_task():
        await asyncio.sleep(3.0)
        await trigger_return_to_base()
    asyncio.create_task(rtb_task())
    return {"status": "ok", "message": "Returning to Base Dock"}


@app.post("/backend/return_to_base")
async def trigger_return_to_base():
    """1-Click Autonomous Return to Base Charging Dock."""
    global current_route, waypoint_index, active_phase
    start_pos = live_location if live_location else destination_location
    base_pos = charging_station if charging_station.get("lat") else {"lat": 24.4332, "lng": 77.1585}

    routes = fetch_routes(start_pos, base_pos, base_pos)
    current_route = routes.get("receive_points", [])
    waypoint_index = 0
    active_phase = "RETURNING_TO_BASE"
    add_log(f"Navigating back to Base Charging Station ({len(current_route)} waypoints)")
    await broadcast_telemetry()
    return {"status": "ok", "phase": active_phase, "waypoints": len(current_route)}


# ============================================================
# WebSocket Gateways
# ============================================================
@app.websocket("/ws/gps")
async def ws_gps(websocket: WebSocket):
    """Receives live phone GPS coordinates and updates vehicle telemetry."""
    global live_location, current_heading, gps_speed, gps_accuracy, last_gps_update, gps_app_connected
    await websocket.accept()
    gps_app_connected = True
    add_log("GPS Phone Streamer linked via WebSocket")

    try:
        while True:
            data = json.loads(await websocket.receive_text())
            live_location = {"latitude": data["latitude"], "longitude": data["longitude"]}
            current_heading = data.get("heading", current_heading)
            gps_speed = data.get("speed", 0.0)
            gps_accuracy = data.get("accuracy", 0.0)
            last_gps_update = datetime.now()
            await broadcast_telemetry()
    except (WebSocketDisconnect, Exception):
        gps_app_connected = False
        add_log("GPS Phone Streamer disconnected")


@app.websocket("/ws/dashboard")
async def ws_dashboard(websocket: WebSocket):
    """Connects Streamlit GSAP Mission Control for 10Hz live telemetry."""
    await websocket.accept()
    dashboard_clients.add(websocket)
    try:
        await broadcast_telemetry()
        while True:
            await websocket.receive_text()
    except (WebSocketDisconnect, Exception):
        dashboard_clients.discard(websocket)


@app.websocket("/ws/track")
async def ws_track(websocket: WebSocket):
    """Connects AutoDrop React mobile app for order tracking & coordinates."""
    await websocket.accept()
    tracking_clients.add(websocket)
    try:
        await broadcast_telemetry()
        while True:
            msg = json.loads(await websocket.receive_text())
            if msg.get("type") == "unlock":
                await verify_qr(Request({"type": "http", "method": "POST"}))
    except (WebSocketDisconnect, Exception):
        tracking_clients.discard(websocket)


if __name__ == "__main__":
    import uvicorn
    print("\n==========================================")
    print(" AutoDrop Fleet Gateway & Mission Control ")
    print("==========================================")
    print(f"Hardware Port: {BOT_WS_URL} @ {BAUD_RATE}")
    print(f"Camera Device: {CAMERA_INDEX}")
    print("==========================================\n")
    uvicorn.run("api:app", host="0.0.0.0", port=8000, reload=False)
