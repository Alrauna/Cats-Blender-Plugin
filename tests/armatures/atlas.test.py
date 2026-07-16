# GPL License

import unittest
import sys
import bpy


class TestAddon(unittest.TestCase):
    def test_material_combiner_integration_operator_is_registered(self):
        self.assertIsNotNone(bpy.ops.cats_atlas.enable_smc.get_rna_type())

    def test_missing_optional_material_combiner_is_handled(self):
        self.assertEqual({'FINISHED'}, bpy.ops.cats_atlas.enable_smc())


suite = unittest.defaultTestLoader.loadTestsFromTestCase(TestAddon)
runner = unittest.TextTestRunner()
ret = not runner.run(suite).wasSuccessful()
sys.exit(ret)
