from labjack import ljm
from sensors import load_sensors_from_json

handle = ljm.openS("T7", "USB", "ANY")

info = ljm.getHandleInfo(handle)
print(f"Opened LabJack (Type {info[0]}, Connection {info[1]}, Serial {info[2]})")

sensors = load_sensors_from_json("labjack_channels.json")

for s in sensors:
    print(s)
    s.configure_labjack(ljm, handle)

print("\n\n\n\n\n")

for i in range(16):  # AIN0–AIN15
    ef_index = ljm.eReadName(handle, f"AIN{i}_EF_INDEX")
    if ef_index != 0:
        print(f"AIN{i} is using EF index {ef_index}")
    else:
        print(f"AIN{i} has no EF function configured")


ljm.close(handle)
