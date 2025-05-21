# main.py
import sys
import signal # Import the signal module
from PySide6.QtWidgets import QApplication
from PySide6.QtCore import QTimer # QTimer is used by XBeeManager for autoconnect

import config # Ensures config is loaded
from logger_setup import app_logger # Initializes logging
from xbee_handler import XBeeManager
from data_processor import DataProcessor
from ui_control_panel import ControlPanelWindow

# --- Signal Handler for Ctrl+C ---
def sigint_handler(*args):
    """Handler for the SIGINT signal (Ctrl+C)."""
    app_logger.info("Ctrl+C pressed. Shutting down application...")
    QApplication.quit()

def main():
    # Install the SIGINT handler
    signal.signal(signal.SIGINT, sigint_handler)

    app = QApplication(sys.argv)
    app.setApplicationName("XBee CAN Control Panel")
    # Apply a basic style (optional)
    # app.setStyle("Fusion")

    app_logger.info("Application starting...")

    # Create core components
    xbee_manager = XBeeManager()
    data_processor = DataProcessor()

    # Create the main window
    main_window = ControlPanelWindow(xbee_manager, data_processor)

    # --- Connect signals between components ---
    xbee_manager.message_received.connect(data_processor.process_incoming_xbee_message)
    
    # --- Threading considerations ---
    # The digi-xbee library typically manages its own threads for I/O and callbacks.
    # UI updates via Qt Signals from those callback threads are safe.
    # XBeeManager's autodetect_and_connect is called with QTimer.singleShot from ControlPanelWindow,
    # and send_data_async is used, which should keep UI responsive.

    # To make Ctrl+C work effectively with Qt, especially if the Python interpreter
    # is not getting much time due to the Qt event loop, we can use a QTimer
    # to periodically allow Python's signal handling to run.
    # This is a common workaround for Qt applications.
    timer = QTimer()
    timer.start(100)  # Check for signals every 100ms
    timer.timeout.connect(lambda: None) # Dummy slot to allow Python interpreter to run

    main_window.show()
    app_logger.info("Main window shown. Application running. Press Ctrl+C to exit.")
    sys.exit(app.exec())

if __name__ == "__main__":
    main()
