# Whack-a-Mole Full-body Game

This ENGG3000 project turns Whack-a-Mole into a full-body game. A player moves inside a 3 m × 3 m area, ultrasonic sensor nodes report the player's position wirelessly, and a Python/Pygame application maps that position to an on-screen hammer cursor.

The repository currently contains an integrated prototype: a 2D game, simulated and UDP-backed cursor input, a validated telemetry protocol, an ESP32 gateway, and ESP32 ultrasonic sensor-node firmware. Some product requirements remain planned; see [Current status](#current-status).

## System architecture

```text
RCWL-1601 sensor                    RCWL-1601 sensor
       │                                   │
ESP32 sensor node box1              ESP32 sensor node box2
  node=box1, sensor=left              node=box2, sensor=right
       └──────────── UDP broadcast ────────────┘
                         │
              ESP32 gateway Wi-Fi AP
               WhackAMole / 192.168.4.1
                         │
                  Windows laptop
          UDP receiver → position source → Pygame
```

The gateway provides a dedicated local Wi-Fi network. It does not measure distance or relay packets. Both sensor nodes join that network and broadcast telemetry to `192.168.4.255:5005`; the laptop joins the same network and listens directly.

## Quick start

Python 3.10 or later is recommended.

```bash
python -m venv .venv
```

Activate the environment on Windows:

```powershell
.venv\Scripts\Activate.ps1
python -m pip install -r requirements.txt
```

Or on Linux/macOS:

```bash
source .venv/bin/activate
python -m pip install -r requirements.txt
```

Run the game without hardware; simulated input is the default:

```bash
python -m software.game.main
```

Run it using versioned UDP telemetry on port `5005`:

```bash
python -m software.game.main --input udp
```

Controls:

- `Enter`, `Space`, or the on-screen button starts/restarts a game.
- `P` or the on-screen pause button pauses and resumes.
- `Esc` exits.
- `G` ends the active game early for development testing.

## Hardware setup

The current prototype hardware baseline is:

- three ESP32U/ESP32-compatible boards: one gateway and two sensor nodes;
- two RCWL-1601 ultrasonic sensors, one per current sensor node; the final number and placement remain subject to measured tracking evidence;
- an SG90 9G servo motor in the hardware plan;
- two sensor enclosures no larger than 100 × 100 × 50 mm;
- 3 × AA NiMH rechargeable cells, with more than one hour of operation and USB-A charging as product constraints.

The current firmware uses one ultrasonic sensor on GPIO `32` (trigger) and GPIO `35` (echo). Battery telemetry is currently the placeholder value `3700 mV`; battery measurement and servo control are not yet implemented.

For upload settings, node identities, network details, and an end-to-end test procedure, see [firmware/sensor_node/README.md](firmware/sensor_node/README.md).

## Telemetry protocol

The primary protocol is version 1 JSON over UDP. A typical datagram is:

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

Protocol decisions:

- millimetres are the wire-format distance unit;
- invalid readings use `"valid": false` and `"distance_mm": null`;
- `v` allows incompatible packet formats to be rejected explicitly;
- `node_id`, `sensor_id`, `seq`, and `sent_ms` support multiple nodes and diagnostics;
- malformed, unsupported, or internally inconsistent packets are dropped rather than used for gameplay.

Sensor nodes currently transmit every `250 ms` (4 Hz). The receiver binds all interfaces on UDP port `5005`. A legacy `box1,123.4` test format remains available on port `4210` with `--mode two-box`, but it is not the primary game protocol.

## Game behaviour

The implemented prototype uses:

- a resizable 900 × 900 starting window at 60 frames per second;
- a 3 × 3 grid of mole holes on a 2D playfield;
- one active mole that moves every 1.75 seconds using a repeatable random-looking sequence;
- a 60-second session, three starting lives, and pause time excluded from the timer;
- a circular hit-preview radius of 70 px at 900 × 900, scaled with the smaller window dimension;
- a coordinate system with `(0 m, 0 m)` at the top-left and `(3 m, 3 m)` at the bottom-right.

The game checks physical safety boundaries before clamping coordinates for display. Crossing the play-area boundary costs one life and enters a safety pause. Entering the screen-proximity zone at `0.50 m` or closer pauses play and shows a warning; the warning clears only beyond `0.60 m` to avoid rapid state changes at the threshold.

## Testing without hardware

Run the full automated suite:

```bash
python -m unittest discover -s testing -v
```

Exercise the rendering paths and exit immediately:

```bash
python -m software.game.main --smoke-test
```

Test the UDP pipeline in two terminals:

```bash
python -m software.transport.udp_receiver
```

```bash
python -m software.transport.mock_udp_sender --include-invalid
```

The mock sender generates deterministic distances from 500–2500 mm and can inject a malformed datagram to verify that the receiver drops bad input safely.

## Requirements and constraints

### Constraints

| ID | Agreed constraint |
|---|---|
| CON-01 | The approved play area is 3 m × 3 m. |
| CON-02 | No system components are placed inside the play area. |
| CON-03 | Each sensor enclosure is no larger than 100 × 100 × 50 mm. |
| CON-04 | The system uses no more than 3 × AA NiMH rechargeable cells and operates for at least one hour. |
| CON-05 | The battery system is rechargeable from a USB-A power source. |
| CON-06 | The project budget is $100. |
| CON-07 | The game is downloadable and installable on a Windows computer as a desktop application. |
| CON-08 | Supplied components are not directly altered. |
| SAF-01 | Audible and effective visual warnings activate when the player is within 50 cm of the screen. |

### Product requirements

“Implemented” means the behaviour exists in this repository; it does not imply final hardware validation.

| ID | Priority | Requirement | Current status |
|---|---|---|---|
| FR-01 | Must | Track the player's position over the approved 3 m × 3 m area. | Partial: coordinate model and one-axis UDP mapping exist; two-axis sensor fusion is pending. |
| FR-02 | Must | Transmit sensor data wirelessly to the Windows laptop or approved receiver. | Implemented in the ESP32/UDP prototype. |
| FR-03 | Must | Move the cursor from player movement without a handheld controller. | Implemented for simulated input and one-axis UDP input. |
| FR-04 | Must | Award a point only when the cursor reaches an active mole. | Partial: collision/highlight detection exists; score mutation is pending. |
| FR-05 | Must | Provide selectable difficulty levels with measurable differences. | Planned. |
| FR-06 | Must | Provide a calibration workflow before normal play. | Planned. |
| FR-07 | Must | Support ready, countdown, active, paused, tracking-lost, and finished states. | Partial: loading, title, playing, paused, safety-paused, screen-warning, and game-over states exist. Countdown and tracking-lost remain planned. |
| FR-08 | Must | Provide visible and audible hit, miss, warning, and session feedback. | Partial: visual UI/warnings exist; audio and complete hit/miss feedback are pending. |
| FR-09 | Must | Prevent invalid, stale, or missing sensor data from causing a score or unsafe cursor jump. | Partial: invalid/missing input is rejected and the last position is retained; stale-packet detection is pending. |
| FR-10 | Should | Record session score, level, duration, and selected quality data. | Planned. |
| FR-11 | Should | Present a 2D playfield while preserving verified gameplay rules. | Implemented as the selected presentation direction. |
| FR-12 | Could | Show a local session-best score. | Planned. |
| NFR-01 | Must | Make tracking accurate and responsive enough for fair gameplay. | Pending physical validation and calibration. |
| NFR-02 | Must | Remain stable through loss and recovery of one sensor node. | Partial: Wi-Fi reconnect and last-known-position behaviour exist; node freshness/fusion logic is pending. |
| NFR-03 | Must | Start on the assessment Windows laptop without a development environment. | Planned packaging work. |
| NFR-04 | Must | Produce repeatable evidence for accuracy, latency, packet quality, safety, runtime, and frame rate. | Partial: automated software tests exist; physical measurements and release evidence remain pending. |
| NFR-05 | Should | Separate transport, tracking, domain rules, and rendering. | Partial: transport and game modules are separate, but tracking/domain boundaries are not yet complete. |
| SAF-01 | Must | Activate audible and effective visual warnings within 50 cm of the screen. | Partial: visual warning and threshold logic exist; the audible hook is not implemented. |
| SAF-02 | Must | Pause scoring during a safety warning or tracking-lost state. | Partial: play pauses during current safety states; tracking-lost and scoring remain pending. |

### Provisional verification targets

These targets make qualitative requirements measurable, but still require tutor/Product Owner confirmation and physical evidence.

| Measure | Provisional target |
|---|---|
| End-to-end response | 95th-percentile movement-to-cursor response at or below 150 ms. |
| Tracking update | At least 10 valid position updates per second. |
| Position error | Median at or below 20 cm; 90th percentile at or below 30 cm. |
| Packet quality | At least 98% of expected packets received during a 10-minute normal-range test. |
| Visual performance | At least 30 FPS on the assessment Windows laptop. |
| Safety trigger | 10 of 10 measured entries into the 50 cm zone activate visual and audible warnings. |
| Runtime | Each final sensor enclosure completes a documented one-hour runtime test. |

## Current status

The repository is an integration prototype, not a completed product. The most important open work is:

- fuse `box1` and `box2` readings into a true two-dimensional position;
- raise or justify the current 4 Hz firmware telemetry rate against the provisional 10-valid-updates-per-second target;
- add packet freshness, per-node health, and tracking-lost behaviour;
- connect collision detection to scoring and miss/life rules;
- implement the audible warning output;
- add calibration, difficulty selection, session records, Windows packaging, and hardware validation;
- measure the real battery voltage and integrate the planned servo if it remains part of the final design.

Keeping these gaps explicit is a project decision: documentation should describe tested behaviour separately from target requirements.
