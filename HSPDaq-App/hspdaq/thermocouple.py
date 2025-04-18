"""
K/J‑type thermocouple helper utilities.
Only depends on NumPy; safe to import anywhere.
"""
from __future__ import annotations
import numpy as np

# --- NIST Type J reference tables (°C vs mV) ---
TEMP_TABLE_C = np.array([
    -200, -195, -190, -185, -180, -175, -170, -165, -160, -155,
    -150, -145, -140, -135, -130, -125, -120, -115, -110, -105,
    -100,  -95,  -90,  -85,  -80,  -75,  -70,  -65,  -60,  -55,
     -50,  -45,  -40,  -35,  -30,  -25,  -20,  -15,  -10,   -5,
       0,    5,   10,   15,   20,   25,   30,   35,   40,   45,
      50,   55,   60,   65,   70,   75,   80,   85,   90,   95,
     100,  105,  110,  115,  120,  125,  130,  135,  140,  145,
     150,  155,  160,  165,  170,  175,  180,  185,  190,  195,  200
])

MV_TABLE = np.array([
    -5.891, -5.813, -5.730, -5.642, -5.550, -5.454, -5.354, -5.250, -5.141, -5.029,
    -4.913, -4.793, -4.669, -4.542, -4.411, -4.276, -4.138, -3.997, -3.852, -3.705,
    -3.554, -3.400, -3.243, -3.083, -2.920, -2.755, -2.587, -2.416, -2.243, -2.067,
    -1.889, -1.709, -1.527, -1.343, -1.156, -0.968, -0.778, -0.586, -0.392, -0.197,
     0.000,  0.198,  0.397,  0.597,  0.798,  1.000,  1.203,  1.407,  1.612,  1.817,
     2.023,  2.230,  2.436,  2.644,  2.851,  3.059,  3.267,  3.474,  3.682,  3.889,
     4.096,  4.303,  4.509,  4.715,  4.920,  5.124,  5.328,  5.532,  5.735,  5.937,
     6.138,  6.339,  6.540,  6.741,  6.941,  7.140,  7.340,  7.540,  7.739,  7.939,  8.138
])


def type_j_temp_from_mv(voltage_mv: float | np.ndarray) -> float | np.ndarray:
    """Interpolate a Type‑J thermocouple temperature (°C) from millivolts."""
    return np.interp(voltage_mv, MV_TABLE, TEMP_TABLE_C)


def thermocouple_voltage_to_temperature(thermo_v: float, cj_temp_c: float) -> float:
    """
    Quick linear K‑type approximation.
      dT (°C) ≈ thermo_v (V) / 41 µV per °C
      TC °C   = CJ °C + dT
      TC °F   = (TC °C × 9/5) + 32
    Note: valid only over a limited range; your original script accepted that.
    """
    dT_c = thermo_v / 0.000041
    tc_c = cj_temp_c + dT_c
    return tc_c * 9/5 + 32
