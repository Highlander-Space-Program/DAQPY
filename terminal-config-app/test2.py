import labjack
from labjack import ljm

# Open LabJack T7 device via USB
handle = ljm.openS("T7", "USB", "ANY")

# Configure AIN0 as positive and AIN1 as negative for thermocouple measurement
# Set up differential analog input (AIN0 - AIN1)
ljm.eWriteName(handle, "AIN0_NEGATIVE_CH", 1)  # AIN1 is negative channel for AIN0

# Configure for thermocouple type (K-type is common)
ljm.eWriteName(handle, "AIN0_EF_INDEX", 22)  # 22 = Thermocouple
ljm.eWriteName(handle, "AIN0_EF_CONFIG_A", 1)  # K-type thermocouple

try:
  while True:
    temperature = ljm.eReadName(handle, "AIN0_EF_READ_A")
    print(f"Thermocouple Temperature: {temperature:.2f}°C")
except KeyboardInterrupt:
  print("\nStopped by user")

# Close the device
ljm.close(handle)