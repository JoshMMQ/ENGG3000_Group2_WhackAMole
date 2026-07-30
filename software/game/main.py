"""Minimal render loop for the Whack-a-Mole prototype."""

from __future__ import annotations

import sys
from typing import Optional

try:
    import pygame
except ImportError:
    pygame = None

try:
    from .coordinates import CoordinateMapper, ScreenPosition
    from .scene import draw_scene
    from .simulated_position import PhysicalPosition, SimulatedPositionSource
    from .udp_position import UdpPositionSource
except ImportError:
    from coordinates import CoordinateMapper, ScreenPosition
    from scene import draw_scene
    from simulated_position import PhysicalPosition, SimulatedPositionSource
    from udp_position import UdpPositionSource


WINDOW_WIDTH_PX = 900
WINDOW_HEIGHT_PX = 900
STATIC_POSITION_M = (1.5, 1.5)
FRAME_RATE = 60


def mapped_cursor_position(
    physical_position: PhysicalPosition,
    mapper: Optional[CoordinateMapper] = None,
) -> ScreenPosition:
    """Return the screen position for a physical metre position."""

    active_mapper = mapper or CoordinateMapper()
    position = active_mapper.physical_to_screen(*physical_position)
    if position is None:
        raise ValueError("cursor position must be valid")
    return position


def static_cursor_position(mapper: Optional[CoordinateMapper] = None) -> ScreenPosition:
    """Return the screen position for the prototype's static centre cursor."""

    return mapped_cursor_position(STATIC_POSITION_M, mapper)


def draw_frame(screen: object, cursor_position: ScreenPosition) -> None:
    """Draw the current prototype frame."""

    if pygame is None:
        raise RuntimeError("pygame is required to draw the game window")

    draw_scene(screen, cursor_position)


def run(smoke_test: bool = False, input_source: str = "simulated") -> int:
    """Open a 900 x 900 window and render a moving cursor."""

    if pygame is None:
        print(
            "pygame is required to render the game window. "
            "Install dependencies with: python3 -m pip install -r requirements.txt",
            file=sys.stderr,
        )
        return 1

    pygame.init()
    screen = pygame.display.set_mode((WINDOW_WIDTH_PX, WINDOW_HEIGHT_PX))
    pygame.display.set_caption("Whack-a-Mole Prototype")
    clock = pygame.time.Clock()
    mapper = CoordinateMapper()
    simulated_source = SimulatedPositionSource()
    udp_source = UdpPositionSource() if input_source == "udp" else None
    start_ticks = pygame.time.get_ticks()

    if smoke_test:
        cursor_position = mapped_cursor_position(simulated_source.position_at(0.0), mapper)
        draw_frame(screen, cursor_position)
        if udp_source is not None:
            udp_source.close()
        pygame.quit()
        return 0

    try:
        running = True
        while running:
            for event in pygame.event.get():
                if event.type == pygame.QUIT:
                    running = False
                elif event.type == pygame.KEYDOWN and event.key == pygame.K_ESCAPE:
                    running = False

            elapsed_s = (pygame.time.get_ticks() - start_ticks) / 1000.0
            if udp_source is None:
                physical_position = simulated_source.position_at(elapsed_s)
            else:
                physical_position = udp_source.poll_position()
            cursor_position = mapped_cursor_position(physical_position, mapper)
            draw_frame(screen, cursor_position)
            clock.tick(FRAME_RATE)
    finally:
        if udp_source is not None:
            udp_source.close()
        pygame.quit()
    return 0


def main(argv: Optional[list[str]] = None) -> int:
    args = argv if argv is not None else sys.argv[1:]
    input_source = "udp" if "--input" in args and "udp" in args else "simulated"
    return run(smoke_test="--smoke-test" in args, input_source=input_source)


if __name__ == "__main__":
    raise SystemExit(main())
