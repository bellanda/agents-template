// @vitest-environment node
// SHARED WIDGETS DRIFT CHECK. Shipped UNEDITED by `rules.py` (Config Files/agents/shared-widgets/)
// into every app at `frontend/src/test/__tests__/`; do not edit the propagated copy.
//
// Why: the fleet's shared widgets (ErrorState, ConfirmDialog, DataList, ListToolbar, ...) are
// meant to be byte-identical across apps; identity (colors, fonts, copy) comes from tokens, not
// from these files. Without a gate they drifted silently (audit 2026-11 drift-frontend-01).
//
// How: `../shared-widgets.manifest.json` (written by `rules.py` per app) holds the sha256 of the
// canonical bytes. This test hashes the local file and fails naming repo + file. No network, no
// other repo needed. To change a shared widget: edit the canonical in the central config, run
// `rules.py --shared-apply` then `rules.py`. Never "fix" the manifest by hand.
import { createHash } from "node:crypto";
import { existsSync, readFileSync } from "node:fs";
import { join } from "node:path";
import { describe, expect, it } from "vitest";

interface Manifest {
  repo: string;
  /** repo-relative path -> sha256 of the canonical bytes */
  files: Record<string, string>;
  /** repo-relative path -> why this app is allowed to differ (not compared) */
  exceptions: Record<string, string>;
  /** non-empty when the app may legitimately lack a shared file (the template) */
  optional: string;
}

// __dirname = <repo>/frontend/src/test/__tests__
const REPO_ROOT = join(__dirname, "..", "..", "..", "..");
const manifest = JSON.parse(
  readFileSync(join(__dirname, "..", "shared-widgets.manifest.json"), "utf8")
) as Manifest;

describe(`shared widgets (${manifest.repo}) match the fleet canonical`, () => {
  const entries = Object.entries(manifest.files).filter(([path]) => !(path in manifest.exceptions));

  it.each(entries)("%s", (path, canonicalSha) => {
    const abs = join(REPO_ROOT, path);
    if (!existsSync(abs)) {
      if (manifest.optional) return;
      throw new Error(`[${manifest.repo}] shared widget missing: ${path}`);
    }
    const sha = createHash("sha256").update(readFileSync(abs)).digest("hex");
    expect(
      sha,
      `[${manifest.repo}] ${path} drifted from the canonical. Edit the canonical in the central ` +
        `config (skills/frontend/references/) and run rules.py --shared-apply, or declare an ` +
        `exception in shared-widgets/shared-widgets.json.`
    ).toBe(canonicalSha);
  });
});
