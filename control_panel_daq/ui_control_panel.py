# ui_control_panel.py
import sys
import time
import signal
import re # Import regex for stylesheet manipulation
from PySide6.QtWidgets import (QMainWindow, QVBoxLayout, QHBoxLayout, QGridLayout, QWidget,
                               QPushButton, QLabel, QLineEdit, QTextEdit, QGroupBox, QScrollArea,
                               QSizePolicy, QFrame, QSplitter, QApplication, QStatusBar, QSpacerItem)
from PySide6.QtCore import Qt, Slot, QTimer, Signal, QObject
from PySide6.QtGui import QPalette, QColor, QIcon, QFont

# Ensure config is imported AFTER potential modifications (though not strictly necessary here)
import config
from logger_setup import app_logger
# import can_parser # Original file had this, keeping it.

class ControlPanelWindow(QMainWindow):
    # Color definitions
    STATUS_UNKNOWN_COLOR = "gainsboro"
    STATUS_ALIVE_COLOR = "mediumseagreen"
    STATUS_DEAD_COLOR = "lightcoral"
    STATUS_WARN_COLOR = "gold"
    STATUS_SERVO_POWERED_OPEN_COLOR = "mediumseagreen"
    STATUS_SERVO_POWERED_CLOSED_COLOR = "lightcoral"
    STATUS_SERVO_UNPOWERED_OPEN_COLOR = "palegreen"
    STATUS_SERVO_UNPOWERED_CLOSED_COLOR = "salmon"
    STATUS_SERVO_POSITION_COLOR = STATUS_WARN_COLOR

    DEFAULT_BUTTON_MIN_HEIGHT = 35
    BOARD_STATUS_LABEL_WIDTH = 120 
    SYSTEM_STATUS_CONTROL_STATE_WIDTH = 130
    SERVO_REPORTED_STATE_WIDTH = 130
    STATUS_INDICATOR_HEIGHT = 25
    RADIO_STATUS_CIRCLE_SIZE = 25 

    INDICATOR_FONT = QFont()
    SENSOR_NAME_FONT = QFont()
    SENSOR_VALUE_FONT = QFont()


    def __init__(self, xbee_manager_instance, data_processor_instance, parent=None):
        super().__init__(parent)
        self.xbee_manager = xbee_manager_instance
        self.data_processor = data_processor_instance

        self.setWindowTitle("XBee CAN Control Panel")
        self.setGeometry(50, 50, 1700, 1050) 

        self._ui_elements = {} 
        self._radio_ui_elements = {} 
        self._device_toggle_status_labels = {} 
        self._board_connectivity_info = {} 
        self._sensor_panel_board_status_labels = {} 

        self.INDICATOR_FONT.setPointSize(9)
        self.INDICATOR_FONT.setBold(True)
        self.SENSOR_NAME_FONT.setPointSize(24)
        self.SENSOR_VALUE_FONT.setPointSize(24)
        self.SENSOR_VALUE_FONT.setBold(True)

        self._initialize_board_connectivity_info()
        self._init_ui()
        self._connect_signals()

        self._board_status_check_timer = QTimer(self)
        self._board_status_check_timer.timeout.connect(self._check_board_timeouts)
        self._board_status_check_timer.start(config.BOARD_STATUS_CHECK_TIMER_MS) 

        QTimer.singleShot(500, self.xbee_manager.autodetect_and_connect)

    def _apply_button_style(self, button: QPushButton, min_height=DEFAULT_BUTTON_MIN_HEIGHT):
        button.setMinimumHeight(min_height)

    def _create_status_indicator_label(self, initial_text="?", color=STATUS_UNKNOWN_COLOR, fixed_width=None, height=STATUS_INDICATOR_HEIGHT):
        label = QLabel(initial_text)
        label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        label.setFont(self.INDICATOR_FONT)

        if fixed_width:
            label.setFixedSize(fixed_width, height)
        else:
            label.setMinimumHeight(height)
            label.setSizePolicy(QSizePolicy.Policy.Preferred, QSizePolicy.Policy.Fixed)

        border_radius = 5
        label.setStyleSheet(
            f"background-color: {color}; color: black; border: 1px solid dimgray; "
            f"border-radius: {border_radius}px; padding: 2px;"
        )
        self._set_label_text_color(label, color) 
        return label

    def _set_label_text_color(self, label: QLabel, background_color_str: str):
         bg_qcolor = QColor(background_color_str)
         text_color = "black" if bg_qcolor.lightnessF() > 0.5 else "white"
         current_style = label.styleSheet()
         new_style = re.sub(r"color: (black|white);", f"color: {text_color};", current_style)
         if f"color: {text_color};" not in new_style:
             insert_pos = new_style.find(';') + 1 if ';' in new_style else len(new_style)
             if insert_pos > 0 and not new_style.strip().endswith(';'):
                  new_style = new_style.strip() + ';' + f" color: {text_color};"
             elif insert_pos == 0: 
                   current_style_base = f"background-color: {background_color_str}; border: 1px solid dimgray; border-radius: 5px; padding: 2px;"
                   new_style = current_style_base + f" color: {text_color};"
             else:
                  new_style = new_style[:insert_pos] + f" color: {text_color};" + new_style[insert_pos:]
         label.setStyleSheet(new_style)

    def _update_board_status_label_style(self, label: QLabel, status_text: str, background_color: str):
        label.setText(status_text)
        label.setFont(self.INDICATOR_FONT) 
        border_radius = 5 
        label.setStyleSheet(
            f"background-color: {background_color}; "
            f"border: 1px solid dimgray; border-radius: {border_radius}px; padding: 2px; font-weight: bold;"
        )
        self._set_label_text_color(label, background_color) 

    def _init_ui(self):
        main_widget = QWidget()
        self.setCentralWidget(main_widget)
        overall_layout = QVBoxLayout(main_widget)

        top_bar_layout = QHBoxLayout()
        top_bar_layout.setSpacing(15)

        conn_group = QGroupBox("XBee Connection")
        conn_layout = QHBoxLayout(conn_group)
        conn_layout.setSpacing(5) 
        conn_layout.setContentsMargins(5, 5, 5, 5) 
        self.connect_button = QPushButton("Connect XBee")
        self._apply_button_style(self.connect_button)
        self.connect_button.clicked.connect(self.xbee_manager.autodetect_and_connect)
        self.disconnect_button = QPushButton("Disconnect")
        self._apply_button_style(self.disconnect_button)
        self.disconnect_button.clicked.connect(self.xbee_manager.disconnect_device)
        self.disconnect_button.setEnabled(False)
        self.com_port_label = QLabel("Port: N/A")
        self.com_port_label.setMinimumWidth(150)
        conn_layout.addWidget(self.connect_button)
        conn_layout.addWidget(self.disconnect_button)
        conn_layout.addWidget(self.com_port_label)
        top_bar_layout.addWidget(conn_group) 

        ui_rate_group = QGroupBox("UI Settings")
        ui_rate_layout = QHBoxLayout(ui_rate_group)
        ui_rate_layout.setSpacing(5)
        ui_rate_layout.setContentsMargins(5, 5, 5, 5)
        ui_rate_label = QLabel("UI Data Update (Hz):")
        ui_rate_layout.addWidget(ui_rate_label)                                      
        self.ui_rate_input = QLineEdit(str(config.DEFAULT_UI_UPDATE_HZ))
        self.ui_rate_input.setFixedWidth(50)
        self.ui_rate_input.editingFinished.connect(self._update_ui_refresh_rate)
        ui_rate_layout.addWidget(self.ui_rate_input)
        top_bar_layout.addWidget(ui_rate_group) 

        top_bar_layout.addStretch(1)

        radio_status_widget = QWidget()
        radio_status_layout = QHBoxLayout(radio_status_widget)
        radio_status_layout.setContentsMargins(20, 20, 20, 20) 
        radio_status_layout.setSpacing(6) 
        self._create_radio_status_elements(radio_status_layout)
        top_bar_layout.addWidget(radio_status_widget, 0) 

        overall_layout.addLayout(top_bar_layout)

        splitter = QSplitter(Qt.Orientation.Horizontal)

        left_column_widget = QWidget()
        left_column_layout = QVBoxLayout(left_column_widget)
        left_column_layout.setSpacing(15)
        self._create_servo_controls_group(left_column_layout)
        self._create_system_controls_group(left_column_layout)
        self._create_general_commands_group(left_column_layout) # Tare buttons will be added here
        self._create_event_log_group(left_column_layout)
        left_column_layout.addStretch(1)
        splitter.addWidget(left_column_widget)

        right_column_widget = QWidget()
        right_column_layout = QVBoxLayout(right_column_widget)
        right_column_layout.setSpacing(15)
        self._create_sensor_display_and_board_status_section(right_column_layout)
        right_column_layout.addStretch(1)
        splitter.addWidget(right_column_widget)

        splitter.setSizes([750, 950])
        overall_layout.addWidget(splitter)

        self.status_bar = QStatusBar()
        self.setStatusBar(self.status_bar)
        self.status_bar.showMessage("Application Started. Waiting for XBee connection...")
    
    def _initialize_board_connectivity_info(self):
        self._board_connectivity_info.clear()
        for board_id_hex, board_info_item in config.BOARD_INFO_LOOKUP_TABLE.items(): # This will now include SHREDDER
            self._board_connectivity_info[board_id_hex] = {
                "name": board_info_item["name"],
                "type": board_info_item.get("type", "UnknownBoard"),
                "components_hosted": board_info_item.get("components_hosted", []),
                "last_seen": 0, "status_str": "Unknown", "ui_labels": []
            }
        app_logger.info(f"Initialized connectivity tracking for {len(self._board_connectivity_info)} boards/systems.")

    def _create_radio_status_elements(self, parent_layout):
        radio_grid_layout = QGridLayout()
        radio_grid_layout.setHorizontalSpacing(4) 
        radio_grid_layout.setVerticalSpacing(3)   
        radio_grid_layout.setContentsMargins(0, 0, 0, 0)

        headers = ["", "Radio (Addr)", "Last TX Cmd", "TX Status", "R"]
        header_labels = []
        for col, header_text in enumerate(headers):
            header_label = QLabel(f"<b>{header_text}</b>")
            align = Qt.AlignmentFlag.AlignCenter if col != 1 and col != 2 else Qt.AlignmentFlag.AlignLeft
            header_label.setAlignment(align | Qt.AlignmentFlag.AlignVCenter)
            radio_grid_layout.addWidget(header_label, 0, col)
            header_labels.append(header_label)

        self._radio_ui_elements.clear()
        row = 1
        num_radios = len(config.XBEE_TARGET_RADIO_CONFIG)

        estimated_header_row_height = 0
        if header_labels: 
            header_font_metrics = header_labels[0].fontMetrics()
            estimated_header_row_height = header_font_metrics.height()
        if num_radios > 0 : 
            estimated_header_row_height += radio_grid_layout.verticalSpacing()

        estimated_data_row_height = self.RADIO_STATUS_CIRCLE_SIZE
        
        grid_height_estimate = estimated_header_row_height
        if num_radios > 0:
            grid_height_estimate += (self.RADIO_STATUS_CIRCLE_SIZE * num_radios) 
            if num_radios > 1: 
                grid_height_estimate += (radio_grid_layout.verticalSpacing() * (num_radios - 1))
        
        grid_height_estimate += 2 
        button_min_height = max(self.DEFAULT_BUTTON_MIN_HEIGHT, int(grid_height_estimate))
        if num_radios == 0: 
            button_min_height = self.DEFAULT_BUTTON_MIN_HEIGHT

        for name, addr_hex in config.XBEE_TARGET_RADIO_CONFIG:
            display_addr = f"...{addr_hex[-6:]}"
            display_name_short = f"{name}"

            status_indicator = QLabel()
            status_indicator.setFixedSize(self.RADIO_STATUS_CIRCLE_SIZE, self.RADIO_STATUS_CIRCLE_SIZE)
            radius = int(self.RADIO_STATUS_CIRCLE_SIZE / 2)
            status_indicator.setStyleSheet(
                f"background-color: {self.STATUS_UNKNOWN_COLOR}; "
                f"border: 1px solid dimgray; border-radius: {radius}px;"
            )
            status_indicator.setToolTip("Radio status unknown")

            name_label = QLabel(f"{display_name_short} <font color='grey'>({display_addr})</font>")
            name_label.setToolTip(f"{name} ({addr_hex})")
            name_label.setTextFormat(Qt.RichText)

            last_tx_desc_label = QLabel("N/A")
            last_tx_desc_label.setMinimumWidth(300) 
            last_tx_desc_label.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Preferred)

            last_tx_status_label = QLabel("N/A")
            last_tx_status_label.setMinimumWidth(100) 

            last_tx_retries_label = QLabel("N/A")
            last_tx_retries_label.setAlignment(Qt.AlignmentFlag.AlignCenter)

            self._radio_ui_elements[addr_hex] = {
                'name_label': name_label,
                'status_indicator': status_indicator,
                'last_tx_desc_label': last_tx_desc_label,
                'last_tx_status_label': last_tx_status_label,
                'last_tx_retries_label': last_tx_retries_label,
            }
            radio_grid_layout.addWidget(status_indicator, row, 0, Qt.AlignmentFlag.AlignCenter)
            radio_grid_layout.addWidget(name_label, row, 1, Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter)
            radio_grid_layout.addWidget(last_tx_desc_label, row, 2, Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter)
            radio_grid_layout.addWidget(last_tx_status_label, row, 3, Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter)
            radio_grid_layout.addWidget(last_tx_retries_label, row, 4, Qt.AlignmentFlag.AlignCenter)
            row += 1

        radio_grid_layout.setColumnStretch(1, 2) 
        radio_grid_layout.setColumnStretch(2, 2) 
        radio_grid_layout.setColumnStretch(3, 1) 

        parent_layout.addLayout(radio_grid_layout)

        refresh_button = QPushButton("Radio Health")
        refresh_button.setMinimumHeight(button_min_height)
        refresh_button.setMaximumHeight(button_min_height)
        refresh_button.setMinimumWidth(90)
        refresh_button.setToolTip("Send Radio Healthchecks (to all targets)")
        refresh_button.clicked.connect(self.xbee_manager.check_all_radio_statuses)
        parent_layout.addWidget(refresh_button, 0, Qt.AlignmentFlag.AlignTop)

    def _create_servo_controls_group(self, parent_layout):
        servos_group = QGroupBox("Servo Valve Controls & Board Status")
        servos_layout = QGridLayout(servos_group)
        servos_layout.setSpacing(10)
        row = 0

        headers = ["Servo Name", "Board Status", "Reported State", "Open Cmd", "Close Cmd"]
        for col, header_text in enumerate(headers):
             header_label = QLabel(f"<b>{header_text}</b>")
             align = Qt.AlignmentFlag.AlignCenter if col > 0 else Qt.AlignmentFlag.AlignLeft
             header_label.setAlignment(align)
             servos_layout.addWidget(header_label, row, col)
        row += 1

        for servo_conf in config.SERVO_LOOKUP_TABLE:
            name = servo_conf["name"]
            purpose = servo_conf.get("purpose", "") 
            parent_board_id = servo_conf.get("parent_board_id_hex")

            if parent_board_id is None:
                app_logger.warning(f"Servo config for '{name}' missing parent board ID. Skipping.")
                continue

            board_info = self._board_connectivity_info.get(parent_board_id)
            board_name = board_info["name"] if board_info else f"Board 0x{parent_board_id:02X}"

            name_display = f"<b>{name}</b>"
            if purpose:
                 name_display += f"<br><font size='-1' color='dimgray'>{purpose}</font>"
            name_display += f"<br><font size='-2' color='grey'>({board_name})</font>"

            name_label = QLabel(name_display)
            name_label.setTextFormat(Qt.RichText)
            name_label.setWordWrap(True)
            servos_layout.addWidget(name_label, row, 0, Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter)

            board_status_indicator = self._create_status_indicator_label("Unknown", self.STATUS_UNKNOWN_COLOR, fixed_width=self.BOARD_STATUS_LABEL_WIDTH)
            servos_layout.addWidget(board_status_indicator, row, 1, Qt.AlignmentFlag.AlignCenter)

            if board_info:
                board_info["ui_labels"].append(board_status_indicator) 
            else:
                 app_logger.warning(f"Board ID 0x{parent_board_id:02X} for servo {name} not found in _board_connectivity_info during UI creation.")

            servo_state_label = self._create_status_indicator_label("Unknown", self.STATUS_UNKNOWN_COLOR, fixed_width=self.SERVO_REPORTED_STATE_WIDTH)
            self._ui_elements[f"{name}_Servo_status"] = servo_state_label
            servos_layout.addWidget(servo_state_label, row, 2, Qt.AlignmentFlag.AlignCenter)

            open_cmd_name = f"Open {name}"
            if open_cmd_name in config.NAMED_COMMANDS:
                open_btn = QPushButton("Open")
                self._apply_button_style(open_btn)
                cmd_val = config.NAMED_COMMANDS[open_cmd_name]
                open_btn.clicked.connect(lambda checked=False, v=cmd_val, n=open_cmd_name:
                                         self.xbee_manager.send_command_to_configured_targets(v, n))
                servos_layout.addWidget(open_btn, row, 3, Qt.AlignmentFlag.AlignCenter)

            close_cmd_name = f"Close {name}"
            if close_cmd_name in config.NAMED_COMMANDS:
                close_btn = QPushButton("Close")
                self._apply_button_style(close_btn)
                cmd_val = config.NAMED_COMMANDS[close_cmd_name]
                close_btn.clicked.connect(lambda checked=False, v=cmd_val, n=close_cmd_name:
                                          self.xbee_manager.send_command_to_configured_targets(v, n))
                servos_layout.addWidget(close_btn, row, 4, Qt.AlignmentFlag.AlignCenter)
            row += 1

        servos_layout.setColumnStretch(0, 3) 
        servos_layout.setColumnStretch(1, 1)
        servos_layout.setColumnStretch(2, 1)
        servos_layout.setColumnStretch(3, 0)
        servos_layout.setColumnStretch(4, 0)
        servos_group.setLayout(servos_layout)
        parent_layout.addWidget(servos_group)


    def _create_sensor_display_and_board_status_section(self, parent_layout):
        top_group_box = QGroupBox("Sensor Data & Board Connectivity Status")
        top_group_layout = QVBoxLayout(top_group_box)

        scroll_area = QScrollArea()
        scroll_area.setWidgetResizable(True)
        scroll_area.setFrameShape(QFrame.Shape.NoFrame)

        scroll_content_widget = QWidget()
        scroll_content_layout = QVBoxLayout(scroll_content_widget)

        sensor_columns_container_widget = QWidget()
        sensor_columns_layout = QHBoxLayout(sensor_columns_container_widget)
        sensor_columns_layout.setSpacing(15)
        sensor_columns_layout.setAlignment(Qt.AlignmentFlag.AlignTop)

        pt_column_group = QGroupBox("Pressure Transducers (PT)")
        pt_column_vbox_layout = QVBoxLayout(pt_column_group)
        self.pt_sensors_display_layout = QVBoxLayout()
        self.pt_sensors_display_layout.setSpacing(10)
        pt_column_vbox_layout.addLayout(self.pt_sensors_display_layout)
        pt_column_vbox_layout.addStretch(1)
        sensor_columns_layout.addWidget(pt_column_group, 1)

        other_column_group = QGroupBox("Other Sensors (TC, LC, etc.)")
        other_column_vbox_layout = QVBoxLayout(other_column_group)
        self.other_sensors_display_layout = QVBoxLayout()
        self.other_sensors_display_layout.setSpacing(10)
        other_column_vbox_layout.addLayout(self.other_sensors_display_layout)
        other_column_vbox_layout.addStretch(1)
        sensor_columns_layout.addWidget(other_column_group, 1)

        self._populate_sensor_columns_dynamically()

        scroll_content_layout.addWidget(sensor_columns_container_widget)
        scroll_area.setWidget(scroll_content_widget)
        top_group_layout.addWidget(scroll_area)

        line = QFrame()
        line.setFrameShape(QFrame.Shape.HLine)
        line.setFrameShadow(QFrame.Shadow.Sunken)
        top_group_layout.addWidget(line)

        sensor_boards_status_group = QGroupBox("Other Board Connection Status") 
        sensor_boards_status_layout = QGridLayout(sensor_boards_status_group)
        sensor_boards_status_layout.setSpacing(10)
        self._sensor_panel_board_status_labels.clear()
        status_row, status_col = 0, 0
        max_status_cols = 3 

        # SHREDDER will be picked up here if its type is not "ServoBoard"
        board_ids_for_status_panel = sorted([
            bid for bid, binfo in self._board_connectivity_info.items()
            if binfo.get("type") != "ServoBoard" 
        ])

        if not board_ids_for_status_panel:
            no_boards_label = QLabel("<i>No other boards configured for status display.</i>")
            sensor_boards_status_layout.addWidget(no_boards_label, 0, 0, 1, max_status_cols * 2)
        else:
            for board_id_hex in board_ids_for_status_panel:
                board_conn_info = self._board_connectivity_info.get(board_id_hex)
                if not board_conn_info: continue
                board_name = board_conn_info["name"]
                name_label = QLabel(f"<b>{board_name}:</b>")
                name_label.setAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
                status_indicator = self._create_status_indicator_label("Unknown", self.STATUS_UNKNOWN_COLOR, fixed_width=self.BOARD_STATUS_LABEL_WIDTH)
                
                sensor_boards_status_layout.addWidget(name_label, status_row, status_col * 2)
                sensor_boards_status_layout.addWidget(status_indicator, status_row, status_col * 2 + 1)
                
                self._sensor_panel_board_status_labels[board_id_hex] = status_indicator 
                if status_indicator not in board_conn_info["ui_labels"]: 
                    board_conn_info["ui_labels"].append(status_indicator)
                
                status_col += 1
                if status_col >= max_status_cols:
                    status_col = 0
                    status_row += 1
            if status_row == 0 and status_col < max_status_cols : 
                 sensor_boards_status_layout.addItem(QSpacerItem(20,10, QSizePolicy.Policy.Minimum, QSizePolicy.Policy.Expanding), status_row +1, 0, 1, max_status_cols*2)
            elif status_row > 0 : 
                 sensor_boards_status_layout.addItem(QSpacerItem(20,10, QSizePolicy.Policy.Minimum, QSizePolicy.Policy.Expanding), status_row +1, 0, 1, max_status_cols*2)

        top_group_layout.addWidget(sensor_boards_status_group)
        parent_layout.addWidget(top_group_box)


    def _populate_sensor_columns_dynamically(self):
        for layout_to_clear in [self.pt_sensors_display_layout, self.other_sensors_display_layout]:
            while layout_to_clear.count():
                item = layout_to_clear.takeAt(0)
                widget = item.widget()
                if widget: widget.deleteLater()
                layout = item.layout()
                if layout: 
                    while layout.count():
                         sub_item = layout.takeAt(0)
                         sub_widget = sub_item.widget()
                         if sub_widget: sub_widget.deleteLater()
                    layout.deleteLater()

        pt_added = False
        other_added = False

        # ALL_COMPONENT_CONFIGS from config.py now includes LabJack LC if enabled
        sorted_components = sorted(config.ALL_COMPONENT_CONFIGS, key=lambda x: x['name'])

        for sensor_conf in sorted_components:
            comp_name = sensor_conf['name']
            comp_purpose = sensor_conf.get('purpose', '')
            
            comp_type_for_ui_key = None 
            is_pt_sensor = False
            target_layout = self.other_sensors_display_layout 

            config_defined_type = sensor_conf.get('type')

            if config_defined_type == 'PressureTransducer':
                comp_type_for_ui_key = 'PressureTransducer'
                is_pt_sensor = True
                target_layout = self.pt_sensors_display_layout
            elif config_defined_type == 'Thermocouple':
                comp_type_for_ui_key = 'Thermocouple'
            elif config_defined_type == 'LoadCell': 
                comp_type_for_ui_key = 'LoadCell'
            elif config_defined_type == 'Heater': 
                 comp_type_for_ui_key = 'Heater'

            if comp_type_for_ui_key is None:
                if comp_name.startswith("PT"):
                    comp_type_for_ui_key = "PressureTransducer"
                    is_pt_sensor = True
                    target_layout = self.pt_sensors_display_layout
                elif comp_name.startswith("TC"):
                    comp_type_for_ui_key = "Thermocouple"
                elif comp_name.startswith("LC"): 
                    comp_type_for_ui_key = "LoadCell"

            if comp_type_for_ui_key not in ["PressureTransducer", "Thermocouple", "LoadCell", "Heater"]:
                continue

            parent_board_id = sensor_conf.get('parent_board_id_hex')
            parent_board_name = sensor_conf.get('parent_board_name') # This will be "LabJack DAQ" for LJ LC
            if parent_board_name is None: 
                if parent_board_id is not None:
                    parent_board_name = config.BOARD_INFO_LOOKUP_TABLE.get(parent_board_id, {}).get('name', f'Board 0x{parent_board_id:02X}')
                else:
                    parent_board_name = "Unknown Board"

            sensor_entry_layout = QHBoxLayout()
            sensor_entry_layout.setSpacing(10)

            name_display_text = f"<b>{comp_name}</b>"
            if comp_purpose:
                 if is_pt_sensor:
                     name_display_text = f"<b>{comp_purpose}</b><br><font size='-2' color='dimgray'>({comp_name} on {parent_board_name})</font>"
                 else:
                      name_display_text = f"<b>{comp_name}</b><br><font size='-2' color='dimgray'>{comp_purpose} (on {parent_board_name})</font>"
            else:
                 name_display_text += f"<br><font size='-2' color='dimgray'>(on {parent_board_name})</font>"

            name_label = QLabel(name_display_text)
            name_label.setTextFormat(Qt.RichText)
            name_label.setFont(self.SENSOR_NAME_FONT)
            name_label.setWordWrap(True)

            value_label = QLabel("N/A")
            value_label.setMinimumWidth(120)
            value_label.setAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
            value_label.setToolTip(f"Sensor: {comp_name}\nBoard: {parent_board_name}\nPurpose: {comp_purpose}")
            value_label.setFont(self.SENSOR_VALUE_FONT)

            sensor_entry_layout.addWidget(name_label, 1)
            sensor_entry_layout.addWidget(value_label)

            ui_element_key = f"{comp_name}_{comp_type_for_ui_key}_value"
            self._ui_elements[ui_element_key] = value_label

            target_layout.addLayout(sensor_entry_layout)
            if is_pt_sensor: pt_added = True
            else: other_added = True

        if not pt_added:
            placeholder_label = QLabel("<i>No PT sensors configured.</i>")
            placeholder_label.setFont(self.SENSOR_NAME_FONT)
            self.pt_sensors_display_layout.addWidget(placeholder_label)
        if not other_added:
            placeholder_label = QLabel("<i>No TC/LC/Other sensors configured.</i>") 
            placeholder_label.setFont(self.SENSOR_NAME_FONT)
            self.other_sensors_display_layout.addWidget(placeholder_label)

    def _create_system_controls_group(self, parent_layout):
        system_controls_group = QGroupBox("System Status & Controls")
        system_layout = QGridLayout(system_controls_group)
        system_layout.setSpacing(10)
        system_layout.setColumnStretch(0, 0) 
        system_layout.setColumnStretch(1, 1) 
        system_layout.setColumnStretch(2, 0) 
        system_layout.setColumnStretch(3, 0) 

        row = 0
        def add_control_row(display_name, status_key, cmd_on_val=None, cmd_off_val=None, on_text=None, off_text=None):
            nonlocal row
            name_label = QLabel(f"<b>{display_name}:</b>")
            name_label.setAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
            system_layout.addWidget(name_label, row, 0)

            status_indicator = self._create_status_indicator_label("?", self.STATUS_UNKNOWN_COLOR, fixed_width=self.SYSTEM_STATUS_CONTROL_STATE_WIDTH)
            self._device_toggle_status_labels[status_key] = status_indicator
            system_layout.addWidget(status_indicator, row, 1, Qt.AlignmentFlag.AlignCenter)

            button_layout = QHBoxLayout() 
            button_layout.setSpacing(5)
            button_layout.setContentsMargins(0,0,0,0)

            has_on_button = False
            if cmd_on_val is not None:
                on_btn_text = on_text if on_text else f"{display_name.replace('Servos ', '').replace(' Mode','')} ON"
                on_btn = QPushButton(on_btn_text)
                self._apply_button_style(on_btn)
                on_btn.clicked.connect(lambda checked=False, v=cmd_on_val, n=f"{display_name} ON":
                                       self.xbee_manager.send_command_to_configured_targets(v, n))
                button_layout.addWidget(on_btn)
                has_on_button = True

            has_off_button = False
            if cmd_off_val is not None:
                off_btn_text = off_text if off_text else f"{display_name.replace('Servos ', '').replace(' Mode','')} OFF"
                off_btn = QPushButton(off_btn_text)
                self._apply_button_style(off_btn)
                off_btn.clicked.connect(lambda checked=False, v=cmd_off_val, n=f"{display_name} OFF":
                                        self.xbee_manager.send_command_to_configured_targets(v, n))
                button_layout.addWidget(off_btn)
                has_off_button = True

            if has_on_button or has_off_button:
                 system_layout.addLayout(button_layout, row, 2, 1, 2, Qt.AlignmentFlag.AlignCenter) 
            else: 
                 system_layout.addItem(QSpacerItem(10, self.DEFAULT_BUTTON_MIN_HEIGHT, QSizePolicy.Policy.Minimum, QSizePolicy.Policy.Fixed), row, 2, 1, 2)
            row += 1

        add_control_row("PC State", "pc_state") 
        add_control_row("Breakwire", "breakwire_status") 
        add_control_row("Igniter", "igniter_status", config.COMMANDS["ACTIVATE_IGNITER"], config.COMMANDS["DEACTIVATE_IGNITER"], on_text="Igniter ON", off_text="Igniter OFF")
        add_control_row("Auto Mode", "auto_mode", config.COMMANDS["AUTO_ON"], config.COMMANDS["AUTO_OFF"], on_text="Auto ON", off_text="Auto OFF")
        add_control_row("Servos Power", "servos_power", config.COMMANDS["ACTIVATE_SERVOS"], config.COMMANDS["DEACTIVATE_SERVOS"], on_text="Power ON", off_text="Power OFF")

        parent_layout.addWidget(system_controls_group)


    def _create_general_commands_group(self, parent_layout):
        general_commands_group = QGroupBox("General Commands")
        general_commands_layout = QGridLayout(general_commands_group)
        general_commands_layout.setSpacing(10)

        row, col = 0, 0
        max_cols = 2 # Adjusted to fit more buttons, can be 3 if space allows

        # Existing commands
        commands_to_add = {
            "Signal All": config.GENERAL_COMMANDS.get("Signal All"),
            "Check State": config.GENERAL_COMMANDS.get("Check State"),
            "Manual Board Status Request": self.xbee_manager.request_board_status_all_targets,
        }

        for name, action in commands_to_add.items():
            if action is None: continue
            btn = QPushButton(name)
            self._apply_button_style(btn)
            if isinstance(action, int):
                 cmd_val = action
                 btn.clicked.connect(lambda checked=False, v=cmd_val, n=name:
                                     self.xbee_manager.send_command_to_configured_targets(v, n))
            elif callable(action):
                 btn.clicked.connect(action)
            else:
                 btn.setEnabled(False)

            general_commands_layout.addWidget(btn, row, col)
            col += 1
            if col >= max_cols:
                 col = 0
                 row += 1
        
        # Add Tare Buttons
        # Ensure they start on a new row if the previous row was partially filled
        if col != 0:
            col = 0
            row += 1

        self.tare_pt_button = QPushButton("Tare All PTs")
        self._apply_button_style(self.tare_pt_button)
        self.tare_pt_button.setToolTip("Set current Pressure Transducer readings as zero offset.")
        # Connection will be done in _connect_signals to self.data_processor
        general_commands_layout.addWidget(self.tare_pt_button, row, 0) # col 0

        self.tare_lc_button = QPushButton("Tare All LCs")
        self._apply_button_style(self.tare_lc_button)
        self.tare_lc_button.setToolTip("Set current Load Cell readings (CAN & LabJack) as zero offset.")
        # Connection will be done in _connect_signals to self.data_processor
        general_commands_layout.addWidget(self.tare_lc_button, row, 1) # col 1
        
        # Example of adding another row if needed
        # row +=1
        # col = 0
        # my_other_button = QPushButton("Another Button")
        # general_commands_layout.addWidget(my_other_button, row, col)


        parent_layout.addWidget(general_commands_group)

    def _create_event_log_group(self, parent_layout):
        log_group = QGroupBox("Event Log")
        log_layout = QVBoxLayout(log_group)
        self.log_text_edit = QTextEdit()
        self.log_text_edit.setReadOnly(True)
        self.log_text_edit.setLineWrapMode(QTextEdit.LineWrapMode.WidgetWidth)
        self.log_text_edit.setMinimumHeight(200)
        self.log_text_edit.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
        log_layout.addWidget(self.log_text_edit)
        parent_layout.addWidget(log_group)


    def _connect_signals(self):
        self.xbee_manager.xbee_connected.connect(self._on_xbee_connected)
        self.xbee_manager.xbee_disconnected.connect(self._on_xbee_disconnected)
        self.xbee_manager.connection_error.connect(self._on_xbee_connection_error)
        self.xbee_manager.log_message.connect(self.add_log_message)
        self.xbee_manager.transmit_status_update.connect(self._update_transmit_status_display)
        self.xbee_manager.radio_status_updated.connect(self._update_radio_status_display)

        self.data_processor.log_message.connect(self.add_log_message)
        self.data_processor.ui_update_sensor.connect(self._update_sensor_display) 
        self.data_processor.ui_update_servo.connect(self._update_servo_display)
        self.data_processor.board_connectivity_update.connect(self._update_board_general_connectivity)
        self.data_processor.ui_update_board_detailed_status.connect(self._update_board_detailed_status_display)
        self.data_processor.ui_update_igniter_status.connect(self._update_igniter_display)
        self.data_processor.ui_update_auto_mode_status.connect(self._update_auto_mode_display)
        self.data_processor.ui_update_servos_power_status.connect(self._update_servos_power_display)
        self.data_processor.ui_update_breakwire_status.connect(self._update_breakwire_display)
        self.data_processor.ui_update_pc_state_status.connect(self._update_pc_state_display)

        # Connect Tare buttons to DataProcessor slots
        if hasattr(self, 'tare_pt_button') and hasattr(self.data_processor, 'tare_all_pressure_transducers'):
            self.tare_pt_button.clicked.connect(self.data_processor.tare_all_pressure_transducers)
        if hasattr(self, 'tare_lc_button') and hasattr(self.data_processor, 'tare_all_load_cells'):
            self.tare_lc_button.clicked.connect(self.data_processor.tare_all_load_cells)


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
        self._reset_all_board_connectivity_ui()
        self._reset_radio_status_ui()

    @Slot(str)
    def _on_xbee_disconnected(self, reason):
        self.com_port_label.setText("Port: N/A")
        self.status_bar.showMessage(f"XBee Disconnected: {reason}", 5000)
        self.connect_button.setEnabled(True)
        self.disconnect_button.setEnabled(False)
        self.add_log_message(f"XBee disconnected: {reason}")
        self._clear_all_dynamic_displays_to_stale()

    @Slot(str)
    def _on_xbee_connection_error(self, error_message):
        self.com_port_label.setText("Port: Error")
        self.status_bar.showMessage(f"XBee Connection Error: {error_message}", 5000)
        self.connect_button.setEnabled(True)
        self.disconnect_button.setEnabled(False)
        self.add_log_message(f"XBee Connection Error: {error_message}")
        self._clear_all_dynamic_displays_to_stale()

    @Slot(dict)
    def _update_transmit_status_display(self, status_info):
        address_64bit = status_info.get('address', '').upper()
        if address_64bit in self._radio_ui_elements:
            ui_set = self._radio_ui_elements[address_64bit]
            desc_text = status_info.get('description', 'N/A')

            metrics = ui_set['last_tx_desc_label'].fontMetrics()
            available_width = ui_set['last_tx_desc_label'].width() - 10 
            elided_text = metrics.elidedText(desc_text, Qt.TextElideMode.ElideRight, max(available_width, 50)) 
            ui_set['last_tx_desc_label'].setText(elided_text)
            ui_set['last_tx_desc_label'].setToolTip(desc_text) 

            status_text = status_info.get('status', 'N/A')
            ui_set['last_tx_status_label'].setText(status_text)
            ui_set['last_tx_retries_label'].setText(str(status_info.get('retries', 'N/A')))

            if "success" in status_text.lower():
                ui_set['last_tx_status_label'].setStyleSheet(f"color: {self.STATUS_ALIVE_COLOR}; font-weight: bold;")
            elif any(err in status_text.lower() for err in ["fail", "error", "timeout", "n/a", "no ack", "invalid", "skipped"]): # Added "skipped"
                ui_set['last_tx_status_label'].setStyleSheet(f"color: {self.STATUS_DEAD_COLOR}; font-weight: bold;")
            else: 
                ui_set['last_tx_status_label'].setStyleSheet("")


    @Slot(dict)
    def _update_radio_status_display(self, radio_info):
        addr = radio_info['address']
        if addr in self._radio_ui_elements:
            ui_set = self._radio_ui_elements[addr]
            status_indicator = ui_set['status_indicator']
            is_alive = radio_info.get('is_alive', False)

            bg_color = self.STATUS_ALIVE_COLOR if is_alive else self.STATUS_DEAD_COLOR
            tooltip = f"Radio: {ui_set['name_label'].toolTip()}\nStatus: {'Alive' if is_alive else 'No Response'}"
            if radio_info.get('is_connection_lost', False): # Add connection lost info
                 tooltip += "\n(Connection currently marked as lost)"
                 bg_color = self.STATUS_DEAD_COLOR # Ensure it's red if connection_lost

            radius = int(status_indicator.width() / 2)
            status_indicator.setStyleSheet(
                f"background-color: {bg_color}; "
                f"border: 1px solid dimgray; border-radius: {radius}px;"
            )
            status_indicator.setToolTip(tooltip)

            if 'last_tx_description' in radio_info:
                 self._update_transmit_status_display({
                     "address": addr,
                     "description": radio_info.get('last_tx_description', 'Healthcheck'),
                     "status": radio_info.get('last_tx_status', 'N/A'),
                     "retries": radio_info.get('last_tx_retries', 'N/A')
                 })

    @Slot(int, str, float)
    def _update_board_general_connectivity(self, board_id_8bit: int, board_name: str, timestamp: float):
        # The board_id_8bit used here is typically the SENDER_ID from the CAN message.
        # We need to ensure our _board_connectivity_info is keyed by the actual board_id that is reporting status
        # or the board_id that hosts the component.
        # For general heartbeats (any message from a CAN sender), we update the sender's connectivity.
        
        # If board_name is a SENDER_NAME (e.g. "PAD_CONTROLLER"), try to get its configured board_id
        board_id_to_update = config.get_board_id_by_name(board_name)
        if board_id_to_update is None: # Fallback if name doesn't match a board directly
            board_id_to_update = board_id_8bit # Use the ID from CAN sender field


        if board_id_to_update in self._board_connectivity_info:
            info = self._board_connectivity_info[board_id_to_update]
            info["last_seen"] = timestamp
            if info["status_str"] in ["Unknown", "Timeout", "Disconnected"]:
                info["status_str"] = "Connected"
                for label_widget in info.get("ui_labels", []):
                    if isinstance(label_widget, QLabel): 
                        self._update_board_status_label_style(label_widget, info["status_str"], self.STATUS_ALIVE_COLOR)
        # else:
            # app_logger.debug(f"General connectivity update for board_id 0x{board_id_to_update:02X} (derived from '{board_name}' or 0x{board_id_8bit:02X}) - not in _board_connectivity_info.")


    @Slot(int, str, str, dict)
    def _update_board_detailed_status_display(self, board_id_8bit: int, board_name: str, source_xbee_addr:str, status_data_dict: dict):
        # Here, board_id_8bit is the ID of the board that *sent* the status response.
        if board_id_8bit in self._board_connectivity_info:
            info = self._board_connectivity_info[board_id_8bit]
            info["last_seen"] = time.time() 

            health_code = status_data_dict.get("health_code", "OK") 
            # Simplification: If board sends detailed status, it's at least somewhat alive.
            # More complex health codes could be parsed from status_data_dict if the firmware provides them.
            current_status_str = str(health_code) if health_code else "Status OK"


            tooltip_details = [f"Board: {board_name} (ID: 0x{board_id_8bit:02X})", f"Status: {current_status_str}"]
            if "raw_payload_hex" in status_data_dict:
                tooltip_details.append(f"Raw Data: {status_data_dict['raw_payload_hex']}")


            info["status_str"] = current_status_str
            bg_color = self.STATUS_ALIVE_COLOR 
            if health_code == "WARN": bg_color = self.STATUS_WARN_COLOR
            elif health_code not in ["OK", "N/A", "Connected", "Initialized", "Status OK"]: 
                 bg_color = self.STATUS_DEAD_COLOR

            for label_widget in info.get("ui_labels", []):
                if isinstance(label_widget, QLabel):
                    self._update_board_status_label_style(label_widget, info["status_str"], bg_color)
                    label_widget.setToolTip("\n".join(tooltip_details))
        # else:
            # app_logger.debug(f"Detailed status update for board_id 0x{board_id_8bit:02X} ('{board_name}') - not in _board_connectivity_info for detailed display.")


    @Slot(str, str, str, str)
    def _update_servo_display(self, name, state_str, board_name, component_type_name):
        status_key = f"{name}_Servo_status"
        if status_key in self._ui_elements:
            label_widget = self._ui_elements[status_key]
            display_text = state_str
            label_widget.setText(display_text)

            color = self.STATUS_UNKNOWN_COLOR
            if state_str == config.SERVO_STATES[2]: color = self.STATUS_SERVO_POWERED_OPEN_COLOR 
            elif state_str == config.SERVO_STATES[0]: color = self.STATUS_SERVO_POWERED_CLOSED_COLOR 
            elif state_str == config.SERVO_STATES[3]: color = self.STATUS_SERVO_UNPOWERED_OPEN_COLOR 
            elif state_str == config.SERVO_STATES[1]: color = self.STATUS_SERVO_UNPOWERED_CLOSED_COLOR 
            elif "°" in state_str: color = self.STATUS_SERVO_POSITION_COLOR 

            self._update_status_indicator_style(label_widget, display_text, color)


    @Slot(str, str, str, str, str)
    def _update_sensor_display(self, name, value_str, unit, board_name, component_type_name):
        key = f"{name}_{component_type_name}_value"
        if key in self._ui_elements:
            value_label = self._ui_elements[key]
            value_label.setFont(self.SENSOR_VALUE_FONT)
            value_label.setText(f"{value_str} {unit}".strip())

            current_tooltip = value_label.toolTip()
            base_tooltip_lines = current_tooltip.split('\n')
            last_line_index = -1
            for i, line in enumerate(reversed(base_tooltip_lines)):
                if line.startswith("Last:"):
                    last_line_index = len(base_tooltip_lines) - 1 - i
                    break
            if last_line_index != -1:
                base_tooltip = "\n".join(base_tooltip_lines[:last_line_index])
            else: 
                base_tooltip = current_tooltip
            value_label.setToolTip(f"{base_tooltip}\nLast: {value_str} {unit}".strip())

    def _update_status_indicator_style(self, label: QLabel, text_to_display: str, background_color: str):
         label.setText(str(text_to_display))
         current_style = label.styleSheet()
         new_style = re.sub(r"background-color: [^;]+;", f"background-color: {background_color};", current_style)
         if f"background-color: {background_color};" not in new_style: 
              new_style = f"background-color: {background_color}; {current_style}" 
         label.setStyleSheet(new_style)
         self._set_label_text_color(label, background_color) 

    @Slot(str, bool, str, str)
    def _update_igniter_display(self, name, is_active, state_str, board_name):
        bg_color = self.STATUS_ALIVE_COLOR if is_active else self.STATUS_DEAD_COLOR
        if state_str == "Init": bg_color = self.STATUS_WARN_COLOR 
        if "igniter_status" in self._device_toggle_status_labels:
             self._update_status_indicator_style(self._device_toggle_status_labels["igniter_status"], state_str, bg_color)

    @Slot(str, bool, str, str)
    def _update_auto_mode_display(self, name, is_on, state_str, board_name):
        bg_color = self.STATUS_ALIVE_COLOR if is_on else self.STATUS_DEAD_COLOR
        if "auto_mode" in self._device_toggle_status_labels:
            self._update_status_indicator_style(self._device_toggle_status_labels["auto_mode"], state_str, bg_color)

    @Slot(str, bool, str, str)
    def _update_servos_power_display(self, name, is_on, state_str, board_name):
        bg_color = self.STATUS_ALIVE_COLOR if is_on else self.STATUS_DEAD_COLOR
        if "servos_power" in self._device_toggle_status_labels:
            self._update_status_indicator_style(self._device_toggle_status_labels["servos_power"], state_str, bg_color)

    @Slot(str, int, str, str)
    def _update_breakwire_display(self, name, raw_state_byte, state_str, board_name):
        bg_color = self.STATUS_UNKNOWN_COLOR
        if raw_state_byte == 0: bg_color = self.STATUS_ALIVE_COLOR 
        elif raw_state_byte == 1: bg_color = "lime"              
        elif raw_state_byte == 2: bg_color = self.STATUS_DEAD_COLOR  
        elif raw_state_byte == 3: bg_color = "orangered"         
        if "breakwire_status" in self._device_toggle_status_labels:
            self._update_status_indicator_style(self._device_toggle_status_labels["breakwire_status"], state_str, bg_color)

    @Slot(str, int, str, str)
    def _update_pc_state_display(self, name, state_int, state_str, board_name):
        bg_color = self.STATUS_UNKNOWN_COLOR
        state_str_upper = state_str.upper()
        if state_str_upper == "STARTUP": bg_color = "lightblue"
        elif state_str_upper == "AUTO_OFF": bg_color = self.STATUS_DEAD_COLOR 
        elif state_str_upper == "AUTO_ON": bg_color = self.STATUS_ALIVE_COLOR 
        elif state_str_upper == "DELAY": bg_color = self.STATUS_WARN_COLOR 
        elif state_str_upper == "FIRE": bg_color = "red" 
        elif state_str_upper == "OPEN": bg_color = "darkorange" 
        if "pc_state" in self._device_toggle_status_labels:
            self._update_status_indicator_style(self._device_toggle_status_labels["pc_state"], state_str, bg_color)


    def _check_board_timeouts(self):
        current_time = time.time()
        default_timeout_s = config.BOARD_ACK_TIMEOUT_MS / 1000.0  
        pad_controller_timeout_s = config.PAD_CONTROLLER_ACK_TIMEOUT_MS / 1000.0 

        pad_controller_board_id = config.get_board_id_by_name("CASEY") 

        for board_id_hex, info in self._board_connectivity_info.items():
            timeout_threshold_s_current_board = default_timeout_s
            if pad_controller_board_id is not None and board_id_hex == pad_controller_board_id:
                timeout_threshold_s_current_board = pad_controller_timeout_s
            
            if info["last_seen"] > 0 and info["status_str"] not in ["Timeout", "Disconnected", "Unknown"]:
                if current_time - info["last_seen"] > timeout_threshold_s_current_board:
                    app_logger.warning(f"Board {info['name']} (ID: 0x{board_id_hex:02X}) timed out. "
                                       f"Last seen {current_time - info['last_seen']:.1f}s ago (Threshold: {timeout_threshold_s_current_board:.1f}s).")
                    info["status_str"] = "Timeout"
                    for label_widget in info.get("ui_labels", []):
                        if isinstance(label_widget, QLabel):
                            self._update_board_status_label_style(label_widget, info["status_str"], self.STATUS_DEAD_COLOR)
                            label_widget.setToolTip(f"Board timed out (>{timeout_threshold_s_current_board:.1f}s since last message)")
    

    def _reset_board_connectivity_ui(self, board_id):
        if board_id in self._board_connectivity_info:
            info = self._board_connectivity_info[board_id]
            info["last_seen"] = 0
            info["status_str"] = "Unknown"
            for label_widget in info.get("ui_labels", []):
                 if isinstance(label_widget, QLabel):
                    self._update_board_status_label_style(label_widget, "Unknown", self.STATUS_UNKNOWN_COLOR)
                    label_widget.setToolTip("Board status unknown")

    def _reset_all_board_connectivity_ui(self):
        for board_id in self._board_connectivity_info.keys():
            self._reset_board_connectivity_ui(board_id)

    def _reset_radio_status_ui(self):
        for addr_hex, ui_set in self._radio_ui_elements.items():
             ui_set['last_tx_desc_label'].setText("N/A"); ui_set['last_tx_desc_label'].setToolTip("")
             ui_set['last_tx_status_label'].setText("N/A"); ui_set['last_tx_status_label'].setStyleSheet("")
             ui_set['last_tx_retries_label'].setText("N/A")

             status_indicator = ui_set['status_indicator']
             radius = int(status_indicator.width() / 2)
             status_indicator.setStyleSheet(
                 f"background-color: {self.STATUS_UNKNOWN_COLOR}; "
                 f"border: 1px solid dimgray; border-radius: {radius}px;"
             )
             status_indicator.setToolTip("Radio status unknown")


    def _clear_all_dynamic_displays_to_stale(self):
        for key, widget in self._ui_elements.items():
            if isinstance(widget, QLabel):
                if "_Servo_status" in key:
                     self._update_status_indicator_style(widget, "Unknown", self.STATUS_UNKNOWN_COLOR)
                     widget.setToolTip("Servo status unknown (disconnected)")
                elif "_value" in key :
                    widget.setText("Stale")
                    widget.setFont(self.SENSOR_VALUE_FONT) 
                    widget.setToolTip("Sensor value stale (disconnected)")

        for key, label in self._device_toggle_status_labels.items():
            self._update_status_indicator_style(label, "?", self.STATUS_UNKNOWN_COLOR)
            label.setToolTip("System status unknown (disconnected)")

        self._reset_radio_status_ui()
        self._reset_all_board_connectivity_ui()


    def _update_ui_refresh_rate(self):
        try:
            hz_text = self.ui_rate_input.text()
            hz = float(hz_text) 
            if hz >= 0:
                if hasattr(self.data_processor, 'set_ui_update_frequency'):
                     self.data_processor.set_ui_update_frequency(hz)
                     self.add_log_message(f"UI data update rate set to {hz} Hz.")
                else:
                     self.add_log_message("Error: Data processor has no rate setting method.")
            else:
                raise ValueError("Rate must be non-negative.")
        except ValueError:
            self.add_log_message(f"Invalid UI data update rate: '{hz_text}'. Please enter a non-negative number.")
            current_hz_text = "N/A"
            if hasattr(self.data_processor, '_ui_update_timer'):
                 current_interval_ms = self.data_processor._ui_update_timer.interval()
                 current_hz = (1000.0 / current_interval_ms) if current_interval_ms > 0 else 0
                 current_hz_text = f"{current_hz:.1f}"
            self.ui_rate_input.setText(current_hz_text)
        except Exception as e:
             app_logger.error(f"Error setting UI refresh rate: {e}")
             self.ui_rate_input.setText(str(config.DEFAULT_UI_UPDATE_HZ)) 


    def closeEvent(self, event):
        self.add_log_message("Closing application...")
        if self._board_status_check_timer.isActive():
            self._board_status_check_timer.stop()
        if hasattr(self.data_processor, 'close_labjack'): # Ensure LabJack is closed
            self.data_processor.close_labjack()
        if hasattr(self.data_processor, '_ui_update_timer') and self.data_processor._ui_update_timer.isActive():
            self.data_processor._ui_update_timer.stop()
            app_logger.info("Stopped Data Processor UI update timer.")
        self.xbee_manager.disconnect_device() 
        app_logger.info("Application closed.")
        super().closeEvent(event)


# --- Mock Objects and Main Execution Block ---
if __name__ == '__main__':
    import random 
    app = QApplication(sys.argv)

    def handle_sigint(*args):
        print("\nCtrl+C detected. Requesting application exit...")
        QTimer.singleShot(0, app.quit)

    signal.signal(signal.SIGINT, handle_sigint)

    class MockXBeeManager(QObject):
        xbee_connected = Signal(str); xbee_disconnected = Signal(str)
        connection_error = Signal(str); log_message = Signal(str)
        transmit_status_update = Signal(dict); radio_status_updated = Signal(dict)
        def __init__(self): super().__init__()
        def autodetect_and_connect(self): self.log_message.emit("Mock Autodetect Start"); QTimer.singleShot(100, lambda: self.xbee_connected.emit("/dev/mockUSB0"))
        def disconnect_device(self): self.log_message.emit("Mock Disconnect Start"); QTimer.singleShot(50, lambda: self.xbee_disconnected.emit("User mock disconnect"))
        def send_command_to_configured_targets(self, v, n): self.log_message.emit(f"Mock Send Cmd: {n} (Value: {v})"); self._simulate_tx_status(n)
        def check_all_radio_statuses(self): self.log_message.emit("Mock Radio Healthcheck Request Sent"); QTimer.singleShot(300, self._simulate_radio_status_responses)
        def request_board_status_all_targets(self): self.log_message.emit("Mock Board Status Request All"); self._simulate_board_status_response()
        def _simulate_tx_status(self, desc):
             if config.XBEE_TARGET_RADIO_CONFIG:
                 addr_conf = random.choice(config.XBEE_TARGET_RADIO_CONFIG); addr = addr_conf[1]
                 status = "Success" if random.random() > 0.1 else "No ACK"
                 retries = 0 if status == "Success" else random.randint(1, 3)
                 self.transmit_status_update.emit({"address": addr, "status": status, "description": desc, "retries": retries})
                 if status == "Success": self.radio_status_updated.emit({"address": addr, "is_alive": True})
        def _simulate_radio_status_responses(self):
            self.log_message.emit("Simulating Radio Healthcheck Responses...")
            for name, addr in config.XBEE_TARGET_RADIO_CONFIG:
                is_alive = random.random() > 0.2
                self.radio_status_updated.emit({"address": addr, "is_alive": is_alive,"last_tx_description": "Healthcheck","last_tx_status": "Success" if is_alive else "Timeout","last_tx_retries": 0 if is_alive else 3})
            self.log_message.emit("Finished simulating radio responses.")
        def _simulate_board_status_response(self):
             board_ids = [bid for bid, binfo in config.BOARD_INFO_LOOKUP_TABLE.items() if binfo.get("type") not in ["ServoBoard"]] # All non-servo boards for status mock
             if board_ids: 
                 board_id = random.choice(board_ids)
                 board_info = config.BOARD_INFO_LOOKUP_TABLE[board_id]
                 self.log_message.emit(f"Intending to simulate detailed status for {board_info['name']} (ID: {board_id}) - MockDataProc will emit signal.")


    class MockDataProcessor(QObject):
        ui_update_sensor = Signal(str, str, str, str, str)
        ui_update_servo = Signal(str, str, str, str)
        log_message = Signal(str)
        board_connectivity_update = Signal(int, str, float)
        ui_update_board_detailed_status = Signal(int, str, str, dict)
        ui_update_igniter_status = Signal(str, bool, str, str)
        ui_update_auto_mode_status = Signal(str, bool, str, str)
        ui_update_servos_power_status = Signal(str, bool, str, str)
        ui_update_breakwire_status = Signal(str, int, str, str)
        ui_update_pc_state_status = Signal(str, int, str, str)
        
        _ui_update_timer = QTimer() 

        def __init__(self):
            super().__init__()
            self._ui_update_timer = QTimer(self) 
            self._ui_update_timer.timeout.connect(self.simulate_periodic_updates)
            self._sim_counter = 0
            self._mock_pt_tare_offsets = {}
            self._mock_lc_tare_offsets = {}
            self._mock_last_raw_values = {}

        def set_ui_update_frequency(self, hz):
            interval_ms = int(1000 / hz) if hz > 0 else 0
            self.log_message.emit(f"Mock UI Freq set: {hz}Hz (Interval: {interval_ms}ms)")
            if interval_ms > 0:
                self._ui_update_timer.setInterval(interval_ms)
                if not self._ui_update_timer.isActive(): 
                    self._ui_update_timer.start()
            else: 
                if self._ui_update_timer.isActive():
                    self._ui_update_timer.stop()

        def process_incoming_xbee_message(self, msg): pass 

        @Slot()
        def tare_all_pressure_transducers(self):
            self.log_message.emit("Mock: Tare All PTs button clicked.")
            # Simple mock: just clear offsets and log
            self._mock_pt_tare_offsets.clear()
            for pt_conf in config.PT_LOOKUP_TABLE:
                pt_name = pt_conf['name']
                # Simulate taring by setting offset to its last "raw" value
                raw_val_key = f"{pt_name}_PressureTransducer"
                if raw_val_key in self._mock_last_raw_values:
                    self._mock_pt_tare_offsets[pt_name] = self._mock_last_raw_values[raw_val_key]
                    self.log_message.emit(f"Mock: PT '{pt_name}' tared with offset {self._mock_last_raw_values[raw_val_key]:.2f}.")
            self.log_message.emit("Mock: PT taring process complete.")


        @Slot()
        def tare_all_load_cells(self):
            self.log_message.emit("Mock: Tare All LCs button clicked.")
            self._mock_lc_tare_offsets.clear()
            # CAN LCs
            for lc_conf in config.LOADCELL_LOOKUP_TABLE:
                lc_name = lc_conf['name']
                raw_val_key = f"{lc_name}_LoadCell"
                if raw_val_key in self._mock_last_raw_values:
                    self._mock_lc_tare_offsets[lc_name] = self._mock_last_raw_values[raw_val_key]
                    self.log_message.emit(f"Mock: CAN LC '{lc_name}' tared with offset {self._mock_last_raw_values[raw_val_key]:.1f}.")
            # LabJack LC
            if config.LABJACK_ENABLED and hasattr(config, 'LABJACK_SUMMED_LC_NAME'):
                lj_lc_name = config.LABJACK_SUMMED_LC_NAME
                raw_val_key_lj = f"{lj_lc_name}_LoadCell"
                if raw_val_key_lj in self._mock_last_raw_values:
                     self._mock_lc_tare_offsets[lj_lc_name] = self._mock_last_raw_values[raw_val_key_lj]
                     self.log_message.emit(f"Mock: LabJack LC '{lj_lc_name}' tared with offset {self._mock_last_raw_values[raw_val_key_lj]:.1f}.")
            self.log_message.emit("Mock: LC taring process complete.")
        
        def close_labjack(self): # Mock method
            self.log_message.emit("Mock: Close LabJack called.")


        @Slot()
        def simulate_periodic_updates(self):
            current_ts = time.time(); self._sim_counter += 1

            if self._sim_counter % 5 == 0:
                board_ids = list(config.BOARD_INFO_LOOKUP_TABLE.keys())
                if board_ids and random.random() < 0.8: 
                    board_id_for_heartbeat = random.choice(board_ids)
                    board_info_hb = config.BOARD_INFO_LOOKUP_TABLE[board_id_for_heartbeat]
                    # Emit connectivity for the actual board ID
                    self.board_connectivity_update.emit(board_id_for_heartbeat, board_info_hb["name"], current_ts)

                    if random.random() < 0.1: # Simulate a detailed status for this board
                         health = random.choice(["OK", "OK", "WARN", "FAIL", "Initialized"])
                         mock_addr = f"0013A200MOCK{board_id_for_heartbeat:02X}" 
                         self.ui_update_board_detailed_status.emit(
                             board_id_for_heartbeat, board_info_hb["name"], mock_addr,
                             {"health_code": health, "raw_payload_hex": f"SIM_DETAILED_{random.randint(0,999):03d}"}
                         )
            
            # Simulate LabJack Load Cell Data
            if config.LABJACK_ENABLED and hasattr(config, 'LABJACK_SUMMED_LC_NAME') and hasattr(config, 'LABJACK_LOADCELL_UNIT'):
                lc_name = config.LABJACK_SUMMED_LC_NAME
                lc_unit = config.LABJACK_LOADCELL_UNIT
                lj_lc_conf = next((c for c in config.ALL_COMPONENT_CONFIGS if c.get("name") == lc_name and c.get("source_type") == "LabJack"), None)
                lc_board_name = lj_lc_conf.get("parent_board_name", "LabJack DAQ") if lj_lc_conf else "LabJack DAQ"

                raw_weight = random.uniform(200, 800) + random.uniform(-20, 20) + 72.0 
                self._mock_last_raw_values[f"{lc_name}_LoadCell"] = raw_weight # Store raw for mock taring
                tare_offset = self._mock_lc_tare_offsets.get(lc_name, 0.0)
                tared_weight = raw_weight - tare_offset
                
                value_str = f"{tared_weight:.1f}"
                self.ui_update_sensor.emit(lc_name, value_str, lc_unit, lc_board_name, "LoadCell")

            # Simulate OTHER sensor data (PT, TC, CAN LC)
            if config.ALL_COMPONENT_CONFIGS and random.random() < 0.7: 
                sensor_conf = random.choice(config.ALL_COMPONENT_CONFIGS)
                comp_name = sensor_conf['name']
                
                is_labjack_sensor_item = (config.LABJACK_ENABLED and \
                                         hasattr(config, 'LABJACK_SUMMED_LC_NAME') and \
                                         comp_name == config.LABJACK_SUMMED_LC_NAME)
                is_not_can_source_for_this_loop = sensor_conf.get("source_type") == "LabJack"

                if is_labjack_sensor_item or is_not_can_source_for_this_loop:
                    pass 
                else:
                    comp_type_name = "Unknown" 
                    val_str, unit_str = "N/A", ""
                    raw_float_val = 0.0
                    tared_float_val = 0.0
                    config_defined_type = sensor_conf.get('type')

                    if config_defined_type == 'PressureTransducer' or (not config_defined_type and comp_name.startswith("PT")):
                        comp_type_name = "PressureTransducer"
                        raw_float_val = random.uniform(-5.0, 1550.0)
                        self._mock_last_raw_values[f"{comp_name}_PressureTransducer"] = raw_float_val
                        tare_offset = self._mock_pt_tare_offsets.get(comp_name, 0.0)
                        tared_float_val = raw_float_val - tare_offset
                        val_str, unit_str = f"{tared_float_val:.1f}", sensor_conf.get("unit", "PSI")
                    elif config_defined_type == 'Thermocouple' or (not config_defined_type and comp_name.startswith("TC")):
                        comp_type_name = "Thermocouple"
                        raw_float_val = random.uniform(18.0, 55.0) # TCs not usually tared in mock
                        val_str, unit_str = f"{raw_float_val:.1f}", sensor_conf.get("unit", "°C")
                    elif config_defined_type == 'LoadCell': # Catches CAN LoadCells
                        comp_type_name = "LoadCell"
                        raw_float_val = random.uniform(-100.0, 5100.0)
                        self._mock_last_raw_values[f"{comp_name}_LoadCell"] = raw_float_val
                        tare_offset = self._mock_lc_tare_offsets.get(comp_name, 0.0)
                        tared_float_val = raw_float_val - tare_offset
                        val_str, unit_str = f"{tared_float_val:.1f}", sensor_conf.get("unit", "lbf")
                    
                    if comp_type_name != "Unknown":
                        parent_board_id = sensor_conf.get("parent_board_id_hex")
                        parent_board_name = "Unknown Board" 
                        if parent_board_id is not None: 
                            parent_board_name = config.BOARD_INFO_LOOKUP_TABLE.get(parent_board_id, {}).get("name", f"Brd 0x{parent_board_id:02X}")
                        
                        self.ui_update_sensor.emit(comp_name, val_str, unit_str, parent_board_name, comp_type_name)

            if config.SERVO_LOOKUP_TABLE and random.random() < 0.3:
                servo_conf = random.choice(config.SERVO_LOOKUP_TABLE); parent_board_id = servo_conf.get("parent_board_id_hex")
                if parent_board_id is not None:
                    parent_board_name = config.BOARD_INFO_LOOKUP_TABLE.get(parent_board_id, {}).get("name", f"Brd 0x{parent_board_id:02X}")
                    state_val = random.choice(list(config.SERVO_STATES.keys())); state_str = config.SERVO_STATES[state_val]
                    self.ui_update_servo.emit(servo_conf["name"], state_str, parent_board_name, "Servo")
                    self.board_connectivity_update.emit(parent_board_id, parent_board_name, current_ts) 

            pad_ctrl_board_id = config.get_board_id_by_name("CASEY") or config.BOARD_CAN_ID_MAPPING.get("SENDER_PAD_CONTROLLER")
            if pad_ctrl_board_id is not None:
                 pad_ctrl_name = config.BOARD_INFO_LOOKUP_TABLE.get(pad_ctrl_board_id, {}).get("name", "PAD_CTRL")
                 if self._sim_counter % 7 == 0: pc_state_val = random.choice(list(config.PC_STATES.keys())); self.ui_update_pc_state_status.emit("PCState", pc_state_val, config.PC_STATES[pc_state_val], pad_ctrl_name)
                 if random.random() < 0.1: ign_state = random.choice([0,1,2]); self.ui_update_igniter_status.emit("Igniter", ign_state==2, config.IGNITER_STATES[ign_state], pad_ctrl_name)
                 if random.random() < 0.1: auto_state = random.choice([0, 1]); self.ui_update_auto_mode_status.emit("AutoMode", auto_state==1, config.ON_OFF_STATES[auto_state], pad_ctrl_name)
                 if random.random() < 0.1: power_state = random.choice([0, 1]); self.ui_update_servos_power_status.emit("ServosPower", power_state==1, config.ON_OFF_STATES[power_state], pad_ctrl_name)
                 if random.random() < 0.1: bw_state_val = random.choice(list(config.BREAKWIRE_STATES.keys())); self.ui_update_breakwire_status.emit("Breakwire", bw_state_val, config.BREAKWIRE_STATES[bw_state_val], pad_ctrl_name)


    mock_xbee = MockXBeeManager()
    mock_data_proc = MockDataProcessor()

    main_window = ControlPanelWindow(mock_xbee, mock_data_proc)
    main_window.show()

    mock_data_proc.set_ui_update_frequency(config.DEFAULT_UI_UPDATE_HZ) 

    print("Mock Application started. Press Ctrl+C in terminal to exit gracefully.")
    exit_code = app.exec()
    print(f"Application exited with code: {exit_code}")
    sys.exit(exit_code)