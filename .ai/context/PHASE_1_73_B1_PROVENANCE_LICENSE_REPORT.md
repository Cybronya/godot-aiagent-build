# Phase 1.73 — Batch B.1
# Stage C — Provenance & License Gate Report

Gate used: the **existing** Phase 1.71 mechanism, unmodified —
`.ai/tools/external_code/provenance.py` (`assess_license`, `assess_provenance`,
`license_files`, `source_file_url`) and its read-only validator
`.ai/tools/external_code/provenance_validator.py`.

No allowlist, status, threshold or rule was changed in this batch.

---

## 1. Gate result per accepted repository

Command per repository (real CLI):

```
python .ai/tools/external_code/provenance_validator.py --repo .ai/skills/foundation/godot-gdscript/code_library/sources/<slug> --json
```

| Repository | Full 40-char commit SHA | Immutable commit URL | SPDX | License text in mirror | `license_status` | `provenance_status` | Validator status |
|---|---|---|---|---|---|---|---|
| gdquest-demos/godot-make-pro-2d-games | `7290681309ffcd700c2c08a8e59a57bfbec14d5e` | yes (`/blob/7290681…/actors/health/Stats.gd`) | MIT | yes (`LICENSE`) | `eligible` | `complete` | `valid` — “metadata, license and full provenance are complete” |
| gdquest-demos/godot-open-rpg | `d59f2f71bc046ac53239a4e590861269e7100a36` | yes | MIT | yes (`LICENSE`) | `eligible` | `complete` | `valid` |
| lampe-games/godot-open-rts | `a628ad3bb6a9a903587a181a7ee3300dbf735e81` | yes | MIT | yes (`LICENSE`) | `eligible` | `complete` | `valid` |
| nezvers/Godot-GameTemplate | `d5d8d15887423b3a8acf0502efb6271c600a80bc` | yes | MIT | yes (`LICENSE`) | `eligible` | `complete` | `valid` |
| bitbrain/beehave | `fe589153fa780a3f88989578ceb5f539afffb7c2` | yes | MIT | **no** | `license_text_missing` (`copy_allowed=true`, basis `spdx_allowlist_existing_policy`) | `complete` | `incomplete` — only reason: “local license text is missing” |

### 1.1 Why beehave is still accepted

The existing gate already defines this exact case: an allowlisted SPDX id resolved from the
GitHub API, with no local root license file, yields `license_text_missing` with
`license_risk=local_license_text_missing` and `copy_allowed=true` under the project's
standing policy. B.1 forbids *lowering* the standard, and this decision comes from the
standard as it already is. The risk is carried into every analysis record
(`license_risk`, `license_status`) and into the final report. If the policy is later
tightened, these three beehave records become `blocked_license` on re-analysis without any
data loss.

### 1.2 Rejected repository

| Repository | Full SHA | Gate result | Consequence |
|---|---|---|---|
| Miziziziz/MizGodotTools | **absent** (`commit_sha_full: null`, short `cb548f9035a3` only) | `provenance_status=incomplete`; validator status `incomplete`; reason “only a short commit SHA is available; full SHA was not guessed” | stopped before analysis; not part of the compliant corpus |

## 2. Provenance verification of the produced records

All 20 new Analysis Records were produced with `--reference` + `--metadata` where the
metadata is the existing catalog entry joined with the repository's own `_meta.json`, and
the `source_url` is rebuilt with the existing `provenance.source_file_url()` helper.
Measured on the records themselves:

| Check | Result |
|---|---|
| `provenance_status` | `complete` — 20 / 20 |
| `provenance.immutable_source_url` | `true` — 20 / 20 |
| `commit_sha_full` length 40 and prefix-consistent with `commit_sha` | 20 / 20 (asserted during generation) |
| `source_consistent` (mirrored source file equals the analysed reference body) | `true` — 20 / 20 |
| `source_digest` present | 20 / 20 |
| `license_status=eligible` | 17 / 20 |
| `license_status=license_text_missing` (beehave only) | 3 / 20 |
| `copy_allowed` | 20 / 20 |

## 3. Why `--snippet` alone was not used

`catalog.yaml` stores only a short `commit_sha` and a branch `source_url`
(`grep -c commit_sha_full catalog.yaml` → 0). Feeding `--snippet` would have produced
`provenance_status=incomplete` records even though the full SHA exists in
`sources/<slug>/_meta.json`. Using the CLI's documented `--reference/--metadata` inputs with
the complete metadata is strictly *stronger* than the catalog path; it does not bypass or
relax the gate.

Note: because the catalog itself is legacy, `provenance_validator.py --entry <id>` reports
`incomplete` (“legacy provenance/license evidence is incomplete”) for catalog entries of
*all* repositories, including the four `valid` ones above. The authoritative per-repository
signal is `--repo` mode plus `assess_provenance()` on the record fields, both of which are
complete here. This is a pre-existing property of the catalog, not a defect introduced by
B.1, and it was not "fixed" by editing the catalog.

## 4. Gate summary

* 5 repositories accepted (4 fully `valid`, 1 `license_text_missing` under existing policy).
* 1 repository rejected for missing full commit SHA.
* 0 repositories analysed without a complete provenance record.
* 0 gate rules modified.
