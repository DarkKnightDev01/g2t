"""Audio file loading and preprocessing."""

import librosa
import numpy as np


def load_audio(file_path, sr=22050, mono=True):
    """Load an audio file and return the waveform and sample rate.

    Supports WAV, MP3, FLAC, OGG, and other formats via soundfile/audioread.

    Args:
        file_path: Path to the audio file.
        sr: Target sample rate. Use None to preserve original.
        mono: If True, convert to mono.

    Returns:
        Tuple of (waveform as numpy array, sample rate).
    """
    y, sr_out = librosa.load(file_path, sr=sr, mono=mono)
    return y, sr_out


def normalize_audio(y):
    """Normalize audio waveform to [-1, 1] range.

    Args:
        y: Audio waveform as numpy array.

    Returns:
        Normalized waveform.
    """
    peak = np.max(np.abs(y))
    if peak > 0:
        return y / peak
    return y


def trim_silence(y, sr, top_db=30):
    """Trim leading and trailing silence from audio.

    Args:
        y: Audio waveform.
        sr: Sample rate.
        top_db: Threshold in dB below peak to consider as silence.

    Returns:
        Trimmed waveform.
    """
    y_trimmed, _ = librosa.effects.trim(y, top_db=top_db)
    return y_trimmed
