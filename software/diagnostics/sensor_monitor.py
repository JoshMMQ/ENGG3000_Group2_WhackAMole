"""Pygame screen showing two independent ESP32 USB sensor readings."""

from __future__ import annotations

import argparse
import sys
import time
from dataclasses import dataclass
from math import sin
from typing import Optional

from software.transport.serial_sensor import (
    DEFAULT_BAUD_RATE,
    BenchSensorReading,
    SerialSensorSource,
    available_serial_ports,
)


WINDOW_SIZE = (1000, 560)
FRAME_RATE = 60
DEFAULT_STALE_AFTER_S = 1.0

BACKGROUND = (28, 44, 38)
CARD = (246, 239, 211)
CARD_EDGE = (107, 76, 48)
TEXT = (48, 37, 28)
MUTED = (105, 98, 84)
LIVE = (42, 158, 87)
WAITING = (208, 153, 39)
ERROR = (205, 66, 55)
WHITE = (255, 255, 255)


@dataclass
class SensorPanelState:
    """Latest display state associated with one physical USB port."""

    label: str
    expected_sensor_id: str
    port: str
    reading: Optional[BenchSensorReading] = None
    received_at_s: Optional[float] = None
    error: Optional[str] = None

    def apply(self, reading: BenchSensorReading, received_at_s: float) -> None:
        self.reading = reading
        self.received_at_s = received_at_s
        self.error = None


def panel_status(
    panel: SensorPanelState,
    now_s: float,
    stale_after_s: float = DEFAULT_STALE_AFTER_S,
) -> tuple[str, tuple[int, int, int]]:
    """Return a concise status label and colour for one display card."""

    if stale_after_s <= 0:
        raise ValueError("stale_after_s must be positive")
    if panel.error is not None:
        return "PORT ERROR", ERROR
    if panel.reading is None or panel.received_at_s is None:
        return "WAITING", WAITING
    if panel.reading.sensor_id != panel.expected_sensor_id:
        return "ID MISMATCH", ERROR
    if now_s - panel.received_at_s > stale_after_s:
        return "STALE", WAITING
    if not panel.reading.valid:
        return "NO ECHO", ERROR
    return "LIVE", LIVE


def distance_text(reading: Optional[BenchSensorReading]) -> tuple[str, str]:
    """Return millimetre and centimetre strings for the large display."""

    if reading is None:
        return "--- mm", "waiting for JSON"
    if not reading.valid or reading.distance_mm is None:
        return "--- mm", "valid: false"
    return f"{reading.distance_mm:.1f} mm", f"{reading.distance_mm / 10.0:.1f} cm"


def panel_rectangles(width: int, height: int) -> tuple[tuple[int, int, int, int], ...]:
    """Return two responsive, non-overlapping card rectangles."""

    margin = max(24, round(width * 0.045))
    gap = max(20, round(width * 0.035))
    top = max(105, round(height * 0.20))
    bottom_margin = max(70, round(height * 0.15))
    card_width = max(1, (width - 2 * margin - gap) // 2)
    card_height = max(1, height - top - bottom_margin)
    return (
        (margin, top, card_width, card_height),
        (margin + card_width + gap, top, card_width, card_height),
    )


def draw_monitor(
    screen: object,
    left: SensorPanelState,
    right: SensorPanelState,
    now_s: float,
    stale_after_s: float = DEFAULT_STALE_AFTER_S,
) -> None:
    """Draw one monitor frame."""

    import pygame

    width, height = screen.get_size()
    screen.fill(BACKGROUND)

    title_font = _font(pygame, width, 0.045, bold=True)
    subtitle_font = _font(pygame, width, 0.020)
    title = title_font.render("TWO-SENSOR BENCH MONITOR", True, WHITE)
    screen.blit(title, title.get_rect(center=(width // 2, round(height * 0.085))))
    subtitle = subtitle_font.render(
        "Independent USB readings — diagnostics only, not triangulated position",
        True,
        (190, 211, 199),
    )
    screen.blit(subtitle, subtitle.get_rect(center=(width // 2, round(height * 0.145))))

    for panel, rect_values in zip((left, right), panel_rectangles(width, height)):
        _draw_panel(pygame, screen, panel, pygame.Rect(rect_values), now_s, stale_after_s)

    footer_font = _font(pygame, width, 0.017)
    footer = footer_font.render(
        "Close Arduino Serial Monitor while this window is running • Esc/Q to quit",
        True,
        (190, 211, 199),
    )
    screen.blit(footer, footer.get_rect(center=(width // 2, height - max(24, round(height * 0.055)))))
    pygame.display.flip()


def run_monitor(
    left_port: Optional[str] = None,
    right_port: Optional[str] = None,
    baud_rate: int = DEFAULT_BAUD_RATE,
    stale_after_s: float = DEFAULT_STALE_AFTER_S,
    demo: bool = False,
    smoke_test: bool = False,
) -> int:
    """Open the two-card monitor until the user exits."""

    if not demo and (not left_port or not right_port):
        raise ValueError("left_port and right_port are required outside demo mode")
    if not demo and left_port == right_port:
        raise ValueError("left_port and right_port must be different devices")
    if stale_after_s <= 0:
        raise ValueError("stale_after_s must be positive")

    try:
        import pygame
    except ModuleNotFoundError:
        print(
            "pygame is required; install dependencies with "
            "'.venv/bin/python -m pip install -r requirements.txt'",
            file=sys.stderr,
        )
        return 1

    left = SensorPanelState("LEFT SENSOR", "left", left_port or "demo-left")
    right = SensorPanelState("RIGHT SENSOR", "right", right_port or "demo-right")
    sources: tuple[tuple[SerialSensorSource, SensorPanelState], ...] = ()

    if not demo:
        opened_sources: list[tuple[SerialSensorSource, SensorPanelState]] = []
        try:
            opened_sources.append((SerialSensorSource(left.port, baud_rate), left))
            opened_sources.append((SerialSensorSource(right.port, baud_rate), right))
            sources = tuple(opened_sources)
        except Exception as exc:
            for source, _ in opened_sources:
                source.close()
            print(f"Unable to open both serial ports: {exc}", file=sys.stderr)
            return 2

    pygame.init()
    screen = pygame.display.set_mode(WINDOW_SIZE, pygame.RESIZABLE)
    pygame.display.set_caption("Whack-a-Mole Sensor Monitor")
    clock = pygame.time.Clock()
    started_at_s = time.monotonic()

    try:
        running = True
        rendered_frames = 0
        while running:
            now_s = time.monotonic()
            for event in pygame.event.get():
                if event.type == pygame.QUIT:
                    running = False
                elif event.type == pygame.KEYDOWN and event.key in (pygame.K_ESCAPE, pygame.K_q):
                    running = False

            if demo:
                _update_demo(left, right, now_s, started_at_s)
            else:
                for source, panel in sources:
                    try:
                        for reading in source.poll_readings():
                            panel.apply(reading, now_s)
                    except Exception as exc:
                        panel.error = str(exc)

            draw_monitor(screen, left, right, now_s, stale_after_s)
            rendered_frames += 1
            if smoke_test and rendered_frames >= 3:
                running = False
            clock.tick(FRAME_RATE)
    finally:
        for source, _ in sources:
            source.close()
        pygame.quit()
    return 0


def list_ports(output: object = sys.stdout) -> int:
    """Print serial devices so the user can identify the two ESP32 ports."""

    try:
        ports = available_serial_ports()
    except RuntimeError as exc:
        print(exc, file=sys.stderr)
        return 1

    if not ports:
        print("No serial ports found. Connect both ESP32 USB cables and try again.", file=output)
        return 0
    for port in ports:
        print(f"{port.device}\t{port.description}", file=output)
    return 0


def main(argv: Optional[list[str]] = None) -> int:
    parser = argparse.ArgumentParser(
        description="Show left and right ESP32 bench readings in a Pygame window."
    )
    parser.add_argument("--left-port", help="Left ESP32 serial port, for example COM5 or /dev/ttyUSB0.")
    parser.add_argument("--right-port", help="Right ESP32 serial port, for example COM6 or /dev/ttyUSB1.")
    parser.add_argument("--baud", type=int, default=DEFAULT_BAUD_RATE)
    parser.add_argument("--stale-after", type=float, default=DEFAULT_STALE_AFTER_S)
    parser.add_argument("--list-ports", action="store_true")
    parser.add_argument("--demo", action="store_true", help="Animate fake readings without hardware.")
    parser.add_argument("--smoke-test", action="store_true", help=argparse.SUPPRESS)
    args = parser.parse_args(argv)

    if args.list_ports:
        return list_ports()
    if not args.demo and (not args.left_port or not args.right_port):
        parser.error("--left-port and --right-port are required unless --demo is used")

    try:
        return run_monitor(
            left_port=args.left_port,
            right_port=args.right_port,
            baud_rate=args.baud,
            stale_after_s=args.stale_after,
            demo=args.demo,
            smoke_test=args.smoke_test,
        )
    except ValueError as exc:
        parser.error(str(exc))
    return 2


def _draw_panel(
    pygame: object,
    screen: object,
    panel: SensorPanelState,
    rect: object,
    now_s: float,
    stale_after_s: float,
) -> None:
    pygame.draw.rect(screen, (12, 27, 22), rect.move(0, max(6, rect.height // 35)), border_radius=24)
    pygame.draw.rect(screen, CARD, rect, border_radius=24)
    pygame.draw.rect(screen, CARD_EDGE, rect, width=max(3, rect.width // 120), border_radius=24)

    label_font = _font(pygame, rect.width, 0.080, bold=True)
    value_font = _font(pygame, rect.width, 0.115, bold=True)
    detail_font = _font(pygame, rect.width, 0.052)
    small_font = _font(pygame, rect.width, 0.038)

    label = label_font.render(panel.label, True, TEXT)
    screen.blit(label, label.get_rect(center=(rect.centerx, rect.top + round(rect.height * 0.16))))

    status_label, status_color = panel_status(panel, now_s, stale_after_s)
    status_surface = small_font.render(status_label, True, WHITE)
    status_rect = status_surface.get_rect(center=(rect.centerx, rect.top + round(rect.height * 0.30)))
    badge = status_rect.inflate(max(22, rect.width // 16), max(12, rect.height // 30))
    pygame.draw.rect(screen, status_color, badge, border_radius=badge.height // 2)
    screen.blit(status_surface, status_rect)

    millimetres, centimetres = distance_text(panel.reading)
    value_surface = value_font.render(millimetres, True, TEXT)
    screen.blit(value_surface, value_surface.get_rect(center=(rect.centerx, rect.top + round(rect.height * 0.52))))
    detail_surface = detail_font.render(centimetres, True, MUTED)
    screen.blit(detail_surface, detail_surface.get_rect(center=(rect.centerx, rect.top + round(rect.height * 0.66))))

    identity = "waiting for sensor identity"
    if panel.reading is not None:
        identity = f"{panel.reading.node_id} / {panel.reading.sensor_id}"
    identity_surface = small_font.render(identity, True, TEXT)
    screen.blit(identity_surface, identity_surface.get_rect(center=(rect.centerx, rect.top + round(rect.height * 0.80))))

    port_surface = small_font.render(panel.port, True, MUTED)
    screen.blit(port_surface, port_surface.get_rect(center=(rect.centerx, rect.top + round(rect.height * 0.91))))


def _update_demo(
    left: SensorPanelState,
    right: SensorPanelState,
    now_s: float,
    started_at_s: float,
) -> None:
    elapsed_s = now_s - started_at_s
    sample_us = max(0, round(elapsed_s * 1_000_000))
    left_distance = 800.0 + 250.0 * sin(elapsed_s * 1.7)
    right_distance = 950.0 + 220.0 * sin(elapsed_s * 1.7 + 1.1)
    left.apply(BenchSensorReading("box1", "left", left_distance, True, sample_us), now_s)
    right.apply(BenchSensorReading("box2", "right", right_distance, True, sample_us), now_s)


def _font(pygame: object, width: int, ratio: float, bold: bool = False) -> object:
    return pygame.font.SysFont("arial", max(16, round(width * ratio)), bold=bold)


if __name__ == "__main__":
    raise SystemExit(main())
