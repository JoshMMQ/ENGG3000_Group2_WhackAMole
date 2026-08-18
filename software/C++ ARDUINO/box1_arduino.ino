/*
 * ESP32 - HC-SR04/RCWL-1601 Sensor + WiFi UDP Broadcast
 * --------------------------------------------------------
 * Reads the ultrasonic sensor (same logic as your existing
 * test sketch) and broadcasts the distance over UDP so the
 * laptop's Python game can pick it up.
 *
 * Run this same sketch on both boxes - just change BOX_ID.
 */

#include <WiFi.h>
#include <WiFiUdp.h>
#include "ultrasonic.cpp"

// ---------- WiFi config ----------
const char* SSID     = "CHINKHUSEL 5444";
const char* PASSWORD = "7h04*M36";

// ---------- Box identity ----------
const char* BOX_ID = "box1"; // change to "box2" on the other unit

// ---------- UDP config ----------
WiFiUDP udp;
const int UDP_PORT = 4210;               // must match the port Python listens on
const char* BROADCAST_IP = "255.255.255.255";

// ---------- Sensor pins ----------
// const int trigPin = 19;
// const int echoPin = 18;

Ultrasonic BOX_1 = Ultrasonic(32, 35, BOX_ID, 40);

// float duration, distance;

void setup() {
  Serial.begin(115200);
  pinMode(BOX_1.trigPin, OUTPUT);
  pinMode(BOX_1.echoPin, INPUT);

  // --- Connect to laptop hotspot ---
  Serial.print("[");
  Serial.print(BOX_ID);
  Serial.println("] Connecting to WiFi...");

  WiFi.mode(WIFI_STA);
  WiFi.begin(SSID, PASSWORD);

  while (WiFi.status() != WL_CONNECTED) {
    delay(300);
    Serial.print(".");
  }

  Serial.println();
  Serial.print("[");
  Serial.print(BOX_ID);
  Serial.print("] Connected. IP: ");
  Serial.println(WiFi.localIP());

  udp.begin(UDP_PORT); // not strictly needed just to send, but harmless to have open
}

void loop() {
  // --- Read sensor (same as your existing test code) ---
  float distance = BOX_1.detectPlayer()
  // digitalWrite(trigPin, LOW);
  // delayMicroseconds(2);
  // digitalWrite(trigPin, HIGH);
  // delayMicroseconds(10);
  // digitalWrite(trigPin, LOW);

  // duration = pulseIn(echoPin, HIGH, 25000); // added timeout so it doesn't hang forever
  // distance = (duration * 0.0343) / 2;

  // if (duration == 0) {
  //   Serial.println("No echo");
  // } else {
  //   Serial.print("Distance: ");
  //   Serial.println(distance);

    // --- Build a simple message and send over UDP ---
    // Format: box1,123.4
    String message = String(BOX_ID) + "," + String(distance);

    udp.beginPacket(BROADCAST_IP, UDP_PORT);
    udp.print(message);
    udp.endPacket();
  // }

  delay(100);
}
