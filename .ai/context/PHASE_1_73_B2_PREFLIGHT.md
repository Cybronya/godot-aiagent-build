# Phase 1.73 — Batch B.2
# Stage A — Preflight

Audit time: 2026-11-15. Read from the live tree, not from earlier reports.

## A.1 Repository state

| Item | Value |
|---|---|
| Project Root | `F:/Godot_v4.7-stable/game` |
| Branch | `master` |
| HEAD | `d64b1cd5b576a44dcfafd7becbb2d2a7f1fd6a84` |
| Staged changes | 0 |
| Modified (tracked) | 33 (all pre-date Batch B.1; none touched by B.1/B.2) |
| Untracked | 350 (`-uall`), of which 110 were produced by Batch B.1 |
| Working tree writes by this stage | none |

## A.2 External analysis

| Item | Value |
|---|---|
| Analysis records | **34** |
| Status split | 11 `analysis_complete`, 22 `analysis_partial`, 1 `unsupported_shader` |
| Index | `.ai/learning/external_code/index.json`, 34 entries, consistent |
| Provenance | 34/34 `provenance_status=complete`, immutable commit-pinned `source_url` |

## A.3 Linkage store

| Item | Value |
|---|---|
| Records | **150** (`feature_links/*.json`, one file per pair) |
| Schema / generator | `external_analysis_feature_linkage` v1 / `feature_linkage` `phase-1.73-b/1` |

| Classification | Count |
|---|---:|
| `DIRECT_EVIDENCE` | 3 |
| `INDIRECT_EVIDENCE` | 1 |
| `DECLARED_CONTEXT` | 0 |
| `POTENTIAL_RELEVANCE` | 10 |
| `AMBIGUOUS` | 8 |
| `NO_SUPPORTED_LINK` | 128 |
| **sum** | **150** |

`linkage_outcome`: `LINKED` 22, `NOT_LINKED` 128. Item roles: `LINKAGE_EVIDENCE` 31,
`PAIR_EVALUATION` 128, no item lacks the role.

Per Feature: 30 evaluable records each (20 unevaluable pairs = 4 analyses × 5 Features).

| Feature | DIRECT | INDIRECT | POTENTIAL | AMBIGUOUS | NO_SUPPORTED_LINK |
|---|---:|---:|---:|---:|---:|
| health | 2 | 0 | 0 | 2 | 26 |
| health_bar | 0 | 0 | 3 | 2 | 25 |
| openable_door | 0 | 0 | 2 | 2 | 26 |
| attack_emitter | 0 | 1 | 2 | 2 | 25 |
| blackboard | 1 | 0 | 3 | 0 | 26 |

## A.4 Feature Evidence Projections

| Feature | `projection_status` | Verification | Evidence counts (EXTRACTED / DECLARED / PARTIAL) |
|---|---|---|---|
| health | PARTIAL | `NOT_VERIFIED` / `NOT_RUN` | 17 / 27 / 5 |
| health_bar | PARTIAL | `NOT_VERIFIED` / `NOT_RUN` | 14 / 17 / 5 |
| openable_door | COMPLETE | `NOT_VERIFIED` / `NOT_RUN` | 16 / 22 / 0 |
| attack_emitter | PARTIAL | `NOT_VERIFIED` / `NOT_RUN` | 16 / 26 / 2 |
| blackboard | COMPLETE | `NOT_VERIFIED` / `NOT_RUN` | 12 / 14 / 0 |

`projection_status=COMPLETE` is a coverage statement only; every Feature remains
`feature_verification_status=NOT_VERIFIED` with `basis=NO_EXECUTION_EVIDENCE`.

## A.5 Freshness and tests (measured before any B.2 edit)

| Check | Command | Exit | Result |
|---|---|---|---|
| Linkage freshness | `feature_linkage.py check --pilot` | 0 | FRESH=150, STALE=0, MISSING_SOURCE=0, INVALID=0; coverage expected 150 / checked 150 / missing 0 / unexpected 0 |
| Linkage tests | `tests/test_feature_linkage.py` | 0 | 65 tests, 65 passed |
| Projection tests | `test_feature_evidence_projection.py` | 0 | 41 tests passed |
| Pipeline | `test_feature_pipeline.py` | 0 | all checks passed (31 Features) |
| Source analysis | `.ai/tools/learning/tests/test_source_analysis.py` | 0 | 17 checks, 0 failures |
| Phase 1.71 A / B | `test_batch_a.py` / `test_batch_b.py` | 0 / 0 | 38 / 33 checks |
| Feature metadata | `.ai/tools/validator/check_feature_metadata.py` | 0 | 31 Features, 0 error, 0 warning |

## A.6 Files and Schemas actually read

* `.ai/tools/external_code/feature_linkage.py` — classification vocabulary, `evaluate_pair`,
  `_apply_indirect`, `validate_linkage`, `evaluate_freshness`, `load_linkage_records`, CLI.
* `.ai/tools/external_code/external_code_understanding.py`, `provenance.py`,
  `provenance_validator.py` — provenance fields and gate semantics.
* Every one of the 150 records under `.ai/learning/external_code/feature_links/`
  (loaded programmatically; the 4 linked records read in full).
* The 4 referenced analysis records, the 3 external source files, the 5 Feature projections,
  `feature_graph.json`, and the mirror metadata for the repositories involved.

## A.7 Divergences from the Batch B.1 report

No state divergence: counts, classifications, SHAs, digests and freshness all match the
B.1 final report exactly.

Two **new facts** were established in this stage that B.1 did not report (they are findings,
not inconsistencies):

1. `line_reference` in every evidence item indexes the **reference copy** under
   `code_library/references/...`, which carries a 3-line provenance header; the canonical
   commit-pinned file under `sources/...` is therefore exactly 3 lines shorter. Both files
   were hashed: the recorded `source_digest` matches the `sources/` copy (MATCHED), the
   `references/` copy has a different digest. Line 23 in a record = line 20 of the commit file
   for `Stats.gd`, and the offset holds for all three DIRECT sources.
2. `analysis_complete` for `nezvers/.../HealthResource.gd` does not mean full symbol coverage:
   the parser captured 1 of the 5 `@export var` declarations (`is_dead` at line 16) and missed
   `hp`, `max_hp`, `reset_hp`, `reset_max_hp`.

Both are carried into Stage B and Stage F. Nothing was stopped: neither fact invalidates a
record, they narrow what a record may be used to claim.

## A.8 Protected state (default read-only, confirmed untouched)

`Features/`, `.ai/context/feature_index.json`, `feature_graph.json`,
`.ai/learning/feature_evidence/`, `.ai/learning/source_analysis/`, the 34 external analysis
records, the 150 linkage records, the catalog, mirror sources and provenance records were read
only. This stage wrote nothing.
