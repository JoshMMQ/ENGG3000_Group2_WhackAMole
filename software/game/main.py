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
    from .scene import (
        GameplayUi,
        active_mole_position,
        continue_button_rect,
        draw_game_over_screen,
        draw_loading_screen,
        draw_scene,
        draw_title_screen,
        start_button_rect,
    )
    from .simulated_position import PhysicalPosition, SimulatedPositionSource
    from .udp_position import UdpPositionSource
except ImportError:
    from coordinates import CoordinateMapper, ScreenPosition
    from scene import (
        GameplayUi,
        active_mole_position,
        continue_button_rect,
        draw_game_over_screen,
        draw_loading_screen,
        draw_scene,
        draw_title_screen,
        start_button_rect,
    )
    from simulated_position import PhysicalPosition, SimulatedPositionSource
    from udp_position import UdpPositionSource


WINDOW_WIDTH_PX = 900
WINDOW_HEIGHT_PX = 900
STATIC_POSITION_M = (1.5, 1.5)
FRAME_RATE = 60
LOADING_SECONDS = 1.0
GAME_SECONDS = 60
MOLE_INTERVAL_SECONDS = 1.75
HIT_RADIUS_PX = 70


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


def create_mapper(screen_size: ScreenPosition = (WINDOW_WIDTH_PX, WINDOW_HEIGHT_PX)) -> CoordinateMapper:
    """Create a coordinate mapper for the active window size."""

    return CoordinateMapper(screen_width_px=screen_size[0], screen_height_px=screen_size[1])


def static_cursor_position(mapper: Optional[CoordinateMapper] = None) -> ScreenPosition:
    """Return the screen position for the prototype's static centre cursor."""

    return mapped_cursor_position(STATIC_POSITION_M, mapper)


def active_hole_index_at(elapsed_s: float, interval_s: float = MOLE_INTERVAL_SECONDS) -> int:
    """Return the active mole hole index for elapsed gameplay time."""

    if interval_s <= 0:
        raise ValueError("interval_s must be positive")
    return int(max(0.0, elapsed_s) // interval_s) % 9


def scaled_hit_radius(screen_size: ScreenPosition, base_radius_px: int = HIT_RADIUS_PX) -> int:
    """Return a hit radius scaled for the current window size."""

    width, height = screen_size
    scale = min(width, height) / WINDOW_WIDTH_PX
    return max(20, round(base_radius_px * scale))


def is_cursor_over_mole(
    cursor_position: ScreenPosition,
    mole_position: ScreenPosition,
    radius_px: int,
) -> bool:
    """Return whether the cursor is inside the active mole hit preview radius."""

    if radius_px < 0:
        raise ValueError("radius_px must be non-negative")
    dx = cursor_position[0] - mole_position[0]
    dy = cursor_position[1] - mole_position[1]
    return dx * dx + dy * dy <= radius_px * radius_px


def draw_frame(
    screen: object,
    cursor_position: ScreenPosition,
    ui: GameplayUi | None = None,
    active_hole_index: int = 4,
    mole_highlighted: bool = False,
) -> None:
    """Draw the current prototype frame."""

    if pygame is None:
        raise RuntimeError("pygame is required to draw the game window")

    draw_scene(screen, cursor_position, ui, active_hole_index, mole_highlighted)


def run(smoke_test: bool = False, input_source: str = "simulated") -> int:
    """Open a resizable 900 x 900 window and render a moving cursor."""

    if pygame is None:
        print(
            "pygame is required to render the game window. "
            "Install dependencies with: python3 -m pip install -r requirements.txt",
            file=sys.stderr,
        )
        return 1

    pygame.init()
    screen = pygame.display.set_mode((WINDOW_WIDTH_PX, WINDOW_HEIGHT_PX), pygame.RESIZABLE)
    pygame.display.set_caption("Whack-a-Mole Prototype")
    clock = pygame.time.Clock()
    mapper = create_mapper(screen.get_size())
    simulated_source = SimulatedPositionSource()
    udp_source = UdpPositionSource() if input_source == "udp" else None
    start_ticks = pygame.time.get_ticks()
    game_start_ticks = start_ticks
    game_state = "loading"
    score = 0

    if smoke_test:
        cursor_position = mapped_cursor_position(simulated_source.position_at(0.0), mapper)
        draw_loading_screen(screen, 1.0)
        draw_title_screen(screen)
        draw_frame(
            screen,
            cursor_position,
            GameplayUi(score=score, lives=3, remaining_seconds=GAME_SECONDS),
            active_hole_index_at(0.0),
            False,
        )
        draw_game_over_screen(screen, score)
        if udp_source is not None:
            udp_source.close()
        pygame.quit()
        return 0

    try:
        running = True
        while running:
            now_ticks = pygame.time.get_ticks()
            for event in pygame.event.get():
                if event.type == pygame.QUIT:
                    running = False
                elif event.type == pygame.KEYDOWN:
                    if event.key == pygame.K_ESCAPE:
                        running = False
                    elif event.key in (pygame.K_RETURN, pygame.K_SPACE):
                        if game_state in ("loading", "title", "game_over"):
                            game_state = "playing"
                            game_start_ticks = now_ticks
                            score = 0
                    elif event.key == pygame.K_g and game_state == "playing":
                        game_state = "game_over"
                elif event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
                    width, height = screen.get_size()
                    if game_state == "title" and pygame.Rect(start_button_rect(width, height)).collidepoint(event.pos):
                        game_state = "playing"
                        game_start_ticks = now_ticks
                        score = 0
                    elif game_state == "game_over" and pygame.Rect(continue_button_rect(width, height)).collidepoint(event.pos):
                        game_state = "playing"
                        game_start_ticks = now_ticks
                        score = 0

            if game_state == "loading":
                progress = (now_ticks - start_ticks) / 1000.0 / LOADING_SECONDS
                draw_loading_screen(screen, progress)
                if progress >= 1.0:
                    game_state = "title"
            elif game_state == "title":
                draw_title_screen(screen)
            elif game_state == "game_over":
                draw_game_over_screen(screen, score)
            else:
                game_elapsed_s = (now_ticks - game_start_ticks) / 1000.0
                remaining_seconds = max(0, GAME_SECONDS - int(game_elapsed_s))
                if remaining_seconds <= 0:
                    game_state = "game_over"
                    draw_game_over_screen(screen, score)
                else:
                    if udp_source is None:
                        physical_position = simulated_source.position_at(game_elapsed_s)
                    else:
                        physical_position = udp_source.poll_position()
                    mapper = create_mapper(screen.get_size())
                    cursor_position = mapped_cursor_position(physical_position, mapper)
                    ui = GameplayUi(score=score, lives=3, remaining_seconds=remaining_seconds)
                    active_hole_index = active_hole_index_at(game_elapsed_s)
                    mole_position = active_mole_position(*screen.get_size(), active_hole_index=active_hole_index)
                    mole_highlighted = is_cursor_over_mole(
                        cursor_position,
                        mole_position,
                        scaled_hit_radius(screen.get_size()),
                    )
                    draw_frame(screen, cursor_position, ui, active_hole_index, mole_highlighted)
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
