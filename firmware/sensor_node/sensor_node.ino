// ESP32 fake UDP telemetry sender for ENGG3000 Whack-a-Mole.
//
// Arduino IDE setup:
// 1. Install/select an ESP32 board package.
// 2. Upload this sketch and open Serial Monitor at 115200 baud.
// 3. Connect the laptop to the ESP32 Wi-Fi access point below.
// 4. Start the Python receiver:
//    .venv/bin/python -m software.transport.udp_receiver

#include <WiFi.h>
#include <WiFiUdp.h>

const char* AP_SSID = "WhackAMole-team2-ESP32";
const char* AP_PASSWORD = "esp123456789";

IPAddress AP_IP(192, 168, 4, 1);
IPAddress AP_GATEWAY(192, 168, 4, 1);
IPAddress AP_SUBNET(255, 255, 255, 0);
IPAddress UDP_BROADCAST_IP(192, 168, 4, 255);

const uint16_t LOCAL_UDP_PORT = 5006;
const uint16_t LAPTOP_PORT = 5005;
const char* NODE_ID = "esp32_01";
const char* SENSOR_ID = "simulated";
const uint32_t SEND_INTERVAL_MS = 250;
const int BATTERY_MV = 3700;

WiFiUDP udp;
uint32_t sequenceNumber = 0;
uint32_t lastSendMs = 0;

void setup() {
  Serial.begin(115200);
  delay(500);

  startAccessPoint();
}

void loop() {
  const uint32_t nowMs = millis();
  if (nowMs - lastSendMs >= SEND_INTERVAL_MS) {
    lastSendMs = nowMs;
    sendTelemetry(nowMs);
  }
}

void startAccessPoint() {
  Serial.print("Starting ESP32 access point: ");
  Serial.println(AP_SSID);

  WiFi.mode(WIFI_AP);
  WiFi.softAPConfig(AP_IP, AP_GATEWAY, AP_SUBNET);

  const bool started = WiFi.softAP(AP_SSID, AP_PASSWORD);
  if (!started) {
    Serial.println("Failed to start access point. Restarting...");
    delay(1000);
    ESP.restart();
  }

  udp.begin(LOCAL_UDP_PORT);

  Serial.print("Access point started. ESP32 AP IP: ");
  Serial.println(WiFi.softAPIP());
  Serial.print("Laptop should connect to SSID: ");
  Serial.println(AP_SSID);
  Serial.print("Sending UDP telemetry broadcast to ");
  Serial.print(UDP_BROADCAST_IP);
  Serial.print(":");
  Serial.println(LAPTOP_PORT);
}

void sendTelemetry(uint32_t nowMs) {
  const int distanceMm = simulatedDistanceMm(sequenceNumber);
  const String payload = buildTelemetryPayload(sequenceNumber, nowMs, distanceMm);

  udp.beginPacket(UDP_BROADCAST_IP, LAPTOP_PORT);
  udp.print(payload);
  udp.endPacket();

  Serial.print("sent seq=");
  Serial.print(sequenceNumber);
  Serial.print(" distance_mm=");
  Serial.print(distanceMm);
  Serial.print(" payload=");
  Serial.println(payload);

  sequenceNumber++;
}

int simulatedDistanceMm(uint32_t sequence) {
  const float phase = (2.0f * PI * static_cast<float>(sequence % 20)) / 20.0f;
  const float ratio = (sin(phase) + 1.0f) / 2.0f;
  return static_cast<int>(round(500.0f + ratio * 2000.0f));
}

String buildTelemetryPayload(uint32_t sequence, uint32_t sentMs, int distanceMm) {
  String payload = "{";
  payload += "\"v\":1,";
  payload += "\"node_id\":\"";
  payload += NODE_ID;
  payload += "\",";
  payload += "\"seq\":";
  payload += sequence;
  payload += ",";
  payload += "\"sent_ms\":";
  payload += sentMs;
  payload += ",";
  payload += "\"readings\":[{";
  payload += "\"sensor_id\":\"";
  payload += SENSOR_ID;
  payload += "\",";
  payload += "\"distance_mm\":";
  payload += distanceMm;
  payload += ",";
  payload += "\"valid\":true";
  payload += "}],";
  payload += "\"battery_mv\":";
  payload += BATTERY_MV;
  payload += ",";
  payload += "\"status\":\"ok\"";
  payload += "}";
  return payload;
}
