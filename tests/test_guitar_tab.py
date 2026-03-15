"""Tests for the guitar_tab module."""

import pytest
from g2t.guitar_tab import (
    get_fret_positions, optimize_positions, generate_tab_string,
    notes_to_tab, STANDARD_TUNING,
)


class TestGetFretPositions:
    def test_open_low_e(self):
        # MIDI 40 = E2, open 6th string
        positions = get_fret_positions(40)
        assert (0, 0) in positions

    def test_a2_on_a_string(self):
        # MIDI 45 = A2, open 5th string
        positions = get_fret_positions(45)
        assert (1, 0) in positions
        # Also fret 5 on low E
        assert (0, 5) in positions

    def test_high_note_fret_12(self):
        # MIDI 52 = E3, fret 12 on low E
        positions = get_fret_positions(52)
        assert (0, 12) in positions

    def test_out_of_range(self):
        # Very low note below guitar range
        positions = get_fret_positions(20)
        assert len(positions) == 0

    def test_high_e4_open(self):
        # MIDI 64 = E4, open high e string
        positions = get_fret_positions(64)
        assert (5, 0) in positions


class TestOptimizePositions:
    def test_empty(self):
        assert optimize_positions([]) == []

    def test_single_note(self):
        notes = [{'midi': 40}]  # Low E
        result = optimize_positions(notes)
        assert len(result) == 1
        assert result[0] is not None
        assert result[0][1] >= 0  # Valid fret

    def test_prefers_nearby_frets(self):
        # Play several notes around fret 5
        notes = [{'midi': 45}, {'midi': 47}, {'midi': 48}]  # A2, B2, C3
        result = optimize_positions(notes)
        frets = [pos[1] for pos in result if pos is not None]
        # All frets should be reasonably close together
        if len(frets) >= 2:
            assert max(frets) - min(frets) <= 10

    def test_out_of_range_returns_none(self):
        notes = [{'midi': 20}]  # Way below guitar range
        result = optimize_positions(notes)
        assert result[0] is None


class TestGenerateTabString:
    def test_empty_notes(self):
        tab = generate_tab_string([], [])
        assert 'e|' in tab
        assert 'E|' in tab

    def test_single_note(self):
        notes = [{'start': 0.0, 'end': 0.5, 'midi': 40}]
        positions = [(0, 0)]
        tab = generate_tab_string(notes, positions, tempo=120.0)
        assert '0' in tab  # Open string should appear


class TestNotesToTab:
    def test_basic_scale(self):
        # Simple ascending notes
        notes = [
            {'start': 0.0, 'end': 0.5, 'midi': 40, 'note_name': 'E2'},
            {'start': 0.5, 'end': 1.0, 'midi': 42, 'note_name': 'F#2'},
            {'start': 1.0, 'end': 1.5, 'midi': 44, 'note_name': 'G#2'},
        ]
        tab = notes_to_tab(notes, tempo=120.0)
        assert isinstance(tab, str)
        assert len(tab) > 0
        # Should contain 6 strings
        assert tab.count('|') >= 12  # At least 6 strings * 2 pipes each
