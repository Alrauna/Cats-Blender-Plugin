# GPL License

"""Smoke-test installation, registration, and removal of the CATS extension."""

from __future__ import annotations

import argparse
import importlib
import sys
import unittest

import bpy


PACKAGE_ID = "cats_blender_plugin"
EXPECTED_OPERATORS = (
    ("cats_armature", "fix"),
    ("cats_importer", "import_any_model"),
    ("cats_material", "combine_mats"),
    ("cats_manual", "start_pose_mode_no_shapekey_reset"),
    ("cats_manual", "stop_pose_mode_no_shapekey_reset"),
    ("cats_shapekey", "shape_key_to_basis"),
    ("mmd_tools_local", "apply_additional_transform"),
    ("mmd_tools_local", "clean_additional_transform"),
    ("mmd_tools_local", "clean_shape_keys"),
    ("mmd_tools_local", "clear_temp_materials"),
    ("mmd_tools_local", "clear_uv_morph_view"),
    ("mmd_tools_local", "reset_object_visibility"),
    ("mmd_tools_local", "separate_by_parts"),
)
EXPECTED_PANEL = "VIEW3D_PT_quickaccess_v3"
EXPECTED_SCENE_PROPERTY = "remove_zero_weight"
EXPECTED_MMD_PREFERENCES = (
    "shared_toon_folder",
    "base_texture_folder",
    "dictionary_folder",
    "default_pmx_import_preset",
    "default_pmx_export_preset",
)


def script_arguments() -> list[str]:
    return sys.argv[sys.argv.index("--") + 1 :] if "--" in sys.argv else []


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    expectation = parser.add_mutually_exclusive_group(required=True)
    expectation.add_argument("--expect-enabled", action="store_true")
    expectation.add_argument("--expect-absent", action="store_true")
    return parser.parse_args(script_arguments())


def is_cats_module(module_name: str) -> bool:
    return module_name.rsplit(".", 1)[-1] == PACKAGE_ID


def enabled_cats_modules() -> list[str]:
    return sorted(
        addon.module
        for addon in bpy.context.preferences.addons
        if is_cats_module(addon.module)
    )


def loaded_cats_modules() -> list[str]:
    return sorted(name for name in sys.modules if is_cats_module(name))


def operator_rna(namespace: str, name: str):
    try:
        return getattr(getattr(bpy.ops, namespace), name).get_rna_type()
    except (AttributeError, KeyError, RuntimeError):
        return None


class ExtensionEnabledTests(unittest.TestCase):
    def test_running_in_blender_5_2(self):
        self.assertEqual((5, 2), bpy.app.version[:2])

    def test_extension_is_enabled_and_imported(self):
        enabled = enabled_cats_modules()
        self.assertEqual(1, len(enabled), f"Expected one enabled CATS extension, found {enabled!r}")
        module = importlib.import_module(enabled[0])
        self.assertTrue(callable(getattr(module, "register", None)))
        self.assertTrue(callable(getattr(module, "unregister", None)))
        self.assertTrue(module.__name__.startswith("bl_ext."))
        self.assertEqual(PACKAGE_ID, module.__name__.rsplit(".", 1)[-1])

    def test_expected_operator_surface_is_registered(self):
        for namespace, name in EXPECTED_OPERATORS:
            with self.subTest(operator=f"{namespace}.{name}"):
                self.assertIsNotNone(operator_rna(namespace, name))

    def test_expected_panel_and_scene_property_are_registered(self):
        self.assertIsNotNone(getattr(bpy.types, EXPECTED_PANEL, None))
        self.assertIsNotNone(bpy.types.Scene.bl_rna.properties.get(EXPECTED_SCENE_PROPERTY))

    def test_bundled_mmd_preferences_are_exposed_through_cats(self):
        module_name = enabled_cats_modules()[0]
        preferences = bpy.context.preferences.addons[module_name].preferences
        for property_name in EXPECTED_MMD_PREFERENCES:
            with self.subTest(property=property_name):
                self.assertTrue(hasattr(preferences, property_name))

        preference_value = bpy.app.tempdir
        preferences.base_texture_folder = preference_value
        bpyutils = importlib.import_module(
            module_name + ".extern_tools.mmd_tools_local.bpyutils"
        )
        fileio = importlib.import_module(
            module_name + ".extern_tools.mmd_tools_local.operators.fileio"
        )
        self.assertEqual(
            preference_value,
            bpyutils.FnContext.get_addon_preferences_attribute(
                bpy.context, "base_texture_folder", ""
            ),
        )
        self.assertEqual(module_name, fileio.get_addon_package_name())


class ExtensionAbsentTests(unittest.TestCase):
    def test_extension_is_not_enabled_or_loaded(self):
        self.assertEqual([], enabled_cats_modules())
        self.assertEqual([], loaded_cats_modules())

    def test_registration_surface_was_removed(self):
        for namespace, name in EXPECTED_OPERATORS:
            with self.subTest(operator=f"{namespace}.{name}"):
                self.assertIsNone(operator_rna(namespace, name))
        self.assertIsNone(getattr(bpy.types, EXPECTED_PANEL, None))
        self.assertIsNone(bpy.types.Scene.bl_rna.properties.get(EXPECTED_SCENE_PROPERTY))


def main() -> int:
    args = parse_args()
    case = ExtensionEnabledTests if args.expect_enabled else ExtensionAbsentTests
    result = unittest.TextTestRunner(verbosity=2).run(
        unittest.defaultTestLoader.loadTestsFromTestCase(case)
    )
    return 0 if result.wasSuccessful() else 1


if __name__ == "__main__":
    raise SystemExit(main())
