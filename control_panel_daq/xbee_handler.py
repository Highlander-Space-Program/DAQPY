# xbee_handler.py
import sys
import re
import time
import threading
from serial.tools import list_ports
from digi.xbee.devices import XBeeDevice, RemoteXBeeDevice, XBee64BitAddress, XBee16BitAddress
from digi.xbee.packets.common import ReceivePacket, TransmitStatusPacket, ModemStatusPacket
from digi.xbee.packets.base import XBeePacket
from digi.xbee.models.status import TransmitStatus, ModemStatus
from digi.xbee.exception import TimeoutException, XBeeException, InvalidOperatingModeException, \
                                 InvalidConfigurationException, XBeeDeviceException, TransmitException
from PySide6.QtCore import QObject, Signal, QTimer
import config  # Ensure this imports your updated config.py
from logger_setup import app_logger, xbee_packet_logger

class XBeeManager(QObject):
    xbee_connected = Signal(str)
    xbee_disconnected = Signal(str)
    connection_error = Signal(str)
    message_received = Signal(dict)
    transmit_status_update = Signal(dict)
    log_message = Signal(str)
    radio_status_updated = Signal(dict) # Emits dict of a single radio's status
    
    DEDICATED_HEALTH_CHECK_INTERVAL_MS = 15000 # For individual lost radios
    SUBSEQUENT_BOARD_STATUS_DELAY_MS = 250 # Delay for board status request after a command

    def __init__(self, parent=None):
        super().__init__(parent)
        self.device = None
        self.port = None
        self.baud_rate = config.XBEE_BAUD_RATE
        self._is_connected = False
        
        self._pending_transmissions = {}
        self._pending_transmissions_lock = threading.Lock()
        self._connection_lock = threading.RLock()
        
        self.target_radios_status = {}
        for name, addr in config.XBEE_TARGET_RADIO_CONFIG:
            self.target_radios_status[addr.upper()] = {
                "name": name,
                "address": addr.upper(),
                "is_alive": False,
                "is_active_for_sending": True, 
                "last_seen": 0.0,
                "last_ni": "N/A",
                "last_tx_status": "N/A",
                "last_tx_description": "N/A",
                "last_tx_retries": "N/A",
                "is_connection_lost": False, 
                "dedicated_health_check_timer": None 
            }
        
        self._radio_healthcheck_timer = QTimer(self)
        self._radio_healthcheck_timer.timeout.connect(self.perform_radio_healthcheck_all_targets)
        
        self._board_status_request_timer = QTimer(self)
        self._board_status_request_timer.timeout.connect(self.request_board_status_all_targets)
        app_logger.info("XBeeManager initialized.")

    def _schedule_subsequent_board_status_request(self, original_command_description: str):
        if not self.is_connected:
            app_logger.info(f"Skipping subsequent board status request after '{original_command_description}': XBee not connected.")
            return
        
        app_logger.info(f"Scheduling subsequent board status request (after {self.SUBSEQUENT_BOARD_STATUS_DELAY_MS}ms) following '{original_command_description}'.")
        QTimer.singleShot(self.SUBSEQUENT_BOARD_STATUS_DELAY_MS, self.request_board_status_all_targets)

    def _usb_serial_ports(self):
        app_logger.debug("Starting USB serial port scan with prioritization...")
        ports_found = list_ports.comports()
        if not ports_found:
            app_logger.warning("No serial ports found by list_ports.comports().")
            return
        known_xbee_adapters = [
            ((0x0403, 0x6001), "FTDI FT232R"),
            ((0x0403, 0x6015), "FTDI FT231X"),
            ((0x10C4, 0xEA60), "Silicon Labs CP210x"),
        ]
        known_usb_manufacturers_lower = ["ftdi", "digi international", "silicon labs", "prolific", "wch.cn", "wch"]
        vid_pid_matches = []
        manufacturer_matches = []
        usb_pattern_matches = []
        other_candidates = []
        processed_devices_set = set()
        app_logger.debug(f"Found {len(ports_found)} raw port entries. Processing and categorizing...")
        for p in ports_found:
            dev_path = p.device
            if sys.platform.startswith("darwin") and dev_path.startswith("/dev/tty."):
                cu_equivalent = dev_path.replace("/dev/tty.", "/dev/cu.", 1)
                if cu_equivalent in processed_devices_set:
                    app_logger.debug(f" Skipping '{dev_path}' as its 'cu' equivalent '{cu_equivalent}' might be preferred or already processed.")
                    continue
            if dev_path in processed_devices_set:
                app_logger.debug(f" Skipping already processed device path: {dev_path}")
                continue
            desc = p.description if p.description else "N/A"
            manu = p.manufacturer if p.manufacturer else "N/A"
            vid = p.vid
            pid = p.pid
            hwid = p.hwid if hasattr(p, 'hwid') else "N/A"
            vid_str = f"{vid:#06x}" if vid is not None else "N/A"
            pid_str = f"{pid:#06x}" if pid is not None else "N/A"
            log_line = f" Port: {dev_path} (VID:{vid_str} PID:{pid_str} Manufacturer:'{manu}' Description:'{desc}' HWID:'{hwid}')"
            app_logger.debug(log_line)
            if sys.platform.startswith("darwin") and \
                ("bluetooth" in dev_path.lower() or "bth" in manu.lower() or "bth" in desc.lower() or "airpods" in desc.lower()):
                app_logger.debug(f" Skipping likely Bluetooth/audio port on macOS: {dev_path}")
                processed_devices_set.add(dev_path)
                continue
            categorized = False
            if vid is not None and pid is not None:
                for (known_vid, known_pid), adapter_desc in known_xbee_adapters:
                    if vid == known_vid and pid == known_pid:
                        app_logger.debug(f" Priority 1 (VID/PID): Matches {adapter_desc}.")
                        if dev_path not in vid_pid_matches: vid_pid_matches.append(dev_path)
                        categorized = True
                        break
            if categorized:
                processed_devices_set.add(dev_path)
                continue
            manu_lower = manu.lower()
            for known_m_lower in known_usb_manufacturers_lower:
                if known_m_lower in manu_lower:
                    app_logger.debug(f" Priority 2 (Manufacturer): Matches '{manu}'.")
                    if dev_path not in manufacturer_matches: manufacturer_matches.append(dev_path)
                    categorized = True
                    break
            if categorized:
                processed_devices_set.add(dev_path)
                continue
            is_usb_pattern = False
            if sys.platform.startswith("darwin"):
                if re.match(r"/dev/cu\.(usbserial-\w+|usbmodem\w+|serial\d*|SLAB_USBtoUART|wchusbserial\w*)", dev_path, re.I):
                    is_usb_pattern = True
            elif sys.platform.startswith("linux"):
                if re.match(r"/dev/tty(USB|ACM)\d+", dev_path):
                    is_usb_pattern = True
            elif sys.platform.startswith("win"):
                if "usb" in desc.lower() or \
                    (hasattr(p, 'hwid') and "usb" in p.hwid.lower()) or \
                    "com" in dev_path.lower(): 
                    is_usb_pattern = True
            if is_usb_pattern:
                app_logger.debug(f" Priority 3 (USB Pattern): Matches USB-like pattern for {sys.platform}.")
                if dev_path not in usb_pattern_matches: usb_pattern_matches.append(dev_path)
                categorized = True
            if categorized:
                processed_devices_set.add(dev_path)
                continue
            
            app_logger.debug(f" Priority 4 (Other): Adding '{dev_path}' as a general candidate.")
            if dev_path not in other_candidates: other_candidates.append(dev_path)
            processed_devices_set.add(dev_path)
        yielded_this_scan = set()
        app_logger.debug("Yielding ports by priority:")
        for port_path in vid_pid_matches:
            if port_path not in yielded_this_scan:
                app_logger.debug(f" Yielding (P1 - VID/PID): {port_path}")
                yield port_path
                yielded_this_scan.add(port_path)
        for port_path in manufacturer_matches:
            if port_path not in yielded_this_scan:
                app_logger.debug(f" Yielding (P2 - Manufacturer): {port_path}")
                yield port_path
                yielded_this_scan.add(port_path)
        for port_path in usb_pattern_matches:
            if port_path not in yielded_this_scan:
                app_logger.debug(f" Yielding (P3 - USB Pattern): {port_path}")
                yield port_path
                yielded_this_scan.add(port_path)
        
        for port_path in other_candidates:
            if port_path not in yielded_this_scan:
                app_logger.debug(f" Yielding (P4 - Other Candidate): {port_path}")
                yield port_path
                yielded_this_scan.add(port_path)
        if not yielded_this_scan:
            app_logger.warning("No candidate serial ports identified after prioritization and filtering.")
        app_logger.debug("Finished USB serial port scan and prioritization.")

    def _try_port(self, port_path: str) -> bool:
        temp_xb = None
        try:
            app_logger.info(f"Probing port: {port_path} to check for responsive XBee.")
            self.log_message.emit(f"Testing port: {port_path}...")
            temp_xb = XBeeDevice(port_path, self.baud_rate)
            temp_xb.set_sync_ops_timeout(config.XBEE_PROBE_TIMEOUT_S)
            app_logger.info(f"Opening {port_path} (Baud: {self.baud_rate}, Probe Timeout: {config.XBEE_PROBE_TIMEOUT_S}s)")
            temp_xb.open()
            app_logger.info(f"Successfully opened {port_path}. Querying basic parameters (NI, VR, HV)...")
            ni = temp_xb.get_node_id()
            fw_version_bytes = temp_xb.get_parameter("VR")
            hw_version_bytes = temp_xb.get_parameter("HV")
            fw_hex = fw_version_bytes.hex() if fw_version_bytes else "N/A"
            hw_hex = hw_version_bytes.hex() if hw_version_bytes else "N/A"
            app_logger.info(f"Device on {port_path}: NI='{ni}', FW=0x{fw_hex}, HW=0x{hw_hex}. Identified as responsive XBee.")
            self.log_message.emit(f"Found responsive XBee (NI:'{ni}') on {port_path}.")
            app_logger.info(f"Port {port_path} probe successful.")
            return True
        except (TimeoutException, InvalidOperatingModeException) as e:
            app_logger.warning(f"Port {port_path} probe failed (Timeout/Mode Error): {type(e).__name__} - {e}")
            self.log_message.emit(f"No responsive/compatible XBee on {port_path}.")
            return False
        except (InvalidConfigurationException, XBeeException, XBeeDeviceException, OSError) as e:
            app_logger.error(f"Error on {port_path} during XBee probing: {type(e).__name__} - {e}", exc_info=False)
            self.log_message.emit(f"Error probing {port_path}: {str(e)[:100]}")
            return False
        except Exception as e:
            app_logger.error(f"Generic error on port {port_path} during probing: {type(e).__name__} - {e}", exc_info=True)
            self.log_message.emit(f"Unexpected error probing {port_path}: {str(e)[:100]}")
            return False
        finally:
            if temp_xb and temp_xb.is_open():
                app_logger.debug(f"Closing temporary XBee device for {port_path} in _try_port finally block.")
                try:
                    temp_xb.close()
                except Exception as e_close:
                    app_logger.error(f"Error closing temp_xb for {port_path} in _try_port finally: {e_close}")

    def autodetect_and_connect(self):
        with self._connection_lock:
            if self._is_connected:
                app_logger.info("Autodetect called, but already connected. Skipping.")
                return True
            app_logger.info("Attempting to autodetect and connect to XBee device.")
            self.log_message.emit("Autodetecting XBee...")
            ports_tried_count = 0
            for port_path in self._usb_serial_ports():
                ports_tried_count += 1
                app_logger.info(f"--- Testing port: {port_path} (Attempt {ports_tried_count}) ---")
                if self._try_port(port_path):
                    app_logger.info(f"Port {port_path} validated. Attempting final connection.")
                    self.connect_to_device(port_path) 
                    if self._is_connected:
                        app_logger.info(f"Final connection to {port_path} successful.")
                        return True
                    else:
                        app_logger.error(f"connect_to_device failed for validated port {port_path}. Trying next port.")
                else:
                    app_logger.info(f"Port {port_path} is not a responsive/compatible XBee. Skipping.")
                app_logger.info(f"--- Finished testing port: {port_path} ---")
            err_msg = "No XBee radio found or connection failed after checking all candidate ports."
            if ports_tried_count == 0:
                err_msg = "No serial ports found or all were filtered out. Check XBee connection and drivers."
            app_logger.error(err_msg)
            self.connection_error.emit(err_msg)
            self.log_message.emit(err_msg)
            self._is_connected = False
            return False

    def connect_to_device(self, port_path: str):
        with self._connection_lock:
            app_logger.info(f"connect_to_device called for {port_path}. Current status: connected={self._is_connected}, port={self.port}")
            if self._is_connected and self.port == port_path and self.device and self.device.is_open():
                app_logger.info(f"Already connected to {port_path}. Triggering connected signal again.")
                self.xbee_connected.emit(self.port)
                return
            if self.device and self.device.is_open():
                app_logger.info(f"Switching connection. Disconnecting from previous port {self.port} first.")
                self._close_current_device() 
            self.port = port_path
            app_logger.info(f"Attempting to establish main connection to XBee on {self.port} at {self.baud_rate} baud.")
            self.log_message.emit(f"Connecting to {self.port}...")
            try:
                self.device = XBeeDevice(self.port, self.baud_rate)
                app_logger.info(f"Opening main device on {self.port}...")
                self.device.open()
                app_logger.info(f"Main device on {self.port} opened.") 
                
                self.device.set_sync_ops_timeout(config.XBEE_DATA_TIMEOUT_S)
                app_logger.info(f"Set synchronous operation timeout for data messages to {config.XBEE_DATA_TIMEOUT_S}s.")
                try:
                    ni = self.device.get_node_id()
                    app_logger.info(f"Successfully read NI ('{ni}') from XBee on {self.port}.")
                except Exception as ni_e:
                    app_logger.warning(f"Could not read NI from {self.port} after open (non-critical): {ni_e}")
                self.device.add_packet_received_callback(self._packet_received_callback)
                self._is_connected = True
                app_logger.info(f"Successfully connected to XBee on {self.port}.")
                self.xbee_connected.emit(self.port)
                self.log_message.emit(f"Connected to XBee on {self.port}")
                if not self._radio_healthcheck_timer.isActive():
                    self._radio_healthcheck_timer.start(config.RADIO_HEALTHCHECK_INTERVAL_MS)
                    app_logger.info(f"Radio healthcheck timer started (Interval: {config.RADIO_HEALTHCHECK_INTERVAL_MS}ms).")
                
                if not self._board_status_request_timer.isActive():
                    interval_ms = getattr(config, 'PERIODIC_BOARD_STATUS_INTERVAL_MS', 3000) 
                    if interval_ms <= 0 : interval_ms = 3000 
                    self._board_status_request_timer.start(interval_ms)
                    app_logger.info(f"Periodic board status request timer started (Interval: {interval_ms}ms).")
                
                QTimer.singleShot(1000, self.perform_radio_healthcheck_all_targets) 
                QTimer.singleShot(1500, self.request_board_status_all_targets) 
            except (XBeeException, XBeeDeviceException, OSError) as e:
                err_msg = f"Failed to connect to XBee on {self.port}: {type(e).__name__} - {e}"
                app_logger.error(err_msg, exc_info=False)
                self.connection_error.emit(err_msg)
                self.log_message.emit(f"Connection error on {self.port}: {str(e)[:100]}")
                self._close_current_device(notify_ui=False) 
            except Exception as e:
                err_msg = f"Unexpected error during main connection to {self.port}: {type(e).__name__} - {e}"
                app_logger.error(err_msg, exc_info=True)
                self.connection_error.emit(err_msg)
                self.log_message.emit(f"Unexpected error on {self.port}: {str(e)[:100]}")
                self._close_current_device(notify_ui=False)

    def _close_current_device(self, notify_ui=True):
        port_that_was_disconnected = self.port
        
        if self._radio_healthcheck_timer.isActive():
            self._radio_healthcheck_timer.stop()
            app_logger.info("Radio healthcheck timer stopped.")
        if self._board_status_request_timer.isActive(): 
            self._board_status_request_timer.stop()
            app_logger.info("Periodic board status request timer stopped.")
        for addr, radio_info in self.target_radios_status.items():
            self._stop_dedicated_health_check_timer(addr) 
            radio_info['is_connection_lost'] = False
            if notify_ui and (radio_info['is_alive'] or radio_info['last_ni'] != "N/A (Host Disconnected)"): 
                radio_info['is_alive'] = False
                radio_info['last_ni'] = "N/A (Host Disconnected)"
                radio_info['last_tx_status'] = "N/A"
                self.radio_status_updated.emit(radio_info.copy())
        if self.device:
            if self.device.is_open():
                app_logger.info(f"Closing connection to XBee on {port_that_was_disconnected if port_that_was_disconnected else 'unknown port'}.")
                try:
                    try:
                        self.device.del_packet_received_callback(self._packet_received_callback)
                    except Exception as cb_e:
                        app_logger.debug(f"Note: Error removing packet callback: {cb_e}")
                    self.device.close()
                    app_logger.info(f"Port {port_that_was_disconnected if port_that_was_disconnected else 'N/A'} closed.")
                except (XBeeException, XBeeDeviceException, OSError) as e:
                    app_logger.error(f"Error closing XBee device on {port_that_was_disconnected}: {type(e).__name__} - {e}", exc_info=False)
                except Exception as e:
                    app_logger.error(f"Unexpected error closing XBee device on {port_that_was_disconnected}: {type(e).__name__} - {e}", exc_info=True)
            else:
                app_logger.info(f"Device on {port_that_was_disconnected if port_that_was_disconnected else 'N/A'} was already closed or not fully open.")
        
        self.device = None
        self.port = None
        self._is_connected = False
        
        return port_that_was_disconnected

    def disconnect_device(self):
        with self._connection_lock:
            if not self._is_connected and not self.device: 
                app_logger.info("disconnect_device called, but already disconnected or not initialized.")
                if self.port is not None or any(r['is_alive'] for r in self.target_radios_status.values()):
                    self._close_current_device() 
                    self.xbee_disconnected.emit("Forced cleanup on disconnect call.")
                else:
                    self.xbee_disconnected.emit("Already disconnected or not initialized.")
                return
            app_logger.info("disconnect_device called. Proceeding with disconnection...")
            disconnected_port = self._close_current_device() 
            msg_base = "XBee disconnected"
            if disconnected_port:
                msg = f"{msg_base} from {disconnected_port}."
            else: 
                msg = f"{msg_base} (port unknown or connection failed early)."
            app_logger.info(msg)
            self.log_message.emit(msg)
            self.xbee_disconnected.emit(msg) 

    def _packet_received_callback(self, packet: XBeePacket):
        try:
            packet_type_name = type(packet).__name__
            raw_frame_data_hex = "N/A"
            if hasattr(packet, '_frame_data') and packet._frame_data is not None:
                raw_frame_data_hex = packet._frame_data.hex()
            xbee_packet_logger.info(f"Type={packet_type_name}, RawFrameData={raw_frame_data_hex}, PacketDetails={str(packet)}")
        except Exception as log_e:
            app_logger.error(f"Error during initial XBee packet logging: {log_e}", exc_info=True)
        is_receive_packet = isinstance(packet, ReceivePacket)
        is_tx_status_packet = isinstance(packet, TransmitStatusPacket)
        is_modem_status_packet = isinstance(packet, ModemStatusPacket)
        if is_receive_packet:
            source_addr_64_str = "UNKNOWN_SOURCE_ADDR"
            can_payload = b''
            try:
                if hasattr(packet, 'x64bit_source_addr') and packet.x64bit_source_addr:
                    source_addr_64_str = str(packet.x64bit_source_addr).upper()
                elif hasattr(packet, 'x16bit_source_addr') and packet.x16bit_source_addr: 
                    addr16_int = int.from_bytes(packet.x16bit_source_addr.address, byteorder='big')
                    source_addr_64_str = f"0x{addr16_int:04X} (16-bit Source)"
                else:
                    app_logger.warning("ReceivePacket missing both x64bit_source_addr and x16bit_source_addr.")
                
                if hasattr(packet, 'rf_data'):
                    can_payload = packet.rf_data
                else:
                    app_logger.warning("'ReceivePacket' object has no attribute 'rf_data', payload will be empty.")
                    can_payload = b'' 
                
                # app_logger.info(f"Message from {source_addr_64_str}: Payload len={len(can_payload)}, Hex: {can_payload.hex() if can_payload else 'N/A'}")
                self.message_received.emit({'can_payload': can_payload, 'source_addr_64': source_addr_64_str})
            except Exception as e_rp:
                app_logger.error(f"Error processing fields of ReceivePacket: {e_rp}", exc_info=True)
                final_source_addr = source_addr_64_str if source_addr_64_str != "UNKNOWN_SOURCE_ADDR" else "ERROR_PARSING_ADDR"
                self.message_received.emit({'can_payload': b'', 'source_addr_64': final_source_addr})
        elif is_tx_status_packet:
            actual_fid_from_packet = packet.frame_id 
            status_val_enum = packet.transmit_status
            status_val = status_val_enum.value if hasattr(status_val_enum, 'value') else status_val_enum
            retries = packet.transmit_retry_count
            
            status_name = "Unknown Status"
            try:
                status_name = TransmitStatus(status_val).name
            except ValueError:
                status_name = f"Unknown Code ({status_val})"
            pending_tx_info = None
            with self._pending_transmissions_lock:
                pending_tx_info = self._pending_transmissions.pop(actual_fid_from_packet, None)
            
            original_description = "Unknown Command (FID not matched)" 
            target_64bit_address_str = "UnknownAddr (FID not matched)"
            was_health_check_command = False
            if pending_tx_info:
                original_description = pending_tx_info.get("description", "Description Missing")
                target_64bit_address_str = pending_tx_info.get("address", "AddrMissing").upper()
                was_health_check_command = pending_tx_info.get("is_health_check", False)
                app_logger.info(f"TX Status (FID:{actual_fid_from_packet}) MATCHED for addr {target_64bit_address_str}.")
            else:
                app_logger.warning(f"TX Status (Callback, FID:{actual_fid_from_packet}) received, but no matching send was found.")
                if hasattr(packet, 'x16bit_dest_addr') and packet.x16bit_dest_addr and packet.x16bit_dest_addr.address:
                    try:
                        addr16_int_val = int.from_bytes(packet.x16bit_dest_addr.address, byteorder='big')
                        if addr16_int_val == 0xFFFE: 
                            target_64bit_address_str = str(XBee64BitAddress.BROADCAST_ADDRESS).upper()
                        else:
                            target_64bit_address_str = f"0x{addr16_int_val:04X} (16-bit Unicast, Unmatched FID)"
                    except TypeError:
                        target_64bit_address_str = "Invalid16BitAddrFormat (Unmatched FID)"
            
            delivery_successful = (status_val == TransmitStatus.SUCCESS.value)
            log_entry = (f"TX Status (FID:{actual_fid_from_packet}, Desc:'{original_description}') "
                         f"to Addr:'{target_64bit_address_str}': {status_name}, Retries: {retries}, Delivered: {delivery_successful}, HC: {was_health_check_command}")
            app_logger.info(log_entry)
            
            self.transmit_status_update.emit({
                'frame_id': actual_fid_from_packet, 
                'description': original_description,
                'status': status_name,
                'retries': retries,
                'address': target_64bit_address_str, 
                'delivery_successful': delivery_successful
            })
            if target_64bit_address_str in self.target_radios_status:
                radio_stat = self.target_radios_status[target_64bit_address_str]
                radio_stat['last_tx_status'] = status_name
                radio_stat['last_tx_description'] = original_description 
                radio_stat['last_tx_retries'] = retries
                
                if delivery_successful:
                    radio_stat['last_seen'] = time.time()
                if was_health_check_command:
                    if delivery_successful:
                        radio_stat['is_alive'] = True
                        if radio_stat.get('is_connection_lost', False):
                            app_logger.info(f"Health check SUCCESS for LOST radio {target_64bit_address_str}. Recovered.")
                            radio_stat['is_connection_lost'] = False
                            self._stop_dedicated_health_check_timer(target_64bit_address_str)
                    else: 
                        radio_stat['is_alive'] = False
                        if radio_stat.get('is_active_for_sending', True) and not radio_stat.get('is_connection_lost', False):
                            app_logger.warning(f"Health check FAILED for radio {target_64bit_address_str}. Marking as connection_lost.")
                            radio_stat['is_connection_lost'] = True
                            self._start_dedicated_health_check_timer(target_64bit_address_str)
                
                self.radio_status_updated.emit(radio_stat.copy())
            elif target_64bit_address_str != str(XBee64BitAddress.BROADCAST_ADDRESS).upper() and pending_tx_info : 
                app_logger.warning(f"TX Status for {target_64bit_address_str} (matched) is not in monitored target_radios_status list.")
        elif is_modem_status_packet:
            status_val_enum = packet.status
            status_val = status_val_enum.value if hasattr(status_val_enum, 'value') else status_val_enum
            status_name = f"Code {status_val}"
            try:
                status_name = ModemStatus(status_val).name
            except ValueError:
                pass
            app_logger.info(f"Modem Status: {status_name} (Code: {status_val})")
            self.log_message.emit(f"XBee Modem Status: {status_name}")
            if status_val == ModemStatus.WATCHDOG_TIMER_RESET.value:
                self.log_message.emit("XBee has reset (Watchdog). Auto-reconnect might be needed if comms fail.")
                app_logger.warning("XBee Watchdog Reset detected by Modem Status packet.")
                self.disconnect_device() 
                QTimer.singleShot(2000, self.autodetect_and_connect)
        else:
            app_logger.debug(f"Received unhandled XBeePacket type: {type(packet).__name__}, Details: {str(packet)}")

    def _calculate_tracking_fid(self, fid_from_get_next_frame_id: int) -> int:
        if fid_from_get_next_frame_id == 0xFF:
            return 1
        else:
            return fid_from_get_next_frame_id + 1

    def send_unicast_command(self, target_address_hex_str: str, command_byte_value: int, 
                             command_description: str = "Unicast Command", 
                             is_health_check_command: bool = False,
                             trigger_board_status_after_send: bool = True): # New parameter
        target_address_hex_str_upper = target_address_hex_str.upper()
        if not self.is_connected or not self.device or not self.device.is_open():
            app_logger.error(f"Cannot send '{command_description}' to {target_address_hex_str_upper}: XBee not connected.")
            self.transmit_status_update.emit({
                'frame_id': "N/A", 'description': command_description,
                'status': "Send Fail: Host Not Connected", 'retries': "N/A",
                'address': target_address_hex_str_upper, 'delivery_successful': False
            })
            return False
        if not re.match(r"^[0-9A-F]{16}$", target_address_hex_str_upper):
            app_logger.error(f"Invalid target 64-bit address format for '{command_description}': {target_address_hex_str_upper}")
            self.transmit_status_update.emit({
                'frame_id': "N/A", 'description': command_description,
                'status': "Send Fail: Invalid Address Format", 'retries': "N/A",
                'address': target_address_hex_str_upper, 'delivery_successful': False
            })
            return False
        
        radio_info = self.target_radios_status.get(target_address_hex_str_upper)
        if radio_info and radio_info.get('is_connection_lost', False) and not is_health_check_command:
            app_logger.warning(f"Skipping command '{command_description}' to {target_address_hex_str_upper}: Connection previously lost. Dedicated health checks active.")
            self.transmit_status_update.emit({
                'frame_id': "N/A", 
                'description': command_description,
                'status': "Skipped: Connection Lost", 
                'retries': "N/A",
                'address': target_address_hex_str_upper, 
                'delivery_successful': False
            })
            if radio_info:
                radio_info['last_tx_description'] = command_description
                radio_info['last_tx_status'] = "Skipped: Connection Lost"
                radio_info['last_tx_retries'] = "N/A"
                self.radio_status_updated.emit(radio_info.copy())
            return False
        
        payload = bytes([command_byte_value])
        target_remote_device = None
        try:
            target_address_obj = XBee64BitAddress.from_hex_string(target_address_hex_str_upper)
            target_remote_device = RemoteXBeeDevice(self.device, target_address_obj)
        except Exception as e: 
            app_logger.error(f"Error creating RemoteXBeeDevice for '{target_address_hex_str_upper}' for '{command_description}': {e}")
            self.transmit_status_update.emit({
                'frame_id': "N/A", 'description': command_description,
                'status': f"Send Fail: Remote Device Creation Error", 'retries': "N/A",
                'address': target_address_hex_str_upper, 'delivery_successful': False
            })
            return False
        
        fid_before_internal_increment = self.device.get_next_frame_id()
        fid_to_track = self._calculate_tracking_fid(fid_before_internal_increment)
        
        with self._pending_transmissions_lock:
            self._pending_transmissions[fid_to_track] = {
                "description": command_description,
                "address": target_address_hex_str_upper, 
                "payload_byte": command_byte_value,
                "timestamp": time.time(),
                "is_health_check": is_health_check_command 
            }
        
        app_logger.info(f"Attempting ASYNC unicast (TrackingFID:{fid_to_track}, Desc:'{command_description}', HC:{is_health_check_command}) to {target_address_hex_str_upper}: Payload 0x{command_byte_value:02X}")
        self.log_message.emit(f"Sending (async) '{command_description}' (0x{command_byte_value:02X}) to {target_address_hex_str_upper[-8:]}...")
        try:
            self.device.send_data_async(target_remote_device, payload) 
            app_logger.info(f"Async unicast (TrackedFID:{fid_to_track}) '{command_description}' to {target_address_hex_str_upper} submitted.")
            
            # Check if we should trigger a subsequent board status request
            board_status_req_cmd_val = config.COMMANDS.get("BOARD_STATUS_REQUEST")
            if trigger_board_status_after_send and command_byte_value != board_status_req_cmd_val:
                self._schedule_subsequent_board_status_request(command_description)
            
            return True
        except Exception as e: 
            app_logger.error(f"Error during send_data_async for '{command_description}' (TrackedFID:{fid_to_track}) to {target_address_hex_str_upper}: {type(e).__name__} - {e}", exc_info=True)
            with self._pending_transmissions_lock:
                self._pending_transmissions.pop(fid_to_track, None) 
            
            self.transmit_status_update.emit({
                'frame_id': fid_to_track, 'description': command_description,
                'status': f"Send Init Fail: {type(e).__name__}", 'retries': "N/A",
                'address': target_address_hex_str_upper, 'delivery_successful': False
            })
            if is_health_check_command and radio_info: 
                if radio_info.get('is_active_for_sending', True) and not radio_info.get('is_connection_lost', False):
                    app_logger.warning(f"Health check send submission FAILED for radio {target_address_hex_str_upper}. Marking as connection_lost.")
                    radio_info['is_alive'] = False
                    radio_info['is_connection_lost'] = True
                    radio_info['last_tx_status'] = f"Send Init Fail: {type(e).__name__}"
                    radio_info['last_tx_description'] = command_description
                    radio_info['last_tx_retries'] = "N/A"
                    self._start_dedicated_health_check_timer(target_address_hex_str_upper)
                    self.radio_status_updated.emit(radio_info.copy())
            return False

    def _start_dedicated_health_check_timer(self, address_hex_str: str):
        radio_info = self.target_radios_status.get(address_hex_str)
        if not radio_info:
            app_logger.error(f"Cannot start dedicated health check: Unknown radio {address_hex_str}")
            return
        if radio_info.get("dedicated_health_check_timer") is not None:
            app_logger.debug(f"Dedicated health check timer already exists for {address_hex_str}. Ensuring it's running.")
            radio_info["dedicated_health_check_timer"].start(self.DEDICATED_HEALTH_CHECK_INTERVAL_MS) 
            return
        app_logger.info(f"Starting dedicated health check timer ({self.DEDICATED_HEALTH_CHECK_INTERVAL_MS}ms) for radio {address_hex_str} ({radio_info['name']}).")
        timer = QTimer() 
        timer.setSingleShot(False) 
        timer.timeout.connect(lambda: self._run_dedicated_health_check_for_lost_radio(address_hex_str))
        radio_info["dedicated_health_check_timer"] = timer
        timer.start(self.DEDICATED_HEALTH_CHECK_INTERVAL_MS)
        self.log_message.emit(f"Radio {radio_info['name']} connection lost. Starting {self.DEDICATED_HEALTH_CHECK_INTERVAL_MS / 1000.0:.1f}s health checks.")

    def _stop_dedicated_health_check_timer(self, address_hex_str: str):
        radio_info = self.target_radios_status.get(address_hex_str)
        if radio_info and radio_info.get("dedicated_health_check_timer"):
            app_logger.info(f"Stopping dedicated health check timer for radio {address_hex_str} ({radio_info.get('name', 'Unknown')}).")
            radio_info["dedicated_health_check_timer"].stop()
            radio_info["dedicated_health_check_timer"].deleteLater() 
            radio_info["dedicated_health_check_timer"] = None
            self.log_message.emit(f"Radio {radio_info.get('name', address_hex_str[-4:])} recovered or disabled. Stopping {self.DEDICATED_HEALTH_CHECK_INTERVAL_MS / 1000.0:.1f}s health checks.")

    def _run_dedicated_health_check_for_lost_radio(self, radio_address_hex: str):
        if not self.is_connected:
            app_logger.warning(f"Dedicated health check for {radio_address_hex} skipped: XBee host not connected.")
            self._stop_dedicated_health_check_timer(radio_address_hex) 
            return
        radio_info = self.target_radios_status.get(radio_address_hex)
        if not radio_info:
            app_logger.error(f"Dedicated health check for {radio_address_hex} failed: Radio not found in status list.")
            self._stop_dedicated_health_check_timer(radio_address_hex) 
            return
        if not radio_info.get('is_connection_lost', False):
            app_logger.info(f"Radio {radio_address_hex} no longer marked as connection_lost. Stopping dedicated health check.")
            self._stop_dedicated_health_check_timer(radio_address_hex)
            return
        
        if not radio_info.get('is_active_for_sending', True):
            app_logger.info(f"Dedicated health check for {radio_address_hex} stopped: Radio is user-disabled.")
            self._stop_dedicated_health_check_timer(radio_address_hex) 
            return
        app_logger.info(f"Running dedicated health check for LOST radio: {radio_address_hex} ({radio_info['name']})")
        command_byte = config.COMMANDS["RADIO_HEALTHCHECK"]
        desc = f"Dedicated Healthcheck ({radio_info['name']})"
        self.send_unicast_command(radio_address_hex, command_byte, desc, is_health_check_command=True)

    def perform_radio_healthcheck_all_targets(self):
        if not self.is_connected:
            app_logger.info("Cannot perform global radio healthcheck: Main XBee not connected.")
            return
        app_logger.info("Performing RADIO_HEALTHCHECK for all active configured targets (including those previously marked connection_lost)...")
        command_byte = config.COMMANDS["RADIO_HEALTHCHECK"]
        command_desc_base = "Radio Healthcheck"
        
        targets_to_attempt_check_count = 0
        sent_to_count = 0
        for radio_info in self.target_radios_status.values():
            if radio_info['is_active_for_sending']: 
                targets_to_attempt_check_count +=1
                addr_hex = radio_info['address']
                desc_with_name = f"{command_desc_base} ({radio_info['name']})"
                
                # For this high-level "all targets" function, we let send_unicast_command handle
                # the subsequent board status request logic if it's a single target.
                # However, the intent here is one HC batch followed by one BSR batch.
                # So, if check_all_radio_statuses() is called, it handles the single BSR.
                # This timer-driven one might result in multiple BSRs if not careful.
                # For now, let individual sends trigger it. If it becomes an issue,
                # this method would need similar logic to check_all_radio_statuses:
                # set trigger_board_status_after_send=False and call scheduler once after loop.
                if self.send_unicast_command(addr_hex, command_byte, desc_with_name, 
                                             is_health_check_command=True, 
                                             trigger_board_status_after_send=True): # Explicitly true for now
                    sent_to_count +=1
                time.sleep(0.05)
        
        if targets_to_attempt_check_count == 0:
            self.log_message.emit("No active targets for scheduled Radio Healthcheck.")
        else:
            self.log_message.emit(f"Sent scheduled Radio Healthcheck to {sent_to_count}/{targets_to_attempt_check_count} active target(s).")
        # If we wanted a single board status request after this whole batch:
        # if sent_to_count > 0:
        #    self._schedule_subsequent_board_status_request("Scheduled Radio Healthcheck (All Targets)")


    def request_board_status_all_targets(self):
        if not self.is_connected:
            app_logger.info("Cannot request board status (periodic): Main XBee not connected.")
            return
        
        app_logger.info("Requesting BOARD_STATUS for all active configured target radios (Periodic).")
        
        command_byte = config.COMMANDS["BOARD_STATUS_REQUEST"] 
        command_desc_base = "Periodic Board Status Request"
        active_targets_count = 0
        sent_to_count = 0
        for radio_info in self.target_radios_status.values():
            if radio_info['is_active_for_sending']: 
                active_targets_count += 1
                addr_hex = radio_info['address']
                desc_with_name = f"{command_desc_base} ({radio_info['name']})"
                # When this calls send_unicast_command, the check for command_byte_value
                # will prevent a subsequent board status request from being scheduled.
                if self.send_unicast_command(addr_hex, command_byte, desc_with_name, 
                                             is_health_check_command=False,
                                             trigger_board_status_after_send=True): # Still true, but won't trigger due to cmd type
                    sent_to_count +=1
                time.sleep(0.05) 
        
        if active_targets_count == 0:
            app_logger.info("No active targets for periodic Board Status Request.")
        elif sent_to_count < active_targets_count :
            app_logger.info(f"Attempted periodic Board Status Request for {active_targets_count} active targets. Sent to {sent_to_count}.")
        else: 
            app_logger.info(f"Sent periodic Board Status Request to {sent_to_count}/{active_targets_count} active target(s).")

    def check_all_radio_statuses(self): 
        self.log_message.emit("User requested: Refreshing all radio statuses by sending Healthcheck command...")
        app_logger.info("check_all_radio_statuses called (manual trigger).")
        command_byte = config.COMMANDS["RADIO_HEALTHCHECK"]
        command_desc_base = "Manual Radio Healthcheck"
        sent_count = 0
        active_count = 0
        for radio_info in self.target_radios_status.values():
            if radio_info['is_active_for_sending']:
                active_count +=1
                addr_hex = radio_info['address']
                desc = f"{command_desc_base} ({radio_info['name']})"
                # Pass False to prevent each individual healthcheck from triggering a board status
                if self.send_unicast_command(addr_hex, command_byte, desc, 
                                             is_health_check_command=True, 
                                             trigger_board_status_after_send=False):
                    sent_count +=1
                time.sleep(0.05)
        
        self.log_message.emit(f"Manual Radio Healthcheck: Sent to {sent_count}/{active_count} active radios.")
        if sent_count > 0:
            # Radio healthchecks are not board status requests, so this is safe to call
            self._schedule_subsequent_board_status_request(f"Manual Radio Healthcheck (All Targets - {sent_count} sent)")

    def toggle_radio_sending_activity(self, address_hex_str: str):
        address_hex_str_upper = address_hex_str.upper()
        if address_hex_str_upper in self.target_radios_status:
            current_status = self.target_radios_status[address_hex_str_upper]
            current_status['is_active_for_sending'] = not current_status['is_active_for_sending']
            action = "enabled" if current_status['is_active_for_sending'] else "disabled"
            app_logger.info(f"Radio {current_status['name']} ({address_hex_str_upper[-8:]}) {action} for targeted sends.")
            self.log_message.emit(f"Radio {current_status['name']} {action} for sends.")
            if not current_status['is_active_for_sending'] and current_status.get('is_connection_lost', False):
                app_logger.info(f"Radio {current_status['name']} disabled by user; stopping its dedicated health checks.")
                self._stop_dedicated_health_check_timer(address_hex_str_upper)
            elif current_status['is_active_for_sending'] and current_status.get('is_connection_lost', False):
                if not current_status.get("dedicated_health_check_timer"): 
                    app_logger.info(f"Radio {current_status['name']} re-enabled by user and still marked connection_lost. Restarting dedicated health check.")
                    self._start_dedicated_health_check_timer(address_hex_str_upper) 
            self.radio_status_updated.emit(current_status.copy())
        else:
            app_logger.warning(f"Attempted to toggle activity for unknown radio: {address_hex_str_upper}")

    def send_command_to_configured_targets(self, command_byte_value: int, command_description: str = "Targeted Command"):
        if not self.is_connected or not self.device or not self.device.is_open():
            app_logger.error(f"Cannot send '{command_description}' to targets: XBee not connected.")
            self.log_message.emit("Error: XBee not connected for sending to targets.")
            return
        active_radios_info = [
            radio for radio in self.target_radios_status.values() if radio['is_active_for_sending']
        ]
        if not active_radios_info:
            app_logger.warning(f"No active target radios to send '{command_description}'.")
            self.log_message.emit("Warning: No active radios for targeted send.")
            return
        
        app_logger.info(f"Sending command '{command_description}' (0x{command_byte_value:02X}) to {len(active_radios_info)} active target(s) asynchronously.")
        submission_success_count = 0
        submission_total_attempts = 0 
        skipped_count = 0
        
        for radio_info in active_radios_info:
            addr_hex_str = radio_info['address']
            individual_cmd_desc = f"{command_description} ({radio_info['name']}: {addr_hex_str[-8:]}...)"
            submission_total_attempts+=1
            
            is_lost_before_send = radio_info.get('is_connection_lost', False)
            # Pass False to prevent each individual command from triggering a board status
            if self.send_unicast_command(addr_hex_str, command_byte_value, individual_cmd_desc, 
                                         is_health_check_command=False, 
                                         trigger_board_status_after_send=False):
                submission_success_count += 1
            else: 
                if is_lost_before_send: 
                    skipped_count +=1
            time.sleep(0.05)
            
        failed_submission_count = submission_total_attempts - submission_success_count - skipped_count
        log_msg = (f"Finished submitting '{command_description}'. "
                   f"Attempts: {submission_total_attempts}, Successfully submitted: {submission_success_count}, "
                   f"Skipped (conn. lost): {skipped_count}, Other send init failures: {failed_submission_count}.")
        app_logger.info(log_msg)
        self.log_message.emit(log_msg)

        # If any command was successfully submitted and it wasn't a board status request itself, trigger one now.
        board_status_req_cmd_val = config.COMMANDS.get("BOARD_STATUS_REQUEST")
        if submission_success_count > 0 and command_byte_value != board_status_req_cmd_val:
            self._schedule_subsequent_board_status_request(command_description + " (All Targets)")

    def send_broadcast_command(self, command_byte_value: int, command_description: str = "Generic Command"):
        app_logger.info(f"Preparing ASYNC broadcast for '{command_description}'.")
        
        broadcast_addr_str = str(XBee64BitAddress.BROADCAST_ADDRESS).upper()
        if not self.is_connected or not self.device or not self.device.is_open():
            app_logger.error(f"Cannot send broadcast '{command_description}': XBee not connected.")
            self.transmit_status_update.emit({
                'frame_id': "N/A", 'description': command_description,
                'status': "Send Fail: Host Not Connected", 'retries': "N/A",
                'address': broadcast_addr_str, 'delivery_successful': False
            })
            return False
        payload = bytes([command_byte_value])
        broadcast_remote_device = RemoteXBeeDevice(self.device, XBee64BitAddress.BROADCAST_ADDRESS)
        
        fid_before_internal_increment = self.device.get_next_frame_id()
        fid_to_track = self._calculate_tracking_fid(fid_before_internal_increment)
        with self._pending_transmissions_lock:
            self._pending_transmissions[fid_to_track] = { 
                "description": command_description,
                "address": broadcast_addr_str, 
                "payload_byte": command_byte_value,
                "timestamp": time.time(),
                "is_health_check": False 
            }
        app_logger.info(f"Attempting ASYNC broadcast (TrackingFID:{fid_to_track}, Desc:'{command_description}'): Payload 0x{command_byte_value:02X}")
        self.log_message.emit(f"Sending ASYNC BROADCAST '{command_description}' (0x{command_byte_value:02X})...")
        try:
            self.device.send_data_async(broadcast_remote_device, payload) 
            app_logger.info(f"Async broadcast (TrackedFID:{fid_to_track}) '{command_description}' submitted.")

            # Check if we should trigger a subsequent board status request
            board_status_req_cmd_val = config.COMMANDS.get("BOARD_STATUS_REQUEST")
            if command_byte_value != board_status_req_cmd_val:
                self._schedule_subsequent_board_status_request(command_description)
            
            return True
        except Exception as e: 
            app_logger.error(f"Error during send_data_async (broadcast) for '{command_description}' (TrackedFID:{fid_to_track}): {type(e).__name__} - {e}", exc_info=True)
            with self._pending_transmissions_lock:
                self._pending_transmissions.pop(fid_to_track, None) 
            self.transmit_status_update.emit({
                'frame_id': fid_to_track, 'description': command_description,
                'status': f"Send Init Fail: {type(e).__name__}",'retries': "N/A",
                'address': broadcast_addr_str, 'delivery_successful': False
            })
            return False
            
    @property
    def is_connected(self):
        return self._is_connected

    def perform_radio_healthcheck_single_target(self, radio_address_hex: str):
        if not self.is_connected:
            app_logger.info(f"Cannot healthcheck {radio_address_hex}: Not connected.")
            self.log_message.emit(f"Cannot healthcheck {radio_address_hex[-4:]}: Host XBee not connected.")
            return
        
        radio_address_hex_upper = radio_address_hex.upper()
        radio_info = self.target_radios_status.get(radio_address_hex_upper)
        if not radio_info:
            app_logger.warning(f"Cannot healthcheck unknown radio: {radio_address_hex_upper}")
            self.log_message.emit(f"Cannot healthcheck unknown radio: {radio_address_hex_upper[-4:]}")
            return
        
        if not radio_info.get('is_active_for_sending', True):
            self.log_message.emit(f"Radio {radio_info['name']} is disabled, manual health check not sent.")
            return
        command_byte = config.COMMANDS["RADIO_HEALTHCHECK"]
        desc = f"Manual Healthcheck ({radio_info['name']})"
        self.log_message.emit(f"Sent manual healthcheck to {radio_info['name']}.")
        # This will use trigger_board_status_after_send=True by default in send_unicast_command.
        # Since RADIO_HEALTHCHECK != BOARD_STATUS_REQUEST, a subsequent BSR will be scheduled.
        self.send_unicast_command(radio_address_hex_upper, command_byte, desc, is_health_check_command=True)