"""Sheet music generation using music21 (MusicXML output)."""

import music21


def notes_to_stream(notes, tempo=120.0):
    """Convert detected notes to a music21 Stream.

    Quantizes note durations to standard musical values for clean notation.

    Args:
        notes: List of note dicts with 'start', 'end', 'midi', 'note_name'.
        tempo: Tempo in BPM.

    Returns:
        music21.stream.Score object.
    """
    score = music21.stream.Score()
    part = music21.stream.Part()

    # Set tempo
    mm = music21.tempo.MetronomeMark(number=tempo)
    part.insert(0, mm)

    # Set time signature
    ts = music21.meter.TimeSignature('4/4')
    part.insert(0, ts)

    beat_duration = 60.0 / tempo  # seconds per beat

    for note_data in notes:
        start = note_data['start']
        end = note_data['end']
        duration_seconds = end - start
        duration_beats = duration_seconds / beat_duration

        # Quantize to nearest standard duration
        duration_ql = _quantize_duration(duration_beats)

        # Create note
        midi_num = note_data['midi']
        n = music21.note.Note(midi=midi_num)
        n.quarterLength = duration_ql

        # Insert at the right offset in beats
        offset_beats = start / beat_duration
        part.insert(offset_beats, n)

    score.insert(0, part)
    return score


def _quantize_duration(duration_beats):
    """Quantize a beat duration to the nearest standard musical duration.

    Standard values: 4 (whole), 3 (dotted half), 2 (half), 1.5 (dotted quarter),
    1 (quarter), 0.75 (dotted eighth), 0.5 (eighth), 0.25 (sixteenth).

    Args:
        duration_beats: Duration in quarter-note beats.

    Returns:
        Quantized duration in quarter lengths.
    """
    standard = [4.0, 3.0, 2.0, 1.5, 1.0, 0.75, 0.5, 0.25]
    best = min(standard, key=lambda s: abs(s - duration_beats))
    return best


def save_musicxml(score, output_path):
    """Save a music21 Score as MusicXML.

    Args:
        score: music21.stream.Score object.
        output_path: Path for the output file (should end in .xml or .musicxml).
    """
    score.write('musicxml', fp=output_path)


def save_midi_via_music21(score, output_path):
    """Save a music21 Score as MIDI.

    Args:
        score: music21.stream.Score object.
        output_path: Path for the output MIDI file.
    """
    score.write('midi', fp=output_path)


def create_sheet_music(notes, output_path, tempo=120.0):
    """One-step: convert notes to sheet music and save as MusicXML.

    Args:
        notes: List of note dicts.
        output_path: Path for the output MusicXML file.
        tempo: Tempo in BPM.
    """
    score = notes_to_stream(notes, tempo)
    save_musicxml(score, output_path)
