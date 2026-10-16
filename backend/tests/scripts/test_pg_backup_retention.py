"""Retention of config/backup/pg_backup.sh (`select-expired N`): what the B2 cleanup deletes.

User decision 2026-10-16: daily/ keeps ONE dump per day for 7 days; predeploy/ keeps only the newest.
"""

import subprocess
from pathlib import Path

SCRIPT = next(
    parent / "config/backup/pg_backup.sh"
    for parent in Path(__file__).resolve().parents
    if (parent / "config/backup/pg_backup.sh").exists()
)


def select_expired(keep: int, names: list[str]) -> list[str]:
    completed = subprocess.run(
        ["bash", str(SCRIPT), "select-expired", str(keep)],
        input="\n".join(names),
        capture_output=True,
        text=True,
        check=True,
    )
    return completed.stdout.split()


def test_daily_keeps_the_newest_dump_of_each_of_the_last_seven_days() -> None:
    days = [f"2026-10-{day:02d}" for day in range(8, 17)]
    names = [f"daily/app-{day}T0300.dump" for day in days]
    names += ["daily/app-2026-10-14T1100.dump", "daily/app-2026-10-14T1500.dump"]

    expired = select_expired(7, names)

    assert sorted(expired) == [
        "daily/app-2026-10-08T0300.dump",
        "daily/app-2026-10-09T0300.dump",
        "daily/app-2026-10-14T0300.dump",
        "daily/app-2026-10-14T1100.dump",
    ]


def test_predeploy_keeps_only_the_last_dump() -> None:
    names = [
        "predeploy/app-2026-10-14T0900.dump",
        "predeploy/app-2026-10-16T1009.dump",
        "predeploy/app-2026-10-16T0800.dump",
    ]

    assert sorted(select_expired(1, names)) == [
        "predeploy/app-2026-10-14T0900.dump",
        "predeploy/app-2026-10-16T0800.dump",
    ]
