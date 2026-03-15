"""Tests for the player module (gp_to_midi conversion and MidiPlayer API)."""

import os
import tempfile
import pytest
import pretty_midi
import guitarpro

from g2t.player import (
    gp_to_midi, MidiPlayer,
    MIDI_EXTENSIONS, GP_EXTENSIONS, ALL_EXTENSIONS,
)


class TestExtensionSets:
    def test_midi_extensions(self):
        assert '.mid' in MIDI_EXTENSIONS
        assert '.midi' in MIDI_EXTENSIONS

    def test_gp_extensions(self):
        for ext in ('.gp', '.gp3', '.gp4', '.gp5', '.gpx'):
            assert ext in GP_EXTENSIONS

    def test_all_extensions_union(self):
        assert ALL_EXTENSIONS == MIDI_EXTENSIONS | GP_EXTENSIONS


class TestMidiPlayerLoad:
    """Tests for MidiPlayer that do not require working audio hardware."""

    def _make_midi(self, tmp_path=None):
        """Create a minimal .mid file and return its path."""
        midi = pretty_midi.PrettyMIDI(initial_tempo=120.0)
        inst = pretty_midi.Instrument(program=0)
        inst.notes.append(pretty_midi.Note(velocity=80, pitch=60,
                                           start=0.0, end=0.5))
        midi.instruments.append(inst)
        if tmp_path is None:
            fd, tmp_path = tempfile.mkstemp(suffix='.mid')
            os.close(fd)
        midi.write(tmp_path)
        return tmp_path

    def test_load_unsupported_extension_raises(self):
        player = MidiPlayer()
        with tempfile.NamedTemporaryFile(suffix='.wav', delete=False) as f:
            tmp = f.name
        try:
            with pytest.raises((ValueError, RuntimeError)):
                player.load(tmp)
        finally:
            os.unlink(tmp)
        player.close()

    def test_play_without_load_raises(self):
        player = MidiPlayer()
        with pytest.raises(RuntimeError, match="No file loaded"):
            player.play()
        player.close()

    def test_is_playing_false_when_not_started(self):
        player = MidiPlayer()
        assert not player.is_playing()
        player.close()

    def test_is_paused_false_when_not_started(self):
        player = MidiPlayer()
        assert not player.is_paused()
        player.close()

    def test_get_position_zero_when_not_playing(self):
        player = MidiPlayer()
        assert player.get_position() == 0.0
        player.close()

    def test_stop_before_play_is_safe(self):
        player = MidiPlayer()
        player.stop()  # should not raise
        player.close()

    def test_close_twice_is_safe(self):
        player = MidiPlayer()
        player.close()
        player.close()  # second close should not raise


class TestGpToMidi:
    """Tests for Guitar Pro → MIDI conversion."""

    def _create_minimal_gp5(self):
        """Build a minimal guitarpro Song object and write a .gp5 file."""
        song = guitarpro.Song()
        song.tempo = 120

        # The default Song already has one track and one measure; just verify
        # the conversion does not crash.
        fd, path = tempfile.mkstemp(suffix='.gp5')
        os.close(fd)
        try:
            guitarpro.write(song, path)
        except Exception:
            os.unlink(path)
            pytest.skip("guitarpro.write not available in this version")
        return path

    def test_gp_to_midi_produces_file(self):
        gp_path = self._create_minimal_gp5()
        try:
            midi_path = gp_to_midi(gp_path)
            try:
                assert os.path.exists(midi_path)
                assert os.path.getsize(midi_path) > 0
                # Must be a readable MIDI file
                loaded = pretty_midi.PrettyMIDI(midi_path)
                assert isinstance(loaded, pretty_midi.PrettyMIDI)
            finally:
                if os.path.exists(midi_path):
                    os.unlink(midi_path)
        finally:
            os.unlink(gp_path)

    def test_gp_to_midi_cleanup_on_caller(self):
        """Caller must be able to delete the returned temp file."""
        gp_path = self._create_minimal_gp5()
        try:
            midi_path = gp_to_midi(gp_path)
            assert os.path.exists(midi_path)
            os.unlink(midi_path)
            assert not os.path.exists(midi_path)
        finally:
            os.unlink(gp_path)
