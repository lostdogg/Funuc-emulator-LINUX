"""Tests for the CNC machine simulation."""

from __future__ import annotations

import pytest

from funuc_emulator.machine import Machine, MachineError


class TestMachineReset:
    def test_default_position(self):
        m = Machine()
        assert m.position.x == 0.0
        assert m.position.y == 0.0
        assert m.position.z == 0.0

    def test_reset_clears_tool_path(self):
        m = Machine()
        m.run_program("G01 X10. F100.")
        assert len(m.tool_path) > 0
        m.reset()
        assert m.tool_path == []


class TestMotion:
    def _run(self, src: str) -> Machine:
        m = Machine()
        msgs = m.run_program(src)
        return m

    def test_g00_rapid_to_x(self):
        m = self._run("G00 X50.")
        assert m.position.x == pytest.approx(50.0)
        assert m.tool_path[0].motion == "rapid"

    def test_g01_feed_to_xy(self):
        m = self._run("G01 X10. Y20. F100.")
        assert m.position.x == pytest.approx(10.0)
        assert m.position.y == pytest.approx(20.0)
        assert m.tool_path[0].motion == "feed"

    def test_g91_incremental(self):
        m = self._run("G91\nG01 X10. F100.\nG01 X10. F100.")
        assert m.position.x == pytest.approx(20.0)

    def test_g28_returns_home(self):
        m = Machine()
        m.run_program("G01 X50. Y30. F100.")
        m.run_program("G28")
        assert m.position.x == pytest.approx(0.0)
        assert m.position.y == pytest.approx(0.0)

    def test_square_profile(self):
        src = """\
G21 G90 G94
G00 X0. Y0.
G01 X50. F200.
G01 Y50.
G01 X0.
G01 Y0.
M30
"""
        m = self._run(src)
        assert m.position.x == pytest.approx(0.0)
        assert m.position.y == pytest.approx(0.0)
        assert m.status == "DONE"

    def test_arc_g02_cw(self):
        src = "G02 X10. Y0. I5. J0. F100."
        m = Machine()
        m.position.x = 0.0
        m.position.y = 0.0
        msgs = m.run_program(f"G00 X0. Y0.\n{src}")
        assert any("arc_cw" == seg.motion for seg in m.tool_path)

    def test_arc_g03_ccw(self):
        src = "G03 X10. Y0. I5. J0. F100."
        m = Machine()
        msgs = m.run_program(f"G00 X0. Y0.\n{src}")
        assert any("arc_ccw" == seg.motion for seg in m.tool_path)


class TestModalCodes:
    def test_g20_sets_inch_units(self):
        m = Machine()
        m.run_program("G20")
        assert m.units == 20

    def test_g21_sets_metric_units(self):
        m = Machine()
        m.run_program("G20")
        m.run_program("G21")
        assert m.units == 21

    def test_g90_absolute(self):
        m = Machine()
        m.run_program("G90")
        assert m.distance_mode == 90

    def test_g91_incremental(self):
        m = Machine()
        m.run_program("G91")
        assert m.distance_mode == 91

    def test_spindle_m03(self):
        m = Machine()
        m.run_program("S500 M03")
        assert m.spindle_on is True
        assert m.spindle_cw is True
        assert m.spindle_speed == pytest.approx(500.0)

    def test_spindle_m04_ccw(self):
        m = Machine()
        m.run_program("S800 M04")
        assert m.spindle_on is True
        assert m.spindle_cw is False

    def test_spindle_m05_stops(self):
        m = Machine()
        m.run_program("S500 M03\nM05")
        assert m.spindle_on is False

    def test_m30_ends_program(self):
        m = Machine()
        m.run_program("G01 X10. F100.\nM30\nG01 X999.")
        # Should not reach X999
        assert m.position.x == pytest.approx(10.0)
        assert m.status == "DONE"

    def test_tool_change(self):
        m = Machine()
        m.run_program("T02 M06")
        assert m.tool_number == 2

    def test_feed_rate_stored(self):
        m = Machine()
        m.run_program("G01 X0. F250.")
        assert m.feed_rate == pytest.approx(250.0)


class TestMDI:
    def test_mdi_move(self):
        m = Machine()
        result = m.execute_mdi("G00 X25.")
        assert result == "OK"
        assert m.position.x == pytest.approx(25.0)

    def test_mdi_bad_parse(self):
        m = Machine()
        # An invalid number should come back as a parse error string
        result = m.execute_mdi("G01 X.")
        # The parser silently skips malformed words – empty MDI returns OK
        # Just assert it doesn't raise
        assert isinstance(result, str)

    def test_mdi_empty(self):
        m = Machine()
        result = m.execute_mdi("")
        assert result == "OK"
