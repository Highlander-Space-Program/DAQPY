from __future__ import annotations
import PySimpleGUI as sg

from hspdaq.constants import FONTANDSIZE


class Sensor:
    def __init__(self, graph: sg.Graph, name: str, unit: str, color: str) -> None:
        self.graph = graph
        self.title = name
        self.unit = unit
        self.color = color

        self.visible = True
        self.tare = 0.0
        self.data = 0.0
        self._prev = 0.0

    def assign(self, value: float) -> None:
        self._prev = self.data
        self.data = float(value) - self.tare

    def data_tare(self, tare_val: float) -> None:
        self.tare = tare_val

    def get_display(self) -> list[str]:
        """Return ['PT-ETH‑01', '123.4 psi'] for the table."""
        return [self.title, f"{self.data:.2f} {self.unit}"]

    # ------------------------------------------------------------------ #
    # drawing helpers
    # ------------------------------------------------------------------ #
    def draw_axes(
        self,
        start_x: int,
        title_y: int,
        y_min: int,
        y_max: int,
        tick: int,
        shift: int = 0,
    ) -> None:
        """Draw Y axis, zero line and tick labels once per pane."""
        self.graph.move(shift, 0)
        self.graph.DrawLine((-500, -500), (-500, 1000))
        self.graph.DrawLine((start_x, 0), (500, 0))

        self.graph.DrawText(
            f"{self.title} ({self.unit})", (0, title_y), color="gray", font=FONTANDSIZE
        )

        for y in range(y_min, y_max, tick):
            if y != 0:
                self.graph.DrawLine((-500, y), (-450, y))
                self.graph.DrawText(y, (-400, y), color="gray", font=FONTANDSIZE)

    def plot_point(self, x: int) -> None:
        """Plot latest value at X; join to previous if large jump."""
        if abs(self.data - self._prev) < 1:
            self.graph.DrawCircle((x, self.data), 1, line_color=self.color)
        else:
            self.graph.DrawLine((x, self._prev), (x, self.data), self.color, 2)
