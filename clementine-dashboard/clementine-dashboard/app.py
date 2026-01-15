"""
Clementine DAQ Dashboard - Flask Backend (v2)
Highlander Space Program

Production-style DAQ dashboard with:
- WebSocket for real-time bidirectional communication
- Simulated TCP sensor/control board connections
- InfluxDB integration (mock, with clear extension points)
- Protected actuation controls
- Comprehensive debugging features

This is a SIMULATION ONLY - no real hardware control is implemented.
"""

import json
import math
import random
import threading
import time
import hashlib
import queue
from collections import deque
from dataclasses import dataclass, asdict, field
from datetime import datetime
from enum import Enum
from typing import Dict, List, Optional, Any
from flask import Flask, Response, jsonify, render_template, request, session
from flask_socketio import SocketIO, emit

app = Flask(__name__)
app.secret_key = 'clementine-gse-2024-hsp'  # Change in production!
socketio = SocketIO(app, cors_allowed_origins="*", async_mode='threading')

# =============================================================================
# CONFIGURATION
# =============================================================================

class Config:
    # Controls page PIN (in production, use proper auth)
    CONTROLS_PIN = "1234"
    CONTROLS_PIN_HASH = hashlib.sha256(CONTROLS_PIN.encode()).hexdigest()
    
    # Telemetry rates
    SENSOR_SAMPLE_RATE_HZ = 20
    WEBSOCKET_BROADCAST_RATE_HZ = 20
    HEARTBEAT_INTERVAL_S = 1.0
    HEARTBEAT_TIMEOUT_S = 3.0
    
    # Simulated board IPs (for display purposes)
    SENSOR_BOARDS = {
        "sensor_board_1": {"ip": "192.168.1.101", "port": 5001, "channels": ["pt_1", "pt_2", "pt_3", "tc_1", "tc_2"]},
        "sensor_board_2": {"ip": "192.168.1.102", "port": 5002, "channels": ["lc_1", "lc_2", "flow_1"]},
        "sensor_board_3": {"ip": "192.168.1.103", "port": 5003, "channels": ["imu_acc", "imu_gyro", "altitude"]},
    }
    
    CONTROL_BOARDS = {
        "control_board_1": {"ip": "192.168.1.201", "port": 5101, "actuators": ["solenoid_1", "solenoid_2", "solenoid_3"]},
        "control_board_2": {"ip": "192.168.1.202", "port": 5102, "actuators": ["valve_main_lox", "valve_main_fuel", "igniter"]},
        "control_board_3": {"ip": "192.168.1.203", "port": 5103, "actuators": ["tvc_pitch", "tvc_yaw"]},
    }

# =============================================================================
# SYSTEM STATE
# =============================================================================

class SystemState(Enum):
    SAFE = "SAFE"
    ARMED = "ARMED"
    PRESSURIZED = "PRESSURIZED"
    COUNTDOWN = "COUNTDOWN"
    FIRING = "FIRING"
    FAULT = "FAULT"

class AlarmSeverity(Enum):
    INFO = "INFO"
    WARN = "WARN"
    FAULT = "FAULT"

class ConnectionState(Enum):
    CONNECTED = "CONNECTED"
    DEGRADED = "DEGRADED"
    DISCONNECTED = "DISCONNECTED"
    TIMEOUT = "TIMEOUT"

@dataclass
class BoardStatus:
    board_id: str
    board_type: str
    ip: str
    port: int
    state: str = ConnectionState.DISCONNECTED.value
    last_heartbeat: float = 0
    last_packet_time: float = 0
    packets_received: int = 0
    packets_sent: int = 0
    errors: int = 0
    latency_ms: float = 0
    latency_history: List[float] = field(default_factory=list)

@dataclass
class Alarm:
    id: str
    severity: str
    message: str
    channel: str
    value: float
    threshold: float
    timestamp: str
    acknowledged: bool = False

@dataclass
class CommandLog:
    id: str
    timestamp: str
    actuator_id: str
    command: str
    state_requested: str
    operator_session: str
    validation_result: str
    tcp_sent: bool
    tcp_packet: dict
    ack_received: bool
    ack_packet: dict
    ack_timestamp: str
    latency_ms: float
    influx_logged: bool

# =============================================================================
# GLOBAL STATE
# =============================================================================

system_state = {
    "state": SystemState.SAFE.value,
    "armed": False,
    "pressurized": False,
    "countdown_active": False,
    "connection": "Sim Connected",
    "fault_acknowledged": False,
    "controls_unlocked": False,
}

board_statuses: Dict[str, BoardStatus] = {}
board_lock = threading.Lock()

for board_id, info in Config.SENSOR_BOARDS.items():
    board_statuses[board_id] = BoardStatus(
        board_id=board_id, board_type="sensor", ip=info["ip"], port=info["port"],
        state=ConnectionState.CONNECTED.value, last_heartbeat=time.time()
    )

for board_id, info in Config.CONTROL_BOARDS.items():
    board_statuses[board_id] = BoardStatus(
        board_id=board_id, board_type="control", ip=info["ip"], port=info["port"],
        state=ConnectionState.CONNECTED.value, last_heartbeat=time.time()
    )

actuator_states = {
    "solenoid_1": {"state": "closed", "last_change": None},
    "solenoid_2": {"state": "closed", "last_change": None},
    "solenoid_3": {"state": "closed", "last_change": None},
    "valve_main_lox": {"state": "closed", "last_change": None},
    "valve_main_fuel": {"state": "closed", "last_change": None},
    "igniter": {"state": "off", "last_change": None},
    "tvc_pitch": {"state": 0.0, "last_change": None},
    "tvc_yaw": {"state": 0.0, "last_change": None},
}
actuator_lock = threading.Lock()

ALARM_THRESHOLDS = {
    "pt_1": {"warn": 850, "fault": 950, "label": "Chamber Pressure"},
    "pt_2": {"warn": 520, "fault": 580, "label": "LOX Line Pressure"},
    "pt_3": {"warn": 480, "fault": 550, "label": "Fuel Line Pressure"},
    "lc_1": {"warn": 22000, "fault": 25000, "label": "Thrust"},
}

CHANNEL_DEFS = {
    "pt_1": {"unit": "psi", "min": 0, "max": 1000, "label": "Chamber Pressure (Pc)", "board": "sensor_board_1"},
    "pt_2": {"unit": "psi", "min": 0, "max": 600, "label": "LOX Line Pressure", "board": "sensor_board_1"},
    "pt_3": {"unit": "psi", "min": 0, "max": 600, "label": "Fuel Line Pressure", "board": "sensor_board_1"},
    "tc_1": {"unit": "°C", "min": -200, "max": 500, "label": "LOX Tank Temp", "board": "sensor_board_1"},
    "tc_2": {"unit": "°C", "min": -50, "max": 500, "label": "Chamber Temp", "board": "sensor_board_1"},
    "lc_1": {"unit": "lbf", "min": 0, "max": 30000, "label": "Thrust", "board": "sensor_board_2"},
    "lc_2": {"unit": "lbf", "min": 0, "max": 5000, "label": "Tank Weight", "board": "sensor_board_2"},
    "flow_1": {"unit": "kg/s", "min": 0, "max": 50, "label": "LOX Flow Rate", "board": "sensor_board_2"},
    "imu_acc": {"unit": "g", "min": -20, "max": 20, "label": "Acceleration", "board": "sensor_board_3"},
    "imu_gyro": {"unit": "°/s", "min": -180, "max": 180, "label": "Angular Rate", "board": "sensor_board_3"},
    "altitude": {"unit": "m", "min": 0, "max": 50000, "label": "Altitude", "board": "sensor_board_3"},
}

active_alarms = {}
alarm_lock = threading.Lock()
logs = deque(maxlen=2000)
logs_lock = threading.Lock()
command_history = deque(maxlen=500)
command_lock = threading.Lock()
raw_packet_buffer = deque(maxlen=100)
packet_buffer_lock = threading.Lock()

debug_metrics = {
    "websocket_clients": 0,
    "packets_per_second": 0,
    "influx_writes_per_second": 0,
    "influx_queue_size": 0,
    "command_queue_size": 0,
    "uptime_seconds": 0,
    "start_time": time.time(),
}

influx_queue = queue.Queue(maxsize=10000)

# =============================================================================
# LOGGING HELPERS
# =============================================================================

def add_log(log_type: str, message: str, details: dict = None):
    with logs_lock:
        entry = {
            "timestamp": datetime.now().isoformat(),
            "type": log_type,
            "message": message,
            "details": details or {}
        }
        logs.append(entry)
        socketio.emit('log_entry', entry)

def add_raw_packet(direction: str, board_id: str, packet: dict, latency_ms: float = 0):
    with packet_buffer_lock:
        entry = {
            "timestamp": datetime.now().isoformat(),
            "direction": direction,
            "board_id": board_id,
            "packet": packet,
            "latency_ms": latency_ms,
            "size_bytes": len(json.dumps(packet))
        }
        raw_packet_buffer.append(entry)

def add_command_log(cmd_log: CommandLog):
    with command_lock:
        command_history.append(asdict(cmd_log))

# =============================================================================
# SIMULATED TCP BOARD COMMUNICATION
# =============================================================================

class SimulatedTCPBoards:
    def __init__(self):
        self.start_time = time.time()
        self._running = True
        self._sensor_thread = None
        self._heartbeat_thread = None
        
    def start(self):
        self._sensor_thread = threading.Thread(target=self._sensor_loop, daemon=True)
        self._sensor_thread.start()
        self._heartbeat_thread = threading.Thread(target=self._heartbeat_loop, daemon=True)
        self._heartbeat_thread.start()
        add_log("system", "TCP board simulation started", {
            "sensor_boards": list(Config.SENSOR_BOARDS.keys()),
            "control_boards": list(Config.CONTROL_BOARDS.keys())
        })
    
    def stop(self):
        self._running = False
    
    def _get_time_offset(self):
        return time.time() - self.start_time
    
    def _simulate_sensor_value(self, channel: str) -> float:
        t = self._get_time_offset()
        
        if channel == "pt_1":
            base = 750 + 50 * math.sin(t * 0.3) + 30 * math.sin(t * 1.2)
            return max(0, base + random.gauss(0, 8))
        elif channel == "pt_2":
            base = 450 + 25 * math.sin(t * 0.25 + 1) + 15 * math.sin(t * 0.8)
            return max(0, base + random.gauss(0, 5))
        elif channel == "pt_3":
            base = 420 + 20 * math.sin(t * 0.28 + 2) + 12 * math.sin(t * 0.9)
            return max(0, base + random.gauss(0, 4))
        elif channel == "tc_1":
            return -180 + 5 * math.sin(t * 0.1) + random.gauss(0, 1)
        elif channel == "tc_2":
            return 200 + 50 * math.sin(t * 0.2) + random.gauss(0, 5)
        elif channel == "lc_1":
            base = 18000 + 1500 * math.sin(t * 0.2) + 800 * math.sin(t * 0.7)
            return max(0, base + random.gauss(0, 200))
        elif channel == "lc_2":
            base = 2000 - (t % 300) * 3
            return max(500, base + random.gauss(0, 10))
        elif channel == "flow_1":
            base = 15 + 2 * math.sin(t * 0.4)
            return max(0, base + random.gauss(0, 0.5))
        elif channel == "imu_acc":
            return 1 + 0.5 * math.sin(t * 0.5) + random.gauss(0, 0.1)
        elif channel == "imu_gyro":
            with actuator_lock:
                tvc_influence = actuator_states["tvc_pitch"]["state"] * 0.5
            return 2 * math.sin(t * 0.3) + tvc_influence + random.gauss(0, 0.3)
        elif channel == "altitude":
            phase = (t % 120) / 120
            if phase < 0.7:
                alt = 1000 + 15000 * (phase / 0.7) ** 0.8
            else:
                descent_phase = (phase - 0.7) / 0.3
                alt = 16000 * (1 - descent_phase ** 1.5)
            return max(0, alt + random.gauss(0, 20))
        return random.gauss(0, 1)
    
    def _sensor_loop(self):
        packet_count = 0
        last_rate_check = time.time()
        
        while self._running:
            loop_start = time.time()
            
            for board_id, board_info in Config.SENSOR_BOARDS.items():
                latency_ms = random.uniform(0.5, 5.0)
                
                packet = {
                    "device_id": board_id,
                    "timestamp": time.time(),
                    "sequence": packet_count,
                    "channels": {}
                }
                
                for channel in board_info["channels"]:
                    if channel in CHANNEL_DEFS:
                        packet["channels"][channel] = round(self._simulate_sensor_value(channel), 4)
                
                with board_lock:
                    status = board_statuses[board_id]
                    status.last_packet_time = time.time()
                    status.packets_received += 1
                    status.latency_ms = latency_ms
                    status.latency_history.append(latency_ms)
                    if len(status.latency_history) > 100:
                        status.latency_history.pop(0)
                
                add_raw_packet("rx", board_id, packet, latency_ms)
                
                try:
                    influx_queue.put_nowait({
                        "measurement": "sensor_data",
                        "tags": {"board": board_id},
                        "fields": packet["channels"],
                        "time": packet["timestamp"]
                    })
                except queue.Full:
                    pass
                
                self._check_alarms(packet["channels"])
                
                socketio.emit('sensor_data', {
                    "board_id": board_id,
                    "timestamp": packet["timestamp"],
                    "channels": packet["channels"],
                    "latency_ms": latency_ms
                })
                
                packet_count += 1
            
            now = time.time()
            if now - last_rate_check >= 1.0:
                debug_metrics["packets_per_second"] = packet_count / (now - last_rate_check)
                packet_count = 0
                last_rate_check = now
                debug_metrics["uptime_seconds"] = int(now - debug_metrics["start_time"])
                debug_metrics["influx_queue_size"] = influx_queue.qsize()
            
            elapsed = time.time() - loop_start
            sleep_time = max(0, (1.0 / Config.SENSOR_SAMPLE_RATE_HZ) - elapsed)
            time.sleep(sleep_time)
    
    def _heartbeat_loop(self):
        while self._running:
            now = time.time()
            
            with board_lock:
                for board_id, status in board_statuses.items():
                    if random.random() < 0.001:
                        status.state = ConnectionState.DEGRADED.value
                        status.errors += 1
                        add_log("system", f"Board {board_id} connection degraded", {
                            "board_id": board_id, "errors": status.errors
                        })
                    elif status.state == ConnectionState.DEGRADED.value and random.random() < 0.3:
                        status.state = ConnectionState.CONNECTED.value
                    
                    status.last_heartbeat = now
                    
                    if now - status.last_packet_time > Config.HEARTBEAT_TIMEOUT_S:
                        if status.state != ConnectionState.TIMEOUT.value:
                            status.state = ConnectionState.TIMEOUT.value
                            add_log("alarm", f"Board {board_id} TIMEOUT", {"board_id": board_id})
            
            socketio.emit('board_status', self.get_all_board_status())
            time.sleep(Config.HEARTBEAT_INTERVAL_S)
    
    def _check_alarms(self, channels: dict):
        global system_state
        timestamp = datetime.now().isoformat()
        has_fault = False
        
        with alarm_lock:
            for channel, thresholds in ALARM_THRESHOLDS.items():
                if channel not in channels:
                    continue
                
                value = channels[channel]
                alarm_id = f"alarm_{channel}"
                
                if value > thresholds["fault"]:
                    has_fault = True
                    if alarm_id not in active_alarms or active_alarms[alarm_id].severity != AlarmSeverity.FAULT.value:
                        alarm = Alarm(
                            id=alarm_id, severity=AlarmSeverity.FAULT.value,
                            message=f"{thresholds['label']} FAULT: {value:.1f} > {thresholds['fault']}",
                            channel=channel, value=value, threshold=thresholds["fault"], timestamp=timestamp
                        )
                        active_alarms[alarm_id] = alarm
                        add_log("alarm", f"FAULT: {alarm.message}", {"alarm": asdict(alarm)})
                        socketio.emit('alarm', asdict(alarm))
                
                elif value > thresholds["warn"]:
                    if alarm_id not in active_alarms:
                        alarm = Alarm(
                            id=alarm_id, severity=AlarmSeverity.WARN.value,
                            message=f"{thresholds['label']} WARNING: {value:.1f} > {thresholds['warn']}",
                            channel=channel, value=value, threshold=thresholds["warn"], timestamp=timestamp
                        )
                        active_alarms[alarm_id] = alarm
                        add_log("alarm", f"WARNING: {alarm.message}", {"alarm": asdict(alarm)})
                        socketio.emit('alarm', asdict(alarm))
                
                elif alarm_id in active_alarms:
                    cleared = active_alarms.pop(alarm_id)
                    add_log("alarm", f"CLEARED: {cleared.message}", {})
                    socketio.emit('alarm_cleared', {"id": alarm_id})
            
            if has_fault and not system_state["fault_acknowledged"]:
                if system_state["state"] != SystemState.FAULT.value:
                    system_state["state"] = SystemState.FAULT.value
                    system_state["armed"] = False
                    add_log("system", "System entered FAULT state", {})
                    socketio.emit('system_state', system_state)
    
    def send_actuator_command(self, board_id: str, actuator_id: str, command: str, state: Any) -> dict:
        send_time = time.time()
        
        cmd_packet = {
            "cmd": "set_state",
            "actuator_id": actuator_id,
            "state": state,
            "timestamp": send_time
        }
        
        latency_ms = random.uniform(2, 15)
        time.sleep(latency_ms / 1000)
        
        with board_lock:
            if board_id in board_statuses:
                board_statuses[board_id].packets_sent += 1
        
        add_raw_packet("tx", board_id, cmd_packet, 0)
        
        success = random.random() < 0.95
        
        if success:
            with actuator_lock:
                if actuator_id in actuator_states:
                    actuator_states[actuator_id]["state"] = state
                    actuator_states[actuator_id]["last_change"] = datetime.now().isoformat()
            
            ack_packet = {
                "ack": True,
                "actuator_id": actuator_id,
                "state": state,
                "hw_timestamp": time.time()
            }
        else:
            ack_packet = {
                "ack": False,
                "actuator_id": actuator_id,
                "error": "NACK: Hardware timeout",
                "hw_timestamp": time.time()
            }
            with board_lock:
                if board_id in board_statuses:
                    board_statuses[board_id].errors += 1
        
        add_raw_packet("rx", board_id, ack_packet, latency_ms)
        
        return {
            "success": success,
            "cmd_packet": cmd_packet,
            "ack_packet": ack_packet,
            "latency_ms": latency_ms
        }
    
    def get_all_board_status(self) -> dict:
        with board_lock:
            return {
                board_id: {
                    "board_id": status.board_id,
                    "board_type": status.board_type,
                    "ip": status.ip,
                    "port": status.port,
                    "state": status.state,
                    "last_heartbeat": status.last_heartbeat,
                    "packets_received": status.packets_received,
                    "packets_sent": status.packets_sent,
                    "errors": status.errors,
                    "latency_ms": round(status.latency_ms, 2),
                    "avg_latency_ms": round(sum(status.latency_history) / len(status.latency_history), 2) if status.latency_history else 0
                }
                for board_id, status in board_statuses.items()
            }

tcp_boards = SimulatedTCPBoards()

# =============================================================================
# COMMAND VALIDATION & EXECUTION
# =============================================================================

def validate_actuator_command(actuator_id: str, command: str, state: Any, session_id: str) -> dict:
    errors = []
    warnings = []
    
    if actuator_id not in actuator_states:
        errors.append(f"Unknown actuator: {actuator_id}")
        return {"valid": False, "errors": errors, "warnings": warnings}
    
    if system_state["state"] == SystemState.FAULT.value:
        errors.append("Cannot actuate: System in FAULT state")
    
    if not system_state["armed"] and actuator_id not in ["tvc_pitch", "tvc_yaw"]:
        errors.append("Cannot actuate: System not ARMED")
    
    board_id = None
    for bid, info in Config.CONTROL_BOARDS.items():
        if actuator_id in info["actuators"]:
            board_id = bid
            break
    
    if board_id:
        with board_lock:
            if board_id in board_statuses:
                status = board_statuses[board_id]
                if status.state == ConnectionState.DISCONNECTED.value:
                    errors.append(f"Cannot actuate: Board {board_id} disconnected")
                elif status.state == ConnectionState.TIMEOUT.value:
                    errors.append(f"Cannot actuate: Board {board_id} timeout")
                elif status.state == ConnectionState.DEGRADED.value:
                    warnings.append(f"Board {board_id} connection degraded")
    
    if actuator_id in ["valve_main_lox", "valve_main_fuel"] and state == "open":
        if not system_state["armed"]:
            errors.append("Cannot open main valves: System not ARMED")
    
    with actuator_lock:
        last_change = actuator_states[actuator_id].get("last_change")
        if last_change:
            try:
                last_time = datetime.fromisoformat(last_change)
                cooldown_s = 0.5
                if (datetime.now() - last_time).total_seconds() < cooldown_s:
                    warnings.append(f"Command within cooldown period ({cooldown_s}s)")
            except:
                pass
    
    return {"valid": len(errors) == 0, "errors": errors, "warnings": warnings, "board_id": board_id}

def execute_actuator_command(actuator_id: str, command: str, state: Any, session_id: str) -> dict:
    cmd_id = f"cmd_{int(time.time() * 1000)}"
    timestamp = datetime.now().isoformat()
    
    validation = validate_actuator_command(actuator_id, command, state, session_id)
    
    cmd_log = CommandLog(
        id=cmd_id, timestamp=timestamp, actuator_id=actuator_id, command=command,
        state_requested=str(state), operator_session=session_id,
        validation_result="PASS" if validation["valid"] else "FAIL: " + ", ".join(validation["errors"]),
        tcp_sent=False, tcp_packet={}, ack_received=False, ack_packet={},
        ack_timestamp="", latency_ms=0, influx_logged=False
    )
    
    if not validation["valid"]:
        add_command_log(cmd_log)
        add_log("command", f"REJECTED: {actuator_id} {command} {state}", {
            "cmd_id": cmd_id, "errors": validation["errors"]
        })
        return {
            "success": False, "cmd_id": cmd_id,
            "errors": validation["errors"], "warnings": validation.get("warnings", [])
        }
    
    board_id = validation["board_id"]
    result = tcp_boards.send_actuator_command(board_id, actuator_id, command, state)
    
    cmd_log.tcp_sent = True
    cmd_log.tcp_packet = result["cmd_packet"]
    cmd_log.ack_received = result["success"]
    cmd_log.ack_packet = result["ack_packet"]
    cmd_log.ack_timestamp = datetime.now().isoformat()
    cmd_log.latency_ms = result["latency_ms"]
    cmd_log.influx_logged = True
    
    add_command_log(cmd_log)
    
    if result["success"]:
        add_log("command", f"EXECUTED: {actuator_id} → {state}", {
            "cmd_id": cmd_id, "latency_ms": result["latency_ms"]
        })
    else:
        add_log("command", f"FAILED: {actuator_id} {command} - {result['ack_packet'].get('error', 'Unknown')}", {
            "cmd_id": cmd_id
        })
    
    with actuator_lock:
        socketio.emit('actuator_state', {
            "actuator_id": actuator_id,
            "state": actuator_states[actuator_id]["state"],
            "last_change": actuator_states[actuator_id]["last_change"]
        })
    
    return {
        "success": result["success"], "cmd_id": cmd_id,
        "ack": result["ack_packet"], "latency_ms": result["latency_ms"],
        "warnings": validation.get("warnings", [])
    }

# =============================================================================
# FLASK ROUTES
# =============================================================================

@app.route("/")
def index():
    return render_template("index.html", channel_defs=CHANNEL_DEFS)

@app.route("/api/state")
def get_state():
    with alarm_lock:
        alarms = [asdict(a) for a in active_alarms.values()]
    with actuator_lock:
        actuators = dict(actuator_states)
    
    return jsonify({
        "system_state": system_state,
        "active_alarms": alarms,
        "actuator_states": actuators,
        "board_status": tcp_boards.get_all_board_status(),
        "debug_metrics": debug_metrics
    })

@app.route("/api/boards")
def get_boards():
    return jsonify(tcp_boards.get_all_board_status())

@app.route("/api/channel_defs")
def get_channel_defs():
    return jsonify(CHANNEL_DEFS)

@app.route("/api/controls/auth", methods=["POST"])
def controls_auth():
    data = request.get_json() or {}
    pin = data.get("pin", "")
    pin_hash = hashlib.sha256(pin.encode()).hexdigest()
    
    if pin_hash == Config.CONTROLS_PIN_HASH:
        session["controls_unlocked"] = True
        session["controls_unlock_time"] = time.time()
        add_log("system", "Controls page unlocked", {"session": request.remote_addr})
        return jsonify({"success": True, "message": "Controls unlocked"})
    else:
        add_log("system", "Controls auth failed", {"session": request.remote_addr})
        return jsonify({"success": False, "message": "Invalid PIN"}), 401

@app.route("/api/controls/lock", methods=["POST"])
def controls_lock():
    session.pop("controls_unlocked", None)
    add_log("system", "Controls page locked", {"session": request.remote_addr})
    return jsonify({"success": True})

@app.route("/api/controls/status")
def controls_status():
    unlocked = session.get("controls_unlocked", False)
    return jsonify({"unlocked": unlocked})

@app.route("/api/control/arm", methods=["POST"])
def control_arm():
    if not session.get("controls_unlocked"):
        return jsonify({"success": False, "message": "Controls locked"}), 403
    
    data = request.get_json() or {}
    arm = data.get("arm", False)
    
    if arm and system_state["state"] == SystemState.FAULT.value:
        add_log("command", "ARM REJECTED: System in FAULT", {})
        return jsonify({"success": False, "message": "Cannot arm: System in FAULT state"}), 400
    
    system_state["armed"] = arm
    system_state["state"] = SystemState.ARMED.value if arm else SystemState.SAFE.value
    
    action = "ARMED" if arm else "DISARMED"
    add_log("command", f"System {action}", {"operator": request.remote_addr})
    socketio.emit('system_state', system_state)
    
    return jsonify({"success": True, "message": f"System {action}", "state": system_state})

@app.route("/api/control/actuate", methods=["POST"])
def control_actuate():
    if not session.get("controls_unlocked"):
        return jsonify({"success": False, "message": "Controls locked"}), 403
    
    data = request.get_json() or {}
    actuator_id = data.get("actuator_id", "")
    command = data.get("command", "set_state")
    state = data.get("state", "")
    
    result = execute_actuator_command(
        actuator_id=actuator_id, command=command,
        state=state, session_id=request.remote_addr
    )
    
    if result["success"]:
        return jsonify(result)
    else:
        return jsonify(result), 400

@app.route("/api/control/estop", methods=["POST"])
def control_estop():
    global system_state
    
    system_state["armed"] = False
    system_state["state"] = SystemState.SAFE.value
    system_state["pressurized"] = False
    
    with actuator_lock:
        for act_id, act_state in actuator_states.items():
            if act_id.startswith("solenoid") or act_id.startswith("valve"):
                act_state["state"] = "closed"
            elif act_id == "igniter":
                act_state["state"] = "off"
            elif act_id.startswith("tvc"):
                act_state["state"] = 0.0
            act_state["last_change"] = datetime.now().isoformat()
    
    add_log("command", "*** E-STOP ACTIVATED ***", {"operator": request.remote_addr})
    socketio.emit('system_state', system_state)
    socketio.emit('estop', {"timestamp": datetime.now().isoformat()})
    
    return jsonify({"success": True, "message": "E-STOP ACTIVATED", "state": system_state})

@app.route("/api/control/acknowledge", methods=["POST"])
def acknowledge_faults():
    system_state["fault_acknowledged"] = True
    
    with alarm_lock:
        has_fault = any(a.severity == AlarmSeverity.FAULT.value for a in active_alarms.values())
    
    if not has_fault:
        system_state["state"] = SystemState.SAFE.value
        system_state["fault_acknowledged"] = False
    
    add_log("command", "Faults acknowledged", {})
    socketio.emit('system_state', system_state)
    
    return jsonify({"success": True, "state": system_state})

@app.route("/api/logs")
def get_logs():
    log_type = request.args.get("type", None)
    limit = min(int(request.args.get("limit", 100)), 2000)
    
    with logs_lock:
        if log_type:
            filtered = [l for l in logs if l["type"] == log_type]
        else:
            filtered = list(logs)
    
    return jsonify({"logs": list(reversed(filtered[-limit:])), "total": len(filtered)})

@app.route("/api/logs/download")
def download_logs():
    with logs_lock:
        log_data = list(logs)
    
    return Response(
        json.dumps(log_data, indent=2),
        mimetype="application/json",
        headers={"Content-Disposition": f"attachment; filename=clementine_logs_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"}
    )

@app.route("/api/commands")
def get_commands():
    limit = min(int(request.args.get("limit", 50)), 500)
    with command_lock:
        cmds = list(command_history)
    return jsonify({"commands": list(reversed(cmds[-limit:])), "total": len(cmds)})

@app.route("/api/debug/packets")
def get_raw_packets():
    with packet_buffer_lock:
        packets = list(raw_packet_buffer)
    return jsonify({"packets": list(reversed(packets)), "total": len(packets)})

@app.route("/api/debug/metrics")
def get_debug_metrics():
    debug_metrics["influx_queue_size"] = influx_queue.qsize()
    return jsonify(debug_metrics)

# =============================================================================
# WEBSOCKET EVENTS
# =============================================================================

@socketio.on('connect')
def handle_connect():
    debug_metrics["websocket_clients"] += 1
    emit('system_state', system_state)
    emit('board_status', tcp_boards.get_all_board_status())
    with actuator_lock:
        emit('actuator_states', dict(actuator_states))

@socketio.on('disconnect')
def handle_disconnect():
    debug_metrics["websocket_clients"] = max(0, debug_metrics["websocket_clients"] - 1)

@socketio.on('request_state')
def handle_request_state():
    emit('system_state', system_state)
    emit('board_status', tcp_boards.get_all_board_status())
    with actuator_lock:
        emit('actuator_states', dict(actuator_states))
    with alarm_lock:
        emit('alarms', [asdict(a) for a in active_alarms.values()])

# =============================================================================
# MAIN
# =============================================================================

if __name__ == "__main__":
    add_log("system", "Dashboard server starting", {"version": "2.0.0"})
    
    print("\n" + "=" * 60)
    print("  CLEMENTINE DAQ DASHBOARD v2.0")
    print("  Highlander Space Program")
    print("=" * 60)
    print(f"\n  Controls PIN: {Config.CONTROLS_PIN}")
    print("  Server starting at http://localhost:5000")
    print("  Press Ctrl+C to stop\n")
    
    tcp_boards.start()
    socketio.run(app, debug=True, host="0.0.0.0", port=5000, allow_unsafe_werkzeug=True)
