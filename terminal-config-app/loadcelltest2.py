from labjack import ljm
import time

# --- Open LabJack ---
handle = ljm.openS("T7", "USB", "ANY")
info = ljm.getHandleInfo(handle)
print(f"Opened LabJack (Type {info[0]}, Connection {info[1]}, Serial {info[2]})")

# --- Configure the differential channel (AIN2 - AIN3) ---
# EF index 22 = Differential voltage
ljm.eWriteName(handle, "AIN2_NEGATIVE_CH", 3)  # AIN2+ uses AIN3− as negative
ljm.eWriteName(handle, "AIN2_RANGE", 0.1)      # Expected range ±0.1V typical for load cells
ljm.eWriteName(handle, "AIN2_RESOLUTION_INDEX", 8)

# --- Read loop ---
print("Reading load cell differential voltage (AIN2 - AIN3)... Press Ctrl+C to stop.")

try:
    while True:
        voltage = ljm.eReadName(handle, "AIN2")  # Reads differential since negative channel set
        print(f"Load Cell Voltage: {voltage:.6f} V")
        time.sleep(0.5)
except KeyboardInterrupt:
    print("\nStopping...")

# --- Close LabJack ---
ljm.close(handle)
print("Closed LabJack connection.")
