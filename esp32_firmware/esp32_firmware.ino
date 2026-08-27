// ============================================================
// ESP32 WebSocket Firmware — Delivery Bot v2.0
// ============================================================
// Upload via Arduino IDE. Libraries needed: "WebSockets" by
// Markus Sattler, "ESP32Servo". Board: ESP32 Dev Module
//
// Fixes: Watchdog, PWM speed control, deadtime, backward alias,
//        slow command, null-termination, disconnect handler

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

// --- SG90 Servo Pin ---
#define SERVO_PIN 18

// --- Safety ---
#define WATCHDOG_MS       1500   // Stop motors after 1.5s of silence
#define DEADTIME_MS       50     // Pause between direction reversals
#define MIN_CMD_INTERVAL  30     // Minimum ms between motor commands

WebSocketsServer webSocket = WebSocketsServer(81);
Servo cargoServo;

// --- State Tracking ---
unsigned long lastCommandTime = 0;
unsigned long lastMotorChange = 0;
bool clientConnected = false;

// Track current motor direction for deadtime logic
// 0=stopped, 1=forward, -1=reverse, 2=left, -2=right
int currentDirection = 0;

// ============================================================
// Motor Control (with PWM speed)
// ============================================================
void setMotorSpeed(int leftSpeed, int rightSpeed) {
  // ESP32 Core v3.x uses the pin directly instead of a channel
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
  // H2 Fix: Insert deadtime before reversing direction
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

// H3 Fix: Rolling turns — slow inner wheel instead of reversing
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
  
  // C1 Fix: Handle disconnection — immediate motor stop
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
    // M5 Fix: Safe null-termination
    payload[length] = '\0';
    String cmd = String((char*)payload);
    cmd.trim();
    
    unsigned long now = millis();
    lastCommandTime = now;
    
    if (cmd == "forward") {
      if (now - lastMotorChange >= MIN_CMD_INTERVAL) {
        driveForward();
        lastMotorChange = now;
      }
    }
    // C2 Fix: Accept both "reverse" and "backward"
    else if (cmd == "reverse" || cmd == "backward") {
      if (now - lastMotorChange >= MIN_CMD_INTERVAL) {
        driveReverse();
        lastMotorChange = now;
      }
    }
    // C3 Fix: Handle "slow" command with PWM
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
    }
    else if (cmd == "lock") {
      cargoServo.write(0);
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
  
  // PWM speed pins (ESP32 Core v3.x API)
  ledcAttach(ENA, PWM_FREQ, PWM_RESOLUTION);
  ledcAttach(ENB, PWM_FREQ, PWM_RESOLUTION);
  
  stopMotors();

  cargoServo.attach(SERVO_PIN);
  cargoServo.write(0);

  WiFi.softAP("DeliveryBot-WiFi", "password123");
  Serial.print("AP IP Address: ");
  Serial.println(WiFi.softAPIP());

  webSocket.begin();
  webSocket.onEvent(webSocketEvent);
  
  lastCommandTime = millis();

  Serial.println("--- WebSocket Server Started on :81 (v2.0) ---");
}

// ============================================================
// Main Loop
// ============================================================
void loop() {
  webSocket.loop();
  
  // C1 Fix: Watchdog — stop motors if no command received recently
  if (clientConnected && (millis() - lastCommandTime > WATCHDOG_MS)) {
    stopMotors();
    Serial.println("WATCHDOG: No command for 1.5s — MOTORS STOPPED");
    lastCommandTime = millis();
  }
}

