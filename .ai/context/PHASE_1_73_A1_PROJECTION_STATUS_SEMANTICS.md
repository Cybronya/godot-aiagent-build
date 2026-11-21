# Phase 1.73 — Batch A.1
# Projection Status Semantics Audit & Clarification

状态：**PASS**

阶段模式：Batch A.1 only。未进入 Batch B，未建立 External Analysis Linkage，未进行 Similarity 分析，未创建 Candidate / Admission Gate，未提交 Git。

---

## A. Baseline

执行前重新检查：

```text
Project Root:       F:/Godot_v4.7-stable/game
Branch:             master
HEAD:               d64b1cd5b576a44dcfafd7becbb2d2a7f1fd6a84
Staged Files:       0
Modified Files:     29
Untracked Files:    171（本报告写入前）
```

与 Batch A 报告一致：

- `master`、HEAD、staged 状态一致。
- Modified 仍为 **29**，均为 Batch A 之前已存在的修改。
- Untracked 171 中包含 Phase 1.73 Preflight、Batch A 实现、测试、5 个 Projection 和 Batch A 报告。
- 五个 Projection 的 `projection_status`、`analysis_references`、`behavior_evidence`、`evidence_counts` 与 Batch A 报告一致。
- 未发现需要停止审计的基线冲突。

审计前五个 Projection 均使用：

```text
extractor_version = phase-1.73-a/1
```

且都不存在顶层 `verification_status`。

---

## B. Audit Findings

### B.1 Projection Status 判定逻辑

当前生成函数：

```python
def _projection_status(evidence_counts, limitations):
    if evidence_counts.get("CONFLICTED", 0):
        return "CONFLICTED"
    if evidence_counts.get("UNSUPPORTED", 0):
        return "UNSUPPORTED"
    if evidence_counts.get("PARTIAL", 0) or evidence_counts.get("MISSING", 0):
        return "PARTIAL"
    return "COMPLETE"
```

结论：

| 检查项 | 结论 |
|---|---|
| COMPLETE 条件 | 不存在 CONFLICTED / UNSUPPORTED / PARTIAL / MISSING 证据 |
| PARTIAL 条件 | 存在 PARTIAL 或 MISSING 证据 |
| CONFLICTED 条件 | 存在 CONFLICTED 证据 |
| UNSUPPORTED 条件 | 存在 UNSUPPORTED 证据 |
| 是否依赖 Source Analysis 的 COMPLETE | **否**。Source Analysis 只影响 behavior evidence 的状态映射 |
| 是否要求所有证据均为 EXTRACTED | **否**。DECLARED、NOT_APPLICABLE 等状态不会阻止 COMPLETE |
| 是否把 NOT_APPLICABLE 计入缺失 | **否**。NOT_APPLICABLE 不计入 PARTIAL / MISSING |
| 是否存在无来源依据的 COMPLETE | **没有发现**。每个 section 都有来源引用或明确的 NOT_APPLICABLE 证据 |

重要语义：

```text
projection_status = COMPLETE
```

只表示：**当前 Projection 所适用的数据已完整投影，没有未解决的 PARTIAL/MISSING/CONFLICTED/UNSUPPORTED 证据。**

它不表示：

- Feature 已通过测试；
- Feature 已通过运行时验证；
- 源码分析一定存在；
- 所有 behavior 都已实现；
- 所有证据都是 EXTRACTED。

`blackboard` 是典型例子：没有 Behavior Contract、没有 Source Analysis，behavior 证据为 `NOT_APPLICABLE`，因此 Projection 仍可为 COMPLETE。这是正确的“适用数据完整”，不是“源码已验证”。

### B.2 Evidence Status 判定逻辑

每条证据只使用以下状态：

```text
DECLARED
EXTRACTED
PARTIAL
MISSING
NOT_APPLICABLE
UNSUPPORTED
CONFLICTED
```

实际规则：

- `DECLARED`：来自 metadata、Graph、测试声明或人工定义。
- `EXTRACTED`：从真实源码成功提取，带文件、符号、行号和 Digest。
- `PARTIAL`：只有部分证据；Source Analysis 的 `PARTIAL` 和 `SOURCE_ENTRY_AMBIGUOUS` 都映射到这里。
- `MISSING`：应有但未找到，例如有 behavior contract 但没有 Source Analysis record。
- `NOT_APPLICABLE`：该 Feature 不适用该项检查，例如没有 Behavior Contract。
- `UNSUPPORTED`：当前 Parser 或数据结构不支持。
- `CONFLICTED`：证据之间存在明确矛盾。

结论：Evidence Status 只描述**单条证据**，不会被写入或替代 `projection_status`，也没有把 `DECLARED` 自动升级为 `EXTRACTED`，或把 `PARTIAL` 自动升级为 `COMPLETE` 的逻辑。

### B.3 Verification Status 判定逻辑

审计发现的实际缺口：

- 原来只有 `test_evidence[].value.execution_status = NOT_RUN` 和 `validation_evidence[].value.execution_status = NOT_RUN`。
- 原来没有顶层字段明确表示 Feature / Runtime / Behavior 的验证状态。
- 因此下游只读 JSON 时，存在把 `projection_status=COMPLETE` 误读为“Feature 已验证”的风险。

这不是 Projection Status 计算错误，而是**状态表达不完整**。

最小修正：

新增顶层：

```json
"verification_status": {
  "feature_verification_status": "NOT_VERIFIED",
  "test_execution_status": "NOT_RUN",
  "runtime_verification_status": "NOT_VERIFIED",
  "behavior_verification_status": "NOT_VERIFIED",
  "basis": "NO_EXECUTION_EVIDENCE"
}
```

生成逻辑是保守常量，不从 `projection_status`、Source Analysis COMPLETE 或证据数量推断。Batch A.1 没有执行测试或运行时，因此不会生成 `VERIFIED`。

### B.4 五个 Pilot 逐项结果

| Feature | Projection Status | Source Analysis | Behavior Evidence | Test Execution | Runtime Verification | Feature Verification |
|---|---|---|---|---|---|---|
| `health` | PARTIAL | 5 × PARTIAL | 5 × PARTIAL | NOT_RUN | NOT_VERIFIED | NOT_VERIFIED |
| `health_bar` | PARTIAL | 5 × PARTIAL | 5 × PARTIAL | NOT_RUN | NOT_VERIFIED | NOT_VERIFIED |
| `openable_door` | COMPLETE | 1 × COMPLETE | 1 × EXTRACTED | NOT_RUN | NOT_VERIFIED | NOT_VERIFIED |
| `attack_emitter` | PARTIAL | 2 × SOURCE_ENTRY_AMBIGUOUS | 2 × PARTIAL | NOT_RUN | NOT_VERIFIED | NOT_VERIFIED |
| `blackboard` | COMPLETE | 无 | 1 × NOT_APPLICABLE | NOT_RUN | NOT_VERIFIED | NOT_VERIFIED |

#### Case 1：openable_door

允许且已确认：

```text
Projection Status:          COMPLETE
Source Analysis Status:     COMPLETE
Behavior Evidence:          EXTRACTED
Test Execution Status:      NOT_RUN
Runtime Verification:       NOT_VERIFIED
Feature Verification:       NOT_VERIFIED
```

`Source Analysis COMPLETE` 来自静态分析，不等于测试执行完成，也不等于运行时行为已验证。

#### Case 2：blackboard

允许且已确认：

```text
Projection Status:          COMPLETE
Source Analysis:            ABSENT
Behavior Contract:          ABSENT
Behavior Evidence:          NOT_APPLICABLE
Test Execution Status:      NOT_RUN
Runtime Verification:       NOT_VERIFIED
Feature Verification:       NOT_VERIFIED
```

- `COMPLETE` 只表示适用数据已正确投影。
- 没有 Source Analysis 不被解释为“源码已经分析”。
- `NOT_APPLICABLE` 不被解释为“源码验证通过”。
- 没有自动生成 `VERIFIED`。

#### Case 3：health / health_bar

两个 PARTIAL 保持分离并可追溯：

```text
Projection Status = PARTIAL
Source Analysis analysis_status = PARTIAL
Behavior Evidence extraction_status = PARTIAL
```

- Projection PARTIAL 的原因是存在 PARTIAL/MISSING 证据。
- Source Analysis PARTIAL 是原始分析记录的状态，保留在 `analysis_references[].analysis_status`。
- 两者没有被合并成一个不可追溯的布尔值。

#### Case 4：attack_emitter

```text
Projection Status = PARTIAL
analysis_references[].analysis_status = SOURCE_ENTRY_AMBIGUOUS
behavior_evidence[].value.analysis_status = SOURCE_ENTRY_AMBIGUOUS
behavior_evidence[].extraction_status = PARTIAL
```

歧义状态在顶层 analysis references 和 behavior evidence 中都可见，没有被 Projection 的 PARTIAL 状态掩盖。

---

## C. Changes

### C.1 修改文件

```text
修改  .ai/tools/feature_registry/feature_evidence.py
修改  .ai/tools/feature_registry/tests/test_feature_evidence_projection.py
修改  .ai/learning/feature_evidence/health.json
修改  .ai/learning/feature_evidence/health_bar.json
修改  .ai/learning/feature_evidence/openable_door.json
修改  .ai/learning/feature_evidence/attack_emitter.json
修改  .ai/learning/feature_evidence/blackboard.json
新增  .ai/context/PHASE_1_73_A1_PROJECTION_STATUS_SEMANTICS.md
```

### C.2 新增字段

顶层新增：

```text
verification_status.feature_verification_status
verification_status.test_execution_status
verification_status.runtime_verification_status
verification_status.behavior_verification_status
verification_status.basis
```

当前值：

```text
Feature:        NOT_VERIFIED
Test execution: NOT_RUN
Runtime:        NOT_VERIFIED
Behavior:       NOT_VERIFIED
Basis:          NO_EXECUTION_EVIDENCE
```

### C.3 Schema 兼容策略

- `verification_status` 是**可选顶层字段**，旧 Projection 不含该字段仍然通过 Schema Validation。
- 新构建的 Projection 始终包含该字段。
- 没有提升 `schema_version`，避免破坏已有读取方；通过 `extractor_version` 标记为 `phase-1.73-a1/1`。
- 五个现有 Projection 已通过重新构建迁移，不是手工改 JSON。
- 旧 Projection 缺失字段时，不会被补写为空值或伪造 `VERIFIED`。

### C.4 修改原因

1. 原 `projection_status` 本身语义正确，但缺少顶层验证标记。
2. 原 `test_evidence.execution_status=NOT_RUN` 仍保留，未改变。
3. 新增字段只表达“没有执行证据”，不构建 Verification Engine、Test Execution Framework 或运行时验证系统。
4. 五个 Projection 只增加了必要字段，并更新了 `generated_at`、`projection_id`、`content_digest` 和 `extractor_version`。

除这些字段外，五个 Projection 的语义内容与审计前完全一致。剔除 `generated_at`、`projection_id`、`content_digest`、`extractor_version`、`verification_status` 后的 SHA-256：

| Feature | 审计前 | 审计后 |
|---|---|---|
| `health` | `e798ebe4b6386fe3452071dd11c2b548afed71fbffce43701c8da7dfd4fa089f` | 相同 |
| `health_bar` | `2f22ef2a4fb4cb41e70a2a9c248b2e83e8f9b7459ab67e355b0a52886f4e92d9` | 相同 |
| `openable_door` | `92df583f6bc420944baaa01156354cbb39c730469b32b89ecb373b6e1b4b0e38` | 相同 |
| `attack_emitter` | `706ef9c8275dbfb0591e5f14b1c84613077cba2c3eb1eb4caaf54c499f521c0e` | 相同 |
| `blackboard` | `4b3a680462835d1817e053d650faddf610956743c3b56b1f15b0f498187a3777` | 相同 |

---

## D. Tests

### D.1 原有测试

原有 31 项 Projection 测试仍然通过，并包含在下面 41 项完整运行中。

### D.2 新增回归测试

新增 10 项，覆盖：

1. Projection COMPLETE 不代表 Feature VERIFIED。
2. Source Analysis COMPLETE 不代表 Test Execution COMPLETE。
3. 没有 Source Analysis 不代表 Source Analysis COMPLETE。
4. NOT_APPLICABLE 不代表 VERIFIED。
5. `test_evidence.execution_status=NOT_RUN` 不得自动升级。
6. `runtime_verification_status=NOT_VERIFIED` 不得自动升级。
7. Source Analysis PARTIAL 不被 Projection 状态覆盖。
8. SOURCE_ENTRY_AMBIGUOUS 继续保留。
9. 不生成任何 `VERIFIED` 状态。
10. 不含 `verification_status` 的旧 Projection 仍通过 Schema Validation。

### D.3 实际执行命令与结果

```bash
python -m py_compile .ai/tools/feature_registry/feature_evidence.py \
  .ai/tools/feature_registry/tests/test_feature_evidence_projection.py
```

结果：Exit 0。

```bash
python .ai/tools/feature_registry/tests/test_feature_evidence_projection.py
```

结果：

```text
Ran 41 tests
OK
Exit Code: 0
```

```bash
python .ai/tools/feature_registry/tests/test_feature_pipeline.py
```

结果：Exit 0，全部既有检查通过。

```bash
python .ai/tools/learning/tests/test_source_analysis.py
```

结果：Exit 0，17 checks / 0 failures。

```bash
python .ai/tools/validator/check_feature_metadata.py
```

结果：

```text
Checked feature metadata: 31
PASS: 0 error(s), 0 warning(s)
Exit Code: 0
```

```bash
python .ai/tools/feature_registry/feature_evidence.py build --pilot
python .ai/tools/feature_registry/feature_evidence.py check --pilot
```

结果：5/5 构建成功；5/5 FRESH；Exit 0。

测试临时目录已显式指向 F 盘项目内。首次核对时发现既有 `test_source_analysis.py` 在 `.ai/learning/feature_evidence/p165_src_jixiq9v1` 留下了一个临时夹具目录；该目录不属于本阶段允许文件，已删除。最终检查：

```text
TEMP_LEFTOVERS=0
FEATURE_EVIDENCE_ENTRIES=attack_emitter.json, blackboard.json, health.json,
                      health_bar.json, openable_door.json
```

### D.4 失败情况

无失败。

---

## E. Safety

| 检查项 | 结果 |
|---|---|
| 五个 Projection | 已重建；仅新增 `verification_status`，并更新生成时间、Digest、ID、extractor_version |
| Projection 语义内容 | 除上述字段外 SHA-256 与审计前完全一致 |
| Feature Metadata | 未修改 |
| Feature Index | 未修改 |
| Feature Graph | 未修改 |
| Source Analysis Records | 未修改 |
| External Analysis Records | 未修改 |
| Scene Intent / Promote | 未修改 |
| Candidate / Similarity / Admission | 未创建 |
| Git staged / commit / push | 未执行 |
| 非本阶段文件清理/覆盖/恢复 | 未执行 |

工作区检查仍为：

```text
Branch:    master
HEAD:      d64b1cd5b576a44dcfafd7becbb2d2a7f1fd6a84
Staged:    0
Modified:  29（既有修改）
```

A.1 新增报告本身会使 Untracked 数量增加 1。

---

## F. Final Verdict

**PASS**

判定依据：

- `projection_status` 的判定条件已确认：只衡量 Projection 数据完整性，不依赖 Source Analysis COMPLETE，也不要求所有证据都是 EXTRACTED。
- `evidence_status` 只描述单条证据，状态没有被提升或合并。
- 新增的 `verification_status` 明确区分 Feature、测试执行、运行时和 behavior 验证状态。
- 五个 Pilot 的所有状态均可独立解释。
- `openable_door` 保持 `Projection COMPLETE + Source Analysis COMPLETE + Test NOT_RUN + Runtime NOT_VERIFIED`。
- `blackboard` 保持 `Projection COMPLETE + 无 Source Analysis + NOT_APPLICABLE + NOT_VERIFIED`。
- `health` / `health_bar` 的 Projection PARTIAL 与 Source Analysis PARTIAL 保持可追溯的独立字段。
- `attack_emitter` 的 `SOURCE_ENTRY_AMBIGUOUS` 仍然可见。
- 没有任何自动生成 `VERIFIED` 的逻辑。
- 原有 31 项测试与新增 10 项测试全部通过。
- 未修改禁止范围内的数据。

Batch A.1 已完成。是否进入 Batch B 仍需人工验收和明确授权。
