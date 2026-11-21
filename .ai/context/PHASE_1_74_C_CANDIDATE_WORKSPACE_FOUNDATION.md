# Phase 1.74 — Batch C
# Restricted Candidate Workspace Foundation
# Final Report

Executed: 2026-11-15. Stage reports: `PHASE_1_74_C_PREFLIGHT.md`, `PHASE_1_74_C_ARCHITECTURE.md`.

---

## A. Executive Summary

**Verdict: `PASS_WITH_LIMITATIONS`** — all 14 acceptance criteria in §15 are satisfied;
the limitations are properties of the reviewed evidence (documented in Stage J), not defects in
the foundation.

| Deliverable | Result |
|---|---|
| Candidate Workspace schema | 2 drafts, `schema_version=1`, `candidate_workspace_draft` |
| Centralized Eligibility Guard | 1 module, 10 ordered checks, every rejection explained |
| health Candidate | `cand-08fdc0b10a112ecf` — 2 separate evidences, 1 context, `NEEDS_REVIEW` |
| blackboard Candidate | `cand-7f52cb8f583124db` — 1 evidence, `NEEDS_REVIEW` |
| Seed evidences | **3** (2 health, 1 blackboard) |
| Context references | **1** (`attack_emitter`, graph-derived, `counts_as_seed=false`) |
| Excluded features | **2** (`health_bar`, `openable_door`), recorded with reasons |
| Candidate freshness | 2/2 `FRESH` |
| Workspace validation | 2/2 `VALID` |
| New tests | **64**, all passing |
| Evidence / Feature / Projection files modified | **0** |

What this stage deliberately did not build: similarity, admission, promotion, ranking,
clustering, symbol equivalence, Feature creation. A candidate answers "which reviewed evidence
belongs to this Feature and on what terms", and says nothing about whether the Feature is
implemented, verified or admitted.

---

## B. Baseline

| Item | Before | After |
|---|---|---|
| Branch / HEAD | `master` / `d64b1cd5` | unchanged |
| Staged | 0 | 0 |
| Modified (tracked) | 33 | 33 (same files) |
| Untracked | 359 | 368 (+9 visible) |
| Linkage records | 150 | 150 (identical bytes) |
| Analysis records | 34 | 34 (identical bytes) |
| Projections | 5 | 5 (identical bytes) |
| Feature metadata/index/graph/coverage | 34 files | identical bytes |
| Linkage freshness | FRESH 150 / coverage 150 | unchanged, exit 0 |

The four reviewed records were re-verified field-by-field against Batch B.2 before any write
(Stage A.4): all matched, so no divergence report was needed.

One design consequence of the preflight: the linkage schema carries `classification` and
`evidence_role`, but **not** `independence`, `derivation_type` or `seed_eligibility`. Those are
Batch B.2 review conclusions, so they enter Batch C as a reviewed **policy file** rather than
being inferred by code.

---

## C. Architecture

### New modules (all additive)

| File | Lines | Role |
|---|---:|---|
| `.ai/tools/feature_registry/candidate_seed_policy.json` | 92 | reviewed eligibility policy: scope, 3 seeds (qualification, independence, architecture, notes, limitations), 1 context relation, 2 exclusions, `policy_version=phase-1.74-c/1` |
| `.ai/tools/feature_registry/candidate_eligibility.py` | 571 | the **only** place that decides seed eligibility: `load_policy`, `evaluate_seed_eligibility`, `build_evidence_reference`, `build_context_reference`, `build_evidence_location`, `resolve_line_offset` |
| `.ai/tools/feature_registry/candidate_workspace.py` | 896 | draft schema + validation, content digest, content identity, atomic persistence, `build/list/show/validate/check-freshness` |
| `.ai/tools/feature_registry/tests/test_candidate_workspace.py` | 811 | 64 tests |

### Reused modules

`feature_linkage.load_linkage_records`, `evaluate_freshness`, `linkage_evidence_items`,
`is_graph_derived_relation`, `LINKED_CLASSIFICATIONS`, `GRAPH_EVIDENCE_TYPES`; the
`mkstemp`+`os.replace` write pattern; projection status vocabulary. No second freshness or
provenance validator was written.

### Data flow

```
feature_links/*.json (read-only)
   → candidate_seed_policy.json → evaluate_seed_eligibility (10 checks)
   → build_evidence_reference / build_context_reference
   → build_candidate → validate_candidate_draft → content_digest → stable candidate_id
   → .ai/learning/candidate_workspace/candidates/*.json  (atomic)
   → list / show / validate / check-freshness (read-only)
```

Nothing writes back to `Features/`, the index, the graph, projections, analyses or linkage records.

### Persistence

```
.ai/learning/candidate_workspace/
  WORKSPACE.json                       workspace id, policy version, candidate index, exclusions
  candidates/cand-08fdc0b10a112ecf.json   health
  candidates/cand-7f52cb8f583124db.json   blackboard
```

One file per candidate; pretty-printed JSON with trailing newline; written via `mkstemp` in the
destination directory + `os.replace`.

### Identity and schema versioning

* `candidate_id = "cand-" + sha256(feature_id | sorted(linkage_ids) | policy_version)[:16]` —
  content identity, no random ids.
* `content_digest` = sha256 of canonical JSON excluding `content_digest`, `created_at`,
  `updated_at`, `source_snapshot.observed_at` and loader-injected `__*` keys, so it is
  recomputable from the file and stable across runs.
* Policy bump ⇒ new candidate id, so a changed eligibility decision cannot silently edit an
  audited draft.
* Draft `schema_version=1`; unknown extra keys are tolerated only when prefixed `x_`, and
  decision keys are rejected outright.

### Implemented commands

```
python .ai/tools/feature_registry/candidate_workspace.py build [--allow-refresh]
python .ai/tools/feature_registry/candidate_workspace.py list
python .ai/tools/feature_registry/candidate_workspace.py show --feature health
python .ai/tools/feature_registry/candidate_workspace.py validate
python .ai/tools/feature_registry/candidate_workspace.py check-freshness
```

---

## D. Candidate Inventory

| | health | blackboard |
|---|---|---|
| candidate_id | `cand-08fdc0b10a112ecf` | `cand-7f52cb8f583124db` |
| feature_id | health | blackboard |
| workspace_id | `ws-7181d8ccc758` | `ws-7181d8ccc758` |
| candidate_status | `NEEDS_REVIEW` | `NEEDS_REVIEW` |
| evidence_refs | 2 | 1 |
| context_refs | 1 | 0 |
| excluded_evidence | 0 | 0 |
| seed_eligibility counts | 1 `QUALIFIED_DIRECT`, 1 `..._WITH_LIMITATIONS` | 1 `QUALIFIED_DIRECT` |
| independent / not-independent | 2 / 0 | 0 / 1 |
| location integrity | COMPLETE × 2 | INCOMPLETE × 1 |
| verification_status | eligibility `CONDITIONAL`, test `NOT_RUN`, runtime/behavior/feature `NOT_VERIFIED`, basis `NO_EXECUTION_EVIDENCE` | same |
| content_digest | `da765709fd68…b666` | `5ed73359a390…c39b` |

**health** keeps both reviewed evidences side by side: different repositories, different
architectures (Node + signals vs Resource + exported state), different commits and digests.
The draft explicitly states "2 evidences are kept as separate sources and are not merged into one
implementation" and repeats the restricted-evidence note for `lnk-6fff3ce176bd5813`.

**blackboard** carries `independence = NOT_INDEPENDENT` with its reason and records the
dependency in `limitations`: derived from `bitbrain/beehave`, so not independent external
cross-validation. `independent_seed_count = 0`.

`NEEDS_REVIEW` is used deliberately instead of `DRAFT`: health contains a conditional seed,
blackboard is non-independent and has one item whose location cannot be dual-coordinated. No
draft claims `ADMITTED`, `PROMOTED` or `VERIFIED`; those values are rejected by validation.

---

## E. Evidence Audit

| | `lnk-d2d95d8162be1592` | `lnk-6fff3ce176bd5813` | `lnk-7084dc8999c2182b` |
|---|---|---|---|
| feature | health | health | blackboard |
| seed_eligibility | QUALIFIED_DIRECT | QUALIFIED_DIRECT_WITH_LIMITATIONS | QUALIFIED_DIRECT |
| classification | DIRECT_EVIDENCE | DIRECT_EVIDENCE | DIRECT_EVIDENCE |
| evidence_role | LINKAGE_EVIDENCE (3 items) | LINKAGE_EVIDENCE (1 item) | LINKAGE_EVIDENCE (5 items) |
| independence | INDEPENDENT | INDEPENDENT | **NOT_INDEPENDENT** |
| provenance | complete, analysis + file digests MATCHED | same | same |
| repository / commit | gdquest-demos/godot-make-pro-2d-games @ `7290681309ff…` | nezvers/Godot-GameTemplate @ `d5d8d1588742…` | bitbrain/beehave @ `fe589153fa78…` |
| source_digest | `ef9f678100f4…` | `fed9dc57052f…` | `e1b980ce875b…` |
| immutable URL | commit-pinned | commit-pinned | commit-pinned |
| evidence_location (first item) | record 23 → commit 20 | record 19 → commit 16 | record 24 → commit 21 |
| offset | +3, **verified by comparing both files** | +3, verified | +3, verified |
| item locations | 3/3 COMPLETE, symbol verified at commit line | 1/1 COMPLETE, symbol verified | 4/5 COMPLETE; `Blackboard` class item has no record line → **INCOMPLETE** |
| location_integrity | COMPLETE | COMPLETE | INCOMPLETE (`source_lookup_allowed=false`) |
| symbol notes | — | property-vs-function note preserved | — |

Every commit line was re-checked by re-reading the immutable file and confirming the symbol text
at that line (`take_damage`@20, `heal`@28, `health_changed`@3, `is_dead`@16, `keys`@21,
`set_value`@27, `has_value`@42, `erase_value`@50). The +3 offset was **derived** per file by
comparing the references copy with the commit copy and accepting only a pure prefix extension —
no hard-coded `-3`. When that comparison fails, or the record has no line, the result is
`LOCATION_INCOMPLETE` with `commit_line=null`; nothing is guessed and no lookup is allowed.

`seed_eligibility` and `location_integrity` are independent by design: blackboard stays
`QUALIFIED_DIRECT` while its location is `INCOMPLETE`, exactly as Batch B.2 requires.

---

## F. Context Audit

`lnk-a099657ab3c9930c` → `attack_emitter`, stored in the **health** draft's `context_refs`:

| Field | Value |
|---|---|
| context_kind | `GRAPH_DERIVED_RELATION` |
| derivation_type | `FEATURE_GRAPH_NEIGHBOUR` |
| feature_id (target) | `attack_emitter` |
| intermediate_feature_ids | `["health"]` |
| derivation_path | `["attack_emitter", "works_with", "health"]` |
| graph_edge_reference | `feature_graph.json#attack_emitter-works_with-health` |
| declaration origin | `Features/attack_emitter/feature.yaml:68` |
| counts_as_seed | **false** |
| counts_as_implementation_evidence | **false** |
| classification | `INDIRECT_EVIDENCE` |

It is not a DIRECT seed, not `QUALIFIED_DIRECT`, not `EXTERNAL_DIRECT_IMPLEMENTATION`, and its
target Feature remains `attack_emitter`. Validation rejects the record if it appears in
`evidence_refs`, if `counts_as_seed` is not `false`, or if `context_kind`/`derivation_type`
change. It adds nothing to any seed count, and `attack_emitter` still has no candidate.

Attaching it to the health draft is safe because the relation is stored with its own target
Feature, path and edge reference, and the draft `limitations` state that it is graph-derived and
not implementation evidence.

---

## G. Exclusions

| Excluded | Reason |
|---|---|
| `health_bar` Candidate | `NO_QUALIFIED_SEED` — 3 `POTENTIAL_RELEVANCE` + 2 `AMBIGUOUS`; the external `hp`/`max_hp` fields are not captured by the parser; `godot-open-rts/HealthBar.gd` has only private members |
| `openable_door` Candidate | `NO_QUALIFIED_SEED` — 2 `POTENTIAL_RELEVANCE` + 2 `AMBIGUOUS`; external `open()`/`is_locked` shares no identifier with `set_open`/`is_open` |
| `attack_emitter` DIRECT Candidate | no direct evidence at all; its only relation is graph-derived and lives in `context_refs` |

No empty candidate was created to make the workspace look complete, and no `POTENTIAL_RELEVANCE`
or `AMBIGUOUS` record was substituted for a seed. Both exclusions are recorded in
`WORKSPACE.json` with reason codes and their B.2 references.

---

## H. Test Results

| Command | Exit | Count | Result |
|---|---|---:|---|
| `python .ai/tools/feature_registry/tests/test_candidate_workspace.py` | 0 | **64** | OK |
| `python .ai/tools/feature_registry/candidate_workspace.py validate` | 0 | 2 candidates | both `VALID` |
| `python .ai/tools/feature_registry/candidate_workspace.py check-freshness` | 0 | 2 candidates | `FRESH: 2, STALE: 0, INCOMPLETE: 0` |
| `python .ai/tools/external_code/tests/test_feature_linkage.py` | 0 | 70 | OK |
| `python .ai/tools/external_code/feature_linkage.py check --pilot` | 0 | 150 records | FRESH 150, coverage 150/150 |
| `python .ai/tools/feature_registry/tests/test_feature_evidence_projection.py` | 0 | 41 | OK |
| `python .ai/tools/feature_registry/tests/test_feature_pipeline.py` | 0 | all | PASS (31 Features) |
| `python .ai/tools/learning/tests/test_source_analysis.py` | 0 | 17 | 0 failures |
| `python .ai/tools/external_code/tests/test_batch_a.py` | 0 | 38 | PASS |
| `python .ai/tools/external_code/tests/test_batch_b.py` | 0 | 33 | PASS |
| `python .ai/tools/validator/check_feature_metadata.py` | 0 | 31 Features | 0 error / 0 warning |

### Coverage of the new 64 tests

| Group | Tests | What they prove |
|---|---:|---|
| `PolicyTests` | 4 | policy loads and is scoped; wrong schema, non-seed qualification and duplicate seeds are refused |
| `EligibilityGuardTests` | 14 | qualified direct (+with limitations) accepted; pair-evaluation, NSL, POTENTIAL, AMBIGUOUS, unreviewed direct, incomplete provenance, mismatched digest, broken identity, out-of-scope, excluded feature and graph-derived all rejected with codes; `UNKNOWN` independence never becomes independent; rejections name field/value/expectation |
| `LocationTests` | 6 | record vs commit line differ and both are kept; offset derived (3 and 7 header lines); missing line → incomplete; unverifiable offset → incomplete; missing files → no fabricated location; graph item has no source line |
| `SchemaTests` | 17 | valid draft; missing field; forbidden/unknown status; non-seed classification; missing/UNKNOWN independence; missing provenance; missing dual coordinate; silent offset; lookup allowed while incomplete; context counted as seed; context listed as seed; tampered digest; schema version; verification claim; forbidden decision key |
| `CreationTests` | 11 | two separate health evidences, not merged; conditional seed kept; blackboard `NOT_INDEPENDENT` kept; attack_emitter context only; exclusions; idempotency; stable summary; no Feature Registry write; linkage records unmodified; atomic write leaves no partial file |
| `FreshnessTests` | 4 | real workspace fresh; changed record → STALE_LINKAGE; missing record → MISSING_LINKAGE; policy change → POLICY_CHANGED |
| `RealStoreEligibilityTests` | 7 | the three real qualifications match B.2; verified offsets `{3}` and line pairs `{(23,20),(31,28),(6,3)}`; property/function note preserved; blackboard class item incomplete; graph record never seed-eligible; helpers exclude `PAIR_EVALUATION` |
| `tearDownModule` | — | temp fixtures removed (verified: no `.tmp_candidate_workspace` residue) |

Idempotency was verified both by test and by direct measurement: a second `build` reported
`built: 0, unchanged: 2`, and the two candidate files and `WORKSPACE.json` were byte-identical
(same md5 before and after).

---

## I. Data Integrity

Hash comparison against the snapshot taken in Stage A (`.ai/tmp/phase174_baseline.json`,
git-ignored):

| Group | Before | After | Added | Removed | **Changed** |
|---|---:|---:|---:|---:|---:|
| Linkage records | 150 | 150 | 0 | 0 | **0** |
| External analysis records | 34 | 34 | 0 | 0 | **0** |
| Feature Evidence Projections | 5 | 5 | 0 | 0 | **0** |
| Feature metadata / index / graph / coverage | 34 | 34 | 0 | 0 | **0** |

Classification distribution unchanged: `NO_SUPPORTED_LINK` 128, `POTENTIAL_RELEVANCE` 10,
`AMBIGUOUS` 8, `DIRECT_EVIDENCE` 3, `INDIRECT_EVIDENCE` 1.

New files created by this stage (10):

```
.ai/tools/feature_registry/candidate_seed_policy.json      (new)
.ai/tools/feature_registry/candidate_eligibility.py        (new)
.ai/tools/feature_registry/candidate_workspace.py          (new)
.ai/tools/feature_registry/tests/test_candidate_workspace.py (new)
.ai/learning/candidate_workspace/WORKSPACE.json            (new)
.ai/learning/candidate_workspace/candidates/cand-08fdc0b10a112ecf.json (new)
.ai/learning/candidate_workspace/candidates/cand-7f52cb8f583124db.json (new)
.ai/context/PHASE_1_74_C_PREFLIGHT.md                      (new)
.ai/context/PHASE_1_74_C_ARCHITECTURE.md                   (new)
.ai/context/PHASE_1_74_C_CANDIDATE_WORKSPACE_FOUNDATION.md (this report)
.ai/tmp/phase174_baseline.json                             (new, git-ignored audit snapshot)
```

Modified files: **none**. Deleted files: **none**. Git: `master` @ `d64b1cd5`, staged 0,
modified 33 (the same pre-existing Phase 1.73 files, all hash-verified untouched by this stage),
untracked 359 → 368 (+9 visible; the snapshot and `__pycache__` are ignored). No commit, push,
fetch, pull, checkout, reset, clean or rebase was run. No Feature was created, no promotion
happened, no new evidence classification was introduced, and nothing was written into the Feature
Registry.

---

## J. Limitations

1. **Parser under-capture.** `@export var` with an initialiser, untyped `var` and property
   setters are still dropped by `gd_parse`. This is why `hp`/`max_hp` are invisible in
   `HealthResource.gd` (1 of 5 exports kept) and why `health_bar` has no seed. A candidate can
   only reference what the analysis captured; the absence of a symbol in a draft is not evidence
   the source lacks it.
2. **Dual coordinates are asymmetric.** `record_line` indexes the references copy and
   `commit_line` the immutable source. Both are stored, the offset is derived and verified per
   file, and both are reported; a consumer that reads only `record_line` against the commit URL
   will land three lines late. A seed whose offset cannot be proved is marked
   `LOCATION_INCOMPLETE` with `commit_line=null` and `source_lookup_allowed=false` — currently
   one blackboard item (the `class_name` evidence) is in that state.
3. **blackboard is not independent.** Its evidence is the acknowledged upstream of the internal
   Feature, so it corroborates the capability but is not independent external cross-validation;
   it is never counted in `independent_seed_count`.
4. **The two health evidences cannot be merged.** Different repositories, architectures
   (Node+signals vs Resource+exported state) and symbol kinds (`is_dead` property vs function).
   The draft keeps them separate by construction; there is no merge path in the code.
5. **Graph-derived is not implementation proof.** The `attack_emitter` reference records an
   internal graph relation plus a health-only analysis; it says nothing about external attack
   code and can never be counted as a seed.
6. **A candidate is not Feature verification.** Every draft has
   `feature/runtime/behavior_verification_status = NOT_VERIFIED` and
   `test_execution_status = NOT_RUN`; validation rejects any other value, and the draft states it
   is evidence grouping only.
7. **Only two Features are in scope.** `health_bar` and `openable_door` have no candidate because
   they have no qualified seed; the workspace records that rather than masking it.
8. **`NEEDS_REVIEW` for both drafts** is the honest status: no draft reaches `DRAFT` (the
   "nothing needs a human" state) because of items 2, 3 and 4.
9. **Eligibility is a policy artefact, not a derivation.** `independence`, qualification and
   architecture come from the reviewed `candidate_seed_policy.json`; if that file is edited
   without review, the drafts follow it. Mitigations: `policy_version` is part of the candidate
   id, `check-freshness` reports `POLICY_CHANGED`, and `load_policy` refuses non-seed
   qualifications and duplicate linkage ids.
10. **Freshness is upstream-limited.** `check-freshness` delegates to
    `feature_linkage.evaluate_freshness` + record digest comparison; it cannot detect a change in
    the remote repository, only local drift.

---

## K. Final Verdict

### `PASS_WITH_LIMITATIONS`

All 14 acceptance criteria are met:

| # | Criterion | Result |
|---|---|---|
| 1 | Candidate Workspace schema established | ✔ `candidate_workspace_draft` v1, validated by code |
| 2 | Eligibility Guard centralized | ✔ one module, one function, 10 checks, explained rejections |
| 3 | health Candidate created correctly | ✔ `cand-08fdc0b10a112ecf` |
| 4 | blackboard Candidate created correctly | ✔ `cand-7f52cb8f583124db` |
| 5 | Two health evidences kept separate | ✔ different repo/commit/digest/architecture, no merge path |
| 6 | blackboard `NOT_INDEPENDENT` preserved | ✔ in ref, summary and limitations |
| 7 | Graph-derived never enters seeds | ✔ context only, `counts_as_seed=false`, guarded twice |
| 8 | health_bar / openable_door create no Candidate | ✔ recorded as exclusions |
| 9 | Dual-coordinate constraint implemented | ✔ derived + symbol-verified; incomplete marked, never guessed |
| 10 | Candidate freshness checkable | ✔ `check-freshness`, FRESH 2/2 |
| 11 | Re-runs idempotent | ✔ content id + digest, built 0 / unchanged 2, byte-identical |
| 12 | No unexpected modification of original data | ✔ 0 changed across 223 hashed files |
| 13 | New tests and required regressions pass | ✔ 64 new + 70/41/17/38/33/31 existing, all exit 0 |
| 14 | Non-goals not implemented | ✔ no similarity/admission/promote/ranking/clustering/equivalence |

The `_WITH_LIMITATIONS` qualifier reflects the *evidence base*, not the implementation: one
evidence location is legitimately incomplete, one seed is non-independent, one seed is
conditional, and two Features still have no seed — all inherited from Batch B.2 and all recorded
in the artefacts rather than smoothed over.

**Next-stage recommendation:** the workspace is ready to be used as the input layer for a future
similarity stage, with three preconditions: (a) apply the policy table on top of the guard for
any additional Feature, (b) treat `location_integrity != COMPLETE` as "no source navigation"
rather than as a mild warning, (c) do not let `NOT_INDEPENDENT` evidence satisfy an
independence requirement. Before `health_bar` can join, the parser must capture
`@export`/untyped `var` declarations and the bar files must be re-analysed — no Candidate can fix
that.

Awaiting human acceptance.
