# Phase 1.73 — Batch B
# External Analysis ↔ Feature Evidence Linkage
# Execution Report

Generated: 2026-11-15T12:55:48Z
Scope: linkage layer only. No similarity, candidate, admission, promotion or verification work.

---

## A. Execution Baseline

| Item | Value |
|---|---|
| Project Root | `F:/Godot_v4.7-stable/game` |
| Branch | `master` |
| HEAD | `d64b1cd5b576a44dcfafd7becbb2d2a7f1fd6a84` |
| Staged | 0 |
| Modified (working tree) | 33 (all pre-existing; none created by Batch B) |
| Untracked entries | 110 (default collapsed listing) / 240 files with `-uall`; Batch B adds 68 of them: 1 module, 1 test file, 65 records, 1 report |
| External Analysis Records (actual) | **14** |
| External Analysis Index entries | **14** |
| Feature Evidence Projections (actual) | **5** |
| Feature Registry features | 31 |

External Analysis status distribution (re-read from disk, not assumed):

| analysis_status | count |
|---|---|
| analysis_complete | 5 |
| analysis_partial | 8 |
| unsupported_shader | 1 |

Cross-check of the 14 records against `.ai/learning/external_code/index.json`:
`MATCHED` — no id missing in either direction (`cross_check_index` → `missing_in_index=[]`,
`missing_records=[]`). No data was rebuilt to make counts match; the historical baseline
was reproduced exactly.

Feature Evidence Projection status distribution (read-only):

| feature_id | projection_status | verification_status |
|---|---|---|
| health | PARTIAL | NOT_VERIFIED / NOT_RUN |
| health_bar | PARTIAL | NOT_VERIFIED / NOT_RUN |
| openable_door | COMPLETE | NOT_VERIFIED / NOT_RUN |
| attack_emitter | PARTIAL | NOT_VERIFIED / NOT_RUN |
| blackboard | COMPLETE | NOT_VERIFIED / NOT_RUN |

Actual file changes from this batch:

| Path | Type |
|---|---|
| `.ai/tools/external_code/feature_linkage.py` | new |
| `.ai/tools/external_code/tests/test_feature_linkage.py` | new |
| `.ai/learning/external_code/feature_links/*.json` (65 files) | new derived store |
| `.ai/context/PHASE_1_73_B_EXTERNAL_ANALYSIS_LINKAGE.md` | new (this report) |

No existing file was modified.

---

## B. Architecture Audit

### B.1 External Analysis Record (verified field names, not assumed)

Real keys of `.ai/learning/external_code/analysis/ext-*.json`:
`analysis_id`, `analysis_status`, `approved_knowledge`, `commit_sha`, `commit_sha_full`,
`conditions`, `copy_allowed`, `created_at`, `domain`, `entry_points`, `failure_paths`,
`feature_created`, `file_type`, `functions_analyzed`, `input_digest`, `knowledge_status`,
`license*`, `limitations`, `parse_status`, `parser_name`, `parser_version`, `provenance`,
`provenance_status`, `reference_path`, `repo`, `schema`, `schema_version`,
`side_effects`, `signals_events`, `snippet_id`, `source_analysis_status`,
`source_consistent`, `source_digest`, `source_exists`, `source_file_path`,
`source_path`, `source_url`, `state_changes`, `symbols`, `unresolved_questions`.

Notes that shaped the implementation:

* There is **no** explicit `what this code is related to` field. Linkage must be derived
  from `symbols` (`class_name`, `functions`, `signals`, `variables`, `exports`),
  `entry_points`, `snippet_id`, `repo`, `source_path`, `source_digest`, `provenance`.
* `source_path` is **repo-relative**; `reference_path`/`source_file_path` are project
  paths to the mirrored reference file. Linkage evidence uses the project path when the
  mirror exists, and always keeps the repo path plus `source_url` in the record.
* The record has no per-symbol commit/path ambiguity information; `provenance_status`
  is the only provenance quality marker (all 14 are `complete`).
* `analysis_status` values present: `analysis_complete`, `analysis_partial`,
  `unsupported_shader`. All are preserved verbatim.

### B.2 Feature Evidence Projection (verified)

Keys used: `feature_id`, `feature_name`, `feature_path`, `projection_status`,
`verification_status` (Batch A.1 block), `symbol_evidence`, `interface_evidence`,
`capability_evidence`, `source_references`, `analysis_references`.

* Feature **source** symbols come from `symbol_evidence` entries with
  `extraction_status=EXTRACTED` and `source_type=GDSCRIPT_SOURCE`.
* Feature **declared** symbols come from `interface_evidence` / `capability_evidence`
  (human-declared, `extraction_status=DECLARED`). They can never produce
  `DIRECT_EVIDENCE`.
* `analysis_references[].analysis_status` may be `SOURCE_ENTRY_AMBIGUOUS`
  (`attack_emitter`). It is copied into the linkage record unchanged under
  `feature_projection.feature_analysis_references`, so ambiguity is not hidden.

### B.3 Existing query / helper capability (reused, not duplicated)

| Need | Reused |
|---|---|
| Path normalization (`original` + project-relative) | `feature_evidence.normalize_path` |
| sha256 / canonical JSON | `feature_evidence._sha256_file` / `._sha256_text` / `._canonical` |
| Evidence / projection / verification vocabularies | `feature_evidence.EVIDENCE_STATUSES`, `.PROJECTION_STATUSES`, `.VERIFICATION_STATUSES` |
| Pilot Feature scope | `feature_evidence.PILOT_FEATURES` |
| GDScript symbol extraction | **Not re-implemented** — read from existing Analysis Records and Projections |
| Feature registry / index / graph | read-only read of `feature_graph.json` edges; no second registry |
| Atomic write pattern | same approach as `feature_evidence.write_projection` and `discovery_to_binding` (same-directory temp file + `os.replace`) |

### B.4 Was there an existing linkage capability?

`grep -ril "linkage" .ai/tools .ai/learning .ai/context` returns only the two files
created by this batch (plus their `__pycache__`). There was **no** pre-existing
linkage store, schema, CLI or index. Nothing was overwritten or re-implemented.

### B.5 Why no duplicate infrastructure was built

* No second parser: external symbols are the ones the Phase 1.71 analysis already
  recorded; feature symbols are the ones Batch A already projected.
* No second Feature Registry / Knowledge Store: both sides are read-only inputs.
* No second Provenance system: the record copies `provenance_status`, `commit_sha_full`,
  `source_digest` and the projection's `source_references` digests.
* No linkage index file: the store is `analysis_id__feature_id.json`, so an individual
  pair can be rebuilt and checked without a mutable index that could itself go stale.

---

## C. Linkage Data Model

* Schema: `external_analysis_feature_linkage`, `schema_version = 1`
* Generator: `feature_linkage`, version `phase-1.73-b/1`,
  classifier `deterministic_symbol_and_declaration_matching`
* Storage: `.ai/learning/external_code/feature_links/<analysis_id>__<feature_id>.json`
* Rebuild: `build --pilot` (all 14), `build --analysis <analysis_id>` (5 pairs)

### C.1 Linkage ID

```
linkage_id = "lnk-" + sha256("phase-1.73-b|" + analysis_id + "|" + feature_id)[:16]
```

Derived from identity only. Never from array position, filename order or mtime.
`validate_linkage` recomputes it, so a mismatched or hand-edited id is rejected.

### C.2 Record structure

```
schema, schema_version, linkage_id, analysis_id, snippet_id, feature_id, feature_name,
generated_at, generator{name,version,classifier},
linkage_classification, linkage_outcome (LINKED | NOT_LINKED),
external_analysis{ analysis_record_path, analysis_record_digest, source_repository,
                   source_commit, source_path, source_digest, analysis_status,
                   parse_status, provenance_status, file_type, source_url },
feature_projection{ feature_projection_path, feature_projection_digest, feature_path,
                    feature_source_references, feature_analysis_references,
                    projection_status, verification_status },
evidence_items[ ... ],
evidence_limitations{ analysis_status, projection_status, verification_status,
                      parser_limitations, missing_evidence, ambiguity_reasons,
                      unsupported_content, provenance_limitations },
pair_evaluation{ external_symbol_count, external_symbols, feature_source_symbol_count,
                 feature_declared_symbol_count, matched_symbols, shared_tokens,
                 declared_relation },
source_verification{ analysis_record, feature_projection, external_source_file,
                     feature_sources },
limitations[ ... ]
```

`feature_analysis_references` is an exact copy of the projection's references, so
`SOURCE_ENTRY_AMBIGUOUS` and other Feature-side analysis statuses survive into the record.

### C.3 Evidence item structure

```
evidence_id, evidence_type, evidence_status, source_side, source_path,
symbol_name, line_reference, matched_value, explanation, provenance_reference
(+ feature_evidence_id for DIRECT_EVIDENCE, intermediate_path for GRAPH_RELATION)
```

Evidence types (closed set, validated):

| evidence_type | meaning |
|---|---|
| `SYMBOL_EXACT_MATCH` | same identifier on both sides, both source-extracted |
| `DECLARED_SYMBOL_MATCH` | Feature metadata declares the matched name |
| `DECLARED_SOURCE_SNIPPET` | Feature metadata declares this external `snippet_id` |
| `GRAPH_RELATION` | declared Feature-graph edge used as an intermediate path |
| `SYMBOL_TOKEN_OVERLAP` | one shared significant token; a clue only |
| `NONE` | the comparison was performed and produced no evidence |

`evidence_status` reuses the existing vocabulary only
(`DECLARED / EXTRACTED / PARTIAL / MISSING / NOT_APPLICABLE / UNSUPPORTED / CONFLICTED`).

### C.4 Classification semantics (evidence type only)

| linkage_classification | rule implemented | forbidden to claim |
|---|---|---|
| `DIRECT_EVIDENCE` | an exact identifier shared by an external symbol and a Feature **source-extracted** symbol; both sides locatable | — |
| `INDIRECT_EVIDENCE` | this analysis has a DIRECT link to Feature B, and Feature A is connected to B by a `works_with` / `commonly_used_with` / `requires` / `composes_with` graph edge; `intermediate_path` recorded | direct source evidence |
| `DECLARED_CONTEXT` | only a human declaration connects the two sides: a `snippet_id` in `feature.yaml`, or an external symbol matching a Feature-declared interface/capability name | source-level evidence |
| `POTENTIAL_RELEVANCE` | one shared significant token (length ≥ 4, not a stopword, not an engine/lifecycle name), nothing stronger | an established link |
| `AMBIGUOUS` | one analysis matches ≥ 2 Features at the same strongest tier; all contenders are recorded with the reason | a chosen single target |
| `NO_SUPPORTED_LINK` | the pair was evaluated and produced nothing; 62 pairs in this pilot | functional irrelevance |

Excluded from evidence by design: identifiers starting with `_` and Godot
engine/lifecycle names (`_ready`, `_init`, `_process`, `connect`, …), because shared
engine overrides are not evidence of a relation. This is what keeps
`_ready`-style noise out of the pilot.

`FORBIDDEN_KEYS` are rejected anywhere in a record:
`similarity*`, `candidate*`, `admission*`, `promoted`, `promotion*`, `feature_verified`,
`verified`. A record can therefore not be turned into a similarity or admission artefact.

### C.5 Digest and freshness rules

Recorded: `analysis_record_digest` (sha256 of the record file),
`feature_projection_digest` (sha256 of the projection file),
`source_digest` (external source content digest, as recorded by Phase 1.71),
`feature_source_references[].source_digest`, `generator.version`, `schema_version`.

`source_verification.external_source_file.digest_status` reports
`MATCHED / MISMATCH / NOT_FOUND / NOT_RECORDED` for the mirrored reference file; a
mismatch is recorded (not silently repaired) and never changes the analysis record.

Freshness (`check`):

| condition | status |
|---|---|
| schema/record invalid, or `schema_version` ≠ 1 | `INVALID` |
| analysis record or projection file missing | `MISSING_SOURCE` |
| analysis-record digest changed, or projection digest changed | `STALE` |
| `generator.version` differs from the running generator | `STALE` (`LINKAGE_GENERATOR_VERSION_CHANGED`) |
| everything matches | `FRESH` |

`FRESH` is never inferred from file existence alone: both digests are recomputed on
every check.

Write safety: validate → verify source digests → temp file in target directory →
write JSON → re-read → validate again → verify digests again → `os.replace` → temp
removed. Any exception unlinks the temp file and leaves the previous record untouched.
**Single-file atomic replace is not multi-file transactional atomicity**: a failed pilot
build reports `built`, `failed` and `unevaluable` separately so completed and failed
pairs are identifiable (`build` exits 1 when anything failed).

---

## D. Pilot Results (per Analysis Record, all 14)

Legend: classification per Feature. `—` means the pair was not evaluated (unevaluable).

| # | analysis_id | analysis_status | source (repo / path) | health | health_bar | openable_door | attack_emitter | blackboard | ev. | Freshness |
|---|---|---|---|---|---|---|---|---|---|---|
| 1 | ext-40ab1c0330e01d7f | analysis_complete | alfredbaudisch/Godello `scripts/drag_utils.gd` | NO_SUPPORTED_LINK | NO_SUPPORTED_LINK | NO_SUPPORTED_LINK | NO_SUPPORTED_LINK | NO_SUPPORTED_LINK | 5 | FRESH |
| 2 | ext-4b7782ce66be92a7 | analysis_complete | alfredbaudisch/Godello `addons/uuid/uuid.gd` | NO_SUPPORTED_LINK | NO_SUPPORTED_LINK | NO_SUPPORTED_LINK | NO_SUPPORTED_LINK | NO_SUPPORTED_LINK | 5 | FRESH |
| 3 | ext-51fbb1e2b03c3f67 | analysis_complete | ceceppa/anima `addons/anima/motion/runtime/anima_race_instance.gd` | NO_SUPPORTED_LINK | NO_SUPPORTED_LINK | NO_SUPPORTED_LINK | NO_SUPPORTED_LINK | NO_SUPPORTED_LINK | 5 | FRESH |
| 4 | ext-56ca48126ec8514d | analysis_partial | alfredbaudisch/Godello `scripts/events.gd` | NO_SUPPORTED_LINK | NO_SUPPORTED_LINK | NO_SUPPORTED_LINK | NO_SUPPORTED_LINK | NO_SUPPORTED_LINK | 5 | FRESH |
| 5 | ext-5adc6644d3347390 | analysis_partial | Ark2000/PankuConsole `.../interactive_shell/mini_repl_2.gd` | NO_SUPPORTED_LINK | NO_SUPPORTED_LINK | NO_SUPPORTED_LINK | NO_SUPPORTED_LINK | NO_SUPPORTED_LINK | 5 | FRESH |
| 6 | ext-80c1104f5262a6ee | unsupported_shader | Ark2000/PankuConsole `.../shader/simple_fast_blur.gdshader` | — | — | — | — | — | 0 | n/a |
| 7 | ext-9e62ed2e3dec8164 | analysis_partial | alfredbaudisch/Godello `scripts/board_member_button.gd` | NO_SUPPORTED_LINK | NO_SUPPORTED_LINK | NO_SUPPORTED_LINK | NO_SUPPORTED_LINK | NO_SUPPORTED_LINK | 5 | FRESH |
| 8 | ext-aa0204cc227b0480 | analysis_partial | derkork/godot-statecharts `addons/godot_state_charts/animation_tree_state.gd` | NO_SUPPORTED_LINK | NO_SUPPORTED_LINK | NO_SUPPORTED_LINK | NO_SUPPORTED_LINK | **POTENTIAL_RELEVANCE** | 5 | FRESH |
| 9 | ext-bfe9b7e6dbebbfae | analysis_partial | blackears/cyclopsLevelBuilder `.../actions/cyclops_action.gd` | NO_SUPPORTED_LINK | NO_SUPPORTED_LINK | NO_SUPPORTED_LINK | NO_SUPPORTED_LINK | NO_SUPPORTED_LINK | 5 | FRESH |
| 10 | ext-ec789727924bfa6c | analysis_complete | foxssake/netfox `examples/forest-brawl/scripts/play-random-3d.gd` | NO_SUPPORTED_LINK | NO_SUPPORTED_LINK | NO_SUPPORTED_LINK | NO_SUPPORTED_LINK | NO_SUPPORTED_LINK | 5 | FRESH |
| 11 | ext-f80d07f302bacc20 | analysis_complete | cis-ash/TEXTREME `Scenes/EffectParameterSelector/EffectParameterSelector.gd` | NO_SUPPORTED_LINK | NO_SUPPORTED_LINK | NO_SUPPORTED_LINK | NO_SUPPORTED_LINK | NO_SUPPORTED_LINK | 5 | FRESH |
| 12 | ext-fb806b579659b155 | analysis_partial | foxssake/netfox `examples/multiplayer-state-machine/scripts/character-states/Idle.gd` | NO_SUPPORTED_LINK | **POTENTIAL_RELEVANCE** | NO_SUPPORTED_LINK | NO_SUPPORTED_LINK | NO_SUPPORTED_LINK | 5 | FRESH |
| 13 | ext-fe3acf782b88edda | analysis_partial | Ark2000/PankuConsole `.../history_manager/env.gd` | NO_SUPPORTED_LINK | NO_SUPPORTED_LINK | **POTENTIAL_RELEVANCE** | NO_SUPPORTED_LINK | NO_SUPPORTED_LINK | 5 | FRESH |
| 14 | ext-fffa637657ffede1 | analysis_partial | alfredbaudisch/Godello `scripts/board_card.gd` | NO_SUPPORTED_LINK | NO_SUPPORTED_LINK | NO_SUPPORTED_LINK | NO_SUPPORTED_LINK | NO_SUPPORTED_LINK | 5 | FRESH |

“ev.” = number of linkage records created for that analysis (one per evaluated pair).

### D.1 The three linked pairs, in full

| analysis_id | feature_id | classification | evidence | basis | limitations |
|---|---|---|---|---|---|
| ext-aa0204cc227b0480 | blackboard | POTENTIAL_RELEVANCE | `SYMBOL_TOKEN_OVERLAP`, token `tree`, matched via external class `AnimationTreeState` ↔ Feature capability `behavior_tree_blackboard` | shared token only | analysis_partial; no exact identifier; no declared relation |
| ext-fb806b579659b155 | health_bar | POTENTIAL_RELEVANCE | `SYMBOL_TOKEN_OVERLAP`, token `display`, external `display_enter` ↔ Feature capability `health_display` | shared token only | analysis_partial; no exact identifier; no declared relation |
| ext-fe3acf782b88edda | openable_door | POTENTIAL_RELEVANCE | `SYMBOL_TOKEN_OVERLAP`, token `open`, external function `open` ↔ Feature source symbol `is_open` | shared token only | analysis_partial; no exact identifier; no declared relation |

Each of these records carries `linkage_outcome = LINKED` (the pair has a documented
evidence type) but its `missing_evidence` states explicitly that no exact identifier,
shared class/signal/export, or declared relation exists. They are clues for Batch C,
**not** similarity findings.

### D.2 Per-analysis notes

* 1, 2, 3, 10, 11 (`analysis_complete`): fully parsed GDScript utility/motion/audio code.
  Their symbol sets are disjoint from all five pilot Features.
* 4 (`events.gd`): `parse_status=partial`, the record carries only signal names
  (`user_logged_in`, `card_clicked`, …) and no functions; dispositions rest on those
  signals only. Limitation preserved: `regex_parser_without_ast_or_type_inference`,
  `no functions found by the regex parser`.
* 5, 7, 9, 12, 13, 14: `analysis_partial` with `annotation_not_fully_interpreted` or
  “no class_name” unresolved questions; preserved in `parser_limitations`.
* 6 (`simple_fast_blur.gdshader`): `unsupported_shader`, zero parseable symbols →
  unevaluable for all five Features; the record itself is untouched.
* 8: the only pair with a feature-graph-adjacent similarity of concept (`tree`) — still
  a token clue only; no `INDIRECT_EVIDENCE` because that requires a **direct** link to a
  graph neighbour, and no direct link exists anywhere in this corpus.

---

## E. Pair Evaluation Summary

Counting rules:

* Total pairs = 14 Analysis Records × 5 pilot Features = **70**.
* A pair is counted once, by its single final `linkage_classification`.
* Unevaluable pairs are not counted in any classification.
* Each linkage record belongs to exactly one analysis and one feature, so no
  double counting is possible.

| Metric | Count |
|---|---|
| Total pairs in scope | 70 |
| Evaluated pairs (record written) | 65 |
| Unevaluable pairs (no record) | 5 |
| DIRECT_EVIDENCE | 0 |
| INDIRECT_EVIDENCE | 0 |
| DECLARED_CONTEXT | 0 |
| POTENTIAL_RELEVANCE | 3 |
| AMBIGUOUS | 0 |
| NO_SUPPORTED_LINK | 62 |
| Sum check (65) | 0 + 0 + 0 + 3 + 0 + 62 = 65 ✔ |

Evidence items produced: 65 (one per record; the three linked records hold one clue item
each, the 62 unlinked records hold one `NONE` comparison item each).

Why so little: the 14 records are utility/UI/audio/state-machine files from five
unrelated repositories (`Godello`, `anima`, `PankuConsole`, `godot-statecharts`,
`cyclopsLevelBuilder`, `netfox`, `TEXTREME`), while the pilot Features are
health / health_bar / openable_door / attack_emitter / blackboard. There is no shared
class, signal, export or declared relationship. No link was manufactured to fill the table.

---

## F. Freshness Results

After `build --pilot` and `check --pilot`:

| Status | Count |
|---|---|
| FRESH | 65 |
| STALE | 0 |
| MISSING_SOURCE | 0 |
| INVALID | 0 |

Coverage: expected 65, checked 65, missing 0, unexpected 0. `check --pilot` exit code 0.

Digest checks performed on every record: analysis-record sha256 and projection sha256
recomputed from disk and compared to the recorded values. All 65 `external_source_file`
checks report `MATCHED` (mirrored reference file digest equals the digest Phase 1.71
recorded in the analysis).

Single-record rebuild verified:
`build --analysis ext-fe3acf782b88edda` → 5 pairs, 5 built, 0 failed;
`check --analysis ext-fe3acf782b88edda` → FRESH=5.

`STALE`, `MISSING_SOURCE` and `INVALID` paths are exercised by the synthetic tests
(edited analysis record, edited projection, deleted record, generator-version bump,
schema-version bump) because the real inputs have not drifted.

---

## G. Tests

### G.1 New Batch B test suite

| Item | Value |
|---|---|
| Command | `python .ai/tools/external_code/tests/test_feature_linkage.py` |
| Test count | 60 |
| PASS | 60 |
| FAIL | 0 |
| Exit code | 0 |
| Framework | `unittest`, temp fixtures under `.ai/tools/external_code/tests/.tmp_linkage` (deleted after the run) |

Synthetic fixture coverage (classification / validation logic):

* Schema: required fields, stable id, unknown classification, outcome mismatch, digest
  format, missing explanation/source_path, forbidden decision keys, unknown
  `projection_status`, limitations copied not invented, invalid record not written.
* Evidence: exact source symbol → DIRECT; pure name similarity (`set_opened` vs
  `set_open`) → not DIRECT; shared token → POTENTIAL only; POTENTIAL cannot be validated
  as DIRECT; declared interface → DECLARED_CONTEXT; DECLARED_CONTEXT cannot carry source
  evidence; `feature.yaml` snippet declaration → DECLARED_CONTEXT; INDIRECT keeps
  `intermediate_path`; INDIRECT requires graph evidence; ambiguous targets are recorded,
  never guessed; AMBIGUOUS without reason rejected; NO_SUPPORTED_LINK is not a negative
  similarity and cannot carry clues; unlocatable source is not `EXTRACTED`.
* Status protection: `analysis_partial` preserved; `unsupported_shader` preserved and its
  record byte-identical after the build; `PARTIAL` projection not overwritten;
  `COMPLETE` projection does not yield `VERIFIED`; verification upgrade rejected;
  `NOT_APPLICABLE` does not verify; `SOURCE_ENTRY_AMBIGUOUS` preserved in
  `feature_analysis_references`.
* Freshness: FRESH; analysis-digest change → STALE; projection change → STALE; deleted
  record → MISSING_SOURCE; generator-version change → STALE; schema-version change →
  INVALID; coverage reporting.
* Atomic write: build failure, JSON serialization failure, schema failure, digest
  failure, replace failure — each leaves the previous record byte-identical with no temp
  file; batch failure reports exactly one failed pair while the other is written and
  valid.

Real-pilot coverage (read-only, temp output): 14 records / 5+8+1 statuses, 5 projections,
70 pairs → 65 records + 5 unevaluable, every record validates and is FRESH, no forbidden
keys, all DIRECT links evidence-backed, verification never upgrades, inputs byte-identical
before/after, index cross-check MATCHED, CLI build/check exit codes, unknown analysis id
fails with exit 1.

Synthetic fixtures and the real pilot are kept separate: the classification cases that
the real corpus does not contain (DIRECT, INDIRECT, DECLARED_CONTEXT, AMBIGUOUS) are
covered **only** by synthetic fixtures; no real record was fabricated to demonstrate them.

### G.2 Regression suite

| Command | Result |
|---|---|
| `python .ai/tools/feature_registry/tests/test_feature_evidence_projection.py` | exit 0 (41 tests) |
| `python .ai/tools/feature_registry/tests/test_feature_pipeline.py` | exit 0 |
| `python .ai/tools/learning/tests/test_source_analysis.py` | exit 0 (17 checks, 0 failures) |
| `python .ai/tools/external_code/tests/test_batch_a.py` | exit 0 (Phase 1.71 Batch A) |
| `python .ai/tools/external_code/tests/test_batch_b.py` | exit 0 (Phase 1.71 Batch B) |
| `python .ai/tools/validator/check_feature_metadata.py` | exit 0 (31 features, 0 errors, 0 warnings) |
| `python .ai/tools/external_code/feature_linkage.py build --pilot` | exit 0 |
| `python .ai/tools/external_code/feature_linkage.py check --pilot` | exit 0 (FRESH=65) |

---

## H. Safety Verification

| Artefact | Status |
|---|---|
| `Features/*/feature.yaml` | not modified (mtimes pre-date this batch, e.g. `Features/attack_emitter/feature.yaml` 2026-10-31T21:26) |
| `.ai/context/feature_index.json` | not modified (2026-10-31T21:29, byte-identical to session start) |
| `.ai/context/feature_graph.json` | not modified (2026-10-31T21:29); read-only edge input |
| 5 × `.ai/learning/feature_evidence/*.json` | not modified (mtimes 2026-11-15T19:52, i.e. Batch A.1; digests recorded in all 65 records still match) |
| 14 × External Analysis Records | not modified (mtimes 2026-11-15T21:57; digests still match) |
| `.ai/learning/external_code/index.json` | not modified; cross-check MATCHED |
| Catalog / Source Library / Reference Library | not written (only read for digest verification) |
| Provenance original records | not modified; copied verbatim into `external_analysis` |
| Scene Intent | not touched |
| Promote flow | not touched |
| Candidate / Similarity / Admission artefacts | none created; forbidden keys rejected by validation |
| `VERIFIED` produced | never; all 65 records carry `NOT_VERIFIED` / `NOT_RUN` |
| Scope of external references | only the 14 existing Analysis Records; the 6,813-entry External References library was **not** scanned |
| Git | branch `master`, HEAD `d64b1cd5…` unchanged; staged 0; modified 33 (all pre-existing, mtimes pre-date this batch); untracked 240 files with `-uall`, of which Batch B contributed exactly 68 (module, test, 65 records, report); no add/commit/push/pull/fetch/reset/checkout/merge/rebase executed |

---

## I. Limitations

1. **Parser granularity.** `regex_parser_without_ast_or_type_inference` for all 14 records.
   No type inference, no cross-file resolution, no line numbers for signals/variables, so
   a shared symbol can only be compared by name at file scope.
2. **Partial analyses.** 8 of 14 records are `analysis_partial`; `events.gd` yielded only
   signals, `mini_repl_2.gd` only `_ready`/`console`. Their dispositions rest on partial
   symbol sets and are marked as such in every record.
3. **Unsupported content.** The shader record (`unsupported_shader`, 1 record) produces no
   symbols and is unevaluable for all five Features; 5 pairs have no record at all.
4. **No real direct/indirect/declared case.** The pilot corpus genuinely contains no link
   of those types; only 3 token-level clues exist. Those code paths are therefore proven
   by synthetic fixtures, not by real data.
5. **Token rule is deliberately weak.** A single shared significant token yields
   `POTENTIAL_RELEVANCE`. Tokens shorter than 4 characters, stopwords and engine names are
   ignored, which also means real but short identifiers (`hp`, `bar`) are not detected.
6. **No `DECLARED_CONTEXT` in the pilot.** The two declared snippet references in Feature
   metadata (`Miziziziz/MizGodotTools` for `attack_emitter`, `bitbrain/beehave` for
   `blackboard`) are not among the 14 analysed records, so the declaration rule matched
   nothing in real data.
7. **Indirect linkage needs a direct seed.** Because no direct link exists, the
   Feature-graph path (`works_with`, `commonly_used_with`, `requires`,
   `composes_with`) never fires in the pilot.
8. **Ambiguity is scoped to tier equality.** `AMBIGUOUS` is raised when ≥ 2 Features share
   the strongest tier. Weaker-tier matches alongside a stronger one keep their own weaker
   classification; this is documented behaviour, not a resolved disambiguation.
9. **Reference-library mirror drift** is reported (`MATCHED/MISMATCH/NOT_FOUND`) but never
   repaired and does not fail the build.
10. **Atomicity scope.** Single-file `os.replace` only. A pilot build is not transactional:
    a mid-run failure leaves earlier records in place and reports which pairs failed.
11. **For Batch C.** At least one real `DIRECT_EVIDENCE` seed requires either external
    analyses of repositories actually related to the pilot Features, or explicit
    Feature→external declarations. Similarity work should not treat the 3
    `POTENTIAL_RELEVANCE` records as findings.

---

## J. Final Verdict

**PASS_WITH_LIMITATIONS**

1. **Has a traceable linkage been established between External Analysis and Features?**
   Yes, as a mechanism: 65 linkage records were built from real inputs, each with
   source paths, digests, evidence items, evidence status and preserved limitations.
   On the real corpus, the linkage is thin — 3 `POTENTIAL_RELEVANCE`, 62
   `NO_SUPPORTED_LINK`, 5 unevaluable, and no direct/indirect/declared relation. No link
   was invented to improve that number.
2. **Can linkage freshness be checked independently?** Yes —
   `check --pilot` / `check --analysis <id>` recompute both source digests and the
   generator version, and report `FRESH / STALE / MISSING_SOURCE / INVALID` with reasons
   and changed sources. 65/65 FRESH now.
3. **Is it safe as Batch C input?** Structurally yes: records are read-only-derived,
   validated, digest-bound, free of similarity/admission fields, and never upgrade
   `verification_status`. Its evidential value is limited by the corpus (see I.4, I.11).
4. **Are there blocking issues that must be resolved first?** No blockers for the
   mechanism. The one substantive prerequisite for useful Batch C work is corpus
   relevance: the current 14 external records do not cover the pilot Features, so no
   real `DIRECT_EVIDENCE` seed exists.

Batch B stops here. No similarity extraction, no candidate, no admission, no Git action.
Awaiting human acceptance and explicit authorisation before any Batch C work.
