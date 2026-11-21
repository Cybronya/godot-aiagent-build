# Phase 1.75 — Batch B
# Targeted Parser Hardening

Scope was fixed by Batch A (`READY_FOR_BATCH_B`): F1–F7 only. No other parser
behaviour, no evidence policy, no analysis record was touched.

---

## A. Implementation Summary

| Item | Change |
|---|---|
| F1 unified declaration grammar | `DECL_RE` / `CONST_RE` replace `EXPORT_RE`/`VAR_RE`/old `CONST_RE`; annotation prefix chain, optional `static`, both `=` and `:=`, optional type, optional trailing `:` |
| F2 declaration model | every `var`/`const`/`signal`/`func` record now carries `declaration_kind`, `annotations[]`, `has_initializer`, `initializer_kind`, `end_line` |
| F3 property accessors | a declaration ending in `:` opens a property block; `get:` / `set(v):` are recorded with real line ranges, never as functions |
| F4 annotations | standalone `@…` lines bind to the next declaration only; unknown annotations are kept with `interpreted: false` and never drop the declaration |
| F5 multi-line | backslash continuation, unbalanced-bracket continuation, multi-line function signatures |
| F6 coverage | `parse_execution_status`, `syntax_coverage_status`, `analysis_completeness`, `unsupported_constructs`, `unrecognized_declarations`, `source_coordinates`; declaration-shaped lines that produced no record are reported |
| F7 versioning | `PARSER_VERSION` in the adapter is now `1.75`; the parser module keeps its API |

No new dependency, no second parser, no AST library. `gd_parse.parse_text`,
`parse_file`, `Function`, `calls()` and `connects()` keep their signatures.

### Root cause fixed

```python
# before (both regexes): initialiser recognised only as ":=", line anchored with $
(?::=\s*(?P<value>.+))?$
# after: ":=" or "=", type optional, trailing ":" captured as a property marker
(?:\s*(?P<op>:=|=)\s*(?P<value>.*))?$
```

---

## B. Parser Data Model Changes

`Script` (all additive, all defaulted):

```python
properties: list[dict]     # declarations with a getter/setter block
declarations: list[dict]   # every captured declaration, one unified list
coverage: dict
```

Declaration dicts keep the pre-1.75 keys (`name`, `line`, `type`, `value`,
`params`, `returns`) and add:

| Field | Values |
|---|---|
| `declaration_kind` | `VARIABLE` `PROPERTY` `FUNCTION` `CONSTANT` `SIGNAL` (`ENUM` is reported, not captured) |
| `type` | source text of the annotation, `""` when absent — never inferred |
| `has_initializer` / `initializer_kind` | `True/False`, `NONE` `EXPLICIT` `INFERRED` |
| `annotations` | `[{name, args, line, interpreted}]` |
| `end_line` | last physical line of the declaration / signature |
| `is_exported` `is_static` `is_onready` | booleans |
| `has_getter` `has_setter` `accessors` | property blocks only: `[{kind, line, end_line, param}]` |

Coverage block:

| Field | Values |
|---|---|
| `parse_execution_status` | `PARSED` |
| `syntax_coverage_status` | `COMPLETE` / `PARTIAL` |
| `analysis_completeness` | `FULL` / `DECLARATION_GAPS` |
| `unsupported_constructs` | `[{code, line, name?}]` — `ENUM_NOT_INTERPRETED`, `INNER_CLASS_NOT_INTERPRETED`, `LEGACY_SETGET_NOT_INTERPRETED`, `LAMBDA_NOT_ANALYZED` |
| `unrecognized_declarations` | `[{line, kind_hint, text}]` — declaration-shaped line that produced no record |
| `source_coordinates` | `ANALYZED_FILE` (the file the parser was given) |

The adapter propagates these into the analysis record and treats
`syntax_coverage_status != COMPLETE` (or any unrecognized declaration) as
`parse_status = partial` / `analysis_status = analysis_partial`. Parser success
is no longer reported as completeness.

---

## C. Syntax Coverage Matrix (after Batch B, measured)

| Construct | Before | After |
|---|---|---|
| `var x = v` / `var x: T = v` | ✘ | ✔ |
| `var x := v` / `var x` | ✔ | ✔ |
| `@export var x = v` / `@export var x` | partial | ✔ |
| `@export var x: T := v` | ✔ | ✔ |
| `@export_range/…(…) var x` | ✘ | ✔ |
| `@onready var x = $Node` | ✘ | ✔ |
| `static var x` | ✘ | ✔ |
| `@export_category/group` above a var | ✘ (var lost) | ✔ (annotation attached, var not exported by it) |
| `const x: T = v` / `const x := v` | ✔ | ✔ |
| `signal` / `func` / `static func` | ✔ | ✔ |
| multi-line function signature | ✘ (function lost) | ✔ |
| multi-line declaration (`\`, brackets) | ✘ | ✔ |
| getter / setter / both | ✘ | ✔ (with line ranges) |
| `@tool` `@icon` `@rpc` `@static_unload` | declaration kept, annotation dropped | declaration kept, annotation recorded |
| `enum` | ✘ silent | ✘ **reported** (`ENUM_NOT_INTERPRETED`) |
| inner `class` | ✘ (limitation text) | ✘ **reported** |
| legacy `export(int) var … setget` | ✘ silent | ✘ **reported** |
| `lambda` | limitation text | limitation + unsupported construct entry |
| class_name / extends | ✔ | ✔ |

Still not interpreted (out of scope, now explicit): enum members, inner-class
members, legacy 3.x export/setget, type resolution (annotations are source text),
property body semantics, `@static_unload` behaviour.

---

## D. Before / After Examples

```gdscript
@export var hp: float = 100.0
```
before: 0 symbols. after: `exports.hp`, type `float`, value `100.0`, line 1,
`initializer_kind=EXPLICIT`, annotations `[export]`.

```gdscript
var hp = 100
```
before: 0. after: `variables.hp`, type `""`, value `100`.

```gdscript
var hp: float = 100.0:
	set(value):
		hp = value
```
before: 0 (declaration and accessor both lost). after: `properties.hp`,
`declaration_kind=PROPERTY`, `has_setter=True`, `has_getter=False`,
`accessors=[{kind:set, line:2, end_line:3, param:value}]`, and `functions` stays empty.

```gdscript
func get_value(
	key: Variant, default_value: Variant = null
) -> Variant:
```
before: function lost. after: `functions.get_value`, `start_line=1`, `end_line=4`.

Real files, old → new symbol counts:

| Source | before | after |
|---|---|---|
| `HealthResource.gd` | 6 funcs, 6 signals, 1 export | 6 funcs, 6 signals, **5 exports** |
| `HealthBar.gd` | 7 funcs, 1 const | 7 funcs, 1 const, **4 vars, 1 property (setter)** |
| `Stats.gd` | 6 funcs, 3 signals | 6 funcs, 3 signals, **2 vars** |
| `blackboard.gd` | 7 funcs, 1 const | **8 funcs**, 1 const, **1 var, 1 property (setter)** |

No previously captured symbol disappeared in any of the four files (checked in
Batch C: `symbols_removed` total 0).

---

## E. Source Location Validation

* Line numbers are the physical lines of the analysed file; the parser never adds
  an offset. The analysed file is the references copy, so its coordinates are
  references-copy coordinates (`source_coordinates = ANALYZED_FILE`); Batch C
  keeps the established dual-coordinate scheme instead of a global offset.
* `end_line` is the last physical line of a declaration/signature; accessor
  ranges are `[line, end_line)` over the real block.
* Multi-line joins never fabricate a line: the recorded first line is the line
  where the declaration starts.
* Batch C verification: for all 4 re-analysed files, **every** reported symbol
  line was read back from the source and contains the symbol name — 0 problems
  over 32 declarations/functions.

---

## F. Schema Compatibility

* `schema_version` stays `1`; no field was renamed or removed.
* Historical records load unchanged: they simply lack the coverage fields, and
  readers must treat absence as "coverage unknown", never as COMPLETE.
* `parser_version` distinguishes records: 34 stored records say `1.71`, new
  analysis says `1.75`. `analysis_id` includes the parser version, so a
  reanalysis produces a **new** id — Batch C keeps the original id alongside it.
* `EXPORT_RE` / `VAR_RE` names are retained as aliases of `DECL_RE` so any
  importer keeps working.

---

## G. New Tests

`.ai/tools/learning/tests/test_gd_parse.py` — **35 checks**, exit 0.

Positive: typed/untyped/inferred/static/onready variables, export with and
without type, `@export_range`, annotation chains and binding, getter, setter,
getter+setter, multi-line declaration (backslash and bracket), multi-line
function signature, real line numbers, coverage status, source coordinates.

Negative: property never in `functions`; function never in
`variables`/`properties`/`exports`; `is_dead` property vs `is_dead()` function
stay distinct; absent type never inferred; legacy `setget` reported, not
silently dropped; inner class reported; unparsable file never COMPLETE.

Compatibility: pre-1.75 declaration set survives; a record without coverage
fields loads; stored historical records still parse.

---

## H. Historical Regression

| Command | Exit | Result |
|---|---|---|
| `python .ai/tools/learning/tests/test_gd_parse.py` | 0 | 35 checks, 0 failures |
| `python .ai/tools/learning/tests/test_source_analysis.py` | 0 | 17 checks, 0 failures |
| `python .ai/tools/external_code/tests/test_batch_a.py` | 0 | 38 checks |
| `python .ai/tools/external_code/tests/test_batch_b.py` | 0 | 33 checks |
| `python .ai/tools/external_code/tests/test_feature_linkage.py` | 0 | 70 tests OK |
| `python .ai/tools/feature_registry/tests/test_feature_evidence_projection.py` | 0 | 41 tests OK |
| `python .ai/tools/feature_registry/tests/test_feature_pipeline.py` | 0 | 21 checks |
| `python .ai/tools/feature_registry/tests/test_candidate_workspace.py` | 0 | 64 tests OK |
| `python .ai/tools/validator/check_feature_metadata.py` | 0 | 31 features, 0 errors, 0 warnings |
| `python .ai/tools/external_code/feature_linkage.py check --pilot` | 0 | 150 FRESH, coverage 150/150 |
| `python .ai/tools/feature_registry/candidate_workspace.py validate` | 0 | 2 VALID |
| `python .ai/tools/feature_registry/candidate_workspace.py check-freshness` | 0 | 2 FRESH |

No historical record, projection, linkage, candidate or metadata was rewritten
by Batch B.

---

## I. Files Changed

| File | Change |
|---|---|
| `.ai/tools/learning/gd_parse.py` | modified — unified declaration grammar, annotations, property accessors, continuation, coverage, unsupported/unrecognized reporting |
| `.ai/tools/external_code/external_code_understanding.py` | modified — `PARSER_VERSION=1.75`, coverage fields on the record, coverage-aware status, annotation-aware limitations, new symbol keys |
| `.ai/tools/learning/tests/test_gd_parse.py` | new — 35 coverage checks |

Nothing else was edited in Batch B.

---

## J. Batch C Readiness

**READY_FOR_BATCH_C.**

* Every audited gap is either captured (variables, exports, annotations,
  accessors, multi-line declarations/signatures) or explicitly reported
  (`enum`, inner class, legacy `setget`, lambda).
* Property/function confusion is prevented and covered by negative tests.
* Source locations verified; no fabricated offsets or lines.
* Full regression suite green, historical data untouched (150 FRESH, 2 VALID,
  31 metadata PASS).
* Coverage semantics are explicit, so a reanalysis can tell "parser ran" apart
  from "declarations complete".
