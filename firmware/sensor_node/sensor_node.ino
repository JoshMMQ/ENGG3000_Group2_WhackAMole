// ESP32 ultrasonic UDP telemetry sender for ENGG3000 Whack-a-Mole.
//
// Arduino IDE setup:
// 1. Install/select an ESP32 board package.
// 2. Upload firmware/gateway_ap/gateway_ap.ino to the gateway ESP32.
// 3. For this sketch, set NODE_ID/SENSOR_ID below for box1 or box2.
// 4. Upload this sketch to each sensor ESP32 and open Serial Monitor at 115200 baud.
// 5. Connect the laptop to the WhackAMole Wi-Fi access point.
// 6. Start the Python receiver:
//    .venv/bin/python -m software.transport.udp_receiver

#include <WiFi.h>
#include <WiFiUdp.h>
#include "ultrasonic.cpp"

const char* WIFI_SSID = "WhackAMole";
const char* WIFI_PASSWORD = "esp123456789";

IPAddress UDP_BROADCAST_IP(192, 168, 4, 255);

const uint16_t LOCAL_UDP_PORT = 5006;
const uint16_t LAPTOP_PORT = 5005;
// Change these before uploading to the second sensor ESP32.
const char* NODE_ID = "box1";
const char* SENSOR_ID = "left";
const uint32_t SEND_INTERVAL_MS = 250;
const int BATTERY_MV = 3700;
const int WIFI_CONNECT_TIMEOUT_MS = 15000;

Ultrasonic left = Ultrasonic(32, 35, "Left", 40);

WiFiUDP udp;
uint32_t sequenceNumber = 0;
uint32_t lastSendMs = 0;

void setup() {
  Serial.begin(115200);
  delay(500);

  pinMode(left.trigPin, OUTPUT);
  pinMode(left.echoPin, INPUT);
  connectToGateway();
  udp.begin(LOCAL_UDP_PORT);
}

void loop() {
  if (WiFi.status() != WL_CONNECTED) {
    connectToGateway();
  }

  const uint32_t nowMs = millis();
  if (nowMs - lastSendMs >= SEND_INTERVAL_MS) {
    lastSendMs = nowMs;
    sendTelemetry(nowMs);
  }
}

void connectToGateway() {
  Serial.print("Connecting sensor node to gateway Wi-Fi: ");
  Serial.println(WIFI_SSID);

  WiFi.mode(WIFI_STA);
  WiFi.begin(WIFI_SSID, WIFI_PASSWORD);

  const uint32_t startedMs = millis();
  while (WiFi.status() != WL_CONNECTED) {
    delay(250);
    Serial.print(".");
    if (millis() - startedMs >= WIFI_CONNECT_TIMEOUT_MS) {
      Serial.println("\nFailed to connect to gateway. Restarting...");
      delay(1000);
      ESP.restart();
    }
  }

  Serial.print("\nConnected. Node IP: ");
  Serial.println(WiFi.localIP());
  Serial.print("Sending UDP telemetry broadcast to ");
  Serial.print(UDP_BROADCAST_IP);
  Serial.print(":");
  Serial.println(LAPTOP_PORT);
}

void sendTelemetry(uint32_t nowMs) {
  const float distanceCm = left.detectPlayer();
  const bool valid = distanceCm > 0.0f;
  const int distanceMm = valid ? static_cast<int>(round(distanceCm * 10.0f)) : 0;
  const String payload = buildTelemetryPayload(sequenceNumber, nowMs, distanceMm, valid);

  udp.beginPacket(UDP_BROADCAST_IP, LAPTOP_PORT);
  udp.print(payload);
  udp.endPacket();

  Serial.print("sent seq=");
  Serial.print(sequenceNumber);
  Serial.print(" distance_mm=");
  Serial.print(distanceMm);
  Serial.print(" valid=");
  Serial.print(valid ? "true" : "false");
  Serial.print(" payload=");
  Serial.println(payload);

  sequenceNumber++;
}

String buildTelemetryPayload(uint32_t sequence, uint32_t sentMs, int distanceMm, bool valid) {
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
  if (valid) {
    payload += distanceMm;
  } else {
    payload += "null";
  }
  payload += ",";
  payload += "\"valid\":";
  payload += valid ? "true" : "false";
  payload += "}],";
  payload += "\"battery_mv\":";
  payload += BATTERY_MV;
  payload += ",";
  payload += "\"status\":\"ok\"";
  payload += "}";
  return payload;
}
