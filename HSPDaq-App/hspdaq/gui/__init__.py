"""
Re‑export the public bits so `from hspdaq.gui import build_main_window`
just works without digging into sub‑modules.
"""
from .layout import build_file_prompt, build_main_window
from .sensor import Sensor
from .events import (
    handle_table_click,
    handle_tare,
    place_button,
    update_pid,
)

__all__ = [
    "build_file_prompt",
    "build_main_window",
    "Sensor",
    "handle_table_click",
    "handle_tare",
    "place_button",
    "update_pid",
]
