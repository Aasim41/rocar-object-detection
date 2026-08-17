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
    page_title="🤖 MISSION CONTROL — Autonomous Delivery",
    page_icon="🤖",
    layout="wide",
    initial_sidebar_state="collapsed"
)

# ============================================================
# Premium Dark Mission Control Theme
# ============================================================
st.markdown("""
<style>
    @import url('https://fonts.googleapis.com/css2?family=JetBrains+Mono:wght@300;400;500;600;700;800&family=Inter:wght@400;500;600;700;800;900&family=Orbitron:wght@400;500;600;700;800;900&display=swap');
    
    /* ===== CORE ===== */
    .stApp {
        background: #0f172a;
        color: #f8fafc;
    }

    /* Kill Streamlit chrome */
    #MainMenu, footer, .stDeployButton, header { display: none !important; }

    /* Scrollbar */
    ::-webkit-scrollbar { width: 5px; }
    ::-webkit-scrollbar-track { background: #0a0f1a; }
    ::-webkit-scrollbar-thumb { background: #1e3a5f; border-radius: 3px; }

    /* ===== TOP BAR ===== */
    .topbar {
        background: rgba(15, 23, 42, 0.6);
        border-bottom: 1px solid rgba(255, 255, 255, 0.05);
        padding: 16px 32px;
        display: flex;
        justify-content: space-between;
        align-items: center;
        margin: -1rem -1rem 20px -1rem;
        position: sticky;
        top: 0;
        z-index: 999;
        backdrop-filter: blur(10px);
    }
    .topbar::after {
        content: '';
        position: absolute;
        bottom: -1px;
        left: 0; right: 0;
        height: 1px;
        background: linear-gradient(90deg, transparent, #38bdf8, #818cf8, #38bdf8, transparent);
        opacity: 0.6;
    }

    .topbar-title {
        font-family: 'Orbitron', sans-serif;
        font-size: 24px;
        font-weight: 800;
        letter-spacing: 2px;
        background: linear-gradient(135deg, #0ea5e9 0%, #10b981 100%);
        -webkit-background-clip: text;
        -webkit-text-fill-color: transparent;
    }
    .topbar-subtitle {
        font-family: 'JetBrains Mono', monospace;
        font-size: 10px;
        color: #475569;
        letter-spacing: 2px;
        margin-top: 2px;
    }

    .topbar-right {
        display: flex;
        align-items: center;
        gap: 16px;
    }

    .live-clock {
        font-family: 'Orbitron', sans-serif;
        font-size: 14px;
        color: #38bdf8;
        letter-spacing: 2px;
        padding: 4px 12px;
        border: 1px solid rgba(56,189,248,0.2);
        border-radius: 6px;
        background: rgba(56,189,248,0.05);
    }

    /* ===== CONNECTION INDICATORS ===== */
    .conn-group {
        display: flex;
        gap: 8px;
    }
    .conn-pill {
        display: flex;
        align-items: center;
        gap: 5px;
        padding: 4px 12px;
        border-radius: 20px;
        font-family: 'JetBrains Mono', monospace;
        font-size: 10px;
        font-weight: 600;
        letter-spacing: 1px;
    }
    .conn-online {
        background: rgba(34,197,94,0.1);
        border: 1px solid rgba(34,197,94,0.3);
        color: #4ade80;
    }
    .conn-offline {
        background: rgba(239,68,68,0.1);
        border: 1px solid rgba(239,68,68,0.3);
        color: #f87171;
    }
    .conn-dot {
        width: 6px; height: 6px;
        border-radius: 50%;
        display: inline-block;
    }
    .conn-dot-on { background: #4ade80; box-shadow: 0 0 6px #4ade80; }
    .conn-dot-off { background: #f87171; box-shadow: 0 0 6px #f87171; }

    @keyframes pulse-dot {
        0%, 100% { opacity: 1; }
        50% { opacity: 0.4; }
    }
    .conn-online .conn-dot { animation: pulse-dot 2s ease-in-out infinite; }

    /* ===== PANELS (BENTO GRID) ===== */
    .panel {
        background: rgba(255, 255, 255, 0.03);
        border: 1px solid rgba(255, 255, 255, 0.08);
        border-radius: 20px;
        padding: 24px;
        margin-bottom: 16px;
        position: relative;
        overflow: hidden;
        backdrop-filter: blur(12px);
        box-shadow: 0 10px 30px rgba(0, 0, 0, 0.2);
        transition: transform 0.3s ease, border-color 0.3s ease;
    }
    .panel:hover {
        border-color: rgba(14, 165, 233, 0.3);
    }
    .panel::before {
        content: '';
        position: absolute;
        top: 0; left: 0; right: 0;
        height: 1px;
        background: linear-gradient(90deg, transparent, rgba(56,189,248,0.3), transparent);
    }

    .panel-label {
        font-family: 'Inter', sans-serif;
        font-size: 11px;
        font-weight: 700;
        color: #94a3b8;
        letter-spacing: 2px;
        text-transform: uppercase;
        margin-bottom: 16px;
        display: flex;
        align-items: center;
        gap: 8px;
    }
    .panel-label::before {
        content: '';
        width: 4px; height: 12px;
        background: linear-gradient(180deg, #0ea5e9, #10b981);
        border-radius: 2px;
    }

    /* ===== MODE BANNER ===== */
    .mode-banner {
        font-family: 'Orbitron', sans-serif;
        font-size: 14px;
        font-weight: 700;
        letter-spacing: 3px;
        padding: 10px 16px;
        border-radius: 8px;
        text-align: center;
        margin-bottom: 14px;
    }
    .mode-auto {
        background: linear-gradient(135deg, rgba(99,102,241,0.15), rgba(56,189,248,0.1));
        border: 1px solid rgba(99,102,241,0.35);
        color: #a5b4fc;
    }
    .mode-manual {
        background: linear-gradient(135deg, rgba(239,68,68,0.15), rgba(249,115,22,0.1));
        border: 1px solid rgba(239,68,68,0.35);
        color: #fca5a5;
        animation: pulse-border 1.5s ease-in-out infinite;
    }
    @keyframes pulse-border {
        0%, 100% { border-color: rgba(239,68,68,0.35); }
        50% { border-color: rgba(239,68,68,0.7); }
    }

    /* ===== STATUS READOUT ===== */
    .status-readout {
        font-family: 'JetBrains Mono', monospace;
        font-size: 18px;
        font-weight: 700;
        color: #38bdf8;
        margin-bottom: 4px;
    }
    .status-detail {
        font-family: 'JetBrains Mono', monospace;
        font-size: 11px;
        color: #64748b;
    }

    /* ===== METRIC TILES ===== */
    .metric-tile {
        background: rgba(10,15,30,0.7);
        border: 1px solid rgba(56,189,248,0.08);
        border-radius: 8px;
        padding: 12px;
        text-align: center;
    }
    .metric-tile-value {
        font-family: 'Orbitron', sans-serif;
        font-size: 26px;
        font-weight: 700;
    }
    .metric-tile-unit {
        font-family: 'JetBrains Mono', monospace;
        font-size: 11px;
        font-weight: 400;
        opacity: 0.5;
    }
    .metric-tile-label {
        font-family: 'JetBrains Mono', monospace;
        font-size: 9px;
        color: #475569;
        letter-spacing: 2px;
        text-transform: uppercase;
        margin-top: 6px;
    }

    /* ===== PROXIMITY BAR ===== */
    .prox-bar-container {
        background: rgba(10,15,30,0.6);
        border: 1px solid rgba(56,189,248,0.1);
        border-radius: 8px;
        padding: 12px 14px;
        margin-bottom: 14px;
    }
    .prox-bar-track {
        width: 100%;
        height: 10px;
        background: rgba(30,58,95,0.3);
        border-radius: 5px;
        overflow: hidden;
        position: relative;
    }
    .prox-bar-fill {
        height: 100%;
        border-radius: 5px;
        transition: width 0.5s ease;
    }
    .prox-bar-labels {
        display: flex;
        justify-content: space-between;
        margin-top: 4px;
        font-family: 'JetBrains Mono', monospace;
        font-size: 9px;
        color: #475569;
    }

    /* ===== VIDEO CONTAINER ===== */
    .video-wrap {
        border-radius: 8px;
        overflow: hidden;
        border: 1px solid rgba(56,189,248,0.15);
        position: relative;
        background: #020617;
    }
    .video-wrap img {
        width: 100%;
        display: block;
    }
    .video-overlay-tl {
        position: absolute;
        top: 8px; left: 10px;
        font-family: 'JetBrains Mono', monospace;
        font-size: 10px;
        color: #ef4444;
        background: rgba(0,0,0,0.6);
        padding: 2px 8px;
        border-radius: 4px;
        letter-spacing: 1px;
    }
    .video-overlay-tr {
        position: absolute;
        top: 8px; right: 10px;
        font-family: 'Orbitron', sans-serif;
        font-size: 9px;
        color: #38bdf8;
        background: rgba(0,0,0,0.6);
        padding: 2px 8px;
        border-radius: 4px;
        letter-spacing: 1px;
    }

    /* ===== BUTTONS ===== */
    .stButton > button {
        background: linear-gradient(135deg, #16a34a, #22c55e) !important;
        color: white !important;
        border: none !important;
        border-radius: 12px !important;
        font-family: 'Inter', sans-serif !important;
        font-weight: 600 !important;
        font-size: 14px !important;
        padding: 12px 16px !important;
        transition: transform 0.2s ease, box-shadow 0.2s ease !important;
        width: 100%;
        box-shadow: 0 4px 15px rgba(22, 163, 74, 0.2) !important;
    }
    .stButton > button:hover {
        transform: scale(1.02);
        box-shadow: 0 10px 25px rgba(22, 163, 74, 0.4) !important;
    }
    .stButton > button:active {
        transform: scale(0.98);
    }

    /* ===== LOG TERMINAL ===== */
    .log-terminal {
        background: rgba(5,8,15,0.9);
        border: 1px solid rgba(56,189,248,0.08);
        border-radius: 8px;
        padding: 10px 12px;
        max-height: 220px;
        overflow-y: auto;
    }
    .log-line {
        font-family: 'JetBrains Mono', monospace;
        font-size: 10px;
        color: #64748b;
        padding: 3px 0;
        border-bottom: 1px solid rgba(30,58,95,0.15);
        line-height: 1.5;
    }
    .log-line:last-child { border-bottom: none; }
    .log-timestamp { color: #1e3a5f; }
    .log-highlight { color: #38bdf8; }

    /* ===== SECTION DIVIDER ===== */
    .section-divider {
        height: 1px;
        background: linear-gradient(90deg, transparent, rgba(56,189,248,0.15), transparent);
        margin: 20px 0;
    }

    /* ===== NO-CAM PLACEHOLDER ===== */
    .no-cam {
        width: 100%;
        height: 400px;
        background: radial-gradient(circle at center, #0a1020, #050810);
        border-radius: 8px;
        display: flex;
        flex-direction: column;
        align-items: center;
        justify-content: center;
        border: 1px solid rgba(56,189,248,0.1);
    }
    .no-cam-icon { font-size: 40px; margin-bottom: 10px; opacity: 0.3; }
    .no-cam-text {
        font-family: 'JetBrains Mono', monospace;
        font-size: 12px;
        color: #334155;
        letter-spacing: 2px;
    }
</style>
""", unsafe_allow_html=True)

# ============================================================
# Configuration
# ============================================================
BACKEND_URL = "http://localhost:8000"

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

def send_control(action: str):
    try:
        requests.post(f"{BACKEND_URL}/backend/manual_control", json={"action": action}, timeout=2)
    except Exception:
        st.error("⚠️ Command failed")

def toggle_mode(mode: str):
    try:
        res = requests.post(f"{BACKEND_URL}/set_mode", json={"mode": mode}, timeout=2)
        return res.ok
    except Exception:
        st.error("⚠️ Mode switch failed")
        return False

# ============================================================
# Fetch Telemetry
# ============================================================
status_data = fetch_status()
backend_online = status_data is not None

if status_data is None:
    status_data = {
        "status": "BACKEND OFFLINE",
        "mode": "unknown",
        "cargo_state": "UNKNOWN",
        "latestLog": "Cannot reach backend",
        "obstacle_detected": False,
        "distance_cm": 0,
        "esp32_connected": False,
        "camera_active": False,
        "log_history": [],
        "esp_commands": []
    }

is_manual = status_data["mode"] == "manual"
now = datetime.now().strftime("%H:%M:%S")

# ============================================================
# MAIN GRID
# ============================================================

# ==================== TOP BAR ====================
s = fetch_status() or status_data
backend_online = s["status"] != "BACKEND OFFLINE"

def conn_pill(label, online):
    cls = "conn-online" if online else "conn-offline"
    dot = "conn-dot-on" if online else "conn-dot-off"
    return f'<span class="conn-pill {cls}"><span class="conn-dot {dot}"></span>{label}</span>'

st.markdown(f"""
<div class="topbar">
    <div>
        <div class="topbar-title">MISSION CONTROL</div>
        <div class="topbar-subtitle">AUTONOMOUS DELIVERY SYSTEM v2.0</div>
    </div>
    <div class="topbar-right">
        <div class="conn-group">
            {conn_pill("BACKEND", backend_online)}
            {conn_pill("ESP32", s.get("esp32_connected", False))}
            {conn_pill("CAMERA", s.get("camera_active", False))}
        </div>
    </div>
</div>
""", unsafe_allow_html=True)

col_left, col_right = st.columns([5, 3], gap="large")

# ==================== LEFT COLUMN ====================
with col_left:
    # --- LIVE FEED ---
    st.markdown('<div class="panel">', unsafe_allow_html=True)
    st.markdown('<div class="panel-label">LIVE VISION FEED — YOLOv8</div>', unsafe_allow_html=True)

    if backend_online and status_data.get("camera_active"):
        st.markdown(f"""
        <div class="video-wrap">
            <img src="{BACKEND_URL}/video_feed" alt="YOLO Feed" />
            <div class="video-overlay-tl">● REC</div>
            <div class="video-overlay-tr">YOLO v8n</div>
        </div>
        """, unsafe_allow_html=True)
    else:
        st.markdown("""
        <div class="no-cam">
            <div class="no-cam-icon">📡</div>
            <div class="no-cam-text">AWAITING VIDEO SIGNAL</div>
        </div>
        """, unsafe_allow_html=True)
    st.markdown('</div>', unsafe_allow_html=True)

    # --- SYSTEM LOG TERMINAL ---
    @st.fragment(run_every="1s")
    def render_system_log():
        s = fetch_status() or status_data
        st.markdown('<div class="panel">', unsafe_allow_html=True)
        st.markdown('<div class="panel-label">SYSTEM LOG</div>', unsafe_allow_html=True)
    
        log_history = s.get("log_history", [])
        if log_history:
            log_html = ""
            for log in reversed(log_history[-15:]):
                if "]" in log:
                    ts, msg = log.split("]", 1)
                    log_html += f'<div class="log-line"><span class="log-timestamp">{ts}]</span>{msg}</div>'
                else:
                    log_html += f'<div class="log-line">{log}</div>'
            st.markdown(f'<div class="log-terminal">{log_html}</div>', unsafe_allow_html=True)
        else:
            st.markdown('<div class="log-terminal"><div class="log-line" style="color:#334155; text-align:center;">Waiting for log data...</div></div>', unsafe_allow_html=True)
        st.markdown('</div>', unsafe_allow_html=True)
        
        # --- ESP32 COMMAND TERMINAL ---
        st.markdown('<div class="panel" style="margin-top: 14px;">', unsafe_allow_html=True)
        st.markdown('<div class="panel-label">ESP32 TELEMETRY</div>', unsafe_allow_html=True)
    
        esp_history = s.get("esp_commands", [])
        if esp_history:
            esp_html = ""
            for log in reversed(esp_history[-10:]):
                if "]" in log:
                    ts, msg = log.split("]", 1)
                    if "SENT" in msg:
                        color = "#4ade80" # Green
                    elif "RECV" in msg:
                        color = "#38bdf8" # Blue
                    else:
                        color = "#64748b"
                        
                    esp_html += f'<div class="log-line"><span class="log-timestamp">{ts}]</span><span style="color:{color}; font-weight:600;">{msg}</span></div>'
                else:
                    esp_html += f'<div class="log-line">{log}</div>'
            st.markdown(f'<div class="log-terminal" style="max-height:150px;">{esp_html}</div>', unsafe_allow_html=True)
        else:
            st.markdown('<div class="log-terminal" style="max-height:150px;"><div class="log-line" style="color:#334155; text-align:center;">No ESP32 telemetry...</div></div>', unsafe_allow_html=True)
        st.markdown('</div>', unsafe_allow_html=True)
        
    render_system_log()


# ==================== RIGHT COLUMN ====================
with col_right:
    @st.fragment(run_every="1s")
    def render_right_column():
        s = fetch_status() or status_data
        is_manual = s["mode"] == "manual"
    
        # --- MODE BANNER ---
        if is_manual:
            st.markdown('<div class="mode-banner mode-manual">⚠ MANUAL OVERRIDE</div>', unsafe_allow_html=True)
        else:
            st.markdown('<div class="mode-banner mode-auto">◉ AUTONOMOUS</div>', unsafe_allow_html=True)
    
        # --- STATUS READOUT ---
        st.markdown('<div class="panel">', unsafe_allow_html=True)
        st.markdown('<div class="panel-label">CURRENT STATUS</div>', unsafe_allow_html=True)
        st.markdown(f'<div class="status-readout">{s["status"]}</div>', unsafe_allow_html=True)
        st.markdown(f'<div class="status-detail">{s["latestLog"]}</div>', unsafe_allow_html=True)
        st.markdown('</div>', unsafe_allow_html=True)
    
        # --- METRICS ROW ---
        m1, m2, m3 = st.columns(3)
        with m1:
            is_blocked = "IN PATH" in s["status"] or "STOP" in s["status"] or "TOO CLOSE" in s["status"]
            is_seen = s["status"] != "🔍 SEARCHING" and "PATH CLEAR" not in s["status"]
            
            if is_blocked:
                obs_color, obs_text, obs_icon = "#ef4444", "BLOCKED", "🚨"
            elif is_seen:
                obs_color, obs_text, obs_icon = "#eab308", "DETECTED", "👁️"
            else:
                obs_color, obs_text, obs_icon = "#22c55e", "CLEAR", "✅"
                
            st.markdown(f"""
            <div class="metric-tile">
                <div class="metric-tile-value" style="color:{obs_color}">{obs_icon}</div>
                <div class="metric-tile-label">{obs_text}</div>
            </div>
            """, unsafe_allow_html=True)
        with m2:
            mode_icon = "🎮" if is_manual else "🤖"
            mode_label = "MANUAL" if is_manual else "AUTO"
            mode_color = "#fca5a5" if is_manual else "#a5b4fc"
            st.markdown(f"""
            <div class="metric-tile">
                <div class="metric-tile-value" style="color:{mode_color}">{mode_icon}</div>
                <div class="metric-tile-label">{mode_label}</div>
            </div>
            """, unsafe_allow_html=True)
        with m3:
            cargo_state = s.get("cargo_state", "UNKNOWN")
            if cargo_state == "LOCKED":
                color = "#ef4444"
                icon = "\U0001f512"  # 🔒
            else:
                color = "#4ade80"
                icon = "\U0001f513"  # 🔓
            st.markdown(f"""
            <div class="metric-tile">
                <div class="metric-tile-value" style="color:{color}">{icon} {cargo_state}</div>
                <div class="metric-tile-label">CARGO STATUS</div>
            </div>
            """, unsafe_allow_html=True)
    
        st.markdown("<br>", unsafe_allow_html=True)
    
        # --- HEALTH & POWER METRICS ---
        st.markdown('<div class="panel">', unsafe_allow_html=True)
        st.markdown('<div class="panel-label">HEALTH & POWER</div>', unsafe_allow_html=True)
        
        battery = s.get("battery_level", 0)
        temp = s.get("robot_temperature", 0.0)
        amps = s.get("motor_current", 0.0)
        
        # Battery Bar
        bat_color = "#4ade80" if battery > 20 else "#ef4444"
        st.markdown(f"""
        <div class="prox-bar-container">
            <div style="font-family:'JetBrains Mono'; font-size:10px; color:#94a3b8; margin-bottom:6px;">MAIN BATTERY: <span style="color:{bat_color}; font-weight:bold;">{battery}%</span></div>
            <div class="prox-bar-track">
                <div class="prox-bar-fill" style="width: {battery}%; background: {bat_color};"></div>
            </div>
        </div>
        """, unsafe_allow_html=True)
        
        # Temp & Current
        t1, t2 = st.columns(2)
        with t1:
            temp_color = "#ef4444" if temp > 45 else "#38bdf8"
            st.markdown(f"""
            <div class="metric-tile" style="padding: 8px;">
                <div class="metric-tile-value" style="font-size:18px; color:{temp_color}">{temp}<span class="metric-tile-unit">°C</span></div>
                <div class="metric-tile-label" style="font-size:8px;">CORE TEMP</div>
            </div>
            """, unsafe_allow_html=True)
        with t2:
            amp_color = "#ef4444" if amps > 10 else "#eab308"
            st.markdown(f"""
            <div class="metric-tile" style="padding: 8px;">
                <div class="metric-tile-value" style="font-size:18px; color:{amp_color}">{amps}<span class="metric-tile-unit">A</span></div>
                <div class="metric-tile-label" style="font-size:8px;">MOTOR DRAW</div>
            </div>
            """, unsafe_allow_html=True)
            
        st.markdown('</div>', unsafe_allow_html=True)
    
        # --- CONTROLS SECTION ---
        st.markdown('<div class="panel">', unsafe_allow_html=True)
        st.markdown('<div class="panel-label">MODE CONTROL</div>', unsafe_allow_html=True)
        if is_manual:
            if st.button("🔄  RESUME AUTONOMOUS", use_container_width=True, key="mode_btn"):
                toggle_mode("autonomous")
                st.rerun()
        else:
            if st.button("🚨  EMERGENCY OVERRIDE", use_container_width=True, key="mode_btn"):
                toggle_mode("manual")
                st.rerun()
        st.markdown('</div>', unsafe_allow_html=True)
    
        if is_manual:
            st.markdown('<div class="panel">', unsafe_allow_html=True)
            st.markdown('<div class="panel-label">DRIVE CONTROLS</div>', unsafe_allow_html=True)
            _, c_fwd, _ = st.columns([1, 1, 1])
            with c_fwd:
                if st.button("▲ FWD", key="fwd"):
                    send_control("forward")
            c_left, c_stop, c_right = st.columns(3)
            with c_left:
                if st.button("◄ LFT", key="left"):
                    send_control("left")
            with c_stop:
                if st.button("■ STP", key="stop"):
                    send_control("stop")
            with c_right:
                if st.button("► RGT", key="right"):
                    send_control("right")
            _, c_rev, _ = st.columns([1, 1, 1])
            with c_rev:
                if st.button("▼ REV", key="rev"):
                    send_control("reverse")
            st.markdown('</div>', unsafe_allow_html=True)
    
        # Cargo Latch — always available regardless of mode
        st.markdown('<div class="panel">', unsafe_allow_html=True)
        st.markdown('<div class="panel-label">CARGO LATCH</div>', unsafe_allow_html=True)
        c_lock, c_unlock = st.columns(2)
        with c_lock:
            if st.button("🔒 LOCK", key="lock"):
                try:
                    requests.post(f"{BACKEND_URL}/backend/pack_order", timeout=3)
                except Exception:
                    st.error("⚠️ Lock command failed")
        with c_unlock:
            if st.button("🔓 UNLOCK", key="unlock"):
                try:
                    requests.post(f"{BACKEND_URL}/backend/unlock", json={"action": "unlock"}, timeout=3)
                except Exception:
                    st.error("⚠️ Unlock command failed")
        st.markdown('</div>', unsafe_allow_html=True)
            
    render_right_column()

    # --- SATELLITE TRACKING MAP ---
    st.markdown('<div class="panel">', unsafe_allow_html=True)
    st.markdown('<div class="panel-label">SATELLITE TRACKING</div>', unsafe_allow_html=True)
    
    GMAPS_API_KEY = os.environ.get("GMAPS_API_KEY", "AIzaSyBX0xNBFK24V2DZgMQHFku3tWcJWtVjgds")
    
    map_html = f"""
    <!DOCTYPE html>
    <html>
    <head>
        <style>
            #map {{ height: 350px; width: 100%; border-radius: 8px; }}
        </style>
        <script>
            (g=>{{var h,a,k,p="The Google Maps JavaScript API",c="google",l="importLibrary",q="__ib__",m=document,b=window;b=b[c]||(b[c]={{}});var d=b.maps||(b.maps={{}}),r=new Set,e=new URLSearchParams,u=()=>h||(h=new Promise(async(f,n)=>{{await (a=m.createElement("script"));e.set("libraries",[...r]+"");for(k in g)e.set(k.replace(/[A-Z]/g,t=>"_"+t[0].toLowerCase()),g[k]);e.set("callback",c+".maps."+q);a.src=`https://maps.${{c}}apis.com/maps/api/js?`+e;d[q]=f;a.onerror=()=>h=n(Error(p+" could not load."));a.nonce=m.querySelector("script[nonce]")?.nonce||"";m.head.append(a)}}));d[l]?console.warn(p+" only loads once. Ignoring:",g):d[l]=(f,...n)=>r.add(f)&&u().then(()=>d[l](f,...n))}})({{
                key: "{GMAPS_API_KEY}",
                v: "weekly"
            }});
        </script>
    </head>
    <body style="margin:0; padding:0; background:#0a0f1a;">
        <div id="map"></div>
        <script>
            let map, botMarker, sourceMarker, destMarker;
            
            async function initMap() {{
                const {{ Map }} = await google.maps.importLibrary("maps");
                const {{ AdvancedMarkerElement, PinElement }} = await google.maps.importLibrary("marker");
                
                map = new Map(document.getElementById("map"), {{
                    zoom: 15,
                    center: {{ lat: 37.7749, lng: -122.4194 }}, // Default SF
                    mapTypeId: 'satellite',
                    mapId: 'DEMO_MAP_ID',
                    disableDefaultUI: true,
                }});

                const botPin = new PinElement({{ background: "#3b82f6", borderColor: "#1d4ed8", glyphColor: "white" }});
                const srcPin = new PinElement({{ background: "#22c55e", borderColor: "#166534", glyphColor: "white" }});
                const dstPin = new PinElement({{ background: "#ef4444", borderColor: "#991b1b", glyphColor: "white" }});

                botMarker = new AdvancedMarkerElement({{ map: map, content: botPin.element, title: "Delivery Cart" }});
                sourceMarker = new AdvancedMarkerElement({{ map: map, content: srcPin.element, title: "Source" }});
                destMarker = new AdvancedMarkerElement({{ map: map, content: dstPin.element, title: "Destination" }});
                
                pollBackend();
            }}
            
            async function pollBackend() {{
                try {{
                    const res = await fetch("{BACKEND_URL}/status");
                    const data = await res.json();
                    
                    if(data.map_data) {{
                        const bounds = new google.maps.LatLngBounds();
                        let hasBounds = false;
                        
                        if(data.map_data.live_location) {{
                            botMarker.position = data.map_data.live_location;
                            botMarker.map = map;
                            bounds.extend(data.map_data.live_location);
                            hasBounds = true;
                        }} else {{
                            botMarker.map = null;
                        }}
                        
                        if(data.map_data.source) {{
                            sourceMarker.position = data.map_data.source;
                            sourceMarker.map = map;
                            bounds.extend(data.map_data.source);
                            hasBounds = true;
                        }} else {{
                            sourceMarker.map = null;
                        }}
                        
                        if(data.map_data.destination) {{
                            destMarker.position = data.map_data.destination;
                            destMarker.map = map;
                            bounds.extend(data.map_data.destination);
                            hasBounds = true;
                        }} else {{
                            destMarker.map = null;
                        }}
                        
                        // Fit map to show all markers (zoomed out as requested)
                        if(hasBounds) {{
                            map.fitBounds(bounds);
                            // Don't zoom in too close if there's only one point
                            if(map.getZoom() > 18) map.setZoom(18);
                        }}
                    }}
                }} catch(e) {{
                    console.error("Failed to fetch map data");
                }}
                
                setTimeout(pollBackend, 2000);
            }}
            
            initMap();
        </script>
    </body>
    </html>
    """
    
    components.html(map_html, height=360)
    st.markdown('</div>', unsafe_allow_html=True)
