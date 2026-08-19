// Command-driven RIGHT ESP32 station for ENGG3000 Whack-a-Mole.
//
// Upload this sketch to the ESP32 connected to the right HC-SR04. The sensor
// does not ping autonomously. It waits for a cycle command from the left host,
// measures once, and returns the result over ESP-NOW. This prevents ultrasonic
// overlap and gives both ranges the same cycle_id.

#include <Arduino.h>
#include <WiFi.h>
#include <esp_idf_version.h>
#include <esp_now.h>
#include <esp_wifi.h>

constexpr uint8_t TRIG_PIN = 32;
constexpr uint8_t ECHO_PIN = 35;
constexpr uint8_t WIFI_CHANNEL = 6;

constexpr unsigned long ECHO_TIMEOUT_US = 18000UL;
constexpr float SPEED_OF_SOUND_MM_PER_US = 0.343f;
constexpr float MIN_DISTANCE_MM = 20.0f;
// The footprint needs at most about 2421 mm in plan view. Keep 3000 mm here
// for measurement/setup tolerance; the laptop rejects out-of-footprint pairs.
constexpr float MAX_DISTANCE_MM = 3000.0f;
constexpr float CALIBRATION_OFFSET_MM = 0.0f;

constexpr uint32_t COMMAND_MAGIC = 0x57414D43UL;  // "WAMC"
constexpr uint32_t RESULT_MAGIC = 0x57414D52UL;   // "WAMR"

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

struct PendingCommand {
  uint32_t cycleId;
  uint32_t receivedAtUs;
};

static_assert(sizeof(MeasureCommand) == 8, "Unexpected command layout");
static_assert(sizeof(MeasureResult) == 17, "Unexpected result layout");

portMUX_TYPE commandMux = portMUX_INITIALIZER_UNLOCKED;
PendingCommand pendingCommand = {};
volatile bool commandReady = false;

RangeSample readRightSensor();
void configureEspNow();
void processCommand(const PendingCommand& command);

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
  if (length != sizeof(MeasureCommand)) {
    return;
  }

  MeasureCommand command;
  memcpy(&command, data, sizeof(command));
  if (command.magic != COMMAND_MAGIC) {
    return;
  }

  const PendingCommand candidate = {command.cycleId, micros()};
  portENTER_CRITICAL(&commandMux);
  if (!commandReady) {
    pendingCommand = candidate;
    commandReady = true;
  }
  portEXIT_CRITICAL(&commandMux);
}

void setup() {
  Serial.begin(115200);
  pinMode(TRIG_PIN, OUTPUT);
  pinMode(ECHO_PIN, INPUT);
  digitalWrite(TRIG_PIN, LOW);
  delay(500);

  configureEspNow();
  Serial.println("V2 right command-driven station ready");
}

void loop() {
  PendingCommand command;
  bool ready = false;

  portENTER_CRITICAL(&commandMux);
  if (commandReady) {
    command = pendingCommand;
    commandReady = false;
    ready = true;
  }
  portEXIT_CRITICAL(&commandMux);

  if (ready) {
    processCommand(command);
  } else {
    delay(1);
  }
}

void configureEspNow() {
  WiFi.mode(WIFI_STA);
  WiFi.setSleep(false);
  WiFi.disconnect();
  if (esp_wifi_set_channel(WIFI_CHANNEL, WIFI_SECOND_CHAN_NONE) != ESP_OK) {
    Serial.println("Unable to select ESP-NOW channel; restarting");
    delay(1000);
    ESP.restart();
  }

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

RangeSample readRightSensor() {
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

void processCommand(const PendingCommand& command) {
  const RangeSample sample = readRightSensor();
  const MeasureResult result = {
      RESULT_MAGIC,
      command.cycleId,
      sample.distanceMm,
      sample.sampleUs - command.receivedAtUs,
      sample.valid ? static_cast<uint8_t>(1) : static_cast<uint8_t>(0)};

  const esp_err_t sendResult = esp_now_send(
      BROADCAST_ADDRESS,
      reinterpret_cast<const uint8_t*>(&result),
      sizeof(result));

  Serial.print("cycle_id=");
  Serial.print(command.cycleId);
  Serial.print(" distance_mm=");
  if (sample.valid) {
    Serial.print(sample.distanceMm, 1);
  } else {
    Serial.print("null");
  }
  Serial.print(" valid=");
  Serial.print(sample.valid ? "true" : "false");
  Serial.print(" esp_now_send=");
  Serial.println(sendResult == ESP_OK ? "ok" : "failed");
}
