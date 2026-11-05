"""Local play session: grid coordinates, character coins and input."""

from dataclasses import dataclass
import math

import pygame
import pygame.gfxdraw
from battle import BattleMode, health_arc_points


@dataclass
class Character:
    name: str
    cell: tuple[int, int]
    color: tuple[int, int, int]
    hp: int = 10
    max_hp: int = 10
    kind: str = "player"
    initiative: int | None = None


class PlayMode(BattleMode):
    def init_play(self):
        self.init_battle()
        self.mode = "edit"
        self.players = []
        self.player_name = ""
        self.name_focused = False
        self.input_field = "name"
        self.hp_input = "10"
        self.max_hp_input = "10"
        self.character_kind = "player"
        self.selected_player = None
        self.token_drag = None
        self.token_pointer = None
        self.player_scroll = 0

    def cell_center(self, cell):
        col, row = cell
        s = self.cell_size
        if self.grid_type == "square":
            return self.grid_offset + pygame.Vector2((col + .5)*s, (row + .5)*s)
        h = math.sqrt(3)*s/2
        return self.grid_offset + pygame.Vector2(col*.75*s, (row + (col % 2)/2)*h)

    def cell_at(self, world):
        p = pygame.Vector2(world) - self.grid_offset
        s = self.cell_size
        if self.grid_type == "square":
            return math.floor(p.x/s), math.floor(p.y/s)
        # Nearest center in the flat-top, odd-column lattice, including negatives.
        col = round(p.x/(.75*s))
        h = math.sqrt(3)*s/2
        candidates = [(c, round(p.y/h - (c % 2)/2)) for c in range(col-1, col+2)]
        return min(candidates, key=lambda cell: self.cell_center(cell).distance_squared_to(world))

    def cell_available(self, cell, exclude=None):
        if self.image is None:
            return False
        p = self.cell_center(cell)
        mx = self.cell_size/2
        my = mx if self.grid_type == "square" else math.sqrt(3)*self.cell_size/4
        w, h = self.image.get_size()
        return (mx <= p.x <= w-mx and my <= p.y <= h-my
                and all(i == exclude or player.cell != cell for i, player in enumerate(self.players)))

    def add_player(self):
        if self.battle_state is not None:
            self.notify("Сначала завершите сражение.")
            return
        name = self.player_name.strip()
        if self.image is None:
            self.notify("Сначала загрузите карту в режиме редактирования.")
            return
        if not name:
            self.notify("Введите имя персонажа.")
            return
        try:
            hp, max_hp = int(self.hp_input), int(self.max_hp_input)
            if not 0 <= hp <= max_hp <= 99999 or max_hp == 0:
                raise ValueError
        except ValueError:
            self.notify("ХП: целые числа; максимум 1–99999, текущие от 0 до максимума.")
            return
        # Search outward from the viewport, clamped to the actual map.
        w, h = self.image.get_size()
        p = self.to_world(self.canvas.center)
        p.update(max(0, min(w, p.x)), max(0, min(h, p.y)))
        col, row = self.cell_at(p)
        max_radius = math.ceil(max(w, h)/(.75*self.cell_size)) + 4
        chosen = None
        for radius in range(max_radius):
            for dx in range(-radius, radius+1):
                for dy in ((0,) if radius == 0 else (-radius, radius)):
                    cell = (col+dx, row+dy)
                    if self.cell_available(cell):
                        chosen = cell
                        break
                if chosen is not None:
                    break
            if chosen is None and radius:
                for dy in range(-radius+1, radius):
                    for dx in (-radius, radius):
                        cell = (col+dx, row+dy)
                        if self.cell_available(cell):
                            chosen = cell
                            break
                    if chosen is not None:
                        break
            if chosen is not None:
                break
        if chosen is None:
            self.notify("На карте нет свободной полной клетки. Уменьшите сетку.")
            return
        colors = [(193, 143, 71), (111, 154, 179), (153, 116, 180), (110, 162, 125), (193, 113, 109)]
        color = (180, 72, 84) if self.character_kind == "enemy" else colors[len(self.players) % len(colors)]
        self.players.append(Character(name, chosen, color, hp, max_hp, self.character_kind))
        self.selected_player = len(self.players)-1
        self.player_scroll = max(0, len(self.players)-self.roster_capacity())
        self.player_name = ""
        self.layout()
        self.notify(f"{name} вступает в приключение.")

    def roster_capacity(self):
        start = 494 if self.battle_state == "active" else 624
        return max(1, int((self.uh-start-72)//48))

    def play_action(self, action):
        if self.battle_action(action):
            return True
        if action == "toggle_mode" and self.battle_state is not None:
            self.notify("Сначала завершите или отмените сражение.")
            return True
        if action in ("kind_player", "kind_enemy"):
            self.character_kind = action.removeprefix("kind_")
            return True
        if action == "toggle_mode":
            self.mode = "play" if self.mode == "edit" else "edit"
            self.target_cell_size = self.cell_size
            self.drag = self.drag_button = self.token_drag = None
            self.name_focused = False
            pygame.key.stop_text_input()
            self.layout()
            return True
        if action == "add_player":
            self.add_player()
            return True
        if action.startswith("player_"):
            self.selected_player = int(action.split("_")[1])
            center = self.cell_center(self.players[self.selected_player].cell)
            self.pan = pygame.Vector2(self.canvas.size)/2-center*self.zoom
            self.zoom_anchor = None
            return True
        return False

    def handle_play_event(self, event):
        if self.mode != "play":
            return False
        if self.handle_battle_event(event):
            return True
        if event.type == pygame.DROPFILE:
            self.notify("Для замены карты переключитесь в редактирование.")
            return True
        fields = {"name": "player_name", "hp": "hp_input", "max_hp": "max_hp_input"}
        if event.type == pygame.TEXTINPUT and self.name_focused:
            attr = fields[self.input_field]
            text = "".join(c for c in event.text if c.isprintable())
            if self.input_field != "name":
                text = "".join(c for c in text if c in "0123456789")
            limit = 40 if self.input_field == "name" else 5
            setattr(self, attr, (getattr(self, attr) + text)[:limit])
            return True
        if event.type == pygame.KEYDOWN and self.name_focused:
            attr = fields[self.input_field]
            if event.key == pygame.K_BACKSPACE:
                setattr(self, attr, getattr(self, attr)[:-1])
            elif event.key == pygame.K_TAB:
                order = list(fields)
                step = -1 if getattr(event, "mod", 0) & pygame.KMOD_SHIFT else 1
                self.input_field = order[(order.index(self.input_field)+step) % len(order)]
                pygame.key.set_text_input_rect(self.input_rects[self.input_field])
            elif event.key in (pygame.K_RETURN, pygame.K_KP_ENTER):
                self.add_player()
            elif event.key == pygame.K_ESCAPE:
                self.name_focused = False
                pygame.key.stop_text_input()
            return True
        if event.type == pygame.WINDOWFOCUSLOST:
            self.token_drag = None
            self.name_focused = False
            pygame.key.stop_text_input()
        if event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
            field = next((name for name, rect in self.input_rects.items() if rect.collidepoint(event.pos)), None) if self.battle_state is None else None
            self.name_focused = field is not None
            if field is not None:
                self.input_field = field
            if self.name_focused:
                pygame.key.start_text_input()
                pygame.key.set_text_input_rect(self.input_rects[self.input_field])
                return True
            pygame.key.stop_text_input()
            if self.canvas.collidepoint(event.pos):
                self.zoom_anchor = None
                world = self.to_world(event.pos)
                self.token_drag = next((i for i, p in reversed(list(enumerate(self.players)))
                                        if self.cell_center(p.cell).distance_to(world) <= self.cell_size*.34), None)
                if self.battle_state == "active" and self.token_drag != self.active_actor:
                    self.token_drag = None
                    self.notify("Сейчас ходит другой участник.")
                self.selected_player = self.token_drag
                self.token_pointer = event.pos
                return True
        if event.type == pygame.MOUSEMOTION and self.token_drag is not None:
            self.token_pointer = event.pos
            return True
        if event.type == pygame.MOUSEBUTTONUP and event.button == 1 and self.token_drag is not None:
            cell = self.cell_at(self.to_world(event.pos))
            if self.canvas.collidepoint(event.pos) and self.cell_available(cell, self.token_drag):
                self.players[self.token_drag].cell = cell
            else:
                self.notify("Выберите свободную клетку внутри карты.")
            self.token_drag = None
            return True
        if event.type == pygame.MOUSEWHEEL:
            point = pygame.mouse.get_pos()
            if self.sidebar.collidepoint(point):
                self.player_scroll = max(0, min(max(0, len(self.players)-self.roster_capacity()), self.player_scroll-event.y))
                self.layout()
                return True
            if self.canvas.collidepoint(point):
                self.zoom_at(point, getattr(event, "precise_y", event.y))
                return True
        return False

    def draw_tokens(self):
        self.screen.set_clip(self.canvas)
        origin = pygame.Vector2(self.canvas.topleft)+self.pan
        for i, player in enumerate(self.players):
            center = origin + self.cell_center(player.cell)*self.zoom
            if self.token_drag == i:
                center = pygame.Vector2(self.token_pointer)
            radius = max(2, round(self.cell_size*self.zoom*.32))
            x, y = round(center.x), round(center.y)
            if not self.canvas.colliderect(pygame.Rect(x-radius, y-radius, radius*2, radius*2)):
                continue
            pygame.gfxdraw.filled_circle(self.screen, x, y, radius, player.color)
            pygame.gfxdraw.aacircle(self.screen, x, y, radius, (246, 214, 145))
            if player.kind == "enemy":
                pygame.draw.line(self.screen, (255, 207, 180), (x-radius//2, y-radius//2),
                                 (x+radius//2, y-radius//2), max(1, self.px(2)))
            ring_radius = radius + max(3, self.px(4))
            pygame.gfxdraw.aacircle(self.screen, x, y, ring_radius, (75, 35, 49))
            points = health_arc_points((x, y), ring_radius, player.hp/player.max_hp)
            if points:
                pygame.draw.lines(self.screen, (235, 65, 85), False, points, max(2, self.px(3)))
            if self.selected_player == i or self.active_actor == i:
                pygame.gfxdraw.aacircle(self.screen, x, y, ring_radius+4,
                                       (117, 225, 196) if self.active_actor == i else (246, 214, 145))
            glyph = self.render_text(player.name[:1].upper(), (28, 22, 35), "token")
            if glyph.get_height() < radius*1.8:
                self.screen.blit(glyph, (x-glyph.get_width()//2, y-glyph.get_height()//2))
        self.screen.set_clip(None)

    def draw_play_panel(self):
        from fantasy_ui import GOLD, MUTED, PALE, EDGE
        x = self.sx+20
        if self.battle_state is not None:
            self.draw_battle_panel()
            return
        self.label("Участники истории", (x, 220), GOLD, "heading")
        self.label("Имя персонажа / существа", (x, 310), MUTED, "small")
        self.label("Текущие ХП", (x, 392), MUTED, "small")
        self.label("Максимум ХП", (x+136, 392), MUTED, "small")
        values = {"name": self.player_name, "hp": self.hp_input, "max_hp": self.max_hp_input}
        for key, rect in self.input_rects.items():
            focused = self.name_focused and self.input_field == key
            pygame.draw.rect(self.screen, (18, 18, 32), rect, border_radius=self.px(4))
            pygame.draw.rect(self.screen, GOLD if focused else EDGE, rect, max(1, self.px(1)))
            cursor = "|" if focused and pygame.time.get_ticks()%1000 < 500 else ""
            self.label(values[key]+cursor, (rect.x/self.ui_scale+9, rect.y/self.ui_scale+10),
                       PALE, max_width=rect.w/self.ui_scale-18)
        self.label("ЛКМ: монетка · Колесо: вид", (x, 580), MUTED, "small")
