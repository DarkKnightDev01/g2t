# g2t

A tool to convert audio (stem-separated instrumental parts or vocals) into accurate guitar tabs, MIDI files, and sheet music — all through a graphical interface.

## Features

- **Pitch detection** — uses the pYIN algorithm (via librosa) for highly accurate monophonic pitch tracking
- **Onset detection** — identifies individual note boundaries in the audio
- **Automatic tempo estimation** — detects BPM from the audio, or set manually
- **Guitar tab generation** — maps detected notes to optimal fretboard positions and outputs ASCII tablature
- **MIDI export** — creates standard MIDI files with correct instrument, timing, and velocity
- **Sheet music export** — generates MusicXML files that can be opened in notation software (MuseScore, Finale, etc.)
- **GUI** — Tkinter-based interface for loading audio, analyzing, and exporting results

## Supported Audio Formats

WAV, MP3, FLAC, OGG, AAC, M4A (anything supported by librosa / soundfile).

## Installation

```bash
pip install -r requirements.txt
```

### Requirements

- Python 3.9+
- librosa, numpy, scipy, soundfile
- pretty_midi
- music21
- matplotlib
- tkinter (included with most Python installations)

## Usage

Launch the GUI:

```bash
python main.py
```

1. Click **Browse…** to select an audio file (ideally a stem-separated track — guitar, piano, or vocals)
2. Choose the **Instrument** type (Guitar, Piano, or Vocals/Other)
3. Set the **Tempo** or leave as "auto" to detect automatically
4. Click **▶ Analyze Audio**
5. View the results in the tabs: Guitar Tab, Detected Notes, Info
6. **Export** as guitar tab (.txt), MIDI (.mid), or sheet music (.musicxml)

## Running Tests

```bash
pip install pytest
python -m pytest tests/ -v
```

## Project Structure

```
g2t/
├── g2t/
│   ├── __init__.py          # Package init
│   ├── audio_loader.py      # Load & preprocess audio files
│   ├── pitch_detector.py    # pYIN pitch detection & note segmentation
│   ├── note_converter.py    # Frequency ↔ MIDI ↔ note name conversion
│   ├── guitar_tab.py        # Guitar tablature generation
│   ├── midi_generator.py    # MIDI file creation
│   ├── sheet_music.py       # MusicXML sheet music generation
│   └── gui.py               # Tkinter GUI
├── tests/                   # Unit tests
├── main.py                  # Entry point
├── requirements.txt         # Python dependencies
└── README.md
```
