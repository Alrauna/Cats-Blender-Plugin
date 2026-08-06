#!/usr/bin/env python3
# GPL License

"""Build, validate, and verify the CATS extension package.

Derives the output name from the manifest and the current commit so a build
cannot be filed under a stale hash or a hand-normalized version string.
"""

from __future__ import annotations

import argparse
import subprocess
import sys
import tomllib
from pathlib import Path


REPOSITORY_DIR = Path(__file__).resolve().parent.parent
OUTPUT_DIR = REPOSITORY_DIR / ".packaged-releases"


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "-b",
        "--blend",
        dest="blender_exec",
        default="blender",
        metavar="BLENDER",
        help="Blender 5.2 executable used to build and validate",
    )
    parser.add_argument(
        "--allow-dirty",
        action="store_true",
        help="build even though tracked files differ from the named commit",
    )
    return parser.parse_args()


def run(command: list[str], *, capture: bool = False) -> str:
    result = subprocess.run(
        command,
        check=False,
        cwd=REPOSITORY_DIR,
        capture_output=capture,
        text=True,
        encoding="utf-8",
        errors="replace",
    )
    if result.returncode != 0:
        if capture and result.stderr:
            print(result.stderr, file=sys.stderr, end="")
        raise SystemExit(f"Command failed ({result.returncode}): {' '.join(command)}")
    return result.stdout.strip() if capture else ""


def main() -> int:
    args = parse_args()

    manifest = tomllib.loads((REPOSITORY_DIR / "blender_manifest.toml").read_text("utf-8"))
    package_id = manifest["id"]
    version = manifest["version"]
    short_hash = run(["git", "rev-parse", "--short", "HEAD"], capture=True)

    # A dirty tree means the ZIP contents do not match the hash in its name.
    dirty = run(["git", "status", "--porcelain", "--untracked-files=no"], capture=True)
    if dirty and not args.allow_dirty:
        raise SystemExit(
            f"Tracked files differ from {short_hash}, so the package name would be "
            f"misleading:\n{dirty}\nCommit, stash, or pass --allow-dirty."
        )

    OUTPUT_DIR.mkdir(exist_ok=True)
    package = OUTPUT_DIR / f"{package_id}-{version}-{short_hash}.zip"
    print(f"id={package_id} version={version} short-hash={short_hash}")
    if dirty:
        print("WARNING: building a dirty tree; the hash in the name is approximate.")

    run([args.blender_exec, "--command", "extension", "validate", str(REPOSITORY_DIR)])
    run([
        args.blender_exec, "--command", "extension", "build",
        "--source-dir", str(REPOSITORY_DIR),
        "--output-filepath", str(package),
    ])
    run([args.blender_exec, "--command", "extension", "validate", str(package)])
    run([
        sys.executable, str(REPOSITORY_DIR / "tests" / "verify_package.py"),
        str(package), "--source-dir", str(REPOSITORY_DIR),
    ])

    print(f"Built and verified {package}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
