"""fleet_drift classification on toy repos (audit 2026-11-13 template-gap-09)."""

import importlib.util
import json
from pathlib import Path

SCRIPT = Path(__file__).resolve().parents[2] / "scripts" / "fleet_drift.py"
spec = importlib.util.spec_from_file_location("fleet_drift", SCRIPT)
fleet_drift = importlib.util.module_from_spec(spec)
spec.loader.exec_module(fleet_drift)


def _write(root: Path, rel: str, text: str) -> None:
    (root / rel).parent.mkdir(parents=True, exist_ok=True)
    (root / rel).write_text(text)


def _repos(tmp_path: Path) -> tuple[Path, list[Path]]:
    template = tmp_path / "template"
    apps = [tmp_path / "a", tmp_path / "b", tmp_path / "c"]
    _write(template, "config/host/x.sh", "v1")
    _write(template, "config/host/stale.sh", "old")
    _write(template, "config/host/drift.sh", "t")
    for app in apps:
        _write(app, "config/host/x.sh", "v1")
        _write(app, "config/host/stale.sh", "new")
        _write(app, "config/host/only_apps.sh", "n")
    _write(apps[0], "config/host/drift.sh", "t")
    _write(apps[1], "config/host/drift.sh", "other")
    return template, apps


def test_classifies_aligned_stale_drift_and_missing(tmp_path: Path) -> None:
    template, apps = _repos(tmp_path)
    report = fleet_drift.classify(template, apps, ["config/host/*"])
    assert {k: v["status"] for k, v in report.items()} == {
        "config/host/x.sh": "aligned",
        "config/host/stale.sh": "template_stale",
        "config/host/drift.sh": "app_drift",
        "config/host/only_apps.sh": "missing_in_template",
    }


def test_update_template_only_where_every_app_agrees(tmp_path: Path) -> None:
    template, apps = _repos(tmp_path)
    report = fleet_drift.classify(template, apps, ["config/host/*"])
    updated = fleet_drift.update_template(template, apps, report)
    assert sorted(updated) == ["config/host/only_apps.sh", "config/host/stale.sh"]
    assert (template / "config/host/stale.sh").read_text() == "new"
    assert (template / "config/host/drift.sh").read_text() == "t"


def test_strict_exit_code_and_real_manifest_is_valid(tmp_path: Path) -> None:
    template, apps = _repos(tmp_path)
    (template / "config").mkdir(exist_ok=True)
    (template / "config/template-manifest.json").write_text(
        json.dumps({"track": ["config/host/*"]})
    )
    argv = ["--template", str(template), "--apps", *map(str, apps), "--strict"]
    assert fleet_drift.main(argv) == 1
    manifest = json.loads((fleet_drift.TEMPLATE_ROOT / "config/template-manifest.json").read_text())
    assert manifest["track"]
