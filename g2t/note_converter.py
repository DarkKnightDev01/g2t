"""Convert frequencies to musical note names and MIDI numbers."""

import math

# Standard tuning reference
A4_FREQ = 440.0
A4_MIDI = 69

NOTE_NAMES = ['C', 'C#', 'D', 'D#', 'E', 'F',
              'F#', 'G', 'G#', 'A', 'A#', 'B']

FLAT_TO_SHARP = {
    'Db': 'C#', 'Eb': 'D#', 'Fb': 'E', 'Gb': 'F#',
    'Ab': 'G#', 'Bb': 'A#', 'Cb': 'B',
}


def freq_to_midi(frequency):
    """Convert frequency in Hz to the nearest MIDI note number.

    Args:
        frequency: Frequency in Hz.

    Returns:
        MIDI note number (integer).
    """
    if frequency <= 0:
        raise ValueError("Frequency must be positive")
    midi_float = 12 * math.log2(frequency / A4_FREQ) + A4_MIDI
    return round(midi_float)


def freq_to_midi_float(frequency):
    """Convert frequency to a fractional MIDI note number (for cents).

    Args:
        frequency: Frequency in Hz.

    Returns:
        MIDI note number as float.
    """
    if frequency <= 0:
        raise ValueError("Frequency must be positive")
    return 12 * math.log2(frequency / A4_FREQ) + A4_MIDI


def midi_to_freq(midi_note):
    """Convert MIDI note number to frequency in Hz.

    Args:
        midi_note: MIDI note number.

    Returns:
        Frequency in Hz.
    """
    return A4_FREQ * (2 ** ((midi_note - A4_MIDI) / 12))


def midi_to_note_name(midi_note):
    """Convert MIDI note number to note name with octave (e.g. 'C4').

    Args:
        midi_note: MIDI note number (0-127).

    Returns:
        Note name string like 'A4', 'C#3', etc.
    """
    octave = (midi_note // 12) - 1
    note_index = midi_note % 12
    return f"{NOTE_NAMES[note_index]}{octave}"


def freq_to_note_name(frequency):
    """Convert frequency directly to note name.

    Args:
        frequency: Frequency in Hz.

    Returns:
        Note name string.
    """
    midi = freq_to_midi(frequency)
    return midi_to_note_name(midi)


def note_name_to_midi(note_name):
    """Convert note name (e.g. 'C4', 'F#3') to MIDI number.

    Args:
        note_name: Note name with octave.

    Returns:
        MIDI note number.
    """
    # Parse note name
    name = note_name[:-1] if note_name[-1].isdigit() else note_name
    octave_str = note_name[-1] if note_name[-1].isdigit() else None

    # Handle flats by converting to sharps
    if name in FLAT_TO_SHARP:
        name = FLAT_TO_SHARP[name]

    if name not in NOTE_NAMES:
        raise ValueError(f"Unknown note name: {name}")

    note_index = NOTE_NAMES.index(name)
    octave = int(octave_str) if octave_str is not None else 4
    return (octave + 1) * 12 + note_index


def cents_off(frequency, midi_note):
    """Calculate how many cents a frequency is off from a MIDI note.

    Args:
        frequency: Actual frequency in Hz.
        midi_note: Target MIDI note number.

    Returns:
        Cents deviation (positive = sharp, negative = flat).
    """
    target_freq = midi_to_freq(midi_note)
    if target_freq <= 0 or frequency <= 0:
        return 0.0
    return 1200 * math.log2(frequency / target_freq)


def quantize_notes(detected_notes):
    """Quantize detected note dicts to nearest semitone.

    Adds 'midi', 'note_name', and 'cents_off' fields to each note.

    Args:
        detected_notes: List of dicts with 'frequency' key.

    Returns:
        Same list with added 'midi', 'note_name', 'cents_off' keys.
    """
    for note in detected_notes:
        freq = note['frequency']
        midi = freq_to_midi(freq)
        note['midi'] = midi
        note['note_name'] = midi_to_note_name(midi)
        note['cents_off'] = cents_off(freq, midi)
    return detected_notes
