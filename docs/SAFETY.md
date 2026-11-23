# Safety policy for the BalVoice robot prototype

This prototype has rotating wheels, an independent motor battery, electrical hazards and an **experimental speech classifier**. It is **not certified for safe autonomous or unattended operation**.

## Before first hardware testing

1. **Disconnect motor battery**, raise all four wheels and secure the chassis so it cannot fall.
2. Confirm Arduino Mega, AFMotor V1 shield model, battery polarity and voltage, shield jumper configuration, and correct GND return. Never supply motor current from Raspberry Pi GPIO or USB.
3. Use an appropriately rated Raspberry Pi 5 power adapter. Inspect `vcgencmd get_throttled` and kernel logs for under-voltage, USB over-current or disconnect messages.
4. Flash only the included **safe-boot** firmware (or independently audit an equivalent implementation). Verify the `? → PONG_SAFE_V06` handshake and ultrasonic distance `D` while motors are unpowered.
5. Test voice recognition and noisy/unknown utterances without connecting Arduino or motor power. A language model score is not an electrical safety interlock.
6. Provide a **physical motor-power cutoff** within immediate reach; preferably disconnect the motor power if anything unexpected happens.

## During supervised testing

- Keep wheels fully **raised** for the initial movement-pulse tests.
- Start in recognition-only mode; do not bypass confidence, device, serial handshake or motor stop checks.
- Re-check the front ultrasonic sensor with a real obstacle before testing forward movement. There is no rear-facing sensor in this prototype.
- Do not use language detection/automatic multilingual modes to drive unless false positive rates have been independently measured in noisy conditions.
- Test with **English first**; the Balochi model is too weak for unattended motor action.
- A USB disconnect prevents a software STOP from reaching the Arduino; physically cut motor power if motion is unexpected.
- Never publish the Tailscale command webpage to the public internet with motor control enabled.

## Recognition model limitations

Research cross-validation was ~72.1% (CNN) / 69.0% (SVM), and the CNN rejected only 13/25 noise clips in those tests. Some live Balochi commands scored around 0.30. Lowering thresholds to accept them could trigger the wrong motion on unrelated speech. Proper evaluation requires **speaker-disjoint phone recordings**, no-command negative samples, noisy-room testing, and error analysis (especially unsafe false positives).

## Privacy, security and licensing

- Do not publish raw voice clips or other people's voices without permission.
- Never commit `.env`, Hugging Face tokens, GitHub tokens, Tailscale credentials, SSH keys, API keys, or `.venv`.
- The browser session check is a *convenience guard*, not strong identity authentication. Tailscale ACLs and private network access remain essential.
- Use caution when opening joblib/PyTorch checkpoint files from untrusted parties; pickled model formats may execute code on load.
