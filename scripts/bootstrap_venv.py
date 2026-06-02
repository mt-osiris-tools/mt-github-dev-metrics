#!/usr/bin/env python3
from __future__ import annotations

import argparse
import subprocess
import sys
import sysconfig
from pathlib import Path

import tomllib


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Install dependencies into a venv and link the project via .pth."
    )
    parser.add_argument(
        "--project-root",
        type=Path,
        default=Path.cwd(),
        help="Path to the repository root.",
    )
    parser.add_argument(
        "--with",
        dest="extras",
        action="append",
        default=[],
        help="Optional dependency group from pyproject.toml to install.",
    )
    return parser.parse_args()


def load_dependencies(project_root: Path, extras: list[str]) -> list[str]:
    pyproject_path = project_root / "pyproject.toml"
    pyproject = tomllib.loads(pyproject_path.read_text(encoding="utf-8"))
    project = pyproject["project"]
    dependencies = list(project.get("dependencies", []))
    optional = project.get("optional-dependencies", {})
    for extra in extras:
        dependencies.extend(optional.get(extra, []))
    return dependencies


def install_dependencies(dependencies: list[str]) -> None:
    if not dependencies:
        return
    subprocess.run(
        [sys.executable, "-m", "pip", "install", *dependencies],
        check=True,
    )


def write_pth(project_root: Path) -> None:
    site_packages = Path(sysconfig.get_paths()["purelib"])
    pth_path = site_packages / "github_dev_metrics_local.pth"
    pth_path.write_text(f"{project_root.resolve()}\n", encoding="utf-8")


def main() -> int:
    args = parse_args()
    project_root = args.project_root.resolve()
    dependencies = load_dependencies(project_root, args.extras)
    install_dependencies(dependencies)
    write_pth(project_root)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
