# Autonomous Delivery Cart (RoCAR)

Autonomous delivery bot system featuring YOLOv8-based obstacle detection, adaptive lane following, dual-engine GPS waypoint routing, and zero-latency smartphone OTG motor control.

---

## Architecture Overview

```
                      +-----------------------------+
                      |   Laptop (Brain / Server)   |
                      |   - FastAPI Backend         |
                      |   - YOLOv8 Obstacle Avoidance|
                      |   - Adaptive Lane Follower  |
                      |   - Dual Routing Engine     |
                      +--------------+--------------+
                                     |
                         Local Wi-Fi / Hotspot
                                     |
                      +--------------v--------------+
                      |   Smartphone (On-Bot Hub)   |
                      |   - IP Webcam (Video Stream)|
                      |   - Compass & GPS Telemetry |
                      |   - Termux Serial Relay     |
                      +--------------+--------------+
                                     |
                              USB-C / OTG Cable
                                     |
                      +--------------v--------------+
                      |    Arduino Uno (Motor Hub)  |
                      |   - L298N 4WD Motor Driver  |
                      |   - Scanning Ultrasonic     |
                      |   - Cargo Lock Servo        |
                      |   - Watchdog & Reflex Safety|
                      +-----------------------------+
```

---

## Directory Structure

```
autonomous-cart-main/
│
├── api.py                    # Core FastAPI backend & autonomous decision loop
├── dashboard.py              # Streamlit Mission Control telemetry dashboard
├── serial_relay.py           # Termux WebSocket-to-USB Serial bridge script
│
├── delivery_app.html         # Customer ordering & live tracking frontend
├── gps_app.html              # Mobile GPS telemetry streamer
├── manual_drive.html         # Ultra-low-latency manual drive pad
│
├── arduino_firmware/         # Microcontroller firmware
│   └── arduino_firmware.ino  # Arduino Uno 4WD motor & sensor driver
│
├── navigation/               # Autonomous navigation stack
│   ├── pipeline.py           # Route coordinator & fallback manager
│   ├── create_path.py        # Google Maps Directions API integrator
│   ├── decode_route.py       # Polyline decoder & point sampler
│   ├── navigate.py           # Bearing calculator & waypoint navigator
│   ├── fnpp.py               # Haversine distance & progressive tracker
│   ├── lane_follower.py      # Vision-based road surface segmenter
│   └── self_navigation/      # Offline campus graph routing engine
│       ├── distance_graph.py # Graph vertices & road weights
│       ├── polyline.py       # Geocoordinate polyline database
│       ├── close_coords.py   # Nearest vertex resolver
│       ├── result_convertor.py# Graph to waypoint formatter
│       └── shortest_distance.py# DFS shortest-path search
│
├── tools/                    # Diagnostic & simulation utilities
│   ├── check_cameras.py      # Camera index discovery tool
│   └── webots_bridge.py      # Webots simulation bridge controller
│
├── requirements.txt          # Python dependencies
├── start.bat                 # 1-click startup launcher
└── README.md                 # System documentation
```

---

## Hardware Pinout (Arduino Uno)

| Component | Arduino Pin | Type | Notes |
| :--- | :--- | :--- | :--- |
| **IN1** | **Pin 4** | Digital Output | Left motor direction |
| **IN2** | **Pin 7** | Digital Output | Left motor direction |
| **IN3** | **Pin 8** | Digital Output | Right motor direction |
| **IN4** | **Pin 12** | Digital Output | Right motor direction |
| **ENA** | **Pin 5** | PWM Output | Left motor speed control |
| **ENB** | **Pin 6** | PWM Output | Right motor speed control |
| **Cargo Servo** | **Pin 9** | PWM Output | Delivery box lock (0°) / unlock (90°) |
| **Scan Servo** | **Pin 10** | PWM Output | Ultrasonic sweep (45°, 90°, 135°) |
| **HC-SR04 TRIG**| **Pin 2** | Digital Output | Distance trigger pulse |
| **HC-SR04 ECHO**| **Pin 3** | Digital Input | Distance measurement pulse |
| **Buzzer** | **Pin 11** | Digital Output | Proximity & obstacle warnings |

---

## Quick Start

### 1. Laptop Setup
Install Python dependencies:
```bash
pip install -r requirements.txt
```

Launch all services with one click:
```cmd
start.bat
```
Or start manually:
```bash
# Terminal 1: Backend
uvicorn api:app --host 0.0.0.0 --port 8000 --reload

# Terminal 2: Dashboard
streamlit run dashboard.py --server.port 8501
```

### 2. Smartphone Setup
1. Mount the phone facing forward on the cart.
2. Install **IP Webcam** (Android) and start the video server.
3. Install **Termux**, then run:
   ```bash
   pkg update && pkg install python
   pip install websockets pyserial
   python serial_relay.py
   ```
4. Plug the Arduino Uno into the phone using a USB OTG adapter.
5. On the laptop, set the bot relay URL:
   ```cmd
   set BOT_WS_URL=ws://<PHONE_IP>:8765/
   ```

---

## Interfaces

- **Mission Control Dashboard**: `http://localhost:8501`
  - Real-time video feed with YOLO & road boundary overlays
  - Live battery, speed, temperature, and ultrasonic telemetry
  - Mode switcher (Autonomous vs Emergency Override)
  - Routing engine selector (Google Maps vs Campus Graph)
- **Manual Drive Pad**: `http://localhost:8000/drive`
  - Zero-latency keyboard & touch controls
- **Customer Delivery App**: `delivery_app.html`
  - Order placement, live cart tracking, and OTP cargo unlock
- **GPS Streamer**: `http://localhost:8000/gps`
  - Phone sensor telemetry streamer
