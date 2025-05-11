# data_processor.py
from PySide6.QtCore import QObject, Signal, QTimer, Slot
import time
import struct

import config
import can_parser
from logger_setup import app_logger, sensor_data_logger

class DataProcessor(QObject):
    # Signals for UI updates
    ui_update_sensor = Signal(str, str, str, str, str)  # name, value_str, unit, board_name, component_type_name
    ui_update_servo = Signal(str, str, str, str)    # name, state_str (Open/Closed/Position), board_name, component_type_name
    log_message = Signal(str) # For general logging messages
    ui_update_board_status = Signal(str, str, str, dict) # board_can_id_hex, board_name, source_xbee_addr, status_data_dict


    def __init__(self, parent=None):
        super().__init__(parent)
        self._data_cache = {} # { "unique_component_id": {"name": str, "value": any, "unit": str, "timestamp": float, ...}}
        self._ui_update_timer = QTimer(self)
        self._ui_update_timer.timeout.connect(self._on_ui_update_timer_timeout)
        self.set_ui_update_frequency(config.DEFAULT_UI_UPDATE_HZ)

    def set_ui_update_frequency(self, hz: int):
        if hz > 0:
            self._ui_update_timer.setInterval(int(1000 / hz))
            if not self._ui_update_timer.isActive(): # Start only if not already active or interval changed
                self._ui_update_timer.start()
            app_logger.info(f"UI update frequency set to {hz} Hz ({int(1000/hz)} ms). Timer active: {self._ui_update_timer.isActive()}")
        elif hz == 0: # Allow stopping the timer explicitly if hz is 0
            if self._ui_update_timer.isActive():
                self._ui_update_timer.stop()
            app_logger.info("UI update timer stopped (frequency set to 0 Hz).")
        else: # hz < 0, invalid
            app_logger.warning(f"Invalid UI update frequency: {hz}. Must be >= 0.")


    @Slot(dict)
    def process_incoming_xbee_message(self, message_info):
        can_payload_bytes = message_info['can_payload']
        source_xbee_addr = message_info['source_addr_64']

        if len(can_payload_bytes) < 4: # Min length for CAN ID
            app_logger.warning(f"Received XBee payload from {source_xbee_addr} too short for CAN ID: {can_payload_bytes.hex()}")
            return

        can_id_32bit_int = int.from_bytes(can_payload_bytes[:4], 'big')
        can_data_bytes = can_payload_bytes[4:]

        try:
            parsed_id_fields = can_parser.parse_can_id_struct(can_id_32bit_int)
            can_id_29bit = parsed_id_fields["original_29bit_id"] # This is the actual CAN ID
        except ValueError as e:
            app_logger.error(f"Error parsing CAN ID 0x{can_id_32bit_int:08X} from {source_xbee_addr}: {e}")
            return

        comp_type_numeric = parsed_id_fields["component_type_id"]
        board_id_8bit = parsed_id_fields["board_id"] # This is the ID of the board *sending* the message
        board_name_from_sender = can_parser.get_board_name(board_id_8bit) # Name of the board that sent this CAN msg
        
        # --- Handle Board Status Response ---
        if comp_type_numeric == config.MESSAGE_TYPE["MSG_TYPE_BOARD_STATUS_RESPONSE"]:
            # The board_id_8bit from the CAN ID is the ID of the board reporting its status.
            # The can_data_bytes is the status payload for this board.
            # The structure of can_data_bytes needs to be defined by the embedded side.
            # Example: could be a series of bytes, or a simple status code.
            # For now, we'll log it and emit a generic signal.
            
            status_data_dict = {
                "raw_payload_hex": can_data_bytes.hex(),
                # Add more parsed fields here based on actual payload structure
                # e.g., "health_code": can_data_bytes[0] if len(can_data_bytes) > 0 else "N/A"
            }
            
            log_msg = (f"BOARD_STATUS_RESPONSE from Board ID 0x{board_id_8bit:02X} ({board_name_from_sender}) "
                       f"(via XBee {source_xbee_addr}): {status_data_dict}")
            app_logger.info(log_msg)
            self.log_message.emit(log_msg) # Also to UI event log

            # Emit a signal for the UI to update the specific board's status display
            # The UI will need a way to map board_id_8bit or board_name_from_sender to its display elements.
            self.ui_update_board_status.emit(f"0x{board_id_8bit:02X}", board_name_from_sender, source_xbee_addr, status_data_dict)
            return # Processing done for this type


        # --- Existing Component Data Processing ---
        component_config = can_parser.get_component_info_by_can_id(can_id_29bit)
        
        if not component_config:
            # Log if it's not a known component *and* not a board status response (already handled)
            app_logger.warning(f"No component config for CAN ID 0x{can_id_29bit:07X} (from 0x{can_id_32bit_int:08X}) "
                               f"on board {board_name_from_sender} (XBee {source_xbee_addr}). Data: {can_data_bytes.hex()}")
            # self.log_message.emit(f"Data from Unknown CAN ID: 0x{can_id_29bit:07X} (Board: {board_name_from_sender})")
            return

        comp_name = component_config["name"]
        comp_type_name_from_config = component_config["type"] # e.g., "Servo", "Thermocouple"
        # board_name_of_component = can_parser.get_board_name(parsed_id_fields["board_id"]) # This is the board where the component resides
        instance_id = parsed_id_fields["instance_id"]
        cache_key = f"{comp_name}_{comp_type_name_from_config}_{instance_id}"

        value_str = "N/A"
        unit = ""
        processed_value = None

        if comp_type_name_from_config == "Servo":
            if len(can_data_bytes) >= 1:
                state_val = can_data_bytes[0]
                open_angle = component_config.get("open_angle", 180)
                closed_angle = component_config.get("closed_angle", 0)
                if state_val == 0: value_str = "Closed"
                elif state_val == 1: value_str = "Open"
                elif closed_angle <= state_val <= open_angle : value_str = f"{state_val}°"
                else: value_str = f"State: {state_val}"
                processed_value = value_str
                self._data_cache[cache_key] = {"name": comp_name, "value_str": value_str, "board": board_name_from_sender, "type": comp_type_name_from_config, "ts": time.time()}
            else: app_logger.warning(f"Servo {comp_name} data too short: {can_data_bytes.hex()}")

        elif comp_type_name_from_config == "Thermocouple":
            unit = "°C"
            if len(can_data_bytes) >= 2:
                raw_temp = struct.unpack('>h', can_data_bytes[:2])[0]
                temperature = float(raw_temp) / 10.0
                value_str = f"{temperature:.1f}"
                processed_value = temperature
                self._data_cache[cache_key] = {"name": comp_name, "value_str": value_str, "unit": unit, "board": board_name_from_sender, "type": comp_type_name_from_config, "ts": time.time()}
            else: app_logger.warning(f"TC {comp_name} data too short: {can_data_bytes.hex()}")

        elif comp_type_name_from_config == "PressureTransducer":
            unit = "PSI"
            if len(can_data_bytes) >= 4: # Assuming float
                try:
                    pressure = struct.unpack('>f', can_data_bytes[:4])[0]
                    value_str = f"{pressure:.2f}"
                    processed_value = pressure
                    self._data_cache[cache_key] = {"name": comp_name, "value_str": value_str, "unit": unit, "board": board_name_from_sender, "type": comp_type_name_from_config, "ts": time.time()}
                except struct.error: app_logger.warning(f"PT {comp_name} data invalid for float: {can_data_bytes.hex()}")
            elif len(can_data_bytes) >=2: # Assuming int that needs scaling
                raw_val = struct.unpack('>h', can_data_bytes[:2])[0]
                gain = component_config.get("gain", 1)
                offset = component_config.get("offset", 0)
                pressure = (raw_val * gain) + offset
                value_str = f"{pressure:.2f}"
                processed_value = pressure
                self._data_cache[cache_key] = {"name": comp_name, "value_str": value_str, "unit": unit, "board": board_name_from_sender, "type": comp_type_name_from_config, "ts": time.time()}
            else: app_logger.warning(f"PT {comp_name} data too short: {can_data_bytes.hex()}")
        
        elif comp_type_name_from_config == "Heater":
            unit = "State"
            if len(can_data_bytes) >= 1:
                status = "ON" if can_data_bytes[0] == 1 else "OFF"
                current_temp_str = ""
                if len(can_data_bytes) >= 3:
                     raw_temp = struct.unpack('>h', can_data_bytes[1:3])[0]
                     current_temp = float(raw_temp) / 10.0
                     current_temp_str = f", Temp: {current_temp:.1f}°C"
                value_str = f"Status: {status}{current_temp_str}"
                processed_value = value_str
                self._data_cache[cache_key] = {"name": comp_name, "value_str": value_str, "unit": unit, "board": board_name_from_sender, "type": comp_type_name_from_config, "ts": time.time()}
            else: app_logger.warning(f"Heater {comp_name} data too short: {can_data_bytes.hex()}")

        # Handle other system messages if needed based on their comp_type_numeric
        elif comp_type_numeric == config.MESSAGE_TYPE["MSG_TYPE_SYSTEM"] or \
             comp_type_numeric == config.MESSAGE_TYPE["MSG_TYPE_FLASH_SIGNAL"]:
            actual_comp_type_name = can_parser.get_component_type_name(comp_type_numeric)
            value_str = f"Data: {can_data_bytes.hex()}"
            processed_value = can_data_bytes.hex()
            self.log_message.emit(f"System/Flash msg from {comp_name if comp_name else 'N/A'} ({board_name_from_sender}, Type: {actual_comp_type_name}): {value_str}")
        
        else:
            # This case should ideally be caught by "No component config" if it's truly unknown,
            # or handled explicitly if it's a known message type not tied to a specific component lookup.
            actual_comp_type_name = can_parser.get_component_type_name(comp_type_numeric)
            app_logger.info(f"Data for unhandled but known component type '{actual_comp_type_name}' from {comp_name if comp_name else 'N/A'} "
                            f"(Board: {board_name_from_sender}): {can_data_bytes.hex()}")
            value_str = can_data_bytes.hex()
            processed_value = value_str


        if processed_value is not None:
            log_val = processed_value if isinstance(processed_value, (int, float)) else f'"{processed_value}"'
            sensor_data_logger.info(f"{comp_name},{log_val},{unit},{board_name_from_sender},{comp_type_name_from_config if comp_type_name_from_config else actual_comp_type_name},{instance_id}")

        app_logger.debug(f"Processed: {comp_name} ({comp_type_name_from_config if comp_type_name_from_config else actual_comp_type_name} on {board_name_from_sender}) -> {value_str} {unit}. XBee Src: {source_xbee_addr}, CAN Data: {can_data_bytes.hex()}")


    def _on_ui_update_timer_timeout(self):
        # app_logger.debug("UI update timer fired.")
        if not self._data_cache: # Optimization: if cache is empty, do nothing
            return

        for key, data in list(self._data_cache.items()): # Iterate over a copy if items might be removed
            # Consider adding staleness check here if needed
            # if time.time() - data.get('ts', 0) > STALE_DATA_THRESHOLD_S:
            #    # Handle stale data, e.g., remove from cache or mark as stale in UI
            #    continue

            if data["type"] == "Servo":
                self.ui_update_servo.emit(data["name"], data["value_str"], data["board"], data["type"])
            elif data["type"] in ["Thermocouple", "PressureTransducer", "Heater"]:
                self.ui_update_sensor.emit(data["name"], data["value_str"], data.get("unit",""), data["board"], data["type"])
            # Add other types as needed if they use the timed UI update mechanism