from labjack import ljm
from sensors import load_sensors_from_json
import time

def thermocouple_voltage_to_temperature(thermo_voltage, cj_temp_c):
    """
    Convert thermocouple voltage (in volts) to temperature in °F.
    
    This uses a simple linear approximation:
      - K-type thermocouple sensitivity is approximately 41 µV/°C.
      - dT (°C) = thermo_voltage (V) / 0.000041
      - Thermocouple temperature (°C) = Cold Junction Temperature (°C) + dT
      - Then convert °C to °F.
    
    Note: This linear approximation is valid only over a narrow temperature range.
    """
    # Calculate the temperature difference from the thermocouple voltage
    dT_c = thermo_voltage / 0.000041  # in °C
    tc_temp_c = cj_temp_c + dT_c        # thermocouple temperature in °C
    tc_temp_f = (tc_temp_c * 9/5) + 32    # convert °C to °F
    return tc_temp_f

handle = ljm.openS("T7", "USB", "ANY")

info = ljm.getHandleInfo(handle)
print(f"Opened LabJack (Type {info[0]}, Connection {info[1]}, Serial {info[2]})")

sensors = load_sensors_from_json("labjack_channels.json")

while(True):
    print("----------------")
    for s in sensors:
        try:
            while(True):
                print("----------------")
                for s in sensors:
                    s.configure_labjack(ljm, handle)
                    temperature = ljm.eReadName(handle, f"{s.ain}_EF_READ_A")
                    print(f"Thermocouple Temperature: {temperature:.2f}°C")
                time.sleep(1)
        except KeyboardInterrupt:
            pass
        finally:
            ljm.close(handle)
        temperature = ljm.eReadName(handle, s.ain)
        print(f"Thermocouple Temperature: {temperature:.2f}°C")
    time.sleep(1)