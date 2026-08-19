// Two-board V2 range-pair host for ENGG3000 Whack-a-Mole.
//
// Upload this sketch to the LEFT ESP32 (the board connected to the left
// HC-SR04). It performs four jobs:
//   1. creates the WhackAMole Wi-Fi network for the laptop;
//   2. measures the left sensor;
//   3. commands the right ESP32 over ESP-NOW 35 ms later;
//   4. broadcasts one synchronized V2 range_pair to UDP port 5005.
//
// Upload firmware/range_station_right/range_station_right.ino to the right
// ESP32 first. Connect the laptop to Wi-Fi WhackAMole / esp123456789, then run:
//   .venv/bin/python -m software.game.main --input udp

#include <Arduino.h>
#include <WiFi.h>
#include <WiFiUdp.h>
#include <esp_idf_version.h>
#include <esp_now.h>
#include <esp_wifi.h>

constexpr uint8_t TRIG_PIN = 32;
constexpr uint8_t ECHO_PIN = 35;
constexpr uint8_t WIFI_CHANNEL = 6;

constexpr unsigned long ECHO_TIMEOUT_US = 18000UL;
constexpr unsigned long RIGHT_TRIGGER_OFFSET_US = 35000UL;
constexpr unsigned long RIGHT_RESULT_TIMEOUT_US = 30000UL;
constexpr unsigned long CYCLE_INTERVAL_US = 70000UL;

constexpr float SPEED_OF_SOUND_MM_PER_US = 0.343f;
constexpr float MIN_DISTANCE_MM = 20.0f;
// The footprint needs at most about 2421 mm in plan view. Keep 3000 mm here
// for measurement/setup tolerance; the laptop rejects out-of-footprint pairs.
constexpr float MAX_DISTANCE_MM = 3000.0f;
constexpr float CALIBRATION_OFFSET_MM = 0.0f;

constexpr uint32_t COMMAND_MAGIC = 0x57414D43UL;  // "WAMC"
constexpr uint32_t RESULT_MAGIC = 0x57414D52UL;   // "WAMR"

const char* AP_SSID = "WhackAMole";
const char* AP_PASSWORD = "esp123456789";

IPAddress AP_IP(192, 168, 4, 1);
IPAddress AP_GATEWAY(192, 168, 4, 1);
IPAddress AP_SUBNET(255, 255, 255, 0);
IPAddress UDP_BROADCAST_IP(192, 168, 4, 255);

constexpr uint16_t LOCAL_UDP_PORT = 5006;
constexpr uint16_t LAPTOP_UDP_PORT = 5005;

const uint8_t BROADCAST_ADDRESS[] = {
    0xFF, 0xFF, 0xFF, 0xFF, 0xFF, 0xFF};

struct __attribute__((packed)) MeasureCommand {
  uint32_t magic;
  uint32_t cycleId;
};

struct __attribute__((packed)) MeasureResult {
  uint32_t magic;
  uint32_t cycleId;
  float distanceMm;
  uint32_t commandToSampleUs;
  uint8_t valid;
};

struct RangeSample {
  uint32_t sampleUs;
  float distanceMm;
  bool valid;
};

static_assert(sizeof(MeasureCommand) == 8, "Unexpected command layout");
static_assert(sizeof(MeasureResult) == 17, "Unexpected result layout");

WiFiUDP udp;
portMUX_TYPE resultMux = portMUX_INITIALIZER_UNLOCKED;

MeasureResult receivedResult = {};
volatile bool resultReady = false;

uint32_t cycleId = 0;
uint32_t nextCycleStartUs = 0;

RangeSample readLeftSensor();
void configureNetwork();
void configureEspNow();
void runMeasurementCycle();
void sendRangePair(
    const RangeSample& left,
    const MeasureResult* right,
    float pairSkewMs);

#if ESP_IDF_VERSION_MAJOR >= 5
void onEspNowReceived(
    const esp_now_recv_info_t* info,
    const uint8_t* data,
    int length) {
  (void)info;
#else
void onEspNowReceived(
    const uint8_t* senderMac,
    const uint8_t* data,
    int length) {
  (void)senderMac;
#endif
  if (length != sizeof(MeasureResult)) {
    return;
  }

  MeasureResult candidate;
  memcpy(&candidate, data, sizeof(candidate));
  if (candidate.magic != RESULT_MAGIC) {
    return;
  }

  portENTER_CRITICAL(&resultMux);
  receivedResult = candidate;
  resultReady = true;
  portEXIT_CRITICAL(&resultMux);
}

void setup() {
  Serial.begin(115200);
  pinMode(TRIG_PIN, OUTPUT);
  pinMode(ECHO_PIN, INPUT);
  digitalWrite(TRIG_PIN, LOW);
  delay(500);

  configureNetwork();
  configureEspNow();
  udp.begin(LOCAL_UDP_PORT);

  nextCycleStartUs = micros();
  Serial.println("V2 left range-pair host ready");
}

void loop() {
  const uint32_t nowUs = micros();
  if (static_cast<int32_t>(nowUs - nextCycleStartUs) < 0) {
    delay(1);
    return;
  }

  runMeasurementCycle();
}

void configureNetwork() {
  WiFi.mode(WIFI_AP_STA);
  WiFi.setSleep(false);
  WiFi.softAPConfig(AP_IP, AP_GATEWAY, AP_SUBNET);

  if (!WiFi.softAP(AP_SSID, AP_PASSWORD, WIFI_CHANNEL, false, 1)) {
    Serial.println("Failed to start WhackAMole access point; restarting");
    delay(1000);
    ESP.restart();
  }

  Serial.print("Laptop Wi-Fi: ");
  Serial.print(AP_SSID);
  Serial.print("  IP: ");
  Serial.print(WiFi.softAPIP());
  Serial.print("  channel: ");
  Serial.println(WIFI_CHANNEL);
}

void configureEspNow() {
  if (esp_now_init() != ESP_OK) {
    Serial.println("ESP-NOW initialization failed; restarting");
    delay(1000);
    ESP.restart();
  }

  esp_now_register_recv_cb(onEspNowReceived);

  esp_now_peer_info_t peer = {};
  memcpy(peer.peer_addr, BROADCAST_ADDRESS, sizeof(BROADCAST_ADDRESS));
  peer.channel = WIFI_CHANNEL;
  peer.ifidx = WIFI_IF_STA;
  peer.encrypt = false;

  const esp_err_t addResult = esp_now_is_peer_exist(BROADCAST_ADDRESS)
      ? ESP_OK
      : esp_now_add_peer(&peer);
  if (addResult != ESP_OK) {
    Serial.print("Unable to add ESP-NOW broadcast peer: ");
    Serial.println(addResult);
    delay(1000);
    ESP.restart();
  }
}

RangeSample readLeftSensor() {
  const uint32_t sampleUs = micros();

  digitalWrite(TRIG_PIN, LOW);
  delayMicroseconds(2);
  digitalWrite(TRIG_PIN, HIGH);
  delayMicroseconds(10);
  digitalWrite(TRIG_PIN, LOW);

  const unsigned long echoDurationUs =
      pulseIn(ECHO_PIN, HIGH, ECHO_TIMEOUT_US);
  if (echoDurationUs == 0) {
    return {sampleUs, 0.0f, false};
  }

  const float distanceMm =
      echoDurationUs * SPEED_OF_SOUND_MM_PER_US / 2.0f
      + CALIBRATION_OFFSET_MM;
  const bool valid =
      distanceMm >= MIN_DISTANCE_MM && distanceMm <= MAX_DISTANCE_MM;
  return {sampleUs, distanceMm, valid};
}

void runMeasurementCycle() {
  const uint32_t cycleStartUs = micros();
  nextCycleStartUs = cycleStartUs + CYCLE_INTERVAL_US;

  const RangeSample left = readLeftSensor();
  while (micros() - cycleStartUs < RIGHT_TRIGGER_OFFSET_US) {
    delayMicroseconds(100);
  }

  portENTER_CRITICAL(&resultMux);
  resultReady = false;
  portEXIT_CRITICAL(&resultMux);

  const MeasureCommand command = {COMMAND_MAGIC, cycleId};
  const uint32_t commandSentUs = micros();
  const esp_err_t sendResult = esp_now_send(
      BROADCAST_ADDRESS,
      reinterpret_cast<const uint8_t*>(&command),
      sizeof(command));

  MeasureResult right = {};
  bool matchedResult = false;
  if (sendResult == ESP_OK) {
    const uint32_t waitStartedUs = micros();
    while (micros() - waitStartedUs < RIGHT_RESULT_TIMEOUT_US) {
      portENTER_CRITICAL(&resultMux);
      const bool ready = resultReady;
      if (ready) {
        right = receivedResult;
        resultReady = false;
      }
      portEXIT_CRITICAL(&resultMux);

      if (ready && right.cycleId == cycleId) {
        matchedResult = true;
        break;
      }
      delay(1);
    }
  }

  const float pairSkewMs = matchedResult
      ? (commandSentUs - left.sampleUs + right.commandToSampleUs) / 1000.0f
      : RIGHT_TRIGGER_OFFSET_US / 1000.0f;
  sendRangePair(left, matchedResult ? &right : nullptr, pairSkewMs);
  cycleId++;
}

void sendRangePair(
    const RangeSample& left,
    const MeasureResult* right,
    float pairSkewMs) {
  const bool rightValid = right != nullptr && right->valid != 0;

  String payload;
  payload.reserve(230);
  payload += "{\"version\":2,\"type\":\"range_pair\",\"cycle_id\":";
  payload += cycleId;
  payload += ",\"left_mm\":";
  if (left.valid) {
    payload += String(left.distanceMm, 1);
  } else {
    payload += "null";
  }
  payload += ",\"right_mm\":";
  if (rightValid) {
    payload += String(right->distanceMm, 1);
  } else {
    payload += "null";
  }
  payload += ",\"left_valid\":";
  payload += (left.valid ? "true" : "false");
  payload += ",\"right_valid\":";
  payload += (rightValid ? "true" : "false");
  payload += ",\"pair_skew_ms\":";
  payload += String(pairSkewMs, 2);
  payload += "}";

  udp.beginPacket(UDP_BROADCAST_IP, LAPTOP_UDP_PORT);
  udp.print(payload);
  udp.endPacket();

  Serial.println(payload);
}
