import json
from typing import List, Optional
from labjack import ljm

class Sensor:
    def __init__(self, ain: str, sensor_type: str, differential: bool):
        self.ain = ain
        self.sensor_type = sensor_type
        self.differential = differential

    def __repr__(self):
        return f"<Sensor {self.ain} | {self.sensor_type} | Differential: {self.differential}>"

    def configure_labjack(self, ljm, handle):
        """
        Configures the LabJack analog input channel.
        Handles both differential and single-ended modes.
        """
        ain_number = int(self.ain.replace("AIN", ""))

        # Set the negative channel for differential mode
        if self.differential:
            negative_channel = ain_number + 1  # AIN2-AIN3, AIN4-AIN5, etc.
            ljm.eWriteName(handle, f"{self.ain}_NEGATIVE_CH", negative_channel)
            print(f"Configuring {self.ain} as DIFFERENTIAL (AIN{ain_number}-AIN{negative_channel})...")
        else:
            # For single-ended, negative channel = 199 (GND reference)
            ljm.eWriteName(handle, f"{self.ain}_NEGATIVE_CH", 199)
            print(f"Configuring {self.ain} as SINGLE-ENDED (to GND)...")

        # Common configuration for both types
        ljm.eWriteName(handle, f"{self.ain}_RANGE", 10.0)  # ±10V range
        ljm.eWriteName(handle, f"{self.ain}_RESOLUTION_INDEX", 8)
        ljm.eWriteName(handle, f"{self.ain}_SETTLING_US", 0)

    def read_value(self, ljm, handle):
        """Reads and returns the current voltage from the channel."""
        value = ljm.eReadName(handle, self.ain)
        print(f"{self.ain}: {value:.6f} V")
        return value


def load_sensors_from_json(path: Optional[str] = "labjack_channels.json") -> List[Sensor]:
    """
    Load sensors from a JSON file and return a list of Sensor objects.
    """
    try:
        with open(path, "r") as f:
            data = json.load(f)
    except FileNotFoundError:
        print(f"Error: File '{path}' not found.")
        return []
    except json.JSONDecodeError:
        print(f"Error: Could not parse '{path}'. File may be corrupted.")
        return []

    # Handle both old and new formats
    if isinstance(data, dict) and "Channels" in data:
        data = data["Channels"]

    sensors = []
    for ch in data:
        try:
            sensors.append(Sensor(ch["AIN"], ch["SensorType"], ch["Differential"]))
        except KeyError as e:
            print(f"Skipping invalid entry (missing {e}): {ch}")

    print(f"Loaded {len(sensors)} sensors from '{path}'")
    return sensors
