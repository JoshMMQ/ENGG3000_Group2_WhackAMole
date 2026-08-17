# Whack-a-Mole Full-Body Game

This ENGG3000 project turns Whack-a-Mole into a full-body game. Ultrasound
tracks a player over a 1.50 m wide x 1.40 m deep playable area behind a 0.60 m
screen dead zone, and a Python/Pygame application maps the estimated position to
an on-screen hammer cursor.

The repository contains a working game, simulated input, a paired Version 2 UDP
tracking path, a software-only paired-range sender, a two-board ESP32 tracker,
and legacy bench diagnostics. That two-sensor path has demonstrated end-to-end
physical cursor movement and is now the migration baseline for an approved
three-sensor 3 x 3 cell tracker. Tracking quality, safety, power, enclosure,
coverage, and Windows release compliance are not yet accepted.

## Source of truth

The formal source is the 5 August 2026 Version 2.0 project brief. The later
Codex clarification approves the tracking architecture: use S1 left, S2 centre,
and S3 right to confirm one of nine logical cells; keep S4 spare and unused.
The clarification changes the implementation architecture but does not replace
the brief's product constraints. Their authority and facts are reconciled in
[docs/SOURCE_FACTS.md](docs/SOURCE_FACTS.md).

The physical 3 x 3 grid mentioned in the guide must not be confused with the
game's 3 x 3 arrangement of nine mole holes. The approved physical playable area
is 1.50 m x 1.40 m.

## Current tracker — migration baseline

```text
left HC-SR04 -> left ESP32 host ---- V2 UDP ----> Windows laptop
                         |                         validate + triangulate
                         |                         reject + filter + map
                         +---- ESP-NOW cycle ----> Pygame at 60 FPS
                                   |
                         right ESP32 -> right HC-SR04
```

The left ESP32 combines the wireless-host and left-sensor roles. It creates the
`WhackAMole` Wi-Fi network, owns `cycle_id`, measures the left range, commands
the right station 35 ms later, pairs the response, and sends one Version 2 UDP
datagram. The right station never free-runs in this mode.

The laptop owns packet validation, triangulation, impossible-geometry rejection,
post-triangulation position filtering, safety state, coordinate mapping, and
rendering. Sensor-model-specific HC-SR04 or RCWL-1601 behavior must remain in
firmware.

This path still uses exactly two active HC-SR04 sensors and two ESP32 boards. It
is kept working for regression and migration; it is not the approved target.

## Approved target tracker

The target uses three of the four available RCWL-1601 modules:

- S1 at the left, primarily associated with column 1;
- S2 at the centre, primarily associated with column 2;
- S3 at the right, primarily associated with column 3; and
- S4 as an unused spare, excluded from telemetry, classification, safety, and
  gameplay.

One complete scan contains valid, fresh S1/S2/S3 measurements from the same
cycle. The laptop calibrates and filters the readings, requires confidence and
hysteresis before confirming a column, classifies the selected depth into a row
with hysteresis, and exposes a row-major `PlayerCell` from 1 to 9. Raw `argmin`
and uncertain candidates must never reach gameplay. No servo is part of this
approved architecture.

For the MVP, three ESP32 boards are assigned: the S1 left board is also the scan
host, while dedicated S2 centre and S3 right boards respond to targeted ESP-NOW
commands. This source path is separate from the current two-board tracker. The
third board is additional to the two listed as supplied and must be included in
the BOM/budget; final standalone-box and wireless compliance still require
evidence. See [docs/THREE_ESP32_SENSOR_SCAN.md](docs/THREE_ESP32_SENSOR_SCAN.md).

## Quick start

Python 3.10 or later is recommended.

```bash
python -m venv .venv
```

On Windows PowerShell:

```powershell
.venv\Scripts\Activate.ps1
python -m pip install -r requirements.txt
python -m software.game.main
```

On Linux/macOS:

```bash
source .venv/bin/activate
python -m pip install -r requirements.txt
python -m software.game.main
```

Simulated input is the default. Run the paired physical/software UDP path with:

```bash
.venv/bin/python -m software.game.main --input udp
```

The temporary tracking-debug runtime defaults to safety gates disabled. It maps
the complete tracked depth `y = 0.00..2.00 m`, retains the previous cursor for
invalid/stale data, and does not pause or remove lives for tracking safety input.
Restore the approved V2 safety behavior for regression testing with:

```bash
.venv/bin/python -m software.game.main --input udp --enable-safety
```

This temporary default is not suitable for final safety acceptance.

Controls:

- `Enter`, `Space`, or the on-screen button starts/restarts a game.
- `P` or the on-screen pause button pauses and resumes.
- `Esc` exits.
- `G` ends the active game early for development testing.

## V2 geometry and safety

- Screen wall: `y = 0`.
- Complete tracked footprint: `0.00 <= x <= 1.50 m` and
  `0.00 <= y <= 2.00 m`.
- Dead zone: `0.00 <= y < 0.60 m`.
- Playable area: `0.00 <= x <= 1.50 m` and
  `0.60 <= y <= 2.00 m`.
- Initial acoustic centres: `(0.00, 0.10)` m and `(1.50, 0.10)` m until measured
  calibration replaces them.
- Software safety entry threshold: `y < 0.60 m`; clear threshold:
  `y >= 0.70 m` for hysteresis.

With `--enable-safety`, dead-zone and tracking-loss states retain the last
playable cursor and suppress active play. The visual warning path exists; the
audible warning function remains a stub and physical safety validation remains
outstanding.

## Current Version 2 packet

The current migration-baseline packet represents one time-matched left/right
cycle:

```json
{
  "version": 2,
  "type": "range_pair",
  "cycle_id": 42,
  "left_mm": 1318.4,
  "right_mm": 1281.7,
  "left_valid": true,
  "right_valid": true,
  "pair_skew_ms": 35.0
}
```

Distances are millimetres. The parser rejects malformed, invalid, excessive-skew,
duplicate/older, stale, impossible, and out-of-footprint input as appropriate.
The game never maps a single range directly to a screen axis.

Run a hardware-free live integration in two terminals:

```bash
.venv/bin/python -m software.game.main --input udp
```

```bash
.venv/bin/python -m software.transport.mock_range_pair_sender
```

The Version 1 `software.transport.mock_udp_sender`, `udp_receiver`,
`firmware/gateway_ap`, and `firmware/sensor_node` paths remain legacy regression
tools. They are not the active V2 gameplay path.

## Target Version 3 scan packet

The separate three-ESP32 MVP emits one strict packet containing exactly S1,
S2, and S3:

```json
{
  "version": 3,
  "type": "sensor_scan",
  "cycle_id": 42,
  "readings": [
    {"sensor_id": "s1", "distance_mm": 900.0, "valid": true, "sample_time_ms": 1000},
    {"sensor_id": "s2", "distance_mm": 1100.0, "valid": true, "sample_time_ms": 1035},
    {"sensor_id": "s3", "distance_mm": 1300.0, "valid": true, "sample_time_ms": 1070}
  ]
}
```

The parser, diagnostic receiver, mock sender, and three firmware sketches now
exist. They are not connected to Pygame or classification yet.

Terminal 1:

```bash
.venv/bin/python -m software.transport.sensor_scan_receiver --host 127.0.0.1
```

Terminal 2:

```bash
.venv/bin/python -m software.transport.mock_sensor_scan_sender
```

For controlled physical evidence, close the console receiver and capture a
stationary flat target with:

```bash
.venv/bin/python -m software.transport.sensor_scan_capture \
  --sensor s2 --known-distance-mm 500 --count 100 \
  --run-label s2-flat-board-500mm \
  --output evidence/S2-500mm-raw.csv
```

The tool refuses to overwrite an existing capture and prints validity, median,
the selected sensor's ground-truth error, range, cycle gaps, and duplicates.
Repeat at 500 mm and 1000 mm for S1, S2, and S3 before setting calibration
offsets.

## Hardware facts and constraints

The formal brief supplies 2 ESP32 boards, 2 antennas, 4 RCWL-1601 sensors,
2 battery packs containing 4 AA NiMH cells and a holder, perfboard, and
connectors. Three RCWL-1601 modules are assigned to the approved target and the
fourth is spare. The current bench instead uses the two supplied/available
ESP32 boards with two HC-SR04 modules for early integration.

Mandatory constraints include:

- every physical component remains within 0.50 m of the wall and outside the
  playable area;
- each sensor is a standalone box no larger than 100 mm x 100 mm x 50 mm;
- each box communicates wirelessly with the PC;
- each box runs for more than one hour with 4 x AA NiMH cells as its only power
  source;
- total project cost, including supplied parts, remains within AUD 100;
- supplied components receive no solder, adhesive, paint, or similar material;
- the game is downloadable and installable on a Windows laptop.

USB-A recharging is desirable but is explicitly not essential in the brief.

The current ordinary HC-SR04 bench arrangement uses temporary 3.3 V sensor
power with Echo connected directly to GPIO35. This is outside nominal HC-SR04
operation. Never move VCC to 5 V while Echo remains directly connected; a
verified protected Echo interface is required before calibration or final use.

See [docs/TWO_BOARD_V2_RANGE_PAIR.md](docs/TWO_BOARD_V2_RANGE_PAIR.md) for the
current migration-baseline procedure and
[docs/TWO_SENSOR_USB_BENCH.md](docs/TWO_SENSOR_USB_BENCH.md) for the separate
dual-USB diagnostic. Neither procedure implements the target centre sensor.

## Current game behavior

The prototype currently provides:

- a resizable 900 x 900 initial window rendered at 60 FPS;
- nine mole holes in a 3 x 3 on-screen layout;
- one timed active mole, hover/hit preview, a 60-second session, pause/resume,
  lives display, safety/tracking overlays, and game-over flow;
- simulated and Version 2 UDP position sources;
- rotating runtime diagnostics in `runtime-logs/game.log`.

Score mutation, difficulty selection, calibration UI, complete audible/visual
feedback, and a packaged Windows release remain incomplete.

## Verification

Run from the repository root:

```bash
.venv/bin/python -m unittest discover -s testing -v
.venv/bin/python -m compileall -q software testing
SDL_VIDEODRIVER=dummy .venv/bin/python -m software.game.main --smoke-test
```

The automated suite is software evidence only. The 14 August 2026 physical run
proved the end-to-end paired cursor path but accepted only 316 of 885 cycles
(35.7%), about five usable positions per second. It did not establish tracking
accuracy, full coverage, power life, enclosure compliance, or final safety.
See [docs/V1_1_CURRENT_IMPLEMENTATION_REPORT.md](docs/V1_1_CURRENT_IMPLEMENTATION_REPORT.md).

## Next migration gate

1. Compile and upload the separate S1-host, S2-centre, and S3-right sketches.
2. Physically verify three sequential, non-overlapping measurements per cycle;
   keep S4 absent and record scan timing/miss rate.
3. Review that evidence before adding calibration or filtering.
4. Add calibration, median filtering, confidence, and column hysteresis.
5. Add row thresholds/hysteresis and expose only a confirmed `PlayerCell`.
6. Integrate cells into gameplay, then restore and physically verify safety.
7. Validate full-cell coverage, latency, four-AA runtime, enclosures, budget,
   and Windows installation.
