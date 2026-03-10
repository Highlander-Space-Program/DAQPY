# app.py
from flask import Flask, render_template
from flask_socketio import SocketIO
from threading import Thread
import time
import streaming

app = Flask(__name__)
socketio = SocketIO(app, cors_allowed_origins="*")


# Serve the main dashboard page
@app.route("/")
def index():
    return render_template("index.html")


# Optional debug route to see raw live data
@app.route("/debug")
def debug():
    with streaming.live_data_lock:
        return streaming.live_data.copy()


# --- Conversion functions ---
def thermocouple_voltage_to_temperature(voltage, cj_temp_c=25.0): #Also potentially wrong equation
    """Convert thermocouple voltage (V) to °F using same formula as streaming.py"""
    dT_c = voltage / 0.000041  # in °C
    tc_temp_c = cj_temp_c + dT_c        # thermocouple temperature in °C
    return tc_temp_c

def loadcell_voltage_to_lbs(voltage):
    # return (0.5104 * (voltage*pow(10,5))) * 2.20462
    return ((-0.4995 * (voltage*pow(10,5))) + 0.8905) * 2.20462

def total_loadcell_voltage_to_lbs(voltage):
    return ((-0.4995 * (voltage*pow(10,5))) + 0.8905) * 2.20462

def pressure_voltage_to_psi(voltage):
    return ((voltage - 0.5) / (4.0) ) * 1600

def calibration(voltage):
    max_load = 1102.31 # lbs
    sens = 2.0 # mV / V
    excitation_voltage = 5.0 # V

    full_scale_voltage = sens * excitation_voltage / 1000

    return -1 * (max_load / full_scale_voltage) * voltage



# Background thread to push live data to the dashboard
def push_live_data():
    # Map your AIN channels to dashboard channel names
    AIN_TO_CHANNEL = {
        "AIN52": "tc_1",
        "AIN51": "tc_2",
        "AIN48": "lc_1",
        "AIN21": "lc_2",
        "AIN50": "pt_1",
        "AIN10": "pt_2",
        "AIN6": "pt_3",
        "AIN7": "flow_1"
    }

    output = [0] * 50
    i = 0

    while True:
        with streaming.live_data_lock:
            data_copy = streaming.live_data.copy()

        if data_copy:
            dash_packet = {
                "timestamp": time.time(),
                "board_id": "labjack",
                "channels": {}
            }

                        # Precompute totals FIRST
            total_loadcell_voltage = sum(
                row["voltage"]
                for row in data_copy.values()
                if row["sensor"] == "LoadCell"
            )

            total_loadcell_lbs = total_loadcell_voltage_to_lbs(total_loadcell_voltage)

            for ain_name, row in data_copy.items():
                dash_name = AIN_TO_CHANNEL.get(ain_name)
                if dash_name:
                    value = row["voltage"]

                    if row["sensor"] == "Thermocouple":
                        value = thermocouple_voltage_to_temperature(value)
                    elif row["sensor"] == "Pressure":
                        value = pressure_voltage_to_psi(value)
                    elif row["sensor"] == "LoadCell":
                        # value = calibration(value)
                        value = loadcell_voltage_to_lbs(value)
                        output[i%len(output)] = value
                        i += 1
                        value = sum(output)/len(output)

                    dash_packet["channels"][dash_name] = value

            # Send to all connected browsers
            socketio.emit("sensor_data", dash_packet)

        time.sleep(0.05)  # ~20 Hz update rate


if __name__ == "__main__":
    # Start LabJack stream in background
    Thread(target=streaming.main, daemon=True).start()

    # Start live data push thread
    Thread(target=push_live_data, daemon=True).start()

    # Run Flask + SocketIO server without reloader to avoid LabJack conflicts
    socketio.run(app, host="0.0.0.0", port=5000, debug=True, use_reloader=False)
