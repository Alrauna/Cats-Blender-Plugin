#!/usr/bin/env python3
# GPL License

"""Run CATS integration tests in Blender 5.2.

The extension must already be installed and enabled in the Blender profile used
by the selected executable. CI installs the built extension ZIP into an
isolated profile before invoking this runner.
"""

from __future__ import annotations

import argparse
import fnmatch
import gzip
import glob
import os
import shutil
import subprocess
import sys
import time
import urllib.request
from dataclasses import dataclass
from pathlib import Path


TESTS_DIR = Path(__file__).resolve().parent
REPOSITORY_DIR = TESTS_DIR.parent
BLENDER_FILE_MAGIC = b"BLENDER"
RUN_ONCE = {"atlas.test.py", "extensions.test.py", "syntax.test.py"}


@dataclass(frozen=True)
class TestAsset:
    relative_path: str
    url: str


TEST_ASSETS = (
    TestAsset(
        "armatures/armature.ryuko.blend",
        "https://www.dropbox.com/s/74fj6msbyn3c7rn/armature.ryuko.blend?dl=1",
    ),
    TestAsset(
        "armatures/armature.bonetranslationerror.blend",
        "https://www.dropbox.com/s/ckoseplcfdozpeu/armature.translationerror.blend?dl=1",
    ),
    TestAsset(
        "shapekeys/shapekey.shape_key_to_basis.blend",
        "https://www.dropbox.com/s/d0efnrkauq596ng/ApplyShapeToBasisTest.blend?dl=1",
    ),
)


def read_blender_file_magic(path: Path) -> bytes:
    with path.open("rb") as blend_file:
        magic = blend_file.read(len(BLENDER_FILE_MAGIC))

    if magic.startswith(b"\x1f\x8b"):
        try:
            with gzip.open(path, "rb") as compressed_blend_file:
                return compressed_blend_file.read(len(BLENDER_FILE_MAGIC))
        except OSError:
            return magic
    return magic


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "-b",
        "--blend",
        dest="blender_exec",
        default="blender",
        metavar="BLENDER",
        help="Blender executable whose isolated profile has CATS enabled",
    )
    parser.add_argument(
        "-t",
        "--test",
        dest="test_pattern",
        default="./tests/armatures/*",
        metavar="FILE_OR_PATTERN",
        help='test path or glob; ".test.py" is appended when omitted',
    )
    parser.add_argument(
        "-f",
        "--bfile",
        dest="blend_pattern",
        default="./tests/armatures/armature.*",
        metavar="FILE_OR_PATTERN",
        help='blend-file path or glob; ".blend" is appended when omitted',
    )
    parser.add_argument(
        "--expected-blender-series",
        default="5.2",
        metavar="MAJOR.MINOR",
        help="required Blender series; pass an empty string to disable the check",
    )
    parser.add_argument(
        "--skip-download",
        action="store_true",
        help="do not download missing test blend files",
    )
    parser.add_argument(
        "--download-timeout",
        type=int,
        default=120,
        metavar="SECONDS",
        help="timeout for each test-asset download",
    )
    parser.add_argument(
        "-c",
        "--ci",
        action="store_true",
        help="emit concise non-interactive output",
    )
    parser.add_argument(
        "-v",
        "--verbose",
        action="store_true",
        help="show successful Blender output",
    )
    parser.add_argument(
        "-e",
        "--continue-on-error",
        action="store_true",
        help="run remaining test combinations after a failure",
    )
    parser.add_argument(
        "-p",
        "--pipe-to-stdio",
        action="store_true",
        help="stream Blender output directly instead of capturing it",
    )
    return parser.parse_args()


def with_suffix(pattern: str, suffix: str) -> str:
    return pattern if pattern.endswith(suffix) else pattern + suffix


def resolve_blender_executable(value: str) -> str:
    candidate = Path(value).expanduser()
    if candidate.is_file():
        return str(candidate.resolve())

    resolved = shutil.which(value)
    if resolved:
        return resolved

    raise FileNotFoundError(f"Blender executable not found: {value}")


def verify_blender_version(blender_exec: str, expected_series: str) -> None:
    result = subprocess.run(
        [blender_exec, "--version"],
        check=False,
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
    )
    if result.returncode != 0:
        raise RuntimeError(result.stderr.strip() or "Unable to query Blender version")

    first_line = result.stdout.splitlines()[0] if result.stdout else ""
    print(first_line)
    if expected_series and not first_line.startswith(f"Blender {expected_series}"):
        raise RuntimeError(
            f"Expected Blender {expected_series}.x, but executable reported {first_line!r}"
        )


def download_asset(asset: TestAsset, timeout: int) -> None:
    destination = TESTS_DIR / asset.relative_path
    if destination.is_file():
        if read_blender_file_magic(destination) == BLENDER_FILE_MAGIC:
            return
        raise RuntimeError(f"Existing test asset is not a Blender file: {destination}")

    destination.parent.mkdir(parents=True, exist_ok=True)
    temporary = destination.with_suffix(destination.suffix + ".part")
    request = urllib.request.Request(asset.url, headers={"User-Agent": "CATS-Blender-CI/5.2"})
    print(f"Downloading test asset: {destination.relative_to(REPOSITORY_DIR)}")

    try:
        with urllib.request.urlopen(request, timeout=timeout) as response, temporary.open("wb") as output:
            shutil.copyfileobj(response, output)

        magic = read_blender_file_magic(temporary)
        if magic != BLENDER_FILE_MAGIC:
            raise RuntimeError(
                f"Download did not produce a Blender file (received {magic!r}): {asset.url}"
            )
        temporary.replace(destination)
    finally:
        temporary.unlink(missing_ok=True)


def collect_files(pattern: str, suffix: str) -> list[Path]:
    matches = [Path(path).resolve() for path in sorted(glob.glob(with_suffix(pattern, suffix)))]
    return [path for path in matches if path.is_file()]


def asset_matches_pattern(asset: TestAsset, pattern: str) -> bool:
    asset_path = os.path.normcase(str((TESTS_DIR / asset.relative_path).resolve()))
    absolute_pattern = os.path.normcase(os.path.abspath(with_suffix(pattern, ".blend")))
    return fnmatch.fnmatchcase(asset_path, absolute_pattern)


def blender_command(blender_exec: str, blend_file: Path, test_file: Path) -> list[str]:
    return [
        blender_exec,
        "--background",
        "--offline-mode",
        "-noaudio",
        str(blend_file),
        "--python-exit-code",
        "1",
        "--python",
        str(test_file),
    ]


def run_test(
    command: list[str],
    *,
    pipe_to_stdio: bool,
    verbose: bool,
) -> tuple[int, str, str]:
    if pipe_to_stdio:
        result = subprocess.run(command, check=False)
        return result.returncode, "", ""

    result = subprocess.run(
        command,
        check=False,
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
    )
    if verbose and result.returncode == 0:
        if result.stdout:
            print(result.stdout, end="" if result.stdout.endswith("\n") else "\n")
        if result.stderr:
            print(result.stderr, file=sys.stderr, end="" if result.stderr.endswith("\n") else "\n")
    return result.returncode, result.stdout, result.stderr


def main() -> int:
    args = parse_args()
    start = time.monotonic()

    try:
        blender_exec = resolve_blender_executable(args.blender_exec)
        verify_blender_version(blender_exec, args.expected_blender_series)

        if not args.skip_download:
            for asset in TEST_ASSETS:
                if asset_matches_pattern(asset, args.blend_pattern):
                    download_asset(asset, args.download_timeout)

        blend_files = collect_files(args.blend_pattern, ".blend")
        test_files = collect_files(args.test_pattern, ".test.py")
        if not blend_files:
            raise RuntimeError(f"No blend files matched {with_suffix(args.blend_pattern, '.blend')!r}")
        if not test_files:
            raise RuntimeError(f"No test files matched {with_suffix(args.test_pattern, '.test.py')!r}")
    except (OSError, RuntimeError) as error:
        print(f"ERROR: {error}", file=sys.stderr)
        return 2

    failures = 0
    executed = 0
    already_executed: set[str] = set()

    for blend_file in blend_files:
        for test_file in test_files:
            if test_file.name in RUN_ONCE and test_file.name in already_executed:
                continue
            already_executed.add(test_file.name)
            executed += 1
            unit_start = time.monotonic()

            returncode, stdout, stderr = run_test(
                blender_command(blender_exec, blend_file, test_file),
                pipe_to_stdio=args.pipe_to_stdio,
                verbose=args.verbose,
            )
            duration = time.monotonic() - unit_start
            status = "PASS" if returncode == 0 else "FAIL"
            print(
                f"[{status}] {test_file.name} :: {blend_file.name} "
                f"({duration:.1f}s)"
            )

            if returncode != 0:
                failures += 1
                if stdout:
                    print(stdout, end="" if stdout.endswith("\n") else "\n")
                if stderr:
                    print(stderr, file=sys.stderr, end="" if stderr.endswith("\n") else "\n")
                if not args.continue_on_error:
                    elapsed = time.monotonic() - start
                    print(f"FAILED after {executed} test invocation(s) in {elapsed:.1f}s")
                    return returncode or 1

    elapsed = time.monotonic() - start
    print(f"Completed {executed} test invocation(s) with {failures} failure(s) in {elapsed:.1f}s")
    return 1 if failures else 0


if __name__ == "__main__":
    raise SystemExit(main())
