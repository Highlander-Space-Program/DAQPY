import random
import time
import threading
import dearpygui.dearpygui as dpg
from threading import Lock

#Open first availbe labjack in Demo mode
#handle = ljm.openS(“ANY”, “ANY”, “-2”) 

#This is how we would call our t7
#handle = ljm.openS("T7", "Ethernet", "Auto")

try:
    import u3  # LabJack U3/T7 library
    labjack_available = True
except ImportError:
    labjack_available = False

# Global variables for live data
running = True
fake_data_mode = True  # Start with fake data if no LabJack is detected
labjack_device = None
data_buffer = {"pressure": [], "temperature": [], "thrust": []}
data_lock = Lock()

# Function to initialize LabJack
def initialize_labjack():
    global labjack_device, fake_data_mode
    if labjack_available:
        try:
            labjack_device = u3.U3()  # Initialize LabJack T7
            fake_data_mode = False
            print("LabJack detected and initialized.")
        except Exception as e:
            print(f"LabJack initialization failed: {e}")
            fake_data_mode = True
    else:
        print("LabJack library not installed. Falling back to fake data.")
        fake_data_mode = True

# Function to fetch live data
def fetch_data():
    global data_buffer, fake_data_mode, running, labjack_device

    while running:
        if not fake_data_mode and labjack_device is not None:
            try:
                # Replace the following lines with actual LabJack readouts
                pressure = labjack_device.getAIN(0)  # Example channel
                temperature = labjack_device.getAIN(1)
                thrust = labjack_device.getAIN(2)
            except Exception as e:
                print(f"LabJack error: {e}")
                pressure, temperature, thrust = (0, 0, 0)
        else:
            pressure = random.uniform(-1, 1)
            temperature = random.uniform(20, 50)
            thrust = random.uniform(110, 120)

        with data_lock:
            # Update data buffers
            data_buffer["pressure"].append(pressure)
            data_buffer["temperature"].append(temperature)
            data_buffer["thrust"].append(thrust)

            # Keep only the last 100 data points
            for key in data_buffer:
                data_buffer[key] = data_buffer[key][-100:]

        time.sleep(0.1)  # Simulate real-time data update

# Function to update plots
def update_dashboard():
    global data_buffer
    with data_lock:
        x_data = list(range(len(data_buffer["pressure"])))
        for i in range(9):
            # Cycle through the available data types for the plots
            data_type = list(data_buffer.keys())[i % len(data_buffer)]
            y_data = data_buffer[data_type]
            dpg.set_value(f"plot_series_{i}", [x_data, y_data])
            # Update the x-axis limits to create a sliding window effect
            if len(x_data) > 1:
                dpg.set_axis_limits(f"x_axis_{i}", x_data[0], x_data[-1])
            # Dynamically adjust the y-axis to fit the data
            if len(y_data) > 0:
                y_min = min(y_data)
                y_max = max(y_data)
                dpg.set_axis_limits(f"y_axis_{i}", y_min, y_max)

# Function to handle fake data toggle
def toggle_fake_data():
    global fake_data_mode
    fake_data_mode = not fake_data_mode
    if fake_data_mode:
        print("Switched to fake data mode.")
        dpg.set_value("labjack_status", "No LabJack detected. Using fake data.")
    else:
        print("Switched to live data mode.")
        dpg.set_value("labjack_status", "LabJack connected.")

# Function to stop the application
def stop_application():
    global running
    running = False
    dpg.stop_dearpygui()

# Main Application UI
def setup_ui():
    # Create a theme for the gray background
    with dpg.theme(tag="gray_theme"):
        with dpg.theme_component(dpg.mvAll):
            dpg.add_theme_color(dpg.mvThemeCol_WindowBg, (70, 70, 70), category=dpg.mvThemeCat_Core)
            dpg.add_theme_color(dpg.mvThemeCol_FrameBg, (90, 90, 90), category=dpg.mvThemeCat_Core)
            dpg.add_theme_color(dpg.mvThemeCol_Button, (120, 120, 120), category=dpg.mvThemeCat_Core)
            dpg.add_theme_color(dpg.mvThemeCol_Text, (220, 220, 220), category=dpg.mvThemeCat_Core)

    with dpg.window(label="Highlander Space Program DAQ", width=1000, height=800, tag="main_window"):
        dpg.bind_theme("gray_theme")
        dpg.set_primary_window("main_window", True)

        # Dashboard layout
        with dpg.tab_bar():
            with dpg.tab(label="Dashboard"):
                # Create a 3x3 grid for plots
                for col in range(3):
                    with dpg.group(horizontal=True):
                        for row in range(3):
                            plot_index = col * 3 + row
                            with dpg.plot(label=f"Graph {plot_index + 1}", height=200, width=300):
                                x_axis = dpg.add_plot_axis(dpg.mvXAxis, label="Time", tag=f"x_axis_{plot_index}")
                                y_axis = dpg.add_plot_axis(dpg.mvYAxis, label="Value", tag=f"y_axis_{plot_index}")
                                dpg.add_line_series([], [], label="Data", parent=y_axis, tag=f"plot_series_{plot_index}")
                                # Set initial axis limits to prevent excessive zooming
                                dpg.set_axis_limits_auto(f"x_axis_{plot_index}")
                                dpg.set_axis_limits_auto(f"y_axis_{plot_index}")

                dpg.add_spacer(height=10)

                # Status and control buttons
                dpg.add_text("Status:")
                dpg.add_text(default_value="Checking for LabJack...", tag="labjack_status")
                dpg.add_button(label="Toggle Fake Data", callback=toggle_fake_data)
                dpg.add_button(label="Quit", callback=stop_application)

            with dpg.tab(label="Settings"):
                dpg.add_input_text(label="LabJack Identifier", default_value="ANY")
                dpg.add_input_text(label="Device Type", default_value="ANY")
                dpg.add_input_text(label="Connection Type", default_value="ANY")
                dpg.add_combo(label="Protocol", items=["http", "https"], default_value="http")
                dpg.add_input_text(label="Address", default_value="localhost")
                dpg.add_input_int(label="Port", default_value=8086)
                dpg.add_input_text(label="Bucket", default_value="poseidon")
                dpg.add_input_text(label="Measurement", default_value="mass_flow_test_1")
                dpg.add_input_text(label="Token", default_value="YourTokenHere", password=True)
                dpg.add_button(label="Save Settings", callback=lambda: print("Settings saved."))

if __name__ == "__main__":
    dpg.create_context()
    dpg.create_viewport(title="Highlander Space Program DAQ", width=1000, height=800)

    initialize_labjack()

    setup_ui()

    # Update LabJack Status in the UI
    if not fake_data_mode:
        dpg.set_value("labjack_status", "LabJack connected.")
    else:
        dpg.set_value("labjack_status", "No LabJack detected. Using fake data.")

    threading.Thread(target=fetch_data, daemon=True).start()

    dpg.setup_dearpygui()
    dpg.show_viewport()

    while dpg.is_dearpygui_running() and running:
        update_dashboard()
        dpg.render_dearpygui_frame()

    dpg.destroy_context()
