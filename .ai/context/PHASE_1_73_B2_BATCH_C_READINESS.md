# Phase 1.73 — Batch B.2
# Stage H — Batch C Readiness Decision

Decision: **`READY_WITH_RESTRICTIONS`**

Permitted scope: Batch C may proceed for **health** and **blackboard**, with **attack_emitter**
present only as graph-derived context. **health_bar** and **openable_door** are excluded.

## H.1 Evidence quality

| Condition | Result |
|---|---|
| Are all 3 `DIRECT_EVIDENCE` records individually audited? | **Yes** — Stage B; 1 `QUALIFIED_DIRECT`, 1 `QUALIFIED_DIRECT` (not independent), 1 `QUALIFIED_DIRECT_WITH_LIMITATIONS` |
| Is the `INDIRECT_EVIDENCE` clearly marked as graph-derived? | **Yes** — Stage C; typed `GRAPH_DERIVED_RELATION`, `source_side=FEATURE_GRAPH`, guarded by `is_graph_derived_relation()` |
| Is `evidence_role` semantically consistent on read paths? | **Yes** — Stage D; 0 `PAIR_EVALUATION` items exposed, 0 `NO_SUPPORTED_LINK` records with usable items, legacy fallback tested |
| Unresolved misclassifications? | **No reclassification needed.** Three known *limitations* are recorded rather than fixed: reference-copy line coordinates, `DECLARED_CONTEXT` masked by a stronger tier, and `analysis_complete` under-reporting exports |

## H.2 Provenance

| Condition | Result |
|---|---|
| Do the seeds have complete provenance? | **Yes** — 40-char SHA, commit-pinned URL, 64-hex digest MATCHED, licence allowlisted (beehave: `license_text_missing`, risk recorded) |
| Any seed with incomplete provenance? | **No** |
| MizGodotTools resolved or excluded? | **Resolved** (`cb548f9035a3b892e34aebbadcb923e68327f2f8`, 71/71 digests + LICENSE verified) but **not admitted** and **not a seed** — no analysis exists for it, and admission is deferred to a future authorised batch |

## H.3 Seed coverage

| Feature | Qualified seed? | Detail |
|---|---|---|
| health | **Yes** | 1 ELIGIBLE (`Stats.gd`) + 1 CONDITIONAL (`HealthResource.gd`), two independent repositories |
| blackboard | **Yes** | 1 ELIGIBLE, `NOT_INDEPENDENT` (derived from this upstream) |
| attack_emitter | **Graph-derived only** | 1 CONDITIONAL auxiliary; zero implementation seeds |
| health_bar | **No** | 3 POTENTIAL + 2 AMBIGUOUS; blocker is naming + parser capture, not absence of real bar code |
| openable_door | **No** | 2 POTENTIAL + 2 AMBIGUOUS; external door state uses a different API vocabulary |

Missing seeds for two Features do not stop Batch C; they define its scope.

## H.4 Downstream safety

| Guarantee | Mechanism | Verified |
|---|---|---|
| `PAIR_EVALUATION` cannot enter a seed | `linkage_evidence_items()` returns role-marked items only | test + 0 occurrences on 150 real records |
| `AMBIGUOUS` cannot enter a seed | not in `LINKED` handling for seeds; eligibility table marks it INELIGIBLE; `linkage_evidence_items` returns its items, so eligibility is applied by the table — **see residual risk R1** | policy + tests |
| `POTENTIAL_RELEVANCE` cannot be auto-upgraded | classifier tier order unchanged; validation forbids direct evidence on a POTENTIAL record; no promotion code exists | tests |
| Graph-derived ≠ external implementation | `is_graph_derived_relation()`; GRAPH items carry `source_side=FEATURE_GRAPH`, `line_reference=null` | test + 1 real record |
| Feature Candidate cannot be mistaken for a verified Feature | no candidate concept exists; projections are `NOT_VERIFIED` / `NOT_RUN`; `FORBIDDEN_KEYS` rejects `verified` / `promoted` / `candidate` keys in linkage records | tests |

### Residual risks carried into Batch C

* **R1 — eligibility is policy, not code.** `linkage_evidence_items()` filters roles, not
  classifications: an `AMBIGUOUS` or `POTENTIAL_RELEVANCE` record still yields its clue items. A
  Batch C consumer must therefore apply the Stage G table (or an equivalent gate) on top. This is
  intentional — clues must remain readable — but it means the guarantee is "guard + policy", not
  "guard alone".
* **R2 — reference-copy line coordinates.** Seeds must record both coordinate systems; a consumer
  that opens the commit URL and jumps to `line_reference` will land 3 lines late.
* **R3 — non-independence of blackboard.** Counting `blackboard.gd` as third-party corroboration
  would overstate coverage.
* **R4 — one narrow direct seed.** `HealthResource.gd` supports only the death-flag/HP claim.
* **R5 — no seed for two of five Features**, so a Batch C that assumes five-Feature coverage would
  be unsound.

## H.5 What Batch C must and must not do

Must:
1. Enumerate seeds only through the Stage G rules and the Stage D helpers.
2. Re-check freshness before use; refuse STALE / MISSING_SOURCE records.
3. Label every seed with `qualification_status`, `independence`, `derivation_type` where relevant.
4. Keep `health_bar` and `openable_door` out of scope; keep `attack_emitter` in auxiliary context.
5. Carry the reference-coordinate note with every location reference.

Must not:
* treat a graph-derived relation as an implementation;
* count `NOT_INDEPENDENT` code as independent evidence;
* promote, verify or admit anything;
* widen to all five Features to make the batch look complete.

## H.6 Decision

```
READY_WITH_RESTRICTIONS
scope:        health, blackboard            (seeds present)
auxiliary:    attack_emitter               (graph-derived context only)
excluded:     health_bar, openable_door     (no qualified seed)
precondition: apply Stage G eligibility on top of linkage_evidence_items()
```
