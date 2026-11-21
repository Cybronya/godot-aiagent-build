# Phase 1.73 — Batch B.2
# Stage D — Evidence Role Consumption Audit

Question: does anything in the project read linkage records, and can it mistake a pair
evaluation, a clue or a graph-derived relation for real evidence?

## D.1 Inventory of linkage readers

Searched the whole tree for `feature_links`, `external_analysis_feature_linkage`,
`linkage_classification`, `evidence_role`, `PAIR_EVALUATION`, `LINKAGE_EVIDENCE`.

| Module | Reads linkage? | Notes |
|---|---|---|
| `.ai/tools/external_code/feature_linkage.py` | **Yes** (sole reader) | `load_linkage_records`, `evaluate_freshness`, `validate_linkage`, `build_linkages`, CLI `build`/`check` |
| `.ai/tools/external_code/tests/test_feature_linkage.py` | Yes (tests) | fixture store + the real store in `PilotTests` |
| `.ai/tools/feature_registry/feature_evidence.py` | **No** | reads Feature sources + `.ai/learning/source_analysis` only |
| `.ai/tools/feature_registry/build_feature_index.py`, `compose_features.py`, `discover_feature.py`, `feature_discovery.py`, `discovery_to_binding.py`, `add_relations.py` | **No** | Feature metadata / index / graph construction |
| `.ai/tools/feature_registry/search_assets.py` | **No** | reads `.ai/learning/external_code/index.json` (the *analysis* index) and the catalog; never linkage |
| `.ai/tools/validator/check_feature_metadata.py` | No | Feature metadata validation |
| `.ai/tools/evaluation/*`, `.ai/tools/learning/*` | No | unrelated evidence systems (`evidence_signature`, `result_analysis`) |
| Scene Intent / Promote / Feature Registry runtime | No | no reference anywhere |

**Conclusion:** exactly one module consumes linkage, and it is the module that produces it. There
is no external-analysis→Feature-consumer path, and no consumer that could currently promote,
score or admit anything from a linkage record.

## D.2 Three categories requested

1. **Already consumes linkage:** `feature_linkage` itself (build, validate, check, CLI report).
2. **Able to read linkage but does not:** the analysis *index* reader `search_assets.py` is the
   only neighbouring component with any external-corpus knowledge; it reads
   `external_code/index.json`, not `feature_links/`.
3. **Not connected to linkage:** Feature Evidence Projection, Feature Index/Graph builders,
   Feature Registry, coverage matrix, evaluation, learning, validator, runtime tools.

## D.3 Role semantics on the actual read paths

Checked against the 150 stored records, not only fixtures:

| Property | Measured |
|---|---|
| Items carrying `evidence_role` | 150/150 records |
| `LINKAGE_EVIDENCE` items | 31 |
| `PAIR_EVALUATION` items | 128 |
| `NO_SUPPORTED_LINK` records whose items are all `PAIR_EVALUATION` | 128/128 |
| Linked records containing a `PAIR_EVALUATION` item | 0 |
| Records without the field | 0 in the store (Batch B's 65 were re-emitted), 1 covered by a compatibility test |

The producer side was already sound (Batch B.1 validation rejects both mismatches). The gap was
on the **consumer** side: nothing defined how a reader is supposed to use the field, and in
particular what to do with a record that predates it. A naive consumer doing
`for item in record["evidence_items"]` would have picked up 128 pair-evaluation markers.

## D.4 Minimal change made

Two read-side helpers were added to `feature_linkage.py` (additive, no schema, no threshold, no
classifier change, no record rewritten):

```python
linkage_evidence_items(record) -> list[dict]
    # the only sanctioned way to enumerate a record's supporting items
    # role == PAIR_EVALUATION  -> never returned
    # role == LINKAGE_EVIDENCE -> returned
    # role missing (Batch B)   -> classification decides:
    #                             linked -> non-NONE items kept, NO_SUPPORTED_LINK -> nothing

is_graph_derived_relation(record) -> bool
    # True only for INDIRECT_EVIDENCE whose support is entirely
    # GRAPH_RELATION / FEATURE_GRAPH / has intermediate_path
```

Behaviour on the real store (executed):

```
records 150
usable items:      attack_emitter 5, health 4, health_bar 5, blackboard 4, openable_door 4
PAIR_EVALUATION items exposed: 0
NO_SUPPORTED_LINK records with usable items: 0
graph-derived records: [('ext-73c80a3db6d71e48','attack_emitter')]
positive records by class: DIRECT 3, INDIRECT 1, POTENTIAL 10, AMBIGUOUS 8
```

The helpers do not decide eligibility (that is Stage G's table, applied by a future stage); they
only guarantee that the inputs to that decision are the right ones.

## D.5 Tests added (D.3 requirements)

Class `SeedQualificationTests`, 5 tests, in `.ai/tools/external_code/tests/test_feature_linkage.py`:

| Requirement | Test |
|---|---|
| `PAIR_EVALUATION` never becomes a seed | `test_pair_evaluation_marker_is_never_seed_evidence` |
| `LINKAGE_EVIDENCE` can enter qualification | `test_linkage_evidence_is_available_for_qualification` |
| Legacy record without the field follows a safe rule | `test_legacy_record_without_role_uses_safe_default` (both a linked and a `NO_SUPPORTED_LINK` legacy record) |
| `NO_SUPPORTED_LINK` is not positive evidence | `test_no_supported_link_is_never_positive_evidence` |
| Graph-derived ≠ external direct implementation | `test_graph_derived_relation_is_not_direct_implementation` |

Suite result: **70 tests, 70 passed, exit 0** (65 before this stage).

## D.6 Defects found

| # | Issue | Severity | Action |
|---|---|---|---|
| 1 | No read-side API; `evidence_items` mixed positive evidence with pair-evaluation markers | Medium (latent) | fixed by `linkage_evidence_items()` |
| 2 | Legacy records without `evidence_role` had no defined read rule | Medium (latent) | fixed by the classification fallback, covered by test |
| 3 | Nothing distinguished graph-derived support from direct support at read time | Medium (latent) | fixed by `is_graph_derived_relation()` |
| 4 | `DECLARED_CONTEXT` never surfaces when a stronger tier wins, so a real declaration can be invisible | Low | **not fixed** — changing tier precedence would change classifications; documented instead (B.1 §F.3, Stage G) |
| 5 | `line_reference` indexes the reference copy, not the commit file | Low (documentation) | **not fixed** — a coordinate remap would rewrite 150 records' meaning; documented and required in the seed schema |

No consumer was modified, no record was rewritten, nothing was promoted.

## D.7 Verdict

**Consumption path is safe today and explicitly guarded for Batch C.** The role vocabulary is
honoured on the only existing read path, the three latent consumer-side defects are closed with
helpers plus tests, and the two remaining issues are documentation-level and recorded as seed
constraints rather than silently repaired.
