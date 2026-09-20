#!/usr/bin/env python3
"""
Serial Relay Bridge — Runs on the phone (Termux)
=================================================
Bridges WebSocket (from laptop) <-> USB Serial (to Arduino Uno).

SETUP (run these in Termux once):
    pkg install python
    pip install websockets pyserial
    
USAGE:
    python serial_relay.py

The script:
  1. Opens USB Serial to Arduino (/dev/ttyUSB0 or /dev/ttyACM0)
  2. Starts a WebSocket server on port 8765
  3. Laptop connects to ws://<phone-ip>:8765
  4. Commands from laptop -> forwarded to Arduino serial
  5. Arduino serial responses -> forwarded back to laptop
"""

import asyncio
import serial
import serial.tools.list_ports
import websockets
import json
import sys
import time

# --- Configuration ---
BAUD_RATE = 115200
WS_PORT = 8765
SERIAL_PORT = None  # Auto-detect

def find_arduino_port():
    """Auto-detect the Arduino's serial port."""
    ports = serial.tools.list_ports.comports()
    for p in ports:
        desc = (p.description or "").lower()
        # Common Arduino identifiers
        if any(kw in desc for kw in ["arduino", "ch340", "cp210", "ftdi", "usb serial", "acm"]):
            print(f"[RELAY] Found Arduino on {p.device}: {p.description}")
            return p.device
    
    # Fallback: try common Android OTG paths
    import os
    for path in ["/dev/ttyUSB0", "/dev/ttyACM0", "/dev/ttyUSB1"]:
        if os.path.exists(path):
            print(f"[RELAY] Found serial device at {path}")
            return path
    
    return None

# --- Global state ---
arduino_serial = None
connected_clients = set()

def open_serial():
    """Open the serial connection to Arduino."""
    global arduino_serial, SERIAL_PORT
    
    if SERIAL_PORT is None:
        SERIAL_PORT = find_arduino_port()
    
    if SERIAL_PORT is None:
        print("[RELAY] ERROR: No Arduino found! Plug in the USB OTG cable.")
        print("[RELAY] Available ports:")
        for p in serial.tools.list_ports.comports():
            print(f"  - {p.device}: {p.description}")
        return False
    
    try:
        arduino_serial = serial.Serial(
            port=SERIAL_PORT,
            baudrate=BAUD_RATE,
            timeout=0.05  # 50ms read timeout (non-blocking)
        )
        time.sleep(2)  # Wait for Arduino to reset after serial open
        print(f"[RELAY] Serial opened: {SERIAL_PORT} @ {BAUD_RATE} baud")
        return True
    except Exception as e:
        print(f"[RELAY] ERROR opening serial: {e}")
        return False

async def handle_client(websocket, path=None):
    """Handle a WebSocket client connection (from the laptop)."""
    global connected_clients
    
    client_ip = websocket.remote_address[0] if websocket.remote_address else "unknown"
    print(f"[RELAY] Laptop connected from {client_ip}")
    connected_clients.add(websocket)
    
    try:
        async for message in websocket:
            message = message.strip()
            if not message:
                continue
            
            # Forward command to Arduino via serial
            if arduino_serial and arduino_serial.is_open:
                try:
                    arduino_serial.write((message + "\n").encode("utf-8"))
                    arduino_serial.flush()
                except Exception as e:
                    print(f"[RELAY] Serial write error: {e}")
                    await websocket.send(json.dumps({"error": f"Serial write failed: {e}"}))
            else:
                await websocket.send(json.dumps({"error": "Arduino not connected"}))
                
    except websockets.exceptions.ConnectionClosed:
        pass
    finally:
        connected_clients.discard(websocket)
        print(f"[RELAY] Laptop disconnected ({client_ip})")

async def serial_reader():
    """Background task: read Arduino serial output and broadcast to all WebSocket clients."""
    global arduino_serial
    
    while True:
        if arduino_serial and arduino_serial.is_open:
            try:
                if arduino_serial.in_waiting > 0:
                    line = arduino_serial.readline().decode("utf-8", errors="ignore").strip()
                    if line and connected_clients:
                        # Broadcast to all connected laptops
                        disconnected = set()
                        for client in connected_clients:
                            try:
                                await client.send(line)
                            except Exception:
                                disconnected.add(client)
                        connected_clients.difference_update(disconnected)
            except Exception as e:
                print(f"[RELAY] Serial read error: {e}")
        
        await asyncio.sleep(0.01)  # 10ms poll interval

async def heartbeat():
    """Send periodic ping to Arduino to keep connection alive."""
    while True:
        if arduino_serial and arduino_serial.is_open:
            try:
                arduino_serial.write(b"ping\n")
            except Exception:
                pass
        await asyncio.sleep(5)

async def main():
    print("=" * 50)
    print("  SERIAL RELAY BRIDGE v1.0")
    print("  Phone (Termux) -> Arduino Uno")
    print("=" * 50)
    
    # Open serial to Arduino
    if not open_serial():
        print("\n[RELAY] Retrying in 5 seconds...")
        time.sleep(5)
        if not open_serial():
            print("[RELAY] FATAL: Cannot open serial. Exiting.")
            sys.exit(1)
    
    # Read the Arduino boot message
    time.sleep(1)
    if arduino_serial and arduino_serial.in_waiting > 0:
        boot_msg = arduino_serial.readline().decode("utf-8", errors="ignore").strip()
        print(f"[RELAY] Arduino says: {boot_msg}")
    
    # Start WebSocket server
    print(f"[RELAY] WebSocket server starting on port {WS_PORT}...")
    print(f"[RELAY] Laptop should connect to: ws://<this-phone-ip>:{WS_PORT}")
    
    # Start all tasks
    server = await websockets.serve(handle_client, "0.0.0.0", WS_PORT)
    
    print(f"[RELAY] ✅ READY — Waiting for laptop connection...")
    
    await asyncio.gather(
        serial_reader(),
        heartbeat(),
    )

if __name__ == "__main__":
    # Allow user to override serial port via command line
    if len(sys.argv) > 1:
        SERIAL_PORT = sys.argv[1]
        print(f"[RELAY] Using manual serial port: {SERIAL_PORT}")
    
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("\n[RELAY] Shutting down...")
        if arduino_serial and arduino_serial.is_open:
            arduino_serial.write(b"stop\n")
            arduino_serial.close()
