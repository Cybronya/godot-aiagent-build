# Phase 1.74 — Batch C
# Stage A — Preflight & Baseline Verification

Audit time: 2026-11-15, before any Batch C file was created.

## A.1 Git

| Item | Value |
|---|---|
| Project Root | `F:/Godot_v4.7-stable/game` |
| Branch | `master` |
| HEAD | `d64b1cd5b576a44dcfafd7becbb2d2a7f1fd6a84` |
| Staged | 0 |
| Modified (tracked) | 33 — all pre-date Phase 1.73; none touched |
| Untracked | 359 (`-uall`): 350 from Phase 1.73 + 9 B.2 reports |

No Git write operation performed.

## A.2 B.2 reports

All nine present and readable:

```
PHASE_1_73_B2_EVIDENCE_READINESS_SEED_QUALIFICATION.md   (verdict PASS_WITH_LIMITATIONS,
                                                          readiness READY_WITH_RESTRICTIONS)
PHASE_1_73_B2_PREFLIGHT.md
PHASE_1_73_B2_DIRECT_EVIDENCE_AUDIT.md
PHASE_1_73_B2_INDIRECT_EVIDENCE_AUDIT.md
PHASE_1_73_B2_EVIDENCE_ROLE_CONSUMPTION_AUDIT.md
PHASE_1_73_B2_MIZGODOTTOOLS_PROVENANCE.md
PHASE_1_73_B2_SYMBOL_EQUIVALENCE_ASSESSMENT.md
PHASE_1_73_B2_SEED_ELIGIBILITY.md
PHASE_1_73_B2_BATCH_C_READINESS.md
```

The final report is the authority for eligibility in this stage.

## A.3 Linkage store

150 records, unchanged, `FRESH=150`.

| Classification | Count |
|---|---:|
| DIRECT_EVIDENCE | 3 |
| INDIRECT_EVIDENCE | 1 |
| POTENTIAL_RELEVANCE | 10 |
| AMBIGUOUS | 8 |
| NO_SUPPORTED_LINK | 128 |

Item roles: `LINKAGE_EVIDENCE` 31, `PAIR_EVALUATION` 128, 0 unmarked.

## A.4 The four referenced records (re-verified against B.2)

| Field | `lnk-d2d95d8162be1592` | `lnk-7084dc8999c2182b` | `lnk-6fff3ce176bd5813` | `lnk-a099657ab3c9930c` |
|---|---|---|---|---|
| file | `ext-1d204b35464cf388__health.json` | `ext-23949c1378c49203__blackboard.json` | `ext-73c80a3db6d71e48__health.json` | `ext-73c80a3db6d71e48__attack_emitter.json` |
| feature_id | health | blackboard | health | attack_emitter |
| classification | DIRECT_EVIDENCE | DIRECT_EVIDENCE | DIRECT_EVIDENCE | INDIRECT_EVIDENCE |
| outcome | LINKED | LINKED | LINKED | LINKED |
| evidence_role (all items) | LINKAGE_EVIDENCE | LINKAGE_EVIDENCE | LINKAGE_EVIDENCE | LINKAGE_EVIDENCE |
| evidence_type | SYMBOL_EXACT_MATCH ×3 | SYMBOL_EXACT_MATCH ×5 | SYMBOL_EXACT_MATCH ×1 | GRAPH_RELATION ×1 |
| repository | gdquest-demos/godot-make-pro-2d-games | bitbrain/beehave | nezvers/Godot-GameTemplate | nezvers/Godot-GameTemplate |
| commit | `7290681309ff…` | `fe589153fa78…` | `d5d8d1588742…` | `d5d8d1588742…` |
| digest | `ef9f6781…` | `e1b980ce…` | `fed9dc57…` | `fed9dc57…` |
| provenance_status | complete | complete | complete | complete |
| source_verification | analysis MATCHED, file MATCHED | MATCHED / MATCHED | MATCHED / MATCHED | MATCHED / MATCHED |
| analysis_status | analysis_partial | analysis_partial | analysis_complete | analysis_complete |
| symbols | take_damage(23), heal(31), health_changed(6) | Blackboard(null), keys(24), set_value(30), has_value(45), erase_value(53) | is_dead(19) | `health`, path `[attack_emitter, works_with, health]` |
| record has `independence` / `derivation_type` | **no** | **no** | **no** | **no** |

**All four match the B.2 report exactly.** No divergence, so candidate creation may proceed.

Consequence recorded for design: the linkage schema does **not** carry `independence`,
`derivation_type` or `seed_eligibility` — those are B.2 *review conclusions*. They must therefore
enter Batch C as a reviewed **policy** artefact, never be inferred inside the guard from counts,
file names or record contents.

## A.5 Upstream state (read-only inputs)

| Item | State |
|---|---|
| External Analysis | 34 (11 complete / 22 partial / 1 unsupported_shader), index consistent |
| Feature Evidence Projections | 5 — health PARTIAL, health_bar PARTIAL, openable_door COMPLETE, attack_emitter PARTIAL, blackboard COMPLETE; all `NOT_VERIFIED` / `NOT_RUN` |
| Feature metadata | 31 Features, validator 0 error / 0 warning |
| Feature index / graph / coverage matrix | present, untouched |

## A.6 Baseline hashes captured

Before any write, sha256 of 150 linkage records + 34 analysis records + 5 projections +
31 `feature.yaml` + `feature_index.json` + `feature_graph.json` + `coverage_matrix.json` was
stored to `.ai/tmp/phase174_baseline.json` (34 feature files, 150, 34, 5). Stage I compares
against it, because `feature_links/` is untracked and Git cannot detect edits there.

## A.7 Baseline checks

| Check | Result |
|---|---|
| Linkage freshness (`check --pilot`) | FRESH 150, coverage 150/150, exit 0 |
| `test_feature_linkage.py` | 70 tests, exit 0 |
| `test_feature_evidence_projection.py` | 41 tests, exit 0 |
| `test_feature_pipeline.py` | PASS, exit 0 |
| `test_source_analysis.py` | 17 checks, 0 failures, exit 0 |
| `test_batch_a.py` / `test_batch_b.py` | 38 / 33 checks, exit 0 |
| `check_feature_metadata.py` | 31 Features, 0/0, exit 0 |

## A.8 Existing modules inventoried for reuse (detail in `PHASE_1_74_C_ARCHITECTURE.md`)

`.ai/tools/feature_registry/` holds 7 scripts, none of which models a candidate or a workspace
(`grep -rl "candidate\|workspace"` finds no Feature-side module; matches are in asset registry,
e2e and evaluation only, all unrelated). `.ai/learning/` has no candidate directory. So a new,
minimal module set is required — built on the existing loader / freshness / atomic-write
conventions.

## A.9 Verdict

**Baseline consistent with Batch B.2; proceed to Stage B.**
