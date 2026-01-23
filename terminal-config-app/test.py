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

def allLoadCellVoltagetolbs(voltage):
    return (18566.66 * voltage) + 1.067

# --- Configure differential channels ---
# Load Cell: AIN2 (positive) - AIN3 (negative)
# Thermocouple: AIN0 (positive) - AIN1 (negative)

# Set ranges and negative channels
loadcell_ains = [48, 49, 50, 51]

for ain in loadcell_ains:
    ljm.eWriteName(handle, f"AIN{ain}_RANGE", 0.1)          # ±0.1 V
    ljm.eWriteName(handle, f"AIN{ain}_NEGATIVE_CH", ain+8) # 48→56, 49→57, etc.

try:
    while True:
        # ---- LOAD CELLS (aggregate first) ----

        total_loadcell_voltage = 0.0

        for i in range (1, 100):
            for ain in loadcell_ains:
                v = ljm.eReadName(handle, f"AIN{ain}")
                total_loadcell_voltage += v

        total_loadcell_voltage /= 100
        total_lbs = allLoadCellVoltagetolbs(total_loadcell_voltage)
        print("Voltage (V) Scaled by 10^5:", total_loadcell_voltage*pow(10,5))
        print(f"Total Force (lbs): {total_lbs:}")
        print("---")

        time.sleep(1)

except KeyboardInterrupt:
    print("Stopped by user")
finally:
    ljm.close(handle)


