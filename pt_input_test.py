import logging
import csv
import json
from labjack import ljm
from datetime import datetime as dt

try:
    handle = ljm.open(ljm.constants.dtT7, ljm.constants.ctUSB, "ANY")
except ljm.LJMError as e:
    logging.error("Error connecting to LabJack device: {}".format(e.errorString))
    exit()

intervalHandle = 1
ljm.startInterval(intervalHandle, 1000)

output = {'units': 'psi', 'data': []}

name = "AIN0"
while True:
    try:
        voltage = ljm.eReadName(handle, name)
        res = (voltage - 0.5) / 0.004
        output['data'].append([dt.now().timestamp(), res])
        print(res)
    except ljm.LJMError as e:
        logging.error("Could not read from {}: {}".format(name, e.errorString))
    except KeyboardInterrupt:
        break;

    ljm.waitForNextInterval(intervalHandle)

with open('pt_data.json', 'w') as f:
    f.write(json.dumps(output, indent=4))

ljm.cleanInterval(intervalHandle)
ljm.close(handle)
