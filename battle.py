"""Initiative entry and the first active turn of a local battle."""

import math
import pygame


def health_arc_points(center, radius, fraction):
    """Remaining arc stays centered at the top; both ends retreat equally."""
    fraction = max(0.0, min(1.0, fraction))
    if fraction == 0:
        return []
    span = math.tau*fraction
    steps = max(8, math.ceil(span*radius/2))
    return [(center[0]+radius*math.cos(-math.pi/2-span/2+span*i/steps),
             center[1]+radius*math.sin(-math.pi/2-span/2+span*i/steps)) for i in range(steps+1)]


class BattleMode:
    def init_battle(self):
        self.battle_state = None
        self.initiative_index = 0
        self.initiative_text = ""
        self.turn_order = []
        self.active_actor = None

    def battle_action(self, action):
        if action == "start_battle":
            if self.battle_state is not None:
                return True
            if not self.players:
                self.notify("Добавьте хотя бы одного участника.")
                return True
            self.battle_state = "setup"
            self.initiative_index = 0
            self.initiative_text = ""
            self.turn_order = []
            self.active_actor = None
            for actor in self.players:
                actor.initiative = None
            self.name_focused = False
            self.token_drag = None
            self.layout()
            pygame.key.start_text_input()
            pygame.key.set_text_input_rect(self.initiative_field)
            return True
        if action == "confirm_initiative":
            if self.battle_state != "setup":
                return True
            try:
                value = int(self.initiative_text)
                if not -99 <= value <= 999:
                    raise ValueError
            except ValueError:
                self.notify("Введите целую инициативу от −99 до 999.")
                return True
            self.players[self.initiative_index].initiative = value
            self.initiative_index += 1
            self.initiative_text = ""
            if self.initiative_index == len(self.players):
                self.battle_state = "active"
                # Equal initiative keeps the order in which actors were added.
                self.turn_order = sorted(range(len(self.players)), key=lambda i: -self.players[i].initiative)
                self.active_actor = self.turn_order[0]
                self.selected_player = self.active_actor
                self.player_scroll = 0
                pygame.key.stop_text_input()
                self.notify(f"Первым ходит {self.players[self.active_actor].name}.")
            self.layout()
            return True
        if action == "end_battle":
            self.init_battle()
            self.token_drag = None
            self.player_scroll = 0
            pygame.key.stop_text_input()
            self.layout()
            return True
        return False

    def handle_battle_event(self, event):
        if self.battle_state != "setup":
            return False
        if event.type == pygame.TEXTINPUT:
            self.initiative_text = (self.initiative_text + "".join(c for c in event.text if c in "-0123456789"))[:4]
            return True
        if event.type == pygame.KEYDOWN:
            if event.key == pygame.K_BACKSPACE:
                self.initiative_text = self.initiative_text[:-1]
            elif event.key in (pygame.K_RETURN, pygame.K_KP_ENTER):
                self.battle_action("confirm_initiative")
            elif event.key == pygame.K_ESCAPE:
                self.battle_action("end_battle")
            return True
        if event.type == pygame.MOUSEBUTTONDOWN:
            if event.button == 1:
                for rect, action in self.buttons:
                    if rect.collidepoint(event.pos):
                        self.action(action)
                        return True
                pygame.key.start_text_input()
            return True
        if event.type in (pygame.MOUSEMOTION, pygame.MOUSEBUTTONUP, pygame.MOUSEWHEEL):
            return True
        return False

    def draw_battle_panel(self):
        from fantasy_ui import GOLD, PALE, MUTED, EDGE
        x = self.sx+20
        if self.battle_state == "setup":
            actor = self.players[self.initiative_index]
            self.label("Бросок судьбы", (x, 220), GOLD, "heading")
            self.label(f"Участник {self.initiative_index+1} из {len(self.players)}", (x, 268), MUTED)
            self.label(actor.name, (x, 300), PALE, "heading", 260)
            self.label("Введите инициативу", (x, 350), MUTED)
            pygame.draw.rect(self.screen, (18, 18, 32), self.initiative_field)
            pygame.draw.rect(self.screen, GOLD, self.initiative_field, max(1, self.px(1)))
            cursor = "|" if pygame.time.get_ticks()%1000 < 500 else ""
            self.label(self.initiative_text+cursor, (x+12, 389), PALE, "value")
            self.label("Enter — подтвердить", (x, 500), MUTED, "small")
            self.label("При равенстве — порядок", (x, 540), MUTED, "small")
            self.label("добавления участников.", (x, 565), MUTED, "small")
        else:
            actor = self.players[self.active_actor]
            self.label("Сражение началось", (x, 220), GOLD, "heading")
            self.label("СЕЙЧАС ХОДИТ", (x, 268), MUTED, "small")
            self.label(actor.name, (x, 295), GOLD, "heading", 260)
            self.label(f"Инициатива: {actor.initiative}", (x, 333), PALE)
            self.label("Двигается только первый.", (x, 430), MUTED, "small")
            self.label("ОЧЕРЕДЬ ПО ИНИЦИАТИВЕ", (x, 470), GOLD, "small")

