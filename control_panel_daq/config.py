# config.py

# XBee Settings
# XBEE_BAUD_RATE = 9600
XBEE_BAUD_RATE = 115200
XBEE_API_MODE = 2  # API mode with escaping. THIS APP ASSUMES XBEE IS PRE-CONFIGURED TO THIS MODE.
XBEE_PROBE_TIMEOUT_S = 2.0 # Timeout for AT commands during initial port probing (e.g., get_node_id)
XBEE_DATA_TIMEOUT_S = 2.5  # Timeout for synchronous data send operations (e.g., send_unicast_command)
DEFAULT_UI_UPDATE_HZ = 2
XBEE_POST_CONFIG_DELAY_S = 1.5 # Relevant if AP mode setting was done by app (currently not)
PERIODIC_BOARD_STATUS_INTERVAL_MS = 3000 # 3 seconds

# Target XBee Radio Addresses for unicast commands via send_command_to_configured_targets
XBEE_TARGET_RADIO_CONFIG = [
    # ("Coordinator", "0013A2004238A3E3"),
    ("PadCtrl-1", "0013A20041AE78C2"),
]
XBEE_TARGET_ADDRESSES_64BIT = [radio[1] for radio in XBEE_TARGET_RADIO_CONFIG]


# Log files
LOG_FILE_NAME = "control_panel_log.txt"
DATA_LOG_FILE_NAME = "sensor_data_log.csv"
XBEE_RAW_PACKET_LOG_FILE_NAME = "xbee_raw_packets.log"

# CAN ID Structure
CAN_ID_ACK_BIT_IN_29BIT_ID = (1 << 28)
CAN_ID_SENDER_SHIFT = 21
CAN_ID_SENDER_MASK = (0xFF << CAN_ID_SENDER_SHIFT)
CAN_ID_BOARD_ID_SHIFT = 13
CAN_ID_BOARD_ID_MASK = (0xFF << CAN_ID_BOARD_ID_SHIFT)
CAN_ID_COMPONENT_TYPE_SHIFT = 5
CAN_ID_COMPONENT_TYPE_MASK = (0xFF << CAN_ID_COMPONENT_TYPE_SHIFT)
CAN_ID_INSTANCE_SHIFT = 0
CAN_ID_INSTANCE_MASK = 0x1F

# Message Types
MESSAGE_TYPE = {
    "MSG_TYPE_SYSTEM": 0,
    "MSG_TYPE_SERVO": 1,
    "MSG_TYPE_THERMOCOUPLE": 2,
    "MSG_TYPE_PRESSURE": 3,
    "MSG_TYPE_HEATER": 4,
    "MSG_TYPE_LED": 5,
    "MSG_TYPE_FLASH_SIGNAL": 6,
    "MSG_TYPE_LOADCELL": 7,
    "MSG_TYPE_BREAKWIRE_STATUS": 19,
    "MSG_TYPE_IGNITER_STATUS": 20,
    "MSG_TYPE_AUTO_MODE_STATUS": 21,
    "MSG_TYPE_SERVOS_POWER_STATUS": 22,
    "MSG_TYPE_PC_STATE_STATUS": 23,
    "MSG_TYPE_BOARD_STATUS_RESPONSE": 24,
    "MSG_TYPE_ACK_GENERIC": 25,
}

# Sender Types / Board Role IDs
BOARD_CAN_ID_MAPPING = {
    "SENDER_DONATELLO": 0x01,
    "SENDER_LEONARDO": 0x02,
    "SENDER_MICHELANGELO": 0x03,
    "SENDER_RAPHAEL": 0x04,
    "SENDER_SPLINTER": 0x11,
    "SENDER_APRIL": 0x12,
    "SENDER_CASEY": 0x20,
    "SENDER_PAD_CONTROLLER": 0x20,
    "SENDER_BREAK_WIRE": 0,
    "SENDER_TESTER_BOARD_SW": 4,
    "SENDER_HW_TESTER": 254,
    "SENDER_PC": 255
}
PC_SENDER_ID = BOARD_CAN_ID_MAPPING["SENDER_PC"]

# Commands sent FROM this PC application
COMMANDS = {
    "OPEN_PYRO": 0, "CLOSE_PYRO": 1, "SIGNAL_ALL": 2, "REPORT_ALL": 3,
    "OPEN_NO4": 4, "CLOSE_NO4": 5, "OPEN_NO3": 6, "CLOSE_NO3": 7,
    "OPEN_NO2": 9, "CLOSE_NO2": 10, "AUTO_ON": 12, "AUTO_OFF": 13,
    "ACTIVATE_IGNITER": 14, "DEACTIVATE_IGNITER": 15, "ACTIVATE_SERVOS": 17,
    "DEACTIVATE_SERVOS": 18, "CHECK_STATE": 20, "RADIO_HEALTHCHECK": 22,
    "BOARD_STATUS_REQUEST": 23,
}

# Board Information Lookup Table
BOARD_INFO_LOOKUP_TABLE = {
    0x01: {"hw_id_struct": {"mcu_id1": 0x00390043, "mcu_id2": 0x48585311, "mcu_id3": 0x20373733}, "name": "DONATELLO", "description": "FV-NO2 Related", "type": "ServoBoard", "components_hosted": ["FV-N02", "TC-02", "H-02"]},
    0x02: {"hw_id_struct": {"mcu_id1": 0x0032002D, "mcu_id2": 0x48585314, "mcu_id3": 0x20373733}, "name": "LEONARDO", "description": "FV-NO3 Related", "type": "ServoBoard", "components_hosted": ["FV-N03", "TC-03", "H-03"]},
    0x03: {"hw_id_struct": {"mcu_id1": 0x00310043, "mcu_id2": 0x48585311, "mcu_id3": 0x20373733}, "name": "MICHELANGELO", "description": "FV-NO4 Related", "type": "ServoBoard", "components_hosted": ["FV-N04", "TC-04", "H-04"]},
    0x04: {"hw_id_struct": {"mcu_id1": 0x003a0042, "mcu_id2": 0x48585311, "mcu_id3": 0x20373733}, "name": "RAPHAEL", "description": "FV-PYRO Related", "type": "ServoBoard", "components_hosted": ["FV-PYRO", "TC-05", "H-05"]},
    0x11: {"hw_id_struct": {"mcu_id1": 0x002b002c, "mcu_id2": 0x48585314, "mcu_id3": 0x20373733}, "name": "SPLINTER", "description": "PT/LC Sensor Board 1", "type": "SensorBoard", "components_hosted": ["CH-01", "N-01"]},
    0x12: {"hw_id_struct": {"mcu_id1": 0x0032001e, "mcu_id2": 0x46304317, "mcu_id3": 0x20383557}, "name": "APRIL", "description": "PT Sensor Board 2", "type": "SensorBoard", "components_hosted": ["PT-03", "N-04"]},
    0x20: {"hw_id_struct": {"mcu_id1": 0x0042003d, "mcu_id2": 0x3034510d, "mcu_id3": 0x37363432}, "name": "CASEY", "description": "PAD-CONTROLLER", "type": "ControllerBoard", "components_hosted": []}
}

def get_board_id_by_name(name_to_find):
    for board_id, info in BOARD_INFO_LOOKUP_TABLE.items():
        if info.get("name", "").lower() == name_to_find.lower():
            return board_id
    return None

# Component Lookup Tables (CAN-based components)
SERVO_LOOKUP_TABLE = [
    {"parent_board_id_hex": get_board_id_by_name("DONATELLO"), "can_id": 0x02010108, "name": "FV-N02", "purpose": "Nitrogen Fill Valve", "open_angle": 200, "closed_angle": 85},
    {"parent_board_id_hex": get_board_id_by_name("LEONARDO"), "can_id": 0x02020108, "name": "FV-N03", "purpose": "Nitrogen Purge Valve", "open_angle": 200, "closed_angle": 85},
    {"parent_board_id_hex": get_board_id_by_name("MICHELANGELO"), "can_id": 0x02030108, "name": "FV-N04", "purpose": "Nitrogen Tank Isolation", "open_angle": 200, "closed_angle": 85},
    {"parent_board_id_hex": get_board_id_by_name("RAPHAEL"), "can_id": 0x02040108, "name": "FV-PYRO", "purpose": "Pyro Valve Actuation", "open_angle": 135, "closed_angle": 0},
]
THERMO_LOOKUP_TABLE = [
    {"parent_board_id_hex": get_board_id_by_name("DONATELLO"), "can_id": 0x02010201, "name": "TC-02", "purpose": "Air Temp", "update_freq": 2},
    {"parent_board_id_hex": get_board_id_by_name("LEONARDO"), "can_id": 0x02020201, "name": "TC-03", "purpose": "Supply Tank Temp", "update_freq": 2},
    {"parent_board_id_hex": get_board_id_by_name("MICHELANGELO"), "can_id": 0x02030201, "name": "TC-04", "purpose": "Chamber Temp", "update_freq": 2},
    {"parent_board_id_hex": get_board_id_by_name("RAPHAEL"), "can_id": 0x02040201, "name": "TC-05", "purpose": "Pyro Area Temp", "update_freq": 2},
]
HEATER_LOOKUP_TABLE = [
    {"parent_board_id_hex": get_board_id_by_name("DONATELLO"), "can_id": 0x02010408, "name": "H-02", "purpose": "Heat Trace N02 Line", "setpoint_max": 30, "setpoint_min": 25, "update_freq": 100, "temp_scale_factor": 10.0},
    {"parent_board_id_hex": get_board_id_by_name("LEONARDO"), "can_id": 0x02020408, "name": "H-03", "purpose": "Heat Trace N03 Line", "setpoint_max": 29, "setpoint_min": 27, "update_freq": 100, "temp_scale_factor": 10.0},
    {"parent_board_id_hex": get_board_id_by_name("MICHELANGELO"), "can_id": 0x02030408, "name": "H-04", "purpose": "Heat Trace N04 Line", "setpoint_max": 29, "setpoint_min": 27, "update_freq": 100, "temp_scale_factor": 10.0},
    {"parent_board_id_hex": get_board_id_by_name("RAPHAEL"), "can_id": 0x02040408, "name": "H-05", "purpose": "Pyro Area Heat", "setpoint_max": 29, "setpoint_min": 27, "update_freq": 100, "temp_scale_factor": 10.0},
]
PT_LOOKUP_TABLE = [
    {"parent_board_id_hex": get_board_id_by_name("SPLINTER"), "can_id": 0x03110308, "name": "CH-01", "purpose": "Chamber", "data_message_sender_name": "SPLINTER", "data_message_instance_id": 1, "freq": 100, "gain": 	13.08, "offset": 2534, "type": 'A', "adc_min_voltage": 0.0, "adc_max_voltage": 1.0, "unit": "PSI", "type": "PressureTransducer"},
    {"parent_board_id_hex": get_board_id_by_name("SPLINTER"), "can_id": 0x03110310, "name": "N-01", "purpose": "Fill Line", "data_message_sender_name": "SPLINTER", "data_message_instance_id": 2, "freq": 5000, "gain": 12.8114, "offset": 2122, "type": 'B', "adc_min_voltage": 0.0, "adc_max_voltage": 1.0, "unit": "PSI", "type": "PressureTransducer"},
    {"parent_board_id_hex": get_board_id_by_name("APRIL"), "can_id": 0x03120308, "name": "E-01", "purpose": "Ethanol Tank", "data_message_sender_name": "APRIL", "data_message_instance_id": 1, "freq": 5000, "gain": 20.79, "offset": 2893, "type": 'B', "adc_min_voltage": 0.0, "adc_max_voltage": 1.0, "unit": "PSI", "type": "PressureTransducer"},
    {"parent_board_id_hex": get_board_id_by_name("APRIL"), "can_id": 0x03120310, "name": "N-04", "purpose": "Nitrous", "data_message_sender_name": "APRIL", "data_message_instance_id": 2, "freq": 100, "gain": 13.33, "offset": 2636, "type": 'A', "adc_min_voltage": 0.0, "adc_max_voltage": 1.0, "unit": "PSI", "type": "PressureTransducer"},
]
#y=0.0481x-128.2
LOADCELL_LOOKUP_TABLE = [ # CAN-based Load Cells
    # {"parent_board_id_hex": get_board_id_by_name("SPLINTER"), "can_id": 0x00110708, "name": "LC-01", "purpose": "Thrust Measurement (CAN)", "update_freq": 1000, "unit": "lbf"},
]

# Combined list of all configured components (CAN-based initially)
ALL_COMPONENT_CONFIGS = (SERVO_LOOKUP_TABLE +
                         THERMO_LOOKUP_TABLE +
                         PT_LOOKUP_TABLE +
                         LOADCELL_LOOKUP_TABLE +
                         HEATER_LOOKUP_TABLE)

# >>> LabJack Load Cell Configuration <<<
LABJACK_ENABLED = True  # Set to True to enable LabJack, False to disable
LABJACK_CONNECTION_TYPE = "ANY"  # e.g., "ANY", "USB", "TCP" (for network devices)
LABJACK_IDENTIFIER = "ANY"      # e.g., "ANY", specific serial number, or IP address
LABJACK_SAMPLING_INTERVAL_MS = 10  # Read LabJack data every 100ms (10 Hz)

# Define the analog input pairs for your load cells on the LabJack.
# Format: (Positive Channel Name, Negative Channel Name Part for eWriteName)
# Example: AIN48 (positive), AIN56 (negative for AIN48) => ("AIN48", "AIN56")
# The data_processor will parse the number from the negative channel name part.
# These are taken from your HSPDAQ.py example.
LABJACK_LOADCELL_DIFF_PAIRS = [
    ("AIN48", "AIN56"),
    ("AIN49", "AIN57"),
    ("AIN50", "AIN58"),
    ("AIN51", "AIN59"),
]
# Name for the UI and logging for the summed load cell data from LabJack.
# If this name matches a LoadCell name in LOADCELL_LOOKUP_TABLE (CAN-based),
# and LABJACK_ENABLED is True, data_processor will prioritize LabJack data.
LABJACK_SUMMED_LC_NAME = "LC-TOTAL-LJ" # Example: "LC-TOTAL-LJ" or "LC-01" if replacing
LABJACK_LOADCELL_UNIT = "lbs"

# Add LabJack Load Cell to ALL_COMPONENT_CONFIGS if enabled.
# This ensures it's available for the UI to discover and display.
if LABJACK_ENABLED:
    lj_lc_config_item = {
        "name": LABJACK_SUMMED_LC_NAME,
        "type": "LoadCell",  # Critical for UI and data_processor cache handling
        "source_type": "LabJack",  # Custom field to identify the source
        "parent_board_name": "LabJack DAQ",  # Pseudo board name for UI grouping
        "unit": LABJACK_LOADCELL_UNIT,
        "purpose": "Total Load (from LabJack)",
        # CAN-specific fields like 'can_id', 'parent_board_id_hex' are not applicable
    }
    ALL_COMPONENT_CONFIGS.append(lj_lc_config_item)
# >>> End LabJack Configuration <<<


# Dictionaries for quick lookup of CAN components by ID or name
ALL_COMPONENTS_LOOKUP = {} # Key: (board_id, component_type_id, instance_id)
COMPONENT_CONFIG_BY_NAME = {} # Key: component_name

def add_to_lookup(item_list, comp_type_str, msg_type_val):
    for item in item_list:
        # Skip if it's a LabJack item or essential CAN fields are missing
        if item.get("source_type") == "LabJack" or "can_id" not in item or "parent_board_id_hex" not in item:
            # If it's a non-CAN item but has a name, still add to COMPONENT_CONFIG_BY_NAME
            if 'name' in item and 'type' in item: # Ensure type is also present
                 COMPONENT_CONFIG_BY_NAME[item['name']] = {"type": item['type'], **item}
            continue

        board_id = item.get("parent_board_id_hex")
        if board_id is None: continue # Should not happen for CAN items after check

        # Extract instance ID from the CAN ID structure defined for the component
        instance_id_from_can_id = (item["can_id"] & CAN_ID_INSTANCE_MASK) >> CAN_ID_INSTANCE_SHIFT
        lookup_key = (board_id, msg_type_val, instance_id_from_can_id)

        # Ensure parent_board_name and purpose are consistently available
        item['parent_board_name'] = BOARD_INFO_LOOKUP_TABLE.get(board_id, {}).get('name', f'Board 0x{board_id:02X}')
        item['component_purpose'] = item.get('purpose', '') # Use existing or empty string

        full_config_item = {"type": comp_type_str, **item}
        ALL_COMPONENTS_LOOKUP[lookup_key] = full_config_item
        if 'name' in item:
            COMPONENT_CONFIG_BY_NAME[item['name']] = full_config_item

# Populate lookup dictionaries (primarily for CAN-based components)
# Note: The LabJack component is already in ALL_COMPONENT_CONFIGS for UI iteration.
# add_to_lookup is primarily for CAN components processed by can_parser.
add_to_lookup(SERVO_LOOKUP_TABLE, "Servo", MESSAGE_TYPE["MSG_TYPE_SERVO"])
add_to_lookup(THERMO_LOOKUP_TABLE, "Thermocouple", MESSAGE_TYPE["MSG_TYPE_THERMOCOUPLE"])
add_to_lookup(PT_LOOKUP_TABLE, "PressureTransducer", MESSAGE_TYPE["MSG_TYPE_PRESSURE"])
add_to_lookup(LOADCELL_LOOKUP_TABLE, "LoadCell", MESSAGE_TYPE["MSG_TYPE_LOADCELL"]) # CAN Loadcells
add_to_lookup(HEATER_LOOKUP_TABLE, "Heater", MESSAGE_TYPE["MSG_TYPE_HEATER"])

# If the LabJack component was added to ALL_COMPONENT_CONFIGS and needs to be in COMPONENT_CONFIG_BY_NAME
# ensure it's added (add_to_lookup might miss it if it expects CAN fields).
# The modified add_to_lookup above attempts to add any named item to COMPONENT_CONFIG_BY_NAME.
# Or, add it explicitly if needed:
if LABJACK_ENABLED and 'lj_lc_config_item' in locals():
    if lj_lc_config_item['name'] not in COMPONENT_CONFIG_BY_NAME:
        COMPONENT_CONFIG_BY_NAME[lj_lc_config_item['name']] = lj_lc_config_item


# Named Commands (for UI buttons etc.)
NAMED_COMMANDS = {
    "Open FV-PYRO": COMMANDS["OPEN_PYRO"], "Close FV-PYRO": COMMANDS["CLOSE_PYRO"],
    "Open FV-N04": COMMANDS["OPEN_NO4"], "Close FV-N04": COMMANDS["CLOSE_NO4"],
    "Open FV-N03": COMMANDS["OPEN_NO3"], "Close FV-N03": COMMANDS["CLOSE_NO3"],
    "Open FV-N02": COMMANDS["OPEN_NO2"], "Close FV-N02": COMMANDS["CLOSE_NO2"],
}

GENERAL_COMMANDS = {
    "Signal All": COMMANDS["SIGNAL_ALL"],
    "Report All State": COMMANDS["REPORT_ALL"],
    "Check State": COMMANDS["CHECK_STATE"],
    "Auto Mode ON": COMMANDS["AUTO_ON"], "Auto Mode OFF": COMMANDS["AUTO_OFF"],
    "Activate Igniter": COMMANDS["ACTIVATE_IGNITER"], "Deactivate Igniter": COMMANDS["DEACTIVATE_IGNITER"],
    "Activate Servos": COMMANDS["ACTIVATE_SERVOS"], "Deactivate Servos": COMMANDS["DEACTIVATE_SERVOS"],
    "Radio Healthcheck": COMMANDS["RADIO_HEALTHCHECK"],
    "Board Status Request": COMMANDS["BOARD_STATUS_REQUEST"],
}

# Timing configurations
RADIO_HEALTHCHECK_INTERVAL_MS = 15 * 1000
BOARD_STATUS_REQUEST_INTERVAL_MS = 5 * 1000 # How often app can request status
BOARD_ACK_TIMEOUT_MS = 10000 # How long UI waits for board response before marking "Timeout"
PAD_CONTROLLER_ACK_TIMEOUT_MS = 10000 # Specific timeout for Pad Controller
BOARD_STATUS_CHECK_TIMER_MS = 2 * 1000 # How often UI checks internal last_seen timestamps

# State Mappings for UI display
IGNITER_STATES = {0: "Init", 1: "Deactivated", 2: "Activated"}
SERVO_STATES = {0: "Powered Closed", 1: "Unpowered Closed", 2: "Powered Open", 3: "Unpowered Open"}
ON_OFF_STATES = {0: "OFF", 1: "ON"}
PC_STATES = {0: "STARTUP", 1: "AUTO_OFF", 2: "AUTO_ON", 3: "DELAY", 4: "FIRE", 5: "OPEN"}
BREAKWIRE_STATES = {0: "Connected", 1: "Connected & Armed", 2: "Disconnected", 3: "Disconnected & Armed"}