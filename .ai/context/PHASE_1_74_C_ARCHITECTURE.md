# Phase 1.74 — Batch C
# Stage B — Candidate Workspace Architecture Audit

Audit of what already exists, then the design that Stage C–G implement.

## B.1 What already exists and is reused

| Existing asset | Reuse |
|---|---|
| `.ai/tools/external_code/feature_linkage.py::load_linkage_records` | reads all 150 records; sole authority on record shape |
| `feature_linkage.evaluate_freshness(record)` | **reused as-is** for candidate freshness — no second freshness validator is written |
| `feature_linkage.linkage_evidence_items(record)` | reused so `PAIR_EVALUATION` markers can never enter a candidate |
| `feature_linkage.is_graph_derived_relation(record)` | reused for the context guard |
| `feature_linkage.LINKED_CLASSIFICATIONS`, `GRAPH_EVIDENCE_TYPES`, `FORBIDDEN_KEYS` | reused vocabulary; no new classification invented |
| `feature_linkage._atomic_write` pattern (mkstemp + `os.replace` in the target dir) | copied as a local helper (module-internal, 15 lines) rather than importing a private symbol |
| Projection status vocabulary (`NOT_VERIFIED`, `NOT_RUN`, `NO_EXECUTION_EVIDENCE`) | mirrored exactly in `verification_status` |
| `.ai/skills/…/code_library/sources|references/` file layout | used to resolve the dual coordinate (`sources/` = commit copy, `references/` = record copy) |
| `provenance.py` fields (`provenance_status`, `source_commit`, `source_digest`, `immutable_source_url`) | read, never recomputed |
| `feature_registry/tests/` conventions (fixture tree under `.tmp_*`, `unittest`, exit code) | followed |

**No existing candidate/workspace structure was found** — checked `.ai/tools/**`, `.ai/learning/**`,
`Feature Registry`, Asset Registry, evaluation and e2e. Nothing to extend, nothing to duplicate.

## B.2 New minimal modules

| File | Role | Lines (approx) |
|---|---|---|
| `.ai/tools/feature_registry/candidate_seed_policy.json` | reviewed eligibility policy transcribed from the B.2 report: scope, per-linkage qualification, independence, architecture, notes, exclusions, context relations | data |
| `.ai/tools/feature_registry/candidate_eligibility.py` | **single** eligibility guard: policy load/validate, `evaluate_seed_eligibility`, `build_evidence_reference`, `build_context_reference`, dual-coordinate resolver | ~380 |
| `.ai/tools/feature_registry/candidate_workspace.py` | draft schema + validation + content digest + stable id + atomic persistence + `build/list/show/validate/check-freshness` CLI + workspace summary | ~520 |
| `.ai/tools/feature_registry/tests/test_candidate_workspace.py` | schema, guard, location, creation, idempotency, atomicity, freshness tests | ~450 |

Workspace data (separate from the Feature Registry):

```
.ai/learning/candidate_workspace/
  WORKSPACE.json                  # workspace id, policy version, candidate index, exclusions
  candidates/<candidate_id>.json  # one draft per feature
```

## B.3 Data flow

```
feature_links/*.json  (read-only, 150)
        │  load_linkage_records()
        ▼
candidate_seed_policy.json ──► candidate_eligibility.evaluate_seed_eligibility(record, policy)
        │                              │  checks: scope, exists, classification, role,
        │                              │  graph-derived, provenance, digest, identity,
        │                              │  reviewed qualification, independence
        │                              ▼
        │                    build_evidence_reference() ── dual coordinate resolution
        │                              │                     (references copy vs sources copy,
        │                              │                      offset *verified*, symbol at line)
        ▼                              ▼
candidate_workspace.build_candidates() ──► draft dict ── validate_candidate_draft()
        │                                                  content_digest, stable candidate_id
        ▼
.ai/learning/candidate_workspace/candidates/*.json  (atomic write)
        ▼
list / show / validate / check-freshness   (read-only)
```

Nothing flows back: no module writes to `Features/`, the Feature Index/Graph, projections,
source analyses, analysis records or linkage records.

## B.4 Persistence and identity

* One JSON file per candidate, pretty-printed, trailing newline, written via `mkstemp` +
  `os.replace` in the destination directory (no half-written file; a failure leaves the previous
  file intact and no temp file behind).
* `candidate_id = "cand-" + sha256(feature_id | sorted(linkage_ids) | policy_version)[:16]` —
  **content identity, not a random id**. Re-running with the same inputs produces the same id and
  the same `content_digest`, so the file is rewritten byte-identically except `updated_at`
  (which is preserved when the digest is unchanged → true idempotency).
* `content_digest` = sha256 over canonical JSON (sorted keys, `content_digest` removed,
  `created_at`/`updated_at` excluded), so it is reproducible from the file.
* `budget` guard: a candidate whose referenced records changed (digest mismatch) is not silently
  rewritten; `check-freshness` reports it and `build` refuses without `--allow-refresh`.

## B.5 Schema version strategy

| Artefact | Version | Rule |
|---|---|---|
| policy | `policy_version = "phase-1.74-c/1"` | bump on any eligibility/qualification change; candidate id includes it, so a policy change yields a new identity rather than a silent edit |
| draft | `schema_version = 1` | additive-only within v1; unknown extra keys rejected unless prefixed `x_`; a future breaking change bumps to 2 and old drafts stay readable |
| workspace summary | `schema_version = 1` | same policy |

## B.6 Boundaries

| Boundary | Enforcement |
|---|---|
| Workspace ≠ Feature Registry | separate directory `.ai/learning/candidate_workspace/`; no import of `build_feature_index`; no write path into `Features/` |
| Draft ≠ Feature | `candidate_status` limited to `DRAFT` / `NEEDS_REVIEW` / `BLOCKED`; `ADMITTED` / `PROMOTED` / `VERIFIED` are rejected values |
| Draft ≠ promotion | no field can be written into Feature metadata; validator rejects `feature_registry_write`-style keys and any `verified`/`promoted`/`admitted` truthy field |
| Evidence reference ≠ evidence | reference stores identity + review snapshot only; the linkage record stays the source of truth and is re-checked by digest |
| Seed ≠ context | `evidence_refs` and `context_refs` are separate arrays with separate builders; the context builder refuses any record that yields seed eligibility |
| No parallel provenance/freshness store | provenance is copied from the record; freshness delegates to `feature_linkage.evaluate_freshness` |

## B.7 Eligibility guard contract (implemented in Stage D)

`evaluate_seed_eligibility(record, policy, location)` returns a dict, never a bare bool:

```
{"linkage_id", "eligible", "seed_eligibility", "independence",
 "derivation_type", "evidence_kind", "location_integrity",
 "codes": [...], "checks": [{"check","status","field","value","expected"}],
 "reason", "recoverable"}
```

Ten ordered checks; first failure yields `eligible=false` with a machine code, the offending
field, its current value, the expected value and whether it is recoverable. `seed_eligibility`
and `location_integrity` are **independent** fields, so a seed that passed B.2 but whose location
cannot be dual-coordinated is kept as `ELIGIBLE` with `location_integrity=PARTIAL` and
`source_lookup_allowed=false`, not rejected.

## B.8 Explicitly not implemented

Similarity engine, semantic similarity, symbol equivalence, ranking, clustering, deduplication
engine, admission gate/policy, promote, automatic Feature creation, Feature metadata/index/graph
edits, runtime/behaviour verification, code generation, health_bar / openable_door backfill,
graph→direct conversion, NOT_INDEPENDENT→INDEPENDENT conversion. No new evidence classification
is introduced.

## B.9 Design review (self-check before implementation)

| Requirement | Design answer |
|---|---|
| Centralized guard, no duplicated logic | one module, one function, called by the single draft builder |
| Two health evidences kept separate | `evidence_refs` is a list of per-linkage references; there is no merge path; id is hashed over the *set* of linkage ids, not a merged source |
| NOT_INDEPENDENT preserved | policy supplies it, guard requires it to be explicit, draft copies it verbatim, summary counts it separately from independent seeds |
| Graph-derived never a seed | context builder only; seed guard rejects `GRAPH_RELATION`/`is_graph_derived_relation` |
| Dual coordinates without silent −3 | offset computed by comparing both files' line arrays, only prefix-only differences accepted, then the symbol is re-checked at the computed commit line; otherwise `LOCATION_INCOMPLETE` |
| Idempotent | content-identity id + digest, `updated_at` preserved on no-change |
| Original data untouched | all inputs opened read-only; workspace is a new directory; Stage I hash comparison |

**Design accepted; proceeding to Stage C.**
