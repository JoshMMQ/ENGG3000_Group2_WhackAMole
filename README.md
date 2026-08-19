# ENGG3000 Whack-a-Mole

This repository contains the three-sensor Whack-a-Mole prototype. The retained
hardware architecture is:

```text
S1 left sensor + host ESP32
  ├─ measures S1 locally
  ├─ commands S2, then S3 over ESP-NOW
  ├─ assembles one Version 3 S1/S2/S3 scan
  └─ hosts the WhackAMole Wi-Fi network and broadcasts UDP to the laptop

S2 centre sensor + station ESP32 ── ESP-NOW response ──┐
S3 right sensor + station ESP32  ── ESP-NOW response ──┤
                                                       ▼
Laptop connected directly to S1 Wi-Fi ── UDP 5005 ── Pygame
```

There is no phone hotspot and no laptop sensor coordinator. S4 is unused.

## Current status

The software can:

- run the game with simulated movement;
- receive strict Version 3 scans containing exactly S1, S2, and S3;
- drive a demonstration cursor from those scans without blocking Pygame;
- inspect, mock, and capture scan packets; and
- enforce the three-firmware source contract with automated tests.

The live cursor uses a deliberately simple algorithm: a rolling median per
sensor, minimum-range sensor selection, two-scan switch confirmation, fixed
left/centre/right X targets, range-derived Y, and render-only interpolation.
This implementation is retained, but it is not yet physical proof of accuracy,
dead-zone safety, or nine-cell scoring.

## Setup

Python 3.12 is recommended.

```bash
python -m venv .venv
.venv/bin/python -m pip install -r requirements.txt
```

On Windows, use `.venv\Scripts\python.exe` instead of
`.venv/bin/python`.

## Run

Simulation:

```bash
.venv/bin/python -m software.game.main --input simulated
```

Physical S1-host scan input:

1. Power S2 and S3, then S1.
2. Connect the laptop to the `WhackAMole` Wi-Fi network created by S1.
3. Allow inbound UDP port 5005 in the laptop firewall.
4. Run:

```bash
.venv/bin/python -m software.game.main --input sensor-scan
```

Do not add `--enable-safety` to sensor-scan mode. Its raw winner-based cursor
has not been validated as safety logic.

## Hardware roles

| Device | Role |
|---|---|
| S1 / left ESP32 | Wi-Fi access point, ESP-NOW coordinator, local S1 acquisition, complete-scan assembly, UDP broadcaster |
| S2 / centre ESP32 | Measures only when an ESP-NOW command targets S2, then replies to S1 |
| S3 / right ESP32 | Measures only when an ESP-NOW command targets S3, then replies to S1 |
| Laptop | Joins S1 Wi-Fi, validates Version 3 scans, updates tracking/game state, and renders Pygame |
| S4 | Spare; absent from firmware, packets, and tracking |

The provisional cycle begins S1 at 0 ms, commands S2 at 35 ms, and commands S3
at 70 ms. Physical cross-talk and timing still need measurement.

## Important files

| Path | Purpose |
|---|---|
| `firmware/three_sensor_host_left/three_sensor_host_left.ino` | S1 host/AP/coordinator firmware |
| `firmware/three_sensor_station_centre/three_sensor_station_centre.ino` | S2 ESP-NOW station |
| `firmware/three_sensor_station_right/three_sensor_station_right.ino` | S3 ESP-NOW station |
| `software/game/main.py` | Game loop and input selection |
| `software/game/presentation_tracking.py` | Current Version 3 cursor tracker |
| `software/game/tracking_state.py` | Sensor-neutral tracking status/snapshot |
| `software/game/sensor_scan.py` | Immutable S1/S2/S3 scan domain model |
| `software/transport/sensor_scan_packet.py` | Strict Version 3 parser/encoder |
| `software/transport/network_config.py` | Shared UDP bind host and port |
| `software/transport/mock_sensor_scan_sender.py` | Hardware-free scan generator |
| `software/transport/sensor_scan_receiver.py` | Console packet diagnostic |
| `software/transport/sensor_scan_capture.py` | Non-overwriting CSV capture tool |
| `docs/architecture.md` | Detailed component and data-flow explanation |
| `docs/runbook.md` | Firmware, network, and verification procedure |

## Packet diagnostics

Receiver:

```bash
.venv/bin/python -m software.transport.sensor_scan_receiver --count 10
```

Mock sender, in a second terminal:

```bash
.venv/bin/python -m software.transport.mock_sensor_scan_sender --count 10
```

Known-distance capture:

```bash
.venv/bin/python -m software.transport.sensor_scan_capture \
  --sensor s2 \
  --known-distance-mm 500 \
  --count 100 \
  --run-label s2-flat-board-500mm \
  --output evidence/S2-500mm-raw.csv
```

## Verification

From the repository root:

```bash
.venv/bin/python -m unittest discover -s testing -v
.venv/bin/python -m compileall -q software testing
SDL_VIDEODRIVER=dummy .venv/bin/python -m software.game.main --smoke-test
```

Automated tests do not replace Arduino compilation, upload, sensor identity,
radio timing, calibration, coverage, latency, power, enclosure, or safety
evidence.

## Product geometry

- Screen wall: `y = 0`
- Dead zone: `0.00 <= y < 0.60 m`
- Playable area: `0.00 <= x <= 1.50 m`, `0.60 <= y <= 2.00 m`
- Safety clear threshold: `y >= 0.70 m`
- Cells are row-major: 1–3 near the screen, 4–6 middle, 7–9 rear

The formal product requirements remain in `docs/PROJECT_V2.md`.
