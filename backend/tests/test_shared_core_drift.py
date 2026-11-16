"""SHARED BACKEND CORE DRIFT CHECK. Shipped UNEDITED by `rules.py` (Config Files/agents/shared-backend/)
into every app at `backend/tests/test_shared_core_drift.py`; do not edit the propagated copy.

Why: the auth core (login_throttle, auth_context_cache, permission_service, the Valkey client, the
auth-invalidation listener, client_ip) must be byte-identical across the fleet; product-specific
behaviour lives in per-app adapter modules (org_access_policy.py, org_admin_gate.py, config/security.py)
that the core imports. Without a gate the 6 repos drifted silently (audit 2026-11 core-security-20).

How: `shared_core.manifest.json` (written by `rules.py` per app) holds the sha256 of the canonical
bytes. This test hashes the local file and fails naming repo + file. No network, no other repo needed.
To change a shared file: edit the canonical in the central config (shared-backend/canonical/) and run
`rules.py --shared-only --shared-apply`. Never "fix" the manifest by hand.
"""

import hashlib
import json
from pathlib import Path

import pytest

_TESTS_DIR = Path(__file__).resolve().parent
# <repo>/backend/tests -> <repo>
_REPO_ROOT = _TESTS_DIR.parents[1]
_MANIFEST = json.loads((_TESTS_DIR / "shared_core.manifest.json").read_text(encoding="utf-8"))
_ENTRIES = sorted(
    (path, sha) for path, sha in _MANIFEST["files"].items() if path not in _MANIFEST["exceptions"]
)


@pytest.mark.parametrize(("path", "canonical_sha"), _ENTRIES, ids=[p for p, _ in _ENTRIES])
def test_shared_core_file_matches_canonical(path: str, canonical_sha: str) -> None:
    target = _REPO_ROOT / path
    assert target.is_file(), f"[{_MANIFEST['repo']}] shared core file missing: {path}"
    sha = hashlib.sha256(target.read_bytes()).hexdigest()
    assert sha == canonical_sha, (
        f"[{_MANIFEST['repo']}] {path} drifted from the canonical. Edit the canonical in the central "
        "config (shared-backend/canonical/) and run `rules.py --shared-only --shared-apply`, or declare "
        "an exception in shared-backend/shared-backend.json."
    )
