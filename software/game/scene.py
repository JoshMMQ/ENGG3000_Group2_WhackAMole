"""Pygame scene drawing for the Whack-a-Mole prototype."""

from __future__ import annotations

from typing import Sequence

from .coordinates import ScreenPosition


SKY_COLOR = (183, 226, 243)
FIELD_COLOR = (184, 216, 91)
FIELD_SHADOW_COLOR = (154, 190, 75)
HILL_COLOR = (142, 204, 199)
CLOUD_COLOR = (255, 255, 255)
FENCE_COLOR = (145, 111, 64)
FENCE_HIGHLIGHT = (166, 130, 78)
HOLE_COLOR = (67, 46, 24)
HOLE_RIM_COLOR = (99, 73, 36)
HUD_PANEL_COLOR = (236, 243, 249)
HUD_BORDER_COLOR = (183, 200, 214)
HUD_ACCENT_COLOR = (255, 139, 40)
HUD_TEXT_COLOR = (77, 87, 96)
CURSOR_COLOR = (64, 199, 255)
CURSOR_OUTLINE_COLOR = (248, 253, 255)
MOLE_COLOR = (166, 111, 55)
MOLE_DARK = (86, 54, 27)
MOLE_LIGHT = (248, 218, 145)


def hole_positions(width: int, height: int) -> tuple[ScreenPosition, ...]:
    """Return the 3 x 3 mole-hole centres for a window size."""

    x_values = (round(width * 0.18), round(width * 0.50), round(width * 0.82))
    y_values = (round(height * 0.48), round(height * 0.64), round(height * 0.80))
    return tuple((x, y) for y in y_values for x in x_values)


def draw_scene(screen: object, cursor_position: ScreenPosition) -> None:
    """Draw the current themed game frame."""

    import pygame

    width, height = screen.get_size()
    screen.fill(SKY_COLOR)
    _draw_clouds(pygame, screen, width, height)
    _draw_hills(pygame, screen, width, height)
    _draw_fence(pygame, screen, width, height)
    _draw_field(pygame, screen, width, height)
    _draw_holes(pygame, screen, hole_positions(width, height), width, height)
    _draw_mole(pygame, screen, (width // 2, round(height * 0.62)), width, height)
    _draw_hud(pygame, screen, width)
    _draw_cursor(pygame, screen, cursor_position)
    pygame.display.flip()


def _draw_clouds(pygame: object, screen: object, width: int, height: int) -> None:
    cloud_groups = (
        ((round(width * 0.12), round(height * 0.19)), 75),
        ((round(width * 0.42), round(height * 0.31)), 55),
        ((round(width * 0.78), round(height * 0.23)), 68),
    )
    for (x, y), radius in cloud_groups:
        for offset_x, offset_y, scale in ((0, 20, 1.1), (55, 0, 0.9), (110, 26, 0.75)):
            pygame.draw.ellipse(
                screen,
                CLOUD_COLOR,
                (
                    x + offset_x - radius,
                    y + offset_y - round(radius * 0.55),
                    round(radius * 2 * scale),
                    round(radius * 1.15),
                ),
            )


def _draw_hills(pygame: object, screen: object, width: int, height: int) -> None:
    pygame.draw.ellipse(screen, HILL_COLOR, (-80, round(height * 0.23), round(width * 0.55), round(height * 0.42)))
    pygame.draw.ellipse(
        screen,
        HILL_COLOR,
        (round(width * 0.66), round(height * 0.23), round(width * 0.42), round(height * 0.34)),
    )


def _draw_fence(pygame: object, screen: object, width: int, height: int) -> None:
    rail_height = max(22, round(height * 0.035))
    for y, color in ((round(height * 0.27), FENCE_HIGHLIGHT), (round(height * 0.37), FENCE_COLOR)):
        pygame.draw.rect(screen, color, (-20, y, width + 40, rail_height), border_radius=10)
    post_width = max(28, round(width * 0.035))
    for x in (round(width * 0.20), round(width * 0.76)):
        pygame.draw.rect(
            screen,
            FENCE_COLOR,
            (x - post_width // 2, round(height * 0.20), post_width, round(height * 0.23)),
            border_radius=8,
        )


def _draw_field(pygame: object, screen: object, width: int, height: int) -> None:
    pygame.draw.ellipse(screen, FIELD_COLOR, (-120, round(height * 0.38), width + 240, round(height * 0.72)))
    pygame.draw.ellipse(
        screen,
        FIELD_SHADOW_COLOR,
        (-80, round(height * 0.86), round(width * 0.75), round(height * 0.18)),
    )
    pygame.draw.ellipse(
        screen,
        (198, 226, 106),
        (round(width * 0.25), round(height * 0.48), round(width * 0.84), round(height * 0.28)),
    )


def _draw_holes(pygame: object, screen: object, holes: Sequence[ScreenPosition], width: int, height: int) -> None:
    hole_width = round(width * 0.18)
    hole_height = round(height * 0.055)
    for x, y in holes:
        pygame.draw.ellipse(
            screen,
            HOLE_RIM_COLOR,
            (x - hole_width // 2, y - hole_height // 2 - 5, hole_width, hole_height + 10),
        )
        pygame.draw.ellipse(screen, HOLE_COLOR, (x - hole_width // 2, y - hole_height // 2, hole_width, hole_height))


def _draw_mole(pygame: object, screen: object, centre: ScreenPosition, width: int, height: int) -> None:
    x, y = centre
    body_w = round(width * 0.115)
    body_h = round(height * 0.12)
    head_r = round(width * 0.05)
    pygame.draw.ellipse(screen, MOLE_COLOR, (x - body_w // 2, y - body_h // 2, body_w, body_h))
    pygame.draw.circle(screen, MOLE_COLOR, (x, y - round(height * 0.065)), head_r)
    pygame.draw.circle(screen, MOLE_COLOR, (x - head_r, y - round(height * 0.08)), round(head_r * 0.35))
    pygame.draw.circle(screen, MOLE_COLOR, (x + head_r, y - round(height * 0.08)), round(head_r * 0.35))
    pygame.draw.circle(screen, (255, 255, 255), (x - round(head_r * 0.35), y - round(height * 0.073)), 7)
    pygame.draw.circle(screen, (255, 255, 255), (x + round(head_r * 0.35), y - round(height * 0.073)), 7)
    pygame.draw.circle(screen, MOLE_DARK, (x - round(head_r * 0.35), y - round(height * 0.073)), 3)
    pygame.draw.circle(screen, MOLE_DARK, (x + round(head_r * 0.35), y - round(height * 0.073)), 3)
    pygame.draw.ellipse(screen, MOLE_DARK, (x - 13, y - round(height * 0.055), 26, 18))
    pygame.draw.rect(screen, MOLE_LIGHT, (x - 13, y - round(height * 0.027), 10, 14), border_radius=4)
    pygame.draw.rect(screen, MOLE_LIGHT, (x + 3, y - round(height * 0.027), 10, 14), border_radius=4)


def _draw_hud(pygame: object, screen: object, width: int) -> None:
    font = pygame.font.SysFont("arial", 28, bold=True)
    _draw_hud_panel(pygame, screen, font, (18, 18, 320, 54), "Time Remaining:", "27")
    _draw_hud_panel(pygame, screen, font, (width - 290, 18, 250, 54), "High Score:", "0")
    _draw_hud_panel(pygame, screen, font, (width - 235, 82, 195, 54), "Score:", "4")


def _draw_hud_panel(
    pygame: object,
    screen: object,
    font: object,
    rect: tuple[int, int, int, int],
    label: str,
    value: str,
) -> None:
    panel = pygame.Rect(rect)
    pygame.draw.rect(screen, HUD_PANEL_COLOR, panel, border_radius=8)
    pygame.draw.rect(screen, HUD_BORDER_COLOR, panel, width=2, border_radius=8)
    label_surface = font.render(label, True, HUD_TEXT_COLOR)
    screen.blit(label_surface, (panel.x + 16, panel.y + 12))
    value_box = pygame.Rect(panel.right - 92, panel.y + 11, 76, 32)
    pygame.draw.rect(screen, HUD_ACCENT_COLOR, value_box, border_radius=8)
    value_surface = font.render(value, True, (255, 255, 255))
    value_rect = value_surface.get_rect(center=value_box.center)
    screen.blit(value_surface, value_rect)


def _draw_cursor(pygame: object, screen: object, cursor_position: ScreenPosition) -> None:
    x, y = cursor_position
    pygame.draw.circle(screen, CURSOR_OUTLINE_COLOR, (x, y), 22)
    pygame.draw.circle(screen, CURSOR_COLOR, (x, y), 17)
    pygame.draw.line(screen, (24, 73, 92), (x - 26, y), (x + 26, y), 3)
    pygame.draw.line(screen, (24, 73, 92), (x, y - 26), (x, y + 26), 3)
