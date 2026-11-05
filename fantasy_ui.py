"""Native-resolution, asset-free fantasy interface for the map workshop."""

import math
import random

import pygame

INK = (15, 15, 29)
PANEL = (25, 24, 43)
GOLD = (215, 180, 113)
PALE = (237, 226, 202)
MUTED = (151, 143, 169)
VIOLET = (151, 130, 202)
EDGE = (77, 63, 91)


class FantasyUI:
    def px(self, value):
        return round(value * self.ui_scale)

    def box(self, x, y, w, h):
        return pygame.Rect(self.px(x), self.px(y), self.px(w), self.px(h))

    def layout(self):
        w, h = self.screen.get_size()
        # Layout scales, but text and shapes are rasterized at actual window pixels.
        # There is deliberately no low-resolution framebuffer or pygame.SCALED.
        self.ui_scale = max(0.85, min(2.8, min(w / 1280, h / 820)))
        self.uw, self.uh = w / self.ui_scale, h / self.ui_scale
        self.fonts = {
            name: pygame.font.SysFont(family, self.px(size), bold=bold)
            for name, family, size, bold in (
                ("small", "dejavusans,segoeui,arial", 13, False),
                ("body", "dejavusans,segoeui,arial", 15, False),
                ("title", "dejavuserif,georgia", 32, True),
                ("heading", "dejavuserif,georgia", 21, False),
                ("value", "dejavusans,segoeui,arial", 22, False),
            )
        }
        self._text_cache = {}
        self.canvas = self.box(24, 146, self.uw - 372, self.uh - 218)
        self.sx = self.uw - 326
        self.sidebar = self.box(self.sx, 146, 302, self.uh - 218)
        self.size_control = self.box(self.sx + 76, 328, 150, 47)
        self.buttons = []
        for i, section in enumerate(("grid", "map", "guide")):
            self.buttons.append((self.box(self.sx + 15 + i * 91, 164, 88, 34), "section_" + section))
        x = self.sx + 20
        rows = {
            "grid": [("square", 248, 0, 126), ("hex", 248, 136, 126),
                     ("minus", 328, 0, 48), ("plus", 328, 214, 48),
                     ("lock", 420, 0, 262), ("visibility", 472, 0, 262),
                     ("color", 516, 0, 262), ("opacity_minus", 600, 0, 126),
                     ("opacity_plus", 600, 136, 126), ("reset", 665, 0, 262)],
            "map": [("fit", 320, 0, 262), ("actual", 370, 0, 262)],
            "guide": [],
        }
        for action, y, dx, width in rows[self.section]:
            self.buttons.append((self.box(x + dx, y, width, 38), action))
        if self.mode == "play":
            self.buttons = []
            self.name_field = self.box(x, 334, 262, 44)
            self.input_rects = {"name": self.name_field, "hp": self.box(x, 414, 126, 42),
                                "max_hp": self.box(x+136, 414, 126, 42)}
            self.buttons.extend([(self.box(x, 260, 126, 34), "kind_player"),
                                 (self.box(x+136, 260, 126, 34), "kind_enemy"),
                                 (self.box(x, 476, 262, 38), "add_player")])
            for i in range(self.player_scroll, min(len(self.players), self.player_scroll+self.roster_capacity())):
                self.buttons.append((self.box(x, 594+(i-self.player_scroll)*48, 262, 40), f"player_{i}"))
        self.buttons.append((self.box(self.sx+15, 108, 272, 30), "toggle_mode"))
        self._background = self.make_background((w, h))

    def make_background(self, size):
        surface = pygame.Surface(size)
        w, h = size
        for y in range(h):
            t = y / max(1, h - 1)
            pygame.draw.line(surface, (int(25 - 13*t), int(22 - 8*t), int(43 - 18*t)), (0, y), (w, y))
        rng = random.Random(17)
        for _ in range(100):
            x, y = rng.randrange(w), rng.randrange(h)
            pygame.draw.circle(surface, rng.choice(((66, 52, 77), (93, 73, 93), (107, 86, 106))),
                               (x, y), max(1, self.px(0.6)))
        return surface

    def label(self, text, pos, color=PALE, font="body", max_width=None):
        """Positions and optional width are logical; glyphs use native pixel sizes."""
        face = self.fonts[font]
        if max_width is not None:
            limit = self.px(max_width)
            if face.size(text)[0] > limit:
                while text and face.size(text + "…")[0] > limit:
                    text = text[:-1]
                text += "…"
        self.screen.blit(self.render_text(text, color, font), (self.px(pos[0]), self.px(pos[1])))

    def render_text(self, text, color, font="body"):
        key = (text, color, font)
        if key not in self._text_cache:
            if len(self._text_cache) > 512:
                self._text_cache.clear()
            self._text_cache[key] = self.fonts[font].render(text, True, color)
        return self._text_cache[key]

    def centered(self, text, x, y, color=PALE, font="body"):
        width = self.fonts[font].size(text)[0] / self.ui_scale
        self.label(text, (x - width / 2, y), color, font)

    def line(self, a, b, color=EDGE):
        pygame.draw.aaline(self.screen, color, (self.px(a[0]), self.px(a[1])),
                           (self.px(b[0]), self.px(b[1])))

    def seal(self, center, radius):
        cx, cy = center
        for factor in (1, 0.89, 0.65):
            pygame.draw.circle(self.screen, EDGE, (self.px(cx), self.px(cy)),
                               self.px(radius * factor), max(1, self.px(1)))
        points = [(cx + radius * 0.82 * math.cos(-math.pi/2 + i * math.tau/5),
                   cy + radius * 0.82 * math.sin(-math.pi/2 + i * math.tau/5)) for i in range(5)]
        for i in range(5):
            self.line(points[i], points[(i + 2) % 5], (100, 81, 122))
        for i in range(12):
            angle = i * math.tau / 12
            a = (cx + radius * 0.92 * math.cos(angle), cy + radius * 0.92 * math.sin(angle))
            b = (cx + radius * 0.99 * math.cos(angle), cy + radius * 0.99 * math.sin(angle))
            self.line(a, b, GOLD if i % 3 == 0 else EDGE)

    def frame(self, rect):
        pygame.draw.rect(self.screen, EDGE, rect, max(1, self.px(1)), border_radius=self.px(5))
        n = self.px(15)
        for x, y, dx, dy in [(rect.left, rect.top, 1, 1), (rect.right-1, rect.top, -1, 1),
                             (rect.left, rect.bottom-1, 1, -1), (rect.right-1, rect.bottom-1, -1, -1)]:
            pygame.draw.lines(self.screen, GOLD, False, [(x, y + n*dy), (x, y), (x+n*dx, y)], max(1, self.px(1)))

    def draw(self):
        self.screen.blit(self._background, (0, 0))
        self.seal((54, 58), 29)
        self.label("А Р К А Н У М", (101, 22), GOLD, "small")
        self.label("Атлас мастера", (98, 43), PALE, "title")
        self.label("Каждая карта — дверь в неизведанное", (100, 91), MUTED, "small")
        self.line((24, 128), (self.uw - 24, 128))
        self.label("I   /   АТЛАС МИРОВ", (self.uw - 300, 39), GOLD, "small")
        self.label(self.filename or "Ненаписанная история", (self.uw - 300, 68), MUTED, max_width=270)
        pygame.draw.rect(self.screen, (12, 14, 23), self.canvas)
        if self.image is not None:
            self.draw_map()
            self.draw_tokens()
        else:
            cx = self.canvas.centerx / self.ui_scale
            cy = self.canvas.centery / self.ui_scale
            self.seal((cx, cy - 84), 73)
            self.centered("Откройте новый мир", cx, cy + 17, PALE, "heading")
            self.centered("Перетащите изображение карты в этот атлас", cx, cy + 59, MUTED)
            self.centered("PNG   ·   JPEG   ·   BMP", cx, cy + 92, GOLD, "small")
        self.frame(self.canvas)
        pygame.draw.rect(self.screen, PANEL, self.sidebar, border_radius=self.px(5))
        self.frame(self.sidebar)
        x = self.sx + 20
        if self.mode == "play":
            self.draw_play_panel()
        elif self.section == "grid":
            self.label("Печати пространства", (x, 214), GOLD, "heading")
            self.label("РАЗМЕР ЯЧЕЙКИ", (x, 301), MUTED, "small")
            pygame.draw.rect(self.screen, (18, 18, 32), self.size_control, border_radius=self.px(5))
            self.centered(f"{self.cell_size:.2f}", self.sx + 151, 332, PALE, "value")
            self.centered("px карты · тяните число ↔", self.sx + 151, 382, MUTED, "small")
            self.label("ПЛОТНОСТЬ ЛИНИЙ", (x, 572), MUTED, "small")
            self.label(f"{round(self.opacity/255*100)}%", (x + 220, 572), GOLD, "small")
        elif self.section == "map":
            self.label("Зеркало миров", (x, 216), GOLD, "heading")
            self.label("Масштаб вида", (x, 262), MUTED)
            self.label(f"{self.zoom * 100:.1f}%", (x + 168, 260), PALE)
            self.label("Путеводная нить", (x, 444), GOLD, "heading")
            for i, text in enumerate(("ПКМ — перемещение мира", "Ctrl + колесо — приближение", "Масштаб не меняет привязку", "сетки к вашей карте.", "", "Новый мир: перетащите", "другое изображение в окно.")):
                self.label(text, (x, 487 + i*26), MUTED, "small")
            if self.image is not None:
                self.label(f"Источник: {self.image.get_width()} × {self.image.get_height()}", (x, 285), MUTED, "small")
        else:
            self.label("Гримуар мастера", (x, 216), GOLD, "heading")
            lines = [("ПЕЧАТИ И ГРАНИЦЫ", GOLD), ("ЛКМ — двигать сетку", PALE),
                     ("Колесо — размер ячеек", PALE), ("Shift + колесо — точно", PALE),
                     ("Тяните число для настройки", MUTED), ("Shift + движение — 0.01 px", MUTED),
                     ("", MUTED), ("ЗАКЛЯТИЯ-КЛАВИШИ", GOLD),
                     ("1 / 2 — квадраты / гексы", PALE), ("L — закрепить печать", PALE),
                     ("G — видимость сетки", PALE), ("F — вписать карту", PALE),
                     ("R — сбросить сетку", PALE), ("Esc — покинуть атлас", PALE)]
            for i, (text, color) in enumerate(lines):
                self.label(text, (x, 265 + i*28), color, "small")
        labels = {"section_grid": "Печати", "section_map": "Карта", "section_guide": "Гримуар",
                  "square": "Квадраты", "hex": "Гексы", "minus": "−", "plus": "+",
                  "lock": "Открепить печать  ·  L" if self.grid_locked else "Закрепить печать  ·  L",
                  "visibility": "Сетка проявлена  ·  G" if self.grid_visible else "Сетка сокрыта  ·  G",
                  "color": "Чернильные линии" if self.grid_dark else "Лунные линии",
                  "opacity_minus": "−", "opacity_plus": "+", "reset": "Сбросить печать  ·  R",
                  "fit": "Охватить весь мир  ·  F", "actual": "Исходный размер  ·  100%"}
        mouse = pygame.mouse.get_pos()
        labels["toggle_mode"] = "К редактированию" if self.mode == "play" else "Начать игру"
        labels["add_player"] = "+ Добавить участника"
        labels["kind_player"] = "Игрок"
        labels["kind_enemy"] = "Противник"
        for i, player in enumerate(self.players):
            # Fit arbitrary Unicode names to the roster width.
            name = ("Враг · " if player.kind == "enemy" else "") + player.name
            full_name = name
            available = self.px(262-30)-self.fonts["body"].size(f"{player.hp}/{player.max_hp}")[0]
            while name and self.fonts["body"].size(name + "…")[0] > available:
                name = name[:-1]
            labels[f"player_{i}"] = name + ("…" if name != full_name else "")
        for rect, action in self.buttons:
            selected = action in (self.grid_type, "section_" + self.section) or (action == "lock" and self.grid_locked) or action == f"player_{self.selected_player}" or action == "kind_" + self.character_kind
            disabled = self.grid_locked and action in ("square", "hex", "minus", "plus", "reset")
            fill = (62, 46, 68) if selected else (45, 38, 63) if rect.collidepoint(mouse) and not disabled else (33, 29, 48)
            pygame.draw.rect(self.screen, fill, rect, border_radius=self.px(4))
            pygame.draw.rect(self.screen, GOLD if selected else EDGE, rect, max(1, self.px(1)), border_radius=self.px(4))
            text = labels[action]
            face = self.fonts["body"]
            if action.startswith("player_"):
                actor = self.players[int(action.split("_")[1])]
                hp_text = f"{actor.hp}/{actor.max_hp}"
                # Reserve the right side for health regardless of name length.
                glyph = self.render_text(text, PALE)
                self.screen.blit(glyph, (rect.x+self.px(9), rect.centery-glyph.get_height()//2))
                health = self.render_text(hp_text, (219, 125, 132) if actor.kind == "enemy" else GOLD)
                self.screen.blit(health, (rect.right-self.px(8)-health.get_width(), rect.centery-health.get_height()//2))
                continue
            tw, th = face.size(text)
            self.screen.blit(self.render_text(text, (94, 85, 109) if disabled else GOLD if selected else PALE),
                             (rect.centerx - tw//2, rect.centery - th//2))
        bottom = self.uh - 48
        self.label("РЕЖИМ ПРИКЛЮЧЕНИЯ" if self.mode == "play" else "ПЕЧАТЬ ЗАКРЕПЛЕНА" if self.grid_locked else "ПЕЧАТЬ СВОБОДНА", (26, bottom), GOLD, "small")
        self.label("ЛКМ: монетка  ·  ПКМ: карта  ·  Колесо: вид" if self.mode == "play" else "Ctrl + колесо: вид  ·  Shift: точная настройка", (252, bottom), MUTED, "small")
        if self.image is not None:
            self.label(f"ВИД  {self.zoom*100:.1f}%", (self.sx + 18, bottom), GOLD, "small")
            if self.grid_visible and self.cell_size*self.zoom < 8:
                self.label("Приблизьте вид, чтобы проявить сетку", (36, 160), GOLD, "small")
        if self.message and pygame.time.get_ticks() < self.message_until:
            rect = self.box(38, self.uh - 126, self.canvas.w/self.ui_scale - 28, 36)
            pygame.draw.rect(self.screen, PANEL, rect, border_radius=self.px(4))
            self.label(self.message, (48, self.uh - 117), PALE, "small", rect.w/self.ui_scale - 20)
        pygame.display.flip()
