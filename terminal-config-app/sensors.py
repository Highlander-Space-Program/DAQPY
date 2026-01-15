import json
from typing import List, Optional
from labjack import ljm

class Sensor:
    def __init__(self, ain: str, sensor_type: str, differential: bool, negative_ain: Optional[str] = None):
        self.ain = ain  # e.g. "AIN48"
        self.sensor_type = sensor_type
        self.differential = differential
        self.negative_ain = negative_ain  # e.g. "AIN56" or None

    def __repr__(self):
        return f"<Sensor {self.ain} | {self.sensor_type} | Diff={self.differential} | Neg={self.negative_ain}>"

    def _ain_num(self, label: str) -> int:
        if not label.startswith("AIN"):
            raise ValueError(f"Expected AIN label like 'AIN48', got '{label}'")
        return int(label.replace("AIN", ""))

    def configure_labjack(self, ljm, handle):
        """
        Configure analog input. Uses explicit negative channel for differential mode.
        Validates:
          - Built-in T7 pairs: AIN0->AIN1 and AIN2->AIN3 (even->odd)
          - Mux80 extended channels (48-127): negative = positive + 8
        """
        ain_num = self._ain_num(self.ain)

        if self.differential:
            if not self.negative_ain:
                raise ValueError(f"Differential sensor {self.ain} requires 'NegativeAIN' in config.")

            neg_num = self._ain_num(self.negative_ain)

            valid = False

            # Built-in T7 small set (AIN0..AIN3): even->odd pairs 0->1 and 2->3
            if (ain_num in (0, 2) and neg_num == ain_num + 1) or (neg_num in (0, 2) and ain_num == neg_num + 1):
                valid = True

            # Mux80 extended channels: negative = positive + 8 (either order)
            # Accept if one is in extended range and the other is exactly +8
            if 48 <= ain_num <= 127:
                if neg_num == ain_num + 8:
                    valid = True

            if not valid:
                raise ValueError(
                    f"Invalid differential pair: {self.ain} and {self.negative_ain}. "
                    "Allowed pairs: built-in AIN0->AIN1 or AIN2->AIN3; "
                    "or Mux80 extended channels where Negative = Positive + 8 (e.g. AIN48->AIN56)."
                )

            # Write the negative channel numeric value
            ljm.eWriteName(handle, f"{self.ain}_NEGATIVE_CH", neg_num)
            print(f"Configuring {self.ain} as DIFFERENTIAL ({self.ain} - {self.negative_ain})")

        else:
            # Single-ended -> negative channel set to ground reference (199)
            ljm.eWriteName(handle, f"{self.ain}_NEGATIVE_CH", 199)
            print(f"Configuring {self.ain} as SINGLE-ENDED (to GND)")

        # Common settings
        ljm.eWriteName(handle, f"{self.ain}_RANGE", 10.0)  # ±10V
        ljm.eWriteName(handle, f"{self.ain}_RESOLUTION_INDEX", 8)
        ljm.eWriteName(handle, f"{self.ain}_SETTLING_US", 10)

    def read_value(self, ljm, handle):
        value = ljm.eReadName(handle, self.ain)
        print(f"{self.ain}: {value:.6f} V")
        return value


def load_sensors_from_json(path: Optional[str] = "labjack_channels.json") -> List[Sensor]:
    try:
        with open(path, "r") as f:
            data = json.load(f)
    except Exception as e:
        print(f"Error reading {path}: {e}")
        return []

    # support wrapped format
    if isinstance(data, dict) and "Channels" in data:
        data = data["Channels"]

    sensors = []
    for entry in data:
        try:
            sensors.append(
                Sensor(
                    ain=entry["AIN"],
                    sensor_type=entry["SensorType"],
                    differential=entry.get("Differential", False),
                    negative_ain=entry.get("NegativeAIN")
                )
            )
        except KeyError as e:
            print(f"Skipping invalid entry (missing {e}): {entry}")

    print(f"Loaded {len(sensors)} sensors")
    return sensors
