"""Tests for the sheet_music module."""

import pytest
from g2t.sheet_music import notes_to_stream, _quantize_duration


class TestQuantizeDuration:
    def test_quarter_note(self):
        assert _quantize_duration(1.0) == 1.0

    def test_half_note(self):
        assert _quantize_duration(2.0) == 2.0

    def test_eighth_note(self):
        assert _quantize_duration(0.5) == 0.5

    def test_whole_note(self):
        assert _quantize_duration(4.0) == 4.0

    def test_rounds_to_nearest(self):
        # 0.6 is between 0.5 (eighth) and 0.75 (dotted eighth)
        result = _quantize_duration(0.6)
        assert result in [0.5, 0.75]

    def test_very_short(self):
        result = _quantize_duration(0.1)
        assert result == 0.25  # Minimum: sixteenth note


class TestNotesToStream:
    def test_basic_stream(self):
        notes = [
            {'start': 0.0, 'end': 0.5, 'midi': 60, 'note_name': 'C4'},
            {'start': 0.5, 'end': 1.0, 'midi': 64, 'note_name': 'E4'},
        ]
        score = notes_to_stream(notes, tempo=120.0)
        assert score is not None

        # Should have one part
        parts = list(score.parts)
        assert len(parts) == 1

    def test_tempo_is_set(self):
        notes = [{'start': 0.0, 'end': 1.0, 'midi': 69, 'note_name': 'A4'}]
        score = notes_to_stream(notes, tempo=140.0)
        parts = list(score.parts)
        tempos = list(parts[0].getElementsByClass('MetronomeMark'))
        assert len(tempos) >= 1
