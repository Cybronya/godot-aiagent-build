# Phase 1.73 — Batch B.1
# Stage D — Targeted External Analysis Report

Tool: the existing `.ai/tools/external_code/external_code_understanding.py` CLI
(`--reference` + `--metadata`), existing `gd_parse` parser (`gd_parse`, parser_version
`1.71`), existing Analysis Schema (`external_code_analysis`, schema_version 1), existing
index builder (`--reindex`).

No parser, schema or extractor was written or modified.

---

## 1. Volume and status

| Metric | Value |
|---|---|
| Repositories analysed | 5 |
| New Analysis Records | **20** |
| `analysis_complete` | **6** |
| `analysis_partial` | **14** |
| `unsupported_*` | **0** |
| Existing records preserved | 14 (unchanged, byte-identical) |
| Analysis Records total after batch | **34** |
| Index entries after `--reindex` | **34** |

`analysis_partial` is never used as a cosmetic downgrade: each of the 14 carries a concrete
reason in `unresolved_questions` / `limitations` (no `class_name`, custom property setter
annotations, or a private-only symbol surface). Nothing was reported `complete` that the
parser did not fully handle, and no shader/unsupported content was invented.

## 2. Record table

| # | analysis_id | Repository / source path | Status | Parsed surface | Partial reason |
|---|---|---|---|---|---|
| 1 | ext-1d204b35464cf388 | gdquest-demos/godot-make-pro-2d-games `actors/health/Stats.gd` | analysis_partial | 6 funcs, 3 signals | no `class_name` (cross-class dependency not attributable) |
| 2 | ext-d9764c3981017194 | … `actors/health/Status.gd` | analysis_partial | 3 funcs, 2 signals | no `class_name` |
| 3 | ext-2a4f612899a6b6a5 | … `actors/hit_box/HitBox.gd` | analysis_partial | 2 funcs | no `class_name` |
| 4 | ext-c7b0d12daf86d973 | … `actors/DamageSource.gd` | analysis_partial | 1 func, 1 var | no `class_name` |
| 5 | ext-9f0aad5e01dd71f7 | … `interface/gui/player/life_bar/Lifebar.gd` | analysis_partial | 3 funcs, 1 signal | no `class_name` |
| 6 | ext-6f85edf0730ee075 | … `core/world/Door.gd` | analysis_partial | 3 funcs, 1 signal | no `class_name` |
| 7 | ext-23949c1378c49203 | bitbrain/beehave `addons/beehave/blackboard.gd` | analysis_partial | class `Blackboard`, 7 funcs | `annotation_not_fully_interpreted:line=4` (`@export` with dictionary setter) |
| 8 | ext-27ddd863881677d7 | … `nodes/leaves/blackboard_set.gd` | analysis_partial | class `BlackboardSetAction`, 2 funcs | annotation at line 6 |
| 9 | ext-55aef2d453370c1b | … `nodes/leaves/blackboard_compare.gd` | analysis_partial | class `BlackboardCompareCondition`, 2 funcs | annotation at line 7 |
| 10 | ext-51d46c1b4943a254 | gdquest-demos/godot-open-rpg `src/field/cutscenes/templates/doors/door.gd` | analysis_partial | class `Door`, 4 funcs | `@tool` annotation at line 4 |
| 11 | ext-43748f09c01294f9 | … `doors/door_trigger.gd` | analysis_partial | 2 funcs (`_ready`, `_on_area_entered`), 1 export (`_anim`) | only private/lifecycle symbols → not distinctive |
| 12 | ext-5a8d53c7f530e4af | … `overworld/maps/town/door_unlock_interaction.gd` | analysis_partial | 1 func (`_execute`) | only a private symbol |
| 13 | ext-7d7933a2343f52d0 | … `combat/ui/battler_entry/ui_life_bar.gd` | analysis_complete | class `UIBattlerLifeBar`, 2 funcs, 1 var | — |
| 14 | ext-d5f7ac2db3a8c4e4 | … `combat/actions/battler_action_attack.gd` | analysis_complete | class `AttackBattlerAction`, 1 func | — |
| 15 | ext-73c80a3db6d71e48 | nezvers/Godot-GameTemplate `addons/top_down/scripts/damage/HealthResource.gd` | analysis_complete | class `HealthResource`, 6 funcs, 6 signals | — |
| 16 | ext-409141da889d20af | … `damage/ActorDamage.gd` | analysis_complete | class `ActorDamage`, 4 funcs, 1 signal | — |
| 17 | ext-d82bd2e536c75c4a | … `ui/game_screen/HealthPanel.gd` | analysis_complete | class `HealthPanel`, 5 funcs, 4 vars | — |
| 18 | ext-7973e94ee75e2819 | … `actor/bots/ProximityAttack.gd` | analysis_complete | class `ProximityAttack`, 4 funcs, 2 vars | — |
| 19 | ext-ab693f3d6ef9439c | lampe-games/godot-open-rts `source/match/units/traits/HealthBar.gd` | analysis_partial | 7 funcs (all private) | only private symbols → not distinctive |
| 20 | ext-c341755c352c7563 | … `units/actions/AutoAttacking.gd` | analysis_partial | 8 funcs | annotation at line 4 |

Every record also carries: `repo`, `commit_sha_full`, `source_path`, `source_digest`
(64-hex), `reference_path`, `source_file_path`, `source_exists=true`,
`source_consistent=true`, `parser_name=gd_parse`, `parser_version=1.71`, `input_digest`,
`provenance` block with immutable URL, `license*` block, `knowledge_status=NOT_KNOWLEDGE`,
`feature_created=false`.

## 3. Parser limitations observed (pre-existing, unmodified)

Verified with a direct probe of `gd_parse.parse_text`:

```
extends Node
var maximum = 100
var current_health = 0
var typed_count: int = 0
@export var size = Vector2(200, 20):
    set(value): ...
signal maximum_changed(maximum)
func initialize(health_node): ...
```
→ parsed: `extends=Node`, 1 func, 1 signal; **0 variables, 0 exports**.

Consequences visible in this batch:

1. Untyped `var` / `@export var` declarations and property setters are dropped, so
   `Lifebar.gd`'s `current_health`/`maximum` and `HealthBar.gd`'s `@export var size` never
   reach the symbol table.
2. Files whose only public surface is private (`_on_area_entered`, `_recalulate_bar_value`)
   yield no distinctive symbols at all and become unevaluable for linkage:
   `door_trigger.gd`, `door_unlock_interaction.gd`, `HealthBar.gd`.
3. `@tool` / custom annotations downgrade a file to `analysis_partial` even when every
   function was parsed (door.gd, the three beehave files).
4. `no class_name` is recorded as an unresolved cross-class dependency rather than being
   silently resolved by guessing the file name as a class.

No workaround was invented in B.1: the limitations are recorded per record and carried into
the linkage records' `evidence_limitations.parser_limitations`.

## 4. Index and reproducibility

`python .ai/tools/external_code/external_code_understanding.py --reindex` → “indexed 34
analysis record(s)”, exit 0, idempotent on repeat. `analysis_id` values are derived from
repo + full SHA + source path + input digest + parser version, so re-analysis of the same
mirror content reproduces the same ids.

Temporary metadata files used to feed `--metadata` were written under
`.ai/learning/external_code/.b1_meta/` and removed after the run; every field they carried
is embedded in the resulting Analysis Record.
