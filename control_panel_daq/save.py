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
    BOARD_STATUS_LABEL_WIDTH = 120 # Increased width for board status (Connected/Timeout etc.)
    SYSTEM_STATUS_CONTROL_STATE_WIDTH = 130
    SERVO_REPORTED_STATE_WIDTH = 130
    STATUS_INDICATOR_HEIGHT = 25
    RADIO_STATUS_CIRCLE_SIZE = 25 # Diameter for radio status circle

    # Fonts
    INDICATOR_FONT = QFont()
    # *** Larger fonts for sensor display ***
    SENSOR_NAME_FONT = QFont()
    SENSOR_VALUE_FONT = QFont()


    def __init__(self, xbee_manager_instance, data_processor_instance, parent=None):
        super().__init__(parent)
        self.xbee_manager = xbee_manager_instance
        self.data_processor = data_processor_instance

        self.setWindowTitle("XBee CAN Control Panel")
        self.setGeometry(50, 50, 1700, 1050) # Slightly larger window

        self._ui_elements = {} # General UI elements (like sensor value labels)
        self._radio_ui_elements = {} # Specific for radio status widgets
        self._device_toggle_status_labels = {} # For system status indicators (igniter, auto, etc.)
        self._board_connectivity_info = {} # Tracks board status (last_seen, ui labels)
        self._sensor_panel_board_status_labels = {} # Status labels in the bottom-right panel

        # Initialize fonts
        self.INDICATOR_FONT.setPointSize(9)
        self.INDICATOR_FONT.setBold(True)
        # *** Use larger point sizes ***
        self.SENSOR_NAME_FONT.setPointSize(14)
        self.SENSOR_VALUE_FONT.setPointSize(15)
        self.SENSOR_VALUE_FONT.setBold(True)


        # Initialize board info FIRST
        self._initialize_board_connectivity_info()

        # Build the UI
        self._init_ui()
        self._connect_signals()

        # Start timers
        self._board_status_check_timer = QTimer(self)
        self._board_status_check_timer.timeout.connect(self._check_board_timeouts)
        self._board_status_check_timer.start(config.BOARD_STATUS_CHECK_TIMER_MS)

        # Attempt auto-connect after UI is shown
        QTimer.singleShot(500, self.xbee_manager.autodetect_and_connect)

    def _apply_button_style(self, button: QPushButton, min_height=DEFAULT_BUTTON_MIN_HEIGHT):
        button.setMinimumHeight(min_height)
        # button.setSizePolicy(QSizePolicy.Policy.Preferred, QSizePolicy.Policy.Fixed)

    # Updated to create standard rectangular indicators
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
        self._set_label_text_color(label, color) # Ensure initial text color is correct
        return label

    # Helper to set text color based on background lightness
    def _set_label_text_color(self, label: QLabel, background_color_str: str):
         bg_qcolor = QColor(background_color_str)
         text_color = "black" if bg_qcolor.lightnessF() > 0.5 else "white"
         # Update only the color part of the stylesheet
         current_style = label.styleSheet()
         new_style = re.sub(r"color: (black|white);", f"color: {text_color};", current_style)
         # If color rule doesn't exist, append it (basic case)
         if f"color: {text_color};" not in new_style:
             # Find the position of the first semicolon or the end of the string
             insert_pos = new_style.find(';') + 1 if ';' in new_style else len(new_style)
             if insert_pos > 0 and not new_style.strip().endswith(';'):
                  new_style = new_style.strip() + ';' + f" color: {text_color};"
             elif insert_pos == 0: # Empty style string
                   # Should not happen if style is always set initially, but handle defensively
                   # Set a reasonable default style if it was somehow empty
                   current_style_base = f"background-color: {background_color_str}; border: 1px solid dimgray; border-radius: 5px; padding: 2px;"
                   new_style = current_style_base + f" color: {text_color};"
             else:
                  new_style = new_style[:insert_pos] + f" color: {text_color};" + new_style[insert_pos:]

         label.setStyleSheet(new_style)


    # Updated style function specifically for BOARD status labels
    def _update_board_status_label_style(self, label: QLabel, status_text: str, background_color: str):
        label.setText(status_text)
        label.setFont(self.INDICATOR_FONT) # Ensure correct font
        border_radius = 5 # Match standard indicators
        label.setStyleSheet(
            f"background-color: {background_color}; "
            f"border: 1px solid dimgray; border-radius: {border_radius}px; padding: 2px; font-weight: bold;"
        )
        self._set_label_text_color(label, background_color) # Set text color

    def _init_ui(self):
        main_widget = QWidget()
        self.setCentralWidget(main_widget)
        overall_layout = QVBoxLayout(main_widget)

        # --- Top Bar (Connection, UI Rate, Radio Status) ---
        top_bar_layout = QHBoxLayout()
        top_bar_layout.setSpacing(15)

        # XBee Connection Group
        conn_group = QGroupBox("XBee Connection")
        conn_layout = QHBoxLayout(conn_group)
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

        # UI Settings Group
        ui_rate_group = QGroupBox("UI Settings")
        ui_rate_layout = QHBoxLayout(ui_rate_group)
        ui_rate_layout.addWidget(QLabel("UI Data Update (Hz):"))
        self.ui_rate_input = QLineEdit(str(config.DEFAULT_UI_UPDATE_HZ))
        self.ui_rate_input.setFixedWidth(50)
        self.ui_rate_input.editingFinished.connect(self._update_ui_refresh_rate)
        ui_rate_layout.addWidget(self.ui_rate_input)
        top_bar_layout.addWidget(ui_rate_group)

        # Radio Status Area (No GroupBox)
        radio_status_widget = QWidget() # Container for grid + button
        radio_status_layout = QHBoxLayout(radio_status_widget)
        radio_status_layout.setContentsMargins(5, 2, 5, 2) # Top/bottom margins
        radio_status_layout.setSpacing(5) # TRY REDUCING THIS (e.g., from 8 to 4 or 5) - space between grid and button
        self._create_radio_status_elements(radio_status_layout)
        top_bar_layout.addWidget(radio_status_widget, 1)

        overall_layout.addLayout(top_bar_layout)

        # --- Main Content Splitter ---
        splitter = QSplitter(Qt.Orientation.Horizontal)

        # --- Left Column ---
        left_column_widget = QWidget()
        left_column_layout = QVBoxLayout(left_column_widget)
        left_column_layout.setSpacing(15)
        self._create_servo_controls_group(left_column_layout)
        self._create_system_controls_group(left_column_layout)
        self._create_general_commands_group(left_column_layout)
        self._create_event_log_group(left_column_layout)
        left_column_layout.addStretch(1)
        splitter.addWidget(left_column_widget)

        # --- Right Column ---
        right_column_widget = QWidget()
        right_column_layout = QVBoxLayout(right_column_widget)
        right_column_layout.setSpacing(15)
        self._create_sensor_display_and_board_status_section(right_column_layout)
        right_column_layout.addStretch(1)
        splitter.addWidget(right_column_widget)

        splitter.setSizes([750, 950]) # Adjust initial split ratio
        overall_layout.addWidget(splitter)

        # --- Status Bar ---
        self.status_bar = QStatusBar()
        self.setStatusBar(self.status_bar)
        self.status_bar.showMessage("Application Started. Waiting for XBee connection...")

    def _initialize_board_connectivity_info(self):
        """Populates the _board_connectivity_info dict for all known boards."""
        self._board_connectivity_info.clear()
        for board_id_hex, board_info_item in config.BOARD_INFO_LOOKUP_TABLE.items():
            self._board_connectivity_info[board_id_hex] = {
                "name": board_info_item["name"],
                "type": board_info_item.get("type", "UnknownBoard"),
                "components_hosted": board_info_item.get("components_hosted", []), # Use updated key
                "last_seen": 0, "status_str": "Unknown", "ui_labels": []
            }

        # Add PAD_CONTROLLER if not already in BOARD_INFO
        pad_controller_id = config.BOARD_CAN_ID_MAPPING.get("SENDER_PAD_CONTROLLER")
        if pad_controller_id is not None and pad_controller_id not in self._board_connectivity_info:
             casey_id = config.get_board_id_by_name("CASEY")
             if casey_id is None: # Only add if no board named CASEY exists
                 self._board_connectivity_info[pad_controller_id] = {
                    "name": "PAD_CTRL",
                    "type": "ControllerBoard",
                    "components_hosted": [],
                    "last_seen": 0, "status_str": "Unknown", "ui_labels": []
                 }

        app_logger.info(f"Initialized connectivity tracking for {len(self._board_connectivity_info)} boards/systems.")

    # **REVISED Radio Status Creation (Reduced Spacing)**
    def _create_radio_status_elements(self, parent_layout):
        """Populates the given QHBoxLayout with radio status grid and button."""
        radio_grid_layout = QGridLayout()
        # *** Reduce HORIZONTAL spacing within the grid ***
        radio_grid_layout.setHorizontalSpacing(4) 
        radio_grid_layout.setVerticalSpacing(3)   # Vertical spacing (you said this is good)
        radio_grid_layout.setContentsMargins(0, 0, 0, 0)

        headers = ["", "Radio (Addr)", "Last TX Cmd", "TX Status", "R"]
        header_labels = []
        for col, header_text in enumerate(headers):
            header_label = QLabel(f"<b>{header_text}</b>")
            # Align Center except for Name and Command Description
            align = Qt.AlignmentFlag.AlignCenter if col != 1 and col != 2 else Qt.AlignmentFlag.AlignLeft
            header_label.setAlignment(align | Qt.AlignmentFlag.AlignVCenter)
            radio_grid_layout.addWidget(header_label, 0, col)
            header_labels.append(header_label)

        self._radio_ui_elements.clear()
        row = 1
        num_radios = len(config.XBEE_TARGET_RADIO_CONFIG)

        # --- Button Height Estimation (Copied from previous correct version, assuming vertical is okay) ---
        estimated_header_row_height = 0
        if header_labels: # Ensure header_labels is not empty
            header_font_metrics = header_labels[0].fontMetrics()
            estimated_header_row_height = header_font_metrics.height()
        if num_radios > 0 : # Add spacing if there are data rows
            estimated_header_row_height += radio_grid_layout.verticalSpacing()

        estimated_data_row_height = self.RADIO_STATUS_CIRCLE_SIZE
        # Add inter-row spacing only if there's more than one data row.
        # This was a slight bug in previous logic, data row already includes its own height.
        # The spacing is between rows.

        grid_height_estimate = estimated_header_row_height
        if num_radios > 0:
            grid_height_estimate += (self.RADIO_STATUS_CIRCLE_SIZE * num_radios) # Height of all data circles
            if num_radios > 1: # Add N-1 vertical spacings for N data rows
                grid_height_estimate += (radio_grid_layout.verticalSpacing() * (num_radios - 1))
        else: # No data rows, just header
             pass # grid_height_estimate is already header_row_height (or 0 if no headers/radios)


        grid_height_estimate += 2 # Small buffer for borders/etc.
        button_min_height = max(self.DEFAULT_BUTTON_MIN_HEIGHT, int(grid_height_estimate))
        if num_radios == 0: # If no radios, button might just be default height
            button_min_height = self.DEFAULT_BUTTON_MIN_HEIGHT
        # --- End Height Estimation ---


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
            # *** Reduce minimum width if 150 is too much ***
            last_tx_desc_label.setMinimumWidth(120) # TRY REDUCING (e.g. to 100-120)
            last_tx_desc_label.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Preferred)

            last_tx_status_label = QLabel("N/A")
            # *** Reduce minimum width if 70 is too much ***
            last_tx_status_label.setMinimumWidth(60) # TRY REDUCING (e.g. to 50-60)

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

        # Adjust column stretch - you might want to make these more even if columns are narrower
        radio_grid_layout.setColumnStretch(1, 2) # Radio Name
        radio_grid_layout.setColumnStretch(2, 2) # Last TX Cmd (was 3, try reducing if desc label is shorter)
        radio_grid_layout.setColumnStretch(3, 1) # TX Status

        parent_layout.addLayout(radio_grid_layout)

        refresh_button = QPushButton("Radio Health")
        refresh_button.setMinimumHeight(button_min_height)
        refresh_button.setMaximumHeight(button_min_height)
        refresh_button.setMinimumWidth(90)
        refresh_button.setToolTip("Send Radio Healthchecks (to all targets)")
        refresh_button.clicked.connect(self.xbee_manager.check_all_radio_statuses)
        parent_layout.addWidget(refresh_button, 0, Qt.AlignmentFlag.AlignTop)

        # Also, the QHBoxLayout containing the grid and button:
        # radio_status_layout.setSpacing(8) # In _init_ui(). Reduce this if the button is too far from the grid.
        # For example: radio_status_layout.setSpacing(4)

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

        # Use the combined component config list for servos
        for servo_conf in config.SERVO_LOOKUP_TABLE:
            name = servo_conf["name"]
            purpose = servo_conf.get("purpose", "") # Get purpose if available
            parent_board_id = servo_conf.get("parent_board_id_hex")

            if parent_board_id is None:
                app_logger.warning(f"Servo config for '{name}' missing parent board ID. Skipping.")
                continue

            board_info = self._board_connectivity_info.get(parent_board_id)
            board_name = board_info["name"] if board_info else f"Board 0x{parent_board_id:02X}"

            # Display name and purpose
            name_display = f"<b>{name}</b>"
            if purpose:
                 name_display += f"<br><font size='-1' color='dimgray'>{purpose}</font>"
            name_display += f"<br><font size='-2' color='grey'>({board_name})</font>"

            name_label = QLabel(name_display)
            name_label.setTextFormat(Qt.RichText)
            name_label.setWordWrap(True)
            servos_layout.addWidget(name_label, row, 0, Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter)

            # Board Status Indicator (Rectangular)
            board_status_indicator = self._create_status_indicator_label("Unknown", self.STATUS_UNKNOWN_COLOR, fixed_width=self.BOARD_STATUS_LABEL_WIDTH)
            servos_layout.addWidget(board_status_indicator, row, 1, Qt.AlignmentFlag.AlignCenter)

            if board_info:
                board_info["ui_labels"].append(board_status_indicator) # Track for updates
            else:
                 app_logger.warning(f"Board ID 0x{parent_board_id:02X} for servo {name} not found in _board_connectivity_info during UI creation.")

            # Servo State Label (Rectangular)
            servo_state_label = self._create_status_indicator_label("Unknown", self.STATUS_UNKNOWN_COLOR, fixed_width=self.SERVO_REPORTED_STATE_WIDTH)
            self._ui_elements[f"{name}_Servo_status"] = servo_state_label
            servos_layout.addWidget(servo_state_label, row, 2, Qt.AlignmentFlag.AlignCenter)

            # Buttons
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

        servos_layout.setColumnStretch(0, 3) # Give Name/Purpose column more space
        servos_layout.setColumnStretch(1, 1)
        servos_layout.setColumnStretch(2, 1)
        servos_layout.setColumnStretch(3, 0)
        servos_layout.setColumnStretch(4, 0)
        servos_group.setLayout(servos_layout)
        parent_layout.addWidget(servos_group)


    # **REVISED Sensor Display Section Setup (calls updated populate function)**
    def _create_sensor_display_and_board_status_section(self, parent_layout):
        top_group_box = QGroupBox("Sensor Data & Board Connectivity Status")
        top_group_layout = QVBoxLayout(top_group_box)

        scroll_area = QScrollArea()
        scroll_area.setWidgetResizable(True)
        scroll_area.setFrameShape(QFrame.Shape.NoFrame) # Make scroll area invisible

        scroll_content_widget = QWidget()
        scroll_content_layout = QVBoxLayout(scroll_content_widget) # Use QVBox for main scroll content

        # --- Sensor Columns ---
        sensor_columns_container_widget = QWidget() # Holds the HBox for columns
        sensor_columns_layout = QHBoxLayout(sensor_columns_container_widget)
        sensor_columns_layout.setSpacing(15)
        sensor_columns_layout.setAlignment(Qt.AlignmentFlag.AlignTop) # Align columns top

        # Column 1: PT Sensors
        pt_column_group = QGroupBox("Pressure Transducers (PT)")
        pt_column_vbox_layout = QVBoxLayout(pt_column_group) # Use a QVBoxLayout inside group
        self.pt_sensors_display_layout = QVBoxLayout() # Layout specifically for PT sensor entries
        # *** Increase spacing between sensor entries ***
        self.pt_sensors_display_layout.setSpacing(10) # Increased from 6
        pt_column_vbox_layout.addLayout(self.pt_sensors_display_layout)
        pt_column_vbox_layout.addStretch(1) # Push sensors to top
        sensor_columns_layout.addWidget(pt_column_group, 1) # Add group to HBox, stretch factor 1

        # Column 2: Other Sensors (TC, Load Cell) - Renamed Group slightly
        other_column_group = QGroupBox("Other Sensors (TC, LC, etc.)")
        other_column_vbox_layout = QVBoxLayout(other_column_group)
        self.other_sensors_display_layout = QVBoxLayout() # Layout for other sensor entries
        # *** Increase spacing between sensor entries ***
        self.other_sensors_display_layout.setSpacing(10) # Increased from 6
        other_column_vbox_layout.addLayout(self.other_sensors_display_layout)
        other_column_vbox_layout.addStretch(1)
        sensor_columns_layout.addWidget(other_column_group, 1)

        # *** Call the updated populate function ***
        self._populate_sensor_columns_dynamically()

        scroll_content_layout.addWidget(sensor_columns_container_widget) # Add columns container to scroll content
        scroll_area.setWidget(scroll_content_widget)
        top_group_layout.addWidget(scroll_area) # Add scroll area to main group

        # --- Separator Line ---
        line = QFrame()
        line.setFrameShape(QFrame.Shape.HLine)
        line.setFrameShadow(QFrame.Shadow.Sunken)
        top_group_layout.addWidget(line)

        # --- Board Connections (Non-Servo Boards) ---
        # (This part remains the same as the previous version)
        sensor_boards_status_group = QGroupBox("Sensor/System Board Connection Status")
        sensor_boards_status_layout = QGridLayout(sensor_boards_status_group)
        sensor_boards_status_layout.setSpacing(10)
        self._sensor_panel_board_status_labels.clear()
        status_row, status_col = 0, 0
        max_status_cols = 3
        board_ids_for_status_panel = sorted([
            bid for bid, binfo in self._board_connectivity_info.items()
            if binfo.get("type") not in ["ServoBoard", "ControllerBoard"]
        ])
        if not board_ids_for_status_panel:
            no_boards_label = QLabel("<i>No dedicated sensor boards configured.</i>")
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
            if status_row < 2 :
                 sensor_boards_status_layout.addItem(QSpacerItem(20, 10, QSizePolicy.Policy.Minimum, QSizePolicy.Policy.Expanding), status_row + 1, 0)

        top_group_layout.addWidget(sensor_boards_status_group)
        # top_group_layout.addStretch(1) # Don't stretch this group excessively
        parent_layout.addWidget(top_group_box)


    # **REVISED Helper to Populate Sensor Columns (Larger Font, Spacing set in parent layout)**
    def _populate_sensor_columns_dynamically(self):
        """Reads sensor configs (from config.ALL_COMPONENT_CONFIGS) and creates UI elements."""
        # Clear existing sensor widgets first
        for layout_to_clear in [self.pt_sensors_display_layout, self.other_sensors_display_layout]:
            while layout_to_clear.count():
                item = layout_to_clear.takeAt(0)
                widget = item.widget()
                if widget: widget.deleteLater()
                layout = item.layout()
                if layout: # If the item was a layout itself
                    while layout.count():
                         sub_item = layout.takeAt(0)
                         sub_widget = sub_item.widget()
                         if sub_widget: sub_widget.deleteLater()
                    layout.deleteLater()

        pt_added = False
        other_added = False

        # Use ALL_COMPONENT_CONFIGS which combines the lists from config.py
        # *** This list intentionally excludes Heaters based on the config.py setup ***
        sorted_components = sorted(config.ALL_COMPONENT_CONFIGS, key=lambda x: x['name'])

        for sensor_conf in sorted_components:
            comp_name = sensor_conf['name']
            comp_purpose = sensor_conf.get('purpose', '')
            comp_type_name = ""
            is_pt_sensor = False
            target_layout = self.other_sensors_display_layout

            # Determine type and target layout
            # Relies on naming convention or could use 'type' if added to config entries
            if comp_name.startswith("PT"):
                comp_type_name = "PressureTransducer"
                is_pt_sensor = True
                target_layout = self.pt_sensors_display_layout
            elif comp_name.startswith("TC"):
                comp_type_name = "Thermocouple"
            elif comp_name.startswith("LC"): # Check for Load Cell
                comp_type_name = "LoadCell"
            # elif comp_name.startswith("H-"): # Heater check - REMOVED as they aren't in ALL_COMPONENT_CONFIGS
            #      app_logger.warning(f"Heater '{comp_name}' found unexpectedly. Skipping UI element.")
            #      continue
            else: # Skip servos or other components not meant for this section
                # Could log this if unexpected items appear in ALL_COMPONENT_CONFIGS
                # app_logger.debug(f"Skipping non-sensor component '{comp_name}' for sensor panel.")
                continue

            parent_board_id = sensor_conf.get('parent_board_id_hex')
            parent_board_name = "Unknown Board"
            if parent_board_id is not None:
                 parent_board_name = config.BOARD_INFO_LOOKUP_TABLE.get(parent_board_id, {}).get('name', f'Board 0x{parent_board_id:02X}')

            # Layout for one sensor entry
            sensor_entry_layout = QHBoxLayout()
            sensor_entry_layout.setSpacing(10) # Spacing between name and value

            # Sensor Name/Purpose Label
            name_display_text = f"<b>{comp_name}</b>"
            if comp_purpose:
                 if is_pt_sensor: # For PTs, show Purpose primarily
                     name_display_text = f"<b>{comp_purpose}</b><br><font size='-2' color='dimgray'>({comp_name} on {parent_board_name})</font>"
                 else: # For TC, LC, show Name primarily
                      name_display_text = f"<b>{comp_name}</b><br><font size='-2' color='dimgray'>{comp_purpose} (on {parent_board_name})</font>"
            else: # No purpose defined
                 name_display_text += f"<br><font size='-2' color='dimgray'>(on {parent_board_name})</font>"

            name_label = QLabel(name_display_text)
            name_label.setTextFormat(Qt.RichText)
            # *** Apply larger font ***
            name_label.setFont(self.SENSOR_NAME_FONT)
            name_label.setWordWrap(True)

            # Sensor Value Label
            value_label = QLabel("N/A")
            value_label.setMinimumWidth(120) # Ensure space for larger font value+unit
            value_label.setAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
            value_label.setToolTip(f"Sensor: {comp_name}\nBoard: {parent_board_name}\nPurpose: {comp_purpose}")
            # *** Apply larger font ***
            value_label.setFont(self.SENSOR_VALUE_FONT)

            sensor_entry_layout.addWidget(name_label, 1) # Name label takes more space
            sensor_entry_layout.addWidget(value_label)

            # Store value label for updates
            ui_element_key = f"{comp_name}_{comp_type_name}_value"
            self._ui_elements[ui_element_key] = value_label

            # Add entry HBox to the correct column VBox
            target_layout.addLayout(sensor_entry_layout)
            if is_pt_sensor: pt_added = True
            else: other_added = True

        # Add placeholder text if no sensors of a type were added
        if not pt_added:
            placeholder_label = QLabel("<i>No PT sensors configured.</i>")
            placeholder_label.setFont(self.SENSOR_NAME_FONT) # Use sensor font
            self.pt_sensors_display_layout.addWidget(placeholder_label)
        if not other_added:
            placeholder_label = QLabel("<i>No TC/LC sensors configured.</i>")
            placeholder_label.setFont(self.SENSOR_NAME_FONT) # Use sensor font
            self.other_sensors_display_layout.addWidget(placeholder_label)


    def _create_system_controls_group(self, parent_layout):
        system_controls_group = QGroupBox("System Status & Controls")
        system_layout = QGridLayout(system_controls_group)
        system_layout.setSpacing(10)
        # Column widths: Label (0), Status (1), ON Button (2), OFF Button (3)
        system_layout.setColumnStretch(0, 0) # Label column fixed size
        system_layout.setColumnStretch(1, 1) # Status indicator flexible
        system_layout.setColumnStretch(2, 0) # Buttons fixed size
        system_layout.setColumnStretch(3, 0) # Buttons fixed size

        row = 0
        def add_control_row(display_name, status_key, cmd_on_val=None, cmd_off_val=None, on_text=None, off_text=None):
            nonlocal row
            name_label = QLabel(f"<b>{display_name}:</b>")
            name_label.setAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
            system_layout.addWidget(name_label, row, 0)

            # Use standard rectangular indicator
            status_indicator = self._create_status_indicator_label("?", self.STATUS_UNKNOWN_COLOR, fixed_width=self.SYSTEM_STATUS_CONTROL_STATE_WIDTH)
            self._device_toggle_status_labels[status_key] = status_indicator
            system_layout.addWidget(status_indicator, row, 1, Qt.AlignmentFlag.AlignCenter)

            # Button generation
            button_layout = QHBoxLayout() # Use HBox for buttons in cells 2 & 3 if needed
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

            # Add button layout spanning columns 2 and 3
            if has_on_button or has_off_button:
                 system_layout.addLayout(button_layout, row, 2, 1, 2, Qt.AlignmentFlag.AlignCenter) # Span 1 row, 2 cols
            else: # Add spacer if no buttons
                 system_layout.addItem(QSpacerItem(10, self.DEFAULT_BUTTON_MIN_HEIGHT, QSizePolicy.Policy.Minimum, QSizePolicy.Policy.Fixed), row, 2, 1, 2)


            row += 1

        # Add rows
        add_control_row("PC State", "pc_state") # No buttons defined in original
        add_control_row("Breakwire", "breakwire_status") # No buttons
        add_control_row("Igniter", "igniter_status", config.COMMANDS["ACTIVATE_IGNITER"], config.COMMANDS["DEACTIVATE_IGNITER"], on_text="Igniter ON", off_text="Igniter OFF")
        add_control_row("Auto Mode", "auto_mode", config.COMMANDS["AUTO_ON"], config.COMMANDS["AUTO_OFF"], on_text="Auto ON", off_text="Auto OFF")
        add_control_row("Servos Power", "servos_power", config.COMMANDS["ACTIVATE_SERVOS"], config.COMMANDS["DEACTIVATE_SERVOS"], on_text="Power ON", off_text="Power OFF")

        parent_layout.addWidget(system_controls_group)


    def _create_general_commands_group(self, parent_layout):
        general_commands_group = QGroupBox("General Commands")
        general_commands_layout = QGridLayout(general_commands_group)
        general_commands_layout.setSpacing(10)

        row, col = 0, 0
        max_cols = 2
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
        # Connect XBee Manager signals
        self.xbee_manager.xbee_connected.connect(self._on_xbee_connected)
        self.xbee_manager.xbee_disconnected.connect(self._on_xbee_disconnected)
        self.xbee_manager.connection_error.connect(self._on_xbee_connection_error)
        self.xbee_manager.log_message.connect(self.add_log_message)
        self.xbee_manager.transmit_status_update.connect(self._update_transmit_status_display)
        self.xbee_manager.radio_status_updated.connect(self._update_radio_status_display)

        # Connect Data Processor signals
        self.data_processor.log_message.connect(self.add_log_message)
        self.data_processor.ui_update_sensor.connect(self._update_sensor_display) # Handles PT, TC, LoadCell
        self.data_processor.ui_update_servo.connect(self._update_servo_display)
        self.data_processor.board_connectivity_update.connect(self._update_board_general_connectivity)
        self.data_processor.ui_update_board_detailed_status.connect(self._update_board_detailed_status_display)
        self.data_processor.ui_update_igniter_status.connect(self._update_igniter_display)
        self.data_processor.ui_update_auto_mode_status.connect(self._update_auto_mode_display)
        self.data_processor.ui_update_servos_power_status.connect(self._update_servos_power_display)
        self.data_processor.ui_update_breakwire_status.connect(self._update_breakwire_display)
        self.data_processor.ui_update_pc_state_status.connect(self._update_pc_state_display)

    @Slot(str)
    def add_log_message(self, message):
        self.log_text_edit.append(message)
        # Optional: Limit log length
        # MAX_LOG_LINES = 1000
        # if self.log_text_edit.document().lineCount() > MAX_LOG_LINES:
        #     ... (log limiting code) ...

    @Slot(str)
    def _on_xbee_connected(self, port):
        self.com_port_label.setText(f"Port: {port}")
        self.status_bar.showMessage(f"Connected to XBee on {port}", 5000)
        self.connect_button.setEnabled(False)
        self.disconnect_button.setEnabled(True)
        self.add_log_message(f"Successfully connected to XBee on {port}.")
        self._reset_all_board_connectivity_ui()
        self._reset_radio_status_ui()
        # Optional: Trigger initial status requests
        # self.xbee_manager.check_all_radio_statuses()
        # self.xbee_manager.request_board_status_all_targets()
        # self.xbee_manager.send_command_to_configured_targets(config.COMMANDS["CHECK_STATE"], "Initial Check State")

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

            # Elide text for description label based on its width
            metrics = ui_set['last_tx_desc_label'].fontMetrics()
            available_width = ui_set['last_tx_desc_label'].width() - 10 # Allow some padding
            elided_text = metrics.elidedText(desc_text, Qt.TextElideMode.ElideRight, max(available_width, 50)) # Min width 50
            ui_set['last_tx_desc_label'].setText(elided_text)
            ui_set['last_tx_desc_label'].setToolTip(desc_text) # Full text in tooltip

            status_text = status_info.get('status', 'N/A')
            ui_set['last_tx_status_label'].setText(status_text)
            ui_set['last_tx_retries_label'].setText(str(status_info.get('retries', 'N/A')))

            # Color code the TX status text
            if "success" in status_text.lower():
                ui_set['last_tx_status_label'].setStyleSheet(f"color: {self.STATUS_ALIVE_COLOR}; font-weight: bold;")
            elif any(err in status_text.lower() for err in ["fail", "error", "timeout", "n/a", "no ack", "invalid"]):
                ui_set['last_tx_status_label'].setStyleSheet(f"color: {self.STATUS_DEAD_COLOR}; font-weight: bold;")
            else: # Clear specific style for other statuses
                ui_set['last_tx_status_label'].setStyleSheet("")


    # **REVISED Radio Status Update**
    @Slot(dict)
    def _update_radio_status_display(self, radio_info):
        """Updates the circular status indicator for a specific radio."""
        addr = radio_info['address']
        if addr in self._radio_ui_elements:
            ui_set = self._radio_ui_elements[addr]
            status_indicator = ui_set['status_indicator']
            is_alive = radio_info.get('is_alive', False)

            bg_color = self.STATUS_ALIVE_COLOR if is_alive else self.STATUS_DEAD_COLOR
            tooltip = f"Radio: {ui_set['name_label'].toolTip()}\nStatus: {'Alive' if is_alive else 'No Response'}"

            # Update background color, keep border and radius
            radius = int(status_indicator.width() / 2)
            status_indicator.setStyleSheet(
                f"background-color: {bg_color}; "
                f"border: 1px solid dimgray; border-radius: {radius}px;"
            )
            status_indicator.setToolTip(tooltip)

            # Optionally update last TX info if provided by the health check status
            if 'last_tx_description' in radio_info:
                 self._update_transmit_status_display({
                     "address": addr,
                     "description": radio_info.get('last_tx_description', 'Healthcheck'),
                     "status": radio_info.get('last_tx_status', 'N/A'),
                     "retries": radio_info.get('last_tx_retries', 'N/A')
                 })

    @Slot(int, str, float)
    def _update_board_general_connectivity(self, board_id_8bit: int, board_name: str, timestamp: float):
        """Updates board status to 'Connected' when any message is received."""
        if board_id_8bit in self._board_connectivity_info:
            info = self._board_connectivity_info[board_id_8bit]
            info["last_seen"] = timestamp
            # Only update status visually if it was previously unknown or timed out
            if info["status_str"] in ["Unknown", "Timeout", "Disconnected"]:
                info["status_str"] = "Connected"
                # Update all UI labels associated with this board (in servo panel AND sensor panel)
                for label_widget in info.get("ui_labels", []):
                    if isinstance(label_widget, QLabel): # Ensure it's a label
                        self._update_board_status_label_style(label_widget, info["status_str"], self.STATUS_ALIVE_COLOR)

    @Slot(int, str, str, dict)
    def _update_board_detailed_status_display(self, board_id_8bit: int, board_name: str, source_xbee_addr:str, status_data_dict: dict):
        """Updates board status based on explicit status response messages."""
        if board_id_8bit in self._board_connectivity_info:
            info = self._board_connectivity_info[board_id_8bit]
            info["last_seen"] = time.time() # Update last_seen on detailed status too

            # Extract status info (adjust keys based on actual parser output)
            health_code = status_data_dict.get("health_code", "OK") # Example key
            current_status_str = str(health_code) # Display the primary health code

            tooltip_details = [f"Board: {board_name} (ID: 0x{board_id_8bit:02X})", f"Status: {health_code}"]

            info["status_str"] = current_status_str

            # Determine background color based on health code
            bg_color = self.STATUS_ALIVE_COLOR # Default to OK/Connected color
            if health_code == "WARN": bg_color = self.STATUS_WARN_COLOR
            elif health_code not in ["OK", "N/A", "Connected", "Initialized"]: # Treat other non-OK codes as errors
                 bg_color = self.STATUS_DEAD_COLOR

            # Update all associated UI labels
            for label_widget in info.get("ui_labels", []):
                if isinstance(label_widget, QLabel):
                    self._update_board_status_label_style(label_widget, info["status_str"], bg_color)
                    label_widget.setToolTip("\n".join(tooltip_details))

    @Slot(str, str, str, str)
    def _update_servo_display(self, name, state_str, board_name, component_type_name):
        """Updates the status indicator for a specific servo."""
        status_key = f"{name}_Servo_status"
        if status_key in self._ui_elements:
            label_widget = self._ui_elements[status_key]
            # Abbreviate text slightly for potentially smaller space
            display_text = state_str
            label_widget.setText(display_text)

            color = self.STATUS_UNKNOWN_COLOR
            if state_str == config.SERVO_STATES[2]: color = self.STATUS_SERVO_POWERED_OPEN_COLOR # Powered Open
            elif state_str == config.SERVO_STATES[0]: color = self.STATUS_SERVO_POWERED_CLOSED_COLOR # Powered Closed
            elif state_str == config.SERVO_STATES[3]: color = self.STATUS_SERVO_UNPOWERED_OPEN_COLOR # Unpowered Open
            elif state_str == config.SERVO_STATES[1]: color = self.STATUS_SERVO_UNPOWERED_CLOSED_COLOR # Unpowered Closed
            elif "°" in state_str: color = self.STATUS_SERVO_POSITION_COLOR # If showing angle

            # Update style (background color is primary change)
            self._update_status_indicator_style(label_widget, display_text, color)


    # **REVISED Sensor Update Slot (Handles Load Cell via key)**
    @Slot(str, str, str, str, str)
    def _update_sensor_display(self, name, value_str, unit, board_name, component_type_name):
        """Updates the value label for any sensor (PT, TC, LoadCell)."""
        # Key format example: "PT-01_PressureTransducer_value", "LC-01_LoadCell_value"
        key = f"{name}_{component_type_name}_value"
        if key in self._ui_elements:
            value_label = self._ui_elements[key]
            # Ensure the font is reapplied (SENSOR_VALUE_FONT is used for all sensors now)
            value_label.setFont(self.SENSOR_VALUE_FONT)

            value_label.setText(f"{value_str} {unit}".strip())

            # Update tooltip with latest value
            current_tooltip = value_label.toolTip()
            # Robustly find and replace/append 'Last:' line
            base_tooltip_lines = current_tooltip.split('\n')
            last_line_index = -1
            for i, line in enumerate(reversed(base_tooltip_lines)):
                if line.startswith("Last:"):
                    last_line_index = len(base_tooltip_lines) - 1 - i
                    break
            if last_line_index != -1:
                base_tooltip = "\n".join(base_tooltip_lines[:last_line_index])
            else: # 'Last:' not found, use whole tooltip as base
                base_tooltip = current_tooltip

            value_label.setToolTip(f"{base_tooltip}\nLast: {value_str} {unit}".strip())

        # else: app_logger.debug(f"Sensor UI key not found for update: {key}")


    # **REVISED Helper to update rectangular status indicators (System Status, Servo Status)**
    def _update_status_indicator_style(self, label: QLabel, text_to_display: str, background_color: str):
         label.setText(str(text_to_display))
         # Update stylesheet for background color, keep border, radius, padding
         current_style = label.styleSheet()
         new_style = re.sub(r"background-color: [^;]+;", f"background-color: {background_color};", current_style)
         if f"background-color: {background_color};" not in new_style: # If rule didn't exist
              new_style = f"background-color: {background_color}; {current_style}" # Prepend it

         label.setStyleSheet(new_style)
         self._set_label_text_color(label, background_color) # Adjust text color based on new background


    # --- System Status Update Slots ---
    # These now call the revised helper _update_status_indicator_style

    @Slot(str, bool, str, str)
    def _update_igniter_display(self, name, is_active, state_str, board_name):
        bg_color = self.STATUS_ALIVE_COLOR if is_active else self.STATUS_DEAD_COLOR
        if state_str == "Init": bg_color = self.STATUS_WARN_COLOR # Yellow for Init state
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
        # States from config: 0:Conn, 1:Conn&Armed, 2:Disconn, 3:Disconn&Armed
        if raw_state_byte == 0: bg_color = self.STATUS_ALIVE_COLOR # Connected
        elif raw_state_byte == 1: bg_color = "lime"              # Connected & Armed
        elif raw_state_byte == 2: bg_color = self.STATUS_DEAD_COLOR  # Disconnected
        elif raw_state_byte == 3: bg_color = "orangered"         # Disconnected & Armed (Bad!)
        if "breakwire_status" in self._device_toggle_status_labels:
            self._update_status_indicator_style(self._device_toggle_status_labels["breakwire_status"], state_str, bg_color)

    @Slot(str, int, str, str)
    def _update_pc_state_display(self, name, state_int, state_str, board_name):
        # Color logic based on state names from config
        bg_color = self.STATUS_UNKNOWN_COLOR
        state_str_upper = state_str.upper()
        if state_str_upper == "STARTUP": bg_color = "lightblue"
        elif state_str_upper == "AUTO_OFF": bg_color = self.STATUS_DEAD_COLOR # Off state is red-ish
        elif state_str_upper == "AUTO_ON": bg_color = self.STATUS_ALIVE_COLOR # On state is green-ish
        elif state_str_upper == "DELAY": bg_color = self.STATUS_WARN_COLOR # Delay is yellow
        elif state_str_upper == "FIRE": bg_color = "red" # Fire is bright red
        elif state_str_upper == "OPEN": bg_color = "darkorange" # Open is orange
        if "pc_state" in self._device_toggle_status_labels:
            self._update_status_indicator_style(self._device_toggle_status_labels["pc_state"], state_str, bg_color)

    # --- Timeout and Reset Logic ---

    def _check_board_timeouts(self):
        current_time = time.time()
        timeout_threshold_s = config.BOARD_ACK_TIMEOUT_MS / 1000.0

        for board_id, info in self._board_connectivity_info.items():
            # Only check boards that have reported in previously and are currently considered 'Connected' or similar
            if info["last_seen"] > 0 and info["status_str"] not in ["Timeout", "Disconnected", "Unknown"]:
                if current_time - info["last_seen"] > timeout_threshold_s:
                    app_logger.warning(f"Board {info['name']} (ID: 0x{board_id:02X}) timed out. Last seen {time.time() - info['last_seen']:.1f}s ago.")
                    info["status_str"] = "Timeout"
                    # Update all associated UI labels for this board
                    for label_widget in info.get("ui_labels", []):
                        if isinstance(label_widget, QLabel):
                            self._update_board_status_label_style(label_widget, info["status_str"], self.STATUS_DEAD_COLOR)
                            label_widget.setToolTip(f"Board timed out (>{timeout_threshold_s:.1f}s)")


    def _reset_board_connectivity_ui(self, board_id):
        """Resets a single board's status display to Unknown."""
        if board_id in self._board_connectivity_info:
            info = self._board_connectivity_info[board_id]
            info["last_seen"] = 0
            info["status_str"] = "Unknown"
            for label_widget in info.get("ui_labels", []):
                 if isinstance(label_widget, QLabel):
                    self._update_board_status_label_style(label_widget, "Unknown", self.STATUS_UNKNOWN_COLOR)
                    label_widget.setToolTip("Board status unknown")

    def _reset_all_board_connectivity_ui(self):
        """Resets all board status displays to Unknown."""
        for board_id in self._board_connectivity_info.keys():
            self._reset_board_connectivity_ui(board_id)

    # **REVISED Radio Reset**
    def _reset_radio_status_ui(self):
        """Resets all radio status indicators and text fields."""
        for addr_hex, ui_set in self._radio_ui_elements.items():
             # Reset Text Fields
             ui_set['last_tx_desc_label'].setText("N/A"); ui_set['last_tx_desc_label'].setToolTip("")
             ui_set['last_tx_status_label'].setText("N/A"); ui_set['last_tx_status_label'].setStyleSheet("")
             ui_set['last_tx_retries_label'].setText("N/A")

             # Reset Status Circle
             status_indicator = ui_set['status_indicator']
             radius = int(status_indicator.width() / 2)
             status_indicator.setStyleSheet(
                 f"background-color: {self.STATUS_UNKNOWN_COLOR}; "
                 f"border: 1px solid dimgray; border-radius: {radius}px;"
             )
             status_indicator.setToolTip("Radio status unknown")


    def _clear_all_dynamic_displays_to_stale(self):
        """Sets all dynamic data displays to a stale/unknown state on disconnect."""
        # Reset sensor values
        for key, widget in self._ui_elements.items():
            if isinstance(widget, QLabel):
                if "_Servo_status" in key:
                     self._update_status_indicator_style(widget, "Unknown", self.STATUS_UNKNOWN_COLOR)
                     widget.setToolTip("Servo status unknown (disconnected)")
                elif "_value" in key :
                    widget.setText("Stale")
                    widget.setFont(self.SENSOR_VALUE_FONT) # Ensure font is reset too
                    widget.setToolTip("Sensor value stale (disconnected)")

        # Reset system status indicators
        for key, label in self._device_toggle_status_labels.items():
            self._update_status_indicator_style(label, "?", self.STATUS_UNKNOWN_COLOR)
            label.setToolTip("System status unknown (disconnected)")

        # Reset radio and board statuses
        self._reset_radio_status_ui()
        self._reset_all_board_connectivity_ui()


    def _update_ui_refresh_rate(self):
        try:
            hz_text = self.ui_rate_input.text()
            hz = float(hz_text) # Allow float for rates like 0.5 Hz
            if hz >= 0:
                # Need access to data_processor instance if setting rate there
                if hasattr(self.data_processor, 'set_ui_update_frequency'):
                     self.data_processor.set_ui_update_frequency(hz)
                     self.add_log_message(f"UI data update rate set to {hz} Hz.")
                else:
                     self.add_log_message("Error: Data processor has no rate setting method.")

            else:
                raise ValueError("Rate must be non-negative.")
        except ValueError:
            self.add_log_message(f"Invalid UI data update rate: '{hz_text}'. Please enter a non-negative number.")
            # Revert to current actual rate if possible
            current_hz_text = "N/A"
            if hasattr(self.data_processor, '_ui_update_timer'):
                 current_interval_ms = self.data_processor._ui_update_timer.interval()
                 current_hz = (1000.0 / current_interval_ms) if current_interval_ms > 0 else 0
                 current_hz_text = f"{current_hz:.1f}"
            self.ui_rate_input.setText(current_hz_text)
        except Exception as e:
             app_logger.error(f"Error setting UI refresh rate: {e}")
             self.ui_rate_input.setText(str(config.DEFAULT_UI_UPDATE_HZ)) # Fallback


    def closeEvent(self, event):
        """Handles application closing."""
        self.add_log_message("Closing application...")
        if self._board_status_check_timer.isActive():
            self._board_status_check_timer.stop()
        # Stop data processor timer BEFORE disconnecting XBee if possible
        if hasattr(self.data_processor, '_ui_update_timer') and self.data_processor._ui_update_timer.isActive():
            self.data_processor._ui_update_timer.stop()
            app_logger.info("Stopped Data Processor UI update timer.")
        # Ensure XBee disconnect happens
        self.xbee_manager.disconnect_device() # This should already log
        app_logger.info("Application closed.")
        super().closeEvent(event)


# --- Mock Objects and Main Execution Block ---
if __name__ == '__main__':
    app = QApplication(sys.argv)

    def handle_sigint(*args):
        print("\nCtrl+C detected. Requesting application exit...")
        # Use QTimer.singleShot to allow the event loop to process the quit request
        QTimer.singleShot(0, app.quit)

    signal.signal(signal.SIGINT, handle_sigint)

    # --- Mock XBee Manager (No changes needed) ---
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
             import random
             if config.XBEE_TARGET_RADIO_CONFIG:
                 addr_conf = random.choice(config.XBEE_TARGET_RADIO_CONFIG); addr = addr_conf[1]
                 status = "Success" if random.random() > 0.1 else "No ACK"
                 retries = 0 if status == "Success" else random.randint(1, 3)
                 self.transmit_status_update.emit({"address": addr, "status": status, "description": desc, "retries": retries})
                 if status == "Success": self.radio_status_updated.emit({"address": addr, "is_alive": True})
        def _simulate_radio_status_responses(self):
            import random; self.log_message.emit("Simulating Radio Healthcheck Responses...")
            for name, addr in config.XBEE_TARGET_RADIO_CONFIG:
                is_alive = random.random() > 0.2
                self.radio_status_updated.emit({"address": addr, "is_alive": is_alive,"last_tx_description": "Healthcheck","last_tx_status": "Success" if is_alive else "Timeout","last_tx_retries": 0 if is_alive else 3})
            self.log_message.emit("Finished simulating radio responses.")
        def _simulate_board_status_response(self):
             # This mock only logs intent; data proc mock simulates the actual signal emit
             import random; board_ids = [bid for bid, binfo in config.BOARD_INFO_LOOKUP_TABLE.items() if binfo.get("type") not in ["ServoBoard", "ControllerBoard"]]
             if board_ids: board_id = random.choice(board_ids); board_info = config.BOARD_INFO_LOOKUP_TABLE[board_id]; self.log_message.emit(f"Intending to simulate detailed status for {board_info['name']} (ID: {board_id})")


    # --- Mock Data Processor (No Heaters simulated) ---
    class MockDataProcessor(QObject):
        # (Signals remain the same)
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
            # Use a real timer instance for the mock
            self._ui_update_timer = QTimer(self)
            self._ui_update_timer.timeout.connect(self.simulate_periodic_updates)
            self._sim_counter = 0

        def set_ui_update_frequency(self, hz):
            interval_ms = int(1000 / hz) if hz > 0 else 0
            self.log_message.emit(f"Mock UI Freq set: {hz}Hz (Interval: {interval_ms}ms)")
            if interval_ms > 0:
                self._ui_update_timer.setInterval(interval_ms)
                # Ensure timer starts/restarts if frequency changes while running
                if self._ui_update_timer.isActive(): self._ui_update_timer.stop()
                self._ui_update_timer.start()
            else:
                if self._ui_update_timer.isActive():
                    self._ui_update_timer.stop()

        def process_incoming_xbee_message(self, msg): pass # No action needed in mock

        @Slot()
        def simulate_periodic_updates(self):
            import random
            current_ts = time.time(); self._sim_counter += 1

            # Simulate board connectivity (general heartbeat)
            if self._sim_counter % 5 == 0:
                board_ids = list(config.BOARD_INFO_LOOKUP_TABLE.keys())
                if board_ids and random.random() < 0.8: # High chance to send heartbeat
                    board_id = random.choice(board_ids); board_info = config.BOARD_INFO_LOOKUP_TABLE[board_id]
                    self.board_connectivity_update.emit(board_id, board_info["name"], current_ts)

                    # Occasionally simulate a detailed status response too
                    if random.random() < 0.1:
                         health = random.choice(["OK", "OK", "OK", "WARN", "FAIL", "Initialized"])
                         mock_addr = f"0013A200MOCK{board_id:02X}" # Fake source address
                         self.ui_update_board_detailed_status.emit(
                             board_id, board_info["name"], mock_addr,
                             {"health_code": health, "raw_payload_hex": f"SIM{random.randint(0,999):03d}"}
                         )


            # Simulate sensor data (PT, TC, LC) - uses ALL_COMPONENT_CONFIGS from config
            # *** This automatically excludes heaters now ***
            if config.ALL_COMPONENT_CONFIGS and random.random() < 0.7: # Increased frequency
                sensor_conf = random.choice(config.ALL_COMPONENT_CONFIGS)
                comp_name = sensor_conf['name']; comp_type_name = "Unknown"
                val_str, unit_str = "N/A", ""

                # Determine type based on name prefix
                if comp_name.startswith("PT"): comp_type_name = "PressureTransducer"; val_str, unit_str = f"{random.uniform(-5.0, 1550.0):.1f}", "PSI"
                elif comp_name.startswith("TC"): comp_type_name = "Thermocouple"; val_str, unit_str = f"{random.uniform(18.0, 55.0):.1f}", "°C"
                elif comp_name.startswith("LC"): comp_type_name = "LoadCell"; val_str, unit_str = f"{random.uniform(-100.0, 5100.0):.1f}", "lbf"
                # No need for Heater check here as they are not in ALL_COMPONENT_CONFIGS

                # Only proceed if it's a known sensor type for this simulation
                if comp_type_name != "Unknown":
                    parent_board_id = sensor_conf.get("parent_board_id_hex")
                    if parent_board_id is not None:
                        parent_board_name = config.BOARD_INFO_LOOKUP_TABLE.get(parent_board_id, {}).get("name", f"Brd 0x{parent_board_id:02X}")
                        self.ui_update_sensor.emit(comp_name, val_str, unit_str, parent_board_name, comp_type_name)


            # Simulate servo state (remains same)
            if config.SERVO_LOOKUP_TABLE and random.random() < 0.3:
                servo_conf = random.choice(config.SERVO_LOOKUP_TABLE); parent_board_id = servo_conf.get("parent_board_id_hex")
                if parent_board_id is not None:
                    parent_board_name = config.BOARD_INFO_LOOKUP_TABLE.get(parent_board_id, {}).get("name", f"Brd 0x{parent_board_id:02X}")
                    state_val = random.choice(list(config.SERVO_STATES.keys())); state_str = config.SERVO_STATES[state_val]
                    self.ui_update_servo.emit(servo_conf["name"], state_str, parent_board_name, "Servo")
                    self.board_connectivity_update.emit(parent_board_id, parent_board_name, current_ts) # Also send heartbeat

            # Simulate system status updates (remains same)
            pad_ctrl_board_id = config.get_board_id_by_name("CASEY") or config.BOARD_CAN_ID_MAPPING.get("SENDER_PAD_CONTROLLER")
            if pad_ctrl_board_id is not None:
                 pad_ctrl_name = config.BOARD_INFO_LOOKUP_TABLE.get(pad_ctrl_board_id, {}).get("name", "PAD_CTRL")
                 if self._sim_counter % 7 == 0: pc_state_val = random.choice(list(config.PC_STATES.keys())); self.ui_update_pc_state_status.emit("PCState", pc_state_val, config.PC_STATES[pc_state_val], pad_ctrl_name)
                 if random.random() < 0.1: ign_state = random.choice([0,1,2]); self.ui_update_igniter_status.emit("Igniter", ign_state==2, config.IGNITER_STATES[ign_state], pad_ctrl_name)
                 if random.random() < 0.1: auto_state = random.choice([0, 1]); self.ui_update_auto_mode_status.emit("AutoMode", auto_state==1, config.ON_OFF_STATES[auto_state], pad_ctrl_name)
                 if random.random() < 0.1: power_state = random.choice([0, 1]); self.ui_update_servos_power_status.emit("ServosPower", power_state==1, config.ON_OFF_STATES[power_state], pad_ctrl_name)
                 if random.random() < 0.1: bw_state_val = random.choice(list(config.BREAKWIRE_STATES.keys())); self.ui_update_breakwire_status.emit("Breakwire", bw_state_val, config.BREAKWIRE_STATES[bw_state_val], pad_ctrl_name)

    # --- Create instances and run ---
    mock_xbee = MockXBeeManager()
    mock_data_proc = MockDataProcessor()

    main_window = ControlPanelWindow(mock_xbee, mock_data_proc)
    main_window.show()

    # Start the mock data simulation timer
    mock_data_proc.set_ui_update_frequency(2) # Simulate updates at 2 Hz

    print("Mock Application started. Press Ctrl+C in terminal to exit gracefully.")
    exit_code = app.exec()
    print(f"Application exited with code: {exit_code}")
    sys.exit(exit_code)