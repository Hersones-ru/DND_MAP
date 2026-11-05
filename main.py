"""Помощь мастеру игры: изображение карты и настраиваемая сетка."""

from __future__ import annotations

import math
import sys
from pathlib import Path

import pygame

BG = (17, 21, 29)
PANEL = (25, 30, 40)
CARD = (35, 42, 54)
TEXT = (231, 234, 240)
MUTED = (148, 159, 177)
ACCENT = (225, 181, 103)


class MapAssistant:
    def __init__(self, size: tuple[int, int] = (1280, 820)) -> None:
        pygame.init()
        pygame.display.set_caption("Помощь мастеру игры • Карты D&D")
        self.screen = pygame.display.set_mode(size, pygame.RESIZABLE)
        self.fonts = {
            "small": pygame.font.SysFont("dejavusans,arial", 14),
            "body": pygame.font.SysFont("dejavusans,arial", 16),
            "title": pygame.font.SysFont("dejavusans,arial", 25, bold=True),
        }
        self.image: pygame.Surface | None = None
        self._scaled_key: tuple | None = None
        self._scaled_map: pygame.Surface | None = None
        self.filename = ""
        self.grid_type = "square"
        self.cell_size = 64.0
        self.grid_offset = pygame.Vector2()
        self.pan = pygame.Vector2()
        self.zoom = 1.0
        self.grid_visible = True
        self.grid_dark = False
        self.opacity = 150
        self.drag: str | None = None
        self.drag_button: int | None = None
        self.running = True
        self.message = ""
        self.message_until = 0
        self.buttons: list[tuple[pygame.Rect, str]] = []
        self.layout()

    def layout(self) -> None:
        width, height = self.screen.get_size()
        self.canvas = pygame.Rect(20, 94, width - 310, height - 146)
        self.sidebar = pygame.Rect(width - 270, 94, 250, height - 146)
        self.buttons = []
        x = self.sidebar.x + 16
        for action, y, dx, w in [
            ("square", 147, 0, 104), ("hex", 147, 114, 104),
            ("minus", 244, 0, 48), ("plus", 244, 170, 48),
            ("visibility", 310, 0, 218), ("color", 356, 0, 218),
            ("opacity_minus", 435, 0, 104), ("opacity_plus", 435, 114, 104),
            ("fit", 511, 0, 218), ("reset", 557, 0, 218),
        ]:
            self.buttons.append((pygame.Rect(x + dx, y, w, 36), action))

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
        self._scaled_key = None
        self._scaled_map = None
        self.filename = Path(path).name
        self.reset_grid()
        self.fit_image()
        self.notify("Карта загружена. Потяните ЛКМ, чтобы совместить сетку.")
        return True

    def reset_grid(self) -> None:
        self.grid_offset.update(0, 0)
        self.cell_size = 64.0

    def fit_image(self) -> None:
        if self.image is not None:
            w, h = self.image.get_size()
            self.zoom = min((self.canvas.w - 40) / w, (self.canvas.h - 40) / h, 4.0)
            self.pan.update((self.canvas.w - w * self.zoom) / 2,
                            (self.canvas.h - h * self.zoom) / 2)

    def to_world(self, point: tuple[int, int]) -> pygame.Vector2:
        return (pygame.Vector2(point) - self.canvas.topleft - self.pan) / self.zoom

    def zoom_at(self, point: tuple[int, int], steps: float) -> None:
        world = self.to_world(point)
        self.zoom = max(0.005, min(8.0, self.zoom * 1.12 ** max(-20, min(20, steps))))
        self.pan = pygame.Vector2(point) - self.canvas.topleft - world * self.zoom

    def resize_cells(self, steps: float) -> None:
        self.cell_size = max(8.0, min(1024.0, self.cell_size * 1.08 ** max(-20, min(20, steps))))

    def action(self, action: str) -> None:
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
        elif action == "reset":
            self.reset_grid()

    def handle_event(self, event: pygame.event.Event) -> None:
        if event.type == pygame.QUIT:
            self.running = False
        elif event.type == pygame.VIDEORESIZE:
            size = (max(900, event.w), max(680, event.h))
            self.screen = pygame.display.set_mode(size, pygame.RESIZABLE)
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
                actions = {pygame.K_1: "square", pygame.K_2: "hex", pygame.K_g: "visibility",
                           pygame.K_f: "fit", pygame.K_r: "reset"}
                if event.key in actions:
                    self.action(actions[event.key])
        elif event.type == pygame.MOUSEBUTTONDOWN:
            if event.button == 1:
                for rect, action in self.buttons:
                    if rect.collidepoint(event.pos):
                        self.action(action)
                        return
            if self.image is not None and self.canvas.collidepoint(event.pos):
                if event.button in (1, 2, 3):
                    self.drag = "grid" if event.button == 1 else "map"
                    self.drag_button = event.button
        elif event.type == pygame.MOUSEBUTTONUP and event.button == self.drag_button:
            self.drag = None
            self.drag_button = None
        elif event.type == pygame.MOUSEMOTION and self.drag:
            if self.drag == "grid":
                self.grid_offset += pygame.Vector2(event.rel) / self.zoom
            else:
                self.pan += event.rel
        elif event.type == pygame.MOUSEWHEEL and self.image is not None:
            point = pygame.mouse.get_pos()
            if self.canvas.collidepoint(point):
                if pygame.key.get_mods() & pygame.KMOD_CTRL:
                    self.zoom_at(point, event.y)
                else:
                    self.resize_cells(event.y)

    def label(self, text: str, pos: tuple[int, int], color: tuple = TEXT,
              font: str = "body", max_width: int | None = None) -> None:
        face = self.fonts[font]
        if max_width is not None and face.size(text)[0] > max_width:
            while text and face.size(text + "…")[0] > max_width:
                text = text[:-1]
            text += "…"
        self.screen.blit(face.render(text, True, color), pos)

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
            layer = pygame.Surface(visible.size, pygame.SRCALPHA)
            color = ((18, 23, 31) if self.grid_dark else (245, 239, 218)) + (self.opacity,)
            offset = origin + self.grid_offset * self.zoom - visible.topleft
            size = self.cell_size * self.zoom
            if self.grid_type == "square":
                for x in range(math.floor(-offset.x / size), math.ceil((visible.w - offset.x) / size) + 1):
                    px = round(offset.x + x * size)
                    pygame.draw.line(layer, color, (px, 0), (px, visible.h))
                for y in range(math.floor(-offset.y / size), math.ceil((visible.h - offset.y) / size) + 1):
                    py = round(offset.y + y * size)
                    pygame.draw.line(layer, color, (0, py), (visible.w, py))
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
                        points = [(round(cx + radius * math.cos(i * math.pi / 3)),
                                   round(cy + radius * math.sin(i * math.pi / 3))) for i in range(6)]
                        pygame.draw.polygon(layer, color, points, 1)
            self.screen.blit(layer, visible.topleft)
        self.screen.set_clip(None)

    def draw(self) -> None:
        self.screen.fill(BG)
        self.label("ПОМОЩЬ МАСТЕРУ ИГРЫ", (22, 16), ACCENT, "small")
        self.label("Мастерская карт", (20, 39), font="title")
        self.label(self.filename or "Новая история начинается с карты", (315, 49), MUTED,
                   max_width=max(100, self.screen.get_width() - 340))
        pygame.draw.rect(self.screen, (12, 16, 23), self.canvas, border_radius=10)
        if self.image is not None:
            self.draw_map()
        else:
            cx, cy = self.canvas.center
            pygame.draw.rect(self.screen, CARD, (cx - 40, cy - 110, 80, 66), border_radius=12)
            pygame.draw.lines(self.screen, ACCENT, False,
                              [(cx - 24, cy - 60), (cx - 7, cy - 83), (cx + 5, cy - 70), (cx + 23, cy - 91)], 3)
            for text, dy, color, font in [("Перетащите сюда карту", -14, TEXT, "title"),
                                         ("Изображение из проводника → в это окно", 30, MUTED, "body"),
                                         ("PNG · JPEG · BMP", 61, ACCENT, "small")]:
                tw = self.fonts[font].size(text)[0]
                self.label(text, (cx - tw // 2, cy + dy), color, font)
        pygame.draw.rect(self.screen, PANEL, self.sidebar, border_radius=10)
        x = self.sidebar.x + 16
        self.label("СЕТКА КАРТЫ", (x, 113), ACCENT, "small")
        self.label("Размер ячейки", (x, 207), MUTED, "small")
        self.label(f"{self.cell_size:.0f} px", (x + 68, 252))
        self.label("Непрозрачность", (x, 402), MUTED, "small")
        self.label(f"{round(self.opacity / 255 * 100)}%", (x + 165, 402), ACCENT, "small")
        labels = {"square": "Квадраты", "hex": "Гексы", "minus": "−", "plus": "+",
                  "visibility": "Сетка: видна" if self.grid_visible else "Сетка: скрыта",
                  "color": "Линии: тёмные" if self.grid_dark else "Линии: светлые",
                  "opacity_minus": "−", "opacity_plus": "+", "fit": "Вписать карту  ·  F",
                  "reset": "Сбросить сетку  ·  R"}
        mouse = pygame.mouse.get_pos()
        for rect, action in self.buttons:
            selected = action == self.grid_type
            fill = (71, 61, 44) if selected else (46, 54, 68) if rect.collidepoint(mouse) else CARD
            pygame.draw.rect(self.screen, fill, rect, border_radius=7)
            if selected:
                pygame.draw.rect(self.screen, ACCENT, rect, 1, border_radius=7)
            text = labels[action]
            tw, th = self.fonts["body"].size(text)
            self.label(text, (rect.centerx - tw // 2, rect.centery - th // 2), ACCENT if selected else TEXT)
        bottom = self.screen.get_height() - 35
        self.label("ЛКМ: сетка  ·  ПКМ: карта", (self.canvas.x, bottom), MUTED, "small")
        self.label("Колесо: ячейки  ·  Ctrl + колесо: зум", (self.canvas.x + 270, bottom), MUTED, "small")
        if self.image is not None:
            self.label(f"Вид: {self.zoom * 100:.0f}%", (x, bottom), ACCENT, "small")
            if self.grid_visible and self.cell_size * self.zoom < 8:
                self.label("Приблизьте вид для сетки", (self.canvas.x + 12, self.canvas.y + 12), ACCENT, "small")
        if self.message and pygame.time.get_ticks() < self.message_until:
            rect = pygame.Rect(self.canvas.x + 10, self.canvas.bottom - 46, self.canvas.w - 20, 36)
            pygame.draw.rect(self.screen, CARD, rect, border_radius=7)
            self.label(self.message, (rect.x + 12, rect.y + 9), TEXT, "small", rect.w - 24)
        pygame.display.flip()

    def run(self) -> None:
        clock = pygame.time.Clock()
        while self.running:
            for event in pygame.event.get():
                self.handle_event(event)
            self.draw()
            clock.tick(60)
        pygame.quit()


def main() -> None:
    app = MapAssistant()
    if len(sys.argv) > 1:
        app.load_image(sys.argv[1])
    app.run()


if __name__ == "__main__":
    main()
