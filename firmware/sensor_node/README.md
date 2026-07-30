# ESP32 Sensor Node

This folder contains the Arduino IDE sketch for the fake ESP32 UDP telemetry sender.

## Current Sketch

`sensor_node.ino` starts an ESP32 Wi-Fi access point and broadcasts simulated distance packets to UDP port `5005`.

It does not require ultrasonic sensors yet.

## Access Point Details

Default values in `sensor_node.ino`:

```cpp
const char* AP_SSID = "WhackAMole-team2-ESP32";
const char* AP_PASSWORD = "whackamole123456789";
IPAddress AP_IP(192, 168, 4, 1);
IPAddress UDP_BROADCAST_IP(192, 168, 4, 255);
```

The laptop connects to the ESP32 network. The ESP32 broadcasts packets so the laptop IP does not need to be hard-coded.

## Test

1. Upload `sensor_node.ino` from Arduino IDE.
2. Open Serial Monitor at `115200` baud.
3. Connect the laptop Wi-Fi to `WhackAMole-ESP32` using password `whackamole123`.
4. Start the laptop receiver:

```bash
.venv/bin/python -m software.transport.udp_receiver
```

Expected laptop output includes:

```text
node=esp32_01 seq=0 sent_ms=... status=ok battery_mv=3700 readings=[simulated=1500mm valid=True]
```

If packets do not appear, check that the laptop firewall allows UDP port `5005` on the ESP32 Wi-Fi network.
