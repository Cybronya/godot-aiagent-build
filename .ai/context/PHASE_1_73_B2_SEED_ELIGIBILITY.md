# Phase 1.73 — Batch B.2
# Stage G — Seed Eligibility Specification

Formal rules for which stored evidence may enter a later stage (Batch C) as a **seed**, and what
each seed may be used to claim. Derived from Stage B (direct audit), C (indirect lineage),
D (consumption guards) and F (symbol equivalence).

Nothing here changes linkage classification, thresholds or records. This is a selection policy
applied **on top of** the frozen linkage store.

## G.1 Evidence type → eligibility

| Evidence type | Default eligibility | Permitted use |
|---|---|---|
| `QUALIFIED_DIRECT` | **ELIGIBLE** | full seed: may seed a similarity/comparison study for that Feature |
| `QUALIFIED_DIRECT_WITH_LIMITATIONS` | **CONDITIONAL** | seed only inside its recorded limitation envelope |
| `GRAPH_DERIVED_RELATION` | **CONDITIONAL** | auxiliary context only; never counted as an implementation seed |
| `DECLARED_CONTEXT` | **REVIEW_REQUIRED** | usable only after human confirmation of the declaration |
| `POTENTIAL_RELEVANCE` | **INELIGIBLE** | search lead only |
| `AMBIGUOUS` | **INELIGIBLE** | never a seed |
| `NO_SUPPORTED_LINK` | **INELIGIBLE** | not positive evidence (and not negative evidence either) |
| `PAIR_EVALUATION` (item role) | **INELIGIBLE** | not linkage evidence at all |
| Unable to Evaluate | **INELIGIBLE** | no basis to evaluate |
| `REJECTED_DIRECT` | **INELIGIBLE** | rejected evidence |

### G.1.1 Three clarifications (tightening, never relaxing)

1. **`INDIRECT_EVIDENCE` is split by derivation type.** `GRAPH_DERIVED_RELATION` ⇒ CONDITIONAL
   auxiliary. A hypothetical `INDIRECT_EVIDENCE` that were not graph-derived would require its
   own review; none exists today.
2. **Independence is an attribute, not a grade.** `blackboard.gd` stays ELIGIBLE but must carry
   `independence = NOT_INDEPENDENT`; it corroborates capability but cannot be counted as an
   independent third-party implementation.
3. **`analysis_complete` does not override known parser under-capture.** Where the parser is
   demonstrably dropping declarations (Stage B.3: 1 of 5 exports kept), the seed is CONDITIONAL
   regardless of the completeness label, because absent symbols are not evidence of absence.

No rule was loosened to raise the seed count.

## G.2 Minimum field set per seed

Every seed record must carry all of the following. `null` is allowed only with a stated
`missing_reason`; fields are never fabricated.

| Field | Source | Notes |
|---|---|---|
| `seed_id` | derived | stable, e.g. `seed-<linkage_id>` |
| `feature_id` | linkage record | |
| `external_analysis_id` | linkage record | |
| `repository` | `external_analysis.source_repository` | |
| `commit_sha` | `external_analysis.source_commit` | must be 40 hex |
| `source_path` | `external_analysis.source_path` | commit-relative |
| `source_digest` | `external_analysis.source_digest` | 64 hex, verified MATCHED |
| `linkage_id` | linkage record | |
| `evidence_role` | item | `LINKAGE_EVIDENCE` for every seed item |
| `evidence_type` | item | `SYMBOL_EXACT_MATCH` / `DECLARED_*` / `GRAPH_RELATION` |
| `evidence_reference` | item `provenance_reference` | |
| `evidence_location` | item + source | **must be explicit about coordinates**: `line_reference` (reference copy) **and** the commit line = `line_reference − 3`, plus the immutable commit URL |
| `qualification_status` | Stage B/G | `QUALIFIED_DIRECT` / `..._WITH_LIMITATIONS` / `GRAPH_DERIVED_RELATION` |
| `limitations` | record + Stage B | copied, not summarised away |
| `qualification_reason` | Stage B | which audit produced the status |
| `independence` | Stage B | `INDEPENDENT` / `NOT_INDEPENDENT` |

Additional fields when graph-derived:

| Field | Value here |
|---|---|
| `derivation_type` | `FEATURE_GRAPH_NEIGHBOUR` |
| `derivation_path` | `["attack_emitter", "works_with", "health"]` |
| `graph_edge_references` | `feature_graph.json#attack_emitter-works_with-health`; declaration origin `Features/attack_emitter/feature.yaml:68` |
| `intermediate_feature_ids` | `["health"]` |
| plus `source_linkage_id` | the direct record that anchors the chain (`lnk-6fff3ce176bd5813`) |

Read-side rules a seed consumer must obey (enforced by helpers added in Stage D):

* obtain items only via `feature_linkage.linkage_evidence_items(record)`;
* ask `feature_linkage.is_graph_derived_relation(record)` before counting a seed as an
  implementation;
* a seed never asserts `feature_verified`, runtime or behavioural truth — every projection in
  this project is `NOT_VERIFIED` / `NOT_RUN`.

## G.3 Coverage per Pilot Feature

| Feature | ELIGIBLE direct | CONDITIONAL direct | Graph-derived | DECLARED_CONTEXT | POTENTIAL | AMBIGUOUS |
|---|---:|---:|---:|---:|---:|---:|
| health | **1** | **1** | 0 | 0 | 0 | 2 |
| blackboard | **1** (not independent) | 0 | 0 | 0 | 3 | 0 |
| attack_emitter | 0 | 0 | **1** | 0 | 2 | 2 |
| health_bar | 0 | 0 | 0 | 0 | 3 | 2 |
| openable_door | 0 | 0 | 0 | 0 | 2 | 2 |

### Seed inventory (4 concrete seeds)

| seed_id | Feature | Source | Commit | Pinned path | Status |
|---|---|---|---|---|---|
| `seed-lnk-d2d95d8162be1592` | health | gdquest-demos/godot-make-pro-2d-games | `7290681309ffcd700c2c08a8e59a57bfbec14d5e` | `actors/health/Stats.gd` | ELIGIBLE |
| `seed-lnk-6fff3ce176bd5813` | health | nezvers/Godot-GameTemplate | `d5d8d15887423b3a8acf0502efb6271c600a80bc` | `addons/top_down/scripts/damage/HealthResource.gd` | CONDITIONAL (narrow claim) |
| `seed-lnk-7084dc8999c2182b` | blackboard | bitbrain/beehave | `fe589153fa780a3f88989578ceb5f539afffb7c2` | `addons/beehave/blackboard.gd` | ELIGIBLE, `NOT_INDEPENDENT` |
| `seed-lnk-a099657ab3c9930c` | attack_emitter | nezvers/Godot-GameTemplate | `d5d8d15887423b3a8acf0502efb6271c600a80bc` | *(graph only; no external location)* | CONDITIONAL auxiliary |

### Why the other three Features have no seed

* **health_bar** — zero shared identifiers with the Feature vocabulary (`get_ratio`,
  `health_path`, `bar_size` vs `hp`, `max_hp`, `target_value`, `fill_rate`); `hp`/`max_hp` are not
  even visible to the parser; the third candidate file (`godot-open-rts/HealthBar.gd`) exposes only
  private members and could not be evaluated. Clues only. See Stage F.
* **openable_door** — external door code names its state `open()` / `is_locked` / `_on_area_entered`
  while the Feature exposes `set_open` / `is_open` / `state_changed`. Token overlap on
  `door` / `open` yields POTENTIAL/AMBIGUOUS only. The Feature projection is COMPLETE, so the gap
  is on the external side, not in Feature metadata.
* **attack_emitter** — Feature vocabulary is `do_attack` / `_apply_damage` / `attacked` /
  `attack_hit`; external candidates use `attack` (token only) or nothing. Its single
  `INDIRECT_EVIDENCE` is graph-derived and must not be counted as an implementation seed. The
  declared upstream (MizGodotTools) is still unanalysed even though its SHA is now resolved
  (Stage E).

### Seed-count integrity check

`4 seeds` = 3 direct records + 1 graph-derived record, of which exactly **2 are ELIGIBLE**
(`Stats.gd` — `INDEPENDENT`; `blackboard.gd` — `NOT_INDEPENDENT`), **1 is a CONDITIONAL direct
seed** (`HealthResource.gd` — `INDEPENDENT`), and **1 is CONDITIONAL auxiliary** (graph-derived,
not an implementation of `attack_emitter`).

Effective coverage: health has two unrelated repositories (1 clean + 1 restricted claim),
blackboard has one repository whose code is the acknowledged origin of the internal Feature, and
`health_bar`, `openable_door`, `attack_emitter` have no independent implementation seed at all.
Only **two of the four seeds** could corroborate the same capability independently of this
project (`Stats.gd`, `HealthResource.gd`), and they cover a single Feature.

## G.4 Prohibitions carried into any downstream use

1. `PAIR_EVALUATION` items, `NO_SUPPORTED_LINK`, `AMBIGUOUS`, `POTENTIAL_RELEVANCE` never become
   seeds — enforced by `linkage_evidence_items()`.
2. `GRAPH_DERIVED_RELATION` never becomes a direct implementation claim — enforced by
   `is_graph_derived_relation()`.
3. No automatic promotion of any seed to "Feature implemented", "verified", "admitted" or
   "candidate". A seed is a *point of comparison*, not a conclusion.
4. No threshold, classifier or record is modified to increase seed counts.
5. Seeds are re-validated against freshness before use: a STALE or MISSING_SOURCE record cannot
   seed anything.
