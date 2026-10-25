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

def fetch_telemetry_stats():
    try:
        res = requests.get(f"{BACKEND_URL}/backend/telemetry/stats", timeout=2)
        if res.ok:
            return res.json()
    except Exception:
        pass
    return {"total_logs": 0, "cached_routes": 0, "cache_hits": 0, "recent_logs": []}

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
            {conn_pill("ARDUINO", s.get("esp32_connected", False))}
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
        
        # --- BOT HARDWARE COMMAND TERMINAL ---
        st.markdown('<div class="panel" style="margin-top: 14px;">', unsafe_allow_html=True)
        st.markdown('<div class="panel-label">BOT HARDWARE TELEMETRY</div>', unsafe_allow_html=True)
    
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
            st.markdown('<div class="log-terminal" style="max-height:150px;"><div class="log-line" style="color:#334155; text-align:center;">No hardware telemetry...</div></div>', unsafe_allow_html=True)
        st.markdown('</div>', unsafe_allow_html=True)
        
    render_system_log()

    # --- MISSION TELEMETRY BLACKBOX & ROUTE CACHE ---
    @st.fragment(run_every="2s")
    def render_mission_telemetry_cache():
        t_stats = fetch_telemetry_stats()
        total_logs = t_stats.get("total_logs", 0)
        cached_routes = t_stats.get("cached_routes", 0)
        cache_hits = t_stats.get("cache_hits", 0)
        recent_logs = t_stats.get("recent_logs", [])
        
        st.markdown('<div class="panel" style="margin-top: 14px;">', unsafe_allow_html=True)
        st.markdown('<div class="panel-label">MISSION TELEMETRY BLACKBOX & ROUTE CACHE</div>', unsafe_allow_html=True)
        
        c1, c2, c3 = st.columns(3)
        with c1:
            st.markdown(f"""
            <div class="metric-tile" style="padding: 8px;">
                <div class="metric-tile-value" style="font-size:16px; color:#38bdf8;">{total_logs:,}</div>
                <div class="metric-tile-label" style="font-size:8px;">FLIGHT TICKS</div>
            </div>
            """, unsafe_allow_html=True)
        with c2:
            st.markdown(f"""
            <div class="metric-tile" style="padding: 8px;">
                <div class="metric-tile-value" style="font-size:16px; color:#a855f7;">{cached_routes}</div>
                <div class="metric-tile-label" style="font-size:8px;">ROUTES CACHED</div>
            </div>
            """, unsafe_allow_html=True)
        with c3:
            st.markdown(f"""
            <div class="metric-tile" style="padding: 8px;">
                <div class="metric-tile-value" style="font-size:16px; color:#4ade80;">{cache_hits}</div>
                <div class="metric-tile-label" style="font-size:8px;">CACHE HITS</div>
            </div>
            """, unsafe_allow_html=True)
            
        if recent_logs:
            rows_html = ""
            for r in recent_logs[:8]:
                ts = r.get("timestamp", "").split()[-1] if r.get("timestamp") else "--:--:--"
                cmd = r.get("motor_cmd", "stop")
                phase = (r.get("phase") or "IDLE")[:8]
                dist = r.get("ultrasonic_cm", 999)
                bias = r.get("steer_bias", 0.0)
                
                # Command Color
                if "steer" in cmd or "curve" in cmd:
                    cmd_color = "#38bdf8" # Blue
                elif "forward" in cmd or "slow" in cmd:
                    cmd_color = "#4ade80" # Green
                elif "stop" in cmd or "BLOCKED" in cmd:
                    cmd_color = "#f43f5e" # Rose
                else:
                    cmd_color = "#fbbf24" # Yellow
                
                dist_str = f"{dist}cm" if dist < 900 else "--"
                bias_str = f"b:{bias:+.2f}" if abs(bias) > 0.01 else "--"
                
                rows_html += f"""
                <div class="log-line" style="display:flex; justify-content:space-between; font-size:10px; font-family:'JetBrains Mono',monospace; padding:3px 0; border-bottom:1px solid rgba(255,255,255,0.03);">
                    <span style="color:#64748b; width:65px;">{ts}</span>
                    <span style="color:#94a3b8; font-weight:600; width:75px;">{phase}</span>
                    <span style="color:{cmd_color}; font-weight:700; flex:1;">{cmd}</span>
                    <span style="color:#e2e8f0; width:50px; text-align:right;">{dist_str}</span>
                    <span style="color:#a78bfa; width:55px; text-align:right;">{bias_str}</span>
                </div>
                """
            st.markdown(f'<div class="log-terminal" style="max-height:160px; margin-top:8px;">{rows_html}</div>', unsafe_allow_html=True)
        else:
            st.markdown('<div class="log-terminal" style="max-height:80px; margin-top:8px;"><div class="log-line" style="color:#334155; text-align:center;">Blackbox flight recorder standing by...</div></div>', unsafe_allow_html=True)
            
        st.markdown('</div>', unsafe_allow_html=True)
        
    render_mission_telemetry_cache()


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

    # --- MODE & FLEET CONTROL ---
    st.markdown('<div class="panel">', unsafe_allow_html=True)
    st.markdown('<div class="panel-label">FLEET COMMAND & MODE CONTROL</div>', unsafe_allow_html=True)
    
    # Handle the pop-up logic after rerun
    if st.session_state.get("open_manual_drive"):
        components.html(f"<script>window.open('{BACKEND_URL}/drive', '_blank');</script>", height=0)
        st.session_state["open_manual_drive"] = False

    mode_status = fetch_status() or status_data
    is_manual_now = mode_status.get("mode") == "manual"

    col_btn1, col_btn2 = st.columns(2)
    with col_btn1:
        if is_manual_now:
            if st.button("🔄  AUTONOMOUS", use_container_width=True, key="mode_btn"):
                toggle_mode("autonomous")
                st.rerun()
        else:
            if st.button("🚨  OVERRIDE", use_container_width=True, key="mode_btn"):
                toggle_mode("manual")
                st.session_state["open_manual_drive"] = True
                st.rerun()

    with col_btn2:
        if st.button("🏠  RETURN TO BASE", use_container_width=True, key="rtb_btn"):
            try:
                res = requests.post(f"{BACKEND_URL}/backend/return_to_base", timeout=3)
                if res.status_code == 200:
                    st.toast("🚀 Returning to Base Charging Station!", icon="🏠")
                else:
                    st.warning("Could not initiate return to base")
            except Exception as e:
                st.error(f"Error: {e}")
            st.rerun()
            
    st.markdown('<div style="margin-top: 15px; border-top: 1px solid rgba(255,255,255,0.1); padding-top: 10px;"></div>', unsafe_allow_html=True)
    
    routing_choice = st.selectbox("Routing Engine", ["Google Maps API", "Internal Graph (JUET)"], index=0, key="routing_engine")
    engine_val = "google" if "Google" in routing_choice else "self"
    
    # Send choice to backend
    if "last_routing_engine" not in st.session_state or st.session_state["last_routing_engine"] != engine_val:
        st.session_state["last_routing_engine"] = engine_val
        try:
            requests.post(f"{BACKEND_URL}/backend/set_routing_engine", json={"engine": engine_val}, timeout=2)
        except Exception:
            pass

    st.markdown('</div>', unsafe_allow_html=True)

    # --- IN-DASHBOARD EMERGENCY MANUAL REMOTE JOYSTICK ---
    if is_manual_now:
        st.markdown('<div class="panel">', unsafe_allow_html=True)
        st.markdown('<div class="panel-label">🕹️ EMERGENCY REMOTE OVERRIDE CONTROLLER</div>', unsafe_allow_html=True)
        
        joystick_html = f"""
        <!DOCTYPE html>
        <html>
        <head>
            <style>
                * {{ box-sizing: border-box; user-select: none; margin: 0; padding: 0; }}
                body {{ background: transparent; font-family: 'Inter', -apple-system, sans-serif; display: flex; flex-direction: column; align-items: center; justify-content: center; }}
                .pad-container {{ display: grid; grid-template-columns: repeat(3, 68px); grid-template-rows: repeat(3, 56px); gap: 8px; margin: 8px auto; }}
                .pad-btn {{
                    background: rgba(39, 39, 42, 0.8);
                    border: 1px solid rgba(255, 255, 255, 0.12);
                    color: #ededed;
                    border-radius: 12px;
                    font-size: 18px;
                    font-weight: 700;
                    display: flex;
                    align-items: center;
                    justify-content: center;
                    cursor: pointer;
                    transition: all 0.1s ease;
                    touch-action: manipulation;
                }}
                .pad-btn:hover {{ background: rgba(63, 63, 70, 0.9); border-color: rgba(255, 255, 255, 0.25); }}
                .pad-btn:active, .pad-btn.active {{
                    background: #3b82f6;
                    color: #ffffff;
                    border-color: #60a5fa;
                    transform: scale(0.94);
                    box-shadow: 0 0 12px rgba(59, 130, 246, 0.5);
                }}
                .btn-stop {{
                    background: rgba(225, 29, 72, 0.2);
                    border-color: rgba(225, 29, 72, 0.4);
                    color: #fb7185;
                    font-size: 13px;
                    font-weight: 800;
                    letter-spacing: 0.5px;
                }}
                .btn-stop:hover {{ background: rgba(225, 29, 72, 0.35); }}
                .btn-stop:active, .btn-stop.active {{
                    background: #e11d48;
                    color: #ffffff;
                    box-shadow: 0 0 16px rgba(225, 29, 72, 0.7);
                }}
                .aux-row {{ display: flex; gap: 8px; width: 100%; max-width: 220px; margin-top: 6px; }}
                .aux-btn {{
                    flex: 1;
                    padding: 8px;
                    background: rgba(30, 41, 59, 0.6);
                    border: 1px solid rgba(255, 255, 255, 0.08);
                    border-radius: 8px;
                    color: #94a3b8;
                    font-size: 11px;
                    font-weight: 600;
                    text-align: center;
                    cursor: pointer;
                    transition: all 0.12s;
                }}
                .aux-btn:hover {{ background: rgba(51, 65, 85, 0.8); color: #f8fafc; }}
                .aux-btn:active {{ background: #0284c7; color: white; }}
                .status-line {{ font-family: monospace; font-size: 11px; color: #64748b; margin-top: 8px; text-align: center; }}
            </style>
        </head>
        <body>
            <div class="pad-container">
                <div></div>
                <button class="pad-btn" id="btn-fwd" title="Forward (W or ↑)">▲</button>
                <div></div>

                <button class="pad-btn" id="btn-left" title="Left (A or ←)">◀</button>
                <button class="pad-btn btn-stop" id="btn-stop" title="Emergency Stop (Space)">STOP</button>
                <button class="pad-btn" id="btn-right" title="Right (D or →)">▶</button>

                <div></div>
                <button class="pad-btn" id="btn-rev" title="Reverse (S or ↓)">▼</button>
                <div></div>
            </div>

            <div class="aux-row">
                <button class="aux-btn" id="btn-beep">🔊 BEEP</button>
                <button class="aux-btn" id="btn-slow">⚡ SLOW</button>
            </div>
            <div class="aux-row" style="margin-top:6px;">
                <button class="aux-btn" id="btn-scan-l" style="background:rgba(13,148,136,0.2); border-color:rgba(13,148,136,0.4); color:#5eead4;">⬅️ SCAN L</button>
                <button class="aux-btn" id="btn-scan-c" style="background:rgba(13,148,136,0.2); border-color:rgba(13,148,136,0.4); color:#5eead4;">⏺️ SCAN C</button>
                <button class="aux-btn" id="btn-scan-r" style="background:rgba(13,148,136,0.2); border-color:rgba(13,148,136,0.4); color:#5eead4;">➡️ SCAN R</button>
            </div>
            <div class="status-line" id="cmd-status">READY: Keys W/A/S/D or Arrows</div>

            <script>
                const BACKEND = "{BACKEND_URL}";
                let isSending = false;

                function sendCmd(cmd) {{
                    const el = document.getElementById("cmd-status");
                    el.innerText = "COMMAND: " + cmd.toUpperCase();
                    el.style.color = cmd === "stop" ? "#f43f5e" : "#38bdf8";

                    if (cmd === "beep") {{
                        fetch(BACKEND + "/backend/beep", {{ method: "POST" }}).catch(() => {{}});
                        return;
                    }}

                    fetch(BACKEND + "/backend/manual_control", {{
                        method: "POST",
                        headers: {{ "Content-Type": "application/json" }},
                        body: JSON.stringify({{ cmd: cmd }})
                    }}).catch(err => {{
                        el.innerText = "ERR: " + err.message;
                        el.style.color = "#ef4444";
                    }});
                }}

                function bindBtn(id, cmd) {{
                    const btn = document.getElementById(id);
                    if (!btn) return;
                    let holdInterval = null;
                    const startAction = (e) => {{
                        e.preventDefault();
                        sendCmd(cmd);
                        if (cmd !== "stop" && cmd !== "beep" && !cmd.startsWith("scan")) {{
                            if (holdInterval) clearInterval(holdInterval);
                            holdInterval = setInterval(() => sendCmd(cmd), 300);
                        }}
                    }};
                    const stopAction = (e) => {{
                        if (holdInterval) {{
                            clearInterval(holdInterval);
                            holdInterval = null;
                        }}
                        if (cmd !== "stop" && cmd !== "beep" && !cmd.startsWith("scan")) {{
                            sendCmd("stop");
                        }}
                    }};
                    btn.addEventListener("mousedown", startAction);
                    btn.addEventListener("mouseup", stopAction);
                    btn.addEventListener("mouseleave", stopAction);
                    btn.addEventListener("touchstart", startAction);
                    btn.addEventListener("touchend", stopAction);
                }}

                bindBtn("btn-fwd", "forward");
                bindBtn("btn-left", "left");
                bindBtn("btn-stop", "stop");
                bindBtn("btn-right", "right");
                bindBtn("btn-rev", "reverse");
                bindBtn("btn-beep", "beep");
                bindBtn("btn-slow", "slow");
                bindBtn("btn-scan-l", "scan_left");
                bindBtn("btn-scan-c", "scan_center");
                bindBtn("btn-scan-r", "scan_right");

                // Keyboard Controls
                window.addEventListener("keydown", (e) => {{
                    if (e.repeat) return;
                    const key = e.key.toLowerCase();
                    if (key === "arrowup" || key === "w") {{ document.getElementById("btn-fwd").classList.add("active"); sendCmd("forward"); }}
                    else if (key === "arrowdown" || key === "s") {{ document.getElementById("btn-rev").classList.add("active"); sendCmd("reverse"); }}
                    else if (key === "arrowleft" || key === "a") {{ document.getElementById("btn-left").classList.add("active"); sendCmd("left"); }}
                    else if (key === "arrowright" || key === "d") {{ document.getElementById("btn-right").classList.add("active"); sendCmd("right"); }}
                    else if (key === " " || key === "escape") {{ document.getElementById("btn-stop").classList.add("active"); sendCmd("stop"); }}
                    else if (key === "b" || key === "h") {{ sendCmd("beep"); }}
                }});

                window.addEventListener("keyup", (e) => {{
                    document.querySelectorAll(".pad-btn").forEach(b => b.classList.remove("active"));
                }});
            </script>
        </body>
        </html>
        """
        components.html(joystick_html, height=260)
        st.markdown(f'<a href="{BACKEND_URL}/drive" target="_blank" style="display:block; width:100%; text-align:center; background:rgba(255, 255, 255, 0.05); border:1px solid rgba(255, 255, 255, 0.1); color:#94a3b8; padding:8px; border-radius:8px; font-size:11px; font-weight:600; text-decoration:none; font-family:Inter; margin-top:4px;">↗ POP OUT STANDALONE DRIVE PAD</a>', unsafe_allow_html=True)
        st.markdown('</div>', unsafe_allow_html=True)

    # --- CARGO LATCH & SCANNABLE QR PASS ---
    st.markdown('<div class="panel">', unsafe_allow_html=True)
    st.markdown('<div class="panel-label">CARGO LATCH & SCANNABLE QR PASS</div>', unsafe_allow_html=True)
    
    cargo_status = s.get("cargo_state", "LOCKED")
    is_unlocked = cargo_status == "UNLOCKED"
    
    qr_endpoint = f"{BACKEND_URL}/backend/verify_qr?cart_id=CART_01&action=unlock"
    qr_img_src = f"https://api.qrserver.com/v1/create-qr-code/?size=200x200&data={qr_endpoint}&bgcolor=18-18-24&color=4ade80"
    
    col_qr, col_latch_act = st.columns([1, 1], gap="medium")
    with col_qr:
        st.markdown(f"""
        <div style="text-align: center; background: rgba(0,0,0,0.3); border: 1px solid rgba(255,255,255,0.08); border-radius: 14px; padding: 14px; position: relative;">
            <div style="font-family: 'JetBrains Mono', monospace; font-size: 10px; color: #38bdf8; margin-bottom: 8px; font-weight: 600; letter-spacing: 0.5px;">📱 SCAN TO UNLOCK SERVO</div>
            <div style="position: relative; display: inline-block; border-radius: 12px; overflow: hidden; border: 2px solid #22c55e; box-shadow: 0 0 20px rgba(34, 197, 94, 0.25);">
                <img src="{qr_img_src}" alt="Scan QR to Unlock" style="display: block; width: 135px; height: 135px;" />
            </div>
            <div style="font-size: 9px; color: #94a3b8; margin-top: 8px; font-family: Inter;">Point any mobile camera to open lid (90°)</div>
        </div>
        """, unsafe_allow_html=True)
        
    with col_latch_act:
        state_badge = '<span style="color:#4ade80; font-weight:bold; font-size:14px;">🔓 UNLOCKED (90°)</span>' if is_unlocked else '<span style="color:#ef4444; font-weight:bold; font-size:14px;">🔒 LOCKED (0°)</span>'
        st.markdown(f"""
        <div style="padding: 4px 0 10px 0;">
            <div style="font-size: 10px; color: #94a3b8; font-family: 'JetBrains Mono';">LATCH HARDWARE STATE:</div>
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
    st.markdown('<div class="panel-label">LIVE SATELLITE & MISSION ROUTE TRACKING</div>', unsafe_allow_html=True)
    
    GMAPS_API_KEY = os.environ.get("GMAPS_API_KEY", "AIzaSyBX0xNBFK24V2DZgMQHFku3tWcJWtVjgds")
    
    map_html = f"""
    <!DOCTYPE html>
    <html>
    <head>
        <style>
            * {{ box-sizing: border-box; }}
            #map-wrapper {{ position: relative; width: 100%; height: 380px; border-radius: 12px; overflow: hidden; border: 1px solid rgba(255,255,255,0.08); }}
            #map {{ height: 100%; width: 100%; }}
            .map-ctrl-bar {{
                position: absolute;
                top: 10px;
                right: 10px;
                z-index: 10;
                display: flex;
                gap: 6px;
                background: rgba(10, 10, 15, 0.85);
                backdrop-filter: blur(12px);
                border: 1px solid rgba(255, 255, 255, 0.12);
                border-radius: 8px;
                padding: 4px;
            }}
            .map-type-btn {{
                background: transparent;
                border: none;
                color: #94a3b8;
                font-family: 'Inter', sans-serif;
                font-size: 11px;
                font-weight: 600;
                padding: 4px 8px;
                border-radius: 6px;
                cursor: pointer;
                transition: all 0.15s;
            }}
            .map-type-btn.active {{
                background: #3b82f6;
                color: #ffffff;
            }}
            .phase-hud {{
                position: absolute;
                bottom: 12px;
                left: 12px;
                z-index: 10;
                background: rgba(10, 10, 15, 0.85);
                backdrop-filter: blur(12px);
                border: 1px solid rgba(255, 255, 255, 0.15);
                border-radius: 8px;
                padding: 6px 14px;
                font-family: 'JetBrains Mono', monospace;
                font-size: 11px;
                color: #38bdf8;
                font-weight: 600;
                box-shadow: 0 4px 20px rgba(0,0,0,0.5);
                display: flex;
                align-items: center;
                gap: 8px;
            }}
            .hud-dot {{
                width: 7px;
                height: 7px;
                border-radius: 50%;
                background: #22c55e;
                box-shadow: 0 0 8px #22c55e;
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
    <body style="margin:0; padding:0; background:#0a0f1a;">
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
                {{ elementType: 'geometry', stylers: [{{ color: '#18181b' }}] }},
                {{ elementType: 'labels.text.stroke', stylers: [{{ color: '#09090b' }}] }},
                {{ elementType: 'labels.text.fill', stylers: [{{ color: '#a1a1aa' }}] }},
                {{ featureType: 'road', elementType: 'geometry', stylers: [{{ color: '#27272a' }}] }},
                {{ featureType: 'road.highway', elementType: 'geometry', stylers: [{{ color: '#3f3f46' }}] }},
                {{ featureType: 'water', elementType: 'geometry', stylers: [{{ color: '#09090b' }}] }},
                {{ featureType: 'poi', elementType: 'labels.text.fill', stylers: [{{ color: '#71717a' }}] }}
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
                        fillColor: '#22c55e',
                        fillOpacity: 1,
                        strokeColor: '#09090b',
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
                        fillColor: '#06b6d4', // Cyan
                        fillOpacity: 1,
                        strokeColor: '#083344',
                        strokeWeight: 3,
                    }},
                    title: "Charging Station (Base Dock)"
                }});

                // Source (Pickup) Circle Marker - Matches Mobile App
                sourceMarker = new google.maps.Marker({{
                    map: map,
                    icon: {{
                        path: google.maps.SymbolPath.CIRCLE,
                        scale: 8,
                        fillColor: '#ffffff',
                        fillOpacity: 1,
                        strokeColor: '#27272a',
                        strokeWeight: 3,
                    }},
                    title: "Pickup Location"
                }});

                // Destination (Dropoff) Amber Circle Marker - Matches Mobile App
                destMarker = new google.maps.Marker({{
                    map: map,
                    icon: {{
                        path: google.maps.SymbolPath.CIRCLE,
                        scale: 8,
                        fillColor: '#f59e0b',
                        fillOpacity: 1,
                        strokeColor: '#27272a',
                        strokeWeight: 3,
                    }},
                    title: "Dropoff Location"
                }});
                
                // Route Polyline - Dense Google Maps Path
                routePoly = new google.maps.Polyline({{
                    geodesic: true,
                    strokeColor: '#3b82f6',
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
