# GPL License

import sys
import unittest

import bpy


class TestAddon(unittest.TestCase):
    def test_eye_tracking_operator_is_registered(self):
        self.assertIsNotNone(bpy.ops.cats_eyes.create_eye_tracking.get_rna_type())

    def test_eye_tracking_is_unavailable_when_all_outputs_are_disabled(self):
        scene = bpy.context.scene
        original_movement = scene.disable_eye_movement
        original_blinking = scene.disable_eye_blinking
        try:
            scene.disable_eye_movement = True
            scene.disable_eye_blinking = True
            self.assertFalse(bpy.ops.cats_eyes.create_eye_tracking.poll())
        finally:
            scene.disable_eye_movement = original_movement
            scene.disable_eye_blinking = original_blinking


suite = unittest.defaultTestLoader.loadTestsFromTestCase(TestAddon)
runner = unittest.TextTestRunner()
ret = not runner.run(suite).wasSuccessful()
sys.exit(ret)
