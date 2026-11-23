# Optional: Upload Arduino sketch directly from Raspberry Pi terminal

You can use Arduino IDE on a PC or Raspberry Pi. If you want to upload **using only the Raspberry Pi terminal**, these commands use the official Arduino CLI for Raspberry Pi OS 64-bit (`aarch64`).

**Disconnect motor battery, stop the voice server, and close Arduino Serial Monitor first.**

```bash
uname -m
# Confirm aarch64. If not, use a different Arduino CLI build.
mkdir -p ~/bin
curl -fL https://downloads.arduino.cc/arduino-cli/arduino-cli_latest_Linux_ARM64.tar.gz -o /tmp/arduino-cli.tar.gz
tar -xzf /tmp/arduino-cli.tar.gz -C ~/bin arduino-cli
~/bin/arduino-cli version
~/bin/arduino-cli core update-index
~/bin/arduino-cli core install arduino:avr
sudo apt install -y git
mkdir -p ~/Arduino/libraries
# If AFMotor already installed in Arduino/libraries, skip clone:
git clone --depth 1 https://github.com/adafruit/Adafruit-Motor-Shield-library.git ~/Arduino/libraries/AFMotor
```

Now compile and upload (change `bilingual_robot_voice_v03` if you installed the full v06 project):

```bash
cd ~/bilingual_robot_voice_v03
~/bin/arduino-cli board list
~/bin/arduino-cli compile -b arduino:avr:mega:cpu=atmega2560 Arduino/Robot_Car_Bilingual_Safe
~/bin/arduino-cli upload -p /dev/ttyACM0 -b arduino:avr:mega:cpu=atmega2560 Arduino/Robot_Car_Bilingual_Safe
```

Use the port shown by `arduino-cli board list`, which may be `/dev/ttyACM1` on another boot. If `AFMotor.h` cannot be found, ensure `~/Arduino/libraries/AFMotor/AFMotor.h` exists, or use the Arduino IDE library manager and install **Adafruit Motor Shield V1** (not V2).

Close all serial-monitor programs after uploading, then run `python test_arduino.py '?'` to confirm `PONG_SAFE_V06`.
