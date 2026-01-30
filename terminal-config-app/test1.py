from labjack import ljm
import time

def pressure_voltage_to_psi(voltage):
    return ((voltage - 0.5) / 4.0) * 1600

handle = ljm.openS("ANY", "ANY", "ANY")

IN_NAMES = ["AIN55"]
NUM_IN_CHANNELS = len(IN_NAMES)

scanList = ljm.namesToAddresses(NUM_IN_CHANNELS, IN_NAMES)[0]

scanRate = 1000
scansPerRead = 500

ljm.eWriteName(handle, "AIN_ALL_NEGATIVE_CH", ljm.constants.GND)
ljm.eWriteName(handle, "AIN_ALL_RANGE", 10.0)
ljm.eWriteName(handle, "AIN_ALL_RESOLUTION_INDEX", 1)

ljm.eStreamStart(
    handle,
    scansPerRead,
    NUM_IN_CHANNELS,
    scanList,
    scanRate
)

try:
    while True:
        data = ljm.eStreamRead(handle)[0]

        ch0 = data[0::NUM_IN_CHANNELS]

        v0 = ch0[-1]

        print(v0)
        print(pressure_voltage_to_psi(v0))

except KeyboardInterrupt:
    pass

ljm.eStreamStop(handle)
ljm.close(handle)