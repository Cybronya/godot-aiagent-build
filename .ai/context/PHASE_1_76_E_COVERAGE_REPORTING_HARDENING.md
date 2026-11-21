# PHASE 1.76 — BATCH E
## Parser Coverage Reporting Hardening

**Task Type:** PARSER COVERAGE REPORTING HARDENING
**Phase:** 1.76 / **Batch:** E
**Execution Mode:** CONTROLLED CODE CHANGE + AUTOMATED TESTS (no formal data write)
**Prerequisite:** Batch D = `PASS_WITH_LIMITATIONS` (`UNSUPPORTED_CONSTRUCT_REPORTING_INCOMPLETE`)
**Authorization Boundary:** Batch E only. No Semantic Linkage Tier, no re-analysis of the 4
analyses without linkage, no Seed Policy gate, no Batch B re-run, no Symbol Diff rebuild, no
formal Analysis / Linkage / Candidate write, no Review Queue, no Batch F, no Git write.

---

## A. Executive Summary

Batch E fixed **reporting**, not parsing breadth. Three defects were named by Batch D; a fourth of
the same class surfaced while testing and was fixed with them.

| Defect | Before | After |
|---|---|---|
| `export(String) var expand_to` / bare `onready var title_label` | grammar did not match, declaration **silently dropped** | both captured as declarations (type / initialiser preserved) |
| captured `setget` declaration | still flagged `LEGACY_SETGET_NOT_INTERPRETED` (**false** "not parsed") | `LEGACY_SETGET_WIRING_NOT_MODELED`, `extent=PARTIALLY_INTERPRETED`, old code kept as `predecessor_code` |
| `unsupported_constructs[].line` | one number silently used as commit line / record line | `line` keeps its historical meaning; `line_space` / `analysis_line` / `source_line` / `record_line` are explicit, unmapped spaces stay `None` |
| declaration-shaped top-level line not matched by the grammar | dropped with `COMPLETE` coverage | reported in `unrecognized_declarations` with `declaration_gap=true` |

Deliberately **not** done: no new coverage-status system (`syntax_coverage_status` stays the single
authority), no removal of legacy markers to hide false positives, no `PARSER_VERSION` bump, no
re-analysis, no formal record rewrite.

| Check | Result |
|---|---|
| `test_gd_parse.py` | **36 checks / 0 failures** |
| `test_coverage_reporting.py` (new, Batch E) | **36 checks / 0 failures** |
| `test_source_analysis.py` | **17 checks / 0 failures** |
| `external_code/tests/test_batch_b.py` | **33 checks / PASS** |
| Batch D's three PARTIAL files | **0 silent drops**; 24/26 declarations in the symbol table, the other 2 represented outside it (`class_name` field, `ENUM_NOT_INTERPRETED`) |
| 34 formal files (stored Batch B snapshot vs now) | **6 files gained declarations, 0 lost** |
| Pinned corpus (7 059 `.gd` files) | COMPLETE 5 846 · PARTIAL 1 129 + 82 · **0** false unsupported from string bodies |
| Protected data | **unchanged** (0 files touched, manifest hashes below) |

---

## B. Prerequisite Verification

- `HEAD = d64b1cd5b576a44dcfafd7becbb2d2a7f1fd6a84` (unchanged, no Git write performed).
- Batch D report `.ai/context/PHASE_1_76_D_MANUAL_EVIDENCE_REVIEW.md` present with
  `UNSUPPORTED_CONSTRUCT_REPORTING_INCOMPLETE`.
- Batch D's declaration table for the three PARTIAL files: 26 declarations, 3 missing,
  2 missing **unflagged** (`expand_to`, `title_label`), 1 missing but flagged (`enum Operators`).
- The three pinned sources and the Reference copies used by the formal records are readable and
  digest-consistent (reference copy = pinned source plus a 3-line header).

---

## C. Input Inventory

| Input | Role |
|---|---|
| `.ai/tools/learning/gd_parse.py` | the parser whose coverage report was audited and hardened |
| `.ai/tools/external_code/external_code_understanding.py` | the adapter that turns parser output into a formal analysis record (owner of record-line projection) |
| `.ai/learning/external_code/evidence_review/phase_1.76/partial_coverage_review.json` | Batch D's 26-declaration table and `UNSUPPORTED_CONSTRUCT_REPORTING_INCOMPLETE` |
| `.ai/learning/external_code/reanalysis/parser_1.76/manifest.json` | the **pre-Batch-E** coverage snapshot for the 34 formal files (used as the "before" state) |
| `code_library/sources/**` + `code_library/references/**` | pinned sources and their record-line copies |
| `.ai/tools/learning/tests/test_gd_parse.py` | existing Batch B suite (contains one assertion naming the retired code) |

`HEAD`'s `gd_parse.py` predates the 1.75 coverage fields entirely (no `coverage` attribute), so the
authoritative "before" state is the stored Batch B snapshot, not `git show HEAD:`. This is stated as
a limitation in section N.

---

## D. Root Cause Analysis

1. **Silent drop (top-level declarations).** `DECL_RE` / `DECL_SHAPED_RE` required the declaration
   keyword to follow only known modifiers. `export(String) var x` (Godot 3 parenthesised export) and
   bare `onready var x := $Node` matched neither, so the line was skipped by the declaration loop
   and then excluded from the residual scan (which only looked for lines *starting* with a keyword).
2. **False positive (`setget`).** A separate whole-file loop set
   `LEGACY_SETGET_NOT_INTERPRETED` whenever `" setget "` appeared in the line, independently of
   whether `DECL_RE` had captured the declaration. Both outcomes were reported at once.
3. **Coordinate mixing.** Constructs carried a single `line` that was produced from the analysed
   file. Formal records analysed the **Reference** copy (3 header lines), so `line` was a
   record-space number while Batch D compared it with **commit** lines. The adapter additionally
   hard-coded `text.splitlines()[3:]` instead of deriving the offset.
4. **Residual blind spot.** A top-level line containing a declaration keyword but not starting with
   it (`wobble var x = 1`) produced `syntax_coverage_status=COMPLETE`.

---

## E. Changes to `gd_parse.py`

**Grammar (capture, not silence)**

- `VAR_MODIFIERS` / `FUNC_MODIFIERS` plus `VAR_MOD_PREFIX` / `FUNC_MOD_PREFIX`; `static`, `onready`,
  `export`, Godot 3 RPC modifiers (`remote`, `master`, `puppet`, `remotesync`, `mastersync`,
  `puppetsync`) are recognised prefixes of `var` / `func`.
- `LEGACY_EXPORT_RE` for `export(Type) var x` and bare `export var x`; `export_syntax` records
  `LEGACY_PARENTHESISED` / `LEGACY_BARE`; the exported type is taken from the hint when it is a
  single type name, and never invented otherwise.
- `FUNC_START_RE` / `CLASS_START_RE` / `ENUM_START_RE` so `opens_property` cannot swallow a function,
  inner class or enum header.
- `_split_legacy_setget` splits only a `setget` token found outside string literals; the declaration
  body is captured first, the suffix afterwards.
- `_multiline_string_lines` marks `"""` / `'''` regions; residual scans skip them.

**Coverage report**

- Every construct is built by `_construct` and carries `line_space`, `analysis_line`, `extent`
  (`NOT_INTERPRETED` / `PARTIALLY_INTERPRETED`), `declaration_gap`, `reason`, optional `name`,
  `detail`, and `predecessor_code`.
- `LEGACY_SETGET_NOT_INTERPRETED` → `LEGACY_SETGET_WIRING_NOT_MODELED` (predecessor recorded), and
  only when the accessor names were actually parsed; an unreadable suffix becomes
  `LEGACY_SETGET_SYNTAX_UNRECOGNISED` (`NOT_INTERPRETED`).
- `analysis_completeness` is `DECLARATION_GAPS` iff an `unrecognized_declaration` or a
  `declaration_gap` construct exists, else `FULL`. Field meaning unchanged; the derivation is now
  correct for enums and inner classes.
- `line_coordinates` states that the parser only knows `ANALYZED_FILE` and that `source_line` /
  `record_line` are `NOT_MAPPED_BY_PARSER`; `project_construct_lines()` performs the projection
  without rewriting `line`, and leaves unknown spaces `None`.
- `coverage_derivation` publishes the authoritative field, the rule, and counts that are asserted to
  agree with the reported lists.
- `_normalise_constructs` gives deterministic ordering and removes duplicate `(code, line, name)`.

**Residual scan** now also flags a top-level line that contains a declaration keyword outside
strings (`DECLARATION_KEYWORDS`), skipping `HARMLESS_TOP_LEVEL` statements and triple-quoted blocks,
and records `declaration_keyword` / `declaration_gap` / `extent` / `reason` on each entry.

---

## F. Changes to the Adapter

- `_reference_offset(reference_text, source_text)` derives the leading-line offset (0–12) by
  aligning the pinned source body inside the Reference copy; the hard-coded `[3:]` is gone.
- `_coverage_with_coordinates` projects `unsupported_constructs` and `unrecognized_declarations` via
  `project_construct_lines(source_offset=…, record_offset=…)` and replaces `line_coordinates` with
  `line`/`analysis_line` = `ANALYZED_FILE`, `source_line` = `PINNED_SOURCE`, `record_line` =
  `ANALYSIS_REFERENCE`, plus `reference_offset` and `mapping_status` (`ALIGNED` / `UNALIGNED`).
- `_base_record` stores `reference_offset` and derives `source_consistent` from the same offset
  instead of assuming three header lines.

Real-pair verification (`board_member_button.gd`, Reference vs pinned Source):

```
offset: 3
coords: line=ANALYZED_FILE  analysis_line=ANALYZED_FILE
        source_line=PINNED_SOURCE  record_line=ANALYSIS_REFERENCE
        reference_offset=3  mapping_status=ALIGNED
LEGACY_SETGET_WIRING_NOT_MODELED line=9  source_line=6  record_line=9  PARTIALLY_INTERPRETED  model
LEGACY_SETGET_WIRING_NOT_MODELED line=10 source_line=7  record_line=10 PARTIALLY_INTERPRETED  board
unrecognized: []
```

---

## G. New Tests

`test_gd_parse.py` (existing suite, one assertion migrated): `N05` now asserts that the legacy
`setget` declaration **is captured**; `N05b` asserts the wiring is reported as partly modelled with
`predecessor_code`; the inner-class check moved to `N05c`.

`.ai/tools/learning/tests/test_coverage_reporting.py` (new, 36 checks, grammar-level, no hard-coded
real variable names):

| Group | Checks |
|---|---|
| Capture | `E01–E05` `export(Type)` / bare `export` / bare `onready` / captured-and-not-downgraded |
| Partial vs absent | `E06–E13` export hint args, RPC modifier, `setget` with and without accessors, retired code never active, `setget` inside strings |
| Real misses | `E14–E18` malformed top-level declaration, multi-line-string false positive, enum, inner class |
| Coordinates | `E19–E22` space stated per construct, no invented mapping, projection preserves `line`, unknown stays `None` |
| Consistency | `E23–E26` PARTIAL not overwritten, derivation counts agree, determinism, supported declarations never leak |
| Pinned samples | `R00–R09` Batch D's three files and the Reference/Source coordinate cross-check |

The 12 required guarantees are covered 1:1: supported declarations never enter
`unsupported_constructs` (`E26`, `R02`); enum and `setget` are reported accurately (`E09–E12`,
`E17`, `R03`); an already captured `setget` is not marked unparsed (`E09`, `E11`); lines match the
commit (`R03`, `R06`, `R09`); coordinate spaces are not mixed (`E19–E22`, `R09`); no construct
contradicts the symbol table (`E24`); PARTIAL is not upgraded (`E23`); FULL does not override
PARTIAL (`E07`, `R04`); output is deterministic (`E25`).

---

## H. Behaviour Differences

**Batch D's three PARTIAL files (pinned sources, commit lines)**

| File | Before | After |
|---|---|---|
| `board_member_button.gd` | `expand_to` absent; `setget` → `LEGACY_SETGET_NOT_INTERPRETED` | `expand_to` export `String` L4; `model` L6 / `board` L7 `LEGACY_SETGET_WIRING_NOT_MODELED`; PARTIAL / FULL |
| `board_card.gd` | `title_label` absent; `setget` → `LEGACY_SETGET_NOT_INTERPRETED` | `title_label` onready var L6 (`$Title`); `model` L4 partly modelled; PARTIAL / FULL |
| `blackboard_compare.gd` | enum flagged; other declarations captured | unchanged reporting (`ENUM_NOT_INTERPRETED` L7), PARTIAL / `DECLARATION_GAPS`; 2 of 9 table rows live outside `declarations` (`class_name` field, enum construct) |

**34 formal files, stored Batch B snapshot → current parser (read-only comparison)**

- Status transitions: COMPLETE→COMPLETE 27, PARTIAL→PARTIAL 4, **COMPLETE→PARTIAL 2**.
- Declarations: **6 files gained, 0 lost**.
  - `Stats.gd` + `max_health`/`strength`/`defense` (previously dropped `export(Type) var` lines).
  - `board_member_button.gd` + `expand_to`, `board_card.gd` + `title_label`.
  - `DamageSource.gd` + `damage`.
  - `Door.gd` + `ACTIVE_AT_START`/`map_path`, `EffectParameterSelector.gd` + 11 exported properties.
- Construct codes changed on 5 files; the `COMPLETE→PARTIAL` pair is
  `LEGACY_EXPORT_HINT_ARGS_NOT_INTERPRETED` — legacy `export(Type, range…)` hint arguments were
  silently unimplemented and are now reported as partial (declaration retained, `FULL` completeness).
- The three former `LEGACY_SETGET_NOT_INTERPRETED` files now report
  `LEGACY_SETGET_WIRING_NOT_MODELED`.

**Pinned corpus (7 059 `.gd` sources, `code_library/sources`)**

```
COMPLETE / FULL                 5 846
PARTIAL  / DECLARATION_GAPS     1 129
PARTIAL  / FULL                    82   (only accessor wiring / hint args / RPC modifiers)
unrecognized declaration entries  795
```

False-positive audit of the new residual rule: **0** entries whose line does not start with a
declaration keyword, **0** entries inside a `"""` block (before the string guard, 14 keyword-only and
16 in-string entries were false positives; both classes are now excluded).

---

## I. Known Unsupported Constructs (reported, not silently dropped)

| Code | Extent | Meaning |
|---|---|---|
| `ENUM_NOT_INTERPRETED` | NOT_INTERPRETED, gap | enum declared, no symbol or member available |
| `INNER_CLASS_NOT_INTERPRETED` | NOT_INTERPRETED, gap | inner class body absent from the symbol table |
| `LAMBDA_NOT_ANALYZED` | NOT_INTERPRETED | anonymous body captures/effects unknown |
| `LEGACY_SETGET_SYNTAX_UNRECOGNISED` | NOT_INTERPRETED, gap | `setget` present, accessor list unreadable |
| `LEGACY_SETGET_UNATTRIBUTED` | NOT_INTERPRETED | `setget` on a line not captured as a declaration |
| `LEGACY_SETGET_WIRING_NOT_MODELED` | PARTIALLY_INTERPRETED, no gap | declaration + accessor names captured, implicit call not modelled |
| `LEGACY_EXPORT_HINT_ARGS_NOT_INTERPRETED` | PARTIALLY_INTERPRETED, no gap | declaration + type captured, extra hint arguments not modelled |
| `LEGACY_RPC_MODIFIER_NOT_INTERPRETED` | PARTIALLY_INTERPRETED, no gap | function captured, network-authority semantics not modelled |
| `unrecognized_declarations[]` | NOT_INTERPRETED, gap | declaration-shaped top-level line the grammar could not capture |

Observed in the corpus, all reported rather than dropped: Godot 4 inner classes with
`class X extends Y:`, multi-line `func` signatures with nested parentheses/default arguments,
Godot 4 inline property setters `var x: T: set = f`, unnamed `enum { … }`.

---

## J. Data Integrity and Non-Mutation

`Batch E` first edit mtime was used as the cut-off; **no protected file is newer than it**.

| Path | Files | SHA-256 (manifest of path + content digests) |
|---|---|---|
| `.ai/learning/external_code/analysis` (34 formal) | 34 | `8202f322fe5cb166f3a2aaaf15617f53a708077a6794a8dc6a60be33e16b9a0c` |
| `.ai/learning/external_code/feature_links` (150 linkage) | 150 | `ce7edc060a5d7917712d8ea0292069d4019c95a9bb52b3e48c935724faa48cd4` |
| `.ai/learning/external_code/reanalysis` (Batch B workspace) | 191 | `53859cb96641bfae9ef146bae262a048b391d28ee0af30be656450e0e666da9c` |
| `.ai/learning/external_code/reconciliation` | 1 | `66ba91f05f00325b74d71f2029ee80210c661101d56cfd433e4d2d205d9dfb62` |
| `.ai/learning/external_code/evidence_impact` (Batch C) | 8 | `c1abd1ba2150818abe3b60732ab0695de316a759a46e8b80f5d351c2a8386695` |
| `.ai/learning/external_code/evidence_review` (Batch D) | 6 | `0220a4840cd1224a957a87d9a419c0856ba05eb081cf485c966a248423730be6` |
| `.ai/learning/candidate_workspace` | 3 | `b991d4f547266ea60980f1cf781ae735c5a8e9014699aa79662fca4c19f4491d` |
| `code_library` (sources + references) | 13 807 | `87af1d7f1ba7abce6cf127d28bc1ed2a35bdd3debc78880c1c5ab09a560606f5` |

No Batch B re-analysis was run, no Symbol Diff rebuilt, no formal Analysis/Linkage/Candidate/Seed
Eligibility rewritten, no Review Queue entry created, no Git write performed.

**Changed source files (current digests)**

| File | SHA-256 | Git |
|---|---|---|
| `.ai/tools/learning/gd_parse.py` | `f56aa340e531dc080bcdf8314d18361ada59214c59b0aab6aa5b888fac58e19b` | `M` |
| `.ai/tools/external_code/external_code_understanding.py` | `fa30686a906dbd6f982ba4591577dbe7f3f7774cb3fef90571637f3174625a4c` | `??` |
| `.ai/tools/learning/tests/test_gd_parse.py` | `fa6edb36349404890ba1ba8b4d39f1fa35171120bd0cca5c7ccc14a58ce6273b` | `??` |
| `.ai/tools/learning/tests/test_coverage_reporting.py` | `82a0e4875e65f6c5a36d56d93092b4b78e603632e894abf4305cfdde9fe01dec` | `??` |

The adapter and the existing test file were already untracked in this working tree before Batch E;
`gd_parse.py` is tracked and modified, and that diff also contains the earlier uncommitted 1.75
coverage work — Batch E's delta is a subset of that diff, not the whole of it.

---

## K. Unresolved Issues

1. **Parser build identity is not bumped.** `PARSER_VERSION` stays `1.75`, because `_analysis_id`
   embeds the version and would change record identity. Behaviour now differs from any stored
   `gd_parse@1.75` record, so a future authorized re-analysis must treat build identity explicitly.
2. **Stored formal records still carry the old codes.** The 34 analyses were not rewritten by
   design; `LEGACY_SETGET_NOT_INTERPRETED` remains in their snapshots until a future authorized
   re-analysis.
3. **1 129 corpus files now show `DECLARATION_GAPS`.** These are pre-existing grammar gaps that were
   previously invisible; they are honest reports, not new parser regressions (0 declarations lost).
4. **795 unrecognized declarations** are dominated by four Godot 4 patterns listed in section I.
   Capturing them is a parser-feature decision outside Batch E.
5. **Two dangling symlinks** in `code_library/sources/foxssake__netfox/gd/addons/` (`nohub.gd`,
   `trimsock.gd`) raise `ParseError`; they were skipped in the corpus probe and are unrelated.
6. **`_reference_offset` only searches 0–12 leading lines.** A Reference copy with a longer header
   reports `UNALIGNED` rather than a wrong offset.

---

## L. Remaining Limitations

- The parser remains a regex/line parser: no AST, no type inference, no semantic validation.
- `analysis_completeness=FULL` means "no declaration gap was detected", not "the file is fully
  understood"; `syntax_coverage_status=PARTIAL` remains the authority.
- `line` is still the analysed-file line and was deliberately not redefined; only the new fields
  describe other spaces. Consumers that keep treating `line` as a commit line will still be wrong —
  they must use `source_line` or `project_construct_lines()`.
- No real-file test asserts `mapping_status=UNALIGNED`; only the `None`-preserving projection is
  unit-tested (`E22`).
- Not verified: any formal record regeneration through the adapter end-to-end (would write formal
  data); Windows path edge cases beyond this machine.

---

## M. Git State

```
HEAD  d64b1cd5b576a44dcfafd7becbb2d2a7f1fd6a84
 M  .ai/tools/learning/gd_parse.py
 ?? .ai/tools/external_code/external_code_understanding.py
 ?? .ai/tools/learning/tests/test_gd_parse.py
 ?? .ai/tools/learning/tests/test_coverage_reporting.py
```

No commit, no push, no staging performed. `.ai/tmp/` probe scripts used for the measurements are
gitignored.

---

## N. Test and Verification Evidence

| Command | Exit | Result |
|---|---|---|
| `python .ai/tools/learning/tests/test_gd_parse.py` | 0 | 36 checks, 0 failures |
| `python .ai/tools/learning/tests/test_coverage_reporting.py` | 0 | 36 checks, 0 failures |
| `python .ai/tools/learning/tests/test_source_analysis.py` | 0 | 17 checks, 0 failures |
| `python .ai/tools/external_code/tests/test_batch_b.py` | 0 | 33 checks, PASS |

Verified, not assumed: sample declarations and lines printed from the pinned files; adapter
projection printed from a real Reference/Source pair; before/after computed against the stored Batch
B snapshot for the 34 formal files; corpus probe over all 7 059 pinned `.gd` sources; protected-data
manifests plus mtime cut-off.

Not done: no re-analysis, no adapter run that writes a record, no `git` write.

---

## O. Final Verdict

**Verdict: `PASS_WITH_LIMITATIONS`**

The three named defects are closed, and the fourth instance of the same class (a declaration-shaped
line reported as `COMPLETE`) was found and closed with them. Supported declarations no longer enter
`unsupported_constructs`; captured `setget` declarations are no longer called unparsed; line numbers
now state their space and the adapter projects them from a derived offset. The limitations are
build-identity/versioning and stored-record staleness, both of which require a separately authorized
re-analysis to resolve — they are not reporting defects.

**Readiness: `READY_FOR_FUTURE_DESIGN_REVIEW`**

Ready to be reviewed as the input to a future design decision about re-analysis, parser build
identity and Semantic Linkage Tier. This does **not** state that formal Evidence Integration is
ready: the 34 formal analyses still carry pre-Batch-E coverage text, 4 analyses remain without
linkage, and Seed Policy gating is still an open design question.

---

## P. Recommended Follow-up (not executed)

1. Decide parser build identity separately from `PARSER_VERSION` (for example an explicit
   `parser_build_identity` field), so coverage semantics can change without record identity drift.
2. Authorize one controlled re-analysis of the 34 formal files and diff it against the Batch B
   snapshot; the 6 gain / 0 loss / 2 COMPLETE→PARTIAL result is the expected shape.
3. Decide whether Godot 4 inner classes, inline property setters, unnamed enums and nested
   default-argument signatures are in scope; today they are reported, not parsed.
4. Update committed record consumers to read `source_line` / `record_line` instead of `line`.
5. Keep the 1 129 `DECLARATION_GAPS` files as a backlog metric, not as an integration blocker.
