# GPL License

"""Exercise Blender 5.2 API surfaces used by CATS without external fixtures."""

from __future__ import annotations

import importlib
import inspect
import sys
import tempfile
import unittest
import zipfile
from pathlib import Path

import bpy


PACKAGE_ID = "cats_blender_plugin"


def cats_module_name() -> str:
    modules = [
        addon.module
        for addon in bpy.context.preferences.addons
        if addon.module.rsplit(".", 1)[-1] == PACKAGE_ID
    ]
    if len(modules) != 1:
        raise AssertionError(f"Expected one enabled CATS extension, found {modules!r}")
    return modules[0]


class Blender52ApiTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.module_name = cats_module_name()
        cls.cats = importlib.import_module(cls.module_name)

    def test_layered_action_compatibility(self):
        compat = importlib.import_module(
            self.module_name + ".extern_tools.mmd_tools_local.compat.action_compat"
        )
        obj = bpy.data.objects.new("CATS Action API Smoke", None)
        action = bpy.data.actions.new("CATS Action API Smoke")
        try:
            compat.assign_action_to_datablock(obj, action)
            fcurve = compat.new_fcurve(
                action, "location", index=0, group_name="CATS Smoke", id_type="OBJECT"
            )
            fcurve.keyframe_points.insert(1.0, 2.0)

            self.assertIs(obj.animation_data.action, action)
            self.assertIsNotNone(obj.animation_data.action_slot)
            found_fcurve = compat.get_action_fcurves(action).find("location", index=0)
            self.assertIsNotNone(found_fcurve)
            self.assertEqual(found_fcurve.as_pointer(), fcurve.as_pointer())
            self.assertEqual(1, len(action.layers))
            self.assertEqual(1, len(action.slots))
        finally:
            obj.animation_data_clear()
            bpy.data.objects.remove(obj, do_unlink=True)
            bpy.data.actions.remove(action)

    def test_generated_mmd_camera_actions_have_slots(self):
        camera_module = importlib.import_module(
            self.module_name + ".extern_tools.mmd_tools_local.core.camera"
        )
        scene = bpy.context.scene
        original_frame_range = (scene.frame_start, scene.frame_end, scene.frame_current)
        source_data = bpy.data.cameras.new("CATS Camera Action API Smoke")
        source = bpy.data.objects.new("CATS Camera Action API Smoke", source_data)
        target = bpy.data.objects.new("CATS Camera Target API Smoke", None)
        scene.collection.objects.link(source)
        scene.collection.objects.link(target)
        generated_root = None
        generated_camera = None
        generated_camera_data = None
        generated_actions = []
        try:
            scene.frame_start = 1
            scene.frame_end = 1
            scene.frame_set(1)
            source.location = (0.0, -5.0, 2.0)
            target.location = (0.0, 0.0, 1.0)

            mmd_camera = camera_module.MMDCamera.newMMDCameraAnimation(source, target)
            generated_root = mmd_camera.object()
            generated_camera = mmd_camera.camera()
            generated_camera_data = generated_camera.data
            generated_actions = [
                generated_root.animation_data.action,
                generated_camera.animation_data.action,
            ]

            self.assertIsNotNone(generated_root.animation_data.action_slot)
            self.assertIsNotNone(generated_camera.animation_data.action_slot)
        finally:
            scene.frame_start, scene.frame_end, frame_current = original_frame_range
            scene.frame_set(frame_current)
            if generated_camera is not None:
                bpy.data.objects.remove(generated_camera, do_unlink=True)
            if generated_camera_data is not None:
                bpy.data.cameras.remove(generated_camera_data)
            if generated_root is not None:
                bpy.data.objects.remove(generated_root, do_unlink=True)
            bpy.data.objects.remove(target, do_unlink=True)
            bpy.data.objects.remove(source, do_unlink=True)
            bpy.data.cameras.remove(source_data)
            for action in generated_actions:
                if action.users == 0:
                    bpy.data.actions.remove(action)

    def test_eye_testing_reset_uses_pose_bones(self):
        armature = bpy.data.armatures.new("CATS Eye Reset API Smoke")
        armature_obj = bpy.data.objects.new("CATS Eye Reset API Smoke", armature)
        mesh = bpy.data.meshes.new("CATS Eye Reset API Smoke")
        mesh_obj = bpy.data.objects.new("CATS Eye Reset API Smoke Mesh", mesh)
        bpy.context.scene.collection.objects.link(armature_obj)
        bpy.context.scene.collection.objects.link(mesh_obj)
        try:
            bpy.context.view_layer.objects.active = armature_obj
            armature_obj.select_set(True)
            bpy.ops.object.mode_set(mode="EDIT")
            for index, name in enumerate(("LeftEye", "RightEye")):
                bone = armature.edit_bones.new(name)
                bone.head.x = float(index)
                bone.tail = (float(index), 0.0, 1.0)
            bpy.ops.object.mode_set(mode="OBJECT")

            mesh.from_pydata([(0.0, 0.0, 0.0)], [], [])
            mesh_obj.shape_key_add(name="Basis")
            mesh_obj.parent = armature_obj
            mesh_obj.modifiers.new("Armature", "ARMATURE").object = armature_obj
            bpy.context.scene.armature = armature_obj.name
            bpy.context.scene.mesh_name_eye = mesh_obj.name

            eye_tracking = importlib.import_module(self.module_name + ".tools.eyetracking")
            eye_tracking.eye_left = armature_obj.pose.bones["LeftEye"]
            eye_tracking.eye_right = armature_obj.pose.bones["RightEye"]
            eye_tracking.eye_left_data = armature.bones["LeftEye"]
            eye_tracking.eye_right_data = armature.bones["RightEye"]
            eye_tracking.eye_left_rot = [0.0, 0.0, 0.0]
            eye_tracking.eye_right_rot = [0.0, 0.0, 0.0]

            self.assertIsNone(eye_tracking.stop_testing(None, bpy.context))
            self.assertIsNone(eye_tracking.eye_left)
            self.assertIsNone(eye_tracking.eye_right)
        finally:
            if bpy.context.object and bpy.context.object.mode != "OBJECT":
                bpy.ops.object.mode_set(mode="OBJECT")
            bpy.data.objects.remove(mesh_obj, do_unlink=True)
            bpy.data.meshes.remove(mesh)
            bpy.data.objects.remove(armature_obj, do_unlink=True)
            bpy.data.armatures.remove(armature)

    def test_armature_bone_collections(self):
        armature = bpy.data.armatures.new("CATS Bone Collection API Smoke")
        obj = bpy.data.objects.new("CATS Bone Collection API Smoke", armature)
        bpy.context.scene.collection.objects.link(obj)
        try:
            bpy.context.view_layer.objects.active = obj
            obj.select_set(True)
            bpy.ops.object.mode_set(mode="EDIT")
            edit_bone = armature.edit_bones.new("Smoke Bone")
            edit_bone.tail.z = 1.0
            collection = armature.collections.new("Bones")
            collection.assign(edit_bone)
            bpy.ops.object.mode_set(mode="OBJECT")

            self.assertIn("Smoke Bone", collection.bones)
            self.assertTrue(collection.is_visible)
        finally:
            if obj.mode != "OBJECT":
                bpy.ops.object.mode_set(mode="OBJECT")
            bpy.data.objects.remove(obj, do_unlink=True)
            bpy.data.armatures.remove(armature)

    def test_object_duplicate_uses_blender_52_operator_context(self):
        source = bpy.data.objects.new("CATS Duplicate API Smoke", None)
        bpy.context.scene.collection.objects.link(source)
        duplicate = None
        try:
            bpy.ops.object.select_all(action="DESELECT")
            source.select_set(True)
            bpy.context.view_layer.objects.active = source
            result = bpy.ops.object.duplicate(linked=False)
            duplicate = bpy.context.active_object
            self.assertEqual({"FINISHED"}, result)
            self.assertIsNot(source, duplicate)
        finally:
            if duplicate is not None and duplicate.name in bpy.data.objects:
                bpy.data.objects.remove(duplicate, do_unlink=True)
            if source.name in bpy.data.objects:
                bpy.data.objects.remove(source, do_unlink=True)

    def test_removed_collada_operator_is_handled(self):
        with self.assertRaises(KeyError):
            bpy.ops.wm.collada_import.get_rna_type()

        importer = importlib.import_module(self.module_name + ".tools.importer")
        common = importlib.import_module(self.module_name + ".tools.common")
        reports = []
        original_show_error = common.show_error
        common.show_error = lambda _scale, lines, **_kwargs: reports.extend(lines)
        try:
            importer.ImportAnyModel.import_file(bpy.app.tempdir, "missing.dae")
        finally:
            common.show_error = original_show_error

        self.assertTrue(reports)
        self.assertIn("Collada", reports[0])
        self.assertIn("Blender 5.2", reports[0])

    def test_shape_key_order_uses_public_id_properties(self):
        armature = bpy.data.armatures.new("CATS Shape Order API Smoke")
        try:
            armature["CUSTOM"] = {"shape_key_order": ["Basis", "Smile"]}
            custom = armature.get("CUSTOM", {})
            if hasattr(custom, "to_dict"):
                custom = custom.to_dict()
            self.assertEqual(["Basis", "Smile"], custom["shape_key_order"])
        finally:
            bpy.data.armatures.remove(armature)

    def test_mmd_color_data_uses_current_mesh_attributes(self):
        mesh = bpy.data.meshes.new("CATS MMD Color Attribute API Smoke")
        try:
            mesh.from_pydata(
                [(0.0, 0.0, 0.0), (1.0, 0.0, 0.0), (0.0, 1.0, 0.0)],
                [],
                [(0, 1, 2)],
            )
            attribute = mesh.color_attributes.new(
                name="Color", type="BYTE_COLOR", domain="CORNER"
            )
            attribute.data.foreach_set(
                "color",
                (
                    1.0,
                    0.0,
                    0.0,
                    1.0,
                    0.0,
                    1.0,
                    0.0,
                    1.0,
                    0.0,
                    0.0,
                    1.0,
                    1.0,
                ),
            )
            self.assertEqual("BYTE_COLOR", attribute.data_type)
            self.assertEqual("CORNER", attribute.domain)
            self.assertEqual(len(mesh.loops), len(attribute.data))
        finally:
            bpy.data.meshes.remove(mesh)

    def test_mutable_state_is_outside_the_installed_extension(self):
        install_root = Path(self.cats.__file__).resolve().parent
        settings = importlib.import_module(self.module_name + ".tools.settings")
        translate = importlib.import_module(self.module_name + ".tools.translate")
        translations = importlib.import_module(self.module_name + ".tools.translations")
        updater = importlib.import_module(self.module_name + ".updater")

        mutable_paths = (
            settings.settings_file,
            translate.dictionary_file,
            translate.dictionary_google_file,
            translations.settings_file,
            updater.ignore_ver_file,
            updater.downloads_dir,
        )
        for value in mutable_paths:
            with self.subTest(path=value):
                self.assertFalse(Path(value).resolve().is_relative_to(install_root))

    def test_mmd_file_handlers_accept_blender_52_arguments(self):
        handlers = importlib.import_module(
            self.module_name + ".extern_tools.mmd_tools_local.handlers"
        )
        inspect.signature(handlers.MMDHanders.load_hander).bind("", None)
        inspect.signature(handlers.MMDHanders.save_pre_handler).bind("", None)
        self.assertIn(handlers.MMDHanders.load_hander, bpy.app.handlers.load_post)
        self.assertIn(handlers.MMDHanders.save_pre_handler, bpy.app.handlers.save_pre)
        handlers.MMDHanders.save_pre_handler("", None)
        handlers.MMDHanders.load_hander("", None)

    def test_network_operators_respect_offline_mode(self):
        self.assertFalse(bpy.app.online_access)
        with self.assertRaisesRegex(RuntimeError, "Online access is disabled"):
            bpy.ops.cats_updater.check_for_update()
        with self.assertRaisesRegex(RuntimeError, "Online access is disabled"):
            bpy.ops.cats_translations.download_latest()

    def test_updater_cannot_use_the_archived_upstream_repository(self):
        updater = importlib.import_module(self.module_name + ".updater")
        self.assertEqual("", updater.UPDATE_REPOSITORY)
        self.assertFalse(updater._update_source_configured())
        with self.assertRaises(KeyError):
            bpy.ops.mmd_tools_local.check_addon_update.get_rna_type()
        with self.assertRaises(KeyError):
            bpy.ops.mmd_tools_local.update_addon.get_rna_type()

        original_online_access = updater._online_access_allowed
        original_urlopen = updater.urllib.request.urlopen
        original_checked_on_startup = updater.checked_on_startup
        original_show_error = updater.show_error
        try:
            updater._online_access_allowed = lambda: True
            updater.urllib.request.urlopen = lambda *_args, **_kwargs: self.fail(
                "Updater attempted network access without a configured fork repository"
            )
            self.assertFalse(
                updater.get_github_releases("", blender_series=(5, 2))
            )

            updater.checked_on_startup = False
            updater.show_error = ""
            updater.check_for_update_background(check_on_startup=True)
            self.assertTrue(updater.checked_on_startup)
            self.assertFalse(updater.is_checking_for_update)
            self.assertFalse(
                bpy.app.timers.is_registered(updater._consume_update_check_result)
            )
        finally:
            updater._online_access_allowed = original_online_access
            updater.urllib.request.urlopen = original_urlopen
            updater.checked_on_startup = original_checked_on_startup
            updater.show_error = original_show_error

    def test_registration_round_trip_has_no_rna_residue(self):
        self.cats.unregister()
        try:
            for property_name in (
                "remove_zero_weight",
                "pose_to_shapekey_name",
                "cats_updater_version_list",
                "cats_update_action",
            ):
                self.assertIsNone(bpy.types.Scene.bl_rna.properties.get(property_name))
            self.assertFalse(hasattr(bpy.types.Object, "mmd_root"))
            self.assertFalse(hasattr(bpy.types.PoseBone, "mmd_bone"))
        finally:
            self.cats.register()

        self.assertIsNotNone(bpy.types.Scene.bl_rna.properties.get("remove_zero_weight"))
        self.assertTrue(hasattr(bpy.types.Object, "mmd_root"))
        self.assertTrue(hasattr(bpy.types.PoseBone, "mmd_bone"))

    def test_sdef_driver_callbacks_are_removed_on_unregister(self):
        sdef = importlib.import_module(
            self.module_name + ".extern_tools.mmd_tools_local.core.sdef"
        )
        callback_names = ("mmd_sdef_driver", "mmd_sdef_driver_wrap")
        sdef.FnSDEF.register_driver_function()
        for name in callback_names:
            self.assertIs(sdef.FnSDEF, bpy.app.driver_namespace[name].__self__)

        self.cats.unregister()
        try:
            for name in callback_names:
                self.assertNotIn(name, bpy.app.driver_namespace)
        finally:
            self.cats.register()
            sdef.FnSDEF.register_driver_function()

    def test_updater_normalizes_and_validates_source_archives(self):
        updater = importlib.import_module(self.module_name + ".updater")
        inspect.signature(updater.show_update_notification).bind(None, None)
        install_root = Path(self.cats.__file__).resolve().parent
        manifest = (install_root / "blender_manifest.toml").read_text(encoding="utf-8")

        with tempfile.TemporaryDirectory() as directory:
            source_path = Path(directory) / "source.zip"
            normalized_path = Path(directory) / "normalized.zip"
            with zipfile.ZipFile(source_path, "w", compression=zipfile.ZIP_DEFLATED) as source:
                source.writestr("cats-main/blender_manifest.toml", manifest)
                source.writestr("cats-main/__init__.py", "")
                source.writestr("cats-main/tests/not-shipped.py", "")
                source.writestr("outside.txt", "")

            updater._normalize_source_archive(source_path, normalized_path)
            with zipfile.ZipFile(normalized_path) as normalized:
                names = set(normalized.namelist())
            self.assertIn("blender_manifest.toml", names)
            self.assertIn("__init__.py", names)
            self.assertNotIn("tests/not-shipped.py", names)
            self.assertNotIn("outside.txt", names)
            self.assertEqual("", updater._validate_update_archive(normalized_path))

            wrong_series_path = Path(directory) / "wrong-series.zip"
            current_version_line = f'version = "{self.cats.CATS_VERSION}"'
            self.assertIn(current_version_line, manifest)
            with zipfile.ZipFile(
                wrong_series_path, "w", compression=zipfile.ZIP_DEFLATED
            ) as wrong_series:
                wrong_series.writestr(
                    "blender_manifest.toml",
                    manifest.replace(
                        current_version_line, 'version = "5.3.0"', 1
                    ),
                )
                wrong_series.writestr("__init__.py", "")
            self.assertIn(
                "different Cats/Blender release series",
                updater._validate_update_archive(wrong_series_path),
            )

            unsafe_path = Path(directory) / "unsafe-path.zip"
            with zipfile.ZipFile(
                unsafe_path, "w", compression=zipfile.ZIP_DEFLATED
            ) as unsafe:
                unsafe.writestr("blender_manifest.toml", manifest)
                unsafe.writestr("__init__.py", "")
                unsafe.writestr("..\\outside.py", "")
            self.assertIn(
                "unsafe path", updater._validate_update_archive(unsafe_path)
            )


def main() -> int:
    result = unittest.TextTestRunner(verbosity=2).run(
        unittest.defaultTestLoader.loadTestsFromTestCase(Blender52ApiTests)
    )
    return 0 if result.wasSuccessful() else 1


if __name__ == "__main__":
    raise SystemExit(main())
