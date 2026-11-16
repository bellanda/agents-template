"""One pinned table for every infra image tag of the template (audit 2026-11-16 r2 lock test).

Why: the same tag is written in several files (compose, pg-backup image, test compose, Dockerfiles)
and an upgrade wave that misses one leaves the fleet drifting (NATS 2.15.1 in one place and 2.15.3 in
another, bun 1.3.14 in a Dockerfile after the rest moved to 1.4.x). Bumping a version = change the
`PINS` row here AND every file that carries it; this test fails on any place that was missed, and on
a new image the table does not know about.
"""

import re
from pathlib import Path

REPO = Path(__file__).resolve().parents[3]

# image name (as written after `image:` / `FROM`) -> the single tag allowed anywhere in the repo.
PINS: dict[str, str] = {
    "postgres": "18.7-trixie",
    "valkey/valkey": "9.1.3-alpine",
    "nats": "2.15.3-alpine",
    "ghcr.io/amacneil/dbmate": "2.38.1",
    "edoburu/pgbouncer": "v1.26.1-p0",
    "oven/bun": "1.4.4-slim",
    "nginx": "1.30.6-trixie",
    "python": "3.13.18-slim-trixie",
}

# Where image references live: compose files (`image:`) and Dockerfiles (`FROM`).
SOURCES = [
    "compose.yaml",
    "backend/tests/compose.yml",
    "backend/Dockerfile",
    "frontend/Dockerfile",
    "config/backup/Dockerfile",
    *(f"config/docker/{p.name}" for p in (REPO / "config/docker").glob("*.y*ml")),
]
REFERENCE = re.compile(r"^\s*(?:image:|FROM)\s+(?P<image>[^\s:@]+):(?P<tag>[^\s@]+)", re.M)


def _references() -> list[tuple[str, str, str]]:
    found = []
    for rel in SOURCES:
        for match in REFERENCE.finditer((REPO / rel).read_text()):
            found.append((rel, match["image"], match["tag"]))
    return found


def test_every_image_tag_equals_the_pinned_table():
    refs = _references()
    assert refs, "no image reference found: the SOURCES list is stale"
    drift = [(rel, image, tag) for rel, image, tag in refs if PINS.get(image) != tag]
    assert not drift, f"image tag differs from PINS (or image unknown to the table): {drift}"


def test_the_core_images_are_actually_referenced():
    """A pin nobody uses is dead weight; a core image that disappeared from every file is a mistake."""
    used = {image for _, image, _ in _references()}
    core = {"postgres", "valkey/valkey", "nats", "oven/bun", "nginx"}
    assert core <= used, f"not referenced anywhere: {sorted(core - used)}"
    assert used <= PINS.keys(), f"unpinned images: {sorted(used - PINS.keys())}"
