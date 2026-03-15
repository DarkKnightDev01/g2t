"""Interactive MIDI and Guitar Pro file player.

Playback is handled by pygame.mixer.music; Guitar Pro files are first
converted to a temporary MIDI file via the pyguitarpro library.
"""

import os
import tempfile
import threading
import time

import guitarpro
import pretty_midi

_pygame_available = False
_pygame_error = ""

try:
    import pygame
    _pygame_available = True
except ImportError:
    _pygame_error = "pygame is not installed (pip install pygame)."

# Ticks per quarter note used by guitarpro Duration.time values
_GP_TICKS_PER_BEAT = 960


def _pygame_init():
    """Initialise pygame mixer once; raises RuntimeError if it fails."""
    if not _pygame_available:
        raise RuntimeError(_pygame_error)
    if not pygame.mixer.get_init():
        try:
            pygame.mixer.init(frequency=44100, size=-16, channels=2, buffer=512)
            pygame.mixer.music.set_volume(1.0)
        except pygame.error as exc:
            raise RuntimeError(
                f"pygame mixer could not be initialised: {exc}\n"
                "On Linux, install timidity or fluidsynth so that pygame can "
                "synthesise MIDI (e.g. 'sudo apt-get install timidity')."
            ) from exc


def gp_to_midi(gp_path):
    """Convert a Guitar Pro file to a temporary MIDI file.

    Parses every non-muted track in the Guitar Pro song, maps fret numbers
    to MIDI pitches using the track's open-string tuning, and writes the
    result to a temporary .mid file.

    Args:
        gp_path: Path to a Guitar Pro file (.gp, .gp3, .gp4, .gp5, .gpx).

    Returns:
        Path to the temporary MIDI file.  The caller is responsible for
        deleting it when it is no longer needed.

    Raises:
        guitarpro.GPException: If the file cannot be parsed.
    """
    song = guitarpro.parse(gp_path)
    tempo = float(song.tempo) if song.tempo > 0 else 120.0
    midi = pretty_midi.PrettyMIDI(initial_tempo=tempo)

    # seconds per guitarpro tick
    tick_seconds = 60.0 / (tempo * _GP_TICKS_PER_BEAT)

    for track in song.tracks:
        if track.isMute:
            continue
        program = max(0, min(127, track.channel.instrument))
        instrument = pretty_midi.Instrument(program=program, name=track.name)

        current_time = 0.0
        # tie_end[string] tracks the end time of tied notes per string
        tie_end = {}

        for measure in track.measures:
            measure_start = current_time
            voice = measure.voices[0]
            beat_time = measure_start

            for beat in voice.beats:
                beat_secs = beat.duration.time * tick_seconds
                if beat.status == guitarpro.BeatStatus.normal:
                    for note in beat.notes:
                        if note.type == guitarpro.NoteType.tie:
                            # Extend the previous note on this string by the
                            # current beat duration to accumulate tied notes.
                            key = note.string
                            if key in tie_end:
                                tie_end[key] += beat_secs
                                # Update the last note's end time
                                if instrument.notes:
                                    last = instrument.notes[-1]
                                    last.end = last.end + beat_secs
                            continue

                        if note.type not in (guitarpro.NoteType.normal,
                                             guitarpro.NoteType.dead):
                            continue

                        string_num = note.string  # 1-indexed
                        fret = note.value
                        open_midi = track.strings[string_num - 1].value
                        midi_note = max(0, min(127, open_midi + fret))
                        velocity = max(1, min(127,
                                              beat.velocity
                                              if beat.velocity else 95))

                        # Shorten each note to 92% of its beat slot to create
                        # a small gap between consecutive notes, simulating
                        # natural articulation and preventing notes from
                        # blurring together on sustain.
                        end_time = beat_time + beat_secs * 0.92
                        n = pretty_midi.Note(
                            velocity=velocity,
                            pitch=midi_note,
                            start=beat_time,
                            end=end_time,
                        )
                        instrument.notes.append(n)
                        tie_end[note.string] = end_time

                beat_time += beat_secs

            current_time = beat_time

        if instrument.notes:
            midi.instruments.append(instrument)

    tmp_fd, tmp_path = tempfile.mkstemp(suffix='.mid')
    os.close(tmp_fd)
    midi.write(tmp_path)
    return tmp_path


# Supported file extensions
MIDI_EXTENSIONS = {'.mid', '.midi'}
GP_EXTENSIONS = {'.gp', '.gp3', '.gp4', '.gp5', '.gpx', '.gp7'}
ALL_EXTENSIONS = MIDI_EXTENSIONS | GP_EXTENSIONS


class MidiPlayer:
    """Play MIDI and Guitar Pro files interactively via pygame.mixer.music.

    Usage::

        player = MidiPlayer()
        player.load('song.mid')
        player.play()
        player.pause()
        player.resume()
        player.stop()
        player.close()

    The ``on_stop`` callback is called (on a background thread) when
    playback finishes naturally or is stopped.
    """

    def __init__(self, on_stop=None):
        """Create a new MidiPlayer.

        Args:
            on_stop: Optional callable invoked when playback ends.
        """
        self._on_stop = on_stop
        self._tmp_path = None       # temp file created for GP files
        self._loaded_path = None    # MIDI path currently loaded
        self._playing = False
        self._paused = False
        self._watch_thread = None
        self._stop_event = threading.Event()

    # ------------------------------------------------------------------ API

    def load(self, path):
        """Load a MIDI or Guitar Pro file, ready for playback.

        For Guitar Pro files a temporary MIDI conversion is created
        automatically.

        Args:
            path: Path to a .mid, .midi, .gp, .gp3, .gp4, .gp5, or .gpx
                file.

        Raises:
            ValueError: If the file extension is not recognised.
            RuntimeError: If pygame cannot be initialised.
        """
        _pygame_init()
        self.stop()
        self._cleanup_tmp()

        ext = os.path.splitext(path)[1].lower()
        if ext in GP_EXTENSIONS:
            midi_path = gp_to_midi(path)
            self._tmp_path = midi_path
        elif ext in MIDI_EXTENSIONS:
            midi_path = path
        else:
            raise ValueError(
                f"Unsupported file type '{ext}'. "
                f"Supported: {sorted(ALL_EXTENSIONS)}"
            )

        pygame.mixer.music.load(midi_path)
        self._loaded_path = midi_path
        self._playing = False
        self._paused = False

    def play(self):
        """Start or restart playback from the beginning.

        Raises:
            RuntimeError: If no file has been loaded.
        """
        if self._loaded_path is None:
            raise RuntimeError("No file loaded. Call load() first.")
        self._stop_event.clear()
        pygame.mixer.music.play()
        self._playing = True
        self._paused = False
        self._start_watch_thread()

    def pause(self):
        """Pause playback."""
        if self._playing and not self._paused:
            pygame.mixer.music.pause()
            self._paused = True

    def resume(self):
        """Resume a paused playback."""
        if self._playing and self._paused:
            pygame.mixer.music.unpause()
            self._paused = False

    def stop(self):
        """Stop playback."""
        self._stop_event.set()
        if _pygame_available and pygame.mixer.get_init():
            pygame.mixer.music.stop()
        self._playing = False
        self._paused = False

    def is_playing(self):
        """Return True if audio is currently playing (not paused)."""
        if not _pygame_available or not pygame.mixer.get_init():
            return False
        return pygame.mixer.music.get_busy() and not self._paused

    def is_paused(self):
        """Return True if playback is paused."""
        return self._paused

    def get_position(self):
        """Return current playback position in seconds (best effort).

        Returns:
            Position in seconds, or 0.0 if not playing.
        """
        if not _pygame_available or not pygame.mixer.get_init():
            return 0.0
        pos_ms = pygame.mixer.music.get_pos()
        return max(0.0, pos_ms / 1000.0)

    def set_volume(self, volume):
        """Set playback volume.

        Args:
            volume: Float in [0.0, 1.0].
        """
        if _pygame_available and pygame.mixer.get_init():
            pygame.mixer.music.set_volume(max(0.0, min(1.0, volume)))

    def close(self):
        """Stop playback and release resources."""
        self.stop()
        self._cleanup_tmp()
        self._loaded_path = None

    # -------------------------------------------------------------- Internals

    def _start_watch_thread(self):
        """Start a background thread that fires on_stop when music ends."""
        if self._watch_thread and self._watch_thread.is_alive():
            return
        self._watch_thread = threading.Thread(
            target=self._watch_playback, daemon=True
        )
        self._watch_thread.start()

    def _watch_playback(self):
        """Poll pygame until playback finishes, then call on_stop."""
        while not self._stop_event.is_set():
            time.sleep(0.1)
            if not (pygame.mixer.get_init() and pygame.mixer.music.get_busy()):
                break
        if not self._stop_event.is_set():
            self._playing = False
            self._paused = False
            if callable(self._on_stop):
                self._on_stop()

    def _cleanup_tmp(self):
        if self._tmp_path and os.path.exists(self._tmp_path):
            try:
                os.unlink(self._tmp_path)
            except OSError:
                pass
        self._tmp_path = None
