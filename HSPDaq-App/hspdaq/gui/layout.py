from __future__ import annotations
import PySimpleGUI as sg
import importlib
_constants = importlib.import_module("hspdaq.constants")   #  ← add this line

from hspdaq.constants import (
    BACKGROUNDCOLOR,
    GRAPHBACKGROUNDCOLOR,
    TEXTCOLOR,
    TEXT_FONT_BIG,
    COLORS,
)


def build_file_prompt() -> sg.Window:
    layout = [
        [sg.Text("Enter File Name:", background_color=GRAPHBACKGROUNDCOLOR)],
        [sg.Input(key="FILE_NAME")],
        [sg.Button("Submit", button_color=GRAPHBACKGROUNDCOLOR)],
    ]
    return sg.Window(
        "HSP UI",
        layout,
        grab_anywhere=True,
        finalize=True,
        background_color=BACKGROUNDCOLOR,
        size=(400, 120),
        resizable=False,
    )

# main daq window

def build_main_window() -> sg.Window:
    graph_panes = [
        [
            sg.Graph(
                canvas_size=(500, 500),
                graph_bottom_left=(-500, -20),
                graph_top_right=(500, 1600),
                enable_events=True,
                key=k,
                background_color=GRAPHBACKGROUNDCOLOR,
            )
            for k in (
                "PT-ETH-01",
                "PT-ETH-02",
                "PT-NO-01",
                "PT-NO-02",
                "PT-NO-03",
            )
        ],
        [
            sg.Graph(
                canvas_size=(500, 500),
                graph_bottom_left=(-500, -20),
                graph_top_right=(500, 1600),
                enable_events=True,
                key="PT-CH-01",
                background_color=GRAPHBACKGROUNDCOLOR,
            ),
            sg.Graph(
                canvas_size=(500, 500),
                graph_bottom_left=(-500, -100),
                graph_top_right=(500, 100),
                enable_events=True,
                key="TOT-WEIGHT",
                background_color=GRAPHBACKGROUNDCOLOR,
            ),
            sg.Graph(
                canvas_size=(500, 500),
                graph_bottom_left=(-500, -20),
                graph_top_right=(500, 100),
                enable_events=True,
                key="TC-01",
                background_color=GRAPHBACKGROUNDCOLOR,
            ),
            sg.Graph(
                canvas_size=(500, 500),
                graph_bottom_left=(-500, -20),
                graph_top_right=(500, 100),
                enable_events=True,
                key="TC-02",
                background_color=GRAPHBACKGROUNDCOLOR,
            ),
            sg.Graph(
                canvas_size=(500, 500),
                graph_bottom_left=(-500, -20),
                graph_top_right=(500, 100),
                enable_events=True,
                key="TC-03",
                background_color=GRAPHBACKGROUNDCOLOR,
            ),
        ],
    ]

    # ----- ETA read‑outs ---------------------------------------------------- #
    eta_layout = [
        [sg.Text("TIME LEFT (s): ")],
        [sg.Text(":(", key="Method1", size=(6, 1))],
        [sg.Text(":(", key="Method2", size=(6, 1))],
        [sg.Text(":(", key="Method3", size=(6, 1))],
        [sg.Text(":(", key="Method4", size=(6, 1))],
    ]

    # ----- PID overlay ------------------------------------------------------ #
    pid_texts = [
        ("PID_PTN01", "PT_NO_01COLOR"),
        ("PID_PTN02", "PT_NO_02COLOR"),
        ("PID_PTN03", "PT_NO_03COLOR"),
        ("PID_PTE01", "PT_ETH_01COLOR"),
        ("PID_PTE02", "PT_ETH_02COLOR"),
        ("PID_PTCH01", "PT_CH_01COLOR"),
        ("PID_TC01", "TC_01COLOR"),
        ("PID_TC02", "TC_02COLOR"),
        ("PID_TC03", "TC_03COLOR"),
    ]
    pid_column = [
        [
            sg.Text(
                key=k,
                colors=(getattr(_constants, c), BACKGROUNDCOLOR),
                p=0,
                font=TEXT_FONT_BIG,
                justification="right",
                size=(11, 1),
                enable_events=True,
            )
        ]
        for k, c in pid_texts
    ]
    pid_column.insert(
        0,
        [
            sg.Image(
                filename="assets/PID.png",
                background_color=BACKGROUNDCOLOR,
                key="IMAGE",
                size=(1001, 957),
            )
        ],
    )
        # ----- Tab group -------------------------------------------------------- #
    # Tab 1 must receive a *layout*, i.e. list‑of‑rows‑of‑elements.
    tab1_layout = [[
        sg.Column(
            graph_panes,
            element_justification="left",
            background_color=BACKGROUNDCOLOR,
            key="col2",
            expand_x=True,
            expand_y=True,
            scrollable=True,
        )
    ]]

    # Tab 2 layout wraps the PID column in its own row list as well.
    tab2_layout = [[sg.VPush(),sg.Column(pid_column, background_color=BACKGROUNDCOLOR)]]

    tab_group = [
        [
            sg.TabGroup(
                layout=[
                    [sg.Tab("Tab 1", tab1_layout, background_color=GRAPHBACKGROUNDCOLOR)],
                    [sg.Tab("Tab 2", tab2_layout, background_color=GRAPHBACKGROUNDCOLOR)],
                ],
                background_color=GRAPHBACKGROUNDCOLOR,
                selected_background_color=GRAPHBACKGROUNDCOLOR,
                selected_title_color=TEXTCOLOR,
            )
        ]
    ]


    # ----- Whole window layout --------------------------------------------- #
    layout = [
        [
            sg.Column([[sg.Button("Start Writing", key="START_WRITING", size=(20, 2))]]),
            sg.Column([[sg.Button("Stop Writing", key="STOP_WRITING", size=(20, 2))]]),
        ],
        [
            sg.Table(
                values=[[0, 0]] * 10,
                headings=["Sensor", "Value"],
                cols_justification=["l", "r"],
                col_widths=[11, 11],
                auto_size_columns=False,
                hide_vertical_scroll=True,
                row_height=85,
                row_colors=COLORS,
                font="Courier 50",
                header_background_color=BACKGROUNDCOLOR,
                header_text_color=TEXTCOLOR,
                background_color=BACKGROUNDCOLOR,
                key="TABLE",
                size=(800, 1000),
                expand_x=True,
                expand_y=True,
                enable_events=True,
            ),
            sg.Column(eta_layout+tab_group, 
                      expand_x=True, expand_y=True),
        ],
    ]

    return sg.Window(
        "HSP UI",
        layout,
        grab_anywhere=True,
        finalize=True,
        background_color=BACKGROUNDCOLOR,
        size=(1920, 1080),
        resizable=True,
    )
