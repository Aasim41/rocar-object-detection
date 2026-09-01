// ============================================================
// ESP32 WebSocket Firmware — Delivery Bot v3.0
// ============================================================
// Upload via Arduino IDE. Libraries needed: "WebSockets" by
// Markus Sattler, "ESP32Servo". Board: ESP32 Dev Module
//
// v3.0: Added ultrasonic sensor on scanning servo, buzzer,
//       directional distance scanning (left/center/right)

#include <WiFi.h>
#include <WebSocketsServer.h>
#include <ESP32Servo.h>

// --- L298N Motor Driver Pins ---
#define IN1 23
#define IN2 22
#define IN3 21
#define IN4 19

// --- PWM Speed Control (L298N ENA/ENB) ---
#define ENA 25   // Left motor pair speed (connect to L298N ENA)
#define ENB 26   // Right motor pair speed (connect to L298N ENB)

// --- PWM Configuration ---
#define PWM_FREQ      1000
#define PWM_RESOLUTION 8    // 0-255
#define PWM_CHANNEL_A  0
#define PWM_CHANNEL_B  1

// --- Speed Presets ---
#define SPEED_FULL   255
#define SPEED_SLOW   120   // ~47% for obstacle approach
#define SPEED_TURN   180   // ~70% for rolling turns (inner wheel)

// --- Servo Pins ---
#define CARGO_SERVO_PIN  18   // Cargo lock servo
#define SCAN_SERVO_PIN   13   // Ultrasonic scanning servo

// --- Ultrasonic Sensor (HC-SR04) ---
#define TRIG_PIN  27
#define ECHO_PIN  14
#define MAX_DIST  400  // cm — max reliable range

// --- Buzzer ---
#define BUZZER_PIN 12

// --- Safety ---
#define WATCHDOG_MS       1500   // Stop motors after 1.5s of silence
#define DEADTIME_MS       50     // Pause between direction reversals
#define MIN_CMD_INTERVAL  30     // Minimum ms between motor commands

// --- Scanning Config ---
#define SCAN_ANGLE_LEFT    45
#define SCAN_ANGLE_CENTER  90
#define SCAN_ANGLE_RIGHT  135
#define SERVO_SETTLE_MS    200   // wait for servo to reach position

WebSocketsServer webSocket = WebSocketsServer(81);
Servo cargoServo;
Servo scanServo;

// --- State Tracking ---
unsigned long lastCommandTime = 0;
unsigned long lastMotorChange = 0;
unsigned long lastDistSend = 0;
bool clientConnected = false;
int currentDirection = 0;

// --- Scanning State ---
int currentScanAngle = SCAN_ANGLE_CENTER;
unsigned long lastScanMove = 0;
bool scanSettled = true;

// ============================================================
// Ultrasonic Distance Measurement
// ============================================================
int measureDistance() {
  digitalWrite(TRIG_PIN, LOW);
  delayMicroseconds(2);
  digitalWrite(TRIG_PIN, HIGH);
  delayMicroseconds(10);
  digitalWrite(TRIG_PIN, LOW);
  
  long duration = pulseIn(ECHO_PIN, HIGH, 25000); // 25ms timeout (~4.3m)
  if (duration == 0) return MAX_DIST; // timeout = no obstacle
  
  int dist = duration * 0.034 / 2;  // speed of sound / 2
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
  // Quick double beep for obstacle warning
  beep(50);
  delay(50);
  beep(50);
}

// ============================================================
// Motor Control (with PWM speed)
// ============================================================
void setMotorSpeed(int leftSpeed, int rightSpeed) {
  ledcWrite(ENA, constrain(leftSpeed, 0, 255));
  ledcWrite(ENB, constrain(rightSpeed, 0, 255));
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
  digitalWrite(IN1, HIGH); digitalWrite(IN2, LOW);
  digitalWrite(IN3, HIGH); digitalWrite(IN4, LOW);
  setMotorSpeed(SPEED_TURN, SPEED_FULL);
  currentDirection = 2;
}

void turnRight() {
  safeDirectionChange(-2);
  digitalWrite(IN1, HIGH); digitalWrite(IN2, LOW);
  digitalWrite(IN3, HIGH); digitalWrite(IN4, LOW);
  setMotorSpeed(SPEED_FULL, SPEED_TURN);
  currentDirection = -2;
}

// ============================================================
// WebSocket Event Handler
// ============================================================
void webSocketEvent(uint8_t num, WStype_t type, uint8_t * payload, size_t length) {
  
  if (type == WStype_DISCONNECTED) {
    stopMotors();
    clientConnected = false;
    Serial.printf("[%u] Client disconnected — MOTORS STOPPED\n", num);
    return;
  }
  
  if (type == WStype_CONNECTED) {
    clientConnected = true;
    lastCommandTime = millis();
    Serial.printf("[%u] Client connected\n", num);
    return;
  }
  
  if (type == WStype_TEXT) {
    payload[length] = '\0';
    String cmd = String((char*)payload);
    cmd.trim();
    
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
    }
    else if (cmd == "lock") {
      cargoServo.write(0);
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
  ledcAttach(ENA, PWM_FREQ, PWM_RESOLUTION);
  ledcAttach(ENB, PWM_FREQ, PWM_RESOLUTION);
  
  stopMotors();

  // Servos
  cargoServo.attach(CARGO_SERVO_PIN);
  cargoServo.write(0);   // locked
  
  scanServo.attach(SCAN_SERVO_PIN);
  scanServo.write(SCAN_ANGLE_CENTER);  // face forward
  
  // Ultrasonic
  pinMode(TRIG_PIN, OUTPUT);
  pinMode(ECHO_PIN, INPUT);
  
  // Buzzer
  pinMode(BUZZER_PIN, OUTPUT);
  digitalWrite(BUZZER_PIN, LOW);

  WiFi.softAP("DeliveryBot-WiFi", "password123");
  Serial.print("AP IP Address: ");
  Serial.println(WiFi.softAPIP());

  webSocket.begin();
  webSocket.onEvent(webSocketEvent);
  
  lastCommandTime = millis();

  Serial.println("--- WebSocket Server Started on :81 (v3.0) ---");
}

// ============================================================
// Main Loop
// ============================================================
void loop() {
  webSocket.loop();
  
  // Watchdog — stop motors if no command received recently
  if (clientConnected && (millis() - lastCommandTime > WATCHDOG_MS)) {
    stopMotors();
    Serial.println("WATCHDOG: No command for 1.5s — MOTORS STOPPED");
    lastCommandTime = millis();
  }
  
  // Check if scan servo has settled after moving
  if (!scanSettled && (millis() - lastScanMove > SERVO_SETTLE_MS)) {
    scanSettled = true;
  }
  
  // Send distance readings every 100ms (10Hz) — only when servo is settled
  if (clientConnected && scanSettled && (millis() - lastDistSend > 100)) {
    int dist = measureDistance();
    lastDistSend = millis();
    
    // Tag the reading with direction so backend knows which angle
    String dirTag;
    if (currentScanAngle <= 60) dirTag = "L";
    else if (currentScanAngle >= 120) dirTag = "R";
    else dirTag = "C";
    
    // Send: "DIST:123:C" (distance 123cm, center)
    String msg = "DIST:" + String(dist) + ":" + dirTag;
    webSocket.broadcastTXT(msg);
    
    // Emergency reflex: if something is within 15cm, stop immediately
    if (dist < 15 && dirTag == "C") {
      stopMotors();
      webSocket.broadcastTXT("BLOCKED");
      beepWarning();
    }
    // Proximity warning beep
    else if (dist < 100 && dirTag == "C") {
      // Single short beep for close objects
      digitalWrite(BUZZER_PIN, HIGH);
      delay(20);
      digitalWrite(BUZZER_PIN, LOW);
    }
  }
}
