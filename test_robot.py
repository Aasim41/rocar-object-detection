#!/usr/bin/env python3
"""
AutoDrop - Interactive Component-by-Component Diagnostic Suite
Tests motors, steering, cargo latch servo, scanning servo, ultrasonic sensor, buzzer, and camera.
"""

import socket
import time
import sys
import threading

PHONE_IP = "10.205.106.115"
TCP_PORT = 8765
CAM_URL = f"http://{PHONE_IP}:8080/video"

sock = None
connected = False
running = True
last_distance = "---"

def listener_thread(s):
    global last_distance, running
    buf = ""
    while running:
        try:
            data = s.recv(1024).decode("utf-8", errors="ignore")
            if not data:
                break
            buf += data
            while "\n" in buf:
                line, buf = buf.split("\n", 1)
                line = line.strip()
                if line:
                    if line.startswith("DIST:"):
                        parts = line.split(":")
                        last_distance = f"{parts[1]} cm (Dir: {parts[2] if len(parts)>2 else 'C'})"
                    elif line == "BLOCKED":
                        print("\n🚨 [ALERT] Hardware Sensor Triggered: BLOCKED (<15cm)!")
                    elif "ACK:" in line:
                        print(f"\n[ARDUINO ACK]: {line}")
        except Exception:
            break

def send_command(cmd, timeout=0.1):
    if not connected or not sock:
        print("❌ Not connected to robot hardware!")
        return
    try:
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

def test_camera():
    print(f"\n📷 Testing phone IP webcam stream at {CAM_URL}...")
    try:
        import cv2
        cap = cv2.VideoCapture(CAM_URL)
        t0 = time.time()
        ret, frame = cap.read()
        latency_ms = int((time.time() - t0) * 1000)
        if ret and frame is not None:
            h, w, c = frame.shape
            print(f"✅ Camera OK! Resolution: {w}x{h}, Grab Latency: {latency_ms}ms")
        else:
            print("❌ Could not grab frame. Make sure IP Webcam is running on your phone!")
        cap.release()
    except Exception as e:
        print(f"❌ Camera test error: {e}")

def main():
    global sock, connected, running
    print("\n" + "="*55)
    print("   🤖 AutoDrop Robot Diagnostic Suite")
    print(f"   Connecting to Arduino via TCP: {PHONE_IP}:{TCP_PORT}...")
    print("="*55)

    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        s.settimeout(3.0)
        s.connect((PHONE_IP, TCP_PORT))
        sock = s
        connected = True
        print(f"✅ CONNECTED to Arduino on {PHONE_IP}:{TCP_PORT}!\n")
    except Exception as e:
        print(f"\n❌ Connection failed: {e}")
        print("👉 Check that TCPUART is running on your phone (Port 8765, Server Mode).\n")
        sys.exit(1)

    t = threading.Thread(target=listener_thread, args=(sock,), daemon=True)
    t.start()

    time.sleep(0.5)

    while True:
        print("\n" + "-"*55)
        print(" [1] 🚗 Forward (2 sec)")
        print(" [2] 🚗 Reverse (2 sec)")
        print(" [3] 🔄 Turn Left (2 sec)")
        print(" [4] 🔄 Turn Right (2 sec)")
        print(" [5] 🛑 Emergency STOP")
        print(" [6] 🔓 Cargo Latch: UNLOCK (Open Lid)")
        print(" [7] 🔒 Cargo Latch: LOCK (Close Lid)")
        print(" [8] 🎯 Scanning Servo: Left -> Center -> Right")
        print(" [9] 📡 Ultrasonic Sensor: Live Distance Stream")
        print(" [0] 🔔 Buzzer Alarm Test")
        print(" [C] 📷 Test Phone Camera Feed")
        print(" [Q] ❌ Quit")
        print("-"*55)

        choice = input("Select an option (0-9, C, Q): ").strip().upper()

        if choice == "1":
            timed_drive("forward", 2.0)
        elif choice == "2":
            timed_drive("reverse", 2.0)
        elif choice == "3":
            timed_drive("left", 1.5)
        elif choice == "4":
            timed_drive("right", 1.5)
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
            time.sleep(1.0)
            print("🎯 Sweeping scanning servo: RIGHT (135°)...")
            send_command("scan_right")
            time.sleep(1.0)
            print("🎯 Sweeping scanning servo: CENTER (90°)...")
            send_command("scan_center")
        elif choice == "9":
            continuous_distance_monitor()
        elif choice == "0":
            print("🔔 Beeping buzzer...")
            send_command("beep")
        elif choice == "C":
            test_camera()
        elif choice == "Q":
            send_command("stop")
            running = False
            print("Goodbye!")
            break
        else:
            print("Invalid choice, please select 0-9, C, or Q.")

if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("\nExiting.")
        if sock:
            sock.close()

