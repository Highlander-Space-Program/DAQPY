"""
LabJack T7 I/O helper utilities – open device, configure channels, grab a snapshot.
Keeps *all* hardware‑specific code in one place so the rest of the app is testable.
"""
from __future__ import annotations

from datetime import datetime

from labjack import ljm

from hspdaq.constants import (
    AIN_CHANNELS,
    DIFF_PAIRS,
    TC_PAIRS,
)
from hspdaq.scaling import apply_scaling, apply_differential_scaling
from hspdaq.thermocouple import thermocouple_voltage_to_temperature


# --------------------------------------------------------------------------- #
# Channel configuration
# --------------------------------------------------------------------------- #
def _configure_differential_pairs(handle, pairs: list[tuple[str, str]]) -> None:
    """
    Configure LabJack differential channels for either load cells or thermocouples.
    """
    for pos, neg in pairs:
        ljm.eWriteName(handle, f"{pos}_RANGE", 0.01)          # ±10 mV range :contentReference[oaicite:4]{index=4}
        ljm.eWriteName(handle, f"{pos}_NEGATIVE_CH", int(neg[3:]))


# --------------------------------------------------------------------------- #
# Device lifecycle helpers
# --------------------------------------------------------------------------- #
def open_device() -> int:
    """
    Open *any* connected LabJack, configure all differential pairs, return handle.
    """
    handle = ljm.openS("ANY", "ANY", "ANY")                   # :contentReference[oaicite:5]{index=5}
    _configure_differential_pairs(handle, DIFF_PAIRS)
    _configure_differential_pairs(handle, TC_PAIRS)
    return handle


def close_device(handle: int) -> None:
    """Close the LabJack handle if open."""
    ljm.close(handle)


# --------------------------------------------------------------------------- #
# Data acquisition
# --------------------------------------------------------------------------- #
def read_snapshot(handle: int) -> dict[str, float]:
    """
    Read all sensors once and return a dict with *scaled* engineering units.
    Keys:
      timestamp, scaled_AINx…, total_weight, TC_1, TC_2, TC_3
    """
    timestamp = datetime.now().strftime("%H:%M:%S:%f")[:-3]

    # --- Single‑ended pressures ------------------------------------------------
    ain_voltages = [ljm.eReadName(handle, ch) for ch in AIN_CHANNELS]
    scaled_ain   = [
        apply_scaling(v, ch) for v, ch in zip(ain_voltages, AIN_CHANNELS)
    ]

    # --- Differential load‑cell weights ---------------------------------------
    diff_voltages = [ljm.eReadName(handle, p[0]) for p in DIFF_PAIRS]
    scaled_weights = [apply_differential_scaling(v) for v in diff_voltages]
    total_weight   = sum(scaled_weights)

    # --- Thermocouples ---------------------------------------------------------
    cj_temp_k  = ljm.eReadName(handle, "TEMPERATURE_DEVICE_K")
    cj_temp_c  = cj_temp_k - 273.15
    tc_voltages = [ljm.eReadName(handle, p[0]) for p in TC_PAIRS]
    tc_temps_f  = [
        thermocouple_voltage_to_temperature(v, cj_temp_c) for v in tc_voltages
    ]

    # Assemble dictionary -------------------------------------------------------
    snapshot: dict[str, float] = {
        "timestamp": timestamp,
        **{f"AIN{i+1}": val for i, val in enumerate(scaled_ain)},
        "total_weight": total_weight,
        **{f"TC_{i+1}": temp for i, temp in enumerate(tc_temps_f)},
    }
    return snapshot
