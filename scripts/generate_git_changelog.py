#!/usr/bin/env python3
"""Generate a small JSON changelog from the local Git history.

The Django changelog page reads the generated file, so the app does not need to
execute Git commands during normal page requests.
"""

from __future__ import annotations

import argparse
import json
import subprocess
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

DEFAULT_OUTPUT = Path("app/static/app/data/changelog_git.json")
FIELD_SEPARATOR = "\x1f"


TYPE_RULES = (
    (("fix", "bug", "repair"), "Fix", "fa-solid fa-screwdriver-wrench"),
    (("add", "create", "implement", "new"), "Neu", "fa-solid fa-plus"),
    (("remove", "delete", "drop"), "Entfernt", "fa-solid fa-trash-can"),
    (("style", "ui", "design", "theme"), "Design", "fa-solid fa-palette"),
    (("translate", "translation", "i18n", "locale"), "Übersetzung", "fa-solid fa-language"),
    (("update", "improve", "enhance", "refactor"), "Update", "fa-solid fa-arrow-trend-up"),
)


def _run_git(repo_root: Path, *args: str) -> str:
    completed = subprocess.run(
        ["git", *args],
        cwd=repo_root,
        check=True,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
    )
    return completed.stdout.strip()


def _resolve_repo_root(start_path: Path) -> Path:
    return Path(_run_git(start_path, "rev-parse", "--show-toplevel"))


def _format_date(date_iso: str) -> str:
    try:
        parsed = datetime.fromisoformat(date_iso.replace("Z", "+00:00"))
        return parsed.strftime("%d.%m.%Y")
    except ValueError:
        return date_iso[:10]


def _detect_type(message: str) -> dict[str, str]:
    normalized = message.strip().lower()
    for prefixes, label, icon in TYPE_RULES:
        if normalized.startswith(prefixes):
            return {"type": label, "icon": icon}
    return {"type": "Commit", "icon": "fa-solid fa-code-commit"}


def _parse_git_log(raw_log: str) -> list[dict[str, str]]:
    entries: list[dict[str, str]] = []
    for line in raw_log.splitlines():
        parts = line.split(FIELD_SEPARATOR, 4)
        if len(parts) != 5:
            continue

        full_hash, short_hash, date_iso, subject, author = [part.strip() for part in parts]
        if not subject:
            continue

        type_meta = _detect_type(subject)
        entries.append(
            {
                "hash": full_hash,
                "short_hash": short_hash,
                "date_iso": date_iso,
                "date_display": _format_date(date_iso),
                "message": subject[:180],
                "author": author[:80],
                "type": type_meta["type"],
                "icon": type_meta["icon"],
            }
        )
    return entries


def _unavailable_payload(reason: str) -> dict[str, Any]:
    now = datetime.now(timezone.utc)
    return {
        "available": False,
        "reason": reason,
        "generated_at": now.isoformat(timespec="seconds"),
        "generated_at_display": now.strftime("%d.%m.%Y %H:%M UTC"),
        "branch": "",
        "current_commit": "",
        "remote": "",
        "entries": [],
    }


def generate_git_changelog(repo_root: Path, output_path: Path, limit: int = 20) -> dict[str, Any]:
    repo_root = Path(repo_root).resolve()
    output_path = Path(output_path)
    if not output_path.is_absolute():
        output_path = repo_root / output_path

    try:
        actual_repo_root = _resolve_repo_root(repo_root)
        limit = max(1, min(int(limit), 100))
        pretty_format = f"%H{FIELD_SEPARATOR}%h{FIELD_SEPARATOR}%cI{FIELD_SEPARATOR}%s{FIELD_SEPARATOR}%an"
        raw_log = _run_git(
            actual_repo_root,
            "log",
            f"--max-count={limit}",
            "--no-merges",
            f"--pretty=format:{pretty_format}",
        )
        branch = _run_git(actual_repo_root, "rev-parse", "--abbrev-ref", "HEAD")
        current_commit = _run_git(actual_repo_root, "rev-parse", "--short", "HEAD")
        try:
            remote = _run_git(actual_repo_root, "config", "--get", "remote.origin.url")
        except subprocess.CalledProcessError:
            remote = ""

        now = datetime.now(timezone.utc)
        payload: dict[str, Any] = {
            "available": True,
            "reason": "",
            "generated_at": now.isoformat(timespec="seconds"),
            "generated_at_display": now.strftime("%d.%m.%Y %H:%M UTC"),
            "branch": branch,
            "current_commit": current_commit,
            "remote": remote,
            "entries": _parse_git_log(raw_log),
        }
    except Exception as exc:  # noqa: BLE001 - this script should not block deploys
        payload = _unavailable_payload(str(exc))

    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return payload


def main() -> int:
    parser = argparse.ArgumentParser(description="Generate app/static/app/data/changelog_git.json from Git commits.")
    parser.add_argument("--repo", default=Path(__file__).resolve().parents[1], type=Path, help="Path inside the Git repository.")
    parser.add_argument("--output", default=DEFAULT_OUTPUT, type=Path, help="Output JSON path. Relative paths are resolved from the repo root.")
    parser.add_argument("--limit", default=20, type=int, help="Number of non-merge commits to include.")
    args = parser.parse_args()

    payload = generate_git_changelog(args.repo, args.output, args.limit)
    if payload.get("available"):
        print(f"Git changelog generated: {len(payload.get('entries', []))} commits -> {args.output}")
    else:
        print(f"Git changelog unavailable: {payload.get('reason', 'unknown error')} -> {args.output}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
