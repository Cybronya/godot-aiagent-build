# Phase 1.75 — Batch A
# Parser Coverage Audit

Audit of `.ai/tools/learning/gd_parse.py` (314 lines, `PARSER_VERSION = "1.71"`), its adapter
`external_code_understanding.py`, and the analysis records it produced.

Baseline verified before the audit: `master` @ `d64b1cd5`, staged 0, modified 33, untracked 369;
34 analysis records, 150 linkage records, 2 candidates, 2 candidates FRESH, 150 linkage FRESH —
identical to the Phase 1.74 close.

---

## A. Parser Architecture

```
gd_parse.parse_text(path, text) → Script
    line-oriented regex scan, one pass, top-level only
    Script: class_name, extends, signals[], exports[], variables[], constants[], functions[]
    Function: name, params, returns, start_line, end_line, body[(line, text)]

external_code_understanding.analyze_external_code()
    gd_parse.parse_text → _symbols() → source_analysis.analyze_external_scripts([script])
    → analysis_status = complete | partial | failed | blocked_*
```

Properties that matter for this audit:

1. **Pure regex, single line, one pass.** Every declaration regex is anchored `^…$` against one
   stripped line. There is no tokenizer, no continuation handling, no brace/bracket balance.
2. **Top-level only.** Declarations inside a body are not parsed (`if width == 0` guard), which
   is correct for a declaration scanner but also means a member block opened by `:` (`get:` /
   `set(value):`) is invisible.
3. **Two offsets in play.** `parse_text` is fed the *references copy* text, so every
   `line`, `start_line`, `end_line` is a references-copy coordinate. `source_consistent` proves
   the copies agree after stripping a 3-line header, but the parser never converts coordinates.
4. **`analysis_status` is derived from limitations + unresolved questions**, not from a
   declaration-completeness check. `_syntax_limitations()` only looks at `@` prefixes that are
   not `@export`/`@onready`, `class ` lines and `lambda`.
5. **One parser, several consumers.** `external_code_understanding`, `source_analysis`,
   `feature_evidence` (projections), `dependencies` all import the same module — so any fix is
   shared by External Analysis *and* Feature-side Source Analysis, which is why the fix must be
   additive and regression-tested on both sides.

---

## B. Existing Syntax Coverage Matrix

Status is what the code actually does, measured by probe (`parse_text` on a minimal sample per
row). Not inferred from intent.

| # | Construct | Status | Evidence |
|---|---|---|---|
| 1 | `class_name` | **Supported** | dedicated field, not in `symbols` |
| 2 | `extends` | **Supported** | dedicated field |
| 3 | `signal` (with/without params) | **Supported** | `SIGNAL_RE` |
| 4 | `enum` | **Unsupported** | probe: `enum State { IDLE, RUN }` → nothing recorded |
| 5 | `const` (typed + inferred) | **Supported** | `const MAX: int = 5` / `const MAX := 5` both captured |
| 6 | `var` no initializer, `var x: T` | **Supported** | `VAR_RE` |
| 7 | `var x := v` (inferred) | **Supported** | `VAR_RE` (`:=` only) |
| 8 | `var x = v` / `var x: T = v` | **Unsupported** | probe M: `var _data: Dictionary = {}` → nothing |
| 9 | `var x = v` untyped | **Unsupported** | probe B: `var hp = 100` → nothing |
| 10 | `@export var x` (no initializer) | **Supported** | probe J: `@export var is_dead: bool` captured |
| 11 | `@export var x = v` | **Unsupported** | probe A/C: nothing — the root cause of the `hp`/`max_hp` loss |
| 12 | `@export var x: T := v` | **Supported** | probe I (this is why the bug looked intermittent) |
| 13 | `@export var x: Array[int] = []` | **Unsupported** | type + `=` both unsupported |
| 14 | `@export_range(...) var x` | **Unsupported** | probe K: annotation prefix not accepted |
| 15 | `@export_category` / `@export_group` | **Unsupported** | probe: declaration on the following line also lost |
| 16 | `@onready var x = $Node` | **Unsupported** | probe D: nothing (`=`), `@onready var x := …` would work |
| 17 | `static var` | **Unsupported** | probe L: nothing |
| 18 | `@static_unload` | **Unsupported** | annotation ignored, no association |
| 19 | `func` | **Supported** | `FUNC_RE` |
| 20 | `static func` | **Supported** | `FUNC_RE` has `(?:static\s+)?` |
| 21 | Multi-line function signature | **Unsupported / silently lost** | probe: `func get_value(\n…\n) -> Variant:` → no function; this is a **real** loss in `blackboard.gd` |
| 22 | `@rpc` before `func` | **Partial** | declaration survives, annotation dropped (probe: `sync` captured) |
| 23 | `@tool` / `@icon` | **Partial** | declaration survives, annotation only appears as a limitation string |
| 24 | Getter / setter blocks (`get:` / `set(value):`) | **Unsupported** | probe E/F/G: declaration *and* accessors lost; one-line `get: return x` also lost |
| 25 | Multi-line declaration (line continuation) | **Unsupported** | probe N: nothing |
| 26 | Nested / inner class | **Unsupported (reported)** | probe: not captured, but `_syntax_limitations` emits `inner_class_not_interpreted` |
| 27 | Typed variable | *see 6/7* | type is stored verbatim (`float`, `Dictionary`, `Array[String]`) or `""` |
| 28 | Untyped / inferred variable | *see 8/9* | untyped with `=` lost; `:=` captured |
| 29 | Signal connection (`.connect(`) | **Supported** | `connects()` |
| 30 | Property accessor as member | **Unsupported** | see 24 |

No row is marked supported without a probe or a real-file check.

---

## C. Known Bug Reproduction

Measured with the shipped parser (probe output, verbatim):

| Case | Source | Result |
|---|---|---|
| A | `@export var hp: float = 100.0` | **0 symbols** |
| B | `var hp = 100` | **0 symbols** |
| C | `@export var max_hp = 100` | **0 symbols** |
| D | `@onready var health_bar = $HealthBar` | **0 symbols** |
| E | `var hp: float = 100.0:` + `set(value):` | **0 symbols**, setter invisible |
| F | `var ratio: float:` + `get:` | **0 symbols**, getter invisible |
| G | getter + setter on one property | **0 symbols** |
| H | `func is_dead() -> bool:` | **1 function**, correct — function is *not* mistaken for a property |
| I | `@export var hp: float := 100.0` | 1 export (`float`, `100.0`) — works |
| J | `@export var is_dead: bool` | 1 export (`bool`, no value) — works |
| K | `@export_range(0,100) var hp: float = 100.0` | **0 symbols** |
| L | `static var instance` | **0 symbols** |
| M | `var _data: Dictionary = {}` | **0 symbols** |
| N | `@export var hp: float = \` + continuation | **0 symbols** |

### Root cause (exact)

```python
EXPORT_RE = ^@export\s+(?:var\s+)?(?P<name>\w+)\s*(?::\s*(?P<type>[\w\[\]]+))?\s*(?::=\s*(?P<value>.+))?$
VAR_RE    = ^(?:@onready\s+)?var\s+(?P<name>\w+)\s*(?::\s*(?P<type>[\w\[\]\.]+))?\s*(?::=\s*(?P<value>.+))?$
```

* Both accept **only `:=`** for an initializer, then require `$` (end of line). `= 5` therefore
  fails the optional group *and* fails `$` ⇒ no match at all. This single defect explains
  Cases A/B/C/D/M, `hp`/`max_hp`/`reset_hp`/`reset_max_hp`, `Stats.gd`'s `health`/`modifiers`,
  and three of the four missed declarations in `HealthBar.gd`.
* `@export` is matched as a literal prefix, so `@export_range`, `@export_category`,
  `@export_group`, `@export_enum`, `@export_flags` all fail (Case K and the `@export_category`
  probe).
* `static` is not in either regex (Case L).
* A trailing `:` (property block) is not in either regex, so property declarations are dropped
  before the accessor block can even be seen (Cases E/F/G).
* `FUNC_RE` requires the closing `): ` on the same line, so a multi-line signature is silently
  lost (probe; `blackboard.gd` `get_value`).

The audit did **not** find a case where a property was recorded as a function or vice versa —
Case H is correct. The risk is loss, not confusion — but loss is what produced the misleading
`analysis_complete`.

---

## D. Real Source Audit

Independent declaration scan (regex over the commit-pinned `sources/` copies) compared with the
stored analysis records.

### D.1 `HealthResource.gd` — `ext-73c80a3db6d71e48`, status `analysis_complete`, `parse_status=parsed`

| Actual declaration | Line | Captured? |
|---|---:|---|
| `class_name HealthResource` | 1 | ✔ (dedicated field) |
| `extends SaveableResource` | 2 | ✔ (dedicated field) |
| `signal damaged/dead/hp_changed/max_hp_changed/full/reset_update` | 4–9 | ✔ 6/6 |
| `@export var hp: float = 5` | 11 | **✘** |
| `@export var max_hp: float = 5` | 12 | **✘** |
| `@export var reset_hp: float = 5` | 14 | **✘** |
| `@export var reset_max_hp: float = 5` | 15 | **✘** |
| `@export var is_dead: bool` | 16 | ✔ (only export kept) |
| 6 functions | 18–52 | ✔ 6/6 |

Capture rate for declarations: **1 of 5 exports (20 %)**. No accessors. No `setget`.
`analysis_complete` is therefore factually wrong about source coverage — this is the defect that
blocked `health_bar` in Phase 1.73/1.74.

`is_dead` is a **property** (`@export var`, kind `export`) and the internal Feature's `is_dead` is
a **function**; the audit preserves that distinction and does not propose equivalence.

### D.2 `HealthBar.gd` (godot-open-rts) — `ext-ab693f3d6ef9439c`, status `analysis_partial`

| Actual | Line | Captured? |
|---|---:|---|
| `class_name` / `extends Node3D` | 2 | extends ✔ |
| `@export var size = Vector2(200, 20):` | 6 | **✘** (declaration + setter) |
| `set(value):` | 7 | **✘** |
| `var _bar_value_initialized = false` | 12 | **✘** |
| `@onready var _unit = get_parent()` | 14 | **✘** |
| `@onready var _actual_bar = find_child("ActualBar")` | 15 | **✘** |
| `@onready var _visibility_timer = find_child("Timer")` | 16 | **✘** |
| 7 functions | 22–65 | ✔ 7/7 |

Correctly `analysis_partial`, but for the wrong reason (it was flagged only because of `@tool`).
The symbol surface the Linkage classifier saw was functions only — all `_`-prefixed and therefore
non-distinctive — which is why this record produced no evaluable pairs in Phase 1.73. That
conclusion was **right by accident**; with Batch B it will have real symbols
(`size`, `_bar_value...`) and may become evaluable, which is a Batch C question, not a Batch A one.

### D.3 `Stats.gd` — `ext-1d204b35464cf388`, status `analysis_partial`, `parse_status=parsed`

| Actual | Line | Captured? |
|---|---:|---|
| `signal health_changed/damage_taken/health_depleted` | 3–5 | ✔ 3/3 |
| `var modifiers = {}` | 7 | **✘** |
| `var health = 0` | 9 | **✘** |
| `export(int) var max_health = 9 setget set_max_health` (legacy 3.x export) | 10 | **✘** (legacy syntax, out of scope) |
| 6 functions | 14–37 | ✔ 6/6 |

Functions — the only thing the DIRECT evidence rests on — are complete, so the Phase 1.73
`Stats.gd` DIRECT evidence is unaffected by the parse gaps. The missing state variables are a
coverage limitation, not an evidence defect.

### D.4 `blackboard.gd` — `ext-23949c1378c49203`, status `analysis_partial`, `parse_status=partial`

| Actual | Line | Captured? |
|---|---:|---|
| `@icon("icons/blackboard.svg")` | 1 | ✘ annotation |
| `class_name Blackboard extends Node` | 2 | ✔ |
| `const DEFAULT = "default"` | 4 | ✔ |
| `@export var blackboard: Dictionary = {}:` + `set(b):` | 8–11 | **✘** declaration + setter |
| `var _data: Dictionary = {}` | 13 | **✘** |
| `func _ready/keys/set_value/get_value/has_value/erase_value/…` | 16–60 | **6 of 7** — `get_value` **lost** (multi-line signature, lines 34–36) |

This is the most consequential finding outside the variable bug: a **public API function was
silently dropped** because its signature spans three lines. The five identifiers the Phase 1.74
candidate relies on (`Blackboard`, `keys`, `set_value`, `has_value`, `erase_value`) are all
present, so the candidate is unaffected — but the symbol table is incomplete for the same reason
the variables are.

### D.5 Location accuracy

* All captured declarations report the correct line **of the analysed text**; verified for
  `Stats.gd` (`take_damage` 23, `heal` 31, `health_changed` 6) and `HealthResource.gd`
  (`is_dead` 19).
* Those are references-copy coordinates = commit line + 3. The parser does not know or claim
  otherwise; the 3-line header is a collector artefact. No global offset fix is proposed —
  Batch C keeps the dual-coordinate scheme Phase 1.74 established.
* No fabricated line numbers were found: every reported line contains the declaration it names.

### D.6 Are current COMPLETE / PARTIAL labels reasonable?

* `HealthResource.gd`: `analysis_complete` — **wrong** (1/5 exports).
* `blackboard.gd`: `analysis_partial` — right label, wrong reason (annotation, not lost symbols).
* `Stats.gd`: `analysis_partial` — right, caused by unresolved questions, not by the 3 lost vars.
* `HealthBar.gd`: `analysis_partial` — right label, wrong reason.

So the labels were right 2/4 times and for the right reason 0/4 times. That is the finding that
justifies Batch B, and it is why Batch B must add an explicit coverage status instead of
re-labelling records.

---

## E. Analysis Completeness Semantics

### E.1 What `analysis_complete` currently means (from the code)

`analysis_status = "analysis_complete"` requires **all** of:

1. provenance known and not `unknown`;
2. license `copy_allowed`;
3. `file_type == "gdscript"`;
4. `parse_text` did not raise;
5. `script.functions` is non-empty;
6. `source_analysis` produced no unresolved questions;
7. `_syntax_limitations()` found no "hard" limitation (non-`@export`/`@onready` `@` line, inner
   class, lambda).

### E.2 Answers to the audit questions

1. **Is COMPLETE only "the parser ran"?** Almost. It is "the parser ran, found functions, and the
   *heuristic* limitation scan was silent". It is not a coverage measurement.
2. **Does it mean all declared structures were captured?** **No.** `HealthResource.gd` proves it.
3. **Is parser coverage recorded?** No. There is no coverage artefact; `limitations[]` is free
   text produced by a line-prefix heuristic, and the declaration regexes' own failures are
   invisible to it.
4. **Can it express "syntax unsupported"?** Only for three hard-coded patterns. `var x = 1` is not
   a "limitation" to the scanner — it simply matches nothing.
5. **Can the parser succeed while missing declarations?** Yes, and it did, four times out of four
   audited files.

### E.3 Proposed separation of concepts (Batch B target)

| Field | Values | Meaning |
|---|---|---|
| `parse_execution_status` | `PARSED` / `FAILED` / `NOT_RUN` / `UNSUPPORTED_FILE` | did the scan run to completion |
| `syntax_coverage_status` | `COMPLETE` / `PARTIAL` / `LIMITED` / `NOT_APPLICABLE` | were all constructs in the file inside the supported grammar |
| `analysis_completeness` | `FULL` / `DECLARATION_GAPS` / `EXECUTION_ONLY` | declaration-level completeness, independent of execution |
| `unsupported_constructs` | list of `{code, line}` | constructs recognised as out of scope (inner class, lambda, legacy `setget`, shader, …) |
| `unrecognized_declarations` | list of `{line, kind_hint, reason}` | **declaration-shaped lines the parser did not account for** — the anti-false-COMPLETE signal |

`analysis_status` keeps its current meaning for compatibility; these fields are added alongside it
by the fixed parser, and old records simply lack them (readers must treat absence as "unknown
coverage", never as COMPLETE).

The rule Batch B must implement: **a file is only `syntax_coverage_status=COMPLETE` when
`unrecognized_declarations` is empty AND no unsupported construct was seen.** Nothing is
relabelled wholesale; `HealthResource.gd` will be re-analysed (Batch C) and only then will its
coverage be reported honestly.

---

## F. Proposed Minimal Fixes

All inside `gd_parse.py`, additive, no new dependency, no second parser.

| # | Fix | Addresses | Size |
|---|---|---|---|
| F1 | One shared declaration regex accepting an annotation prefix chain (`@export*`, `@onready`, `@rpc(…)`, `@tool`, any `@x(…)`), optional `static`, and **both** `=` and `:=` initialisers, optional type, optional trailing `:` (property) | A/B/C/D/I/J/K/L/M, `hp`/`max_hp`, `Stats.gd` state, `HealthBar.gd` exports | ~40 lines |
| F2 | Declaration records gain `declaration_kind` (`VARIABLE`/`PROPERTY`/`CONSTANT`/`SIGNAL`/`ENUM`/`FUNCTION`), `annotations[]`, `has_initializer`, `initializer_kind` (`EXPLICIT_TYPE`/`INFERRED`/`UNTYPED`), `end_line`, keep existing keys | B2 model | ~30 lines |
| F3 | Property accessor blocks: when a declaration ends with `:`, consume the indented `get:` / `set(v):` blocks, record `has_getter`/`has_setter` and each accessor's line range; never emit them as functions | E/F/G, `HealthBar.gd` setter, `blackboard.gd` setter | ~60 lines |
| F4 | Annotation collection: preceding annotation lines attach to the next declaration; unknown annotations are kept in `annotations[]` with `interpreted: false` and never drop the declaration | K, `@tool`, `@icon`, `@rpc`, `@export_category` | ~25 lines |
| F5 | Multi-line continuation: join lines while brackets are unbalanced or the line ends with `\` or a declaration ends with `:`; applies to declarations and function signatures | N, `blackboard.gd` `get_value` | ~45 lines |
| F6 | Coverage metadata + unrecognized-declaration scan (a declaration-shaped line that produced no record) | E.3 | ~50 lines |
| F7 | Bump `PARSER_VERSION` to `1.75`; keep old API and keys | provenance of results | 1 line |

Explicitly **not** fixed: `enum` capture, inner classes, legacy `export(int) var … setget`,
lambdas, full type inference, `@static_unload` semantics. They are reported as unsupported
constructs instead (`enum` and inner class become `unrecognized_declarations` entries so the
coverage status is honest).

---

## G. Compatibility Risks

| Risk | Why | Mitigation |
|---|---|---|
| **Analysis digests change** | new symbol entries change `input_digest`-independent content of analysis records; `analysis_id` includes `PARSER_VERSION`, so re-analysis produces a *new* id | Batch C writes to a separate reanalysis workspace, never overwriting; original records keep their ids and digests |
| Linkage freshness flips to STALE | `evaluate_freshness` compares analysis record digests | do not rebuild linkage in this phase; Batch C only produces review output |
| Feature-side projections change | `feature_evidence.py` and `source_analysis.py` import `gd_parse` | do not regenerate projections/analyses in this phase; regression tests must prove feature-side behaviour on existing files is additive |
| Symbol tables grow | new `variables`/`exports` entries could change `POTENTIAL_RELEVANCE` token overlap for *future* linkage builds | no linkage rebuild here; any future change is a human-reviewed diff, and eligibility policy is untouched |
| Property/function confusion introduced by F3 | accessors could leak into `functions` | negative tests: accessors never appear in `functions`, `is_dead` property vs `is_dead()` function stay distinct |
| Old records unreadable | new fields in `symbols` | all changes are additive keys; readers use `.get`; a compatibility test reads a pre-existing record unchanged |
| Coordinates misread as commit lines | parser input is the references copy | keep reporting references-copy lines; add explicit `source_coordinates` marker; Batch C keeps dual coordinates |

**Hard constraint carried forward:** parser output never sets
`QUALIFIED_DIRECT` / `VERIFIED` / `ADMITTED`, never changes independence, never upgrades
graph-derived relations, never touches candidates. Batch C only *reports* differences.

---

## H. Regression Test Plan

New file `.ai/tools/learning/tests/test_gd_parse.py` (no dedicated parser test file exists today):

**Positive (16)** — typed var, untyped var, inferred var, `@export var` (with/without type),
`@export var` untyped, `@onready`, `static var`, multi-annotation (`@export_range`, `@export_group`
+ `@export`), getter only, setter only, getter+setter, multi-line declaration, multi-line function
signature, annotation-to-declaration association (two declarations in a row), source line numbers,
`declaration_kind` correctness.

**Negative (6)** — property never appears in `functions`; function never appears in
`variables`/`exports`; missing type never becomes a fabricated type (`type_annotation is null` /
`""` only when absent in source); unrecognised declaration is reported rather than dropped; failed
parse never yields `COMPLETE` coverage; legacy `export(int) var … setget` reported as unsupported,
not silently captured as something else.

**Compatibility (3)** — a stored analysis record from Phase 1.73 still loads and validates; a
record lacking the new coverage fields is treated as unknown coverage; `parse_text` output for the
four audited files keeps every previously captured symbol (superset check).

**Existing suites to rerun** (all must stay green):
`test_source_analysis.py` (17), `test_feature_evidence_projection.py` (41),
`test_feature_pipeline.py`, `test_feature_linkage.py` (70), `test_batch_a.py` (38),
`test_batch_b.py` (33), `test_candidate_workspace.py` (64),
`check_feature_metadata.py`, `candidate_workspace.py validate`, `check-freshness`,
`feature_linkage.py check --pilot`.

Acceptance for Batch B: superset of previously captured symbols on the four real files, zero
regressions, zero new mismatches between property and function, and every audited gap above either
captured or explicitly reported.

---

## I. Non-goals (this phase)

No similarity engine, no semantic similarity, no symbol equivalence, no ranking, clustering or
dedup, no admission gate/policy, no promote, no Feature creation or metadata edit, no automatic
candidate update or policy change, no automatic DIRECT approval, no automatic `health_bar` seed, no
graph→direct conversion, no runtime/behaviour verification, no full GDScript compiler, no
wholesale corpus rebuild. Enum/inner-class/legacy-`setget` support is out of scope for this phase
and will be *reported*, not implemented.

---

## J. Batch B Readiness

**`READY_FOR_BATCH_B`**

Justification:

1. The defect is proven at the regex level and reproduced on eight minimal cases.
2. Its consequence is quantified on real sources: 1/5 exports in `HealthResource.gd`, 5 missed
   declarations in `HealthBar.gd`, 3 in `Stats.gd`, 2 variables **and one public function** in
   `blackboard.gd`.
3. The completeness semantics are explained, and the audit explicitly rejects "relabel everything
   PARTIAL" in favour of explicit coverage fields.
4. The fix set is bounded (F1–F7, ~250 lines inside one module), additive, dependency-free, and
   each item maps to a reproduced case.
5. Compatibility risks are enumerated with a rule — no historical record, linkage, projection,
   candidate or policy is written in this phase.
6. The regression plan is concrete, including three negative tests against exactly the failure
   modes the current parser could newly introduce (property/function confusion, fabricated types,
   silent drops).

Batch B scope is fixed to F1–F7. Anything outside it stops and returns to audit.
