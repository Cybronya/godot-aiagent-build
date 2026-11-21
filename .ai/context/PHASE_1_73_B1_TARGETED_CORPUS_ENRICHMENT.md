# Phase 1.73 — Batch B.1
# Targeted External Corpus Enrichment
# Final Report

Executed: 2026-11-15 (preflight 14:33:58Z). Stage reports:
`PHASE_1_73_B1_PREFLIGHT.md`, `PHASE_1_73_B1_REPOSITORY_CANDIDATES.md`,
`PHASE_1_73_B1_PROVENANCE_LICENSE_REPORT.md`, `PHASE_1_73_B1_EXTERNAL_ANALYSIS_REPORT.md`.

---

## A. Executive Summary

| Item | Result |
|---|---|
| Final verdict | **PASS_WITH_LIMITATIONS** |
| Repositories accepted | **5** (4 fully gate-valid, 1 `license_text_missing` under existing policy) |
| Repositories rejected | 1 (missing full commit SHA) + 2 `NEEDS_REVIEW` + 3 rejected for name-only/redundant relevance |
| New Analysis Records | **20** (6 `analysis_complete`, 14 `analysis_partial`, 0 unsupported) |
| New Linkage Records | **+85** (65 → **150**) |
| New `DIRECT_EVIDENCE` | **+3** (health ×2, blackboard ×1) |
| New `INDIRECT_EVIDENCE` | **+1** (attack_emitter via `works_with` → health) |
| New `POTENTIAL_RELEVANCE` | +7 (3 → 10) |
| New `AMBIGUOUS` | +8 (0 → 8) |
| `DECLARED_CONTEXT` | 0 (unchanged) |
| `NO_SUPPORTED_LINK` | 62 → 128 |
| Unable to evaluate | 5 → 20 pairs (4 analyses × 5) |
| Freshness | 150/150 FRESH, coverage 150/150, 0 STALE / MISSING_SOURCE / INVALID |
| Historical data | all 65 Batch B records preserved: same `linkage_id`, same classification, same source digests |
| Recommend entering Batch C? | **Yes, with a defined scope** — use `DIRECT_EVIDENCE` + `INDIRECT_EVIDENCE` seeds only; treat `POTENTIAL_RELEVANCE`/`AMBIGUOUS` as clues, never as findings (see J) |

The batch did not lower any threshold, relax any gate, or manufacture a link. The growth in
linkages is entirely a consequence of adding genuinely related, provenance-complete code.

---

## B. Baseline (before this batch)

| Item | Value |
|---|---|
| Project Root | `F:/Godot_v4.7-stable/game` |
| Branch / HEAD | `master` / `d64b1cd5b576a44dcfafd7becbb2d2a7f1fd6a84` |
| Staged / Modified / Untracked | 0 / 33 / 240 files (`-uall`) |
| Repository Catalog | 7,270 entries, 6,813 unique fragments |
| Reference files / Source repositories | 6,813 / 77 |
| External Analysis Records | 14 (5 complete, 8 partial, 1 shader) |
| Feature Evidence Projections | 5 — health PARTIAL, health_bar PARTIAL, openable_door COMPLETE, attack_emitter PARTIAL, blackboard COMPLETE; all `NOT_VERIFIED` / `NOT_RUN` |
| Feature Linkage Records | 65 — 0 DIRECT, 0 INDIRECT, 0 DECLARED, 3 POTENTIAL, 62 NO_SUPPORTED_LINK, 5 unevaluable |
| Linkage freshness | FRESH 65/65 |

After the batch: staged 0, modified **33 (unchanged)**, untracked **350** files — the 240
pre-existing ones plus exactly the 110 artefacts this batch produced (20 analysis records,
85 linkage records, 5 reports). No tracked file was modified, no user change was reverted.

---

## C. Repository Discovery

Full table and rationale: `PHASE_1_73_B1_REPOSITORY_CANDIDATES.md`.

**Accepted (5)** — selected from the existing mirror, judged on read source code:

| Repository | Files | Feature coverage | Evidence basis |
|---|---|---|---|
| gdquest-demos/godot-make-pro-2d-games | 6 | health, health_bar, attack_emitter, openable_door | `Stats.gd` `take_damage`/`heal`/`health_changed`; `Lifebar.gd` binds `health_changed` to a `TextureProgress`; `DamageSource.gd` `damage`; `HitBox.gd`/`Door.gd` |
| bitbrain/beehave | 3 | blackboard | `class_name Blackboard` + `set_value/get_value/has_value/erase_value/keys` |
| gdquest-demos/godot-open-rpg | 5 | openable_door, health_bar, attack_emitter | `class_name Door` with `is_locked`/`open()`; `ui_life_bar.gd` tween against `max_value`; `battler_action_attack.gd` → `take_hit` |
| nezvers/Godot-GameTemplate | 4 | health, health_bar, attack_emitter | `HealthResource` `hp/max_hp/is_dead` + `damaged`/`dead` signals; `HealthPanel` ratio; `ProximityAttack` range |
| lampe-games/godot-open-rts | 2 | health_bar | `HealthBar.gd` recomputes a gradient from `_unit.hp / _unit.hp_max`, connects `hp_changed` |

**Rejected / not selected:**

| Repository | Decision | Reason |
|---|---|---|
| Miziziziz/MizGodotTools | REJECT | no full 40-char SHA in the mirror (`commit_sha_full: null`) → `provenance_status=incomplete`; B.1 forbids incomplete SHA as new source proof |
| godotengine/godot-demo-projects | NEEDS_REVIEW | one thin demo `health.gd`; coverage already satisfied |
| foxssake/netfox | NEEDS_REVIEW | a `health-progress-bar.gd` exists but netfox is already analysed; redundant here |
| gdquest-demos/godot-platformer-2d | REJECT | duplicates make-pro's damage pattern, no new capability |
| MrEliptik/godot_experiments (`hinge_door.gd`), GodotVR/godot-xr-tools (`fall_damage.gd`, `damage_area.gd`) | REJECT | name-only similarity: no state, no interaction system, no health model in the code |

**Coverage of the five pilot Features:** all five now have at least one analysis of code that
genuinely implements the capability. Only `health` and `blackboard` reach
`DIRECT_EVIDENCE`; `health_bar`, `openable_door` and `attack_emitter` remain at
clue/indirect level because their external code shares no exact identifier with the Feature.

---

## D. Provenance & License

Full detail: `PHASE_1_73_B1_PROVENANCE_LICENSE_REPORT.md`. Gate used unchanged
(`provenance.py` + `provenance_validator.py --repo`).

| Repository | Full commit SHA | License | `license_status` | `provenance_status` | Validator |
|---|---|---|---|---|---|
| gdquest-demos/godot-make-pro-2d-games | `7290681309ffcd700c2c08a8e59a57bfbec14d5e` | MIT + LICENSE | eligible | complete | valid |
| gdquest-demos/godot-open-rpg | `d59f2f71bc046ac53239a4e590861269e7100a36` | MIT + LICENSE | eligible | complete | valid |
| lampe-games/godot-open-rts | `a628ad3bb6a9a903587a181a7ee3300dbf735e81` | MIT + LICENSE | eligible | complete | valid |
| nezvers/Godot-GameTemplate | `d5d8d15887423b3a8acf0502efb6271c600a80bc` | MIT + LICENSE | eligible | complete | valid |
| bitbrain/beehave | `fe589153fa780a3f88989578ceb5f539afffb7c2` | MIT (API) | `license_text_missing` (risk recorded, `copy_allowed=true`) | complete | incomplete (license text only) |
| Miziziziz/MizGodotTools | **—** | MIT + LICENSE | eligible | **incomplete** | incomplete → rejected |

On the 20 records themselves: `provenance_status=complete` 20/20,
`immutable_source_url=true` 20/20, `source_consistent=true` 20/20, 64-hex
`source_digest` 20/20, `license_status=eligible` 17/20 (+3 beehave
`license_text_missing`), `copy_allowed` 20/20.

---

## E. External Analysis

Full detail: `PHASE_1_73_B1_EXTERNAL_ANALYSIS_REPORT.md`.

* 20 records produced through the existing CLI/schema/parser: **6 complete, 14 partial,
  0 unsupported**; total analyses 14 → **34**; index re-built to 34 entries (exit 0).
* `analysis_partial` reasons are concrete and preserved per record: missing `class_name`
  (6 files), custom property-setter/annotation (`@tool`, `@export ... set:`; 6 files),
  private-only symbol surface (3 files: `door_trigger.gd`, `door_unlock_interaction.gd`,
  `HealthBar.gd`).
* Parser limitation verified by probe: `gd_parse` drops untyped `var` / `@export var`
  declarations and property setters, so fields such as `current_health`, `maximum` and
  `@export var size` never enter the symbol table. Not patched — recorded.
* No shader or unsupported file was analysed; nothing was reported complete that the parser
  did not fully handle.

---

## F. Linkage Results

Re-evaluated with the existing CLI only (`feature_linkage.py build --pilot`), no threshold
change.

| Metric | Before | After | Delta |
|---|---:|---:|---:|
| Analysis Records | 14 | 34 | +20 |
| Linkage Records | 65 | 150 | +85 |
| DIRECT_EVIDENCE | 0 | 3 | **+3** |
| INDIRECT_EVIDENCE | 0 | 1 | **+1** |
| DECLARED_CONTEXT | 0 | 0 | 0 |
| POTENTIAL_RELEVANCE | 3 | 10 | +7 |
| AMBIGUOUS | 0 | 8 | +8 |
| NO_SUPPORTED_LINK | 62 | 128 | +66 |
| Unable to Evaluate | 5 | 20 | +15 |

Sum check: 3 + 1 + 0 + 10 + 8 + 128 = 150 records; 20 unevaluable pairs = 4 analyses × 5
Features (`simple_fast_blur.gdshader`, `door_trigger.gd`, `door_unlock_interaction.gd`,
`HealthBar.gd`).

### F.1 Per-Feature distribution (records)

| Feature | DIRECT | INDIRECT | POTENTIAL | AMBIGUOUS | NO_SUPPORTED_LINK |
|---|---:|---:|---:|---:|---:|
| health | 2 | 0 | 0 | 2 | 26 |
| health_bar | 0 | 0 | 3 | 2 | 25 |
| openable_door | 0 | 0 | 2 | 2 | 26 |
| attack_emitter | 0 | 1 | 2 | 2 | 25 |
| blackboard | 1 | 0 | 3 | 0 | 26 |

### F.2 The 22 positive / ambiguous records (every one evidence-backed)

| analysis_id | source | feature | classification | evidence |
|---|---|---|---|---|
| ext-1d204b35464cf388 | make-pro `actors/health/Stats.gd` | health | **DIRECT** | `take_damage`, `heal`, `health_changed` (EXTRACTED, both sides) |
| ext-1d204b35464cf388 | same | attack_emitter | POTENTIAL | token `damage` |
| ext-1d204b35464cf388 | same | health_bar | POTENTIAL | token `health` |
| ext-23949c1378c49203 | beehave `blackboard.gd` | blackboard | **DIRECT** | `Blackboard`, `keys`, `set_value`, `has_value`, `erase_value` |
| ext-27ddd863881677d7 | beehave `blackboard_set.gd` | blackboard | POTENTIAL | token `blackboard` |
| ext-55aef2d453370c1b | beehave `blackboard_compare.gd` | blackboard | POTENTIAL | token `blackboard` |
| ext-73c80a3db6d71e48 | nezvers `HealthResource.gd` | health | **DIRECT** | `is_dead` |
| ext-73c80a3db6d71e48 | same | attack_emitter | **INDIRECT** | graph `attack_emitter → works_with → health` (health is DIRECT-linked) |
| ext-73c80a3db6d71e48 | same | health_bar | POTENTIAL | token `health` |
| ext-409141da889d20af | nezvers `ActorDamage.gd` | health / attack_emitter | AMBIGUOUS | tokens `damage`, `dead`, `died` tie between two Features |
| ext-51d46c1b4943a254 | open-rpg `doors/door.gd` | openable_door | POTENTIAL | tokens `door`, `open` |
| ext-7973e94ee75e2819 | nezvers `ProximityAttack.gd` | attack_emitter / openable_door | AMBIGUOUS | tokens `attack` vs `target` |
| ext-7d7933a2343f52d0 | open-rpg `ui_life_bar.gd` | health_bar / openable_door | AMBIGUOUS | tokens `fill` vs `target` |
| ext-d5f7ac2db3a8c4e4 | open-rpg `battler_action_attack.gd` | attack_emitter | POTENTIAL | token `attack` |
| ext-d82bd2e536c75c4a | nezvers `HealthPanel.gd` | health / health_bar | AMBIGUOUS | token `health` (hp/max_hp → progress shader) |
| ext-aa0204cc227b0480 | statecharts `animation_tree_state.gd` (Batch B) | blackboard | POTENTIAL | token `tree` |
| ext-fb806b579659b155 | netfox `Idle.gd` (Batch B) | health_bar | POTENTIAL | token `display` |
| ext-fe3acf782b88edda | PankuConsole `env.gd` (Batch B) | openable_door | POTENTIAL | token `open` |

(22 records; 3 DIRECT + 1 INDIRECT + 10 POTENTIAL + 8 AMBIGUOUS.)

The three `DIRECT_EVIDENCE` records are the ones with locatable identifiers on both sides;
each item names the external symbol, its line where the parser recorded one, the Feature
projection's `evidence_id`, and both source paths. Nothing was promoted on file-name or
short-token similarity.

### F.3 Why `DECLARED_CONTEXT` is still 0

`Features/blackboard/feature.yaml` declares
`snippet_id: bitbrain__beehave__addons__beehave__blackboard.gd`, and that exact snippet was
analysed in this batch. The pair is nevertheless classified `DIRECT_EVIDENCE` because exact
identifiers outrank a declaration in the classifier's tier order, so the declaration is not
surfaced as a separate item. This is existing Batch B behaviour, reported rather than
silently changed (see G.3).

---

## G. Evidence Semantics Audit (Stage F)

### G.1 Pair Evaluation vs Linkage Evidence — finding

Before this batch, a `NO_SUPPORTED_LINK` record carried one item under `evidence_items`
whose content was, correctly, *“compared N symbols … no exact match …”*. The item was
already typed `NONE` with `evidence_status=MISSING`, the record already said
`linkage_outcome=NOT_LINKED`, and validation already forbade any supporting evidence type on
such a record. So the conclusion was never modelled as a positive link — but the distinction
lived only in a convention (`evidence_type=NONE`), inside a field called `evidence_items`.

Verdict: **not a factual mis-modelling, but an under-specified schema.** 128 of 150 records
currently rely on that convention.

### G.2 Two minimal fixes applied

**(1) Duplicate evidence for one identifier.** The external parser lists some names twice
(function + entry point). `evaluate_pair` matched both and emitted two items, inflating
`evidence_items` and the evidence count of the new `DIRECT` records (5 items where 3
identifiers exist; 9 where 5 exist). Fixed with `_one_item_per_identifier()`: one item per
identifier, first occurrence wins. This changes no classification and no historical record
(all 65 Batch B records had a single item). Test:
`test_duplicate_symbol_tables_do_not_duplicate_evidence`.

**(2) Explicit evidence role (additive, optional).**

| Aspect | Before | After |
|---|---|---|
| item fields | `evidence_id, evidence_type, evidence_status, source_side, source_path, symbol_name, line_reference, matched_value, explanation, provenance_reference` | + optional `evidence_role` |
| allowed values | — | `LINKAGE_EVIDENCE` / `PAIR_EVALUATION` |
| `NO_SUPPORTED_LINK` | one `NONE` item, positive/non-positive only by convention | item must be `PAIR_EVALUATION`; a `LINKAGE_EVIDENCE` role is rejected |
| linked classifications | — | an item may not be a `PAIR_EVALUATION` marker |
| old records without the field | — | still valid (optional) |
| schema_version | 1 | **1 (unchanged)** |

Measured on the store: `NO_SUPPORTED_LINK` → 100 % `PAIR_EVALUATION`; `DIRECT`, `INDIRECT`,
`POTENTIAL`, `AMBIGUOUS` → 100 % `LINKAGE_EVIDENCE`.

### G.3 Historical compatibility

* All 65 Batch B records: same filename, same `linkage_id`, same classification, same
  `analysis_record_digest` and `feature_projection_digest` — verified programmatically against
  a pre-batch snapshot (`drift class: []`, `drift id: []`).
* They were re-emitted by the documented rebuild (`build --pilot`), so they now also carry
  `evidence_role` and a current `generated_at`; their semantic content is unchanged.
* `schema_version` was **not** bumped; records without `evidence_role` still validate and
  check fresh (test `test_records_without_role_marker_stay_compatible`).
* No threshold, no classifier tier, no classification rule was changed. `DECLARED_CONTEXT`
  co-existence with `DIRECT` (F.3) was deliberately left as-is and documented.

---

## H. Freshness & Regression

### H.1 Real corpus commands (project CLI, this batch)

| Command | Exit | Result |
|---|---|---|
| `python .ai/tools/external_code/external_code_understanding.py --reindex` | 0 | “indexed 34 analysis record(s)” (idempotent) |
| `python .ai/tools/external_code/feature_linkage.py build --pilot` | 0 | 170 pairs, 150 evaluated, 20 unevaluable, 150 built, 0 failed |
| `python .ai/tools/external_code/feature_linkage.py check --pilot` | 0 | FRESH=150, STALE=0, MISSING_SOURCE=0, INVALID=0; coverage expected 150 / checked 150 / missing 0 / unexpected 0 |
| duplicate `linkage_id` count | — | 0 |
| missing pair count | — | 0 |
| generator/schema version drift | — | 0 (all `phase-1.73-b/1`, `schema_version=1`) |

### H.2 Synthetic tests (fixtures)

`python .ai/tools/external_code/tests/test_feature_linkage.py` → **65 tests, 65 PASS, 0 FAIL,
exit 0**. Covers schema, evidence semantics, status protection, freshness, atomic-write
failure injection, the duplicate-identifier regression, the `evidence_role` rules, and the
old-record compatibility case. Fixtures live under
`.ai/tools/external_code/tests/.tmp_linkage` and are deleted after the run.

### H.3 Real corpus tests (inside the same suite, read-only + temp output)

Same command, `PilotTests` class: 34 analysis records with 11 complete / 22 partial /
1 shader and index agreement; 5 projections; 170 pairs → 150 records + 20 unevaluable; every
record validates and is FRESH; no forbidden decision keys; DIRECT links evidence-backed;
verification never upgrades; all analysis/projection inputs byte-identical before and after;
analysis index cross-check `MATCHED`; CLI build/check exit codes; unknown `analysis_id` → 1.

### H.4 Regression suites

| Suite | Exit |
|---|---|
| `test_feature_evidence_projection.py` (Batch A + A.1) | 0 |
| `test_feature_pipeline.py` | 0 |
| `test_source_analysis.py` (17 checks / 0 failures) | 0 |
| `test_batch_a.py` (Phase 1.71 Batch A) | 0 |
| `test_batch_b.py` (Phase 1.71 Batch B) | 0 |
| `check_feature_metadata.py` (31 features) | 0 — 0 error(s), 0 warning(s) |

### H.5 Protected inputs

| Artefact | State |
|---|---|
| `Features/*/feature.yaml`, `feature_index.json`, `feature_graph.json` | not written (pre-existing modifications untouched; mtimes pre-date the batch) |
| 5 Feature Evidence Projections | not written; digests recorded in all 150 records still match |
| Feature Source Analysis | not written |
| 14 original External Analysis Records | not written; digests unchanged |
| Existing 65 Linkage Records | preserved (see G.3) |
| Catalog / Source / Reference library / Provenance originals | read-only (mirror only read; no file added to the library) |
| Scene Intent / Promote / Feature Registry | untouched |
| Candidate / Similarity / Admission / Decision agents | none created (validation rejects such keys) |
| Git | branch `master`, HEAD `d64b1cd5…`; staged 0; 33 modified (unchanged); no add/commit/push/pull/fetch/reset/checkout/merge/rebase |

---

## I. Limitations

1. **`health_bar` has no direct evidence.** Real bindings exist (`HealthPanel`, `Lifebar`,
   `ui_life_bar`, rts `HealthBar`) but they use names such as `hp`, `max_hp`, `target_value`,
   `current_health`, which share no exact identifier with the Feature's `get_ratio` /
   `health_path` / `class_name HealthBar`. Result: POTENTIAL ×3, AMBIGUOUS ×2, no DIRECT.
2. **Private-only files are unevaluable.** `HealthBar.gd` (rts), `door_trigger.gd` and
   `door_unlock_interaction.gd` expose only `_`-prefixed members, which the classifier
   excludes as non-distinctive; 15 of the 20 new pairs therefore have no record.
3. **`openable_door` and `attack_emitter` stay at token/clue level.** Their external code
   (`Door.open()`, `is_locked`, `AttackBattlerAction`, `ProximityAttack`) has no shared
   identifier with `set_open`/`is_open`/`do_attack`/`attack_hit`. Only one indirect link
   reaches `attack_emitter`, through the Feature graph.
4. **Parser gaps limit evidence.** Untyped `var`/`@export var` and property setters are
   dropped by `gd_parse`, so several fields that *do* correspond to Feature symbols never
   compete for a match.
5. **Ambiguity from generic tokens.** 8 records are `AMBIGUOUS` because a single word
   (`target`, `damage`, `health`, `fill`) matches two Features at the same weakest tier.
   These are honest tie outcomes, not evidence of dual relevance; they are also a signal
   that tier-1 token matching is noisy at this corpus size.
6. **`DECLARED_CONTEXT` is not surfaced when a stronger tier wins** (F.3) — the blackboard
   declaration is real but hidden behind `DIRECT_EVIDENCE`.
7. **A key repository is unavailable.** Miziziziz/MizGodotTools (the declared source of
   `attack_emitter`) cannot enter the corpus until a full commit SHA is recorded in its
   mirror metadata; this is the single largest remaining evidence gap for `attack_emitter`.
8. **One repository carries a licence-text risk** (beehave: MIT per GitHub API, no local
   LICENSE file). Accepted under the existing recorded-risk policy; it would flip to
   `blocked_license` if that policy is tightened.
9. **Unevaluable pairs are not "unrelated"** — they mean the current symbol surface cannot be
   compared, not that the code is irrelevant.
10. **No shader or non-GDScript source** was brought in; those remain outside the pipeline.

---

## J. Final Verdict

**PASS_WITH_LIMITATIONS**

1. **Did we find genuinely relevant external code?** Yes — five repositories whose *source
   code* implements health, health-bar binding, door state/interaction, attack delivery and
   blackboard storage. Name-only candidates were rejected and one powerful candidate was
   rejected for provenance.
2. **Do source, commit and licence meet the existing standard?** Yes for all 20 records
   (complete provenance, pinned 40-char commit URLs, allowlisted licence); one repository
   carries the pre-existing `license_text_missing` risk, recorded per record and here.
3. **Can the existing pipeline understand the new code?** Yes — 6 complete, 14 partial, 0
   fake-complete, with the parser's gaps recorded per file.
4. **Did the new analysis produce valid new linkages?** Yes: 3 `DIRECT_EVIDENCE` and 1
   `INDIRECT_EVIDENCE`, each with locatable identifiers or a graph path, plus 15 additional
   clue-level or ambiguous records — with **no** change to matching thresholds.
5. **Can the mechanism distinguish real evidence, context clues and name similarity?**
   Yes, and the distinction is now explicit: `evidence_role` separates positive linkage
   evidence from pair-evaluation markers, and `DIRECT` items must carry EXTRACTED identifiers
   on both sides. Generic-word ties are reported as `AMBIGUOUS`, not as links.
6. **Is the corpus sufficient to enter Batch C?** Partly — sufficient for a scoped Batch C
   on `health` and `blackboard` (two direct seeds), and for one graph-derived
   `attack_emitter` case. Not sufficient for an unqualified "all five Features" similarity
   study: `health_bar` still lacks a direct seed and `openable_door` has only clues.

**Recommendation:** proceed to Batch C only with scope limited to pairs seeded by
`DIRECT_EVIDENCE`/`INDIRECT_EVIDENCE`, treating `POTENTIAL_RELEVANCE` and `AMBIGUOUS` as
clues requiring manual confirmation, and with two prerequisites recorded: (a) obtain a full
commit SHA for Miziziziz/MizGodotTools, (b) decide whether feature-side health-bar symbols
(`get_ratio`/`health_path`) or external `hp`/`max_hp` naming should be declared as an
equivalence, since no automatic identifier match can bridge them.

Batch B.1 stops here. No Batch C work, no similarity engine, no candidate workspace, no
admission gate, no promotion, no Git operation. Awaiting human acceptance and further
authorisation.
