"""Functional checks using SDL's off-screen video driver."""

import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

os.environ["SDL_VIDEODRIVER"] = "dummy"
os.environ["SDL_AUDIODRIVER"] = "dummy"
os.environ["PYGAME_HIDE_SUPPORT_PROMPT"] = "1"

import pygame

from main import MapAssistant


class MapAssistantTests(unittest.TestCase):
    def setUp(self):
        self.app = MapAssistant()
        self.temp = tempfile.TemporaryDirectory()
        self.path = Path(self.temp.name) / "карта с пробелами.png"
        surface = pygame.Surface((800, 600))
        surface.fill((90, 110, 80))
        pygame.draw.rect(surface, (130, 90, 65), (100, 100, 400, 300))
        pygame.image.save(surface, self.path)

    def tearDown(self):
        pygame.quit()
        self.temp.cleanup()

    def load(self):
        self.app.handle_event(pygame.event.Event(pygame.DROPFILE, file=str(self.path)))
        self.assertEqual(self.app.image.get_size(), (800, 600))

    def test_drop_and_invalid_file_preserve_map(self):
        self.load()
        image = self.app.image
        bad = Path(self.temp.name) / "bad.png"
        bad.write_text("not an image")
        self.assertFalse(self.app.load_image(str(bad)))
        self.assertIs(self.app.image, image)
        self.assertFalse(self.app.load_image(str(bad.with_name("missing.png"))))

    def test_grid_drag_is_independent_and_uses_map_coordinates(self):
        self.load()
        pan = self.app.pan.copy()
        point = self.app.canvas.center
        self.app.handle_event(pygame.event.Event(pygame.MOUSEBUTTONDOWN, button=1, pos=point))
        self.app.handle_event(pygame.event.Event(pygame.MOUSEMOTION, rel=(32, -16)))
        self.assertEqual(self.app.pan, pan)
        self.assertLess(self.app.grid_offset.distance_to(pygame.Vector2(32, -16) / self.app.zoom), 1e-8)
        self.app.handle_event(pygame.event.Event(pygame.MOUSEBUTTONUP, button=1))
        self.assertIsNone(self.app.drag)

    def test_map_pan_preserves_grid_alignment(self):
        self.load()
        offset = self.app.grid_offset.copy()
        pan = self.app.pan.copy()
        self.app.handle_event(pygame.event.Event(pygame.MOUSEBUTTONDOWN, button=3, pos=self.app.canvas.center))
        self.app.handle_event(pygame.event.Event(pygame.MOUSEMOTION, rel=(40, 20)))
        self.assertEqual(self.app.pan, pan + (40, 20))
        self.assertEqual(self.app.grid_offset, offset)
        self.app.handle_event(pygame.event.Event(pygame.WINDOWFOCUSLOST))
        self.assertIsNone(self.app.drag)

    def test_wheel_changes_grid_and_ctrl_zoom_preserves_cursor_anchor(self):
        self.load()
        point = self.app.canvas.center
        wheel = pygame.event.Event(pygame.MOUSEWHEEL, y=2)
        with patch("pygame.mouse.get_pos", return_value=point), patch("pygame.key.get_mods", return_value=0):
            size, zoom = self.app.cell_size, self.app.zoom
            self.app.handle_event(wheel)
            self.app.update(1 / 60)
            self.assertGreater(self.app.cell_size, size)
            self.assertEqual(self.app.zoom, zoom)
        world = self.app.to_world(point)
        with patch("pygame.mouse.get_pos", return_value=point), patch("pygame.key.get_mods", return_value=pygame.KMOD_CTRL):
            self.app.handle_event(wheel)
        for _ in range(60):
            self.app.update(1 / 60)
        self.assertLess(self.app.to_world(point).distance_to(world), 1e-8)
        self.assertGreater(self.app.zoom, zoom)

    def test_fractional_wheel_and_fine_adjustment_ease_without_pixel_steps(self):
        self.load()
        point = self.app.canvas.center
        with patch("pygame.mouse.get_pos", return_value=point), patch("pygame.key.get_mods", return_value=pygame.KMOD_SHIFT):
            self.app.handle_event(pygame.event.Event(pygame.MOUSEWHEEL, y=1, precise_y=0.5))
        before = self.app.cell_size
        target = self.app.target_cell_size
        self.assertGreater(target, before)
        self.assertLess(target - before, 0.01)
        self.app.update(1 / 120)
        self.assertGreater(self.app.cell_size, before)
        self.assertLess(self.app.cell_size, target)
        after = self.app.cell_size
        self.app.update(1 / 120)
        self.assertGreater(self.app.cell_size, after)

    def test_lock_blocks_geometry_but_allows_view_and_unlock(self):
        self.load()
        self.app.grid_offset.update(10.5, 22.1)
        self.app.action("lock")
        state = (self.app.cell_size, self.app.grid_offset.copy(), self.app.grid_type)
        for action in ("hex", "reset", "plus", "minus"):
            self.app.action(action)
        self.app.resize_cells(3)
        self.app.handle_event(pygame.event.Event(pygame.MOUSEBUTTONDOWN, button=1, pos=self.app.canvas.center))
        self.app.handle_event(pygame.event.Event(pygame.MOUSEMOTION, rel=(100, 100)))
        self.app.update(1)
        self.assertEqual((self.app.cell_size, self.app.grid_offset, self.app.grid_type), state)
        world = self.app.to_world(self.app.canvas.center)
        zoom = self.app.zoom
        self.app.zoom_at(self.app.canvas.center, 2)
        self.app.update(0.1)
        self.assertGreater(self.app.zoom, zoom)
        self.assertLess(self.app.to_world(self.app.canvas.center).distance_to(world), 1e-8)
        self.app.action("lock")
        self.app.resize_cells(1)
        self.app.update(1)
        self.assertGreater(self.app.cell_size, state[0])

    def test_native_4k_fonts_and_section_navigation(self):
        self.load()
        base_font = self.app.fonts["title"].get_height()
        self.app.handle_event(pygame.event.Event(pygame.VIDEORESIZE, w=3840, h=2160))
        self.assertEqual(self.app.screen.get_size(), (3840, 2160))
        self.assertGreater(self.app.fonts["title"].get_height(), base_font * 2)
        for section in ("map", "guide", "grid"):
            rect = next(r for r, a in self.app.buttons if a == "section_" + section)
            self.app.handle_event(pygame.event.Event(pygame.MOUSEBUTTONDOWN, button=1, pos=rect.center))
            self.assertEqual(self.app.section, section)
            self.app.draw()
            for rect, action in self.app.buttons:
                if action != "toggle_mode":
                    self.assertTrue(self.app.sidebar.contains(rect))

    def test_play_spawn_move_and_reject_occupied_cell_for_both_grids(self):
        for kind in ("square", "hex"):
            self.app.mode = "edit"
            self.load()
            self.app.grid_type = kind
            self.app.mode = "edit"
            self.app.action("toggle_mode")
            for name in ("Эльминстер", "Луна"):
                self.app.player_name = name
                self.app.action("add_player")
            self.assertEqual(len(self.app.players), 2)
            first, second = self.app.players
            self.assertNotEqual(first.cell, second.cell)
            self.assertEqual(self.app.cell_at(self.app.cell_center(first.cell)), first.cell)
            old = first.cell
            origin = pygame.Vector2(self.app.canvas.topleft) + self.app.pan
            def screen(cell):
                p = origin + self.app.cell_center(cell)*self.app.zoom
                return round(p.x), round(p.y)
            self.app.handle_event(pygame.event.Event(pygame.MOUSEBUTTONDOWN, button=1, pos=screen(old)))
            self.app.handle_event(pygame.event.Event(pygame.MOUSEBUTTONUP, button=1, pos=screen(second.cell)))
            self.assertEqual(first.cell, old)
            dest = (old[0]+2, old[1])
            self.assertTrue(self.app.cell_available(dest))
            self.app.handle_event(pygame.event.Event(pygame.MOUSEBUTTONDOWN, button=1, pos=screen(old)))
            self.app.handle_event(pygame.event.Event(pygame.MOUSEBUTTONUP, button=1, pos=screen(dest)))
            self.assertEqual(first.cell, dest)
            self.app.draw()
            size = self.app.cell_size
            self.app.resize_cells(5)
            self.app.action("reset")
            self.app.update(1)
            self.assertEqual(self.app.cell_size, size)

    def test_hp_validation_and_enemy_creation(self):
        self.load()
        self.app.action("toggle_mode")
        for hp, maximum in (("15", "14"), ("-1", "14"), ("1", "0"), ("", "14"), ("abc", "20")):
            self.app.player_name = "Гоблин"
            self.app.hp_input, self.app.max_hp_input = hp, maximum
            self.app.add_player()
            self.assertEqual(len(self.app.players), 0)
        self.app.hp_input, self.app.max_hp_input = "12", "14"
        self.app.add_player()
        hero = self.app.players[0]
        self.assertEqual((hero.hp, hero.max_hp, hero.kind), (12, 14, "player"))
        self.app.action("kind_enemy")
        self.app.player_name = "Гоблин"
        self.app.hp_input, self.app.max_hp_input = "0", "7"
        self.app.add_player()
        enemy = self.app.players[1]
        self.assertEqual((enemy.hp, enemy.max_hp, enemy.kind), (0, 7, "enemy"))
        self.assertNotEqual(hero.cell, enemy.cell)
        self.app.draw()
        self.app.handle_event(pygame.event.Event(pygame.VIDEORESIZE, w=900, h=680))
        self.app.draw()
        for rect, action in self.app.buttons:
            if action != "toggle_mode":
                self.assertTrue(self.app.sidebar.contains(rect))

    def test_battle_initiative_and_only_first_actor_can_move(self):
        for kind in ("square", "hex"):
            self.app.mode = "edit"
            self.app.init_battle()
            self.load()
            self.app.grid_type = kind
            self.app.action("toggle_mode")
            self.app.action("start_battle")
            self.assertIsNone(self.app.battle_state)
            for name in ("Воин", "Маг", "Гоблин"):
                self.app.player_name = name
                self.app.add_player()
            self.app.action("start_battle")
            self.app.initiative_text = ""
            self.app.action("confirm_initiative")
            self.assertEqual(self.app.initiative_index, 0)
            for value in ("-2", "18", "18"):
                self.app.initiative_text = value
                self.app.action("confirm_initiative")
            self.assertEqual(self.app.battle_state, "ties")
            self.app.action("tie_1")
            self.assertEqual(self.app.turn_order, [1, 2, 0])
            self.assertEqual(self.app.active_actor, 1)
            self.app.draw()
            for index in (0, 1):
                origin = pygame.Vector2(self.app.canvas.topleft)+self.app.pan
                p = origin+self.app.cell_center(self.app.players[index].cell)*self.app.zoom
                pos = (round(p.x), round(p.y))
                self.app.handle_event(pygame.event.Event(pygame.MOUSEBUTTONDOWN, button=1, pos=pos))
                self.assertEqual(self.app.token_drag, 1 if index == 1 else None)
                if index == 1:
                    cell = self.app.players[index].cell
                    dest = (cell[0]+3, cell[1])
                    self.assertTrue(self.app.cell_available(dest))
                    p = origin+self.app.cell_center(dest)*self.app.zoom
                    self.app.handle_event(pygame.event.Event(pygame.MOUSEBUTTONUP, button=1, pos=(round(p.x), round(p.y))))
                    self.assertEqual(self.app.players[index].cell, dest)
            count = len(self.app.players)
            self.app.add_player()
            self.assertEqual(len(self.app.players), count)
            self.app.action("end_battle")
            self.assertIsNone(self.app.active_actor)

    def test_hero_priority_manual_ties_and_round_rotation(self):
        self.load()
        self.app.action("toggle_mode")
        for name, kind in (("Враг", "enemy"), ("Воин", "player"), ("Маг", "player"), ("Второй враг", "enemy")):
            self.app.character_kind = kind
            self.app.player_name = name
            self.app.add_player()
        self.app.action("start_battle")
        for value in ("20", "20", "20", "5"):
            self.app.initiative_text = value
            self.app.action("confirm_initiative")
        self.assertEqual(self.app.battle_state, "ties")
        self.assertEqual(self.app.tie_remaining, [1, 2])
        self.assertIsNone(self.app.active_actor)
        self.app.draw()
        rect = next(r for r, a in self.app.buttons if a == "tie_2")
        self.app.handle_event(pygame.event.Event(pygame.MOUSEBUTTONDOWN, button=1, pos=rect.center))
        self.assertEqual(self.app.turn_order, [2, 1, 0, 3])
        self.assertEqual(self.app.active_actor, 2)
        for actor in (1, 0, 3, 2):
            self.app.token_drag = self.app.active_actor
            self.app.action("end_turn")
            self.assertEqual(self.app.active_actor, actor)
            self.assertIsNone(self.app.token_drag)
            self.app.draw()
        self.assertEqual(self.app.round_number, 2)
        self.app.action("end_battle")
        self.assertEqual(self.app.round_number, 1)
        self.assertEqual(self.app.turn_order, [])

    def test_multiple_hero_tie_groups(self):
        self.load()
        self.app.action("toggle_mode")
        for name in ("A", "B", "C", "D"):
            self.app.player_name = name
            self.app.add_player()
        self.app.action("start_battle")
        for value in ("15", "15", "7", "7"):
            self.app.initiative_text = value
            self.app.action("confirm_initiative")
        self.app.action("tie_1")
        self.assertEqual(self.app.tie_remaining, [2, 3])
        self.assertEqual(self.app.battle_state, "ties")
        self.app.action("tie_3")
        self.assertEqual(self.app.turn_order, [1, 0, 3, 2])

    def test_health_arc_shrinks_symmetrically(self):
        from battle import health_arc_points
        import math
        for fraction in (1, .75, .5, .25):
            points = health_arc_points((100, 100), 30, fraction)
            first, last = points[0], points[-1]
            midpoint = points[len(points)//2]
            self.assertGreater(midpoint[1], 129)
            self.assertAlmostEqual(first[0]+last[0], 200)
            self.assertAlmostEqual(first[1], last[1])
            for x, y in points:
                self.assertAlmostEqual(math.hypot(x-100, y-100), 30)
        self.assertEqual(health_arc_points((0, 0), 30, 0), [])
        self.assertTrue(all(y >= 100-1e-8 for x, y in health_arc_points((100, 100), 30, .5)))

    def test_hp_input_and_tab_navigation(self):
        self.load()
        self.app.action("toggle_mode")
        hp_rect = self.app.input_rects["hp"]
        self.app.handle_event(pygame.event.Event(pygame.MOUSEBUTTONDOWN, button=1, pos=hp_rect.center))
        self.app.hp_input = ""
        self.app.handle_event(pygame.event.Event(pygame.TEXTINPUT, text="12abc"))
        self.assertEqual(self.app.hp_input, "12")
        self.app.handle_event(pygame.event.Event(pygame.KEYDOWN, key=pygame.K_TAB, mod=0))
        self.assertEqual(self.app.input_field, "max_hp")
        self.app.max_hp_input = ""
        self.app.handle_event(pygame.event.Event(pygame.TEXTINPUT, text="14"))
        self.app.player_name = "Игрок1"
        self.app.handle_event(pygame.event.Event(pygame.KEYDOWN, key=pygame.K_RETURN))
        self.assertEqual((self.app.players[0].hp, self.app.players[0].max_hp), (12, 14))

    def test_play_text_entry_does_not_trigger_shortcuts(self):
        self.load()
        self.app.action("toggle_mode")
        self.app.handle_event(pygame.event.Event(pygame.MOUSEBUTTONDOWN, button=1, pos=self.app.name_field.center))
        self.app.handle_event(pygame.event.Event(pygame.TEXTINPUT, text="Грим"))
        self.app.handle_event(pygame.event.Event(pygame.KEYDOWN, key=pygame.K_g))
        self.assertTrue(self.app.grid_visible)
        self.app.handle_event(pygame.event.Event(pygame.KEYDOWN, key=pygame.K_RETURN))
        self.assertEqual(self.app.players[0].name, "Грим")
        self.app.player_name = "  "
        self.app.add_player()
        self.assertEqual(len(self.app.players), 1)

    def test_drag_size_field_supports_fractional_precision_and_lock_button(self):
        self.load()
        self.app.handle_event(pygame.event.Event(pygame.MOUSEBUTTONDOWN, button=1, pos=self.app.size_control.center))
        self.assertEqual(self.app.drag, "size")
        with patch("pygame.key.get_mods", return_value=pygame.KMOD_SHIFT):
            self.app.handle_event(pygame.event.Event(pygame.MOUSEMOTION, rel=(1, 0)))
        self.assertAlmostEqual(self.app.target_cell_size, 64.01)
        lock = next(r for r, a in self.app.buttons if a == "lock")
        self.app.handle_event(pygame.event.Event(pygame.MOUSEBUTTONDOWN, button=1, pos=lock.center))
        self.assertTrue(self.app.grid_locked)
        self.assertIsNone(self.app.drag)

    def test_easing_is_independent_of_frame_rate(self):
        self.load()
        self.app.resize_cells(4)
        for _ in range(60):
            self.app.update(1/60)
        at_60 = self.app.cell_size
        self.app.cell_size = 64
        for _ in range(120):
            self.app.update(1/120)
        self.assertAlmostEqual(self.app.cell_size, at_60, places=7)

    def test_both_grids_render_and_are_clipped_to_map(self):
        self.load()
        self.app.message = ""
        self.app.grid_visible = False
        self.app.draw()
        plain = pygame.image.tobytes(self.app.screen.subsurface(self.app.canvas), "RGB")
        outside = self.app.screen.get_at((self.app.canvas.x + 2, self.app.canvas.y + 2))
        rendered = []
        self.app.grid_visible = True
        self.app.grid_offset.update(-19, 23)
        for kind in ("square", "hex"):
            self.app.action(kind)
            self.app.draw()
            rendered.append(pygame.image.tobytes(self.app.screen.subsurface(self.app.canvas), "RGB"))
            self.assertNotEqual(rendered[-1], plain)
            self.assertEqual(self.app.screen.get_at((self.app.canvas.x + 2, self.app.canvas.y + 2)), outside)
        self.assertNotEqual(*rendered)

    def test_sidebar_buttons_resize_and_offscreen_map(self):
        self.load()
        rect = next(rect for rect, action in self.app.buttons if action == "hex")
        self.app.handle_event(pygame.event.Event(pygame.MOUSEBUTTONDOWN, button=1, pos=rect.center))
        self.assertEqual(self.app.grid_type, "hex")
        self.assertIsNone(self.app.drag)
        self.app.handle_event(pygame.event.Event(pygame.VIDEORESIZE, w=900, h=680))
        self.app.draw()
        self.assertEqual(self.app.screen.get_size(), (900, 680))
        self.app.pan.update(-100000, -100000)
        self.app.draw()
        self.app.action("fit")
        self.app.action("reset")
        self.assertEqual(self.app.grid_offset, (0, 0))
        self.assertEqual(self.app.cell_size, 64)

    def test_real_loop_exits_on_quit(self):
        self.load()
        pygame.event.post(pygame.event.Event(pygame.QUIT))
        self.app.run()
        self.assertFalse(self.app.running)


if __name__ == "__main__":
    unittest.main()
