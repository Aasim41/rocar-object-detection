import streamlit as st
import streamlit.components.v1 as components
import requests
import time
import os
from datetime import datetime

# ============================================================
# Page Configuration
# ============================================================
st.set_page_config(
    page_title="AutoDrop™ Mission Control",
    page_icon="⚡",
    layout="wide",
    initial_sidebar_state="collapsed"
)

# ============================================================
# Minimal Modern Obsidian Theme & GSAP Stylesheet
# ============================================================
st.markdown("""
<style>
    @import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700;800&family=JetBrains+Mono:wght@400;500;600;700&display=swap');
    
    :root {
        --bg-main: #07090e;
        --bg-panel: rgba(15, 20, 32, 0.75);
        --bg-subtle: rgba(255, 255, 255, 0.03);
        --border-subtle: rgba(255, 255, 255, 0.07);
        --border-highlight: rgba(255, 255, 255, 0.12);
        --accent-cyan: #06b6d4;
        --accent-emerald: #10b981;
        --accent-amber: #f59e0b;
        --accent-rose: #f43f5e;
        --text-primary: #f8fafc;
        --text-secondary: #94a3b8;
        --text-muted: #64748b;
    }

    /* Ambient Minimal Mesh */
    .stApp {
        background-color: var(--bg-main) !important;
        background-image: 
            radial-gradient(circle at 15% 10%, rgba(6, 182, 212, 0.06) 0%, transparent 45%),
            radial-gradient(circle at 85% 15%, rgba(99, 102, 241, 0.05) 0%, transparent 50%),
            radial-gradient(circle at 50% 90%, rgba(16, 185, 129, 0.04) 0%, transparent 55%) !important;
        background-attachment: fixed !important;
        color: var(--text-primary);
        font-family: 'Inter', -apple-system, BlinkMacSystemFont, sans-serif;
    }

    #MainMenu, footer, .stDeployButton, header { display: none !important; }

    ::-webkit-scrollbar { width: 5px; height: 5px; }
    ::-webkit-scrollbar-track { background: transparent; }
    ::-webkit-scrollbar-thumb { background: rgba(255,255,255,0.1); border-radius: 6px; }
    ::-webkit-scrollbar-thumb:hover { background: rgba(255,255,255,0.2); }

    /* Hide Streamlit re-render artifacts */
    [data-stale="true"],
    .stale,
    .element-container.stale,
    .stMarkdown.stale {
        opacity: 1 !important;
        transition: none !important;
    }
    
    .stElementContainer,
    .element-container,
    [data-testid="stVerticalBlock"],
    [data-testid="column"] {
        transition: none !important;
        animation: none !important;
    }
    
    .stSpinner, [data-testid="stSpinner"] {
        display: none !important;
    }

    /* ===== MINIMAL BENTO GLASS PANELS ===== */
    .panel {
        background: var(--bg-panel);
        border: 1px solid var(--border-subtle);
        border-top: 1px solid var(--border-highlight);
        border-radius: 14px;
        padding: 18px 20px;
        margin-bottom: 16px;
        backdrop-filter: blur(20px);
        -webkit-backdrop-filter: blur(20px);
        box-shadow: 0 10px 25px -5px rgba(0, 0, 0, 0.4), inset 0 1px 0 rgba(255, 255, 255, 0.05);
        transition: border-color 0.2s ease;
    }
    
    .panel:hover {
        border-color: rgba(255, 255, 255, 0.14);
    }

    .panel-label {
        font-family: 'JetBrains Mono', monospace;
        font-size: 10px;
        font-weight: 600;
        color: var(--text-muted);
        letter-spacing: 1.4px;
        text-transform: uppercase;
        margin-bottom: 14px;
        display: flex;
        align-items: center;
        gap: 8px;
    }
    
    .panel-label::before {
        content: '';
        width: 5px;
        height: 5px;
        background: var(--accent-cyan);
        border-radius: 50%;
        display: inline-block;
    }

    /* ===== MINIMAL STATUS READOUTS ===== */
    .status-badge {
        display: inline-flex;
        align-items: center;
        gap: 6px;
        background: rgba(6, 182, 212, 0.08);
        border: 1px solid rgba(6, 182, 212, 0.22);
        padding: 4px 10px;
        border-radius: 6px;
        font-family: 'JetBrains Mono', monospace;
        font-size: 11px;
        font-weight: 600;
        color: #38bdf8;
        margin-bottom: 8px;
    }

    .status-readout {
        font-family: 'Inter', sans-serif;
        font-size: 18px;
        font-weight: 700;
        color: #ffffff;
        letter-spacing: -0.2px;
        margin-bottom: 4px;
    }
    
    .status-detail {
        font-family: 'JetBrains Mono', monospace;
        font-size: 11px;
        color: var(--text-muted);
        line-height: 1.4;
    }

    /* ===== MINIMAL METRIC TILES ===== */
    .metric-tile {
        background: rgba(0, 0, 0, 0.25);
        border: 1px solid rgba(255, 255, 255, 0.05);
        border-radius: 10px;
        padding: 12px;
        text-align: center;
        transition: border-color 0.15s ease;
    }
    .metric-tile:hover {
        border-color: rgba(255, 255, 255, 0.12);
    }
    .metric-tile-value {
        font-family: 'JetBrains Mono', monospace;
        font-size: 18px;
        font-weight: 700;
        letter-spacing: -0.5px;
        margin-bottom: 2px;
    }
    .metric-tile-label {
        font-family: 'JetBrains Mono', monospace;
        font-size: 9px;
        font-weight: 600;
        color: var(--text-muted);
        letter-spacing: 1.2px;
        text-transform: uppercase;
    }

    /* ===== STREAMLIT BUTTON OVERHAUL (MINIMAL & SHARP) ===== */
    .stButton > button {
        background: rgba(255, 255, 255, 0.05) !important;
        color: #ffffff !important;
        border: 1px solid rgba(255, 255, 255, 0.1) !important;
        border-top: 1px solid rgba(255, 255, 255, 0.18) !important;
        border-radius: 8px !important;
        font-family: 'Inter', sans-serif !important;
        font-weight: 600 !important;
        font-size: 12px !important;
        letter-spacing: 0.3px !important;
        padding: 10px 16px !important;
        box-shadow: 0 2px 8px rgba(0, 0, 0, 0.3) !important;
        transition: all 0.15s ease !important;
        width: 100%;
    }
    .stButton > button:hover {
        background: rgba(255, 255, 255, 0.09) !important;
        border-color: rgba(255, 255, 255, 0.22) !important;
        transform: translateY(-1px) !important;
    }
    .stButton > button:active {
        transform: translateY(0) !important;
    }

    /* ===== CLEAN TERMINAL STYLING ===== */
    .log-terminal {
        background: #090b11;
        border: 1px solid rgba(255, 255, 255, 0.06);
        border-radius: 10px;
        padding: 12px 14px;
        max-height: 200px;
        overflow-y: auto;
        font-family: 'JetBrains Mono', monospace;
    }
    .log-line {
        font-size: 11px;
        color: #cbd5e1;
        padding: 3px 0;
        border-bottom: 1px solid rgba(255,255,255,0.02);
        line-height: 1.5;
        display: flex;
        gap: 10px;
    }
    .log-line:last-child { border-bottom: none; }
    .log-timestamp { 
        color: #475569; 
        min-width: 60px;
        font-size: 10px;
    }

    /* ===== VIDEO CONTAINER ===== */
    .video-wrap {
        position: relative;
        border-radius: 10px;
        overflow: hidden;
        border: 1px solid rgba(255,255,255,0.08);
        background: #000;
    }
    .video-wrap img {
        display: block;
        width: 100%;
        height: auto;
        max-height: 420px;
        object-fit: cover;
    }
    .video-overlay-tl {
        position: absolute;
        top: 10px; left: 12px;
        font-family: 'JetBrains Mono', monospace;
        font-size: 10px;
        font-weight: 700;
        color: #fff;
        background: rgba(225, 29, 72, 0.9);
        padding: 3px 8px;
        border-radius: 4px;
        letter-spacing: 0.6px;
        display: flex;
        align-items: center;
        gap: 5px;
    }
    .video-overlay-tr {
        position: absolute;
        top: 10px; right: 12px;
        font-family: 'JetBrains Mono', monospace;
        font-size: 10px;
        color: #38bdf8;
        background: rgba(10, 14, 22, 0.85);
        backdrop-filter: blur(8px);
        border: 1px solid rgba(255, 255, 255, 0.1);
        padding: 3px 8px;
        border-radius: 4px;
    }
    .no-cam {
        width: 100%;
        height: 340px;
        background: rgba(0,0,0,0.25);
        border-radius: 10px;
        display: flex;
        flex-direction: column;
        align-items: center;
        justify-content: center;
        border: 1px dashed rgba(255,255,255,0.1);
    }
    .no-cam-text {
        font-family: 'JetBrains Mono', monospace;
        font-size: 11px;
        font-weight: 600;
        color: #64748b;
        letter-spacing: 1px;
        text-transform: uppercase;
    }
</style>
""", unsafe_allow_html=True)

# ============================================================
# Configuration
# ============================================================
BACKEND_URL = os.environ.get("BACKEND_URL", "http://localhost:8000")

# ============================================================
# Helpers
# ============================================================
def fetch_status():
    try:
        res = requests.get(f"{BACKEND_URL}/status", timeout=1.5)
        if res.ok:
            return res.json()
    except Exception:
        pass
    return None

def fetch_telemetry_stats():
    try:
        res = requests.get(f"{BACKEND_URL}/backend/telemetry/stats", timeout=1.5)
        if res.ok:
            return res.json()
    except Exception:
        pass
    return {"total_logs": 0, "cached_routes": 0, "cache_hits": 0, "recent_logs": []}

def toggle_mode(mode: str):
    try:
        res = requests.post(f"{BACKEND_URL}/set_mode", json={"mode": mode}, timeout=2)
        return res.ok
    except Exception:
        st.error("Mode switch failed")
        return False

# Initial Fetch
status_data = fetch_status()
if status_data is None:
    status_data = {
        "status": "BACKEND OFFLINE",
        "mode": "unknown",
        "active_phase": "IDLE",
        "cargo_state": "LOCKED",
        "latestLog": "Connecting to AutoDrop backend...",
        "obstacle_detected": False,
        "distance_cm": 999,
        "esp32_connected": False,
        "camera_active": False,
        "gps_app_connected": False,
        "tracking_clients": 0,
        "log_history": [],
        "esp_commands": []
    }

backend_online = status_data.get("status") != "BACKEND OFFLINE"

# ============================================================
# UNIFIED REAL-TIME COCKPIT & TELEMETRY HUD (GSAP POWERED)
# All status pills, velocity, radar, battery, latch, and mission
# phases update in REAL TIME via WebSocket + 1s REST polling!
# ============================================================
hud_html = f"""
<!DOCTYPE html>
<html>
<head>
<meta charset="utf-8">
<style>
    * {{ box-sizing: border-box; margin: 0; padding: 0; user-select: none; }}
    body {{ background: transparent; font-family: 'Inter', -apple-system, BlinkMacSystemFont, sans-serif; color: #f8fafc; }}
    
    .cockpit-wrapper {{
        background: rgba(13, 17, 28, 0.85);
        backdrop-filter: blur(20px);
        -webkit-backdrop-filter: blur(20px);
        border: 1px solid rgba(255, 255, 255, 0.08);
        border-top: 1px solid rgba(255, 255, 255, 0.16);
        border-radius: 14px;
        padding: 16px 20px;
        margin-bottom: 16px;
        box-shadow: 0 12px 28px -6px rgba(0, 0, 0, 0.5), inset 0 1px 0 rgba(255, 255, 255, 0.06);
        display: flex;
        flex-direction: column;
        gap: 14px;
    }}

    /* Top Bar Header */
    .hdr-row {{
        display: flex;
        justify-content: space-between;
        align-items: center;
        padding-bottom: 12px;
        border-bottom: 1px solid rgba(255, 255, 255, 0.06);
    }}

    .brand-group {{
        display: flex;
        align-items: center;
        gap: 10px;
    }}

    .brand-icon {{
        width: 28px;
        height: 28px;
        background: linear-gradient(135deg, #06b6d4, #3b82f6);
        border-radius: 7px;
        display: flex;
        align-items: center;
        justify-content: center;
        font-family: 'JetBrains Mono', monospace;
        font-size: 14px;
        font-weight: 800;
        color: #fff;
        box-shadow: 0 0 12px rgba(6, 182, 212, 0.35);
    }}

    .brand-title {{
        font-size: 15px;
        font-weight: 700;
        letter-spacing: -0.3px;
        color: #ffffff;
    }}

    .brand-sub {{
        font-family: 'JetBrains Mono', monospace;
        font-size: 9px;
        color: #64748b;
        letter-spacing: 1.2px;
        text-transform: uppercase;
    }}

    /* Live Connection Pills */
    .pills-group {{
        display: flex;
        align-items: center;
        gap: 6px;
    }}

    .pill {{
        display: flex;
        align-items: center;
        gap: 6px;
        padding: 4px 9px;
        border-radius: 6px;
        font-family: 'JetBrains Mono', monospace;
        font-size: 10px;
        font-weight: 600;
        letter-spacing: 0.3px;
        background: rgba(255, 255, 255, 0.03);
        border: 1px solid rgba(255, 255, 255, 0.06);
        color: #64748b;
        transition: all 0.25s ease;
    }}

    .pill-dot {{
        width: 6px;
        height: 6px;
        border-radius: 50%;
        background: #475569;
        transition: all 0.25s ease;
    }}

    .pill.online {{
        background: rgba(16, 185, 129, 0.08);
        border-color: rgba(16, 185, 129, 0.25);
        color: #34d399;
    }}
    .pill.online .pill-dot {{
        background: #10b981;
        box-shadow: 0 0 6px #10b981;
    }}

    .pill.offline {{
        background: rgba(239, 68, 68, 0.06);
        border-color: rgba(239, 68, 68, 0.2);
        color: #f87171;
    }}
    .pill.offline .pill-dot {{
        background: #ef4444;
    }}

    .clock-tag {{
        font-family: 'JetBrains Mono', monospace;
        font-size: 11px;
        color: #64748b;
        margin-left: 8px;
    }}

    /* 5-Stage Minimal Mission Stepper */
    .stepper-wrap {{
        display: flex;
        align-items: center;
        justify-content: space-between;
        background: rgba(0, 0, 0, 0.25);
        border: 1px solid rgba(255, 255, 255, 0.04);
        border-radius: 8px;
        padding: 10px 14px;
        position: relative;
    }}

    .step-node {{
        display: flex;
        align-items: center;
        gap: 8px;
        opacity: 0.4;
        transition: opacity 0.3s ease, transform 0.3s ease;
    }}
    .step-node.active {{
        opacity: 1;
        transform: scale(1.02);
    }}

    .step-num {{
        width: 22px;
        height: 22px;
        border-radius: 6px;
        background: rgba(255, 255, 255, 0.06);
        border: 1px solid rgba(255, 255, 255, 0.1);
        display: flex;
        align-items: center;
        justify-content: center;
        font-family: 'JetBrains Mono', monospace;
        font-size: 10px;
        font-weight: 700;
        color: #94a3b8;
        transition: all 0.3s ease;
    }}
    .step-node.active .step-num {{
        background: #06b6d4;
        border-color: #38bdf8;
        color: #000;
        box-shadow: 0 0 10px rgba(6, 182, 212, 0.5);
    }}

    .step-title {{
        font-family: 'Inter', sans-serif;
        font-size: 11px;
        font-weight: 600;
        letter-spacing: 0.4px;
        color: #94a3b8;
    }}
    .step-node.active .step-title {{
        color: #ffffff;
    }}

    .step-line {{
        flex: 1;
        height: 2px;
        background: rgba(255, 255, 255, 0.06);
        margin: 0 10px;
        position: relative;
        overflow: hidden;
        border-radius: 2px;
    }}
    .step-line-fill {{
        position: absolute;
        top: 0; left: 0; bottom: 0; width: 0%;
        background: linear-gradient(90deg, #06b6d4, #3b82f6);
        transition: width 0.4s ease;
    }}

    /* 4 Primary Telemetry Bento Cards */
    .metrics-grid {{
        display: grid;
        grid-template-columns: 1.1fr 1.4fr 1fr 1.1fr;
        gap: 10px;
    }}

    .card {{
        background: rgba(0, 0, 0, 0.22);
        border: 1px solid rgba(255, 255, 255, 0.05);
        border-radius: 10px;
        padding: 10px 14px;
        display: flex;
        flex-direction: column;
        justify-content: space-between;
        min-height: 72px;
    }}

    .card-label {{
        display: flex;
        justify-content: space-between;
        align-items: center;
        font-family: 'JetBrains Mono', monospace;
        font-size: 9px;
        font-weight: 600;
        color: #64748b;
        letter-spacing: 1px;
        text-transform: uppercase;
    }}

    .big-stat {{
        font-family: 'JetBrains Mono', monospace;
        font-size: 22px;
        font-weight: 700;
        color: #f8fafc;
        letter-spacing: -0.5px;
        line-height: 1.1;
        margin: 4px 0 2px 0;
        font-variant-numeric: tabular-nums;
    }}
    .stat-unit {{
        font-size: 11px;
        font-weight: 500;
        color: #64748b;
        margin-left: 3px;
    }}

    .sub-stat {{
        font-family: 'JetBrains Mono', monospace;
        font-size: 10px;
        color: #64748b;
    }}

    /* Radar Mini Gauge */
    .radar-row {{
        display: flex;
        align-items: center;
        gap: 12px;
    }}
    .radar-svg {{
        width: 58px;
        height: 32px;
        overflow: visible;
    }}
    .radar-tag {{
        display: inline-block;
        padding: 2px 6px;
        border-radius: 4px;
        font-family: 'JetBrains Mono', monospace;
        font-size: 9px;
        font-weight: 700;
        letter-spacing: 0.5px;
        background: rgba(16, 185, 129, 0.1);
        color: #10b981;
        margin-top: 2px;
    }}
    .radar-tag.warn {{
        background: rgba(245, 158, 11, 0.12);
        color: #fbbf24;
    }}
    .radar-tag.alert {{
        background: rgba(244, 63, 94, 0.15);
        color: #f43f5e;
    }}

    /* Cargo Latch Pill */
    .latch-chip {{
        display: inline-flex;
        align-items: center;
        gap: 5px;
        padding: 4px 10px;
        border-radius: 6px;
        font-family: 'JetBrains Mono', monospace;
        font-size: 11px;
        font-weight: 700;
        background: rgba(244, 63, 94, 0.1);
        border: 1px solid rgba(244, 63, 94, 0.25);
        color: #fb7185;
        transition: all 0.25s ease;
    }}
    .latch-chip.unlocked {{
        background: rgba(16, 185, 129, 0.12);
        border-color: rgba(16, 185, 129, 0.3);
        color: #34d399;
    }}
</style>
<script src="https://cdnjs.cloudflare.com/ajax/libs/gsap/3.12.5/gsap.min.js"></script>
</head>
<body>
<div class="cockpit-wrapper">

    <!-- 1. Minimal Header Row with Live Connection Pills -->
    <div class="hdr-row">
        <div class="brand-group">
            <div class="brand-icon">AD</div>
            <div>
                <div class="brand-title">AutoDrop™ Mission Control</div>
                <div class="brand-sub">Autonomous Ground Vehicle Fleet • Unit 01</div>
            </div>
        </div>

        <div class="pills-group">
            <div class="pill offline" id="pill-backend"><span class="pill-dot"></span>Backend</div>
            <div class="pill offline" id="pill-arduino"><span class="pill-dot"></span>Arduino (COM7)</div>
            <div class="pill offline" id="pill-camera"><span class="pill-dot"></span>Vision (YOLO)</div>
            <div class="pill offline" id="pill-gps"><span class="pill-dot"></span>GPS Phone</div>
            <div class="pill offline" id="pill-app"><span class="pill-dot"></span>Fleet Client</div>
            <div class="clock-tag" id="live-clock">--:--:--</div>
        </div>
    </div>

    <!-- 2. 5-Stage Mission Breadcrumb -->
    <div class="stepper-wrap">
        <div class="step-node active" id="st-base">
            <div class="step-num">01</div>
            <div class="step-title">Base Dock</div>
        </div>
        <div class="step-line"><div class="step-line-fill" id="sfill-1"></div></div>

        <div class="step-node" id="st-pickup">
            <div class="step-num">02</div>
            <div class="step-title">Sender (Pickup)</div>
        </div>
        <div class="step-line"><div class="step-line-fill" id="sfill-2"></div></div>

        <div class="step-node" id="st-transit">
            <div class="step-num">03</div>
            <div class="step-title">In Transit</div>
        </div>
        <div class="step-line"><div class="step-line-fill" id="sfill-3"></div></div>

        <div class="step-node" id="st-receive">
            <div class="step-num">04</div>
            <div class="step-title">Receiver (Unlock)</div>
        </div>
        <div class="step-line"><div class="step-line-fill" id="sfill-4"></div></div>

        <div class="step-node" id="st-return">
            <div class="step-num">05</div>
            <div class="step-title">Return To Base</div>
        </div>
    </div>

    <!-- 3. Primary Telemetry Bento Cards -->
    <div class="metrics-grid">
        <!-- Velocity & ETA -->
        <div class="card">
            <div class="card-label"><span>GPS VELOCITY</span><span>🛰️</span></div>
            <div class="big-stat" id="stat-speed">0.0<span class="stat-unit">km/h</span></div>
            <div class="sub-stat" id="stat-eta">ETA: Calculating...</div>
        </div>

        <!-- Sonar Radar & Clearance -->
        <div class="card">
            <div class="card-label"><span>ULTRASONIC RADAR</span><span>RADAR</span></div>
            <div class="radar-row">
                <svg viewBox="0 0 100 50" class="radar-svg">
                    <path d="M 10 46 A 40 40 0 0 1 90 46" fill="none" stroke="rgba(255,255,255,0.08)" stroke-width="2.5" stroke-dasharray="3,3" />
                    <path d="M 25 46 A 25 25 0 0 1 75 46" fill="none" stroke="rgba(255,255,255,0.06)" stroke-width="2" />
                    <line id="radar-beam" x1="50" y1="46" x2="50" y2="8" stroke="#06b6d4" stroke-width="2.5" stroke-linecap="round" />
                </svg>
                <div>
                    <div class="big-stat" style="font-size: 17px; margin:0;" id="stat-dist">--<span class="stat-unit">cm</span></div>
                    <div class="radar-tag" id="stat-radar-tag">PATH CLEAR</div>
                </div>
            </div>
        </div>

        <!-- Energy Core & Load -->
        <div class="card">
            <div class="card-label"><span>ENERGY CORE</span><span>PWR</span></div>
            <div class="big-stat" id="stat-battery">--<span class="stat-unit">%</span></div>
            <div class="sub-stat" id="stat-current" style="color:#10b981;">0.0A Draw</div>
        </div>

        <!-- Cargo Compartment -->
        <div class="card">
            <div class="card-label"><span>CARGO COMPARTMENT</span><span>SERVO</span></div>
            <div style="margin-top: 4px;">
                <span class="latch-chip" id="stat-latch">LOCKED (0°)</span>
            </div>
            <div class="sub-stat" style="margin-top: 4px;">Dual PIN & QR Latch</div>
        </div>
    </div>
</div>

<script>
    const BACKEND_URL = "{BACKEND_URL}";
    const wsUrl = BACKEND_URL.replace(/^http/, 'ws') + "/ws/dashboard";
    
    // Live Clock
    function updateClock() {{
        const d = new Date();
        document.getElementById('live-clock').innerText = d.toLocaleTimeString() + " LOCAL";
    }}
    setInterval(updateClock, 1000);
    updateClock();

    // GSAP Continuous Sonar Arc Sweep
    if (window.gsap) {{
        gsap.to('#radar-beam', {{
            rotation: 38,
            transformOrigin: "50px 46px",
            duration: 1.3,
            repeat: -1,
            yoyo: true,
            ease: "sine.inOut"
        }});
    }}

    // State cache to avoid redundant DOM updates
    let lastData = {{}};
    let animSpeed = {{ val: 0 }};
    let animDist = {{ val: 0 }};

    function updatePill(id, online, label) {{
        const el = document.getElementById(id);
        if (!el) return;
        el.className = 'pill ' + (online ? 'online' : 'offline');
        if (label) el.innerHTML = '<span class="pill-dot"></span>' + label;
    }}

    function applyTelemetry(data) {{
        if (!data) return;

        // 1. Connection Status Pills
        const backendOnline = data.status !== 'BACKEND OFFLINE';
        updatePill('pill-backend', backendOnline, backendOnline ? 'Backend' : 'Backend Off');
        updatePill('pill-arduino', !!data.esp32_connected, data.esp32_connected ? 'Arduino COM7' : 'COM7 Off');
        updatePill('pill-camera', !!data.camera_active, data.camera_active ? 'Vision Live' : 'Vision Stby');
        updatePill('pill-gps', !!data.gps_app_connected, data.gps_app_connected ? 'GPS Active' : 'GPS Stby');
        
        const clients = Number(data.tracking_clients || 0);
        updatePill('pill-app', clients > 0, clients > 0 ? 'Fleet (' + clients + ')' : 'Fleet Stby');

        // 2. Velocity with GSAP Smooth Number Rolling
        if (data.gps_speed !== undefined || data.speed !== undefined) {{
            const spd = Number(data.gps_speed !== undefined ? data.gps_speed : data.speed) || 0;
            if (window.gsap) {{
                gsap.to(animSpeed, {{
                    val: spd,
                    duration: 0.35,
                    ease: "power1.out",
                    onUpdate: () => {{
                        document.getElementById('stat-speed').innerHTML = animSpeed.val.toFixed(1) + '<span class="stat-unit">km/h</span>';
                    }}
                }});
            }} else {{
                document.getElementById('stat-speed').innerHTML = spd.toFixed(1) + '<span class="stat-unit">km/h</span>';
            }}
        }}

        // 3. ETA
        const eta = data.eta_seconds;
        const etaEl = document.getElementById('stat-eta');
        if (eta !== undefined && eta !== null) {{
            if (eta > 0) {{
                const m = Math.ceil(eta / 60);
                etaEl.innerText = "ETA: ~" + m + " min (" + eta + "s)";
            }} else {{
                etaEl.innerText = "ETA: Destination Reached";
            }}
        }} else {{
            etaEl.innerText = "ETA: Calculating...";
        }}

        // 4. Ultrasonic Radar & Clearance
        const dist = Number(data.distance_cm !== undefined ? data.distance_cm : 999);
        const distEl = document.getElementById('stat-dist');
        const tagEl = document.getElementById('stat-radar-tag');
        const beamEl = document.getElementById('#radar-beam');

        if (dist < 900) {{
            distEl.innerHTML = dist + '<span class="stat-unit">cm</span>';
            if (dist < 30 || data.obstacle_detected) {{
                tagEl.className = 'radar-tag alert';
                tagEl.innerText = 'OBSTACLE STOP';
            }} else if (dist < 70) {{
                tagEl.className = 'radar-tag warn';
                tagEl.innerText = 'CAUTION SLOW';
            }} else {{
                tagEl.className = 'radar-tag';
                tagEl.innerText = 'PATH CLEAR';
            }}
        }} else {{
            distEl.innerHTML = '--<span class="stat-unit">cm</span>';
            tagEl.className = 'radar-tag';
            tagEl.innerText = 'CLEAR';
        }}

        // 5. Energy Core & Current Draw
        if (data.battery_level !== undefined) {{
            document.getElementById('stat-battery').innerHTML = data.battery_level + '<span class="stat-unit">%</span>';
        }}
        if (data.motor_current !== undefined) {{
            const amps = Number(data.motor_current).toFixed(1);
            document.getElementById('stat-current').innerText = amps + "A Draw";
        }}

        // 6. Cargo Latch
        const latchEl = document.getElementById('stat-latch');
        if (data.cargo_state === 'UNLOCKED' || data.cargo_state === 'OPEN') {{
            latchEl.className = 'latch-chip unlocked';
            latchEl.innerText = 'UNLOCKED (90°)';
        }} else {{
            latchEl.className = 'latch-chip';
            latchEl.innerText = 'LOCKED (0°)';
        }}

        // 7. Mission Phase Stepper & Connecting Lines
        const phase = String(data.active_phase || data.phase || '').toUpperCase();
        const nodes = ['st-base', 'st-pickup', 'st-transit', 'st-receive', 'st-return'];
        nodes.forEach(n => document.getElementById(n).classList.remove('active'));

        const setLines = (w1, w2, w3, w4) => {{
            document.getElementById('sfill-1').style.width = w1;
            document.getElementById('sfill-2').style.width = w2;
            document.getElementById('sfill-3').style.width = w3;
            document.getElementById('sfill-4').style.width = w4;
        }};

        if (phase === 'IDLE' || !phase) {{
            document.getElementById('st-base').classList.add('active');
            setLines('0%', '0%', '0%', '0%');
        }} else if (phase === 'HEADING_TO_SENDER' || phase === 'AWAITING_LOAD') {{
            document.getElementById('st-pickup').classList.add('active');
            setLines('100%', '0%', '0%', '0%');
        }} else if (phase === 'DELIVERING') {{
            document.getElementById('st-transit').classList.add('active');
            setLines('100%', '100%', '0%', '0%');
        }} else if (phase === 'AWAITING_RETRIEVAL') {{
            document.getElementById('st-receive').classList.add('active');
            setLines('100%', '100%', '100%', '0%');
        }} else if (phase === 'RETURNING_TO_BASE') {{
            document.getElementById('st-return').classList.add('active');
            setLines('100%', '100%', '100%', '100%');
        }}
    }}

    // Polling fallback to guarantee instant data on page load
    async function pollStatus() {{
        try {{
            const res = await fetch(BACKEND_URL + '/status', {{ cache: 'no-store' }});
            if (res.ok) {{
                const data = await res.json();
                applyTelemetry(data);
            }}
        }} catch(e) {{
            updatePill('pill-backend', false, 'Backend Off');
        }}
    }}
    pollStatus();
    setInterval(pollStatus, 1000);

    // WebSocket Real-Time Connection
    let ws;
    function connectWS() {{
        try {{
            ws = new WebSocket(wsUrl);
            ws.onopen = () => {{
                updatePill('pill-backend', true, 'Backend');
            }};
            ws.onmessage = (event) => {{
                try {{
                    const payload = JSON.parse(event.data);
                    applyTelemetry(payload);
                }} catch(err) {{}}
            }};
            ws.onclose = () => {{
                setTimeout(connectWS, 2000);
            }};
            ws.onerror = () => {{
                ws.close();
            }};
        }} catch(e) {{
            setTimeout(connectWS, 2000);
        }}
    }}
    connectWS();
</script>
</body>
</html>
"""

components.html(hud_html, height=215)

# ============================================================
# MAIN TWO-COLUMN DASHBOARD LAYOUT
# ============================================================
col_left, col_right = st.columns([5, 3], gap="large")

# ==================== LEFT COLUMN ====================
with col_left:
    # --- LIVE VISION STREAM ---
    st.markdown('<div class="panel">', unsafe_allow_html=True)
    st.markdown('<div class="panel-label">LIVE VISION STREAM — YOLOV8 DETECTION</div>', unsafe_allow_html=True)

    if backend_online and status_data.get("camera_active"):
        st.markdown(f"""
        <div class="video-wrap">
            <img id="yolo-feed" src="{BACKEND_URL}/video_feed" alt="YOLO Feed"
                 onerror="setTimeout(function(){{ document.getElementById('yolo-feed').src='{BACKEND_URL}/video_feed?t='+Date.now(); }}, 2000);" />
            <div class="video-overlay-tl">● LIVE</div>
            <div class="video-overlay-tr">YOLOv8n • 640×480 • 30 FPS</div>
        </div>
        """, unsafe_allow_html=True)
    else:
        st.markdown("""
        <div class="no-cam">
            <div class="no-cam-text">Camera Index 0 Standby</div>
            <div style="font-size:11px; color:#475569; margin-top:4px;">Awaiting video stream signal from backend</div>
        </div>
        """, unsafe_allow_html=True)
    st.markdown('</div>', unsafe_allow_html=True)

    # --- REAL-TIME SYSTEM & HARDWARE LOG TERMINAL ---
    @st.fragment(run_every="1s")
    def render_system_log():
        import html
        s = fetch_status() or status_data
        st.markdown('<div class="panel">', unsafe_allow_html=True)
        st.markdown('<div class="panel-label">SYSTEM EVENT LOG</div>', unsafe_allow_html=True)
    
        log_history = s.get("log_history", [])
        if log_history:
            log_html = ""
            for log in reversed(log_history[-15:]):
                if "]" in log:
                    ts, msg = log.split("]", 1)
                    ts, msg = html.escape(ts), html.escape(msg)
                    log_html += f'<div class="log-line"><span class="log-timestamp">{ts}]</span>{msg}</div>'
                else:
                    log_html += f'<div class="log-line">{html.escape(log)}</div>'
            st.markdown(f'<div class="log-terminal">{log_html}</div>', unsafe_allow_html=True)
        else:
            st.markdown('<div class="log-terminal"><div class="log-line" style="color:#64748b; text-align:center;">Waiting for system telemetry...</div></div>', unsafe_allow_html=True)
        st.markdown('</div>', unsafe_allow_html=True)
        
        # --- BOT HARDWARE COMMAND TERMINAL ---
        st.markdown('<div class="panel" style="margin-top: 14px;">', unsafe_allow_html=True)
        st.markdown('<div class="panel-label">ARDUINO SERIAL FEED (COM7)</div>', unsafe_allow_html=True)
    
        esp_history = s.get("esp_commands", [])
        if esp_history:
            esp_html = ""
            for log in reversed(esp_history[-10:]):
                if "]" in log:
                    ts, msg = log.split("]", 1)
                    ts, msg = html.escape(ts), html.escape(msg)
                    color = "#34d399" if "SENT" in msg else "#38bdf8" if "RECV" in msg else "#94a3b8"
                    esp_html += f'<div class="log-line"><span class="log-timestamp">{ts}]</span><span style="color:{color}; font-weight:600;">{msg}</span></div>'
                else:
                    esp_html += f'<div class="log-line">{html.escape(log)}</div>'
            st.markdown(f'<div class="log-terminal" style="max-height:130px;">{esp_html}</div>', unsafe_allow_html=True)
        else:
            st.markdown('<div class="log-terminal" style="max-height:130px;"><div class="log-line" style="color:#64748b; text-align:center;">No serial commands exchanged...</div></div>', unsafe_allow_html=True)
        st.markdown('</div>', unsafe_allow_html=True)
        
    render_system_log()

    # --- MISSION TELEMETRY BLACKBOX ---
    @st.fragment(run_every="2s")
    def render_mission_telemetry_cache():
        t_stats = fetch_telemetry_stats()
        total_logs = t_stats.get("total_logs", 0)
        cached_routes = t_stats.get("cached_routes", 0)
        cache_hits = t_stats.get("cache_hits", 0)
        recent_logs = t_stats.get("recent_logs", [])
        
        st.markdown('<div class="panel" style="margin-top: 14px;">', unsafe_allow_html=True)
        st.markdown('<div class="panel-label">TELEMETRY BLACKBOX & ROUTE CACHE</div>', unsafe_allow_html=True)
        
        c1, c2, c3 = st.columns(3)
        with c1:
            st.markdown(f"""
            <div class="metric-tile">
                <div class="metric-tile-value" style="color:#38bdf8;">{total_logs:,}</div>
                <div class="metric-tile-label">FLIGHT TICKS</div>
            </div>
            """, unsafe_allow_html=True)
        with c2:
            st.markdown(f"""
            <div class="metric-tile">
                <div class="metric-tile-value" style="color:#a855f7;">{cached_routes}</div>
                <div class="metric-tile-label">ROUTES CACHED</div>
            </div>
            """, unsafe_allow_html=True)
        with c3:
            st.markdown(f"""
            <div class="metric-tile">
                <div class="metric-tile-value" style="color:#34d399;">{cache_hits}</div>
                <div class="metric-tile-label">CACHE HITS</div>
            </div>
            """, unsafe_allow_html=True)
            
        if recent_logs:
            rows_html = ""
            for r in recent_logs[:5]:
                ts = r.get("timestamp", "").split()[-1] if r.get("timestamp") else "--:--:--"
                cmd = r.get("motor_cmd", "stop")
                phase = (r.get("phase") or "IDLE")[:8]
                dist = r.get("ultrasonic_cm", 999)
                bias = r.get("steer_bias", 0.0)
                cmd_color = "#38bdf8" if "steer" in cmd or "curve" in cmd else "#34d399" if "forward" in cmd or "slow" in cmd else "#f43f5e" if "stop" in cmd else "#fbbf24"
                dist_str = f"{dist}cm" if dist < 900 else "--"
                bias_str = f"b:{bias:+.2f}" if abs(bias) > 0.01 else "--"
                
                rows_html += f"""
                <div class="log-line" style="display:flex; justify-content:space-between; font-size:10px; padding:3px 0; border-bottom:1px solid rgba(255,255,255,0.02);">
                    <span style="color:#64748b; width:60px;">{ts}</span>
                    <span style="color:#94a3b8; font-weight:600; width:70px;">{phase}</span>
                    <span style="color:{cmd_color}; font-weight:700; flex:1;">{cmd}</span>
                    <span style="color:#e2e8f0; width:45px; text-align:right;">{dist_str}</span>
                    <span style="color:#a78bfa; width:50px; text-align:right;">{bias_str}</span>
                </div>
                """
            st.markdown(f'<div class="log-terminal" style="max-height:120px; margin-top:8px;">{rows_html}</div>', unsafe_allow_html=True)
        st.markdown('</div>', unsafe_allow_html=True)
        
    render_mission_telemetry_cache()


# ==================== RIGHT COLUMN ====================
with col_right:
    # --- AUTONOMOUS STATE & CONTROLS ---
    @st.fragment(run_every="1s")
    def render_status_controls():
        s = fetch_status() or status_data
        is_manual = s.get("mode") == "manual"
        phase = s.get("active_phase", "IDLE")
    
        # Status Card
        st.markdown('<div class="panel">', unsafe_allow_html=True)
        st.markdown('<div class="panel-label">AUTONOMOUS MISSION STATE</div>', unsafe_allow_html=True)
        
        st.markdown(f'<div class="status-badge">PHASE: {phase}</div>', unsafe_allow_html=True)
        st.markdown(f'<div class="status-readout">{s.get("status", "IDLE")}</div>', unsafe_allow_html=True)
        st.markdown(f'<div class="status-detail">{s.get("latestLog", "")}</div>', unsafe_allow_html=True)
    
        # Clean Metrics Row
        m1, m2, m3 = st.columns(3)
        with m1:
            is_blocked = "IN PATH" in s["status"] or "STOP" in s["status"] or "TOO CLOSE" in s["status"]
            is_seen = s["status"] != "🔍 SEARCHING" and "PATH CLEAR" not in s["status"]
            obs_color, obs_text = ("#ef4444", "BLOCKED") if is_blocked else ("#f59e0b", "DETECTED") if is_seen else ("#10b981", "CLEAR")
            st.markdown(f"""
            <div class="metric-tile">
                <div class="metric-tile-value" style="color:{obs_color}">{obs_text}</div>
                <div class="metric-tile-label">CORRIDOR</div>
            </div>
            """, unsafe_allow_html=True)
        with m2:
            mode_label = "MANUAL" if is_manual else "AUTO"
            mode_color = "#f87171" if is_manual else "#38bdf8"
            st.markdown(f"""
            <div class="metric-tile">
                <div class="metric-tile-value" style="color:{mode_color}">{mode_label}</div>
                <div class="metric-tile-label">CONTROL</div>
            </div>
            """, unsafe_allow_html=True)
        with m3:
            cargo_state = s.get("cargo_state", "LOCKED")
            c_color = "#ef4444" if cargo_state == "LOCKED" else "#34d399"
            st.markdown(f"""
            <div class="metric-tile">
                <div class="metric-tile-value" style="color:{c_color}">{cargo_state}</div>
                <div class="metric-tile-label">CARGO</div>
            </div>
            """, unsafe_allow_html=True)
            
        st.markdown('</div>', unsafe_allow_html=True)
    
    render_status_controls()

    # --- FLEET COMMAND PANEL ---
    st.markdown('<div class="panel">', unsafe_allow_html=True)
    st.markdown('<div class="panel-label">FLEET COMMAND & OVERRIDE</div>', unsafe_allow_html=True)
    
    if st.session_state.get("open_manual_drive"):
        components.html(f"<script>window.open('{BACKEND_URL}/drive', '_blank');</script>", height=0)
        st.session_state["open_manual_drive"] = False

    mode_status = fetch_status() or status_data
    is_manual_now = mode_status.get("mode") == "manual"

    col_btn1, col_btn2 = st.columns(2)
    with col_btn1:
        if is_manual_now:
            if st.button("AUTONOMOUS MODE", use_container_width=True, key="mode_btn"):
                toggle_mode("autonomous")
                st.rerun()
        else:
            if st.button("MANUAL OVERRIDE", use_container_width=True, key="mode_btn"):
                toggle_mode("manual")
                st.session_state["open_manual_drive"] = True
                st.rerun()

    with col_btn2:
        if st.button("RETURN TO BASE", use_container_width=True, key="rtb_btn"):
            try:
                res = requests.post(f"{BACKEND_URL}/backend/return_to_base", timeout=3)
                if res.status_code == 200:
                    st.toast("Returning to Base Dock Charging Station", icon="🏠")
            except Exception as e:
                st.error(f"Error: {e}")
            st.rerun()
            
    st.markdown('<div style="margin-top: 10px; border-top: 1px solid rgba(255,255,255,0.06); padding-top: 8px;"></div>', unsafe_allow_html=True)
    routing_choice = st.selectbox("Routing Engine", ["Google Maps API (Dense Geodesic)", "Internal Campus Graph"], index=0, key="routing_engine")
    engine_val = "google" if "Google" in routing_choice else "self"
    if "last_routing_engine" not in st.session_state or st.session_state["last_routing_engine"] != engine_val:
        st.session_state["last_routing_engine"] = engine_val
        try:
            requests.post(f"{BACKEND_URL}/backend/set_routing_engine", json={"engine": engine_val}, timeout=2)
        except Exception:
            pass
    st.markdown('</div>', unsafe_allow_html=True)

    # --- SCANNABLE CARGO SECURITY QR PASS ---
    st.markdown('<div class="panel">', unsafe_allow_html=True)
    st.markdown('<div class="panel-label">CARGO LATCH & SCANNABLE QR PASS</div>', unsafe_allow_html=True)
    
    cargo_status = status_data.get("cargo_state", "LOCKED")
    is_unlocked = cargo_status == "UNLOCKED" or cargo_status == "OPEN"
    
    qr_endpoint = f"{BACKEND_URL}/backend/verify_qr?cart_id=CART_01&action=unlock"
    qr_img_src = f"https://api.qrserver.com/v1/create-qr-code/?size=220x220&data={qr_endpoint}&bgcolor=11-16-26&color=38bdf8"
    
    col_qr, col_latch_act = st.columns([1, 1], gap="medium")
    with col_qr:
        st.markdown(f"""
        <style>
            @keyframes laserSweep {{
                0% {{ top: 4px; opacity: 0; }}
                20% {{ opacity: 1; }}
                80% {{ opacity: 1; }}
                100% {{ top: 118px; opacity: 0; }}
            }}
            .laser-line {{
                position: absolute;
                left: 0; right: 0; height: 2px;
                background: linear-gradient(90deg, transparent, #38bdf8, #06b6d4, transparent);
                box-shadow: 0 0 10px #38bdf8;
                animation: laserSweep 2s ease-in-out infinite;
            }}
        </style>
        <div style="text-align: center; background: rgba(0,0,0,0.3); border: 1px solid rgba(255,255,255,0.06); border-radius: 10px; padding: 10px; position: relative;">
            <div style="font-family: 'JetBrains Mono', monospace; font-size: 9px; color: #38bdf8; margin-bottom: 6px; font-weight: 700; letter-spacing: 0.8px;">SCAN WITH PHONE CAMERA</div>
            <div style="position: relative; display: inline-block; border-radius: 8px; overflow: hidden; border: 1px solid #06b6d4;">
                <div class="laser-line"></div>
                <img src="{qr_img_src}" alt="Scan to Unlock" style="display: block; width: 120px; height: 120px;" />
            </div>
            <div style="font-size: 9px; color: #64748b; margin-top: 6px;">Opens latch to 90°</div>
        </div>
        """, unsafe_allow_html=True)
        
    with col_latch_act:
        state_badge = '<span style="color:#34d399; font-weight:700; font-size:14px;">UNLOCKED (90°)</span>' if is_unlocked else '<span style="color:#f87171; font-weight:700; font-size:14px;">LOCKED (0°)</span>'
        st.markdown(f"""
        <div style="padding: 4px 0 10px 0;">
            <div style="font-size: 10px; color: #64748b; font-family: 'JetBrains Mono';">HARDWARE SERVO:</div>
            <div style="margin: 4px 0 10px 0;">{state_badge}</div>
        </div>
        """, unsafe_allow_html=True)
        
        if st.button("UNLOCK LATCH (90°)", key="btn_unlock_servo", use_container_width=True):
            try:
                requests.post(f"{BACKEND_URL}/backend/verify_qr", json={"action": "unlock", "cart_id": "CART_01"}, timeout=3)
                st.toast("Latch servo rotated to 90° (Unlocked)", icon="🔓")
            except Exception as e:
                st.error(f"Error: {e}")
            st.rerun()
            
        if st.button("LOCK LATCH (0°)", key="btn_lock_servo", use_container_width=True):
            try:
                requests.post(f"{BACKEND_URL}/backend/pack_order", timeout=3)
                st.toast("Latch servo secured to 0° (Locked)", icon="🔒")
            except Exception as e:
                st.error(f"Error: {e}")
            st.rerun()
            
    st.markdown('</div>', unsafe_allow_html=True)

    # --- SATELLITE & CYBER DARK TRACKING MAP ---
    st.markdown('<div class="panel">', unsafe_allow_html=True)
    st.markdown('<div class="panel-label">GOOGLE MAPS SATELLITE & WAYPOINT TRACKING</div>', unsafe_allow_html=True)
    
    GMAPS_API_KEY = os.environ.get("GMAPS_API_KEY", "AIzaSyBX0xNBFK24V2DZgMQHFku3tWcJWtVjgds")
    
    map_html = f"""
    <!DOCTYPE html>
    <html>
    <head>
        <style>
            * {{ box-sizing: border-box; margin:0; padding:0; }}
            #map-wrapper {{ position: relative; width: 100%; height: 360px; border-radius: 10px; overflow: hidden; border: 1px solid rgba(255,255,255,0.08); }}
            #map {{ height: 100%; width: 100%; }}
            .map-ctrl-bar {{
                position: absolute;
                top: 10px;
                right: 10px;
                z-index: 10;
                display: flex;
                gap: 4px;
                background: rgba(10, 14, 22, 0.9);
                backdrop-filter: blur(10px);
                border: 1px solid rgba(255, 255, 255, 0.1);
                border-radius: 6px;
                padding: 3px;
            }}
            .map-type-btn {{
                background: transparent;
                border: none;
                color: #94a3b8;
                font-family: 'Inter', sans-serif;
                font-size: 10px;
                font-weight: 600;
                padding: 4px 8px;
                border-radius: 4px;
                cursor: pointer;
                transition: all 0.15s;
            }}
            .map-type-btn.active {{
                background: #06b6d4;
                color: #000;
            }}
            .phase-hud {{
                position: absolute;
                bottom: 10px;
                left: 10px;
                z-index: 10;
                background: rgba(10, 14, 22, 0.9);
                backdrop-filter: blur(10px);
                border: 1px solid rgba(255, 255, 255, 0.1);
                border-radius: 6px;
                padding: 5px 12px;
                font-family: 'JetBrains Mono', monospace;
                font-size: 10px;
                color: #38bdf8;
                font-weight: 700;
                display: flex;
                align-items: center;
                gap: 6px;
            }}
            .hud-dot {{
                width: 6px;
                height: 6px;
                border-radius: 50%;
                background: #10b981;
                box-shadow: 0 0 6px #10b981;
            }}
        </style>
        <script src="https://cdnjs.cloudflare.com/ajax/libs/gsap/3.12.5/gsap.min.js"></script>
        <script>
            (g=>{{var h,a,k,p="The Google Maps JavaScript API",c="google",l="importLibrary",q="__ib__",m=document,b=window;b=b[c]||(b[c]={{}});var d=b.maps||(b.maps={{}}),r=new Set,e=new URLSearchParams,u=()=>h||(h=new Promise(async(f,n)=>{{await (a=m.createElement("script"));e.set("libraries",[...r]+"");for(k in g)e.set(k.replace(/[A-Z]/g,t=>"_"+t[0].toLowerCase()),g[k]);e.set("callback",c+".maps."+q);a.src=`https://maps.${{c}}apis.com/maps/api/js?`+e;d[q]=f;a.onerror=()=>h=n(Error(p+" could not load."));a.nonce=m.querySelector("script[nonce]")?.nonce||"";m.head.append(a)}}));d[l]?console.warn(p+" only loads once. Ignoring:",g):d[l]=(f,...n)=>r.add(f)&&u().then(()=>d[l](f,...n))}})({{
                key: "{GMAPS_API_KEY}",
                v: "weekly"
            }});
        </script>
    </head>
    <body>
        <div id="map-wrapper">
            <div class="map-ctrl-bar">
                <button class="map-type-btn active" id="btn-dark" onclick="setMode('dark')">Dark Cyber</button>
                <button class="map-type-btn" id="btn-sat" onclick="setMode('hybrid')">Satellite</button>
            </div>
            <div class="phase-hud" id="phase-hud">
                <span class="hud-dot" id="hud-dot"></span>
                <span id="hud-text">PHASE: IDLE (DOCKED)</span>
            </div>
            <div id="map"></div>
        </div>

        <script>
            let map, botMarker, chargingMarker, sourceMarker, destMarker, routePoly;
            
            const darkMapStyles = [
                {{ elementType: 'geometry', stylers: [{{ color: '#0d131f' }}] }},
                {{ elementType: 'labels.text.stroke', stylers: [{{ color: '#070a10' }}] }},
                {{ elementType: 'labels.text.fill', stylers: [{{ color: '#94a3b8' }}] }},
                {{ featureType: 'road', elementType: 'geometry', stylers: [{{ color: '#1e293b' }}] }},
                {{ featureType: 'road.highway', elementType: 'geometry', stylers: [{{ color: '#334155' }}] }},
                {{ featureType: 'water', elementType: 'geometry', stylers: [{{ color: '#070a10' }}] }},
                {{ featureType: 'poi', elementType: 'labels.text.fill', stylers: [{{ color: '#64748b' }}] }}
            ];

            function setMode(mode) {{
                if (!map) return;
                document.getElementById('btn-dark').classList.toggle('active', mode === 'dark');
                document.getElementById('btn-sat').classList.toggle('active', mode === 'hybrid');
                if (mode === 'dark') {{
                    map.setMapTypeId('roadmap');
                    map.setOptions({{ styles: darkMapStyles }});
                }} else {{
                    map.setMapTypeId('hybrid');
                    map.setOptions({{ styles: [] }});
                }}
            }}

            async function initMap() {{
                const {{ Map }} = await google.maps.importLibrary("maps");
                
                map = new Map(document.getElementById("map"), {{
                    zoom: 16,
                    center: {{ lat: 24.4332, lng: 77.1585 }}, // Default JUET Campus
                    styles: darkMapStyles,
                    disableDefaultUI: true,
                    zoomControl: true,
                }});

                // Dynamic Directional Arrow for Autonomous Cart
                botMarker = new google.maps.Marker({{ 
                    map: map, 
                    icon: {{
                        path: google.maps.SymbolPath.FORWARD_CLOSED_ARROW,
                        scale: 6,
                        fillColor: '#10b981',
                        fillOpacity: 1,
                        strokeColor: '#070a10',
                        strokeWeight: 2,
                        rotation: 0,
                    }},
                    zIndex: 100,
                    title: "AutoDrop Cart"
                }});

                // Base Dock Charging Station Cyan Marker
                chargingMarker = new google.maps.Marker({{
                    map: map,
                    icon: {{
                        path: google.maps.SymbolPath.CIRCLE,
                        scale: 8,
                        fillColor: '#06b6d4',
                        fillOpacity: 1,
                        strokeColor: '#083344',
                        strokeWeight: 2,
                    }},
                    title: "Base Dock Charging Station"
                }});

                // Sender (Pickup) White Circle Marker
                sourceMarker = new google.maps.Marker({{
                    map: map,
                    icon: {{
                        path: google.maps.SymbolPath.CIRCLE,
                        scale: 7,
                        fillColor: '#ffffff',
                        fillOpacity: 1,
                        strokeColor: '#1e293b',
                        strokeWeight: 2,
                    }},
                    title: "Pickup Location"
                }});

                // Destination (Receiver) Amber Circle Marker
                destMarker = new google.maps.Marker({{
                    map: map,
                    icon: {{
                        path: google.maps.SymbolPath.CIRCLE,
                        scale: 7,
                        fillColor: '#f59e0b',
                        fillOpacity: 1,
                        strokeColor: '#451a03',
                        strokeWeight: 2,
                    }},
                    title: "Delivery Destination"
                }});

                // Dense Route Polyline
                routePoly = new google.maps.Polyline({{
                    map: map,
                    strokeColor: '#06b6d4',
                    strokeOpacity: 0.9,
                    strokeWeight: 4,
                }});

                startMapWS();
            }}

            function startMapWS() {{
                const ws = new WebSocket("{BACKEND_URL}".replace(/^http/, 'ws') + "/ws/track");
                
                ws.onmessage = (event) => {{
                    try {{
                        const data = JSON.parse(event.data);
                        if (data.type !== 'location_update') return;

                        const bounds = new google.maps.LatLngBounds();
                        let hasBounds = false;
                        
                        // Update Phase HUD
                        if (data.phase) {{
                            const hudEl = document.getElementById('hud-text');
                            if (hudEl && hudEl.innerText !== "PHASE: " + data.phase) {{
                                hudEl.innerText = "PHASE: " + data.phase;
                                if (window.gsap) {{
                                    gsap.fromTo('#phase-hud', 
                                        {{ scale: 0.94 }}, 
                                        {{ scale: 1.0, duration: 0.35, ease: "back.out(2)" }}
                                    );
                                }}
                            }}
                        }}

                        // 1. Cart live location
                        if (data.cart && data.cart.latitude) {{
                            const pos = {{ lat: data.cart.latitude, lng: data.cart.longitude }};
                            botMarker.setPosition(pos);
                            if (data.cart.heading !== undefined) {{
                                const icon = botMarker.getIcon();
                                icon.rotation = data.cart.heading;
                                botMarker.setIcon(icon);
                            }}
                            bounds.extend(pos);
                            hasBounds = true;
                        }}

                        // 2. Base Dock Charging Station
                        if (data.charging_station && data.charging_station.lat) {{
                            const pos = {{ lat: data.charging_station.lat, lng: data.charging_station.lng }};
                            chargingMarker.setPosition(pos);
                            bounds.extend(pos);
                            hasBounds = true;
                        }}

                        // 3. Sender Location
                        if (data.source && data.source.latitude) {{
                            const pos = {{ lat: data.source.latitude, lng: data.source.longitude }};
                            sourceMarker.setPosition(pos);
                            bounds.extend(pos);
                            hasBounds = true;
                        }}

                        // 4. Destination Location
                        if (data.destination && data.destination.latitude) {{
                            const pos = {{ lat: data.destination.latitude, lng: data.destination.longitude }};
                            destMarker.setPosition(pos);
                            bounds.extend(pos);
                            hasBounds = true;
                        }}

                        // 5. Dense Google Maps Waypoint Polyline
                        if (data.route_points && data.route_points.length > 0) {{
                            const path = data.route_points.map(p => ({{ lat: p.lat, lng: p.lng }}));
                            routePoly.setPath(path);
                        }} else {{
                            routePoly.setPath([]);
                        }}

                        if (hasBounds && !map._fitted) {{
                            map.fitBounds(bounds, 50);
                            map._fitted = true;
                        }}
                    }} catch(e) {{}}
                }};
                
                ws.onclose = () => setTimeout(startMapWS, 2000);
            }}

            window.onload = initMap;
        </script>
    </body>
    </html>
    """

    components.html(map_html, height=380)
    st.markdown('</div>', unsafe_allow_html=True)
