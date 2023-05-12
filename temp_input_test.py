from labjack import ljm
import logging

try:
    handle = ljm.open(ljm.constants.dtT7, ljm.constants.ctUSB, "ANY")
except ljm.LJMError as e:
    logging.error("Error connecting to LabJack device: {}".format(e.errorString))
    exit()

# Config
ljm.eWriteName(handle, "AIN0_NEGATIVE_CH", 1)
ljm.eWriteName(handle, "AIN0_EF_INDEX", 22)
ljm.eWriteName(handle, "AIN0_EF_CONFIG_A", 2)

intervalHandle = 1
ljm.startInterval(intervalHandle, 1000000)

name = "AIN0_EF_READ_A"
while True:
    try:
        res = ljm.eReadName(handle, name)
        print(res)
    except ljm.LJMError as e:
        logging.error("Could not read from {}: {}".format(name, e.errorString))
    except KeyboardInterrupt:
        break;
    ljm.waitForNextInterval(intervalHandle)

ljm.cleanInterval(intervalHandle)
ljm.close(handle)
