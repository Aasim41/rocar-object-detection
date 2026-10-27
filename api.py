from fastapi import FastAPI, Request, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel
from typing import Optional, List, Dict, Any
from collections import deque
import cv2
import numpy as np
import threading
import time
import json
import asyncio
import traceback
from datetime import datetime
import pathlib
_orig_path_exists = pathlib.Path.exists
def _safe_path_exists(self):
    try:
        return _orig_path_exists(self)
    except PermissionError:
        return False
pathlib.Path.exists = _safe_path_exists

from ultralytics import YOLO

# --- Try to import websocket for bot hardware connection ---
try:
    import websocket
    WS_AVAILABLE = True
except ImportError:
    WS_AVAILABLE = False
    print("⚠️  websocket-client not installed. Bot hardware connection disabled.")
    print("   Install with: pip install websocket-client")

from navigation.pipeline import fetch_routes
from navigation.navigate import navigate, calculate_bearing
from navigation.fnpp import to_tuple, calculate_distance
from navigation.lane_follower import LaneFollower
from telemetry_db import telemetry_db

lane_follower = LaneFollower()
state_lock = threading.Lock()
esp32_reconnect_lock = threading.Lock()

# ============================================================
# App Setup
# ============================================================
from contextlib import asynccontextmanager

@asynccontextmanager
async def lifespan(app: FastAPI):
    add_log("🚀 Backend starting up...")
    
    # Start the bot hardware sender queue worker
    threading.Thread(target=esp32_sender_worker, daemon=True).start()
    
    # Auto-reconnect worker handles initial connection + continuous monitoring
    threading.Thread(target=esp32_reconnect_worker, daemon=True).start()
    
    # Start camera capture thread
    threading.Thread(target=camera_loop, daemon=True).start()
    add_log("📷 Camera thread started")
    
    # Start unified YOLO loop (inference + navigation)
    threading.Thread(target=yolo_loop, daemon=True).start()
    add_log("🧠 YOLO loop started")
    
    # Start Arduino listener thread
    threading.Thread(target=esp32_listener, daemon=True).start()
    add_log("👂 Arduino listener thread started")
    
    # Start dashboard broadcast loop (async)
    asyncio.create_task(dashboard_broadcast_loop())
    add_log("📡 WebSocket broadcast loop started")
    
    add_log("✅ All systems initialized!")
    
    yield

app = FastAPI(title="Autonomous Cart Backend", version="2.0", lifespan=lifespan)
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
    action: Optional[str] = None
    cmd: Optional[str] = None
    command: Optional[str] = None

class OrderRequest(BaseModel):
    amount_inr: float

class VerifyRequest(BaseModel):
    razorpay_order_id: str
    razorpay_payment_id: str
    razorpay_signature: str

# ============================================================
# Razorpay Setup
# ============================================================
import razorpay
try:
    rzp_client = razorpay.Client(auth=("rzp_test_TXX8gDzQSotwG0", "utHgCGw506pd4SRWMtk4eYLG"))
except Exception as e:
    print(f"⚠️ Failed to initialize Razorpay: {e}")
    rzp_client = None

@app.post("/api/create_order")
def create_order(req: OrderRequest):
    if not rzp_client:
        return JSONResponse(status_code=500, content={"error": "Razorpay client not configured"})
    amount_paise = int(req.amount_inr * 100)
    data = {
        "amount": amount_paise,
        "currency": "INR",
        "payment_capture": "1"
    }
    try:
        order = rzp_client.order.create(data=data)
        return {"order_id": order["id"], "amount": amount_paise}
    except Exception as e:
        return JSONResponse(status_code=500, content={"error": str(e)})

@app.post("/api/verify_payment")
def verify_payment(req: VerifyRequest):
    if not rzp_client:
        return JSONResponse(status_code=500, content={"error": "Razorpay client not configured"})
    try:
        rzp_client.utility.verify_payment_signature({
            'razorpay_order_id': req.razorpay_order_id,
            'razorpay_payment_id': req.razorpay_payment_id,
            'razorpay_signature': req.razorpay_signature
        })
        return {"status": "success", "message": "Payment verified successfully"}
    except razorpay.errors.SignatureVerificationError:
        return JSONResponse(status_code=400, content={"error": "Invalid payment signature!"})

# ============================================================
# Global State
# ============================================================
current_heading = 0.0
current_route = []
waypoint_index = 0  # Tracks which waypoint the cart is currently heading toward
stored_deliver_points = []
active_phase = "IDLE"  # IDLE, HEADING_TO_SENDER, AWAITING_LOAD, DELIVERING, AWAITING_RETRIEVAL, STANDBY, RETURNING_TO_BASE
cargo_state = "LOCKED"  # LOCKED on boot (matches firmware servo at 0°)
charging_station = {"lat": 0.0, "lng": 0.0}  # Set via API
current_delivery_id = None
shop_return_location = None  # Saved shop location for return trip
current_mode = "autonomous"  # "autonomous" or "manual"
current_status = "INITIALIZING"
latest_log = "System starting up..."
obstacle_detected = False
blocked_until = 0.0  # Time-based lockout: YOLO won't send forward/slow until this timestamp
prev_area_ratio = 0.0  # Tracks object size growth between frames (fast approach detection)
current_distance_cm = 999
log_history = deque(maxlen=100)
esp_commands = deque(maxlen=30)

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

# Active Detour State (Ultrasonic Scanner Sweep Bypass)
detour_active = False
detour_dir = None
detour_start_time = 0.0
last_detour_sweep = 0.0

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
import re
import subprocess

def get_phone_hotspot_ip():
    """Auto-detect phone hotspot IP address from network gateway."""
    try:
        out = subprocess.check_output("ipconfig", text=True)
        m = re.findall(r'(?:Default Gateway[.\s:]+)(?:fe80[^\r\n]+\r?\n\s+)?(\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3})', out)
        if m:
            return m[0]
    except Exception:
        pass
    return "10.194.42.199"

AUTO_PHONE_IP = get_phone_hotspot_ip()
print(f"📡 Auto-detected Phone Hotspot IP: {AUTO_PHONE_IP}")

# Camera
CAMERA_SOURCE = os.environ.get("CAMERA_SOURCE", f"http://{AUTO_PHONE_IP}:8080/video").strip()
# If it's a digit, treat it as an integer (USB webcam index)
if CAMERA_SOURCE.isdigit():
    CAMERA_SOURCE = int(CAMERA_SOURCE)

use_url = isinstance(CAMERA_SOURCE, str)
cap = None
try:
    if not use_url:
        temp_cap = cv2.VideoCapture(CAMERA_SOURCE)
        if temp_cap and temp_cap.isOpened():
            cap = temp_cap
            cap.set(cv2.CAP_PROP_BUFFERSIZE, 1)
        else:
            print("📷 No local webcam detected — running in headless cloud mode.")
except Exception as e:
    print(f"📷 Camera init notice: {e}")

latest_frame = None
annotated_frame = None
annotated_jpeg = None  # Pre-compressed JPEG buffer for zero-latency streaming
frame_lock = threading.Lock()
annotated_lock = threading.Lock()

import queue

# ============================================================
# Bot Hardware Connection (ESP32 direct, USB Serial, TCP Bridge, or WebSocket Relay)
# ============================================================
import socket

ws = None
bot_socket = None
bot_serial = None
is_tcp_bot = False
is_serial_bot = False
ws_connected = False
esp32_cmd_queue = queue.Queue(maxsize=50)
BOT_WS_URL = os.environ.get("BOT_WS_URL", f"tcp://{AUTO_PHONE_IP}:8765")

def process_bot_message(msg: str):
    """Process incoming telemetry line from Arduino/ESP32."""
    global obstacle_detected, blocked_until, current_distance_cm, current_status, battery_level, motor_current, robot_temperature
    global dist_left_cm, dist_center_cm, dist_right_cm
    
    msg = msg.strip()
    if not msg:
        return
        
    if msg == "BLOCKED":
        obstacle_detected = True
        blocked_until = time.time() + 1.5
        current_status = "🚨 OBSTACLE BLOCKED"
        add_log("🚨 Hardware Reflex: Obstacle within 15cm!")
        print(f"🚨 [OBSTACLE DETECTED] Ultrasonic distance is {current_distance_cm} cm (< 18 cm)! Robot emergency brake engaged.")
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
    elif msg.startswith("SWEEP:"):
        try:
            parts = msg.split(":")
            dist_left_cm = int(parts[1])
            dist_center_cm = int(parts[2])
            dist_right_cm = int(parts[3])
            current_distance_cm = dist_center_cm
            add_log(f"🎯 Radar Sweep: Left={dist_left_cm}cm, Center={dist_center_cm}cm, Right={dist_right_cm}cm")
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

def esp32_sender_worker():
    """Background thread that consumes the command queue and sends to bot."""
    global ws, ws_connected, bot_socket, is_tcp_bot, bot_serial, is_serial_bot
    while True:
        cmd = esp32_cmd_queue.get()
        if cmd is None:
            break
        if ws_connected:
            try:
                if is_serial_bot and bot_serial and bot_serial.is_open:
                    bot_serial.write((cmd + "\n").encode("utf-8"))
                    bot_serial.flush()
                    print(f"🚀 [PC -> BOT SERIAL] {cmd.upper()}")
                elif is_tcp_bot and bot_socket:
                    bot_socket.sendall((cmd + "\n").encode("utf-8"))
                    print(f"🚀 [PC -> BOT TCP] {cmd.upper()}")
                elif ws is not None:
                    ws.send(cmd)
                    print(f"🚀 [PC -> BOT WS] {cmd.upper()}")
            except Exception as e:
                print(f"❌ [BOT SEND ERROR] {e}")
                if ws_connected:
                    ws_connected = False
                    if bot_socket:
                        try:
                            bot_socket.close()
                        except Exception:
                            pass
                        bot_socket = None
                    add_log(f"⚠️ Bot send failed: {e}. Reconnecting...")
        esp32_cmd_queue.task_done()

def connect_esp32():
    """Connect to Arduino via Direct USB Serial, Phone-Relay WebSocket, or raw TCP server."""
    global ws, ws_connected, bot_socket, is_tcp_bot, bot_serial, is_serial_bot
    if ws_connected:
        return
        
    url = os.environ.get("BOT_WS_URL")
    if not url:
        current_ip = get_phone_hotspot_ip()
        url = f"tcp://{current_ip}:8765"
    url = url.strip()

    # --- Direct USB Serial Mode (Laptop connected to Arduino via USB Cable) ---
    if url.upper().startswith("COM") or url.startswith("/dev/") or url.upper() in ("AUTO", "AUTO_SERIAL", "SERIAL"):
        try:
            import serial
            import serial.tools.list_ports
            
            port_to_use = url
            if url.upper() in ("AUTO", "AUTO_SERIAL", "SERIAL"):
                ports = list(serial.tools.list_ports.comports())
                usb_ports = [p.device for p in ports if "bluetooth" not in p.description.lower()]
                if usb_ports:
                    port_to_use = usb_ports[0]
                elif ports:
                    port_to_use = ports[0].device
                else:
                    return

            s = serial.Serial(port=port_to_use, baudrate=115200, timeout=0.08)
            time.sleep(1.8)  # Wait for Arduino Uno AVR bootloader reset cycle to complete
            s.reset_input_buffer()
            s.reset_output_buffer()
            
            bot_serial = s
            is_serial_bot = True
            is_tcp_bot = False
            ws = None
            ws_connected = True
            add_log(f"✅ Connected directly to Arduino on USB Serial {port_to_use} (115200 baud)")
            print(f"✅ Connected directly to Arduino on USB Serial {port_to_use} (115200 baud)")
            return
        except Exception as e:
            ws_connected = False
            bot_serial = None
            is_serial_bot = False
            return

    # --- TCP Socket Mode (ESP32 Direct AP or Network TCP) ---
    if url.startswith("tcp://"):
        clean_url = url.replace("tcp://", "")
        # Probe candidates: configured/detected IP first, then ESP32 SoftAP default IP (192.168.4.1:8765)
        candidates = [clean_url]
        if "192.168.4.1:8765" not in candidates:
            candidates.append("192.168.4.1:8765")

        for cand in candidates:
            try:
                if bot_socket:
                    try:
                        bot_socket.close()
                    except Exception:
                        pass
                    bot_socket = None
                host, port_str = cand.split(":")
                s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
                s.settimeout(0.8)  # Fast probe
                s.connect((host, int(port_str)))
                s.settimeout(None)  # Connected - reset to non-timeout blocking
                bot_socket = s
                is_tcp_bot = True
                is_serial_bot = False
                ws = None
                ws_connected = True
                add_log(f"✅ Connected to ESP32 bot hardware via TCP at tcp://{cand}")
                print(f"✅ Connected to ESP32 bot hardware via TCP at tcp://{cand}")
                return
            except Exception:
                if bot_socket:
                    try:
                        bot_socket.close()
                    except Exception:
                        pass
                    bot_socket = None
                ws_connected = False

        # Fallback: check if an ESP32 / Arduino USB serial port is plugged in!
            try:
                import serial
                import serial.tools.list_ports
                ports = list(serial.tools.list_ports.comports())
                usb_ports = [p.device for p in ports if "bluetooth" not in p.description.lower()]
                if usb_ports:
                    port_to_use = usb_ports[0]
                    s = serial.Serial(port=port_to_use, baudrate=115200, timeout=0.08)
                    time.sleep(1.8)
                    s.reset_input_buffer()
                    s.reset_output_buffer()
                    bot_serial = s
                    is_serial_bot = True
                    is_tcp_bot = False
                    ws = None
                    ws_connected = True
                    add_log(f"✅ Auto-switched to USB Serial on {port_to_use}")
                    print(f"✅ Auto-switched to USB Serial on {port_to_use}")
                    return
            except Exception:
                pass
    else:
        # --- WebSocket Relay Mode ---
        if not WS_AVAILABLE:
            return
        try:
            ws_client = websocket.WebSocket()
            ws_client.settimeout(2)
            ws_client.connect(url)
            ws = ws_client
            is_tcp_bot = False
            is_serial_bot = False
            ws_connected = True
            add_log(f"✅ Connected to bot hardware at {url}")
            print(f"✅ Connected to bot hardware at {url}")
            return
        except Exception as e:
            ws_connected = False
            ws = None

def esp32_reconnect_worker():
    """Continuous background worker to ensure auto-reconnect to bot hardware."""
    while True:
        if not ws_connected:
            if esp32_reconnect_lock.acquire(blocking=False):
                try:
                    connect_esp32()
                finally:
                    esp32_reconnect_lock.release()
        time.sleep(2.0)

def send_esp32(cmd: str):
    """Queue a command to Arduino via Serial/WebSocket/TCP without blocking the AI loop."""
    global ws_connected
    
    # Always log the command intent for the dashboard UI (avoid spam)
    cmd_str = f"SENT: {cmd.upper()}"
    if not esp_commands or cmd_str not in esp_commands[-1]:
        ts = datetime.now().strftime("%H:%M:%S")
        esp_commands.append(f"[{ts}] {cmd_str}")
    
    # Store for Webots bridge polling
    global last_webots_cmd, last_webots_steer
    last_webots_cmd = cmd
    
    # If the AI commands left/right manually (e.g. YOLO dodging), override continuous steer.
    if cmd == "left":
        last_webots_steer = -0.3
    elif cmd == "right":
        last_webots_steer = 0.3
    
    if not ws_connected:
        if cmd not in ("stop", "ping"):
            print(f"⚠️ [HARDWARE DROPPED] '{cmd.upper()}' — Bot hardware not connected")
        return
        
    try:
        esp32_cmd_queue.put_nowait(cmd)
    except queue.Full:
        pass # Drop command if queue is backed up (prevents memory leak)

def esp32_listener():
    """Background thread to listen for Arduino messages via Serial or TCP/WebSocket."""
    global ws_connected, bot_socket, is_tcp_bot, ws, bot_serial, is_serial_bot
    tcp_buf = ""
    while True:
        if ws_connected:
            try:
                if is_serial_bot and bot_serial and bot_serial.is_open:
                    line = bot_serial.readline().decode("utf-8", errors="ignore").strip()
                    if line:
                        if not line.startswith("DIST:"):
                            print(f"📥 [BOT -> PC] {line}")
                        process_bot_message(line)
                    else:
                        time.sleep(0.01)
                elif is_tcp_bot and bot_socket:
                    try:
                        chunk = bot_socket.recv(1024).decode("utf-8", errors="ignore")
                    except (socket.timeout, TimeoutError):
                        continue
                    if not chunk:
                        print("⚠️ [TCP] Remote closed connection.")
                        ws_connected = False
                        if bot_socket:
                            try:
                                bot_socket.close()
                            except Exception:
                                pass
                            bot_socket = None
                        continue
                    tcp_buf += chunk
                    while "\n" in tcp_buf:
                        line, tcp_buf = tcp_buf.split("\n", 1)
                        line = line.strip()
                        if line:
                            if not line.startswith("DIST:"):
                                print(f"📥 [BOT -> PC] {line}")
                            process_bot_message(line)
                elif ws is not None:
                    msg = ws.recv()
                    if msg:
                        process_bot_message(msg)
            except Exception:
                time.sleep(0.05)
        else:
            time.sleep(0.5)

# ============================================================
# Logging
# ============================================================
def add_log(message: str):
    global latest_log, log_history
    timestamp = datetime.now().strftime("%H:%M:%S")
    entry = f"[{timestamp}] {message}"
    latest_log = entry
    log_history.append(entry)

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
            # ── Phone IP camera (Zero-latency grabber) ──
            stream_cap = cv2.VideoCapture(CAMERA_SOURCE)
            stream_cap.set(cv2.CAP_PROP_BUFFERSIZE, 1)
            if not stream_cap.isOpened():
                add_log("📷 Cannot open phone stream, retrying...")
                time.sleep(2.0)
                continue

            while True:
                # Fast grab to drop accumulated queue frames in OpenCV
                ret = stream_cap.grab()
                if not ret:
                    add_log("📷 Phone stream dropped, reconnecting...")
                    break
                ret, frame = stream_cap.retrieve()
                if not ret or frame is None:
                    break
                
                if frame.shape[1] != 640 or frame.shape[0] != 480:
                    frame = cv2.resize(frame, (640, 480))
                with frame_lock:
                    latest_frame = frame
                # Do NOT sleep here — let hardware stream pace the loop without buffering lag

            stream_cap.release()
            time.sleep(1.0)
        else:
            # ── Local USB / laptop webcam ──
            global cap
            if cap is None or not cap.isOpened():
                try:
                    idx = int(CAMERA_SOURCE) if str(CAMERA_SOURCE).isdigit() else 0
                    temp_c = cv2.VideoCapture(idx)
                    if temp_c and temp_c.isOpened():
                        temp_c.set(cv2.CAP_PROP_BUFFERSIZE, 1)
                        cap = temp_c
                        add_log(f"📷 Local webcam index {idx} connected!")
                except Exception:
                    pass

            if cap is not None and cap.isOpened():
                ret = cap.grab()
                if ret:
                    _, frame = cap.retrieve()
                    if frame is not None:
                        if frame.shape[1] != 640 or frame.shape[0] != 480:
                            frame = cv2.resize(frame, (640, 480))
                        with frame_lock:
                            latest_frame = frame
                else:
                    time.sleep(0.05)
            else:
                time.sleep(1.0)
            time.sleep(0.01)

# ============================================================
# Background: Autonomous YOLO Loop
# ============================================================
def yolo_loop():
    """Single YOLO loop: runs inference once and caches the annotated frame."""
    global current_status, obstacle_detected, prev_area_ratio, current_distance_cm, annotated_frame, annotated_jpeg
    global current_route, destination_location, source_location, active_phase, cargo_state, waypoint_index
    global scan_servo_angle, obstacle_stopped_since, obstacle_creep_active, obstacle_creep_start
    global detour_active, detour_dir, detour_start_time, last_detour_sweep
    add_log("🤖 YOLO loop started (Low-Latency Mode)")
    last_telemetry_time = 0.0
    last_logged_cmd = ""
    
    while True:
        try:
            with frame_lock:
                frame = latest_frame.copy() if latest_frame is not None else None
            
            if frame is None:
                # If camera is offline, create a lightweight placeholder frame so GPS autonomous navigation continues!
                frame = np.zeros((480, 640, 3), dtype=np.uint8)
                cv2.putText(frame, "VISION OFFLINE - GPS NAVIGATION ACTIVE", (30, 240), cv2.FONT_HERSHEY_SIMPLEX, 0.7, (0, 165, 255), 2)
            
            if current_mode == "manual":
                # In manual mode: bypass YOLO to give maximum FPS and 0ms latency
                with annotated_lock:
                    annotated_frame = frame
                    _, jpeg_buf = cv2.imencode('.jpg', frame, [cv2.IMWRITE_JPEG_QUALITY, 60])
                    annotated_jpeg = jpeg_buf.tobytes()
                time.sleep(0.02)
                continue
                
            # Run YOLO with imgsz=416 for 2x faster inference and minimal lag
            results = model(frame, imgsz=416, conf=0.45, verbose=False)
            ann = results[0].plot()
            
            # ALWAYS process for lane tracking so the dashboard always shows the tracking lines
            lane_cmd, lane_msg, ann, lane_steer = lane_follower.process_frame(ann)
            
            global last_webots_steer
            last_webots_steer = lane_steer
            
            # Cache the annotated frame and pre-encode JPEG in background thread
            with annotated_lock:
                annotated_frame = ann
                _, jpeg_buf = cv2.imencode('.jpg', ann, [cv2.IMWRITE_JPEG_QUALITY, 60])
                annotated_jpeg = jpeg_buf.tobytes()
            
            # Only do navigation logic in autonomous mode
            if current_mode == "autonomous":
                # ── 1. ACTIVE DETOUR IN-FLIGHT EXECUTION ──
                if detour_active:
                    dt = time.time() - detour_start_time
                    if dt < 1.6:
                        send_esp32(detour_dir)
                        current_status = f"↪️ ACTIVE DETOUR ({detour_dir.upper()}) — Bypassing ({dt:.1f}s)"
                        time.sleep(0.04)
                        continue
                    else:
                        # Detour curve burst complete, check if center obstacle is cleared
                        if dist_center_cm > 55:
                            detour_active = False
                            detour_dir = None
                            send_esp32("forward")
                            current_status = "✅ DETOUR CLEAR — Obstacle cleared, resuming path"
                            add_log("Detour maneuver complete. Route resumed.")
                        else:
                            if dt < 2.8:
                                send_esp32(detour_dir)
                                current_status = f"↪️ EXTENDING DETOUR ({detour_dir.upper()})..."
                                time.sleep(0.04)
                                continue
                            else:
                                detour_active = False
                                detour_dir = None

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
                    
                    if is_fast_approaching and total_area_ratio > 0.05:
                        current_status = f"🛑 FAST {closest_name} — EMERGENCY STOP"
                        send_esp32("beep")
                        send_esp32("stop")
                        obstacle_detected = True
                        if obstacle_stopped_since is None:
                            obstacle_stopped_since = time.time()
                            
                    elif dist_cm < 20:
                        current_status = f"🛑 {closest_name} COLLISION ({dist_cm}cm) — STOP"
                        send_esp32("stop")
                        obstacle_detected = True
                        if obstacle_stopped_since is None:
                            obstacle_stopped_since = time.time()
                            
                    elif can_go_around:
                        obstacle_stopped_since = None
                        obstacle_creep_active = False
                        
                        if dist_cm < 80:
                            # Close — slow + hard pivot steer
                            send_esp32("slow")
                            current_status = f"↪️ Dodging {closest_name} {steer_label} ({dist_cm}cm)"
                            send_esp32(steer_dir)
                        elif dist_cm < 200:
                            # Medium range — slow + smooth proportional curve
                            curve_cmd = "curve_left" if steer_dir == "left" else "curve_right"
                            send_esp32("slow")
                            send_esp32(curve_cmd)
                            current_status = f"↪️ Curving around {closest_name} {steer_label} ({dist_cm}cm)"
                        else:
                            # Far — normal speed + smooth curve
                            curve_cmd = "curve_left" if steer_dir == "left" else "curve_right"
                            send_esp32(curve_cmd)
                            current_status = f"↪️ Passing {closest_name} {steer_label}"
                        
                        add_log(f"Avoiding {closest_name} → {steer_label} (gap {gap_ratio:.0%})")
                        obstacle_detected = True
                    
                    elif is_moving_away and dist_cm > 50:
                        obstacle_stopped_since = None
                        obstacle_creep_active = False
                        current_status = f"🚶 Following {closest_name} ({dist_cm}cm, moving away)"
                        send_esp32("slow")
                        obstacle_detected = True
                    
                    elif dist_cm > 250 and total_area_ratio < 0.08:
                        current_status = f"⬆️ {closest_name} far ({dist_cm}cm) — FORWARD"
                        send_esp32("forward")
                        obstacle_detected = False
                        obstacle_stopped_since = None
                        obstacle_creep_active = False
                    
                    else:
                        obstacle_detected = True
                        now_t = time.time()
                        
                        # Trigger Active Ultrasonic Radar Sweep
                        if now_t - last_detour_sweep > 3.0:
                            send_esp32("sweep")
                            last_detour_sweep = now_t
                            current_status = f"🎯 SCANNING RADAR — Sweeping Left & Right for Detour..."
                            add_log(f"Blocked by {closest_name}: Sweeping scanner servo to find bypass.")
                        
                        # Evaluate Left vs Right clearance for active bypass
                        if dist_left_cm >= 55 and (dist_left_cm >= dist_right_cm or dist_right_cm < 45):
                            detour_active = True
                            detour_dir = "curve_left"
                            detour_start_time = now_t
                            send_esp32("curve_left")
                            current_status = f"↪️ DETOUR LEFT (L:{dist_left_cm}cm vs R:{dist_right_cm}cm)"
                            add_log(f"Active Detour: Left is clear ({dist_left_cm}cm) -> Steering curve_left")
                        elif dist_right_cm >= 55 and (dist_right_cm > dist_left_cm or dist_left_cm < 45):
                            detour_active = True
                            detour_dir = "curve_right"
                            detour_start_time = now_t
                            send_esp32("curve_right")
                            current_status = f"↪️ DETOUR RIGHT (R:{dist_right_cm}cm vs L:{dist_left_cm}cm)"
                            add_log(f"Active Detour: Right is clear ({dist_right_cm}cm) -> Steering curve_right")
                        else:
                            current_status = f"🛑 BLOCKED by {closest_name} (L:{dist_left_cm}cm | C:{dist_cm}cm | R:{dist_right_cm}cm)"
                            send_esp32("stop")
                
                else:
                    obstacle_stopped_since = None
                    obstacle_creep_active = False
                    
                    # ── Ultrasonic Blindspot Obstacle Check ──
                    if dist_center_cm <= 38:
                        obstacle_detected = True
                        now_t = time.time()
                        if now_t - last_detour_sweep > 3.0:
                            send_esp32("sweep")
                            last_detour_sweep = now_t
                            current_status = f"🎯 BLINDSPOT OBSTACLE ({dist_center_cm}cm) — Sweeping for Detour..."
                            add_log(f"Obstacle in path ({dist_center_cm}cm): Sweeping scanner servo.")
                        
                        if dist_left_cm >= 55 and (dist_left_cm >= dist_right_cm or dist_right_cm < 45):
                            detour_active = True
                            detour_dir = "curve_left"
                            detour_start_time = now_t
                            send_esp32("curve_left")
                            current_status = f"↪️ DETOUR LEFT (Clearance: {dist_left_cm}cm)"
                            add_log("Bypassing blindspot obstacle via curve_left")
                            continue
                        elif dist_right_cm >= 55 and (dist_right_cm > dist_left_cm or dist_left_cm < 45):
                            detour_active = True
                            detour_dir = "curve_right"
                            detour_start_time = now_t
                            send_esp32("curve_right")
                            current_status = f"↪️ DETOUR RIGHT (Clearance: {dist_right_cm}cm)"
                            add_log("Bypassing blindspot obstacle via curve_right")
                            continue
                        else:
                            current_status = f"🛑 ULTRASONIC STOP ({dist_center_cm}cm) — Path Blocked"
                            send_esp32("stop")
                            continue
                    
                    if active_phase in ["IDLE", "AWAITING_LOAD", "AWAITING_RETRIEVAL", "STANDBY"]:
                        send_esp32("stop")
                        if active_phase == "IDLE":
                            current_status = "⏸️ IDLE — Waiting for order"
                        elif active_phase == "AWAITING_LOAD":
                            current_status = "📦 Waiting for sender to load"
                        elif active_phase == "AWAITING_RETRIEVAL":
                            current_status = "🎯 Waiting for receiver to retrieve"
                        elif active_phase == "STANDBY":
                            current_status = "⏱️ STANDBY — Waiting for next order"
                        continue
                    
                    nav_cmd = lane_cmd
                    nav_msg = lane_msg
                    
                    # 2. Check if GPS demands a specific intersection turn
                    if current_route and live_location:
                        try:
                            from navigation.fnpp import calculate_distance, to_tuple
                            
                            target_loc = None
                            if active_phase == "HEADING_TO_SENDER":
                                target_loc = source_location
                            elif active_phase == "DELIVERING":
                                target_loc = destination_location
                            elif active_phase == "RETURNING_TO_BASE":
                                target_loc = charging_station
                                
                            if target_loc:
                                dist_to_dest = calculate_distance(to_tuple(live_location), to_tuple(target_loc))
                                
                                if dist_to_dest < 5.0:  # Within 5 meters
                                    nav_cmd = "stop"
                                    send_esp32("stop")
                                    
                                    if active_phase == "HEADING_TO_SENDER":
                                        nav_msg = "🏪 AT SENDER → WAITING FOR LOAD"
                                        current_status = nav_msg
                                        active_phase = "AWAITING_LOAD"
                                        current_route = []
                                        waypoint_index = 0
                                    elif active_phase == "DELIVERING":
                                        nav_msg = "🎯 DESTINATION REACHED → WAITING FOR RETRIEVAL"
                                        current_status = nav_msg
                                        active_phase = "AWAITING_RETRIEVAL"
                                        current_route = []
                                        waypoint_index = 0
                                    elif active_phase == "RETURNING_TO_BASE":
                                        nav_msg = "🏠 RETURNED TO BASE → IDLE"
                                        current_status = nav_msg
                                        add_log("✅ Cart has returned to base!")
                                        active_phase = "IDLE"
                                        current_route = []
                                        waypoint_index = 0
                                else:
                                    nav_result = navigate(current_heading, live_location, current_route, waypoint_index)
                                    gps_cmd = nav_result.get("command", "F")
                                    waypoint_index = nav_result.get("waypoint_index", waypoint_index)
                                    
                                    # Check if the progressive waypoint tracker reached the final destination waypoint
                                    if nav_result.get("route_complete") or gps_cmd == "STOP":
                                        nav_cmd = "stop"
                                        send_esp32("stop")
                                        if active_phase == "HEADING_TO_SENDER":
                                            nav_msg = "🏪 AT SENDER → WAITING FOR LOAD"
                                            current_status = nav_msg
                                            active_phase = "AWAITING_LOAD"
                                            current_route = []
                                            waypoint_index = 0
                                        elif active_phase == "DELIVERING":
                                            nav_msg = "🎯 DESTINATION REACHED → WAITING FOR RETRIEVAL"
                                            current_status = nav_msg
                                            active_phase = "AWAITING_RETRIEVAL"
                                            current_route = []
                                            waypoint_index = 0
                                        elif active_phase == "RETURNING_TO_BASE":
                                            nav_msg = "🏠 RETURNED TO BASE → IDLE"
                                            current_status = nav_msg
                                            add_log("✅ Cart has returned to base!")
                                            active_phase = "IDLE"
                                            current_route = []
                                            waypoint_index = 0
                                    else:
                                        wp_total = len(current_route)
                                        if waypoint_index < wp_total:
                                            wp_dist = calculate_distance(to_tuple(live_location), to_tuple(current_route[min(waypoint_index, wp_total - 1)]))
                                            nav_msg = f"GPS WP {waypoint_index+1}/{wp_total} ({wp_dist:.0f}m) → {gps_cmd}"
                                        
                                        cmd_map = {
                                            "F": "forward",
                                            "SL": "curve_left",   # Smooth proportional curve left
                                            "SR": "curve_right",  # Smooth proportional curve right
                                            "L": "left",          # Sharp pivot turn at 90deg junction
                                            "R": "right",         # Sharp pivot turn at 90deg junction
                                            "STOP": "stop"
                                        }
                                        if not gps_cmd.startswith("steer:"):
                                            gps_cmd = cmd_map.get(gps_cmd, "forward")
                                        
                                        # At intersections, GPS ALWAYS overrides lane following; also let GPS proceed if lane follower has no visual line
                                        if lane_follower.is_intersection or gps_cmd != "forward" or lane_cmd == "stop":
                                            nav_cmd = gps_cmd
                                            junction_tag = " [JUNCTION]" if lane_follower.is_intersection else ""
                                            nav_msg = f"GPS Steering: {nav_cmd.upper()} (WP {waypoint_index+1}/{wp_total}){junction_tag}"
                        except Exception as e:
                            print(f"Navigation error: {e}")
                            
                    if dist_center_cm < 400:
                        current_distance_cm = dist_center_cm

                    # ── Proportional Braking (Smart Distance Slowdown) ──
                    if 18 < dist_center_cm <= 65 and nav_cmd == "forward":
                        nav_cmd = "slow"
                        current_status = f"🟡 PROPORTIONAL BRAKE ({dist_center_cm}cm) — Decelerating to SLOW"
                    elif dist_center_cm <= 18 and nav_cmd in ("forward", "slow"):
                        nav_cmd = "stop"
                        current_status = f"🛑 PROXIMITY STOP ({dist_center_cm}cm)"
                    else:
                        if current_status != f"✅ PATH CLEAR → {nav_cmd.upper()}":
                            add_log(f"✅ {nav_msg}")
                        current_status = f"✅ PATH CLEAR → {nav_cmd.upper()}"
                    
                    # ── BLOCKED lockout: don't override Arduino's emergency stop ──
                    if (time.time() < blocked_until or dist_center_cm <= 18) and nav_cmd in ("forward", "slow"):
                        send_esp32("stop")
                        current_status = "🚨 BLOCKED LOCKOUT — waiting for clearance"
                    else:
                        # ── Scan Servo Reset ──
                        target_scan_angle = "scan_center"
                        if "left" in nav_cmd: target_scan_angle = "scan_left"
                        elif "right" in nav_cmd: target_scan_angle = "scan_right"
                        
                        if scan_servo_angle != target_scan_angle:
                            send_esp32(target_scan_angle)
                            scan_servo_angle = target_scan_angle
                        # ── Send the navigation command ──
                        send_esp32(nav_cmd)
                        # Keep continuous steer for Webots
                        if nav_cmd == "forward":
                            last_webots_steer = lane_steer
                        obstacle_detected = False

                        # ── Blackbox Mission Telemetry Logging (SQLite) ──
                        now_t = time.time()
                        if now_t - last_telemetry_time >= 1.0 or nav_cmd != last_logged_cmd:
                            last_telemetry_time = now_t
                            last_logged_cmd = nav_cmd
                            try:
                                telemetry_db.log_telemetry(
                                    delivery_id=current_delivery_id or "idle",
                                    phase=active_phase,
                                    mode=current_mode,
                                    lat=live_location["lat"] if live_location else None,
                                    lng=live_location["lng"] if live_location else None,
                                    heading=current_heading,
                                    speed=gps_speed,
                                    motor_cmd=nav_cmd,
                                    ultrasonic_cm=current_distance_cm,
                                    obstacle_detected=obstacle_detected,
                                    obstacle_name=closest_name if obstacle_detected else None,
                                    cte=lane_steer,
                                    steer_bias=0.0
                                )
                            except Exception:
                                pass
            
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
    """Stream pre-annotated YOLO frames as MJPEG with zero latency."""
    async def generate():
        last_sent = None
        while True:
            jpeg = annotated_jpeg
            if jpeg is not None and jpeg is not last_sent:
                last_sent = jpeg
                yield (b'--frame\r\n'
                       b'Content-Type: image/jpeg\r\n\r\n' + jpeg + b'\r\n')
            await asyncio.sleep(0.015)
    
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

@app.get("/drive")
def get_manual_drive():
    """Serves the ultra-low latency Manual Drive web controller."""
    try:
        with open("manual_drive.html", "r", encoding="utf-8") as f:
            return HTMLResponse(content=f.read())
    except FileNotFoundError:
        return HTMLResponse(content="<h1>manual_drive.html not found!</h1>", status_code=404)

@app.get("/status")
async def get_status():
    """Get current bot telemetry."""
    return {
        "status": current_status,
        "mode": current_mode,
        "active_phase": active_phase,
        "current_delivery_id": current_delivery_id,
        "battery_level": battery_level,
        "motor_current": motor_current,
        "robot_temperature": robot_temperature,
        "last_gps_update": last_gps_update.isoformat() if last_gps_update else None,
        "cargo_state": cargo_state,
        "latestLog": latest_log,
        "obstacle_detected": obstacle_detected,
        "distance_cm": current_distance_cm,
        "dist_left_cm": dist_left_cm,
        "dist_center_cm": dist_center_cm,
        "dist_right_cm": dist_right_cm,
        "esp32_connected": ws_connected,
        "gps_app_connected": gps_app_connected,
        "gps_speed": gps_speed,
        "gps_accuracy": gps_accuracy,
        "tracking_clients": len(tracking_clients),
        "camera_active": latest_frame is not None,
        "log_history": list(log_history)[-20:],
        "esp_commands": list(esp_commands)[-20:],
        "map_data": {
            "live_location": live_location,
            "source": source_location,
            "destination": destination_location,
            "charging_station": charging_station
        }
    }

@app.post("/set_mode")
async def set_mode(req: ModeRequest):
    """Toggle between autonomous and manual mode."""
    global current_mode, current_status, obstacle_detected, obstacle_stopped_since, obstacle_creep_active
    current_mode = req.mode
    if current_mode == "manual":
        # Flush any queued autonomous commands to prevent leakage
        while not esp32_cmd_queue.empty():
            try:
                esp32_cmd_queue.get_nowait()
            except queue.Empty:
                break
        send_esp32("stop")
        obstacle_detected = False
        obstacle_stopped_since = None
        obstacle_creep_active = False
        current_status = "🎮 MANUAL OVERRIDE"
        add_log("🚨 Manual Override Activated")
    else:
        current_status = "🔍 SEARCHING"
        add_log("🤖 Autonomous Mode Resumed")
    return {"status": "success", "mode": current_mode}

@app.post("/backend/manual_control")
async def manual_control(req: ControlRequest):
    global cargo_state, current_mode
    if current_mode != "manual":
        current_mode = "manual"
        while not esp32_cmd_queue.empty():
            try:
                esp32_cmd_queue.get_nowait()
            except queue.Empty:
                break
        add_log("🎮 Switched to MANUAL mode from controller input")
    
    raw = req.action or req.cmd or req.command or ""
    cmd = raw.lower().strip()
    if cmd == "open_lid": cmd = "unlock"
    if cmd == "close_lid": cmd = "lock"
    
    allowed = [
        "forward", "backward", "reverse", "left", "right", "slow",
        "curve_left", "curve_right", "swing_left", "swing_right", "sweep",
        "stop", "lock", "unlock", "beep",
        "scan_left", "scan_center", "scan_right", "ping"
    ]
    if cmd in allowed or cmd.startswith("steer:"):
        send_esp32(cmd)
        if cmd == "lock":
            cargo_state = "LOCKED"
        elif cmd == "unlock":
            cargo_state = "OPEN"
        add_log(f"Manual override: {cmd.upper()}")
        return {"status": "success", "command": cmd, "mode": current_mode}
    return JSONResponse(status_code=400, content={"status": "error", "message": f"Invalid command: {cmd}"})

@app.post("/backend/beep")
async def trigger_beep():
    send_esp32("beep")
    add_log("🔔 Cart Bell / Piezo Buzzer Sounded")
    return {"status": "success", "message": "beep sent"}

@app.get("/backend/telemetry/stats")
async def get_telemetry_stats():
    """Retrieve blackbox telemetry statistics and persistent cache status."""
    return telemetry_db.get_stats()

@app.post("/backend/return_to_base")
async def trigger_return_to_base():
    global active_phase, current_route, waypoint_index, stored_deliver_points
    active_phase = "RETURNING_TO_BASE"
    start_lat = live_location["lat"] if live_location else (destination_location.get("lat") or 0.0)
    start_lng = live_location["lng"] if live_location else (destination_location.get("lng") or 0.0)
    
    # Priority 1: Retrace the delivery route backwards to the pickup/sender location!
    if stored_deliver_points and len(stored_deliver_points) > 1:
        current_route = list(reversed(stored_deliver_points))
        waypoint_index = 0
        add_log(f"🏠 Returning to Sender (Pickup) along reversed Google Maps route ({len(current_route)} waypoints)")
    elif charging_station.get("lat") and charging_station.get("lng"):
        try:
            # Check route cache first
            cached_rtb = telemetry_db.get_cached_route((start_lat, start_lng), (charging_station["lat"], charging_station["lng"]))
            if cached_rtb:
                current_route = cached_rtb
            else:
                kart_obj = KartCoordinates(latitude=start_lat, longitude=start_lng, heading=current_heading)
                base_obj = Coordinates(latitude=charging_station["lat"], longitude=charging_station["lng"])
                routes = fetch_routes(kart_obj, base_obj, base_obj)
                current_route = routes.get('receive_points', [])
                if current_route:
                    telemetry_db.save_cached_route((start_lat, start_lng), (charging_station["lat"], charging_station["lng"]), current_route)
            waypoint_index = 0
            add_log(f"🏠 1-Click Override: Returning to base. Route points: {len(current_route)}")
        except Exception as e:
            add_log(f"⚠️ Return to base routing error: {e}")
    else:
        add_log("🏠 1-Click Override: Returning to base (No charging station coordinate configured)")
        send_esp32("stop")
    await broadcast_to_dashboard()
    await broadcast_to_tracking()
    return {"status": "success", "phase": active_phase, "waypoints": len(current_route)}

@app.post("/backend/set_routing_engine")
async def set_routing(req: Request):
    """Set the routing engine to google or self."""
    body = await req.body()
    try:
        data = json.loads(body.decode("utf-8"))
        engine = data.get("engine", "google")
        from navigation.pipeline import set_routing_engine
        set_routing_engine(engine)
        add_log(f"🔄 Routing Engine changed to: {engine.upper()}")
        return {"status": "success", "engine": engine}
    except Exception as e:
        return JSONResponse(status_code=400, content={"status": "error", "message": str(e)})

@app.post("/backend/set_charging_station")
async def set_charging_station(request: Request):
    global charging_station
    body = await request.json()
    charging_station = {"lat": body["lat"], "lng": body["lng"]}
    return {"status": "ok", "charging_station": charging_station}

@app.post("/backend/set_route")
async def set_route_endpoint(request: Request):
    """Directly ingest Google Maps route points from AutoDrop app for live navigation."""
    global current_route, waypoint_index, stored_deliver_points, source_location, destination_location
    try:
        body = await request.json()
        pts = body.get("route_points") or body.get("route") or []
        if pts:
            deliver_pts = [{"latitude": p["lat"], "longitude": p["lng"]} for p in pts if "lat" in p and "lng" in p]
            if deliver_pts:
                stored_deliver_points = deliver_pts.copy()
                if active_phase == "DELIVERING" or not current_route:
                    current_route = deliver_pts
                    waypoint_index = 0
                
                # Cache the route if coordinates are present
                if source_location.get("lat") and destination_location.get("lat"):
                    telemetry_db.save_cached_route(
                        (source_location["lat"], source_location["lng"]),
                        (destination_location["lat"], destination_location["lng"]),
                        deliver_pts
                    )
                add_log(f"🗺️ AutoDrop Sync: Ingested & cached {len(deliver_pts)} Google Maps route points!")
                await broadcast_to_tracking()
                return {"status": "ok", "waypoints": len(deliver_pts)}
        return JSONResponse(status_code=400, content={"status": "error", "message": "No valid route points provided"})
    except Exception as e:
        return JSONResponse(status_code=500, content={"status": "error", "message": str(e)})


@app.post("/backend/new_delivery")
async def new_delivery(request: Request):
    global active_phase, source_location, destination_location, current_delivery_id, current_route, waypoint_index, charging_station, stored_deliver_points
    body = await request.json()
    
    pickup = body.get("pickup", {})
    dropoff = body.get("dropoff", {})
    current_delivery_id = body.get("delivery_id", "")
    
    source_location = {"lat": pickup.get("lat", 0), "lng": pickup.get("lng", 0)}
    destination_location = {"lat": dropoff.get("lat", 0), "lng": dropoff.get("lng", 0)}
    
    # Preserve or configure charging_station (Base Station)
    base = body.get("base") or body.get("charging_station")
    if base and base.get("lat") and base.get("lng"):
        charging_station = {"lat": float(base["lat"]), "lng": float(base["lng"])}
    elif not charging_station or (charging_station.get("lat") == 0.0 and charging_station.get("lng") == 0.0):
        # Default charging dock if not configured
        if live_location and live_location.get("lat") and live_location.get("lng"):
            charging_station = {"lat": float(live_location["lat"]), "lng": float(live_location["lng"])}
        else:
            # Default base station at JUET Campus dock
            charging_station = {"lat": 24.4332, "lng": 77.1585}
    
    start_lat = live_location["lat"] if (live_location and live_location.get("lat")) else charging_station["lat"]
    start_lng = live_location["lng"] if (live_location and live_location.get("lng")) else charging_station["lng"]

    # 1. Accept Google Maps route points directly from AutoDrop app if provided
    app_route = body.get("route_points") or body.get("route") or []
    deliver_pts = []
    if app_route:
        deliver_pts = [{"latitude": p["lat"], "longitude": p["lng"]} for p in app_route if "lat" in p and "lng" in p]
        if deliver_pts:
            telemetry_db.save_cached_route(
                (source_location["lat"], source_location["lng"]),
                (destination_location["lat"], destination_location["lng"]),
                deliver_pts
            )
            add_log(f"🗺️ Received & Cached {len(deliver_pts)} Google Maps route points from AutoDrop app!")

    # 2. Check persistent SQLite cache for repeat addresses if not sent
    if not deliver_pts:
        cached = telemetry_db.get_cached_route(
            (source_location["lat"], source_location["lng"]),
            (destination_location["lat"], destination_location["lng"])
        )
        if cached:
            deliver_pts = cached
            add_log(f"⚡ Loaded {len(deliver_pts)} waypoints from Persistent Route Cache!")

    # 3. Check cache / fetch route to sender
    cached_pickup = telemetry_db.get_cached_route(
        (start_lat, start_lng),
        (source_location["lat"], source_location["lng"])
    )
    receive_pts = cached_pickup if cached_pickup else []

    if not receive_pts or not deliver_pts:
        kart_obj = KartCoordinates(latitude=start_lat, longitude=start_lng, heading=current_heading)
        market_obj = Coordinates(latitude=source_location["lat"], longitude=source_location["lng"])
        del_obj = Coordinates(latitude=destination_location["lat"], longitude=destination_location["lng"])
        
        routes = fetch_routes(kart_obj, market_obj, del_obj)
        if not receive_pts:
            receive_pts = routes.get('receive_points', [])
        if not deliver_pts:
            deliver_pts = routes.get('deliver_points', [])

    stored_deliver_points = deliver_pts.copy()

    dist_to_pickup = calculate_distance((start_lat, start_lng), (source_location["lat"], source_location["lng"]))
    if dist_to_pickup < 10.0 or not receive_pts:
        current_route = deliver_pts if deliver_pts else receive_pts
        active_phase = "AWAITING_LOAD"
        add_log(f"📍 New Delivery: Cart at pickup. Delivery route points: {len(current_route)}")
    else:
        current_route = receive_pts
        active_phase = "HEADING_TO_SENDER"
        add_log(f"📍 New Delivery: Heading to sender. Route points: {len(current_route)}")

    waypoint_index = 0
    await broadcast_to_dashboard()
    await broadcast_to_tracking()
    return {"status": "ok", "delivery_id": current_delivery_id, "phase": active_phase, "waypoints": len(current_route)}

@app.api_route("/backend/verify_qr", methods=["GET", "POST"])
async def verify_qr(request: Request):
    global active_phase, cargo_state
    if request.method == "POST":
        try:
            body = await request.json()
        except Exception:
            body = {}
    else:
        body = dict(request.query_params)
        
    cart_qr = body.get("cart_id") or body.get("cartId") or "cart_01"
    action = body.get("action", "")
    
    cargo_state = "UNLOCKED"
    send_esp32("unlock")
    
    is_browser = request.method == "GET" and "text/html" in request.headers.get("accept", "")
    
    if action == "load":
        if active_phase == "HEADING_TO_SENDER":
            active_phase = "AWAITING_LOAD"
        add_log(f"🔓 Cart unlocked for loading (QR: {cart_qr})")
        await broadcast_to_dashboard()
        await broadcast_to_tracking()
        resp_data = {"status": "unlocked", "action": "load", "phase": active_phase, "message": "Cart unlocked for loading"}
    elif action == "retrieve":
        if active_phase == "DELIVERING":
            active_phase = "AWAITING_RETRIEVAL"
        add_log(f"🔓 Cart unlocked for retrieval (QR: {cart_qr})")
        await broadcast_to_dashboard()
        await broadcast_to_tracking()
        resp_data = {"status": "unlocked", "action": "retrieve", "phase": active_phase, "message": "Cart unlocked for retrieval"}
    else:
        add_log(f"🔓 Cart bypass unlocked via QR scan ({cart_qr})")
        await broadcast_to_dashboard()
        await broadcast_to_tracking()
        resp_data = {"status": "unlocked", "action": "unlock", "phase": active_phase, "message": "Cart latch unlocked"}

    if is_browser:
        html = f"""
        <!DOCTYPE html>
        <html>
        <head>
            <meta name="viewport" content="width=device-width, initial-scale=1.0">
            <title>AutoDrop Cargo Unlocked</title>
            <style>
                body {{ background: #09090b; color: #fff; font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif; display: flex; flex-direction: column; align-items: center; justify-content: center; height: 100vh; margin: 0; padding: 20px; box-sizing: border-box; text-align: center; }}
                .card {{ background: #18181b; border: 1px solid #27272a; border-radius: 28px; padding: 36px 24px; max-width: 380px; width: 100%; box-shadow: 0 25px 50px -12px rgba(0,0,0,0.7); }}
                .icon {{ font-size: 56px; margin-bottom: 16px; animation: bounce 1s infinite alternate; }}
                @keyframes bounce {{ from {{ transform: translateY(0); }} to {{ transform: translateY(-8px); }} }}
                h1 {{ font-size: 22px; font-weight: 800; margin: 0 0 8px; color: #4ade80; letter-spacing: -0.5px; }}
                p {{ font-size: 14px; color: #a1a1aa; line-height: 1.5; margin: 0 0 24px; }}
                .badge {{ display: inline-block; background: rgba(74, 222, 128, 0.15); color: #4ade80; border: 1px solid rgba(74, 222, 128, 0.3); padding: 6px 14px; border-radius: 999px; font-size: 12px; font-weight: 700; margin-bottom: 18px; }}
                .tag {{ font-size: 12px; color: #71717a; font-family: monospace; }}
            </style>
        </head>
        <body>
            <div class="card">
                <div class="icon">🔓</div>
                <div class="badge">SERVO ROTATED 90°</div>
                <h1>Cargo Bay Unlocked!</h1>
                <p>The compartment lid is open. Please retrieve or load your package now.</p>
                <div class="tag">AutoDrop Fleet • {cart_qr.upper()}</div>
            </div>
        </body>
        </html>
        """
        return HTMLResponse(content=html)
    return resp_data

@app.post("/backend/dispatch")
async def dispatch_cart(request: Request):
    global active_phase, cargo_state, current_route, waypoint_index, stored_deliver_points
    cargo_state = "LOCKED"
    send_esp32("lock")
    
    # Use the Google Maps delivery route
    if stored_deliver_points:
        current_route = stored_deliver_points.copy()
    else:
        start_lat = live_location["lat"] if live_location else source_location["lat"]
        start_lng = live_location["lng"] if live_location else source_location["lng"]
        cached = telemetry_db.get_cached_route((start_lat, start_lng), (destination_location["lat"], destination_location["lng"]))
        if cached:
            current_route = cached
        else:
            kart_obj = KartCoordinates(latitude=start_lat, longitude=start_lng, heading=current_heading)
            del_obj = Coordinates(latitude=destination_location["lat"], longitude=destination_location["lng"])
            routes = fetch_routes(kart_obj, del_obj, del_obj)
            current_route = routes.get('receive_points', [])
            
    waypoint_index = 0
    active_phase = "DELIVERING"
    add_log(f"📍 Dispatched! Following Google Maps route to destination ({len(current_route)} waypoints)")
    await broadcast_to_dashboard()
    await broadcast_to_tracking()
    return {"status": "dispatched", "phase": active_phase, "waypoints": len(current_route)}

@app.post("/backend/complete_retrieval")
async def complete_retrieval(request: Request):
    global active_phase, cargo_state
    cargo_state = "LOCKED"
    send_esp32("lock")
    add_log("📦 Retrieval complete! Locking cargo bay and initiating autonomous return to base...")
    active_phase = "STANDBY"
    await broadcast_to_dashboard()
    await broadcast_to_tracking()
    asyncio.create_task(auto_return_after_retrieval())
    return {"status": "returning", "message": "Package retrieved. Returning to Charging Base."}

async def auto_return_after_retrieval():
    global active_phase, current_route, waypoint_index, stored_deliver_points, charging_station
    # 4-second safety pause so user has retrieved hands/package and stepped clear
    await asyncio.sleep(4)
    active_phase = "RETURNING_TO_BASE"
    add_log("🚀 Auto-return initiated: Cart departing destination for Charging Station Dock...")
    
    # 1. Reverse route from dropoff back to base or sender
    if stored_deliver_points and len(stored_deliver_points) > 1:
        current_route = list(reversed(stored_deliver_points))
        waypoint_index = 0
        add_log(f"🏠 Following reverse waypoint trajectory back to Base ({len(current_route)} waypoints)")
    elif charging_station.get("lat") and charging_station.get("lng"):
        start_lat = live_location["lat"] if live_location else destination_location["lat"]
        start_lng = live_location["lng"] if live_location else destination_location["lng"]
        kart_obj = KartCoordinates(latitude=start_lat, longitude=start_lng, heading=current_heading)
        base_obj = Coordinates(latitude=charging_station["lat"], longitude=charging_station["lng"])
        routes = fetch_routes(kart_obj, base_obj, base_obj)
        current_route = routes.get('receive_points', [])
        waypoint_index = 0
        add_log(f"🏠 Navigation route planned to Base charging station ({len(current_route)} waypoints)")
        
    await broadcast_to_dashboard()
    await broadcast_to_tracking()

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
    active_phase = "AWAITING_PACKING"
    waypoint_index = 0
    shop_return_location = source_location
    
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
    """Triggered when the user enters the OTP. After unlocking, cart returns to shop."""
    global current_status, active_phase, cargo_state
    
    send_esp32("unlock")
    with state_lock:
        cargo_state = "OPEN"
        current_status = "🔓 CARGO UNLOCKED → Customer collecting order..."
        # Keep active_phase as DELIVERY so no new orders are accepted yet
    add_log("🔓 Customer unlocked cargo. Waiting 30s for collection...")
    
    async def return_to_shop_task():
        global current_status, current_route, active_phase, cargo_state, source_location, destination_location, waypoint_index
        
        # Wait for customer to collect the order, then lock and return
        await asyncio.sleep(30)
        
        send_esp32("lock")
        with state_lock:
            cargo_state = "LOCKED"
        add_log("🔒 Cargo locked. Preparing return route to shop...")
        
        # Build return route
        if shop_return_location and live_location:
            try:
                from navigation.pipeline import fetch_routes
                kart_obj = KartCoordinates(latitude=live_location["lat"], longitude=live_location["lng"], heading=current_heading)
                shop_obj = Coordinates(latitude=shop_return_location["lat"], longitude=shop_return_location["lng"])
                
                # Reuse fetch_routes but just for the return leg
                return_routes = fetch_routes(kart_obj, shop_obj, shop_obj)
                return_points = return_routes.get("receive_points", [])
                
                with state_lock:
                    current_route = return_points
                    waypoint_index = 0
                    destination_location = shop_return_location
                    source_location = None
                    active_phase = "RETURNING"
                    current_status = f"🏠 RETURNING TO SHOP ({len(return_points)} waypoints)"
                add_log(f"🏠 Return route calculated: {len(return_points)} waypoints back to shop")
            except Exception as e:
                add_log(f"⚠️ Could not calculate return route: {e}")
                with state_lock:
                    active_phase = "IDLE"
                    current_status = "⏸️ IDLE — Return route failed"
        else:
            add_log("⚠️ No shop location saved — cannot return")
            with state_lock:
                active_phase = "IDLE"

    # Start the return task in the background so the HTTP request completes instantly
    asyncio.create_task(return_to_shop_task())
    
    return {"status": "success", "message": "Unlocked and returning to shop"}

# ============================================================
# WebSocket Broadcast Helpers
# ============================================================

async def broadcast_to_dashboard():
    """Push full telemetry to all connected dashboard clients."""
    if not dashboard_clients:
        return

    # Calculate accurate Path Distance ETA
    eta_seconds = None
    if live_location and destination_location:
        try:
            total_dist_meters = 0.0
            if current_route and waypoint_index < len(current_route):
                curr = to_tuple(live_location)
                for i in range(waypoint_index, len(current_route)):
                    nxt = to_tuple(current_route[i])
                    total_dist_meters += calculate_distance(curr, nxt)
                    curr = nxt
                total_dist_meters += calculate_distance(curr, to_tuple(destination_location))
            else:
                total_dist_meters = calculate_distance(
                    to_tuple(live_location),
                    to_tuple(destination_location)
                )
            effective_speed_kmh = gps_speed if gps_speed > 0.5 else 3.0
            eta_seconds = int(total_dist_meters / (effective_speed_kmh / 3.6))
        except Exception:
            pass

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
        "dist_left_cm": dist_left_cm,
        "dist_center_cm": dist_center_cm,
        "dist_right_cm": dist_right_cm,
        "esp32_connected": ws_connected,
        "gps_app_connected": gps_app_connected,
        "gps_speed": gps_speed,
        "gps_accuracy": gps_accuracy,
        "eta_seconds": eta_seconds,
        "tracking_clients": len(tracking_clients),
        "camera_active": latest_frame is not None,
        "log_history": list(log_history)[-20:],
        "esp_commands": list(esp_commands)[-20:],
        "map_data": {
            "live_location": live_location,
            "source": source_location,
            "destination": destination_location,
            "charging_station": charging_station
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
    
    # Calculate accurate Path Distance ETA
    eta_seconds = None
    if live_location and destination_location:
        try:
            # 1. Calculate true remaining path distance instead of straight line
            total_dist_meters = 0.0
            if current_route and waypoint_index < len(current_route):
                # Distance from current loc to the next waypoint
                curr = to_tuple(live_location)
                for i in range(waypoint_index, len(current_route)):
                    nxt = to_tuple(current_route[i])
                    total_dist_meters += calculate_distance(curr, nxt)
                    curr = nxt
                # Add final leg from last waypoint to destination
                total_dist_meters += calculate_distance(curr, to_tuple(destination_location))
            else:
                # Fallback to straight line if no route
                total_dist_meters = calculate_distance(
                    to_tuple(live_location),
                    to_tuple(destination_location)
                )

            # 2. Prevent wild ETA swings by using a smoothed speed or average walking speed fallback (3.0 km/h)
            effective_speed_kmh = gps_speed if gps_speed > 0.5 else 3.0
            
            # 3. Time = Distance / Speed
            eta_seconds = int(total_dist_meters / (effective_speed_kmh / 3.6))
        except Exception as e:
            add_log(f"ETA Calc Error: {str(e)}")
            pass
    
    data = {
        "type": "location_update",
        "cart": live_location,
        "source": source_location,
        "destination": destination_location,
        "charging_station": charging_station,
        "phase": active_phase,
        "cargo_state": cargo_state,
        "speed": gps_speed,
        "eta_seconds": eta_seconds,
        "battery_level": battery_level,
        "motor_current": motor_current,
        "distance_cm": current_distance_cm,
        "obstacle_detected": obstacle_detected,
        "esp32_connected": ws_connected,
        "camera_active": latest_frame is not None,
        "gps_app_connected": gps_app_connected,
        "delivery_id": current_delivery_id,
        "route_points": [{"lat": p.get("latitude", p.get("lat", 0)), "lng": p.get("longitude", p.get("lng", 0))} for p in current_route if isinstance(p, dict)] if current_route else []
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
            
            # Apply EMA smoothing to speed (alpha = 0.3)
            if gps_speed == 0:
                gps_speed = speed
            else:
                gps_speed = (0.3 * speed) + (0.7 * gps_speed)
                
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
            
            # ── Heading: always accept phone compass when available ──
            if "heading" in data and data["heading"] is not None:
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
                
                # Since the cart is always at the shop initially, we skip PICKUP
                # and go straight to AWAITING_PACKING (waiting for shopkeeper to load).
                current_route = [{"latitude": p["lat"], "longitude": p["lng"]} for p in route_points]
                stored_deliver_points = current_route.copy()
                waypoint_index = 0
                active_phase = "AWAITING_PACKING"
                shop_return_location = source_location
                current_status = "📍 NEW ORDER → Waiting for shopkeeper to pack"
                
                # We open the cargo lock so the shopkeeper can load it
                send_esp32("unlock")
                cargo_state = "OPEN"
                
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
# Startup completed via lifespan above
# ============================================================

if __name__ == "__main__":
    import uvicorn
    port = int(os.environ.get("PORT", 8000))
    uvicorn.run(app, host="0.0.0.0", port=port)
