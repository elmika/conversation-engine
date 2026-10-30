#!/usr/bin/env python3
"""Apply a named model preset: a consistent batch of model choices across every
task in the app (see docs/prompts.md "Model presets").

Rewrites each prompt file's `model:` frontmatter line to match the preset, then
prints the app/settings.py-level model values (default_model, wrap_up_model) as
.env lines to set by hand — those aren't sourced from prompt frontmatter, and
this script never writes .env itself (it may hold secrets / personal overrides).

This only edits files on disk. The prompts table is reseeded from those files on
the next API restart (`docker compose restart api`, per docs/prompts.md's "Critical:
seeder behaviour") — this script does not touch the running stack or the DB.

Usage:
  python3 scripts/apply_model_preset.py --list
  python3 scripts/apply_model_preset.py baseline-2026-09
  python3 scripts/apply_model_preset.py candidate-x --dry-run
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
PRESETS_DIR = REPO_ROOT / "config" / "model_presets"
PROMPTS_DIR = REPO_ROOT / "prompts"

_MODEL_LINE_RE = re.compile(r"^model:\s*.*$", re.MULTILINE)
_NAME_LINE_RE = re.compile(r"^name:\s*.*$", re.MULTILINE)
_SLUG_RE = re.compile(r"[a-z0-9][a-z0-9._-]*")


def _file_in(directory: Path, name: str, suffix: str) -> Path:
    """Return directory/<name><suffix>, refusing names that could escape `directory`.

    Preset names come from the command line and prompt slugs from the preset's JSON, and this
    script writes files: a name like `../../app/main` must not reach outside the directory.
    """
    if not _SLUG_RE.fullmatch(name):
        raise SystemExit(f"Invalid name {name!r}: expected a slug like 'course-session-core'.")
    path = (directory / f"{name}{suffix}").resolve()
    if path.parent != directory.resolve():
        raise SystemExit(f"Refusing {name!r}: resolves outside {directory}.")
    return path


def load_preset(name: str, presets_dir: Path) -> dict:
    path = _file_in(presets_dir, name, ".json")
    if not path.exists():
        available = sorted(p.stem for p in presets_dir.glob("*.json"))
        raise SystemExit(
            f"No preset '{name}' at {path}.\nAvailable: {', '.join(available) or '(none)'}"
        )
    return json.loads(path.read_text(encoding="utf-8"))


def list_presets(presets_dir: Path) -> None:
    for path in sorted(presets_dir.glob("*.json")):
        preset = json.loads(path.read_text(encoding="utf-8"))
        print(f"{preset.get('name', path.stem)}: {preset.get('description', '')}")


def _frontmatter_span(content: str) -> tuple[int, int] | None:
    """Return (start, end) char offsets of the frontmatter body (between the
    two `---` lines), or None if the file has no frontmatter block."""
    if not content.startswith("---\n"):
        return None
    end = content.find("\n---", 4)
    if end == -1:
        return None
    return 4, end


def apply_model_to_prompt(path: Path, model: str, dry_run: bool) -> str:
    """Set `model:` in `path`'s frontmatter. Returns a one-line status string."""
    if not path.exists():
        return f"  SKIP  {path.name} (file not found)"

    content = path.read_text(encoding="utf-8")
    span = _frontmatter_span(content)
    if span is None:
        return f"  SKIP  {path.name} (no frontmatter block)"
    start, end = span
    frontmatter = content[start:end]

    existing = _MODEL_LINE_RE.search(frontmatter)
    if existing and existing.group(0) == f"model: {model}":
        return f"  OK    {path.name} (already {model})"

    if existing:
        old = existing.group(0).removeprefix("model: ").strip()
        new_frontmatter = _MODEL_LINE_RE.sub(f"model: {model}", frontmatter, count=1)
        status = f"  {'DRY-RUN' if dry_run else 'UPDATE'} {path.name}: {old} -> {model}"
    else:
        # No model: line yet -- insert right after `name:` (present in every
        # seeded prompt file) so frontmatter stays readable.
        name_match = _NAME_LINE_RE.search(frontmatter)
        if not name_match:
            return f"  SKIP  {path.name} (no name: line to anchor insertion)"
        insert_at = name_match.end()
        new_frontmatter = frontmatter[:insert_at] + f"\nmodel: {model}" + frontmatter[insert_at:]
        status = f"  {'DRY-RUN' if dry_run else 'ADD'}    {path.name}: (none) -> {model}"

    if not dry_run:
        new_content = content[:start] + new_frontmatter + content[end:]
        path.write_text(new_content, encoding="utf-8")
    return status


def main() -> int:
    ap = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter
    )
    ap.add_argument("preset", nargs="?", help="preset name (config/model_presets/<name>.json)")
    ap.add_argument("--list", action="store_true", help="list available presets and exit")
    ap.add_argument("--dry-run", action="store_true", help="show changes without writing files")
    ap.add_argument("--presets-dir", default=str(PRESETS_DIR))
    ap.add_argument("--prompts-dir", default=str(PROMPTS_DIR))
    args = ap.parse_args()

    presets_dir = Path(args.presets_dir)
    prompts_dir = Path(args.prompts_dir)

    if args.list or not args.preset:
        list_presets(presets_dir)
        return 0

    preset = load_preset(args.preset, presets_dir)
    print(f"Applying preset '{preset['name']}'{' (dry run)' if args.dry_run else ''}")
    if preset.get("description"):
        print(f"  {preset['description']}\n")

    for slug, model in preset.get("prompts", {}).items():
        print(apply_model_to_prompt(_file_in(prompts_dir, slug, ".md"), model, args.dry_run))

    settings = preset.get("settings", {})
    if settings:
        print("\nSettings-level models (not frontmatter -- set these in .env by hand):")
        for key, model in settings.items():
            print(f"  {key.upper()}={model}")

    if not args.dry_run:
        print("\nRestart the API to reseed the prompts table from these files:")
        print("  docker compose restart api")
    return 0


if __name__ == "__main__":
    sys.exit(main())
