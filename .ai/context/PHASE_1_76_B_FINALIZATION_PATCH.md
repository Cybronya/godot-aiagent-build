# Phase 1.76 — Batch B Finalization Patch

Report-only finalization of Batch B. No parser run, no reanalysis, no workspace
write, no evidence/linkage/candidate change, no git write.

Authority: `.ai/context/PHASE_1_76_B_CONTROLLED_FULL_REANALYSIS.md`,
`.ai/learning/external_code/reanalysis/parser_1.76/`,
`.ai/learning/external_code/reconciliation/phase_1.76/inventory.json`.

---

## 1. Baseline

| Item | Value |
|---|---|
| Project root | `F:/Godot_v4.7-stable/game` |
| Branch / HEAD | `master` / `d64b1cd5b576a44dcfafd7becbb2d2a7f1fd6a84` (unchanged) |
| Staged | 0 |
| Modified | 34 (pre-existing, untouched) |
| Untracked | 139 before this patch (Batch A report, Batch B tool, Batch B report) |
| Deleted | 0 |
| Batch B workspace | present, 162 files |
| Batch B report | present |
| Parser build identity (recorded, re-read not rebuilt) | `gd_parse@1.75+build:6b74a6cd20a06033` |
| Identity source | `manifest.json → parser_build_identity`; parser/adapter digests identical to the recorded values |

The parser identity was read from the existing records and confirmed unchanged
(parser and adapter file digests match the snapshot); it was **not** recomputed by
running the parser, and no parser file was modified.

Pre-patch digest snapshot: 383 files (Batch B workspace 162, Phase 1.75 workspace
29, 34 analysis, 150 linkage, candidate workspace, Batch A inventory, parser,
adapter, tools, this report) — recorded in `.ai/tmp/phase176b_snapshot.json`.

---

## 2. Symbol Diff Accounting Audit

Recomputed from the 29 original analysis records and the 29 reanalysis records in
the workspace, using identity `(group, name)` plus a name-level pass for
structural changes. No summary figure from the earlier report was reused.

### 2.1 Result

| Metric | Earlier report | Recomputed |
|---|---:|---:|
| Original symbols (29 records) | 135 | **135** |
| Reanalysis symbols (29 records) | 179 | **179** |
| Matched (same group + name) | not stated | **134** |
| Added (genuinely new) | 45 | **44** |
| Removed | 0 | **0** |
| Structurally reclassified | 1 | **1** |
| Net change | +44 | **+44** |
| Diff-listed addition entries | 45 | **45 = 44 new + 1 reclassified** |

### 2.2 Counting rules

* **Matched** — the same `(declaration group, name)` exists in both records.
  Declaration kind is compared implicitly through the group.
* **Added** — a reanalysis symbol with no counterpart of the same name anywhere in
  the original record. This is the only dimension counted as growth.
* **Removed** — an original symbol with no counterpart of the same name in the
  reanalysis. Only these would be "lost symbols".
* **Reclassified** — same name and same source line, but a different declaration
  group/kind. Counted in its own dimension; its new-side entry also appears in the
  diff's `symbols_added` list, which is why that list totals 45.
* Never counted by name alone: a name present in two different groups within one
  file would be treated as two identities.

### 2.3 Verifiable identities

```
Original   = Matched + Reclassified + Removed     135 = 134 + 1 + 0
Reanalysis = Matched + Reclassified + Added       179 = 134 + 1 + 44
Net change = Added - Removed                        44 = 44 - 0
Listed additions        = Added + Reclassified       45 = 44 + 1
```

Per-record check: every one of the 29 records satisfies
`|original| + added − removed == |reanalysis|`. The only record with a
non-trivial decomposition is `ext-7d7933a2343f52d0` (`ui_life_bar.gd`):
original 4, reanalysis 11 = 3 matched + 1 reclassified + 7 new; its diff lists
8 additions because the reclassified `target_value` also appears on the new side.

### 2.4 Conclusion

The earlier report's numbers were arithmetically consistent but presented two
different bases in adjacent columns (`Added 45` = listing count, `Net +44` = net
symbols). The corrected presentation is §2.1. **Accounting status:
`SYMBOL_DIFF_ACCOUNTING_RESOLVED`**; no diff file, manifest entry or analysis
record was modified — only the report.

---

## 3. Structural Reclassification Audit: `ui_life_bar.gd::target_value`

| Aspect | Original | Reanalysis |
|---|---|---|
| Record | `ext-7d7933a2343f52d0` (`gdquest-demos/godot-open-rpg`) | same |
| Identity | `variables:target_value` | `properties:target_value` |
| Declaration kind | not recorded (pre-1.75 schema) | `PROPERTY` |
| Source line | 18 (record) / 15 (commit) | 18 (record) / 15 (commit) |
| Value | `"0.0:"` — trailing property colon absorbed by the old regex | `"0.0"` |
| Initializer | not recorded | `INFERRED` (`:=`) |
| Getter / setter | none visible | `has_setter=true`, `has_getter=false` |
| Setter range | not recorded | line 19 (record) / 16 (commit), `param=new_value`, `end_line=37` |
| Diff events | `symbols_removed = []` | `symbols_reclassified` (1 entry), new side in `symbols_added` |
| Unexplained differences | — | `[]` |

Source (reference copy):

```
18: var target_value := 0.0:
19:     set(new_value):
```

Verdict: a structural correction, not a loss. It is counted once as a
reclassification and once on the new side of the added list; it is never counted
in `symbols_removed`, and `unexplained_differences` is empty for that record.

---

## 4. Coverage Limitation Review

Distribution across the 29 reanalysed records (re-read from the workspace):

| Field | Value |
|---|---|
| `parse_execution_status` | `PARSED` 29 |
| `syntax_coverage_status` | `COMPLETE` 26 · `PARTIAL` 3 |
| `analysis_completeness` | `FULL` 29 |
| `unrecognized_declarations` | 0 |
| `unsupported_constructs` | 3 records |

### 4.1 The three `PARTIAL` records

| Record | Repository | Commit | Source path | Unsupported constructs |
|---|---|---|---|---|
| `ext-55aef2d453370c1b` | `bitbrain/beehave` | `fe589153fa780a3f88989578ceb5f539afffb7c2` | `addons/beehave/nodes/leaves/blackboard_compare.gd` | `ENUM_NOT_INTERPRETED` line 10 (`Operators`) |
| `ext-9e62ed2e3dec8164` | `alfredbaudisch/Godello` | `4458a143644fbadec23ae0cee99578ad3b811eb8` | `scripts/board_member_button.gd` | `LEGACY_SETGET_NOT_INTERPRETED` lines 9 and 10 |
| `ext-fffa637657ffede1` | `alfredbaudisch/Godello` | `4458a143644fbadec23ae0cee99578ad3b811eb8` | `scripts/board_card.gd` | `LEGACY_SETGET_NOT_INTERPRETED` line 7 |

Parser behaviour in each case:

* **enum** — the enum name and line are reported as an unsupported construct;
  members are not captured as symbols. The rest of the file parses normally.
* **legacy `export(...) var … setget`** — the declaration is not matched by the
  modern declaration grammar and is reported as `LEGACY_SETGET_NOT_INTERPRETED`;
  the variable, its type and its `setget` accessors are **absent from `symbols`**.

### 4.2 Field semantics kept distinct

* `parse_execution_status = PARSED` only means the scan ran to completion; it says
  nothing about grammar coverage.
* `syntax_coverage_status = PARTIAL` means at least one construct in the file is
  outside the supported grammar (the three cases above).
* `analysis_completeness = FULL` means no declaration-shaped line was *silently*
  dropped: every such line was either captured or explicitly reported. In the two
  legacy-`setget` files the missing declarations are reported, so completeness is
  `FULL` while coverage is `PARTIAL`.

Therefore `PARSED` ≠ complete coverage, and `FULL` ≠ `COMPLETE`; for these three
files the symbol table is **not** a complete declaration list, and that limitation
is preserved for downstream review. No unsupported construct was repaired here.

---

## 5. Verdict Correction

| Report section | Before | After |
|---|---|---|
| Executive summary | implied full success | states 29/29 parsed, 26/29 complete coverage, verdict `PASS_WITH_LIMITATIONS` |
| Final verdict | `PASS` | **`PASS_WITH_LIMITATIONS`** |
| Batch C readiness | "Ready" prose | **`READY_FOR_BATCH_C_WITH_RESTRICTIONS`** |

Rationale: execution, provenance, determinism, idempotency and data integrity all
pass, so the batch is not a failure; but 3 of 29 records lack complete syntax
coverage and one symbol changed structural class, so a plain `PASS` would
overstate the result. Per the Batch B acceptance definitions, that combination is
`PASS_WITH_LIMITATIONS`.

---

## 6. Report Changes

Only `.ai/context/PHASE_1_76_B_CONTROLLED_FULL_REANALYSIS.md` was modified:

1. **A. Executive Summary** — added the 134/1/44 decomposition and the
   execution-vs-coverage distinction.
2. **K. Analysis Diff Summary** — clarified the 45-entry listing.
3. **K.1 Symbol Diff Accounting Audit** *(new)* — recomputed table, counting
   rules, verifiable identities, per-record check, accounting status.
4. **K.2 Structural Reclassification** *(new)* — full `target_value` audit.
5. **N.1 The three status fields mean different things** *(new)*.
6. **N.2 The three PARTIAL records** *(new)* — repository/commit/path/constructs.
7. **V/W** — verdict corrected to `PASS_WITH_LIMITATIONS` with explicit
   pass/limit split.
8. **X** — readiness changed to `READY_FOR_BATCH_C_WITH_RESTRICTIONS` with three
   named restrictions; superseded readiness note restructured into inputs list.
9. **Y. Finalization Record** *(new)* — points to this patch.

New document: `.ai/context/PHASE_1_76_B_FINALIZATION_PATCH.md` (this file).

No workspace file was added or changed: the workspace remains 162 files so its
existing `idempotency/verification.json` (162 → 162) stays accurate.

---

## 7. Data Integrity

Digest comparison before and after the patch (383-file snapshot):

| Object | Expected | Observed |
|---|---|---|
| Batch B report | allowed to change | changed (only object changed) |
| Batch B workspace (162 files) | 0 changes | 0 |
| `manifest.json`, `preflight.json`, `reanalyzed/`, `diff/`, `validation/`, `deterministic_runs/`, `idempotency/`, `reports/` | 0 changes | 0 |
| Original analysis records (34) | 0 changes | 0 |
| Formal linkage (150) | 0 changes | 0 |
| Candidates (2 + workspace manifest) | 0 changes | 0 |
| Phase 1.75 workspace (29) | 0 changes | 0 |
| Batch A inventory and audit tool | 0 changes | 0 |
| `gd_parse.py` / `external_code_understanding.py` / schema | 0 changes | 0 |
| Feature metadata / index / graph / seed policy | 0 changes | 0 |
| Deleted files | 0 | 0 |
| New files | 1 (this patch) | 1 |

Parser was not executed; no reanalysis was re-run; no diff was regenerated.

---

## 8. Git Status

| | Before | After |
|---|---|---|
| Branch / HEAD | `master` / `d64b1cd5…` | unchanged |
| Staged | 0 | 0 |
| Modified | 34 | 34 |
| Untracked (porcelain) | 139 | 140 (+1 patch document) |

The Batch B report's own §B table shows `137 → 138` because it was measured
before that report file itself was written; the measured pre-patch value for this
finalization was 139.
| Deleted | 0 | 0 |

Read-only git usage only (`rev-parse`, `status`). No commit, push, fetch, pull,
checkout, reset, clean, rebase or cherry-pick.

---

## 9. Final Result

Accounting: `SYMBOL_DIFF_ACCOUNTING_RESOLVED` (135 = 134 + 1 + 0;
179 = 134 + 1 + 44; net +44; diff listing 45 = 44 + 1).

Coverage: 26 `COMPLETE`, 3 `PARTIAL` with named constructs; `PARSED` and `FULL`
explicitly not equated with complete coverage.

Verdict: **`PASS_WITH_LIMITATIONS`**. Readiness:
**`READY_FOR_BATCH_C_WITH_RESTRICTIONS`** (approval required separately).

Data integrity: only the report and this patch changed; workspace, historical and
formal artefacts untouched; 0 deletions.

**Finalization result: `FINALIZATION_PASS_WITH_LIMITATIONS`**
