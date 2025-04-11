"""
Event‑handler helpers extracted from the monolithic script.
They *only* mutate the window & sensors; the main loop decides when to call them.
"""
from __future__ import annotations
import PySimpleGUI as sg

from hspdaq.constants import OFFSET_X, OFFSET_Y, COLORS
from hspdaq.gui.sensor import Sensor

def handle_table_click(values: dict, window: sg.Window, sensors: list[Sensor]) -> None:
    """Toggle graph visibility based on the index returned in values['TABLE']."""
    index_map = {
        0: ("PT-ETH-01", 0),
        1: ("PT-ETH-02", 1),
        2: ("PT-NO-01", 2),
        3: ("PT-NO-02", 3),
        4: ("PT-NO-03", 4),
        5: ("PT-CH-01", 5),
        6: ("TOT-WEIGHT", 6),
        7: ("TC-01", 7),
        8: ("TC-02", 8),
        9: ("TC-03", 9),
    }
    if values.get("TABLE"):
        idx = values["TABLE"][0]
        key, sensor_idx = index_map[idx]
        sensors[sensor_idx].visible = not sensors[sensor_idx].visible
        window[key].update(visible=sensors[sensor_idx].visible)
        window["col2"].contents_changed()

def handle_tare(event: str, sensors: list[Sensor], data_line: list[str]) -> None:
    mapping = {
        ("PT-ETH-01", "PID_PTE01"): (0, 1),
        ("PT-ETH-02", "PID_PTE02"): (1, 2),
        ("PT-NO-01", "PID_PTN01"): (2, 3),
        ("PT-NO-02", "PID_PTN02"): (3, 4),
        ("PT-NO-03", "PID_PTN03"): (4, 5),
        ("PT-CH-01", "PID_PTCH01"): (5, 6),
        ("TOT-WEIGHT",): (6, 7),
    }
    for keys, (sensor_idx, data_idx) in mapping.items():
        if event in keys:
            sensors[sensor_idx].data_tare(float(data_line[data_idx]))
            break


def place_button(window: sg.Window, key: str, x_pos: int, y_pos: int) -> None:
    widget = window[key].widget
    widget.master.place(x=x_pos, y=y_pos, bordermode=sg.tk.INSIDE)


def update_pid(window: sg.Window, key: str, value: str, unit: str) -> None:
    try:
        window[key].update(f"{float(value):.2f}{unit}")
    except ValueError:
        window[key].update(value)
