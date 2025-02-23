import csv
import time
from datetime import datetime
from labjack import ljm
import numpy as np

# --- NIST Type J Table ---
temp_table = np.array([
    -200, -190, -180, -170, -160, -150, -140, -130, -120, -110,
    -100,  -90,  -80,  -70,  -60,  -50,  -40,  -30,  -20,  -10,
       0,   10,   20,   30,   40,   50,   60,   70,   80,   90,
     100,  110,  120,  130,  140,  150,  160,  170,  180,  190,
     200
])

mv_table = np.array([
    -8.095, -7.890, -7.659, -7.403, -7.123, -6.821, -6.500, -6.159, -5.801, -5.426,
    -5.037, -4.633, -4.215, -3.786, -3.344, -2.893, -2.431, -1.961, -1.482, -0.995,
    -0.501,  0.000,  0.507,  1.019,  1.537,  2.059,  2.585,  3.116,  3.650,  4.187,
     4.726,  5.269,  5.814,  6.360,  6.909,  7.459,  8.010,  8.562,  9.115,  9.669,
    10.224
])

def type_j_temp_from_mv(voltage_mv):
    """Convert a measured thermocouple voltage (mV) to temperature (°C)."""
    return np.interp(voltage_mv, mv_table, temp_table)

# --- Configuration ---
AIN_CHANNELS = ["AIN0", "AIN1", "AIN2", "AIN3", "AIN120", "AIN122"]  # Single-ended inputs
DIFF_PAIRS = [("AIN48", "AIN56"), ("AIN49", "AIN57"), ("AIN50", "AIN58")]  # Load Cell Pairs
TC_PAIRS = [("AIN80", "AIN88"), ("AIN81", "AIN89"), ("AIN82", "AIN90")]  # Thermocouple Pairs
BUFFER_LIMIT = 5000
CSV_FILE = "sensor_data.csv"

def apply_scaling(value, channel):
    """Applies the appropriate scaling equation based on the channel."""
    if channel == "AIN0":
        return (421.98) * (value - 0.04) - 166.26 + 4
    elif channel == "AIN1":
        return (421.98) * (value - 0.04) - 166.26 + 10
    elif channel in ["AIN2", "AIN3", "AIN120"]:
        return (421.98) * (value - 0.04) - 166.26 + 10
    elif channel == "AIN122":
        return (306.25) * (value - 0.04) - 132.81
    else:
        return 0

def apply_differential_scaling(voltage):
    """Applies scaling to differential load cell readings."""
    return (-(voltage * 51412) + 2.0204) / 0.45359237  # Converts voltage to weight (lbs)

def configure_differential_channels(handle, diff_pairs):
    """Configures differential channels."""
    for pos, neg in diff_pairs:
        ljm.eWriteName(handle, f"{pos}_RANGE", 0.01)  # Set range to ±0.01V
        ljm.eWriteName(handle, f"{pos}_NEGATIVE_CH", int(neg[3:]))  # Assign negative channel

def main():
    handle = ljm.openS("ANY", "ANY", "ANY")  # Open LabJack device
    print("Opened device:", ljm.getHandleInfo(handle))

    configure_differential_channels(handle, DIFF_PAIRS)
    configure_differential_channels(handle, TC_PAIRS)

    with open(CSV_FILE, mode="w", newline="") as file:
        writer = csv.writer(file)
        header = ["Timestamp"] + AIN_CHANNELS + ["Total_Scaled_Weight (lbs)"] + [f"TC_{i+1} (°F)" for i in range(len(TC_PAIRS))]
        writer.writerow(header)

        try:
            buffer = []
            while True:
                timestamp = datetime.now().strftime("%H:%M:%S:%f")[:-3]

                # Read AIN Values
                ain_values = [ljm.eReadName(handle, ch) for ch in AIN_CHANNELS]
                scaled_ain_values = [apply_scaling(ain_values[i], AIN_CHANNELS[i]) for i in range(len(AIN_CHANNELS))]

                # Read Load Cell (Weight) Differential Values
                diff_voltages = [ljm.eReadName(handle, pair[0]) for pair in DIFF_PAIRS]
                scaled_diffs = [apply_differential_scaling(v) for v in diff_voltages]
                total_scaled_weight = sum(scaled_diffs)

                # Read Thermocouple Differential Voltages
                tc_voltages = [ljm.eReadName(handle, pair[0]) for pair in TC_PAIRS]
                tc_temps = [type_j_temp_from_mv(v * 1000.0)*(9/2) +32 for v in tc_voltages]  # Convert V to mV and to °F

                # Print Data
                print(f"{timestamp} | AIN Scaled: {', '.join(f'{v:.2f}' for v in scaled_ain_values)} "
                      f"| Weight: {total_scaled_weight:.2f} pounds | TC Temps: {', '.join(f'{t:.2f}°F' for t in tc_temps)}")

                # Append Data to Buffer
                buffer.append([timestamp] + scaled_ain_values + [total_scaled_weight] + tc_temps)

                # Write Buffer to CSV if limit is reached
                if len(buffer) >= BUFFER_LIMIT:
                    writer.writerows(buffer)
                    file.flush()  # Ensure immediate write
                    buffer.clear()
                    print(f"Written {BUFFER_LIMIT} rows to {CSV_FILE}")

             #   time.sleep(0.01)  # Adjust sampling rate
        except KeyboardInterrupt:
            print("\nStream interrupted by user.")
        finally:
            if buffer:
                writer.writerows(buffer)
                print(f"Written remaining {len(buffer)} rows to {CSV_FILE}")

            ljm.close(handle)
            print("Stream stopped and device closed.")

if __name__ == "__main__":
    main()
