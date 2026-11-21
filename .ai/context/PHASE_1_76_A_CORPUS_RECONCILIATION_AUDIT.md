# Phase 1.76 — Batch A
# External Analysis Corpus Reconciliation Audit

Read-only audit of the whole External Analysis corpus against the Phase 1.75
hardened parser. One artefact was written:
`.ai/learning/external_code/reconciliation/phase_1.76/inventory.json`
(produced by `.ai/tools/external_code/corpus_audit_176.py`).

No analysis record, linkage record, candidate, projection, Feature metadata,
index or graph was written. `git status` shows 0 deletions and no staged change.

---

## A. Current Baseline

| Item | Value |
|---|---|
| Project root | `F:/Godot_v4.7-stable/game` |
| Branch / HEAD | `master` / `d64b1cd5b576a44dcfafd7becbb2d2a7f1fd6a84` (unchanged since Phase 1.75) |
| Staged | 0 |
| Modified | 34 (33 pre-existing + `gd_parse.py` from Phase 1.75) |
| Untracked | 137 porcelain entries (Phase 1.75 additions included) |
| Deleted | 0 |
| External analysis records | 34 |
| Feature linkage records | 150 (150 FRESH) |
| Candidates | 2 (`cand-08fdc0b10a112ecf`, `cand-7f52cb8f583124db`), 2 VALID / 2 FRESH |
| Feature metadata | 31, 0 errors / 0 warnings |
| Phase 1.75 workspace | present, generated with parser `1.75`, `official_analysis_overwritten: false` |

Baseline test suite re-run for this audit (all exit 0):

| Command | Exit | Result |
|---|---|---|
| `python .ai/tools/learning/tests/test_gd_parse.py` | 0 | 35 checks, 0 failures |
| `python .ai/tools/learning/tests/test_source_analysis.py` | 0 | 17 checks, 0 failures |
| `python .ai/tools/external_code/tests/test_batch_a.py` | 0 | 38 checks |
| `python .ai/tools/external_code/tests/test_batch_b.py` | 0 | 33 checks |
| `python .ai/tools/external_code/tests/test_feature_linkage.py` | 0 | 70 tests OK |
| `python .ai/tools/feature_registry/tests/test_feature_evidence_projection.py` | 0 | 41 tests OK |
| `python .ai/tools/validator/check_feature_metadata.py` | 0 | 31 features, 0/0 |
| `python .ai/tools/external_code/feature_linkage.py check --pilot` | 0 | FRESH=150 STALE=0 MISSING_SOURCE=0 INVALID=0 |
| `python .ai/tools/external_code/corpus_audit_176.py` | 0 | 34 records inventoried |

The Phase 1.75 historical figure "34 records / 4 reanalysed / ~21 would gain
symbols / 6 status changes" is **confirmed at 34 / 4**, while the projected
change counts remain a read-only estimate that Batch B must re-measure (Stage A5
scope is 29 records, broader than the 21 estimated to gain symbols, because
records that gain no symbol can still gain coverage metadata, annotations or
location detail).

---

## B. External Analysis Inventory

Aggregates: **34 records**, **12 repositories**, **12 full commits**, **34
distinct source paths**, **34 distinct identity tuples**
(`repo + full_commit + source_path + source_digest`), **0 duplicates**, **0
ambiguous identities**, 173 symbols total, 150 linkages attached.

| Missing metadata | Count |
|---|---:|
| Missing provenance (`repo`/commit/path/url) | 0 |
| Missing `source_digest` | 0 |
| Missing `input_digest` | 0 |
| Missing `parser_version` | 0 (all `1.71`) |
| Missing coverage metadata | 34 (`NOT_RECORDED`, expected: schema 1 predates Phase 1.75 fields) |
| Location integrity `LOCATION_INCOMPLETE` | 0 (173 reported symbol lines verified against the reference copies) |

File types: 33 `gdscript`, 1 `gdshader`. Schema: all `external_code_analysis`
version `1`. Provenance: `complete` for 34/34. License: 30 `eligible`, 4
`license_text_missing`, `copy_allowed = true` for all 34.

### B.1 Per-record inventory

`sym` = captured symbols (functions+signals+exports+variables+constants+
properties), `lnk` = existing linkage records.

| analysis_id | repository | source_path | sym | lnk | record status | disposition |
|---|---|---|---:|---:|---|---|
| `ext-1d204b35464cf388` | gdquest-demos/godot-make-pro-2d-games | `actors/health/Stats.gd` | 9 | 5 | analysis_partial | REANALYZED_VALID |
| `ext-23949c1378c49203` | bitbrain/beehave | `addons/beehave/blackboard.gd` | 8 | 5 | analysis_partial | REANALYZED_VALID |
| `ext-73c80a3db6d71e48` | nezvers/Godot-GameTemplate | `addons/top_down/scripts/damage/HealthResource.gd` | 13 | 5 | analysis_complete | REANALYZED_VALID |
| `ext-ab693f3d6ef9439c` | lampe-games/godot-open-rts | `source/match/units/traits/HealthBar.gd` | 8 | 0 | analysis_partial | REANALYZED_VALID |
| `ext-27ddd863881677d7` | bitbrain/beehave | `addons/beehave/nodes/leaves/blackboard_set.gd` | 2 | 5 | analysis_partial | REQUIRES_REANALYSIS |
| `ext-2a4f612899a6b6a5` | gdquest-demos/godot-make-pro-2d-games | `actors/hit_box/HitBox.gd` | 3 | 5 | analysis_partial | REQUIRES_REANALYSIS |
| `ext-409141da889d20af` | nezvers/Godot-GameTemplate | `addons/top_down/scripts/damage/ActorDamage.gd` | 12 | 5 | analysis_complete | REQUIRES_REANALYSIS |
| `ext-40ab1c0330e01d7f` | alfredbaudisch/Godello | `scripts/drag_utils.gd` | 3 | 5 | analysis_complete | REQUIRES_REANALYSIS |
| `ext-43748f09c01294f9` | gdquest-demos/godot-open-rpg | `field/cutscenes/templates/doors/door_trigger.gd` | 3 | 0 | analysis_partial | REQUIRES_REANALYSIS |
| `ext-4b7782ce66be92a7` | alfredbaudisch/Godello | `addons/uuid/uuid.gd` | 4 | 5 | analysis_complete | REQUIRES_REANALYSIS |
| `ext-51d46c1b4943a254` | gdquest-demos/godot-open-rpg | `src/field/cutscenes/templates/doors/door.gd` | 4 | 5 | analysis_partial | REQUIRES_REANALYSIS |
| `ext-51fbb1e2b03c3f67` | ceceppa/anima | `addons/anima/motion/runtime/anima_race_instance.gd` | 4 | 5 | analysis_complete | REQUIRES_REANALYSIS |
| `ext-55aef2d453370c1b` | bitbrain/beehave | `addons/beehave/nodes/leaves/blackboard_compare.gd` | 2 | 5 | analysis_partial | REQUIRES_REANALYSIS |
| `ext-56ca48126ec8514d` | alfredbaudisch/Godello | `scripts/events.gd` | 8 | 5 | analysis_partial | REQUIRES_REANALYSIS |
| `ext-5a8d53c7f530e4af` | gdquest-demos/godot-open-rpg | `src/overworld/maps/town/door_unlock_interaction.gd` | 1 | 0 | analysis_partial | REQUIRES_REANALYSIS |
| `ext-5adc6644d3347390` | Ark2000/PankuConsole | `addons/panku_console/modules/interactive_shell/mini_repl_2.gd` | 4 | 5 | analysis_partial | REQUIRES_REANALYSIS |
| `ext-6f85edf0730ee075` | gdquest-demos/godot-make-pro-2d-games | `core/world/Door.gd` | 4 | 5 | analysis_partial | REQUIRES_REANALYSIS |
| `ext-7973e94ee75e2819` | nezvers/Godot-GameTemplate | `addons/top_down/scripts/actor/bots/ProximityAttack.gd` | 8 | 5 | analysis_complete | REQUIRES_REANALYSIS |
| `ext-7d7933a2343f52d0` | gdquest-demos/godot-open-rpg | `src/combat/ui/battler_entry/ui_life_bar.gd` | 4 | 5 | analysis_complete | REQUIRES_REANALYSIS |
| `ext-80c1104f5262a6ee` | Ark2000/PankuConsole | `addons/panku_console/res/shader/simple_fast_blur.gdshader` | 0 | 0 | unsupported_shader | NOT_APPLICABLE |
| `ext-9e62ed2e3dec8164` | alfredbaudisch/Godello | `scripts/board_member_button.gd` | 8 | 5 | analysis_partial | REQUIRES_REANALYSIS |
| `ext-9f0aad5e01dd71f7` | gdquest-demos/godot-make-pro-2d-games | `interface/gui/player/life_bar/Lifebar.gd` | 4 | 5 | analysis_partial | REQUIRES_REANALYSIS |
| `ext-aa0204cc227b0480` | derkork/godot-statecharts | `addons/godot_state_charts/animation_tree_state.gd` | 4 | 5 | analysis_partial | REQUIRES_REANALYSIS |
| `ext-bfe9b7e6dbebbfae` | blackears/cyclopsLevelBuilder | `addons/cyclops_level_builder/actions/cyclops_action.gd` | 5 | 5 | analysis_partial | REQUIRES_REANALYSIS |
| `ext-c341755c352c7563` | lampe-games/godot-open-rts | `source/match/units/actions/AutoAttacking.gd` | 10 | 5 | analysis_partial | REQUIRES_REANALYSIS |
| `ext-c7b0d12daf86d973` | gdquest-demos/godot-make-pro-2d-games | `actors/DamageSource.gd` | 2 | 5 | analysis_partial | REQUIRES_REANALYSIS |
| `ext-d5f7ac2db3a8c4e4` | gdquest-demos/godot-open-rpg | `src/combat/actions/battler_action_attack.gd` | 1 | 5 | analysis_complete | REQUIRES_REANALYSIS |
| `ext-d82bd2e536c75c4a` | nezvers/Godot-GameTemplate | `addons/top_down/scripts/ui/game_screen/HealthPanel.gd` | 12 | 5 | analysis_complete | REQUIRES_REANALYSIS |
| `ext-d9764c3981017194` | gdquest-demos/godot-make-pro-2d-games | `actors/health/Status.gd` | 7 | 5 | analysis_partial | REQUIRES_REANALYSIS |
| `ext-ec789727924bfa6c` | foxssake/netfox | `examples/forest-brawl/scripts/play-random-3d.gd` | 2 | 5 | analysis_complete | REQUIRES_REANALYSIS |
| `ext-f80d07f302bacc20` | cis-ash/TEXTREME | `addons/effect_parameter_selector/EffectParameterSelector.gd` | 4 | 5 | analysis_complete | REQUIRES_REANALYSIS |
| `ext-fb806b579659b155` | foxssake/netfox | `addons/state-machine/scripts/character-states/Idle.gd` | 4 | 5 | analysis_partial | REQUIRES_REANALYSIS |
| `ext-fe3acf782b88edda` | Ark2000/PankuConsole | `addons/panku_console/modules/history_manager/env.gd` | 2 | 5 | analysis_partial | REQUIRES_REANALYSIS |
| `ext-fffa637657ffede1` | alfredbaudisch/Godello | `scripts/board_card.gd` | 4 | 5 | analysis_partial | REQUIRES_REANALYSIS |

Disposition totals: `REANALYZED_VALID` 4 · `REQUIRES_REANALYSIS` 29 ·
`NOT_APPLICABLE` 1 · `SOURCE_CHANGED` 0 · `SOURCE_MISSING` 0 ·
`PROVENANCE_INCOMPLETE` 0 · `DUPLICATE_OR_AMBIGUOUS` 0.

No two records share an identity tuple; no source path appears under two commits
inside this corpus, so each record keeps its own identity (nothing was merged by
filename).

---

## C. Phase 1.75 Reanalysis Matching

Matching used the stable identity tuple only (repository + full commit SHA +
source path + source digest); filenames were never used as the key.

| Original | Reanalysis | New parser | Digest same | Provenance verified | Locations | Verdict |
|---|---|---|---|---|---|---|
| `ext-1d204b35464cf388` (Stats.gd) | `ext-0ee947aef4c9aeca` | 1.75 | ✔ | ✔ | 11/11 | `REANALYZED_VALID` |
| `ext-23949c1378c49203` (blackboard.gd) | `ext-d0a93201b6f352df` | 1.75 | ✔ | ✔ | 11/11 | `REANALYZED_VALID` |
| `ext-73c80a3db6d71e48` (HealthResource.gd) | `ext-8759bb47cb020625` | 1.75 | ✔ | ✔ | 17/17 | `REANALYZED_VALID` |
| `ext-ab693f3d6ef9439c` (HealthBar.gd) | `ext-322df918a5ebee02` | 1.75 | ✔ | ✔ | 13/13 | `REANALYZED_VALID` |

All four satisfy the reuse condition: parser version equals the current build
(`1.75`), `source_digest` in the new record equals the original, provenance
fields are identical, and no location problem was recorded. **They will be
reused, not recomputed**, in Batch B.

The corpus is therefore 4/34 aligned (11.8 %). Every remaining record is either
`REQUIRES_REANALYSIS` (29) or `NOT_APPLICABLE` (1) — no record is ambiguously
classified.

---

## D. Parser Build Identity

The project has a declared parser version (`PARSER_VERSION = "1.75"` in the
adapter) but no formal "build identity". Batch A establishes one that is
repeatable and verifiable from file content, not invented:

```
identity       = gd_parse@1.75+build:6b74a6cd20a06033
identity_sha256= sha256(gd_parse.py bytes || 0x00 || external_code_understanding.py bytes)
gd_parse_sha256= d7593797923f2302…   (full digest in inventory.json)
adapter_sha256 = recorded alongside
declared_parser_version = 1.75
schema_version = 1
```

| Component | Value |
|---|---|
| Parser module | `.ai/tools/learning/gd_parse.py` |
| Adapter | `.ai/tools/external_code/external_code_understanding.py` |
| Declared version | `1.75` (Phase 1.75 Batch B) |
| Analysis schema | `external_code_analysis` v1, additive coverage keys |
| Declaration kinds | `VARIABLE` `PROPERTY` `FUNCTION` `CONSTANT` `SIGNAL` |
| Coverage fields | `parse_execution_status`, `syntax_coverage_status`, `analysis_completeness`, `unsupported_constructs`, `unrecognized_declarations`, `source_coordinates` |
| Backward read | old records load unchanged; missing coverage fields mean `NOT_RECORDED`, never COMPLETE |

Rules carried into Batch B: all new reanalysis records must carry this exact
identity; if either file digest changes between runs, Batch B stops instead of
mixing identities; historical `parser_version 1.71` is recorded as-is and is
**never** back-filled.

---

## E. Provenance Verification

Per record, the audit checked: repository present, full commit SHA present,
source path present, immutable source URL present, reference copy readable,
pinned source file readable.

| Check | Result |
|---|---:|
| `provenance_complete` | 34/34 |
| immutable `source_url` present | 34/34 |
| reference copy readable | 34/34 |
| pinned commit source file readable | 34/34 |
| license recorded | 34/34 (`eligible` 30, `license_text_missing` 4) |
| `copy_allowed` | true 34/34 |
| `provenance_status` | `complete` 34/34 |
| `commit_sha` short + `commit_sha_full` consistent | 34/34 |

The four `license_text_missing` records (`blackboard.gd`, `blackboard_set.gd`,
`blackboard_compare.gd`, `animation_tree_state.gd`) keep the status they already
had in Phase 1.73/1.75. Reanalysis is still permitted (they are read-only
analyses of an immutable public commit), but any *future* evidence qualification
from them must carry the existing license limitation. Batch B will not "upgrade"
their license state.

---

## F. Source Digest Verification

| Check | Result |
|---|---:|
| reference copy digest == recorded `input_digest` | 34/34 |
| pinned source digest == recorded `source_digest` | 34/34 |
| `SOURCE_CHANGED` dispositions | 0 |
| sources recovered from the recorded commit | 34/34 (via the collector's pinned `sources/<repo>/gd/<path>` tree) |

No record failed digest verification, so no record needs to be excluded for a
source change. No working-tree file was used in place of a historical commit
file: the audit only read the recorded `source_file_path` and `reference_path`
of each record and compared digests.

---

## G. Reanalysis Scope

Formal scope for Batch B: the **29** `REQUIRES_REANALYSIS` records, all of which
pass every preflight check above. They span all 12 repositories of the corpus
and two license states (26 `eligible`, 3 `license_text_missing`).

Phase 1.75's four records join the Batch B baseline as **reused** entries
(`REANALYZED_VALID`) with their existing `parser_version 1.75` data, so the
corpus baseline after Batch B covers **33 of 34** records on the identical
parser build identity.

Per-record expectation for Batch B (from Phase 1.75's read-only measurement,
to be re-measured and never assumed): ~21 records gain declarations, ~6 change
`analysis_status` (annotation interpretation), the rest change only by gaining
coverage metadata. Records that gain nothing are still written as
`REANALYZED` so the baseline has one parser identity.

---

## H. Excluded Records

| Record | Reason | Handling |
|---|---|---|
| `ext-80c1104f5262a6ee` (`PankuConsole`, `simple_fast_blur.gdshader`) | `file_type = gdshader`; the parser is GDScript-only and the adapter deliberately returns `unsupported_shader` with empty symbols | `NOT_APPLICABLE` — excluded from Batch B, remains on its original record with no reanalysis. It has 0 symbols and 0 linkages, so no evidence depends on it. |

No other record is excluded. Nothing is excluded for provenance, digest, license
or readability problems — those categories are empty, not suppressed.

---

## I. Data Integrity Risks

| Risk | Assessment | Control carried into Batch B |
|---|---|---|
| Coverage metadata absent on all 34 historical records | expected; schema predates the fields | new records carry it; historical records stay `NOT_RECORDED` (no bulk rewrite) |
| `analysis_id` changes with parser version (id includes `PARSER_VERSION`) | 29 records would get a new id | every new record keeps `original_analysis_id`; official records untouched |
| 6 records would change `analysis_status` (`partial → complete`) | label drift, not evidence drift | status change recorded per record in the diff, never written back |
| 21 records would gain symbols → linkage freshness could go STALE if recomputed | linkage must not be rebuilt in B | Batch B writes only to `reanalysis/parser_1.76/`; linkage check stays read-only until Batch C |
| `license_text_missing` (4 records, 3 in scope) | pre-existing limitation | carried verbatim; no license upgrade |
| Determinism | same digest + identity must give same content | Batch B must run twice and compare content digests (excluding timestamps) |
| Duplicate analysis records on rerun | idempotency | Batch B writes by `original_analysis_id` key and asserts one file per original |
| Shader record | parser cannot analyse it | documented exclusion, not a silent skip |

---

## J. Batch B Readiness

**Verdict: `READY_FOR_BATCH_B`**

Conditions satisfied and verified:

1. **Inventory complete** — 34/34 records enumerated with identity, digests,
   parser version, coverage status, symbol and linkage counts, and location
   integrity; 0 duplicates, 0 ambiguous identities.
2. **Phase 1.75 matching verified** — 4 records matched on the full identity
   tuple, all reusable with the current parser identity.
3. **Parser Build Identity defined and reproducible** —
   `gd_parse@1.75+build:6b74a6cd20a06033`, derived from file content digests.
4. **Provenance and digests verified for the entire scope** — 29/29 scope records
   pass; 0 `SOURCE_CHANGED`, 0 `SOURCE_MISSING`, 0 `PROVENANCE_INCOMPLETE`.
5. **Scope is explicit and per-record** — 29 reanalyze, 4 reuse, 1 not applicable;
   no record is "assumed done".
6. **No historical data was written** — inventory is the only new artefact;
   150/150 linkage FRESH, metadata 31/31 clean.

Restrictions Batch B must honour:

* reuse the 4 Phase 1.75 results; do not recompute or overwrite that workspace;
* exclude `ext-80c1104f5262a6ee` (shader);
* stop rather than proceed if any digest or the parser identity changes at run
  time, and report `PARSER_DEFECT_FOUND` instead of patching the parser mid-batch;
* keep the 4 `license_text_missing` records' license state unchanged.
