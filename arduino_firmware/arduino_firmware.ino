#include <Servo.h>

#define IN1 4
#define IN2 7
#define IN3 8
#define IN4 12

#define ENA 5
#define ENB 6

#define SPEED_FULL   255
#define SPEED_SLOW   120
#define SPEED_DRIFT  160

#define CARGO_SERVO_PIN  9
#define SCAN_SERVO_PIN   10

#define TRIG_PIN  2
#define ECHO_PIN  3
#define MAX_DIST  400

#define BUZZER_PIN 11

#define WATCHDOG_MS       1500
#define DEADTIME_MS       50
#define MIN_CMD_INTERVAL  30

#define SCAN_ANGLE_LEFT    45
#define SCAN_ANGLE_CENTER  90
#define SCAN_ANGLE_RIGHT  135
#define SERVO_SETTLE_MS    200

Servo cargoServo;
Servo scanServo;

unsigned long lastCommandTime = 0;
unsigned long lastMotorChange = 0;
unsigned long lastDistSend = 0;
int currentDirection = 0;

int currentScanAngle = SCAN_ANGLE_CENTER;
unsigned long lastScanMove = 0;
bool scanSettled = true;

String inputBuffer = "";

int measureDistance() {
  digitalWrite(TRIG_PIN, LOW);
  delayMicroseconds(2);
  digitalWrite(TRIG_PIN, HIGH);
  delayMicroseconds(10);
  digitalWrite(TRIG_PIN, LOW);
  
  long duration = pulseIn(ECHO_PIN, HIGH, 25000);
  if (duration == 0) return MAX_DIST;
  
  int dist = duration * 0.034 / 2;
  return constrain(dist, 0, MAX_DIST);
}

void beep(int durationMs) {
  digitalWrite(BUZZER_PIN, HIGH);
  delay(durationMs);
  digitalWrite(BUZZER_PIN, LOW);
}

void beepWarning() {
  beep(50);
  delay(50);
  beep(50);
}

void setMotorSpeed(int leftSpeed, int rightSpeed) {
  analogWrite(ENA, constrain(leftSpeed, 0, 255));
  analogWrite(ENB, constrain(rightSpeed, 0, 255));
}

void stopMotors() {
  digitalWrite(IN1, LOW); digitalWrite(IN2, LOW);
  digitalWrite(IN3, LOW); digitalWrite(IN4, LOW);
  setMotorSpeed(0, 0);
  currentDirection = 0;
}

void safeDirectionChange(int newDirection) {
  if (currentDirection != 0 && currentDirection != newDirection) {
    bool wasForward = (currentDirection == 1);
    bool wasReverse = (currentDirection == -1);
    bool goingForward = (newDirection == 1);
    bool goingReverse = (newDirection == -1);
    
    if ((wasForward && goingReverse) || (wasReverse && goingForward)) {
      stopMotors();
      delay(DEADTIME_MS);
    }
  }
}

void driveForward() {
  safeDirectionChange(1);
  digitalWrite(IN1, HIGH); digitalWrite(IN2, LOW);
  digitalWrite(IN3, HIGH); digitalWrite(IN4, LOW);
  setMotorSpeed(SPEED_FULL, SPEED_FULL);
  currentDirection = 1;
}

void driveForwardSlow() {
  safeDirectionChange(1);
  digitalWrite(IN1, HIGH); digitalWrite(IN2, LOW);
  digitalWrite(IN3, HIGH); digitalWrite(IN4, LOW);
  setMotorSpeed(SPEED_SLOW, SPEED_SLOW);
  currentDirection = 1;
}

void driveReverse() {
  safeDirectionChange(-1);
  digitalWrite(IN1, LOW);  digitalWrite(IN2, HIGH);
  digitalWrite(IN3, LOW);  digitalWrite(IN4, HIGH);
  setMotorSpeed(SPEED_FULL, SPEED_FULL);
  currentDirection = -1;
}

void turnLeft() {
  safeDirectionChange(2);
  digitalWrite(IN1, LOW); digitalWrite(IN2, HIGH);
  digitalWrite(IN3, HIGH); digitalWrite(IN4, LOW);
  setMotorSpeed(SPEED_DRIFT, SPEED_DRIFT);
  currentDirection = 2;
}

void turnRight() {
  safeDirectionChange(-2);
  digitalWrite(IN1, HIGH); digitalWrite(IN2, LOW);
  digitalWrite(IN3, LOW); digitalWrite(IN4, HIGH);
  setMotorSpeed(SPEED_DRIFT, SPEED_DRIFT);
  currentDirection = -2;
}

void processCommand(String cmd) {
  cmd.trim();
  if (cmd.length() == 0) return;
  
  unsigned long now = millis();
  lastCommandTime = now;
  
  if (cmd == "forward") {
    if (now - lastMotorChange >= MIN_CMD_INTERVAL) {
      driveForward();
      lastMotorChange = now;
    }
  }
  else if (cmd == "reverse" || cmd == "backward") {
    if (now - lastMotorChange >= MIN_CMD_INTERVAL) {
      driveReverse();
      lastMotorChange = now;
    }
  }
  else if (cmd == "slow") {
    if (now - lastMotorChange >= MIN_CMD_INTERVAL) {
      driveForwardSlow();
      lastMotorChange = now;
    }
  }
  else if (cmd == "left") {
    if (now - lastMotorChange >= MIN_CMD_INTERVAL) {
      turnLeft();
      lastMotorChange = now;
    }
  }
  else if (cmd == "right") {
    if (now - lastMotorChange >= MIN_CMD_INTERVAL) {
      turnRight();
      lastMotorChange = now;
    }
  }
  else if (cmd == "stop") {
    stopMotors();
    lastMotorChange = now;
  }
  else if (cmd == "unlock") {
    cargoServo.write(90);
    Serial.println("ACK:unlock");
  }
  else if (cmd == "lock") {
    cargoServo.write(0);
    Serial.println("ACK:lock");
  }
  else if (cmd == "scan_left") {
    scanServo.write(SCAN_ANGLE_LEFT);
    currentScanAngle = SCAN_ANGLE_LEFT;
    lastScanMove = millis();
    scanSettled = false;
  }
  else if (cmd == "scan_center") {
    scanServo.write(SCAN_ANGLE_CENTER);
    currentScanAngle = SCAN_ANGLE_CENTER;
    lastScanMove = millis();
    scanSettled = false;
  }
  else if (cmd == "scan_right") {
    scanServo.write(SCAN_ANGLE_RIGHT);
    currentScanAngle = SCAN_ANGLE_RIGHT;
    lastScanMove = millis();
    scanSettled = false;
  }
  else if (cmd == "beep") {
    beepWarning();
  }
  else if (cmd == "ping") {
    Serial.println("pong");
  }
}

void setup() {
  Serial.begin(115200);

  pinMode(IN1, OUTPUT); pinMode(IN2, OUTPUT);
  pinMode(IN3, OUTPUT); pinMode(IN4, OUTPUT);
  
  pinMode(ENA, OUTPUT);
  pinMode(ENB, OUTPUT);
  
  stopMotors();

  cargoServo.attach(CARGO_SERVO_PIN);
  cargoServo.write(0);
  
  scanServo.attach(SCAN_SERVO_PIN);
  scanServo.write(SCAN_ANGLE_CENTER);
  
  pinMode(TRIG_PIN, OUTPUT);
  pinMode(ECHO_PIN, INPUT);
  
  pinMode(BUZZER_PIN, OUTPUT);
  digitalWrite(BUZZER_PIN, LOW);
  
  lastCommandTime = millis();

  beep(100);
  delay(100);
  beep(100);

  Serial.println("READY");
}

void loop() {
  while (Serial.available()) {
    char c = Serial.read();
    if (c == '\n' || c == '\r') {
      if (inputBuffer.length() > 0) {
        processCommand(inputBuffer);
        inputBuffer = "";
      }
    } else {
      inputBuffer += c;
      if (inputBuffer.length() > 64) {
        inputBuffer = "";
      }
    }
  }
  
  if (millis() - lastCommandTime > WATCHDOG_MS) {
    if (currentDirection != 0) {
      stopMotors();
    }
    lastCommandTime = millis();
  }
  
  if (!scanSettled && (millis() - lastScanMove > SERVO_SETTLE_MS)) {
    scanSettled = true;
  }
  
  if (scanSettled && (millis() - lastDistSend > 100)) {
    int dist = measureDistance();
    lastDistSend = millis();
    
    String dirTag = (currentScanAngle <= 60) ? "L" : (currentScanAngle >= 120 ? "R" : "C");
    Serial.println("DIST:" + String(dist) + ":" + dirTag);
    
    if (dist < 15 && dirTag == "C") {
      stopMotors();
      Serial.println("BLOCKED");
      beepWarning();
    } else if (dist < 100 && dirTag == "C") {
      digitalWrite(BUZZER_PIN, HIGH);
      delay(20);
      digitalWrite(BUZZER_PIN, LOW);
    }
  }
}
