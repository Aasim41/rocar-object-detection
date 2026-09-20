// ============================================================
// Arduino Uno Serial Firmware — Delivery Bot v4.0
// ============================================================
// Upload via Arduino IDE. Libraries: "Servo" (built-in).
// Board: Arduino Uno
//
// v4.0: Ported from ESP32 WebSocket to Arduino USB Serial.
//       Phone acts as WiFi-to-Serial bridge via Termux.
//       Same command protocol as ESP32 version.

#include <Servo.h>

// --- L298N Motor Driver Pins (digital only) ---
#define IN1 4
#define IN2 7
#define IN3 8
#define IN4 12

// --- PWM Speed Control (must be PWM-capable pins) ---
#define ENA 5    // Left motor pair speed  (PWM pin)
#define ENB 6    // Right motor pair speed (PWM pin)

// --- Speed Presets ---
#define SPEED_FULL   255
#define SPEED_SLOW   120   // ~47% for obstacle approach
#define SPEED_DRIFT  160   // Speed for tank/drift steering

// --- Servo Pins (must be PWM-capable) ---
#define CARGO_SERVO_PIN  9    // Cargo lock servo
#define SCAN_SERVO_PIN   10   // Ultrasonic scanning servo

// --- Ultrasonic Sensor (HC-SR04) ---
#define TRIG_PIN  2
#define ECHO_PIN  3
#define MAX_DIST  400  // cm — max reliable range

// --- Buzzer ---
#define BUZZER_PIN 11

// --- Safety ---
#define WATCHDOG_MS       1500   // Stop motors after 1.5s of silence
#define DEADTIME_MS       50     // Pause between direction reversals
#define MIN_CMD_INTERVAL  30     // Minimum ms between motor commands

// --- Scanning Config ---
#define SCAN_ANGLE_LEFT    45
#define SCAN_ANGLE_CENTER  90
#define SCAN_ANGLE_RIGHT  135
#define SERVO_SETTLE_MS    200   // wait for servo to reach position

Servo cargoServo;
Servo scanServo;

// --- State Tracking ---
unsigned long lastCommandTime = 0;
unsigned long lastMotorChange = 0;
unsigned long lastDistSend = 0;
bool clientConnected = true;  // Always true for serial (direct USB)
int currentDirection = 0;

// --- Scanning State ---
int currentScanAngle = SCAN_ANGLE_CENTER;
unsigned long lastScanMove = 0;
bool scanSettled = true;

// --- Serial Input Buffer ---
String inputBuffer = "";

// ============================================================
// Ultrasonic Distance Measurement
// ============================================================
int measureDistance() {
  digitalWrite(TRIG_PIN, LOW);
  delayMicroseconds(2);
  digitalWrite(TRIG_PIN, HIGH);
  delayMicroseconds(10);
  digitalWrite(TRIG_PIN, LOW);
  
  long duration = pulseIn(ECHO_PIN, HIGH, 25000); // 25ms timeout
  if (duration == 0) return MAX_DIST;
  
  int dist = duration * 0.034 / 2;
  return constrain(dist, 0, MAX_DIST);
}

// ============================================================
// Buzzer
// ============================================================
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

// ============================================================
// Motor Control (analogWrite for Arduino Uno)
// ============================================================
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
  // DRIFT STEER: Left reverse, Right forward
  safeDirectionChange(2);
  digitalWrite(IN1, LOW); digitalWrite(IN2, HIGH);
  digitalWrite(IN3, HIGH); digitalWrite(IN4, LOW);
  setMotorSpeed(SPEED_DRIFT, SPEED_DRIFT);
  currentDirection = 2;
}

void turnRight() {
  // DRIFT STEER: Left forward, Right reverse
  safeDirectionChange(-2);
  digitalWrite(IN1, HIGH); digitalWrite(IN2, LOW);
  digitalWrite(IN3, LOW); digitalWrite(IN4, HIGH);
  setMotorSpeed(SPEED_DRIFT, SPEED_DRIFT);
  currentDirection = -2;
}

// ============================================================
// Process Incoming Serial Command
// ============================================================
void processCommand(String cmd) {
  cmd.trim();
  if (cmd.length() == 0) return;
  
  unsigned long now = millis();
  lastCommandTime = now;
  
  // --- Motor commands ---
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
  // --- Cargo servo ---
  else if (cmd == "unlock") {
    cargoServo.write(90);
    Serial.println("ACK:unlock");
  }
  else if (cmd == "lock") {
    cargoServo.write(0);
    Serial.println("ACK:lock");
  }
  // --- Scan servo commands ---
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
  // --- Buzzer ---
  else if (cmd == "beep") {
    beepWarning();
  }
  // --- Ping (heartbeat from relay) ---
  else if (cmd == "ping") {
    Serial.println("pong");
  }
}

// ============================================================
// Setup
// ============================================================
void setup() {
  Serial.begin(115200);

  // Motor direction pins
  pinMode(IN1, OUTPUT); pinMode(IN2, OUTPUT);
  pinMode(IN3, OUTPUT); pinMode(IN4, OUTPUT);
  
  // PWM speed pins
  pinMode(ENA, OUTPUT);
  pinMode(ENB, OUTPUT);
  
  stopMotors();

  // Servos
  cargoServo.attach(CARGO_SERVO_PIN);
  cargoServo.write(0);   // locked position on boot
  
  scanServo.attach(SCAN_SERVO_PIN);
  scanServo.write(SCAN_ANGLE_CENTER);  // face forward
  
  // Ultrasonic
  pinMode(TRIG_PIN, OUTPUT);
  pinMode(ECHO_PIN, INPUT);
  
  // Buzzer
  pinMode(BUZZER_PIN, OUTPUT);
  digitalWrite(BUZZER_PIN, LOW);
  
  lastCommandTime = millis();

  // Startup beep to confirm boot
  beep(100);
  delay(100);
  beep(100);

  Serial.println("--- Arduino Serial Bot Ready (v4.0) ---");
}

// ============================================================
// Main Loop
// ============================================================
void loop() {
  // --- Read serial commands (newline-terminated) ---
  while (Serial.available()) {
    char c = Serial.read();
    if (c == '\n' || c == '\r') {
      if (inputBuffer.length() > 0) {
        processCommand(inputBuffer);
        inputBuffer = "";
      }
    } else {
      inputBuffer += c;
      // Safety: prevent buffer overflow
      if (inputBuffer.length() > 64) {
        inputBuffer = "";
      }
    }
  }
  
  // Watchdog — stop motors if no command received recently
  if (millis() - lastCommandTime > WATCHDOG_MS) {
    if (currentDirection != 0) {
      stopMotors();
      Serial.println("WATCHDOG: No command for 1.5s — MOTORS STOPPED");
    }
    lastCommandTime = millis();
  }
  
  // Check if scan servo has settled after moving
  if (!scanSettled && (millis() - lastScanMove > SERVO_SETTLE_MS)) {
    scanSettled = true;
  }
  
  // Send distance readings every 100ms (10Hz) — only when servo is settled
  if (scanSettled && (millis() - lastDistSend > 100)) {
    int dist = measureDistance();
    lastDistSend = millis();
    
    // Tag the reading with direction
    String dirTag;
    if (currentScanAngle <= 60) dirTag = "L";
    else if (currentScanAngle >= 120) dirTag = "R";
    else dirTag = "C";
    
    // Send: "DIST:123:C" (same format as ESP32)
    Serial.println("DIST:" + String(dist) + ":" + dirTag);
    
    // Emergency reflex: stop if something is within 15cm (center only)
    if (dist < 15 && dirTag == "C") {
      stopMotors();
      Serial.println("BLOCKED");
      beepWarning();
    }
    // Proximity warning beep
    else if (dist < 100 && dirTag == "C") {
      digitalWrite(BUZZER_PIN, HIGH);
      delay(20);
      digitalWrite(BUZZER_PIN, LOW);
    }
  }
}
