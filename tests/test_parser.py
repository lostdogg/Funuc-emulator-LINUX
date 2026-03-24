"""Tests for the Fanuc G-code parser."""

from __future__ import annotations

import pytest

from funuc_emulator.parser import Block, Word, arc_points, parse_program


# ---------------------------------------------------------------------------
# parse_program
# ---------------------------------------------------------------------------

class TestParseProgram:
    def test_empty_string(self):
        blocks, errors = parse_program("")
        assert blocks == []
        assert errors == []

    def test_percent_lines_skipped(self):
        src = "%\nG00 X10.\n%"
        blocks, errors = parse_program(src)
        assert len(blocks) == 1
        assert errors == []

    def test_blank_lines_skipped(self):
        src = "G00 X10.\n\n   \nG01 Y5."
        blocks, errors = parse_program(src)
        assert len(blocks) == 2

    def test_line_numbers_extracted(self):
        src = "N10 G00 X10. Y20."
        blocks, _ = parse_program(src)
        assert blocks[0].line_number == 10

    def test_words_parsed(self):
        src = "G01 X100. Y-50.5 F200."
        blocks, errors = parse_program(src)
        assert errors == []
        b = blocks[0]
        assert b.get("G") == 1.0
        assert b.get("X") == 100.0
        assert b.get("Y") == pytest.approx(-50.5)
        assert b.get("F") == 200.0

    def test_inline_comment_stripped(self):
        src = "G00 X10. (rapid to X10) Y20."
        blocks, errors = parse_program(src)
        assert errors == []
        b = blocks[0]
        assert b.get("X") == 10.0
        assert b.get("Y") == 20.0
        assert "rapid to X10" in b.comment

    def test_semicolon_comment(self):
        src = "G01 Y5. ; move to Y5"
        blocks, _ = parse_program(src)
        b = blocks[0]
        assert b.get("Y") == 5.0
        assert "move to Y5" in b.comment

    def test_negative_value(self):
        src = "G01 Z-10."
        blocks, _ = parse_program(src)
        assert blocks[0].get("Z") == pytest.approx(-10.0)

    def test_scientific_notation(self):
        src = "G01 X1.5E1"
        blocks, errors = parse_program(src)
        assert errors == []
        assert blocks[0].get("X") == pytest.approx(15.0)

    def test_multiple_g_codes_in_block(self):
        src = "G21 G90 G94"
        blocks, _ = parse_program(src)
        b = blocks[0]
        g_vals = [w.value for w in b.words if w.letter == "G"]
        assert 21.0 in g_vals
        assert 90.0 in g_vals
        assert 94.0 in g_vals

    def test_block_has(self):
        src = "G00 X10."
        blocks, _ = parse_program(src)
        b = blocks[0]
        assert b.has("G")
        assert b.has("X")
        assert not b.has("Y")

    def test_block_get_default(self):
        src = "G00 X10."
        blocks, _ = parse_program(src)
        b = blocks[0]
        assert b.get("Y", 99.0) == 99.0

    def test_full_program(self):
        src = """\
%
O0001
N10 G21 G90
N20 G00 X0. Y0.
N30 G01 X50. F100.
N40 M30
%
"""
        blocks, errors = parse_program(src)
        assert errors == []
        # O word + N10 + N20 + N30 + N40
        assert len(blocks) == 5


# ---------------------------------------------------------------------------
# arc_points
# ---------------------------------------------------------------------------

class TestArcPoints:
    def test_quarter_circle_cw(self):
        import math
        start = (10.0, 0.0)
        end = (0.0, -10.0)
        center = (0.0, 0.0)
        pts = arc_points(start, end, center, clockwise=True, segments=4)
        # Start and end should be close to the given points
        assert pts[0] == pytest.approx(start, abs=1e-9)
        # All points should be on the circle
        for x, y in pts:
            assert math.hypot(x, y) == pytest.approx(10.0, abs=1e-6)

    def test_quarter_circle_ccw(self):
        import math
        start = (10.0, 0.0)
        end = (0.0, 10.0)
        center = (0.0, 0.0)
        pts = arc_points(start, end, center, clockwise=False, segments=4)
        assert pts[0] == pytest.approx(start, abs=1e-9)
        for x, y in pts:
            assert math.hypot(x, y) == pytest.approx(10.0, abs=1e-6)

    def test_segment_count(self):
        pts = arc_points((1, 0), (0, 1), (0, 0), clockwise=False, segments=10)
        assert len(pts) == 11  # segments + 1
