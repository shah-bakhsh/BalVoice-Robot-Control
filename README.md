# BalVoice Robot Control

### Balochi + English voice control for a Raspberry Pi 5 and Arduino Mega 2560 robot

**Research prototype · Offline speech recognition · Android phone microphone · Arduino motor shield · Ultrasonic obstacle sensing**

[![Research prototype](https://img.shields.io/badge/status-experimental-orange)](docs/SAFETY.md)
[![Raspberry Pi 5](https://img.shields.io/badge/platform-Raspberry%20Pi%205-c51a4a)](docs/ARCHITECTURE.md)
[![Arduino Mega](https://img.shields.io/badge/controller-Arduino%20Mega%202560-00878f)](Arduino/Robot_Car_Bilingual_Safe/Robot_Car_Bilingual_Safe.ino)
[![Balochi](https://img.shields.io/badge/voice-Balochi%20%2B%20English-blue)](research_dual_models/README.md)

> **Safety status:** The trained Balochi classifiers are **not reliable enough to control an unattended moving robot**. Keep the wheels raised and motor power disconnected for recognition-only testing. Motor control is disabled by default, and a physical motor-power cutoff is required during supervised hardware experiments. See [Safety](docs/SAFETY.md).

**Project links:** [GitHub repository](https://github.com/shah-bakhsh/BalVoice-Robot-Control) · [Hugging Face model repository](https://huggingface.co/shah-bakhsh/BalVoice-Robot-Control) (verify uploaded weights separately).

## Overview

BalVoice lets an Android phone supply microphone audio to a Raspberry Pi, which uses two *separate* speech-recognition systems:

- **English:** an external offline **Vosk** model, `vosk-model-small-en-us-0.15` (not shipped in this repository).
- **Balochi (integrated controller):** a small, custom **MFCC + SVM** keyword classifier stored in `balochi_model_v02.joblib`.

Research experiments in `research_dual_models/` also include an **SVM comparison model and a small log-mel CNN** for Raspberry Pi recognition-only tests. **The CNN is not automatically connected to the motor controller.**

```text
Android Chrome (microphone)
           │
           ▼  Private Tailscale HTTPS
    Raspberry Pi 5
    FastAPI (app.py)
           │
           ├─ English ──► Vosk
           └─ Balochi ──► experimental SVM
                         │
                         ▼
               recognition + safety checks
                         │
               [opt-in hardware tests only]
                         ▼  USB serial: F/B/L/R/S
                 Arduino Mega 2560
                         │
          ┌──────────────┴──────────────┐
          ▼                             ▼
      AFMotor V1 shield           Ultrasonic + servo
      Four DC motors              Obstacle sensing
```

## Supported voice commands

| Meaning | English | Balochi (Roman script) | Serial code |
|---|---|---|---|
| Stop | Stop / Halt | **Bosht** | `S` |
| Forward | Forward | **Dema bro** | `F` |
| Backward | Backward | **Poshta bro** | `B` |
| Turn left | Left / Turn left | **Chapen kasha bro** | `L` |
| Turn right | Right / Turn right | **Rasten kash a bro** | `R` |

Arduino diagnostics additionally support `?` (firmware handshake) and `D` (distance). `A` enters autonomous obstacle-avoidance mode, and `V` enters stopped voice mode; **the Raspberry Pi motor bridge does not send `A` automatically**. The board boots with motors stopped.

## What's included

```text
BalVoice-Robot-Control/
├── app.py, index.html                 # FastAPI server and Android-friendly web page
├── recognizer.py                     # English Vosk + original Balochi SVM routing
├── balochi_features.py, balochi_v02.py
├── balochi_model_v02.joblib          # Original integrated Balochi classifier
├── motor_link.py, test_arduino.py    # Guarded USB serial bridge and diagnostics
├── test_audio.py, train_balochi.py   # Original audio testing and training utilities
├── check_install.py, start_robot.sh
├── requirements.txt, .env.example, .gitignore
├── Arduino/Robot_Car_Bilingual_Safe/
│   └── Robot_Car_Bilingual_Safe.ino   # Arduino firmware (Arduino Mega + AFMotor V1)
├── research_dual_models/
│   ├── balochi_cnn_final.pt          # Experimental PyTorch CNN checkpoint
│   ├── balochi_cnn_numpy.npz         # CNN weights for lightweight Pi inference
│   ├── balochi_svm_final.joblib      # Experimental SVM checkpoint
│   ├── dual_recognizer.py, cnn_runtime.py, test_dual.py
│   ├── train_dual.py, prep.py, web_test.py, index.html
│   ├── evaluation.json, README.md   # Benchmark results and limitations
│   └── requirements_pi.txt, requirements_train.txt
├── docs/
│   ├── ARCHITECTURE.md               # Hardware/software design
│   ├── SAFETY.md                     # Safe testing rules
│   ├── TROUBLESHOOTING.md            # Common phone, USB and model issues
│   ├── VOICE_SERVER_V06.md           # Historical integration instructions
│   └── V061_PHONE_SESSION_FIX.txt
├── tests/test_release_integrity.py
└── MODEL_SHA256SUMS                  # Checkpoints' SHA-256 hashes
```

## Hardware requirements

| Item | Role |
|---|---|
| Raspberry Pi 5 + appropriate power supply | Speech processing, FastAPI, Tailscale |
| Arduino Mega 2560 | Motor timing, obstacle detection and safety stops |
| Adafruit / L293D **Motor Shield V1** (AFMotor library) | Controls 4 DC motors (M1–M4) |
| 4-wheel robot chassis and motors | Robot movement |
| Ultrasonic sensor | Obstacle detection: `TRIG=24`, `ECHO=22` |
| Servo scanner | Sensor orientation: `SERVO=44` |
| Properly rated **separate motor battery** + cutoff switch | Motor power; don't draw motor current from Raspberry Pi USB |
| Android phone with Chrome | Microphone and command interface |
| Private Tailscale network | HTTPS access between phone and Pi |

Motor shield V1 jumper behavior must be checked against your exact shield revision. Disconnect power before changing wiring or jumpers. **Never connect a motor battery directly to Raspberry Pi GPIO/USB power.**

## Quick start: recognition-only (safe default)

Run on Raspberry Pi OS (Python 3), from a terminal:

```bash
sudo apt update
sudo apt install -y python3-venv ffmpeg libsndfile1

git clone https://github.com/shah-bakhsh/BalVoice-Robot-Control.git
cd BalVoice-Robot-Control
python3 -m venv .venv
source .venv/bin/activate
python -m pip install -r requirements.txt

# Download the licensed external Vosk model separately, then set its path.
export VOSK_MODEL_PATH="$HOME/robot-live-voice/models/vosk-model-small-en-us-0.15"

python check_install.py
bash start_robot.sh
```

`start_robot.sh` serves on **127.0.0.1:8001**. With no motor-enable flags, it runs recognition only and **does not open the Arduino serial port**. Keep the server terminal open.

If you already configured Tailscale Serve to point to port 8001, open the Pi's private HTTPS URL on Android Chrome. Otherwise configure Serve after checking the current configuration:

```bash
tailscale status
tailscale serve status
# This example may need adjustment for your installed Tailscale version:
tailscale serve --bg --https=8443 http://127.0.0.1:8001
```

Record one short phrase using the phone webpage. Check the recognition result both in Chrome and the Raspberry Pi terminal. If `/status` is not responding, see [Troubleshooting](docs/TROUBLESHOOTING.md).

## Verify Arduino independently (motors unpowered)

Flash [`Robot_Car_Bilingual_Safe.ino`](Arduino/Robot_Car_Bilingual_Safe/Robot_Car_Bilingual_Safe.ino) with the **AFMotor V1 library** installed, and select **Arduino Mega 2560** in Arduino IDE.

With wheels raised, **motor battery disconnected**, and the voice server plus Arduino Serial Monitor stopped:

```bash
source .venv/bin/activate
python test_arduino.py '?'
python test_arduino.py D
```

The firmware must answer `PONG_SAFE_V06` to the first test. The distance test should report `DISTANCE_CM`. Verify that no USB disconnections or over-current warnings occur. **Do not enable motor power or bypass a failed handshake**. See [Safety](docs/SAFETY.md).

## Research models: test both without moving the robot

```bash
cd research_dual_models
# Using the repository root venv is fine if dependencies are installed there.
python3 -m venv .venv
source .venv/bin/activate
python -m pip install -r requirements_pi.txt
python test_dual.py /path/to/new-recording.wav --mode balochi
```

The experimental comparison server can be run separately with `bash start_phone_test.sh` after stopping the main application on port 8001. The comparison code **never opens the Arduino serial port**.

### Benchmark results (research only)

| Model | Input representation | Shuffled 3-fold CV | Operational status |
|---|---|---:|---|
| Original integrated Balochi SVM | MFCC-derived features | Earlier experimental training; phone confidence ~0.30 on some commands | Weak live-phone generalization |
| Research SVM | MFCC temporal features | **69.0%** (156/226) | Recognition-only candidate |
| Research CNN | Log-mel spectrogram | **72.1%** (163/226) | Recognition-only candidate |

Training used **226 unique recordings** (five commands plus noise; 229 before three exact duplicates). The CNN misclassified **12/25 noise examples** in cross-validation. The original recording environment differs from a new Android phone, and speakers may overlap between folds. **These scores are not field accuracy or safety guarantees.** See [full evaluation](research_dual_models/evaluation.json).

## Project status and limitations

- **Available:** phone voice capture, English Vosk support, original Balochi SVM recognition, guarded Arduino serial protocol, safe-boot firmware, ultrasonic/servo code, motor-shield control code, and independent model comparison.
- **Not demonstrated as reliable:** Balochi prediction on a new phone/speaker, USB electrical stability in every setup, live robot movement from the integrated app, unattended navigation, and emergency stop reliability after power failure.
- **Deployment rule:** never treat a recognized word or a high model score as sufficient proof of safe movement.
- **Privacy:** the original voice recordings and access credentials are intentionally **not published**. Obtain all speakers' informed consent before distributing audio.

## Documentation

- [System architecture and command flow](docs/ARCHITECTURE.md)
- [Safety requirements](docs/SAFETY.md)
- [Troubleshooting and diagnostics](docs/TROUBLESHOOTING.md)
- [Research model details and training](research_dual_models/README.md)
- [Historical v0.6 integration notes](docs/VOICE_SERVER_V06.md)
- [Model integrity checksums](MODEL_SHA256SUMS)

## Development and testing

```bash
python3 -m compileall -q app.py recognizer.py motor_link.py research_dual_models
python3 -m unittest discover -s tests -v
sha256sum -c MODEL_SHA256SUMS
```

CI tests file integrity and Python syntax only; **they cannot certify voice recognition, robot mechanics or hardware safety**.

## Contributing and licensing

Suggestions and improvements are welcome via GitHub issues and pull requests. Please document the hardware, Pi OS/Python version, phone/browser, test conditions, and results, and avoid including secrets or recordings without consent.

**No license is granted by default.** The repository owner has not yet selected an open-source license; do not assume model weights, voice recordings, or external Vosk/Arduino dependencies may be redistributed freely. Separate component licenses apply to external dependencies.