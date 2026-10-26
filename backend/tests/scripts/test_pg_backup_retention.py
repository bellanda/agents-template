"""Retention of config/backup/pg_backup.sh (`select-expired N`, `monthly-due`): what the B2 cleanup
deletes and when the monthly copy is taken.

User decision 2026-10-26: at most 7 dumps per app — daily/ keeps ONE dump per day for 3 days, weekly/ 2,
monthly/ 1 (first scheduled run of each month), predeploy/ only the newest (decision 2026-10-16).
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


def is_monthly_due(month: str, names: list[str]) -> bool:
    completed = subprocess.run(
        ["bash", str(SCRIPT), "monthly-due", month],
        input="\n".join(names),
        capture_output=True,
        text=True,
        check=False,
    )
    assert completed.returncode in (0, 1), completed.stderr
    return completed.returncode == 0


def test_daily_keeps_the_newest_dump_of_each_of_the_last_three_days() -> None:
    days = [f"2026-10-{day:02d}" for day in range(20, 27)]
    names = [f"daily/app-{day}T0300.dump" for day in days]
    names += ["daily/app-2026-10-25T1100.dump", "daily/app-2026-10-25T1500.dump"]

    expired = select_expired(3, names)

    assert sorted(expired) == [
        "daily/app-2026-10-20T0300.dump",
        "daily/app-2026-10-21T0300.dump",
        "daily/app-2026-10-22T0300.dump",
        "daily/app-2026-10-23T0300.dump",
        "daily/app-2026-10-25T0300.dump",
        "daily/app-2026-10-25T1100.dump",
    ]


def test_monthly_copy_is_taken_once_per_month_even_if_the_first_was_missed() -> None:
    current = ["backups/postgres/monthly/app-2026-11-03.dump"]
    previous = ["backups/postgres/monthly/app-2026-10-27.dump"]

    assert is_monthly_due("2026-10", []) is True
    assert is_monthly_due("2026-11", previous) is True
    assert is_monthly_due("2026-11", current) is False
    assert select_expired(1, previous + current) == previous


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
