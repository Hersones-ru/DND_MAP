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
            self.assertGreater(self.app.cell_size, size)
            self.assertEqual(self.app.zoom, zoom)
        world = self.app.to_world(point)
        with patch("pygame.mouse.get_pos", return_value=point), patch("pygame.key.get_mods", return_value=pygame.KMOD_CTRL):
            self.app.handle_event(wheel)
        self.assertLess(self.app.to_world(point).distance_to(world), 1e-8)
        self.assertGreater(self.app.zoom, zoom)

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
