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

def total_loadcell_voltage_to_lbs(voltage):
    return ((-0.4995 * (voltage*pow(10,5))) + 0.8905) * 2.20462

def pressure_voltage_to_psi(voltage):
    return ((voltage - 0.5) / 4.0) * 1600

# --- Configure differential channels ---
# Load Cell: AIN2 (positive) - AIN3 (negative)
# Thermocouple: AIN0 (positive) - AIN1 (negative)

# Set ranges and negative channels
loadcell_ains = [48, 49, 50, 51]

for ain in loadcell_ains:
    ljm.eWriteName(handle, f"AIN{ain}_RANGE", 0.01)          # ±0.1 V
    ljm.eWriteName(handle, f"AIN{ain}_NEGATIVE_CH", ain+8) # 48→56, 49→57, etc.

# Pressure transducer on AIN7 (single-ended)
ljm.eWriteName(handle, "AIN55_RANGE", .01)      # ±10 V (safe default)
ljm.eWriteName(handle, "AIN55_NEGATIVE_CH", 199) # single-ended

try:
    while True:
        # ---- LOAD CELLS (average + sum) ----
        total_loadcell_voltage = 0.0

        for _ in range(100):
            for ain in loadcell_ains:
                total_loadcell_voltage += ljm.eReadName(handle, f"AIN{ain}")

        total_loadcell_voltage /= 100
        total_lbs = total_loadcell_voltage_to_lbs(total_loadcell_voltage)

        print("Voltage (V) Scaled by 10^5:", total_loadcell_voltage * 1e5)
        print(f"Total Force (lbs): {total_lbs:.6f}")

        # ---- PRESSURE TRANSDUCER ----
        pressure_voltage = ljm.eReadName(handle, "AIN7")
        pressure = pressure_voltage_to_psi(pressure_voltage)
        print(f"Pressure Transducer Voltage (V): {pressure_voltage:.6f}")
        print(f"PSI: {pressure}")

        print("---")
        time.sleep(1)

except KeyboardInterrupt:
    print("Stopped by user")
finally:
    ljm.close(handle)


