from labjack import ljm
from sensors import load_sensors_from_json
import time

# Open connection to LabJack
handle = ljm.openS("T7", "USB", "ANY")

info = ljm.getHandleInfo(handle)
print(f"Opened LabJack (Type {info[0]}, Connection {info[1]}, Serial {info[2]})")

# Load and configure sensors
sensors = load_sensors_from_json("labjack_channels.json")

while(True):
    print("----------------")
    for s in sensors:
        s.configure_labjack(ljm, handle)
        voltage = ljm.eReadName(handle, s.ain)
        print(voltage)
        
    time.sleep(1)
ljm.close(handle)
