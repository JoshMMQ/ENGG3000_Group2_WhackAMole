# Legacy ESP32 Gateway And Independent Sensor-Node Firmware

This directory reproduces the superseded Version 1 network diagnostic. It is
not the current V2 gameplay architecture and its independently timed packets
must never be paired for triangulation, safety, or scoring.

The active two-board V2 path is:

- `firmware/range_pair_host/range_pair_host.ino` on the left/host ESP32;
- `firmware/range_station_right/range_station_right.ino` on the right ESP32;
- `docs/TWO_BOARD_V2_RANGE_PAIR.md` for the complete procedure.

This legacy network design uses three ESP32-compatible boards and one laptop:

```text
ESP32 #1  gateway access point (no ultrasonic sensor)
ESP32 #2  sensor node box1 / left
ESP32 #3  sensor node box2 / right
Laptop    joins the gateway Wi-Fi and runs the Python game or receiver
```

The gateway creates the network only. Sensor nodes broadcast directly to every client on the subnet, including the laptop.

## Gateway

Upload [gateway_ap.ino](../gateway_ap/gateway_ap.ino) to ESP32 #1.

Default development network:

```cpp
const char* AP_SSID = "WhackAMole";
const char* AP_PASSWORD = "esp123456789";
IPAddress AP_IP(192, 168, 4, 1);
```

The gateway uses a `/24` subnet and prints its connected-client count every five seconds at `115200` baud. If access-point startup fails, it restarts the ESP32.

These credentials are shared prototype credentials committed for repeatable team setup; change them if the system is used outside a controlled demonstration network, and make the same change in both sketches.

## Sensor nodes

Upload [sensor_node.ino](sensor_node.ino) to both sensor ESP32 boards. Before each upload, configure the identity constants.

ESP32 #2:

```cpp
const char* NODE_ID = "box1";
const char* SENSOR_ID = "left";
```

ESP32 #3:

```cpp
const char* NODE_ID = "box2";
const char* SENSOR_ID = "right";
```

Both use:

```cpp
const char* WIFI_SSID = "WhackAMole";
const char* WIFI_PASSWORD = "esp123456789";
IPAddress UDP_BROADCAST_IP(192, 168, 4, 255);

const uint16_t LOCAL_UDP_PORT = 5006;
const uint16_t LAPTOP_PORT = 5005;
const uint32_t SEND_INTERVAL_MS = 250;
```

The current ultrasonic wiring is:

| Signal | ESP32 GPIO |
|---|---:|
| Trigger | 32 |
| Echo | 35 |

Confirm that the selected ESP32 board and sensor interface provide safe electrical levels before connecting the echo pin. The repository records the selected sensor as an RCWL-1601, but wiring, voltage compatibility, range, and enclosure placement still require physical validation.

## Measurement behaviour

The ultrasonic helper:

1. sends a trigger pulse;
2. measures echo high time with `pulseIn()`;
3. calculates one-way distance as `(0.0343 × duration_us) / 2` centimetres;
4. returns a three-sample moving average;
5. converts centimetres to integer millimetres for telemetry.

A positive averaged result is marked valid. Invalid readings are sent as `distance_mm: null` with `valid: false`.

The moving-average buffer starts with three `100 cm` values, so early packets are biased toward 100 cm. Its smoothing latency and startup behaviour are prototype limitations that must be considered during calibration.

The current 250 ms send interval is 4 Hz, below the project's provisional target of 10 valid position updates per second. The interval, ultrasonic sampling schedule, and smoothing must be measured and tuned together rather than treating network transmit rate alone as tracking update rate.

## Version 1 packet format

Each node sends one JSON datagram every 250 ms:

```json
{
  "v": 1,
  "node_id": "box1",
  "seq": 42,
  "sent_ms": 10500,
  "readings": [
    {
      "sensor_id": "left",
      "distance_mm": 1230,
      "valid": true
    }
  ],
  "battery_mv": 3700,
  "status": "ok"
}
```

| Field | Meaning |
|---|---|
| `v` | Protocol version; the current laptop parser accepts only `1`. |
| `node_id` | Physical sender identity, currently `box1` or `box2`. |
| `seq` | Per-node sequence number starting at zero after boot. |
| `sent_ms` | Sender uptime from `millis()`, not wall-clock time. |
| `readings` | Non-empty list so the protocol can carry one or more named sensors. |
| `sensor_id` | Logical sensor identity, currently `left` or `right`. |
| `distance_mm` | Non-negative integer millimetres when valid; otherwise `null`. |
| `valid` | Boolean measurement validity flag. |
| `battery_mv` | Battery millivolts; currently a hard-coded `3700` placeholder. |
| `status` | Node status text; currently always `ok`. |

The identities, sequence, timestamp, battery, and status fields were chosen to support multi-node diagnostics and future freshness/health logic. Packet ordering and delivery are not guaranteed because the transport is UDP.

## End-to-end test

1. Upload `gateway_ap.ino` to ESP32 #1.
2. Open its Serial Monitor at `115200` baud and confirm that the access point starts at `192.168.4.1`.
3. Configure `box1` / `left`, upload `sensor_node.ino` to ESP32 #2, and inspect its Serial Monitor.
4. Configure `box2` / `right`, upload the same sketch to ESP32 #3, and inspect its Serial Monitor.
5. Connect the laptop to `WhackAMole` with password `esp123456789`.
6. From the repository root, start the diagnostic receiver:

   ```bash
   python -m software.transport.udp_receiver
   ```

7. Confirm that both nodes appear and their sequence numbers advance:

   ```text
   192.168.4.x:5006 node=box1 seq=0 sent_ms=... status=ok battery_mv=3700 readings=[left=1230mm valid=True]
   192.168.4.y:5006 node=box2 seq=0 sent_ms=... status=ok battery_mv=3700 readings=[right=1180mm valid=True]
   ```

8. Stop the receiver, then run the game with hardware input:

   ```bash
   python -m software.game.main --input udp
   ```

Only one valid reading is currently mapped to the horizontal axis; the vertical coordinate remains fixed at `1.5 m`. Receiving both nodes is therefore an integration test, not yet full two-dimensional tracking.

## Troubleshooting

- If a sensor node repeatedly restarts, verify the SSID/password and start the gateway first. Nodes restart after a 15-second connection timeout.
- If packets do not arrive, confirm the laptop is on the `WhackAMole` network and its firewall permits inbound UDP port `5005` on that network.
- If only one node appears, verify each uploaded sketch has a different `NODE_ID`/`SENSOR_ID` and inspect both serial logs.
- If the receiver reports `invalid packet dropped`, compare the serial payload with the schema above; the Python parser intentionally rejects malformed or unsupported input.
- If readings begin near 100 cm, remember that the three-sample average is initialised to 100 cm.
- Port `4210` and `--mode two-box` are retained only for the older `box1,123.4` laptop-hotspot test format. New integration should use JSON on port `5005`.
