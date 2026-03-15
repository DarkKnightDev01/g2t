"""Guitar tab generation from detected notes.

Maps MIDI notes to guitar fretboard positions and generates ASCII tabs.
"""

# Standard guitar tuning (low to high): E2, A2, D3, G3, B3, E4
STANDARD_TUNING = [40, 45, 50, 55, 59, 64]
STRING_NAMES = ['E', 'A', 'D', 'G', 'B', 'e']
MAX_FRET = 24


def get_fret_positions(midi_note, tuning=None):
    """Get all possible fret positions for a MIDI note on a guitar.

    Args:
        midi_note: MIDI note number.
        tuning: List of MIDI note numbers for open strings (low to high).

    Returns:
        List of (string_index, fret) tuples where the note can be played.
    """
    if tuning is None:
        tuning = STANDARD_TUNING

    positions = []
    for string_idx, open_note in enumerate(tuning):
        fret = midi_note - open_note
        if 0 <= fret <= MAX_FRET:
            positions.append((string_idx, fret))
    return positions


def optimize_positions(notes, tuning=None):
    """Choose optimal fret positions minimizing hand movement.

    Uses a greedy algorithm that prefers positions close to the current
    hand position and avoids large jumps across the fretboard.

    Args:
        notes: List of note dicts with 'midi' key.
        tuning: Guitar tuning as MIDI numbers.

    Returns:
        List of (string_index, fret) tuples, one per note.
    """
    if tuning is None:
        tuning = STANDARD_TUNING

    if not notes:
        return []

    positions = []
    current_fret = 0  # Track average hand position

    for note in notes:
        candidates = get_fret_positions(note['midi'], tuning)
        if not candidates:
            # Note out of guitar range - pick closest possible
            positions.append(None)
            continue

        # Score candidates: prefer small distance from current position
        # and prefer middle strings for ergonomics
        best = None
        best_score = float('inf')
        for string_idx, fret in candidates:
            fret_dist = abs(fret - current_fret)
            # Small penalty for extreme strings (0=low E, 5=high e)
            string_penalty = abs(string_idx - 2.5) * 0.5
            score = fret_dist + string_penalty
            if score < best_score:
                best_score = score
                best = (string_idx, fret)

        positions.append(best)
        if best is not None:
            # Smooth hand position update
            current_fret = best[1]

    return positions


def generate_tab_string(notes, positions, tuning=None, measures_per_line=4,
                        tempo=120.0):
    """Generate ASCII guitar tablature.

    Args:
        notes: List of note dicts with 'start', 'end', 'midi' keys.
        positions: List of (string_index, fret) or None per note.
        tuning: Guitar tuning.
        measures_per_line: How many measures to display per tab line.
        tempo: Tempo in BPM for timing calculation.

    Returns:
        ASCII tab string.
    """
    if tuning is None:
        tuning = STANDARD_TUNING

    num_strings = len(tuning)
    string_labels = STRING_NAMES[:num_strings]

    if not notes or not positions:
        lines = []
        for i in range(num_strings - 1, -1, -1):
            lines.append(f"{string_labels[i]}|{'-' * 40}|")
        return '\n'.join(lines)

    # Calculate total duration and allocate characters
    total_duration = max(n['end'] for n in notes) if notes else 0
    beat_duration = 60.0 / tempo
    total_beats = total_duration / beat_duration if beat_duration > 0 else 0
    chars_per_beat = 4
    total_chars = max(int(total_beats * chars_per_beat), 1)

    # Build tab grid
    grid = [['-'] * total_chars for _ in range(num_strings)]

    for note, pos in zip(notes, positions):
        if pos is None:
            continue
        string_idx, fret = pos
        char_pos = int(note['start'] / beat_duration * chars_per_beat)
        char_pos = min(char_pos, total_chars - 1)

        fret_str = str(fret)
        for j, ch in enumerate(fret_str):
            idx = char_pos + j
            if idx < total_chars:
                grid[string_idx][idx] = ch

    # Split into lines of manageable width
    beats_per_measure = 4
    chars_per_measure = beats_per_measure * chars_per_beat
    chars_per_line = chars_per_measure * measures_per_line

    tab_lines = []
    for start in range(0, total_chars, chars_per_line):
        end = min(start + chars_per_line, total_chars)
        for i in range(num_strings - 1, -1, -1):
            label = string_labels[i]
            content = ''.join(grid[i][start:end])
            tab_lines.append(f"{label}|{content}|")
        tab_lines.append('')  # Blank line between sections

    return '\n'.join(tab_lines)


def notes_to_tab(notes, tuning=None, tempo=120.0):
    """Full pipeline: convert note list to guitar tab string.

    Args:
        notes: List of note dicts with 'start', 'end', 'midi' keys.
        tuning: Guitar tuning as MIDI note numbers.
        tempo: Tempo in BPM.

    Returns:
        ASCII guitar tab string.
    """
    positions = optimize_positions(notes, tuning)
    return generate_tab_string(notes, positions, tuning, tempo=tempo)
