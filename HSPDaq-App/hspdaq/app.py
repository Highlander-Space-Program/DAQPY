# hspdaq/app.py
"""
Single entry‑point for the HSPDAQ application.

All heavy lifting (GUI widgets, hardware I/O, ML, scaling, CSV buffering)
lives in the sub‑modules; this file just orchestrates them.
"""
from __future__ import annotations

import pathlib
from datetime import datetime

import numpy as np
import PySimpleGUI as sg

from hspdaq.constants import (
    AIN_CHANNELS,
    COLORS,
    OFFSET_X,
    OFFSET_Y,
    STARTING_SIZE,
)
from hspdaq.hardware import open_device, close_device, read_snapshot
from hspdaq.model import predict_remaining_time
from hspdaq.recorder import Recorder
from hspdaq.gui import (
    build_file_prompt,
    build_main_window,
    Sensor,
    handle_table_click,
    handle_tare,
    place_button,
    update_pid,
)


# --------------------------------------------------------------------------- #
# helper to build sensors list & draw static axes once
# --------------------------------------------------------------------------- #
def _init_sensors(window: sg.Window) -> list[Sensor]:
    sensors = [
        Sensor(window["PT-ETH-01"], "PT-ETH-01", "psi", COLORS[0][1]),
        Sensor(window["PT-ETH-02"], "PT-ETH-02", "psi", COLORS[1][1]),
        Sensor(window["PT-NO-01"], "PT-NO-01", "psi", COLORS[2][1]),
        Sensor(window["PT-NO-02"], "PT-NO-02", "psi", COLORS[3][1]),
        Sensor(window["PT-NO-03"], "PT-NO-03", "psi", COLORS[4][1]),
        Sensor(window["PT-CH-01"], "PT-CH-01", "psi", COLORS[5][1]),
        Sensor(window["TOT-WEIGHT"], "TOT-Weight", "lb", COLORS[6][1]),
        Sensor(window["TC-01"], "TC-01", "F", COLORS[7][1]),
        Sensor(window["TC-02"], "TC-02", "F", COLORS[8][1]),
        Sensor(window["TC-03"], "TC-03", "F", COLORS[9][1]),
    ]

    # replicate the original static grid lines
    sensors[0].draw_axes(-500, 1520, 0, 1600, 250)
    sensors[1].draw_axes(-500, 1520, 0, 1600, 250)
    sensors[2].draw_axes(-500, 1520, 0, 1600, 250)
    sensors[3].draw_axes(-500, 1520, 0, 1600, 250)
    sensors[4].draw_axes(-500, 1520, 0, 1600, 250)
    sensors[5].draw_axes(-500, 1520, 0, 1600, 250)
    sensors[6].draw_axes(-500, 1330, -100, 100, 10)
    sensors[7].draw_axes(-500, 95, -20, 100, 10)
    sensors[8].draw_axes(-500, 95, -20, 100, 10)
    sensors[9].draw_axes(-500, 95, -20, 100, 10)

    return sensors


# --------------------------------------------------------------------------- #
# main function
# --------------------------------------------------------------------------- #
def main() -> None:
    # 1) ask for CSV file name -------------------------------------------------
    prompt = build_file_prompt()
    event, values = prompt.read()
    if event == sg.WIN_CLOSED:
        prompt.close()
        return
    csv_name = values.get("FILE_NAME") or datetime.now().strftime("%Y%m%d_%H%M%S")
    prompt.close()

    # 2) build main window & sensors ------------------------------------------
    window = build_main_window()
    sensors = _init_sensors(window)

    # 3) open LabJack + CSV recorder ------------------------------------------
    handle = open_device()
    header = ["Timestamp"] + AIN_CHANNELS + ["Total_Weight"] + [f"TC_{i}" for i in range(1, 4)]
    data_dir = pathlib.Path.cwd() / "data"
    data_dir.mkdir(exist_ok=True)
    recorder = Recorder(data_dir / f"{csv_name}.csv", header)

    # variables mirroring original script -------------------------------------
    x_coord = -500
    write_csv = True
    first_tare_done = False
    load_tare = 0.0
    mass_samples: list[float] = []
    time_samples: list[float] = []
    poly_coeff_ref = np.array([1.72501276, -24.80675432, 95.42369204])

    try:
        while True:
            # ---------------------------------------------------------------- #
            # handle PySimpleGUI events first
            # ---------------------------------------------------------------- #
            event, values = window.read(timeout=0)
            if event == sg.WIN_CLOSED:
                break
            if event == "START_WRITING":
                write_csv = True
            if event == "STOP_WRITING":
                write_csv = False
            if values.get("TABLE"):
                handle_table_click(values, window, sensors)
            if event:
                # data_line not yet known here; tare after reading snapshot
                pending_tare_event = event
            else:
                pending_tare_event = None

            # ---------------------------------------------------------------- #
            # read one snapshot from hardware
            # ---------------------------------------------------------------- #
            snap = read_snapshot(handle)

            # update sensors ---------------------------------------------------
            for idx, s in enumerate(sensors):
                # first six sensors correspond to scaled AIN values
                if idx < 6:
                    s.assign(snap[f"AIN{idx+1}"])
                elif idx == 6:
                    s.assign(snap["total_weight"])
                else:  # thermocouples
                    s.assign(snap[f"TC_{idx-6}"])

            # tare if requested -----------------------------------------------
            if pending_tare_event:
                handle_tare(pending_tare_event, sensors, list(snap.values()))

            # update table -----------------------------------------------------
            window["TABLE"].update(values=[s.get_display() for s in sensors], row_colors=COLORS)

            # plot points ------------------------------------------------------
            for s in sensors:
                if s.visible:
                    s.plot_point(x_coord)

            # ---------------------------------------------------------------- #
            # ETA prediction logic (same as original)
            # ---------------------------------------------------------------- #
            if snap["AIN4"] > 400.0:  # run_pressure threshold
                if not first_tare_done:
                    load_tare = abs(snap["total_weight"])
                    first_tare_done = True

                feature_dict = {
                    "supply_pressure": snap["AIN3"],
                    "supply_temperature": snap["TC_1"],
                    "run_pressure": snap["AIN4"],
                    "run_temperature": snap["TC_2"],
                    "current_mass": abs(snap["total_weight"]) - load_tare,
                }
                eta = predict_remaining_time(feature_dict)
                window["Method2"].update(round(eta, 2))

                # polynomial fit replicating legacy code ----------------------
                current_mass = abs(snap["total_weight"]) - load_tare
                if current_mass >= 5:
                    now = datetime.now()
                    elapsed = now.timestamp()
                    mass_samples.append(current_mass)
                    time_samples.append(elapsed)

                    if len(mass_samples) >= 3 and len(set(time_samples)) > 1:
                        coeff_live = np.polyfit(mass_samples, time_samples, 2)
                        window["Method1"].update(round(np.polyval(coeff_live, 17) - time_samples[-1]))
                        window["Method3"].update(round(np.polyval(poly_coeff_ref, 17) - time_samples[-1]))
                        window["Method4"].update(round(np.polyval(poly_coeff_ref, 17) - time_samples[-1]))

            # ---------------------------------------------------------------- #
            # write CSV buffer
            # ---------------------------------------------------------------- #
            if write_csv:
                row = [
                    snap["timestamp"],
                    *(snap[f"AIN{i+1}"] for i in range(6)),
                    snap["total_weight"],
                    snap["TC_1"],
                    snap["TC_2"],
                    snap["TC_3"],
                ]
                recorder.append(row)

            # ---------------------------------------------------------------- #
            # PID overlay absolute placement (unchanged numbers)
            # ---------------------------------------------------------------- #
            place_button(window, "PID_PTN01", 715 + OFFSET_X, 596 + OFFSET_Y)
            place_button(window, "PID_PTN02", 411 + OFFSET_X, 387 + OFFSET_Y)
            place_button(window, "PID_PTN03", 411 + OFFSET_X, 693 + OFFSET_Y)
            place_button(window, "PID_PTE01", 411 + OFFSET_X, 28 + OFFSET_Y)
            place_button(window, "PID_PTE02", 1 + OFFSET_X, 693 + OFFSET_Y)
            place_button(window, "PID_PTCH01", 411 + OFFSET_X, 790 + OFFSET_Y)
            place_button(window, "PID_TC01", 715 + OFFSET_X, 790 + OFFSET_Y)
            place_button(window, "PID_TC02", 411 + OFFSET_X, 294 + OFFSET_Y)
            place_button(window, "PID_TC03", 715 + OFFSET_X, 107 + OFFSET_Y)

            # update PID text values
            update_pid(window, "PID_PTE01", sensors[0].data, " psi")
            update_pid(window, "PID_PTE02", sensors[1].data, " psi")
            update_pid(window, "PID_PTN01", sensors[2].data, " psi")
            update_pid(window, "PID_PTN02", sensors[3].data, " psi")
            update_pid(window, "PID_PTN03", sensors[4].data, " psi")
            update_pid(window, "PID_PTCH01", sensors[5].data, " psi")
            update_pid(window, "PID_TC01", sensors[7].data, " F")
            update_pid(window, "PID_TC02", sensors[8].data, " F")
            update_pid(window, "PID_TC03", sensors[9].data, " F")

            # scroll graphs every 500 points ----------------------------------
            x_coord += 1
            if x_coord == 500:
                x_coord = -250
                for s in sensors:
                    s.draw_axes(-250, 1520 if s.unit == "psi" else 95, -20, 1600, 250, -750)

    finally:
        # graceful shutdown
        recorder.close()
        close_device(handle)
        window.close()


# allow `python -m hspdaq` to run
if __name__ == "__main__":
    main()
