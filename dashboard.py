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
    page_icon="🤖",
    layout="wide",
    initial_sidebar_state="collapsed"
)

# ============================================================
# Executive Cyber-Dark Glassmorphic Theme & GSAP Stylesheet
# ============================================================
st.markdown("""
<style>
    @import url('https://fonts.googleapis.com/css2?family=Outfit:wght@400;500;600;700;800&family=JetBrains+Mono:wght@400;500;600;700&family=Inter:wght@400;500;600;700;800&display=swap');
    
    :root {
        --bg-main: #06080e;
        --bg-panel: linear-gradient(145deg, rgba(18, 24, 38, 0.72), rgba(10, 14, 24, 0.78));
        --border-color: rgba(255, 255, 255, 0.08);
        --border-glow: rgba(56, 189, 248, 0.35);
        --cyan-neon: #06b6d4;
        --emerald-neon: #10b981;
        --amber-neon: #f59e0b;
        --purple-neon: #8b5cf6;
        --rose-neon: #f43f5e;
        --text-main: #f8fafc;
        --text-muted: #94a3b8;
    }

    /* Ambient Background Mesh */
    .stApp {
        background-color: var(--bg-main) !important;
        background-image: 
            radial-gradient(circle at 10% 8%, rgba(6, 182, 212, 0.12) 0%, transparent 40%),
            radial-gradient(circle at 90% 15%, rgba(139, 92, 246, 0.10) 0%, transparent 45%),
            radial-gradient(circle at 50% 95%, rgba(16, 185, 129, 0.08) 0%, transparent 50%) !important;
        background-attachment: fixed !important;
        color: var(--text-main);
        font-family: 'Outfit', 'Inter', -apple-system, sans-serif;
    }

    #MainMenu, footer, .stDeployButton, header { display: none !important; }

    ::-webkit-scrollbar { width: 6px; }
    ::-webkit-scrollbar-track { background: transparent; }
    ::-webkit-scrollbar-thumb { background: rgba(255,255,255,0.12); border-radius: 10px; }
    ::-webkit-scrollbar-thumb:hover { background: rgba(56, 189, 248, 0.3); }

    /* Hide Streamlit fragment re-render flash */
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

    /* ===== LUXURY TOP BAR ===== */
    .topbar {
        background: linear-gradient(180deg, rgba(12, 16, 28, 0.94) 0%, rgba(8, 11, 18, 0.90) 100%);
        backdrop-filter: blur(28px);
        -webkit-backdrop-filter: blur(28px);
        border-bottom: 1px solid rgba(255, 255, 255, 0.1);
        padding: 16px 36px;
        display: flex;
        justify-content: space-between;
        align-items: center;
        margin: -1.2rem -1.2rem 20px -1.2rem;
        position: sticky;
        top: 0;
        z-index: 999;
        box-shadow: 0 10px 30px -5px rgba(0, 0, 0, 0.6);
    }

    .brand-wrap {
        display: flex;
        align-items: center;
        gap: 14px;
    }

    .brand-logo-icon {
        width: 38px;
        height: 38px;
        background: linear-gradient(135deg, #06b6d4, #3b82f6);
        border-radius: 10px;
        display: flex;
        align-items: center;
        justify-content: center;
        font-size: 20px;
        box-shadow: 0 0 18px rgba(6, 182, 212, 0.4);
    }

    .topbar-title {
        font-family: 'Outfit', sans-serif;
        font-size: 20px;
        font-weight: 800;
        letter-spacing: 0.5px;
        line-height: 1.1;
    }
    
    .topbar-title span {
        background: linear-gradient(90deg, #ffffff 0%, #38bdf8 60%, #818cf8 100%);
        -webkit-background-clip: text;
        -webkit-text-fill-color: transparent;
    }

    .topbar-subtitle {
        font-family: 'JetBrains Mono', monospace;
        font-size: 10px;
        color: #94a3b8;
        letter-spacing: 1.8px;
        text-transform: uppercase;
        margin-top: 3px;
    }

    .topbar-right {
        display: flex;
        align-items: center;
        gap: 18px;
    }

    .live-clock {
        font-family: 'JetBrains Mono', monospace;
        font-size: 12px;
        color: #94a3b8;
        background: rgba(255,255,255,0.04);
        padding: 6px 14px;
        border-radius: 8px;
        border: 1px solid var(--border-color);
    }

    /* ===== CONNECTION PILLS ===== */
    .conn-group { display: flex; gap: 8px; }
    .conn-pill {
        display: flex;
        align-items: center;
        gap: 7px;
        padding: 5px 12px;
        border-radius: 30px;
        font-family: 'JetBrains Mono', monospace;
        font-size: 11px;
        font-weight: 600;
        letter-spacing: 0.5px;
        transition: all 0.3s ease;
    }
    .conn-online {
        background: rgba(16, 185, 129, 0.1);
        border: 1px solid rgba(16, 185, 129, 0.3);
        color: #34d399;
        box-shadow: 0 0 12px rgba(16, 185, 129, 0.15);
    }
    .conn-offline {
        background: rgba(239, 68, 68, 0.08);
        border: 1px solid rgba(239, 68, 68, 0.25);
        color: #f87171;
    }
    
    .conn-dot {
        width: 6px; height: 6px;
        border-radius: 50%;
    }
    .conn-dot-on { background: #34d399; box-shadow: 0 0 8px #34d399; }
    .conn-dot-off { background: #f87171; box-shadow: 0 0 8px #f87171; }

    @keyframes pulseRing {
        0% { transform: scale(0.95); opacity: 0.8; }
        50% { transform: scale(1.15); opacity: 0.3; }
        100% { transform: scale(0.95); opacity: 0.8; }
    }
    .conn-online .conn-dot { animation: pulseRing 2s ease-in-out infinite; }

    /* ===== BENTO GLASS PANELS ===== */
    .panel {
        background: var(--bg-panel);
        border: 1px solid var(--border-color);
        border-top: 1px solid rgba(255, 255, 255, 0.16);
        border-radius: 18px;
        padding: 22px;
        margin-bottom: 20px;
        backdrop-filter: blur(24px);
        -webkit-backdrop-filter: blur(24px);
        box-shadow: 0 16px 36px -10px rgba(0, 0, 0, 0.6), inset 0 1px 0 rgba(255, 255, 255, 0.08);
        transition: all 0.25s cubic-bezier(0.16, 1, 0.3, 1);
        position: relative;
        overflow: hidden;
    }
    
    .panel::after {
        content: '';
        position: absolute;
        top: 0; left: 0; right: 0; height: 1px;
        background: linear-gradient(90deg, transparent, rgba(56, 189, 248, 0.35), transparent);
    }

    .panel:hover {
        border-color: rgba(255, 255, 255, 0.16);
        transform: translateY(-2px);
        box-shadow: 0 20px 45px -8px rgba(6, 182, 212, 0.15), inset 0 1px 0 rgba(255, 255, 255, 0.15);
    }

    .panel-label {
        font-family: 'Outfit', sans-serif;
        font-size: 11px;
        font-weight: 700;
        color: #94a3b8;
        letter-spacing: 1.6px;
        text-transform: uppercase;
        margin-bottom: 18px;
        display: flex;
        align-items: center;
        gap: 10px;
    }
    .panel-label::before {
        content: '';
        width: 6px; height: 6px;
        background: var(--cyan-neon);
        border-radius: 50%;
        box-shadow: 0 0 10px var(--cyan-neon);
    }

    /* ===== STATUS READOUT ===== */
    .status-badge {
        display: inline-flex;
        align-items: center;
        gap: 8px;
        background: rgba(6, 182, 212, 0.12);
        border: 1px solid rgba(6, 182, 212, 0.3);
        padding: 6px 14px;
        border-radius: 999px;
        font-family: 'JetBrains Mono', monospace;
        font-size: 12px;
        font-weight: 700;
        color: #38bdf8;
        margin-bottom: 10px;
    }

    .status-readout {
        font-family: 'Outfit', sans-serif;
        font-size: 22px;
        font-weight: 800;
        color: #ffffff;
        letter-spacing: -0.3px;
        margin-bottom: 6px;
    }
    
    .status-detail {
        font-family: 'JetBrains Mono', monospace;
        font-size: 12px;
        color: #94a3b8;
        line-height: 1.5;
    }

    /* ===== METRIC TILES ===== */
    .metric-tile {
        background: rgba(0, 0, 0, 0.32);
        border: 1px solid rgba(255, 255, 255, 0.07);
        border-top: 1px solid rgba(255, 255, 255, 0.12);
        border-radius: 14px;
        padding: 16px 14px;
        text-align: center;
        transition: all 0.2s ease;
    }
    .metric-tile:hover {
        background: rgba(255, 255, 255, 0.03);
        border-color: rgba(56, 189, 248, 0.3);
        transform: translateY(-1px);
    }
    .metric-tile-value {
        font-family: 'JetBrains Mono', monospace;
        font-size: 24px;
        font-weight: 700;
        color: #f8fafc;
        letter-spacing: -0.5px;
    }
    .metric-tile-unit {
        font-family: 'Outfit', sans-serif;
        font-size: 12px;
        font-weight: 600;
        color: #94a3b8;
        margin-left: 2px;
    }
    .metric-tile-label {
        font-family: 'Outfit', sans-serif;
        font-size: 10px;
        color: #94a3b8;
        letter-spacing: 1.2px;
        text-transform: uppercase;
        margin-top: 6px;
        font-weight: 700;
    }

    /* ===== VIDEO WRAPPER WITH HUD FRAME ===== */
    .video-wrap {
        border-radius: 14px;
        overflow: hidden;
        border: 1px solid rgba(255, 255, 255, 0.1);
        background: #000;
        position: relative;
        box-shadow: 0 10px 30px rgba(0,0,0,0.7);
    }
    .video-wrap img {
        width: 100%;
        display: block;
        opacity: 0.95;
    }
    
    .video-reticle-tl { position: absolute; top: 10px; left: 10px; width: 14px; height: 14px; border-top: 2px solid #38bdf8; border-left: 2px solid #38bdf8; }
    .video-reticle-tr { position: absolute; top: 10px; right: 10px; width: 14px; height: 14px; border-top: 2px solid #38bdf8; border-right: 2px solid #38bdf8; }
    .video-reticle-bl { position: absolute; bottom: 10px; left: 10px; width: 14px; height: 14px; border-bottom: 2px solid #38bdf8; border-left: 2px solid #38bdf8; }
    .video-reticle-br { position: absolute; bottom: 10px; right: 10px; width: 14px; height: 14px; border-bottom: 2px solid #38bdf8; border-right: 2px solid #38bdf8; }

    .video-overlay-tl {
        position: absolute;
        top: 14px; left: 18px;
        font-family: 'JetBrains Mono', monospace;
        font-size: 10px;
        font-weight: 700;
        color: #fff;
        background: rgba(225, 29, 72, 0.85);
        padding: 4px 10px;
        border-radius: 6px;
        letter-spacing: 0.8px;
        display: flex;
        align-items: center;
        gap: 6px;
        box-shadow: 0 0 12px rgba(225, 29, 72, 0.5);
    }
    
    .video-overlay-tr {
        position: absolute;
        top: 14px; right: 18px;
        font-family: 'JetBrains Mono', monospace;
        font-size: 10px;
        color: #38bdf8;
        background: rgba(10, 15, 25, 0.85);
        backdrop-filter: blur(8px);
        border: 1px solid rgba(56, 189, 248, 0.3);
        padding: 4px 10px;
        border-radius: 6px;
    }

    /* ===== STREAMLIT BUTTON OVERHAUL ===== */
    .stButton > button {
        background: linear-gradient(180deg, rgba(30, 41, 59, 0.85) 0%, rgba(15, 23, 42, 0.95) 100%) !important;
        color: #ffffff !important;
        border: 1px solid rgba(255, 255, 255, 0.12) !important;
        border-top: 1px solid rgba(255, 255, 255, 0.25) !important;
        border-radius: 12px !important;
        font-family: 'Outfit', sans-serif !important;
        font-weight: 700 !important;
        font-size: 13px !important;
        letter-spacing: 0.6px !important;
        padding: 12px 18px !important;
        box-shadow: 0 4px 15px rgba(0, 0, 0, 0.4), inset 0 1px 0 rgba(255, 255, 255, 0.1) !important;
        transition: all 0.18s cubic-bezier(0.16, 1, 0.3, 1) !important;
        width: 100%;
    }
    .stButton > button:hover {
        background: linear-gradient(180deg, rgba(51, 65, 85, 0.9) 0%, rgba(30, 41, 59, 1.0) 100%) !important;
        border-color: rgba(56, 189, 248, 0.5) !important;
        transform: translateY(-2px) !important;
        box-shadow: 0 6px 20px rgba(6, 182, 212, 0.25), inset 0 1px 0 rgba(255, 255, 255, 0.2) !important;
    }
    .stButton > button:active {
        transform: translateY(1px) !important;
    }

    /* ===== LOG TERMINAL ===== */
    .log-terminal {
        background: rgba(0, 0, 0, 0.4);
        border: 1px solid rgba(255, 255, 255, 0.08);
        border-radius: 12px;
        padding: 14px;
        max-height: 220px;
        overflow-y: auto;
        font-family: 'JetBrains Mono', monospace;
    }
    .log-line {
        font-size: 11px;
        color: #cbd5e1;
        padding: 4px 0;
        border-bottom: 1px solid rgba(255,255,255,0.03);
        line-height: 1.6;
        display: flex;
        gap: 12px;
    }
    .log-line:last-child { border-bottom: none; }
    .log-timestamp { 
        color: #64748b; 
        min-width: 65px;
    }

    /* ===== NO-CAM PLACEHOLDER ===== */
    .no-cam {
        width: 100%;
        height: 380px;
        background: rgba(0,0,0,0.3);
        border-radius: 14px;
        display: flex;
        flex-direction: column;
        align-items: center;
        justify-content: center;
        border: 1px dashed rgba(255,255,255,0.15);
    }
    .no-cam-icon { 
        font-size: 36px; 
        margin-bottom: 12px; 
        opacity: 0.6;
    }
    .no-cam-text {
        font-family: 'Outfit', sans-serif;
        font-size: 13px;
        font-weight: 600;
        color: #94a3b8;
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
        res = requests.get(f"{BACKEND_URL}/status", timeout=2)
        if res.ok:
            return res.json()
    except Exception:
        pass
    return None

def fetch_telemetry_stats():
    try:
        res = requests.get(f"{BACKEND_URL}/backend/telemetry/stats", timeout=2)
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
        st.error("⚠️ Mode switch failed")
        return False

# ============================================================
# Initial Fetch
# ============================================================
status_data = fetch_status()
backend_online = status_data is not None

if status_data is None:
    status_data = {
        "status": "BACKEND OFFLINE",
        "mode": "unknown",
        "active_phase": "IDLE",
        "cargo_state": "UNKNOWN",
        "latestLog": "Cannot reach backend",
        "obstacle_detected": False,
        "distance_cm": 0,
        "esp32_connected": False,
        "camera_active": False,
        "log_history": [],
        "esp_commands": []
    }

is_manual = status_data.get("mode") == "manual"
now = datetime.now().strftime("%H:%M:%S")

# ============================================================
# TOP BAR
# ============================================================
s = fetch_status() or status_data
backend_online = s["status"] != "BACKEND OFFLINE"

def conn_pill(label, online):
    cls = "conn-online" if online else "conn-offline"
    dot = "conn-dot-on" if online else "conn-dot-off"
    return f'<span class="conn-pill {cls}"><span class="conn-dot {dot}"></span>{label}</span>'

st.markdown(f"""
<div class="topbar">
    <div class="brand-wrap">
        <div class="brand-logo-icon">🤖</div>
        <div>
            <div class="topbar-title"><span>AutoDrop™ MISSION CONTROL</span></div>
            <div class="topbar-subtitle">AUTONOMOUS GROUND FLEET TELEMETRY • CART 01</div>
        </div>
    </div>
    <div class="topbar-right">
        <div class="conn-group">
            {conn_pill("BACKEND", backend_online)}
            {conn_pill("ARDUINO", s.get("esp32_connected", False))}
            {conn_pill("CAMERA", s.get("camera_active", False))}
            {conn_pill("GPS PHONE", s.get("gps_app_connected", False))}
            {conn_pill("APP TRACK", s.get("tracking_clients", 0) > 0)}
        </div>
        <div class="live-clock">{now} LOCAL</div>
    </div>
</div>
""", unsafe_allow_html=True)

# ============================================================
# INTERACTIVE GSAP COCKPIT TELEMETRY & PHASE RIBBON
# ============================================================
hud_html = f"""
<!DOCTYPE html>
<html>
<head>
<style>
    * {{ box-sizing: border-box; margin: 0; padding: 0; user-select: none; }}
    body {{ background: transparent; font-family: 'Outfit', -apple-system, sans-serif; color: #f8fafc; padding: 0 4px; }}
    
    .cockpit-container {{
        background: linear-gradient(135deg, rgba(20, 27, 45, 0.75) 0%, rgba(10, 14, 24, 0.8) 100%);
        backdrop-filter: blur(24px);
        -webkit-backdrop-filter: blur(24px);
        border: 1px solid rgba(255, 255, 255, 0.1);
        border-top: 1px solid rgba(255, 255, 255, 0.2);
        border-radius: 18px;
        padding: 16px 20px;
        margin-bottom: 20px;
        box-shadow: 0 16px 36px -10px rgba(0, 0, 0, 0.6), inset 0 1px 0 rgba(255, 255, 255, 0.1);
        display: flex;
        flex-direction: column;
        gap: 14px;
    }}

    /* Mission Phase Ribbon */
    .ribbon-wrap {{
        display: flex;
        align-items: center;
        justify-content: space-between;
        background: rgba(0, 0, 0, 0.35);
        border: 1px solid rgba(255, 255, 255, 0.06);
        border-radius: 12px;
        padding: 12px 18px;
        position: relative;
    }}
    
    .phase-node {{
        display: flex;
        align-items: center;
        gap: 10px;
        opacity: 0.45;
        transition: all 0.4s ease;
    }}
    .phase-node.active {{
        opacity: 1;
        transform: scale(1.05);
    }}
    
    .phase-badge {{
        width: 32px;
        height: 32px;
        border-radius: 10px;
        background: rgba(255, 255, 255, 0.05);
        border: 1px solid rgba(255, 255, 255, 0.12);
        display: flex;
        align-items: center;
        justify-content: center;
        font-size: 15px;
        transition: all 0.3s;
    }}
    .phase-node.active .phase-badge {{
        background: #06b6d4;
        border-color: #38bdf8;
        box-shadow: 0 0 16px rgba(6, 182, 212, 0.6);
        color: #000;
    }}

    .phase-name {{
        font-size: 11px;
        font-weight: 700;
        letter-spacing: 0.8px;
        text-transform: uppercase;
        color: #94a3b8;
    }}
    .phase-node.active .phase-name {{
        color: #ffffff;
    }}

    .phase-line {{
        flex: 1;
        height: 2px;
        background: rgba(255, 255, 255, 0.08);
        margin: 0 12px;
        position: relative;
        overflow: hidden;
    }}
    .phase-line-fill {{
        position: absolute;
        top: 0; left: 0; bottom: 0; width: 0%;
        background: linear-gradient(90deg, #06b6d4, #3b82f6);
        box-shadow: 0 0 8px #06b6d4;
        transition: width 0.5s ease;
    }}

    /* Cockpit Metrics Grid */
    .cockpit-grid {{
        display: grid;
        grid-template-columns: 1.2fr 1.5fr 1fr 1.2fr;
        gap: 12px;
    }}

    .cockpit-card {{
        background: rgba(0, 0, 0, 0.3);
        border: 1px solid rgba(255, 255, 255, 0.06);
        border-radius: 12px;
        padding: 12px 14px;
        display: flex;
        flex-direction: column;
        justify-content: space-between;
    }}

    .card-hdr {{
        display: flex;
        justify-content: space-between;
        align-items: center;
        font-size: 10px;
        font-weight: 700;
        letter-spacing: 1.2px;
        color: #94a3b8;
        text-transform: uppercase;
    }}

    .big-num {{
        font-family: 'JetBrains Mono', monospace;
        font-size: 26px;
        font-weight: 700;
        color: #ffffff;
        margin: 4px 0;
    }}
    .num-unit {{
        font-size: 12px;
        color: #94a3b8;
        font-weight: 600;
        margin-left: 2px;
    }}

    /* Radar Sonar Arc */
    .radar-arc-wrap {{
        display: flex;
        align-items: center;
        gap: 12px;
        margin-top: 4px;
    }}
    .radar-svg {{
        width: 100px;
        height: 48px;
    }}
    .radar-dist-tag {{
        font-family: 'JetBrains Mono', monospace;
        font-size: 16px;
        font-weight: 700;
        color: #10b981;
    }}

    /* Latch Dial Pill */
    .latch-pill {{
        display: inline-flex;
        align-items: center;
        gap: 6px;
        padding: 6px 12px;
        border-radius: 8px;
        font-family: 'JetBrains Mono', monospace;
        font-size: 12px;
        font-weight: 700;
        margin-top: 6px;
        background: rgba(239, 68, 68, 0.15);
        color: #f87171;
        border: 1px solid rgba(239, 68, 68, 0.3);
    }}
    .latch-pill.unlocked {{
        background: rgba(16, 185, 129, 0.15);
        color: #34d399;
        border-color: rgba(16, 185, 129, 0.3);
    }}
</style>
<script src="https://cdnjs.cloudflare.com/ajax/libs/gsap/3.12.5/gsap.min.js"></script>
</head>
<body>
<div class="cockpit-container">
    <!-- 1. Live Mission Ribbon -->
    <div class="ribbon-wrap">
        <div class="phase-node active" id="node-base">
            <div class="phase-badge">⚡</div>
            <div class="phase-name">1. Base Dock</div>
        </div>
        <div class="phase-line"><div class="phase-line-fill" id="pfill-1"></div></div>

        <div class="phase-node" id="node-pickup">
            <div class="phase-badge">📦</div>
            <div class="phase-name">2. Sender (Pickup)</div>
        </div>
        <div class="phase-line"><div class="phase-line-fill" id="pfill-2"></div></div>

        <div class="phase-node" id="node-transit">
            <div class="phase-badge">🚀</div>
            <div class="phase-name">3. In Transit</div>
        </div>
        <div class="phase-line"><div class="phase-line-fill" id="pfill-3"></div></div>

        <div class="phase-node" id="node-receiver">
            <div class="phase-badge">🎯</div>
            <div class="phase-name">4. Receiver (Unlock)</div>
        </div>
        <div class="phase-line"><div class="phase-line-fill" id="pfill-4"></div></div>

        <div class="phase-node" id="node-return">
            <div class="phase-badge">🏠</div>
            <div class="phase-name">5. Return To Base</div>
        </div>
    </div>

    <!-- 2. Live Telemetry Strip -->
    <div class="cockpit-grid">
        <!-- Velocity -->
        <div class="cockpit-card">
            <div class="card-hdr"><span>GPS VELOCITY</span><span>🛰️</span></div>
            <div class="big-num" id="val-speed">0.0<span class="num-unit">km/h</span></div>
            <div style="font-size:10px; color:#64748b;" id="val-eta">ETA: Calculating...</div>
        </div>

        <!-- Radar Sonar Arc -->
        <div class="cockpit-card">
            <div class="card-hdr"><span>ULTRASONIC RADAR</span><span>🎯</span></div>
            <div class="radar-arc-wrap">
                <svg viewBox="0 0 100 50" class="radar-svg">
                    <path d="M 10 46 A 40 40 0 0 1 90 46" fill="none" stroke="rgba(255,255,255,0.12)" stroke-width="3" stroke-dasharray="3,3" />
                    <path d="M 25 46 A 25 25 0 0 1 75 46" fill="none" stroke="rgba(255,255,255,0.08)" stroke-width="2" />
                    <line id="radar-beam" x1="50" y1="46" x2="50" y2="8" stroke="#06b6d4" stroke-width="2.5" stroke-linecap="round" />
                </svg>
                <div>
                    <div class="radar-dist-tag" id="val-dist">-- cm</div>
                    <div style="font-size:9px; color:#94a3b8;" id="val-radar-status">PATH CLEAR</div>
                </div>
            </div>
        </div>

        <!-- Power Core -->
        <div class="cockpit-card">
            <div class="card-hdr"><span>ENERGY CORE</span><span>🔋</span></div>
            <div class="big-num" id="val-bat">--<span class="num-unit">%</span></div>
            <div style="font-size:10px; color:#10b981;" id="val-amps">0.0A Draw</div>
        </div>

        <!-- Latch Status -->
        <div class="cockpit-card">
            <div class="card-hdr"><span>CARGO COMPARTMENT</span><span>🔒</span></div>
            <div>
                <span class="latch-pill" id="val-latch">🔒 LOCKED (0°)</span>
            </div>
            <div style="font-size:10px; color:#64748b; margin-top:4px;">Dual PIN & QR Servo Latch</div>
        </div>
    </div>
</div>

<script>
    // Continuous GSAP Radar Sonar Beam Sweep
    gsap.to('#radar-beam', {{
        rotation: 40,
        transformOrigin: "50px 46px",
        duration: 1.4,
        repeat: -1,
        yoyo: true,
        ease: "sine.inOut"
    }});

    // Live WebSocket connection to Cart
    const wsUrl = "{BACKEND_URL}".replace(/^http/, 'ws') + "/ws/track";
    let ws;

    function connectWS() {{
        ws = new WebSocket(wsUrl);
        ws.onmessage = (event) => {{
            try {{
                const data = JSON.parse(event.data);
                if (data.type !== 'location_update') return;

                // 1. Update Velocity with GSAP
                if (data.speed !== undefined) {{
                    const spd = Number(data.speed).toFixed(1);
                    document.getElementById('val-speed').innerHTML = spd + '<span class="num-unit">km/h</span>';
                }}
                
                // 2. Update ETA
                if (data.eta_seconds !== undefined) {{
                    const etaEl = document.getElementById('val-eta');
                    if (data.eta_seconds > 0) {{
                        const m = Math.ceil(data.eta_seconds / 60);
                        etaEl.innerText = "ETA: ~" + m + " min (" + data.eta_seconds + "s)";
                    }} else {{
                        etaEl.innerText = "ETA: Destination Reached";
                    }}
                }}

                // 3. Update Cargo Latch
                const latchEl = document.getElementById('val-latch');
                if (data.cargo_state === 'UNLOCKED') {{
                    latchEl.className = 'latch-pill unlocked';
                    latchEl.innerText = '🔓 UNLOCKED (90°)';
                }} else {{
                    latchEl.className = 'latch-pill';
                    latchEl.innerText = '🔒 LOCKED (0°)';
                }}

                // 4. Update Mission Stage Ribbon
                const phase = String(data.phase || '').toUpperCase();
                const nodes = ['node-base', 'node-pickup', 'node-transit', 'node-receiver', 'node-return'];
                nodes.forEach(n => document.getElementById(n).classList.remove('active'));

                if (phase === 'IDLE') {{
                    document.getElementById('node-base').classList.add('active');
                }} else if (phase === 'HEADING_TO_SENDER' || phase === 'AWAITING_LOAD') {{
                    document.getElementById('node-pickup').classList.add('active');
                    document.getElementById('pfill-1').style.width = '100%';
                }} else if (phase === 'DELIVERING') {{
                    document.getElementById('node-transit').classList.add('active');
                    document.getElementById('pfill-1').style.width = '100%';
                    document.getElementById('pfill-2').style.width = '100%';
                }} else if (phase === 'AWAITING_RETRIEVAL') {{
                    document.getElementById('node-receiver').classList.add('active');
                    document.getElementById('pfill-1').style.width = '100%';
                    document.getElementById('pfill-2').style.width = '100%';
                    document.getElementById('pfill-3').style.width = '100%';
                }} else if (phase === 'RETURNING_TO_BASE') {{
                    document.getElementById('node-return').classList.add('active');
                    document.getElementById('pfill-1').style.width = '100%';
                    document.getElementById('pfill-2').style.width = '100%';
                    document.getElementById('pfill-3').style.width = '100%';
                    document.getElementById('pfill-4').style.width = '100%';
                }}
            }} catch(e) {{}}
        }};
        ws.onclose = () => setTimeout(connectWS, 2000);
    }}
    connectWS();
</script>
</body>
</html>
"""

components.html(hud_html, height=185)

# ============================================================
# MAIN TWO-COLUMN LAYOUT
# ============================================================
col_left, col_right = st.columns([5, 3], gap="large")

# ==================== LEFT COLUMN ====================
with col_left:
    # --- LIVE VISION FEED ---
    st.markdown('<div class="panel">', unsafe_allow_html=True)
    st.markdown('<div class="panel-label">LIVE VISION STREAM — YOLOv8 AI DETECTION</div>', unsafe_allow_html=True)

    if backend_online and status_data.get("camera_active"):
        st.markdown(f"""
        <div class="video-wrap">
            <div class="video-reticle-tl"></div>
            <div class="video-reticle-tr"></div>
            <div class="video-reticle-bl"></div>
            <div class="video-reticle-br"></div>
            <img id="yolo-feed" src="{BACKEND_URL}/video_feed" alt="YOLO Feed"
                 onerror="setTimeout(function(){{ document.getElementById('yolo-feed').src='{BACKEND_URL}/video_feed?t='+Date.now(); }}, 2000);" />
            <div class="video-overlay-tl">● REC LIVE</div>
            <div class="video-overlay-tr">YOLOv8n • 640×480 • 30 FPS</div>
        </div>
        """, unsafe_allow_html=True)
    else:
        st.markdown("""
        <div class="no-cam">
            <div class="no-cam-icon">📡</div>
            <div class="no-cam-text">AWAITING VIDEO CAMERA SIGNAL</div>
            <div style="font-size:11px; color:#64748b; margin-top:6px;">Webcam index 0 standing by</div>
        </div>
        """, unsafe_allow_html=True)
    st.markdown('</div>', unsafe_allow_html=True)

    # --- SYSTEM LOG TERMINAL ---
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
            st.markdown('<div class="log-terminal"><div class="log-line" style="color:#64748b; text-align:center;">Waiting for system logs...</div></div>', unsafe_allow_html=True)
        st.markdown('</div>', unsafe_allow_html=True)
        
        # --- BOT HARDWARE COMMAND TERMINAL ---
        st.markdown('<div class="panel" style="margin-top: 14px;">', unsafe_allow_html=True)
        st.markdown('<div class="panel-label">ARDUINO SERIAL COMMAND FEED</div>', unsafe_allow_html=True)
    
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
            st.markdown(f'<div class="log-terminal" style="max-height:140px;">{esp_html}</div>', unsafe_allow_html=True)
        else:
            st.markdown('<div class="log-terminal" style="max-height:140px;"><div class="log-line" style="color:#64748b; text-align:center;">No hardware telemetry...</div></div>', unsafe_allow_html=True)
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
        st.markdown('<div class="panel-label">BLACKBOX TELEMETRY & ROUTE CACHE</div>', unsafe_allow_html=True)
        
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
            for r in recent_logs[:6]:
                ts = r.get("timestamp", "").split()[-1] if r.get("timestamp") else "--:--:--"
                cmd = r.get("motor_cmd", "stop")
                phase = (r.get("phase") or "IDLE")[:8]
                dist = r.get("ultrasonic_cm", 999)
                bias = r.get("steer_bias", 0.0)
                cmd_color = "#38bdf8" if "steer" in cmd or "curve" in cmd else "#34d399" if "forward" in cmd or "slow" in cmd else "#f43f5e" if "stop" in cmd else "#fbbf24"
                dist_str = f"{dist}cm" if dist < 900 else "--"
                bias_str = f"b:{bias:+.2f}" if abs(bias) > 0.01 else "--"
                
                rows_html += f"""
                <div class="log-line" style="display:flex; justify-content:space-between; font-size:10px; padding:3px 0; border-bottom:1px solid rgba(255,255,255,0.03);">
                    <span style="color:#64748b; width:65px;">{ts}</span>
                    <span style="color:#94a3b8; font-weight:600; width:75px;">{phase}</span>
                    <span style="color:{cmd_color}; font-weight:700; flex:1;">{cmd}</span>
                    <span style="color:#e2e8f0; width:50px; text-align:right;">{dist_str}</span>
                    <span style="color:#a78bfa; width:55px; text-align:right;">{bias_str}</span>
                </div>
                """
            st.markdown(f'<div class="log-terminal" style="max-height:140px; margin-top:8px;">{rows_html}</div>', unsafe_allow_html=True)
        st.markdown('</div>', unsafe_allow_html=True)
        
    render_mission_telemetry_cache()


# ==================== RIGHT COLUMN ====================
with col_right:
    # --- STATUS & PRIMARY TELEMETRY ---
    @st.fragment(run_every="1s")
    def render_status_telemetry():
        s = fetch_status() or status_data
        is_manual = s.get("mode") == "manual"
        phase = s.get("active_phase", "IDLE")
    
        # Status Card
        st.markdown('<div class="panel">', unsafe_allow_html=True)
        st.markdown('<div class="panel-label">LIVE AUTONOMOUS STATE</div>', unsafe_allow_html=True)
        
        st.markdown(f'<div class="status-badge">MISSION PHASE: {phase}</div>', unsafe_allow_html=True)
        st.markdown(f'<div class="status-readout">{s.get("status", "IDLE")}</div>', unsafe_allow_html=True)
        st.markdown(f'<div class="status-detail">{s.get("latestLog", "")}</div>', unsafe_allow_html=True)
    
        # Metrics Bento
        m1, m2, m3 = st.columns(3)
        with m1:
            is_blocked = "IN PATH" in s["status"] or "STOP" in s["status"] or "TOO CLOSE" in s["status"]
            is_seen = s["status"] != "🔍 SEARCHING" and "PATH CLEAR" not in s["status"]
            obs_color, obs_text, obs_icon = ("#ef4444", "BLOCKED", "🚨") if is_blocked else ("#f59e0b", "DETECTED", "👁️") if is_seen else ("#10b981", "CLEAR", "✅")
            st.markdown(f"""
            <div class="metric-tile">
                <div class="metric-tile-value" style="color:{obs_color}">{obs_icon}</div>
                <div class="metric-tile-label">{obs_text}</div>
            </div>
            """, unsafe_allow_html=True)
        with m2:
            mode_icon = "🎮" if is_manual else "🤖"
            mode_label = "MANUAL" if is_manual else "AUTONOMOUS"
            mode_color = "#f87171" if is_manual else "#38bdf8"
            st.markdown(f"""
            <div class="metric-tile">
                <div class="metric-tile-value" style="color:{mode_color}">{mode_icon}</div>
                <div class="metric-tile-label">{mode_label}</div>
            </div>
            """, unsafe_allow_html=True)
        with m3:
            cargo_state = s.get("cargo_state", "UNKNOWN")
            c_color = "#ef4444" if cargo_state == "LOCKED" else "#34d399"
            c_icon = "🔒" if cargo_state == "LOCKED" else "🔓"
            st.markdown(f"""
            <div class="metric-tile">
                <div class="metric-tile-value" style="color:{c_color}">{c_icon}</div>
                <div class="metric-tile-label">{cargo_state}</div>
            </div>
            """, unsafe_allow_html=True)
            
        st.markdown('</div>', unsafe_allow_html=True)
    
    render_status_telemetry()

    # --- FLEET MODE CONTROLS ---
    st.markdown('<div class="panel">', unsafe_allow_html=True)
    st.markdown('<div class="panel-label">FLEET COMMAND & DISPATCH</div>', unsafe_allow_html=True)
    
    if st.session_state.get("open_manual_drive"):
        components.html(f"<script>window.open('{BACKEND_URL}/drive', '_blank');</script>", height=0)
        st.session_state["open_manual_drive"] = False

    mode_status = fetch_status() or status_data
    is_manual_now = mode_status.get("mode") == "manual"

    col_btn1, col_btn2 = st.columns(2)
    with col_btn1:
        if is_manual_now:
            if st.button("🤖  AUTONOMOUS MODE", use_container_width=True, key="mode_btn"):
                toggle_mode("autonomous")
                st.rerun()
        else:
            if st.button("🚨  MANUAL OVERRIDE", use_container_width=True, key="mode_btn"):
                toggle_mode("manual")
                st.session_state["open_manual_drive"] = True
                st.rerun()

    with col_btn2:
        if st.button("🏠  RETURN TO BASE", use_container_width=True, key="rtb_btn"):
            try:
                res = requests.post(f"{BACKEND_URL}/backend/return_to_base", timeout=3)
                if res.status_code == 200:
                    st.toast("🚀 Returning to Base Charging Station!", icon="🏠")
            except Exception as e:
                st.error(f"Error: {e}")
            st.rerun()
            
    st.markdown('<div style="margin-top: 12px; border-top: 1px solid rgba(255,255,255,0.08); padding-top: 10px;"></div>', unsafe_allow_html=True)
    routing_choice = st.selectbox("Routing Engine", ["Google Maps API", "Internal Graph (JUET)"], index=0, key="routing_engine")
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
    
    cargo_status = s.get("cargo_state", "LOCKED")
    is_unlocked = cargo_status == "UNLOCKED"
    
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
                100% {{ top: 128px; opacity: 0; }}
            }}
            .laser-line {{
                position: absolute;
                left: 0; right: 0; height: 2px;
                background: linear-gradient(90deg, transparent, #38bdf8, #06b6d4, transparent);
                box-shadow: 0 0 12px #38bdf8, 0 0 20px #06b6d4;
                animation: laserSweep 2s ease-in-out infinite;
            }}
        </style>
        <div style="text-align: center; background: rgba(0,0,0,0.35); border: 1px solid rgba(255,255,255,0.08); border-radius: 14px; padding: 12px; position: relative;">
            <div style="font-family: 'JetBrains Mono', monospace; font-size: 10px; color: #38bdf8; margin-bottom: 8px; font-weight: 700; letter-spacing: 0.8px;">📱 SCAN WITH PHONE CAMERA</div>
            <div style="position: relative; display: inline-block; border-radius: 12px; overflow: hidden; border: 2px solid #06b6d4; box-shadow: 0 0 20px rgba(6, 182, 212, 0.35);">
                <div class="laser-line"></div>
                <img src="{qr_img_src}" alt="Scan to Unlock" style="display: block; width: 130px; height: 130px;" />
            </div>
            <div style="font-size: 9px; color: #94a3b8; margin-top: 8px;">Opens hardware latch to 90°</div>
        </div>
        """, unsafe_allow_html=True)
        
    with col_latch_act:
        state_badge = '<span style="color:#34d399; font-weight:bold; font-size:15px;">🔓 UNLOCKED (90°)</span>' if is_unlocked else '<span style="color:#f87171; font-weight:bold; font-size:15px;">🔒 LOCKED (0°)</span>'
        st.markdown(f"""
        <div style="padding: 4px 0 12px 0;">
            <div style="font-size: 10px; color: #94a3b8; font-family: 'JetBrains Mono';">HARDWARE SERVO ANGLE:</div>
            <div style="margin: 4px 0 12px 0;">{state_badge}</div>
        </div>
        """, unsafe_allow_html=True)
        
        if st.button("🔓 UNLOCK LATCH (90°)", key="btn_unlock_servo", use_container_width=True):
            try:
                requests.post(f"{BACKEND_URL}/backend/verify_qr", json={"action": "unlock", "cart_id": "CART_01"}, timeout=3)
                st.toast("🔓 Latch servo rotated to 90° (Unlocked)!", icon="🔓")
            except Exception as e:
                st.error(f"Error: {e}")
            st.rerun()
            
        if st.button("🔒 LOCK LATCH (0°)", key="btn_lock_servo", use_container_width=True):
            try:
                requests.post(f"{BACKEND_URL}/backend/pack_order", timeout=3)
                st.toast("🔒 Latch servo secured to 0° (Locked)!", icon="🔒")
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
            #map-wrapper {{ position: relative; width: 100%; height: 380px; border-radius: 14px; overflow: hidden; border: 1px solid rgba(255,255,255,0.1); }}
            #map {{ height: 100%; width: 100%; }}
            .map-ctrl-bar {{
                position: absolute;
                top: 12px;
                right: 12px;
                z-index: 10;
                display: flex;
                gap: 6px;
                background: rgba(10, 14, 24, 0.88);
                backdrop-filter: blur(12px);
                border: 1px solid rgba(255, 255, 255, 0.12);
                border-radius: 8px;
                padding: 4px;
            }}
            .map-type-btn {{
                background: transparent;
                border: none;
                color: #94a3b8;
                font-family: 'Outfit', sans-serif;
                font-size: 11px;
                font-weight: 700;
                padding: 5px 10px;
                border-radius: 6px;
                cursor: pointer;
                transition: all 0.15s;
            }}
            .map-type-btn.active {{
                background: #06b6d4;
                color: #000;
            }}
            .phase-hud {{
                position: absolute;
                bottom: 12px;
                left: 12px;
                z-index: 10;
                background: rgba(10, 14, 24, 0.88);
                backdrop-filter: blur(14px);
                border: 1px solid rgba(255, 255, 255, 0.15);
                border-radius: 8px;
                padding: 6px 14px;
                font-family: 'JetBrains Mono', monospace;
                font-size: 11px;
                color: #38bdf8;
                font-weight: 700;
                display: flex;
                align-items: center;
                gap: 8px;
            }}
            .hud-dot {{
                width: 7px;
                height: 7px;
                border-radius: 50%;
                background: #10b981;
                box-shadow: 0 0 8px #10b981;
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
                        scale: 7,
                        fillColor: '#10b981',
                        fillOpacity: 1,
                        strokeColor: '#070a10',
                        strokeWeight: 2,
                        rotation: 0,
                    }},
                    zIndex: 100,
                    title: "AutoDrop Cart"
                }});

                // Charging Station (Base Dock) Cyan Marker
                chargingMarker = new google.maps.Marker({{
                    map: map,
                    icon: {{
                        path: google.maps.SymbolPath.CIRCLE,
                        scale: 9,
                        fillColor: '#06b6d4',
                        fillOpacity: 1,
                        strokeColor: '#083344',
                        strokeWeight: 3,
                    }},
                    title: "Base Dock Charging Station"
                }});

                // Source (Pickup) White Circle Marker
                sourceMarker = new google.maps.Marker({{
                    map: map,
                    icon: {{
                        path: google.maps.SymbolPath.CIRCLE,
                        scale: 8,
                        fillColor: '#ffffff',
                        fillOpacity: 1,
                        strokeColor: '#1e293b',
                        strokeWeight: 3,
                    }},
                    title: "Pickup Location"
                }});

                // Destination (Dropoff) Amber Circle Marker
                destMarker = new google.maps.Marker({{
                    map: map,
                    icon: {{
                        path: google.maps.SymbolPath.CIRCLE,
                        scale: 8,
                        fillColor: '#f59e0b',
                        fillOpacity: 1,
                        strokeColor: '#1e293b',
                        strokeWeight: 3,
                    }},
                    title: "Dropoff Location"
                }});
                
                // Dense Google Maps Route Polyline
                routePoly = new google.maps.Polyline({{
                    geodesic: true,
                    strokeColor: '#38bdf8',
                    strokeOpacity: 0.9,
                    strokeWeight: 5,
                    map: map,
                }});
                
                connectWebSocket();
            }}
            
            function connectWebSocket() {{
                const wsUrl = "{BACKEND_URL}".replace(/^http/, 'ws') + "/ws/track";
                const ws = new WebSocket(wsUrl);
                
                ws.onmessage = (event) => {{
                    try {{
                        const data = JSON.parse(event.data);
                        if (data.type !== 'location_update') return;
                        
                        const bounds = new google.maps.LatLngBounds();
                        let hasBounds = false;
                        
                        // Update Phase HUD with GSAP pulse
                        if (data.phase) {{
                            const hudEl = document.getElementById('hud-text');
                            if (hudEl && hudEl.innerText !== "PHASE: " + data.phase) {{
                                hudEl.innerText = "PHASE: " + data.phase;
                                if (window.gsap) {{
                                    gsap.fromTo('#phase-hud', 
                                        {{ scale: 0.92, borderColor: '#38bdf8' }}, 
                                        {{ scale: 1.0, borderColor: 'rgba(255, 255, 255, 0.15)', duration: 0.45, ease: "back.out(2)" }}
                                    );
                                }}
                            }}
                        }}
                        
                        if (data.cart) {{
                            const curr = botMarker.getPosition();
                            if (curr) {{
                                const dLng = data.cart.lng - curr.lng();
                                const dLat = data.cart.lat - curr.lat();
                                if (dLng !== 0 || dLat !== 0) {{
                                    const heading = (Math.atan2(dLng, dLat) * 180) / Math.PI;
                                    const icon = botMarker.getIcon();
                                    icon.rotation = heading;
                                    botMarker.setIcon(icon);
                                }}
                            }}
                            botMarker.setPosition(data.cart);
                            bounds.extend(data.cart);
                            hasBounds = true;
                        }}
                        
                        if (data.charging_station && data.charging_station.lat) {{
                            chargingMarker.setPosition(data.charging_station);
                            chargingMarker.setMap(map);
                            bounds.extend(data.charging_station);
                            hasBounds = true;
                        }} else {{
                            chargingMarker.setMap(null);
                        }}
                        
                        if (data.source && data.source.lat) {{
                            sourceMarker.setPosition(data.source);
                            sourceMarker.setMap(map);
                            bounds.extend(data.source);
                            hasBounds = true;
                        }} else {{
                            sourceMarker.setMap(null);
                        }}
                        
                        if (data.destination && data.destination.lat) {{
                            destMarker.setPosition(data.destination);
                            destMarker.setMap(map);
                            bounds.extend(data.destination);
                            hasBounds = true;
                        }} else {{
                            destMarker.setMap(null);
                        }}
                        
                        if (data.route_points && data.route_points.length > 0) {{
                            routePoly.setPath(data.route_points);
                        }} else {{
                            routePoly.setPath([]);
                        }}
                        
                        if (hasBounds && !window.hasFittedBounds) {{
                            map.fitBounds(bounds, 45);
                            if(map.getZoom() > 18) map.setZoom(18);
                            window.hasFittedBounds = true;
                        }}
                    }} catch(e) {{ console.error(e); }}
                }};
                
                ws.onclose = () => setTimeout(connectWebSocket, 2000);
            }}
            
            initMap();
        </script>
    </body>
    </html>
    """
    
    components.html(map_html, height=400)
    st.markdown('</div>', unsafe_allow_html=True)
