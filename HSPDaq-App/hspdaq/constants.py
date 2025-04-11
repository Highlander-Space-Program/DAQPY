"""
Centralised, edit‑in‑one‑place constants for the HSPDAQ application.
Only passive data lives here—no imports from other project modules.
"""

# --- UI colours & fonts ---
BACKGROUNDCOLOR      = "#121212"
GRAPHBACKGROUNDCOLOR = "#222222"
TEXTCOLOR            = "#FFFFFF"
FONTANDSIZE          = "Courier 15"
TEXT_FONT_BIG        = "Courier 20"

# Individual trace / label colours
PT_ETH_01COLOR = "#FF5733"
PT_ETH_02COLOR = "#33C3FF"
PT_NO_01COLOR  = "#FFC300"
PT_NO_02COLOR  = "#8D33FF"
PT_NO_03COLOR  = "#3333FF"
PT_CH_01COLOR  = "#FF33A1"
TOT_WEIGHTCOLOR= "#17A2B8"
TC_01COLOR     = "#C70039"
TC_02COLOR     = "#00994D"
TC_03COLOR     = "#EE00FF"

# Sensor‑table row colour mapping
COLORS = [
    [0, PT_ETH_01COLOR, BACKGROUNDCOLOR],
    [1, PT_ETH_02COLOR, BACKGROUNDCOLOR],
    [2, PT_NO_01COLOR,  BACKGROUNDCOLOR],
    [3, PT_NO_02COLOR,  BACKGROUNDCOLOR],
    [4, PT_NO_03COLOR,  BACKGROUNDCOLOR],
    [5, PT_CH_01COLOR,  BACKGROUNDCOLOR],
    [6, TOT_WEIGHTCOLOR,BACKGROUNDCOLOR],
    [7, TC_01COLOR,     BACKGROUNDCOLOR],
    [8, TC_02COLOR,     BACKGROUNDCOLOR],
    [9, TC_03COLOR,     BACKGROUNDCOLOR],
]

# --- Hardware configuration ---
AIN_CHANNELS = ["AIN68", "AIN65", "AIN67", "AIN63", "AIN64", "AIN66"]  # Single‑ended
DIFF_PAIRS   = [("AIN48", "AIN56"), ("AIN49", "AIN57"),
                ("AIN50", "AIN58"), ("AIN51", "AIN59")]               # Load cells
TC_PAIRS     = [("AIN54", "AIN62"), ("AIN53", "AIN61"), ("AIN52", "AIN60")]

BUFFER_LIMIT = 5000        # rows before flushing CSV buffer
STARTING_SIZE = (1920, 1080)

# Small offsets for absolute‑placement tweaks in PID overlay
OFFSET_X = 15
OFFSET_Y = 14