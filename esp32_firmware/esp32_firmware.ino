/*
  =============================================================================
  DELIVERYBOT ESP32 HACKATHON FIRMWARE (DUAL-CORE & WIRELESS)
  Autonomous 4WD Skid-Steer Rover • Built-in Wi-Fi AP • TCP & Web Controller
  =============================================================================
  Target Board: ESP32 Dev Module / DOIT ESP32 DEVKIT V1
  Core 0: Wi-Fi Stack, Port 8765 TCP Server (API), Port 80 Web Controller
  Core 1: 20kHz Motor PWM, HC-SR04 Sonar Reflex, SG90 Servos, 1500ms Watchdog
  =============================================================================
*/

#include <WiFi.h>
#include <WiFiServer.h>
#include <WebServer.h>
#include <ESP32Servo.h>
#include <esp_arduino_version.h>

// =============================================================================
// 1. PIN DEFINITIONS (Playbook Safe Non-Strapping Pins)
// =============================================================================
#define PIN_ENA          25  // Left Motors Speed (LEDC PWM)
#define PIN_ENB          26  // Right Motors Speed (LEDC PWM)
#define PIN_IN1          27  // Left Motors Forward
#define PIN_IN2          14  // Left Motors Reverse
#define PIN_IN3          16  // Right Motors Forward
#define PIN_IN4          17  // Right Motors Reverse

#define SCAN_SERVO_PIN   18  // Sonar Pan/Scan Servo (Orange wire)
#define CARGO_SERVO_PIN  19  // Cargo Bay Latch Servo (Orange wire)

#define PIN_TRIG          4  // HC-SR04 Sonar Trigger Pulse
#define PIN_ECHO          5  // HC-SR04 Echo via 1k/2k Resistor Divider (3.33V)

#define PIN_BUZZER       23  // Warning Buzzer Signal (+)

// =============================================================================
// 2. SPEED & MOTION CONFIGURATION
// =============================================================================
#define SPEED_FULL       255
#define SPEED_SLOW       130
#define SPEED_DRIFT      255  // 100% torque to break static floor friction on turns
#define MAX_DIST         400

#define WATCHDOG_MS      1500  // Auto-stop motors if no command received for 1.5s
#define DEADTIME_MS        50  // Reversing shoot-through protection
#define MIN_CMD_INTERVAL   25  // Debounce rapid commands
#define BLOCKED_LOCKOUT_MS 500 // Lockout after collision reflex

#define SCAN_ANGLE_LEFT   45
#define SCAN_ANGLE_CENTER 90
#define SCAN_ANGLE_RIGHT  135
#define SERVO_SETTLE_MS  200

// =============================================================================
// 3. WIRELESS & NETWORK CONFIGURATION
// =============================================================================
// SoftAP Mode (Robot creates its own Wi-Fi Hotspot)
const char* AP_SSID = "DeliveryBot-AP";
const char* AP_PASS = "12345678"; // Min 8 chars for WPA2, or set to "" for open

// Optional Station Mode (Connect to home Wi-Fi or Phone Hotspot if available)
// Leave empty ("") if using SoftAP only
const char* STA_SSID = "";
const char* STA_PASS = "";

WiFiServer tcpServer(8765);  // Listens on 8765 for Python api.py
WiFiClient tcpClient;
WebServer  webServer(80);    // Listens on 80 for Smartphone Web Joystick

// FreeRTOS Inter-Core Queue (Core 0 Network -> Core 1 Motor Controller)
QueueHandle_t cmdQueue;
struct CommandMsg {
  char text[64];
};

// =============================================================================
// 4. HARDWARE STATE & SERVO OBJECTS
// =============================================================================
Servo cargoServo;
Servo scanServo;

volatile unsigned long lastCommandTime = 0;
volatile unsigned long lastMotorChange = 0;
volatile unsigned long lastDistSend = 0;
volatile unsigned long blockedUntil = 0;
volatile int currentDirection = 0; // 0=Stop, 1=Fwd, -1=Rev, 2=Left, -2=Right
volatile int targetForwardSpeed = SPEED_FULL;
volatile unsigned long lastBeepTime = 0;

volatile int currentScanAngle = SCAN_ANGLE_CENTER;
volatile unsigned long lastScanMove = 0;
volatile bool scanSettled = true;
volatile int lastMeasuredDist = 400;

// LEDC PWM Compatibility Macro (ESP32 Core 2.x & Core 3.x)
#if defined(ESP_ARDUINO_VERSION_MAJOR) && (ESP_ARDUINO_VERSION_MAJOR >= 3)
  #define PWM_ATTACH(pin, ch) ledcAttach(pin, 20000, 8)
  #define PWM_WRITE(pin, ch, val) ledcWrite(pin, constrain(val, 0, 255))
#else
  #define PWM_ATTACH(pin, ch) do { ledcSetup(ch, 20000, 8); ledcAttachPin(pin, ch); } while(0)
  #define PWM_WRITE(pin, ch, val) ledcWrite(ch, constrain(val, 0, 255))
#endif

// =============================================================================
// 5. MOTOR & ACTUATOR CONTROL PRIMITIVES
// =============================================================================
void setMotorSpeed(int leftSpeed, int rightSpeed) {
  PWM_WRITE(PIN_ENA, 0, leftSpeed);
  PWM_WRITE(PIN_ENB, 1, rightSpeed);
}

void stopMotors() {
  digitalWrite(PIN_IN1, LOW); digitalWrite(PIN_IN2, LOW);
  digitalWrite(PIN_IN3, LOW); digitalWrite(PIN_IN4, LOW);
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
  digitalWrite(PIN_IN1, HIGH); digitalWrite(PIN_IN2, LOW);
  digitalWrite(PIN_IN3, HIGH); digitalWrite(PIN_IN4, LOW);
  targetForwardSpeed = SPEED_FULL;
  setMotorSpeed(SPEED_FULL, SPEED_FULL);
  currentDirection = 1;
}

void driveForwardSlow() {
  safeDirectionChange(1);
  digitalWrite(PIN_IN1, HIGH); digitalWrite(PIN_IN2, LOW);
  digitalWrite(PIN_IN3, HIGH); digitalWrite(PIN_IN4, LOW);
  targetForwardSpeed = SPEED_SLOW;
  setMotorSpeed(SPEED_SLOW, SPEED_SLOW);
  currentDirection = 1;
}

void driveReverse() {
  safeDirectionChange(-1);
  digitalWrite(PIN_IN1, LOW);  digitalWrite(PIN_IN2, HIGH);
  digitalWrite(PIN_IN3, LOW);  digitalWrite(PIN_IN4, HIGH);
  setMotorSpeed(SPEED_FULL, SPEED_FULL);
  currentDirection = -1;
}

// Stationary Pivot Turn Left (Zero-radius spin)
void turnLeft() {
  safeDirectionChange(2);
  digitalWrite(PIN_IN1, LOW);  digitalWrite(PIN_IN2, HIGH);
  digitalWrite(PIN_IN3, HIGH); digitalWrite(PIN_IN4, LOW);
  setMotorSpeed(SPEED_DRIFT, SPEED_DRIFT);
  currentDirection = 2;
}

// Stationary Pivot Turn Right (Zero-radius spin)
void turnRight() {
  safeDirectionChange(-2);
  digitalWrite(PIN_IN1, HIGH); digitalWrite(PIN_IN2, LOW);
  digitalWrite(PIN_IN3, LOW);  digitalWrite(PIN_IN4, HIGH);
  setMotorSpeed(SPEED_DRIFT, SPEED_DRIFT);
  currentDirection = -2;
}

// Proportional Differential Steering (Smooth rolling curves)
void steerDifferential(int leftSpeed, int rightSpeed) {
  safeDirectionChange(1);
  digitalWrite(PIN_IN1, leftSpeed >= 0 ? HIGH : LOW);
  digitalWrite(PIN_IN2, leftSpeed >= 0 ? LOW : HIGH);
  digitalWrite(PIN_IN3, rightSpeed >= 0 ? HIGH : LOW);
  digitalWrite(PIN_IN4, rightSpeed >= 0 ? LOW : HIGH);
  setMotorSpeed(abs(leftSpeed), abs(rightSpeed));
  currentDirection = (leftSpeed >= 0 && rightSpeed >= 0) ? 1 : -1;
}

void curveLeft()   { steerDifferential(80, 255); }
void curveRight()  { steerDifferential(255, 80); }
void swingLeft()   { steerDifferential(0, 255); }
void swingRight()  { steerDifferential(255, 0); }

// =============================================================================
// 6. SENSORS & ALERTS
// =============================================================================
int measureDistance() {
  digitalWrite(PIN_TRIG, LOW);
  delayMicroseconds(2);
  digitalWrite(PIN_TRIG, HIGH);
  delayMicroseconds(10);
  digitalWrite(PIN_TRIG, LOW);

  long duration = pulseIn(PIN_ECHO, HIGH, 25000);
  if (duration == 0) return MAX_DIST;

  int dist = duration * 0.034 / 2;
  return constrain(dist, 0, MAX_DIST);
}

void beep(int durationMs) {
  digitalWrite(PIN_BUZZER, HIGH);
  delay(durationMs);
  digitalWrite(PIN_BUZZER, LOW);
}

void beepWarning() {
  beep(40);
  delay(40);
  beep(40);
}

// Broadcast telemetry line to both Serial (USB) and TCP Client (Wi-Fi)
void broadcastTelemetry(const String& line) {
  Serial.println(line);
  if (tcpClient && tcpClient.connected()) {
    tcpClient.println(line);
  }
}

// =============================================================================
// 7. COMMAND PARSER & DISPATCHER
// =============================================================================
void processCommand(String cmd) {
  cmd.trim();
  if (cmd.length() == 0) return;

  unsigned long now = millis();
  lastCommandTime = now;
  bool isBlocked = (now < blockedUntil);

  if (cmd == "forward") {
    if (isBlocked) return;
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
    if (isBlocked) return;
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
  else if (cmd == "curve_left") {
    if (isBlocked) return;
    if (now - lastMotorChange >= MIN_CMD_INTERVAL) {
      curveLeft();
      lastMotorChange = now;
    }
  }
  else if (cmd == "curve_right") {
    if (isBlocked) return;
    if (now - lastMotorChange >= MIN_CMD_INTERVAL) {
      curveRight();
      lastMotorChange = now;
    }
  }
  else if (cmd == "swing_left") {
    if (isBlocked) return;
    if (now - lastMotorChange >= MIN_CMD_INTERVAL) {
      swingLeft();
      lastMotorChange = now;
    }
  }
  else if (cmd == "swing_right") {
    if (isBlocked) return;
    if (now - lastMotorChange >= MIN_CMD_INTERVAL) {
      swingRight();
      lastMotorChange = now;
    }
  }
  else if (cmd.startsWith("steer:")) {
    if (isBlocked) return;
    if (now - lastMotorChange >= MIN_CMD_INTERVAL) {
      int firstColon = cmd.indexOf(':');
      int secondColon = cmd.indexOf(':', firstColon + 1);
      if (secondColon > 0) {
        int lSpeed = cmd.substring(firstColon + 1, secondColon).toInt();
        int rSpeed = cmd.substring(secondColon + 1).toInt();
        steerDifferential(lSpeed, rSpeed);
      } else {
        int bias = cmd.substring(firstColon + 1).toInt();
        int baseSpeed = SPEED_FULL - 35;
        int lSpeed = constrain(baseSpeed - bias, 0, 255);
        int rSpeed = constrain(baseSpeed + bias, 0, 255);
        steerDifferential(lSpeed, rSpeed);
      }
      lastMotorChange = now;
    }
  }
  else if (cmd == "stop") {
    stopMotors();
    lastMotorChange = now;
  }
  else if (cmd == "unlock") {
    cargoServo.write(90);
    broadcastTelemetry("ACK:unlock");
  }
  else if (cmd == "lock") {
    cargoServo.write(0);
    broadcastTelemetry("ACK:lock");
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
  else if (cmd == "sweep") {
    stopMotors();
    scanServo.write(SCAN_ANGLE_LEFT);
    delay(220);
    int dL = measureDistance();

    scanServo.write(SCAN_ANGLE_RIGHT);
    delay(280);
    int dR = measureDistance();

    scanServo.write(SCAN_ANGLE_CENTER);
    currentScanAngle = SCAN_ANGLE_CENTER;
    delay(180);
    int dC = measureDistance();

    broadcastTelemetry("SWEEP:" + String(dL) + ":" + String(dC) + ":" + String(dR));
  }
  else if (cmd == "beep") {
    beepWarning();
  }
  else if (cmd == "ping") {
    broadcastTelemetry("pong");
  }
}

// Queue a command safely from Core 0 network handlers into Core 1
void queueCommand(const String& cmdStr) {
  if (cmdQueue == NULL) return;
  CommandMsg msg;
  strncpy(msg.text, cmdStr.c_str(), sizeof(msg.text) - 1);
  msg.text[sizeof(msg.text) - 1] = '\0';
  xQueueSend(cmdQueue, &msg, 0);
}

// =============================================================================
// 8. ONBOARD WEB CONTROLLER (PROGMEM HTML5 UI)
// =============================================================================
const char INDEX_HTML[] PROGMEM = R"rawliteral(
<!DOCTYPE html>
<html>
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1, user-scalable=no">
  <title>DeliveryBot Remote</title>
  <style>
    * { box-sizing: border-box; touch-action: manipulation; -webkit-tap-highlight-color: transparent; }
    body { font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif; background: #0f172a; color: #f8fafc; margin: 0; padding: 16px; text-align: center; }
    h1 { font-size: 20px; margin: 6px 0; color: #38bdf8; letter-spacing: 0.5px; }
    .badge { display: inline-block; padding: 4px 10px; background: #1e293b; border-radius: 999px; font-size: 12px; color: #94a3b8; margin-bottom: 12px; border: 1px solid #334155; }
    .telemetry { display: flex; justify-content: space-around; background: #1e293b; border-radius: 12px; padding: 12px; margin-bottom: 16px; border: 1px solid #334155; }
    .telemetry-item { font-size: 12px; color: #94a3b8; }
    .telemetry-val { font-size: 20px; font-weight: 700; color: #38bdf8; display: block; margin-top: 4px; }
    .dpad { display: grid; grid-template-columns: repeat(3, 1fr); gap: 10px; max-width: 280px; margin: 0 auto 16px; }
    .btn { background: #1e293b; border: 2px solid #334155; color: #f8fafc; font-size: 20px; font-weight: bold; border-radius: 14px; padding: 18px 0; cursor: pointer; transition: all 0.1s; user-select: none; }
    .btn:active, .btn.pressed { background: #38bdf8; color: #0f172a; border-color: #38bdf8; transform: scale(0.96); }
    .btn-stop { background: #ef4444; border-color: #dc2626; color: white; }
    .btn-stop:active { background: #b91c1c; }
    .action-row { display: flex; gap: 10px; max-width: 280px; margin: 0 auto 12px; }
    .btn-action { flex: 1; padding: 12px; font-size: 13px; font-weight: 600; border-radius: 10px; background: #334155; border: none; color: white; cursor: pointer; }
    .btn-action:active { opacity: 0.8; }
    .btn-unlock { background: #10b981; }
    .btn-lock { background: #f59e0b; }
    .radar { font-size: 12px; color: #64748b; margin-top: 8px; }
  </style>
</head>
<body>
  <h1>⚡ DELIVERYBOT ESP32</h1>
  <div class="badge">Connected to AP • 192.168.4.1</div>
  <div class="telemetry">
    <div class="telemetry-item">SONAR DIST<span class="telemetry-val" id="distVal">-- cm</span></div>
    <div class="telemetry-item">RADAR<span class="telemetry-val" id="radarVal">CENTER</span></div>
    <div class="telemetry-item">LATCH<span class="telemetry-val" id="latchVal">LOCKED</span></div>
  </div>
  <div class="dpad">
    <div></div>
    <button class="btn" onmousedown="sendCmd('forward')" onmouseup="sendCmd('stop')" ontouchstart="sendCmd('forward');event.preventDefault();" ontouchend="sendCmd('stop');event.preventDefault();">▲</button>
    <div></div>
    <button class="btn" onmousedown="sendCmd('left')" onmouseup="sendCmd('stop')" ontouchstart="sendCmd('left');event.preventDefault();" ontouchend="sendCmd('stop');event.preventDefault();">◀</button>
    <button class="btn btn-stop" onclick="sendCmd('stop')">■</button>
    <button class="btn" onmousedown="sendCmd('right')" onmouseup="sendCmd('stop')" ontouchstart="sendCmd('right');event.preventDefault();" ontouchend="sendCmd('stop');event.preventDefault();">▶</button>
    <div></div>
    <button class="btn" onmousedown="sendCmd('reverse')" onmouseup="sendCmd('stop')" ontouchstart="sendCmd('reverse');event.preventDefault();" ontouchend="sendCmd('reverse');event.preventDefault();">▼</button>
    <div></div>
  </div>
  <div class="action-row">
    <button class="btn-action btn-unlock" onclick="sendCmd('unlock');document.getElementById('latchVal').innerText='OPEN';">🔓 UNLOCK</button>
    <button class="btn-action btn-lock" onclick="sendCmd('lock');document.getElementById('latchVal').innerText='LOCKED';">🔒 LOCK</button>
  </div>
  <div class="action-row">
    <button class="btn-action" onclick="sendCmd('sweep')">📡 RADAR SWEEP</button>
    <button class="btn-action" onclick="sendCmd('beep')">🔔 BEEP</button>
  </div>
  <div class="radar" id="statusLine">Autonomous Obstacle Avoidance Active</div>

  <script>
    function sendCmd(c) {
      fetch('/command?cmd=' + c, { cache: 'no-store' }).catch(function(){});
    }
    setInterval(function() {
      fetch('/status', { cache: 'no-store' })
        .then(function(r) { return r.json(); })
        .then(function(d) {
          if (d.dist !== undefined) {
            document.getElementById('distVal').innerText = d.dist + ' cm';
            if (d.dist < 18) {
              document.getElementById('distVal').style.color = '#ef4444';
            } else {
              document.getElementById('distVal').style.color = '#38bdf8';
            }
          }
        }).catch(function(){});
    }, 400);
  </script>
</body>
</html>
)rawliteral";

void handleWebRoot() {
  webServer.send_P(200, "text/html", INDEX_HTML);
}

void handleWebCommand() {
  if (webServer.hasArg("cmd")) {
    String cmd = webServer.arg("cmd");
    queueCommand(cmd);
    webServer.send(200, "application/json", "{\"status\":\"ok\",\"cmd\":\"" + cmd + "\"}");
  } else {
    webServer.send(400, "application/json", "{\"error\":\"Missing cmd arg\"}");
  }
}

void handleWebDrive() {
  if (webServer.hasArg("l") && webServer.hasArg("r")) {
    int l = webServer.arg("l").toInt();
    int r = webServer.arg("r").toInt();
    queueCommand("steer:" + String(l) + ":" + String(r));
    webServer.send(200, "application/json", "{\"status\":\"ok\"}");
  } else {
    webServer.send(400, "application/json", "{\"error\":\"Missing l or r\"}");
  }
}

void handleWebStatus() {
  String json = "{";
  json += "\"dist\":" + String(lastMeasuredDist) + ",";
  json += "\"dir\":" + String(currentDirection) + ",";
  json += "\"uptime\":" + String(millis() / 1000) + ",";
  json += "\"blocked\":" + String(millis() < blockedUntil ? 1 : 0);
  json += "}";
  webServer.send(200, "application/json", json);
}

// =============================================================================
// 9. CORE 0 FREE-RTOS TASK: NETWORKING & PROTOCOLS
// =============================================================================
void networkTask(void* parameter) {
  // 1. Setup Wi-Fi SoftAP
  WiFi.mode(WIFI_AP_STA);
  WiFi.softAP(AP_SSID, (AP_PASS && strlen(AP_PASS) >= 8) ? AP_PASS : NULL);
  Serial.print("📡 SoftAP Created: ");
  Serial.println(AP_SSID);
  Serial.print("🌐 SoftAP IP Address: ");
  Serial.println(WiFi.softAPIP());

  // 2. Connect to Station if configured
  if (STA_SSID && strlen(STA_SSID) > 0) {
    Serial.printf("Connecting to STA Wi-Fi '%s'...\n", STA_SSID);
    WiFi.begin(STA_SSID, STA_PASS);
    unsigned long start = millis();
    while (WiFi.status() != WL_CONNECTED && millis() - start < 5000) {
      vTaskDelay(100 / portTICK_PERIOD_MS);
    }
    if (WiFi.status() == WL_CONNECTED) {
      Serial.print("✅ Connected to STA. IP: ");
      Serial.println(WiFi.localIP());
    } else {
      Serial.println("⚠️ STA connection timed out. SoftAP remains active.");
    }
  }

  // 3. Start TCP Server (Port 8765)
  tcpServer.begin();
  tcpServer.setNoDelay(true);
  Serial.println("🚀 TCP Server listening on port 8765");

  // 4. Start HTTP WebServer (Port 80)
  webServer.on("/", HTTP_GET, handleWebRoot);
  webServer.on("/command", HTTP_GET, handleWebCommand);
  webServer.on("/drive", HTTP_GET, handleWebDrive);
  webServer.on("/status", HTTP_GET, handleWebStatus);
  webServer.begin();
  Serial.println("🌐 Web Dashboard ready on port 80");

  String tcpBuffer = "";

  while (true) {
    // A. Handle incoming TCP connections
    if (tcpServer.hasClient()) {
      if (!tcpClient || !tcpClient.connected()) {
        if (tcpClient) tcpClient.stop();
        tcpClient = tcpServer.available();
        tcpClient.setNoDelay(true);
        Serial.println("🤝 [TCP] Client connected (api.py / controller)");
        tcpClient.println("READY");
        tcpBuffer = "";
      } else {
        // Reject secondary connections to prevent contention
        WiFiClient rejected = tcpServer.available();
        rejected.stop();
      }
    }

    // B. Read from TCP Client
    if (tcpClient && tcpClient.connected()) {
      while (tcpClient.available()) {
        char c = tcpClient.read();
        if (c == '\n' || c == '\r') {
          if (tcpBuffer.length() > 0) {
            queueCommand(tcpBuffer);
            tcpBuffer = "";
          }
        } else {
          tcpBuffer += c;
          if (tcpBuffer.length() > 64) tcpBuffer = "";
        }
      }
    }

    // C. Handle HTTP WebServer requests
    webServer.handleClient();

    vTaskDelay(5 / portTICK_PERIOD_MS);
  }
}

// =============================================================================
// 10. SETUP & CORE 1 MAIN CONTROL LOOP
// =============================================================================
String serialInputBuffer = "";

void setup() {
  Serial.begin(115200);

  // Setup motor pins
  pinMode(PIN_IN1, OUTPUT); pinMode(PIN_IN2, OUTPUT);
  pinMode(PIN_IN3, OUTPUT); pinMode(PIN_IN4, OUTPUT);

  // Attach 20kHz PWM on ENA & ENB
  PWM_ATTACH(PIN_ENA, 0);
  PWM_ATTACH(PIN_ENB, 1);
  stopMotors();

  // Setup Servos
  cargoServo.attach(CARGO_SERVO_PIN);
  cargoServo.write(0); // 0° = Locked

  scanServo.attach(SCAN_SERVO_PIN);
  scanServo.write(SCAN_ANGLE_CENTER); // 90° = Center

  // Setup Sonar Pins
  pinMode(PIN_TRIG, OUTPUT);
  pinMode(PIN_ECHO, INPUT);

  // Setup Buzzer Pin
  pinMode(PIN_BUZZER, OUTPUT);
  digitalWrite(PIN_BUZZER, LOW);

  // Create inter-core command queue
  cmdQueue = xQueueCreate(20, sizeof(CommandMsg));

  // Boot melody
  beep(80);
  delay(80);
  beep(80);

  lastCommandTime = millis();

  // Launch Core 0 Network Task
  xTaskCreatePinnedToCore(
    networkTask,
    "NetworkTask",
    8192,
    NULL,
    1,
    NULL,
    0
  );

  Serial.println("READY");
}

void loop() {
  // 1. Process commands from Core 0 Queue (TCP / Web)
  CommandMsg qMsg;
  if (cmdQueue != NULL && xQueueReceive(cmdQueue, &qMsg, 0) == pdPASS) {
    processCommand(String(qMsg.text));
  }

  // 2. Process commands from USB Serial port
  while (Serial.available()) {
    char c = Serial.read();
    if (c == '\n' || c == '\r') {
      if (serialInputBuffer.length() > 0) {
        processCommand(serialInputBuffer);
        serialInputBuffer = "";
      }
    } else {
      serialInputBuffer += c;
      if (serialInputBuffer.length() > 64) {
        serialInputBuffer = "";
      }
    }
  }

  // 3. Hardware Watchdog: Auto-brake if command stream dies
  if (millis() - lastCommandTime > WATCHDOG_MS) {
    if (currentDirection != 0) {
      stopMotors();
    }
    lastCommandTime = millis();
  }

  // 4. Servo Settle Timer
  if (!scanSettled && (millis() - lastScanMove > SERVO_SETTLE_MS)) {
    scanSettled = true;
  }

  // 5. Ultrasonic Sampling & Collision Avoidance Reflex (10 Hz rate)
  if (scanSettled && (millis() - lastDistSend > 100)) {
    int dist = measureDistance();
    lastDistSend = millis();
    lastMeasuredDist = dist;

    String dirTag = (currentScanAngle <= 60) ? "L" : (currentScanAngle >= 120 ? "R" : "C");
    broadcastTelemetry("DIST:" + String(dist) + ":" + dirTag);

    // EMERGENCY REFLEX: Obstacle within 18cm ahead
    if (dist < 18 && dirTag == "C") {
      stopMotors();
      blockedUntil = millis() + BLOCKED_LOCKOUT_MS;
      broadcastTelemetry("BLOCKED");
      beepWarning();
    }
    // PROPORTIONAL BRAKING: Smoothly crawl between 18cm and 65cm
    else if (dist <= 65 && dirTag == "C" && currentDirection == 1) {
      int minCrawlSpeed = 85;
      int propSpeed = map(dist, 18, 65, minCrawlSpeed, targetForwardSpeed);
      propSpeed = constrain(propSpeed, minCrawlSpeed, targetForwardSpeed);
      setMotorSpeed(propSpeed, propSpeed);

      // Warning beep rate accelerates as obstacle closes
      if (dist < 35 && (millis() - lastBeepTime > ((unsigned long)dist * 18))) {
        digitalWrite(PIN_BUZZER, HIGH);
        delay(12);
        digitalWrite(PIN_BUZZER, LOW);
        lastBeepTime = millis();
      }
    }
    // CLEAR PATH: Resume target speed
    else if (dist > 65 && dirTag == "C" && currentDirection == 1) {
      setMotorSpeed(targetForwardSpeed, targetForwardSpeed);
    }
  }
}
