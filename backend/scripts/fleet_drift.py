"""Template x fleet drift report (audit 2026-11-13 template-gap-09).

The template used to age silently: the only sync script covers `backend/agents` one way and never
says when files diverge. This compares every file matched by `config/template-manifest.json` across
the template and the apps and classifies it:

- `aligned`: template and all apps that have the file are byte-identical.
- `template_stale`: the apps agree with each other but the template differs (the template needs
  updating; this is the class that makes a new app be born old).
- `app_drift`: apps differ from each other or from the template (some app diverged; look at it).
- `missing_in_template`: apps have the file, the template does not.
Files an app does not have are ignored (apps legitimately skip features).

Usage (from anywhere):
    uv run python scripts/fleet_drift.py --apps ~/code/kailos ~/code/akmeo [--json] [--strict]
    uv run python scripts/fleet_drift.py --apps ... --update-template   # copy app consensus into the template
`--strict` exits 1 when anything but `aligned` shows up (use it in the template's check).
"""

from __future__ import annotations

import argparse
import hashlib
import json
import shutil
import sys
from pathlib import Path

TEMPLATE_ROOT = Path(__file__).resolve().parents[2]
MANIFEST = TEMPLATE_ROOT / "config" / "template-manifest.json"


def _digest(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _tracked_paths(roots: list[Path], patterns: list[str]) -> list[str]:
    found: set[str] = set()
    for root in roots:
        for pattern in patterns:
            found.update(str(p.relative_to(root)) for p in root.glob(pattern) if p.is_file())
    return sorted(found)


def classify(template: Path, apps: list[Path], patterns: list[str]) -> dict[str, dict]:
    report: dict[str, dict] = {}
    for rel in _tracked_paths([template, *apps], patterns):
        template_file = template / rel
        app_digests = {app.name: _digest(app / rel) for app in apps if (app / rel).is_file()}
        if not app_digests:
            continue
        if not template_file.is_file():
            status = "missing_in_template"
        else:
            template_digest = _digest(template_file)
            distinct = set(app_digests.values())
            if distinct == {template_digest}:
                status = "aligned"
            elif len(distinct) == 1:
                status = "template_stale"
            else:
                status = "app_drift"
        report[rel] = {"status": status, "apps": sorted(app_digests)}
    return report


def update_template(template: Path, apps: list[Path], report: dict[str, dict]) -> list[str]:
    """Copy the apps' shared version into the template, only where every app agrees."""
    updated = []
    for rel, entry in report.items():
        if entry["status"] not in {"template_stale", "missing_in_template"}:
            continue
        sources = [app / rel for app in apps if (app / rel).is_file()]
        if len({_digest(p) for p in sources}) != 1:
            continue
        (template / rel).parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(sources[0], template / rel)
        updated.append(rel)
    return updated


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--apps", nargs="+", type=Path, required=True)
    parser.add_argument("--template", type=Path, default=TEMPLATE_ROOT)
    parser.add_argument("--json", action="store_true")
    parser.add_argument("--strict", action="store_true")
    parser.add_argument("--update-template", action="store_true")
    args = parser.parse_args(argv)

    patterns = json.loads((args.template / "config" / "template-manifest.json").read_text())[
        "track"
    ]
    apps = [a.expanduser().resolve() for a in args.apps]
    report = classify(args.template.resolve(), apps, patterns)
    if args.update_template:
        for rel in update_template(args.template.resolve(), apps, report):
            sys.stdout.write(f"updated template: {rel}\n")
        report = classify(args.template.resolve(), apps, patterns)

    if args.json:
        sys.stdout.write(json.dumps(report, indent=2) + "\n")
    else:
        for rel, entry in report.items():
            if entry["status"] != "aligned":
                sys.stdout.write(f"{entry['status']:20} {rel}  ({', '.join(entry['apps'])})\n")
        sys.stdout.write(
            f"{len(report)} tracked files, {sum(e['status'] != 'aligned' for e in report.values())} not aligned\n"
        )
    drifted = any(e["status"] != "aligned" for e in report.values())
    return 1 if (args.strict and drifted) else 0


if __name__ == "__main__":
    raise SystemExit(main())
