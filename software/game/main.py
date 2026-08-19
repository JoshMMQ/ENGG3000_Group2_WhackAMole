"""Minimal render loop for the Whack-a-Mole prototype."""

from __future__ import annotations

import argparse
import logging
from math import isfinite
import sys
from typing import Optional

try:
    import pygame
except ImportError:
    pygame = None

try:
    from .coordinates import CoordinateMapper, ScreenPosition
    from .logging_config import DEFAULT_LOG_PATH, configure_logging
    from .scene import (
        GameplayUi,
        active_mole_position,
        continue_button_rect,
        draw_game_over_screen,
        draw_loading_screen,
        draw_scene,
        draw_title_screen,
        pause_button_rect,
        start_button_rect,
    )
    from .presentation_tracking import (
        PresentationTrackingSnapshot,
        PresentationTrackingSource,
        interpolate_position,
    )
    from .simulated_position import PhysicalPosition, SimulatedPositionSource
    from .tracking_state import TrackingSnapshot, TrackingStatus
except ImportError:
    from coordinates import CoordinateMapper, ScreenPosition
    from logging_config import DEFAULT_LOG_PATH, configure_logging
    from scene import (
        GameplayUi,
        active_mole_position,
        continue_button_rect,
        draw_game_over_screen,
        draw_loading_screen,
        draw_scene,
        draw_title_screen,
        pause_button_rect,
        start_button_rect,
    )
    from presentation_tracking import (
        PresentationTrackingSnapshot,
        PresentationTrackingSource,
        interpolate_position,
    )
    from simulated_position import PhysicalPosition, SimulatedPositionSource
    from tracking_state import TrackingSnapshot, TrackingStatus


WINDOW_WIDTH_PX = 900
WINDOW_HEIGHT_PX = 900
STATIC_POSITION_M = (0.75, 1.30)
FRAME_RATE = 60
LOADING_SECONDS = 1.0
GAME_SECONDS = 60
MOLE_INTERVAL_SECONDS = 1.75
HIT_RADIUS_PX = 70
PLAY_AREA_WIDTH_M = 1.50
PLAY_AREA_TOP_M = 0.60
PLAY_AREA_HEIGHT_M = 1.40
TRACKED_DEPTH_M = 2.00
STARTING_LIVES = 3
SCREEN_WARNING_DISTANCE_M = 0.60
SCREEN_WARNING_CLEAR_DISTANCE_M = 0.70

logger = logging.getLogger(__name__)


def randomized_hole_index(slot: int, hole_count: int = 9) -> int:
    """Return a repeatable random-looking hole index for a time slot."""

    if hole_count <= 0:
        raise ValueError("hole_count must be positive")
    normalized_slot = max(0, slot)
    return (normalized_slot * 5 + normalized_slot // 2 + 3) % hole_count


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


def tracking_only_position(snapshot: TrackingSnapshot) -> PhysicalPosition:
    """Use every valid triangulated position and otherwise retain the cursor."""

    return (
        snapshot.world_position
        if snapshot.world_position is not None
        else snapshot.cursor_position
    )


def is_inside_play_area(
    physical_position: PhysicalPosition,
    width_m: float = PLAY_AREA_WIDTH_M,
    height_m: float = PLAY_AREA_HEIGHT_M,
    top_m: float = PLAY_AREA_TOP_M,
) -> bool:
    """Return whether a physical position is inside the playable area."""

    if width_m <= 0 or height_m <= 0:
        raise ValueError("play area dimensions must be positive")
    try:
        x_m = float(physical_position[0])
        y_m = float(physical_position[1])
    except (TypeError, ValueError, IndexError):
        return False
    if not isfinite(x_m) or not isfinite(y_m):
        return False
    return 0.0 <= x_m <= width_m and top_m <= y_m <= top_m + height_m


def is_inside_tracked_footprint(
    physical_position: PhysicalPosition,
    width_m: float = PLAY_AREA_WIDTH_M,
    depth_m: float = TRACKED_DEPTH_M,
) -> bool:
    """Return whether a position is inside the full V2 field plus dead zone."""

    if width_m <= 0 or depth_m <= 0:
        raise ValueError("tracked footprint dimensions must be positive")
    try:
        x_m = float(physical_position[0])
        y_m = float(physical_position[1])
    except (TypeError, ValueError, IndexError):
        return False
    if not isfinite(x_m) or not isfinite(y_m):
        return False
    return 0.0 <= x_m <= width_m and 0.0 <= y_m <= depth_m


def is_inside_screen_warning_zone(
    physical_position: PhysicalPosition,
    warning_distance_m: float = SCREEN_WARNING_DISTANCE_M,
) -> bool:
    """Return whether the player is inside the screen-proximity warning zone."""

    if warning_distance_m < 0:
        raise ValueError("warning_distance_m must be non-negative")
    try:
        y_m = float(physical_position[1])
    except (TypeError, ValueError, IndexError):
        return False
    if not isfinite(y_m):
        return False
    return y_m < warning_distance_m


def should_clear_screen_warning(
    physical_position: PhysicalPosition,
    clear_distance_m: float = SCREEN_WARNING_CLEAR_DISTANCE_M,
) -> bool:
    """Return whether hysteresis allows the screen warning to clear."""

    if clear_distance_m < 0:
        raise ValueError("clear_distance_m must be non-negative")
    try:
        y_m = float(physical_position[1])
    except (TypeError, ValueError, IndexError):
        return False
    if not isfinite(y_m):
        return False
    return y_m >= clear_distance_m


def set_audible_warning_active(active: bool) -> None:
    """Future hook for laptop speaker or external audible warning hardware."""

    _ = active


def create_mapper(
    screen_size: ScreenPosition = (WINDOW_WIDTH_PX, WINDOW_HEIGHT_PX),
    tracking_only: bool = False,
) -> CoordinateMapper:
    """Create a playable-area or full-footprint mapper for the active window."""

    if tracking_only:
        return CoordinateMapper(
            play_area_top_m=0.0,
            play_area_height_m=TRACKED_DEPTH_M,
            screen_width_px=screen_size[0],
            screen_height_px=screen_size[1],
        )
    return CoordinateMapper(
        screen_width_px=screen_size[0],
        screen_height_px=screen_size[1],
    )


def static_cursor_position(mapper: Optional[CoordinateMapper] = None) -> ScreenPosition:
    """Return the screen position for the prototype's static centre cursor."""

    return mapped_cursor_position(STATIC_POSITION_M, mapper)


def active_hole_index_at(elapsed_s: float, interval_s: float = MOLE_INTERVAL_SECONDS) -> int:
    """Return the active mole hole index for elapsed gameplay time."""

    if interval_s <= 0:
        raise ValueError("interval_s must be positive")
    slot = int(max(0.0, elapsed_s) // interval_s)
    return randomized_hole_index(slot)


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


def gameplay_elapsed_seconds(now_ticks: int, game_start_ticks: int, total_paused_ms: int) -> float:
    """Return active gameplay seconds, excluding paused duration."""

    return max(0, now_ticks - game_start_ticks - total_paused_ms) / 1000.0


def draw_frame(
    screen: object,
    cursor_position: ScreenPosition,
    ui: GameplayUi | None = None,
    active_hole_index: int = 4,
    mole_highlighted: bool = False,
    paused: bool = False,
    safety_alert: bool = False,
    screen_warning: bool = False,
) -> None:
    """Draw the current prototype frame."""

    if pygame is None:
        raise RuntimeError("pygame is required to draw the game window")

    draw_scene(
        screen,
        cursor_position,
        ui,
        active_hole_index,
        mole_highlighted,
        paused,
        safety_alert,
        screen_warning,
    )


def run(
    smoke_test: bool = False,
    input_source: str = "simulated",
    safety_enabled: bool = False,
) -> int:
    """Open the game; safety gates are opt-in during tracking development."""

    if input_source not in {"simulated", "sensor-scan"}:
        raise ValueError("input_source must be simulated or sensor-scan")
    if input_source == "sensor-scan" and safety_enabled:
        raise ValueError("the presentation sensor-scan input is not a safety input")

    logger.info(
        "Game run starting input_source=%s smoke_test=%s safety_enabled=%s",
        input_source,
        smoke_test,
        safety_enabled,
    )
    if not safety_enabled:
        logger.warning(
            "Safety gates disabled for tracking-only development: no boundary/dead-zone/"
            "tracking-loss pause or life penalty"
        )

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
    mapper = create_mapper(screen.get_size(), tracking_only=not safety_enabled)
    simulated_source = SimulatedPositionSource()
    presentation_source = (
        PresentationTrackingSource() if input_source == "sensor-scan" else None
    )
    position_source = presentation_source
    start_ticks = pygame.time.get_ticks()
    last_frame_ticks = start_ticks
    game_start_ticks = start_ticks
    total_paused_ms = 0
    pause_started_ticks: Optional[int] = None
    last_game_elapsed_s = 0.0
    last_cursor_position = static_cursor_position(mapper)
    last_active_hole_index = active_hole_index_at(0.0)
    last_mole_highlighted = False
    game_state = "loading"
    score = 0
    lives = STARTING_LIVES
    audible_warning_active = False
    presentation_snapshot: Optional[PresentationTrackingSnapshot] = (
        presentation_source.tracking_snapshot
        if presentation_source is not None
        else None
    )
    render_physical_position = STATIC_POSITION_M

    def poll_tracking_source():
        nonlocal presentation_snapshot
        if position_source is None:
            return None
        tracking = position_source.poll()
        if presentation_source is not None:
            presentation_snapshot = tracking
        return tracking

    def current_gameplay_ui(
        remaining_seconds: int,
        displayed_lives: Optional[int] = None,
    ) -> GameplayUi:
        return GameplayUi(
            score=score,
            lives=lives if displayed_lives is None else displayed_lives,
            remaining_seconds=remaining_seconds,
            tracking_debug_lines=(
                presentation_snapshot.diagnostic_lines
                if presentation_snapshot is not None
                else ()
            ),
        )

    if smoke_test:
        cursor_position = mapped_cursor_position(simulated_source.position_at(0.0), mapper)
        draw_loading_screen(screen, 1.0)
        draw_title_screen(screen)
        draw_frame(
            screen,
            cursor_position,
            current_gameplay_ui(GAME_SECONDS),
            active_hole_index_at(0.0),
            False,
        )
        draw_frame(
            screen,
            cursor_position,
            current_gameplay_ui(GAME_SECONDS),
            active_hole_index_at(0.0),
            False,
            paused=True,
        )
        draw_frame(
            screen,
            cursor_position,
            current_gameplay_ui(GAME_SECONDS, displayed_lives=max(0, lives - 1)),
            active_hole_index_at(0.0),
            False,
            paused=True,
            safety_alert=True,
        )
        draw_frame(
            screen,
            cursor_position,
            current_gameplay_ui(GAME_SECONDS),
            active_hole_index_at(0.0),
            False,
            paused=True,
            screen_warning=True,
        )
        draw_game_over_screen(screen, score)
        if position_source is not None:
            position_source.close()
        pygame.quit()
        return 0

    try:
        running = True
        while running:
            now_ticks = pygame.time.get_ticks()
            frame_delta_s = max(0.0, now_ticks - last_frame_ticks) / 1000.0
            last_frame_ticks = now_ticks
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
                            total_paused_ms = 0
                            pause_started_ticks = None
                            last_game_elapsed_s = 0.0
                            last_active_hole_index = active_hole_index_at(0.0)
                            last_mole_highlighted = False
                            score = 0
                            lives = STARTING_LIVES
                    elif event.key == pygame.K_p:
                        if game_state == "playing":
                            game_state = "paused"
                            pause_started_ticks = now_ticks
                        elif game_state in ("paused", "safety_paused") and pause_started_ticks is not None:
                            total_paused_ms += now_ticks - pause_started_ticks
                            pause_started_ticks = None
                            game_state = "game_over" if lives <= 0 else "playing"
                    elif event.key == pygame.K_g and game_state == "playing":
                        game_state = "game_over"
                elif event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
                    width, height = screen.get_size()
                    if game_state in ("playing", "paused", "safety_paused") and pygame.Rect(pause_button_rect(width, height)).collidepoint(event.pos):
                        if game_state == "playing":
                            game_state = "paused"
                            pause_started_ticks = now_ticks
                        elif pause_started_ticks is not None:
                            total_paused_ms += now_ticks - pause_started_ticks
                            pause_started_ticks = None
                            game_state = "game_over" if lives <= 0 else "playing"
                    elif game_state == "title" and pygame.Rect(start_button_rect(width, height)).collidepoint(event.pos):
                        game_state = "playing"
                        game_start_ticks = now_ticks
                        total_paused_ms = 0
                        pause_started_ticks = None
                        last_game_elapsed_s = 0.0
                        last_active_hole_index = active_hole_index_at(0.0)
                        last_mole_highlighted = False
                        score = 0
                        lives = STARTING_LIVES
                    elif game_state == "game_over" and pygame.Rect(continue_button_rect(width, height)).collidepoint(event.pos):
                        game_state = "playing"
                        game_start_ticks = now_ticks
                        total_paused_ms = 0
                        pause_started_ticks = None
                        last_game_elapsed_s = 0.0
                        last_active_hole_index = active_hole_index_at(0.0)
                        last_mole_highlighted = False
                        score = 0
                        lives = STARTING_LIVES

            if game_state == "loading":
                progress = (now_ticks - start_ticks) / 1000.0 / LOADING_SECONDS
                draw_loading_screen(screen, progress)
                if progress >= 1.0:
                    game_state = "title"
            elif game_state == "title":
                draw_title_screen(screen)
            elif game_state == "game_over":
                draw_game_over_screen(screen, score)
            elif game_state == "screen_warning":
                if not audible_warning_active:
                    set_audible_warning_active(True)
                    audible_warning_active = True
                if position_source is None:
                    input_elapsed_s = max(0, now_ticks - game_start_ticks) / 1000.0
                    physical_position = simulated_source.position_at(input_elapsed_s)
                    tracking_status = TrackingStatus.PLAYABLE
                else:
                    tracking = poll_tracking_source()
                    tracking_status = tracking.status
                    physical_position = tracking.world_position
                if tracking_status in (TrackingStatus.WAITING, TrackingStatus.TRACKING_LOST):
                    set_audible_warning_active(False)
                    audible_warning_active = False
                    game_state = "tracking_lost"
                    remaining_seconds = max(0, GAME_SECONDS - int(last_game_elapsed_s))
                    draw_frame(
                        screen,
                        last_cursor_position,
                        current_gameplay_ui(remaining_seconds),
                        last_active_hole_index,
                        False,
                        paused=True,
                        safety_alert=True,
                    )
                elif physical_position is None or not is_inside_tracked_footprint(physical_position):
                    set_audible_warning_active(False)
                    audible_warning_active = False
                    lives = max(0, lives - 1)
                    game_state = "safety_paused"
                    remaining_seconds = max(0, GAME_SECONDS - int(last_game_elapsed_s))
                    draw_frame(
                        screen,
                        last_cursor_position,
                        current_gameplay_ui(remaining_seconds),
                        last_active_hole_index,
                        last_mole_highlighted,
                        paused=True,
                        safety_alert=True,
                    )
                elif tracking_status == TrackingStatus.PLAYABLE and should_clear_screen_warning(
                    physical_position
                ):
                    if pause_started_ticks is not None:
                        total_paused_ms += now_ticks - pause_started_ticks
                    pause_started_ticks = None
                    set_audible_warning_active(False)
                    audible_warning_active = False
                    game_state = "playing"
                else:
                    remaining_seconds = max(0, GAME_SECONDS - int(last_game_elapsed_s))
                    draw_frame(
                        screen,
                        last_cursor_position,
                        current_gameplay_ui(remaining_seconds),
                        last_active_hole_index,
                        last_mole_highlighted,
                        paused=True,
                        screen_warning=True,
                    )
            elif game_state == "tracking_lost":
                tracking = poll_tracking_source()
                if tracking is not None and tracking.status in (
                    TrackingStatus.PLAYABLE,
                    TrackingStatus.DEAD_ZONE,
                ):
                    if pause_started_ticks is not None:
                        total_paused_ms += now_ticks - pause_started_ticks
                    pause_started_ticks = None
                    if tracking.status == TrackingStatus.DEAD_ZONE:
                        game_state = "screen_warning"
                        pause_started_ticks = now_ticks
                        set_audible_warning_active(True)
                        audible_warning_active = True
                    else:
                        game_state = "playing"
                else:
                    remaining_seconds = max(0, GAME_SECONDS - int(last_game_elapsed_s))
                    draw_frame(
                        screen,
                        last_cursor_position,
                        current_gameplay_ui(remaining_seconds),
                        last_active_hole_index,
                        False,
                        paused=True,
                        safety_alert=True,
                    )
            elif game_state in ("paused", "safety_paused"):
                remaining_seconds = max(0, GAME_SECONDS - int(last_game_elapsed_s))
                ui = current_gameplay_ui(remaining_seconds)
                draw_frame(
                    screen,
                    last_cursor_position,
                    ui,
                    last_active_hole_index,
                    last_mole_highlighted,
                    paused=True,
                    safety_alert=game_state == "safety_paused",
                )
            else:
                game_elapsed_s = gameplay_elapsed_seconds(now_ticks, game_start_ticks, total_paused_ms)
                last_game_elapsed_s = game_elapsed_s
                remaining_seconds = max(0, GAME_SECONDS - int(game_elapsed_s))
                if remaining_seconds <= 0:
                    game_state = "game_over"
                    draw_game_over_screen(screen, score)
                else:
                    if position_source is None:
                        physical_position = simulated_source.position_at(game_elapsed_s)
                        tracking_status = TrackingStatus.PLAYABLE
                    else:
                        tracking = poll_tracking_source()
                        tracking_status = tracking.status
                        target_position = (
                            tracking.world_position
                            if safety_enabled
                            else tracking_only_position(tracking)
                        )
                        if presentation_source is not None:
                            render_physical_position = interpolate_position(
                                render_physical_position,
                                target_position,
                                frame_delta_s,
                            )
                            physical_position = render_physical_position
                        else:
                            physical_position = target_position
                    if safety_enabled and tracking_status in (
                        TrackingStatus.WAITING,
                        TrackingStatus.TRACKING_LOST,
                    ):
                        game_state = "tracking_lost"
                        pause_started_ticks = now_ticks
                        draw_frame(
                            screen,
                            last_cursor_position,
                            current_gameplay_ui(remaining_seconds),
                            last_active_hole_index,
                            False,
                            paused=True,
                            safety_alert=True,
                        )
                        clock.tick(FRAME_RATE)
                        continue
                    if safety_enabled and (
                        physical_position is None
                        or not is_inside_tracked_footprint(physical_position)
                    ):
                        lives = max(0, lives - 1)
                        game_state = "safety_paused"
                        pause_started_ticks = now_ticks
                        remaining_seconds = max(0, GAME_SECONDS - int(last_game_elapsed_s))
                        draw_frame(
                            screen,
                            last_cursor_position,
                            current_gameplay_ui(remaining_seconds),
                            last_active_hole_index,
                            last_mole_highlighted,
                            paused=True,
                            safety_alert=True,
                        )
                        clock.tick(FRAME_RATE)
                        continue
                    if safety_enabled and (
                        tracking_status == TrackingStatus.DEAD_ZONE
                        or is_inside_screen_warning_zone(physical_position)
                    ):
                        game_state = "screen_warning"
                        pause_started_ticks = now_ticks
                        set_audible_warning_active(True)
                        audible_warning_active = True
                        draw_frame(
                            screen,
                            last_cursor_position,
                            current_gameplay_ui(remaining_seconds),
                            last_active_hole_index,
                            last_mole_highlighted,
                            paused=True,
                            screen_warning=True,
                        )
                        clock.tick(FRAME_RATE)
                        continue
                    if safety_enabled and not is_inside_play_area(physical_position):
                        lives = max(0, lives - 1)
                        game_state = "safety_paused"
                        pause_started_ticks = now_ticks
                        draw_frame(
                            screen,
                            last_cursor_position,
                            current_gameplay_ui(remaining_seconds),
                            last_active_hole_index,
                            False,
                            paused=True,
                            safety_alert=True,
                        )
                        clock.tick(FRAME_RATE)
                        continue
                    mapper = create_mapper(
                        screen.get_size(),
                        tracking_only=not safety_enabled,
                    )
                    cursor_position = mapped_cursor_position(physical_position, mapper)
                    if cursor_position != last_cursor_position:
                        logger.debug(
                            "Cursor moved world_x_m=%.4f world_y_m=%.4f "
                            "screen_x_px=%s screen_y_px=%s tracking_status=%s",
                            physical_position[0],
                            physical_position[1],
                            cursor_position[0],
                            cursor_position[1],
                            tracking_status.value,
                        )
                    last_cursor_position = cursor_position
                    ui = current_gameplay_ui(remaining_seconds)
                    active_hole_index = active_hole_index_at(game_elapsed_s)
                    last_active_hole_index = active_hole_index
                    mole_position = active_mole_position(*screen.get_size(), active_hole_index=active_hole_index)
                    mole_highlighted = is_cursor_over_mole(
                        cursor_position,
                        mole_position,
                        scaled_hit_radius(screen.get_size()),
                    )
                    last_mole_highlighted = mole_highlighted
                    draw_frame(screen, cursor_position, ui, active_hole_index, mole_highlighted)
            clock.tick(FRAME_RATE)
    finally:
        if audible_warning_active:
            set_audible_warning_active(False)
        if position_source is not None:
            position_source.close()
        pygame.quit()
        logger.info("Game run stopped")
    return 0


def main(argv: Optional[list[str]] = None) -> int:
    parser = argparse.ArgumentParser(description="Run the Whack-a-Mole game.")
    parser.add_argument(
        "--input",
        choices=("simulated", "sensor-scan"),
        default="simulated",
        help=(
            "Use built-in movement or the Version 3 S1-host sensor-scan input."
        ),
    )
    parser.add_argument(
        "--enable-safety",
        action="store_true",
        help="Re-enable dead-zone, boundary, tracking-loss, and life-penalty gates.",
    )
    parser.add_argument(
        "--log-file",
        default=str(DEFAULT_LOG_PATH),
        help="Rotating crash/tracking log path (default: runtime-logs/game.log).",
    )
    parser.add_argument("--smoke-test", action="store_true", help=argparse.SUPPRESS)
    args = parser.parse_args(argv)

    if args.input == "sensor-scan" and args.enable_safety:
        parser.error("--input sensor-scan cannot be used with --enable-safety")

    log_path = configure_logging(args.log_file)
    logger.info("Parsed command line args=%s", vars(args))

    try:
        return run(
            smoke_test=args.smoke_test,
            input_source=args.input,
            safety_enabled=args.enable_safety,
        )
    except Exception:
        logger.exception("Unhandled game crash")
        print(f"Game crashed; diagnostic traceback written to {log_path}", file=sys.stderr)
        raise


if __name__ == "__main__":
    raise SystemExit(main())
