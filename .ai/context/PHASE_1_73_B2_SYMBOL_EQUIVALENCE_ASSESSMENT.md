# Phase 1.73 — Batch B.2
# Stage F — health_bar Symbol Equivalence Assessment

Scope: decide whether a manual Symbol Equivalence declaration mechanism is worth building for
`health_bar`. **No mechanism is implemented, no declaration is created, no threshold is
changed, no `POTENTIAL_RELEVANCE` is promoted.**

## F.1 The two symbol sets, as stored

Internal `Features/health_bar` (projection, `PARTIAL`, 14 EXTRACTED symbols):

| Symbol | Kind | Note |
|---|---|---|
| `HealthBar` | `class_name` | |
| `get_ratio` | function | **computed** ratio from `_health` and the target's health |
| `_on_health_changed` / `_on_died` | function | signal handlers |
| `health_path` | export | `NodePath` to the health component |
| `bar_size`, `back_color`, `fill_color` | export | rendering parameters |
| `_health` | variable | cached reference/value |

External candidates actually captured by the parser:

| Repository / file | Symbol | Kind | Stored line |
|---|---|---|---|
| `gdquest-demos/godot-open-rpg` `ui_life_bar.gd` | `fill_rate` | export | 12 |
| same | `target_value` | variable | 18 |
| `nezvers/Godot-GameTemplate` `HealthPanel.gd` | `health_resource` | export | 7 |
| same | `progress_shader`, `label` | export | 11, 9 |
| same | `value_front`, `value_middle` | variable | 18, 19 |
| `nezvers/…/HealthResource.gd` | `hp`, `max_hp` | export | **not captured** (lines 11–12 of the file) |
| `lampe-games/godot-open-rts` `HealthBar.gd` | — | — | **no symbols at all** (private-only surface) |

Note the two structural facts that shape the whole assessment:

1. `hp`/`max_hp` — the only genuinely health-valued external names in this set — are **invisible
   to the parser** in `HealthResource.gd` (1 of 5 exports kept: `is_dead`). They appear in no
   analysis record, so no equivalence could be applied to them without re-analysis.
2. `godot-open-rts/HealthBar.gd` has an entirely `_`-prefixed member surface, which the
   classifier excludes as non-distinctive; that file cannot participate in any matching scheme.

## F.2 Per-symbol semantic review

| External symbol | Type / source | Meaning | Read/write | Range | Current health? | Max health? | UI use? | Relation to internal | Equivalence class |
|---|---|---|---|---|---|---|---|---|---|
| `hp` (HealthResource) | `@export float`, default 5 | current hit points | read + written by `add_hp`, `reset_resource`, `prepare_load` | `[0, max_hp]`, clamped | **yes** | no | no | `_health` holds a reference; `get_ratio()` divides two such numbers | `SEMANTIC_EQUIVALENCE` with the *concept* of current health; **not** with `get_ratio` |
| `max_hp` | `@export float`, default 5 | ceiling | written by `set_max_hp` | `> 0` | no | **yes** | no | same | `SEMANTIC_EQUIVALENCE` with the concept of maximum health |
| `target_value` (ui_life_bar) | untyped `var` | tween target for the fill animation | written by `setup`/`_update` | 0…1 (fill fraction) | no | no | **yes** | this is what `get_ratio()` would feed; it is a *derived display value* | `CONCEPTUAL_RELATEDNESS` only |
| `fill_rate` | `@export float` | animation speed of the fill | read | seconds/ratio | no | no | yes | nothing internal | `CONCEPTUAL_RELATEDNESS` only |
| `health_resource` (HealthPanel) | `@export` reference | the health component the panel watches | read | — | no | no | yes | analogous to the Feature's **`health_path`** (a reference to health) | closest structural analogue found — still `SEMANTIC_EQUIVALENCE` at best |
| `progress_shader`, `label`, `value_front/middle` | exports/vars | rendering plumbing | — | — | no | no | yes | `bar_size`/`fill_color`/`_draw` plumbing | `CONCEPTUAL_RELATEDNESS` |

**Answers to the specific warnings in the brief:**

* `hp` ≠ `health`: right — but here `hp` *is* the current-health value while the internal
  `_current_health`-equivalent is not an exported symbol at all. Equivalence would have to be
  declared against a **concept**, not a symbol.
* `max_hp` ≠ `max_health`: same situation.
* `target_value` is **not** health: it is a normalised display fraction. Equating it with health
  would be a semantic error.
* `get_ratio()` is a **computation**, not a field: no external field can be "the same symbol" as
  it. At most, an external *pair* (`hp`, `max_hp`) supplies its inputs.

Consequently, **no `EXACT_SYMBOL_EQUIVALENCE` exists anywhere in this Feature**, and the honest
maximum is `SEMANTIC_EQUIVALENCE` between an external field and an internal *concept*.

## F.3 Is a mechanism worth building?

**Yes — but only as a narrow, reviewed, non-promoting declaration.** Reasons:

For:
* `health_bar` will never acquire a direct seed by identifier matching: its vocabulary
  (`get_ratio`, `health_path`, `bar_size`) is rendering-centric while external bar code is
  state-centric (`hp`, `max_hp`, `target_value`). Every other route to a health-bar seed has been
  exhausted in B.1.
* Two real, structural analogues already exist and are being discarded purely on naming
  (`health_resource` ↔ `health_path`; `hp`+`max_hp` ↔ `get_ratio`'s inputs). Recording that as a
  reviewed statement is more honest than leaving it as an `AMBIGUOUS` artefact of the token
  “health”.

Against / conditions:
* A free-form synonym table would be a licence to manufacture links. It must not be able to
  produce `DIRECT_EVIDENCE`, and `CONCEPTUAL_RELATEDNESS` must never be seed-grade.
* It cannot fix the two structural blockers: the parser cannot see `hp`/`max_hp` in
  `HealthResource.gd`, and `godot-open-rts/HealthBar.gd` exposes nothing matchable. Equivalence
  is not a substitute for parser work or corpus coverage.

## F.4 Proposed minimal declaration schema (design only, not implemented)

One declaration per (external symbol × internal concept), versioned, human-signed:

| Field | Purpose |
|---|---|
| `declaration_id`, `declaration_version` | stable identity, immutable revisions |
| `external_repository`, `external_commit_sha` (40), `external_source_path`, `external_symbol` | pins the external side to a commit, like an analysis record |
| `external_symbol_kind` (function / export / variable / signal) | prevents property↔function confusions like B.3 |
| `feature_id`, `internal_symbol_or_concept` | the internal side; a **concept** string is allowed when no symbol exists |
| `equivalence_type` | `EXACT_SYMBOL_EQUIVALENCE` / `SEMANTIC_EQUIVALENCE` / `CONCEPTUAL_RELATEDNESS` |
| `semantic_explanation` | required free text: what the value means, its range and direction |
| `direction` (read / write / both), `value_range`, `units` | the properties that make a substitution safe |
| `evidence_reference` | linkage id and/or analysis item this declaration is anchored to |
| `reviewer`, `review_status` (`PROPOSED` / `APPROVED` / `REJECTED`), `reviewed_at` | human gate |
| `limitations` | what the declaration does *not* establish |

Rules that must hold if it is ever built:

1. `CONCEPTUAL_RELATEDNESS` **must not** become `DIRECT_EVIDENCE`, a seed, or a
   `POTENTIAL_RELEVANCE` upgrade. It is documentation.
2. `SEMANTIC_EQUIVALENCE` may at most justify a **`CONDITIONAL` seed with
   `qualification_reason = MANUAL_SEMANTIC_EQUIVALENCE`**, and only together with an independent
   structural fact from the same file (e.g. the file connects a health-change signal to a UI
   node and computes a ratio), never on the declaration alone.
3. `EXACT_SYMBOL_EQUIVALENCE` requires identical symbol kind and identical value semantics —
   none qualifies today.
4. Declarations never edit linkage records, never alter thresholds, never touch Feature metadata.
5. Declarations expire when the external commit or the Feature projection digest changes.

## F.5 Verdict

**A manual Symbol Equivalence mechanism has real but limited value, and is not the next step for
`health_bar`.** The two `hp`/`max_hp` names that would make it worthwhile are not even visible to
the current parser, and the third candidate file has no matchable symbols at all. Recommended
order of work: (1) fix export/variable capture in the parser, (2) re-analyse the bar files,
(3) only then, if `health_bar` still has no direct seed, build the declaration mechanism with the
schema and rules above. `health_bar` therefore has **no seed** in this stage.
