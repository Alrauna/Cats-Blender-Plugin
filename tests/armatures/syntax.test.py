# GPL License

import unittest
import importlib
import sys

import bpy


PACKAGE_ID = 'cats_blender_plugin'


def find_enabled_module():
    modules = [
        addon.module
        for addon in bpy.context.preferences.addons
        if addon.module.rsplit('.', 1)[-1] == PACKAGE_ID
    ]
    if len(modules) != 1:
        raise AssertionError(f'Expected one enabled CATS extension, found {modules!r}')
    return modules[0]


class TestAddon(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.module_name = find_enabled_module()
        cls.cats = importlib.import_module(cls.module_name)

    def test_extension_module_name(self):
        self.assertEqual(PACKAGE_ID, self.module_name.rsplit('.', 1)[-1])

    def test_registration_entrypoints(self):
        self.assertTrue(self.cats.__name__.startswith('bl_ext.'))
        self.assertTrue(callable(self.cats.register))
        self.assertTrue(callable(self.cats.unregister))


suite = unittest.defaultTestLoader.loadTestsFromTestCase(TestAddon)
runner = unittest.TextTestRunner()
ret = not runner.run(suite).wasSuccessful()
sys.exit(ret)
