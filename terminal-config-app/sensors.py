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
        Placeholder for future LabJack integration.
        You’ll eventually call LJ commands here, e.g.:
        lj.eWriteName(f"{self.ain}_ENABLE", 1)
        lj.eWriteName(f"{self.ain}_TYPE", self.sensor_type)
        """
        ljm.eWriteName(handle, f"{self.ain}_EF_INDEX", 22)
        ljm.eWriteName(handle, f"{self.ain}_EF_CONFIG_A", 3)
        ljm.eWriteName(handle, f"{self.ain}_RANGE", 0.1)
        ljm.eWriteName(handle, f"{self.ain}_RESOLUTION_INDEX", 8)
        print(f"Configuring {self.ain} ({self.sensor_type}) on LabJack...")

def load_sensors_from_json(path: Optional[str] = "labjack_channels.json") -> List[Sensor]:
    """
    Load sensors from a JSON file and return a list of Sensor objects.

    Args:
        path (str): Path to the JSON configuration file. Defaults to 'labjack_channels.json'.

    Returns:
        List[Sensor]: List of Sensor objects parsed from the file.
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

    # Validate structure
    sensors = []
    for ch in data:
        try:
            sensors.append(Sensor(ch["AIN"], ch["SensorType"], ch["Differential"]))
        except KeyError as e:
            print(f"Skipping invalid entry (missing {e}): {ch}")

    print(f"Loaded {len(sensors)} sensors from '{path}'")
    return sensors