# config.py

# XBee Settings
XBEE_BAUD_RATE = 9600
XBEE_API_MODE = 2  # API mode with escaping. THIS APP ASSUMES XBEE IS PRE-CONFIGURED TO THIS MODE.
XBEE_PROBE_TIMEOUT_S = 2.0 # Timeout for AT commands during initial port probing (e.g., get_node_id)
XBEE_DATA_TIMEOUT_S = 2.5  # Timeout for synchronous data send operations (e.g., send_unicast_command)
DEFAULT_UI_UPDATE_HZ = 1
XBEE_POST_CONFIG_DELAY_S = 1.5 # Relevant if AP mode setting was done by app (currently not)

# Target XBee Radio Addresses for unicast commands via send_command_to_configured_targets
# Replace with your actual 64-bit hex addresses.
# The first part of the tuple is a display name/alias, the second is the address.
XBEE_TARGET_RADIO_CONFIG = [
    ("Coordinator", "0013A2004238A3E3"),
    ("PadCtrl-1", "0013A20041AE78C2"),
    # Add more radios here as needed, e.g.:
]
# Extract just the addresses for internal use where only the address list is needed
XBEE_TARGET_ADDRESSES_64BIT = [radio[1] for radio in XBEE_TARGET_RADIO_CONFIG]


# Log files
LOG_FILE_NAME = "control_panel_log.txt" # General application operational logs
DATA_LOG_FILE_NAME = "sensor_data_log.csv" # Parsed sensor data
XBEE_RAW_PACKET_LOG_FILE_NAME = "xbee_raw_packets.log" # Log for all raw XBee packets

# CAN ID Structure (based on 29-bit ID in a 32-bit field, LSB padded)
# Example: 0x01050401 (hex) = 00000001 00000101 00000100 00001 000 (binary)
#                             |        |        |        |     |
#                             |        |        |        |     +-- Padding (3 bits)
#                             |        |        |        +-------- Instance (5 bits)
#                             |        |        |        +----------------- Component Type (8 bits)
#                             |        +-------------------------- Board ID (8 bits)
#                             +----------------------------------- Sender (8 bits)

CAN_ID_SENDER_SHIFT = 21
CAN_ID_SENDER_MASK = 0xFF << CAN_ID_SENDER_SHIFT

CAN_ID_BOARD_ID_SHIFT = 13
CAN_ID_BOARD_ID_MASK = 0xFF << CAN_ID_BOARD_ID_SHIFT

CAN_ID_COMPONENT_TYPE_SHIFT = 5
CAN_ID_COMPONENT_TYPE_MASK = 0xFF << CAN_ID_COMPONENT_TYPE_SHIFT

CAN_ID_INSTANCE_SHIFT = 0 # This is after the 3-bit LSB padding is removed
CAN_ID_INSTANCE_MASK = 0x1F # 5 bits for instance

# Message Types (from Component Type field)
MESSAGE_TYPE = {
    "MSG_TYPE_SYSTEM": 0,
    "MSG_TYPE_SERVO": 1,
    "MSG_TYPE_THERMOCOUPLE": 2,
    "MSG_TYPE_PRESSURE": 3,
    "MSG_TYPE_HEATER": 4,
    "MSG_TYPE_LED": 5,
    "MSG_TYPE_FLASH_SIGNAL": 6,
    "MSG_TYPE_IGNITER_STATUS": 20, # Example, if igniter sends its own status
    "MSG_TYPE_AUTO_MODE_STATUS": 21, # Example
    "MSG_TYPE_SERVOS_POWER_STATUS": 22, # Example
    "MSG_TYPE_BOARD_STATUS_RESPONSE": 24, # Added for board status responses
}

# Sender Types (from Sender field)
BOARD_CAN_ID_MAPPING = {
    "SENDER_BREAK_WIRE": 0,
    "SENDER_PAD_CONTROLLER": 1,
    "SENDER_SERVO_BOARD": 2,
    "SENDER_SENSOR_BOARD": 3,
    "SENDER_TESTER_BOARD_SW": 4, # This code and controller
    "SENDER_HW_TESTER": 254,
    "SENDER_PC": 255 # This application when sending commands (or use Tester Board SW)
}
# We'll use SENDER_PC for messages originating from this control panel
PC_SENDER_ID = BOARD_CAN_ID_MAPPING["SENDER_PC"]


# Commands to be sent
# These are the values that will be sent as a single byte payload
COMMANDS = {
    "OPEN_PYRO": 0,
    "CLOSE_PYRO": 1,
    "SIGNAL_ALL": 2,
    "REPORT_ALL": 3,
    "OPEN_NO4": 4,
    "CLOSE_NO4": 5,
    "OPEN_NO3": 6,
    "CLOSE_NO3": 7,
    "START_1": 8,
    "OPEN_NO2": 9,
    "CLOSE_NO2": 10,
    "AUTO_ON": 12,
    "AUTO_OFF": 13,
    "ACTIVATE_IGNITER": 14,
    "DEACTIVATE_IGNITER": 15,
    "ABORT": 16,
    "ACTIVATE_SERVOS": 17,
    "DEACTIVATE_SERVOS": 18,
    "DEABORT": 19,
    "CHECK_STATE": 20,
    "DESTART": 21,
    "RADIO_HEALTHCHECK": 22,         # New
    "BOARD_STATUS_REQUEST": 23,      # New
    # BOARD_STATUS_RESPONSE is primarily a message type received, not sent as a command byte this way.
    # It will be identified by its CAN message type or a specific payload structure.
}

# Lookup Tables
SERVO_LOOKUP_TABLE = [
    {"board_id_hw": {"mcu_id1": 0x00390043, "mcu_id2": 0x48585311, "mcu_id3": 0x20373733}, "can_id": 0x02010108, "name": "FV-N02", "open_angle": 200, "closed_angle": 85},
    {"board_id_hw": {"mcu_id1": 0x0032002D, "mcu_id2": 0x48585314, "mcu_id3": 0x20373733}, "can_id": 0x02020108, "name": "FV-N03", "open_angle": 200, "closed_angle": 85},
    {"board_id_hw": {"mcu_id1": 0x00310043, "mcu_id2": 0x48585311, "mcu_id3": 0x20373733}, "can_id": 0x02030108, "name": "FV-N04", "open_angle": 200, "closed_angle": 85},
    {"board_id_hw": {"mcu_id1": 0x003a0042, "mcu_id2": 0x48585311, "mcu_id3": 0x20373733}, "can_id": 0x00040108, "name": "FV-PYRO", "open_angle": 135, "closed_angle": 0},
]

THERMO_LOOKUP_TABLE = [
    {"board_id_hw": {"mcu_id1": 0x00390043, "mcu_id2": 0x48585311, "mcu_id3": 0x20373733}, "can_id": 0x02010208, "name": "TC-02", "update_freq": 100},
    {"board_id_hw": {"mcu_id1": 0x0032002D, "mcu_id2": 0x48585314, "mcu_id3": 0x20373733}, "can_id": 0x02020208, "name": "TC-03", "update_freq": 100},
    {"board_id_hw": {"mcu_id1": 0x00310043, "mcu_id2": 0x48585311, "mcu_id3": 0x20373733}, "can_id": 0x02030208, "name": "TC-04", "update_freq": 100},
    {"board_id_hw": {"mcu_id1": 0x003a0042, "mcu_id2": 0x48585311, "mcu_id3": 0x20373733}, "can_id": 0x00040208, "name": "TC-05", "update_freq": 100},
]

HEATER_LOOKUP_TABLE = [
    {"board_id_hw": {"mcu_id1": 0x00390043, "mcu_id2": 0x48585311, "mcu_id3": 0x20373733}, "can_id": 0x02010408, "name": "H-02", "setpoint_max": 30, "setpoint_min": 25, "update_freq": 100},
    {"board_id_hw": {"mcu_id1": 0x0032002D, "mcu_id2": 0x48585314, "mcu_id3": 0x20373733}, "can_id": 0x02020408, "name": "H-03", "setpoint_max": 29, "setpoint_min": 27, "update_freq": 100},
    {"board_id_hw": {"mcu_id1": 0x00310043, "mcu_id2": 0x48585311, "mcu_id3": 0x20373733}, "can_id": 0x02030408, "name": "H-04", "setpoint_max": 29, "setpoint_min": 27, "update_freq": 100},
    {"board_id_hw": {"mcu_id1": 0x003a0042, "mcu_id2": 0x48585311, "mcu_id3": 0x20373733}, "can_id": 0x00040408, "name": "H-05", "setpoint_max": 29, "setpoint_min": 27, "update_freq": 100},
]

PT_LOOKUP_TABLE = [
    {"board_id_hw": {"mcu_id1": 0x002b002c, "mcu_id2": 0x48585314, "mcu_id3": 0x20373733}, "can_id": 0x00110308, "name": "PT-01", "freq": 100, "gain": 0, "offset": 100, "type": 'A'},
    {"board_id_hw": {"mcu_id1": 0x002b002c, "mcu_id2": 0x48585314, "mcu_id3": 0x20373733}, "can_id": 0x00110310, "name": "PT-02", "freq": 5000, "gain": 0, "offset": 100, "type": 'B'},
    {"board_id_hw": {"mcu_id1": 0x0032001e, "mcu_id2": 0x46304317, "mcu_id3": 0x200003e0}, "can_id": 0x00120308, "name": "PT-03", "freq": 5000, "gain": 0, "offset": 100, "type": 'B'},
    {"board_id_hw": {"mcu_id1": 0x0032001e, "mcu_id2": 0x46304317, "mcu_id3": 0x200003e0}, "can_id": 0x00120310, "name": "PT-04", "freq": 100, "gain": 0, "offset": 100, "type": 'A'},
]

BOARD_INFO_LOOKUP_TABLE = {
    0x01: {"hw_id_struct": {"mcu_id1": 0x00390043, "mcu_id2": 0x48585311, "mcu_id3": 0x20373733}, "name": "DONATELLO", "description": "FV-NO2 Related"},
    0x02: {"hw_id_struct": {"mcu_id1": 0x0032002D, "mcu_id2": 0x48585314, "mcu_id3": 0x20373733}, "name": "LEONARDO", "description": "FV-NO3 Related"},
    0x03: {"hw_id_struct": {"mcu_id1": 0x00310043, "mcu_id2": 0x48585311, "mcu_id3": 0x20373733}, "name": "MICHELANGELO", "description": "FV-NO4 Related"},
    0x04: {"hw_id_struct": {"mcu_id1": 0x003a0042, "mcu_id2": 0x48585311, "mcu_id3": 0x20373733}, "name": "RAPHAEL", "description": "FV-PYRO Related"},
    0x11: {"hw_id_struct": {"mcu_id1": 0x002b002c, "mcu_id2": 0x48585314, "mcu_id3": 0x20373733}, "name": "SPLINTER", "description": "PT Sensor Board 1"},
    0x12: {"hw_id_struct": {"mcu_id1": 0x0032001e, "mcu_id2": 0x46304317, "mcu_id3": 0x200003e0}, "name": "APRIL", "description": "PT Sensor Board 2"},
}

ALL_COMPONENTS_LOOKUP = {}
for item in SERVO_LOOKUP_TABLE:
    ALL_COMPONENTS_LOOKUP[item["can_id"]] = {"type": "Servo", **item}
for item in THERMO_LOOKUP_TABLE:
    ALL_COMPONENTS_LOOKUP[item["can_id"]] = {"type": "Thermocouple", **item}
for item in HEATER_LOOKUP_TABLE:
    ALL_COMPONENTS_LOOKUP[item["can_id"]] = {"type": "Heater", **item}
for item in PT_LOOKUP_TABLE:
    ALL_COMPONENTS_LOOKUP[item["can_id"]] = {"type": "PressureTransducer", **item}

NAMED_COMMANDS = {
    "Open FV-PYRO": COMMANDS["OPEN_PYRO"],
    "Close FV-PYRO": COMMANDS["CLOSE_PYRO"],
    "Open FV-N04": COMMANDS["OPEN_NO4"],
    "Close FV-N04": COMMANDS["CLOSE_NO4"],
    "Open FV-N03": COMMANDS["OPEN_NO3"],
    "Close FV-N03": COMMANDS["CLOSE_NO3"],
    "Open FV-N02": COMMANDS["OPEN_NO2"],
    "Close FV-N02": COMMANDS["CLOSE_NO2"],
}

# Commands for the main "System Commands" / "Device Toggles" section
# These will be sent to all configured targets.
# Note: Some of these (like "Report All", "Check State") will effectively become
# aliases or be replaced by "Board Status Request" or "Radio Healthcheck" logic.
# The UI part will determine final button names and actions.
GENERAL_COMMANDS = {
    # System-wide/General
    "Signal All": COMMANDS["SIGNAL_ALL"],
    # "Report All": COMMANDS["REPORT_ALL"], # Will be handled by BOARD_STATUS_REQUEST mechanism
    "Start Sequence 1": COMMANDS["START_1"],
    "Stop Sequence 1 (Destart)": COMMANDS["DESTART"],
    "ABORT": COMMANDS["ABORT"],
    "Clear Abort (Deabort)": COMMANDS["DEABORT"],
    # "Check State": COMMANDS["CHECK_STATE"], # Will be handled by BOARD_STATUS_REQUEST
    # New direct commands from UI perspective
    "Radio Healthcheck": COMMANDS["RADIO_HEALTHCHECK"], # For button/manual trigger
    "Board Status Request": COMMANDS["BOARD_STATUS_REQUEST"], # For button/manual trigger
    # Toggleable states
    "Auto Mode ON": COMMANDS["AUTO_ON"],
    "Auto Mode OFF": COMMANDS["AUTO_OFF"],
    "Activate Igniter": COMMANDS["ACTIVATE_IGNITER"],
    "Deactivate Igniter": COMMANDS["DEACTIVATE_IGNITER"],
    "Activate Servos": COMMANDS["ACTIVATE_SERVOS"],
    "Deactivate Servos": COMMANDS["DEACTIVATE_SERVOS"],
}

# Timer intervals (in milliseconds)
RADIO_HEALTHCHECK_INTERVAL_MS = 15 * 1000  # 15 seconds
BOARD_STATUS_REQUEST_INTERVAL_MS = 60 * 1000 # 1 minute