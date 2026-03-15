"""Pitch detection using librosa's pYIN algorithm for high accuracy."""

import librosa
import numpy as np


def detect_pitches(y, sr, fmin=50.0, fmax=2000.0, frame_length=2048,
                   hop_length=512):
    """Detect pitches in an audio signal using pYIN.

    pYIN is a probabilistic variant of YIN, well suited for monophonic
    pitch tracking of musical instruments and vocals.

    Args:
        y: Audio waveform.
        sr: Sample rate.
        fmin: Minimum expected frequency in Hz.
        fmax: Maximum expected frequency in Hz.
        frame_length: Length of analysis frames in samples.
        hop_length: Hop between frames in samples.

    Returns:
        Tuple of (f0 array in Hz with NaN for unvoiced, voiced_flag,
                  voiced_probabilities).
    """
    f0, voiced_flag, voiced_probs = librosa.pyin(
        y, fmin=fmin, fmax=fmax,
        frame_length=frame_length, hop_length=hop_length, sr=sr
    )
    return f0, voiced_flag, voiced_probs


def detect_onsets(y, sr, hop_length=512, backtrack=True):
    """Detect note onsets in the audio signal.

    Args:
        y: Audio waveform.
        sr: Sample rate.
        hop_length: Hop between frames.
        backtrack: If True, move onsets back to nearest preceding minimum.

    Returns:
        Array of onset times in seconds.
    """
    onset_frames = librosa.onset.onset_detect(
        y=y, sr=sr, hop_length=hop_length, backtrack=backtrack,
        units='frames'
    )
    onset_times = librosa.frames_to_time(
        onset_frames, sr=sr, hop_length=hop_length
    )
    return onset_times


def estimate_tempo(y, sr, hop_length=512):
    """Estimate the tempo (BPM) of the audio.

    Args:
        y: Audio waveform.
        sr: Sample rate.
        hop_length: Hop between frames.

    Returns:
        Estimated tempo in BPM.
    """
    tempo, _ = librosa.beat.beat_track(y=y, sr=sr, hop_length=hop_length)
    if hasattr(tempo, '__len__'):
        return float(tempo[0])
    return float(tempo)


def segment_notes(f0, voiced_flag, onset_times, sr, hop_length=512):
    """Segment continuous pitch data into discrete notes using onsets.

    Args:
        f0: Array of fundamental frequencies (Hz), NaN for unvoiced.
        voiced_flag: Boolean array indicating voiced frames.
        onset_times: Array of onset times in seconds.
        sr: Sample rate.
        hop_length: Hop length used in pitch detection.

    Returns:
        List of dicts with keys: 'start', 'end', 'frequency', 'confidence'.
        Times are in seconds.
    """
    times = librosa.frames_to_time(
        np.arange(len(f0)), sr=sr, hop_length=hop_length
    )
    total_duration = times[-1] if len(times) > 0 else 0.0

    if len(onset_times) == 0:
        return []

    # Build segment boundaries from onsets
    boundaries = list(onset_times)
    boundaries.append(total_duration)

    notes = []
    for i in range(len(boundaries) - 1):
        seg_start = boundaries[i]
        seg_end = boundaries[i + 1]

        # Get frames in this segment
        mask = (times >= seg_start) & (times < seg_end) & voiced_flag
        seg_f0 = f0[mask]

        if len(seg_f0) == 0:
            continue

        # Use the median frequency for robustness
        freq = float(np.nanmedian(seg_f0))
        if np.isnan(freq) or freq <= 0:
            continue

        # Confidence based on fraction of voiced frames
        all_in_seg = (times >= seg_start) & (times < seg_end)
        confidence = float(np.sum(mask) / max(np.sum(all_in_seg), 1))

        notes.append({
            'start': float(seg_start),
            'end': float(seg_end),
            'frequency': freq,
            'confidence': confidence,
        })

    return notes
