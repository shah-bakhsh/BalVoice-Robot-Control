"""MFCC temporal features used by the Balochi small-vocabulary model v0.2.

Input audio is expected to be 16000 Hz mono float32 from balochi_features.
"""
from __future__ import annotations

import numpy as np
from scipy.signal import stft
from scipy.fft import dct
from scipy.ndimage import uniform_filter1d
from balochi_features import _MEL_FILTERS, SAMPLE_RATE


def extract_v02_features(raw_audio: np.ndarray) -> np.ndarray:
    x = np.asarray(raw_audio, dtype=np.float32)
    if x.ndim != 1 or not x.size:
        raise ValueError('Audio must be nonempty mono audio')
    power = uniform_filter1d(x * x, size=320, mode='constant')
    rms = np.sqrt(np.maximum(power, 0))
    threshold = max(0.008, float(rms.max()) * 0.10)
    voiced = np.flatnonzero(rms > threshold)
    if len(voiced) >= 100:
        x = x[max(0, int(voiced[0])-2400):min(len(x), int(voiced[-1])+2400)]
    if len(x) < 1600:
        x = np.zeros(SAMPLE_RATE, dtype=np.float32)
    x = x - np.mean(x)
    x = x / max(float(np.max(np.abs(x))), 1e-6)
    _, _, spectrum = stft(x, fs=SAMPLE_RATE, nperseg=512, noverlap=352, boundary='zeros')
    logmel = np.log(np.maximum(_MEL_FILTERS @ np.maximum(np.abs(spectrum)**2, 1e-12), 1e-10))
    mfcc = dct(logmel, type=2, axis=0, norm='ortho')[1:20]
    n = mfcc.shape[1]
    segments = []
    for j in range(8):
        a, b = int(n*j/8), max(int(n*j/8)+1, int(n*(j+1)/8))
        segments.append(mfcc[:, a:b].mean(axis=1))
    return np.concatenate([mfcc.mean(axis=1), mfcc.std(axis=1), np.concatenate(segments)]).astype(np.float32)
