"""MIDI file generation from detected notes."""

import pretty_midi


def notes_to_midi(notes, instrument_name='Acoustic Grand Piano',
                  tempo=120.0):
    """Convert detected notes to a PrettyMIDI object.

    Args:
        notes: List of note dicts with 'start', 'end', 'midi' keys.
        instrument_name: General MIDI instrument name.
        tempo: Tempo in BPM.

    Returns:
        PrettyMIDI object.
    """
    midi = pretty_midi.PrettyMIDI(initial_tempo=tempo)
    program = pretty_midi.instrument_name_to_program(instrument_name)
    instrument = pretty_midi.Instrument(program=program)

    for note_data in notes:
        midi_note = note_data['midi']
        start = note_data['start']
        end = note_data['end']
        velocity = int(note_data.get('velocity', 100))

        # Clamp MIDI note to valid range
        midi_note = max(0, min(127, midi_note))
        velocity = max(1, min(127, velocity))

        # Ensure positive duration
        if end <= start:
            end = start + 0.1

        note = pretty_midi.Note(
            velocity=velocity,
            pitch=midi_note,
            start=start,
            end=end,
        )
        instrument.notes.append(note)

    midi.instruments.append(instrument)
    return midi


def save_midi(midi_obj, output_path):
    """Write a PrettyMIDI object to a .mid file.

    Args:
        midi_obj: PrettyMIDI object.
        output_path: Path for the output MIDI file.
    """
    midi_obj.write(output_path)


def create_midi_file(notes, output_path, instrument_name='Acoustic Grand Piano',
                     tempo=120.0):
    """One-step: convert notes to MIDI and save.

    Args:
        notes: List of note dicts.
        output_path: Path for the output MIDI file.
        instrument_name: GM instrument name.
        tempo: Tempo in BPM.
    """
    midi_obj = notes_to_midi(notes, instrument_name, tempo)
    save_midi(midi_obj, output_path)
