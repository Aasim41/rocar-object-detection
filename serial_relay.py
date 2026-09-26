#!/usr/bin/env python3
"""
Serial Relay Bridge (Termux on Android)
Bridges WebSocket (laptop) <-> USB Serial (Arduino Uno via OTG).
"""

import asyncio
import serial
import serial.tools.list_ports
import websockets
import json
import sys
import time
import os

BAUD_RATE = 115200
WS_PORT = 8765
SERIAL_PORT = None

arduino_serial = None
connected_clients = set()

def find_arduino_port():
    ports = serial.tools.list_ports.comports()
    for p in ports:
        desc = (p.description or "").lower()
        if any(kw in desc for kw in ["arduino", "ch340", "cp210", "ftdi", "usb serial", "acm"]):
            return p.device
    
    for path in ["/dev/ttyUSB0", "/dev/ttyACM0", "/dev/ttyUSB1"]:
        if os.path.exists(path):
            return path
    return None

def open_serial():
    global arduino_serial, SERIAL_PORT
    if SERIAL_PORT is None:
        SERIAL_PORT = find_arduino_port()
    
    if SERIAL_PORT is None:
        print("[RELAY] ERROR: No Arduino found. Connect via USB OTG.")
        return False
    
    try:
        arduino_serial = serial.Serial(port=SERIAL_PORT, baudrate=BAUD_RATE, timeout=0.05)
        time.sleep(2)
        print(f"[RELAY] Serial connected: {SERIAL_PORT} @ {BAUD_RATE}")
        return True
    except Exception as e:
        print(f"[RELAY] Serial connection error: {e}")
        return False

async def handle_client(websocket, path=None):
    global connected_clients
    client_ip = websocket.remote_address[0] if websocket.remote_address else "unknown"
    print(f"[RELAY] Client connected: {client_ip}")
    connected_clients.add(websocket)
    
    try:
        async for message in websocket:
            msg = message.strip()
            if not msg:
                continue
            if arduino_serial and arduino_serial.is_open:
                try:
                    arduino_serial.write((msg + "\n").encode("utf-8"))
                    arduino_serial.flush()
                except Exception as e:
                    await websocket.send(json.dumps({"error": f"Serial write failed: {e}"}))
            else:
                await websocket.send(json.dumps({"error": "Arduino not connected"}))
    except websockets.exceptions.ConnectionClosed:
        pass
    finally:
        connected_clients.discard(websocket)
        print(f"[RELAY] Client disconnected: {client_ip}")

async def serial_reader():
    global arduino_serial
    while True:
        if arduino_serial and arduino_serial.is_open:
            try:
                if arduino_serial.in_waiting > 0:
                    line = arduino_serial.readline().decode("utf-8", errors="ignore").strip()
                    if line and connected_clients:
                        disconnected = set()
                        for client in connected_clients:
                            try:
                                await client.send(line)
                            except Exception:
                                disconnected.add(client)
                        connected_clients.difference_update(disconnected)
            except Exception as e:
                print(f"[RELAY] Serial read error: {e}")
        await asyncio.sleep(0.01)

async def heartbeat():
    while True:
        if arduino_serial and arduino_serial.is_open:
            try:
                arduino_serial.write(b"ping\n")
            except Exception:
                pass
        await asyncio.sleep(5)

async def main():
    if not open_serial():
        print("[RELAY] Retrying in 5 seconds...")
        time.sleep(5)
        if not open_serial():
            sys.exit(1)
    
    server = await websockets.serve(handle_client, "0.0.0.0", WS_PORT)
    print(f"[RELAY] Listening on port {WS_PORT}")
    await asyncio.gather(serial_reader(), heartbeat())

if __name__ == "__main__":
    if len(sys.argv) > 1:
        SERIAL_PORT = sys.argv[1]
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        if arduino_serial and arduino_serial.is_open:
            arduino_serial.write(b"stop\n")
            arduino_serial.close()
