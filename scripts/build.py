#!/usr/bin/env python3
# SiYuan - https://github.com/siyuan-note/siyuan
# Copyright (c) 2020-present, b3log.org
# SPDX-License-Identifier: AGPL-3.0-or-later
"""Validate the WorkBuddy connector package and build the uploadable zip.

The zip layout is flat: ``connector-meta.json`` must sit at the archive root,
because the WorkBuddy open platform reads the manifest from there and rejects a
package wrapped in an extra directory.

Usage:
    python3 scripts/build.py           # validate, then write dist/siyuan-connector-<version>.zip
    python3 scripts/build.py --check   # validate only, no archive (used by CI)
    python3 scripts/build.py --list    # print the files that would be packed
"""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import sys
import zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
DIST_DIR = ROOT / "dist"

# Files that must live at the archive root, in this order for readability.
MANIFEST_FILES = ("connector-meta.json", "mcp.json", "token-schema.json", "icon.svg")
# Directories copied recursively (skills/<name>/SKILL.md and its assets).
PACKAGE_DIRS = ("skills",)

SERVER_KEY = "siyuan"
PLACEHOLDER_RE = re.compile(r"\$\{([A-Za-z0-9_]+)\}")
SEMVER_RE = re.compile(r"^\d+\.\d+\.\d+$")
HOSTNAME_RE = re.compile(r"^[A-Za-z0-9.-]+$")

# 1980-01-01 is the earliest timestamp a zip entry can carry. A fixed timestamp
# keeps archives byte-identical between builds, so the sha256 is meaningful.
FIXED_TIMESTAMP = (1980, 1, 1, 0, 0, 0)


class Report:
    def __init__(self) -> None:
        self.errors: list[str] = []
        self.warnings: list[str] = []

    def error(self, message: str) -> None:
        self.errors.append(message)

    def warn(self, message: str) -> None:
        self.warnings.append(message)

    def emit(self) -> None:
        for message in self.warnings:
            print(f"warning: {message}")
        for message in self.errors:
            print(f"error: {message}")


def load_json(path: Path, report: Report) -> dict | None:
    try:
        with path.open(encoding="utf-8") as handle:
            return json.load(handle)
    except FileNotFoundError:
        report.error(f"missing {path.relative_to(ROOT).as_posix()}")
    except json.JSONDecodeError as err:
        report.error(f"{path.relative_to(ROOT).as_posix()} is not valid JSON: {err}")
    return None


def iter_package_files() -> list[Path]:
    """Return the files to pack, sorted, as absolute paths."""
    files = [ROOT / name for name in MANIFEST_FILES]
    for dirname in PACKAGE_DIRS:
        base = ROOT / dirname
        if base.is_dir():
            files.extend(sorted(path for path in base.rglob("*") if path.is_file()))
    return files


def collect_placeholders(node: object, found: set[str]) -> None:
    """Collect ``${VAR}`` references from any string inside a JSON structure."""
    if isinstance(node, str):
        found.update(PLACEHOLDER_RE.findall(node))
    elif isinstance(node, dict):
        for value in node.values():
            collect_placeholders(value, found)
    elif isinstance(node, list):
        for value in node:
            collect_placeholders(value, found)


def validate() -> tuple[Report, str | None]:
    report = Report()

    for name in MANIFEST_FILES:
        if not (ROOT / name).is_file():
            report.error(f"missing {name}")

    meta = load_json(ROOT / "connector-meta.json", report)
    mcp = load_json(ROOT / "mcp.json", report)
    schema = load_json(ROOT / "token-schema.json", report)

    version = None
    if meta is not None:
        version = meta.get("version")
        if not isinstance(version, str) or not SEMVER_RE.match(version):
            report.error(f"connector-meta.json version must be x.y.z, got {version!r}")
        if meta.get("type") != "mcp":
            report.error('connector-meta.json type must be "mcp"')
        if meta.get("auth_mode") != "token":
            report.error('connector-meta.json auth_mode must be "token"')
        for key in ("name", "name_en", "description", "description_en"):
            if not meta.get(key):
                report.error(f"connector-meta.json is missing {key}")
        if not SEMVER_RE.match(str(meta.get("minWorkbuddyVersion", ""))):
            report.error("connector-meta.json minWorkbuddyVersion must be x.y.z")

    field_keys: set[str] = set()
    fields: list[dict] = []
    if schema is not None:
        fields = schema.get("fields") or []
        if not isinstance(fields, list) or not fields:
            report.error("token-schema.json must declare a non-empty fields array")
            fields = []
        seen: set[str] = set()
        for field in fields:
            key = field.get("key")
            if not key:
                report.error("token-schema.json has a field without key")
                continue
            if key in seen:
                report.error(f"token-schema.json declares {key} twice")
            seen.add(key)
            field_keys.add(key)
            for required in ("label", "type", "description"):
                if not field.get(required):
                    report.error(f"token-schema.json field {key} is missing {required}")
            if field.get("type") == "text" and not field.get("defaultValue"):
                report.warn(f"token-schema.json field {key} has no defaultValue")
            # Guard the regression fixed in 1.0.3: the client rejects hostname
            # variables that contain a colon, so the host field must never carry
            # the port. The port belongs to its own field.
            if key.endswith("_HOST"):
                default = str(field.get("defaultValue", ""))
                if not HOSTNAME_RE.match(default):
                    report.error(
                        f"token-schema.json field {key} default {default!r} is not a bare "
                        "hostname; put the port in a separate *_PORT field"
                    )
            if key.endswith("_PORT"):
                default = str(field.get("defaultValue", ""))
                if not default.isdigit():
                    report.error(f"token-schema.json field {key} default {default!r} is not a port")
        if not any(field.get("type") == "password" for field in fields):
            report.error("token-schema.json needs a password field for the API token")

    if meta and "auth_mode" in meta and field_keys and not any(k.endswith("TOKEN") for k in field_keys):
        report.warn("no *TOKEN field found in token-schema.json")

    if mcp is not None:
        servers = mcp.get("mcpServers") or {}
        if list(servers) != [SERVER_KEY]:
            report.error(f'mcp.json must declare exactly one server named "{SERVER_KEY}"')
        server = servers.get(SERVER_KEY) or {}
        url = server.get("url", "")
        if not url.startswith("${") or "/mcp" not in url:
            report.error("mcp.json server url must be a ${VAR} template ending in /mcp")
        if server.get("type") not in ("streamableHttp", "streamable-http"):
            report.error('mcp.json server type must be "streamableHttp"')

        used: set[str] = set()
        collect_placeholders(server, used)
        if schema is not None:
            missing = sorted(used - field_keys)
            unused = sorted(field_keys - used)
            if missing:
                report.error(f"mcp.json references variables absent from token-schema.json: {missing}")
            if unused:
                report.warn(f"token-schema.json declares unused variables: {unused}")

    skill = ROOT / "skills" / SERVER_KEY / "SKILL.md"
    if not skill.is_file():
        report.error(f"missing skills/{SERVER_KEY}/SKILL.md")
    else:
        head = skill.read_text(encoding="utf-8").split("---")
        front = head[1] if len(head) > 2 else ""
        for key in ("name:", "description:"):
            if key not in front:
                report.error(f"skills/{SERVER_KEY}/SKILL.md frontmatter is missing {key[:-1]}")

    changelog = ROOT / "CHANGELOG.md"
    if version and changelog.is_file():
        if version not in changelog.read_text(encoding="utf-8"):
            report.warn(f"CHANGELOG.md has no entry for {version}")

    return report, version


def build(version: str) -> Path:
    DIST_DIR.mkdir(exist_ok=True)
    target = DIST_DIR / f"siyuan-connector-{version}.zip"

    files = iter_package_files()
    with zipfile.ZipFile(target, "w", compression=zipfile.ZIP_DEFLATED, compresslevel=9) as archive:
        for path in files:
            arcname = path.relative_to(ROOT).as_posix()
            info = zipfile.ZipInfo(arcname, date_time=FIXED_TIMESTAMP)
            info.compress_type = zipfile.ZIP_DEFLATED
            info.create_system = 3  # unix, so file modes are honoured
            info.external_attr = 0o644 << 16
            archive.writestr(info, path.read_bytes())

    print(f"built {target.relative_to(ROOT).as_posix()} ({target.stat().st_size} bytes)")
    print(f"sha256 {hashlib.sha256(target.read_bytes()).hexdigest()}")
    for path in files:
        print(f"  + {path.relative_to(ROOT).as_posix()}")
    return target


def main() -> int:
    parser = argparse.ArgumentParser(description="Validate and pack the SiYuan WorkBuddy connector.")
    parser.add_argument("--check", action="store_true", help="validate only, do not build the archive")
    parser.add_argument("--list", action="store_true", help="list the files that would be packed")
    args = parser.parse_args()

    if args.list:
        for path in iter_package_files():
            print(path.relative_to(ROOT).as_posix())
        return 0

    report, version = validate()
    report.emit()
    if report.errors:
        print(f"\n{len(report.errors)} error(s); package is not releasable")
        return 1
    print(f"package is valid (version {version})")
    if not args.check:
        build(version)
    return 0


if __name__ == "__main__":
    sys.exit(main())
