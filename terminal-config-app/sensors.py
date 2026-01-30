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
        Configure analog input for LabJack T7.

        Supports:
        - Single-ended sensors
        - Differential sensors (load cells, TCs)
        - Thermocouples via Extended Features (EF)

        Validates:
        - Built-in T7 pairs: AIN0->AIN1 and AIN2->AIN3
        - Mux80 extended channels (48-127): negative = positive + 8
        """

        ain_num = self._ain_num(self.ain)

        # ----------------------------
        # Differential / Single-ended
        # ----------------------------
        if self.differential:
            if not self.negative_ain:
                raise ValueError(
                    f"Differential sensor {self.ain} requires 'NegativeAIN' in config."
                )

            neg_num = self._ain_num(self.negative_ain)
            valid = False

            # Built-in T7 pairs
            if ain_num in (0, 2) and neg_num == ain_num + 1:
                valid = True

            # Mux80 extended channels
            if 48 <= ain_num <= 127 and neg_num == ain_num + 8:
                valid = True

            if not valid:
                raise ValueError(
                    f"Invalid differential pair: {self.ain} and {self.negative_ain}. "
                    "Allowed: AIN0->AIN1, AIN2->AIN3, or Mux80 (AINx->AINx+8)."
                )

            ljm.eWriteName(handle, f"{self.ain}_RANGE", 0.01)
            ljm.eWriteName(handle, f"{self.ain}_NEGATIVE_CH", neg_num)
            # mode_desc = f"DIFFERENTIAL ({self.ain} - {self.negative_ain})"

        else:
            # Single-ended (GND reference)
            ljm.eWriteName(handle, f"{self.ain}_NEGATIVE_CH", 199)
            mode_desc = "SINGLE-ENDED (GND)"

        # ----------------------------
        # Sensor-type-specific config
        # ----------------------------
        # if self.sensor_type == "thermocouple":
        #     # Thermocouple MUST be differential
        #     if not self.differential:
        #         raise ValueError(f"{self.ain} thermocouple must be differential")

        #     # Enable Extended Feature: Type K thermocouple
        #     ljm.eWriteName(handle, f"{self.ain}_EF_INDEX", 21)     # Type K
        #     ljm.eWriteName(handle, f"{self.ain}_EF_CONFIG_A", 1)   # Output in °C

        #     # Tight range improves noise
        #     ljm.eWriteName(handle, f"{self.ain}_RANGE", 0.1)

        #     print(f"Configured {self.ain} as THERMOCOUPLE (Type K, °C) | {mode_desc}")
        #     return

        # elif self.sensor_type == "load_cell":
        #     # Load cells: very small differential voltages
        #     ljm.eWriteName(handle, f"{self.ain}_RANGE", 0.01)
        #     ljm.eWriteName(handle, f"{self.ain}_EF_INDEX", 13)      # Load cell / bridge
        #     ljm.eWriteName(handle, f"{self.ain}_EF_CONFIG_A", 2.0) # mV/V (example)
        #     ljm.eWriteName(handle, f"{self.ain}_EF_CONFIG_B", 100) # full scale lbs
        #     print(f"Configured {self.ain} as LOAD CELL | {mode_desc}")

        # else:
        #     # Default analog (pressure transducers, etc.)
        #     ljm.eWriteName(handle, f"{self.ain}_RANGE", 10.0)
        #     print(f"Configured {self.ain} as ANALOG | {mode_desc}")

        # ----------------------------
        # Common ADC settings
        # ----------------------------
        # ljm.eWriteName(handle, f"{self.ain}_RESOLUTION_INDEX", 8)
        # ljm.eWriteName(handle, f"{self.ain}_SETTLING_US", 10)


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
