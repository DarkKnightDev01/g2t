"""Tests for the midi_generator module."""

import os
import tempfile
import pytest
import pretty_midi

from g2t.midi_generator import notes_to_midi, save_midi, create_midi_file


class TestNotesToMidi:
    def test_basic(self):
        notes = [
            {'start': 0.0, 'end': 0.5, 'midi': 60},
            {'start': 0.5, 'end': 1.0, 'midi': 64},
        ]
        midi_obj = notes_to_midi(notes)
        assert len(midi_obj.instruments) == 1
        assert len(midi_obj.instruments[0].notes) == 2

    def test_note_pitches(self):
        notes = [{'start': 0.0, 'end': 1.0, 'midi': 69}]  # A4
        midi_obj = notes_to_midi(notes)
        assert midi_obj.instruments[0].notes[0].pitch == 69

    def test_clamps_velocity(self):
        notes = [{'start': 0.0, 'end': 1.0, 'midi': 60, 'velocity': 200}]
        midi_obj = notes_to_midi(notes)
        assert midi_obj.instruments[0].notes[0].velocity == 127

    def test_clamps_midi_note(self):
        notes = [{'start': 0.0, 'end': 1.0, 'midi': 130}]
        midi_obj = notes_to_midi(notes)
        assert midi_obj.instruments[0].notes[0].pitch == 127

    def test_zero_duration_corrected(self):
        notes = [{'start': 1.0, 'end': 1.0, 'midi': 60}]
        midi_obj = notes_to_midi(notes)
        note = midi_obj.instruments[0].notes[0]
        assert note.end > note.start


class TestSaveMidi:
    def test_save_and_read(self):
        notes = [
            {'start': 0.0, 'end': 0.5, 'midi': 60},
            {'start': 0.5, 'end': 1.0, 'midi': 64},
            {'start': 1.0, 'end': 1.5, 'midi': 67},
        ]
        midi_obj = notes_to_midi(notes, tempo=120.0)

        with tempfile.NamedTemporaryFile(suffix='.mid', delete=False) as f:
            tmp_path = f.name

        try:
            save_midi(midi_obj, tmp_path)
            assert os.path.exists(tmp_path)
            assert os.path.getsize(tmp_path) > 0

            # Read it back
            loaded = pretty_midi.PrettyMIDI(tmp_path)
            assert len(loaded.instruments) == 1
            assert len(loaded.instruments[0].notes) == 3
        finally:
            os.unlink(tmp_path)


class TestCreateMidiFile:
    def test_one_step(self):
        notes = [{'start': 0.0, 'end': 1.0, 'midi': 69}]
        with tempfile.NamedTemporaryFile(suffix='.mid', delete=False) as f:
            tmp_path = f.name

        try:
            create_midi_file(notes, tmp_path)
            assert os.path.exists(tmp_path)
            loaded = pretty_midi.PrettyMIDI(tmp_path)
            assert loaded.instruments[0].notes[0].pitch == 69
        finally:
            os.unlink(tmp_path)
