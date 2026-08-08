#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-3.0-or-later

"""Security-sensitive helpers used by CATS GitHub Actions."""

from __future__ import annotations

import argparse
import hashlib
import ipaddress
import plistlib
import re
import secrets
import shutil
import socket
import ssl
import struct
import subprocess
import tomllib
from pathlib import Path
from urllib.parse import urlparse


SHA256_PATTERN = re.compile(r"[0-9a-f]{64}\Z")
VERSION_PATTERN = re.compile(r"[0-9]+\.[0-9]+\.[0-9]+\Z")
BLENDER_VERSION = "5.2.0"
BLENDER_SERIES = "5.2"
BASE_URL = "https://download.blender.org/release/Blender5.2"
CHECKSUM_URL = f"{BASE_URL}/blender-{BLENDER_VERSION}.sha256"
CLOUDFLARE_DOH_URL = "https://cloudflare-dns.com/dns-query"
QUAD9_DOT_HOST = "dns.quad9.net"
QUAD9_DOT_PORT = 853
MAX_RESOLVED_ADDRESSES = 16
CONNECT_TIMEOUT_SECONDS = 30
TOTAL_TIMEOUT_SECONDS = 900
PROCESS_TIMEOUT_SECONDS = 960
RETRIES = 2
PLATFORMS = {
    "windows": {
        "filename": "blender-5.2.0-windows-x64.zip",
        "sha256": (
            "2d184b626c001692c362291911293b6a"
            "297179d618d95e9e9192c3a80318adc4"
        ),
        "root": "blender-5.2.0-windows-x64",
        "executable": "blender.exe",
        "python_dir": "5.2/python/bin",
        "python_glob": "python.exe",
    },
    "linux": {
        "filename": "blender-5.2.0-linux-x64.tar.xz",
        "sha256": (
            "96f6c181a30f4950607839dc84d42a35"
            "4b250d8a0231b098b59b7bc69c351c48"
        ),
        "root": "blender-5.2.0-linux-x64",
        "executable": "blender",
        "python_dir": "5.2/python/bin",
        "python_glob": "python3.*",
    },
    "macos": {
        "filename": "blender-5.2.0-macos-arm64.dmg",
        "sha256": (
            "ed4d8390166dec5ea0a2813a03db6221"
            "f206ce016442be7f59f41d760972568a"
        ),
        "root": "Blender.app",
        "executable": "Contents/MacOS/Blender",
        "python_dir": "Contents/Resources/5.2/python/bin",
        "python_glob": "python3.*",
    },
}


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


def _read_exact(stream: object, size: int) -> bytes:
    result = bytearray()
    while len(result) < size:
        chunk = stream.recv(size - len(result))  # type: ignore[attr-defined]
        if not chunk:
            raise ValueError("truncated DNS-over-TLS response")
        result.extend(chunk)
    return bytes(result)


def _decode_dns_name(
    message: bytes,
    offset: int,
    known_label_offsets: set[int],
) -> tuple[tuple[bytes, ...], int, set[int]]:
    labels: list[bytes] = []
    observed_offsets: set[int] = set()
    cursor = offset
    next_offset: int | None = None
    expanded_size = 1
    while True:
        if cursor >= len(message):
            raise ValueError("truncated DNS name")
        length = message[cursor]
        encoding = length & 0xC0
        if encoding == 0xC0:
            if cursor + 2 > len(message):
                raise ValueError("truncated DNS name pointer")
            pointer = ((length & 0x3F) << 8) | message[cursor + 1]
            if pointer not in known_label_offsets:
                raise ValueError("invalid DNS name pointer")
            if next_offset is None:
                next_offset = cursor + 2
            cursor = pointer
            continue
        if encoding:
            raise ValueError("invalid DNS label encoding")
        observed_offsets.add(cursor)
        cursor += 1
        if length == 0:
            if next_offset is None:
                next_offset = cursor
            return tuple(labels), next_offset, observed_offsets
        if length > 63 or cursor + length > len(message):
            raise ValueError("invalid DNS name")
        expanded_size += length + 1
        if expanded_size > 255:
            raise ValueError("DNS name exceeds 255 bytes")
        labels.append(message[cursor : cursor + length].lower())
        cursor += length


def _parse_dns_a_response(
    message: bytes,
    transaction_id: int,
    expected_question: bytes,
) -> tuple[str, ...]:
    if len(message) < 12:
        raise ValueError("truncated DNS response")
    response_id, flags, questions, answers, _, _ = struct.unpack(
        "!HHHHHH", message[:12]
    )
    if (
        response_id != transaction_id
        or not flags & 0x8000
        or flags & 0x7A0F
        or questions != 1
    ):
        raise ValueError("invalid DNS response")
    offset = 12 + len(expected_question)
    if message[12:offset] != expected_question:
        raise ValueError("DNS response question mismatch")
    question_name, question_end, known_label_offsets = _decode_dns_name(
        message, 12, set()
    )
    if (
        question_end + 4 != offset
        or message[question_end:offset] != struct.pack("!HH", 1, 1)
    ):
        raise ValueError("invalid DNS response question")
    addresses: list[str] = []
    for _ in range(answers):
        owner, offset, owner_offsets = _decode_dns_name(
            message, offset, known_label_offsets
        )
        if offset + 10 > len(message):
            raise ValueError("truncated DNS record")
        record_type, record_class, _, length = struct.unpack(
            "!HHIH", message[offset : offset + 10]
        )
        offset += 10
        data = message[offset : offset + length]
        if len(data) != length:
            raise ValueError("truncated DNS record data")
        offset += length
        if record_type == 1 and record_class == 1 and length == 4:
            if owner != question_name:
                raise ValueError("DNS answer owner mismatch")
            address = str(ipaddress.IPv4Address(data))
            if address not in addresses:
                if len(addresses) >= MAX_RESOLVED_ADDRESSES:
                    raise ValueError("DNS address budget exceeded")
                addresses.append(address)
            known_label_offsets.update(owner_offsets)
    if not addresses:
        raise ValueError("Quad9 returned no IPv4 address")
    return tuple(addresses)


def quad9_addresses(hostname: str) -> tuple[str, ...]:
    labels = hostname.encode("idna").split(b".")
    if any(not label or len(label) > 63 for label in labels):
        raise ValueError("invalid DNS hostname")
    transaction_id = secrets.randbits(16)
    question = (
        b"".join(bytes((len(label),)) + label for label in labels)
        + b"\0"
        + struct.pack("!HH", 1, 1)
    )
    message = (
        struct.pack("!HHHHHH", transaction_id, 0x0100, 1, 0, 0, 0)
        + question
    )
    context = ssl.create_default_context()
    context.minimum_version = ssl.TLSVersion.TLSv1_2
    with socket.create_connection(
        (QUAD9_DOT_HOST, QUAD9_DOT_PORT), timeout=CONNECT_TIMEOUT_SECONDS
    ) as raw:
        with context.wrap_socket(raw, server_hostname=QUAD9_DOT_HOST) as tls:
            tls.sendall(struct.pack("!H", len(message)) + message)
            response_size = struct.unpack("!H", _read_exact(tls, 2))[0]
            response = _read_exact(tls, response_size)
    return _parse_dns_a_response(response, transaction_id, question)


def curl_command(
    url: str,
    output: Path,
    doh_url: str | None = None,
    resolved_addresses: tuple[str, ...] | None = None,
) -> list[str]:
    parsed = urlparse(url)
    if parsed.scheme != "https":
        raise ValueError("HTTPS is required")
    if doh_url and resolved_addresses is not None:
        raise ValueError("choose DNS-over-HTTPS or a resolved address")
    command = [
        "curl",
        "--proto",
        "=https",
        "--tlsv1.2",
        "--fail",
        "--silent",
        "--show-error",
        "--connect-timeout",
        str(CONNECT_TIMEOUT_SECONDS),
        "--max-time",
        str(TOTAL_TIMEOUT_SECONDS),
        "--retry",
        str(RETRIES),
        "--retry-delay",
        "2",
        "--retry-max-time",
        str(TOTAL_TIMEOUT_SECONDS),
        "--retry-all-errors",
        "--output",
        str(output),
        "--write-out",
        "%{http_code}",
    ]
    if doh_url:
        if urlparse(doh_url).scheme != "https":
            raise ValueError("DNS-over-HTTPS requires HTTPS")
        command.extend(("--doh-url", doh_url))
    if resolved_addresses is not None:
        if (
            not resolved_addresses
            or len(resolved_addresses) > MAX_RESOLVED_ADDRESSES
            or parsed.hostname is None
        ):
            raise ValueError("resolved addresses require a hostname")
        addresses = ",".join(
            str(ipaddress.IPv4Address(address)) for address in resolved_addresses
        )
        command.extend(("--resolve", f"{parsed.hostname}:443:{addresses}"))
    return [*command, url]


def download(
    url: str,
    output: Path,
    doh_url: str | None = None,
    resolved_addresses: tuple[str, ...] | None = None,
) -> None:
    try:
        result = subprocess.run(
            curl_command(url, output, doh_url, resolved_addresses),
            check=False,
            capture_output=True,
            text=True,
            timeout=PROCESS_TIMEOUT_SECONDS,
        )
    except subprocess.TimeoutExpired as error:
        output.unlink(missing_ok=True)
        raise RuntimeError(f"download timed out: {url}") from error
    if result.returncode or result.stdout.strip() != "200":
        output.unlink(missing_ok=True)
        raise RuntimeError(
            f"download failed: curl={result.returncode} "
            f"http={result.stdout.strip()!r} {result.stderr.strip()}"
        )


def _extract_dmg(archive: Path, destination: Path, root: str) -> None:
    attached = subprocess.run(
        ["hdiutil", "attach", "-nobrowse", "-readonly", "-plist", str(archive)],
        check=True,
        capture_output=True,
    )
    entities = plistlib.loads(attached.stdout)["system-entities"]
    mount_points = [
        entity["mount-point"] for entity in entities if entity.get("mount-point")
    ]
    if len(mount_points) != 1:
        for mount_point in mount_points:
            subprocess.run(
                ["hdiutil", "detach", mount_point, "-quiet"], check=False
            )
        raise ValueError(f"expected one mount point, got {mount_points}")
    mount = Path(mount_points[0])
    try:
        source = mount / root
        if not source.is_dir():
            raise ValueError(f"{root} not found in the disk image")
        shutil.copytree(source, destination / root, symlinks=True)
    finally:
        subprocess.run(["hdiutil", "detach", str(mount), "-quiet"], check=False)


def extract_archive(platform: str, archive: Path, destination: Path) -> None:
    metadata = PLATFORMS[platform]
    if platform == "macos":
        _extract_dmg(archive, destination, metadata["root"])
    elif platform == "linux":
        shutil.unpack_archive(archive, destination, filter="data")
    else:
        shutil.unpack_archive(archive, destination)


def locate_blender_and_python(
    platform: str, extracted: Path
) -> tuple[Path, Path]:
    metadata = PLATFORMS[platform]
    root = extracted / metadata["root"]
    blender = (root / metadata["executable"]).resolve()
    if not blender.is_file():
        raise ValueError(f"expected Blender executable at {blender}")
    python_matches = [
        path.resolve()
        for path in (root / metadata["python_dir"]).glob(metadata["python_glob"])
        if path.is_file() and "config" not in path.name
    ]
    if not python_matches:
        raise ValueError("bundled Python executable was not found")
    python = min(python_matches, key=lambda path: len(path.name))
    return blender, python


def require_blender_version(version: str) -> None:
    if version != f"Blender {BLENDER_VERSION} LTS":
        raise ValueError(f"unexpected Blender version: {version!r}")


def prepare_blender(
    platform: str,
    output_dir: Path,
    github_output: Path | None = None,
) -> tuple[Path, Path]:
    metadata = PLATFORMS[platform]
    output_dir.mkdir(parents=True, exist_ok=False)
    checksum_paths = tuple(
        output_dir / f"checksums-{index}.txt" for index in range(3)
    )
    download(CHECKSUM_URL, checksum_paths[0])
    download(CHECKSUM_URL, checksum_paths[1], doh_url=CLOUDFLARE_DOH_URL)
    download(
        CHECKSUM_URL,
        checksum_paths[2],
        resolved_addresses=quad9_addresses("download.blender.org"),
    )
    payloads = tuple(path.read_bytes() for path in checksum_paths)
    require_checksum_consensus(payloads, metadata["filename"], metadata["sha256"])
    archive = output_dir / metadata["filename"]
    download(f"{BASE_URL}/{metadata['filename']}", archive)
    require_file_sha256(archive, metadata["sha256"])
    extracted = output_dir / "blender"
    extract_archive(platform, archive, extracted)
    blender, python = locate_blender_and_python(platform, extracted)
    reported = subprocess.run(
        [str(blender), "--version"],
        check=True,
        capture_output=True,
        text=True,
    ).stdout.splitlines()[0].strip()
    require_blender_version(reported)
    write_github_output(github_output, blender=blender, python=python)
    return blender, python


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    subparsers = parser.add_subparsers(dest="command", required=True)
    prepare = subparsers.add_parser("prepare-blender")
    prepare.add_argument("--platform", choices=tuple(PLATFORMS), required=True)
    prepare.add_argument("--output-dir", type=Path, required=True)
    prepare.add_argument("--github-output", type=Path)

    check_release = subparsers.add_parser("check-release")
    check_release.add_argument("--version", required=True)
    check_release.add_argument("--manifest", type=Path, required=True)

    prepare_release = subparsers.add_parser("prepare-release")
    prepare_release.add_argument("--version", required=True)
    prepare_release.add_argument("--manifest", type=Path, required=True)
    prepare_release.add_argument("--archive", type=Path, required=True)
    prepare_release.add_argument("--checksum-output", type=Path, required=True)
    prepare_release.add_argument("--github-output", type=Path, required=True)

    verify_file = subparsers.add_parser("verify-file")
    verify_file.add_argument("--file", type=Path, required=True)
    verify_file.add_argument("--expected-sha256", required=True)
    return parser


def main(argv: list[str] | None = None) -> int:
    arguments = _parser().parse_args(argv)
    if arguments.command == "prepare-blender":
        prepare_blender(
            arguments.platform, arguments.output_dir, arguments.github_output
        )
    elif arguments.command == "check-release":
        release_identity(arguments.version, arguments.manifest)
    elif arguments.command == "prepare-release":
        tag, archive_name = release_identity(arguments.version, arguments.manifest)
        if arguments.archive.name != archive_name:
            raise ValueError(f"release archive must be named {archive_name!r}")
        digest = write_sha256s(arguments.archive, arguments.checksum_output)
        write_github_output(
            arguments.github_output,
            tag=tag,
            archive_name=archive_name,
            sha256=digest,
        )
    elif arguments.command == "verify-file":
        require_file_sha256(arguments.file, arguments.expected_sha256)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
