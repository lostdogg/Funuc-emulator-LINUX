"""Status and coordinate display panels for the Fanuc emulator."""

from __future__ import annotations

import tkinter as tk
from tkinter import ttk
from typing import Optional

from ..machine import Machine


_DARK_BG = "#1e1e1e"
_PANEL_BG = "#252525"
_LABEL_FG = "#aaaaaa"
_VALUE_FG = "#00ff88"
_ALARM_FG = "#ff4444"
_TITLE_FG = "#ffffff"

_MONO = ("Monospace", 10)
_MONO_LG = ("Monospace", 14, "bold")
_MONO_SM = ("Monospace", 9)


class CoordinatePanel(tk.Frame):
    """Shows current machine / work coordinates (X Y Z)."""

    def __init__(self, parent: tk.Widget, **kwargs) -> None:
        kwargs.setdefault("bg", _PANEL_BG)
        kwargs.setdefault("padx", 8)
        kwargs.setdefault("pady", 8)
        super().__init__(parent, **kwargs)

        tk.Label(self, text="COORDINATES", bg=_PANEL_BG, fg=_TITLE_FG,
                 font=_MONO_SM).grid(row=0, column=0, columnspan=2,
                                     sticky="w", pady=(0, 4))

        self._vars = {}
        for row, axis in enumerate(("X", "Y", "Z"), start=1):
            tk.Label(self, text=f" {axis} ", bg=_PANEL_BG, fg=_LABEL_FG,
                     font=_MONO_LG).grid(row=row, column=0, sticky="w")
            var = tk.StringVar(value="   0.000")
            tk.Label(self, textvariable=var, bg=_PANEL_BG, fg=_VALUE_FG,
                     font=_MONO_LG, width=12, anchor="e").grid(
                row=row, column=1, sticky="e", padx=(4, 0))
            self._vars[axis] = var

    def update_from(self, machine: Machine) -> None:
        self._vars["X"].set(f"{machine.position.x:>10.3f}")
        self._vars["Y"].set(f"{machine.position.y:>10.3f}")
        self._vars["Z"].set(f"{machine.position.z:>10.3f}")


class StatusPanel(tk.Frame):
    """Shows spindle speed, feed rate, tool, mode, and status."""

    def __init__(self, parent: tk.Widget, **kwargs) -> None:
        kwargs.setdefault("bg", _PANEL_BG)
        kwargs.setdefault("padx", 8)
        kwargs.setdefault("pady", 8)
        super().__init__(parent, **kwargs)

        tk.Label(self, text="MACHINE STATUS", bg=_PANEL_BG, fg=_TITLE_FG,
                 font=_MONO_SM).grid(row=0, column=0, columnspan=2,
                                     sticky="w", pady=(0, 4))

        rows = [
            ("STATUS", "status"),
            ("FEED", "feed"),
            ("SPINDLE", "spindle"),
            ("TOOL", "tool"),
            ("UNITS", "units"),
            ("MODE", "mode"),
        ]
        self._vars = {}
        for i, (label, key) in enumerate(rows, start=1):
            tk.Label(self, text=f"{label}:", bg=_PANEL_BG, fg=_LABEL_FG,
                     font=_MONO_SM, anchor="w", width=9).grid(
                row=i, column=0, sticky="w")
            var = tk.StringVar(value="—")
            color = _ALARM_FG if key == "status" else _VALUE_FG
            tk.Label(self, textvariable=var, bg=_PANEL_BG, fg=color,
                     font=_MONO, anchor="w").grid(row=i, column=1, sticky="w")
            self._vars[key] = var

    def update_from(self, machine: Machine) -> None:
        st = machine.status
        self._vars["status"].set(st)
        self._vars["feed"].set(f"{machine.feed_rate:.1f} mm/min")
        spindle_dir = "CW" if machine.spindle_cw else "CCW"
        state = f"{machine.spindle_speed:.0f} rpm {spindle_dir}" \
            if machine.spindle_on else "OFF"
        self._vars["spindle"].set(state)
        self._vars["tool"].set(f"T{machine.tool_number:02d}")
        self._vars["units"].set("Metric (mm)" if machine.units == 21 else "Inch")
        self._vars["mode"].set(
            "ABSOLUTE" if machine.distance_mode == 90 else "INCREMENTAL"
        )


class MessageLog(tk.Frame):
    """Scrollable log of execution messages."""

    def __init__(self, parent: tk.Widget, **kwargs) -> None:
        kwargs.setdefault("bg", _PANEL_BG)
        super().__init__(parent, **kwargs)

        tk.Label(self, text="MESSAGE LOG", bg=_PANEL_BG, fg=_TITLE_FG,
                 font=_MONO_SM).pack(anchor="w", padx=6, pady=(6, 2))

        frame = tk.Frame(self, bg=_PANEL_BG)
        frame.pack(fill="both", expand=True, padx=6, pady=(0, 6))

        scrollbar = tk.Scrollbar(frame)
        scrollbar.pack(side="right", fill="y")

        self._text = tk.Text(
            frame,
            height=6,
            bg="#111111",
            fg="#cccccc",
            font=_MONO_SM,
            relief="flat",
            state="disabled",
            yscrollcommand=scrollbar.set,
        )
        self._text.pack(side="left", fill="both", expand=True)
        scrollbar.config(command=self._text.yview)

    def log(self, message: str) -> None:
        self._text.config(state="normal")
        self._text.insert("end", message + "\n")
        self._text.see("end")
        self._text.config(state="disabled")

    def clear(self) -> None:
        self._text.config(state="normal")
        self._text.delete("1.0", "end")
        self._text.config(state="disabled")
