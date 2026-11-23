"""Shared audio decoding and MFCC features for the experimental Balochi robot model.

Keep this code identical for training and inference.
"""
from __future__ import annotations

import io
import subprocess
from math import gcd
from pathlib import Path

import numpy as np
import soundfile as sf
from scipy.fft import dct
from scipy.ndimage import uniform_filter1d
from scipy.signal import resample_poly, stft

SAMPLE_RATE = 16000
FFT_SIZE = 512
HOP = 160
MEL_BANDS = 40
MFCC_COEFFS = 20


def _mel(hz):
    return 2595.0 * np.log10(1.0 + hz / 700.0)


def _hz(mel):
    return 700.0 * (10.0 ** (mel / 2595.0) - 1.0)


_grid = _hz(np.linspace(_mel(40.0), _mel(SAMPLE_RATE / 2), MEL_BANDS + 2))
_freqs = np.linspace(0, SAMPLE_RATE / 2, FFT_SIZE // 2 + 1)
_MEL_FILTERS = np.zeros((MEL_BANDS, len(_freqs)))
for _i in range(MEL_BANDS):
    _lower, _center, _upper = _grid[_i : _i + 3]
    _MEL_FILTERS[_i] = np.maximum(
        0.0,
        np.minimum(
            (_freqs - _lower) / (_center - _lower),
            (_upper - _freqs) / (_upper - _center),
        ),
    )
_MEL_FILTERS *= (2.0 / (_grid[2:] - _grid[:-2]))[:, None]


def decode_audio_bytes(data: bytes) -> np.ndarray:
    """Decode WAV/OGG with SoundFile; FFmpeg fallback handles browser WebM etc."""
    if not data:
        raise ValueError("Empty audio file")
    try:
        audio, rate = sf.read(io.BytesIO(data), dtype="float32", always_2d=False)
        if audio.ndim == 2:
            audio = audio.mean(axis=1)
        if rate != SAMPLE_RATE:
            divisor = gcd(SAMPLE_RATE, int(rate))
            audio = resample_poly(audio, SAMPLE_RATE // divisor, int(rate) // divisor)
        return np.asarray(audio, dtype=np.float32)
    except (RuntimeError, OSError, ValueError):
        result = subprocess.run(
            [
                "ffmpeg", "-nostdin", "-v", "error", "-i", "pipe:0",
                "-ar", str(SAMPLE_RATE), "-ac", "1", "-f", "f32le", "pipe:1"
            ],
            input=data,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            check=False,
            timeout=20,
        )
        if result.returncode != 0 or not result.stdout:
            raise ValueError("Could not decode audio (install ffmpeg if using WebM)")
        return np.frombuffer(result.stdout, dtype="<f4").copy()


def decode_audio_file(path: str | Path) -> np.ndarray:
    return decode_audio_bytes(Path(path).read_bytes())


def extract_features(raw_audio: np.ndarray) -> np.ndarray:
    """Return 114-dimensional MFCC+temporal SVM features; exact v0.1 pipeline."""
    audio = np.asarray(raw_audio, dtype=np.float32)
    if audio.ndim != 1:
        raise ValueError("Expected mono audio")
    if audio.size == 0:
        raise ValueError("Empty decoded audio")
    power = uniform_filter1d(audio * audio, size=320, mode="constant")
    rms = np.sqrt(np.maximum(power, 0.0))
    threshold = max(0.008, float(np.max(rms)) * 0.10)
    voiced = np.flatnonzero(rms > threshold)
    if len(voiced) >= 100:
        audio = audio[max(0, int(voiced[0]) - 2400) : min(len(audio), int(voiced[-1]) + 2400)]
    if len(audio) < SAMPLE_RATE // 10:
        audio = np.zeros(SAMPLE_RATE, dtype=np.float32)
    audio = audio - np.mean(audio)
    audio = audio / max(float(np.max(np.abs(audio))), 1e-6)
    _, _, spectrum = stft(
        audio, fs=SAMPLE_RATE, nperseg=FFT_SIZE,
        noverlap=FFT_SIZE - HOP, boundary="zeros"
    )
    spectral_power = np.maximum(np.abs(spectrum) ** 2, 1e-12)
    logmel = np.log(np.maximum(_MEL_FILTERS @ spectral_power, 1e-10))
    mfcc = dct(logmel, type=2, axis=0, norm="ortho")[:MFCC_COEFFS][1:]
    nframes = mfcc.shape[1]
    boundaries = [
        (0, max(1, nframes // 4)),
        (nframes // 4, max(1, nframes // 2)),
        (nframes // 2, max(1, nframes * 3 // 4)),
        (nframes * 3 // 4, nframes),
    ]
    quartiles = np.stack([mfcc[:, a:b].mean(axis=1) for a, b in boundaries])
    result = np.concatenate([mfcc.mean(axis=1), mfcc.std(axis=1), quartiles.flatten()])
    return result.astype(np.float32)


LABEL_TO_COMMAND = {
    "bosht": "S",
    "dema bro": "F",
    "poshta bro": "B",
    "chapen kasha bro": "L",
    "rasten kash a bro": "R",
    "noise": None,
}
