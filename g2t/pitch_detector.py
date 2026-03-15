"""Pitch detection using librosa's pYIN algorithm for high accuracy."""

import librosa
import numpy as np
from scipy.signal import medfilt


def separate_harmonic(y):
    """Separate the harmonic component of an audio signal.

    Harmonic-percussive source separation (HPSS) isolates the sustained
    tonal content, greatly reducing false detections from transients and
    improving pitch accuracy for instruments like guitar and piano.

    Args:
        y: Audio waveform.

    Returns:
        Harmonic component of the waveform.
    """
    y_harmonic, _ = librosa.effects.hpss(y)
    return y_harmonic


def detect_pitches(y, sr, fmin=50.0, fmax=2000.0, frame_length=2048,
                   hop_length=512):
    """Detect pitches in an audio signal using pYIN.

    pYIN is a probabilistic variant of YIN, well suited for monophonic
    pitch tracking of musical instruments and vocals.

    A median filter is applied to the raw f0 output to suppress brief
    octave errors that pYIN can introduce between adjacent frames.

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

    # Apply a median filter over f0 to smooth out brief octave jumps.
    # NaN values (unvoiced) are temporarily replaced with 0 for filtering,
    # then restored.
    was_nan = np.isnan(f0)
    f0 = medfilt(np.where(was_nan, 0.0, f0), kernel_size=5)
    f0[was_nan] = np.nan

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


def segment_notes(f0, voiced_flag, onset_times, sr, hop_length=512,
                  voiced_probs=None, min_voiced_ratio=0.3):
    """Segment continuous pitch data into discrete notes using onsets.

    Only segments that contain a sufficient fraction of high-confidence
    voiced frames are kept, which removes spurious detections caused by
    noise or silence between notes.

    Args:
        f0: Array of fundamental frequencies (Hz), NaN for unvoiced.
        voiced_flag: Boolean array indicating voiced frames.
        onset_times: Array of onset times in seconds.
        sr: Sample rate.
        hop_length: Hop length used in pitch detection.
        voiced_probs: Optional array of voicing probabilities from pYIN.
            When provided, frames with probability < 0.5 are excluded.
        min_voiced_ratio: Minimum fraction of voiced frames required to
            accept a segment as a note (default 0.3).

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

    # Build a reliable voiced mask combining voiced_flag and, when available,
    # the probability threshold from pYIN.
    if voiced_probs is not None:
        voiced_mask = voiced_flag & (voiced_probs >= 0.5)
    else:
        voiced_mask = voiced_flag

    # Build segment boundaries from onsets
    boundaries = list(onset_times)
    boundaries.append(total_duration)

    notes = []
    for i in range(len(boundaries) - 1):
        seg_start = boundaries[i]
        seg_end = boundaries[i + 1]

        all_in_seg = (times >= seg_start) & (times < seg_end)
        mask = all_in_seg & voiced_mask
        seg_f0 = f0[mask]

        if len(seg_f0) == 0:
            continue

        # Require a minimum voiced fraction to avoid spurious notes
        voiced_ratio = float(np.sum(mask) / max(np.sum(all_in_seg), 1))
        if voiced_ratio < min_voiced_ratio:
            continue

        # Use the median frequency for robustness against remaining outliers
        freq = float(np.nanmedian(seg_f0))
        if np.isnan(freq) or freq <= 0:
            continue

        notes.append({
            'start': float(seg_start),
            'end': float(seg_end),
            'frequency': freq,
            'confidence': voiced_ratio,
        })

    return notes
