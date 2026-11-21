# PHASE 1.76 — BATCH D
## Manual Evidence Review

**Task Type:** CONTROLLED MANUAL EVIDENCE REVIEW
**Phase:** 1.76 / **Batch:** D
**Execution Mode:** READ-ONLY REVIEW
**Prerequisite:** Batch C = `PASS_WITH_LIMITATIONS` (verified)
**Authorization Boundary:** Batch D only. No Parser Hardening, no Coverage Schema change, no Seed
Policy change, no formal Analysis/Linkage update, no Candidate promotion, no Review Queue, no
Batch E, no Git write.

---

## A. Executive Summary

Batch D answers one question: **which Parser 1.76 findings are genuinely valuable functional
evidence, which are merely parser-level discoveries, and what must be fixed before formal evidence
integration?**

| Finding | Result |
|---|---|
| Batch C potential impacts reviewed | **13 / 13** |
| P0 source-level reviews | **6 / 6** (covers P0 groups A–E) |
| P1 source-level reviews | **7 / 7** |
| Source provenance | **13 / 13 `SOURCE_VERIFIED`**, 0 `PROVENANCE_MISMATCH` |
| `get_value` (blackboard) | **`CONFIRMED_SUPPORTING_EVIDENCE`** — real read path into `_data`, same file as the existing DIRECT seed, `NOT_INDEPENDENT`; **not** a new seed |
| `health` / `max_hp` | **`CONFIRMED_SUPPORTING_EVIDENCE`** — state cell and clamp bound behind already-DIRECT seeds; same files/commits; no new independence |
| `is_locked` | **`CONFIRMED_SUPPORTING_EVIDENCE`** — real lock/unlock behaviour with movement blocking; **not** `set_open`/`is_open`, so not DIRECT under identifier rules |
| `current_health` / `maximum` | **`CONFIRMED_DIRECT_EVIDENCE`** + supporting — the Lifebar really subscribes `health_changed` and reads health/max to drive a `TextureProgress`; the only true health_bar implementation found this batch |
| `target_value` | **confirmed NOT door evidence**; conclusion stays `EVIDENCE_INTERPRETATION_CORRECTED_NO_CLASSIFICATION_CHANGE` |
| PARTIAL declaration coverage | **26 declarations audited, 3 missing (1 flagged, 2 unflagged)** — new defect `UNSUPPORTED_CONSTRUCT_REPORTING_INCOMPLETE` |
| Candidates / Seeds | **2 / 2 candidates, 3 / 3 seeds** verified; **0** new seeds, **0** qualification or status changes |
| Graph-derived seed rule | intact (`counts_as_seed=false` on the single context relation) |
| Formal data mutation | **0** across **423** files |
| Verdict | **`PASS_WITH_LIMITATIONS`** |
| Batch E readiness | **`READY_FOR_BATCH_E_WITH_RESTRICTIONS`** |

Five headline conclusions:

1. **Parser 1.76 added no new DIRECT evidence identifier.** All 44 genuinely new Batch B symbols
   yielded, at best, supporting or contextual meaning. The one semantic DIRECT candidate —
   `current_health`/`maximum` in `Lifebar.gd` — is a *human semantic* judgement that the current
   identifier-matching layer cannot express.
2. **The most valuable finding is a read path, not a new symbol set.** `get_value` closes the
   `set/get/has/erase` API square of the already-DIRECT blackboard linkage, but it lives in the same
   file, commit and digest as that seed, so it strengthens rather than expands the evidence base.
3. **`is_locked` is real behaviour, not a state field** — it spawns a cell blocker and selects a
   distinct locked animation — yet the Feature's contract (`set_open`/`is_open`/`_is_open`) shares no
   identifier with it, so the existing `POTENTIAL_RELEVANCE` classification must stand.
4. **Coverage reporting is the weakest link.** `expand_to` and `title_label` are real declarations
   that the parser never captured and never flagged; the reported `unsupported_constructs` entries
   point at a different construct (legacy `setget`) that was in fact captured.
5. **`target_value` moves in the opposite direction from Batch C's worry**: the 1.76 property view
   makes the single AMBIGUOUS door evidence item *less* plausible, and no door evidence is gained.

---

## B. Prerequisite Verification

| Prerequisite | Required | Observed | Source |
|---|---|---|---|
| Batch C Verdict | `PASS_WITH_LIMITATIONS` | `PASS_WITH_LIMITATIONS` | `.ai/learning/external_code/evidence_impact/phase_1.76/audit_validation.json` → `audit.verdict` |
| Batch D Readiness | `READY_FOR_BATCH_D_WITH_RESTRICTIONS` | `READY_FOR_BATCH_D_WITH_RESTRICTIONS` | same file → `audit.batch_d_readiness` |
| 34/34 analysis mapping | complete | 34 / 34 `EXACT_IDENTITY_MATCH` | `analysis_mapping.json` |
| 150 linkages audited | complete | 150 | `linkage_coverage.json` |
| 3 PARTIAL records audited | complete | 3 | `partial_coverage_impact.json` |
| `target_value` standalone audit | complete | present | `target_value_reclassification.json` |
| 2 candidates audited | complete | 2 | `candidate_impact.json` |

No `BLOCKED_PREREQUISITE_MISMATCH`. All seven preconditions hold.

**Input identity:** `manifest.json` in the Batch C workspace declares
`parser_build_identity = gd_parse@1.75+build:6b74a6cd20a06033`, `read_only = true`, and
`counts.batch_d_executed = false`; Batch D did not modify that value.

---

## C. Input Inventory and Provenance

### C.1 Machine-readable inputs

| Input | Records | Use in Batch D |
|---|---:|---|
| `symbol_impact.json` | 92 rows = 59 symbol rows + 33 analysis summaries | authoritative review list: 46 `NO_IMPACT` + **13 potential impacts** |
| `analysis_mapping.json` | 34 | reanalysis-id resolution (4 reused → `parser_1.75/analysis/`) |
| `partial_coverage_impact.json` | 3 | declaration-level starting point |
| `target_value_reclassification.json` | 1 | semantic re-check |
| `candidate_impact.json` | 2 candidates / 3 seeds | seed independence re-check |
| `linkage_coverage.json` | 150 / 30 analyses | linkage-gap confirmation |
| `audit_validation.json` | 1 | prerequisite gate |
| Batch B workspace | 162 files | parser-1.76 symbol/coverage ground truth |
| Formal analysis | 34 (`parser_version=1.71`) | commit, path, digest, coverage identity |
| Formal linkage | 150 | existing classifications and evidence items |
| Candidates | 2 + `WORKSPACE.json` | qualification / independence |
| Seed policy | 3 seeds + 1 context relation | graph-derived rule check |
| Feature metadata | `Features/{health,health_bar,openable_door,blackboard,attack_emitter}/feature.yaml` | target semantics |
| Source copies | 13 commit copies under `code_library/sources/<repo>/gd/` | line-level semantics |

### C.2 Line-number basis (provenance-critical)

Batch B reanalysis records are written against the **references copy**, which prepends **3 lines** to
the commit copy; the formal linkage `line_reference` values follow the same space. Batch D read the
**commit copies** under `.ai/skills/foundation/godot-gdscript/code_library/sources/…`, whose SHA256
equals the recorded `source_digest` in every case (13 / 13 `MATCH`).

- **Every line number in this report is a commit line.**
- `record_line = commit_line + 3` (verified on 26 declarations across the 3 PARTIAL files, and on
  the candidate seed locations, e.g. `is_dead` commit 16 / record 19).
- The `unsupported_constructs[].line` field is in **record space**, not commit space. This mixed
  line space is itself a reporting defect (see §G.4).

### C.3 Source verification result

`source_verification.json` records, per item: repository, full commit SHA, path, recorded digest,
local copy digest, digest status, line basis, symbol-at-line check, and the existing linkage record
digest. Result: **13 / 13 `MATCH` + `VERIFIED`** for the reviewed items, plus the two PARTIAL files
that carry no review item (`blackboard_compare.gd`, `board_card.gd`) — **15 rows, 15 verified, 0
mismatched** (`board_member_button.gd` is already item 13). No repository-copy fallback was needed;
no line offset was assumed.

---

## D. Complete Review Item Inventory

Deterministic scope: every row in `symbol_impact.json` with an `impact_classification` other than
`NO_IMPACT`. That yields exactly the 13 items below — identical to the Batch C set, with no additions
and no omissions.

| ID | Symbol | Analysis | Feature | Existing linkage | Batch C | Priority |
|---|---|---|---|---|---|---|
| RV-176D-01 | `health` | `ext-1d204b35464cf388` | health | `lnk-d2d95d8162be1592` (DIRECT) | STRENGTHENING | P0 |
| RV-176D-02 | `get_value` | `ext-23949c1378c49203` | blackboard | `lnk-7084dc8999c2182b` (DIRECT) | STRENGTHENING | P0 |
| RV-176D-03 | `key` | `ext-27ddd863881677d7` | blackboard | `lnk-bb935a2c8bdbfc39` (POTENTIAL) | STRENGTHENING | P1 |
| RV-176D-04 | `value` | `ext-27ddd863881677d7` | blackboard | `lnk-bb935a2c8bdbfc39` (POTENTIAL) | STRENGTHENING | P1 |
| RV-176D-05 | `is_locked` | `ext-51d46c1b4943a254` | openable_door | `lnk-b382814f8bca80a5` (POTENTIAL) | STRENGTHENING | P0 |
| RV-176D-06 | `door` | `ext-5a8d53c7f530e4af` | openable_door | none (gap) | FEATURE_MATCH | P1 |
| RV-176D-07 | `max_hp` | `ext-73c80a3db6d71e48` | health | `lnk-6fff3ce176bd5813` (DIRECT) | STRENGTHENING | P0 |
| RV-176D-08 | `current_health` | `ext-9f0aad5e01dd71f7` | health_bar | `lnk-bdec07041badaf0d` (NO_SUPPORTED_LINK) | FEATURE_MATCH | P0 |
| RV-176D-09 | `maximum` | `ext-9f0aad5e01dd71f7` | health_bar | `lnk-bdec07041badaf0d` (NO_SUPPORTED_LINK) | FEATURE_MATCH | P1 |
| RV-176D-10 | `size` | `ext-ab693f3d6ef9439c` | health_bar | none (gap) | FEATURE_MATCH | P1 |
| RV-176D-11 | `base_damage` | `ext-d5f7ac2db3a8c4e4` | attack_emitter | `lnk-01c9ea986153c619` (POTENTIAL) | FEATURE_MATCH | P1 |
| RV-176D-12 | `target_value` | `ext-7d7933a2343f52d0` | openable_door | `lnk-23addea8960377c4` (AMBIGUOUS) | RECLASSIFICATION | P0 |
| RV-176D-13 | `board` | `ext-9e62ed2e3dec8164` | blackboard | `lnk-042638ff10ae0b0e` (NO_SUPPORTED_LINK) | REQUIRES_MANUAL_REVIEW | P1 |

Batch C also listed "Potential Contradiction" as a possible class. **Zero contradiction records
exist** in `symbol_impact.json`; nothing in this batch creates one.

---

## E. P0 Manual Evidence Review

### E.1 `get_value` — blackboard (`RV-176D-02`)

**Provenance** — `bitbrain/beehave`, `addons/beehave/blackboard.gd`, commit
`fe589153fa780a3f88989578ceb5f539afffb7c2`, digest
`e1b980ce875b611f5881d158c4cce4d61b92ce8f27e09101304e8014706c10b6` (MATCH). Declaration kind
**FUNCTION**, commit lines **34–39**. Existing linkage `lnk-7084dc8999c2182b` = **DIRECT_EVIDENCE**
with 5 exact evidence items (`Blackboard`, `keys`, `set_value`, `has_value`, `erase_value`), seed
`QUALIFIED_DIRECT`, independence **NOT_INDEPENDENT**.

**Observed behaviour (commit lines)**

```
34  func get_value(
35      key: Variant, default_value: Variant = null, blackboard_name: String = DEFAULT
36  ) -> Variant:
37      if has_value(key, blackboard_name):
38          return _data[blackboard_name].get(key, default_value)
39      return default_value
```

**Findings against the ten required checks**

1. Complete implementation read: 6 lines, no delegation to an external store. ✔
2. Parameters: `key: Variant`, `default_value: Variant = null`, `blackboard_name: String = DEFAULT`
   (`DEFAULT = "default"`, L4); returns `Variant`. ✔
3. It does read Blackboard state: `_data[blackboard_name]` is the very `Dictionary` the Feature
   declares as ownership state (`_data: Dictionary`, L13). ✔
4. Key lookup with default (`Dictionary.get(key, default_value)`), no type conversion, and the
   `has_value` pre-check applies the null-as-absent rule (L42–47). ✔
5. Callers inside this file: none. Consumers exist in the addon's leaves — `blackboard_compare.gd`
   documents `get_value("key_name")` expressions (L19, L26) and `blackboard_set.gd` calls
   `blackboard.set_value(...)` (L26). Cross-file call graph is **not parsed**, so caller counts are
   file-documented usage only, not a verified call graph. ✔ (partially verified)
6. Multiple behaviour nodes use the blackboard API; the exact call sites live in expression strings
   executed at runtime, so static call counting is not decidable. Recorded as a limitation.
7. Consistent with the Feature definition: the Feature's interface list contains the identical
   `get_value(key, default_value, blackboard_name) -> Variant` signature. ✔
8. **Not** merely a generic getter: it is one of four symmetric operations on a named-board
   dictionary, and the other three are already exact-matched in the same DIRECT linkage.
9. Independent evidence value: **no**. Same file, same commit, same digest, same linkage. It
   strengthens the existing claim and cannot found a second seed.
10. Same-repository / same-implementation / same-evidence-source as the existing DIRECT seed: yes on
    all three — the candidate's `NOT_INDEPENDENT` verdict is unaffected.

**Conclusion:** `CONFIRMED_SUPPORTING_EVIDENCE` · `SOURCE_VERIFIED` · confidence **HIGH** ·
follow-up `ELIGIBLE_FOR_FUTURE_FORMAL_REVIEW`.

*Why not DIRECT:* the linkage is already DIRECT; `get_value` adds a sixth exact identifier to that
same claim rather than creating a new claim. *Why not GENERIC_API_EVIDENCE:* the getter is bound to
the Feature's declared `_data` state, not to unrelated data.

### E.2 Health: `health`, `hp`, `max_hp` (`RV-176D-01`, `RV-176D-07`)

**`health` — gdquest-demos/godot-make-pro-2d-games, `actors/health/Stats.gd`, commit
`7290681309ffcd700c2c08a8e59a57bfbec14d5e`** (digest
`ef9f678100f419defea9868954ec434e168d0e03135683a66ad0b66f4ed1a20b`, MATCH).

- L9 `var health = 0` — the live value; L15 `_ready()` seeds it from `max_health`.
- L20–26 `take_damage()`: subtract, `max(0, health)` clamp, emits `health_changed` + `damage_taken`,
  emits `health_depleted` at 0 → **real damage state management**.
- L28–31 `heal()`: add, clamp with `max(health, max_health)` (an upstream bug worth noting: it
  behaves as a full heal), emits `health_changed`.
- Existing linkage `lnk-d2d95d8162be1592` is DIRECT via `take_damage`/`heal`/`health_changed`.
- `health` itself is not a Feature symbol (the Feature exposes `max_health`, `take_damage`, …), so it
  is not a new exact identifier; it is the state cell behind the existing one.

**`max_hp` — nezvers/Godot-GameTemplate, `addons/top_down/scripts/damage/HealthResource.gd`, commit
`d5d8d15887423b3a8acf0502efb6271c600a80bc`** (digest
`fed9dc57052f1f9ed40702116d1237ab3775618d336e6e6850d928ab7614bd94`, MATCH).

- L12 `@export var max_hp:float = 5`; L18–20 `set_max_hp` emits `max_hp_changed`.
- L38–49 `add_hp()`: `clamp(hp + value, 0.0, max_hp)`, `damaged` on negative, `is_dead = true` +
  `dead` at 0, `full` at `hp == max_hp`.
- The seed's recorded limitation "parser captured 1 of 5 @export vars, so
  hp/max_hp/reset_hp/reset_max_hp are absent" is **removed** by 1.76 — but the identifier `max_hp`
  is not `max_health`, so no exact match is created.

**`hp`:** not a Batch C potential-impact item (it appears only as part of the reused Phase 1.75
symbol set). Inspected anyway: L11 `@export var hp:float = 5`, written by `reset_resource` (L25),
`prepare_load` (L31), `add_hp` (L39). It is the same state cell as `max_hp`; no separate conclusion.

**Judgement**

| Question | `health` | `max_hp` |
|---|---|---|
| Direct implementation evidence of Health? | Supporting, not direct (no exact identifier; `health_depleted` ≠ `died`, arity differs) | Supporting (`is_dead` remains the only exact identifier) |
| Merely a numeric store? | No — mutated by damage/heal with clamps and signals | No — it is the clamp bound and full threshold |
| Real health-state management? | Yes | Yes |
| Independent of existing seed? | **No** (same file/commit/digest as `lnk-d2d95d8162be1592`) | **No** (same as `lnk-6fff3ce176bd5813`) |
| Duplicate of existing evidence? | Same implementation, additional symbol | Same implementation, additional symbol |
| Cross-repo independent implementation? | No | No |

**Conclusion:** both `CONFIRMED_SUPPORTING_EVIDENCE` · `SOURCE_VERIFIED` · **HIGH** ·
`ELIGIBLE_FOR_FUTURE_FORMAL_REVIEW`. **Neither may be counted as a new seed.**

### E.3 `is_locked` — openable_door (`RV-176D-05`)

**Provenance** — `gdquest-demos/godot-open-rpg`,
`src/field/cutscenes/templates/doors/door.gd`, commit
`d59f2f71bc046ac53239a4e590861269e7100a36`, digest
`f4df1c3da5f5216716cc6d46105bd9f85ed5b9b3523a8cea99b8d4ae3f92c478` (MATCH). Declared kind
**PROPERTY**, commit **7–25**; behaviour in `open()` **39–49**. Existing linkage
`lnk-b382814f8bca80a5` = **POTENTIAL_RELEVANCE** via `Door`/`open` tokens only.

1. **Declaration:** `@export var is_locked := false` (L7) with an inline setter (L8–25).
2. **Setter:** guards re-entry (`value != is_locked`), awaits `ready` if outside the tree (L12–13),
   and — this is the substantive part — when locking instantiates `GP_SCENE` (a gamepiece) as
   `_dummy_gp`, names it `CellBlocker`, and adds it to `_closed_door` (L15–19); when unlocking it
   calls `open()` and frees the blocker (L21–25).
3. **Reads/writes:** read in `open()` (L44); written by the setter and by
   `overworld/maps/town/door_unlock_interaction.gd:13` after consuming a KEY.
4. **Door open/close/lock logic:** `open()` returns early if already open (L41–42), plays `locked`
   while locked (L44–45), otherwise plays `open` (L47–48), awaits `animation_finished`; entering the
   area also plays `open` (L52–55).
5. **Feature consistency:** the Feature's contract is `set_open(bool)` / `is_open()` / `_is_open` /
   `state_changed` / `start_open`. A locked door is *not* an open door: `is_locked` gates opening but
   does not represent open state, and `open()` here is an animation trigger, not a collision toggle.
6. **Real lock state, not UI/temporary:** confirmed — it physically blocks a board cell via the
   dummy gamepiece and selects a distinct animation.
7. **Real callers:** `door_unlock_interaction.gd` L9 reads it, L13 sets it false; `open()` branches on
   it. Interaction is genuine.

**Conclusion:** `CONFIRMED_SUPPORTING_EVIDENCE` · `SOURCE_VERIFIED` · **HIGH** ·
`ELIGIBLE_FOR_FUTURE_FORMAL_REVIEW`. It is **not** Openable Door DIRECT evidence (no identifier
correspondence, different state model), it is **not** a duplicate of an existing evidence item (the
existing items are `Door`/`open`), and it does require a human semantic decision before any
classification change.

### E.4 `current_health` / `maximum` — health_bar (`RV-176D-08`, `RV-176D-09`)

**Provenance** — `gdquest-demos/godot-make-pro-2d-games`,
`interface/gui/player/life_bar/Lifebar.gd`, commit
`7290681309ffcd700c2c08a8e59a57bfbec14d5e`, digest
`e032da8e7dfa0f97d2892441329da8fc966febc9d3b388e498df441981e56e5a` (MATCH). Existing linkage
`lnk-bdec07041badaf0d` = **NO_SUPPORTED_LINK** (5 external symbols vs 7 Feature source + 8 declared).

```
5   var maximum = 100
6   var current_health = 0
8   func initialize(health_node):
9       health_node.connect('health_changed', self, '_on_Player_Health_health_changed')
10      maximum = health_node.max_health
11      current_health = health_node.health
13      animate_bar(current_health)
15  func _on_Player_Health_health_changed(new_health):
16      animate_bar(new_health)
17      current_health = new_health
19  func animate_bar(target_health):
20      $TextureProgress.animate_value(current_health, target_health)
21      $TextureProgress.update_color(target_health)
```

| Check | Result |
|---|---|
| Current / maximum meaning | Current HP and the bar's upper bound, both taken from the bound Health node |
| Progress control binding | `$TextureProgress` (`TextureProgress`), `animate_value` / `update_color` |
| Update mechanism | Signal subscription to `health_changed` (L9) + immediate repaint (L20–21) |
| Listens to Health changes | **Yes** — this is the decisive fact |
| Generic UI component? | No — it is coupled to a `health_node` API (`max_health`, `health`, `health_changed`) |
| Matches health_bar Feature definition | **Yes**: "血条显示组件：绑定宿主 Health，按当前/最大生命值比例绘制…纯显示、只读" |

**Conclusion:** `current_health` = **`CONFIRMED_DIRECT_EVIDENCE`**; `maximum` =
**`CONFIRMED_SUPPORTING_EVIDENCE`**; both `SOURCE_VERIFIED`, **HIGH**, follow-up
`ELIGIBLE_FOR_FUTURE_FORMAL_REVIEW`. Both are `HEALTH_BAR_FUNCTIONAL_IMPLEMENTATION`, not
`GENERIC_PROGRESS_DISPLAY`, because the UI is provably wired to health state. This is a **review
conclusion only** — the formal linkage stays `NO_SUPPORTED_LINK` because `current_health` is not
`get_ratio` and no semantic-link rule exists.

### E.5 `target_value` — openable_door (`RV-176D-12`)

**Provenance** — `gdquest-demos/godot-open-rpg`, `src/combat/ui/battler_entry/ui_life_bar.gd`,
commit `d59f2f71bc046ac53239a4e590861269e7100a36`, digest
`38a36c53f2429cad49e447d9a3a4222df1547d6d749b48237c7f1c06f0e57e19` (MATCH).

| Aspect | Formal 1.71 | Batch B 1.76 | Source (commit) |
|---|---|---|---|
| Kind | `variables` (implied) | `PROPERTY` | `var target_value := 0.0:` with setter |
| Value | `"0.0:"` (colon swallowed) | `"0.0"` | `0.0` |
| Lines | record 18 | record 18, setter 19, end 18 | declaration 15, setter 16–33 |
| Setter | not modelled | `has_setter = true` | L16–33 |

**Behaviour:** on decrease it plays the `damage` animation (L19–20), stores the value, kills the
running tween, computes `duration = abs(target_value - value) / max_value * fill_rate` (L26) and
tweens `value` toward it (L27–28), then plays `danger` below `danger_cutoff * max_value` (L29–33).

**Judgement:** a tweened life-bar target on a `TextureProgressBar` subclass — no door semantics. The
only formal evidence item citing the symbol is `lnk-23addea8960377c4:ev:01`, a token overlap
(`target` vs `boolean_target`) already classified **AMBIGUOUS**. The 1.76 property view makes the
door association weaker, not stronger. The reclassification is a **representation correction**: not
a removal, not two symbols.

**Conclusion:** `NOT_RELEVANT` (as door evidence) · `SOURCE_VERIFIED` · **HIGH** · follow-up
`ELIGIBLE_FOR_FUTURE_FORMAL_REVIEW` (re-word the single AMBIGUOUS item; **no classification change
authorized**). Conclusion: `EVIDENCE_INTERPRETATION_CORRECTED_NO_CLASSIFICATION_CHANGE`, unchanged
from Batch C.

---

## F. P1 Manual Evidence Review

### F.1 `key`, `value` — blackboard (`RV-176D-03`, `RV-176D-04`)

**Provenance** — `bitbrain/beehave`, `addons/beehave/nodes/leaves/blackboard_set.gd`, commit
`fe589153fa780a3f88989578ceb5f539afffb7c2`, digest
`fb4fc4dde707ecf1d20998cb6d6da6d9568b73af060ecfa7e1aeb337453410e0` (MATCH). Commit lines 7 and 9.

Both are `@export_placeholder(EXPRESSION_PLACEHOLDER) var …: String = ""` — *expression source
strings*, compiled with `_parse_expression` (L11–12) and executed against the blackboard (L16, L21);
the results are passed to `blackboard.set_value(key_value, value_value)` (L26).

| Question | Answer |
|---|---|
| Real declaration kind | `VARIABLE` (exported String) — confirmed |
| Feature correspondence | The Feature has no `key` or `value` symbol |
| Independent evidence value | None: placeholder strings, not blackboard data |
| Existing linkage | `POTENTIAL_RELEVANCE` on the class token `blackboard` only — must not be upgraded |

**Conclusion:** both `CONTEXT_ONLY` · `SOURCE_VERIFIED` · **HIGH** · `NO_FURTHER_ACTION`. The file is
consumer-side usage of `set_value`; usable context, not implementation evidence.

### F.2 `door` — openable_door (`RV-176D-06`)

**Provenance** — `gdquest-demos/godot-open-rpg`, `overworld/maps/town/door_unlock_interaction.gd`,
commit `d59f2f71bc046ac53239a4e590861269e7100a36`, digest
`8573670e7381df7c2f9cb36a6fc06307bccc753bc865664a23fb49595e22dade` (MATCH). Commit line 4:
`@onready var door := get_parent() as Door`.

The symbol is a typed node reference, but the surrounding `_execute()` (L8–17) is real unlock
behaviour: check `door.is_locked`, require and consume `Inventory.ItemTypes.KEY`, set
`door.is_locked = false`, deactivate the popup, then `door.open()`.

**Conclusion:** `CONTEXT_ONLY` · `SOURCE_VERIFIED` · **HIGH** · `REQUIRES_ADDITIONAL_SOURCE_REVIEW`.
This analysis has **no formal linkage record at all**, so there is no link to strengthen; the
analysis-level gap is carried to §K.

### F.3 `size` — health_bar (`RV-176D-10`)

**Provenance** — `lampe-games/godot-open-rts`, `source/match/units/traits/HealthBar.gd`, commit
`a628ad3bb6a9a903587a181a7ee3300dbf735e81`, digest
`cc6b52103cccd74235624dea1edb0904c4d6ae36366f7be2630c9e257434b3eb` (MATCH). Commit 6–10.

`@export var size = Vector2(200, 20)` with a setter assigning
`find_child("ActualBar").texture.width/height`. Purely visual sizing; `bar_size` in the Feature is a
different identifier and a different concept. Notably, the **file** is a genuine unit health bar
(`_recalulate_bar_value()` computes `_unit.hp / _unit.hp_max` into a gradient offset, `hp_changed`
connected at L26) — but it has **no formal linkage at all**, which is a health_bar coverage gap, not
a `size` evidence item.

**Conclusion:** `GENERIC_API_ONLY` · `SOURCE_VERIFIED` · **HIGH** · `NO_FURTHER_ACTION`.

### F.4 `base_damage` — attack_emitter (`RV-176D-11`)

**Provenance** — `gdquest-demos/godot-open-rpg`, `src/combat/actions/battler_action_attack.gd`, commit
`d59f2f71bc046ac53239a4e590861269e7100a36`, digest
`754107d5816d19184cce8aeebcc07d0cb89a4fd445726836a6249e4eb9237d86` (MATCH). Commit line 9.

`@export var base_damage: = 50`; `execute()` (L12–53) computes
`base_damage + source.stats.attack` plus ±10 % noise (L35–36), builds `BattlerHit.new(...)` (L42) and
applies it with `target.take_hit(hit)` (L43).

The Feature is an emitter chain: `do_attack()` broadcasts `attacked`/`attack_performed`/`attack_hit`
and settles damage through `Health.take_damage`. This file has no emitter, no chain, no signal and no
`take_damage` call; damage flows through the turn-based `BattlerHit`/`take_hit` protocol. It is
adjacent context at best; the existing `POTENTIAL_RELEVANCE` rests on the class token `attack`.

**Conclusion:** `CONTEXT_ONLY` · `SOURCE_VERIFIED` · **MEDIUM** (protocol divergence is clear from
source, but the semantic distance between "turn-based attack action" and "attack emitter" is a
judgement call) · `NO_FURTHER_ACTION`.

### F.5 `board` — blackboard (`RV-176D-13`)

**Provenance** — `alfredbaudisch/Godello`, `scripts/board_member_button.gd`, commit
`4458a143644fbadec23ae0cee99578ad3b811eb8`, digest
`540fdf1f898b8909b51cf68fe501aa370bba25b069653ab2135556b34038bc75` (MATCH). Commit line 7:
`var board : BoardModel setget set_board`.

Read as `board.user_owner` (L42) and `board.remove_member(model)` (L47) — a Kanban board model. The
only relation to the Feature is the token `board`.

**Conclusion:** `NOT_RELEVANT` · `SOURCE_VERIFIED` · **HIGH** · `NO_FURTHER_ACTION`. Retained as an
explicit negative so a future name-based matcher cannot resurrect it.

---

## G. PARTIAL Coverage Deep Review

Three records, **26 top-level declarations**, 3 missing, 2 unreported. All three commit copies
verified against recorded digests; all line numbers are commit lines.

### G.1 `ext-55aef2d453370c1b` — `addons/beehave/nodes/leaves/blackboard_compare.gd`

Commit `fe589153fa780a3f88989578ceb5f539afffb7c2`, digest `cd7008ea…df75` (MATCH). Batch B:
`coverage_status=PARTIAL`, `syntax_coverage_status=PARTIAL`, `analysis_completeness=FULL`,
`parse_status=parsed`, `unsupported_constructs=[ENUM_NOT_INTERPRETED line 10 (name Operators)]`.

| Declaration | Source Location | Parser Result | Unsupported Reported | Coverage Finding |
|---|---|---|---|---|
| `class_name BlackboardCompareCondition` | :5 | CAPTURED | no | `SOURCE_CONFIRMED` |
| `enum Operators` | :7 | **NOT_CAPTURED** | yes (`ENUM_NOT_INTERPRETED`) | `UNSUPPORTED_CONSTRUCT_REPORTED` |
| `var left_operand` | :20 | CAPTURED | no | `SOURCE_CONFIRMED` |
| `var operator` | :22 | CAPTURED | no | `SOURCE_CONFIRMED` |
| `var right_operand` | :27 | CAPTURED | no | `SOURCE_CONFIRMED` |
| `var _left_expression` | :29 | CAPTURED | no | `SOURCE_CONFIRMED` |
| `var _right_expression` | :30 | CAPTURED | no | `SOURCE_CONFIRMED` |
| `func tick` | :33 | CAPTURED | no | `SOURCE_CONFIRMED` |
| `func _get_expression_sources` | :63 | CAPTURED | no | `SOURCE_CONFIRMED` |

`unsupported_reporting_completeness = COMPLETE` for this file. The reported line (10) is the record
line; the commit line is 7 — correct construct, inconsistent line space.

### G.2 `ext-9e62ed2e3dec8164` — `scripts/board_member_button.gd`

Commit `4458a143644fbadec23ae0cee99578ad3b811eb8`, digest `540fdf1f…bc75` (MATCH). Batch B:
`PARTIAL` / `PARTIAL` / `FULL` / `parse_status=partial`,
`unsupported_constructs=[LEGACY_SETGET_NOT_INTERPRETED line 9, line 10]`.

| Declaration | Source Location | Parser Result | Unsupported Reported | Coverage Finding |
|---|---|---|---|---|
| `export(String) var expand_to` | :4 | **NOT_CAPTURED** | **no** | `UNSUPPORTED_CONSTRUCT_NOT_REPORTED` |
| `var model … setget set_model` | :6 | CAPTURED | yes (`LEGACY_SETGET_NOT_INTERPRETED`) | `UNSUPPORTED_CONSTRUCT_REPORTED` |
| `var board … setget set_board` | :7 | CAPTURED | yes (`LEGACY_SETGET_NOT_INTERPRETED`) | `UNSUPPORTED_CONSTRUCT_REPORTED` |
| `var normal_text` | :8 | CAPTURED | no | `SOURCE_CONFIRMED` |
| `func _ready` | :11 | CAPTURED | no | `SOURCE_CONFIRMED` |
| `func set_model` | :15 | CAPTURED | no | `SOURCE_CONFIRMED` |
| `func set_board` | :25 | CAPTURED | no | `SOURCE_CONFIRMED` |
| `func _on_BoardOwnerButton_gui_input` | :29 | CAPTURED | no | `SOURCE_CONFIRMED` |
| `func _on_Timer_timeout` | :35 | CAPTURED | no | `SOURCE_CONFIRMED` |
| `func _on_BoardMemberButton_pressed` | :41 | CAPTURED | no | `SOURCE_CONFIRMED` |
| `func _on_delete_confirmed` | :46 | CAPTURED | no | `SOURCE_CONFIRMED` |

`unsupported_reporting_completeness = INCOMPLETE`. **Key finding:** the two reported entries describe
the legacy `setget` construct on `model`/`board`, which *was* captured as a variable (only the
accessor semantics were not interpreted). The genuinely un-captured declaration — the `export`
`expand_to` at commit line 4 — is **not reported at all**. The flag therefore points at accepted
partial interpretation while the real omission stays invisible.

### G.3 `ext-fffa637657ffede1` — `scripts/board_card.gd`

Commit `4458a143644fbadec23ae0cee99578ad3b811eb8`, digest `9d67c3fe…b3fa` (MATCH). Batch B:
`PARTIAL` / `PARTIAL` / `FULL` / `parse_status=partial`,
`unsupported_constructs=[LEGACY_SETGET_NOT_INTERPRETED line 7]`.

| Declaration | Source Location | Parser Result | Unsupported Reported | Coverage Finding |
|---|---|---|---|---|
| `var model … setget set_model, get_model` | :4 | CAPTURED | yes (`LEGACY_SETGET_NOT_INTERPRETED`) | `UNSUPPORTED_CONSTRUCT_REPORTED` |
| `onready var title_label := $Title` | :6 | **NOT_CAPTURED** | **no** | `UNSUPPORTED_CONSTRUCT_NOT_REPORTED` |
| `func _ready` | :9 | CAPTURED | no | `SOURCE_CONFIRMED` |
| `func set_model` | :14 | CAPTURED | no | `SOURCE_CONFIRMED` |
| `func get_model` | :19 | CAPTURED | no | `SOURCE_CONFIRMED` |
| `func _on_board_deleted` | :23 | CAPTURED | no | `SOURCE_CONFIRMED` |

`unsupported_reporting_completeness = INCOMPLETE`. `title_label` is a plain `onready var`; the parser
emits no `unsupported_constructs` entry for it and no coverage nuance beyond `PARTIAL`.

### G.4 Coverage Reporting Defect Classification

| Finding | Code |
|---|---|
| `Operators` enum missing from symbol table, explicitly flagged | `UNSUPPORTED_CONSTRUCT_REPORTED` |
| `expand_to` export missing, no flag | `UNSUPPORTED_CONSTRUCT_NOT_REPORTED` |
| `title_label` onready var missing, no flag | `UNSUPPORTED_CONSTRUCT_NOT_REPORTED` |
| `Operators` declared at commit 7 / reported at record 10 | line-space inconsistency (see below) |
| All three missing declarations exist in source | `SOURCE_CONFIRMED` |
| Parser capability boundary for legacy `setget` / `onready` / `@export` | `PARSER_COVERAGE_UNKNOWN` beyond the observed cases |

**Defect:** `UNSUPPORTED_CONSTRUCT_REPORTING_INCOMPLETE`.

Three distinct sub-defects are visible:

1. **Detection gap.** `expand_to` (`export(String) var …`) and `title_label` (`onready var …`) are not
   in the symbol table and produce no diagnostic, so `PARTIAL` is under-reported in content while
   being correctly reported in status.
2. **Flag-target mismatch.** The reported `LEGACY_SETGET_NOT_INTERPRETED` entries refer to lines whose
   declarations *were* captured. A consumer reading "unsupported" would look at `model`/`board`,
   not at the real omission.
3. **Line-space mixing.** `unsupported_constructs[].line` uses record space (`commit + 3`) while
   formal `symbols` entries use record space too but `line_reference` values in linkage records are
   often `null`; consumers cannot tell which space a bare integer belongs to without external
   knowledge. Additionally the formal 1.71 records carry **no** `unsupported_constructs` field at
   all — coverage is expressed only as `parse_status=partial`.

### G.5 Impact Scope

| Possible impact | Assessment |
|---|---|
| Blackboard Feature | **None.** `Operators` is a comparison enum, `expand_to` a UI text string, `title_label` a label reference. None implements store/read/has/erase semantics. |
| Existing DIRECT / POTENTIAL linkages | **None changed.** All five linkages on each PARTIAL analysis remain as recorded; absence of a parsed symbol is not evidence of absence. |
| Seed evidence | **None.** No PARTIAL analysis is a candidate seed. |
| Candidate independence | **None.** No seed touches these three analyses. |
| Feature semantic judgement | **None established.** The missing declarations carry no health/health_bar/door/blackboard/attack semantics. |
| Untested risk | A future `expand_to`-style `export` reminder: `board_member_button.gd` had an export the parser missed, so `analysis_completeness=FULL` with `syntax_coverage_status=PARTIAL` must never be read as "all declarations captured". |

### G.6 Remediation Design (no implementation in this batch)

`UNSUPPORTED_CONSTRUCT_REPORTING_INCOMPLETE`. Future Parser / Coverage Hardening should satisfy:

1. Every known unsupported construct has an explicit detector (`export(X) var` without a supported
   annotation, `onready var`, legacy `setget`, `enum`, multi-line `@export` with setter blocks).
2. `unsupported_constructs` covers the declarations **actually** missing, not only constructs that
   were partially interpreted.
3. Coverage status is not derived from "parse succeeded"; a declaration inventory diff (source
   declarations vs symbol table) should decide `COMPLETE` vs `PARTIAL`.
4. If a completeness cross-check cannot run, the record must **not** output `COMPLETE`.
5. `unsupported_constructs[].line` must state its line space (or be normalised to commit lines).

---

## H. Candidate and Seed Review

Two candidates, three seeds — all `NEEDS_REVIEW`, `policy_version = phase-1.74-c/1`. Every recorded
digest was recomputed from the actual file on disk.

| Candidate | Feature | Seeds | Status | Verdict |
|---|---|---:|---|---|
| `cand-08fdc0b10a112ecf` | health | 2 | `NEEDS_REVIEW` | **RETAIN_AS_IS** |
| `cand-7f52cb8f583124db` | blackboard | 1 | `NEEDS_REVIEW` | **RETAIN_AS_IS** |

### H.1 `cand-08fdc0b10a112ecf` (health)

| Seed | Eligibility | Independence | Analysis digest | Linkage digest | Source digest | Batch B status | Batch D item |
|---|---|---|---|---|---|---|---|
| `lnk-6fff3ce176bd5813` | `QUALIFIED_DIRECT_WITH_LIMITATIONS` | INDEPENDENT | MATCH | MATCH | MATCH | `REUSED_PHASE_1_75` | `max_hp` |
| `lnk-d2d95d8162be1592` | `QUALIFIED_DIRECT` | INDEPENDENT | MATCH | MATCH | MATCH | `REUSED_PHASE_1_75` | `health` |

- Source identities: `nezvers/Godot-GameTemplate@d5d8d158…`, `gdquest-demos/godot-make-pro-2d-games@72906813…`.
- Context ref: `lnk-a099657ab3c9930c` (`attack_emitter`, `GRAPH_DERIVED_RELATION`,
  `counts_as_seed=false`, `counts_as_implementation_evidence=false`) — unchanged, still not a seed.
- Impact of the 13 items: both reviewed symbols are **inside the seed files themselves**. `max_hp` is
  the clamp bound the `is_dead` seed relies on; `health` is the state cell of the `take_damage` seed.
  Neither adds a repository, commit or digest → **0 new independent seeds**, qualification unchanged.
- The removed seed limitation ("parser captured 1 of 5 @export vars") is a **limitation-text change
  only**; it does not alter eligibility, and no rewrite is authorized here.

### H.2 `cand-7f52cb8f583124db` (blackboard)

| Seed | Eligibility | Independence | Analysis digest | Linkage digest | Source digest | Batch B status | Batch D item |
|---|---|---|---|---|---|---|---|
| `lnk-7084dc8999c2182b` | `QUALIFIED_DIRECT` | **NOT_INDEPENDENT** | MATCH | MATCH | MATCH | `REUSED_PHASE_1_75` | `get_value` |

- `get_value` is a sixth exact identifier in the **same** linkage, same file, same commit, same
  digest. It cannot introduce independence: the internal Feature declares it was abstracted from
  bitbrain/beehave, and `get_value` confirms the same derivation.
- The candidate's own limitation already records `analysis_status=analysis_partial (@icon annotation
  not interpreted)`; Batch D confirms the partial status is accurate but does not change it.
- **0 new seeds**, **0 status changes**.

### H.3 Seed Policy Audit

| Requirement | Observation |
|---|---|
| `graph-derived evidence must not count as an independent seed` | **Enforced** — `context_relations[0]` carries `counts_as_seed=false` / `counts_as_implementation_evidence=false`, and the candidate `context_refs` repeat them |
| Seeds keyed to formal records | Yes — `linkage_id` + analysis/linkage digests; workspace results cannot satisfy these references |
| Explicit "formal analysis only" rule | **Absent** (implicit via digests only) — unchanged gap |
| Machine-readable coverage gate | **Absent** — no `coverage_status` / `parser_version` field in the policy |
| Seed count consistency | 3 policy seeds = 3 candidate seeds, eligibility strings match |

**Conclusion:** `READ_ONLY_REVIEWED`, no policy change proposed in this batch.

---

## I. Evidence Classification Summary

| Semantic assessment | Count | Items |
|---|---:|---|
| `CONFIRMED_DIRECT_EVIDENCE` | 1 | `current_health` |
| `CONFIRMED_SUPPORTING_EVIDENCE` | 5 | `health`, `get_value`, `is_locked`, `max_hp`, `maximum` |
| `GENERIC_API_ONLY` | 1 | `size` |
| `CONTEXT_ONLY` | 4 | `key`, `value`, `door`, `base_damage` |
| `NOT_RELEVANT` | 2 | `target_value` (door), `board` |
| `STATE_DECLARATION_ONLY` | 0 | — |
| `DUPLICATE_EVIDENCE` | 0 | — (duplication is recorded inside the supporting reasoning) |
| `INSUFFICIENT_SOURCE_EVIDENCE` | 0 | — |
| `COVERAGE_BLOCKED` | 0 | — |

| Evidence integrity | Count |
|---|---:|
| `SOURCE_VERIFIED` | 13 |
| `SOURCE_PARTIALLY_VERIFIED` | 0 |
| `SOURCE_NOT_VERIFIED` | 0 |
| `PROVENANCE_MISMATCH` | 0 |

| Follow-up | Count | Items |
|---|---:|---|
| `ELIGIBLE_FOR_FUTURE_FORMAL_REVIEW` | 7 | `health`, `get_value`, `is_locked`, `max_hp`, `current_health`, `maximum`, `target_value` |
| `REQUIRES_ADDITIONAL_SOURCE_REVIEW` | 1 | `door` (no linkage exists) |
| `REQUIRES_PARSER_HARDENING` | 0 (items) | the requirement is record-level, see §G.6 |
| `NO_FURTHER_ACTION` | 5 | `key`, `value`, `size`, `base_damage`, `board` |
| `DO_NOT_PROMOTE` | 0 | — |

**Cross-tab with Batch C:** 6 STRENGTHENING → 2 supporting (`get_value`, `health`/`max_hp`/`is_locked`)
+ 2 context (`key`, `value`); 5 FEATURE_MATCH → 1 direct + 1 supporting (`current_health`,
`maximum`), 1 generic, 2 context; 1 RECLASSIFICATION → 1 not-relevant; 1 REQUIRES_MANUAL_REVIEW → 1
not-relevant. **No Batch C classification survives as a new DIRECT linkage**, and exactly one item
reaches semantic DIRECT value.

---

## J. Severity and Confidence Summary

| Review severity | Count | Items |
|---|---:|---|
| CRITICAL | 0 | — |
| HIGH | 0 | — |
| MEDIUM | 4 | `get_value`, `is_locked`, `current_health`, `target_value` |
| LOW | 5 | `health`, `max_hp`, `maximum`, `door`, `board` |
| INFO | 4 | `key`, `value`, `size`, `base_damage` |

| Confidence | Count | Items |
|---|---:|---|
| HIGH | 12 | all except `base_damage` |
| MEDIUM | 1 | `base_damage` (semantic distance between a turn-based attack action and an emitter) |
| LOW | 0 | — |

Coverage findings: one **MEDIUM** record-level defect (`UNSUPPORTED_CONSTRUCT_REPORTING_INCOMPLETE`),
two MEDIUM analysis-level linkage gaps (health_bar × 1, openable_door × 1) plus two already-known gaps.

---

## K. Unresolved Issues

| # | Issue | Severity | Owner | Blocking for integration? |
|---|---|---|---|---|
| K1 | `expand_to` and `title_label` are un-captured and unreported | MEDIUM | Parser / Coverage Hardening | Yes — coverage cannot be trusted at declaration level |
| K2 | `unsupported_constructs` points at captured declarations (legacy `setget`) rather than the real omissions | MEDIUM | Parser / Coverage Hardening | Yes — misleading diagnostics |
| K3 | `unsupported_constructs[].line` mixes record and commit line space; formal 1.71 records have no field at all | LOW | Schema / Provenance | No, but blocks automated cross-checks |
| K4 | No semantic-link mechanism: `current_health`/`maximum`/`is_locked`/`get_value` cannot enter formal DIRECT even when semantics are confirmed | MEDIUM | Linkage policy | Yes — the only semantic DIRECT cannot be represented |
| K5 | 4 analyses still have no linkage at all (`ext-43748f09c01294f9`, `ext-5a8d53c7f530e4af`, `ext-80c1104f5262a6ee`, `ext-ab693f3d6ef9439c`), of which two are functionally relevant (door unlock, open-rts HealthBar) | MEDIUM | Linkage coverage | Yes — evidence exists but is never evaluated |
| K6 | Seed Policy has no explicit formal-analysis-only rule and no coverage gate | LOW | Seed policy | No (implicit digest keying holds) |
| K7 | `get_value`'s caller graph is not statically verified (expression strings executed at runtime) | LOW | Parser capability | No — item classified supporting, not DIRECT |
| K8 | Upstream `heal()` clamps with `max(health, max_health)`, which always yields a full heal | INFO | Source behaviour note | No — recorded as a seed limitation, not a defect here |
| K9 | Formal blackboard linkage keeps a class_name evidence item with `line_reference = null` (candidate `location_integrity=INCOMPLETE`) | LOW | Linkage provenance | No |

---

## L. Data Integrity and Non-Mutation Verification

**Baseline:** `.ai/tmp/phase176d_baseline.json`, captured before any Batch D file was written
(gitignored). Scope: **423 files** in 9 groups.

| Group | Files | Changed | Missing | Added | Status |
|---|---:|---:|---:|---:|---|
| Formal External Analysis | 34 | 0 | 0 | 0 | PASS |
| Formal Feature Linkage | 150 | 0 | 0 | 0 | PASS |
| Candidates (+`WORKSPACE.json`) | 3 | 0 | 0 | 0 | PASS |
| Batch B workspace (`parser_1.76`) | 162 | 0 | 0 | 0 | PASS |
| Phase 1.75 workspace | 29 | 0 | 0 | 0 | PASS |
| Batch C workspace (`evidence_impact/phase_1.76`) | 8 | 0 | 0 | 0 | PASS |
| Batch A inventory | 1 | 0 | 0 | 0 | PASS |
| Parser / adapter (`gd_parse.py`, `external_code_understanding.py`) | 2 | 0 | 0 | 0 | PASS |
| Feature layer (`feature_index.json`, `feature_graph.json`, Seed Policy, 31 `feature.yaml`) | 34 | 0 | 0 | 0 | PASS |
| **Total** | **423** | **0** | **0** | **0** | **PASS** |

**Read-only verification:** `python .ai/tools/external_code/manual_evidence_review_176.py validate`
→ exit 0, `"result": "PASS"`, `problems: []`, `integrity.status: PASS`, 423 files compared, 0
changed / 0 missing / 0 added.

**New files created by Batch D (allowed):**

| Path | Purpose |
|---|---|
| `.ai/context/PHASE_1_76_D_MANUAL_EVIDENCE_REVIEW.md` | this report |
| `.ai/tools/external_code/manual_evidence_review_176.py` | read-only review tool (`build` / `validate`) |
| `.ai/learning/external_code/evidence_review/phase_1.76/manifest.json` | run manifest, counts, vocabularies |
| `.ai/learning/external_code/evidence_review/phase_1.76/review_items.json` | 13 traceable review items |
| `.ai/learning/external_code/evidence_review/phase_1.76/source_verification.json` | per-item digest / line verification |
| `.ai/learning/external_code/evidence_review/phase_1.76/partial_coverage_review.json` | 26-declaration tables |
| `.ai/learning/external_code/evidence_review/phase_1.76/candidate_review.json` | 2 candidates / 3 seeds |
| `.ai/learning/external_code/evidence_review/phase_1.76/review_validation.json` | checks + integrity snapshot |
| `.ai/tmp/phase176d_baseline.json` | integrity baseline (gitignored, not an artefact) |

**Prohibited actions — all confirmed not performed:** formal analysis write, linkage write, candidate
write, feature metadata/index/graph write, seed policy write, parser/adapter/schema write, Batch A/B/C
workspace write, parser rerun, reanalysis rebuild, symbol-diff rebuild, linkage rebuild/refresh,
candidate rebuild/promotion/qualification, Review Queue creation, new formal seed, seed-eligibility
change, automatic DIRECT linkage creation, Batch E execution, Git add/commit/push/reset/checkout/
clean/stash, file deletion.

**Review Queue check:** no `*review_queue*` file exists anywhere in the workspace
(`review_validation.json` → `review_queue.created = false`).

---

## M. Git State

| Item | Value |
|---|---|
| Branch | `master` |
| HEAD | `d64b1cd5b576a44dcfafd7becbb2d2a7f1fd6a84` |
| Staged | 0 |
| Modified (tracked) | 30 |
| Deleted | 0 |
| Untracked (collapsed) | 141 before this report → **142** after it |
| Untracked (`-uall`) | 590 (582 before Batch D + 8 new files: report, tool, 6 artefacts) |
| Git write operations | **None** |

`.ai/learning/external_code/` and `.ai/tools/external_code/` contain **no tracked files**
(`git ls-files` = 0), so the new tool and the 6 new artefacts stay inside already-untracked
directories and do not add collapsed entries; only the report under the tracked `.ai/context/`
directory adds one. The 30 modified tracked files are the pre-existing state carried from earlier
phases and were not touched by Batch D.

---

## N. Final Verdict

```text
PHASE 1.76 — BATCH D
VERDICT: PASS_WITH_LIMITATIONS
```

**Why not `PASS`:** the review body is complete and every conclusion is source-verified, but three
things remain open: (1) coverage reporting is provably incomplete (`UNSUPPORTED_CONSTRUCT_REPORTING_INCOMPLETE`,
2 unflagged missing declarations); (2) the only semantic DIRECT evidence (`current_health`) cannot be
represented by the current identifier-only linkage layer; (3) four analyses still have no linkage at
all, two of which hold real feature behaviour. None of these invalidates the review, and none is a data
integrity failure.

**Why not `BLOCKED`:** all inputs were present, all 13 commits and digests verified, all P0/P1 reviews
executed at source level; no commit identity was unverifiable.

**Why not `FAIL`:** 423/423 in-scope files unchanged, no unauthorized write, no Review Queue, no
formal mutation.

---

## O. Next-Stage Readiness

```text
BATCH_E_READINESS: READY_FOR_BATCH_E_WITH_RESTRICTIONS
```

Ready means **planning may be authorized only**; it does not authorize execution. Any Batch E plan must
respect these restrictions:

1. No formal Analysis, Linkage, Candidate, Seed Policy or Feature layer write.
2. Formal evidence integration may only be *planned*, never performed.
3. `current_health`/`maximum` may be planned as a semantic-link pilot; they may not be written as
   DIRECT until a semantic-link rule is designed and approved.
4. `expand_to`/`title_label` may be planned only as Parser/Coverage Hardening items — not as evidence.
5. The 4 linkage-gap analyses may be planned for linkage coverage work, not rebuilt.
6. `target_value` planning must keep `EVIDENCE_INTERPRETATION_CORRECTED_NO_CLASSIFICATION_CHANGE`.
7. No Review Queue creation.
8. Batch E remains **NOT AUTHORIZED** until explicitly granted.

---

## P. Recommended Follow-up

**Genuinely valuable functional evidence (plan for formal review, no writes now)**

1. `get_value` — closes the blackboard read path; supports the existing DIRECT seed. Highest
   integration value *within* an existing claim.
2. `health` and `max_hp` — convert the two health seeds' architecture and clamp claims from
   "inferred" to "shown", and remove the "1 of 5 @export vars" limitation text.
3. `is_locked` — the strongest door behaviour found; supports `POTENTIAL_RELEVANCE` but cannot become
   DIRECT under identifier matching.
4. `current_health` + `maximum` — the only semantic DIRECT finding; needs a semantic-link policy
   before it can ever be written.

**Merely parser-level discoveries (no evidence action)**

5. `key`, `value` — expression strings in a consumer node.
6. `size` — generic texture sizing.
7. `base_damage` — damage number in a different damage protocol.
8. `board` — Kanban model, explicit negative.
9. `door` — node reference; the *analysis* matters (linkage gap), the *symbol* does not.
10. `target_value` — representation correction; the AMBIGUOUS door item should be re-worded, not
    reclassified.

**Must be fixed before formal evidence integration**

11. Parser/Coverage: detect `export(X) var`, `onready var`, legacy `setget`, enums; emit a diagnostic
    for every missing declaration; stop deriving `COMPLETE` from "parse succeeded".
12. Provenance: normalise `unsupported_constructs[].line` to a declared line space; add the field to
    formal records.
13. Linkage policy: decide whether a semantic (non-identifier) link tier is allowed, and if so how it
    is recorded and reviewed; otherwise `current_health` can never be consumed.
14. Linkage coverage: evaluate the 4 unlinked analyses, at minimum `door_unlock_interaction.gd` and
    `HealthBar.gd`.
15. Seed Policy: make the formal-analysis-only rule and a coverage-status gate explicit.

**Explicit answer to the batch question**

> **Which Parser 1.76 findings are genuinely valuable functional evidence, which are merely
> parser-level discoveries, and what must be fixed before formal evidence integration?**
>
> Genuinely valuable functional evidence: `get_value` (blackboard read path, supporting an existing
> DIRECT seed), `health` and `max_hp` (health state cell and clamp bound behind the two health seeds),
> `is_locked` (real lock/unlock behaviour for doors), and `current_health` + `maximum` (a Lifebar
> provably bound to Health — the only semantic DIRECT finding). Merely parser-level discoveries:
> `key`, `value`, `size`, `base_damage`, `door`, `board`, and `target_value` (a property
> representation correction that weakens, rather than supports, the AMBIGUOUS door link). Before
> formal evidence integration, fix coverage-reporting completeness (`expand_to`, `title_label`
> unflagged), the mixed line space / missing `unsupported_constructs` field, the absence of any
> semantic-link rule, the four unlinked analyses, and the implicit-only seed policy gates.

**Batch D stops here.** No Parser Hardening, no Coverage Schema change, no Seed Policy change, no
formal Analysis/Linkage update, no Candidate promotion, no Review Queue, no Batch E, no Git write.
Awaiting human acceptance.

---

## Final Output Block

```text
PHASE 1.76 — BATCH D
VERDICT: PASS_WITH_LIMITATIONS

POTENTIAL IMPACT REVIEW:
13 / 13

P0 REVIEW:
6 / 6

P1 REVIEW:
7 / 7

PARTIAL COVERAGE:
3 / 3 reviewed

UNSUPPORTED REPORTING:
INCOMPLETE

TARGET_VALUE:
EVIDENCE_INTERPRETATION_CORRECTED_NO_CLASSIFICATION_CHANGE (NOT_RELEVANT as door evidence; tweened life-bar property confirmed in source)

CANDIDATES:
2 / 2 reviewed

SEEDS:
3 reviewed

SOURCE PROVENANCE:
PASS

DATA INTEGRITY:
PASS

FORMAL DATA MUTATION:
0

REVIEW QUEUE:
NOT_CREATED

BATCH E:
NOT_EXECUTED

BATCH_E_READINESS:
READY_FOR_BATCH_E_WITH_RESTRICTIONS
```
