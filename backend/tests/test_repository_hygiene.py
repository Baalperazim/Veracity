from __future__ import annotations

import subprocess
from pathlib import Path


def test_repository_has_no_forbidden_brand_mentions() -> None:
    repo_root = Path(__file__).resolve().parents[2]
    tracked_files = (
        subprocess.check_output(["git", "ls-files"], cwd=repo_root, text=True)
        .strip()
        .splitlines()
    )

    forbidden_token = "".join(chr(code) for code in (99, 111, 100, 101, 120))

    offenders: list[str] = []
    for rel_path in tracked_files:
        path = repo_root / rel_path
        if not path.is_file():
            continue

        try:
            content = path.read_text(encoding="utf-8")
        except UnicodeDecodeError:
            continue

        if forbidden_token in content.casefold():
            offenders.append(rel_path)

    assert offenders == [], f"Found forbidden brand term in: {offenders}"
