# Whack-a-Mole Full-Body Game

This ENGG3000 project turns Whack-a-Mole into a full-body game. Ultrasound
tracks a player over a 1.50 m wide x 1.40 m deep playable area behind a 0.60 m
screen dead zone, and a Python/Pygame application maps the estimated position to
an on-screen hammer cursor.

The repository contains a working game, simulated input, a paired Version 2 UDP
tracking path, a software-only paired-range sender, a two-board ESP32 Phase 1
implementation, and legacy bench diagnostics. End-to-end physical cursor
movement has been demonstrated, but tracking quality, safety, power, enclosure,
coverage, and Windows release compliance are not yet accepted.

## Source of truth

The formal source is the 5 August 2026 Version 2.0 project brief. The supplied
3-sensor tracking guide is a non-authoritative implementation proposal and does
not replace the brief or the accepted two-range architecture. Their facts and
conflicts are reconciled in [docs/SOURCE_FACTS.md](docs/SOURCE_FACTS.md).

The physical 3 x 3 grid mentioned in the guide must not be confused with the
game's 3 x 3 arrangement of nine mole holes. The approved physical playable area
is 1.50 m x 1.40 m.

## Current Phase 1 architecture

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

Phase 1 uses exactly one fixed HC-SR04 per side and no servo. It proves only the
central beam-overlap path. A servo or additional sensor is evidence-gated and
must not be added before the Phase 1 tests in
[docs/TRACKING_FEATURE.md](docs/TRACKING_FEATURE.md) pass.

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

## Version 2 packet

One host packet represents one time-matched left/right cycle:

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

## Hardware facts and constraints

The formal brief supplies 2 ESP32 boards, 2 antennas, 4 RCWL-1601 sensors,
2 battery packs containing 4 AA NiMH cells and a holder, perfboard, and
connectors. The current Phase 1 bench instead uses the two supplied/available
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
active physical procedure and [docs/TWO_SENSOR_USB_BENCH.md](docs/TWO_SENSOR_USB_BENCH.md)
for the separate dual-USB diagnostic.

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

## Next evidence gate

1. Build and verify protected 5 V HC-SR04 interfaces.
2. Record separate sensor calibration/repeatability data at known distances.
3. Re-run central-overlap tracking and measure valid-fix rate, accuracy,
   latency, jitter, and loss duration.
4. Restore safety by default and verify repeated dead-zone crossings with
   audible and visual output.
5. Test the complete field on a 0.30 m grid before deciding on servos or more
   sensors.
6. Validate four-AA runtime, standalone enclosures, budget, and Windows
   installation.
