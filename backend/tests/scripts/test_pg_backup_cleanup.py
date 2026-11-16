"""Dump cleanup of config/backup/pg_backup.sh when a run FAILS (audit r2-fleet-infra-02, 2026-11-16).

The cleanup used to be a RETURN trap, which bash does not fire when `set -e` aborts the shell: every
failed run (B2 outage, revoked key, partial pg_dump) left a full dump on the volume, one per 15-minute
retry. Pure bash test: pg_dump / pg_restore / b2 are stubs on PATH, no docker, no Postgres.
"""

import os
import subprocess
import time
from pathlib import Path

import pytest

SCRIPT = next(
    parent / "config/backup/pg_backup.sh"
    for parent in Path(__file__).resolve().parents
    if (parent / "config/backup/pg_backup.sh").exists()
)

PG_DUMP = """#!/bin/bash
while [[ $# -gt 0 ]]; do [[ "$1" == "-f" ]] && out="$2"; shift; done
echo "fake dump" > "$out"
"""
PG_RESTORE = "#!/bin/bash\nexit 0\n"
# `ls` lists one daily dump; `file download` writes a partial file and then fails (B2 dropped mid-transfer);
# every other call (upload, cancel...) fails like an unreachable bucket.
B2 = """#!/bin/bash
if [[ "$1 $2" == "ls --json" ]]; then echo '[{"fileName": "backups/postgres/daily/testapp-2026-11-01T0300.dump"}]'; exit 0; fi
if [[ "$1 $2" == "file download" ]]; then echo partial > "${@: -1}"; exit 1; fi
exit 1
"""


@pytest.fixture
def env(tmp_path: Path) -> dict[str, str]:
    bin_dir = tmp_path / "bin"
    bin_dir.mkdir()
    for name, body in {"pg_dump": PG_DUMP, "pg_restore": PG_RESTORE, "b2": B2}.items():
        (bin_dir / name).write_text(body)
        (bin_dir / name).chmod(0o755)
    return {
        **os.environ,
        "PATH": f"{bin_dir}:{os.environ['PATH']}",
        "BACKUP_DIR": str(tmp_path / "backup"),
        "STARTED_FILE": str(tmp_path / "started"),
        "BACKUP_APP": "testapp",
        "POSTGRES_USER": "u",
        "POSTGRES_DB": "d",
        "B2_PRIVATE_BUCKET": "bucket",
        "B2_PRIVATE_KEY_ID": "id",
        "B2_PRIVATE_APP_KEY": "key",
    }


def run(env: dict[str, str], *args: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        ["bash", str(SCRIPT), *args], env=env, capture_output=True, text=True, check=False
    )


def dumps(env: dict[str, str]) -> list[str]:
    return sorted(p.name for p in (Path(env["BACKUP_DIR"]) / "dump").glob("*.dump"))


def test_failed_upload_leaves_no_dump_behind(env: dict[str, str]) -> None:
    completed = run(env, "__backup", "scheduled")

    assert completed.returncode != 0  # the stubbed B2 is unreachable
    assert '"event":"dump"' in completed.stdout  # pg_dump did run, so there was something to leak
    assert dumps(env) == []


def test_failed_rehearsal_download_leaves_no_dump_behind(env: dict[str, str]) -> None:
    completed = run(env, "rehearse")

    assert completed.returncode != 0
    assert dumps(env) == []


def test_next_run_sweeps_dumps_a_killed_container_left_but_keeps_recent_ones(
    env: dict[str, str],
) -> None:
    dump_dir = Path(env["BACKUP_DIR"]) / "dump"
    dump_dir.mkdir(parents=True)
    stale, recent = dump_dir / "testapp-old.1.dump", dump_dir / "testapp-recent.2.dump"
    stale.write_text("x")
    recent.write_text("x")
    two_days_ago = time.time() - 2 * 86400
    os.utime(stale, (two_days_ago, two_days_ago))

    run(env, "__backup", "scheduled")

    assert not stale.exists()
    assert recent.exists()  # a dry-run dump kept on purpose for restore tests must survive
