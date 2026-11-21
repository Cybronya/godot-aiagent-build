# Phase 1.76 — Batch B
# Controlled Full Reanalysis

Workspace: `.ai/learning/external_code/reanalysis/parser_1.76/` (162 files)
Tool: `.ai/tools/external_code/reanalysis_176.py` (`build` / `idempotency` / `validate`)
Inventory authority: `.ai/learning/external_code/reconciliation/phase_1.76/inventory.json` (unmodified)

Everything below was measured in this run; no figure is copied from Batch A.

---

## A. Executive Summary

All 34 External Analysis records now have exactly one final processing result:

| Status | Count |
|---|---:|
| `REANALYZED_AND_VALIDATED` | 29 |
| `REUSED_PHASE_1_75` | 4 |
| `NOT_APPLICABLE` (shader) | 1 |
| `REQUIRES_MANUAL_ANALYSIS_VALIDATION` | 0 |
| `SOURCE_INTEGRITY_FAILED` / `REANALYSIS_FAILED` / `PARSER_DEFECT_FOUND` | 0 |

The 29 reanalysed records used one Parser Build Identity
(`gd_parse@1.75+build:6b74a6cd20a06033`, recomputed from the current files and
equal to Batch A's). Symbols went from 135 to 179 across those 29 records:
**134 matched + 1 reclassified + 0 removed = 135**, and
**134 matched + 1 reclassified + 44 genuinely new = 179** (see §K.1; the diff's
"45 added" listing includes the reclassified symbol, so 45 − 1 = 44 new).
Coverage metadata now exists for all 29: 26 `COMPLETE` / 3 `PARTIAL` (enum,
legacy `setget`), 29 `FULL` declaration completeness, 0
`unrecognized_declarations`.

Execution success and syntax coverage are different outcomes and are reported
separately: 29/29 records were parsed and validated, but only 26/29 have complete
syntax coverage. The final verdict is therefore **`PASS_WITH_LIMITATIONS`**
(§W), not `PASS`.

Determinism: 29/29 records produced identical canonical content on a second
in-memory analysis. Idempotency: a second full workspace build produced 162 → 162
files, no new/removed files, identical normalised content for all 92 compared
JSON artefacts, stable record ids, 0 duplicates.

Data integrity: the 225-file formal artefact snapshot (34 analysis, 150 linkage,
2 candidates, Phase 1.75 workspace, Batch A inventory, feature index/graph, seed
policy, parser, adapter, tools) is byte-identical before and after.

---

## B. Baseline

| Item | Start | End |
|---|---|---|
| Branch / HEAD | `master` / `d64b1cd5b576a44dcfafd7becbb2d2a7f1fd6a84` | unchanged |
| Staged | 0 | 0 |
| Modified | 34 | 34 |
| Untracked | 137 | 138 (+1 new tool) |
| Deleted | 0 | 0 |
| External analysis | 34 | 34 (unchanged) |
| Linkage | 150 FRESH | 150 FRESH |
| Candidates | 2 VALID / 2 FRESH | 2 VALID / 2 FRESH |
| Feature metadata | 31, 0 errors | 31, 0 errors |

No git write command was issued (`status`, `rev-parse`, `diff --cached` only).

---

## C. Parser Build Identity Verification

```
identity        = gd_parse@1.75+build:6b74a6cd20a06033   (recomputed)
expected        = gd_parse@1.75+build:6b74a6cd20a06033   (Batch A)
identity_match  = true
```

| Component | Value |
|---|---|
| `gd_parse_sha256` | `d7593797923f2302…` (full digest in `preflight.json`) |
| `adapter_sha256` | recorded in `preflight.json` |
| Declared parser version | `1.75` |
| Schema | `external_code_analysis` v1 |
| Coverage fields | `parse_execution_status`, `syntax_coverage_status`, `analysis_completeness`, `unsupported_constructs`, `unrecognized_declarations`, `source_coordinates` |
| Analysis configuration | unchanged (same entry points, same adapter options) |

Neither parser file was modified in this batch (they appear in the formal
snapshot with identical digests before and after).

---

## D. Inventory Integrity

| Check | Result |
|---|---|
| Inventory digest recorded | `preflight.json → inventory_digest` |
| Records in inventory | 34 |
| `REQUIRES_REANALYSIS` | 29 ✔ |
| `REANALYZED_VALID` | 4 ✔ |
| `NOT_APPLICABLE` | 1 ✔ |
| Per-record identity re-verified against the record file (repo, full commit, path, digest) | 29/29 consistent |
| Inventory file modified | no (digest identical at the end) |

The scope was taken from the inventory, not redefined.

---

## E. Reanalysis Scope

29 records across 12 repositories, 26 `license_status=eligible` + 3
`license_text_missing`. Every one passed the preflight (reference copy digest ==
`input_digest`, pinned source digest == `source_digest`, provenance complete,
commit full SHA present).

Largest deltas: `ui_life_bar.gd` 8 listed (7 new + 1 reclassified), `door.gd` +5, `blackboard_compare.gd` +5,
`blackboard_set.gd` +4, `AutoAttacking.gd` +3, `battler_action_attack.gd` +3.

---

## F. Provenance Verification

For each of the 29: `provenance_preserved = true`, i.e. the new record's
`repo`, `commit_sha`, `commit_sha_full`, `source_path`, `source_url`,
`license`, `license_status`, `license_text_present`, `license_source`,
`provenance_status`, `input_digest`, `source_digest`, `file_type` all equal the
original record's. `licence_preserved = true` for 29/29 — the 3
`license_text_missing` records stayed `license_text_missing`, `copy_allowed`
unchanged; nothing was inferred or upgraded.

---

## G. Source Digest Verification

| Check | Result |
|---|---:|
| reference copy digest == `input_digest` | 29/29 |
| pinned commit source digest == `source_digest` | 29/29 |
| source read from the recorded commit tree (`sources/<repo>/gd/<path>`) | 29/29 |
| working-tree or default-branch file used | 0 |
| `SOURCE_INTEGRITY_FAILED` | 0 |

---

## H. Reanalysis Execution Results

| Metric | Value |
|---|---:|
| Records reanalysed | 29 |
| `parse_execution_status = PARSED` | 29 |
| `analysis_completeness = FULL` | 29 |
| `syntax_coverage_status = COMPLETE` | 26 |
| `syntax_coverage_status = PARTIAL` | 3 |
| Records with `unsupported_constructs` | 3 |
| Records with `unrecognized_declarations` | 0 |
| Parser failures | 0 |
| New analysis ids | 29 (derived from parser version + input digest) |

Each new record keeps `original_analysis_id`, the full provenance tuple, the
parser build identity, schema version, coverage block, symbols and source
locations; `reanalyzed/<original_id>.json` mirrors the record 1:1 so a reviewer
can diff originals without touching the official tree.

---

## I. Phase 1.75 Reuse Validation

| Original | Reanalysis | Parser | Digest | Provenance | Symbols re-located | Offset | Problems | Status |
|---|---|---|---|---|---|---:|---:|---|
| `ext-1d204b35464cf388` (Stats.gd) | `ext-0ee947aef4c9aeca` | 1.75 | ✔ | ✔ | 11 | 3 | 0 | `REUSED_PHASE_1_75` |
| `ext-23949c1378c49203` (blackboard.gd) | `ext-d0a93201b6f352df` | 1.75 | ✔ | ✔ | 11 | 3 | 0 | `REUSED_PHASE_1_75` |
| `ext-73c80a3db6d71e48` (HealthResource.gd) | `ext-8759bb47cb020625` | 1.75 | ✔ | ✔ | 17 | 3 | 0 | `REUSED_PHASE_1_75` |
| `ext-ab693f3d6ef9439c` (HealthBar.gd) | `ext-322df918a5ebee02` | 1.75 | ✔ | ✔ | 13 | 3 | 0 | `REUSED_PHASE_1_75` |

The Phase 1.75 numbers 11/11/17/13 were **recomputed** here from the pinned
commit files (`validate_reuse` re-reads both copies and re-checks every symbol
line), not copied. The parser was not executed again for these four, no new
analysis id was generated, and the Phase 1.75 workspace was not modified (its
29 files are in the formal snapshot and unchanged).

---

## J. Shader Exclusion

`ext-80c1104f5262a6ee` — `PankuConsole/…/simple_fast_blur.gdshader`

| Check | Value |
|---|---|
| `file_type` | `gdshader` |
| Symbols | empty (0 in every group) |
| Linkage records | 0 |
| GDScript parser executed | no |
| Manifest status | `NOT_APPLICABLE` with `exclusion_reason` |
| Original record | untouched |

No synthetic GDScript analysis was produced for it.

---

## K. Analysis Diff Summary

Per-record diffs are in `diff/<original_analysis_id>.json`, each containing:
original/new ids, parser identity, source identity, added/removed/reclassified
symbols, symbol counts before/after, coverage old(`NOT_RECORDED`)/new, analysis
status, unsupported/unrecognized items, location offset plus problems, and
`unexplained_differences`.

Aggregate over the 29 records:

| Symbol group | Before | After | Δ |
|---|---:|---:|---:|
| functions | 86 | 86 | 0 |
| signals | 13 | 13 | 0 |
| exports | 19 | 31 | **+12** |
| variables | 12 | 38 | **+26** |
| constants | 5 | 7 | **+2** |
| properties | 0 | 4 | **+4** |
| **total** | **135** | **179** | **+44** |

Added declarations as listed in the diffs: 45 entries = 27 `VARIABLE`,
12 exported `VARIABLE`, 4 `PROPERTY`, 2 `CONSTANT`. One of those 45 is the new
side of a reclassification (below), so the net symbol count rises by 44.

### K.1 Symbol Diff Accounting Audit (recomputed from workspace data)

Recalculated directly from the 29 original records and the 29 reanalysis records
with identity `(group, name)`, plus a name-level pass for structural changes.
Nothing from the earlier summary was reused.

| Metric | Recomputed value |
|---|---:|
| Original symbols (29 records) | 135 |
| Reanalysis symbols (29 records) | 179 |
| Matched (same group + same name) | 134 |
| Genuinely added (no counterpart by name in the original) | 44 |
| Removed (no counterpart by name in the reanalysis) | 0 |
| Structurally reclassified (same name + same line, different group) | 1 |
| Diff-listed additions (`symbols_added` entries) | 45 = 44 new + 1 reclassified |
| Net change | +44 |

Recomputable identities (all three hold on the actual data):

```
Original  = Matched + Reclassified + Removed      135 = 134 + 1 + 0
Reanalysis= Matched + Reclassified + Added        179 = 134 + 1 + 44
Net change= Added - Removed                         44 = 44 - 0
Listed additions = Added + Reclassified              45 = 44 + 1
```

So the earlier table was arithmetically consistent but its column headings mixed
two different counting bases: `Added = 45` was a *listing* count (new-side
entries in the diff), while `Net change = +44` was a *net symbol* count. The
corrected presentation is the table above: 44 genuinely new symbols, 1
reclassification, 0 removals.

Per-record check: for every one of the 29 records
`|original| + added − removed == |reanalysis|` and
`|matched| + reclassified == |original|`, with the only non-trivial record being
`ext-7d7933a2343f52d0` (`ui_life_bar.gd`, 4 → 11 symbols: 3 matched +
1 reclassified + 7 new; its diff lists 8 additions because the reclassified
`target_value` appears on the new side too).

**Accounting status: `SYMBOL_DIFF_ACCOUNTING_RESOLVED`** — no diff data and no
manifest field was changed; only this report's presentation was corrected.

### K.2 Structural Reclassification: `ui_life_bar.gd::target_value`

| Aspect | Original (`ext-7d7933a2343f52d0`) | Reanalysis (`parser_1.76`) |
|---|---|---|
| Identity | `variables:target_value` | `properties:target_value` |
| `declaration_kind` | absent (pre-1.75 schema) | `PROPERTY` |
| Line | 18 | 18 |
| Value | `"0.0:"` (property colon absorbed into the value) | `"0.0"` |
| Getter / setter | none recorded | `has_setter = true`, `has_getter = false` |
| Setter location | not recorded | record line 19 (commit line 16), `param = new_value`, `end_line = 37` |
| Diff classification | appears in `symbols_removed`? **no** — in `symbols_reclassified` | appears in `symbols_added` as `properties` |
| Removed count | — | **0** (not counted as a loss) |
| Unexplained differences | — | **[]** |

Source (reference copy line 18): `var target_value := 0.0:` followed by
`set(new_value):` on line 19. The old parser merged the trailing property colon
into the value and could not see the setter; the hardened parser records the
declaration as a property with a real setter range. Classification rule used by
the diff: *same name and same line in a different group = reclassification*, so
it is counted once in the reclassification dimension and once on the new side of
`symbols_added`, never in `symbols_removed`.

**No symbol disappeared.** `symbols_removed = 0` in all 29 diffs, and
`symbols_reclassified = 1`:

| Record | Symbol | From | To | Detail |
|---|---|---|---|---|
| `ext-7d7933a2343f52d0` (`ui_life_bar.gd`) | `target_value` (line 18) | `variables` (value `"0.0:"`) | `properties` (value `"0.0"`, `has_setter=true`) | same name and line; the old parser merged the property colon into the value and could not see the setter. Not a loss — a structural correction. |

Coverage status changes (old record had no coverage field; this compares
`analysis_status`):

| Record | Source | Old | New |
|---|---|---|---|
| `ext-27ddd863881677d7` | `blackboard_set.gd` | partial | complete |
| `ext-51d46c1b4943a254` | `door.gd` | partial | complete |
| `ext-55aef2d453370c1b` | `blackboard_compare.gd` | partial | complete |
| `ext-aa0204cc227b0480` | `animation_tree_state.gd` | partial | complete |
| `ext-bfe9b7e6dbebbfae` | `cyclops_action.gd` | partial | complete |

All five moved because their only "hard limitation" was an annotation the
hardened parser now interprets (`@onready`/`@tool`/`@rpc`). No classification,
score or evidence was touched.

---

## L. Symbol Integrity

* Identity matching used group + name + line (+ type/value for change
  detection); a same-name symbol in a different group is reported as a
  reclassification, never silently merged.
* Added declarations were checked for fabricated types: where the source has no
  annotation (e.g. `var danger_cutoff: = 0.2`, `var _bar_anim: = $BarAnimation`)
  the record stores `type: ""` — 0 inferred types.
* No `Function ⇄ Property` confusion: functions stayed 86 → 86 with identical
  names, parameters, returns and lines; all 4 new properties have real setter
  blocks.
* `unrecognized_declarations = 0` everywhere: a blind re-scan of every
  top-level declaration-shaped line in all 29 sources found **0 unaccounted
  declarations** (each line is either captured or reported as an unsupported
  construct).
* 3 records carry explicit `unsupported_constructs`: `blackboard_compare.gd`
  (`ENUM_NOT_INTERPRETED`), `board_member_button.gd` (2×
  `LEGACY_SETGET_NOT_INTERPRETED`), `board_card.gd`
  (`LEGACY_SETGET_NOT_INTERPRETED`). These are reported, not hidden, and are the
  reason those 3 records are `PARTIAL`.
* `REQUIRES_MANUAL_ANALYSIS_VALIDATION`: 0.

---

## M. Source Location Validation

* Offset per record is **derived** by aligning the analysed (references) copy with
  the pinned commit copy — never assumed. All 29 derived `offset = 3`, matching
  the documented 3-line provenance header; the 4 reused records also derive 3.
* 179 symbols in the 29 new records plus 52 in the reused 4 = **231 symbols**
  verified twice: the record line must contain the symbol name, and the commit
  line (`record_line − offset`) must contain it too.
* Accessor ranges are checked to point at `get:`/`set(` lines; `end_line ≥ line`
  is enforced.
* Result: `LOCATION_INCOMPLETE = 0`, location problems = 0, `LOCATION` mismatches
  requiring manual review = 0.

---

## N. Coverage Metadata

| Field | Distribution |
|---|---|
| `parse_execution_status` | `PARSED` 29 |
| `syntax_coverage_status` | `COMPLETE` 26, `PARTIAL` 3 |
| `analysis_completeness` | `FULL` 29 |
| `unsupported_constructs` | 3 records (1 enum, 3 legacy-setget occurrences) |
| `unrecognized_declarations` | 0 |
| `source_coordinates` | `ANALYZED_FILE` |

Historical records keep `NOT_RECORDED` for all coverage fields — nothing was
bulk-relabelled, and absence is never read as COMPLETE.

### N.1 The three status fields mean different things

| Field | Question answered | Value in this batch |
|---|---|---|
| `parse_execution_status` | did the scan run to completion? | `PARSED` 29 — the parser never aborted |
| `syntax_coverage_status` | was every construct in the file inside the supported grammar? | `COMPLETE` 26 / `PARTIAL` 3 — 3 files contain constructs the grammar does not model |
| `analysis_completeness` | was every *declaration-shaped* line either captured or explicitly reported? | `FULL` 29 — no silent gaps, 0 `unrecognized_declarations` |

Consequences that must not be blurred:

* `PARSED` ≠ complete coverage. All 29 ran; 3 are still `PARTIAL`.
* `FULL` ≠ `COMPLETE`. In the 3 `PARTIAL` files, declarations written in legacy
  3.x `export(...) var … setget` form are **not captured at all**; they are
  reported through `unsupported_constructs` instead, which is why
  `analysis_completeness` stays `FULL` (nothing was silently dropped) while
  `syntax_coverage_status` is `PARTIAL` (the grammar does not model them).
  For those files the symbol table is therefore *not* a complete declaration list.

### N.2 The three `PARTIAL` records

| Record | Repository | Commit | Source path | Unsupported constructs | Effect |
|---|---|---|---|---|---|
| `ext-55aef2d453370c1b` | `bitbrain/beehave` | `fe589153fa780a3f88989578ceb5f539afffb7c2` | `addons/beehave/nodes/leaves/blackboard_compare.gd` | `ENUM_NOT_INTERPRETED` line 10 (`Operators`) | enum name/line reported, **members not captured**; the rest of the file parsed normally |
| `ext-9e62ed2e3dec8164` | `alfredbaudisch/Godello` | `4458a143644fbadec23ae0cee99578ad3b811eb8` | `scripts/board_member_button.gd` | 2 × `LEGACY_SETGET_NOT_INTERPRETED` lines 9, 10 | the two legacy `export(...)` variables (with `setget`) are **not** in `symbols`; reported as unsupported |
| `ext-fffa637657ffede1` | `alfredbaudisch/Godello` | `4458a143644fbadec23ae0cee99578ad3b811eb8` | `scripts/board_card.gd` | 1 × `LEGACY_SETGET_NOT_INTERPRETED` line 7 | one legacy `export(...)` variable **not** captured; reported as unsupported |

No unsupported construct was repaired in this batch, and none was hidden: each
one appears in the record's `unsupported_constructs` with its line, which is why
these three records are `PARTIAL` rather than `COMPLETE`.

---

## O. Determinism Verification

Method: each of the 29 inputs was analysed twice from scratch in the same run
(`ext.analyze_external_code` on the same reference copy), and both results were
canonicalised (sorted keys, volatile run metadata removed: `created_at`,
`generated_at`, `reanalysis_timestamp`, `reanalysis_run`, `executed_at`,
`duration_ms`) before comparing digests. List order is preserved because parser
output order is semantic.

| Metric | Value |
|---|---:|
| Records compared | 29 |
| Identical canonical digest | 29 |
| Differing fields | 0 |
| `NON_DETERMINISTIC` | 0 |

Evidence: `deterministic_runs/<analysis_id>.json` (run1 digest, run2 digest,
`identical: true`, ignored fields listed).

---

## P. Idempotency Verification

A second full build was executed into the same workspace (no output isolation
needed because the build is a pure function of inventory + sources + parser).

| Metric | Value |
|---|---:|
| Workspace files before / after | 162 / 162 |
| New files | 0 |
| Removed files | 0 |
| JSON artefacts compared by normalised content | 92 |
| Records with changed content | 0 |
| Duplicate analysis ids | 0 |
| Duplicate manifest entries | 0 |
| Record ids stable | true |
| Official snapshot unchanged | true |
| Byte-changed files | only those embedding a timestamp (`manifest.json`, `preflight.json`, `reanalyzed/*.json` `created_at`, `idempotency/run_primary.json`) — normalised content identical |

Evidence: `idempotency/verification.json`. The Phase 1.75 workspace and the
Batch A inventory were not written (checked by digest).

---

## Q. Reanalysis Manifest

`manifest.json` holds, for every one of the 34 records:
`analysis_id`, `repository`, `full_commit_sha`, `source_path`, `source_digest`,
`input_digest`, `original_analysis_ref`, `reanalysis_ref`, `reanalysis_id`,
`diff_ref`, `parser_build_identity`, `processing_status`, `validation_status`,
`exclusion_reason`, plus (for reanalysed records) `symbols_added`,
`symbols_removed`, `symbols_reclassified`, `symbol_counts`,
`parse_execution_status`, `syntax_coverage_status`, `analysis_completeness`,
`unsupported_constructs`, `unrecognized_declarations`, `deterministic`,
`location_integrity`.

Summary (recomputable from the manifest alone):

| Statistic | Value |
|---|---:|
| Total records | 34 |
| Reanalysed (executed) | 29 |
| Reanalysed and validated | 29 |
| Reused (`REUSED_PHASE_1_75`) | 4 |
| Not applicable | 1 |
| Requires manual analysis validation | 0 |
| Failed | 0 |
| Parser defect found | 0 |
| Source integrity failed | 0 |
| Non-deterministic | 0 |
| Symbols added / removed / reclassified | 45 / 0 / 1 |
| Records with status change | 5 |
| Records with unsupported constructs | 3 |
| Records with unrecognized declarations | 0 |
| New symbol total (29 records) | 179 |

`34/34 reconciled` — and `29/29 of the executed records validated`; the four
reused and one excluded record are accounted for explicitly, not counted as
reanalysis.

---

## R. Formal Data Integrity

Snapshot: **225 files** (34 official analysis, 150 linkage, 2 candidate drafts,
29 Phase 1.75 workspace files, Batch A inventory, `candidate_workspace/WORKSPACE.json`,
`external_code/index.json`, `feature_index.json`, `feature_graph.json`,
`candidate_seed_policy.json`, `gd_parse.py`, `external_code_understanding.py`,
`corpus_audit_176.py`, `reanalysis_175.py`).

| Expectation | Result |
|---|---|
| Official analysis modified | 0 |
| Linkage modified | 0 |
| Candidates modified | 0 |
| Feature metadata / index / graph modified | 0 |
| Phase 1.75 workspace modified | 0 |
| Batch A inventory modified | 0 |
| Parser / adapter modified | 0 |
| Deleted files | 0 |
| Files added outside the workspace | 1 tool + 1 report |

`manifest.json → summary.official_files_changed = []`, `official_files_added = []`.

---

## S. Tests & Regression

| Command | Exit | Observed result |
|---|---|---|
| `python .ai/tools/learning/tests/test_gd_parse.py` | 0 | 35 checks, 0 failures, 0 skipped |
| `python .ai/tools/learning/tests/test_source_analysis.py` | 0 | 17 checks, 0 failures |
| `python .ai/tools/external_code/tests/test_batch_a.py` | 0 | 38 checks |
| `python .ai/tools/external_code/tests/test_batch_b.py` | 0 | 33 checks |
| `python .ai/tools/external_code/tests/test_feature_linkage.py` | 0 | 70 tests OK |
| `python .ai/tools/feature_registry/tests/test_feature_evidence_projection.py` | 0 | 41 tests OK |
| `python .ai/tools/feature_registry/tests/test_feature_pipeline.py` | 0 | 21 checks |
| `python .ai/tools/feature_registry/tests/test_candidate_workspace.py` | 0 | 64 tests OK |
| `python .ai/tools/validator/check_feature_metadata.py` | 0 | 31 features, 0 errors, 0 warnings |
| `python .ai/tools/external_code/feature_linkage.py check --pilot` | 0 | FRESH=150 STALE=0 MISSING_SOURCE=0 INVALID=0 |
| `python .ai/tools/feature_registry/candidate_workspace.py validate` | 0 | 2 VALID, policy `phase-1.74-c/1` |
| `python .ai/tools/feature_registry/candidate_workspace.py check-freshness` | 0 | 2 FRESH, 0 STALE, 0 INCOMPLETE |
| `python .ai/tools/external_code/reanalysis_176.py build` | 0 | 29 validated, 0 failed, official drift 0 |
| `python .ai/tools/external_code/reanalysis_176.py idempotency` | 0 | content stable, 0 duplicates, official unchanged |
| `python .ai/tools/external_code/reanalysis_176.py validate` | 0 | workspace validation PASS, 34 records |

No test was skipped, weakened or re-run to hide a failure. Coverage scope of the
"OK" suites: `test_feature_linkage` exercises linkage build/check/freshness on
fixtures and the frozen pilot corpus; the projection suite exercises
`feature_evidence.py`; the pipeline suite exercises feature discovery/composition
end to end on fixtures.

---

## T. Files Changed

New (this batch):

| Path | Purpose |
|---|---|
| `.ai/tools/external_code/reanalysis_176.py` | required Batch B component: preflight, reanalysis, diff, validation, determinism, idempotency, manifest |
| `.ai/learning/external_code/reanalysis/parser_1.76/` (162 files) | `preflight.json`, `manifest.json`, `original/` 34, `reanalyzed/` 29, `diff/` 29, `validation/` 34, `deterministic_runs/` 29, `idempotency/` 2, `reports/` 3, `validation/workspace_validation.json` |
| `.ai/context/PHASE_1_76_B_CONTROLLED_FULL_REANALYSIS.md` | this report |

Modified: none. Deleted: none.

Pre-existing and untouched: the 33 previously modified files, `gd_parse.py`
(Phase 1.75), Phase 1.75 workspace, Batch A inventory and audit tool, all
official analysis/linkage/candidate/projection/metadata/index/graph files.

---

## U. Git Status

| | Start | End |
|---|---|---|
| Branch / HEAD | `master` / `d64b1cd5…` | `master` / `d64b1cd5…` |
| Staged | 0 | 0 |
| Modified | 34 | 34 |
| Untracked (porcelain) | 137 | 138 |
| Deleted | 0 | 0 |

These counts were taken before this report file and the finalization patch were
written; the measured total after the report-only finalization is **140**
untracked entries (see `PHASE_1_76_B_FINALIZATION_PATCH.md` §8).

No commit, push, fetch, pull, checkout, reset, clean, rebase or cherry-pick was
executed.

---

## V. Limitations

1. **Unsupported constructs remain.** `enum` members (1 record) and legacy 3.x
   `export(...) var … setget` (2 records, 3 occurrences) are reported, not
   parsed; those 3 records are `syntax_coverage_status = PARTIAL` by design.
2. **One structural reclassification.** `target_value` in `ui_life_bar.gd` moved
   from `variables` to `properties`; the old value `"0.0:"` shows the previous
   parser bug. Reviewers comparing old vs new symbol lists must read it as a
   correction, not a loss.
3. **Five label changes.** Five records moved `analysis_partial →
   analysis_complete` because annotation lines are now interpreted. The official
   records still carry the old labels; the new labels exist only in the workspace.
4. **Coordinates are analysed-file coordinates** with a per-record derived offset
   (all 3). The commit line is verified, not stored as the record line.
5. **Old symbol detail is coarse.** Pre-1.75 records have no
   `declaration_kind`/`annotations`; "changed" entries therefore include
   additive-key changes (e.g. `declaration_kind: null → VARIABLE`).
6. **No evidence decision was made.** Linkage/candidate/independence are
   untouched here; that is Batch C's read-only job.

---

## W. Final Verdict

**`PASS_WITH_LIMITATIONS`**

Corrected from the earlier `PASS`. Execution and data-integrity objectives all
pass, but three records do not have complete syntax coverage, so the batch
cannot be described as a complete-corpus, complete-syntax baseline.

What passes (no limitation):

* 29/29 in-scope records reanalysed, validated, deterministic and idempotent.
* 4/4 Phase 1.75 records reused after independent re-validation
  (11/11/17/13 symbols re-located against the pinned commit).
* 1/1 shader record excluded with a reason and no fabricated analysis.
* One parser build identity throughout; provenance and digests verified for every
  record; 0 removed symbols; 0 unexplained differences; 0 location problems.
* 225 formal artefacts byte-identical; 0 deletions; no git write.

What limits the verdict:

* 3 of 29 reanalysed records are `syntax_coverage_status = PARTIAL`: one enum
  (`blackboard_compare.gd`) and two files using legacy 3.x
  `export(...) var … setget` (`board_member_button.gd`, `board_card.gd`); those
  declarations are reported as unsupported but are absent from `symbols` (§N.2).
* One symbol changed structural class
  (`ui_life_bar.gd::target_value`, Variable → Property); it is a correction, not
  a loss, but it means old and new symbol lists are not 1:1 comparable by group.
* The five `analysis_partial → analysis_complete` label changes exist only in this
  workspace; the official records still carry their original labels.

None of these limitations weakens the batch's actual deliverables: every record
is traceable to a frozen commit, every diff is reproducible, determinism and
idempotency hold, and no official artefact changed. They are limitations in
*syntax coverage*, not in *execution success* or *data integrity*.

---

## X. Batch C Readiness

**`READY_FOR_BATCH_C_WITH_RESTRICTIONS`**

This is a readiness statement only; Batch C requires separate human approval and
was not started.

Restrictions Batch C must carry:

1. Treat the 3 `PARTIAL` records as partially covered: symbols from
   `blackboard_compare.gd`, `board_member_button.gd` and `board_card.gd` are
   incomplete by construction (enum members, legacy `setget` variables), so no
   "no evidence" conclusion may be drawn from a missing symbol in those files.
2. Read `target_value` as one property (not a lost variable) when matching
   `ui_life_bar.gd` against health_bar symbols.
3. Do not rebuild linkage: the 150 official records were produced from
   parser-1.71 analyses; a rebuild would report STALE/altered freshness and is
   outside Batch C's read-only scope.

The batch remains ready because every input Batch C needs — manifest, diffs,
new records, reuse validation, locations — exists and is internally consistent.

### X.1 Inputs Batch C may use

* `manifest.json` — authoritative per-record status and diff references.
* `diff/<id>.json` — added/reclassified/changed symbols with locations.
* `reanalyzed/<id>.json` — full new analysis records (symbols + coverage).
* `reports/reuse_validation.json` — the four reused records.

Constraints carried forward: official linkage (150) and candidates (2) must not
be modified; linkage freshness will read as STALE only if a rebuild is attempted,
which Batch C must not do; new symbols must be evaluated against the five pilot
features read-only, and any promotion candidate must be marked
`REQUIRES_MANUAL_EVIDENCE_REVIEW`.

---

## Y. Finalization Record (report-only patch)

This report was finalised by `.ai/context/PHASE_1_76_B_FINALIZATION_PATCH.md`
(report-only; no reanalysis, no parser run, no workspace write).

| Change | Before | After |
|---|---|---|
| Symbol diff accounting | `Added 45`, `Net +44` presented as separate columns without a stated basis | explicit decomposition 134 matched + 1 reclassified + 44 new; "45" is the diff listing count (44 new + 1 reclassified) |
| Coverage limitation detail | one line listing 3 `PARTIAL` records | per-record table with repository, commit, path, construct lines and symbol impact (§N.2) |
| Status-field semantics | implied | `parse_execution_status` / `syntax_coverage_status` / `analysis_completeness` explained and explicitly kept distinct (§N.1) |
| Final verdict | `PASS` | **`PASS_WITH_LIMITATIONS`** (§W) |
| Batch C readiness | "Ready" prose | **`READY_FOR_BATCH_C_WITH_RESTRICTIONS`** with three named restrictions (§X) |

Integrity during finalization: the Batch B workspace (162 files), all official
analysis/linkage/candidate artefacts, the Phase 1.75 workspace, the Batch A
inventory and the parser/adapter were digest-compared before and after this
patch and were unchanged. Only this report and the new patch document were
written. Accounting status: `SYMBOL_DIFF_ACCOUNTING_RESOLVED`.
