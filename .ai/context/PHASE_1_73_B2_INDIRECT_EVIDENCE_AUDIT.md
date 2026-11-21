# Phase 1.73 — Batch B.2
# Stage C — INDIRECT_EVIDENCE Lineage Audit

One record is classified `INDIRECT_EVIDENCE`:
`ext-73c80a3db6d71e48` → `attack_emitter` (`lnk-a099657ab3c9930c`),
`nezvers/Godot-GameTemplate` @ `d5d8d15887423b3a8acf0502efb6271c600a80bc`,
`addons/top_down/scripts/damage/HealthResource.gd`.

## C.1 What the external analysis proves

The analysis of `HealthResource.gd` proves exactly one thing about this Feature set: the file
implements a health state. It matched `health` on one identifier, `is_dead`.

The same analysis matched **nothing** for `attack_emitter`:

```
pair_evaluation.matched_symbols  = []
pair_evaluation.shared_tokens     = []
external_symbols = [HealthResource, add_hp, damaged, dead, full, hp_changed,
                    insta_kill, is_dead, is_full, max_hp_changed, prepare_load,
                    reset_resource, reset_update, set_max_hp]
```

The file has no attack entry point, no hit detection, no target selection, no projectile or
raycast use. Direct answer: **the external analysis proves HealthResource's health capability
only; `attack_emitter` is derived entirely inside the pipeline.**

## C.2 Where the record's evidence actually comes from

`lnk-a099657ab3c9930c` has one item:

| Field | Value |
|---|---|
| `evidence_type` | `GRAPH_RELATION` |
| `evidence_status` | `DECLARED` |
| `source_side` | `FEATURE_GRAPH` |
| `source_path` | `.ai/context/feature_graph.json` |
| `symbol_name` / `matched_value` | `health` / `works_with` |
| `intermediate_path` | `["attack_emitter", "works_with", "health"]` |
| `provenance_reference` | `feature_graph.json#attack_emitter-works_with-health` |
| `line_reference` | `null` |
| `missing_evidence` | "evidence is indirect: no direct identifier match between this analysis and this Feature" |

There is no `SYMBOL_EXACT_MATCH` item, no external symbol name, and no line in the external file.
The record is structurally incapable of claiming an external implementation — provided a
consumer reads the item role and type rather than the classification label alone.

## C.3 Derivation chain, step by step

| Step | Fact | Source of the fact | Evidence reference |
|---|---|---|---|
| 1 | `HealthResource.gd` implements health (`is_dead` exported, set from `hp == 0`) | external analysis item | `lnk-6fff3ce176bd5813` ev01, `analysis/ext-73c80a3db6d71e48.json#is_dead` |
| 2 | internal Feature `health` is a feature of this project | Feature projection | `.ai/learning/feature_evidence/health.json` (digest `cfeb979d…`) |
| 3 | internal graph declares `attack_emitter` —`works_with`→ `health` | `feature_graph.json` edge | `feature_graph.json#attack_emitter-works_with-health` |
| 4 | therefore this analysis is recorded as indirectly related to `attack_emitter` | classifier `_apply_indirect` | `lnk-a099657ab3c9930c` ev01 |

Step 3's origin: `Features/attack_emitter/feature.yaml:68-76` declares

```yaml
relations:
  works_with:
    - health
```

The edge is a **human-declared metadata relation with no rationale field**. The graph edge object
itself carries only `{from, to, type}` — no author, no source, no justification text. So step 3
is traceable to a file and a line, but not explained.

## C.4 Is the derivation sound as implemented?

Read from `feature_linkage.py::_apply_indirect`:

* Promotion only touches pairs currently classified `NO_SUPPORTED_LINK`; a pair that already has
  a clue or a declaration is never overwritten.
* Promotion requires the **same analysis** to hold a `DIRECT_EVIDENCE` record for the graph
  neighbour. The neighbour map is symmetric, so the relation may be traversed in either
  direction.
* `direct_by_feature` is captured **before** the promotion loop, so a promoted `INDIRECT_EVIDENCE`
  never seeds another promotion — no chained or circular derivation, no indirect-of-indirect.
* Only one edge is used (`break` after the first match); the path is exactly
  `[feature, edge_type, neighbour]`.
* The generated item is `DECLARED` / `FEATURE_GRAPH`, never `EXTRACTED`, and validation requires
  `GRAPH_RELATION` + `intermediate_path` for this classification.

Two observations, neither a defect but both worth recording:

1. `attack_emitter → health` exists twice (`works_with` and `commonly_used_with`). The first
   matching edge wins, so the recorded relation type is order-dependent; here it is
   `works_with`, the stronger of the two.
2. Symmetry means the same analysis could equally promote `health` from a direct
   `attack_emitter` link. The direction is therefore a property of which side was matched
   directly, not of the relation.

## C.5 Semantic classification

| Label | Applies? | Why |
|---|---|---|
| `EXTERNAL_DIRECT_IMPLEMENTATION` | **No** | no external symbol matches `attack_emitter`; the file contains no attack code |
| `GRAPH_DERIVED_RELATION` | **Yes** | the entire claim is: internal graph says attack_emitter works_with health, and this analysis is directly linked to health |
| `DECLARED_RELATION` | Partly | the underlying edge is human-declared metadata, but the *record* is derived by the tool, not declared by a human |
| `UNSUPPORTED_INFERENCE` | No | every step has a reference; nothing is invented |

Recorded as **`GRAPH_DERIVED_RELATION`** with `derivation_type = FEATURE_GRAPH_NEIGHBOUR`,
`intermediate_feature_ids = ["health"]`.

## C.6 Can it be misread as "external code implements attack emission"?

Textually, yes — the classification label `INDIRECT_EVIDENCE` sits next to
`feature_id=attack_emitter`, and a reader who skips the item would conclude the external file
emits attacks. Structurally it is protected: `source_side=FEATURE_GRAPH`, `source_path` points at
the graph (not the `.gd` file), `line_reference=null`, `matched_value=works_with`, and
`missing_evidence` says so explicitly. Batch B.2 added the read-side guard
`is_graph_derived_relation()` so a consumer can ask the question directly instead of re-deriving
the answer from fields.

## C.7 Seed permission

| Question | Answer |
|---|---|
| May it be a seed equivalent to `DIRECT_EVIDENCE`? | **No.** |
| May it be a restricted auxiliary seed? | **Yes**, under the conditions below. |
| What is its legitimate use? | It asserts that external health code exists in a project whose health component this system expects to be used together with an attack emitter — a hint that the external project may also contain an attack component worth a targeted search, nothing more. |

Conditions for the restricted use:

1. Derivation chain complete — satisfied (4 steps, each referenced).
2. Every relation has a recorded origin — satisfied for the edge (feature.yaml line 68) but the
   edge has **no rationale**, so it is `CONDITIONAL`, not `ELIGIBLE`.
3. No semantic jump — none: the record never claims an attack API.
4. The seed must be labelled `derivation_type=FEATURE_GRAPH_NEIGHBOUR`, must cite both the
   direct record on `health` and the graph reference, and must never appear in a
   "direct implementations" count.
5. It cannot be used to satisfy "attack_emitter has a seed": `attack_emitter` still has zero
   direct seeds.

## C.8 Verdict

**Lineage is complete and correctly typed; the record is a `GRAPH_DERIVED_RELATION` and only a
conditional auxiliary seed.** No implementation change was required. The feature-metadata edge it
depends on has no recorded justification, which is the one weakness in the chain and the reason
the permission is conditional rather than clean.
