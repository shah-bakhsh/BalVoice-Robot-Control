# Architecture: BalVoice Robot Control

## Roles

1. **Android Chrome** captures a 0.4–8 second command and posts it through the user's private Tailscale HTTPS address.
2. **Raspberry Pi 5** receives the microphone recording through FastAPI `app.py`. `recognizer.py` decodes the audio and selects English Vosk or the original Balochi SVM (`balochi_model_v02.joblib`).
3. **Command gate** requires a recent registered browser session and a high recognition score before any USB write. Acceptance is not evidence of safe physical movement.
4. **MotorLink** is disabled by default. With explicit local opt-in, it searches for exactly one Arduino by `/dev/serial/by-id`, opens 9600 baud and requires a `PONG_SAFE_V06` handshake from the included firmware before sending commands. It tries to STOP on disconnect/shutdown where USB remains available.
5. **Arduino Mega 2560** parses `F/B/L/R/S`; motor pulses stop independently on timeout and the ultrasonic sensor blocks unsafe forward movement. It starts with motors stopped. The Arduino supports `A` for manual autonomous mode, but the Pi's voice bridge doesn't expose `A` as a spoken command.

## Hardware pins / ports

| Component | Connection |
|---|---|
| Motor shield V1 | Arduino Mega + AFMotor V1 library |
| Motors | M1, M2, M3, M4 |
| Ultrasonic TRIG | Digital pin 24 |
| Ultrasonic ECHO | Digital pin 22 |
| Scanner servo signal | Digital pin 44 |
| Pi → Arduino | USB serial at 9600 baud |
| API | `http://127.0.0.1:8001` |
| Private Android HTTPS | Tailscale Serve configured by the user |

**Do not assume the pinout is suitable for another motor shield revision.** Verify shield, jumpers, motor battery voltage and GND before hardware tests.

## Voice commands and serial protocol

| Command | Code | Arduino behavior |
|---|---|---|
| Forward | `F` | Brief forward pulse if ultrasonic path clear |
| Backward | `B` | Brief reverse pulse; no rear sensor, supervise closely |
| Left | `L` | Timed turn |
| Right | `R` | Timed turn |
| Stop | `S` | Latched stop |
| Handshake | `?` | Reply `PONG_SAFE_V06` |
| Distance | `D` | Reply `DISTANCE_CM ...`; never starts motor |
| Voice mode | `V` | Stop and await voice |
| Auto | `A` | Manual opt-in to obstacle-avoidance mode (not sent by Pi voice app) |

## How the models differ

The default server uses an **original MFCC/SVM Balochi classifier**, while `research_dual_models` contains **separate** trained CNN and SVM candidates. The CNN's higher cross-validation score does not mean the default server automatically runs the CNN. To change deployed recognizers, perform real phone/speaker tests first and review the safety gate.

## Failure scenarios

- Browser session expires: recognized command not sent.
- Confidence below threshold: recognized candidate rejected or not sent.
- Arduino absent, handshake wrong, or USB drops: motor bridge remains disabled or raises an error.
- Ultrasound gives zero/no echo: Arduino should stop forward movement.
- Arduino USB is already disconnected: software STOP cannot guarantee physical braking; use physical power cutoff.
