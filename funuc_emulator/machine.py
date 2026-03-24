"""CNC machine simulation for the Fanuc emulator.

The :class:`Machine` class interprets parsed G-code blocks and maintains
the machine state (position, modal groups, spindle, feed, etc.).  It also
accumulates the tool path so the UI can draw it.
"""

from __future__ import annotations

import math
from dataclasses import dataclass, field
from typing import Callable, List, Optional, Tuple

from .parser import Block, arc_points, parse_program


# ---------------------------------------------------------------------------
# Machine state
# ---------------------------------------------------------------------------

@dataclass
class Position:
    x: float = 0.0
    y: float = 0.0
    z: float = 0.0

    def as_tuple(self) -> Tuple[float, float, float]:
        return (self.x, self.y, self.z)

    def copy(self) -> "Position":
        return Position(self.x, self.y, self.z)


@dataclass
class ToolPathSegment:
    """A single move recorded in the tool path."""
    motion: str          # 'rapid', 'feed', 'arc_cw', 'arc_ccw'
    start: Tuple[float, float, float]
    end: Tuple[float, float, float]
    # For arcs: intermediate points in the XY plane
    arc_points: List[Tuple[float, float]] = field(default_factory=list)


class MachineError(Exception):
    """Raised when an invalid G-code is encountered during execution."""


class Machine:
    """Virtual Fanuc CNC machine (3-axis mill)."""

    # Modal group defaults
    _DEFAULT_MOTION = 0        # G00
    _DEFAULT_PLANE = 17        # G17 (XY)
    _DEFAULT_UNIT = 21         # metric
    _DEFAULT_DISTANCE = 90     # absolute
    _DEFAULT_FEED_MODE = 94    # per minute

    def __init__(self) -> None:
        self.reset()

    # ------------------------------------------------------------------
    # Public interface
    # ------------------------------------------------------------------

    def reset(self) -> None:
        """Reset machine to power-on state."""
        self.position = Position()
        self.home = Position()

        # Modal G groups
        self.motion_mode: int = self._DEFAULT_MOTION
        self.plane: int = self._DEFAULT_PLANE
        self.units: int = self._DEFAULT_UNIT      # 20 = inch, 21 = mm
        self.distance_mode: int = self._DEFAULT_DISTANCE   # 90/91

        # Spindle / coolant
        self.spindle_on: bool = False
        self.spindle_cw: bool = True
        self.spindle_speed: float = 0.0

        # Feed
        self.feed_rate: float = 0.0
        self.feed_mode: int = self._DEFAULT_FEED_MODE

        # Tool
        self.tool_number: int = 0
        self.tool_length_offset: float = 0.0

        # Execution state
        self.program_running: bool = False
        self.program_stopped: bool = False
        self.optional_stop: bool = False

        # Tool path recording
        self.tool_path: List[ToolPathSegment] = []

        # Status message
        self.status: str = "READY"

    def load_program(self, source: str) -> Tuple[List[Block], list]:
        """Parse *source* and return ``(blocks, errors)``."""
        blocks, errors = parse_program(source)
        return blocks, errors

    def run_program(
        self,
        source: str,
        on_block: Optional[Callable[[int, Block], None]] = None,
    ) -> List[str]:
        """Execute a G-code program string.

        *on_block* is an optional callback invoked before each block is
        executed: ``on_block(index, block)``.

        Returns a list of warning/info messages produced during execution.
        """
        blocks, parse_errors = parse_program(source)
        messages: List[str] = [
            f"N{e.line_number}: parse error – {e.message}" for e in parse_errors
        ]

        self.program_running = True
        self.program_stopped = False
        self.tool_path = []
        self.status = "RUNNING"

        try:
            for idx, block in enumerate(blocks):
                if self.program_stopped:
                    break
                if on_block:
                    on_block(idx, block)
                msg = self._execute_block(block)
                if msg:
                    messages.append(msg)
        except MachineError as exc:
            messages.append(f"MACHINE ERROR: {exc}")
            self.status = "ALARM"
            return messages

        self.program_running = False
        if self.status != "ALARM":
            self.status = "DONE"
        return messages

    def execute_mdi(self, line: str) -> str:
        """Execute a single MDI line.  Returns a status / error string."""
        blocks, errors = parse_program(line)
        if errors:
            return f"Parse error: {errors[0].message}"
        if not blocks:
            return "OK"
        try:
            for block in blocks:
                msg = self._execute_block(block)
                if msg:
                    return msg
        except MachineError as exc:
            self.status = "ALARM"
            return f"ALARM: {exc}"
        return "OK"

    # ------------------------------------------------------------------
    # Internal execution
    # ------------------------------------------------------------------

    def _execute_block(self, block: Block) -> Optional[str]:
        """Process one G-code block.  Returns an optional warning string."""
        msg: Optional[str] = None

        # ---- M codes (order matters: stop first) ----------------------
        m = block.get("M")
        if m is not None:
            m = int(m)
            if m in (2, 30):
                self.program_stopped = True
                self.spindle_on = False
                self.status = "DONE"
                return None
            elif m == 0:
                self.program_stopped = True
                self.status = "STOP"
                return None
            elif m == 1 and self.optional_stop:
                self.program_stopped = True
                self.status = "OPT STOP"
                return None
            elif m == 3:
                self.spindle_on = True
                self.spindle_cw = True
            elif m == 4:
                self.spindle_on = True
                self.spindle_cw = False
            elif m == 5:
                self.spindle_on = False
            elif m == 6:
                t = block.get("T")
                if t is not None:
                    self.tool_number = int(t)
            elif m in (8, 9):
                pass  # coolant – noted but not simulated

        # ---- T / S / F words -----------------------------------------
        t = block.get("T")
        if t is not None and block.get("M") != 6:
            self.tool_number = int(t)

        s = block.get("S")
        if s is not None:
            self.spindle_speed = s

        f = block.get("F")
        if f is not None:
            self.feed_rate = f

        # ---- G codes --------------------------------------------------
        g_words = [int(w.value) for w in block.words if w.letter == "G"]

        for g in g_words:
            if g in (17, 18, 19):
                self.plane = g
            elif g == 20:
                self.units = 20
            elif g == 21:
                self.units = 21
            elif g in (90, 91):
                self.distance_mode = g
            elif g in (94, 95):
                self.feed_mode = g
            elif g == 28:
                # Return to reference / home
                prev = self.position.copy()
                self.position = Position()
                self.tool_path.append(ToolPathSegment(
                    motion="rapid",
                    start=prev.as_tuple(),
                    end=self.position.as_tuple(),
                ))
            elif g in (40, 41, 42, 43, 44, 49):
                pass  # compensation – accepted, not simulated
            elif g in range(54, 60):
                pass  # WCS offset – accepted, not simulated
            elif g == 80:
                self.motion_mode = 0
            elif g == 4:
                # Dwell
                p = block.get("P", 0.0)
                msg = f"DWELL {p} ms"
            elif g in (0, 1, 2, 3):
                self.motion_mode = g

        # ---- Motion block --------------------------------------------
        has_xyz = block.has("X") or block.has("Y") or block.has("Z")
        if not has_xyz:
            return msg

        motion = self.motion_mode
        # Allow explicit G on the same block to override modal
        for g in g_words:
            if g in (0, 1, 2, 3):
                motion = g

        # Resolve target position
        target = self._resolve_target(block)

        if motion == 0:
            self._move_rapid(target)
        elif motion == 1:
            self._move_linear(target)
        elif motion == 2:
            self._move_arc(block, target, clockwise=True)
        elif motion == 3:
            self._move_arc(block, target, clockwise=False)

        return msg

    def _resolve_target(self, block: Block) -> Position:
        """Return the absolute target position for this block."""
        cur = self.position
        if self.distance_mode == 90:
            # Absolute
            x = block.get("X", cur.x)
            y = block.get("Y", cur.y)
            z = block.get("Z", cur.z)
        else:
            # Incremental
            x = cur.x + block.get("X", 0.0)
            y = cur.y + block.get("Y", 0.0)
            z = cur.z + block.get("Z", 0.0)
        return Position(x, y, z)

    def _move_rapid(self, target: Position) -> None:
        seg = ToolPathSegment(
            motion="rapid",
            start=self.position.as_tuple(),
            end=target.as_tuple(),
        )
        self.tool_path.append(seg)
        self.position = target

    def _move_linear(self, target: Position) -> None:
        seg = ToolPathSegment(
            motion="feed",
            start=self.position.as_tuple(),
            end=target.as_tuple(),
        )
        self.tool_path.append(seg)
        self.position = target

    def _move_arc(self, block: Block, target: Position, clockwise: bool) -> None:
        """Circular interpolation in the selected plane."""
        start = self.position
        # Centre offsets I J K are incremental from start
        i = block.get("I", 0.0)
        j = block.get("J", 0.0)
        # Radius form
        r = block.get("R")

        if self.plane == 17:  # XY
            if r is not None:
                cx, cy = self._centre_from_radius(
                    start.x, start.y, target.x, target.y, r, clockwise
                )
            else:
                cx = start.x + i
                cy = start.y + j
            pts = arc_points(
                (start.x, start.y), (target.x, target.y),
                (cx, cy), clockwise
            )
        else:
            # For G18/G19 just treat as linear for visualisation
            pts = []

        label = "arc_cw" if clockwise else "arc_ccw"
        seg = ToolPathSegment(
            motion=label,
            start=start.as_tuple(),
            end=target.as_tuple(),
            arc_points=pts,
        )
        self.tool_path.append(seg)
        self.position = target

    @staticmethod
    def _centre_from_radius(
        x1: float, y1: float,
        x2: float, y2: float,
        r: float,
        clockwise: bool,
    ) -> Tuple[float, float]:
        """Compute arc centre from start/end and radius."""
        dx = x2 - x1
        dy = y2 - y1
        dist = math.hypot(dx, dy)
        if dist == 0 or dist > 2 * abs(r):
            raise MachineError("Arc radius too small for start/end distance")
        # Midpoint
        mx = (x1 + x2) / 2
        my = (y1 + y2) / 2
        # Perpendicular offset magnitude
        h = math.sqrt(r * r - (dist / 2) ** 2)
        # Perpendicular unit vector
        px = -dy / dist
        py = dx / dist
        # Two candidate centres
        c1 = (mx + h * px, my + h * py)
        c2 = (mx - h * px, my - h * py)
        # For positive radius, Fanuc chooses the centre that makes the arc
        # span ≤ 180°; the sign of r selects the half.
        if r > 0:
            return c2 if clockwise else c1
        else:
            return c1 if clockwise else c2
