# Phase 1.73 — Batch B.2
# Stage B — DIRECT_EVIDENCE Quality Audit

Three records are classified `DIRECT_EVIDENCE`. Each was opened, its source file read at the
byte level, and its symbols checked against the Feature side.

Method for every record: (1) hash the mirror file and the reference copy, (2) read the source
file with line numbers, (3) read the analysis `symbols` block, (4) read the Feature projection
symbol list and the Feature source, (5) check the record's evidence items, digests and
`source_verification`, (6) look for parser blind spots.

Coordinate note used throughout: **`line_reference` indexes the reference copy**, which is the
commit file plus a 3-line header. Verified by hashing both copies of each file. A record line
`N` therefore means commit line `N-3`.

---

## B.1 `ext-1d204b35464cf388` → `health`
`lnk-d2d95d8162be1592` · `gdquest-demos/godot-make-pro-2d-games` @
`7290681309ffcd700c2c08a8e59a57bfbec14d5e` · `actors/health/Stats.gd`

### Checklist

| Question | Finding |
|---|---|
| Symbols exist in the source? | Yes, all three: `signal health_changed` (commit line 3, record 6), `func take_damage` (20 / 23), `func heal` (28 / 31) |
| Locatable file + line + declaration? | Yes — declaration lines, in reference coordinates (see note) |
| Semantically related to Health? | Yes: current HP field, damage subtraction with clamp, heal addition, change signal, depletion signal |
| Real implementation, not a declaration? | Yes — `health -= amount`, `health = max(0, health)`, `emit_signal("health_changed", health)`, `emit_signal("health_depleted")` when `health == 0` |
| Data flow / call relation? | Yes, inside the same file: `_ready` seeds `health = max_health`; both mutators write the field and emit; `set_max_health` clamps the ceiling |
| Complete commit SHA traceable? | Yes — full SHA in `external_analysis.source_commit` and `source_url`, digest `ef9f6781…` MATCHED against `sources/…/Stats.gd` |
| Feature projection supports it? | Partially — `projection_status=PARTIAL`; the three matched symbols are Feature `EXTRACTED` symbols (`take_damage:28`, `heal:38`, `signal health_changed:14`) |
| Parser-induced misjudgement risk? | Present but bounded: `analysis_partial` because `Stats.gd` has no `class_name`; the parser also recorded `symbols.variables: []` and `exports: []`, so `health`, `max_health`, `modifiers` are invisible. The match does not depend on them |

### Divergences that limit how far this seed reaches

* `heal` clamps with `health = max(health, max_health)` — effectively a full heal; the Feature
  uses `min(_current_health + amount, max_health)`. The capability matches; the arithmetic
  differs, so this file is not a behavioural reference for clamping.
* External death is a `health_depleted` signal and `health == 0`; the Feature exposes
  `died` + `is_dead()`. Death semantics are **not** matched here (they are matched by B.3).
* `health_changed` carries `(new_health)` externally vs `(current, amount)` in the Feature.
* External `_ready` seeds health but has no invulnerability gate; the Feature has one.

### Verdict

**`QUALIFIED_DIRECT`** — real, self-contained health implementation; three exact identifiers on
both sides; source, commit and digest verified.
Seed limitations to carry: reference-coordinate lines; non-matching heal arithmetic; no death
signal match; `analysis_partial` / `projection_status=PARTIAL`.

---

## B.2 `ext-23949c1378c49203` → `blackboard`
`lnk-7084dc8999c2182b` · `bitbrain/beehave` @
`fe589153fa780a3f88989578ceb5f539afffb7c2` · `addons/beehave/blackboard.gd`

### Checklist

| Question | Finding |
|---|---|
| Symbols exist? | Yes: `class_name Blackboard` (commit 2 / record 5), `keys` (21 / 24), `set_value` (27 / 30), `has_value` (42 / 45), `erase_value` (50 / 53) |
| Locatable? | Yes — five declarations, reference coordinates |
| Real blackboard store, not a name match? | Yes — multi-board storage: `_data: Dictionary` keyed by board name, each holding a `Dictionary` of keys; `set_value` creates a missing board then writes `_data[board][key]`; `get_value` reads with a default and only if `has_value` |
| Actual read/write logic? | Yes: write (`set_value`), read (`get_value`), existence (`has_value`, with a `!= null` test), removal (`erase_value` writes `null`), enumeration (`keys`) |
| Shared-context semantics? | Yes — `@export var blackboard` is duplicated on assignment and `_ready`, so each node holds an independent copy and shares data through the board rather than by reference |
| Just a `Dictionary` wrapper? | No. It manages named sub-boards, a default board constant, duplicate-on-assign semantics, and a null-as-absent convention; the Feature adds `get_blackboard`/`get_blackboard_names`, the external file adds a debug sanitiser |
| Consistent with the internal Feature's capability boundary? | Yes, and more than that: the Feature source header states it was abstracted from `bitbrain/beehave` (MIT) and keeps exactly this API |
| Name-similar-but-different-semantics risk? | Not the risk here. The opposite risk applies: this is the **acknowledged upstream** of the internal Feature, so the match cannot be treated as independent corroboration |

### Divergences

* Feature uses `duplicate(true)` (deep) in the setter; external uses `duplicate()` (shallow).
* Feature dropped the debug sanitiser; external keeps `get_debug_data` / `_sanitize_for_debug`.
* `analysis_partial` because `@icon(...)` is an uninterpreted annotation (record line 4 of the
  reference copy = `const DEFAULT`).

### Verdict

**`QUALIFIED_DIRECT`** — a real, working blackboard with five exact identifiers, complete
provenance and verified digest.
Mandatory attribute: **`independence = NOT_INDEPENDENT`** (derived from this repository). It
corroborates the capability, it does not demonstrate that an independent third party arrived at
the same design.

---

## B.3 `ext-73c80a3db6d71e48` → `health`
`lnk-6fff3ce176bd5813` · `nezvers/Godot-GameTemplate` @
`d5d8d15887423b3a8acf0502efb6271c600a80bc` ·
`addons/top_down/scripts/damage/HealthResource.gd`

### Checklist

| Question | Finding |
|---|---|
| `is_dead` exists? | Yes — commit line 16, record line 19 |
| Function, property or other? | **`@export var is_dead: bool` — an exported property**, not a function. The Feature side is `func is_dead() -> bool` (line 57). Same identifier, different symbol kind |
| Provably about health state? | Yes — set `true` inside `add_hp` when `hp == 0.0` (line 44), cleared by `reset_resource` (23), restored by `prepare_load` (30) |
| Real health numbers behind it? | Yes: `hp`/`max_hp` floats, `add_hp` clamps to `[0, max_hp]`, emits `damaged`/`hp_changed`/`dead`/`full` |
| Merge/dedupe with B.1? | **No.** Different repository, different architecture (a `Resource` carrying exported state vs a `Node` with signals), independent author. Keep as a second seed; it corroborates the capability across two unrelated projects |
| Independent implementation? | Yes — independent of this project and of `make-pro` |

### Limitations (why this is not a clean pass)

1. **Symbol-kind mismatch** — property vs function. The identifier coincides; the access shape
   does not.
2. **Single identifier** — one exact symbol out of 20 external symbols. The richest signals here
   (`hp`, `max_hp`, `damaged`, `dead`, `hp_changed`) match nothing in the Feature, because the
   Feature names them `_current_health`, `max_health`, `died`, `health_changed`.
3. **Parser under-capture behind an `analysis_complete` label** — of five `@export var`
   declarations the analysis kept only `is_dead`; `hp`, `max_hp`, `reset_hp`, `reset_max_hp` are
   absent from `symbols`, and `variables` is empty. The record's completeness claim covers the
   file as parsed, not the file as written.
4. **`projection_status=PARTIAL`** on the Feature side.
5. **No health-bar or attack link** — the record's other pairs (`health_bar` POTENTIAL,
   `attack_emitter` INDIRECT) do not inherit credibility from this match.

### Verdict

**`QUALIFIED_DIRECT_WITH_LIMITATIONS`** — the evidence is real and provenance-complete, but it
supports only a narrow claim: *this external resource tracks a death flag derived from clamped
HP*. It must not be used to claim full symbol coverage, an API-shape match, or anything about
health display.

---

## B.4 Summary

| Record | Feature | Verdict | Seed role |
|---|---|---|---|
| `lnk-d2d95d8162be1592` (`Stats.gd`) | health | `QUALIFIED_DIRECT` | full seed, with 4 behavioural caveats |
| `lnk-7084dc8999c2182b` (`blackboard.gd`) | blackboard | `QUALIFIED_DIRECT` | full seed, `NOT_INDEPENDENT` |
| `lnk-6fff3ce176bd5813` (`HealthResource.gd`) | health | `QUALIFIED_DIRECT_WITH_LIMITATIONS` | restricted seed (narrow claim only) |

No classification was changed and no record was edited: all three stand as `DIRECT_EVIDENCE`.
No `REJECTED_DIRECT` was warranted — none of the three rests on name similarity alone, and each
has a verified commit-pinned source with a real implementation.

**Cross-cutting finding for every seed:** `line_reference` values are reference-copy
coordinates (commit line − 3). A seed must therefore carry both the reference line and the
commit-pinned path, or its location cannot be re-checked against the immutable URL.
