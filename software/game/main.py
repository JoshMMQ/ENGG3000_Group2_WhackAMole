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
    from .simulated_position import PhysicalPosition, SimulatedPositionSource
except ImportError:
    from coordinates import CoordinateMapper, ScreenPosition
    from simulated_position import PhysicalPosition, SimulatedPositionSource


WINDOW_WIDTH_PX = 900
WINDOW_HEIGHT_PX = 900
STATIC_POSITION_M = (1.5, 1.5)
BACKGROUND_COLOR = (24, 28, 36)
CURSOR_COLOR = (85, 195, 255)
CURSOR_OUTLINE_COLOR = (235, 248, 255)
CURSOR_RADIUS_PX = 18
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

    screen.fill(BACKGROUND_COLOR)
    pygame.draw.circle(screen, CURSOR_OUTLINE_COLOR, cursor_position, CURSOR_RADIUS_PX + 3)
    pygame.draw.circle(screen, CURSOR_COLOR, cursor_position, CURSOR_RADIUS_PX)
    pygame.display.flip()


def run(smoke_test: bool = False) -> int:
    """Open a 900 x 900 window and render a simulated moving cursor."""

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
    position_source = SimulatedPositionSource()
    start_ticks = pygame.time.get_ticks()

    if smoke_test:
        cursor_position = mapped_cursor_position(position_source.position_at(0.0), mapper)
        draw_frame(screen, cursor_position)
        pygame.quit()
        return 0

    running = True
    while running:
        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                running = False
            elif event.type == pygame.KEYDOWN and event.key == pygame.K_ESCAPE:
                running = False

        elapsed_s = (pygame.time.get_ticks() - start_ticks) / 1000.0
        cursor_position = mapped_cursor_position(position_source.position_at(elapsed_s), mapper)
        draw_frame(screen, cursor_position)
        clock.tick(FRAME_RATE)

    pygame.quit()
    return 0


def main(argv: Optional[list[str]] = None) -> int:
    args = argv if argv is not None else sys.argv[1:]
    return run(smoke_test="--smoke-test" in args)


if __name__ == "__main__":
    raise SystemExit(main())
