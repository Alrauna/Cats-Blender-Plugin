#!/usr/bin/env python3
# GPL License

"""Verify the structure and source fidelity of a built Blender extension ZIP."""

from __future__ import annotations

import argparse
import stat
import tomllib
import warnings
import zipfile
from pathlib import Path, PurePosixPath


TARGET_BLENDER_VERSION = (5, 2, 0)
FORBIDDEN_PARTS = {".git", ".github", "__pycache__"}
FORBIDDEN_SUFFIXES = {".blend1", ".part", ".pyc", ".pyo", ".tmp"}


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("package", type=Path, help="extension ZIP produced by Blender")
    parser.add_argument(
        "--source-dir",
        type=Path,
        default=Path.cwd(),
        help="source directory containing blender_manifest.toml",
    )
    return parser.parse_args()


def version_tuple(value: str) -> tuple[int, int, int]:
    parts = value.split(".")
    if not 1 <= len(parts) <= 3 or any(not part.isdigit() for part in parts):
        raise AssertionError(f"Invalid Blender version in manifest: {value!r}")
    return tuple(int(part) for part in (parts + ["0", "0"])[:3])


def archive_prefix(file_names: list[str]) -> str:
    manifests = [
        name
        for name in file_names
        if PurePosixPath(name).name == "blender_manifest.toml"
    ]
    assert len(manifests) == 1, (
        "Package must contain exactly one blender_manifest.toml; "
        f"found {manifests!r}"
    )
    manifest_path = PurePosixPath(manifests[0])
    assert len(manifest_path.parts) <= 2, (
        "Manifest must be at archive root or inside one wrapper directory: "
        f"{manifest_path}"
    )
    return "" if len(manifest_path.parts) == 1 else manifest_path.parts[0] + "/"


def validate_member_paths(infos: list[zipfile.ZipInfo]) -> list[str]:
    file_names: list[str] = []
    casefolded: set[str] = set()

    for info in infos:
        name = info.filename
        assert "\\" not in name, f"Archive path uses a backslash: {name!r}"
        path = PurePosixPath(name)
        assert not path.is_absolute(), f"Archive path is absolute: {name!r}"
        assert ".." not in path.parts, f"Archive path traverses upward: {name!r}"
        assert not (set(path.parts) & FORBIDDEN_PARTS), f"Forbidden build artifact: {name!r}"
        assert path.suffix.lower() not in FORBIDDEN_SUFFIXES, f"Forbidden build artifact: {name!r}"
        assert not (info.flag_bits & 0x1), f"Encrypted ZIP member is not allowed: {name!r}"

        unix_mode = (info.external_attr >> 16) & 0xFFFF
        assert stat.S_IFMT(unix_mode) != stat.S_IFLNK, f"Symbolic link is not allowed: {name!r}"

        if info.is_dir():
            continue
        folded = name.casefold()
        assert folded not in casefolded, f"Duplicate or case-colliding archive path: {name!r}"
        casefolded.add(folded)
        file_names.append(name)

    assert file_names, "Package contains no files"
    return file_names


def main() -> int:
    args = parse_args()
    package = args.package.resolve()
    source_dir = args.source_dir.resolve()
    source_manifest_path = source_dir / "blender_manifest.toml"

    assert package.is_file(), f"Package does not exist: {package}"
    assert zipfile.is_zipfile(package), f"Package is not a valid ZIP: {package}"
    assert source_manifest_path.is_file(), f"Source manifest does not exist: {source_manifest_path}"

    with zipfile.ZipFile(package) as archive:
        corrupt_member = archive.testzip()
        assert corrupt_member is None, f"Corrupt ZIP member: {corrupt_member}"

        infos = archive.infolist()
        file_names = validate_member_paths(infos)
        prefix = archive_prefix(file_names)
        assert all(name.startswith(prefix) for name in file_names), (
            "Files exist outside the package wrapper directory"
        )
        packaged_test_files = [
            name
            for name in file_names
            if PurePosixPath(name.removeprefix(prefix)).parts[0] == "tests"
        ]
        assert not packaged_test_files, (
            f"CI-only tests were included in the user package: {packaged_test_files!r}"
        )

        manifest_name = prefix + "blender_manifest.toml"
        init_name = prefix + "__init__.py"
        assert init_name in file_names, f"Package is missing {init_name!r}"

        archived_manifest_bytes = archive.read(manifest_name)
        source_manifest_bytes = source_manifest_path.read_bytes()
        assert archived_manifest_bytes == source_manifest_bytes, (
            "Packaged manifest differs from the source manifest"
        )

        manifest = tomllib.loads(archived_manifest_bytes.decode("utf-8"))
        assert manifest.get("schema_version") == "1.0.0"
        assert manifest.get("type") == "add-on"
        assert manifest.get("id") == "cats_blender_plugin"
        assert isinstance(manifest.get("version"), str) and manifest["version"]

        minimum_version = version_tuple(manifest["blender_version_min"])
        assert minimum_version <= TARGET_BLENDER_VERSION, (
            f"Package requires Blender {minimum_version}, which excludes Blender 5.2"
        )

        python_files = [name for name in file_names if name.endswith(".py")]
        assert python_files, "Package contains no Python files"
        with warnings.catch_warnings(record=True) as compilation_warnings:
            warnings.simplefilter("always", SyntaxWarning)
            for name in python_files:
                compile(archive.read(name), name, "exec")
        syntax_warning_count = sum(
            issubclass(warning.category, SyntaxWarning)
            for warning in compilation_warnings
        )

    print(
        f"Verified {package.name}: {len(file_names)} files, "
        f"{len(python_files)} Python modules, Blender 5.2 compatible manifest"
    )
    if syntax_warning_count:
        print(
            f"Recorded {syntax_warning_count} legacy invalid-escape SyntaxWarnings "
            "without treating them as package errors"
        )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
