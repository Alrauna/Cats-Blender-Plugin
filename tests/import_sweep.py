# GPL License

"""Import every Python module shipped in the installed CATS extension."""

from __future__ import annotations

import importlib
import sys
import unittest
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


class InstalledModuleImportTests(unittest.TestCase):
    def test_every_packaged_python_module_imports(self):
        module_name = cats_module_name()
        package = importlib.import_module(module_name)
        install_root = Path(package.__file__).resolve().parent
        module_names = set()

        for path in install_root.rglob("*.py"):
            relative = path.relative_to(install_root).with_suffix("")
            parts = list(relative.parts)
            if parts[-1] == "__init__":
                parts.pop()
            module_names.add(
                module_name if not parts else module_name + "." + ".".join(parts)
            )

        failures = {}
        for name in sorted(module_names):
            try:
                importlib.import_module(name)
            except Exception as exc:  # Report every failed packaged module together.
                failures[name] = f"{type(exc).__name__}: {exc}"

        self.assertFalse(failures, failures)
        self.assertGreaterEqual(len(module_names), 100)
        print(f"Imported {len(module_names)} installed CATS Python modules")


def main() -> int:
    result = unittest.TextTestRunner(verbosity=2).run(
        unittest.defaultTestLoader.loadTestsFromTestCase(InstalledModuleImportTests)
    )
    return 0 if result.wasSuccessful() else 1


if __name__ == "__main__":
    raise SystemExit(main())
