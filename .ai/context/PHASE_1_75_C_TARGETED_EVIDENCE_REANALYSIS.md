# Phase 1.75 — Batch C
# Targeted Evidence Reanalysis

Workspace: `.ai/learning/external_code/reanalysis/parser_1.75/`
(`WORKSPACE.json`, `analysis/`, `diff/`, `linkage_evaluation/`)
Tool: `.ai/tools/external_code/reanalysis_175.py` (writes only inside that workspace)

**Nothing official was rewritten.** A digest snapshot of all 188 official
artefacts (34 analysis + 150 linkage + 2 candidates + workspace manifest +
index) was taken before the run and compared after:
`official unchanged: True, 188 files, 0 changed, 0 extra, 0 removed`.

---

## A. Reanalysis Scope

| Record | Source | Original status | Reanalysis id |
|---|---|---|---|
| `ext-73c80a3db6d71e48` | `nezvers/Godot-GameTemplate` `addons/top_down/scripts/damage/HealthResource.gd` | `analysis_complete` | `ext-8759bb47cb020625` |
| `ext-ab693f3d6ef9439c` | `lampe-games/godot-open-rts` `source/match/units/traits/HealthBar.gd` | `analysis_partial` | `ext-322df918a5ebee02` |
| `ext-1d204b35464cf388` | `gdquest-demos/godot-make-pro-2d-games` `actors/health/Stats.gd` | `analysis_partial` | `ext-0ee947aef4c9aeca` |
| `ext-23949c1378c49203` | `bitbrain/beehave` `addons/beehave/blackboard.gd` | `analysis_partial` | `ext-d0a93201b6f352df` |

Only these four were written. An additional **read-only impact measurement**
(no files written) over all 34 stored records shows the blast radius of the
parser fix: 21 of 34 records would gain symbols, 6 would move
`analysis_partial → analysis_complete` (all six only because `@tool`/`@icon`/
`@rpc` annotations are now interpreted instead of being counted as syntax
limitations). Those 30 records were deliberately **not** reanalysed in this
phase; see Limitations.

---

## B. Source Provenance Verification

| Check | Result |
|---|---|
| reference copy digest == recorded `input_digest` | 4/4 ✔ |
| pinned source file digest == recorded `source_digest` | 4/4 ✔ |
| `source_digest` unchanged in the new record | 4/4 ✔ |
| repo / source_path / commit_sha / commit_sha_full / source_url unchanged | 4/4 ✔ |
| license / license_status / license_text_present / license_source unchanged | 4/4 ✔ |
| provenance_status / file_type / input_digest unchanged | 4/4 ✔ |
| stop-on-mismatch triggered | 0 times |

A stop would have aborted the file. No commit was mixed, no source file was
substituted, no offset was applied to make a line match.

---

## C. Parser Version Comparison

| | old | new |
|---|---|---|
| `parser_name` | `gd_parse` | `gd_parse` |
| `parser_version` | `1.71` | `1.75` |
| `schema_version` | 1 | 1 (additive keys only) |
| coverage fields | absent | `parse_execution_status`, `syntax_coverage_status`, `analysis_completeness`, `unsupported_constructs`, `unrecognized_declarations`, `source_coordinates` |

`analysis_id` includes the parser version, so each reanalysis has a new id and
the original id is retained in every diff file and in `WORKSPACE.json`.

---

## D. HealthResource Diff

`symbols_removed = 0`. Added 4 exports:

| Symbol | kind | type | initialiser | annotation | record line | commit line |
|---|---|---|---|---:|---:|---:|
| `hp` | VARIABLE | `float` | `5` | `@export` | 14 | 11 |
| `max_hp` | VARIABLE | `float` | `5` | `@export` | 15 | 12 |
| `reset_hp` | VARIABLE | `float` | `5` | `@export` | 17 | 14 |
| `reset_max_hp` | VARIABLE | `float` | `5` | `@export` | 18 | 15 |

`is_dead` keeps its identity and is now documented as
`declaration_kind=VARIABLE`, `is_exported=True`, `initializer_kind=NONE`,
annotations `[export]` (record line 19 / commit line 16). It has no getter or
setter.

Answers:

* `hp` recognised — yes; `max_hp` — yes.
* declaration kind — exported `VARIABLE` (not a function, not a property block).
* export annotation preserved — yes, with its line.
* type preserved — yes, `float` verbatim, no inference.
* initialiser preserved — yes, `5`, `EXPLICIT`.
* location — record line 14/15 ↔ commit line 11/12; verified by reading the line.
* getter/setter — none in this file.
* relationship to the internal feature — conceptual only. `hp`/`max_hp` are
  state; the internal feature's `is_dead` is a **function**, the external one is a
  **property**. No symbol equivalence is asserted, and this reanalysis does not
  change the linkage classification (`DIRECT_EVIDENCE → DIRECT_EVIDENCE`).

Coverage: `COMPLETE` / `FULL`; `analysis_complete` (now a truthful label: 5 of 5
exports, 6 of 6 functions, 6 of 6 signals).

---

## E. HealthBar Diff

`symbols_removed = 0`. Added 5 declarations (4 variables + 1 property):

| Symbol | kind | value | annotation | accessors | record line |
|---|---|---|---|---:|---:|---:|
| `size` | PROPERTY | `Vector2(200, 20)` | `@export` | `set` (line 10) | 9 |
| `_bar_value_initialized` | VARIABLE | `false` | — | — | 15 |
| `_unit` | VARIABLE | `get_parent()` | `@onready` | — | 17 |
| `_actual_bar` | VARIABLE | `find_child("ActualBar")` | `@onready` | — | 18 |
| `_visibility_timer` | VARIABLE | `find_child("Timer")` | `@onready` | — | 19 |

`hp`, `max_hp`, `target_value`, `get_ratio()`, `health_path` do **not** exist in
this file. The symbol surface is: a UI `size` with a clamping setter, three
`@onready` node handles, one initialisation flag, one duration constant, and
seven `_`-prefixed private methods. The stored evidence for a health-bar feature
(`hp`/`max_hp` reading, normalisation, update mechanism) is not in this file, and
this reanalysis did not invent it.

Data-flow questions answered from source: the value is recalculated in
`_recalulate_bar_value` from a `unit` node found via `get_parent()`; it is
normalised for display through the `size` setter; the update path is
`_on_hp_changed` connected to a unit signal; none of this binds a Health
Resource or exports `hp`/`max_hp`.

Classification consequence: the record remains **not evaluable** for linkage —
linkage still reports `NOT_EVALUABLE`, reason *"no distinctive parseable symbols
(analysis_status=analysis_partial, parse_status=parsed)"* (its `analysis_partial`
comes from the unresolved "no class_name" question, not from syntax).
`health_bar` therefore still has **no qualifying seed**. Only conceptual
relevance can be claimed; if a human wants to pursue it, the marker is
`REQUIRES_MANUAL_EVIDENCE_REVIEW`, never `QUALIFIED_DIRECT`.

---

## F. Stats Diff

`symbols_removed = 0`; functions and signals unchanged; `take_damage`, `heal`,
`health_changed` keep identical names, parameters, return types and line numbers
(no semantic drift). Added:

| Symbol | kind | value | record line |
|---|---|---|---:|
| `modifiers` | VARIABLE | `{}` | 10 |
| `health` | VARIABLE | `0` | 12 |

`max_health` uses legacy 3.x syntax (`export(int) var max_health = 9 setget
set_max_health`) and is **reported, not captured**:
`unsupported_constructs = [{code: LEGACY_SETGET_NOT_INTERPRETED, line: 13}]`.
`parse_status` therefore moves `parsed → partial` — a deliberate, honest
downgrade rather than a silent success. `analysis_status` stays
`analysis_partial`.

---

## G. Blackboard Diff

`symbols_removed = 0`. Added 3 declarations:

| Symbol | kind | type | value | accessors | annotation | record line |
|---|---|---|---|---|---:|---:|---|
| `get_value` | FUNCTION | — | — | — | — | 37 (multi-line signature, was lost) |
| `blackboard` | PROPERTY | `Dictionary` | `{}` | `set` (line 12) | `@export` | 11 |
| `_data` | VARIABLE | `Dictionary` | `{}` | — | — | 16 |

`Blackboard`, `keys`, `set_value`, `has_value`, `erase_value` unchanged.
`get_value` is restored as a top-level function with `start_line 37`, not as a
property — the property/function boundary is preserved. `@icon` is now recorded
as an interpreted annotation, so `analysis_status` moves
`analysis_partial → analysis_complete` with `COMPLETE`/`FULL` coverage.

**`independence = NOT_INDEPENDENT` is unchanged.** Parser output never carries
an independence verdict, and the candidate's evidence reference was not rewritten.

---

## H. Feature Linkage Re-evaluation

Method: the four reanalysis records were written to the workspace, then
`feature_linkage.build_linkages()` was run for them with the unchanged 5 pilot
features, projections, features and graph, into a **scratch directory**
(`tempfile`). Official records were only read. Every pair is written to
`linkage_evaluation/` with `review_status = REVIEW_ONLY_NOT_WRITTEN`.

Result: **20 pairs, 15 built, 5 not evaluable, 0 reclassified.**

| Source | health | health_bar | attack_emitter | blackboard | openable_door |
|---|---|---|---|---|---|
| HealthResource.gd | DIRECT → DIRECT | POTENTIAL → POTENTIAL | INDIRECT → INDIRECT | NO_SUPPORTED → NO_SUPPORTED | NO_SUPPORTED → NO_SUPPORTED |
| Stats.gd | DIRECT → DIRECT | POTENTIAL → POTENTIAL | POTENTIAL → POTENTIAL | NO_SUPPORTED → NO_SUPPORTED | NO_SUPPORTED → NO_SUPPORTED |
| blackboard.gd | NO_SUPPORTED → NO_SUPPORTED | NO_SUPPORTED → NO_SUPPORTED | NO_SUPPORTED → NO_SUPPORTED | **DIRECT → DIRECT** | NO_SUPPORTED → NO_SUPPORTED |
| HealthBar.gd | NOT_EVALUABLE | NOT_EVALUABLE | NOT_EVALUABLE | NOT_EVALUABLE | NOT_EVALUABLE |

Notes that follow directly from this table:

* The four new `HealthResource` exports did **not** upgrade any pair. Adding
  state symbols changed no rule outcome, so no human review is required to
  "undo" an automatic promotion — nothing was promoted.
* `attack_emitter` from `HealthResource.gd` stays `INDIRECT_EVIDENCE`; the
  graph-derived relation on `ext-fffa637657ffede1` is untouched and nothing was
  converted to DIRECT.
* `blackboard.gd`'s DIRECT for the blackboard feature is stable across parsers,
  and `get_value` being restored did not change it.
* `NO_SUPPORTED_LINK` remains "no supported link", never "missing evidence".
* No classification change was written to `feature_links/`; the official 150
  records are byte-identical before and after (digest snapshot).

---

## I. Candidate Impact Assessment

| Candidate | Feature | Status | Refs | Refs touched | Verdict |
|---|---|---|---|---:|---|
| `cand-08fdc0b10a112ecf` | health | NEEDS_REVIEW | 2 | 2 | new symbols in referenced sources (`hp`, `max_hp`, `reset_hp`, `reset_max_hp`, `health`, `modifiers`) — **REQUIRES_MANUAL_EVIDENCE_REVIEW** |
| `cand-7f52cb8f583124db` | blackboard | NEEDS_REVIEW | 1 | 1 | new symbols in referenced source (`get_value`, `blackboard`, `_data`) — **REQUIRES_MANUAL_EVIDENCE_REVIEW** |

* `candidate_mutated: False` for both. Candidate id, status, content digest,
  policy version, `evidence_refs`, `excluded_evidence` and `WORKSPACE.json` were
  not written by this phase (digest snapshot proves it).
* Neither candidate's *classification basis* changed: the health candidate still
  rests on `DIRECT_EVIDENCE`/`QUALIFIED_DIRECT` and
  `QUALIFIED_DIRECT_WITH_LIMITATIONS`, and `re-satisfiability` was not
  re-derived. The new symbols are **additional review material only**: `hp`/
  `max_hp` now exist as parsed declarations, which is exactly the kind of fact a
  human reviewer may want to re-read when revisiting the
  "`is_dead` property vs function" limitation. Marking it
  `REQUIRES_MANUAL_EVIDENCE_REVIEW` is the maximum this phase may say.
* `health_bar` still has **no** candidate and **no** qualified seed. New parsed
  symbols there were insufficient for the linkage policy to even evaluate the
  record; the maximum claim remains conceptual.
* `attack_emitter` retains `GRAPH_DERIVED_RELATION` / `INDIRECT_EVIDENCE`; the
  parser fix did not and cannot change evidence kind.

---

## J. Evidence Qualification Restrictions Observed

| Boundary | Status |
|---|---|
| parser emits `QUALIFIED_DIRECT` / `VERIFIED` / `ADMITTED` | never — parser emits declarations, annotations, locations, coverage only |
| same name ⇒ same concept | not applied: `is_dead` property vs `is_dead()` function kept apart; `hp`/`max_hp` vs `target_value`/`get_ratio()` not equated |
| independence recomputed | no: blackboard stays `NOT_INDEPENDENT`, no parser output touches it |
| graph-derived upgraded | no: `attack_emitter` unchanged |
| candidate auto-updated | no: both drafts untouched, review markers only |
| official linkage rewritten | no: 150 records digest-identical, 0 reclassifications |
| official analysis overwritten | no: 34 records digest-identical; new records live in the reanalysis workspace |

---

## K. Limitations

1. Only the 4 mandated records were reanalysed. A read-only measurement shows 21
   of 34 records would gain symbols and 6 would change `analysis_status` if
   reanalysed; those 30 remain on parser 1.71 data.
2. Linkage re-evaluation was limited to the 5 pilot features and the existing
   projections; it is not a rebuild of the corpus.
3. Lines are references-copy coordinates (commit line + 3 header lines),
   consistent with Phase 1.73/1.74; the offset is verified, not fixed globally.
4. Still-unparsed grammar: `enum` members, inner classes, legacy 3.x
   `export(...) var ... setget`, lambda bodies. `Stats.gd`'s `max_health` is
   reported as unsupported rather than captured.
5. `HealthBar.gd`'s symbols remain non-distinctive for linkage; its
   `analysis_partial` stems from a missing `class_name` (unresolved question),
   not from parser gaps.
6. `size` is a property with a setter; no runtime behaviour was verified —
   the parser reports structure, not semantics.

---

## L. Final Readiness Decision

**Batch C complete — READY_FOR_FINAL_REPORT.**

* Provenance verified for all four sources; digests identical; no stops.
* Every added declaration checked against the real source line (0 problems over
  52 symbols across the four files).
* Diff recorded per file; no symbol disappeared; no type or line was fabricated.
* Linkage re-evaluation produced review-only output with
  **0 classification changes**.
* Candidate impact assessed with `REQUIRES_MANUAL_EVIDENCE_REVIEW` where new
  material exists; no candidate, policy, seed or official record was modified.
* `health_bar` still has no qualified seed.
