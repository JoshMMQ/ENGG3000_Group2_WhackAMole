// Three-ESP32 Version 3 scan host for ENGG3000 Whack-a-Mole.
//
// MVP topology:
//   this ESP32: S1 left RCWL-1601 + Wi-Fi/ESP-NOW coordinator
//   centre ESP32: S2 centre RCWL-1601 command-driven station
//   right ESP32: S3 right RCWL-1601 command-driven station
//
// S1 samples at 0 ms, S2 at 35 ms, and S3 at 70 ms. The host then emits one
// complete sensor_scan packet. S4 is deliberately absent. The 35 ms guard is a
// conservative prototype value and must be verified with physical RCWL-1601
// timing/cross-talk measurements before it is accepted.

#include <Arduino.h>
#include <WiFi.h>
#include <WiFiUdp.h>
#include <esp_idf_version.h>
#include <esp_now.h>

constexpr uint8_t TRIG_PIN = 32;
constexpr uint8_t ECHO_PIN = 35;
constexpr uint8_t WIFI_CHANNEL = 6;

constexpr unsigned long ECHO_TIMEOUT_US = 18000UL;
constexpr unsigned long SENSOR_SLOT_US = 35000UL;
constexpr unsigned long S2_TRIGGER_OFFSET_US = 35000UL;
constexpr unsigned long S3_TRIGGER_OFFSET_US = 70000UL;
constexpr unsigned long STATION_RESULT_TIMEOUT_US = 30000UL;
constexpr unsigned long SCAN_INTERVAL_US = 105000UL;

constexpr float SPEED_OF_SOUND_MM_PER_US = 0.343f;
constexpr float MIN_DISTANCE_MM = 20.0f;
constexpr float MAX_DISTANCE_MM = 3000.0f;
constexpr float CALIBRATION_OFFSET_MM = 0.0f;

constexpr uint8_t S1_INDEX = 1;
constexpr uint8_t S2_INDEX = 2;
constexpr uint8_t S3_INDEX = 3;

constexpr uint32_t COMMAND_MAGIC = 0x57414D33UL;  // "WAM3"
constexpr uint32_t RESULT_MAGIC = 0x57414D53UL;   // "WAMS"

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
  uint8_t targetSensorIndex;
};

struct __attribute__((packed)) MeasureResult {
  uint32_t magic;
  uint32_t cycleId;
  float distanceMm;
  uint32_t commandToSampleUs;
  uint8_t valid;
  uint8_t sensorIndex;
};

struct RangeSample {
  uint32_t sampleTimeUs;
  float distanceMm;
  bool valid;
};

static_assert(sizeof(MeasureCommand) == 9, "Unexpected command layout");
static_assert(sizeof(MeasureResult) == 18, "Unexpected result layout");

WiFiUDP udp;
portMUX_TYPE resultMux = portMUX_INITIALIZER_UNLOCKED;

MeasureResult receivedResults[4] = {};
volatile bool resultReady[4] = {false, false, false, false};

uint32_t cycleId = 0;
uint32_t nextCycleStartUs = 0;

RangeSample readLocalSensor();
RangeSample requestStation(uint8_t sensorIndex, uint32_t activeCycleId);
void configureNetwork();
void configureEspNow();
void runMeasurementCycle();
void waitForOffset(uint32_t cycleStartUs, uint32_t offsetUs);
void appendReading(String& payload, const char* sensorId, const RangeSample& sample);
void sendSensorScan(
    const RangeSample& s1,
    const RangeSample& s2,
    const RangeSample& s3);

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
  if (candidate.sensorIndex != S2_INDEX && candidate.sensorIndex != S3_INDEX) {
    return;
  }

  portENTER_CRITICAL(&resultMux);
  receivedResults[candidate.sensorIndex] = candidate;
  resultReady[candidate.sensorIndex] = true;
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
  Serial.println("V3 S1 left scan host ready");
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
    Serial.println("Unable to add ESP-NOW broadcast peer; restarting");
    delay(1000);
    ESP.restart();
  }
}

RangeSample readLocalSensor() {
  const uint32_t sampleTimeUs = micros();
  digitalWrite(TRIG_PIN, LOW);
  delayMicroseconds(2);
  digitalWrite(TRIG_PIN, HIGH);
  delayMicroseconds(10);
  digitalWrite(TRIG_PIN, LOW);

  const unsigned long echoDurationUs =
      pulseIn(ECHO_PIN, HIGH, ECHO_TIMEOUT_US);
  if (echoDurationUs == 0) {
    return {sampleTimeUs, 0.0f, false};
  }

  const float distanceMm =
      echoDurationUs * SPEED_OF_SOUND_MM_PER_US / 2.0f
      + CALIBRATION_OFFSET_MM;
  const bool valid =
      distanceMm >= MIN_DISTANCE_MM && distanceMm <= MAX_DISTANCE_MM;
  return {sampleTimeUs, distanceMm, valid};
}

RangeSample requestStation(uint8_t sensorIndex, uint32_t activeCycleId) {
  portENTER_CRITICAL(&resultMux);
  resultReady[sensorIndex] = false;
  portEXIT_CRITICAL(&resultMux);

  const MeasureCommand command = {
      COMMAND_MAGIC, activeCycleId, sensorIndex};
  const uint32_t commandSentUs = micros();
  const esp_err_t sendResult = esp_now_send(
      BROADCAST_ADDRESS,
      reinterpret_cast<const uint8_t*>(&command),
      sizeof(command));
  if (sendResult != ESP_OK) {
    return {commandSentUs, 0.0f, false};
  }

  const uint32_t waitStartedUs = micros();
  while (micros() - waitStartedUs < STATION_RESULT_TIMEOUT_US) {
    MeasureResult candidate = {};
    bool ready = false;

    portENTER_CRITICAL(&resultMux);
    if (resultReady[sensorIndex]) {
      candidate = receivedResults[sensorIndex];
      resultReady[sensorIndex] = false;
      ready = true;
    }
    portEXIT_CRITICAL(&resultMux);

    if (
        ready
        && candidate.cycleId == activeCycleId
        && candidate.sensorIndex == sensorIndex) {
      return {
          commandSentUs + candidate.commandToSampleUs,
          candidate.distanceMm,
          candidate.valid != 0};
    }
    delay(1);
  }

  return {commandSentUs, 0.0f, false};
}

void waitForOffset(uint32_t cycleStartUs, uint32_t offsetUs) {
  while (micros() - cycleStartUs < offsetUs) {
    delayMicroseconds(100);
  }
}

void runMeasurementCycle() {
  const uint32_t cycleStartUs = micros();
  nextCycleStartUs = cycleStartUs + SCAN_INTERVAL_US;

  const RangeSample s1 = readLocalSensor();
  waitForOffset(cycleStartUs, S2_TRIGGER_OFFSET_US);
  const RangeSample s2 = requestStation(S2_INDEX, cycleId);
  waitForOffset(cycleStartUs, S3_TRIGGER_OFFSET_US);
  const RangeSample s3 = requestStation(S3_INDEX, cycleId);

  sendSensorScan(s1, s2, s3);
  cycleId++;
}

void appendReading(
    String& payload,
    const char* sensorId,
    const RangeSample& sample) {
  payload += "{\"sensor_id\":\"";
  payload += sensorId;
  payload += "\",\"distance_mm\":";
  if (sample.valid) {
    payload += String(sample.distanceMm, 1);
  } else {
    payload += "null";
  }
  payload += ",\"valid\":";
  payload += sample.valid ? "true" : "false";
  payload += ",\"sample_time_ms\":";
  payload += sample.sampleTimeUs / 1000UL;
  payload += "}";
}

void sendSensorScan(
    const RangeSample& s1,
    const RangeSample& s2,
    const RangeSample& s3) {
  String payload;
  payload.reserve(420);
  payload += "{\"version\":3,\"type\":\"sensor_scan\",\"cycle_id\":";
  payload += cycleId;
  payload += ",\"readings\":[";
  appendReading(payload, "s1", s1);
  payload += ",";
  appendReading(payload, "s2", s2);
  payload += ",";
  appendReading(payload, "s3", s3);
  payload += "]}";

  udp.beginPacket(UDP_BROADCAST_IP, LAPTOP_UDP_PORT);
  udp.print(payload);
  udp.endPacket();
  Serial.println(payload);
}
