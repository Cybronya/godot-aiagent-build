# Phase 1.73 — Batch B.1
# Stage B — Targeted Repository Discovery
# Repository Candidates

Recorded: 2026-11-15T14:33:58Z (preflight) / discovery and code inspection performed in this batch.

Every candidate below was judged on **actual source code** read from the existing mirror
under `.ai/skills/foundation/godot-gdscript/code_library/sources/<slug>/gd/`, never on a
repository name, README claim or file name alone.

Candidate pool: the 77 mirrored repositories / 7,270 catalog entries. Selection was
capability-driven (health, health bar, door/interaction, attack delivery, blackboard), not
a full-library scan of all 6,813 references.

---

## 1. Decision table

| Repository | Target Feature(s) | Relevant Files | Relevance (evidence seen in code) | License | Provenance | Decision |
|---|---|---|---|---|---|---|
| gdquest-demos/godot-make-pro-2d-games | health, health_bar, attack_emitter, openable_door | 6 analysed | `actors/health/Stats.gd` implements `take_damage`, `heal`, `signal health_changed`, `export max_health`; `interface/gui/player/life_bar/Lifebar.gd` connects `health_changed` and drives a `TextureProgress`; `actors/DamageSource.gd` carries `damage`; `actors/hit_box/HitBox.gd` delivers it on contact | MIT (+ LICENSE text) | full SHA `7290681309ffcd700c2c08a8e59a57bfbec14d5e` | ACCEPT |
| bitbrain/beehave | blackboard | 3 analysed | `addons/beehave/blackboard.gd` declares `class_name Blackboard` with `set_value/get_value/has_value/erase_value/keys` over a per-node `_data` dictionary; leaf nodes consume it | MIT (metadata only, no local LICENSE text) | full SHA `fe589153fa780a3f88989578ceb5f539afffb7c2` | ACCEPT (with recorded `license_text_missing`) |
| gdquest-demos/godot-open-rpg | openable_door, health_bar, attack_emitter | 5 analysed | `src/field/cutscenes/templates/doors/door.gd` = `class_name Door` with `is_locked` setter, `open()`, animation + cell blocker; `door_unlock_interaction.gd` gates on a key item; `src/combat/ui/battler_entry/ui_life_bar.gd` animates `target_value` against `max_value`; `battler_action_attack.gd` builds `BattlerHit` and calls `target.take_hit` | MIT (+ LICENSE text) | full SHA `d59f2f71bc046ac53239a4e590861269e7100a36` | ACCEPT |
| nezvers/Godot-GameTemplate | health, health_bar, attack_emitter | 4 analysed | `addons/top_down/scripts/damage/HealthResource.gd` = `class_name HealthResource` with `hp/max_hp/is_dead`, signals `damaged/dead/hp_changed`; `ActorDamage.gd` subscribes `damaged`/`dead`; `ui/game_screen/HealthPanel.gd` divides `hp / max_hp` into a progress shader; `actor/bots/ProximityAttack.gd` fires when `distance <= attack_distance` | MIT (+ LICENSE text) | full SHA `d5d8d15887423b3a8acf0502efb6271c600a80bc` | ACCEPT |
| lampe-games/godot-open-rts | health_bar | 2 analysed | `source/match/units/traits/HealthBar.gd` recomputes a gradient bar from `_unit.hp / _unit.hp_max`, connecting `hp_changed` and selection signals; `units/actions/AutoAttacking.gd` issues attacks | MIT (+ LICENSE text) | full SHA `a628ad3bb6a9a903587a181a7ee3300dbf735e81` | ACCEPT |
| Miziziziz/MizGodotTools | health, attack_emitter | 0 analysed | `characters_utility/health_manager/health_manager.gd` and `items/weapons/attack_emitters/attack_emitter.gd` are highly relevant (the latter is the declared source of the `attack_emitter` Feature) — **but the mirror records no full commit SHA** | MIT (+ LICENSE text) | short SHA only `cb548f9035a3`; `commit_sha_full` is `null` → `provenance_status=incomplete` | REJECT |
| godotengine/godot-demo-projects | health | 0 analysed | `2d/role_playing_game/combat/combatants/health.gd` is a minimal demo health node; single relevant file | MIT | short SHA `b761b4cd5718` in catalog | NEEDS_REVIEW |
| foxssake/netfox | health_bar | 0 analysed | `examples/multiplayer-fps/scripts/ui/health-progress-bar.gd` binds a progress bar to health; netfox is already covered by two existing analyses | MIT | full SHA present for the repo | NEEDS_REVIEW |
| gdquest-demos/godot-platformer-2d | attack_emitter | 0 analysed | `DamageSource.gd` / `HitBox.gd` repeat the make-pro pattern with no additional capability | MIT | short SHA only in catalog | REJECT (redundant) |
| MrEliptik/godot_experiments | openable_door | 0 analysed | `2D/damped_oscillator/.../hinge_door.gd` is a physics hinge demo: no state, no trigger, no interaction | — | — | REJECT (name similarity only) |
| GodotVR/godot-xr-tools | health / openable_door | 0 analysed | `fall_damage.gd`, `damage_area.gd` are XR demo helpers without a health state model | MIT | — | REJECT (name similarity only) |
| Ark2000/PankuConsole, alfredbaudisch/Godello, ceceppa/anima, derkork/godot-statecharts, blackears/cyclopsLevelBuilder, cis-ash/TEXTREME | — | 0 new | already analysed in Phase 1.73 Batch B; no health/door/attack/blackboard capability in the analysed files | MIT | full SHA | not re-analysed |

## 2. Accepted repositories and coverage

| Feature | Strongest evidence after B.1 | Repositories |
|---|---|---|
| health | **DIRECT_EVIDENCE** ×2 (`take_damage`/`heal`/`health_changed`; `is_dead`) | make-pro, nezvers |
| health_bar | POTENTIAL_RELEVANCE ×3, AMBIGUOUS ×2 (ratio/health binding present, no shared identifier) | make-pro, nezvers, open-rpg (+ netfox kept in review) |
| openable_door | POTENTIAL_RELEVANCE ×2, AMBIGUOUS ×2 (`open`, `door`) | open-rpg (+ make-pro `Door.gd`) |
| attack_emitter | POTENTIAL_RELEVANCE ×2, AMBIGUOUS ×2, **INDIRECT_EVIDENCE** ×1 | open-rpg, nezvers, make-pro |
| blackboard | **DIRECT_EVIDENCE** ×1 (`class_name Blackboard` + `set_value`/`get_value`/`has_value`/`erase_value`/`keys`), POTENTIAL ×3 | beehave |

All five pilot Features now have at least one analysis whose code genuinely implements
the capability. Only health and blackboard reach `DIRECT_EVIDENCE`, because only they share
exact identifiers with the Feature projections' source-extracted symbols.

## 3. Rejected-candidate rationale (kept explicit)

* **Miziziziz/MizGodotTools** — the strongest topical match for `attack_emitter` (its
  `attack_emitter.gd` is the Feature's declared source) but the mirror has **no full
  40-character SHA**. Phase 1.71's own gate returns `provenance_status=incomplete` for it,
  and B.1 forbids using an incomplete SHA as new source proof, so it stays out of the
  compliant corpus. Recorded as an access limitation, not as an accepted source.
* **godot-demo-projects / netfox** — relevant but redundant: one thin demo file each, while
  the selected five already cover every pilot Feature. Kept as `NEEDS_REVIEW` for a later
  batch instead of padding the corpus.
* **platformer-2d** — duplicates make-pro's damage pattern; no new capability.
* **godot_experiments / godot-xr-tools** — matched only by file/class names (`hinge_door`,
  `fall_damage`, `damage_area`); reading the code showed no health state, no door state and
  no interaction system. Rejected for name-only similarity.
