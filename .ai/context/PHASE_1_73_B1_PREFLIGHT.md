# Phase 1.73 — Batch B.1
# Targeted External Corpus Enrichment
# Stage A — Preflight

Recorded: 2026-11-15T14:33:58Z
Project Root: `F:/Godot_v4.7-stable/game`

---

## 1. Git state (measured, not assumed)

| Item | Value |
|---|---|
| Branch | `master` |
| HEAD | `d64b1cd5b576a44dcfafd7becbb2d2a7f1fd6a84` |
| Staged | 0 |
| Modified (tracked) | 33 |
| Untracked files (`-uall`) | 240 |

The 33 modified tracked files and all untracked files pre-date this batch and are the
user's existing working-tree state (Batch A / A.1 / B artefacts plus older phase work).
Nothing was reset, cleaned or reverted.

## 2. Corpus state

| Item | Value | Source of truth |
|---|---|---|
| Repository Catalog entries | 7270 | `code_library/catalog.yaml` → `total_entries` |
| Catalog unique fragments | 6813 | `catalog.yaml` → `unique_fragments` |
| Reference files on disk | 6813 | `.ai/skills/.../code_library/references/**` |
| Source mirror repositories | 77 | directories under `code_library/sources/` |
| Catalog generated_at | 2026-10-31 | `catalog.yaml` |

Note: `catalog.yaml` stores `duplicate_of` as the string `"None"` for non-duplicates, so a
naive truthiness count yields 0 unique entries. The real unique count is 6813, matching
`unique_fragments` and the reference file count.

## 3. Phase 1.73 artefacts before this batch

| Item | Value |
|---|---|
| External Analysis Records | 14 |
| External Analysis Index entries | 14 |
| Feature Evidence Projections | 5 (`health`, `health_bar`, `openable_door`, `attack_emitter`, `blackboard`) |
| Feature Linkage Records | 65 |
| Linkage freshness | FRESH=65, STALE=0, MISSING_SOURCE=0, INVALID=0 (coverage 65/65) |
| Feature Registry features | 31 |

Projection status: `health` PARTIAL, `health_bar` PARTIAL, `openable_door` COMPLETE,
`attack_emitter` PARTIAL, `blackboard` COMPLETE — all five
`feature_verification_status=NOT_VERIFIED`, `test_execution_status=NOT_RUN`.

Linkage baseline: 3 `POTENTIAL_RELEVANCE`, 62 `NO_SUPPORTED_LINK`, 0 DIRECT / INDIRECT /
DECLARED, 5 unevaluable pairs (shader).

## 4. Tool interfaces verified in this batch (CLI help output, not memory)

| Tool | Verified interface |
|---|---|
| `external_code_understanding.py` | `--snippet ID` (repeatable), `--reference PATH`, `--metadata JSON`, `--catalog`, `--out-dir`, `--index-path`, `--json`, `--reindex` |
| `provenance_validator.py` | `--catalog [PATH]`, `--repo DIR`, `--reference PATH`, `--entry ID`, `--json`, `--limit` (read-only) |
| `provenance.py` | library only (no CLI): `assess_license`, `assess_provenance`, `license_files`, `has_license_text`, `source_file_url`, `metadata_for_source` |
| `feature_linkage.py` | `build` / `check`, each with `--pilot`, `--analysis ID`, `--feature ID`, `--analysis-dir`, `--projection-dir`, `--features-dir`, `--graph`, `--out`, `--json` |

### 4.1 A critical interface finding

`external_code_understanding.py --snippet <id>` builds its metadata **only from
`catalog.yaml`**, whose entries carry a *short* `commit_sha` and a *branch* `source_url`
and **no `commit_sha_full`** (`grep -c commit_sha_full catalog.yaml` → 0).

Feeding `--snippet` directly would therefore produce
`provenance_status="incomplete"` and `immutable_source_url=false` for every new record,
even though the full SHA is known. The full 40-character SHA lives in
`code_library/sources/<repo_slug>/_meta.json` (`commit_sha_full`, verified present and
consistent with the short SHA prefix for all five selected repositories).

Consequence for this batch: new analyses are produced through the **same CLI**, but with
`--reference <mirrored reference file>` plus `--metadata <json>`, where the metadata is
built from the existing catalog entry + the repository's own `_meta.json`, and the
`source_url` is rebuilt with the existing `provenance.source_file_url()` helper so that it
is commit-pinned. No parser, schema, gate or gate-rule was changed; only the documented
`--reference/--metadata` input path is used, with complete provenance data.

## 5. Licence / provenance gate state (read-only inspection)

`provenance.py` is the single decision point (allowlist MIT/CC0/BSD/Apache/Unlicense/ISC/
Zlib/MPL-2.0; `license_text_missing` is a recorded risk but still copy-allowed under the
existing policy). Gate rules were **not** modified.

| Repository | slug | short SHA | full SHA | SPDX | LICENSE file at mirror root |
|---|---|---|---|---|---|
| gdquest-demos/godot-make-pro-2d-games | `gdquest-demos__godot-make-pro-2d-games` | 7290681309ff | 7290681309ffcd700c2c08a8e59a57bfbec14d5e | MIT | yes |
| bitbrain/beehave | `bitbrain__beehave` | fe589153fa78 | fe589153fa780a3f88989578ceb5f539afffb7c2 | MIT | **no** |
| gdquest-demos/godot-open-rpg | `gdquest-demos__godot-open-rpg` | d59f2f71bc04 | d59f2f71bc046ac53239a4e590861269e7100a36 | MIT | yes |
| nezvers/Godot-GameTemplate | `nezvers__Godot-GameTemplate` | d5d8d1588742 | d5d8d15887423b3a8acf0502efb6271c600a80bc | MIT | yes |
| lampe-games/godot-open-rts | `lampe-games__godot-open-rts` | a628ad3bb6a9 | a628ad3bb6a9a903587a181a7ee3300dbf735e81 | MIT | yes |
| Miziziziz/MizGodotTools | `Miziziziz__MizGodotTools` | cb548f9035a3 | **absent (`null`)** | MIT | yes |

## 6. Differences from the historical baseline

None material. Counts (14 analyses, 65 linkages, 5 projections, 31 features) reproduce the
Batch B baseline exactly; catalog/reference/source counts agree with the historical
figures (7,270 / 6,813 / 77 repositories). No existing modification was overwritten.

## 7. Preflight verdict

Proceed to Stage B. Gate, parser, schema and linkage tooling are intact and usable; the
only run-time adjustment is supplying complete pinned metadata at analysis time.
