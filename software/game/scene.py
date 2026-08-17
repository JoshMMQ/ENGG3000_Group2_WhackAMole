"""Pygame scene drawing for the Whack-a-Mole prototype."""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING, Sequence

try:
    from .coordinates import ScreenPosition
except ImportError:
    from coordinates import ScreenPosition

if TYPE_CHECKING:
    try:
        from .sensor_overlay import SensorOverlaySnapshot, SensorOverlayValue
    except ImportError:
        from sensor_overlay import SensorOverlaySnapshot, SensorOverlayValue


DESERT_COLOR = (238, 149, 70)
SAND_LINE_COLOR = (209, 119, 54)
SAND_DARK = (178, 94, 45)
FIELD_GREEN = (130, 194, 71)
FIELD_GREEN_LIGHT = (164, 216, 89)
FIELD_GREEN_DARK = (93, 155, 55)
ROCK_DARK = (108, 62, 41)
ROCK_MID = (139, 84, 56)
ROCK_LIGHT = (166, 103, 72)
GRASS_DARK = (102, 156, 58)
GRASS_LIGHT = (159, 216, 83)
DIRT_DARK = (82, 52, 34)
DIRT_MID = (111, 73, 49)
DIRT_LIGHT = (129, 84, 55)
MOLE_BODY = (43, 45, 51)
MOLE_HIGHLIGHT_BODY = (65, 92, 180)
MOLE_CUTE_BODY = (136, 105, 78)
MOLE_CUTE_BODY_DARK = (72, 52, 39)
MOLE_CUTE_MUZZLE = (250, 188, 184)
MOLE_FACE = (189, 104, 76)
MOLE_FACE_DARK = (128, 57, 50)
MOLE_BLACK = (18, 19, 21)
HIT_FLASH_COLOR = (255, 231, 82)
WHITE = (255, 255, 255)
PANEL_DARK = (86, 40, 22)
BUTTON_GREEN = (86, 194, 112)
BUTTON_GREEN_DARK = (32, 126, 69)
BUTTON_YELLOW = (255, 218, 62)
BUTTON_YELLOW_DARK = (161, 128, 38)
TITLE_FILL = (255, 218, 155)
TITLE_SHADOW = (70, 22, 26)
TITLE_EDGE = (116, 49, 35)
CURSOR_COLOR = (64, 199, 255)
CURSOR_OUTLINE_COLOR = (248, 253, 255)
HAMMER_WOOD = (194, 119, 31)
HAMMER_WOOD_LIGHT = (231, 160, 55)
HAMMER_WOOD_DARK = (121, 72, 24)
SENSOR_OVERLAY_BACKGROUND = (28, 43, 53)
SENSOR_OVERLAY_PANEL = (42, 61, 72)
SENSOR_OVERLAY_LIVE = (42, 177, 105)
SENSOR_OVERLAY_WAITING = (224, 159, 42)
SENSOR_OVERLAY_ERROR = (211, 68, 60)
SENSOR_OVERLAY_UNKNOWN = (112, 126, 135)


RectTuple = tuple[int, int, int, int]


@dataclass(frozen=True)
class SensorOverlayLayout:
    """Pure rectangle layout for the optional two-reading USB strip."""

    container: RectTuple
    banner: RectTuple
    left_panel: RectTuple
    right_panel: RectTuple


@dataclass(frozen=True)
class GameplayUi:
    """Values displayed by the gameplay HUD."""

    score: int = 0
    lives: int = 3
    remaining_seconds: int = 60
    sensor_overlay: SensorOverlaySnapshot | None = None


def hole_positions(width: int, height: int) -> tuple[ScreenPosition, ...]:
    """Return the 3 x 3 mole-hole centres for a window size."""

    x_values = (round(width * 0.24), round(width * 0.50), round(width * 0.76))
    y_values = (round(height * 0.42), round(height * 0.62), round(height * 0.80))
    return tuple((x, y) for y in y_values for x in x_values)


def active_mole_position(width: int, height: int, active_hole_index: int = 4) -> ScreenPosition:
    """Return the current single active mole position."""

    holes = hole_positions(width, height)
    return holes[active_hole_index % len(holes)]


def start_button_rect(width: int, height: int) -> tuple[int, int, int, int]:
    """Return the title-screen start button rectangle."""

    button_width = round(width * 0.34)
    button_height = round(height * 0.11)
    return (
        (width - button_width) // 2,
        round(height * 0.68),
        button_width,
        button_height,
    )


def continue_button_rect(width: int, height: int) -> tuple[int, int, int, int]:
    """Return the game-over continue button rectangle."""

    button_width = round(width * 0.34)
    button_height = round(height * 0.11)
    return (
        (width - button_width) // 2,
        round(height * 0.66),
        button_width,
        button_height,
    )


def pause_button_rect(width: int, height: int) -> tuple[int, int, int, int]:
    """Return the gameplay pause button rectangle."""

    size = max(46, round(min(width, height) * 0.07))
    return (
        width - size - round(width * 0.025),
        round(height * 0.025),
        size,
        size,
    )


def sensor_overlay_layout(width: int, height: int) -> SensorOverlayLayout:
    """Return a responsive, non-overlapping layout for two USB readings."""

    if width <= 0 or height <= 0:
        raise ValueError("window dimensions must be positive")

    edge_margin = max(4, round(min(width, height) * 0.012))
    available_width = max(1, width - edge_margin * 2)
    container_width = min(
        available_width,
        max(min(280, available_width), min(720, round(width * 0.62))),
    )

    hud_top = round(height * 0.025)
    hud_height = max(54, round(height * 0.075))
    container_top = min(height - edge_margin, hud_top + hud_height + edge_margin)
    available_height = max(1, height - container_top - edge_margin)
    container_height = min(available_height, max(84, min(108, round(height * 0.12))))
    container_left = (width - container_width) // 2

    padding = min(
        max(2, round(min(container_width, container_height) * 0.055)),
        max(0, (container_width - 2) // 4),
    )
    inner_width = max(1, container_width - padding * 2)
    banner_height = min(
        max(14, round(container_height * 0.25)),
        max(1, container_height - padding * 3 - 1),
    )
    banner = (
        container_left + padding,
        container_top + padding,
        inner_width,
        banner_height,
    )

    panel_gap = min(max(2, round(container_width * 0.012)), max(0, inner_width - 2))
    left_width = max(1, (inner_width - panel_gap) // 2)
    right_width = max(1, inner_width - panel_gap - left_width)
    panel_top = banner[1] + banner[3] + padding
    panel_height = max(1, container_top + container_height - padding - panel_top)
    left_panel = (container_left + padding, panel_top, left_width, panel_height)
    right_panel = (left_panel[0] + left_width + panel_gap, panel_top, right_width, panel_height)

    return SensorOverlayLayout(
        container=(container_left, container_top, container_width, container_height),
        banner=banner,
        left_panel=left_panel,
        right_panel=right_panel,
    )


def draw_loading_screen(
    screen: object,
    progress: float,
    sensor_overlay: SensorOverlaySnapshot | None = None,
) -> None:
    """Draw the loading screen."""

    import pygame

    width, height = screen.get_size()
    screen.fill((105, 50, 24))
    _draw_title_logo(pygame, screen, width, height, scale=0.52, y_ratio=0.46)
    _draw_intro_characters(pygame, screen, width, height, scale=0.5, y_ratio=0.55)
    percent = max(0, min(100, round(progress * 100)))
    font = _font(pygame, width, 0.06, bold=True)
    text = font.render(f"{percent}%", True, WHITE)
    screen.blit(text, text.get_rect(center=(width // 2, round(height * 0.66))))
    if sensor_overlay is not None:
        _draw_sensor_overlay(pygame, screen, width, height, sensor_overlay)
    pygame.display.flip()


def draw_title_screen(
    screen: object,
    sensor_overlay: SensorOverlaySnapshot | None = None,
) -> None:
    """Draw the title/start screen."""

    import pygame

    width, height = screen.get_size()
    _draw_desert_background(pygame, screen, width, height)
    _draw_title_logo(pygame, screen, width, height, scale=1.0, y_ratio=0.28)
    _draw_intro_characters(pygame, screen, width, height, scale=1.0, y_ratio=0.50)
    _draw_start_button(pygame, screen, width, height)
    if sensor_overlay is not None:
        _draw_sensor_overlay(pygame, screen, width, height, sensor_overlay)
    pygame.display.flip()


def draw_scene(
    screen: object,
    cursor_position: ScreenPosition,
    ui: GameplayUi | None = None,
    active_hole_index: int = 4,
    mole_highlighted: bool = False,
    paused: bool = False,
    safety_alert: bool = False,
    screen_warning: bool = False,
) -> None:
    """Draw the current gameplay frame."""

    import pygame

    width, height = screen.get_size()
    active_ui = ui or GameplayUi()
    _draw_green_field_background(pygame, screen, width, height)
    _draw_gameplay_hud(pygame, screen, width, height, active_ui)
    if active_ui.sensor_overlay is not None:
        _draw_sensor_overlay(
            pygame,
            screen,
            width,
            height,
            active_ui.sensor_overlay,
        )
    _draw_holes(
        pygame,
        screen,
        hole_positions(width, height),
        width,
        height,
        active_index=active_hole_index,
        mole_highlighted=mole_highlighted,
    )
    _draw_cursor(pygame, screen, cursor_position)
    if safety_alert:
        _draw_safety_overlay(pygame, screen, width, height)
    elif screen_warning:
        _draw_screen_warning_overlay(pygame, screen, width, height)
    elif paused:
        _draw_pause_overlay(pygame, screen, width, height)
    pygame.display.flip()


def draw_game_over_screen(
    screen: object,
    score: int,
    sensor_overlay: SensorOverlaySnapshot | None = None,
) -> None:
    """Draw the game-over overlay."""

    import pygame

    width, height = screen.get_size()
    _draw_desert_background(pygame, screen, width, height)

    overlay = pygame.Surface((width, height), pygame.SRCALPHA)
    overlay.fill((75, 38, 20, 145))
    screen.blit(overlay, (0, 0))

    panel = pygame.Rect(round(width * 0.22), round(height * 0.24), round(width * 0.56), round(height * 0.55))
    pygame.draw.rect(screen, (247, 219, 183), panel.inflate(38, 38), border_radius=42)
    pygame.draw.rect(screen, (181, 123, 66), panel.inflate(38, 38), width=max(6, width // 120), border_radius=42)
    pygame.draw.rect(screen, (255, 246, 203), panel, border_radius=20)

    banner = pygame.Rect(round(width * 0.30), round(height * 0.20), round(width * 0.40), round(height * 0.13))
    pygame.draw.rect(screen, (211, 140, 67), banner, border_radius=18)
    pygame.draw.rect(screen, (126, 68, 37), banner, width=max(4, width // 150), border_radius=18)
    for x in (banner.left + 24, banner.right - 24):
        pygame.draw.circle(screen, (151, 86, 45), (x, banner.y + 24), max(6, width // 140))

    title_font = _font(pygame, width, 0.07, bold=True)
    score_font = _font(pygame, width, 0.10, bold=True)
    label_font = _font(pygame, width, 0.035, bold=True)
    _center_text(screen, title_font, "Game Over", WHITE, (width // 2, round(height * 0.265)))
    _center_text(screen, score_font, f"{score} PTS", (151, 92, 42), (width // 2, round(height * 0.43)))
    _center_text(screen, label_font, "Final score", (92, 54, 32), (width // 2, round(height * 0.53)))
    _draw_continue_button(pygame, screen, width, height)
    if sensor_overlay is not None:
        _draw_sensor_overlay(pygame, screen, width, height, sensor_overlay)
    pygame.display.flip()


def _draw_desert_background(pygame: object, screen: object, width: int, height: int) -> None:
    screen.fill(DESERT_COLOR)
    line_sets = (
        (0.08, 0.26, 0.14),
        (0.28, 0.18, 0.12),
        (0.54, 0.24, 0.16),
        (0.70, 0.34, 0.13),
        (0.16, 0.52, 0.11),
        (0.48, 0.58, 0.14),
        (0.78, 0.63, 0.16),
        (0.20, 0.82, 0.13),
        (0.56, 0.88, 0.16),
    )
    for x_ratio, y_ratio, length_ratio in line_sets:
        x = round(width * x_ratio)
        y = round(height * y_ratio)
        pygame.draw.arc(
            screen,
            SAND_LINE_COLOR,
            (x, y, round(width * length_ratio), round(height * 0.035)),
            0.1,
            2.9,
            max(2, width // 450),
        )
    _draw_rock(pygame, screen, (round(width * 0.03), round(height * 0.02)), round(width * 0.23), flip=False)
    _draw_rock(pygame, screen, (round(width * 0.78), round(height * 0.05)), round(width * 0.18), flip=True)
    _draw_rock(pygame, screen, (round(width * 0.00), round(height * 0.86)), round(width * 0.24), flip=False)
    _draw_rock(pygame, screen, (round(width * 0.75), round(height * 0.86)), round(width * 0.22), flip=True)
    _draw_rock(pygame, screen, (round(width * 0.58), round(height * -0.02)), round(width * 0.12), flip=True)
    for x_ratio, y_ratio, scale in ((0.07, 0.22, 0.9), (0.86, 0.13, 0.8), (0.88, 0.94, 0.7), (0.16, 0.98, 0.75)):
        _draw_grass(pygame, screen, round(width * x_ratio), round(height * y_ratio), max(18, round(width * 0.035 * scale)))
    for x_ratio, y_ratio, scale in ((0.18, 0.42, 0.25), (0.82, 0.42, 0.3), (0.38, 0.86, 0.25), (0.95, 0.67, 0.32)):
        _draw_small_rock(pygame, screen, round(width * x_ratio), round(height * y_ratio), max(8, round(width * 0.03 * scale)))


def _draw_green_field_background(pygame: object, screen: object, width: int, height: int) -> None:
    screen.fill(FIELD_GREEN)
    pygame.draw.ellipse(screen, FIELD_GREEN_LIGHT, (-round(width * 0.18), round(height * 0.12), round(width * 0.80), round(height * 0.54)))
    pygame.draw.ellipse(
        screen,
        (145, 207, 76),
        (round(width * 0.40), round(height * 0.20), round(width * 0.86), round(height * 0.50)),
    )
    pygame.draw.ellipse(
        screen,
        FIELD_GREEN_DARK,
        (-round(width * 0.06), round(height * 0.82), round(width * 0.68), round(height * 0.22)),
    )
    for x_ratio, y_ratio, length_ratio in (
        (0.10, 0.26, 0.10),
        (0.35, 0.22, 0.14),
        (0.62, 0.30, 0.12),
        (0.18, 0.55, 0.13),
        (0.48, 0.52, 0.11),
        (0.72, 0.62, 0.14),
        (0.27, 0.86, 0.15),
        (0.58, 0.84, 0.12),
    ):
        x = round(width * x_ratio)
        y = round(height * y_ratio)
        pygame.draw.arc(
            screen,
            (110, 176, 62),
            (x, y, round(width * length_ratio), round(height * 0.035)),
            0.1,
            2.9,
            max(2, width // 500),
        )
    _draw_rock(pygame, screen, (round(width * 0.03), round(height * 0.03)), round(width * 0.20), flip=False)
    _draw_rock(pygame, screen, (round(width * 0.76), round(height * 0.06)), round(width * 0.18), flip=True)
    _draw_rock(pygame, screen, (round(width * 0.03), round(height * 0.88)), round(width * 0.18), flip=False)
    _draw_rock(pygame, screen, (round(width * 0.78), round(height * 0.86)), round(width * 0.18), flip=True)
    for x_ratio, y_ratio, scale in ((0.07, 0.25, 0.9), (0.86, 0.15, 0.8), (0.88, 0.95, 0.7), (0.16, 0.96, 0.75)):
        _draw_grass(pygame, screen, round(width * x_ratio), round(height * y_ratio), max(18, round(width * 0.035 * scale)))
    for x_ratio, y_ratio, scale in ((0.18, 0.42, 0.25), (0.82, 0.42, 0.3), (0.38, 0.86, 0.25), (0.95, 0.67, 0.32)):
        _draw_small_rock(pygame, screen, round(width * x_ratio), round(height * y_ratio), max(8, round(width * 0.03 * scale)))


def _draw_rock(pygame: object, screen: object, top_left: ScreenPosition, size: int, flip: bool) -> None:
    x, y = top_left
    points = [
        (x, y + round(size * 0.55)),
        (x + round(size * 0.17), y + round(size * 0.18)),
        (x + round(size * 0.43), y),
        (x + round(size * 0.80), y + round(size * 0.11)),
        (x + size, y + round(size * 0.45)),
        (x + round(size * 0.72), y + round(size * 0.75)),
        (x + round(size * 0.28), y + round(size * 0.72)),
    ]
    if flip:
        points = [(x + size - (px - x), py) for px, py in points]
    pygame.draw.polygon(screen, ROCK_MID, points)
    pygame.draw.polygon(screen, ROCK_LIGHT, points[:4])
    pygame.draw.polygon(screen, ROCK_DARK, [points[0], points[-1], points[-2], points[-3]])
    pygame.draw.lines(screen, (152, 95, 66), False, points, max(2, size // 70))


def _draw_small_rock(pygame: object, screen: object, x: int, y: int, radius: int) -> None:
    points = (
        (x - radius, y + radius // 2),
        (x - radius // 2, y - radius // 2),
        (x + radius // 2, y - radius),
        (x + radius, y),
        (x + radius // 2, y + radius),
    )
    pygame.draw.polygon(screen, ROCK_MID, points)
    pygame.draw.polygon(screen, ROCK_DARK, (points[0], points[3], points[4]))


def _draw_grass(pygame: object, screen: object, x: int, y: int, size: int) -> None:
    for offset, height_scale in ((-0.9, 1.1), (-0.45, 0.8), (0.0, 1.25), (0.45, 0.9), (0.9, 1.05)):
        tip = (x + round(size * offset), y - round(size * height_scale))
        base = (x, y)
        ctrl = (x + round(size * offset * 0.25), y - round(size * height_scale * 0.6))
        pygame.draw.lines(screen, GRASS_DARK, False, (base, ctrl, tip), max(3, size // 8))
        pygame.draw.lines(screen, GRASS_LIGHT, False, ((base[0] + 2, base[1]), (ctrl[0] + 2, ctrl[1]), (tip[0] + 2, tip[1])), max(2, size // 11))


def _draw_title_logo(
    pygame: object,
    screen: object,
    width: int,
    height: int,
    scale: float,
    y_ratio: float,
) -> None:
    font = _font(pygame, width, 0.085 * scale, bold=True)
    text = "WHACK-A-MOLE"
    center = (width // 2, round(height * y_ratio))
    for offset, color in (((5, 7), TITLE_SHADOW), ((2, 3), TITLE_EDGE), ((0, 0), TITLE_FILL)):
        surface = font.render(text, True, color)
        screen.blit(surface, surface.get_rect(center=(center[0] + offset[0], center[1] + offset[1])))


def _draw_intro_characters(
    pygame: object,
    screen: object,
    width: int,
    height: int,
    scale: float,
    y_ratio: float,
) -> None:
    centres = (
        (round(width * 0.36), round(height * y_ratio)),
        (round(width * 0.50), round(height * y_ratio)),
        (round(width * 0.64), round(height * y_ratio)),
    )
    size_w = max(42, round(width * 0.10 * scale))
    size_h = max(74, round(height * 0.22 * scale))
    _draw_mole_shape(pygame, screen, centres[0], size_w, size_h, "plain")
    _draw_mole_shape(pygame, screen, centres[1], size_w, size_h, "open")
    _draw_bomb_mole(pygame, screen, centres[2], size_w, size_h)


def _draw_start_button(pygame: object, screen: object, width: int, height: int) -> None:
    rect = pygame.Rect(start_button_rect(width, height))
    shadow = rect.move(0, max(5, height // 90))
    pygame.draw.rect(screen, BUTTON_YELLOW_DARK, shadow, border_radius=round(rect.height * 0.35))
    pygame.draw.rect(screen, (255, 198, 48), rect, border_radius=round(rect.height * 0.35))
    pygame.draw.rect(screen, (255, 231, 82), rect.inflate(-10, -10), border_radius=round(rect.height * 0.28))
    pygame.draw.circle(screen, (255, 255, 180), (rect.left + rect.width // 8, rect.top + rect.height // 4), max(4, rect.width // 45))
    font = _font(pygame, width, 0.05, bold=True)
    _center_text(screen, font, "Start", WHITE, rect.center)


def _draw_continue_button(pygame: object, screen: object, width: int, height: int) -> None:
    rect = pygame.Rect(continue_button_rect(width, height))
    shadow = rect.move(0, max(6, height // 85))
    pygame.draw.rect(screen, BUTTON_GREEN_DARK, shadow, border_radius=round(rect.height * 0.25))
    pygame.draw.rect(screen, BUTTON_GREEN, rect, border_radius=round(rect.height * 0.25))
    pygame.draw.rect(screen, (111, 211, 130), rect.inflate(-10, -12), border_radius=round(rect.height * 0.2))
    font = _font(pygame, width, 0.048, bold=True)
    _center_text(screen, font, "Continue", WHITE, rect.center)


def _draw_gameplay_hud(pygame: object, screen: object, width: int, height: int, ui: GameplayUi) -> None:
    panel_h = max(54, round(height * 0.075))
    left_panel = pygame.Rect(round(width * 0.075), round(height * 0.025), round(width * 0.17), panel_h)
    timer_panel = pygame.Rect(round(width * 0.27), round(height * 0.025), round(width * 0.23), panel_h)
    pause_panel = pygame.Rect(pause_button_rect(width, height))
    pygame.draw.rect(screen, PANEL_DARK, left_panel, border_radius=8)
    pygame.draw.rect(screen, PANEL_DARK, timer_panel, border_radius=8)
    _draw_heart(pygame, screen, (left_panel.left - round(panel_h * 0.10), left_panel.centery), round(panel_h * 0.48))
    hud_font = _font(pygame, width, 0.042, bold=True)
    small_font = _font(pygame, width, 0.026, bold=True)
    lives_surface = hud_font.render(f"x {ui.lives}", True, WHITE)
    screen.blit(lives_surface, lives_surface.get_rect(center=(left_panel.centerx + round(left_panel.width * 0.12), left_panel.centery)))
    _draw_hourglass(pygame, screen, (timer_panel.left + round(panel_h * 0.42), timer_panel.centery), round(panel_h * 0.65))
    minutes = max(0, ui.remaining_seconds) // 60
    seconds = max(0, ui.remaining_seconds) % 60
    time_surface = hud_font.render(f"{minutes:02d}:{seconds:02d}", True, WHITE)
    screen.blit(time_surface, time_surface.get_rect(center=(timer_panel.centerx + round(timer_panel.width * 0.12), timer_panel.centery)))
    score_surface = small_font.render(f"{ui.score} PTS", True, (72, 38, 22))
    score_width = round(width * 0.12)
    score_rect = pygame.Rect(pause_panel.left - round(width * 0.018) - score_width, round(height * 0.025), score_width, panel_h)
    pygame.draw.rect(screen, (255, 230, 88), score_rect, border_radius=8)
    pygame.draw.rect(screen, BUTTON_YELLOW_DARK, score_rect, width=3, border_radius=8)
    screen.blit(score_surface, score_surface.get_rect(center=score_rect.center))
    _draw_pause_button(pygame, screen, pause_panel, active=False)


def _draw_sensor_overlay(
    pygame: object,
    screen: object,
    width: int,
    height: int,
    snapshot: SensorOverlaySnapshot,
) -> None:
    layout = sensor_overlay_layout(width, height)
    container = pygame.Rect(layout.container)
    banner = pygame.Rect(layout.banner)
    shadow_offset = max(2, round(container.height * 0.05))
    pygame.draw.rect(
        screen,
        (18, 29, 36),
        container.move(0, shadow_offset),
        border_radius=max(6, round(container.height * 0.10)),
    )
    pygame.draw.rect(
        screen,
        SENSOR_OVERLAY_BACKGROUND,
        container,
        border_radius=max(6, round(container.height * 0.10)),
    )
    pygame.draw.rect(
        screen,
        (222, 234, 238),
        container,
        width=max(1, round(container.height * 0.025)),
        border_radius=max(6, round(container.height * 0.10)),
    )

    pygame.draw.rect(
        screen,
        (72, 86, 93),
        banner,
        border_radius=max(3, banner.height // 4),
    )
    banner_font = _fitted_font(
        pygame,
        "USB DIAGNOSTIC — NOT GAMEPLAY INPUT",
        banner.width - max(6, banner.width // 30),
        max(9, round(banner.height * 0.56)),
        bold=True,
    )
    _center_text(
        screen,
        banner_font,
        "USB DIAGNOSTIC — NOT GAMEPLAY INPUT",
        WHITE,
        banner.center,
    )

    _draw_sensor_overlay_value(pygame, screen, pygame.Rect(layout.left_panel), snapshot.left, "LEFT")
    _draw_sensor_overlay_value(pygame, screen, pygame.Rect(layout.right_panel), snapshot.right, "RIGHT")


def _draw_sensor_overlay_value(
    pygame: object,
    screen: object,
    panel: object,
    value: SensorOverlayValue,
    fallback_label: str,
) -> None:
    status = str(value.status).strip().upper()
    status_color = _sensor_status_color(status)
    radius = max(3, round(panel.height * 0.10))
    pygame.draw.rect(screen, SENSOR_OVERLAY_PANEL, panel, border_radius=radius)
    pygame.draw.rect(screen, status_color, panel, width=max(2, round(panel.height * 0.055)), border_radius=radius)

    label = str(value.label).strip().upper() or fallback_label
    label_font = _fitted_font(
        pygame,
        label,
        max(1, round(panel.width * 0.38)),
        max(9, round(panel.height * 0.20)),
        bold=True,
    )
    label_surface = label_font.render(label, True, WHITE)
    label_rect = label_surface.get_rect(
        midleft=(panel.left + max(5, round(panel.width * 0.045)), panel.top + round(panel.height * 0.22))
    )
    screen.blit(label_surface, label_rect)

    status_font = _fitted_font(
        pygame,
        status,
        max(1, round(panel.width * 0.50)),
        max(8, round(panel.height * 0.18)),
        bold=True,
    )
    status_surface = status_font.render(status, True, WHITE)
    status_padding_x = max(4, round(panel.width * 0.025))
    status_padding_y = max(2, round(panel.height * 0.035))
    status_badge = status_surface.get_rect(
        midright=(panel.right - max(5, round(panel.width * 0.045)), panel.top + round(panel.height * 0.22))
    ).inflate(status_padding_x * 2, status_padding_y * 2)
    pygame.draw.rect(screen, status_color, status_badge, border_radius=status_badge.height // 2)
    screen.blit(status_surface, status_surface.get_rect(center=status_badge.center))

    distance_text = "--- mm" if value.distance_mm is None else f"{value.distance_mm:.1f} mm"
    distance_font = _fitted_font(
        pygame,
        distance_text,
        max(1, panel.width - max(10, round(panel.width * 0.10))),
        max(12, round(panel.height * 0.34)),
        bold=True,
    )
    _center_text(
        screen,
        distance_font,
        distance_text,
        WHITE,
        (panel.centerx, panel.top + round(panel.height * 0.57)),
    )

    port_text = str(value.port).strip()
    port_font = _fitted_font(
        pygame,
        port_text,
        max(1, panel.width - max(10, round(panel.width * 0.10))),
        max(8, round(panel.height * 0.16)),
    )
    _center_text(
        screen,
        port_font,
        port_text,
        (196, 211, 217),
        (panel.centerx, panel.top + round(panel.height * 0.84)),
    )


def _sensor_status_color(status: str) -> tuple[int, int, int]:
    if status == "LIVE":
        return SENSOR_OVERLAY_LIVE
    if status in {"WAITING", "STALE"}:
        return SENSOR_OVERLAY_WAITING
    if status in {"NO ECHO", "ID MISMATCH", "PORT ERROR"}:
        return SENSOR_OVERLAY_ERROR
    return SENSOR_OVERLAY_UNKNOWN


def _draw_pause_button(pygame: object, screen: object, rect: object, active: bool) -> None:
    color = (255, 230, 88) if active else BUTTON_GREEN
    shadow_color = BUTTON_YELLOW_DARK if active else BUTTON_GREEN_DARK
    pygame.draw.rect(screen, shadow_color, rect.move(0, max(4, rect.height // 10)), border_radius=8)
    pygame.draw.rect(screen, color, rect, border_radius=8)
    bar_width = max(6, rect.width // 6)
    bar_height = round(rect.height * 0.50)
    gap = max(6, rect.width // 8)
    for offset in (-gap, gap):
        pygame.draw.rect(
            screen,
            WHITE,
            (
                rect.centerx + offset - bar_width // 2,
                rect.centery - bar_height // 2,
                bar_width,
                bar_height,
            ),
            border_radius=3,
        )


def _draw_pause_overlay(pygame: object, screen: object, width: int, height: int) -> None:
    overlay = pygame.Surface((width, height), pygame.SRCALPHA)
    overlay.fill((20, 35, 20, 140))
    screen.blit(overlay, (0, 0))
    panel = pygame.Rect(round(width * 0.28), round(height * 0.35), round(width * 0.44), round(height * 0.22))
    pygame.draw.rect(screen, (255, 246, 203), panel, border_radius=18)
    pygame.draw.rect(screen, (126, 68, 37), panel, width=max(4, width // 180), border_radius=18)
    title_font = _font(pygame, width, 0.07, bold=True)
    label_font = _font(pygame, width, 0.026, bold=True)
    _center_text(screen, title_font, "Paused", (72, 38, 22), (width // 2, round(height * 0.425)))
    _center_text(screen, label_font, "Click pause or press P to resume", (92, 54, 32), (width // 2, round(height * 0.505)))
    _draw_pause_button(pygame, screen, pygame.Rect(pause_button_rect(width, height)), active=True)


def _draw_safety_overlay(pygame: object, screen: object, width: int, height: int) -> None:
    overlay = pygame.Surface((width, height), pygame.SRCALPHA)
    overlay.fill((88, 24, 18, 165))
    screen.blit(overlay, (0, 0))
    panel = pygame.Rect(round(width * 0.18), round(height * 0.31), round(width * 0.64), round(height * 0.32))
    pygame.draw.rect(screen, (255, 246, 203), panel, border_radius=18)
    pygame.draw.rect(screen, (192, 68, 45), panel, width=max(5, width // 150), border_radius=18)
    title_font = _font(pygame, width, 0.055, bold=True)
    label_font = _font(pygame, width, 0.028, bold=True)
    small_font = _font(pygame, width, 0.022, bold=True)
    _center_text(screen, title_font, "Safety Pause", (151, 44, 31), (width // 2, round(height * 0.39)))
    _center_text(screen, label_font, "Step back inside the 1.50 x 1.40 m play area", (72, 38, 22), (width // 2, round(height * 0.48)))
    _center_text(screen, small_font, "One life lost. Click pause or press P to resume.", (92, 54, 32), (width // 2, round(height * 0.55)))
    _draw_pause_button(pygame, screen, pygame.Rect(pause_button_rect(width, height)), active=True)


def _draw_screen_warning_overlay(pygame: object, screen: object, width: int, height: int) -> None:
    overlay = pygame.Surface((width, height), pygame.SRCALPHA)
    overlay.fill((120, 78, 10, 150))
    screen.blit(overlay, (0, 0))
    panel = pygame.Rect(round(width * 0.16), round(height * 0.30), round(width * 0.68), round(height * 0.30))
    pygame.draw.rect(screen, (255, 246, 203), panel, border_radius=18)
    pygame.draw.rect(screen, (236, 165, 33), panel, width=max(5, width // 150), border_radius=18)
    title_font = _font(pygame, width, 0.055, bold=True)
    label_font = _font(pygame, width, 0.028, bold=True)
    small_font = _font(pygame, width, 0.022, bold=True)
    _center_text(screen, title_font, "Too Close To Screen", (139, 82, 14), (width // 2, round(height * 0.38)))
    _center_text(screen, label_font, "Step back from the screen", (72, 38, 22), (width // 2, round(height * 0.47)))
    _center_text(screen, small_font, "Game resumes when you move past the clear zone.", (92, 54, 32), (width // 2, round(height * 0.535)))


def _draw_holes(
    pygame: object,
    screen: object,
    holes: Sequence[ScreenPosition],
    width: int,
    height: int,
    active_index: int | None = None,
    mole_highlighted: bool = False,
) -> None:
    hole_w = round(width * 0.15)
    hole_h = round(height * 0.075)
    for index, (x, y) in enumerate(holes):
        if index == active_index:
            _draw_active_hole(pygame, screen, x, y, width, height, hole_w, hole_h, mole_highlighted)
        else:
            _draw_hole(pygame, screen, x, y, hole_w, hole_h)


def _draw_active_hole(
    pygame: object,
    screen: object,
    x: int,
    y: int,
    width: int,
    height: int,
    hole_w: int,
    hole_h: int,
    mole_highlighted: bool,
) -> None:
    _draw_hole(pygame, screen, x, y, hole_w, hole_h)
    if mole_highlighted:
        pygame.draw.ellipse(
            screen,
            HIT_FLASH_COLOR,
            (x - round(hole_w * 0.62), y - round(hole_h * 0.62), round(hole_w * 1.24), round(hole_h * 1.24)),
            width=max(4, hole_w // 18),
        )
    mole_w = round(width * 0.12)
    mole_h = round(height * 0.18)
    _draw_cute_mole(
        pygame,
        screen,
        (x, y - round(hole_h * 1.10)),
        mole_w,
        mole_h,
        highlighted=mole_highlighted,
    )
    _draw_dirt_mound(pygame, screen, x, y + round(hole_h * 0.18), round(hole_w * 1.20), round(hole_h * 0.72))


def _draw_hole(pygame: object, screen: object, x: int, y: int, hole_w: int, hole_h: int) -> None:
    _draw_dirt_mound(pygame, screen, x, y, round(hole_w * 1.18), round(hole_h * 0.92))
    pygame.draw.ellipse(
        screen,
        DIRT_DARK,
        (x - hole_w // 2, y - hole_h // 2, hole_w, hole_h),
    )
    pygame.draw.ellipse(
        screen,
        (47, 31, 20),
        (x - round(hole_w * 0.39), y - round(hole_h * 0.32), round(hole_w * 0.78), round(hole_h * 0.64)),
    )


def _draw_dirt_mound(pygame: object, screen: object, x: int, y: int, mound_w: int, mound_h: int) -> None:
    pygame.draw.ellipse(screen, (105, 61, 39), (x - mound_w // 2, y + mound_h // 6, mound_w, mound_h // 2))
    offsets = (-0.42, -0.24, -0.08, 0.08, 0.25, 0.42)
    for i, offset in enumerate(offsets):
        radius = max(8, round(mound_h * (0.42 if i % 2 else 0.52)))
        color = (DIRT_LIGHT, DIRT_MID, DIRT_DARK)[i % 3]
        pygame.draw.circle(screen, color, (x + round(mound_w * offset), y + round(mound_h * 0.16 * (i % 2))), radius)
    pygame.draw.ellipse(screen, DIRT_MID, (x - mound_w // 2, y, mound_w, mound_h))


def _draw_mole(
    pygame: object,
    screen: object,
    centre: ScreenPosition,
    width: int,
    height: int,
    variant: str,
) -> None:
    x, y = centre
    _draw_mole_shape(pygame, screen, (x, y - round(height * 0.055)), round(width * 0.12), round(height * 0.20), variant)
    _draw_dirt_mound(pygame, screen, x, y + round(height * 0.04), round(width * 0.17), round(height * 0.07))


def _draw_cute_mole(
    pygame: object,
    screen: object,
    centre: ScreenPosition,
    body_w: int,
    body_h: int,
    highlighted: bool,
) -> None:
    x, y = centre
    body_color = (161, 124, 88) if highlighted else MOLE_CUTE_BODY
    if highlighted:
        pygame.draw.ellipse(
            screen,
            HIT_FLASH_COLOR,
            (
                x - round(body_w * 0.68),
                y - round(body_h * 0.50),
                round(body_w * 1.36),
                round(body_h * 1.02),
            ),
            width=max(4, body_w // 18),
        )

    body_rect = pygame.Rect(
        x - round(body_w * 0.44),
        y - round(body_h * 0.50),
        round(body_w * 0.88),
        round(body_h * 0.92),
    )
    pygame.draw.ellipse(screen, MOLE_CUTE_BODY_DARK, body_rect.inflate(max(4, body_w // 18), max(4, body_w // 18)))
    pygame.draw.ellipse(screen, body_color, body_rect)

    muzzle_radius = max(16, round(body_w * 0.20))
    pygame.draw.circle(screen, MOLE_CUTE_MUZZLE, (x, y - round(body_h * 0.08)), muzzle_radius)
    pygame.draw.circle(screen, MOLE_CUTE_BODY_DARK, (x, y - round(body_h * 0.20)), max(7, round(body_w * 0.07)))
    pygame.draw.circle(screen, (58, 45, 42), (x - round(body_w * 0.27), y - round(body_h * 0.18)), max(5, round(body_w * 0.05)))
    pygame.draw.circle(screen, (58, 45, 42), (x + round(body_w * 0.27), y - round(body_h * 0.18)), max(5, round(body_w * 0.05)))
    pygame.draw.line(screen, MOLE_CUTE_BODY_DARK, (x, y - round(body_h * 0.13)), (x, y + round(body_h * 0.02)), max(3, body_w // 28))
    pygame.draw.line(
        screen,
        MOLE_CUTE_BODY_DARK,
        (x, y + round(body_h * 0.02)),
        (x - round(body_w * 0.10), y + round(body_h * 0.12)),
        max(3, body_w // 32),
    )
    pygame.draw.line(
        screen,
        MOLE_CUTE_BODY_DARK,
        (x, y + round(body_h * 0.02)),
        (x + round(body_w * 0.10), y + round(body_h * 0.12)),
        max(3, body_w // 32),
    )

    for side in (-1, 1):
        paw_centre = (x + side * round(body_w * 0.44), y + round(body_h * 0.30))
        paw_rect = pygame.Rect(0, 0, round(body_w * 0.34), round(body_h * 0.22))
        paw_rect.center = paw_centre
        pygame.draw.ellipse(screen, MOLE_CUTE_BODY_DARK, paw_rect.inflate(max(3, body_w // 30), max(3, body_w // 30)))
        pygame.draw.ellipse(screen, MOLE_CUTE_MUZZLE, paw_rect)
        for claw in (-1, 0, 1):
            claw_x = paw_centre[0] + side * round(body_w * (0.10 + claw * 0.055))
            claw_y = paw_centre[1] + round(body_h * 0.05)
            pygame.draw.polygon(
                screen,
                WHITE,
                (
                    (claw_x, claw_y),
                    (claw_x + side * round(body_w * 0.12), claw_y + round(body_h * 0.03)),
                    (claw_x + side * round(body_w * 0.02), claw_y + round(body_h * 0.11)),
                ),
            )

    if highlighted:
        marker_font = _font(pygame, body_w * 6, 0.045, bold=True)
        _center_text(screen, marker_font, "HIT", WHITE, (x, y - round(body_h * 0.58)))


def _draw_mole_shape(
    pygame: object,
    screen: object,
    centre: ScreenPosition,
    body_w: int,
    body_h: int,
    variant: str,
) -> None:
    x, y = centre
    body_rect = pygame.Rect(x - body_w // 2, y - body_h // 2, body_w, body_h)
    body_color = MOLE_HIGHLIGHT_BODY if variant == "hit" else MOLE_BODY
    pygame.draw.ellipse(screen, body_color, body_rect)
    eye_y = y - round(body_h * 0.16)
    for eye_x in (x - round(body_w * 0.28), x + round(body_w * 0.28)):
        pygame.draw.circle(screen, MOLE_BLACK, (eye_x, eye_y), max(6, body_w // 13))
        pygame.draw.circle(screen, WHITE, (eye_x + max(1, body_w // 35), eye_y - max(1, body_w // 35)), max(2, body_w // 28))
    face_rect = pygame.Rect(x - round(body_w * 0.18), y + round(body_h * 0.02), round(body_w * 0.36), round(body_h * 0.26))
    pygame.draw.ellipse(screen, MOLE_FACE, face_rect)
    if variant == "hit":
        pygame.draw.line(
            screen,
            WHITE,
            (x - round(body_w * 0.18), y - round(body_h * 0.05)),
            (x - round(body_w * 0.04), y + round(body_h * 0.08)),
            max(4, body_w // 18),
        )
        pygame.draw.line(
            screen,
            WHITE,
            (x - round(body_w * 0.04), y - round(body_h * 0.05)),
            (x - round(body_w * 0.18), y + round(body_h * 0.08)),
            max(4, body_w // 18),
        )
        pygame.draw.line(
            screen,
            WHITE,
            (x + round(body_w * 0.04), y - round(body_h * 0.05)),
            (x + round(body_w * 0.18), y + round(body_h * 0.08)),
            max(4, body_w // 18),
        )
        pygame.draw.line(
            screen,
            WHITE,
            (x + round(body_w * 0.18), y - round(body_h * 0.05)),
            (x + round(body_w * 0.04), y + round(body_h * 0.08)),
            max(4, body_w // 18),
        )
    elif variant == "open":
        pygame.draw.ellipse(screen, MOLE_FACE_DARK, (x - round(body_w * 0.12), y + round(body_h * 0.12), round(body_w * 0.24), round(body_h * 0.20)))
    else:
        pygame.draw.ellipse(screen, MOLE_BLACK, (x - round(body_w * 0.07), y + round(body_h * 0.12), round(body_w * 0.14), round(body_h * 0.07)))
    for paw_x in (x - round(body_w * 0.43), x + round(body_w * 0.43)):
        pygame.draw.ellipse(screen, WHITE, (paw_x - body_w // 8, y + round(body_h * 0.30), body_w // 4, body_h // 6))
        for claw in (-1, 0, 1):
            pygame.draw.line(
                screen,
                MOLE_FACE,
                (paw_x + claw * body_w // 18, y + round(body_h * 0.31)),
                (paw_x + claw * body_w // 20, y + round(body_h * 0.42)),
                max(2, body_w // 34),
            )


def _draw_bomb_mole(pygame: object, screen: object, centre: ScreenPosition, body_w: int, body_h: int) -> None:
    x, y = centre
    radius = body_w // 2
    pygame.draw.circle(screen, MOLE_BLACK, (x, y), radius)
    pygame.draw.circle(screen, (80, 83, 83), (x - radius // 3, y - radius // 3), max(6, radius // 8))
    pygame.draw.circle(screen, (46, 49, 49), (x + radius // 4, y + radius // 3), max(5, radius // 10))
    pygame.draw.circle(screen, (72, 76, 76), (x - radius // 4, y - radius), max(8, radius // 4))
    pygame.draw.line(screen, MOLE_BLACK, (x - radius // 7, y - radius), (x + radius, y - radius - body_h // 4), max(6, body_w // 14))
    pygame.draw.circle(screen, (255, 80, 25), (x + radius + body_w // 16, y - radius - body_h // 4), max(12, body_w // 7))
    pygame.draw.circle(screen, (255, 180, 42), (x + radius + body_w // 16, y - radius - body_h // 4), max(6, body_w // 10))


def _draw_score_pop(pygame: object, screen: object, centre: ScreenPosition, width: int, height: int) -> None:
    x, y = centre
    rect = pygame.Rect(x - round(width * 0.08), y + round(height * 0.05), round(width * 0.16), round(height * 0.07))
    pygame.draw.rect(screen, BUTTON_GREEN_DARK, rect.move(0, max(5, height // 120)), border_radius=14)
    pygame.draw.rect(screen, (148, 230, 81), rect, border_radius=14)
    pygame.draw.rect(screen, (71, 166, 53), rect, width=max(3, width // 250), border_radius=14)
    font = _font(pygame, width, 0.034, bold=True)
    _center_text(screen, font, "+100PTS", (35, 43, 62), rect.center)


def _draw_heart(pygame: object, screen: object, centre: ScreenPosition, size: int) -> None:
    x, y = centre
    pygame.draw.circle(screen, (236, 15, 86), (x - size // 3, y - size // 5), size // 2)
    pygame.draw.circle(screen, (236, 15, 86), (x + size // 3, y - size // 5), size // 2)
    pygame.draw.polygon(screen, (199, 16, 73), ((x - size, y - size // 8), (x + size, y - size // 8), (x, y + size)))
    pygame.draw.circle(screen, (255, 66, 129), (x - size // 3, y - size // 3), size // 4)


def _draw_hourglass(pygame: object, screen: object, centre: ScreenPosition, size: int) -> None:
    x, y = centre
    w = round(size * 0.55)
    h = size
    pygame.draw.rect(screen, (138, 73, 38), (x - w // 2, y - h // 2, w, max(5, h // 12)), border_radius=3)
    pygame.draw.rect(screen, (138, 73, 38), (x - w // 2, y + h // 2 - max(5, h // 12), w, max(5, h // 12)), border_radius=3)
    pygame.draw.polygon(screen, WHITE, ((x - w // 2, y - h // 2 + 6), (x + w // 2, y - h // 2 + 6), (x, y)))
    pygame.draw.polygon(screen, WHITE, ((x - w // 2, y + h // 2 - 6), (x + w // 2, y + h // 2 - 6), (x, y)))
    pygame.draw.polygon(screen, (255, 211, 45), ((x - w // 3, y - h // 3), (x + w // 3, y - h // 3), (x, y - h // 10)))
    pygame.draw.polygon(screen, (255, 211, 45), ((x - w // 4, y + h // 3), (x + w // 4, y + h // 3), (x, y + h // 10)))


def _draw_cursor(pygame: object, screen: object, cursor_position: ScreenPosition) -> None:
    x, y = cursor_position
    size = max(42, round(min(screen.get_size()) * 0.085))
    handle_start = (x + round(size * 0.42), y + round(size * 0.34))
    handle_end = (x - round(size * 0.32), y - round(size * 0.36))
    pygame.draw.line(screen, HAMMER_WOOD_DARK, handle_start, handle_end, max(10, size // 5))
    pygame.draw.line(screen, HAMMER_WOOD, handle_start, handle_end, max(7, size // 7))
    pygame.draw.line(
        screen,
        HAMMER_WOOD_LIGHT,
        (handle_start[0] - round(size * 0.04), handle_start[1] - round(size * 0.04)),
        (handle_end[0] - round(size * 0.04), handle_end[1] - round(size * 0.04)),
        max(2, size // 24),
    )

    head = (
        (x - round(size * 0.75), y - round(size * 0.48)),
        (x - round(size * 0.32), y - round(size * 0.86)),
        (x + round(size * 0.14), y - round(size * 0.42)),
        (x - round(size * 0.28), y - round(size * 0.03)),
    )
    pygame.draw.polygon(screen, HAMMER_WOOD_DARK, head)
    inset_head = (
        (x - round(size * 0.66), y - round(size * 0.48)),
        (x - round(size * 0.32), y - round(size * 0.78)),
        (x + round(size * 0.04), y - round(size * 0.42)),
        (x - round(size * 0.29), y - round(size * 0.12)),
    )
    pygame.draw.polygon(screen, HAMMER_WOOD_LIGHT, inset_head)
    for offset in (-0.22, 0.0, 0.22):
        pygame.draw.line(
            screen,
            HAMMER_WOOD_DARK,
            (x - round(size * (0.58 - offset)), y - round(size * 0.50)),
            (x - round(size * (0.36 - offset)), y - round(size * 0.68)),
            max(2, size // 28),
        )
    pygame.draw.circle(screen, (35, 58, 42), (x, y), max(4, size // 14), width=max(2, size // 34))


def _font(pygame: object, width: int, ratio: float, bold: bool = False) -> object:
    return pygame.font.SysFont("arial", max(18, round(width * ratio)), bold=bold)


def _fitted_font(
    pygame: object,
    text: str,
    max_width: int,
    preferred_size: int,
    bold: bool = False,
) -> object:
    """Return the largest compact font up to ``preferred_size`` that fits."""

    size = max(7, preferred_size)
    while size > 7:
        font = pygame.font.SysFont("arial", size, bold=bold)
        if font.size(text)[0] <= max_width:
            return font
        size -= 1
    return pygame.font.SysFont("arial", 7, bold=bold)


def _center_text(screen: object, font: object, text: str, color: tuple[int, int, int], center: ScreenPosition) -> None:
    surface = font.render(text, True, color)
    screen.blit(surface, surface.get_rect(center=center))
