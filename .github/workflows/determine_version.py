#!/usr/bin/env python3
from __future__ import annotations

import os
import pathlib
import re
import sys

PYPROJECT_PATH = pathlib.Path("pyproject.toml")


def main() -> int:
    try:
        text = PYPROJECT_PATH.read_text(encoding="utf-8")
    except FileNotFoundError:
        print("::error file=pyproject.toml::pyproject.toml not found", file=sys.stderr)
        return 1

    match = re.search(r'^version\s*=\s*"([^\"]+)"', text, re.MULTILINE)
    if not match:
        print("::error file=pyproject.toml::version not found in pyproject.toml", file=sys.stderr)
        return 1

    base_version = match.group(1)

    github_ref = os.environ.get("GITHUB_REF", "")
    github_ref_name = os.environ.get("GITHUB_REF_NAME", "")
    github_sha = os.environ.get("GITHUB_SHA", "")
    github_run_number = os.environ.get("GITHUB_RUN_NUMBER", "")

    if github_ref.startswith("refs/tags/"):
        tag_version = github_ref_name[1:] if github_ref_name.startswith("v") else github_ref_name
        package_version = tag_version
    else:
        short_sha = github_sha[:7]
        package_version = f"{base_version}.dev{github_run_number}+git.{short_sha}"

    print(f"::notice::Using package version: {package_version}", file=sys.stderr)
    print(f"package_version={package_version}")
    print(f"base_version={base_version}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
