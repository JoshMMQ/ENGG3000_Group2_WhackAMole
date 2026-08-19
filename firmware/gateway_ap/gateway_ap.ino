// Dedicated ESP32 Wi-Fi access point for ENGG3000 Whack-a-Mole.
//
// Upload this sketch to the gateway ESP32. The laptop and sensor-node ESP32s
// connect to this network. Sensor nodes send UDP telemetry to 192.168.4.255:5005.

#include <WiFi.h>

const char* AP_SSID = "WhackAMole";
const char* AP_PASSWORD = "esp123456789";

IPAddress AP_IP(192, 168, 4, 1);
IPAddress AP_GATEWAY(192, 168, 4, 1);
IPAddress AP_SUBNET(255, 255, 255, 0);

const uint32_t STATUS_INTERVAL_MS = 5000;

uint32_t lastStatusMs = 0;

void setup() {
  Serial.begin(115200);
  delay(500);

  startAccessPoint();
}

void loop() {
  const uint32_t nowMs = millis();
  if (nowMs - lastStatusMs >= STATUS_INTERVAL_MS) {
    lastStatusMs = nowMs;
    Serial.print("Connected clients: ");
    Serial.println(WiFi.softAPgetStationNum());
  }
}

void startAccessPoint() {
  Serial.print("Starting Whack-a-Mole gateway AP: ");
  Serial.println(AP_SSID);

  WiFi.mode(WIFI_AP);
  WiFi.softAPConfig(AP_IP, AP_GATEWAY, AP_SUBNET);

  const bool started = WiFi.softAP(AP_SSID, AP_PASSWORD);
  if (!started) {
    Serial.println("Failed to start gateway AP. Restarting...");
    delay(1000);
    ESP.restart();
  }

  Serial.print("Gateway AP ready. IP: ");
  Serial.println(WiFi.softAPIP());
  Serial.print("SSID: ");
  Serial.println(AP_SSID);
  Serial.println("Laptop and sensor nodes should connect to this network.");
}
