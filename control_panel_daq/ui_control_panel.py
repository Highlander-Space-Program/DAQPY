# ui_control_panel.py
import sys
from PySide6.QtWidgets import (QMainWindow, QVBoxLayout, QHBoxLayout, QGridLayout, QWidget,
                               QPushButton, QLabel, QLineEdit, QTextEdit, QGroupBox, QScrollArea,
                               QSizePolicy, QFrame, QSplitter, QApplication, QStatusBar)
from PySide6.QtCore import Qt, Slot, QTimer
from PySide6.QtGui import QPalette, QColor, QIcon, QFont

import config
from logger_setup import app_logger
import can_parser

class ControlPanelWindow(QMainWindow):
    STATUS_UNKNOWN_COLOR = "gainsboro"
    STATUS_ALIVE_COLOR = "mediumseagreen"
    STATUS_DEAD_COLOR = "lightcoral"
    STATUS_OPEN_COLOR = "mediumseagreen"
    STATUS_CLOSED_COLOR = "lightcoral"
    STATUS_ON_COLOR = "mediumseagreen"
    STATUS_OFF_COLOR = "lightcoral"
    DEFAULT_BUTTON_MIN_HEIGHT = 40

    def __init__(self, xbee_manager_instance, data_processor_instance, parent=None):
        super().__init__(parent)
        self.xbee_manager = xbee_manager_instance
        self.data_processor = data_processor_instance

        self.setWindowTitle("XBee CAN Control Panel")
        self.setGeometry(50, 50, 1600, 950) # Adjusted width for more per-radio info

        self._ui_elements = {} 
        self._radio_ui_elements = {} 
        self._device_toggle_status_labels = {}
        self._board_status_labels = {} # For MSG_TYPE_BOARD_STATUS_RESPONSE display (future use)

        self._init_ui()
        self._connect_signals()

        QTimer.singleShot(500, self.xbee_manager.autodetect_and_connect)

    def _apply_button_style(self, button: QPushButton):
        button.setMinimumHeight(self.DEFAULT_BUTTON_MIN_HEIGHT)

    def _create_status_indicator_label(self, initial_text="?", color="gray", width=25, height=25):
        label = QLabel(initial_text)
        label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        label.setFixedSize(width, height)
        font = label.font()
        font.setPointSize(10) 
        font.setBold(True)
        label.setFont(font)
        label.setStyleSheet(f"background-color: {color}; color: black; border: 1px solid dimgray; border-radius: {width/2}px;")
        return label

    def _update_status_indicator(self, label: QLabel, is_on: bool, on_color="green", off_color="red", on_text="●", off_text="●"):
        text_color = "white" if is_on and on_color != "yellow" else "black" 
        bg_color = on_color if is_on else off_color
        text = on_text if is_on else off_text
        label.setText(text)
        label.setStyleSheet(f"background-color: {bg_color}; color: {text_color}; border: 1px solid dimgray; border-radius: {label.width()/2}px;")


    def _init_ui(self):
        main_widget = QWidget()
        self.setCentralWidget(main_widget)
        overall_layout = QVBoxLayout(main_widget)

        # Top Bar (XBee Connection, UI Settings) - Remains the same
        top_bar_layout = QHBoxLayout()
        conn_group = QGroupBox("XBee Connection")
        conn_layout = QHBoxLayout()
        self.connect_button = QPushButton("Connect XBee")
        self._apply_button_style(self.connect_button)
        self.connect_button.clicked.connect(self.xbee_manager.autodetect_and_connect)
        self.disconnect_button = QPushButton("Disconnect")
        self._apply_button_style(self.disconnect_button)
        self.disconnect_button.clicked.connect(self.xbee_manager.disconnect_device)
        self.disconnect_button.setEnabled(False)
        self.com_port_label = QLabel("Port: N/A")
        conn_layout.addWidget(self.connect_button)
        conn_layout.addWidget(self.disconnect_button)
        conn_layout.addWidget(self.com_port_label)
        conn_group.setLayout(conn_layout)
        top_bar_layout.addWidget(conn_group)

        ui_rate_group = QGroupBox("UI Settings")
        ui_rate_layout = QHBoxLayout()
        ui_rate_layout.addWidget(QLabel("UI Update (Hz):"))
        self.ui_rate_input = QLineEdit(str(config.DEFAULT_UI_UPDATE_HZ))
        self.ui_rate_input.setFixedWidth(50)
        self.ui_rate_input.editingFinished.connect(self._update_ui_refresh_rate)
        ui_rate_layout.addWidget(self.ui_rate_input)
        ui_rate_group.setLayout(ui_rate_layout)
        top_bar_layout.addWidget(ui_rate_group)
        top_bar_layout.addStretch(1)
        overall_layout.addLayout(top_bar_layout)

        # Main content area with splitter
        splitter = QSplitter(Qt.Orientation.Horizontal)

        # --- Left Column ---
        left_column_widget = QWidget()
        left_column_layout = QVBoxLayout(left_column_widget)
        left_column_layout.setSpacing(15)

        self._create_servo_controls_group(left_column_layout) # Remains here
        self._create_system_controls_group(left_column_layout) # Renamed and will include new buttons
        # Event Log MOVED to bottom of left column
        self._create_event_log_group(left_column_layout) 
        left_column_layout.addStretch(1) 
        
        splitter.addWidget(left_column_widget)

        # --- Right Column ---
        right_column_widget = QWidget()
        right_column_layout = QVBoxLayout(right_column_widget)
        right_column_layout.setSpacing(15)

        # Sensor Data MOVED to top of right column
        self._create_sensor_data_group(right_column_layout)
        # Radio Status (now includes per-radio TX status)
        self._create_radio_status_group(right_column_layout) 
        # Old global Transmission Status group will be REMOVED.
        # self._create_transmission_status_group(right_column_layout) # This will be removed
        
        # Placeholder for Board Status display (if needed later)
        # self._create_board_statuses_group(right_column_layout)

        right_column_layout.addStretch(1)
        splitter.addWidget(right_column_widget)
        
        splitter.setSizes([700, 900]) # Adjust initial proportions, right side wider for radio details
        overall_layout.addWidget(splitter)

        self.status_bar = QStatusBar()
        self.setStatusBar(self.status_bar)
        self.status_bar.showMessage("Application Started. Waiting for XBee connection...")

    def _create_servo_controls_group(self, parent_layout):
        # This group remains physically in the same spot (top-left area)
        servos_group = QGroupBox("Servo Valve Controls")
        servos_layout = QGridLayout()
        servos_layout.setSpacing(10)
        row = 0
        for servo_conf in config.SERVO_LOOKUP_TABLE:
            name = servo_conf["name"]
            name_label = QLabel(f"<b>{name}</b>")
            servos_layout.addWidget(name_label, row, 0)

            status_label = QLabel("Unknown")
            status_label.setFrameShape(QFrame.Shape.StyledPanel)
            status_label.setFrameShadow(QFrame.Shadow.Sunken)
            status_label.setMinimumWidth(100)
            status_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
            status_label.setStyleSheet(f"background-color: {self.STATUS_UNKNOWN_COLOR}; padding: 5px; border-radius: 5px;")
            self._ui_elements[f"{name}_Servo_status"] = status_label
            servos_layout.addWidget(status_label, row, 1)

            open_cmd_name = f"Open {name}"
            if open_cmd_name in config.NAMED_COMMANDS:
                open_btn = QPushButton("Open")
                self._apply_button_style(open_btn)
                cmd_val = config.NAMED_COMMANDS[open_cmd_name]
                open_btn.clicked.connect(lambda checked=False, v=cmd_val, n=open_cmd_name: 
                                         self.xbee_manager.send_command_to_configured_targets(v, n))
                servos_layout.addWidget(open_btn, row, 2)

            close_cmd_name = f"Close {name}"
            if close_cmd_name in config.NAMED_COMMANDS:
                close_btn = QPushButton("Close")
                self._apply_button_style(close_btn)
                cmd_val = config.NAMED_COMMANDS[close_cmd_name]
                close_btn.clicked.connect(lambda checked=False, v=cmd_val, n=close_cmd_name: 
                                          self.xbee_manager.send_command_to_configured_targets(v, n))
                servos_layout.addWidget(close_btn, row, 3)
            row += 1
        
        servos_layout.setColumnStretch(0, 2) 
        servos_layout.setColumnStretch(1, 1) 
        servos_layout.setColumnStretch(2, 0) 
        servos_layout.setColumnStretch(3, 0)
        servos_group.setLayout(servos_layout)
        parent_layout.addWidget(servos_group)

    def _create_system_controls_group(self, parent_layout):
        # Renamed from _create_device_toggles_group to be more encompassing
        # This group remains physically in the same spot (left column, below servos)
        system_controls_group = QGroupBox("System Controls & Manual Triggers")
        system_controls_main_layout = QVBoxLayout()
        system_controls_main_layout.setSpacing(15)

        # --- Device Toggles Section (existing) ---
        toggles_section_group = QGroupBox("Device Toggles (To Configured Targets)")
        toggles_layout = QGridLayout()
        toggles_layout.setSpacing(10)
        toggle_row = 0

        def add_toggle_row(display_name, cmd_on_val, cmd_off_val, status_key_base):
            nonlocal toggle_row
            name_label = QLabel(f"<b>{display_name}:</b>")
            toggles_layout.addWidget(name_label, toggle_row, 0)
            status_indicator = self._create_status_indicator_label("?", self.STATUS_UNKNOWN_COLOR)
            self._device_toggle_status_labels[status_key_base] = status_indicator
            toggles_layout.addWidget(status_indicator, toggle_row, 1)
            on_btn = QPushButton(f"{display_name} ON")
            self._apply_button_style(on_btn)
            on_btn.clicked.connect(lambda checked=False, v=cmd_on_val, n=f"{display_name} ON":
                                   self.xbee_manager.send_command_to_configured_targets(v, n))
            toggles_layout.addWidget(on_btn, toggle_row, 2)
            off_btn = QPushButton(f"{display_name} OFF")
            self._apply_button_style(off_btn)
            off_btn.clicked.connect(lambda checked=False, v=cmd_off_val, n=f"{display_name} OFF":
                                    self.xbee_manager.send_command_to_configured_targets(v, n))
            toggles_layout.addWidget(off_btn, toggle_row, 3)
            toggle_row += 1
        
        add_toggle_row("Servos Power", config.COMMANDS["ACTIVATE_SERVOS"], config.COMMANDS["DEACTIVATE_SERVOS"], "servos_power")
        add_toggle_row("Auto Mode", config.COMMANDS["AUTO_ON"], config.COMMANDS["AUTO_OFF"], "auto_mode")
        add_toggle_row("Igniter", config.COMMANDS["ACTIVATE_IGNITER"], config.COMMANDS["DEACTIVATE_IGNITER"], "igniter_status")
        
        toggles_layout.setColumnStretch(0,1)
        toggles_layout.setColumnStretch(1,0) 
        toggles_layout.setColumnStretch(2,1) 
        toggles_layout.setColumnStretch(3,1)
        toggles_section_group.setLayout(toggles_layout)
        system_controls_main_layout.addWidget(toggles_section_group)

        # --- Other System Commands Section (existing + new buttons) ---
        general_commands_section_group = QGroupBox("Other System Commands & Manual Triggers")
        general_commands_layout = QGridLayout()
        general_commands_layout.setSpacing(10)
        
        sys_row, sys_col = 0,0
        # Add existing general commands from config.GENERAL_COMMANDS
        # Filter out commands that are now handled by new specific buttons/timers
        # to avoid redundancy, or re-purpose them if needed.
        
        # Explicitly add existing buttons that should remain
        commands_to_add = {
            "Signal All": config.COMMANDS["SIGNAL_ALL"],
            "Start Sequence 1": config.COMMANDS["START_1"],
            "Stop Sequence 1 (Destart)": config.COMMANDS["DESTART"],
            "ABORT": config.COMMANDS["ABORT"],
            "Clear Abort (Deabort)": config.COMMANDS["DEABORT"],
        }

        # Add NEW Manual Trigger Buttons
        commands_to_add["Manual Radio Healthcheck"] = config.COMMANDS["RADIO_HEALTHCHECK"] # Uses existing command val
        commands_to_add["Manual Board Status Request"] = config.COMMANDS["BOARD_STATUS_REQUEST"] # Uses existing command val

        # Function map for new buttons
        manual_trigger_actions = {
            "Manual Radio Healthcheck": self.xbee_manager.perform_radio_healthcheck_all_targets,
            "Manual Board Status Request": self.xbee_manager.request_board_status_all_targets,
        }

        for name, cmd_val_or_action in commands_to_add.items():
            btn = QPushButton(name)
            self._apply_button_style(btn)
            if name in manual_trigger_actions:
                # For new buttons that call specific XBeeManager methods directly
                btn.clicked.connect(manual_trigger_actions[name])
            else:
                # For old buttons sending command bytes
                cmd_val = cmd_val_or_action # In this case, it's the command value
                btn.clicked.connect(lambda checked=False, v=cmd_val, n=name:
                                    self.xbee_manager.send_command_to_configured_targets(v,n))
            general_commands_layout.addWidget(btn, sys_row, sys_col)
            sys_col +=1
            if sys_col >=2: # Arrange in 2 columns
                sys_col = 0
                sys_row +=1
        
        general_commands_section_group.setLayout(general_commands_layout)
        system_controls_main_layout.addWidget(general_commands_section_group)
        
        system_controls_group.setLayout(system_controls_main_layout)
        parent_layout.addWidget(system_controls_group)


    def _create_radio_status_group(self, parent_layout):
        radio_group = QGroupBox("Target Radio Status & Control")
        # Main layout for the group box, allowing scrolling if content is too tall
        scroll_area = QScrollArea()
        scroll_area.setWidgetResizable(True)
        content_widget = QWidget()
        radio_layout = QGridLayout(content_widget) # Layout on the content widget
        radio_layout.setSpacing(10) 
        
        row = 0
        # Headers
        headers = ["Status", "Radio (Last 8 Addr)", "Send To", "Last TX Cmd", "Last TX Status", "Retries"]
        for col, header_text in enumerate(headers):
            header_label = QLabel(f"<b>{header_text}</b>")
            header_label.setAlignment(Qt.AlignmentFlag.AlignCenter if col !=1 else Qt.AlignmentFlag.AlignLeft)
            radio_layout.addWidget(header_label, row, col)
        row += 1

        for name, addr_hex in config.XBEE_TARGET_RADIO_CONFIG:
            display_name_short = f"{name} (...{addr_hex[-8:]})"
            
            status_indicator = self._create_status_indicator_label("?", self.STATUS_UNKNOWN_COLOR, width=22, height=22)
            name_label = QLabel(display_name_short)
            
            toggle_button = QPushButton("Active")
            self._apply_button_style(toggle_button)
            toggle_button.setMinimumWidth(100)
            toggle_button.setCheckable(True) 
            toggle_button.setChecked(True)
            toggle_button.clicked.connect(lambda checked=False, a=addr_hex: self._toggle_radio_clicked(a))

            # New labels for per-radio TX status
            last_tx_desc_label = QLabel("N/A")
            last_tx_status_label = QLabel("N/A")
            last_tx_retries_label = QLabel("N/A")
            
            # Make TX Desc label elide if too long
            last_tx_desc_label.setMinimumWidth(150) # Give it some space
            last_tx_desc_label.setSizePolicy(QSizePolicy.Policy.Ignored, QSizePolicy.Policy.Preferred)


            self._radio_ui_elements[addr_hex] = {
                'name_label': name_label,
                'status_indicator': status_indicator,
                'toggle_button': toggle_button,
                'last_tx_desc_label': last_tx_desc_label,
                'last_tx_status_label': last_tx_status_label,
                'last_tx_retries_label': last_tx_retries_label,
            }
            radio_layout.addWidget(status_indicator, row, 0, Qt.AlignmentFlag.AlignCenter)
            radio_layout.addWidget(name_label, row, 1)
            radio_layout.addWidget(toggle_button, row, 2, Qt.AlignmentFlag.AlignCenter)
            radio_layout.addWidget(last_tx_desc_label, row, 3)
            radio_layout.addWidget(last_tx_status_label, row, 4)
            radio_layout.addWidget(last_tx_retries_label, row, 5, Qt.AlignmentFlag.AlignCenter)
            row += 1
        
        # "Refresh All Radio Statuses" button functionality is now "Radio Healthcheck"
        # The method xbee_manager.check_all_radio_statuses() now calls perform_radio_healthcheck_all_targets()
        refresh_button = QPushButton("Send Radio Healthchecks") # Updated text for clarity
        self._apply_button_style(refresh_button)
        refresh_button.clicked.connect(self.xbee_manager.check_all_radio_statuses) # This method now performs healthcheck
        radio_layout.addWidget(refresh_button, row, 0, 1, len(headers)) # Span all columns

        radio_layout.setColumnStretch(1, 2) # Radio name
        radio_layout.setColumnStretch(3, 3) # TX Desc
        radio_layout.setColumnStretch(4, 2) # TX Status
        
        scroll_area.setWidget(content_widget)
        
        # Final layout for the group box to hold the scroll area
        group_box_layout = QVBoxLayout()
        group_box_layout.addWidget(scroll_area)
        radio_group.setLayout(group_box_layout)
        
        parent_layout.addWidget(radio_group)

    def _toggle_radio_clicked(self, address_hex_str):
        self.xbee_manager.toggle_radio_sending_activity(address_hex_str)

    # def _create_transmission_status_group(self, parent_layout):
    #     # This group is now REMOVED as its functionality is integrated into _create_radio_status_group
    #     pass

    def _create_sensor_data_group(self, parent_layout):
        # This group is MOVED to the top of the right column
        sensors_group = QGroupBox("Sensor Data")
        sensors_scroll_area = QScrollArea() 
        sensors_scroll_area.setWidgetResizable(True)
        sensors_scroll_content_widget = QWidget()
        sensors_layout = QGridLayout(sensors_scroll_content_widget)
        
        row = 0
        all_sensors = config.THERMO_LOOKUP_TABLE + config.PT_LOOKUP_TABLE + config.HEATER_LOOKUP_TABLE
        all_sensors_sorted = sorted(all_sensors, key=lambda x: x["name"])

        for sensor_conf in all_sensors_sorted:
            name = sensor_conf["name"]
            can_id_val = sensor_conf.get("can_id")
            if can_id_val is None: continue
            parsed_can = can_parser.parse_can_id_struct(can_id_val)
            comp_type_name = can_parser.get_component_type_name(parsed_can["component_type_id"])
            
            sensors_layout.addWidget(QLabel(f"<b>{name}</b> ({comp_type_name})"), row, 0)
            value_label = QLabel("Value: N/A")
            sensors_layout.addWidget(value_label, row, 1)
            self._ui_elements[f"{name}_{comp_type_name}_value"] = value_label
            row += 1
        
        sensors_layout.setColumnStretch(0,1)
        sensors_layout.setColumnStretch(1,2) 
        sensors_scroll_area.setWidget(sensors_scroll_content_widget)
        
        sensors_group_layout = QVBoxLayout()
        sensors_group_layout.addWidget(sensors_scroll_area)
        sensors_group.setLayout(sensors_group_layout)
        
        parent_layout.addWidget(sensors_group)


    def _create_event_log_group(self, parent_layout):
        # This group is MOVED to the bottom of the left column
        log_group = QGroupBox("Event Log")
        log_group_layout = QVBoxLayout()
        self.log_text_edit = QTextEdit()
        self.log_text_edit.setReadOnly(True)
        self.log_text_edit.setLineWrapMode(QTextEdit.LineWrapMode.WidgetWidth)
        # Adjust minimum height if needed, or let it expand more freely
        self.log_text_edit.setMinimumHeight(200) 
        self.log_text_edit.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
        log_group_layout.addWidget(self.log_text_edit)
        log_group.setLayout(log_group_layout)
        parent_layout.addWidget(log_group)

    # Placeholder for Board Status Display group (if implemented visually later)
    # def _create_board_statuses_group(self, parent_layout):
    #     board_statuses_group = QGroupBox("Board Statuses")
    #     layout = QVBoxLayout()
    #     # Example: You might populate this dynamically based on boards found or configured
    #     # For now, just a placeholder
    #     placeholder_label = QLabel("Board statuses will appear here...")
    #     layout.addWidget(placeholder_label)
    #     board_statuses_group.setLayout(layout)
    #     parent_layout.addWidget(board_statuses_group)


    def _connect_signals(self):
        self.xbee_manager.xbee_connected.connect(self._on_xbee_connected)
        self.xbee_manager.xbee_disconnected.connect(self._on_xbee_disconnected)
        self.xbee_manager.connection_error.connect(self._on_xbee_connection_error)
        self.xbee_manager.log_message.connect(self.add_log_message)
        self.xbee_manager.transmit_status_update.connect(self._update_transmit_status_display) # Now updates per-radio
        self.xbee_manager.radio_status_updated.connect(self._update_radio_status_display)

        self.data_processor.ui_update_sensor.connect(self._update_sensor_display)
        self.data_processor.ui_update_servo.connect(self._update_servo_display)
        # self.data_processor.ui_update_board_status.connect(self._update_board_status_display_slot) # Connect if you implement UI for it

        # Connect signals for device toggle status updates from DataProcessor (if they exist)
        # For example:
        # if hasattr(self.data_processor, 'ui_update_igniter_status'):
        #     self.data_processor.ui_update_igniter_status.connect(self._update_igniter_display)
        # if hasattr(self.data_processor, 'ui_update_auto_mode_status'):
        #     self.data_processor.ui_update_auto_mode_status.connect(self._update_auto_mode_display)
        # if hasattr(self.data_processor, 'ui_update_servos_power_status'):
        #     self.data_processor.ui_update_servos_power_status.connect(self._update_servos_power_display)
        self.data_processor.log_message.connect(self.add_log_message)


    @Slot(str)
    def add_log_message(self, message):
        self.log_text_edit.append(message)

    @Slot(str)
    def _on_xbee_connected(self, port):
        self.com_port_label.setText(f"Port: {port}")
        self.status_bar.showMessage(f"Connected to XBee on {port}", 5000)
        self.connect_button.setEnabled(False)
        self.disconnect_button.setEnabled(True)
        self.add_log_message(f"Successfully connected to XBee on {port}.")
        # Initial radio status check is handled by XBeeManager after connection

    @Slot(str)
    def _on_xbee_disconnected(self, reason):
        self.com_port_label.setText("Port: N/A")
        self.status_bar.showMessage(f"XBee Disconnected: {reason}", 5000)
        self.connect_button.setEnabled(True)
        self.disconnect_button.setEnabled(False)
        self.add_log_message(f"XBee disconnected: {reason}")
        self._clear_sensor_displays_to_stale()
        for addr_hex_str in self._radio_ui_elements.keys():
            # Reset radio UI elements to disconnected state
            radio_info = self.xbee_manager.target_radios_status.get(addr_hex_str, {})
            self._update_radio_status_display({
                'address': addr_hex_str, 
                'name': radio_info.get('name', 'Unknown Radio'),
                'is_alive': False, 
                'is_active_for_sending': radio_info.get('is_active_for_sending', True), # Retain sending preference
                'last_tx_description': "N/A",
                'last_tx_status': "N/A",
                'last_tx_retries': "N/A"
            })

    @Slot(str)
    def _on_xbee_connection_error(self, error_message):
        self.com_port_label.setText("Port: Error")
        self.status_bar.showMessage(f"XBee Connection Error: {error_message}", 5000)
        self.connect_button.setEnabled(True)
        self.disconnect_button.setEnabled(False)
        self.add_log_message(f"XBee Connection Error: {error_message}")

    @Slot(dict)
    def _update_transmit_status_display(self, status_info):
        # This slot now updates the per-radio TX status in the "Target Radio Status & Control" group.
        address_64bit = status_info.get('address', '').upper()
        
        # Attempt to find a direct match in configured radios first
        if address_64bit in self._radio_ui_elements:
            ui_set = self._radio_ui_elements[address_64bit]
            
            desc_text = status_info.get('description', 'N/A')
            # Elide text for description if too long
            font_metrics = ui_set['last_tx_desc_label'].fontMetrics()
            elided_text = font_metrics.elidedText(desc_text, Qt.TextElideMode.ElideRight, ui_set['last_tx_desc_label'].width())
            ui_set['last_tx_desc_label'].setText(elided_text)
            ui_set['last_tx_desc_label'].setToolTip(desc_text) # Show full text on hover

            status_text = status_info.get('status', 'N/A')
            ui_set['last_tx_status_label'].setText(status_text)
            ui_set['last_tx_retries_label'].setText(str(status_info.get('retries', 'N/A')))

            # Color code the status text
            if "success" in status_text.lower():
                ui_set['last_tx_status_label'].setStyleSheet("color: mediumseagreen; font-weight: bold;")
            elif any(err_term in status_text.lower() for err_term in ["fail", "error", "timeout", "n/a", "not found", "unknown"]):
                ui_set['last_tx_status_label'].setStyleSheet("color: lightcoral; font-weight: bold;")
            else:
                ui_set['last_tx_status_label'].setStyleSheet("") # Reset to default
        
        elif "(16-bit" in address_64bit: # If it's a 16-bit address string (from unmatched FID)
            # Log it, but we can't easily map it to a specific 64-bit radio row.
            # This could be displayed in a general "Unmatched TX Statuses" area if desired.
            self.add_log_message(f"Unmatched TX Status (FID:{status_info.get('frame_id')}): {status_info.get('description')} to {address_64bit} -> {status_info.get('status')}")
        
        # The old global labels are no longer updated here.

    @Slot(dict)
    def _update_radio_status_display(self, radio_info):
        # This slot is typically called by XBeeManager.radio_status_updated signal
        addr = radio_info['address']
        if addr in self._radio_ui_elements:
            ui_set = self._radio_ui_elements[addr]
            self._update_status_indicator(ui_set['status_indicator'], radio_info.get('is_alive', False), 
                                          self.STATUS_ALIVE_COLOR, self.STATUS_DEAD_COLOR, "●", "✖")
            
            is_active = radio_info.get('is_active_for_sending', True)
            ui_set['toggle_button'].setText("Sending To" if is_active else "Disabled")
            ui_set['toggle_button'].setChecked(is_active) 
            if is_active:
                ui_set['toggle_button'].setStyleSheet(f"background-color: {self.STATUS_ALIVE_COLOR}; color: white;")
            else:
                ui_set['toggle_button'].setStyleSheet(f"background-color: {self.STATUS_UNKNOWN_COLOR}; color: black;")

            # Also update last TX info if provided by this signal
            # (XBeeManager's target_radios_status now holds these)
            desc_text = radio_info.get('last_tx_description', 'N/A')
            font_metrics = ui_set['last_tx_desc_label'].fontMetrics()
            elided_text = font_metrics.elidedText(desc_text, Qt.TextElideMode.ElideRight, ui_set['last_tx_desc_label'].width())
            ui_set['last_tx_desc_label'].setText(elided_text)
            ui_set['last_tx_desc_label'].setToolTip(desc_text)

            status_text = radio_info.get('last_tx_status', 'N/A')
            ui_set['last_tx_status_label'].setText(status_text)
            ui_set['last_tx_retries_label'].setText(str(radio_info.get('last_tx_retries', 'N/A')))
            
            if "success" in status_text.lower():
                ui_set['last_tx_status_label'].setStyleSheet("color: mediumseagreen; font-weight: bold;")
            elif any(err_term in status_text.lower() for err_term in ["fail", "error", "timeout", "n/a", "not found", "unknown"]):
                ui_set['last_tx_status_label'].setStyleSheet("color: lightcoral; font-weight: bold;")
            else:
                ui_set['last_tx_status_label'].setStyleSheet("")


    @Slot(str, str, str, str)
    def _update_servo_display(self, name, state_str, board_name, component_type_name):
        status_key = f"{name}_Servo_status"
        if status_key in self._ui_elements:
            label_widget = self._ui_elements[status_key]
            label_widget.setText(state_str.upper())
            if state_str.lower() == "open":
                label_widget.setStyleSheet(f"background-color: {self.STATUS_OPEN_COLOR}; color: black; padding: 5px; border-radius: 5px; font-weight: bold;")
            elif state_str.lower() == "closed":
                label_widget.setStyleSheet(f"background-color: {self.STATUS_CLOSED_COLOR}; color: black; padding: 5px; border-radius: 5px; font-weight: bold;")
            else: 
                label_widget.setStyleSheet(f"background-color: {self.STATUS_UNKNOWN_COLOR}; color: black; padding: 5px; border-radius: 5px;")
    
    # Slots for device toggle status updates
    @Slot(bool) # Assuming data_processor emits simplified signals now
    def _update_igniter_display(self, is_on):
        if "igniter_status" in self._device_toggle_status_labels:
            self._update_status_indicator(self._device_toggle_status_labels["igniter_status"], is_on, 
                                          self.STATUS_ON_COLOR, self.STATUS_OFF_COLOR, "ON", "OFF")
    
    @Slot(bool)
    def _update_auto_mode_display(self, is_on):
        if "auto_mode" in self._device_toggle_status_labels:
            self._update_status_indicator(self._device_toggle_status_labels["auto_mode"], is_on,
                                          self.STATUS_ON_COLOR, self.STATUS_OFF_COLOR, "ON", "OFF")

    @Slot(bool)
    def _update_servos_power_display(self, is_on):
        if "servos_power" in self._device_toggle_status_labels:
             self._update_status_indicator(self._device_toggle_status_labels["servos_power"], is_on,
                                           self.STATUS_ON_COLOR, self.STATUS_OFF_COLOR, "ON", "OFF")


    @Slot(str, str, str, str, str)
    def _update_sensor_display(self, name, value_str, unit, board_name, component_type_name):
        key = f"{name}_{component_type_name}_value"
        if key in self._ui_elements:
            self._ui_elements[key].setText(f"Value: {value_str} {unit}")


    def _clear_sensor_displays_to_stale(self):
        for key, widget in self._ui_elements.items():
            if ("_value" in key or "_Servo_status" in key) and isinstance(widget, QLabel):
                original_text_part = widget.text().split(':')[0]
                if "_Servo_status" in key:
                     widget.setText("Unknown")
                     widget.setStyleSheet(f"background-color: {self.STATUS_UNKNOWN_COLOR}; color: black; padding: 5px; border-radius: 5px;")
                elif "_value" in key:
                    if "N/A" not in original_text_part and "Unknown" not in original_text_part:
                        widget.setText(f"{original_text_part}: Stale")
                    else: 
                        widget.setText(f"{original_text_part}: N/A")
        for key, label in self._device_toggle_status_labels.items():
            self._update_status_indicator(label, False, off_color=self.STATUS_UNKNOWN_COLOR, off_text="?", on_text="?")
        # Clear per-radio TX status as well
        for addr_hex in self._radio_ui_elements:
            ui_set = self._radio_ui_elements[addr_hex]
            ui_set['last_tx_desc_label'].setText("N/A")
            ui_set['last_tx_status_label'].setText("N/A")
            ui_set['last_tx_status_label'].setStyleSheet("") # Reset color
            ui_set['last_tx_retries_label'].setText("N/A")


    def _update_ui_refresh_rate(self):
        try:
            hz = int(self.ui_rate_input.text())
            if hz >= 0: 
                self.data_processor.set_ui_update_frequency(hz)
                self.add_log_message(f"UI update rate set to {hz} Hz.")
            else:
                self.add_log_message("Invalid UI update rate. Must be >= 0.")
                self.ui_rate_input.setText(str(config.DEFAULT_UI_UPDATE_HZ)) 
        except ValueError:
            self.add_log_message("Invalid UI update rate. Please enter a number.")
            self.ui_rate_input.setText(str(config.DEFAULT_UI_UPDATE_HZ)) 


    def closeEvent(self, event):
        self.add_log_message("Closing application...")
        # XBeeManager timers are stopped in its disconnect/close methods
        self.xbee_manager.disconnect_device() 
        if hasattr(self.data_processor, '_ui_update_timer') and self.data_processor._ui_update_timer.isActive():
            self.data_processor._ui_update_timer.stop()
        app_logger.info("Application closed.")
        super().closeEvent(event)

# Mock classes for standalone testing (mostly unchanged but ensure they exist)
if __name__ == '__main__': 
    # Import QObject and Signal from QtCore for mock classes if not already at top level
    from PySide6.QtCore import QObject, Signal 

    app = QApplication(sys.argv)
    class MockXBeeManager(QObject):
        xbee_connected = Signal(str)
        xbee_disconnected = Signal(str)
        connection_error = Signal(str)
        log_message = Signal(str)
        transmit_status_update = Signal(dict)
        radio_status_updated = Signal(dict) 
        target_radios_status = {
            addr: {"name": name, "address": addr, "is_active_for_sending": True, "is_alive":False, 
                   "last_tx_description":"Init N/A", "last_tx_status":"Init N/A", "last_tx_retries":"Init N/A"} 
            for name, addr in config.XBEE_TARGET_RADIO_CONFIG
        }

        def autodetect_and_connect(self): 
            self.log_message.emit("Mock Autodetect & Connect")
            QTimer.singleShot(100, lambda: self.xbee_connected.emit("/dev/mockport"))
        def disconnect_device(self): 
            self.log_message.emit("Mock Disconnect")
            QTimer.singleShot(100, lambda: self.xbee_disconnected.emit("User disconnected"))
        def send_command_to_configured_targets(self, v, n): self.log_message.emit(f"Mock Send General Cmd: {n} (0x{v:02X})")
        def check_all_radio_statuses(self): self.perform_radio_healthcheck_all_targets() # Alias
        
        def perform_radio_healthcheck_all_targets(self):
            self.log_message.emit("Mock: Performing Radio Healthchecks...")
            import random
            for i, (addr, radio_stat_info) in enumerate(self.target_radios_status.items()):
                is_alive = random.choice([True, False])
                desc = f"Healthcheck to {radio_stat_info['name']}"
                status = "SUCCESS" if is_alive else "ROUTE_NOT_FOUND"
                retries = 0 if is_alive else 1
                
                # Simulate transmit_status_update for this radio
                self.transmit_status_update.emit({
                    'frame_id': 100+i, 'description': desc, 'status': status, 
                    'retries': retries, 'address': addr, 'delivery_successful': is_alive
                })
                # Simulate radio_status_updated (which XBeeManager would do from TX status)
                radio_stat_info['is_alive'] = is_alive
                radio_stat_info['last_tx_description'] = desc
                radio_stat_info['last_tx_status'] = status
                radio_stat_info['last_tx_retries'] = retries
                self.radio_status_updated.emit(radio_stat_info.copy())


        def request_board_status_all_targets(self): self.log_message.emit("Mock: Requesting All Board Statuses...")
        
        def toggle_radio_sending_activity(self, addr):
            self.log_message.emit(f"Mock Toggle Radio: {addr}")
            if addr in self.target_radios_status:
                self.target_radios_status[addr]['is_active_for_sending'] = not self.target_radios_status[addr]['is_active_for_sending']
                # Also update the 'is_alive' part for the toggle button visual feedback
                self.radio_status_updated.emit(self.target_radios_status[addr].copy()) 

    class MockDataProcessor(QObject):
        ui_update_sensor = Signal(str, str, str, str, str)
        ui_update_servo = Signal(str, str, str, str)
        log_message = Signal(str)
        # Example: ui_update_igniter = Signal(bool) # Simplified if name isn't needed
        # ui_update_board_status = Signal(str, str, str, dict) # board_can_id_hex, board_name, source_xbee_addr, status_data_dict

        class MockUITimer: 
            def isActive(self): return False
            def stop(self): pass
        _ui_update_timer = MockUITimer()
        def set_ui_update_frequency(self, hz): self.log_message.emit(f"Mock UI Freq: {hz}Hz")

    mock_xbee = MockXBeeManager()
    mock_data = MockDataProcessor()
    
    main_window = ControlPanelWindow(mock_xbee, mock_data)
    main_window.show()

    def simulate_updates():
        import random
        if config.SERVO_LOOKUP_TABLE:
            servo_name = random.choice(config.SERVO_LOOKUP_TABLE)["name"]
            servo_state = random.choice(["Open", "Closed", "Moving"])
            mock_data.ui_update_servo.emit(servo_name, servo_state, "MockBoard", "Servo")
        
        # Simulate sensor data
        all_sensors_mock = config.THERMO_LOOKUP_TABLE + config.PT_LOOKUP_TABLE + config.HEATER_LOOKUP_TABLE
        if all_sensors_mock:
            sensor_conf = random.choice(all_sensors_mock)
            parsed_can = can_parser.parse_can_id_struct(sensor_conf["can_id"])
            comp_type_name = can_parser.get_component_type_name(parsed_can["component_type_id"])
            mock_data.ui_update_sensor.emit(sensor_conf["name"], f"{random.randint(0,100)}", "mockUnit", "MockBoardSensor", comp_type_name)

        # Simulate a radio status update (as if from XBeeManager)
        # This is now mostly driven by transmit_status_update in the mock
        # mock_xbee.check_all_radio_statuses() # This will trigger TX and radio updates in mock

    test_data_timer = QTimer()
    test_data_timer.timeout.connect(simulate_updates)
    test_data_timer.timeout.connect(mock_xbee.check_all_radio_statuses) # Periodically simulate healthchecks
    test_data_timer.start(5000) # Update every 5 seconds

    sys.exit(app.exec())