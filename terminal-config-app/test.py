import time
from labjack import ljm

# Open LabJack device
handle = ljm.openS("T7", "ANY", "ANY")
info = ljm.getHandleInfo(handle)
print(f"Opened device: type={info[0]}, connection={info[1]}, serial={info[2]}")


# --- Conversion functions ---
def thermocouple_voltage_to_temperature(voltage, cj_temp_c=25.0): #Also potentially wrong equation
    """Convert thermocouple voltage (V) to °F using same formula as streaming.py"""
    dT_c = voltage / 0.000041
    tc_temp_c = cj_temp_c + dT_c
    return (tc_temp_c * 9/5) + 32 


def loadcell_voltage_to_lbs(voltage):
    """Convert load cell voltage to lbs of force"""
    return (0.5104 * (voltage*pow(10,5))) * 2.20462

# --- Configure differential channels ---
# Load Cell: AIN2 (positive) - AIN3 (negative)
# Thermocouple: AIN0 (positive) - AIN1 (negative)

# Set ranges and negative channels
ljm.eWriteName(handle, "AIN2_RANGE", 0.1)  # ±0.1 V for load cell
ljm.eWriteName(handle, "AIN2_NEGATIVE_CH", 3)

ljm.eWriteName(handle, "AIN0_RANGE", 0.1)  # ±0.1 V for thermocouple
ljm.eWriteName(handle, "AIN0_NEGATIVE_CH", 1)

try:
    while True:
        # Read differential voltages directly
        load_cell_voltage = ljm.eReadName(handle, "AIN2")
        thermocouple_voltage = ljm.eReadName(handle, "AIN0")
        temperature = thermocouple_voltage_to_temperature(thermocouple_voltage, cj_temp_c=25.0)
        lbs = loadcell_voltage_to_lbs(load_cell_voltage)

        print(f"Load Cell Voltage (V): {load_cell_voltage:}, Force (lbs): {lbs:.6f}")
        print(f"Thermocouple Voltage (V): {thermocouple_voltage:}, Temperature (F): {temperature:.6f}")
        print("---")

        time.sleep(0.25)

except KeyboardInterrupt:
    print("Stopped by user")
finally:
    ljm.close(handle)

