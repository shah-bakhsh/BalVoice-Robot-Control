/*
  ROBOT CAR — AUTOMATIC + ENGLISH/BALOCHI VOICE CONTROL
  Arduino Mega 2560 + L293D / Adafruit Motor Shield V1 (AFMotor)

  STARTUP:  motors remain STOPPED until a command is received.
            Send A to opt into automatic obstacle avoidance.
  VIA USB:  Raspberry Pi can send single characters:
            F forward, B backward, L left, R right, S STOP,
            A resume automatic mode, V enter stopped voice mode.

  Safety:
  - Boots with motors stopped before auto-navigation begins.
  - No echo from the ultrasonic sensor => STOP (never blindly forward).
  - No clear path => STOP (no blind reversing without rear sensor).
  - In VOICE mode, movement times out if commands stop arriving.
  - STOP is checked during servo and turning delays.

  Mount car with wheels OFF the ground for the first test.
  Motor battery must be separately powered via shield EXT_PWR; remove
  shield power jumper if powering Arduino through Pi USB + motor battery.
*/

#include <AFMotor.h>
#include <Servo.h>

// ---------------- BOARD / WIRING ----------------
AF_DCMotor motor1(1);   // left front
AF_DCMotor motor2(2);   // left rear
AF_DCMotor motor3(3);   // right front
AF_DCMotor motor4(4);   // right rear

const byte TRIG_PIN  = 24;
const byte ECHO_PIN  = 22;
const byte SERVO_PIN = 44;
Servo scanner;

// ---------------- SETTINGS ----------------
const uint8_t MOTOR_SPEED = 180;           // 0..255
const int SAFE_DISTANCE_CM = 30;
const unsigned long ECHO_TIMEOUT_US = 25000UL;
const unsigned long TURN_TIME_MS = 900UL; // tune for your chassis
const unsigned long SCAN_SETTLE_MS = 500UL;
const unsigned long CENTER_SETTLE_MS = 300UL;
const unsigned long VOICE_TIMEOUT_MS = 900UL;
const unsigned long REVERSE_LIMIT_MS = 600UL; // no rear obstacle sensor!
const unsigned long VOICE_TURN_LIMIT_MS = 600UL;
const unsigned long FORWARD_LIMIT_MS = 700UL;
const int SERVO_CENTER = 90;
const int SERVO_LEFT   = 150;
const int SERVO_RIGHT  = 30;

enum RobotMode { AUTO_MODE, VOICE_MODE, STOPPED_MODE };
RobotMode mode = STOPPED_MODE;    // SAFE: no motion automatically at boot
char voiceAction = 'S';
unsigned long lastVoiceCommandAt = 0;
unsigned long voiceActionStartedAt = 0;
bool actionReported = false;

// ---------------- MOTOR HELPERS ----------------
void stopAll() {
  motor1.run(RELEASE);
  motor2.run(RELEASE);
  motor3.run(RELEASE);
  motor4.run(RELEASE);
}

void moveForward() {
  motor1.run(FORWARD);
  motor2.run(FORWARD);
  motor3.run(FORWARD);
  motor4.run(FORWARD);
}

void moveBackward() {
  motor1.run(BACKWARD);
  motor2.run(BACKWARD);
  motor3.run(BACKWARD);
  motor4.run(BACKWARD);
}

// Same turning pattern as your original code: front motors released.
void turnLeftDrive() {
  motor1.run(RELEASE);
  motor3.run(RELEASE);
  motor2.run(BACKWARD);
  motor4.run(FORWARD);
}

void turnRightDrive() {
  motor1.run(RELEASE);
  motor3.run(RELEASE);
  motor2.run(FORWARD);
  motor4.run(BACKWARD);
}

// ---------------- DISTANCE ----------------
// 0 means no valid sensor echo (treat as unsafe).
int getDistanceCm() {
  digitalWrite(TRIG_PIN, LOW);
  delayMicroseconds(2);
  digitalWrite(TRIG_PIN, HIGH);
  delayMicroseconds(10);
  digitalWrite(TRIG_PIN, LOW);

  unsigned long duration = pulseIn(ECHO_PIN, HIGH, ECHO_TIMEOUT_US);
  if (duration == 0) return 0;
  return (int)(duration / 58UL);
}

// ---------------- USB COMMAND INPUT ----------------
// Both language recognizers on the Pi should send SAME letter commands.
void readCommands() {
  while (Serial.available() > 0) {
    char c = (char)Serial.read();
    if (c >= 'a' && c <= 'z') c = c - 'a' + 'A';

    if (c == 'S') {
      mode = STOPPED_MODE; // latched stop until a new movement/A/V command
      voiceAction = 'S';
      stopAll();
      Serial.println(F("STOPPED"));
    }
    else if (c == 'A') {
      stopAll();
      scanner.write(SERVO_CENTER);
      mode = AUTO_MODE;
      voiceAction = 'S';
      Serial.println(F("AUTO MODE"));
    }
    else if (c == 'V') {
      stopAll();
      scanner.write(SERVO_CENTER);
      mode = VOICE_MODE;
      voiceAction = 'S';
      lastVoiceCommandAt = millis();
      Serial.println(F("VOICE MODE: WAITING"));
    }
    else if (c == 'F' || c == 'B' || c == 'L' || c == 'R') {
      const bool newAction = (mode != VOICE_MODE || voiceAction != c);
      mode = VOICE_MODE;
      lastVoiceCommandAt = millis();
      if (newAction) {
        stopAll();
        scanner.write(SERVO_CENTER);
        voiceAction = c;
        voiceActionStartedAt = millis();
        actionReported = false;
        Serial.print(F("RECEIVED "));
        Serial.println(c);
      }
    }
    else if (c == 'D') {
      // Sensor-only diagnostic; never starts a motor.
      stopAll();
      mode = STOPPED_MODE;
      voiceAction = 'S';
      scanner.write(SERVO_CENTER);
      delay(180);
      Serial.print(F("DISTANCE_CM "));
      Serial.println(getDistanceCm());
    }
    else if (c == '?') {
      Serial.println(F("PONG_SAFE_V06"));
    }
    // Ignore CR, LF, and any unknown characters.
  }
}

// Used for AUTO mode delays, so S (stop) and voice commands interrupt them.
bool waitWhileAuto(unsigned long durationMs) {
  const unsigned long startedAt = millis();
  while ((unsigned long)(millis() - startedAt) < durationMs) {
    readCommands();
    if (mode != AUTO_MODE) {
      stopAll();
      return false;
    }
    delay(5);
  }
  return true;
}

int scanAt(int angle) {
  scanner.write(angle);
  if (!waitWhileAuto(SCAN_SETTLE_MS)) return 0;
  return getDistanceCm();
}

void autoTurn(bool goLeft) {
  if (goLeft) {
    Serial.println(F("AUTO: TURN LEFT"));
    turnLeftDrive();
  } else {
    Serial.println(F("AUTO: TURN RIGHT"));
    turnRightDrive();
  }
  waitWhileAuto(TURN_TIME_MS);
  stopAll();
}

// ---------------- AUTONOMOUS MODE ----------------
void runAutomatic() {
  scanner.write(SERVO_CENTER);
  int front = getDistanceCm();

  if (front == 0) {
    stopAll();
    Serial.println(F("AUTO: ULTRASONIC NO ECHO - STOP"));
    waitWhileAuto(250);
    return;
  }

  if (front > SAFE_DISTANCE_CM) {
    moveForward();
    waitWhileAuto(70); // check forward distance frequently
    return;
  }

  // Obstacle: stop, scan both sides while stationary.
  stopAll();
  Serial.print(F("AUTO: OBSTACLE AT "));
  Serial.print(front);
  Serial.println(F(" cm"));
  if (!waitWhileAuto(180)) return;

  const int leftDistance = scanAt(SERVO_LEFT);
  if (mode != AUTO_MODE) return;
  const int rightDistance = scanAt(SERVO_RIGHT);
  if (mode != AUTO_MODE) return;
  scanner.write(SERVO_CENTER);
  if (!waitWhileAuto(CENTER_SETTLE_MS)) return;

  Serial.print(F("LEFT: "));
  Serial.print(leftDistance);
  Serial.print(F(" cm, RIGHT: "));
  Serial.print(rightDistance);
  Serial.println(F(" cm"));

  const bool leftClear  = leftDistance > SAFE_DISTANCE_CM;
  const bool rightClear = rightDistance > SAFE_DISTANCE_CM;

  if (!leftClear && !rightClear) {
    // No rear sensor: do not blindly reverse into an unseen obstacle.
    stopAll();
    Serial.println(F("AUTO: BOTH SIDES BLOCKED - STOP"));
    waitWhileAuto(450);
    return;
  }

  bool turnToLeft = leftClear && (!rightClear || leftDistance > rightDistance);
  autoTurn(turnToLeft);
  if (mode != AUTO_MODE) return;

  // Before moving forward again, recheck clearance in the next loop.
  waitWhileAuto(220);
}

// ---------------- VOICE MODE ----------------
void runVoice() {
  if (voiceAction == 'S') {
    stopAll();
    delay(10);
    return;
  }

  if ((unsigned long)(millis() - lastVoiceCommandAt) > VOICE_TIMEOUT_MS) {
    stopAll();
    voiceAction = 'S';
    Serial.println(F("VOICE: TIMEOUT - STOP"));
    return;
  }

  const unsigned long actionAge = millis() - voiceActionStartedAt;
  if (actionAge < CENTER_SETTLE_MS) {
    stopAll(); // let servo return to center before moving
    delay(10);
    return;
  }

  if (voiceAction == 'F') {
    if (actionAge > FORWARD_LIMIT_MS) {
      stopAll();
      voiceAction = 'S';
      Serial.println(F("DONE F"));
      return;
    }
    int d = getDistanceCm();
    if (d == 0 || d <= SAFE_DISTANCE_CM) {
      stopAll();
      voiceAction = 'S';
      Serial.println(F("BLOCKED F: OBSTACLE OR NO SENSOR ECHO"));
    } else {
      if (!actionReported) { Serial.println(F("EXEC F")); actionReported = true; }
      moveForward();
    }
  }
  else if (voiceAction == 'B') {
    if (actionAge > REVERSE_LIMIT_MS) {
      stopAll();
      voiceAction = 'S';
      Serial.println(F("DONE B"));
    } else {
      if (!actionReported) { Serial.println(F("EXEC B")); actionReported = true; }
      moveBackward();
    }
  }
  else if (voiceAction == 'L') {
    if (actionAge > VOICE_TURN_LIMIT_MS) {
      stopAll();
      voiceAction = 'S';
      Serial.println(F("DONE L"));
    } else {
      if (!actionReported) { Serial.println(F("EXEC L")); actionReported = true; }
      turnLeftDrive();
    }
  }
  else if (voiceAction == 'R') {
    if (actionAge > VOICE_TURN_LIMIT_MS) {
      stopAll();
      voiceAction = 'S';
      Serial.println(F("DONE R"));
    } else {
      if (!actionReported) { Serial.println(F("EXEC R")); actionReported = true; }
      turnRightDrive();
    }
  }
  delay(20);
}

// ---------------- ARDUINO STARTUP ----------------
void setup() {
  Serial.begin(9600);
  pinMode(TRIG_PIN, OUTPUT);
  pinMode(ECHO_PIN, INPUT);
  digitalWrite(TRIG_PIN, LOW);

  stopAll();
  motor1.setSpeed(MOTOR_SPEED);
  motor2.setSpeed(MOTOR_SPEED);
  motor3.setSpeed(MOTOR_SPEED);
  motor4.setSpeed(MOTOR_SPEED);

  scanner.attach(SERVO_PIN);
  scanner.write(SERVO_CENTER);
  delay(1000);

  Serial.println(F("ROBOT READY - STOPPED MODE"));
  Serial.println(F("F/B/L/R voice, S stop, A auto, V voice waiting"));
}

void loop() {
  readCommands();
  if (mode == AUTO_MODE) {
    runAutomatic();
  } else if (mode == VOICE_MODE) {
    runVoice();
  } else {
    stopAll();
    delay(15);
  }
}
