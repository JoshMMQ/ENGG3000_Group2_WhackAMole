# ESP32 Gateway And Sensor Nodes

The firmware now uses three ESP32 boards:

```text
ESP32 #1: gateway access point
ESP32 #2: sensor node box1
ESP32 #3: sensor node box2
Laptop: connects to the gateway AP and runs the Python game or receiver
```

## Gateway ESP32

Upload:

```text
firmware/gateway_ap/gateway_ap.ino
```

Default gateway network:

```cpp
const char* AP_SSID = "WhackAMole";
const char* AP_PASSWORD = "esp123456789";
IPAddress AP_IP(192, 168, 4, 1);
```

The gateway only creates the Wi-Fi network. It does not need an ultrasonic sensor.

## Sensor ESP32 Nodes

Upload:

```text
firmware/sensor_node/sensor_node.ino
```

Before uploading to each sensor ESP32, set the node identity in `sensor_node.ino`.

For sensor ESP32 #2:

```cpp
const char* NODE_ID = "box1";
const char* SENSOR_ID = "left";
```

For sensor ESP32 #3:

```cpp
const char* NODE_ID = "box2";
const char* SENSOR_ID = "right";
```

Both sensor nodes connect to the gateway network:

```cpp
const char* WIFI_SSID = "WhackAMole";
const char* WIFI_PASSWORD = "esp123456789";
IPAddress UDP_BROADCAST_IP(192, 168, 4, 255);
```

They broadcast versioned JSON telemetry to UDP port `5005`.

## Packet Format

Expected receiver output:

```text
node=box1 seq=0 sent_ms=... status=ok battery_mv=3700 readings=[left=1230mm valid=True]
node=box2 seq=0 sent_ms=... status=ok battery_mv=3700 readings=[right=1180mm valid=True]
```

## Test

1. Upload `gateway_ap.ino` to ESP32 #1.
2. Open gateway Serial Monitor at `115200` baud and confirm the AP starts.
3. Set `NODE_ID = "box1"` and `SENSOR_ID = "left"` in `sensor_node.ino`.
4. Upload `sensor_node.ino` to ESP32 #2.
5. Set `NODE_ID = "box2"` and `SENSOR_ID = "right"` in `sensor_node.ino`.
6. Upload `sensor_node.ino` to ESP32 #3.
7. Connect the laptop Wi-Fi to `WhackAMole` using password `esp123456789`.
8. Start the laptop receiver:

```bash
.venv/bin/python -m software.transport.udp_receiver
```

9. Confirm packets arrive from both `box1` and `box2`.

If packets do not appear, check that the laptop firewall allows UDP port `5005` on the `WhackAMole` network.
