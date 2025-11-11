from labjack import ljm
from sensors import load_sensors_from_json

USE_SIM = True  # Toggle between real and simulated device

if USE_SIM:
    handle = ljm.openS("T7", "ANY", "LJM_SIM")  # or "LJM_DUMMY"
else:
    handle = ljm.openS("T7", "USB", "ANY")

info = ljm.getHandleInfo(handle)
print(f"Opened LabJack (Type {info[0]}, Connection {info[1]}, Serial {info[2]})")

sensors = load_sensors_from_json("labjack_channels.json")

for s in sensors:
    print(s)
    s.configure_labjack(ljm, handle)

ljm.close(handle)
