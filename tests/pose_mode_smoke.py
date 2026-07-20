# GPL License

"""Exercise all CATS Pose Mode reset combinations in Blender 5.2."""

from __future__ import annotations

import importlib
import unittest

import bpy
from mathutils import Vector


PACKAGE_ID = "cats_blender_plugin"
POSE_LOCATION = Vector((0.25, -0.5, 0.75))
POSE_ROTATION = Vector((0.2, -0.3, 0.4))
POSE_SCALE = Vector((1.2, 0.8, 1.4))
SHAPE_VALUES = (0.65, -0.35)
UNRELATED_VALUE = 0.45


def cats_module_name() -> str:
    modules = [
        addon.module
        for addon in bpy.context.preferences.addons
        if addon.module.rsplit(".", 1)[-1] == PACKAGE_ID
    ]
    if len(modules) != 1:
        raise AssertionError(f"Expected one enabled CATS extension, found {modules!r}")
    return modules[0]


def invoke_operator(idname: str) -> set[str]:
    namespace, name = idname.split(".", 1)
    return getattr(getattr(bpy.ops, namespace), name)()


class PoseModeSmokeTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.module_name = cats_module_name()
        cls.armature_manual = importlib.import_module(
            cls.module_name + ".tools.armature_manual"
        )
        cls.quickaccess = importlib.import_module(cls.module_name + ".ui.quickaccess")

    def setUp(self):
        self.created_objects = []
        self.created_meshes = []
        self.created_armatures = []
        self._clear_selection()

    def tearDown(self):
        self._cleanup_fixture()

    def _cleanup_fixture(self):
        if bpy.context.object is not None and bpy.context.object.mode != "OBJECT":
            bpy.ops.object.mode_set(mode="OBJECT")
        self._clear_selection()
        for obj in reversed(self.created_objects):
            if obj.name in bpy.data.objects:
                bpy.data.objects.remove(obj, do_unlink=True)
        for mesh in reversed(self.created_meshes):
            if mesh.name in bpy.data.meshes:
                bpy.data.meshes.remove(mesh)
        for armature in reversed(self.created_armatures):
            if armature.name in bpy.data.armatures:
                bpy.data.armatures.remove(armature)
        self.created_objects.clear()
        self.created_meshes.clear()
        self.created_armatures.clear()

    @staticmethod
    def _clear_selection():
        if bpy.context.object is not None and bpy.context.object.mode != "OBJECT":
            bpy.ops.object.mode_set(mode="OBJECT")
        for obj in bpy.context.selected_objects:
            obj.select_set(False)
        bpy.context.view_layer.objects.active = None

    def _new_mesh(self, name: str, parent=None, with_shape_keys=True):
        mesh = bpy.data.meshes.new(name)
        mesh.from_pydata(
            [(0.0, 0.0, 0.0), (1.0, 0.0, 0.0), (0.0, 1.0, 0.0)],
            [],
            [(0, 1, 2)],
        )
        obj = bpy.data.objects.new(name, mesh)
        bpy.context.scene.collection.objects.link(obj)
        obj.parent = parent
        self.created_objects.append(obj)
        self.created_meshes.append(mesh)

        if with_shape_keys:
            obj.shape_key_add(name="Basis")
            smile = obj.shape_key_add(name="Smile")
            frown = obj.shape_key_add(name="Frown")
            frown.slider_min = -1.0
            frown.mute = True
            smile.value, frown.value = SHAPE_VALUES
        return obj

    def _create_fixture(self):
        armature_data = bpy.data.armatures.new("CATS Pose Mode Smoke Armature")
        armature = bpy.data.objects.new(
            "CATS Pose Mode Smoke Armature", armature_data
        )
        bpy.context.scene.collection.objects.link(armature)
        self.created_objects.append(armature)
        self.created_armatures.append(armature_data)

        bpy.context.view_layer.objects.active = armature
        armature.select_set(True)
        bpy.ops.object.mode_set(mode="EDIT")
        bone = armature_data.edit_bones.new("Pose Bone")
        bone.head = (0.0, 0.0, 0.0)
        bone.tail = (0.0, 0.0, 1.0)
        bpy.ops.object.mode_set(mode="OBJECT")

        attached = [
            self._new_mesh("CATS Pose Mode Smoke Face", parent=armature),
            self._new_mesh("CATS Pose Mode Smoke Body", parent=armature),
        ]
        no_shapes = self._new_mesh(
            "CATS Pose Mode Smoke No Shapes",
            parent=armature,
            with_shape_keys=False,
        )
        unrelated = self._new_mesh("CATS Pose Mode Smoke Unrelated")
        unrelated.data.shape_keys.key_blocks["Smile"].value = UNRELATED_VALUE

        bpy.context.scene.armature = armature.name
        self._select_armature(armature)
        self._set_pose(armature)
        return armature, attached, no_shapes, unrelated

    @staticmethod
    def _select_armature(armature):
        for obj in bpy.context.selected_objects:
            obj.select_set(False)
        armature.hide_set(False)
        armature.select_set(True)
        bpy.context.view_layer.objects.active = armature

    @staticmethod
    def _set_pose(armature):
        pose_bone = armature.pose.bones["Pose Bone"]
        pose_bone.rotation_mode = "XYZ"
        pose_bone.location = POSE_LOCATION
        pose_bone.rotation_euler = POSE_ROTATION
        pose_bone.scale = POSE_SCALE

    def assert_pose(self, armature, reset: bool):
        pose_bone = armature.pose.bones["Pose Bone"]
        expected_location = Vector((0.0, 0.0, 0.0)) if reset else POSE_LOCATION
        expected_rotation = Vector((0.0, 0.0, 0.0)) if reset else POSE_ROTATION
        expected_scale = Vector((1.0, 1.0, 1.0)) if reset else POSE_SCALE
        for actual, expected in (
            (pose_bone.location, expected_location),
            (pose_bone.rotation_euler, expected_rotation),
            (pose_bone.scale, expected_scale),
        ):
            self.assertLess((Vector(actual) - expected).length, 1e-6)

    def assert_shape_values(self, meshes, reset: bool):
        expected = (0.0, 0.0) if reset else SHAPE_VALUES
        for mesh in meshes:
            key_blocks = mesh.data.shape_keys.key_blocks
            with self.subTest(mesh=mesh.name):
                self.assertAlmostEqual(expected[0], key_blocks["Smile"].value)
                self.assertAlmostEqual(expected[1], key_blocks["Frown"].value)
                self.assertTrue(key_blocks["Frown"].mute)

    def test_start_pose_mode_reset_matrix(self):
        cases = (
            ("cats_manual.start_pose_mode", True, True),
            (
                "cats_manual.start_pose_mode_no_shapekey_reset",
                True,
                False,
            ),
            ("cats_manual.start_pose_mode_no_reset", False, False),
        )
        for idname, reset_pose, reset_shapes in cases:
            with self.subTest(operator=idname):
                try:
                    armature, attached, _no_shapes, unrelated = self._create_fixture()
                    self.assertEqual({"FINISHED"}, invoke_operator(idname))
                    self.assertEqual("POSE", armature.mode)
                    self.assert_pose(armature, reset_pose)
                    self.assert_shape_values(attached, reset_shapes)
                    self.assertAlmostEqual(
                        UNRELATED_VALUE,
                        unrelated.data.shape_keys.key_blocks["Smile"].value,
                    )
                finally:
                    self._cleanup_fixture()

    def test_stop_pose_mode_reset_matrix(self):
        cases = (
            ("cats_manual.stop_pose_mode", True, True),
            (
                "cats_manual.stop_pose_mode_no_shapekey_reset",
                True,
                False,
            ),
            ("cats_manual.stop_pose_mode_no_reset", False, False),
        )
        for idname, reset_pose, reset_shapes in cases:
            with self.subTest(operator=idname):
                try:
                    armature, attached, _no_shapes, unrelated = self._create_fixture()
                    bpy.ops.object.mode_set(mode="POSE")
                    self.assertEqual({"FINISHED"}, invoke_operator(idname))
                    self.assertEqual("OBJECT", armature.mode)
                    self.assert_pose(armature, reset_pose)
                    self.assert_shape_values(attached, reset_shapes)
                    self.assertAlmostEqual(
                        UNRELATED_VALUE,
                        unrelated.data.shape_keys.key_blocks["Smile"].value,
                    )
                finally:
                    self._cleanup_fixture()

    def test_helper_one_argument_behavior_is_unchanged(self):
        armature, attached, _no_shapes, _unrelated = self._create_fixture()
        self.armature_manual.start_pose_mode(False)
        self.assert_pose(armature, reset=False)
        self.assert_shape_values(attached, reset=False)

        self.armature_manual.stop_pose_mode(True)
        self.assert_pose(armature, reset=True)
        self.assert_shape_values(attached, reset=True)

    def test_repeated_middle_button_cycle_preserves_shape_keys(self):
        armature, attached, _no_shapes, _unrelated = self._create_fixture()
        for _ in range(3):
            self._select_armature(armature)
            self._set_pose(armature)
            for mesh in attached:
                key_blocks = mesh.data.shape_keys.key_blocks
                key_blocks["Smile"].value, key_blocks["Frown"].value = SHAPE_VALUES

            self.assertEqual(
                {"FINISHED"},
                invoke_operator("cats_manual.start_pose_mode_no_shapekey_reset"),
            )
            self.assert_pose(armature, reset=True)
            self.assert_shape_values(attached, reset=False)

            self._set_pose(armature)
            self.assertEqual(
                {"FINISHED"},
                invoke_operator("cats_manual.stop_pose_mode_no_shapekey_reset"),
            )
            self.assert_pose(armature, reset=True)
            self.assert_shape_values(attached, reset=False)

    def test_middle_buttons_preserve_shape_key_animation_and_drivers(self):
        armature, attached, _no_shapes, _unrelated = self._create_fixture()
        shape_keys = attached[0].data.shape_keys
        animated = attached[0].shape_key_add(name="Animated")
        driven = attached[0].shape_key_add(name="Driven")

        animated.value = 0.2
        animated.keyframe_insert(data_path="value", frame=1.0)
        animated.value = 0.8
        animated.keyframe_insert(data_path="value", frame=10.0)
        driver_curve = driven.driver_add("value")
        driver_curve.driver.expression = "0.33"
        bpy.context.scene.frame_set(1)
        bpy.context.view_layer.update()

        action = shape_keys.animation_data.action
        action_pointer = action.as_pointer()
        driver_pointer = driver_curve.as_pointer()
        animated_value = animated.value
        driven_value = driven.value

        self.assertEqual(
            {"FINISHED"},
            invoke_operator("cats_manual.start_pose_mode_no_shapekey_reset"),
        )
        self.assertEqual(
            {"FINISHED"},
            invoke_operator("cats_manual.stop_pose_mode_no_shapekey_reset"),
        )

        self.assertEqual(action_pointer, shape_keys.animation_data.action.as_pointer())
        self.assertEqual(driver_pointer, driver_curve.as_pointer())
        self.assertEqual("0.33", driver_curve.driver.expression)
        self.assertAlmostEqual(animated_value, animated.value)
        self.assertAlmostEqual(driven_value, driven.value)

    def test_quick_access_draws_three_ordered_pose_controls(self):
        class RecordingLayout:
            def __init__(self):
                self.operator_ids = []
                self.scale_y = 1.0

            def row(self, **_kwargs):
                return self

            def split(self, **_kwargs):
                return self

            def column(self, **_kwargs):
                return self

            def separator(self):
                return None

            def operator(self, operator_id, **_kwargs):
                self.operator_ids.append(operator_id)
                return None

        armature, _attached, _no_shapes, _unrelated = self._create_fixture()
        start_layout = RecordingLayout()
        self.quickaccess.QuickAccessPanel.draw_pose_section(
            object(), start_layout, bpy.context
        )
        self.assertEqual(
            [
                "cats_manual.start_pose_mode",
                "cats_manual.start_pose_mode_no_shapekey_reset",
                "cats_manual.start_pose_mode_no_reset",
            ],
            start_layout.operator_ids[:3],
        )

        bpy.ops.object.mode_set(mode="POSE")
        stop_layout = RecordingLayout()
        self.quickaccess.QuickAccessPanel.draw_pose_section(
            object(), stop_layout, bpy.context
        )
        self.assertEqual(
            [
                "cats_manual.stop_pose_mode",
                "cats_manual.stop_pose_mode_no_shapekey_reset",
                "cats_manual.stop_pose_mode_no_reset",
            ],
            stop_layout.operator_ids[:3],
        )

        for idname in (
            "start_pose_mode_no_shapekey_reset",
            "stop_pose_mode_no_shapekey_reset",
        ):
            description = getattr(bpy.ops.cats_manual, idname).get_rna_type().description
            self.assertIn("without resetting shape keys", description)


def main() -> int:
    result = unittest.TextTestRunner(verbosity=2).run(
        unittest.defaultTestLoader.loadTestsFromTestCase(PoseModeSmokeTests)
    )
    return 0 if result.wasSuccessful() else 1


if __name__ == "__main__":
    raise SystemExit(main())
