"""Tests for the note_converter module."""

import math
import pytest
from g2t.note_converter import (
    freq_to_midi, freq_to_midi_float, midi_to_freq, midi_to_note_name,
    freq_to_note_name, note_name_to_midi, cents_off, quantize_notes,
    A4_FREQ, A4_MIDI,
)


class TestFreqToMidi:
    def test_a4(self):
        assert freq_to_midi(440.0) == 69

    def test_middle_c(self):
        # C4 = MIDI 60, ~261.63 Hz
        assert freq_to_midi(261.63) == 60

    def test_a3(self):
        assert freq_to_midi(220.0) == 57

    def test_a5(self):
        assert freq_to_midi(880.0) == 81

    def test_low_e2(self):
        # E2 = MIDI 40, ~82.41 Hz (low E guitar string)
        assert freq_to_midi(82.41) == 40

    def test_invalid_zero(self):
        with pytest.raises(ValueError):
            freq_to_midi(0)

    def test_invalid_negative(self):
        with pytest.raises(ValueError):
            freq_to_midi(-100)


class TestFreqToMidiFloat:
    def test_a4_exact(self):
        result = freq_to_midi_float(440.0)
        assert abs(result - 69.0) < 0.001

    def test_between_notes(self):
        # Frequency between A4 and A#4
        result = freq_to_midi_float(453.0)
        assert 69 < result < 70


class TestMidiToFreq:
    def test_a4(self):
        assert abs(midi_to_freq(69) - 440.0) < 0.01

    def test_roundtrip(self):
        for midi in [40, 60, 69, 80, 100]:
            freq = midi_to_freq(midi)
            assert freq_to_midi(freq) == midi


class TestMidiToNoteName:
    def test_a4(self):
        assert midi_to_note_name(69) == "A4"

    def test_c4(self):
        assert midi_to_note_name(60) == "C4"

    def test_e2(self):
        assert midi_to_note_name(40) == "E2"

    def test_c_sharp_5(self):
        assert midi_to_note_name(73) == "C#5"


class TestFreqToNoteName:
    def test_a4(self):
        assert freq_to_note_name(440.0) == "A4"

    def test_c4(self):
        assert freq_to_note_name(261.63) == "C4"


class TestNoteNameToMidi:
    def test_a4(self):
        assert note_name_to_midi("A4") == 69

    def test_c4(self):
        assert note_name_to_midi("C4") == 60

    def test_f_sharp_3(self):
        assert note_name_to_midi("F#3") == 54

    def test_unknown_raises(self):
        with pytest.raises(ValueError):
            note_name_to_midi("X4")


class TestCentsOff:
    def test_exact_pitch(self):
        assert abs(cents_off(440.0, 69)) < 0.01

    def test_sharp(self):
        # Slightly above A4
        c = cents_off(445.0, 69)
        assert c > 0

    def test_flat(self):
        # Slightly below A4
        c = cents_off(435.0, 69)
        assert c < 0


class TestQuantizeNotes:
    def test_basic(self):
        notes = [{'frequency': 440.0, 'start': 0, 'end': 1}]
        result = quantize_notes(notes)
        assert result[0]['midi'] == 69
        assert result[0]['note_name'] == 'A4'
        assert abs(result[0]['cents_off']) < 0.1

    def test_multiple(self):
        notes = [
            {'frequency': 261.63, 'start': 0, 'end': 0.5},
            {'frequency': 329.63, 'start': 0.5, 'end': 1.0},
        ]
        result = quantize_notes(notes)
        assert result[0]['note_name'] == 'C4'
        assert result[1]['note_name'] == 'E4'
