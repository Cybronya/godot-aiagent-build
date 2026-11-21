# PHASE 1.76 — BATCH C
## Evidence Impact Review

**Task Type:** READ-ONLY EVIDENCE IMPACT AUDIT
**Phase:** 1.76 / **Batch:** C
**Prerequisite:** Batch B Finalization = `FINALIZATION_PASS_WITH_LIMITATIONS` (verified)
**Execution Mode:** read-only audit; independent impact assessment
**Authorization Boundary:** Batch C only. Batch D was **not** started and the Review Queue was **not** created.

---

## A. Executive Summary

Batch C answers one question: *what would change if the Parser 1.76 / 1.75 results were
formally consumed, and what must remain unchanged until human approval?*

**Answer:** nothing in the formal layer would change automatically, and only a small,
reviewable set of evidence could change if a human chose to consume it.

| Finding | Result |
|---|---|
| Batch B → formal analysis mapping | **34 / 34 exact identity matches**, 0 missing formal records |
| Workspace results consumed by the formal layer | **No** — all 34 formal records remain `gd_parse@1.71`, created 2026-11-14…2026-11-15, before Batch B (2026-11-16) |
| Symbols inventoried | **59** = 44 new (Batch B) + 1 reclassified + 14 from the 4 reused Phase 1.75 records; **0 removed** |
| Symbols with potential evidence impact | **13** (46 `NO_IMPACT`) |
| New **exact-identifier** matches introduced by Batch B's 44 new symbols | **0** |
| Exact match recovered by the reused Phase 1.75 records | **1** (`get_value`, blackboard) |
| PARTIAL records reviewed | **3 / 3**; 3 declarations missing, of which **2 are not flagged by the parser** |
| `target_value` | **1** existing linkage reference (AMBIGUOUS), representation correction only, not a removal |
| Candidates reviewed | **2 / 2**; no qualification change, all seeds on reused analyses, all digests verified |
| Seed Policy | `READ_ONLY_REVIEWED` — implicit (not explicit) workspace exclusion; no coverage-status gate |
| Formal data mutation | **0** across 384 files |
| Verdict | **`PASS_WITH_LIMITATIONS`** |
| Batch D readiness | **`READY_FOR_BATCH_D_WITH_RESTRICTIONS`** |

Four headline findings:

1. **No Batch B symbol creates a new exact identifier match** against the five audited
   Features (`health`, `health_bar`, `openable_door`, `blackboard`, `attack_emitter`).
   Every Batch B "potential" impact is token-level, semantic, or coverage-related.
2. **The strongest evidence change would come from the reused Phase 1.75 record**
   `ext-23949c1378c49203`, whose `get_value` is an exact FUNCTION match that the formal
   DIRECT blackboard linkage (and its seed) does not currently list.
3. **PARTIAL coverage under-reports itself.** Two declarations
   (`expand_to` in `board_member_button.gd`, `title_label` in `board_card.gd`) are absent
   from the symbol table without any `unsupported_constructs` entry.
4. **`target_value` is a representation correction, not a deletion**, and the only
   evidence item touching it is an AMBIGUOUS door link that the new representation makes
   less plausible — not more.

---

## B. Prerequisite Verification

| Prerequisite | Required value | Observed | Source |
|---|---|---|---|
| Finalization result | `FINALIZATION_PASS_WITH_LIMITATIONS` | `FINALIZATION_PASS_WITH_LIMITATIONS` | `PHASE_1_76_B_FINALIZATION_PATCH.md:265` |
| Verdict | `PASS_WITH_LIMITATIONS` | `PASS_WITH_LIMITATIONS` | patch `:259`, report `:589` |
| Batch C readiness | `READY_FOR_BATCH_C_WITH_RESTRICTIONS` | `READY_FOR_BATCH_C_WITH_RESTRICTIONS` | patch `:260`, report `:626` |

All three match. No `BLOCKED_PREREQUISITE_MISMATCH`.

The three Batch C restrictions were applied throughout:

1. The 3 `PARTIAL` records were never read as "no evidence".
2. `target_value` was read as a property, not as a lost variable.
3. No linkage was rebuilt, refreshed or regenerated; all 150 were read only.

---

## C. Input Inventory and Identity

### C.1 Batch B workspace (read-only)

| Item | Count | Note |
|---|---:|---|
| Files | **162** | unchanged before/after Batch C |
| `manifest.json` records | 34 | 29 `REANALYZED_AND_VALIDATED`, 4 `REUSED_PHASE_1_75`, 1 `NOT_APPLICABLE` |
| `original/` | 34 | pre-Batch-B copies |
| `reanalyzed/` | 29 | parser 1.75 workspace, build `gd_parse@1.75+build:6b74a6cd20a06033` |
| `diff/` | 29 | symbol diff + coverage |
| `validation/` | 34 | per-record + reuse + workspace validation |
| `deterministic_runs/` | 29 | 29/29 identical (Batch B) |
| `idempotency/` | 2 | 162 → 162 (Batch B) |
| `reports/` | 3 | summary, reuse validation, excluded |

### C.2 Formal data (read-only)

| Layer | Count | Version / identity | Digest basis |
|---|---:|---|---|
| External Analysis | **34** | `parser_version=1.71` on all 34 | `input_digest`, `source_digest`, `commit_sha_full` |
| Feature Linkage | **150** | derived from the 34 analyses; 30 analyses × 5 Features | `analysis_record_digest`, `linkage_id` |
| Candidates | **2** (+ `WORKSPACE.json`) | `policy_version=phase-1.74-c/1`, both `NEEDS_REVIEW` | `content_digest`, `analysis_record_digest`, `linkage_record_digest` |
| Feature Metadata | 31 | `feature_index.json` registry_version as stored | file digest |
| Feature Graph | 80 edges | feature-level only, **no symbol-level edges** | file digest |
| Seed Policy | 3 seeds, 1 context relation | `phase-1.74-c/1` | file digest |
| Phase 1.75 workspace | 29 files | 4 reused records' source of truth | file digest |
| Batch A inventory | 1 | authoritative 34-record scope | file digest |

Formal records were created **2026-11-14T13:57:06Z … 2026-11-15T14:51:51Z**; Batch B
generated its workspace on **2026-11-16**. Combined with `parser_version=1.71` and the
unchanged digests, this establishes that the formal layer has **not** consumed any
Batch B result.

---

## D. Batch B → Formal Analysis Mapping (C1)

Match keys used: repository, full commit SHA, source path, source digest, input digest,
plus the formal `analysis_id`. Repository name or symbol name alone was never used.

**Result: 34 / 34 `EXACT_IDENTITY_MATCH`** (all five checks true for every record),
**0** digest-only / commit-only / path-only / ambiguous / missing-formal-record cases.

| Impact status | Records |
|---|---:|
| `WORKSPACE_ONLY_NOT_CONSUMED` | 29 |
| `REUSED_P75_WORKSPACE_ONLY_NOT_CONSUMED` | 4 |
| `NOT_APPLICABLE_NOT_CONSUMED` | 1 |

| # | batch_b_record_id | repository | commit | source_path | source_digest | batch_b_parser | formal_analysis_id | formal_parser | identity_match | impact_status |
|---|---|---|---|---|---|---|---|---|---|---|
| 1 | `ext-1d204b35464cf388` | gdquest-demos/godot-make-pro-2d-games | `7290681309ff` | `actors/health/Stats.gd` | `ef9f678100f4` | `gd_parse@1.75+build:6b74a6cd20a06033` | `ext-1d204b35464cf388` | `gd_parse@1.71` | EXACT_IDENTITY_MATCH | REUSED_P75_WORKSPACE_ONLY_NOT_CONSUMED |
| 2 | `ext-23949c1378c49203` | bitbrain/beehave | `fe589153fa78` | `addons/beehave/blackboard.gd` | `e1b980ce875b` | `gd_parse@1.75+build:6b74a6cd20a06033` | `ext-23949c1378c49203` | `gd_parse@1.71` | EXACT_IDENTITY_MATCH | REUSED_P75_WORKSPACE_ONLY_NOT_CONSUMED |
| 3 | `ext-27ddd863881677d7` | bitbrain/beehave | `fe589153fa78` | `addons/beehave/nodes/leaves/blackboard_set.gd` | `fb4fc4dde707` | `gd_parse@1.75+build:6b74a6cd20a06033` | `ext-27ddd863881677d7` | `gd_parse@1.71` | EXACT_IDENTITY_MATCH | WORKSPACE_ONLY_NOT_CONSUMED |
| 4 | `ext-2a4f612899a6b6a5` | gdquest-demos/godot-make-pro-2d-games | `7290681309ff` | `actors/hit_box/HitBox.gd` | `2332e1243f82` | `gd_parse@1.75+build:6b74a6cd20a06033` | `ext-2a4f612899a6b6a5` | `gd_parse@1.71` | EXACT_IDENTITY_MATCH | WORKSPACE_ONLY_NOT_CONSUMED |
| 5 | `ext-409141da889d20af` | nezvers/Godot-GameTemplate | `d5d8d1588742` | `addons/top_down/scripts/damage/ActorDamage.gd` | `dc8a87b32fd1` | `gd_parse@1.75+build:6b74a6cd20a06033` | `ext-409141da889d20af` | `gd_parse@1.71` | EXACT_IDENTITY_MATCH | WORKSPACE_ONLY_NOT_CONSUMED |
| 6 | `ext-40ab1c0330e01d7f` | alfredbaudisch/Godello | `4458a143644f` | `scripts/drag_utils.gd` | `abd80468ed07` | `gd_parse@1.75+build:6b74a6cd20a06033` | `ext-40ab1c0330e01d7f` | `gd_parse@1.71` | EXACT_IDENTITY_MATCH | WORKSPACE_ONLY_NOT_CONSUMED |
| 7 | `ext-43748f09c01294f9` | gdquest-demos/godot-open-rpg | `d59f2f71bc04` | `src/field/cutscenes/templates/doors/door_trigger.gd` | `4c68056c9c1c` | `gd_parse@1.75+build:6b74a6cd20a06033` | `ext-43748f09c01294f9` | `gd_parse@1.71` | EXACT_IDENTITY_MATCH | WORKSPACE_ONLY_NOT_CONSUMED |
| 8 | `ext-4b7782ce66be92a7` | alfredbaudisch/Godello | `4458a143644f` | `addons/uuid/uuid.gd` | `87db22e8a2ac` | `gd_parse@1.75+build:6b74a6cd20a06033` | `ext-4b7782ce66be92a7` | `gd_parse@1.71` | EXACT_IDENTITY_MATCH | WORKSPACE_ONLY_NOT_CONSUMED |
| 9 | `ext-51d46c1b4943a254` | gdquest-demos/godot-open-rpg | `d59f2f71bc04` | `src/field/cutscenes/templates/doors/door.gd` | `f4df1c3da5f5` | `gd_parse@1.75+build:6b74a6cd20a06033` | `ext-51d46c1b4943a254` | `gd_parse@1.71` | EXACT_IDENTITY_MATCH | WORKSPACE_ONLY_NOT_CONSUMED |
| 10 | `ext-51fbb1e2b03c3f67` | ceceppa/anima | `f4a454ebd4d5` | `addons/anima/motion/runtime/anima_race_instance.gd` | `050613ecec7f` | `gd_parse@1.75+build:6b74a6cd20a06033` | `ext-51fbb1e2b03c3f67` | `gd_parse@1.71` | EXACT_IDENTITY_MATCH | WORKSPACE_ONLY_NOT_CONSUMED |
| 11 | `ext-55aef2d453370c1b` | bitbrain/beehave | `fe589153fa78` | `addons/beehave/nodes/leaves/blackboard_compare.gd` | `cd7008ea7deb` | `gd_parse@1.75+build:6b74a6cd20a06033` | `ext-55aef2d453370c1b` | `gd_parse@1.71` | EXACT_IDENTITY_MATCH | WORKSPACE_ONLY_NOT_CONSUMED |
| 12 | `ext-56ca48126ec8514d` | alfredbaudisch/Godello | `4458a143644f` | `scripts/events.gd` | `819b9f1e9dd3` | `gd_parse@1.75+build:6b74a6cd20a06033` | `ext-56ca48126ec8514d` | `gd_parse@1.71` | EXACT_IDENTITY_MATCH | WORKSPACE_ONLY_NOT_CONSUMED |
| 13 | `ext-5a8d53c7f530e4af` | gdquest-demos/godot-open-rpg | `d59f2f71bc04` | `overworld/maps/town/door_unlock_interaction.gd` | `8573670e7381` | `gd_parse@1.75+build:6b74a6cd20a06033` | `ext-5a8d53c7f530e4af` | `gd_parse@1.71` | EXACT_IDENTITY_MATCH | WORKSPACE_ONLY_NOT_CONSUMED |
| 14 | `ext-5adc6644d3347390` | Ark2000/PankuConsole | `863324dfb752` | `addons/panku_console/modules/interactive_shell/mini_repl_2.gd` | `ad826b6ca230` | `gd_parse@1.75+build:6b74a6cd20a06033` | `ext-5adc6644d3347390` | `gd_parse@1.71` | EXACT_IDENTITY_MATCH | WORKSPACE_ONLY_NOT_CONSUMED |
| 15 | `ext-6f85edf0730ee075` | gdquest-demos/godot-make-pro-2d-games | `7290681309ff` | `core/world/Door.gd` | `5d1f00befa4e` | `gd_parse@1.75+build:6b74a6cd20a06033` | `ext-6f85edf0730ee075` | `gd_parse@1.71` | EXACT_IDENTITY_MATCH | WORKSPACE_ONLY_NOT_CONSUMED |
| 16 | `ext-73c80a3db6d71e48` | nezvers/Godot-GameTemplate | `d5d8d1588742` | `addons/top_down/scripts/damage/HealthResource.gd` | `fed9dc57052f` | `gd_parse@1.75+build:6b74a6cd20a06033` | `ext-73c80a3db6d71e48` | `gd_parse@1.71` | EXACT_IDENTITY_MATCH | REUSED_P75_WORKSPACE_ONLY_NOT_CONSUMED |
| 17 | `ext-7973e94ee75e2819` | nezvers/Godot-GameTemplate | `d5d8d1588742` | `addons/top_down/scripts/actor/bots/ProximityAttack.gd` | `a649943fbcd4` | `gd_parse@1.75+build:6b74a6cd20a06033` | `ext-7973e94ee75e2819` | `gd_parse@1.71` | EXACT_IDENTITY_MATCH | WORKSPACE_ONLY_NOT_CONSUMED |
| 18 | `ext-7d7933a2343f52d0` | gdquest-demos/godot-open-rpg | `d59f2f71bc04` | `src/combat/ui/battler_entry/ui_life_bar.gd` | `38a36c53f242` | `gd_parse@1.75+build:6b74a6cd20a06033` | `ext-7d7933a2343f52d0` | `gd_parse@1.71` | EXACT_IDENTITY_MATCH | WORKSPACE_ONLY_NOT_CONSUMED |
| 19 | `ext-80c1104f5262a6ee` | Ark2000/PankuConsole | `863324dfb752` | `addons/panku_console/res/shader/simple_fast_blur.gdshader` | `769a72513283` | `gd_parse@1.75+build:6b74a6cd20a06033` | `ext-80c1104f5262a6ee` | `gd_parse@1.71` | EXACT_IDENTITY_MATCH | NOT_APPLICABLE_NOT_CONSUMED |
| 20 | `ext-9e62ed2e3dec8164` | alfredbaudisch/Godello | `4458a143644f` | `scripts/board_member_button.gd` | `540fdf1f898b` | `gd_parse@1.75+build:6b74a6cd20a06033` | `ext-9e62ed2e3dec8164` | `gd_parse@1.71` | EXACT_IDENTITY_MATCH | WORKSPACE_ONLY_NOT_CONSUMED |
| 21 | `ext-9f0aad5e01dd71f7` | gdquest-demos/godot-make-pro-2d-games | `7290681309ff` | `interface/gui/player/life_bar/Lifebar.gd` | `e032da8e7dfa` | `gd_parse@1.75+build:6b74a6cd20a06033` | `ext-9f0aad5e01dd71f7` | `gd_parse@1.71` | EXACT_IDENTITY_MATCH | WORKSPACE_ONLY_NOT_CONSUMED |
| 22 | `ext-aa0204cc227b0480` | derkork/godot-statecharts | `76d226a3efac` | `addons/godot_state_charts/animation_tree_state.gd` | `4cc0d9a64c00` | `gd_parse@1.75+build:6b74a6cd20a06033` | `ext-aa0204cc227b0480` | `gd_parse@1.71` | EXACT_IDENTITY_MATCH | WORKSPACE_ONLY_NOT_CONSUMED |
| 23 | `ext-ab693f3d6ef9439c` | lampe-games/godot-open-rts | `a628ad3bb6a9` | `source/match/units/traits/HealthBar.gd` | `cc6b52103ccc` | `gd_parse@1.75+build:6b74a6cd20a06033` | `ext-ab693f3d6ef9439c` | `gd_parse@1.71` | EXACT_IDENTITY_MATCH | REUSED_P75_WORKSPACE_ONLY_NOT_CONSUMED |
| 24 | `ext-bfe9b7e6dbebbfae` | blackears/cyclopsLevelBuilder | `ea41feaab5dd` | `godot/addons/cyclops_level_builder/actions/cyclops_action.gd` | `2a323c4f422d` | `gd_parse@1.75+build:6b74a6cd20a06033` | `ext-bfe9b7e6dbebbfae` | `gd_parse@1.71` | EXACT_IDENTITY_MATCH | WORKSPACE_ONLY_NOT_CONSUMED |
| 25 | `ext-c341755c352c7563` | lampe-games/godot-open-rts | `a628ad3bb6a9` | `source/match/units/actions/AutoAttacking.gd` | `d4e37f8883d9` | `gd_parse@1.75+build:6b74a6cd20a06033` | `ext-c341755c352c7563` | `gd_parse@1.71` | EXACT_IDENTITY_MATCH | WORKSPACE_ONLY_NOT_CONSUMED |
| 26 | `ext-c7b0d12daf86d973` | gdquest-demos/godot-make-pro-2d-games | `7290681309ff` | `actors/DamageSource.gd` | `4e63701d87ab` | `gd_parse@1.75+build:6b74a6cd20a06033` | `ext-c7b0d12daf86d973` | `gd_parse@1.71` | EXACT_IDENTITY_MATCH | WORKSPACE_ONLY_NOT_CONSUMED |
| 27 | `ext-d5f7ac2db3a8c4e4` | gdquest-demos/godot-open-rpg | `d59f2f71bc04` | `src/combat/actions/battler_action_attack.gd` | `754107d5816d` | `gd_parse@1.75+build:6b74a6cd20a06033` | `ext-d5f7ac2db3a8c4e4` | `gd_parse@1.71` | EXACT_IDENTITY_MATCH | WORKSPACE_ONLY_NOT_CONSUMED |
| 28 | `ext-d82bd2e536c75c4a` | nezvers/Godot-GameTemplate | `d5d8d1588742` | `addons/top_down/scripts/ui/game_screen/HealthPanel.gd` | `e04c3a2983c9` | `gd_parse@1.75+build:6b74a6cd20a06033` | `ext-d82bd2e536c75c4a` | `gd_parse@1.71` | EXACT_IDENTITY_MATCH | WORKSPACE_ONLY_NOT_CONSUMED |
| 29 | `ext-d9764c3981017194` | gdquest-demos/godot-make-pro-2d-games | `7290681309ff` | `actors/health/Status.gd` | `40c1a1b6c64f` | `gd_parse@1.75+build:6b74a6cd20a06033` | `ext-d9764c3981017194` | `gd_parse@1.71` | EXACT_IDENTITY_MATCH | WORKSPACE_ONLY_NOT_CONSUMED |
| 30 | `ext-ec789727924bfa6c` | foxssake/netfox | `cf5189d18e98` | `examples/forest-brawl/scripts/play-random-3d.gd` | `0aa48f82404b` | `gd_parse@1.75+build:6b74a6cd20a06033` | `ext-ec789727924bfa6c` | `gd_parse@1.71` | EXACT_IDENTITY_MATCH | WORKSPACE_ONLY_NOT_CONSUMED |
| 31 | `ext-f80d07f302bacc20` | cis-ash/TEXTREME | `673dc09d9132` | `Scenes/EffectParameterSelector/EffectParameterSelector.gd` | `a34a997d42f2` | `gd_parse@1.75+build:6b74a6cd20a06033` | `ext-f80d07f302bacc20` | `gd_parse@1.71` | EXACT_IDENTITY_MATCH | WORKSPACE_ONLY_NOT_CONSUMED |
| 32 | `ext-fb806b579659b155` | foxssake/netfox | `cf5189d18e98` | `examples/multiplayer-state-machine/scripts/character-states/Idle.gd` | `be4e79427622` | `gd_parse@1.75+build:6b74a6cd20a06033` | `ext-fb806b579659b155` | `gd_parse@1.71` | EXACT_IDENTITY_MATCH | WORKSPACE_ONLY_NOT_CONSUMED |
| 33 | `ext-fe3acf782b88edda` | Ark2000/PankuConsole | `863324dfb752` | `addons/panku_console/modules/history_manager/env.gd` | `94dc2c7c50c4` | `gd_parse@1.75+build:6b74a6cd20a06033` | `ext-fe3acf782b88edda` | `gd_parse@1.71` | EXACT_IDENTITY_MATCH | WORKSPACE_ONLY_NOT_CONSUMED |
| 34 | `ext-fffa637657ffede1` | alfredbaudisch/Godello | `4458a143644f` | `scripts/board_card.gd` | `9d67c3fefd55` | `gd_parse@1.75+build:6b74a6cd20a06033` | `ext-fffa637657ffede1` | `gd_parse@1.71` | EXACT_IDENTITY_MATCH | WORKSPACE_ONLY_NOT_CONSUMED |

`consumed_by_formal_analysis = false` for all 34. Workspace results are **independent
workspace artefacts**, not formal analysis updates.

### D.1 Formal Linkage coverage gap (observed fact)

150 linkage records exist for only **30** analyses (5 Features each). Four formal
analyses have **no** linkage row at all:

| analysis_id | file_type | repository | source_path |
|---|---|---|---|
| `ext-43748f09c01294f9` | gdscript | gdquest-demos/godot-open-rpg | `src/field/cutscenes/templates/doors/door_trigger.gd` |
| `ext-5a8d53c7f530e4af` | gdscript | gdquest-demos/godot-open-rpg | `overworld/maps/town/door_unlock_interaction.gd` |
| `ext-80c1104f5262a6ee` | gdshader | Ark2000/PankuConsole | `addons/panku_console/res/shader/simple_fast_blur.gdshader` |
| `ext-ab693f3d6ef9439c` | gdscript | lampe-games/godot-open-rts | `source/match/units/traits/HealthBar.gd` |

This is a pre-existing formal-layer gap (not caused by Batch B), but it means two
health_bar-relevant files were never evaluated against the Feature at all. Severity
`MEDIUM`; requires a decision in Batch D, not a Batch C change.

---

## E. Symbol-Level Evidence Impact (C2)

Scope: 29 reanalyzed + 4 reused records = 33 records with diffs; **59 symbols
inventoried**, **0 removed**.

| Accounting | Value |
|---|---:|
| Diff-listed additions (33 diffs) | 59 |
| New symbols (Batch B) | 44 |
| Reclassified symbols (Batch B) | 1 |
| Additions from reused Phase 1.75 records | 14 |
| Removed | 0 |
| Records with ≥1 symbol change | 21 |
| Records with metadata-only diff | 12 |
| Symbols `NO_IMPACT` | 46 |
| Symbols with potential impact | **13** |

**Exact-identifier test.** Each of the 44 new Batch B symbols was compared against the
`source_symbol` set of the five audited Feature projections (`health` 15, `health_bar` 12,
`openable_door` 13, `blackboard` 10, `attack_emitter` 14 symbols). **Zero exact matches.**
Only the reused `get_value` (blackboard) is an exact FUNCTION match not currently listed
in the formal linkage.

### E.1 Potential impacts (every row is an *Inferred Potential Impact*, not an Observed Fact)

| analysis | symbol | change | old → new | related feature | linkage | evidence type | impact | severity | confidence | human review |
|---|---|---|---|---|---|---|---|---|---|---|
| `ext-1d204b35464cf388` | `health` | ADDED | — → VARIABLE | health | `lnk-d2d95d8162be1592` | SYMBOL_EXACT_MATCH | POTENTIAL_EVIDENCE_STRENGTHENING | MEDIUM | MEDIUM | YES |
| `ext-23949c1378c49203` | `get_value` | ADDED | — → FUNCTION | blackboard | `lnk-7084dc8999c2182b` | SYMBOL_EXACT_MATCH | POTENTIAL_EVIDENCE_STRENGTHENING | MEDIUM | HIGH | YES |
| `ext-27ddd863881677d7` | `key` | ADDED | — → VARIABLE | blackboard | `lnk-bb935a2c8bdbfc39` | SYMBOL_TOKEN_OVERLAP | POTENTIAL_EVIDENCE_STRENGTHENING | LOW | LOW | YES |
| `ext-27ddd863881677d7` | `value` | ADDED | — → VARIABLE | blackboard | `lnk-bb935a2c8bdbfc39` | SYMBOL_TOKEN_OVERLAP | POTENTIAL_EVIDENCE_STRENGTHENING | LOW | LOW | YES |
| `ext-51d46c1b4943a254` | `is_locked` | ADDED | — → PROPERTY | openable_door | `lnk-b382814f8bca80a5` | SYMBOL_TOKEN_OVERLAP | POTENTIAL_EVIDENCE_STRENGTHENING | MEDIUM | LOW | YES |
| `ext-5a8d53c7f530e4af` | `door` | ADDED | — → VARIABLE | openable_door | NONE | NONE | POTENTIAL_FEATURE_MATCH | LOW | LOW | YES |
| `ext-73c80a3db6d71e48` | `max_hp` | ADDED | — → VARIABLE | health | `lnk-6fff3ce176bd5813` | NONE | POTENTIAL_EVIDENCE_STRENGTHENING | MEDIUM | LOW | YES |
| `ext-7d7933a2343f52d0` | `target_value` | RECLASSIFIED | variables → PROPERTY | openable_door | `lnk-23addea8960377c4` | SYMBOL_TOKEN_OVERLAP | POTENTIAL_EVIDENCE_RECLASSIFICATION | MEDIUM | HIGH | YES |
| `ext-9e62ed2e3dec8164` | `board` | ADDED | — → VARIABLE | blackboard | `lnk-042638ff10ae0b0e` | NONE | REQUIRES_MANUAL_REVIEW | LOW | HIGH | YES |
| `ext-9f0aad5e01dd71f7` | `current_health` | ADDED | — → VARIABLE | health_bar | `lnk-bdec07041badaf0d` | NONE | POTENTIAL_FEATURE_MATCH | MEDIUM | LOW | YES |
| `ext-9f0aad5e01dd71f7` | `maximum` | ADDED | — → VARIABLE | health_bar | `lnk-bdec07041badaf0d` | NONE | POTENTIAL_FEATURE_MATCH | LOW | LOW | YES |
| `ext-ab693f3d6ef9439c` | `size` | ADDED | — → PROPERTY | health_bar | NONE | SYMBOL_TOKEN_OVERLAP | POTENTIAL_FEATURE_MATCH | LOW | LOW | YES |
| `ext-d5f7ac2db3a8c4e4` | `base_damage` | ADDED | — → VARIABLE | attack_emitter | `lnk-01c9ea986153c619` | SYMBOL_TOKEN_OVERLAP | POTENTIAL_FEATURE_MATCH | LOW | LOW | YES |

### E.2 C2 question-by-question

1. **Do new symbols correspond to existing Features?** No exact identifier does. Five
   token/semantic candidates exist (`current_health`, `maximum`, `size`, `door`,
   `base_damage`) and all sit on linkages that are `NO_SUPPORTED_LINK` or
   `POTENTIAL_RELEVANCE`/`AMBIGUOUS`.
2. **Can an existing linkage gain stronger direct evidence?** Yes, but only from the
   reused Phase 1.75 records: `get_value` (exact, DIRECT blackboard seed),
   `health`/`modifiers` (DIRECT health seed), `hp`/`max_hp`/`reset_hp`/`reset_max_hp`
   (health seed). None of these are Batch B reanalyses.
3. **Do declaration-kind changes force reinterpretation?** One: `target_value`
   (`variables` → `PROPERTY`, with setter). No other Batch B record has a kind change;
   the remaining `symbols_changed` entries are descriptive-field enrichments
   (`declaration_kind` old = null), not kind transitions.
4. **Any previously unmatched Feature now matchable?** No exact match. The closest are
   the health_bar hints from `Lifebar.gd`/`HealthBar.gd`, and both analyses lack a
   health_bar linkage (`ext-ab693f3d6ef9439c` has no linkage at all).
5. **Same name, different declaration_kind?** `target_value` only (Batch B). Outside
   Batch B, the seed-policy-documented `is_dead` (external property vs internal
   function) remains unchanged.
6. **Same name, different semantics (must not be equated)?** `board` (Kanban
   `BoardModel`) vs the `blackboard` Feature; `door` (a node reference) vs the
   openable_door API; `_unit` in HealthBar (unit node) vs `_unit` in AutoAttacking;
   `size` (bar size) vs `bar_size`. Explicitly recorded so no future matcher merges them.
7. **Surface-only additions caused by capture capability?** Yes — 46 `NO_IMPACT`
   entries are almost entirely capture expansion: `onready` node references
   (`_bar_anim`, `_name_label`, `_text_anim`, `_value_label`, `_tween`), private state
   (`_key_expression`, `_value_expression`, `_child_*`, `_target_unit`, `_sub_action`),
   export metadata, and enriched `symbols_changed` fields. These are **not** independent
   evidence and must not be promoted.

---

## F. PARTIAL Coverage Impact (C3)

Source verification method: read-only read of the commit copy under
`.ai/skills/foundation/godot-gdscript/code_library/sources/...` (raw commit file, no
header). Record line = commit line + 3. This read explains impact; it does **not** claim
parser support.

`PARTIAL coverage means absence of a parsed symbol is not evidence of source-level absence.`

| # | analysis | repository / commit | path | limitation | coverage | declarations parsed | missing (record line) | flagged? | existing linkages |
|---|---|---|---|---|---|---|---|---|---|
| 1 | `ext-55aef2d453370c1b` | bitbrain/beehave `fe589153` | `addons/beehave/nodes/leaves/blackboard_compare.gd` | `ENUM_NOT_INTERPRETED` L10 | PARTIAL | class `BlackboardCompareCondition`, exports `left_operand`/`operator`/`right_operand`, onready `_left_expression`/`_right_expression`, `tick`, `_get_expression_sources` | `Operators` (enum, L10) + 6 members | YES | 5: `lnk-6a49ac99c8be4f01` blackboard POTENTIAL_RELEVANCE; other 4 NO_SUPPORTED_LINK |
| 2 | `ext-9e62ed2e3dec8164` | alfredbaudisch/Godello `4458a143` | `scripts/board_member_button.gd` | `LEGACY_SETGET_NOT_INTERPRETED` L9, L10 | PARTIAL | `model`, `board`, `normal_text`, 7 functions | `expand_to` (export var, L7) | **NO — unflagged** | 5: `lnk-042638ff10ae0b0e` blackboard NO_SUPPORTED_LINK; other 4 NO_SUPPORTED_LINK |
| 3 | `ext-fffa637657ffede1` | alfredbaudisch/Godello `4458a143` | `scripts/board_card.gd` | `LEGACY_SETGET_NOT_INTERPRETED` L7 | PARTIAL | `model`, 4 functions | `title_label` (onready var, L9) | **NO — unflagged** | 5: `lnk-5b9d6ba1c10e1857` blackboard NO_SUPPORTED_LINK; other 4 NO_SUPPORTED_LINK |

### F.1 What the limitation actually removes

- **`blackboard_compare.gd`:** `enum Operators { EQUAL, NOT_EQUAL, GREATER, LESS,
  GREATER_EQUAL, LESS_EQUAL }` (commit L7–L14, record L10–L17) is not interpreted. The
  comparison-operator vocabulary is therefore absent from the symbol table while the
  `operator` export and both operands are present. The enum declaration is explicitly
  flagged. Impact on the blackboard linkage: none — that link rests on the class name
  token, and enum members share no identifier with the Feature.
- **`board_member_button.gd` / `board_card.gd`:** the legacy `setget` clause is not
  interpreted, so the accessor relationship (`setget set_model`, `setget set_model,
  get_model`) is missing while the variable names and setter/getter functions are
  present. Additionally `expand_to` and `title_label` are missing with **no flag**.

### F.2 Risks recorded

1. **Under-reported PARTIAL (HIGH confidence, MEDIUM severity).** The parser's
   `unsupported_constructs` list does not cover every missing declaration. A consumer
   that trusts `unsupported_constructs` as the complete gap list would still over-read
   the symbol table. This is a *coverage-reporting* gap, not a syntax-support claim.
2. **Under-estimated linkage (LOW confidence).** Both Godello linkages are
   `NO_SUPPORTED_LINK`; the newly captured `model`/`board` names are UI/model plumbing,
   not blackboard API. They would at most add token proximity, never a DIRECT link.
3. **Absence misread as no-declaration (must be prevented).** Any Batch D decision that
   treats the missing `expand_to`/`title_label` (or the `Operators` enum) as
   "not present in source" would be wrong; the commit copy proves otherwise.

No unsupported construct was added to any formal Analysis, no PARTIAL record was
promoted to COMPLETE, and no missing declaration was used as counter-evidence.

---

## G. `target_value` Reclassification Impact (C4)

| Layer | Representation |
|---|---|
| **Parser 1.71 formal record (what the system actually stores today)** | `symbols.variables`: `{line: 18, name: "target_value", type: "", value: "0.0:"}` — the old regex swallowed the property colon into the value |
| **Batch B 1.76 workspace** | `symbols.properties`: `declaration_kind=PROPERTY`, `line=18`, `value="0.0"`, `has_setter=true`, `has_getter=false`, setter record line 19 / commit line 16, property `end_line=18`, accessor `end_line=37`, `explained=true`, old value `"0.0:"` |
| **Commit source (confirmed read-only)** | `ui_life_bar.gd` commit L15 `var target_value := 0.0:` with `set(new_value):` at commit L16; record offset +3 → L18/L19 |

- **Not a removal:** `symbols_removed = 0`; `unexplained_differences = []`.
- **Not two symbols:** one symbol at record line 18, moved from `variables` to `properties`.
- **Existing linkage references:** exactly **1** evidence item —
  `lnk-23addea8960377c4:ev:01` (openable_door, `AMBIGUOUS`, `SYMBOL_TOKEN_OVERLAP`,
  `target_value` vs Feature `boolean_target`, matched token `target`).
- **Explanation-only mentions:** 3 `NO_SUPPORTED_LINK` linkages (attack_emitter,
  blackboard, health) mention `target_value` in their pair-evaluation prose; they carry
  no evidence item.
- **Feature metadata / graph dependency:** none. `feature_graph.json` edges are
  feature-level (80 edges, e.g. `health ↔ health_bar`), with no symbol-level reference.
- **`NO_EXISTING_LINKAGE_REFERENCE` does not apply** — one reference exists and is
  audited above.

**Impact:** `POTENTIAL_EVIDENCE_RECLASSIFICATION` / MEDIUM / confidence HIGH. The new
representation shows a tweened life-bar value with a setter, which makes the door
token overlap *less* plausible. No classification change is authorized here; a human must
decide whether to re-word or re-evaluate that single item. The reclassification is a
**parser representation correction**, not new evidence and not new semantics.

---

## H. Candidate and Seed Policy Impact (C5)

### H.1 Candidates (read: 2)

| candidate | feature | status | seed linkage | seed analysis | Batch B status of that analysis | seed symbols | digests |
|---|---|---|---|---|---|---|---|
| `cand-08fdc0b10a112ecf` | health | NEEDS_REVIEW | `lnk-6fff3ce176bd5813` (QUALIFIED_DIRECT_WITH_LIMITATIONS, INDEPENDENT) | `ext-73c80a3db6d71e48` | `REUSED_PHASE_1_75` | `is_dead` | analysis ✓ linkage ✓ source ✓ commit ✓ |
| `cand-08fdc0b10a112ecf` | health | NEEDS_REVIEW | `lnk-d2d95d8162be1592` (QUALIFIED_DIRECT, INDEPENDENT) | `ext-1d204b35464cf388` | `REUSED_PHASE_1_75` | `take_damage`, `heal`, `health_changed` | analysis ✓ linkage ✓ source ✓ commit ✓ |
| `cand-7f52cb8f583124db` | blackboard | NEEDS_REVIEW | `lnk-7084dc8999c2182b` (QUALIFIED_DIRECT, **NOT_INDEPENDENT**) | `ext-23949c1378c49203` | `REUSED_PHASE_1_75` | `Blackboard`, `keys`, `set_value`, `has_value`, `erase_value` | analysis ✓ linkage ✓ source ✓ commit ✓ |

Context evidence: `lnk-a099657ab3c9930c` (attack_emitter → health) is
`GRAPH_DERIVED_RELATION`, `INDIRECT_EVIDENCE`, `counts_as_seed=false`,
`counts_as_implementation_evidence=false`. It was not and cannot be treated as a seed.

**Findings**

1. **No candidate qualification changes because of Batch B.** All three seeds sit on
   Phase-1.75-reused analyses; Batch B produced no new reanalysis for those files and
   left their workspace artefacts untouched.
2. **Symbols touched by the audit on seed analyses:** `is_dead`-analysis → `max_hp`
   (reused addition, not a seed item); `Stats.gd` → `health`; blackboard →
   `get_value`. If a human later consumes the reused 1.75 additions, the *strength* of
   these seeds would improve, but eligibility and independence would not change.
3. **No over-optimism or over-conservatism detected at current state.** The blackboard
   candidate is explicitly `NOT_INDEPENDENT` (beehave is the acknowledged upstream of
   the internal Feature), and the health candidate carries the documented
   property-vs-function `is_dead` limitation. Both remain `NEEDS_REVIEW`.
4. **No seed, status, eligibility or policy value was modified.**

### H.2 Seed Policy (read-only review)

| Question | Answer | Basis |
|---|---|---|
| Do current rules allow a Parser 1.76 workspace result into a formal seed? | **No — implicitly** | No parser-version clause exists, but seeds are keyed by `linkage_id` plus `linkage_record_digest` / `analysis_record_digest`, which embed the formal analysis digest. An unreviewed workspace record cannot satisfy them. |
| Is a formal Analysis update required before consuming new parse results? | **IMPLICIT_ONLY** | Same mechanism; no explicit rule. |
| Does the policy distinguish `COMPLETE` from `PARTIAL` coverage? | **No** | The policy JSON has no coverage or parser-version field; the only coverage statement is free text in one seed's `limitations` ("parser captured 1 of 5 @export vars"). |
| Is graph-derived evidence prevented from becoming an independent seed? | **Yes** | `context_relations` enumerates the relation; candidate `context_refs` carry `counts_as_seed=false` and `counts_as_implementation_evidence=false`. |

Policy gaps recorded (no change made): (a) no explicit "formal analysis only" rule;
(b) no machine-readable coverage-status gate. Both are `MEDIUM` policy risks for Batch D.

---

## I. Impact Severity Summary

| Severity | Count | Items |
|---|---:|---|
| `CRITICAL` | **0** | — |
| `HIGH` | **0** | — |
| `MEDIUM` | **6** | `target_value` reclassification; `is_locked`; `current_health`; `get_value`; `health` (Stats); `max_hp`; plus the PARTIAL under-reporting risk and the linkage coverage gap (recorded at record level, not symbol level) |
| `LOW` | **7** | `key`, `value`, `maximum`, `size`, `door`, `base_damage`, `board` |
| `INFO` | **46** | remaining `NO_IMPACT` symbols |

Classification counts over the 59 inventoried symbols: `NO_IMPACT` 46,
`POTENTIAL_EVIDENCE_STRENGTHENING` 6, `POTENTIAL_FEATURE_MATCH` 5,
`POTENTIAL_EVIDENCE_RECLASSIFICATION` 1, `REQUIRES_MANUAL_REVIEW` 1,
`POTENTIAL_NEW_DIRECT_EVIDENCE` 0, `POTENTIAL_CONTRADICTION` 0,
`INSUFFICIENT_COVERAGE` 0 at symbol level (recorded for the 3 PARTIAL records).

**No `CRITICAL` or `HIGH` item exists**, because nothing found can break formal evidence
correctness or identity: no symbol was removed, no identity was ambiguous, no exact match
was auto-promoted, and nothing was written.

Statement types used above:

- *Observed Fact* — counts, digests, stored values, linkage classifications as read.
- *Parser-derived Result* — the 1.76 symbol tables, diffs and coverage statuses.
- *Inferred Potential Impact* — every row in §E.1 and the §F.2 risks.
- *Human-confirmed Semantic Fact* — none. This batch confirms no semantics; it only
  records where a human decision is required.

---

## J. Data Integrity and Non-Mutation Verification

Baseline captured before any Batch C write; re-verified after the final artefact build.

| Group | Files | Changed | Missing | Added |
|---|---:|---:|---:|---:|
| Formal Analysis | 34 | 0 | 0 | 0 |
| Formal Linkage | 150 | 0 | 0 | 0 |
| Candidate workspace (2 candidates + `WORKSPACE.json`) | 3 | 0 | 0 | 0 |
| Batch B workspace | 162 | 0 | 0 | 0 |
| Phase 1.75 workspace | 29 | 0 | 0 | 0 |
| Batch A inventory | 1 | 0 | 0 | 0 |
| Parser + adapter | 2 | 0 | 0 | 0 |
| Feature index / graph / seed policy | 3 | 0 | 0 | 0 |
| **Total** | **384** | **0** | **0** | **0** |

- Deleted files: **0**.
- No parser run, no reanalysis run, no diff regeneration, no linkage rebuild/refresh,
  no candidate rebuild/promotion/qualification, no evidence creation.
- Review Queue directory `.ai/learning/external_code/review_queue/phase_1.76/`:
  **not created**.
- Batch D artefacts: **none**.
- Allowed changes only: the Batch C report, the Batch C audit tool, and the 8 Batch C
  audit artefacts under `.ai/learning/external_code/evidence_impact/phase_1.76/`.

### J.1 Validation results

`python .ai/tools/external_code/evidence_impact_176.py validate` → exit 0,
`"result": "PASS"`, all checks true:

| Check | Result |
|---|---|
| 34 / 34 Batch B records mapped, all with a status | PASS |
| No mapped record consumed by formal analysis | PASS |
| 150 formal linkages audited | PASS |
| 3 / 3 PARTIAL records reviewed, absence rule recorded | PASS |
| `target_value` reviewed, not a removal, not two symbols | PASS |
| 2 / 2 candidates reviewed | PASS |
| Seed policy reviewed | PASS |
| Every inventoried symbol has a source; every potential impact has reasoning | PASS |
| Review Queue not created; no Batch D artefacts | PASS |
| Formal data unmutated | PASS |

Determinism of the audit itself: the artefact build was executed repeatedly and produced
byte-identical `audit_validation.json` integrity results (`changed/missing/added = []`).

---

## K. Git State

| Item | Before Batch C | After Batch C |
|---|---|---|
| Branch | `master` | `master` |
| HEAD | `d64b1cd5b576a44dcfafd7becbb2d2a7f1fd6a84` | `d64b1cd5b576a44dcfafd7becbb2d2a7f1fd6a84` |
| Staged | 0 | 0 |
| Modified | 34 | 34 |
| Untracked (collapsed entries) | 140 | **141** (+1: the Batch C report) |
| Untracked files (`-uall`) | not captured | 582 paths |
| Deleted | 0 | 0 |

Note: `.ai/learning/external_code/` and `.ai/tools/external_code/` contain **no tracked
files** (`git ls-files` = 0), so git reports each of them as a single untracked directory
entry. The 8 audit artefacts and the audit tool therefore add no new collapsed entry; only
the report file does. Expanded with `-uall` all 10 new files are visible individually.

Only read-only git commands were used (`rev-parse`, `status`, `diff` was not needed).
No `add`, `commit`, `push`, `reset`, `checkout`, `clean` or `stash` was executed. The 34
modified / 140 pre-existing untracked files are the pre-existing state, not Batch C
changes.

---

## L. Limitations and Unresolved Questions

1. **Formal layer is still parser 1.71.** Nothing in this review changes that; all impact
   statements are conditional on a future, separately authorized consumption decision.
2. **3 PARTIAL records; 2 gaps are unflagged.** `expand_to` and `title_label` are provably
   absent from source and absent from the symbol table without a flag. The coverage
   mechanism under-reports.
3. **No Feature-side semantic confirmation.** Symbol-name and token comparisons are
   parser-derived; whether `is_locked` truly implements the door Feature's state, or
   `current_health`/`maximum` implement health_bar, is unverified and is explicitly *not*
   asserted.
4. **Linkage coverage gap.** Four formal analyses (incl. `HealthBar.gd`) have no linkage
   rows, so health_bar evidence may be under-evaluated for reasons unrelated to parsing.
5. **`target_value` decision is open.** The single AMBIGUOUS item was not changed; whether
   to re-word or re-evaluate it is a human call.
6. **Candidate strength question is open.** Consuming the reused 1.75 additions
   (`get_value`, `hp`/`max_hp`, `health`) would strengthen existing DIRECT seeds; it would
   not change qualification, and this batch did not do it.
7. **Not verified:** feature-side source semantics (no Feature source re-read beyond
   projection symbols), runtime behaviour, and any similarity/equivalence judgement
   (explicit non-goals).

---

## M. Batch C Verdict

**`PASS_WITH_LIMITATIONS`**

Basis: the mapping is complete and exact, the audit is reproducible and non-mutating, and
every formal datum is unchanged. Limitations: 3 PARTIAL records (2 with unflagged missing
declarations), the formal layer remains on parser 1.71, one AMBIGUOUS evidence item needs a
human decision, and the seed policy lacks an explicit coverage gate.

`BLOCKED` and `FAIL` do not apply: no prerequisite mismatch, no identity ambiguity, and no
unexpected data change was observed.

---

## N. Batch D Readiness

**`READY_FOR_BATCH_D_WITH_RESTRICTIONS`**

Restrictions carried into any Batch D planning:

1. Batch D may plan review items but must not create or modify a Review Queue without the
   next explicit authorization.
2. The 3 PARTIAL records keep the "absence ≠ absence" rule; the two unflagged missing
   declarations must be in scope.
3. `target_value` must be treated as one reclassified property with one AMBIGUOUS item.
4. No evidence may be promoted from token/semantic proximity; `POTENTIAL_FEATURE_MATCH`
   items stay unlinked until human semantic confirmation.
5. The formal layer stays parser 1.71 until a separate consumption decision.

Readiness here is an audit conclusion only — it grants **no execution authorization**.

---

## O. Recommended Next Actions

For human review (in this order):

1. Decide whether the reused Phase 1.75 additions (`get_value`, `hp`/`max_hp`/`reset_*`,
   `health`) should be proposed for formal consumption — highest evidence value, exact
   match, already reviewed in Phase 1.73/1.75.
2. Decide the `target_value` / `lnk-23addea8960377c4` item (keep as AMBIGUOUS with
   corrected wording, or re-evaluate).
3. Rule on the two unflagged PARTIAL omissions (coverage-reporting defect) before any
   parser-1.76 consumption.
4. Confirm that the four analyses without linkage rows are out of scope or need a linkage
   decision.
5. Only then authorize Batch D (Review Queue planning), with the restrictions in §N.

---

## Appendix — Deliverables and Self-Check

**New files (10):**

| Path | Purpose |
|---|---|
| `.ai/context/PHASE_1_76_C_EVIDENCE_IMPACT_REVIEW.md` | this report |
| `.ai/tools/external_code/evidence_impact_176.py` | read-only audit tool (`build` / `validate`) |
| `.ai/learning/external_code/evidence_impact/phase_1.76/manifest.json` | audit manifest, input digests, counts |
| `…/analysis_mapping.json` | 34-record mapping |
| `…/symbol_impact.json` | 59 symbol rows + 33 record summaries |
| `…/partial_coverage_impact.json` | 3 PARTIAL records, missing declarations, affected linkages |
| `…/target_value_reclassification.json` | G section data |
| `…/candidate_impact.json` | 2 candidates + seed policy review |
| `…/linkage_coverage.json` | 150/30/4 coverage gap |
| `…/audit_validation.json` | checks + integrity results |

**Final format block**

```text
PHASE 1.76 — BATCH C
VERDICT: PASS_WITH_LIMITATIONS

ANALYSIS MAPPING:
34 / 34 records accounted for

FORMAL LINKAGE:
150 audited
0 mutation

PARTIAL COVERAGE:
3 / 3 reviewed

TARGET_VALUE:
RECLASSIFICATION_IMPACT: EVIDENCE_INTERPRETATION_CORRECTED_NO_CLASSIFICATION_CHANGE
(1 AMBIGUOUS reference: lnk-23addea8960377c4; not a removal; not two symbols)

CANDIDATES:
2 / 2 reviewed

SEED POLICY:
READ_ONLY_REVIEWED

DATA INTEGRITY:
PASS

REVIEW QUEUE:
NOT_CREATED

BATCH D:
NOT_EXECUTED

BATCH_D_READINESS:
READY_FOR_BATCH_D_WITH_RESTRICTIONS
```

**Agent self-check:** every number above was recomputed from the files in this session
(no Batch B summary value was reused as evidence); the audit tool's `validate` mode
re-derives counts, identity and integrity and returns `PASS`; no formal, workspace,
candidate, feature or policy file was written; Batch D was not started.
