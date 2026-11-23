# Troubleshooting: BalVoice on Raspberry Pi 5

## 1. `curl /status` says `Expecting value`

The JSON parser received no JSON (often because the server isn't running). First run the server in a separate terminal:

```bash
cd ~/BalVoice-Robot-Control
source .venv/bin/activate
bash start_robot.sh
```

Then inspect the raw HTTP response:

```bash
curl -sS -i http://127.0.0.1:8001/status
ss -ltnp | grep ':8001' || true
```

Do not parse empty output with `python3 -m json.tool` until the endpoint returns HTTP 200 JSON.

## 2. Phone speech recognized but command not sent

Check the Pi terminal's exact message. A registered session is needed before dispatch; open the voice page through **private Tailscale HTTPS** and allow browser microphone access. The integrated app is recognition-only by default, even with a working phone. **Do not enable motors just to test speech accuracy.**

## 3. `REJECTED | BALOCHI | dema bro | score=0.326`

The classifier predicted the command name but did not have enough confidence. This is a **model generalization** problem, not proof of an Arduino or phone transport failure. Do not reduce movement safety thresholds to 0.3. Collect new phone recordings, train new models and evaluate by independent speaker/session before considering integration.

## 4. `ARDUINO DISCONNECTED` / `USB serial connection lost`

Only one process can own the Arduino serial port. Stop the voice server, serial monitor and other test scripts. Check:

```bash
ls -l /dev/serial/by-id/ || true
python3 -m serial.tools.list_ports -v
vcgencmd get_throttled
sudo dmesg | grep -Ei 'over-current|undervoltage|under-voltage|usb disconnect|ttyACM' | tail -30
```

Disconnect motor power while diagnosing, try a reliable short **data-capable** USB cable, confirm the Pi has a correct power supply, and check shielding/battery wiring. Do not bypass missing `PONG_SAFE_V06` handshake.

## 5. `python test_arduino.py '?'` fails

Verify firmware is the Arduino Mega safe sketch at `Arduino/Robot_Car_Bilingual_Safe/Robot_Car_Bilingual_Safe.ino`, with AFMotor V1 library installed and baud rate 9600. Select exactly one Arduino by-id port. Serial opening may reset the Mega; retry once after waiting for reboot. Motors should remain unpowered during diagnostics.

## 6. Terminal shows `ARDUINO SENT | F`, but wheels don't move

`ARDUINO SENT` means bytes were written to USB, **not** that the motors actually ran. Check whether Arduino replies `RECEIVED F`, `EXEC F`, or an obstacle/ultrasonic STOP report. Raise wheels. Verify motor shield power jumper and separate battery, polarity, connections on M1–M4, motor power cutoff, and sensor distance. If Pi USB drops after motion, treat it as a power/wiring problem rather than a recognition problem.

## 7. English model unavailable

This repo does not include Vosk model weights. Download the pretrained `vosk-model-small-en-us-0.15` from an appropriate source, unpack it and set `VOSK_MODEL_PATH` to the local directory. Run `python check_install.py` for a status report.

## 8. Port 8001 is already in use

Stop other FastAPI/Uvicorn applications using 8001. The research test webpage is a separate app and must not run alongside the integrated app on the same port.

## 9. Research CNN appears better than original Balochi SVM

`research_dual_models/` is a **separate recognition-only** project; it does not replace the original SVM used by `app.py`. The reported CNN 72.1% validation score is not evidence of safe independent-speaker recognition or robot operation.
