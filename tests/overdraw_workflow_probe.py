# GPL License

"""Prove CATS mirrors the separator's own Preview and Apply gating.

Skipped when the separator is absent, so the CATS-only CI profile stays green.
Run it in a profile with Alpha Material Separator 1.3.0 or newer installed to
exercise the integration for real.

Regression cover for the defect where CATS read only last_status_code: the
separator's depsgraph path publishes no status, so a stale-looking success text
stayed on screen while Preview silently returned CANCELLED.
"""

from __future__ import annotations

import importlib
import os
import sys
import unittest

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


def enable_separator() -> None:
    """Enable the separator extension if it is installed but not enabled.

    A test profile only has to have the separator installed; which repository it
    came from decides its module path, so every configured repository is tried.
    """
    for repo in bpy.context.preferences.extensions.repos:
        directory = repo.directory
        if not directory or not os.path.isdir(
            os.path.join(directory, "alpha_material_separator")
        ):
            continue
        bpy.ops.preferences.addon_enable(
            module=f"bl_ext.{repo.module}.alpha_material_separator"
        )
        return


class ShimOperatorProperties:
    """Stands in for the property group layout.operator() returns."""

    def __init__(self):
        self._values = {}

    def __setattr__(self, name, value):
        if name.startswith("_"):
            super().__setattr__(name, value)
        else:
            self._values[name] = value

    def kwargs(self):
        return dict(self._values)


def build_alpha_scene():
    """One grid with a half-transparent image driving Principled Alpha."""
    for obj in list(bpy.data.objects):
        bpy.data.objects.remove(obj)

    image = bpy.data.images.new("overdraw_probe", 64, 64, alpha=True)
    pixels = []
    for _row in range(64):
        for column in range(64):
            pixels.extend((1.0, 1.0, 1.0, 0.0 if column < 32 else 1.0))
    image.pixels[:] = pixels

    material = bpy.data.materials.new("overdraw_probe_mat")
    material.use_nodes = True
    material.blend_method = "BLEND"
    nodes = material.node_tree.nodes
    texture = nodes.new("ShaderNodeTexImage")
    texture.image = image
    material.node_tree.links.new(
        texture.outputs["Alpha"], nodes["Principled BSDF"].inputs["Alpha"]
    )

    bpy.ops.mesh.primitive_grid_add(x_subdivisions=2, y_subdivisions=2)
    obj = bpy.context.active_object
    obj.data.materials.append(material)
    bpy.ops.object.mode_set(mode="OBJECT")
    bpy.ops.object.select_all(action="DESELECT")
    obj.select_set(True)
    bpy.context.view_layer.objects.active = obj
    return obj


class OverdrawWorkflowGatingTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.overdraw = importlib.import_module(cats_module_name() + ".tools.overdraw")
        if not cls.overdraw.is_available():
            enable_separator()
        if not cls.overdraw.is_available():
            raise unittest.SkipTest("Alpha Material Separator is not installed")
        cls.window_manager = bpy.context.window_manager
        cls.api_state = getattr(
            cls.window_manager, cls.overdraw.SEPARATOR_API_PROPERTY
        )
        cls.settings = getattr(
            cls.window_manager, cls.overdraw.SEPARATOR_SETTINGS_PROPERTY
        )

    def setUp(self):
        self.obj = build_alpha_scene()

    def analyze(self):
        props = ShimOperatorProperties()
        self.overdraw.configure_analysis(props, self.settings)
        self.assertEqual(
            {"FINISHED"}, bpy.ops.alpha_material_separator.analyze(**props.kwargs())
        )

    def view(self):
        state = self.overdraw.workflow_state(self.api_state)
        self.assertIsNotNone(
            state, "separator 1.3.0 or newer must publish workflow_json"
        )
        return state

    def test_the_installed_separator_meets_the_minimum_api(self):
        self.assertEqual((1, 3), self.overdraw.api_version(self.api_state)[:2])
        self.assertTrue(self.overdraw.meets_minimum_api(self.api_state))

    def test_preview_and_apply_are_gated_off_before_any_analysis(self):
        bpy.ops.alpha_material_separator.clear_results()
        view = self.view()
        self.assertFalse(view["can_preview"])
        self.assertFalse(view["can_apply"])
        self.assertEqual("", view["analysis_id"])

    def test_preview_and_apply_open_after_analysis(self):
        self.analyze()
        view = self.view()
        self.assertTrue(view["can_preview"])
        self.assertTrue(view["can_apply"])
        self.assertFalse(view["stale"])
        self.assertNotEqual("", view["analysis_id"])

    def test_a_settings_change_closes_preview_and_reports_stale(self):
        self.analyze()
        original = self.settings.alpha_threshold
        try:
            self.settings.alpha_threshold = 0.5
            view = self.view()
            self.assertTrue(view["stale"])
            self.assertFalse(view["can_preview"])
            self.assertFalse(view["can_apply"])
            self.assertTrue(self.overdraw.status_message(self.api_state))
        finally:
            self.settings.alpha_threshold = original

    def test_a_mesh_edit_does_not_falsely_close_preview(self):
        """The depsgraph path publishes no status and is not proof of staleness.

        The separator resolves RECHECK_PENDING on the next action, so CATS must
        not hide Preview here or a mode switch would blank the panel.
        """
        self.analyze()
        self.obj.data.vertices[0].co.x += 0.25
        self.obj.data.update()
        bpy.context.view_layer.update()
        view = self.view()
        self.assertEqual("RECHECK_PENDING", view["validation_state"])
        self.assertTrue(view["can_preview"])


if __name__ == "__main__":
    runner = unittest.TextTestRunner(verbosity=2)
    result = runner.run(
        unittest.defaultTestLoader.loadTestsFromTestCase(
            OverdrawWorkflowGatingTests
        )
    )
    sys.exit(0 if result.wasSuccessful() else 1)
