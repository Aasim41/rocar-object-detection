# Autonomous Delivery Cart (RoCAR) - ESP32 Edition

Autonomous indoor/campus delivery bot system featuring YOLOv8-based obstacle detection, adaptive lane following, dual-engine GPS waypoint routing, and untethered ESP32 wireless IoT telemetry.

---

## Architecture Overview

`
                      +-----------------------------+
                      |   Laptop (Brain / Server)   |
                      |   - FastAPI Backend         |
                      |   - YOLOv8 Obstacle Avoidance|
                      |   - Adaptive Lane Follower  |
                      |   - Dual Routing Engine     |
                      +--------------+--------------+
                                     |
                         Direct Wi-Fi / Hotspot
                         (DeliveryBot-AP / Port 8765)
                                     |
                      +--------------v--------------+
                      |   ESP32 Dual-Core Controller|
                      |   - Dual L298N 4WD Drivers  |
                      |   - Scanning Ultrasonic     |
                      |   - Cargo Lock Servo        |
                      |   - Autonomous Brake Reflex |
                      |   - Self-Hosted Web Remote  |
                      +-----------------------------+
`

---

## Directory Structure

`
autonomous-cart-main/
│
├── api.py                    # Core FastAPI backend & autonomous decision loop
├── dashboard.py              # Streamlit Mission Control telemetry dashboard
├── test_robot.py             # Interactive hardware test suite
│
├── delivery_app.html         # Customer ordering & live tracking frontend
├── gps_app.html              # Mobile GPS telemetry streamer
├── manual_drive.html         # Ultra-low-latency manual drive pad
│
├── esp32_firmware/           # ESP32 Dual-Core Microcontroller Firmware
│   └── esp32_firmware.ino    # FreeRTOS 4WD motor, sonar reflex, AP & TCP driver
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
`

---

## Hardware Pinout (ESP32)

| Component | ESP32 Pin | Signal Type | Notes |
| :--- | :--- | :--- | :--- |
| **Left Speed (ENA)** | **GPIO 25** | LEDC PWM (20kHz) | Left motors speed control (0-255) |
| **Left Forward (IN1)** | **GPIO 27** | Digital Output | Left wheels forward |
| **Left Reverse (IN2)** | **GPIO 14** | Digital Output | Left wheels reverse |
| **Right Speed (ENB)** | **GPIO 26** | LEDC PWM (20kHz) | Right motors speed control (0-255) |
| **Right Forward (IN3)** | **GPIO 16** | Digital Output | Right wheels forward |
| **Right Reverse (IN4)** | **GPIO 17** | Digital Output | Right wheels reverse |
| **Scan Turret Servo** | **GPIO 18** | 50Hz PWM | Ultrasonic sweep (45°, 90°, 135°) |
| **Cargo Bay Latch** | **GPIO 19** | 50Hz PWM | Delivery box lock (0°) / unlock (90°) |
| **HC-SR04 TRIG** | **GPIO 4** | Digital Output | Distance trigger pulse |
| **HC-SR04 ECHO** | **GPIO 5** | Digital Input | Via 1kΩ / 2kΩ voltage divider (3.33V) |
| **Buzzer** | **GPIO 23** | Digital Output | Proximity & obstacle warnings |

---

## Quick Start

### 1. ESP32 Firmware Upload
1. Turn robot battery switch OFF.
2. Open esp32_firmware/esp32_firmware.ino in Arduino IDE.
3. Select board **ESP32 Dev Module** and the correct COM port.
4. Install the ESP32Servo library via Library Manager.
5. Click **Upload**.

### 2. Laptop Setup
Install Python dependencies:
`ash
pip install -r requirements.txt
`

Launch all services with one click:
`cmd
start.bat
`
Or start manually:
`ash
# Terminal 1: Backend
uvicorn api:app --host 0.0.0.0 --port 8000 --reload

# Terminal 2: Dashboard
streamlit run dashboard.py --server.port 8501
`

Connect laptop to the robot's Wi-Fi: **DeliveryBot-AP** (Password: 12345678).
pi.py will auto-discover and connect to 	cp://192.168.4.1:8765!

---

## Interfaces

- **ESP32 Onboard Web Joystick**: http://192.168.4.1
  - Self-hosted mobile touch remote served directly from ESP32 flash (zero apps needed).
- **Mission Control Dashboard**: http://localhost:8501
  - Real-time video feed with YOLO & road boundary overlays
  - Live battery, speed, temperature, and ultrasonic telemetry
  - Mode switcher (Autonomous vs Emergency Override)
  - Routing engine selector (Google Maps vs Campus Graph)
- **Manual Drive Pad**: http://localhost:8000/drive
  - Zero-latency keyboard & touch controls
- **Customer Delivery App**: delivery_app.html
  - Order placement, live cart tracking, and OTP cargo unlock
- **GPS Streamer**: http://localhost:8000/gps
  - Phone sensor telemetry streamer
