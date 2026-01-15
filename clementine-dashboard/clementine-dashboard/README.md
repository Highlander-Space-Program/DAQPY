# Clementine DAQ Dashboard v2

**Highlander Space Program | Ground Support Equipment**

A production-style web dashboard for liquid bi-propellant rocket test stand data acquisition and control. This implementation demonstrates the complete TCP-based architecture for communicating with custom sensor boards and control boards.

> ⚠️ **SIMULATION ONLY** - This is a demonstration system. No real hardware control is implemented.

## Architecture Overview

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                           SENSOR DATA PATH                                   │
│                                                                              │
│  ┌──────────────┐    TCP     ┌──────────────┐  WebSocket   ┌─────────────┐ │
│  │ Sensor Board │ ────────▶ │   Backend    │ ──────────▶ │  Dashboard  │ │
│  │   (TCP Srv)  │           │  (TCP Client) │              │  (Browser)  │ │
│  └──────────────┘           └──────┬───────┘              └─────────────┘ │
│                                    │                                       │
│                                    ▼                                       │
│                             ┌──────────────┐                               │
│                             │   InfluxDB   │                               │
│                             │ (Batch Write)│                               │
│                             └──────────────┘                               │
└─────────────────────────────────────────────────────────────────────────────┘

┌─────────────────────────────────────────────────────────────────────────────┐
│                          ACTUATION PATH                                      │
│                                                                              │
│  ┌─────────────┐  HTTP POST  ┌──────────────┐    TCP     ┌───────────────┐ │
│  │  Dashboard  │ ──────────▶ │   Backend    │ ────────▶ │ Control Board │ │
│  │  (Browser)  │             │  (Validates) │            │   (TCP Srv)   │ │
│  └─────────────┘             └──────────────┘            └───────┬───────┘ │
│        ▲                            │                            │         │
│        │         WebSocket          │         TCP ACK            │         │
│        └────────────────────────────┴────────────────────────────┘         │
└─────────────────────────────────────────────────────────────────────────────┘
```

## Features

### Dashboard Pages

1. **Overview** - System health, key metrics, active alarms, board connection status
2. **Telemetry** - Real-time charts for all sensor channels with configurable time windows
3. **Controls** (PIN Protected) - Solenoid/valve actuation, TVC servo control, E-STOP
4. **TVC** - 3D rocket visualization with attitude data
5. **Debug** - TCP board connections, raw packet inspector, latency monitor, command history
6. **Logs** - Filterable system logs with download capability

### Key Capabilities

- **WebSocket Communication** - Bidirectional real-time data flow
- **Simulated TCP Boards** - 3 sensor boards, 3 control boards with realistic behavior
- **PIN-Protected Controls** - Actuation page requires authentication
- **Safety Validation** - Backend enforces state checks, cooldowns, connection health
- **Full Command Tracing** - Every actuation logged with validation result, TCP packet, ACK, latency
- **Raw Packet Inspection** - View incoming/outgoing TCP packet contents for debugging
- **Board Health Monitoring** - Connection state, packet counts, latency statistics

## Quick Start

```bash
# Clone or extract the project
cd clementine-dashboard

# Create virtual environment
python -m venv venv
source venv/bin/activate  # Linux/macOS
# or: venv\Scripts\activate  # Windows

# Install dependencies
pip install -r requirements.txt

# Run the server
python app.py
```

Open http://localhost:5000 in your browser.

**Controls PIN:** `1234` (configurable in `app.py`)

## TCP Message Formats

### Sensor Packet (Sensor Board → Backend)

```json
{
  "device_id": "sensor_board_1",
  "timestamp": 1718734928.032,
  "sequence": 12345,
  "channels": {
    "pt_1": 750.5,
    "pt_2": 450.2,
    "tc_1": -180.3
  }
}
```

### Actuation Command (Backend → Control Board)

```json
{
  "cmd": "set_state",
  "actuator_id": "solenoid_3",
  "state": "open",
  "timestamp": 1718734928.100
}
```

### Acknowledgment (Control Board → Backend)

```json
{
  "ack": true,
  "actuator_id": "solenoid_3",
  "state": "open",
  "hw_timestamp": 1718734928.112
}
```

### Dashboard Command (Dashboard → Backend)

```json
{
  "actuator_id": "solenoid_3",
  "command": "set_state",
  "state": "open"
}
```

## Simulated Board Configuration

### Sensor Boards

| Board ID | IP Address | Port | Channels |
|----------|------------|------|----------|
| sensor_board_1 | 192.168.1.101 | 5001 | pt_1, pt_2, pt_3, tc_1, tc_2 |
| sensor_board_2 | 192.168.1.102 | 5002 | lc_1, lc_2, flow_1 |
| sensor_board_3 | 192.168.1.103 | 5003 | imu_acc, imu_gyro, altitude |

### Control Boards

| Board ID | IP Address | Port | Actuators |
|----------|------------|------|-----------|
| control_board_1 | 192.168.1.201 | 5101 | solenoid_1, solenoid_2, solenoid_3 |
| control_board_2 | 192.168.1.202 | 5102 | valve_main_lox, valve_main_fuel, igniter |
| control_board_3 | 192.168.1.203 | 5103 | tvc_pitch, tvc_yaw |

## API Endpoints

### State & Telemetry

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/api/state` | GET | Complete system state |
| `/api/boards` | GET | All board connection status |
| `/api/channel_defs` | GET | Channel definitions and units |

### Controls (Requires Auth)

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/api/controls/auth` | POST | Authenticate with PIN |
| `/api/controls/lock` | POST | Lock controls |
| `/api/controls/status` | GET | Check auth status |
| `/api/control/arm` | POST | Arm/disarm system |
| `/api/control/actuate` | POST | Send actuator command |
| `/api/control/estop` | POST | Emergency stop (always available) |
| `/api/control/acknowledge` | POST | Acknowledge faults |

### Debug & Logs

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/api/logs` | GET | System logs (filterable) |
| `/api/logs/download` | GET | Download logs as JSON |
| `/api/commands` | GET | Command history |
| `/api/debug/packets` | GET | Raw packet buffer |
| `/api/debug/metrics` | GET | System metrics |

## WebSocket Events

### Server → Client

| Event | Description |
|-------|-------------|
| `sensor_data` | Telemetry from sensor boards |
| `system_state` | System state updates |
| `board_status` | Board connection status |
| `actuator_state` | Individual actuator state change |
| `actuator_states` | All actuator states |
| `alarm` | New alarm triggered |
| `alarm_cleared` | Alarm cleared |
| `log_entry` | New log entry |
| `estop` | E-STOP activated notification |

### Client → Server

| Event | Description |
|-------|-------------|
| `request_state` | Request full state update |

## Debug Features

### Raw Packet Inspector

View the last 100 TCP packets (RX and TX) with:
- Timestamp
- Direction (RX from sensor/control, TX to control)
- Board ID
- Packet size
- Latency
- Raw JSON content

### Board Connection Monitor

For each board displays:
- Connection state (CONNECTED, DEGRADED, TIMEOUT, DISCONNECTED)
- IP:Port
- Packets received/sent
- Error count
- Current latency and rolling average

### Command History

Full trace of every actuation command:
- Timestamp
- Actuator ID
- Requested state
- Validation result (PASS/FAIL with reasons)
- TCP packet sent
- ACK received (true/false)
- Round-trip latency
- InfluxDB logged status

### Latency Monitor

Real-time chart showing packet latency from all boards.

## Extending to Real Hardware

### 1. Replace Simulated TCP Clients

The `SimulatedTCPBoards` class can be replaced with actual TCP socket connections:

```python
class RealTCPBoards:
    def __init__(self):
        self.sensor_connections = {}
        self.control_connections = {}
        
    def connect_sensor_board(self, board_id, ip, port):
        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        sock.connect((ip, port))
        sock.setblocking(False)
        self.sensor_connections[board_id] = sock
        
    def read_sensor_data(self, board_id):
        sock = self.sensor_connections[board_id]
        data = sock.recv(4096)
        return json.loads(data.decode())
```

### 2. Implement InfluxDB Writer

Replace the simulated queue with actual InfluxDB client:

```python
from influxdb_client import InfluxDBClient, Point
from influxdb_client.client.write_api import SYNCHRONOUS

client = InfluxDBClient(url="http://localhost:8086", token="...", org="...")
write_api = client.write_api(write_options=SYNCHRONOUS)

def write_to_influx(measurement, tags, fields, timestamp):
    point = Point(measurement)
    for k, v in tags.items():
        point.tag(k, v)
    for k, v in fields.items():
        point.field(k, v)
    point.time(timestamp)
    write_api.write(bucket="daq", record=point)
```

### 3. Add Hardware Interlocks

Critical safety note: Software validation is **NOT** sufficient for safety-critical systems. Real hardware must include:

- Physical E-STOP circuits
- Hardware interlocks (cannot open LOX + Fuel without ignition sequence)
- Watchdog timers on control boards
- Pressure relief valves
- Redundant sensors

### 4. Production Authentication

Replace PIN with proper authentication:
- OAuth/OIDC integration
- Role-based access control
- Operator logging with user IDs
- Session timeouts

## Project Structure

```
clementine-dashboard/
├── app.py                    # Flask + SocketIO backend
├── requirements.txt          # Python dependencies
├── README.md                 # This file
├── templates/
│   └── index.html           # Main dashboard template
└── static/
    ├── css/
    │   └── style.css        # Dashboard styles
    └── js/
        └── dashboard.js      # Frontend logic
```

## Safety Notes

This is a **SIMULATION ONLY**. For actual rocket test operations:

1. Never rely solely on software interlocks
2. Always have redundant hardware safety systems
3. Follow established test procedures
4. Ensure all personnel are trained and certified
5. Maintain proper documentation and test logs
6. Conduct thorough pre-test safety reviews

## License

Internal use - Highlander Space Program

---

*Built with 🚀 by the Highlander Space Program GSE Team*
