"""Tool-path canvas widget for the Fanuc emulator.

Draws the recorded :class:`~funuc_emulator.machine.ToolPathSegment` list
onto a ``tk.Canvas``.  Supports zoom and pan.
"""

from __future__ import annotations

import math
import tkinter as tk
from typing import List, Optional, Tuple

from ..machine import ToolPathSegment


_RAPID_COLOR = "#e74c3c"       # red
_FEED_COLOR = "#2ecc71"        # green
_ARC_CW_COLOR = "#3498db"      # blue
_ARC_CCW_COLOR = "#9b59b6"     # purple
_GRID_COLOR = "#2c2c2c"
_AXIS_COLOR = "#555555"
_BG_COLOR = "#1a1a1a"
_CURSOR_COLOR = "#f39c12"      # orange (current position marker)


class ToolPathCanvas(tk.Canvas):
    """Resizable canvas that renders the 2-D tool path (XY plane)."""

    def __init__(self, parent: tk.Widget, **kwargs) -> None:
        kwargs.setdefault("bg", _BG_COLOR)
        kwargs.setdefault("highlightthickness", 0)
        super().__init__(parent, **kwargs)

        self._segments: List[ToolPathSegment] = []
        self._current_pos: Tuple[float, float] = (0.0, 0.0)

        # View transform
        self._scale: float = 5.0        # pixels per mm (default)
        self._offset_x: float = 0.0    # canvas-centre offset in pixels
        self._offset_y: float = 0.0

        # Pan state
        self._pan_start: Optional[Tuple[int, int]] = None

        self.bind("<Configure>", self._on_resize)
        self.bind("<MouseWheel>", self._on_scroll)       # Windows / X11
        self.bind("<Button-4>", self._on_scroll)         # Linux scroll up
        self.bind("<Button-5>", self._on_scroll)         # Linux scroll down
        self.bind("<ButtonPress-2>", self._on_pan_start)  # middle button
        self.bind("<B2-Motion>", self._on_pan_move)
        self.bind("<ButtonPress-1>", self._on_pan_start)  # left drag also pans
        self.bind("<B1-Motion>", self._on_pan_move)

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def set_tool_path(
        self,
        segments: List[ToolPathSegment],
        current_pos: Tuple[float, float] = (0.0, 0.0),
    ) -> None:
        self._segments = segments
        self._current_pos = current_pos
        self.redraw()

    def fit_all(self) -> None:
        """Auto-scale so all segments fit in the canvas."""
        if not self._segments:
            self._scale = 5.0
            self._offset_x = 0.0
            self._offset_y = 0.0
            self.redraw()
            return

        xs: List[float] = []
        ys: List[float] = []
        for seg in self._segments:
            xs += [seg.start[0], seg.end[0]]
            ys += [seg.start[1], seg.end[1]]
            for px, py in seg.arc_points:
                xs.append(px)
                ys.append(py)
        xs.append(0.0)
        ys.append(0.0)

        min_x, max_x = min(xs), max(xs)
        min_y, max_y = min(ys), max(ys)
        cx = (min_x + max_x) / 2
        cy = (min_y + max_y) / 2

        w = self.winfo_width() or 600
        h = self.winfo_height() or 400
        margin = 40

        span_x = max_x - min_x or 1
        span_y = max_y - min_y or 1
        scale_x = (w - 2 * margin) / span_x
        scale_y = (h - 2 * margin) / span_y
        self._scale = min(scale_x, scale_y)
        self._offset_x = -cx * self._scale
        self._offset_y = cy * self._scale
        self.redraw()

    def redraw(self) -> None:
        self.delete("all")
        self._draw_grid()
        self._draw_axes()
        self._draw_segments()
        self._draw_cursor()

    # ------------------------------------------------------------------
    # Coordinate helpers
    # ------------------------------------------------------------------

    def _to_canvas(self, x: float, y: float) -> Tuple[float, float]:
        """Convert machine coordinates (mm) to canvas pixels."""
        w = self.winfo_width() or 600
        h = self.winfo_height() or 400
        cx = w / 2 + self._offset_x + x * self._scale
        cy = h / 2 + self._offset_y - y * self._scale  # flip Y
        return cx, cy

    # ------------------------------------------------------------------
    # Drawing
    # ------------------------------------------------------------------

    def _draw_grid(self) -> None:
        w = self.winfo_width() or 600
        h = self.winfo_height() or 400

        # Choose a sensible grid spacing in machine units
        raw_spacing = 10.0 / self._scale  # target ~10px between lines in mm
        # Round to nearest 1 / 5 / 10 / 50 / 100 …
        magnitude = 10 ** math.floor(math.log10(max(raw_spacing, 0.001)))
        for factor in (1, 2, 5, 10):
            if magnitude * factor * self._scale >= 8:
                grid_mm = magnitude * factor
                break
        else:
            grid_mm = magnitude * 10

        # World-coordinate visible range
        min_x = (0 - w / 2 - self._offset_x) / self._scale
        max_x = (w - w / 2 - self._offset_x) / self._scale
        min_y = -(h / 2 + self._offset_y) / self._scale
        max_y = -(-h / 2 + self._offset_y) / self._scale

        # Vertical lines
        x = math.floor(min_x / grid_mm) * grid_mm
        while x <= max_x:
            cx, _ = self._to_canvas(x, 0)
            self.create_line(cx, 0, cx, h, fill=_GRID_COLOR, width=1)
            x += grid_mm

        # Horizontal lines
        y = math.floor(min_y / grid_mm) * grid_mm
        while y <= max_y:
            _, cy = self._to_canvas(0, y)
            self.create_line(0, cy, w, cy, fill=_GRID_COLOR, width=1)
            y += grid_mm

    def _draw_axes(self) -> None:
        w = self.winfo_width() or 600
        h = self.winfo_height() or 400

        # X axis
        ox, oy = self._to_canvas(0, 0)
        self.create_line(0, oy, w, oy, fill=_AXIS_COLOR, width=1)
        # Y axis
        self.create_line(ox, 0, ox, h, fill=_AXIS_COLOR, width=1)

        # Labels
        self.create_text(w - 20, oy - 10, text="X", fill=_AXIS_COLOR, font=("Monospace", 9))
        self.create_text(ox + 10, 15, text="Y", fill=_AXIS_COLOR, font=("Monospace", 9))
        self.create_text(ox + 4, oy + 10, text="0", fill=_AXIS_COLOR, font=("Monospace", 8))

    def _draw_segments(self) -> None:
        for seg in self._segments:
            if seg.motion in ("arc_cw", "arc_ccw"):
                color = _ARC_CW_COLOR if seg.motion == "arc_cw" else _ARC_CCW_COLOR
                if len(seg.arc_points) >= 2:
                    pts: List[float] = []
                    for px, py in seg.arc_points:
                        cx, cy = self._to_canvas(px, py)
                        pts += [cx, cy]
                    if len(pts) >= 4:
                        self.create_line(*pts, fill=color, width=1, smooth=True)
                else:
                    # Fall back to straight line
                    x1, y1 = self._to_canvas(seg.start[0], seg.start[1])
                    x2, y2 = self._to_canvas(seg.end[0], seg.end[1])
                    self.create_line(x1, y1, x2, y2, fill=color, width=1)
            else:
                color = _RAPID_COLOR if seg.motion == "rapid" else _FEED_COLOR
                x1, y1 = self._to_canvas(seg.start[0], seg.start[1])
                x2, y2 = self._to_canvas(seg.end[0], seg.end[1])
                dash = (4, 4) if seg.motion == "rapid" else None
                self.create_line(x1, y1, x2, y2, fill=color, width=1,
                                 dash=dash)

    def _draw_cursor(self) -> None:
        mx, my = self._current_pos
        cx, cy = self._to_canvas(mx, my)
        r = 6
        self.create_line(cx - r, cy, cx + r, cy, fill=_CURSOR_COLOR, width=2)
        self.create_line(cx, cy - r, cx, cy + r, fill=_CURSOR_COLOR, width=2)
        self.create_oval(cx - 3, cy - 3, cx + 3, cy + 3,
                         outline=_CURSOR_COLOR, width=1)

    # ------------------------------------------------------------------
    # Event handlers
    # ------------------------------------------------------------------

    def _on_resize(self, event: tk.Event) -> None:
        self.redraw()

    def _on_scroll(self, event: tk.Event) -> None:
        if event.num == 4 or getattr(event, "delta", 0) > 0:
            factor = 1.15
        else:
            factor = 1 / 1.15
        self._scale *= factor
        self.redraw()

    def _on_pan_start(self, event: tk.Event) -> None:
        self._pan_start = (event.x, event.y)

    def _on_pan_move(self, event: tk.Event) -> None:
        if self._pan_start is None:
            return
        dx = event.x - self._pan_start[0]
        dy = event.y - self._pan_start[1]
        self._offset_x += dx
        self._offset_y += dy
        self._pan_start = (event.x, event.y)
        self.redraw()
