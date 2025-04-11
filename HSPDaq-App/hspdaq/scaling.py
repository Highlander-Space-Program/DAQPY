"""
Voltage‑to‑engineering‑unit scaling functions.
No GUI or hardware imports—pure math only.
"""
from __future__ import annotations

def apply_scaling(value: float, channel: str) -> float:
    """
    Convert raw single‑ended AIN voltage to pressure or other units.
    The equations come directly from the original script.
    """
    if channel == "AIN68":                     # ETH1
        return (value - 0.5) / 4 * 1000       # psi
    else:                                      # all other pressure transducers
        return 397.14 * value - 189.29         # psi


def apply_differential_scaling(voltage: float) -> float:
    """
    Convert differential load‑cell voltage to weight in pounds (lb).
    """
    return (-(voltage * 51412) + 2.0204) / 0.45359237
