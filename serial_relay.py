#!/usr/bin/env python3
"""
Serial Relay Bridge (Termux on Android & Desktop)
Bridges WebSocket (laptop api.py) <-> USB Serial (Arduino Uno / ESP32 via OTG).
"""

import asyncio
import glob
import json
import os
import sys
import time

try:
    import serial
except ImportError:
    serial = None

try:
    import websockets
except ImportError:
    websockets = None

BAUD_RATE = 115200
WS_PORT = 8765
SERIAL_PORT = None
MOCK_MODE = False

arduino_serial = None
connected_clients = set()


def find_arduino_port():
    """Detect Arduino/ESP32 USB serial port without relying on broken posix list_ports."""
    # 1. Direct device nodes common on Android OTG and Linux
    candidates = []
    
    # Check glob patterns
    for pattern in ["/dev/ttyUSB*", "/dev/ttyACM*", "/dev/rfcomm*"]:
        try:
            candidates.extend(glob.glob(pattern))
        except Exception:
            pass

    # Standard static fallbacks if glob is restricted
    fallbacks = [
        "/dev/ttyUSB0", "/dev/ttyUSB1", "/dev/ttyUSB2",
        "/dev/ttyACM0", "/dev/ttyACM1", "/dev/ttyACM2",
        "/dev/rfcomm0"
    ]
    for fb in fallbacks:
        if os.path.exists(fb) and fb not in candidates:
            candidates.append(fb)

    if candidates:
        print(f"[RELAY] Found serial candidate(s): {candidates}")
        return candidates[0]

    # Try pyserial list_ports safely (works on Windows/macOS/desktop Linux, fails on Android)
    try:
        import serial.tools.list_ports
        ports = serial.tools.list_ports.comports()
        for p in ports:
            desc = (p.description or "").lower()
            if any(kw in desc for kw in ["arduino", "ch340", "cp210", "ftdi", "usb serial", "acm"]):
                return p.device
            if p.device:
                return p.device
    except Exception:
        pass

    return None


def try_open_serial():
    """Attempt to open the serial port; returns True on success, False otherwise."""
    global arduino_serial, SERIAL_PORT

    if MOCK_MODE:
        return True

    if serial is None:
        print("[RELAY] ERROR: pyserial is not installed. Run: pip install pyserial")
        return False

    if SERIAL_PORT is None or SERIAL_PORT == "auto":
        target = find_arduino_port()
    else:
        target = SERIAL_PORT

    if not target:
        return False

    try:
        ser = serial.Serial(port=target, baudrate=BAUD_RATE, timeout=0.05)
        time.sleep(1.5)  # Allow Arduino bootloader reset
        arduino_serial = ser
        SERIAL_PORT = target
        print(f"[RELAY] >>> Serial connected successfully: {SERIAL_PORT} @ {BAUD_RATE} <<<")
        return True
    except PermissionError:
        print(f"[RELAY] PERMISSION DENIED accessing {target}!")
        print("[RELAY] Hint: Check USB OTG prompt on phone or run: chmod 666 " + target)
        return False
    except Exception as e:
        print(f"[RELAY] Serial connection attempt failed ({target}): {e}")
        return False


async def handle_client(websocket, *args):
    """Handle incoming WebSocket connections from the laptop backend (api.py)."""
    global connected_clients
    client_ip = websocket.remote_address[0] if websocket.remote_address else "unknown"
    print(f"[RELAY] [+] Client connected from: {client_ip}")
    connected_clients.add(websocket)

    # Send welcome handshake
    status_msg = {
        "type": "relay_status",
        "mock_mode": MOCK_MODE,
        "serial_connected": arduino_serial is not None and arduino_serial.is_open,
        "port": SERIAL_PORT,
    }
    await websocket.send(json.dumps(status_msg))

    try:
        async for message in websocket:
            msg = message.strip()
            if not msg:
                continue

            if MOCK_MODE:
                print(f"[RELAY MOCK] -> Cmd: {msg}")
                # Echo simulated ack for lock commands or sonar
                if "LOCK" in msg:
                    await websocket.send(f"ACK:{msg}")
                continue

            if arduino_serial and arduino_serial.is_open:
                try:
                    arduino_serial.write((msg + "\n").encode("utf-8"))
                    arduino_serial.flush()
                except Exception as e:
                    print(f"[RELAY] Serial write error: {e}")
                    await websocket.send(json.dumps({"error": f"Serial write failed: {e}"}))
            else:
                print(f"[RELAY WARNING] Dropped command '{msg}' (Arduino not connected yet)")
                await websocket.send(json.dumps({"error": "Arduino not connected"}))
    except websockets.exceptions.ConnectionClosed:
        pass
    finally:
        connected_clients.discard(websocket)
        print(f"[RELAY] [-] Client disconnected: {client_ip}")


async def serial_reader_loop():
    """Continuously read telemetry/logs from Arduino and forward to WebSocket clients."""
    global arduino_serial
    while True:
        if arduino_serial and arduino_serial.is_open:
            try:
                if arduino_serial.in_waiting > 0:
                    line = arduino_serial.readline().decode("utf-8", errors="ignore").strip()
                    if line:
                        print(f"[ARDUINO -> LAPTOP]: {line}")
                        if connected_clients:
                            disconnected = set()
                            for client in list(connected_clients):
                                try:
                                    await client.send(line)
                                except Exception:
                                    disconnected.add(client)
                            connected_clients.difference_update(disconnected)
            except Exception as e:
                print(f"[RELAY] Serial read error: {e}")
                try:
                    arduino_serial.close()
                except Exception:
                    pass
                arduino_serial = None
        await asyncio.sleep(0.01)


async def background_reconnect_loop():
    """Background monitor to auto-reconnect if USB OTG is plugged in or power-cycled."""
    global arduino_serial
    while True:
        if not MOCK_MODE and (arduino_serial is None or not arduino_serial.is_open):
            try_open_serial()
        await asyncio.sleep(3.0)


async def heartbeat_loop():
    """Send periodic ping to keep serial link alive and active."""
    while True:
        if arduino_serial and arduino_serial.is_open:
            try:
                arduino_serial.write(b"ping\n")
            except Exception:
                pass
        await asyncio.sleep(5.0)


async def main():
    global SERIAL_PORT, MOCK_MODE

    if websockets is None:
        print("[RELAY] ERROR: websockets is not installed. Run: pip install websockets")
        sys.exit(1)

    # Parse command-line args if any
    for arg in sys.argv[1:]:
        if arg.lower() in ["--mock", "mock", "-m"]:
            MOCK_MODE = True
            print("[RELAY] Running in MOCK (SIMULATED) MODE. No physical serial required.")
        elif not arg.startswith("-"):
            SERIAL_PORT = arg

    print("=" * 55)
    print("  AutoDrop Phone Serial Relay Bridge")
    print(f"  WebSocket Port: {WS_PORT}")
    print(f"  Target Serial : {SERIAL_PORT or 'Auto-detect'}")
    print("=" * 55)

    # Initial connection attempt (will continue retrying in background if not ready)
    if not MOCK_MODE:
        if not try_open_serial():
            print("[RELAY] Notice: Arduino not detected immediately.")
            print("[RELAY] WebSocket server will start anyway and keep scanning for USB OTG...")

    # Start WebSocket server
    server = await websockets.serve(handle_client, "0.0.0.0", WS_PORT)
    print(f"[RELAY] Server listening on ws://0.0.0.0:{WS_PORT}")
    print("[RELAY] Ready for laptop connection!")

    await asyncio.gather(
        serial_reader_loop(),
        background_reconnect_loop(),
        heartbeat_loop()
    )


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("\n[RELAY] Shutting down...")
        if arduino_serial and arduino_serial.is_open:
            try:
                arduino_serial.write(b"stop\n")
                arduino_serial.close()
            except Exception:
                pass
        print("[RELAY] Goodbye.")
