# BalVoice Research Models

This directory contains **experimental Balochi speech-command classifiers** for the BalVoice Robot Control project.

> **Not ready for unattended motor control.** These models are intended for offline recognition-only experiments, with Arduino motors disconnected. Recognition scores do not establish safe driving performance.

## What is included

| File | Purpose |
| --- | --- |
| `balochi_svm_final.joblib` | Experimental MFCC-based SVM classifier |
| `balochi_cnn_final.pt` | Experimental log-mel CNN checkpoint for PyTorch |
| `balochi_cnn_numpy.npz` | Exported CNN parameters for lightweight NumPy/SciPy inference on Raspberry Pi |
| `dual_recognizer.py` | Loads and compares the two research classifiers |
| `cnn_runtime.py` | Lightweight CNN inference implementation |
| `test_dual.py` | Recognition-only test for a recorded WAV file |
| `web_test.py` and `index.html` | Phone/browser recognition test interface |
| `train_dual.py`, `prep.py`, `export_numpy.py` | Research training and export utilities |
| `evaluation.json` | Measured model comparison results |
| `requirements_pi.txt` / `requirements_train.txt` | Raspberry Pi inference and model training dependencies |

The original **integrated** controller loads `../balochi_model_v02.joblib`, a separate SVM. The CNN/SVM candidates here are **not automatically connected to Arduino**.

## Commands

| Spoken command (Balochi Latin) | Meaning | Serial code |
| --- | --- | --- |
| `bosht` | Stop | `S` |
| `dema bro` | Forward | `F` |
| `poshta bro` | Backward | `B` |
| `chapen kasha bro` | Left | `L` |
| `rasten kash a bro` | Right | `R` |

A sixth class contains noise/unrelated speech.

## Training data and measured results

The research experiment used **226 unique short recordings**, after identifying three duplicate clips among 229 originals. Results were obtained using **shuffled three-fold cross-validation**:

| Model | Correct / total | Accuracy |
| --- | ---: | ---: |
| MFCC + SVM | 156 / 226 | **69.0%** |
| Log-mel + CNN | 163 / 226 | **72.1%** |

The CNN misclassified **12 of 25** noise samples. Shuffled folds may share speakers or recording environments, so these values do **not** measure independent-speaker generalization or safety. Earlier live Android tests also produced low-confidence predictions.

The CNN was the stronger *research candidate* in this comparison, not a validated driving model.

## Recognition-only testing

On a Raspberry Pi running Raspberry Pi OS:

```bash
cd research_dual_models
python3 -m venv .venv
source .venv/bin/activate
python -m pip install -r requirements_pi.txt
python test_dual.py /path/to/new-recording.wav --mode balochi
```

On Windows PowerShell, use `python -m venv .venv` followed by
`./.venv/Scripts/python.exe -m pip install -r requirements_pi.txt` and
`./.venv/Scripts/python.exe test_dual.py C:\\path\\to\\audio.wav --mode balochi`.

These tests **must not** move motors. Keep the motor power disconnected while measuring recognition quality.

## Hardware context

The full system uses an Android phone microphone, private Tailscale HTTPS connection, Raspberry Pi 5 (Python FastAPI), Arduino Mega 2560, a V1 L293D/AFMotor shield with four DC motors, a servo scanner, and an ultrasonic distance sensor.

The English voice recognizer uses a separate third-party Vosk checkpoint that is not redistributed here. See the [main project README](../README.md) for architecture, setup, wiring, and independent Arduino connection testing.

## Before considering physical movement

Collect independent new-speaker and new-phone test recordings, explicitly evaluate false command triggers on unrelated speech and noise, keep a physical motor power cutoff, verify obstacle detection and USB stability, and perform supervised tests with the wheels raised. Do not bypass rejection thresholds simply to make a command move the vehicle.

## Publishing and privacy

Original speakers' recordings and private connection credentials are **not** part of the published model package. Share audio only with speaker consent. Model serialization formats such as PyTorch `.pt` and joblib `.joblib` should only be loaded from trusted sources.

The repository owner has not selected an open-source license; do not presume permission to redistribute model weights.
