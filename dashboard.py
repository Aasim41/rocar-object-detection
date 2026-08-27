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
    @import url('https://fonts.googleapis.com/css2?family=JetBrains+Mono:wght@400;500;600&family=Inter:wght@400;500;600;700;800&display=swap');
    
    /* ===== CORE VARIABLES & ANIMATIONS ===== */
    :root {
        --bg-main: #0A0A0B; /* Deep neutral black */
        --bg-panel: rgba(24, 24, 27, 0.6); /* Neutral zinc */
        --border-color: rgba(255, 255, 255, 0.08);
        --border-hover: rgba(255, 255, 255, 0.15);
        --accent-blue: #ffffff; /* Clean white instead of neon blue */
        --text-main: #ededed;
        --text-muted: #a1a1aa;
    }

    @keyframes fadeSlideUp {
        0% { opacity: 0; transform: translateY(15px); }
        100% { opacity: 1; transform: translateY(0); }
    }

    .stApp {
        background: var(--bg-main) !important;
        /* Removed the glowing radial gradients for a cleaner, flatter look */
        color: var(--text-main);
        font-family: 'Inter', sans-serif;
    }

    #MainMenu, footer, .stDeployButton, header { display: none !important; }

    ::-webkit-scrollbar { width: 6px; }
    ::-webkit-scrollbar-track { background: transparent; }
    ::-webkit-scrollbar-thumb { background: rgba(255,255,255,0.1); border-radius: 10px; }
    ::-webkit-scrollbar-thumb:hover { background: rgba(255,255,255,0.2); }

    /* ===== ANTI-BLINK: Hide Streamlit fragment re-render flash ===== */
    [data-stale="true"],
    .stale,
    .element-container.stale,
    .stMarkdown.stale {
        opacity: 1 !important;
        transition: none !important;
    }
    
    /* Prevent any fade-out/fade-in transitions on fragment containers */
    .stElementContainer,
    .element-container,
    [data-testid="stVerticalBlock"],
    [data-testid="column"] {
        transition: none !important;
        animation: none !important;
    }
    
    /* Kill the spinner/loading overlay that appears during re-render */
    .stSpinner, [data-testid="stSpinner"] {
        display: none !important;
    }

    /* ===== TOP BAR (GLASSMORPHISM) ===== */
    .topbar {
        background: rgba(10, 10, 11, 0.85);
        backdrop-filter: blur(20px);
        -webkit-backdrop-filter: blur(20px);
        border-bottom: 1px solid var(--border-color);
        padding: 20px 40px;
        display: flex;
        justify-content: space-between;
        align-items: center;
        margin: -1.2rem -1.2rem 24px -1.2rem;
        position: sticky;
        top: 0;
        z-index: 999;
        animation: fadeSlideUp 0.5s ease-out;
    }

    .topbar-title {
        font-family: 'Inter', sans-serif;
        font-size: 20px;
        font-weight: 800;
        letter-spacing: 0.5px;
        display: flex;
        align-items: center;
        gap: 12px;
    }
    
    .topbar-title span {
        background: linear-gradient(to right, #ffffff, #94a3b8);
        -webkit-background-clip: text;
        -webkit-text-fill-color: transparent;
    }

    .topbar-subtitle {
        font-family: 'JetBrains Mono', monospace;
        font-size: 11px;
        color: var(--text-muted);
        letter-spacing: 1.5px;
        text-transform: uppercase;
        margin-top: 4px;
        opacity: 0.7;
    }

    .topbar-right {
        display: flex;
        align-items: center;
        gap: 20px;
    }

    .live-clock {
        font-family: 'JetBrains Mono', monospace;
        font-size: 13px;
        color: var(--text-muted);
        background: rgba(255,255,255,0.03);
        padding: 6px 14px;
        border-radius: 8px;
        border: 1px solid var(--border-color);
    }

    /* ===== CONNECTION PILLS ===== */
    .conn-group { display: flex; gap: 10px; }
    .conn-pill {
        display: flex;
        align-items: center;
        gap: 8px;
        padding: 6px 14px;
        border-radius: 30px;
        font-family: 'Inter', sans-serif;
        font-size: 11px;
        font-weight: 600;
        letter-spacing: 0.5px;
        transition: all 0.3s ease;
    }
    .conn-online {
        background: rgba(16, 185, 129, 0.08);
        border: 1px solid rgba(16, 185, 129, 0.2);
        color: #34d399;
    }
    .conn-offline {
        background: rgba(239, 68, 68, 0.08);
        border: 1px solid rgba(239, 68, 68, 0.2);
        color: #f87171;
    }
    
    .conn-dot {
        width: 6px; height: 6px;
        border-radius: 50%;
    }
    .conn-dot-on { background: #34d399; box-shadow: 0 0 8px rgba(52, 211, 153, 0.4); }
    .conn-dot-off { background: #f87171; box-shadow: 0 0 8px rgba(248, 113, 113, 0.4); }

    @keyframes softPulse {
        0%, 100% { opacity: 1; transform: scale(1); }
        50% { opacity: 0.6; transform: scale(0.95); }
    }
    .conn-online .conn-dot { animation: softPulse 2.5s ease-in-out infinite; }

    /* ===== PREMIUM PANELS ===== */
    .panel {
        background: var(--bg-panel);
        border: 1px solid var(--border-color);
        border-radius: 16px;
        padding: 24px;
        margin-bottom: 20px;
        backdrop-filter: blur(12px);
        -webkit-backdrop-filter: blur(12px);
        box-shadow: 0 8px 32px rgba(0, 0, 0, 0.15);
        transition: all 0.3s cubic-bezier(0.4, 0, 0.2, 1);
        animation: fadeSlideUp 0.6s ease-out backwards;
    }
    
    /* Stagger panel animations */
    .panel:nth-child(1) { animation-delay: 0.1s; }
    .panel:nth-child(2) { animation-delay: 0.2s; }
    .panel:nth-child(3) { animation-delay: 0.3s; }

    .panel:hover {
        border-color: var(--border-hover);
        box-shadow: 0 8px 32px rgba(14, 165, 233, 0.05);
        transform: translateY(-2px);
    }

    .panel-label {
        font-family: 'Inter', sans-serif;
        font-size: 11px;
        font-weight: 700;
        color: var(--text-muted);
        letter-spacing: 1.5px;
        text-transform: uppercase;
        margin-bottom: 20px;
        display: flex;
        align-items: center;
        gap: 10px;
    }
    .panel-label::before {
        content: '';
        width: 6px; height: 6px;
        background: var(--accent-blue);
        border-radius: 50%;
        box-shadow: 0 0 8px rgba(14, 165, 233, 0.4);
    }

    /* ===== STATUS READOUT ===== */
    .status-readout {
        font-family: 'Inter', sans-serif;
        font-size: 20px;
        font-weight: 700;
        color: #f1f5f9;
        margin-bottom: 6px;
    }
    .status-detail {
        font-family: 'JetBrains Mono', monospace;
        font-size: 12px;
        color: var(--text-muted);
    }

    /* ===== METRIC TILES ===== */
    .metric-tile {
        background: rgba(0, 0, 0, 0.2);
        border: 1px solid var(--border-color);
        border-radius: 12px;
        padding: 16px;
        text-align: center;
        transition: all 0.2s ease;
    }
    .metric-tile:hover {
        background: rgba(255, 255, 255, 0.02);
        border-color: rgba(255, 255, 255, 0.1);
    }
    .metric-tile-value {
        font-family: 'JetBrains Mono', monospace;
        font-size: 24px;
        font-weight: 600;
        color: #f8fafc;
    }
    .metric-tile-unit {
        font-family: 'Inter', sans-serif;
        font-size: 12px;
        font-weight: 500;
        color: var(--text-muted);
        margin-left: 2px;
    }
    .metric-tile-label {
        font-family: 'Inter', sans-serif;
        font-size: 10px;
        color: var(--text-muted);
        letter-spacing: 1px;
        text-transform: uppercase;
        margin-top: 8px;
        font-weight: 600;
    }

    /* ===== VIDEO WRAPPER ===== */
    .video-wrap {
        border-radius: 12px;
        overflow: hidden;
        border: 1px solid var(--border-color);
        background: #000;
        position: relative;
        box-shadow: inset 0 0 20px rgba(0,0,0,0.5);
    }
    .video-wrap img {
        width: 100%;
        display: block;
        opacity: 0.9;
        transition: opacity 0.3s ease;
    }
    .video-wrap:hover img {
        opacity: 1;
    }
    .video-overlay-tl {
        position: absolute;
        top: 12px; left: 12px;
        font-family: 'Inter', sans-serif;
        font-size: 10px;
        font-weight: 700;
        color: #fff;
        background: rgba(239, 68, 68, 0.9);
        padding: 4px 10px;
        border-radius: 6px;
        letter-spacing: 0.5px;
        display: flex;
        align-items: center;
        gap: 6px;
        box-shadow: 0 2px 10px rgba(0,0,0,0.2);
    }
    .video-overlay-tl::before {
        content: '';
        display: block;
        width: 6px; height: 6px;
        background: #fff;
        border-radius: 50%;
        animation: softPulse 2s infinite;
    }
    .video-overlay-tr {
        position: absolute;
        top: 12px; right: 12px;
        font-family: 'JetBrains Mono', monospace;
        font-size: 10px;
        color: rgba(255,255,255,0.8);
        background: rgba(0,0,0,0.6);
        backdrop-filter: blur(4px);
        padding: 4px 10px;
        border-radius: 6px;
    }

    /* ===== STREAMLIT NATIVE BUTTONS ===== */
    .stButton > button {
        background: rgba(255, 255, 255, 0.05) !important;
        color: #f1f5f9 !important;
        border: 1px solid rgba(255, 255, 255, 0.1) !important;
        border-radius: 10px !important;
        font-family: 'Inter', sans-serif !important;
        font-weight: 500 !important;
        font-size: 14px !important;
        padding: 10px 16px !important;
        transition: all 0.2s cubic-bezier(0.4, 0, 0.2, 1) !important;
        width: 100%;
    }
    .stButton > button:hover {
        background: rgba(255, 255, 255, 0.1) !important;
        border-color: rgba(255, 255, 255, 0.2) !important;
        transform: translateY(-1px);
        box-shadow: 0 4px 12px rgba(0,0,0,0.1);
    }
    .stButton > button:active {
        transform: translateY(1px);
        background: rgba(255, 255, 255, 0.03) !important;
    }
    
    /* Highlight specific buttons if they contain specific text (hack for Streamlit) */
    .stButton > button p:contains("START") { color: #34d399 !important; }
    .stButton > button p:contains("STOP") { color: #f87171 !important; }

    /* ===== LOG TERMINAL ===== */
    .log-terminal {
        background: rgba(0, 0, 0, 0.3);
        border: 1px solid var(--border-color);
        border-radius: 10px;
        padding: 12px 16px;
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
    
    /* ===== PROXIMITY BAR ===== */
    .prox-bar-container {
        background: rgba(0,0,0,0.2);
        border: 1px solid var(--border-color);
        border-radius: 10px;
        padding: 14px 16px;
        margin-bottom: 16px;
    }
    .prox-bar-track {
        width: 100%;
        height: 6px;
        background: rgba(255,255,255,0.05);
        border-radius: 3px;
        overflow: hidden;
        position: relative;
    }
    .prox-bar-fill {
        height: 100%;
        border-radius: 3px;
        transition: width 0.4s cubic-bezier(0.4, 0, 0.2, 1);
    }
    .prox-bar-labels {
        display: flex;
        justify-content: space-between;
        margin-top: 8px;
        font-family: 'Inter', sans-serif;
        font-size: 10px;
        font-weight: 500;
        color: var(--text-muted);
    }

    /* ===== NO-CAM PLACEHOLDER ===== */
    .no-cam {
        width: 100%;
        height: 400px;
        background: rgba(0,0,0,0.2);
        border-radius: 12px;
        display: flex;
        flex-direction: column;
        align-items: center;
        justify-content: center;
        border: 1px dashed rgba(255,255,255,0.15);
    }
    .no-cam-icon { 
        font-size: 32px; 
        margin-bottom: 12px; 
        opacity: 0.5;
        filter: grayscale(1);
    }
    .no-cam-text {
        font-family: 'Inter', sans-serif;
        font-size: 13px;
        font-weight: 500;
        color: var(--text-muted);
        letter-spacing: 0.5px;
    }
</style>
""", unsafe_allow_html=True)

# ============================================================
# Configuration
# ============================================================
import os
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
            {conn_pill("GPS APP", s.get("gps_app_connected", False))}
            {conn_pill("TRACKING", s.get("tracking_clients", 0) > 0)}
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
            <img id="yolo-feed" src="{BACKEND_URL}/video_feed" alt="YOLO Feed"
                 onerror="setTimeout(function(){{ document.getElementById('yolo-feed').src='{BACKEND_URL}/video_feed?t='+Date.now(); }}, 2000);" />
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
        import html
        s = fetch_status() or status_data
        st.markdown('<div class="panel">', unsafe_allow_html=True)
        st.markdown('<div class="panel-label">SYSTEM LOG</div>', unsafe_allow_html=True)
    
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
                    ts, msg = html.escape(ts), html.escape(msg)
                    if "SENT" in msg:
                        color = "#4ade80" # Green
                    elif "RECV" in msg:
                        color = "#38bdf8" # Blue
                    else:
                        color = "#64748b"
                        
                    esp_html += f'<div class="log-line"><span class="log-timestamp">{ts}]</span><span style="color:{color}; font-weight:600;">{msg}</span></div>'
                else:
                    esp_html += f'<div class="log-line">{html.escape(log)}</div>'
            st.markdown(f'<div class="log-terminal" style="max-height:150px;">{esp_html}</div>', unsafe_allow_html=True)
        else:
            st.markdown('<div class="log-terminal" style="max-height:150px;"><div class="log-line" style="color:#334155; text-align:center;">No ESP32 telemetry...</div></div>', unsafe_allow_html=True)
        st.markdown('</div>', unsafe_allow_html=True)
        
    render_system_log()


# ==================== RIGHT COLUMN ====================
with col_right:
    # --- STATUS & METRICS (auto-refresh) ---
    @st.fragment(run_every="1s")
    def render_status_telemetry():
        s = fetch_status() or status_data
        is_manual = s["mode"] == "manual"
    
        # --- STATUS READOUT ---
        st.markdown('<div class="panel">', unsafe_allow_html=True)
        st.markdown('<div class="panel-label">CURRENT STATUS</div>', unsafe_allow_html=True)
        st.markdown(f'<div class="status-readout">{s["status"]}</div>', unsafe_allow_html=True)
        st.markdown(f'<div class="status-detail">{s["latestLog"]}</div>', unsafe_allow_html=True)
    
        # --- METRICS ROW (inside the same panel) ---
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
        st.markdown('</div>', unsafe_allow_html=True)
    
        # --- HEALTH & POWER METRICS ---
        st.markdown('<div class="panel">', unsafe_allow_html=True)
        st.markdown('<div class="panel-label">HEALTH, POWER & TELEMETRY</div>', unsafe_allow_html=True)
        
        battery = s.get("battery_level", 0)
        temp = s.get("robot_temperature", 0.0)
        amps = s.get("motor_current", 0.0)
        speed = s.get("gps_speed", 0.0)
        accuracy = s.get("gps_accuracy", 0.0)
        
        bat_color = "#4ade80" if battery > 20 else "#ef4444"
        st.markdown(f"""
        <div class="prox-bar-container">
            <div style="font-family:'JetBrains Mono'; font-size:10px; color:#94a3b8; margin-bottom:6px;">MAIN BATTERY: <span style="color:{bat_color}; font-weight:bold;">{battery}%</span></div>
            <div class="prox-bar-track">
                <div class="prox-bar-fill" style="width: {battery}%; background: {bat_color};"></div>
            </div>
        </div>
        """, unsafe_allow_html=True)
        
        t1, t2 = st.columns(2)
        with t1:
            temp_color = "#ef4444" if temp > 45 else "#a1a1aa"
            st.markdown(f"""
            <div class="metric-tile" style="padding: 8px;">
                <div class="metric-tile-value" style="font-size:18px; color:{temp_color}">{temp}<span class="metric-tile-unit">°C</span></div>
                <div class="metric-tile-label" style="font-size:8px;">CORE TEMP</div>
            </div>
            """, unsafe_allow_html=True)
            speed_color = "#4ade80" if speed > 0 else "#a1a1aa"
            st.markdown(f"""
            <div class="metric-tile" style="padding: 8px;">
                <div class="metric-tile-value" style="font-size:18px; color:{speed_color}">{speed:.1f}<span class="metric-tile-unit">km/h</span></div>
                <div class="metric-tile-label" style="font-size:8px;">GPS SPEED</div>
            </div>
            """, unsafe_allow_html=True)
        with t2:
            amp_color = "#ef4444" if amps > 10 else "#a1a1aa"
            st.markdown(f"""
            <div class="metric-tile" style="padding: 8px;">
                <div class="metric-tile-value" style="font-size:18px; color:{amp_color}">{amps}<span class="metric-tile-unit">A</span></div>
                <div class="metric-tile-label" style="font-size:8px;">MOTOR DRAW</div>
            </div>
            """, unsafe_allow_html=True)
            acc_color = "#4ade80" if accuracy > 0 and accuracy < 10 else "#eab308" if accuracy >= 10 else "#a1a1aa"
            st.markdown(f"""
            <div class="metric-tile" style="padding: 8px;">
                <div class="metric-tile-value" style="font-size:18px; color:{acc_color}">±{accuracy:.1f}<span class="metric-tile-unit">m</span></div>
                <div class="metric-tile-label" style="font-size:8px;">GPS ACCURACY</div>
            </div>
            """, unsafe_allow_html=True)
            
        st.markdown('</div>', unsafe_allow_html=True)
    
    render_status_telemetry()

    # --- MODE TOGGLE (static, no auto-refresh) ---
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

    # --- MANUAL DRIVE PAD (pure HTML/JS — zero Streamlit lag) ---
    if is_manual:
        drive_pad_html = f"""
        <html>
        <body style="margin:0; background:transparent;">
        <div style="
            background: rgba(24,24,27,0.6);
            border: 1px solid rgba(255,255,255,0.08);
            border-radius: 16px;
            padding: 24px;
        ">
            <div style="font-family:'Inter', sans-serif; font-size:11px; font-weight:700; color:#a1a1aa; letter-spacing:1.5px; text-transform:uppercase; margin-bottom:16px;">
                ● DRIVE CONTROLS
            </div>
            <style>
                .dpad {{ display:grid; grid-template-columns:1fr 1fr 1fr; gap:8px; max-width:240px; margin:0 auto; }}
                .dpad-btn {{
                    background: rgba(255,255,255,0.05);
                    border: 1px solid rgba(255,255,255,0.12);
                    border-radius: 10px;
                    color: #ededed;
                    font-family: 'Inter', sans-serif;
                    font-size: 18px;
                    font-weight: 600;
                    padding: 14px 0;
                    cursor: pointer;
                    transition: all 0.15s ease;
                    text-align: center;
                    user-select: none;
                    -webkit-user-select: none;
                }}
                .dpad-btn:hover {{ background: rgba(255,255,255,0.1); border-color: rgba(255,255,255,0.2); }}
                .dpad-btn:active {{ background: rgba(255,255,255,0.15); transform: scale(0.95); }}
                .dpad-stop {{
                    background: rgba(239,68,68,0.15) !important;
                    border-color: rgba(239,68,68,0.3) !important;
                    color: #f87171 !important;
                }}
                .dpad-stop:hover {{ background: rgba(239,68,68,0.25) !important; }}
                .dpad-label {{ font-size:9px; font-weight:500; color:#71717a; margin-top:2px; letter-spacing:1px; }}
            </style>
            <div class="dpad">
                <div></div>
                <button class="dpad-btn" onclick="sendCmd('forward')">▲<div class="dpad-label">FWD</div></button>
                <div></div>
                <button class="dpad-btn" onclick="sendCmd('left')">◄<div class="dpad-label">LFT</div></button>
                <button class="dpad-btn dpad-stop" onclick="sendCmd('stop')">■<div class="dpad-label">STOP</div></button>
                <button class="dpad-btn" onclick="sendCmd('right')">►<div class="dpad-label">RGT</div></button>
                <div></div>
                <button class="dpad-btn" onclick="sendCmd('reverse')">▼<div class="dpad-label">REV</div></button>
                <div></div>
            </div>
        </div>
        <script>
            function sendCmd(action) {{
                fetch("{BACKEND_URL}/backend/manual_control", {{
                    method: "POST",
                    headers: {{"Content-Type": "application/json"}},
                    body: JSON.stringify({{action: action}})
                }}).catch(e => console.error("Command failed:", e));
            }}
        </script>
        </body>
        </html>
        """
        components.html(drive_pad_html, height=270, scrolling=False)

    # --- CARGO LATCH (static, no auto-refresh) ---
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
