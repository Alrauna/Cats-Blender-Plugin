# GPL License

"""Stress CATS registration cleanup and reload behavior in Blender 5.2."""

from __future__ import annotations

import importlib
import sys
import unittest

import bpy


PACKAGE_ID = "cats_blender_plugin"
CYCLES = 3


def cats_module_name() -> str:
    modules = [
        addon.module
        for addon in bpy.context.preferences.addons
        if addon.module.rsplit(".", 1)[-1] == PACKAGE_ID
    ]
    if len(modules) != 1:
        raise AssertionError(f"Expected one enabled CATS extension, found {modules!r}")
    return modules[0]


def operator_rna(namespace: str, name: str):
    try:
        return getattr(getattr(bpy.ops, namespace), name).get_rna_type()
    except (AttributeError, KeyError, RuntimeError):
        return None


def draw_functions(menu_type) -> tuple:
    return tuple(getattr(menu_type.draw, "_draw_funcs", ()))


def cats_keymap_items() -> tuple:
    keyconfig = bpy.context.window_manager.keyconfigs.addon
    if keyconfig is None:
        return ()
    return tuple(
        (keymap.name, item.idname)
        for keymap in keyconfig.keymaps
        for item in keymap.keymap_items
        if item.idname.startswith(("cats_", "mmd_tools_local."))
    )


class LifecycleStressTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.module_name = cats_module_name()
        cls.cats = importlib.import_module(cls.module_name)

    def modules(self):
        prefix = self.module_name
        return {
            "common": importlib.import_module(prefix + ".tools.common"),
            "extentions": importlib.import_module(prefix + ".extentions"),
            "register": importlib.import_module(prefix + ".tools.register"),
            "settings": importlib.import_module(prefix + ".tools.settings"),
            "shapekey": importlib.import_module(prefix + ".tools.shapekey"),
            "translations": importlib.import_module(prefix + ".tools.translations"),
            "updater": importlib.import_module(prefix + ".updater"),
            "mmd": importlib.import_module(prefix + ".extern_tools.mmd_tools_local"),
            "mmd_auto_load": importlib.import_module(
                prefix + ".extern_tools.mmd_tools_local.auto_load"
            ),
            "mmd_handlers": importlib.import_module(
                prefix + ".extern_tools.mmd_tools_local.handlers"
            ),
            "mmd_menus": importlib.import_module(
                prefix + ".extern_tools.mmd_tools_local.menus"
            ),
            "mmd_shading": importlib.import_module(
                prefix + ".extern_tools.mmd_tools_local.panels.shading"
            ),
        }

    def menu_callbacks(self, modules):
        shapekey = modules["shapekey"]
        menus = modules["mmd_menus"]
        shading = modules["mmd_shading"]
        return (
            (bpy.types.MESH_MT_shape_key_context_menu, shapekey.addToShapekeyMenu),
            (bpy.types.TOPBAR_MT_file_import, menus.MMDFileImportMenu.draw_menu),
            (bpy.types.TOPBAR_MT_file_export, menus.MMDFileExportMenu.draw_menu),
            (bpy.types.VIEW3D_MT_armature_add, menus.MMDArmatureAddMenu.draw_menu),
            (bpy.types.VIEW3D_MT_object, menus.MMDObjectMenu.draw_menu),
            (bpy.types.VIEW3D_MT_select_object, menus.MMDSelectObjectMenu.draw_menu),
            (bpy.types.VIEW3D_MT_pose, menus.MMDPoseMenu.draw_menu),
            (bpy.types.VIEW3D_MT_pose_context_menu, menus.MMDPoseMenu.draw_menu),
            (bpy.types.VIEW3D_PT_shading, shading.MMDShadingPanel.draw_panel),
        )

    def assert_registered(self, modules, *, expect_pending_timers):
        extentions = modules["extentions"]
        register = modules["register"]
        updater = modules["updater"]
        handlers = modules["mmd_handlers"]
        auto_load = modules["mmd_auto_load"]
        common = modules["common"]
        translations = modules["translations"]

        for property_name in extentions._SCENE_PROPERTIES + (
            "cats_updater_version_list",
            "cats_update_action",
            "mmd_validation_results",
        ):
            with self.subTest(registered_scene_property=property_name):
                self.assertIsNotNone(
                    bpy.types.Scene.bl_rna.properties.get(property_name)
                )

        for owner, property_names in (
            (
                bpy.types.Object,
                (
                    "mmd_type",
                    "mmd_root",
                    "mmd_rigid",
                    "mmd_joint",
                    "mmd_camera",
                    "select",
                    "hide",
                ),
            ),
            (
                bpy.types.PoseBone,
                (
                    "mmd_bone",
                    "is_mmd_shadow_bone",
                    "mmd_shadow_bone_type",
                    "mmd_ik_toggle",
                ),
            ),
            (bpy.types.Material, ("mmd_material",)),
        ):
            for property_name in property_names:
                with self.subTest(registered_rna=f"{owner.__name__}.{property_name}"):
                    self.assertTrue(hasattr(owner, property_name))

        self.assertIsNotNone(operator_rna("cats_armature", "fix"))
        self.assertIsNotNone(
            operator_rna("mmd_tools_local", "apply_additional_transform")
        )
        self.assertTrue(getattr(register, "__bl_registered_classes"))
        self.assertTrue(all(cls.is_registered for cls in updater.to_register))
        self.assertTrue(all(cls.is_registered for cls in auto_load.ordered_classes))

        self.assertEqual(1, bpy.app.handlers.load_post.count(handlers.MMDHanders.load_hander))
        self.assertEqual(
            1,
            bpy.app.handlers.save_pre.count(handlers.MMDHanders.save_pre_handler),
        )
        for menu_type, callback in self.menu_callbacks(modules):
            with self.subTest(registered_menu=menu_type.__name__):
                self.assertEqual(1, draw_functions(menu_type).count(callback))

        self.assertTrue(hasattr(bpy.types.Action, "_original_getattribute"))
        if expect_pending_timers:
            self.assertTrue(common._pending_one_shot_timers)
            self.assertTrue(translations._pending_one_shot_timers)
            self.assertTrue(
                all(
                    bpy.app.timers.is_registered(callback)
                    for callback in common._pending_one_shot_timers
                    | translations._pending_one_shot_timers
                )
            )
        else:
            self.assertFalse(common._pending_one_shot_timers)
            self.assertFalse(translations._pending_one_shot_timers)
        keymap_items = cats_keymap_items()
        self.assertEqual(2 if sys.platform == "darwin" else 1, len(keymap_items))
        self.assertTrue(
            all(item_idname == "mmd_tools_local.export_pmx" for _, item_idname in keymap_items)
        )

    def assert_unregistered(self, modules):
        extentions = modules["extentions"]
        register = modules["register"]
        settings = modules["settings"]
        updater = modules["updater"]
        handlers = modules["mmd_handlers"]
        auto_load = modules["mmd_auto_load"]
        common = modules["common"]
        translations = modules["translations"]

        for property_name in extentions._SCENE_PROPERTIES + (
            "cats_updater_version_list",
            "cats_update_action",
            "mmd_validation_results",
        ):
            with self.subTest(unregistered_scene_property=property_name):
                self.assertIsNone(
                    bpy.types.Scene.bl_rna.properties.get(property_name)
                )

        for owner, property_names in (
            (
                bpy.types.Object,
                (
                    "mmd_type",
                    "mmd_root",
                    "mmd_rigid",
                    "mmd_joint",
                    "mmd_camera",
                    "select",
                    "hide",
                ),
            ),
            (
                bpy.types.PoseBone,
                (
                    "mmd_bone",
                    "is_mmd_shadow_bone",
                    "mmd_shadow_bone_type",
                    "mmd_ik_toggle",
                ),
            ),
            (bpy.types.Material, ("mmd_material",)),
        ):
            for property_name in property_names:
                with self.subTest(unregistered_rna=f"{owner.__name__}.{property_name}"):
                    self.assertFalse(hasattr(owner, property_name))

        self.assertIsNone(operator_rna("cats_armature", "fix"))
        self.assertIsNone(
            operator_rna("mmd_tools_local", "apply_additional_transform")
        )
        self.assertEqual([], getattr(register, "__bl_registered_classes"))
        self.assertTrue(all(not cls.is_registered for cls in updater.to_register))
        self.assertTrue(all(not cls.is_registered for cls in auto_load.ordered_classes))

        self.assertNotIn(handlers.MMDHanders.load_hander, bpy.app.handlers.load_post)
        self.assertNotIn(
            handlers.MMDHanders.save_pre_handler, bpy.app.handlers.save_pre
        )
        self.assertNotIn(updater.show_update_notification, updater.get_update_post())
        self.assertFalse(
            bpy.app.timers.is_registered(settings.apply_settings_with_timeout)
        )
        self.assertFalse(
            bpy.app.timers.is_registered(updater._consume_update_check_result)
        )
        self.assertFalse(common._pending_one_shot_timers)
        self.assertFalse(translations._pending_one_shot_timers)
        for menu_type, callback in self.menu_callbacks(modules):
            with self.subTest(unregistered_menu=menu_type.__name__):
                self.assertNotIn(callback, draw_functions(menu_type))

        self.assertFalse(hasattr(bpy.types.Action, "_original_getattribute"))
        self.assertEqual((), cats_keymap_items())

    def test_repeated_disable_enable_and_reload(self):
        registered = True
        try:
            for cycle in range(CYCLES):
                modules = self.modules()
                common = modules["common"]
                settings = modules["settings"]
                translations = modules["translations"]
                updater = modules["updater"]

                settings.start_apply_settings_timer()
                if not bpy.app.timers.is_registered(
                    updater._consume_update_check_result
                ):
                    bpy.app.timers.register(
                        updater._consume_update_check_result, first_interval=60.0
                    )
                updater.prepare_to_show_update_notification()
                common._register_one_shot_timer(lambda: None, first_interval=60.0)
                translations._register_one_shot_timer(
                    lambda: None, first_interval=60.0
                )
                self.assert_registered(modules, expect_pending_timers=True)

                self.cats.unregister()
                registered = False
                self.assert_unregistered(modules)

                if cycle == 1:
                    self.cats = importlib.reload(self.cats)

                self.cats.register()
                registered = True
                self.assert_registered(
                    self.modules(), expect_pending_timers=False
                )
        finally:
            if not registered:
                self.cats.register()


def main() -> int:
    result = unittest.TextTestRunner(verbosity=2).run(
        unittest.defaultTestLoader.loadTestsFromTestCase(LifecycleStressTests)
    )
    return 0 if result.wasSuccessful() else 1


if __name__ == "__main__":
    raise SystemExit(main())
