# GPL License

import sys
import unittest

import bpy


BOOLEAN_SCENE_PROPERTIES = (
    'debug_translations',
    'embed_textures',
    'disable_eye_blinking',
    'disable_eye_movement',
    'merge_armatures_cleanup_shape_keys',
    'merge_armatures_remove_zero_weight_bones',
    'merge_armatures_join_meshes',
    'apply_transforms',
    'merge_same_bones',
    'show_more_options',
    'merge_visible_meshes_only',
    'keep_merged_bones',
    'use_google_only',
    'remove_rigidbodies_joints',
    'connect_bones',
    'join_meshes',
    'fix_twist_bones',
    'keep_twist_bones',
    'keep_end_bones',
    'remove_zero_weight',
    'keep_upper_chest',
)


class TestAddon(unittest.TestCase):
    def test_boolean_scene_properties_are_registered_and_writable(self):
        scene = bpy.context.scene
        for name in BOOLEAN_SCENE_PROPERTIES:
            with self.subTest(property=name):
                rna_property = bpy.types.Scene.bl_rna.properties.get(name)
                self.assertIsNotNone(rna_property, f'Missing Scene.{name}')
                self.assertEqual('BOOLEAN', rna_property.type)

                original = getattr(scene, name)
                self.assertIsInstance(original, bool)
                try:
                    setattr(scene, name, not original)
                    self.assertEqual(not original, getattr(scene, name))
                finally:
                    setattr(scene, name, original)


suite = unittest.defaultTestLoader.loadTestsFromTestCase(TestAddon)
runner = unittest.TextTestRunner()
ret = not runner.run(suite).wasSuccessful()
sys.exit(ret)
