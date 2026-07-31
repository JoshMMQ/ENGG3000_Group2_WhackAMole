"""Pygame scene drawing for the Whack-a-Mole prototype."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Sequence

try:
    from .coordinates import ScreenPosition
except ImportError:
    from coordinates import ScreenPosition


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
MOLE_FACE = (189, 104, 76)
MOLE_FACE_DARK = (128, 57, 50)
MOLE_BLACK = (18, 19, 21)
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


@dataclass(frozen=True)
class GameplayUi:
    """Values displayed by the gameplay HUD."""

    score: int = 0
    lives: int = 3
    remaining_seconds: int = 60


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


def draw_loading_screen(screen: object, progress: float) -> None:
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
    pygame.display.flip()


def draw_title_screen(screen: object) -> None:
    """Draw the title/start screen."""

    import pygame

    width, height = screen.get_size()
    _draw_desert_background(pygame, screen, width, height)
    _draw_title_logo(pygame, screen, width, height, scale=1.0, y_ratio=0.28)
    _draw_intro_characters(pygame, screen, width, height, scale=1.0, y_ratio=0.50)
    _draw_start_button(pygame, screen, width, height)
    pygame.display.flip()


def draw_scene(
    screen: object,
    cursor_position: ScreenPosition,
    ui: GameplayUi | None = None,
    active_hole_index: int = 4,
) -> None:
    """Draw the current gameplay frame."""

    import pygame

    width, height = screen.get_size()
    active_ui = ui or GameplayUi()
    _draw_green_field_background(pygame, screen, width, height)
    _draw_gameplay_hud(pygame, screen, width, height, active_ui)
    _draw_holes(pygame, screen, hole_positions(width, height), width, height, active_index=active_hole_index)
    _draw_cursor(pygame, screen, cursor_position)
    pygame.display.flip()


def draw_game_over_screen(screen: object, score: int) -> None:
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
    score_rect = pygame.Rect(width - round(width * 0.18), round(height * 0.025), round(width * 0.12), panel_h)
    pygame.draw.rect(screen, (255, 230, 88), score_rect, border_radius=8)
    pygame.draw.rect(screen, BUTTON_YELLOW_DARK, score_rect, width=3, border_radius=8)
    screen.blit(score_surface, score_surface.get_rect(center=score_rect.center))


def _draw_holes(
    pygame: object,
    screen: object,
    holes: Sequence[ScreenPosition],
    width: int,
    height: int,
    active_index: int | None = None,
) -> None:
    hole_w = round(width * 0.15)
    hole_h = round(height * 0.075)
    for index, (x, y) in enumerate(holes):
        if index == active_index:
            _draw_active_hole(pygame, screen, x, y, width, height, hole_w, hole_h)
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
) -> None:
    _draw_hole(pygame, screen, x, y, hole_w, hole_h)
    mole_w = round(width * 0.12)
    mole_h = round(height * 0.18)
    _draw_mole_shape(pygame, screen, (x, y - round(hole_h * 1.15)), mole_w, mole_h, "plain")
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
    pygame.draw.ellipse(screen, MOLE_BODY, body_rect)
    eye_y = y - round(body_h * 0.16)
    for eye_x in (x - round(body_w * 0.28), x + round(body_w * 0.28)):
        pygame.draw.circle(screen, MOLE_BLACK, (eye_x, eye_y), max(6, body_w // 13))
        pygame.draw.circle(screen, WHITE, (eye_x + max(1, body_w // 35), eye_y - max(1, body_w // 35)), max(2, body_w // 28))
    face_rect = pygame.Rect(x - round(body_w * 0.18), y + round(body_h * 0.02), round(body_w * 0.36), round(body_h * 0.26))
    pygame.draw.ellipse(screen, MOLE_FACE, face_rect)
    if variant == "open":
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
    pygame.draw.circle(screen, CURSOR_OUTLINE_COLOR, (x, y), 22)
    pygame.draw.circle(screen, CURSOR_COLOR, (x, y), 17)
    pygame.draw.line(screen, (24, 73, 92), (x - 26, y), (x + 26, y), 3)
    pygame.draw.line(screen, (24, 73, 92), (x, y - 26), (x, y + 26), 3)


def _font(pygame: object, width: int, ratio: float, bold: bool = False) -> object:
    return pygame.font.SysFont("arial", max(18, round(width * ratio)), bold=bold)


def _center_text(screen: object, font: object, text: str, color: tuple[int, int, int], center: ScreenPosition) -> None:
    surface = font.render(text, True, color)
    screen.blit(surface, surface.get_rect(center=center))
