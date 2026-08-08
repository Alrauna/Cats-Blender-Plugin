# GPL License

"""Verify the CATS Overdraw Prevention integration helpers in Blender 5.2."""

from __future__ import annotations

import importlib
import json
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


class StubApiState:
    def __init__(self, last_status_json):
        self.last_status_json = last_status_json


class StubNamed:
    def __init__(self, name_full):
        self.name_full = name_full


class StubOverride:
    def __init__(self, material, image=None, image_channel="RED",
                 uv_map_name="UVMap", address_mode="CLIP"):
        self.material = material
        self.image = image
        self.image_channel = image_channel
        self.uv_map_name = uv_map_name
        self.address_mode = address_mode


class StubSettings:
    def __init__(self, overrides=(), **tuning):
        self.material_overrides = list(overrides)
        for key, value in tuning.items():
            setattr(self, key, value)


class StubOperatorProperties:
    pass


class OverdrawHelperTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.overdraw = importlib.import_module(cats_module_name() + ".tools.overdraw")

    def test_separator_is_absent_in_this_profile(self):
        self.assertFalse(self.overdraw.is_available())

    def test_read_status_returns_payload_dict(self):
        payload = {"api_version": "1.2", "code": "ANALYSIS_COMPLETE", "message": "Done"}
        self.assertEqual(
            payload, self.overdraw.read_status(StubApiState(json.dumps(payload)))
        )

    def test_read_status_returns_none_for_unusable_input(self):
        for raw in ("", "{", "not json", "[]", "null", '"text"', None):
            with self.subTest(raw=raw):
                self.assertIsNone(self.overdraw.read_status(StubApiState(raw)))

    def test_read_status_returns_none_when_property_absent(self):
        self.assertIsNone(self.overdraw.read_status(object()))
        self.assertIsNone(self.overdraw.read_status(None))

    def test_status_message_returns_message(self):
        raw = json.dumps({"code": "ANALYSIS_COMPLETE", "message": "3 materials"})
        self.assertEqual("3 materials", self.overdraw.status_message(StubApiState(raw)))

    def test_status_message_suppresses_unqueried_and_blank(self):
        cases = (
            {"code": "NOT_QUERIED", "message": "nothing yet"},
            {"code": "ANALYSIS_COMPLETE", "message": "   "},
            {"code": "ANALYSIS_COMPLETE"},
            {"message": "no code"},
        )
        for payload in cases:
            with self.subTest(payload=payload):
                self.assertIsNone(
                    self.overdraw.status_message(StubApiState(json.dumps(payload)))
                )

    def test_status_is_actionable_for_stale_codes(self):
        for code in ("RESULT_STALE", "STALE_ANALYSIS"):
            with self.subTest(code=code):
                raw = json.dumps({"code": code, "message": "changed"})
                self.assertTrue(
                    self.overdraw.status_is_actionable(StubApiState(raw))
                )

    def test_status_is_not_actionable_for_normal_codes(self):
        for code in ("ANALYSIS_COMPLETE", "ASSIGNMENT_COMPLETE", "CLEARED"):
            with self.subTest(code=code):
                raw = json.dumps({"code": code, "message": "fine"})
                self.assertFalse(
                    self.overdraw.status_is_actionable(StubApiState(raw))
                )

    def test_status_is_not_actionable_without_a_payload(self):
        self.assertFalse(self.overdraw.status_is_actionable(StubApiState("")))
        self.assertFalse(self.overdraw.status_is_actionable(None))

    def test_overrides_json_defaults_to_empty_list(self):
        self.assertEqual("[]", self.overdraw.overrides_json(None))
        self.assertEqual("[]", self.overdraw.overrides_json(StubSettings()))

    def test_overrides_json_mirrors_the_separator_payload(self):
        settings = StubSettings(overrides=[
            StubOverride(StubNamed("Hair"), StubNamed("hair.png")),
            StubOverride(None),
        ])
        self.assertEqual(
            [{
                "address_mode": "CLIP",
                "image_channel": "RED",
                "image_name": "hair.png",
                "material_name": "Hair",
                "uv_map_name": "UVMap",
            }],
            json.loads(self.overdraw.overrides_json(settings)),
        )

    def test_overrides_json_forces_alpha_channel_without_an_image(self):
        settings = StubSettings(overrides=[StubOverride(StubNamed("Lace"))])
        entry = json.loads(self.overdraw.overrides_json(settings))[0]
        self.assertEqual("ALPHA", entry["image_channel"])
        self.assertEqual("", entry["image_name"])

    def test_configure_analysis_sets_api_major_and_overrides(self):
        props = StubOperatorProperties()
        self.overdraw.configure_analysis(props, None)
        self.assertEqual(1, props.api_major)
        self.assertEqual("[]", props.material_overrides_json)

    def test_configure_analysis_copies_tuning_settings(self):
        settings = StubSettings(
            address_mode="MIRROR", alpha_threshold=0.5, min_affected_texels=4,
            min_affected_fraction=0.25, margin_texels=2, max_scanlines=1234,
            max_run_emissions=99,
        )
        props = StubOperatorProperties()
        self.overdraw.configure_analysis(props, settings)
        self.assertEqual("MIRROR", props.address_mode)
        self.assertEqual(0.5, props.alpha_threshold)
        self.assertEqual(4, props.min_affected_texels)
        self.assertEqual(0.25, props.min_affected_fraction)
        self.assertEqual(2, props.margin_texels)
        self.assertEqual(1234, props.max_scanlines)
        self.assertEqual(99, props.max_run_emissions)

    def test_configure_analysis_skips_settings_it_cannot_read(self):
        props = StubOperatorProperties()
        self.overdraw.configure_analysis(props, StubSettings(alpha_threshold=0.75))
        self.assertEqual(0.75, props.alpha_threshold)
        self.assertFalse(hasattr(props, "address_mode"))


class OverdrawOperatorTests(unittest.TestCase):
    def test_cats_overdraw_operators_are_registered(self):
        for name in ("download_separator", "help"):
            with self.subTest(operator=name):
                self.assertTrue(hasattr(bpy.ops.cats_overdraw, name))
                self.assertIsNotNone(
                    getattr(bpy.ops.cats_overdraw, name).get_rna_type()
                )

    def test_operator_urls_point_at_the_separator_repository(self):
        translations = importlib.import_module(
            cats_module_name() + ".tools.translations"
        )
        for key in ("DownloadSeparatorButton.URL", "OverdrawHelpButton.URL"):
            with self.subTest(key=key):
                self.assertIn(
                    "github.com/Alrauna/blender-alpha-material-separator",
                    translations.t(key),
                )


def main() -> int:
    loader = unittest.defaultTestLoader
    suite = unittest.TestSuite([
        loader.loadTestsFromTestCase(OverdrawHelperTests),
        loader.loadTestsFromTestCase(OverdrawOperatorTests),
    ])
    result = unittest.TextTestRunner(verbosity=2).run(suite)
    return 0 if result.wasSuccessful() else 1


if __name__ == "__main__":
    raise SystemExit(main())
