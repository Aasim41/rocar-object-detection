"""
Mission Telemetry & Route Cache Engine for AutoDrop Autonomous Cart.
Stores flight-recorder blackbox logs and persists verified Google Maps routes in a local SQLite database.
"""

import sqlite3
import json
import time
import os
import threading
from datetime import datetime
from typing import List, Dict, Optional, Tuple

DB_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "mission_telemetry.db")

class MissionTelemetryDB:
    def __init__(self, db_path: str = DB_PATH):
        self.db_path = db_path
        self._lock = threading.Lock()
        self._init_db()

    def _get_connection(self) -> sqlite3.Connection:
        conn = sqlite3.connect(self.db_path, timeout=10.0)
        conn.row_factory = sqlite3.Row
        return conn

    def _init_db(self):
        with self._lock:
            with self._get_connection() as conn:
                cursor = conn.cursor()
                
                # 1. Flight Recorder Blackbox Telemetry Table
                cursor.execute("""
                    CREATE TABLE IF NOT EXISTS telemetry_logs (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        timestamp DATETIME DEFAULT (datetime('now', 'localtime')),
                        delivery_id TEXT,
                        phase TEXT,
                        mode TEXT,
                        lat REAL,
                        lng REAL,
                        heading REAL,
                        speed REAL,
                        motor_cmd TEXT,
                        ultrasonic_cm INTEGER,
                        obstacle_detected INTEGER,
                        obstacle_name TEXT,
                        cte REAL,
                        steer_bias REAL
                    )
                """)
                cursor.execute("CREATE INDEX IF NOT EXISTS idx_telemetry_delivery ON telemetry_logs(delivery_id)")
                cursor.execute("CREATE INDEX IF NOT EXISTS idx_telemetry_time ON telemetry_logs(timestamp)")

                # 2. Persistent Route Cache for Repetitive Campus Addresses
                cursor.execute("""
                    CREATE TABLE IF NOT EXISTS route_cache (
                        cache_key TEXT PRIMARY KEY,
                        origin_lat REAL,
                        origin_lng REAL,
                        dest_lat REAL,
                        dest_lng REAL,
                        route_json TEXT,
                        waypoints_count INTEGER,
                        total_distance_m REAL,
                        hit_count INTEGER DEFAULT 1,
                        created_at DATETIME DEFAULT (datetime('now', 'localtime')),
                        last_accessed DATETIME DEFAULT (datetime('now', 'localtime'))
                    )
                """)

                # 3. Mission Summary Sessions
                cursor.execute("""
                    CREATE TABLE IF NOT EXISTS mission_summaries (
                        delivery_id TEXT PRIMARY KEY,
                        start_time DATETIME DEFAULT (datetime('now', 'localtime')),
                        end_time DATETIME,
                        start_lat REAL,
                        start_lng REAL,
                        end_lat REAL,
                        end_lng REAL,
                        total_waypoints INTEGER,
                        status TEXT,
                        obstacle_events INTEGER DEFAULT 0
                    )
                """)
                conn.commit()

    # ─── TELEMETRY LOGGING ──────────────────────────────────────

    def log_telemetry(
        self,
        delivery_id: str,
        phase: str,
        mode: str,
        lat: Optional[float] = None,
        lng: Optional[float] = None,
        heading: float = 0.0,
        speed: float = 0.0,
        motor_cmd: str = "stop",
        ultrasonic_cm: int = 999,
        obstacle_detected: bool = False,
        obstacle_name: Optional[str] = None,
        cte: float = 0.0,
        steer_bias: float = 0.0
    ):
        """Asynchronously record a flight log tick."""
        def _write():
            try:
                with self._lock:
                    with self._get_connection() as conn:
                        cursor = conn.cursor()
                        cursor.execute("""
                            INSERT INTO telemetry_logs (
                                delivery_id, phase, mode, lat, lng, heading, speed,
                                motor_cmd, ultrasonic_cm, obstacle_detected, obstacle_name, cte, steer_bias
                            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                        """, (
                            delivery_id, phase, mode, lat, lng, heading, speed,
                            motor_cmd, ultrasonic_cm, 1 if obstacle_detected else 0,
                            obstacle_name, cte, steer_bias
                        ))
                        conn.commit()
            except Exception as e:
                print(f"[TelemetryDB] Log error: {e}")

        # Spawn non-blocking thread so DB write never hitches the 30fps vision loop
        threading.Thread(target=_write, daemon=True).start()

    # ─── ROUTE CACHING ──────────────────────────────────────────

    @staticmethod
    def _make_cache_key(origin: Tuple[float, float], dest: Tuple[float, float]) -> str:
        """Round coordinates to 4 decimals (~11m grid resolution) to match repeat campus locations."""
        o_lat, o_lng = round(origin[0], 4), round(origin[1], 4)
        d_lat, d_lng = round(dest[0], 4), round(dest[1], 4)
        return f"{o_lat:.4f},{o_lng:.4f}->{d_lat:.4f},{d_lng:.4f}"

    def get_cached_route(self, origin: Tuple[float, float], dest: Tuple[float, float]) -> Optional[List[Dict[str, float]]]:
        """Look up verified Google Maps route from persistent cache."""
        key = self._make_cache_key(origin, dest)
        try:
            with self._lock:
                with self._get_connection() as conn:
                    cursor = conn.cursor()
                    cursor.execute("""
                        SELECT route_json, hit_count FROM route_cache WHERE cache_key = ?
                    """, (key,))
                    row = cursor.fetchone()
                    if row:
                        cursor.execute("""
                            UPDATE route_cache 
                            SET hit_count = hit_count + 1, last_accessed = datetime('now', 'localtime')
                            WHERE cache_key = ?
                        """, (key,))
                        conn.commit()
                        pts = json.loads(row["route_json"])
                        print(f"⚡ [RouteCache] Cache HIT for {key} (hits: {row['hit_count'] + 1})")
                        return pts
        except Exception as e:
            print(f"[RouteCache] Get error: {e}")
        return None

    def save_cached_route(
        self,
        origin: Tuple[float, float],
        dest: Tuple[float, float],
        route_points: List[Dict[str, float]],
        total_distance_m: float = 0.0
    ):
        """Save a newly calculated or received Google Maps route into persistent cache."""
        if not route_points or len(route_points) < 2:
            return

        key = self._make_cache_key(origin, dest)
        payload = json.dumps(route_points)
        count = len(route_points)

        def _save():
            try:
                with self._lock:
                    with self._get_connection() as conn:
                        cursor = conn.cursor()
                        cursor.execute("""
                            INSERT INTO route_cache (
                                cache_key, origin_lat, origin_lng, dest_lat, dest_lng,
                                route_json, waypoints_count, total_distance_m, hit_count
                            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, 1)
                            ON CONFLICT(cache_key) DO UPDATE SET
                                route_json = excluded.route_json,
                                waypoints_count = excluded.waypoints_count,
                                total_distance_m = excluded.total_distance_m,
                                last_accessed = datetime('now', 'localtime')
                        """, (key, origin[0], origin[1], dest[0], dest[1], payload, count, total_distance_m))
                        conn.commit()
                print(f"💾 [RouteCache] Saved route for {key} ({count} waypoints)")
            except Exception as e:
                print(f"[RouteCache] Save error: {e}")

        threading.Thread(target=_save, daemon=True).start()

    # ─── STATS & QUERY HELPERS ─────────────────────────────────

    def get_stats(self) -> Dict:
        """Fetch summary statistics for dashboard display."""
        try:
            with self._lock:
                with self._get_connection() as conn:
                    cursor = conn.cursor()
                    cursor.execute("SELECT COUNT(*) as total_logs FROM telemetry_logs")
                    total_logs = cursor.fetchone()["total_logs"]

                    cursor.execute("SELECT COUNT(*) as cached_routes, SUM(hit_count) as total_hits FROM route_cache")
                    r_row = cursor.fetchone()
                    cached_routes = r_row["cached_routes"] or 0
                    total_hits = r_row["total_hits"] or 0

                    cursor.execute("SELECT * FROM telemetry_logs ORDER BY id DESC LIMIT 10")
                    recent_logs = [dict(row) for row in cursor.fetchall()]

                    return {
                        "total_logs": total_logs,
                        "cached_routes": cached_routes,
                        "cache_hits": total_hits,
                        "recent_logs": recent_logs
                    }
        except Exception as e:
            return {"total_logs": 0, "cached_routes": 0, "cache_hits": 0, "recent_logs": [], "error": str(e)}

# Global Singleton Instance
telemetry_db = MissionTelemetryDB()
