# Phase 1.73 — Batch B.2
# Evidence Readiness & Seed Qualification
# Final Report

Executed: 2026-11-15. Stage reports:

| Stage | Report |
|---|---|
| A Preflight | `PHASE_1_73_B2_PREFLIGHT.md` |
| B DIRECT audit | `PHASE_1_73_B2_DIRECT_EVIDENCE_AUDIT.md` |
| C INDIRECT audit | `PHASE_1_73_B2_INDIRECT_EVIDENCE_AUDIT.md` |
| D Role consumption | `PHASE_1_73_B2_EVIDENCE_ROLE_CONSUMPTION_AUDIT.md` |
| E Provenance | `PHASE_1_73_B2_MIZGODOTTOOLS_PROVENANCE.md` |
| F Symbol equivalence | `PHASE_1_73_B2_SYMBOL_EQUIVALENCE_ASSESSMENT.md` |
| G Seed eligibility | `PHASE_1_73_B2_SEED_ELIGIBILITY.md` |
| H Batch C readiness | `PHASE_1_73_B2_BATCH_C_READINESS.md` |

---

## A. Executive Summary

**Final verdict: `PASS_WITH_LIMITATIONS`**
**Batch C readiness: `READY_WITH_RESTRICTIONS`** — scope `health` + `blackboard`, `attack_emitter`
as graph-derived context only, `health_bar` and `openable_door` excluded.

| Item | Result |
|---|---|
| DIRECT records audited | 3/3 |
| `QUALIFIED_DIRECT` | 2 (`Stats.gd`→health; `blackboard.gd`→blackboard) |
| `QUALIFIED_DIRECT_WITH_LIMITATIONS` | 1 (`HealthResource.gd`→health) |
| `REJECTED_DIRECT` | 0 |
| INDIRECT records audited | 1/1 — `GRAPH_DERIVED_RELATION`, conditional auxiliary |
| Linkage read paths found | 1 (the producer itself); 0 downstream consumers |
| Real consumer defects found | 3 latent, all closed with helpers + tests |
| MizGodotTools SHA | **resolved**: `cb548f9035a3b892e34aebbadcb923e68327f2f8`, 71/71 digests verified |
| health_bar equivalence mechanism | **worth building, but not now** — blockers are parser capture and corpus, not a synonym table |
| Seeds qualified | 4 total: 2 ELIGIBLE, 1 CONDITIONAL direct, 1 CONDITIONAL graph |
| Records / analyses changed | **0** (all read-only; only tool code + tests + reports written) |

The batch's answer to "which evidence can be trusted" is narrower than the linkage store's
headline: of 150 records, **3 support a direct implementation claim and 1 more supports a
graph-derived relation**; the remaining 146 are clues, ties or null results and are explicitly
ineligible.

---

## B. Baseline

| Item | Value |
|---|---|
| Project Root | `F:/Godot_v4.7-stable/game` |
| Branch / HEAD | `master` / `d64b1cd5b576a44dcfafd7becbb2d2a7f1fd6a84` |
| Staged / Modified / Untracked (at Stage A) | 0 / 33 / 350 |
| External Analysis Records | 34 (11 complete, 22 partial, 1 unsupported) |
| Linkage Records | 150 |
| `DIRECT / INDIRECT / DECLARED / POTENTIAL / AMBIGUOUS / NSL` | 3 / 1 / 0 / 10 / 8 / 128 |
| `linkage_outcome` | LINKED 22, NOT_LINKED 128 |
| Item roles | `LINKAGE_EVIDENCE` 31, `PAIR_EVALUATION` 128 |
| Freshness | FRESH 150, STALE 0, MISSING_SOURCE 0, INVALID 0; coverage 150/150, exit 0 |
| Projections | health PARTIAL, health_bar PARTIAL, openable_door COMPLETE, attack_emitter PARTIAL, blackboard COMPLETE — all `NOT_VERIFIED` / `NOT_RUN` |

No divergence from the Batch B.1 report. Two new facts were established (reference-copy line
coordinates; `analysis_complete` under-reporting exports) and are carried as limitations.

---

## C. DIRECT Evidence Audit

| Record | Source | Verdict |
|---|---|---|
| `lnk-d2d95d8162be1592` | `gdquest-demos/godot-make-pro-2d-games@7290681309ff…` `actors/health/Stats.gd` | `QUALIFIED_DIRECT` |
| `lnk-7084dc8999c2182b` | `bitbrain/beehave@fe589153fa78…` `addons/beehave/blackboard.gd` | `QUALIFIED_DIRECT` (`NOT_INDEPENDENT`) |
| `lnk-6fff3ce176bd5813` | `nezvers/Godot-GameTemplate@d5d8d1588742…` `addons/top_down/scripts/damage/HealthResource.gd` | `QUALIFIED_DIRECT_WITH_LIMITATIONS` |

**Evidence locations (all verified against the files):**

* `Stats.gd`: `signal health_changed` commit 3; `func take_damage` 20; `func heal` 28 — record
  lines 6 / 23 / 31. Real data flow (`health -= amount` → `max(0, …)` → `emit_signal`), plus a
  `health_depleted` emission at zero. Limitations: `heal` uses `max(health, max_health)` (effectively
  a full heal) vs the Feature's `min(...)` clamp; death signal is `health_depleted`, not `died`;
  `health_changed` arity differs; `analysis_partial`, projection PARTIAL.
* `blackboard.gd`: `class_name Blackboard` commit 2; `keys` 21; `set_value` 27; `has_value` 42;
  `erase_value` 50. Genuine multi-board store (`_data[board][key]`), duplicate-on-assign, null-as-absent
  convention — not a thin `Dictionary` wrapper. Feature source header states it was abstracted from
  this repository, so the pair is corroboration, not independent evidence. Feature uses
  `duplicate(true)`, external uses shallow `duplicate()`.
* `HealthResource.gd`: `is_dead` at commit **16** as `@export var is_dead: bool` — a **property**,
  while the Feature exposes `func is_dead() -> bool` at line 57. It is genuinely health state
  (`is_dead = true` when `hp == 0`), backed by clamped `hp`/`max_hp`. Limitations: symbol-kind
  mismatch, single identifier, and the parser kept only 1 of 5 exports (`hp`, `max_hp`,
  `reset_hp`, `reset_max_hp` are invisible) despite `analysis_complete`.

**Deduplication question:** `Stats.gd` and `HealthResource.gd` are **not** duplicates — different
repositories, different architectures (Node + signals vs Resource + exported state), independent
authors. Both are kept; they are the only two seeds that corroborate one capability independently
of this project.

**Cross-cutting:** `line_reference` indexes the reference copy (`sources/` file + 3-line header);
commit line = `line_reference − 3`. Verified by hashing both copies of all three files (recorded
`source_digest` matches the `sources/` copy).

No classification was changed; no record was edited.

---

## D. INDIRECT Evidence Audit

`lnk-a099657ab3c9930c` (`ext-73c80a3db6d71e48` → `attack_emitter`). Chain:

1. `HealthResource.gd` → **health**, DIRECT on `is_dead` (`lnk-6fff3ce176bd5813`).
2. `Features/attack_emitter/feature.yaml:68` declares `relations.works_with: [health]` →
   graph edge `attack_emitter —works_with→ health` (edge object carries only
   `{from,to,type}`; **no rationale field**).
3. `_apply_indirect` promotes the pair, producing one `GRAPH_RELATION` item with
   `source_side=FEATURE_GRAPH`, `source_path=feature_graph.json`, `line_reference=null`,
   `intermediate_path=["attack_emitter","works_with","health"]`.

Does external code implement attack emission? **No** — the analysis matched zero symbols for
`attack_emitter` and the file has no attack entry point, hit detection or targeting.

Not circular: promotions run after all pairs are evaluated, `direct_by_feature` is captured
before the loop, so an indirect record can never seed another. Recorded relation type is
order-dependent (`works_with` and `commonly_used_with` both exist for this pair; the stronger one
is kept).

Typed as **`GRAPH_DERIVED_RELATION`** (`derivation_type=FEATURE_GRAPH_NEIGHBOUR`,
`intermediate_feature_ids=["health"]`, anchored on `lnk-6fff3ce176bd5813`). Permission:
**CONDITIONAL auxiliary** — never equivalent to DIRECT, never counted as an `attack_emitter`
implementation seed.

---

## E. Evidence Role Consumption Audit

Readers of `feature_links/`: **exactly one** — `feature_linkage.py` (loader, validation, freshness,
build, CLI). `search_assets.py` reads the *analysis* index, not linkage. Feature Evidence
Projection, Feature Index/Graph builders, Feature Registry, evaluation, learning, validator and
runtime tools do not touch linkage at all. So no existing path can misinterpret a marker today.

Producer-side semantics were already enforced by validation; the **consumer side was undefined**.
Three latent defects were closed additively in `feature_linkage.py`:

| Helper | Rule |
|---|---|
| `linkage_evidence_items(record)` | returns only role-marked supporting items; `PAIR_EVALUATION` never returned; legacy records without the field fall back to the classification (linked → non-`NONE` items, `NO_SUPPORTED_LINK` → nothing) |
| `is_graph_derived_relation(record)` | `True` only for `INDIRECT_EVIDENCE` whose items are all `GRAPH_RELATION` / `FEATURE_GRAPH` / have `intermediate_path` |

Measured on the real store: 150 records, **0 `PAIR_EVALUATION` items exposed**, **0
`NO_SUPPORTED_LINK` records with usable items**, 22 positive records (3 DIRECT, 1 INDIRECT,
10 POTENTIAL, 8 AMBIGUOUS), 1 graph-derived record.

Not fixed (documented instead): `DECLARED_CONTEXT` masked by a stronger tier; reference-copy line
coordinates. Both would require reclassifying or rewriting existing records.

5 tests added (`SeedQualificationTests`): pair-evaluation exclusion, linkage-evidence availability,
legacy fallback, `NO_SUPPORTED_LINK` never positive, graph-derived ≠ direct implementation.

---

## F. MizGodotTools Provenance

**`PROVENANCE_RESOLVED`** — `cb548f9035a3b892e34aebbadcb923e68327f2f8`.

* Local state had only `commit_sha: cb548f9035a3`, no `.git`, no 40-hex anywhere.
* API route blocked (`403 rate limit exceeded`, no token). Authorised read-only fallback:
  `https://github.com/Miziziziz/MizGodotTools/commit/cb548f9035a3.patch` → mbox header
  `From cb548f9035a3b892e34aebbadcb923e68327f2f8 …`, subject “Update .gitignore”,
  date `2026-07-20 14:26:43 -0400` (matches `_meta.pushed_at 18:26:45Z`).
* Identity verified: **71/71** mirror `.gd` files byte-identical to the tarball at the full SHA
  (`match 71, missing 0, diff 0`), `LICENSE` identical (1,066 bytes, MIT).
* Nothing was fetched into the workspace, nothing was rewritten: the mirror, catalog, provenance
  and analysis records were left untouched, so the historical `incomplete` status remains
  historically accurate.

Consequence: the *provenance* blocker for admitting this repository is closed; the *evidence*
blocker for `attack_emitter` is not — no file of it has been analysed. Admission is deferred to a
future authorised batch.

---

## G. Symbol Equivalence Assessment

`health_bar` has **no** shared identifier: internal `get_ratio` / `health_path` / `bar_size` vs
external `hp` / `max_hp` / `target_value` / `fill_rate` / `health_resource`.

Findings: `hp` and `max_hp` are current/max health **values** but are invisible to the parser in
`HealthResource.gd` (1 of 5 exports kept); `target_value` is a normalised display fraction, not
health; `get_ratio()` is a computation, not a field. Therefore **no `EXACT_SYMBOL_EQUIVALENCE`
exists**; the honest ceiling is `SEMANTIC_EQUIVALENCE` between an external field and an internal
*concept*, and `CONCEPTUAL_RELATEDNESS` for display plumbing. `godot-open-rts/HealthBar.gd` has
only private members and cannot participate at all.

Recommendation: a manual declaration mechanism is **worth building eventually** (with the schema
and the three rules in Stage F — commit-pinned, reviewer-signed, and never able to produce
`DIRECT_EVIDENCE`), but **not before the parser captures typed `@export`/untyped `var`
declarations and the bar files are re-analysed**. Implied seed count for `health_bar` today:
**zero**.

---

## H. Seed Eligibility

| Feature | ELIGIBLE direct | CONDITIONAL direct | Graph-derived | DECLARED | POTENTIAL | AMBIGUOUS |
|---|---:|---:|---:|---:|---:|---:|
| health | 1 | 1 | 0 | 0 | 0 | 2 |
| blackboard | 1 (not independent) | 0 | 0 | 0 | 3 | 0 |
| attack_emitter | 0 | 0 | 1 | 0 | 2 | 2 |
| health_bar | 0 | 0 | 0 | 0 | 3 | 2 |
| openable_door | 0 | 0 | 0 | 0 | 2 | 2 |

Seeds: `seed-lnk-d2d95d8162be1592` (health, ELIGIBLE), `seed-lnk-7084dc8999c2182b` (blackboard,
ELIGIBLE/not independent), `seed-lnk-6fff3ce176bd5813` (health, CONDITIONAL narrow claim),
`seed-lnk-a099657ab3c9930c` (attack_emitter, CONDITIONAL auxiliary).

Rules: 9-type eligibility table; three tightening clarifications (INDIRECT split by derivation,
independence as an attribute, `analysis_complete` cannot override known parser under-capture);
17-field minimum seed schema including `evidence_location` with **both** coordinate systems;
graph-derived extra fields (`derivation_type`, `derivation_path`, `graph_edge_references`,
`intermediate_feature_ids`, `source_linkage_id`).

Reasons for missing seeds: `health_bar` — naming gap + parser blind spot + one private-only file;
`openable_door` — external `open()`/`is_locked` vs internal `set_open`/`is_open`; `attack_emitter` —
no external attack API matched, only a token and a graph edge.

---

## I. Batch C Readiness

```
READY_WITH_RESTRICTIONS
```

* Evidence quality: all three DIRECT audited, INDIRECT typed, roles consistent on the only read
  path, no unresolved misclassification (three recorded limitations instead).
* Provenance: every seed has 40-hex SHA + pinned URL + MATCHED digest + allowlisted licence;
  MizGodotTools resolved but excluded from seeds.
* Coverage: health ✔, blackboard ✔, attack_emitter graph-only, health_bar ✘, openable_door ✘.
* Downstream safety: `PAIR_EVALUATION`, `POTENTIAL_RELEVANCE`-as-seed, graph-as-implementation and
  candidate-as-verified are each blocked by a guard + test, with one acknowledged residual risk:
  eligibility is **policy on top of the guard**, not built into it (clue records remain readable by
  design).

Batch C must not widen to five Features, must not count `NOT_INDEPENDENT` code as independent, and
must re-check freshness before using any seed.

---

## J. Regression & Final Verdict

| Check | Command | Exit | Result |
|---|---|---|---|
| Linkage tests | `python .ai/tools/external_code/tests/test_feature_linkage.py` | 0 | **70 tests, 70 passed** (65 + 5 new) |
| Freshness | `feature_linkage.py check --pilot` | 0 | FRESH 150, STALE 0, MISSING_SOURCE 0, INVALID 0; coverage 150/150 |
| Projection | `test_feature_evidence_projection.py` | 0 | 41 tests passed |
| Pipeline | `test_feature_pipeline.py` | 0 | all checks passed (31 Features) |
| Source analysis | `.ai/tools/learning/tests/test_source_analysis.py` | 0 | 17 checks, 0 failures |
| Phase 1.71 A | `test_batch_a.py` | 0 | 38 checks |
| Phase 1.71 B | `test_batch_b.py` | 0 | 33 checks |
| Feature metadata | `.ai/tools/validator/check_feature_metadata.py` | 0 | 31 Features, 0 error, 0 warning |

Synthetic fixtures: `SeedQualificationTests`, `EvidenceTests`, `SchemaTests`, `FreshnessTests`,
`StatusProtectionTests`. Real corpus: `PilotTests` (34 analyses, 170 pairs, 150 records) plus the
read-only data audits in Stages A–H — every count in this report comes from the live store, not
from a fixture.

**Data integrity:** 0 linkage records modified, 0 analysis records modified, 0 records promoted,
0 reclassified, 0 deleted. Tool change is additive: 2 read-side helpers + 5 tests. Git untouched
(no add/commit/push/reset/checkout); `master` @ `d64b1cd5…`; 33 pre-existing modifications
unchanged; untracked files grew only by this batch's reports.

**Final verdict: `PASS_WITH_LIMITATIONS`** — the audit itself is complete and conclusive, but the
evidence base it certifies is small: **two Features have seeds, one has only a graph-derived hint,
two have none**, and three of the four seeds carry named limitations. Batch C may proceed with the
stated restrictions; it must not treat 150 linkage records or 22 linked pairs as 22 pieces of
usable evidence.

Awaiting human acceptance. Batch C is not started.
