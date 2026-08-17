#include <Arduino.h>

constexpr uint8_t TRIG_PIN = 32;
constexpr uint8_t ECHO_PIN = 35;

// The project maximum range is about 2.47 m. An 18 ms timeout permits
// approximately 3.1 m while preventing a missing echo from blocking forever.
constexpr unsigned long ECHO_TIMEOUT_US = 18000UL;
constexpr unsigned long SAMPLE_DELAY_MS = 70UL;

constexpr float SPEED_OF_SOUND_MM_PER_US = 0.343f;
constexpr float MIN_DISTANCE_MM = 20.0f;
constexpr float MAX_DISTANCE_MM = 3000.0f;

// Calibrate this independently from the right sensor.
constexpr float CALIBRATION_OFFSET_MM = 0.0f;

const char* NODE_ID = "box1";
const char* SENSOR_ID = "left";

struct RangeSample {
  unsigned long sampleUs;
  float distanceMm;
  bool valid;
};

RangeSample readSensor() {
  const unsigned long sampleUs = micros();

  digitalWrite(TRIG_PIN, LOW);
  delayMicroseconds(2);
  digitalWrite(TRIG_PIN, HIGH);
  delayMicroseconds(10);
  digitalWrite(TRIG_PIN, LOW);

  // This blocking measurement is for one-sensor-at-a-time bench testing only.
  const unsigned long echoDurationUs =
      pulseIn(ECHO_PIN, HIGH, ECHO_TIMEOUT_US);

  if (echoDurationUs == 0) {
    return {sampleUs, 0.0f, false};
  }

  float distanceMm =
      echoDurationUs * SPEED_OF_SOUND_MM_PER_US / 2.0f;
  distanceMm += CALIBRATION_OFFSET_MM;

  const bool valid =
      distanceMm >= MIN_DISTANCE_MM && distanceMm <= MAX_DISTANCE_MM;
  return {sampleUs, distanceMm, valid};
}

void printSample(const RangeSample& sample) {
  Serial.print("{\"node_id\":\"");
  Serial.print(NODE_ID);
  Serial.print("\",\"sensor_id\":\"");
  Serial.print(SENSOR_ID);
  Serial.print("\",\"distance_mm\":");

  if (sample.valid) {
    Serial.print(sample.distanceMm, 1);
  } else {
    Serial.print("null");
  }

  Serial.print(",\"valid\":");
  Serial.print(sample.valid ? "true" : "false");
  Serial.print(",\"sample_us\":");
  Serial.print(sample.sampleUs);
  Serial.println("}");
}

void setup() {
  Serial.begin(115200);

  pinMode(TRIG_PIN, OUTPUT);
  pinMode(ECHO_PIN, INPUT);
  digitalWrite(TRIG_PIN, LOW);

  delay(500);
  Serial.println("Left HC-SR04 ready");
}

void loop() {
  const RangeSample sample = readSensor();
  printSample(sample);
  delay(SAMPLE_DELAY_MS);
}
