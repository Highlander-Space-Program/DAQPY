# data_processor.py
from PySide6.QtCore import QObject, Signal, QTimer, Slot
import time
import struct

import config # Imports the updated config.py
import can_parser
from logger_setup import app_logger, sensor_data_logger

# Attempt to import LabJack library
try:
    from labjack import ljm
    LJM_AVAILABLE = True
except ImportError:
    LJM_AVAILABLE = False
    ljm = None # Ensure ljm is defined even if import fails

class DataProcessor(QObject):
    # Signals for UI updates (Existing)
    ui_update_sensor = Signal(str, str, str, str, str) # name, value_str, unit, board_name, component_type
    ui_update_servo = Signal(str, str, str, str)
    log_message = Signal(str)
    ui_update_pc_state_status = Signal(str, int, str, str)
    ui_update_board_detailed_status = Signal(int, str, str, dict)
    board_connectivity_update = Signal(int, str, float)
    ui_update_igniter_status = Signal(str, bool, str, str)
    ui_update_auto_mode_status = Signal(str, bool, str, str)
    ui_update_servos_power_status = Signal(str, bool, str, str)
    ui_update_breakwire_status = Signal(str, int, str, str)


    def __init__(self, parent=None):
        super().__init__(parent)
        self._data_cache = {}
        self._ui_update_timer = QTimer(self)
        self._ui_update_timer.timeout.connect(self._on_ui_update_timer_timeout)
        self.set_ui_update_frequency(config.DEFAULT_UI_UPDATE_HZ)

        # Tare and raw value storage
        self._last_raw_sensor_values = {} # Key: f"{name}_{type}", Value: float raw_value
        self._pt_tare_offsets = {}      # Key: "PT_Name", Value: float offset
        self._lc_tare_offsets = {}      # Key: "LC_Name", Value: float offset

        # LabJack Integration
        self.labjack_handle = None
        self._labjack_timer = None
        if config.LABJACK_ENABLED:
            if LJM_AVAILABLE and ljm:
                self._labjack_timer = QTimer(self)
                self._labjack_timer.timeout.connect(self._read_labjack_data_slot)
                self._initialize_labjack()
            else:
                log_msg = "LabJack LJM library not found, but LabJack integration is enabled in config. LabJack will be disabled."
                self.log_message.emit(log_msg)
                app_logger.error(log_msg)
                config.LABJACK_ENABLED = False 
        else:
            app_logger.info("LabJack integration is disabled in config.")

    def _code_to_name(self, prefix, code):
        if not LJM_AVAILABLE or not ljm: return f"Unknown (Code {code})"
        mapping = {
            getattr(ljm.constants, name): name
            for name in dir(ljm.constants)
            if name.startswith(prefix)
        }
        return mapping.get(code, f"Unknown (Code {code})")


    def _initialize_labjack(self):
        if not (LJM_AVAILABLE and config.LABJACK_ENABLED and ljm and self._labjack_timer):
            app_logger.info("Skipping LabJack initialization (not enabled, LJM not available, or timer not created).")
            return
        try:
            self.labjack_handle = ljm.openS(config.LABJACK_CONNECTION_TYPE,
                                            config.LABJACK_IDENTIFIER,
                                            "ANY")
            info = ljm.getHandleInfo(self.labjack_handle)
            ip_address_str = ljm.numberToIP(info[3]) if info[3] != 0 else "N/A (Not Ethernet)"
            device_type_str = self._code_to_name('dt', info[0])
            conn_type_str   = self._code_to_name('ct', info[1])


            log_msg = (f"LabJack opened: DevType={device_type_str}, ConnType={conn_type_str}, "
                       f"Serial={info[2]}, IP={ip_address_str}")
            app_logger.info(log_msg)
            self.log_message.emit(log_msg)

            self._configure_labjack_channels()
            self._labjack_timer.start(config.LABJACK_SAMPLING_INTERVAL_MS)
            self.log_message.emit(f"LabJack configured and polling started at {config.LABJACK_SAMPLING_INTERVAL_MS}ms interval.")

        except ljm.LJMError as e:
            self.labjack_handle = None
            err_msg = f"Failed to open or configure LabJack: {e} (Code: {e.errorCode})"
            app_logger.error(err_msg)
            self.log_message.emit(f"Error: LabJack connection failed: {str(e)}")
            config.LABJACK_ENABLED = False 
            if self._labjack_timer and self._labjack_timer.isActive():
                self._labjack_timer.stop()
        except Exception as e:
            self.labjack_handle = None
            err_msg = f"An unexpected error occurred during LabJack initialization: {e}"
            app_logger.error(err_msg)
            self.log_message.emit(f"Error: Unexpected LabJack initialization error: {str(e)}")
            config.LABJACK_ENABLED = False
            if self._labjack_timer and self._labjack_timer.isActive():
                self._labjack_timer.stop()

    def _configure_labjack_channels(self):
        if not self.labjack_handle or not ljm:
            app_logger.warning("Cannot configure LabJack channels, no handle or LJM library.")
            return
        try:
            if hasattr(config, 'LABJACK_LOADCELL_DIFF_PAIRS') and config.LABJACK_LOADCELL_DIFF_PAIRS:
                app_logger.info(f"Configuring LabJack differential pairs for summed load cell: {config.LABJACK_LOADCELL_DIFF_PAIRS}")
                for pos_ch, neg_ch_name_part in config.LABJACK_LOADCELL_DIFF_PAIRS:
                    try:
                        neg_ch_num_str = ''.join(filter(str.isdigit, neg_ch_name_part))
                        if not neg_ch_num_str:
                            raise ValueError(f"Could not extract AIN number from negative channel name: {neg_ch_name_part}")
                        neg_ch_num = int(neg_ch_num_str)

                        ljm.eWriteName(self.labjack_handle, f"{pos_ch}_NEGATIVE_CH", neg_ch_num)
                        ljm.eWriteName(self.labjack_handle, f"{pos_ch}_RANGE", 0.01) 
                        app_logger.info(f"LabJack: Configured {pos_ch} with Negative Channel AIN{neg_ch_num}, Range ±0.01V.")
                    except ValueError as ve:
                        app_logger.error(f"ValueError configuring LabJack channel {pos_ch} with {neg_ch_name_part}: {ve}")
                    except ljm.LJMError as ljme:
                         app_logger.error(f"LJMError configuring LabJack channel {pos_ch} with {neg_ch_name_part}: {ljme} (Code: {ljme.errorCode})")
                app_logger.info("LabJack differential channels configuration attempt finished.")
            else:
                app_logger.warning("LABJACK_LOADCELL_DIFF_PAIRS not defined or empty in config. No LabJack load cell channels configured.")
        except ljm.LJMError as e:
            app_logger.error(f"LJMError during LabJack channel configuration phase: {e} (Code: {e.errorCode})")
        except Exception as e:
            app_logger.error(f"Unexpected error during LabJack channel configuration phase: {e}")

    def _apply_differential_scaling_labjack(self, voltage: float) -> float:
        try:
            scaled_value = (-(float(voltage) * 51412.0) + 2.0204) / 0.45359237
            return scaled_value
        except Exception as e:
            app_logger.error(f"Error applying LabJack differential scaling to voltage {voltage}: {e}")
            return 0.0

    @Slot()
    def _read_labjack_data_slot(self):
        if not self.labjack_handle or not ljm or not config.LABJACK_ENABLED:
            if self._labjack_timer and self._labjack_timer.isActive():
                 app_logger.warning("LabJack reading attempted but system not ready or disabled. Stopping LabJack timer.")
                 self._labjack_timer.stop()
            return

        try:
            timestamp = time.time()
            diff_voltages = []
            raw_total_scaled_weight = 0.0 # Renamed to indicate it's pre-tare

            if hasattr(config, 'LABJACK_LOADCELL_DIFF_PAIRS') and config.LABJACK_LOADCELL_DIFF_PAIRS:
                for pos_ch, _ in config.LABJACK_LOADCELL_DIFF_PAIRS:
                    try:
                        voltage = ljm.eReadName(self.labjack_handle, pos_ch)
                        diff_voltages.append(voltage)
                    except ljm.LJMError as e:
                        app_logger.error(f"LJMError reading LabJack channel {pos_ch}: {e} (Code: {e.errorCode})")
                        diff_voltages.append(0.0) 
                        if e.errorCode in [ljm.constants.LJME_DEVICE_NOT_OPEN, ljm.constants.LJME_RECONNECT_FAILED, ljm.constants.LJME_NO_DEVICES_FOUND, ljm.constants.LJME_CONNECTION_HAS_CLOSED]:
                             raise 
                
                scaled_diffs = [self._apply_differential_scaling_labjack(v) for v in diff_voltages]
                raw_total_scaled_weight = sum(scaled_diffs) if scaled_diffs else 0.0
                raw_total_scaled_weight += 66 # Original offset
                
                lc_ui_name = config.LABJACK_SUMMED_LC_NAME
                lc_key_for_raw_cache = f"{lc_ui_name}_LoadCell"
                self._last_raw_sensor_values[lc_key_for_raw_cache] = raw_total_scaled_weight

                # Apply tare offset
                tare_offset = self._lc_tare_offsets.get(lc_ui_name, 0.0)
                tared_total_scaled_weight = raw_total_scaled_weight - tare_offset
                
                sensor_data_logger.info(f"{lc_ui_name},{tared_total_scaled_weight:.2f},{config.LABJACK_LOADCELL_UNIT},LabJackDAQ,LoadCellSummed,0,RAW:{raw_total_scaled_weight:.2f},TARE_OFFSET:{tare_offset:.2f}")

                lj_lc_conf = next((c for c in config.ALL_COMPONENT_CONFIGS if c.get("name") == lc_ui_name and c.get("source_type") == "LabJack"), None)
                lc_ui_unit = config.LABJACK_LOADCELL_UNIT
                lc_ui_board_name = "LabJack DAQ" 

                if lj_lc_conf: 
                    lc_ui_unit = lj_lc_conf.get("unit", config.LABJACK_LOADCELL_UNIT)
                    lc_ui_board_name = lj_lc_conf.get("parent_board_name", "LabJack DAQ")
                
                cache_key_for_ui = f"{lc_ui_name}_LoadCell" # Matches UI expectation
                self._data_cache[cache_key_for_ui] = {
                    "name": lc_ui_name,
                    "value_str": f"{tared_total_scaled_weight:.1f}",
                    "unit": lc_ui_unit,
                    "board": lc_ui_board_name,
                    "type": "LoadCell", 
                    "ts": timestamp
                }
            else:
                app_logger.warning("_read_labjack_data_slot called but no LABJACK_LOADCELL_DIFF_PAIRS configured.")
                if self._labjack_timer and self._labjack_timer.isActive(): self._labjack_timer.stop()
                return

        except ljm.LJMError as e:
            app_logger.error(f"LJMError during LabJack data read processing: {e} (Code: {e.errorCode})")
            if e.errorCode in [ljm.constants.LJME_DEVICE_NOT_OPEN, ljm.constants.LJME_RECONNECT_FAILED, ljm.constants.LJME_NO_DEVICES_FOUND, ljm.constants.LJME_CONNECTION_HAS_CLOSED]:
                app_logger.warning(f"LabJack connection issue (Code: {e.errorCode}). Stopping LabJack timer and attempting to close handle.")
                if self._labjack_timer and self._labjack_timer.isActive(): self._labjack_timer.stop()
                if self.labjack_handle:
                    try: ljm.close(self.labjack_handle)
                    except Exception as close_exc: app_logger.error(f"Error closing already troubled LabJack handle: {close_exc}")
                    self.labjack_handle = None
                self.log_message.emit(f"Error: LabJack connection lost (Code: {e.errorCode}). Please check device.")
        except Exception as e:
            app_logger.error(f"Unexpected error in _read_labjack_data_slot: {e}")
            if self._labjack_timer and self._labjack_timer.isActive(): self._labjack_timer.stop()

    def close_labjack(self):
        if hasattr(self, '_labjack_timer') and self._labjack_timer and self._labjack_timer.isActive():
            self._labjack_timer.stop()
            app_logger.info("LabJack timer stopped.")
        if self.labjack_handle and ljm:
            try:
                app_logger.info("Closing LabJack connection handle.")
                ljm.close(self.labjack_handle)
                self.labjack_handle = None
                self.log_message.emit("LabJack connection closed successfully.")
            except ljm.LJMError as e:
                app_logger.error(f"LJMError closing LabJack: {e} (Code: {e.errorCode})")
                self.log_message.emit(f"Error: LJMError closing LabJack: {e}")
            except Exception as e:
                app_logger.error(f"Unexpected error closing LabJack: {e}")
                self.log_message.emit(f"Error: Unexpected error closing LabJack: {e}")
        else:
            app_logger.info("close_labjack called, but no active LabJack handle or LJM library not available/loaded.")

    def set_ui_update_frequency(self, hz: float):
        if hz > 0:
            interval_ms = int(1000.0 / hz)
            if interval_ms <= 0: interval_ms = 1 
            self._ui_update_timer.setInterval(interval_ms)
            if not self._ui_update_timer.isActive():
                self._ui_update_timer.start()
            app_logger.info(f"UI update frequency set to {hz} Hz ({interval_ms} ms). Timer active: {self._ui_update_timer.isActive()}")
        elif hz == 0: 
            if self._ui_update_timer.isActive():
                self._ui_update_timer.stop()
            app_logger.info("UI update timer stopped (frequency set to 0 Hz).")
        else:
            app_logger.warning(f"Invalid UI update frequency: {hz}. Must be >= 0.")

    def _convert_adc_to_raw_pressure_psi(self, raw_adc_value: int, pt_config: dict) -> float:
        """Converts ADC to PSI without applying tare. Stores raw value."""
        if 'gain' not in pt_config or 'offset' not in pt_config:
            err_msg = f"PT config for '{pt_config.get('name', 'Unknown PT')}' is missing 'gain' or 'offset'. Config: {pt_config}"
            app_logger.error(err_msg)
            # Log and return NaN or raise error. For now, return NaN to avoid crash.
            return float('nan')
        m_coefficient = pt_config['gain']; b_coefficient = pt_config['offset']
        if m_coefficient == 0:
            err_msg =f"Coefficient 'm' (gain) is zero for PT '{pt_config.get('name', 'Unknown PT')}'. Cannot divide by zero."
            app_logger.error(err_msg)
            return float('nan')
        
        pressure_psi_raw = (float(raw_adc_value) - b_coefficient) / m_coefficient
        
        # Store the raw value before taring
        pt_name = pt_config.get('name', f"UNKNOWN_PT_ADC_{raw_adc_value}")
        raw_value_key = f"{pt_name}_PressureTransducer"
        self._last_raw_sensor_values[raw_value_key] = pressure_psi_raw
        
        return pressure_psi_raw

    @Slot(dict)
    def process_incoming_xbee_message(self, message_info):
        timestamp = time.time()
        can_payload_bytes = message_info['can_payload']
        source_xbee_addr = message_info['source_addr_64']

        if len(can_payload_bytes) < 4: 
            app_logger.warning(f"Received XBee payload from {source_xbee_addr} too short for CAN ID: {can_payload_bytes.hex()}")
            return

        can_id_32bit_int = int.from_bytes(can_payload_bytes[:4], 'big')
        can_data_bytes = can_payload_bytes[4:]

        try:
            parsed_id_fields = can_parser.parse_can_id_struct(can_id_32bit_int)
        except ValueError as e:
            app_logger.error(f"Error parsing CAN ID 0x{can_id_32bit_int:08X} from XBee {source_xbee_addr}: {e}")
            return

        is_ack = parsed_id_fields["is_ack"]
        sender_id_from_can = parsed_id_fields["sender_id"]
        sender_name = can_parser.get_sender_name(sender_id_from_can)
        board_id_in_can_field = parsed_id_fields["board_id"]
        board_name_in_can_field = can_parser.get_board_name(board_id_in_can_field)
        component_type_numeric = parsed_id_fields["component_type_id"]
        instance_id = parsed_id_fields["instance_id"]
        component_type_name_from_parser = can_parser.get_component_type_name(component_type_numeric)
        
        board_context_for_component_id = sender_id_from_can
        board_context_for_component_name = sender_name
        
        self.board_connectivity_update.emit(sender_id_from_can, sender_name, timestamp)
        msg_handled = False
        reporting_entity_name_for_system_status = sender_name

        if component_type_numeric == config.MESSAGE_TYPE["MSG_TYPE_BOARD_STATUS_RESPONSE"]:
            reporting_board_id = board_id_in_can_field
            reporting_board_name = can_parser.get_board_name(reporting_board_id)
            self.board_connectivity_update.emit(reporting_board_id, reporting_board_name, timestamp)
            status_data_dict = { "raw_payload_hex": can_data_bytes.hex() }
            log_msg = (f"BOARD_STATUS_RESPONSE from Board ID 0x{reporting_board_id:02X} ({reporting_board_name}) "
                       f"(via XBee {source_xbee_addr}): {status_data_dict}")
            app_logger.info(log_msg); self.log_message.emit(log_msg)
            self.ui_update_board_detailed_status.emit(reporting_board_id, reporting_board_name, source_xbee_addr, status_data_dict)
            msg_handled = True
        elif component_type_numeric == config.MESSAGE_TYPE["MSG_TYPE_ACK_GENERIC"]:
            acked_by_board_id = board_id_in_can_field
            acked_by_board_name = board_name_in_can_field
            log_msg = (f"GENERIC_ACK received. CAN_ID Board field (ACK sender): {acked_by_board_name} (0x{acked_by_board_id:02X}). "
                       f"CAN_ID Original Sender/Context field: {board_context_for_component_name} (0x{board_context_for_component_id:02X}). "
                       f"Payload: {can_data_bytes.hex() if can_data_bytes else 'None'}")
            app_logger.info(log_msg)
            self.log_message.emit(log_msg)
            if not can_data_bytes: msg_handled = True
        elif component_type_numeric == config.MESSAGE_TYPE["MSG_TYPE_IGNITER_STATUS"]:
            if len(can_data_bytes) >= 1:
                state_val = can_data_bytes[0]; state_str = config.IGNITER_STATES.get(state_val, f"Unknown ({state_val})"); is_active = (state_val == 2) 
                self.ui_update_igniter_status.emit("Igniter", is_active, state_str, reporting_entity_name_for_system_status)
                app_logger.info(f"IGNITER_STATUS from {reporting_entity_name_for_system_status}: {state_str}"); msg_handled = True
            else: app_logger.warning(f"Igniter Status data too short from {reporting_entity_name_for_system_status}: {can_data_bytes.hex()}")
        elif component_type_numeric == config.MESSAGE_TYPE["MSG_TYPE_AUTO_MODE_STATUS"]:
            if len(can_data_bytes) >= 1:
                state_val = can_data_bytes[0]; state_str = config.ON_OFF_STATES.get(state_val, f"Unknown ({state_val})"); is_on = (state_val == 1)
                self.ui_update_auto_mode_status.emit("AutoMode", is_on, state_str, reporting_entity_name_for_system_status)
                app_logger.info(f"AUTO_MODE_STATUS from {reporting_entity_name_for_system_status}: {state_str}"); msg_handled = True
            else: app_logger.warning(f"Auto Mode Status data too short from {reporting_entity_name_for_system_status}: {can_data_bytes.hex()}")
        elif component_type_numeric == config.MESSAGE_TYPE["MSG_TYPE_SERVOS_POWER_STATUS"]:
            if len(can_data_bytes) >= 1:
                state_val = can_data_bytes[0]; state_str = config.ON_OFF_STATES.get(state_val, f"Unknown ({state_val})"); is_on = (state_val == 1)
                self.ui_update_servos_power_status.emit("ServosPower", is_on, state_str, reporting_entity_name_for_system_status)
                app_logger.info(f"SERVOS_POWER_STATUS from {reporting_entity_name_for_system_status}: {state_str}"); msg_handled = True
            else: app_logger.warning(f"Servos Power Status data too short from {reporting_entity_name_for_system_status}: {can_data_bytes.hex()}")
        elif component_type_numeric == config.MESSAGE_TYPE["MSG_TYPE_BREAKWIRE_STATUS"]:
            if len(can_data_bytes) >= 1:
                state_val = can_data_bytes[0]; state_str = config.BREAKWIRE_STATES.get(state_val, f"Unknown ({state_val})")
                self.ui_update_breakwire_status.emit("Breakwire", state_val, state_str, reporting_entity_name_for_system_status)
                app_logger.info(f"BREAKWIRE_STATUS from {reporting_entity_name_for_system_status}: {state_str} (Raw: {state_val})"); msg_handled = True
            else: app_logger.warning(f"Breakwire Status data too short from {reporting_entity_name_for_system_status}: {can_data_bytes.hex()}")
        elif component_type_numeric == config.MESSAGE_TYPE["MSG_TYPE_PC_STATE_STATUS"]:
            if len(can_data_bytes) >= 1:
                state_val = can_data_bytes[0]; state_str = config.PC_STATES.get(state_val, f"Unknown ({state_val})")
                self.ui_update_pc_state_status.emit("PCState", state_val, state_str, reporting_entity_name_for_system_status)
                app_logger.info(f"PC_STATE_STATUS from {reporting_entity_name_for_system_status}: {state_str} ({state_val})"); msg_handled = True
            else: app_logger.warning(f"PC State Status data too short from {reporting_entity_name_for_system_status}: {can_data_bytes.hex()}")
        elif component_type_numeric == config.MESSAGE_TYPE["MSG_TYPE_PRESSURE"]:
            if len(can_data_bytes) == 2:
                try:
                    raw_adc_value = struct.unpack('>H', can_data_bytes)[0]
                    value_str, unit = "N/A", "PSI"
                    pressure_psi_raw, tared_pressure_psi = float('nan'), float('nan')
                    tare_offset_used = 0.0

                    found_pt_config = next((pt_conf for pt_conf in config.PT_LOOKUP_TABLE
                                            if pt_conf.get("data_message_sender_name") == board_context_for_component_name and
                                               pt_conf.get("data_message_instance_id") == instance_id), None)
                    
                    actual_sensor_name_for_ui = f"PT_{board_context_for_component_name}_I{instance_id}"
                    if found_pt_config:
                        actual_sensor_name_for_ui = found_pt_config.get("name", actual_sensor_name_for_ui)
                        unit = found_pt_config.get("unit", "PSI")
                        try:
                            pressure_psi_raw = self._convert_adc_to_raw_pressure_psi(raw_adc_value, found_pt_config)
                            tare_offset_used = self._pt_tare_offsets.get(actual_sensor_name_for_ui, 0.0)
                            tared_pressure_psi = pressure_psi_raw - tare_offset_used
                            value_str = f"{tared_pressure_psi:.2f}"
                        except ValueError as e: # From _convert_adc_to_raw_pressure_psi if config bad
                            app_logger.error(f"Error converting ADC for {actual_sensor_name_for_ui}: {e}")
                            value_str = "Conv. Error"
                    else:
                        app_logger.warning(f"PT msg from {board_context_for_component_name} (Inst {instance_id}) - no specific PT config found. Raw ADC: {raw_adc_value}")
                        value_str = f"Raw: {raw_adc_value}"

                    cache_key = f"{actual_sensor_name_for_ui}_PressureTransducer"
                    self._data_cache[cache_key] = {
                        "name": actual_sensor_name_for_ui, "value_str": value_str, "unit": unit,
                        "board": board_context_for_component_name, "type": "PressureTransducer", "ts": timestamp
                    }
                    log_psi_val_str = f"{tared_pressure_psi:.2f}" if not (isinstance(tared_pressure_psi, float) and tared_pressure_psi != tared_pressure_psi) else "NaN"
                    sensor_data_logger.info(f"{actual_sensor_name_for_ui},{log_psi_val_str},{unit},{board_context_for_component_name},PressureTransducer,{instance_id},RAW:{pressure_psi_raw:.2f},TARE_OFFSET:{tare_offset_used:.2f}")
                    msg_handled = True
                except struct.error as e:
                    app_logger.error(f"Error unpacking PT ADC value for {board_context_for_component_name} (Inst {instance_id}): {e}. Data: {can_data_bytes.hex()}")
                except Exception as e:
                    app_logger.error(f"General error processing PT message for {board_context_for_component_name} (Inst {instance_id}): {e}. Data: {can_data_bytes.hex()}")
            else:
                app_logger.warning(f"PT message from {board_context_for_component_name} (Inst {instance_id}) incorrect data len. Expected 2, got {len(can_data_bytes)}. Data: {can_data_bytes.hex()}")

        if not msg_handled:
            component_config_can = can_parser.get_component_info_by_id_tuple(
                board_context_for_component_id, component_type_numeric, instance_id
            )

            if component_config_can is None and component_type_numeric == config.MESSAGE_TYPE["MSG_TYPE_SERVO"]:
                app_logger.debug(f"Servo message for Board {board_context_for_component_name} ({board_context_for_component_id}), Inst {instance_id} "
                                 f"has no exact config match by (Board, Type, Message_Instance). Trying fallback lookup by BoardID only.")
                found_servo_configs = []
                if hasattr(config, 'ALL_COMPONENTS_LOOKUP'):
                    for key_tuple, config_item_val in config.ALL_COMPONENTS_LOOKUP.items():
                        lookup_board_id, _, _ = key_tuple 
                        if lookup_board_id == board_context_for_component_id and config_item_val.get("type") == "Servo":
                            found_servo_configs.append(config_item_val)
                else:
                    app_logger.warning("config.ALL_COMPONENTS_LOOKUP not found. Cannot perform servo fallback.")

                if len(found_servo_configs) == 1:
                    component_config_can = found_servo_configs[0] 
                    original_instance_id_in_config = (component_config_can["can_id"] & config.CAN_ID_INSTANCE_MASK) >> config.CAN_ID_INSTANCE_SHIFT
                    app_logger.info(f"Fallback successful: Mapping Servo message (Board {board_context_for_component_name}, Message Inst {instance_id}) "
                                    f"to configured Servo '{component_config_can['name']}' (Config Inst {original_instance_id_in_config}).")
                elif len(found_servo_configs) > 1:
                    strict_match_found = False
                    for cfg in found_servo_configs:
                        cfg_inst_id = (cfg["can_id"] & config.CAN_ID_INSTANCE_MASK) >> config.CAN_ID_INSTANCE_SHIFT
                        if cfg_inst_id == instance_id: 
                            component_config_can = cfg 
                            strict_match_found = True
                            app_logger.info(f"Fallback successful (multiple servos, matched instance): Mapping Servo message (Board {board_context_for_component_name}, Message Inst {instance_id}) "
                                            f"to configured Servo '{component_config_can['name']}' (Config Inst {cfg_inst_id}).")
                            break
                    if not strict_match_found:
                        app_logger.warning(f"Servo message fallback: Found {len(found_servo_configs)} servos for Board {board_context_for_component_name}. "
                                           f"Message Inst {instance_id} did not uniquely match a configured servo instance. Cannot map.")
                elif not found_servo_configs: 
                    app_logger.warning(f"Servo message fallback failed: No servos configured for Board {board_context_for_component_name} ({board_context_for_component_id}).")
            
            if component_config_can:
                comp_name = component_config_can["name"]
                comp_type_name_from_config = component_config_can["type"]
                
                value_str, unit = "N/A", ""
                processed_value_for_log = None 
                raw_value_for_log = None # For sensor_data_logger
                tare_offset_for_log = 0.0 # For sensor_data_logger
                
                cache_key_instance_part = ""
                if "can_id" in component_config_can and comp_type_name_from_config == "Servo": 
                    config_inst_id_from_can = (component_config_can["can_id"] & config.CAN_ID_INSTANCE_MASK) >> config.CAN_ID_INSTANCE_SHIFT
                    cache_key = f"{comp_name}_{comp_type_name_from_config}_{config_inst_id_from_can}"
                else: 
                    cache_key = f"{comp_name}_{comp_type_name_from_config}"


                if comp_type_name_from_config == "Servo":
                    if len(can_data_bytes) >= 1:
                        state_val = can_data_bytes[0]
                        value_str = config.SERVO_STATES.get(state_val, f"Raw State: {state_val}")
                        processed_value_for_log = value_str # For servos, the state string is the "value"
                        self.ui_update_servo.emit(comp_name, value_str, board_context_for_component_name, comp_type_name_from_config)
                        self._data_cache[cache_key] = {"name": comp_name, "value_str": value_str, "board": board_context_for_component_name, "type": comp_type_name_from_config, "ts": timestamp}
                        msg_handled = True
                    else: app_logger.warning(f"Servo {comp_name} (CAN) data too short: {can_data_bytes.hex()}")

                elif comp_type_name_from_config == "Thermocouple":
                    unit = component_config_can.get('unit', "°C")
                    if len(can_data_bytes) >= 4:
                        try:
                            temperature_raw = struct.unpack('>f', can_data_bytes[:4])[0]
                            # Note: TCs usually aren't tared in this context, but if they were, logic would go here.
                            # For now, raw is the same as processed for TCs.
                            self._last_raw_sensor_values[f"{comp_name}_Thermocouple"] = temperature_raw
                            processed_value_for_log = temperature_raw # Value to log
                            raw_value_for_log = temperature_raw
                            tare_offset_for_log = 0.0 # Assuming no tare for TCs

                            value_str = f"{temperature_raw:.2f}"
                            self._data_cache[cache_key] = {"name": comp_name, "value_str": value_str, "unit": unit, "board": board_context_for_component_name, "type": comp_type_name_from_config, "ts": timestamp}
                            msg_handled = True
                        except struct.error: app_logger.warning(f"TC {comp_name} (CAN) data invalid format for float: {can_data_bytes[:4].hex()}")
                    else: app_logger.warning(f"TC {comp_name} (CAN) data too short for float: {can_data_bytes.hex()}")
                
                elif comp_type_name_from_config == "LoadCell": # CAN Load Cells
                    if config.LABJACK_ENABLED and hasattr(config, 'LABJACK_SUMMED_LC_NAME') and comp_name == config.LABJACK_SUMMED_LC_NAME:
                        app_logger.info(f"Ignoring CAN message for LoadCell '{comp_name}' as it is configured to be sourced from LabJack.")
                    else:
                        unit = component_config_can.get('unit', "lbf")
                        if len(can_data_bytes) >= 4:
                             try:
                                 load_value_raw = struct.unpack('>f', can_data_bytes[:4])[0]
                                 self._last_raw_sensor_values[f"{comp_name}_LoadCell"] = load_value_raw
                                 
                                 tare_offset = self._lc_tare_offsets.get(comp_name, 0.0)
                                 tared_load_value = load_value_raw - tare_offset
                                 
                                 processed_value_for_log = tared_load_value # Value to log
                                 raw_value_for_log = load_value_raw
                                 tare_offset_for_log = tare_offset

                                 value_str = f"{tared_load_value:.1f}"
                                 self._data_cache[cache_key] = {"name": comp_name, "value_str": value_str, "unit": unit, "board": board_context_for_component_name, "type": comp_type_name_from_config, "ts": timestamp}
                                 msg_handled = True
                             except struct.error: app_logger.warning(f"LC {comp_name} (CAN) data invalid struct for float: {can_data_bytes.hex()}")
                        else: app_logger.warning(f"LC {comp_name} (CAN) data too short for float: {can_data_bytes.hex()}")

                elif comp_type_name_from_config == "Heater": 
                    unit = "Status"
                    status_byte, current_temp_str, temp_val_for_log_combined = None, "", None 
                    if len(can_data_bytes) >= 1:
                        status_byte = can_data_bytes[0]
                        status_str = "ON" if status_byte == 1 else "OFF"
                        value_str = f"State: {status_str}"
                        temp_val_for_log_combined = status_str 

                        if len(can_data_bytes) >= 3:
                            try:
                                raw_temp_adc = struct.unpack('>h', can_data_bytes[1:3])[0]
                                temp_scale_factor = component_config_can.get("temp_scale_factor", 10.0)
                                current_temp_raw = float(raw_temp_adc) / temp_scale_factor
                                # Heaters typically aren't tared for temp, but storing raw if needed
                                self._last_raw_sensor_values[f"{comp_name}_Heater_Temp"] = current_temp_raw 
                                current_temp_str = f", Temp: {current_temp_raw:.1f}°C"
                                value_str += current_temp_str
                                temp_val_for_log_combined += f", Temp: {current_temp_raw:.1f}" 
                            except struct.error: app_logger.warning(f"Heater {comp_name} (CAN) temp data invalid format: {can_data_bytes[1:3].hex()}")
                        
                        processed_value_for_log = value_str # For heaters, log the combined string
                        raw_value_for_log = processed_value_for_log # No separate raw for this complex type logging
                        tare_offset_for_log = 0.0

                        self._data_cache[cache_key] = {"name": comp_name, "value_str": value_str, "unit": unit, "board": board_context_for_component_name, "type": comp_type_name_from_config, "ts": timestamp}
                        msg_handled = True
                    else: app_logger.warning(f"Heater {comp_name} (CAN) data too short: {can_data_bytes.hex()}")

                if msg_handled and processed_value_for_log is not None:
                    log_val_str = f'"{processed_value_for_log}"' if isinstance(processed_value_for_log, str) else f"{processed_value_for_log:.2f}" if isinstance(processed_value_for_log, float) else str(processed_value_for_log)
                    
                    # Add raw and tare offset to sensor data log if available
                    extra_log_info = ""
                    if raw_value_for_log is not None:
                        raw_val_log_str = f'"{raw_value_for_log}"' if isinstance(raw_value_for_log, str) else f"{raw_value_for_log:.2f}" if isinstance(raw_value_for_log, float) else str(raw_value_for_log)
                        extra_log_info += f",RAW:{raw_val_log_str}"
                    if tare_offset_for_log != 0.0 or comp_type_name_from_config in ["PressureTransducer", "LoadCell"]: # Log tare even if zero for PT/LC
                        extra_log_info += f",TARE_OFFSET:{tare_offset_for_log:.2f}"

                    sensor_data_logger.info(f"{comp_name},{log_val_str},{unit},{board_context_for_component_name},{comp_type_name_from_config},{instance_id}{extra_log_info}")
                    app_logger.debug(f"Processed CAN Component: {comp_name} ({comp_type_name_from_config} on {board_context_for_component_name}, Msg Inst {instance_id}) -> {value_str} {unit}.")

            if not msg_handled:
                state_info = "" 
                if component_type_numeric == config.MESSAGE_TYPE["MSG_TYPE_SERVO"] and can_data_bytes:
                    state_val = can_data_bytes[0]; state_str = config.SERVO_STATES.get(state_val, f"Raw State {state_val}"); state_info = f" State: {state_str}"
                
                is_simple_ack = component_type_numeric == config.MESSAGE_TYPE["MSG_TYPE_ACK_GENERIC"] and not can_data_bytes

                if not is_simple_ack: 
                    app_logger.warning(f"No component config or specific handler for Msg Type {component_type_numeric} ('{component_type_name_from_parser}') "
                                       f"from Original Sender/Context: {board_context_for_component_name} (0x{board_context_for_component_id:02X}), "
                                       f"Board Field in CAN ID: {board_name_in_can_field} (0x{board_id_in_can_field:02X}), Message Inst {instance_id}. "
                                       f"XBee Src: {source_xbee_addr}. Data: {can_data_bytes.hex()}.{state_info}")

    def _on_ui_update_timer_timeout(self):
        if not self._data_cache:
            return
        try:
            for key, data_item in list(self._data_cache.items()):
                if data_item["type"] in ["Thermocouple", "PressureTransducer", "Heater", "LoadCell"]:
                    self.ui_update_sensor.emit(
                        data_item["name"],
                        data_item["value_str"],
                        data_item.get("unit","N/A"), 
                        data_item["board"],
                        data_item["type"]
                    )
        except Exception as e:
            app_logger.error(f"Error during UI update timer timeout: {e}")

    @Slot()
    def tare_all_pressure_transducers(self):
        app_logger.info("Attempting to tare all configured Pressure Transducers.")
        self.log_message.emit("Taring all Pressure Transducers...")
        tared_count = 0
        for pt_conf in config.PT_LOOKUP_TABLE:
            pt_name = pt_conf['name']
            raw_value_key = f"{pt_name}_PressureTransducer"
            if raw_value_key in self._last_raw_sensor_values:
                raw_value_to_tare_with = self._last_raw_sensor_values[raw_value_key]
                self._pt_tare_offsets[pt_name] = raw_value_to_tare_with
                self.log_message.emit(f"PT '{pt_name}' tared with offset: {raw_value_to_tare_with:.2f} {pt_conf.get('unit','PSI')}.")
                app_logger.info(f"PT '{pt_name}' tared. New offset: {raw_value_to_tare_with:.2f}")
                tared_count += 1
                
                # Trigger an immediate update for this PT with the new tare
                tare_offset = self._pt_tare_offsets.get(pt_name, 0.0)
                tared_value = raw_value_to_tare_with - tare_offset # This will be 0.0
                
                # Update data_cache and emit signal
                ui_cache_key = f"{pt_name}_PressureTransducer" # Matches the key for UI elements
                self._data_cache[ui_cache_key] = {
                    "name": pt_name,
                    "value_str": f"{tared_value:.2f}",
                    "unit": pt_conf.get("unit", "PSI"),
                    "board": pt_conf.get("parent_board_name", "Unknown Board"), # Get board name from PT config
                    "type": "PressureTransducer",
                    "ts": time.time()
                }
                # No direct emit here, _on_ui_update_timer_timeout will pick it up.
                # Or, if immediate UI update is desired:
                # self.ui_update_sensor.emit(pt_name, f"{tared_value:.2f}", pt_conf.get("unit", "PSI"),
                #                           pt_conf.get("parent_board_name", "Unknown Board"), "PressureTransducer")

            else:
                self.log_message.emit(f"Cannot tare PT '{pt_name}': No recent raw value.")
                app_logger.warning(f"Cannot tare PT '{pt_name}': No recent raw value in _last_raw_sensor_values for key '{raw_value_key}'.")
        if tared_count == 0:
            self.log_message.emit("No Pressure Transducers had recent data to tare.")
        else:
            self.log_message.emit(f"Taring complete for {tared_count} PT(s). Next UI update will reflect changes.")


    @Slot()
    def tare_all_load_cells(self):
        app_logger.info("Attempting to tare all configured Load Cells (CAN and LabJack).")
        self.log_message.emit("Taring all Load Cells...")
        tared_count = 0

        # Tare CAN Load Cells
        for lc_conf in config.LOADCELL_LOOKUP_TABLE: # Iterate CAN LC configs
            lc_name = lc_conf['name']
            raw_value_key = f"{lc_name}_LoadCell"
            if raw_value_key in self._last_raw_sensor_values:
                raw_value_to_tare_with = self._last_raw_sensor_values[raw_value_key]
                self._lc_tare_offsets[lc_name] = raw_value_to_tare_with
                self.log_message.emit(f"CAN LC '{lc_name}' tared with offset: {raw_value_to_tare_with:.1f} {lc_conf.get('unit','lbf')}.")
                app_logger.info(f"CAN LC '{lc_name}' tared. New offset: {raw_value_to_tare_with:.1f}")
                tared_count += 1
                
                # Trigger update for this LC
                tare_offset = self._lc_tare_offsets.get(lc_name, 0.0)
                tared_value = raw_value_to_tare_with - tare_offset
                ui_cache_key = f"{lc_name}_LoadCell"
                self._data_cache[ui_cache_key] = {
                    "name": lc_name, "value_str": f"{tared_value:.1f}", "unit": lc_conf.get("unit", "lbf"),
                    "board": lc_conf.get("parent_board_name", "Unknown Board"), "type": "LoadCell", "ts": time.time()
                }
            else:
                self.log_message.emit(f"Cannot tare CAN LC '{lc_name}': No recent raw value.")
                app_logger.warning(f"Cannot tare CAN LC '{lc_name}': No recent raw value for key '{raw_value_key}'.")

        # Tare LabJack Load Cell (if enabled)
        if config.LABJACK_ENABLED and hasattr(config, 'LABJACK_SUMMED_LC_NAME'):
            lj_lc_name = config.LABJACK_SUMMED_LC_NAME
            raw_value_key_lj = f"{lj_lc_name}_LoadCell"
            if raw_value_key_lj in self._last_raw_sensor_values:
                raw_value_to_tare_with_lj = self._last_raw_sensor_values[raw_value_key_lj]
                self._lc_tare_offsets[lj_lc_name] = raw_value_to_tare_with_lj
                self.log_message.emit(f"LabJack LC '{lj_lc_name}' tared with offset: {raw_value_to_tare_with_lj:.1f} {config.LABJACK_LOADCELL_UNIT}.")
                app_logger.info(f"LabJack LC '{lj_lc_name}' tared. New offset: {raw_value_to_tare_with_lj:.1f}")
                tared_count += 1

                # Trigger update for LabJack LC
                tare_offset_lj = self._lc_tare_offsets.get(lj_lc_name, 0.0)
                tared_value_lj = raw_value_to_tare_with_lj - tare_offset_lj
                ui_cache_key_lj = f"{lj_lc_name}_LoadCell"
                self._data_cache[ui_cache_key_lj] = {
                    "name": lj_lc_name, "value_str": f"{tared_value_lj:.1f}", "unit": config.LABJACK_LOADCELL_UNIT,
                    "board": "LabJack DAQ", "type": "LoadCell", "ts": time.time()
                }
            else:
                self.log_message.emit(f"Cannot tare LabJack LC '{lj_lc_name}': No recent raw value.")
                app_logger.warning(f"Cannot tare LabJack LC '{lj_lc_name}': No recent raw value for key '{raw_value_key_lj}'.")
        
        if tared_count == 0:
            self.log_message.emit("No Load Cells had recent data to tare.")
        else:
             self.log_message.emit(f"Taring complete for {tared_count} LC(s). Next UI update will reflect changes.")