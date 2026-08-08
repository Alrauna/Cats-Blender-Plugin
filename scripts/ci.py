#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-3.0-or-later

"""Security-sensitive helpers used by CATS GitHub Actions."""

from __future__ import annotations

import hashlib
import re
import tomllib
from pathlib import Path


SHA256_PATTERN = re.compile(r"[0-9a-f]{64}\Z")
VERSION_PATTERN = re.compile(r"[0-9]+\.[0-9]+\.[0-9]+\Z")


def sha256_file(path: Path) -> str:
    with path.open("rb") as stream:
        return hashlib.file_digest(stream, "sha256").hexdigest()


def parse_checksum_manifest(payload: bytes) -> dict[str, str]:
    result: dict[str, str] = {}
    for line in payload.decode("utf-8").splitlines():
        if not line.strip():
            continue
        parts = line.split()
        if len(parts) != 2 or not SHA256_PATTERN.fullmatch(parts[0].lower()):
            raise ValueError(f"malformed checksum row: {line!r}")
        digest, filename = parts[0].lower(), parts[1].removeprefix("*")
        if filename in result:
            raise ValueError(f"duplicate checksum entry: {filename}")
        result[filename] = digest
    if not result:
        raise ValueError("empty checksum manifest")
    return result


def require_checksum_consensus(
    payloads: tuple[bytes, bytes, bytes],
    filename: str,
    expected_sha256: str,
) -> None:
    if len(set(payloads)) != 1:
        raise ValueError("resolver checksum payloads disagree")
    published = parse_checksum_manifest(payloads[0]).get(filename)
    if published is None:
        raise ValueError(f"checksum entry is missing: {filename}")
    if published != expected_sha256:
        raise ValueError("official checksum disagrees with committed checksum")


def write_github_output(path: Path | None, **values: str | Path) -> None:
    if path is None:
        return
    with path.open("a", encoding="utf-8", newline="\n") as stream:
        for key, value in values.items():
            text = str(value)
            if "\n" in text or "\r" in text:
                raise ValueError(f"GitHub output must be single-line: {key}")
            stream.write(f"{key}={text}\n")


def release_identity(version: str, manifest: Path) -> tuple[str, str]:
    if not VERSION_PATTERN.fullmatch(version):
        raise ValueError(f"release version must use X.Y.Z: {version!r}")
    data = tomllib.loads(manifest.read_text(encoding="utf-8"))
    if data["version"] != version:
        raise ValueError(
            f"manifest version {data['version']!r} does not match {version!r}"
        )
    return f"v{version}", f"{data['id']}-{version}.zip"


def write_sha256s(archive: Path, output: Path) -> str:
    digest = sha256_file(archive)
    output.write_text(
        f"{digest}  {archive.name}\n", encoding="utf-8", newline="\n"
    )
    return digest


def require_file_sha256(path: Path, expected_sha256: str) -> None:
    if not SHA256_PATTERN.fullmatch(expected_sha256):
        raise ValueError("expected SHA-256 is malformed")
    actual = sha256_file(path)
    if actual != expected_sha256:
        raise ValueError(
            f"file SHA-256 mismatch: expected {expected_sha256}, got {actual}"
        )
