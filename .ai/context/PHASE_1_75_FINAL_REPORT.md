# Phase 1.75 — Final Report
# Parser Coverage Hardening & Targeted Evidence Reanalysis

---

## A. Executive Summary

The GDScript declaration parser had one dominant defect: every `var`/`@export
var` regex accepted only `:=` for an initialiser and then required end-of-line,
so any declaration using `=` — the common GDScript form — was silently dropped.
On top of that, `@export_range(…)`-style prefixes, `static var`, property blocks
(`get:`/`set(v):`) and multi-line declarations/signatures were unsupported, and
`analysis_complete` was derived from "parser ran + functions present + heuristic
limitations silent", so a record could claim completeness while missing 4 of 5
exported variables.

Batch A proved the defect and quantified it on four real sources. Batch B fixed
exactly the proven gaps (single declaration grammar, annotation binding,
property accessors, continuation, explicit coverage status) with no new
dependency and no second parser, and added a 35-check coverage suite including
negative guarantees. Batch C reanalysed the four affected records into an
isolated, versioned workspace with provenance and digest verification, diffed
old vs new, verified every reported source line, re-evaluated linkage read-only,
and produced candidate impact assessments.

Result: `HealthResource.gd` 1 → 5 exports; `HealthBar.gd` 1 → 6 declarations
(including a property with a setter); `Stats.gd` 1 → 3 declarations plus an
explicit "legacy setget unsupported" report; `blackboard.gd` recovered a lost
public function (`get_value`) plus two declaration gaps. No symbol was lost, no
type or line was fabricated, no official record changed (188 official files
digest-identical), **0 linkage classifications changed**, no candidate mutated,
`blackboard` independence and `attack_emitter` graph-derived status untouched,
and `health_bar` still has no qualified seed.

Verdict: **PASS_WITH_LIMITATIONS**.

---

## B. Baseline

| Item | Value |
|---|---|
| Project root | `F:/Godot_v4.7-stable/game` |
| Branch / HEAD | `master` / `d64b1cd5b576a44dcfafd7becbb2d2a7f1fd6a84` |
| Staged | 0 |
| Modified at start | 33 (all pre-existing, untouched by this phase) |
| Untracked at start | as recorded at the Phase 1.74 close (different counting mode; see M) |
| External analysis records | 34 |
| Feature linkage records | 150 (150 FRESH) |
| Candidates | 2 (`cand-08fdc0b10a112ecf` health, `cand-7f52cb8f583124db` blackboard), 2 FRESH, 2 VALID |
| Feature metadata | 31, 0 errors |
| Parser | `.ai/tools/learning/gd_parse.py`, `parser_version 1.71` |

No pre-existing modified/untracked file was cleaned, staged, committed or
reverted.

---

## C. Parser Coverage Audit (Batch A)

Full report: `.ai/context/PHASE_1_75_A_PARSER_COVERAGE_AUDIT.md`.

* 26-row coverage matrix measured by probe, not assumed: 11 supported, 2
  partial, 13 unsupported/mis-detected.
* Root cause: `(?::=\s*(?P<value>.+))?$` in `EXPORT_RE`/`VAR_RE` — `=` never
  matched; `@export` matched as a literal prefix so `@export_range` failed;
  no `static`, no trailing `:`, no continuation.
* Real-source audit: `HealthResource.gd` captured 1 of 5 exports while reporting
  `analysis_complete`; `HealthBar.gd` missed 5 declarations plus a setter;
  `Stats.gd` missed 2 state variables (plus one legacy `setget`); `blackboard.gd`
  missed two declarations **and one public function** whose signature spans three
  lines.
* Completeness semantics: `analysis_complete` meant "parser ran, found
  functions, heuristic limitation scan silent" — never "all declarations
  captured". The audit rejected relabelling records in favour of explicit
  coverage fields.
* Conclusion: `READY_FOR_BATCH_B`.

---

## D. Parser Changes (Batch B)

Full report: `.ai/context/PHASE_1_75_B_PARSER_HARDENING.md`.

1. **Unified declaration grammar** (`DECL_RE`, `CONST_RE`): annotation prefix
   chain (`@export*`, `@onready`, `@rpc(…)`, `@tool`, unknown `@x(…)`), optional
   `static`, optional type, `=` **and** `:=`, optional trailing `:` marking a
   property.
2. **Declaration model**: `declaration_kind` (`VARIABLE`/`PROPERTY`/`FUNCTION`/
   `CONSTANT`/`SIGNAL`), `annotations[]`, `has_initializer`,
   `initializer_kind`, `end_line`, `is_exported`/`is_static`/`is_onready`;
   `type` is verbatim source text or `""` — never inferred.
3. **Property accessors**: `get:` / `set(v):` recorded with real line ranges,
   `has_getter`/`has_setter`; accessors are never emitted as functions.
4. **Annotation binding**: a standalone annotation line applies to the next
   declaration only; unknown annotations are preserved with `interpreted:false`
   and never drop the declaration. `@export_category`/`@export_group` do not make
   a variable exported.
5. **Continuation**: backslash, unbalanced brackets, multi-line function
   signatures — first physical line is recorded, nothing invented.
6. **Coverage metadata**: `parse_execution_status`, `syntax_coverage_status`,
   `analysis_completeness`, `unsupported_constructs`,
   `unrecognized_declarations`, `source_coordinates`; declaration-shaped lines
   that produced no record are reported, so "parser ran" can no longer be
   reported as "complete".
7. `PARSER_VERSION` → `1.75` in the adapter; schema stays version 1, additive
   keys only, `EXPORT_RE`/`VAR_RE` kept as aliases.

---

## E. New Tests

`.ai/tools/learning/tests/test_gd_parse.py` — **35 checks, 0 failures, exit 0**.

Positive 24 (typed/untyped/inferred/static/onready variables, exports with and
without type, `@export_range`, annotation chain and binding, getter, setter,
both, `\`-continuation, bracket continuation, multi-line signature, real line
numbers, coverage status, coordinates). Negative 8 (property never in
`functions`; function never in `variables`/`properties`/`exports`; `is_dead`
property vs `is_dead()` function distinct; absent type never inferred; legacy
`setget` reported not dropped; inner class reported; unparsable file never
COMPLETE). Compatibility 3 (pre-1.75 declarations survive; record without
coverage fields loads; stored records still parse).

---

## F. Historical Regression

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
| `python .ai/tools/external_code/feature_linkage.py check --pilot` | 0 | FRESH=150 STALE=0 MISSING_SOURCE=0 INVALID=0; coverage 150/150 |
| `python .ai/tools/feature_registry/candidate_workspace.py validate` | 0 | 2 VALID, policy `phase-1.74-c/1` |
| `python .ai/tools/feature_registry/candidate_workspace.py check-freshness` | 0 | 2 FRESH, 0 STALE, 0 INCOMPLETE |
| `python .ai/tools/external_code/reanalysis_175.py` | 0 | 4/4 reanalysed, 0 stopped |

No failure was suppressed, skipped or worked around.

---

## G. Reanalysis Results

Full report: `.ai/context/PHASE_1_75_C_TARGETED_EVIDENCE_REANALYSIS.md`.
Workspace: `.ai/learning/external_code/reanalysis/parser_1.75/` (29 files).

| Source | symbols removed | symbols added | analysis_status |
|---|---:|---|---|
| `HealthResource.gd` | 0 | 4 exports (`hp`, `max_hp`, `reset_hp`, `reset_max_hp`; `float`, `5`, `@export`) | complete → complete (now truthful) |
| `HealthBar.gd` | 0 | 4 vars + 1 property (`size` with setter) | partial → partial (missing `class_name`) |
| `Stats.gd` | 0 | 2 vars (`modifiers`, `health`) | partial → partial (legacy `setget` reported) |
| `blackboard.gd` | 0 | 3 (`get_value` function restored, `blackboard` property+setter, `_data`) | partial → complete |

Provenance: 4/4 identical repo, commit, path, URL, license, `input_digest`,
`source_digest`; 0 stops. Source lines: 52 reported symbols read back from the
source — **0 location problems**. No value, type, line, parameter or return type
of a previously captured symbol changed; the only "changed" entries are additive
keys (`declaration_kind`, `annotations`, `end_line`, `type: ""` on constants).

Read-only blast-radius measurement over all 34 records (nothing written): 21
records would gain symbols, 6 would move `analysis_partial → analysis_complete`
(annotation interpretation only). Those 30 were intentionally not reanalysed.

---

## H. Linkage Evaluation Differences

20 pairs evaluated read-only for the 4 records × 5 pilot features; 15 records
built, 5 not evaluable (the `HealthBar.gd` record); **0 classification changes**.

* `HealthResource → health`: `DIRECT_EVIDENCE → DIRECT_EVIDENCE`
* `HealthResource → health_bar`: `POTENTIAL_RELEVANCE → POTENTIAL_RELEVANCE`
* `HealthResource → attack_emitter`: `INDIRECT_EVIDENCE → INDIRECT_EVIDENCE`
* `Stats → health`: `DIRECT_EVIDENCE → DIRECT_EVIDENCE`
* `blackboard → blackboard`: `DIRECT_EVIDENCE → DIRECT_EVIDENCE`
* `HealthBar → *`: `NOT_EVALUABLE` (no distinctive parseable symbols)

Nothing was promoted, no `POTENTIAL_RELEVANCE` became `DIRECT`, no
graph-derived relation was converted, `NO_SUPPORTED_LINK` was not treated as
missing evidence, and no same-name identifier was declared equivalent. All
evaluation output is `REVIEW_ONLY_NOT_WRITTEN` under
`reanalysis/parser_1.75/linkage_evaluation/`.

---

## I. Candidate Impact Assessment

| Candidate | Refs touched | New source material | Marker |
|---|---:|---|---|
| `cand-08fdc0b10a112ecf` (health) | 2/2 | `hp`, `max_hp`, `reset_hp`, `reset_max_hp`, `health`, `modifiers` | `REQUIRES_MANUAL_EVIDENCE_REVIEW` |
| `cand-7f52cb8f583124db` (blackboard) | 1/1 | `get_value`, `blackboard`, `_data` | `REQUIRES_MANUAL_EVIDENCE_REVIEW` |

No candidate id, status, content digest, policy version, evidence reference or
excluded-evidence list was modified. `health_bar` obtained **no** seed: its
record is still not evaluable, and even with new declarations the maximum claim
stays conceptual. `attack_emitter` keeps `GRAPH_DERIVED_RELATION` /
`INDIRECT_EVIDENCE`. `blackboard` keeps `NOT_INDEPENDENT`.

---

## J. Data Integrity

* Snapshot of 188 official artefacts before the run; identical after
  (`0 changed, 0 extra, 0 missing`): 34 analysis, 150 linkage, 2 candidates,
  `WORKSPACE.json`, `index.json`.
* Official analysis, linkage, projections, feature metadata, index, graph,
  seed policy and candidate drafts were **read only**.
* New data lives exclusively in
  `.ai/learning/external_code/reanalysis/parser_1.75/` (29 files).
* Historical records keep `parser_version 1.71`; nothing was bulk-relabelled.
* `reanalysis_175.py` stops a file on any provenance, license or digest
  mismatch; it stopped on none.

---

## K. Limitations

1. Enum members, inner classes, legacy 3.x `export(...) var … setget` and lambda
   bodies are reported as unsupported, not parsed (`Stats.gd.max_health` is one
   such case).
2. Type annotations are source text, not resolved types; no type inference.
3. Only first-level property accessor blocks are recognised.
4. Coordinates are references-copy coordinates (commit line + verified 3-line
   header); the offset is verified per record, never applied globally.
5. Only 4 of 34 records were reanalysed, per scope; the other 30 still carry
   parser-1.71 data, and 21 of them would change if reanalysed (measured, not
   written).
6. Linkage re-evaluation covers the 5 pilot features only; it is not a corpus
   rebuild.
7. No runtime or behavioural verification: the parser describes structure only.
8. `HealthBar.gd`'s record remains `analysis_partial` because it has no
   `class_name` (unresolved cross-class dependency), not because of parsing.

---

## L. Files Changed

Added:

| Path | Content |
|---|---|
| `.ai/tools/learning/tests/test_gd_parse.py` | 35-check parser coverage suite |
| `.ai/tools/external_code/reanalysis_175.py` | Batch C reanalysis workspace tool |
| `.ai/learning/external_code/reanalysis/parser_1.75/` | 29 files: `WORKSPACE.json`, 4 new analysis records, 4 diffs, 20 review-only linkage evaluations |
| `.ai/context/PHASE_1_75_A_PARSER_COVERAGE_AUDIT.md` | Batch A report |
| `.ai/context/PHASE_1_75_B_PARSER_HARDENING.md` | Batch B report |
| `.ai/context/PHASE_1_75_C_TARGETED_EVIDENCE_REANALYSIS.md` | Batch C report |
| `.ai/context/PHASE_1_75_FINAL_REPORT.md` | this report |

Modified:

| Path | Change |
|---|---|
| `.ai/tools/learning/gd_parse.py` | declaration grammar, annotations, property accessors, continuation, coverage reporting |
| `.ai/tools/external_code/external_code_understanding.py` (an untracked file) | `PARSER_VERSION 1.75`, coverage fields on records, coverage-aware status, annotation-aware limitations, extra symbol keys |

Deleted: **none** (`git status` reports 0 deletions).

---

## M. Git Status

| | Start | End |
|---|---|---|
| Branch / HEAD | `master` / `d64b1cd5…` | `master` / `d64b1cd5…` (unchanged) |
| Staged | 0 | 0 |
| Modified | 33 | 34 (`gd_parse.py` added to the pre-existing 33) |
| Untracked | pre-existing set | +35 entries from this phase (6 new files + 29 workspace files) |

Untracked counts differ from the Phase 1.74 record because the earlier figure was
produced with a different untracked mode; the value measured now is
`git status --porcelain` = 136 entries / `-uall` = 435 files, with **0 deletions**.
No git command other than read-only `status` / `rev-parse` / `ls-files` /
`diff --cached` was executed: no commit, push, fetch, pull, checkout, reset,
clean, rebase or cherry-pick.

---

## N. Final Verdict

**PASS_WITH_LIMITATIONS**

Why not FAIL: the parser no longer confuses property and function (negative
tests plus `is_dead` property vs `is_dead()` function in real data), never
fabricates a type (`type` is `""` when absent, verified on `var hp = 100`,
`@export var max_hp = 100` and the four real files), and every reported line was
read back from source (0 problems over 52 symbols).

Why not PASS: enum, inner class, legacy `setget` and lambda remain unparsed
(reported, not silent); only 4 of 34 records were reanalysed; 30 records still
carry parser-1.71 data.

---

## O. Next Phase Recommendation

1. **Reanalysis expansion (opt-in):** reanalyse the remaining 30 records with the
   same workspace/diff/verify pipeline. This is a data migration decision and
   needs explicit authorization, because 21 records would change content and 6
   would change `analysis_status`.
2. **Legacy/grammar follow-ups, in priority order:** enum capture (name +
   members), multi-line/`setget` 3.x export reporting refinement, inner-class
   member extraction.
3. **Candidate review (human):** the two `REQUIRES_MANUAL_EVIDENCE_REVIEW`
   markers now have extra parsed state (`hp`, `max_hp`, `health`, `modifiers`,
   `get_value`) to consider; `health_bar` remains without a seed and needs a
   real Health-Resource binding, not merely matching names.
4. Do **not** start similarity/ranking/admission/promote work until the review
   queue above is resolved.
