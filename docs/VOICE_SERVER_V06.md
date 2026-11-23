# Balochi + English Voice Robot v0.6 — Pi 5 ↔ Arduino Mega

This project uses your original robot wiring, existing English Vosk model, and the Balochi classifier you trained with 229 recordings. It provides a simple one-button Android voice page served over your *existing private Tailscale HTTPS* setup.

**IMPORTANT: At startup all motor controls are disabled.** After you upload the included safe-boot Arduino sketch, check the ultrasonic sensor, verify appropriate independent motor power, raise all wheels and prove manual motor tests, you can *explicitly enable* voice-to-serial commands. The Balochi classifier is experimental (~76–77% on preliminary shuffled cross-validation): it may confuse commands, even when giving a high score. Do not run the car near people, pets or drop-offs. Keep a physical motor power cutoff within reach.

## Commands

| English | Balochi | Arduino |
|---|---|---|
| forward | dema bro | `F` |
| backward | poshta bro | `B` |
| left / turn left | chapen kasha bro | `L` |
| right / turn right | rasten kash a bro | `R` |
| stop | bosht | `S` |

Arduino uses your original AFMotor motors M1–M4, TRIG 24, ECHO 22, SERVO 44. It starts STOPPED at every boot. It limits voice movement to short pulses and blocks forward motion when the ultrasonic sensor reports an obstacle or no echo. `D` checks distance without motion; `?` confirms safe v0.6 firmware. `A` exists on Arduino for manually requested obstacle-avoidance auto mode but is *not available through the phone model*.

## 1. Transfer this project

**Update an existing working v0.3/v0.5 Pi installation**: download `bilingual_voice_arduino_v06_update.zip` to your Raspberry Pi with Firefox, and ensure it is in `~/Downloads`.

```bash
ls -lh ~/Downloads/bilingual_voice_arduino_v06_update.zip
cd ~/bilingual_robot_voice_v03
cp app.py app_previous_backup.py
cp index.html index_previous_backup.html
unzip -o ~/Downloads/bilingual_voice_arduino_v06_update.zip -d .
source .venv/bin/activate
python -m pip install pyserial
```

**Full installation instead**: download `bilingual_robot_voice_v06_full.zip` into the Pi Downloads folder. Then:

```bash
cd ~
unzip -o ~/Downloads/bilingual_robot_voice_v06_full.zip -d ~
cd ~/bilingual_robot_voice_v06
sudo apt install -y python3-venv ffmpeg libsndfile1
python3 -m venv .venv
source .venv/bin/activate
python -m pip install -r requirements.txt
```

Use whichever directory you installed for the following steps; below `cd ~/bilingual_robot_voice_v03` assumes the update path.

## 2. Upload Arduino firmware (motor battery DISCONNECTED)

Arduino IDE: File -> Open `Arduino/Robot_Car_Bilingual_Safe/Robot_Car_Bilingual_Safe.ino`, install Adafruit Motor Shield **V1** `AFMotor` library (NOT V2), Tools -> Board -> Arduino Mega 2560, Tools -> Port -> Arduino's USB port, Upload. Close Serial Monitor afterward.

Default state is STOPPED. To move, Arduino must be explicitly commanded.

## 3. Check USB and ultrasonic sensor (battery still disconnected)

```bash
cd ~/bilingual_robot_voice_v03
source .venv/bin/activate
ls -l /dev/serial/by-id/
python test_arduino.py '?'
python test_arduino.py D
vcgencmd get_throttled
sudo dmesg | grep -Ei 'over-current|under-voltage|usb disconnect' | tail -10
```

`?` must print `PONG_SAFE_V06`. `D` must print `DISTANCE_CM n`. A value of `0` means no usable echo (forward movement is blocked). Make sure the ultrasonic sensor measures a plausible distance before moving.

## 4. Short motor tests (only after verifying shield and motor-battery power)

When Raspberry Pi and Arduino logic are USB-powered and motors have separate external supply on `EXT_PWR`, remove the motor shield's power jumper **with all power off**, then check battery voltage/polarity are suitable. Keep all four wheels **raised** and have a physical power cutoff.

```bash
python test_arduino.py S
python test_arduino.py F --wheels-raised
python test_arduino.py B --wheels-raised
python test_arduino.py L --wheels-raised
python test_arduino.py R --wheels-raised
```

Expected serial responses are `RECEIVED F`, `EXEC F`, `DONE F`, etc. If sensor reads 0 or <=30 cm, `F` is blocked intentionally. Ensure wheels follow intended directions. Do not run the Python voice server or Arduino Serial Monitor at the same time as this test: they must not compete for the USB port.

## 5. Run mobile voice recognition ONLY (no motors)

```bash
cd ~/bilingual_robot_voice_v03
bash start_robot.sh
```

Existing Tailscale HTTPS configuration on the Pi was port **8443** -> `http://127.0.0.1:8001`. Verify `tailscale serve status` on a second terminal and open on Android Chrome:

`https://raspberrypi.tailb99b29.ts.net:8443/?v=6`

Tap **Speak**, say one command. Commands are shown on Android and logged in the Pi terminal, but not transmitted to motors yet. `--no-access-log` avoids noisy `GET /health` lines.

## 6. Enable SHORT voice movement only after successful testing

Stop server with Ctrl+C and ensure the included safe firmware is uploaded. Keep the wheels raised. Start with:

```bash
cd ~/bilingual_robot_voice_v03
ROBOT_ENABLE_MOTORS=1 ROBOT_SAFE_SKETCH_CONFIRMED=YES bash start_robot.sh
```

The Pi verifies that the Arduino replies `PONG_SAFE_V06`. If it does not, motor control remains OFF. The Pi sends STOP on server shutdown or when the Android phone disconnects. The Arduino has its own short motor pulses and command timeout even if USB is lost. Clear movements require an English score >=0.80 or Balochi >=0.90; a lower score can display as recognized while motor output remains disabled for that attempt. These scores do **not** guarantee safety.

**Console examples (illustrative only)**:

```
PHONE CONNECTED | Android/iPhone browser connected through Tailscale
VOICE #001 | ACCEPTED | BALOCHI | 'dema bro' -> FORWARD (F) | ARDUINO SENT
ARDUINO | RECEIVED F
ARDUINO | EXEC F
ARDUINO | DONE F
```

`EXEC` means Arduino ran its motor-control code, **not** that wheel movement was measured by a sensor. The phone interface shows the same recognition and the latest Arduino board report.

Stop server: **Ctrl+C**. Disconnect motor power if abnormal heating, disconnections, wrong motion, or loss of control.

## Troubleshooting

- `No such file or directory` for ZIP: download it on the Pi or transfer it from your PC first.
- `Port busy`: stop voice server/Arduino Serial Monitor. Only one program can own Arduino serial USB.
- No `PONG_SAFE_V06`: wrong sketch or wrong USB port; update firmware, retry with motors unpowered.
- `DISTANCE_CM 0`: recheck TRIG 24, ECHO 22, 5V and GND wiring; forward remains blocked.
- `Arduino=OFF`: motor-enable variables missing or safe firmware handshake failed.
- Pi terminal shows recognized but not sent: inspect `motor_message` (often low confidence or no authorized Android client).
- Phone microphone fails: Tailscale ON and Chrome HTTPS URL are required; grant microphone permission. Browser microphone recording needs a small inline JavaScript API; all speech processing is Python on Pi.
- `over-current` or `usb disconnect`: stop motors and check power distribution, shielding, motor cables, Pi PSU and wiring before retesting.
- Phone URL unreachable: `tailscale status`, `tailscale serve status`, and ensure the app is running on 127.0.0.1:8001.
