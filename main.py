"""Помощь мастеру игры: изображение карты и настраиваемая сетка."""

from __future__ import annotations

import math
import os
import sys
from pathlib import Path

import pygame
from fantasy_ui import FantasyUI
from play import PlayMode

def enable_native_dpi() -> None:
    """Opt out of Windows bitmap scaling before creating the SDL window."""
    os.environ.setdefault("SDL_WINDOWS_DPI_AWARENESS", "permonitorv2")
    if sys.platform == "win32":
        import ctypes
        try:
            ctypes.windll.user32.SetProcessDpiAwarenessContext(ctypes.c_void_p(-4))
        except (AttributeError, OSError):
            try:
                ctypes.windll.shcore.SetProcessDpiAwareness(2)
            except (AttributeError, OSError):
                pass


class MapAssistant(PlayMode, FantasyUI):
    def __init__(self, size: tuple[int, int] = (1280, 820)) -> None:
        enable_native_dpi()
        pygame.init()
        pygame.display.set_caption("Арканум • Атлас мастера")
        self.screen = pygame.display.set_mode(size, pygame.RESIZABLE)
        self.image: pygame.Surface | None = None
        self._scaled_key: tuple | None = None
        self._scaled_map: pygame.Surface | None = None
        self.filename = ""
        self.grid_type = "square"
        self.cell_size = 64.0
        self.target_cell_size = 64.0
        self.grid_offset = pygame.Vector2()
        self.pan = pygame.Vector2()
        self.zoom = 1.0
        self.target_zoom = 1.0
        self.zoom_anchor: tuple[int, int] | None = None
        self.grid_locked = False
        self.section = "grid"
        self.grid_visible = True
        self.grid_dark = False
        self.opacity = 150
        self.drag: str | None = None
        self.drag_button: int | None = None
        self.running = True
        self.message = ""
        self.message_until = 0
        self.buttons: list[tuple[pygame.Rect, str]] = []
        self.init_play()
        self.layout()

    def notify(self, message: str) -> None:
        self.message = message
        self.message_until = pygame.time.get_ticks() + 6500

    def load_image(self, path: str) -> bool:
        # Keep the previous map when decoding the new file fails.
        try:
            image = pygame.image.load(path).convert_alpha()
        except (pygame.error, OSError, ValueError):
            self.notify("Не удалось открыть изображение. Попробуйте PNG или JPEG.")
            return False
        self.image = image
        self.players.clear()
        self.selected_player = None
        self.player_scroll = 0
        self.token_drag = None
        self._scaled_key = None
        self._scaled_map = None
        self.filename = Path(path).name
        self.grid_locked = False
        self.reset_grid()
        self.fit_image()
        self.notify("Карта загружена. Потяните ЛКМ, чтобы совместить сетку.")
        return True

    def reset_grid(self) -> None:
        if self.grid_locked:
            return
        self.grid_offset.update(0, 0)
        self.cell_size = self.target_cell_size = 64.0

    def fit_image(self) -> None:
        if self.image is not None:
            w, h = self.image.get_size()
            self.zoom = min((self.canvas.w - 40) / w, (self.canvas.h - 40) / h, 4.0)
            self.target_zoom = self.zoom
            self.zoom_anchor = None
            self.pan.update((self.canvas.w - w * self.zoom) / 2,
                            (self.canvas.h - h * self.zoom) / 2)

    def to_world(self, point: tuple[int, int]) -> pygame.Vector2:
        return (pygame.Vector2(point) - self.canvas.topleft - self.pan) / self.zoom

    def zoom_at(self, point: tuple[int, int], steps: float) -> None:
        self.zoom_anchor = point
        self.target_zoom = max(0.005, min(8.0, self.target_zoom * math.exp(0.10 * max(-20, min(20, steps)))))

    def resize_cells(self, steps: float, fine: bool = False) -> None:
        if not self.grid_locked and self.mode == "edit":
            rate = 0.0002 if fine else 0.01
            self.target_cell_size = max(8.0, min(1024.0, self.target_cell_size * math.exp(rate * max(-20, min(20, steps)))))

    def update(self, dt: float) -> None:
        """Frame-rate independent easing; geometry stays in fractional map pixels."""
        blend = -math.expm1(-20 * max(0, dt))
        if not self.grid_locked and self.mode == "edit":
            self.cell_size += (self.target_cell_size - self.cell_size) * blend
            if abs(self.target_cell_size - self.cell_size) < 1e-8:
                self.cell_size = self.target_cell_size
        if self.zoom_anchor is not None:
            world = self.to_world(self.zoom_anchor)
            self.zoom += (self.target_zoom - self.zoom) * blend
            if abs(self.target_zoom - self.zoom) < 1e-10:
                self.zoom = self.target_zoom
            self.pan = pygame.Vector2(self.zoom_anchor) - self.canvas.topleft - world * self.zoom

    def action(self, action: str) -> None:
        if self.play_action(action):
            return
        if self.mode == "play" and action in ("square", "hex", "minus", "plus", "reset", "lock"):
            return
        if action.startswith("section_"):
            self.section = action.removeprefix("section_")
            self.layout()
            return
        if action == "lock":
            self.grid_locked = not self.grid_locked
            self.target_cell_size = self.cell_size
            self.drag = self.drag_button = None
            return
        if self.grid_locked and action in ("square", "hex", "minus", "plus", "reset"):
            return
        if action in ("square", "hex"):
            self.grid_type = action
        elif action in ("minus", "plus"):
            self.resize_cells(-1 if action == "minus" else 1)
        elif action == "visibility":
            self.grid_visible = not self.grid_visible
        elif action == "color":
            self.grid_dark = not self.grid_dark
        elif action.startswith("opacity_"):
            delta = -20 if action.endswith("minus") else 20
            self.opacity = max(25, min(255, self.opacity + delta))
        elif action == "fit":
            self.fit_image()
        elif action == "actual":
            self.target_zoom = 1.0
            self.zoom_anchor = self.canvas.center
        elif action == "reset":
            self.reset_grid()

    def handle_event(self, event: pygame.event.Event) -> None:
        if self.handle_play_event(event):
            return
        if event.type == pygame.QUIT:
            self.running = False
        elif event.type == pygame.VIDEORESIZE:
            size = (max(900, event.w), max(680, event.h))
            self.screen = pygame.display.set_mode(size, pygame.RESIZABLE)
            self.layout()
        elif event.type in (pygame.WINDOWSIZECHANGED, pygame.WINDOWDISPLAYCHANGED):
            self.screen = pygame.display.get_surface()
            self.layout()
        elif event.type == pygame.DROPFILE:
            self.drag = None
            self.load_image(event.file)
        elif event.type == pygame.WINDOWFOCUSLOST:
            self.drag = None
            self.drag_button = None
        elif event.type == pygame.KEYDOWN:
            if event.key == pygame.K_ESCAPE:
                self.running = False
            else:
                actions = {pygame.K_1: "square", pygame.K_2: "hex", pygame.K_g: "visibility", pygame.K_l: "lock",
                           pygame.K_f: "fit", pygame.K_r: "reset"}
                if event.key in actions:
                    self.action(actions[event.key])
        elif event.type == pygame.MOUSEBUTTONDOWN:
            if event.button == 1:
                for rect, action in self.buttons:
                    if rect.collidepoint(event.pos):
                        self.action(action)
                        return
                if self.mode == "edit" and self.section == "grid" and self.size_control.collidepoint(event.pos) and not self.grid_locked:
                    self.drag, self.drag_button = "size", 1
                    return
            if self.image is not None and self.canvas.collidepoint(event.pos):
                if event.button in (1, 2, 3):
                    if event.button == 1 and self.grid_locked:
                        return
                    self.zoom_anchor = None
                    self.target_zoom = self.zoom
                    self.drag = "grid" if event.button == 1 else "map"
                    self.drag_button = event.button
        elif event.type == pygame.MOUSEBUTTONUP and event.button == self.drag_button:
            self.drag = None
            self.drag_button = None
        elif event.type == pygame.MOUSEMOTION and self.drag:
            if self.drag == "size" and not self.grid_locked:
                fine = bool(pygame.key.get_mods() & pygame.KMOD_SHIFT)
                delta = event.rel[0] * (0.01 if fine else 0.1) / self.ui_scale
                self.target_cell_size = max(8.0, min(1024.0, self.target_cell_size + delta))
            elif self.drag == "grid" and not self.grid_locked:
                self.grid_offset += pygame.Vector2(event.rel) / self.zoom
            elif self.drag == "map":
                self.pan += event.rel
        elif event.type == pygame.MOUSEWHEEL and self.image is not None:
            point = pygame.mouse.get_pos()
            if self.canvas.collidepoint(point):
                if pygame.key.get_mods() & pygame.KMOD_CTRL:
                    self.zoom_at(point, getattr(event, "precise_y", event.y))
                else:
                    self.resize_cells(getattr(event, "precise_y", event.y), bool(pygame.key.get_mods() & pygame.KMOD_SHIFT))

    def draw_map(self) -> None:
        if self.image is None:
            return
        origin = pygame.Vector2(self.canvas.topleft) + self.pan
        w, h = self.image.get_size()
        map_rect = pygame.Rect(round(origin.x), round(origin.y), round(w * self.zoom), round(h * self.zoom))
        visible = map_rect.clip(self.canvas)
        if visible.w <= 0 or visible.h <= 0:
            return
        # Scale only the visible region, avoiding huge surfaces for zoomed-in maps.
        left = max(0, math.floor((visible.left - origin.x) / self.zoom))
        top = max(0, math.floor((visible.top - origin.y) / self.zoom))
        right = min(w, math.ceil((visible.right - origin.x) / self.zoom) + 1)
        bottom = min(h, math.ceil((visible.bottom - origin.y) / self.zoom) + 1)
        if right <= left or bottom <= top:
            return
        source = self.image.subsurface((left, top, right - left, bottom - top))
        target = (max(1, round(source.get_width() * self.zoom)),
                  max(1, round(source.get_height() * self.zoom)))
        key = (left, top, right, bottom, target)
        if key != self._scaled_key:
            self._scaled_map = pygame.transform.smoothscale(source, target)
            self._scaled_key = key
        self.screen.set_clip(visible)
        self.screen.blit(self._scaled_map,
                         (round(origin.x + left * self.zoom), round(origin.y + top * self.zoom)))
        if self.grid_visible and self.cell_size * self.zoom >= 8:
            color = ((18, 23, 31) if self.grid_dark else (245, 239, 218)) + (self.opacity,)
            offset = origin + self.grid_offset * self.zoom - visible.topleft
            size = self.cell_size * self.zoom
            key = (visible.size, tuple(offset), size, self.grid_type, color)
            if key != getattr(self, "_grid_key", None):
                layer = pygame.Surface(visible.size, pygame.SRCALPHA)
                if self.grid_type == "square":
                    for x in range(math.floor(-offset.x / size), math.ceil((visible.w - offset.x) / size) + 1):
                        px = offset.x + x * size
                        pygame.draw.aaline(layer, color, (px, 0), (px, visible.h))
                    for y in range(math.floor(-offset.y / size), math.ceil((visible.h - offset.y) / size) + 1):
                        py = offset.y + y * size
                        pygame.draw.aaline(layer, color, (0, py), (visible.w, py))
                else:
                    radius = size / 2
                    height = math.sqrt(3) * radius
                    step = 1.5 * radius
                    start = math.floor((-offset.x - radius) / step)
                    end = math.ceil((visible.w - offset.x + radius) / step)
                    for col in range(start, end + 1):
                        cx = offset.x + col * step
                        shift = offset.y + (col % 2) * height / 2
                        first = math.floor((-shift - height / 2) / height)
                        last = math.ceil((visible.h - shift + height / 2) / height)
                        for row in range(first, last + 1):
                            cy = shift + row * height
                            points = [(cx + radius * math.cos(i * math.pi / 3),
                                       cy + radius * math.sin(i * math.pi / 3)) for i in range(6)]
                            pygame.draw.aalines(layer, color, True, points)
                self._grid_layer = layer
                self._grid_key = key
            self.screen.blit(self._grid_layer, visible.topleft)
        self.screen.set_clip(None)

    def run(self) -> None:
        clock = pygame.time.Clock()
        while self.running:
            dt = clock.tick(120) / 1000
            for event in pygame.event.get():
                self.handle_event(event)
            self.update(dt)
            self.draw()
        pygame.quit()


def main() -> None:
    app = MapAssistant()
    if len(sys.argv) > 1:
        app.load_image(sys.argv[1])
    app.run()


if __name__ == "__main__":
    main()
