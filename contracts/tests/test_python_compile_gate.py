from __future__ import annotations

import py_compile
from pathlib import Path


def _python_files(root: Path) -> list[Path]:
    files: list[Path] = []
    for path in root.rglob("*.py"):
        if "/external/" in path.as_posix():
            continue
        files.append(path)
    return files


def test_python_modules_compile_cleanly() -> None:
    project_root = Path(__file__).resolve().parents[2]
    targets = [project_root / "api", project_root / "agent", project_root / "contracts"]

    for target in targets:
        for file_path in _python_files(target):
            py_compile.compile(str(file_path), doraise=True)
