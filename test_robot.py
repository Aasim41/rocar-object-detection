#!/usr/bin/env python3
"""
AutoDrop - Interactive Diagnostic & Test Suite
Direct Laptop USB Serial & Phone TCP support.
Tests motors, differential steering curves, cargo servo, scanning servo, ultrasonic sensor, buzzer, and camera.
"""

import socket
import time
import sys
import os
import threading

# Configuration
BAUD_RATE = 115200
DEFAULT_TCP_IP = "10.194.42.199"
DEFAULT_TCP_PORT = 8765

sock = None
ser = None
is_serial = False
connected = False
running = True
last_distance = "---"

def listener_thread():
    global last_distance, running
    buf = ""
    while running:
        try:
            if is_serial and ser and ser.is_open:
                line = ser.readline().decode("utf-8", errors="ignore").strip()
                if line:
                    handle_line(line)
                else:
                    time.sleep(0.01)
            elif sock:
                data = sock.recv(1024).decode("utf-8", errors="ignore")
                if not data:
                    break
                buf += data
                while "\n" in buf:
                    line, buf = buf.split("\n", 1)
                    line = line.strip()
                    if line:
                        handle_line(line)
        except Exception:
            time.sleep(0.05)

def handle_line(line):
    global last_distance
    if line.startswith("DIST:"):
        parts = line.split(":")
        dir_t = parts[2] if len(parts) > 2 else "C"
        last_distance = f"{parts[1]} cm (Dir: {dir_t})"
    elif line == "BLOCKED":
        print("\n🚨 [ALERT] Sensor Reflex Triggered: BLOCKED (<15cm)!")
    elif "ACK:" in line:
        print(f"\n[ARDUINO ACK]: {line}")
    elif line == "READY":
        print(f"\n[ARDUINO READY]: Boot complete at {BAUD_RATE} baud.")

def send_command(cmd, timeout=0.08):
    if not connected:
        print("❌ Not connected to robot hardware!")
        return
    try:
        if is_serial and ser:
            ser.write((cmd + "\n").encode("utf-8"))
            ser.flush()
        elif sock:
            sock.sendall((cmd + "\n").encode("utf-8"))
        time.sleep(timeout)
    except Exception as e:
        print(f"❌ Failed to send '{cmd}': {e}")

def timed_drive(cmd, duration_sec):
    print(f"▶️ Driving '{cmd}' for {duration_sec}s...")
    send_command(cmd)
    time.sleep(duration_sec)
    send_command("stop")
    print("⏹️ Stopped.")

def continuous_distance_monitor():
    print("\n" + "="*50)
    print("  LIVE ULTRASONIC SENSOR MONITOR (Press Ctrl+C to stop)")
    print("  Wave your hand in front of the HC-SR04 sensor:")
    print("="*50)
    try:
        while True:
            sys.stdout.write(f"\r  📏 Distance: {last_distance:<25}")
            sys.stdout.flush()
            time.sleep(0.1)
    except KeyboardInterrupt:
        print("\n  Stopped monitor.\n")

def test_camera(cam_idx=0):
    print(f"\n📷 Testing local USB webcam index {cam_idx}...")
    try:
        import cv2
        cap = cv2.VideoCapture(cam_idx)
        t0 = time.time()
        ret, frame = cap.read()
        latency_ms = int((time.time() - t0) * 1000)
        if ret and frame is not None:
            h, w, c = frame.shape
            print(f"✅ Camera OK! Resolution: {w}x{h}, Grab Latency: {latency_ms}ms")
        else:
            print(f"❌ Could not grab frame from camera index {cam_idx}.")
        cap.release()
    except Exception as e:
        print(f"❌ Camera test error: {e}")

def main():
    global sock, ser, is_serial, connected, running
    print("\n" + "="*58)
    print("       🤖 AutoDrop Robot Diagnostic Station")
    print("="*58)

    # Determine connection target
    target = None
    if len(sys.argv) > 1:
        target = sys.argv[1].strip()
    else:
        # Check available COM ports
        try:
            import serial.tools.list_ports
            ports = list(serial.tools.list_ports.comports())
            usb_ports = [p.device for p in ports if "bluetooth" not in p.description.lower()]
            if usb_ports:
                target = usb_ports[0]
                print(f"🔍 Auto-detected USB Serial Port: {target}")
            elif ports:
                print("Available COM Ports:")
                for p in ports:
                    print(f"  - {p.device}: {p.description}")
        except Exception:
            pass

    if not target:
        user_input = input("Enter COM Port (e.g. COM3) or IP (e.g. 10.194.42.199): ").strip()
        target = user_input if user_input else "COM3"

    # Connect via Serial or TCP
    if target.upper().startswith("COM") or target.startswith("/dev/"):
        print(f"🔌 Connecting to Arduino via Direct USB Serial ({target} @ {BAUD_RATE})...")
        try:
            import serial
            ser = serial.Serial(port=target, baudrate=BAUD_RATE, timeout=0.1)
            time.sleep(1.8)  # Bootloader reset delay
            ser.reset_input_buffer()
            ser.reset_output_buffer()
            is_serial = True
            connected = True
            print(f"✅ CONNECTED directly to Arduino on {target}!\n")
        except Exception as e:
            print(f"\n❌ Serial connection to {target} failed: {e}")
            print("👉 Check that Arduino USB cable is plugged in and no other program has the port open.\n")
            sys.exit(1)
    else:
        print(f"📡 Connecting to Arduino via TCP ({target}:{DEFAULT_TCP_PORT})...")
        try:
            s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            s.settimeout(3.0)
            s.connect((target, DEFAULT_TCP_PORT))
            sock = s
            is_serial = False
            connected = True
            print(f"✅ CONNECTED to Arduino on {target}:{DEFAULT_TCP_PORT}!\n")
        except Exception as e:
            print(f"\n❌ TCP connection failed: {e}")
            sys.exit(1)

    t = threading.Thread(target=listener_thread, daemon=True)
    t.start()
    time.sleep(0.5)

    while True:
        print("\n" + "-"*58)
        print(" [1] 🚗 Forward (2 sec)")
        print(" [2] 🚗 Reverse (2 sec)")
        print(" [3] 🔄 Stationary Turn Left (Pivot)")
        print(" [4] 🔄 Stationary Turn Right (Pivot)")
        print(" [Q] ↖️ Rolling Curve Left (Best under weight)")
        print(" [E] ↗️ Rolling Curve Right (Best under weight)")
        print(" [<] ↩️ Swing Left (Left stop, Right forward)")
        print(" [>] ↪️ Swing Right (Left forward, Right stop)")
        print(" [5] 🛑 Emergency STOP")
        print(" [6] 🔓 Cargo Latch: UNLOCK (Open Lid)")
        print(" [7] 🔒 Cargo Latch: LOCK (Close Lid)")
        print(" [8] 🎯 Scanning Servo: Left -> Center -> Right")
        print(" [9] 📡 Ultrasonic Sensor: Live Distance Stream")
        print(" [0] 🔔 Buzzer Test")
        print(" [C] 📷 Test Local Webcam (Index 0)")
        print(" [X] ❌ Exit")
        print("-"*58)

        choice = input("Select an option: ").strip().upper()

        if choice == "1":
            timed_drive("forward", 2.0)
        elif choice == "2":
            timed_drive("reverse", 2.0)
        elif choice == "3":
            timed_drive("left", 1.8)
        elif choice == "4":
            timed_drive("right", 1.8)
        elif choice == "Q":
            timed_drive("curve_left", 2.0)
        elif choice == "E":
            timed_drive("curve_right", 2.0)
        elif choice == "<":
            timed_drive("swing_left", 2.0)
        elif choice == ">":
            timed_drive("swing_right", 2.0)
        elif choice == "5":
            send_command("stop")
            print("⏹️ Sent STOP command.")
        elif choice == "6":
            print("🔓 Unlocking cargo lid...")
            send_command("unlock")
        elif choice == "7":
            print("🔒 Locking cargo lid...")
            send_command("lock")
        elif choice == "8":
            print("🎯 Sweeping scanning servo: LEFT (45°)...")
            send_command("scan_left")
            time.sleep(0.8)
            print("🎯 Sweeping scanning servo: RIGHT (135°)...")
            send_command("scan_right")
            time.sleep(0.8)
            print("🎯 Sweeping scanning servo: CENTER (90°)...")
            send_command("scan_center")
        elif choice == "9":
            continuous_distance_monitor()
        elif choice == "0":
            print("🔔 Beeping buzzer...")
            send_command("beep")
        elif choice == "C":
            test_camera(0)
        elif choice in ("X", "EXIT", "QUIT"):
            send_command("stop")
            running = False
            print("Goodbye!")
            break
        else:
            print("Invalid choice, please select from menu.")

if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("\nExiting.")
        if ser:
            ser.close()
        if sock:
            sock.close()
