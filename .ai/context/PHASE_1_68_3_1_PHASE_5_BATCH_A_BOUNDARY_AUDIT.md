# Phase 1.68.3.1 — Phase 5 Batch A: Batch Boundary Audit

## 1. 审计目的

本审计只做批次归属核查，不执行测试、不修改代码、不修改 Feature/Registry/Schema/Contract/Evidence/Attestation，也不删除任何测试日志或临时文件。

需要回答：

1. Phase 3 原始 Batch A 与 Batch F 的准确名单；
2. `test_composite.py` 的原始归属；
3. Phase 5 Batch A 实际执行是否越界；
4. 已执行结果如何计入后续 Regression；
5. 是否可正式验收 Batch A 并建议进入 Batch C。

---

## 2. HEAD 和 Git 状态

### 2.1 当前状态

| 项目 | 值 |
|---|---|
| HEAD | `04f50636c7d3afb37a2a58454cb4ae16f1a38593` |
| Branch | `master` |
| staged | `0` |
| dirty（审计报告生成前） | `1061` |
| Phase 5 Batch A 执行前 dirty | `1060` |

Phase 4 报告后的 dirty 为 1060；Phase 5 Batch A 报告生成后为 1061。两者差额是：

```text
?? .ai/context/PHASE_1_68_3_1_PHASE_5_BATCH_A_REPORT.md
```

本审计报告生成后，预计 dirty 为 **1062**，新增项仅为：

```text
?? .ai/context/PHASE_1_68_3_1_PHASE_5_BATCH_A_BOUNDARY_AUDIT.md
```

### 2.2 受保护文件哈希

审计时执行 `sha256sum -c`，全部通过：

```text
.ai/context/feature_index.json: OK
.ai/context/feature_graph.json: OK
Features/FEATURE_SCHEMA.md: OK
.ai/context/behavior_protocol.yaml: OK
.ai/tmp/p168/official/evidence/evidence_index.json: OK
```

当前哈希：

| 文件 | SHA256 |
|---|---|
| `.ai/context/feature_index.json` | `1fdce0264e29c3dabcece0938da33e740be31f8c4d74b3bbe88527760f3b4fe4` |
| `.ai/context/feature_graph.json` | `b4ace8a9b069dfa01a112bc8d4c3af4b7c3f3393ae4642312698799b0de77d47` |
| `Features/FEATURE_SCHEMA.md` | `dca7c57accf7464ccd8f4919741a078c629cdbf661718440a8c5b31f01cb56fc` |
| `.ai/context/behavior_protocol.yaml` | `d2a480b068559124bb51d74782b6ec2d33c29135573f9a9f39aa491559eea778` |
| `.ai/tmp/p168/official/evidence/evidence_index.json` | `0e1f4ab03bab6442045eca3b56c88cf2ddc7116878428c52194196942e1ee910` |

---

## 3. Phase 3 原始 Batch 划分

来源：

`.ai/context/PHASE_1_68_3_1_PHASE_3_REGRESSION_DEPENDENCY_AUDIT.md`

### 3.1 实际测试总数与剩余数

- 目录实际测试文件：**31**
- Phase 2 已完成 target：`test_behavior_protocol_consistency.py`
- 剔除 target 后的剩余测试：**30**
- Batch A + B + C + D + F：`12 + 8 + 7 + 1 + 2 = 30`
- Batch E：**0**（相关测试因执行前置为 Python-only，归入 A，不是遗漏）

### 3.2 Batch A（原始 12 项）

```text
test_scene_intent_contract.py
test_scene_builder_intent_input.py
test_capability_contract_validator.py
test_scene_validator_intent_input.py
test_scene_intent_capability.py
test_scene_intent_runtime.py
test_plan_generator.py
test_scene_compatibility_gate.py
test_feature_capability_pipeline.py
test_feature_capability_adoption.py
test_scene_composer.py
test_composite.py
```

原始报告对 `test_composite.py` 的分类是：

> `A（Integration；必须单独串行）`

原始报告还明确写明：

> `test_composite.py` 放最后，因为它会短暂写真实 `Scenes/`。

Phase 3 的风险 R2 专门描述 `test_composite.py` 创建 `Scenes/E2eCompositeTestPlayer.tscn`，要求单独串行、执行前后检查、残留则保留现场。

### 3.3 Batch B（原始 8 项）

```text
test_runtime_instance_evidence.py
test_behavior_time_driven.py
test_chase_movement_behavior.py
test_condition_gate_behavior.py
test_contact_damage_behavior.py
test_health_behavior.py
test_health_bar_behavior.py
test_stun_behavior.py
```

### 3.4 Batch C（原始 7 项）

```text
test_artifact_evidence_validator.py
test_component_instance_materialization.py
test_component_instance_ownership.py
test_external_artifact_evidence.py
test_entity_root_instance.py
test_feature_instance_evidence.py
test_instance_evidence_reconciliation.py
```

### 3.5 Batch D（原始 1 项）

```text
test_feature_behavior_evidence.py
```

### 3.6 Batch F（原始 2 项）

```text
test_composite_behavior_evidence.py
test_slime_contact_arena.py
```

Batch F 的约束：

- 两个测试共享 `.ai/tmp/composite` 和固定 bad-contract 目录；
- 串行，先 composite 后 slime；
- 每个测试 300 秒外层预算；
- 结束后检查 workspace 所有权清理与 evidence 保留。

### 3.7 Batch R（可选 target 复验）

```text
test_behavior_protocol_consistency.py
```

不计入剩余 30 个的新增覆盖。

---

## 4. Phase 5 实际执行清单

来源：

- `.ai/tmp/phase5_batch_a_logs_20261111/commands.tsv`
- `.ai/tmp/phase5_batch_a_logs_20261111/results.tsv`
- `.ai/tmp/phase5_batch_a_logs_20261111/12_test_composite.*`

实际 `results.tsv` 有 **12 行**，顺序与 Phase 3 原始 Batch A 完全一致：

| # | 实际执行测试 | 状态 | 退出码 | PASS 行 | FAIL 行 |
|---:|---|---|---:|---:|---:|
| 1 | `test_scene_intent_contract.py` | VERIFIED_PASS | 0 | 68 | 0 |
| 2 | `test_scene_builder_intent_input.py` | VERIFIED_PASS | 0 | 42 | 0 |
| 3 | `test_capability_contract_validator.py` | VERIFIED_PASS | 0 | 42 | 0 |
| 4 | `test_scene_validator_intent_input.py` | VERIFIED_PASS | 0 | 48 | 0 |
| 5 | `test_scene_intent_capability.py` | VERIFIED_PASS | 0 | 46 | 0 |
| 6 | `test_scene_intent_runtime.py` | VERIFIED_PASS | 0 | 44 | 0 |
| 7 | `test_plan_generator.py` | VERIFIED_PASS | 0 | 25 | 0 |
| 8 | `test_scene_compatibility_gate.py` | VERIFIED_PASS | 0 | 62 | 0 |
| 9 | `test_feature_capability_pipeline.py` | VERIFIED_PASS | 0 | 37 | 0 |
| 10 | `test_feature_capability_adoption.py` | VERIFIED_PASS | 0 | 230 | 0 |
| 11 | `test_scene_composer.py` | VERIFIED_PASS | 0 | 72 | 0 |
| 12 | `test_composite.py` | VERIFIED_PASS | 0 | 17 | 0 |

实际命令均记录为：

```text
PYTHONUNBUFFERED=1 timeout 300s python -u .ai/tools/scene_composer/tests/<test>.py
```

`commands.tsv` 只有这 12 条；`results.tsv` 只有这 12 条；没有重复项、遗漏项或额外项。

---

## 5. 批次归属对照表

| 测试文件 | Phase 3 原始 Batch | Phase 5 实际执行 Batch | 执行结果 | 边界状态 |
|---|---|---|---|---|
| `test_scene_intent_contract.py` | A | A | VERIFIED_PASS | **IN_SCOPE** |
| `test_scene_builder_intent_input.py` | A | A | VERIFIED_PASS | **IN_SCOPE** |
| `test_capability_contract_validator.py` | A | A | VERIFIED_PASS | **IN_SCOPE** |
| `test_scene_validator_intent_input.py` | A | A | VERIFIED_PASS | **IN_SCOPE** |
| `test_scene_intent_capability.py` | A | A | VERIFIED_PASS | **IN_SCOPE** |
| `test_scene_intent_runtime.py` | A | A | VERIFIED_PASS | **IN_SCOPE** |
| `test_plan_generator.py` | A | A | VERIFIED_PASS | **IN_SCOPE** |
| `test_scene_compatibility_gate.py` | A | A | VERIFIED_PASS | **IN_SCOPE** |
| `test_feature_capability_pipeline.py` | A | A | VERIFIED_PASS | **IN_SCOPE** |
| `test_feature_capability_adoption.py` | A | A | VERIFIED_PASS | **IN_SCOPE** |
| `test_scene_composer.py` | A | A | VERIFIED_PASS | **IN_SCOPE** |
| `test_composite.py` | **A（Integration）** | **A** | VERIFIED_PASS | **IN_SCOPE** |
| `test_composite_behavior_evidence.py` | F | 未执行 | NOT_EXECUTED | **IN_SCOPE**（未提前执行） |
| `test_slime_contact_arena.py` | F | 未执行 | NOT_EXECUTED | **IN_SCOPE**（未提前执行） |

说明：

- 表中的 `IN_SCOPE` 对未执行的 F 项表示“仍在原始批次范围内，未被提前执行”，不是已执行。
- 本次不存在 `OUT_OF_SCOPE_EARLY_EXECUTION`。
- 本次不存在 `UNKNOWN` 的批次归属。

### 5.1 关键名字区分

需要区分两个相似名称：

```text
test_composite.py
```

属于 **Batch A**，是 Python-only Composite 单元/集成回归，执行时短暂写入 `Scenes/E2eCompositeTestPlayer.tscn` 并清理。

```text
test_composite_behavior_evidence.py
```

属于 **Batch F**，是 Composite + Behavior + Evidence 链路，尚未执行。

“Composite 测试放在 Batch F”这一历史印象对应的是后者，不是 `test_composite.py`。

---

## 6. `test_composite.py` 归属结论

**结论：`test_composite.py` 原始属于 Batch A，不属于 Batch F。**

证据：

- Phase 3 Batch A 名单第 12 项明确列出 `test_composite.py`；
- Phase 3 Execution Matrix 对该文件的 Execution Group 写为 `A（Integration；必须单独串行）`；
- Phase 3 风险 R2 专门要求该 Batch A 测试单独串行并检查真实 `Scenes/` 写入；
- Phase 3 Batch F 名单只有 `test_composite_behavior_evidence.py` 和 `test_slime_contact_arena.py`。

因此：

- 没有发生 `test_composite.py` 的批次提前执行；
- 不应把它的 `VERIFIED_PASS` 移到 Batch F；
- 不需要调整 Batch F 的剩余清单；Batch F 仍是 2 项未执行。

---

## 7. 独立执行和串行执行证据

### 7.1 `test_composite.py`

实际只有一次执行记录：

- 命令：`PYTHONUNBUFFERED=1 timeout 300s python -u .ai/tools/scene_composer/tests/test_composite.py`
- 开始：`2026-11-11 22:07:03`
- 结束：`2026-11-11 22:07:05`
- 耗时：`1s`
- 退出码：`0`
- `PASS` 行：`17`
- `FAIL` 行：`0`
- 最终状态：`VERIFIED_PASS`

日志：

```text
.ai/tmp/phase5_batch_a_logs_20261111/12_test_composite.stdout.log
.ai/tmp/phase5_batch_a_logs_20261111/12_test_composite.stderr.log
.ai/tmp/phase5_batch_a_logs_20261111/12_test_composite.protected_check.log
```

### 7.2 是否同时存在独立执行与串行执行？

**没有两个独立批次。**

Phase 5 是在一次串行批次中依次执行 12 个测试；`test_composite.py` 只有这一条执行记录。不存在单独的 `serial_test_composite.log`，也不存在另一条独立执行记录。

因此：

- “串行执行”成立：它作为第 12 项在串行批次中执行；
- “独立执行 + 串行执行都发生”不成立：没有重复执行；
- 不应为补齐“独立执行”证据而重跑。

本审计目录中没有以下命名日志：

```text
test_composite.log
serial_test_composite.log
```

实际命名是 `12_test_composite.*`。此前的 Phase 4 日志仅包含 Phase 4 的三个目标测试，不包含 composite。

---

## 8. 临时场景清理证据

### 8.1 测试代码行为

`test_composite.py` 第 151–165 行：

```python
temp_scene = PROJECT_ROOT / "Scenes" / "E2eCompositeTestPlayer.tscn"
try:
    temp_scene.write_text(player_text, encoding="utf-8")
    ...
finally:
    temp_scene.unlink(missing_ok=True)
    temp_scene.with_suffix(".tscn.uid").unlink(missing_ok=True)
```

### 8.2 日志证据

`12_test_composite.stdout.log` 显示：

```text
PASS: P5b: two player_controller instances are refused (input claim conflict)
...
PASS: all 16 checks
```

日志没有单独打印“已删除 `E2eCompositeTestPlayer.tscn`”这一行。因此：

- **没有直接的 cleanup 日志行**；
- 不能把日志本身说成“明确记录了清理动作”；
- 但测试源码包含 `finally` 无条件 unlink；
- 当前 `Scenes/E2eCompositeTestPlayer.tscn` 和 `.tscn.uid` 均不存在；
- 当前 `Scenes/` 中没有其他 `E2eComposite*` 文件；
- 测试 stdout 为 PASS、stderr 为空、退出码 0，未见异常中断。

结论：清理结果有当前文件状态和源码路径佐证，但没有独立的 cleanup 日志证据。该证据不足以单独证明“删除动作被记录”，足以支持“当前无残留、未发现异常”。

---

## 9. 其他副产物检查

- Phase 5 新增目录：`.ai/tmp/phase5_batch_a_logs_20261111/`，包含 12 项 stdout/stderr、受保护哈希检查、`results.tsv`、`commands.tsv` 和完整性检查日志。
- `test_composite.py` 的系统临时工作目录由测试自身清理；没有发现项目内残留。
- `Scenes/E2eCompositeTestPlayer.tscn`：不存在。
- `Scenes/E2eCompositeTestPlayer.tscn.uid`：不存在。
- 未发现其他 `Scenes` 临时场景。
- 没有删除、移动或覆盖既有 dirty 文件。
- 没有 Batch F 的日志或执行产物。

---

## 10. Evidence / Attestation 完整性

独立只读哈希检查：

### Feature

```text
sha256sum -c .ai/tmp/p1683/baseline/features_sha256.txt
EXIT=0
OK=265
FAILED=0
```

### Historical Evidence / Attestation

```text
sha256sum -c .ai/tmp/p1683/baseline/historical_sha256.txt
EXIT=0
OK=828
FAILED=0
```

### Critical

```text
EXIT=0
.ai/tools/run_tests.py: OK
.ai/tools/scene_composer/tests/test_behavior_protocol_consistency.py: OK
.ai/context/behavior_protocol.yaml: OK
.ai/context/PHASE_1_68_3_OFFICIAL_EXECUTION_STABILIZATION_REPORT.md: OK
```

### Code

```text
EXIT=0
.ai/tools/evaluation/coverage_matrix.py: OK
.ai/tools/validator/check_behavior_evidence.py: OK
.ai/tools/run_tests.py: OK
```

### Protocol

```text
EXIT=0
.ai/context/behavior_protocol.yaml: OK
.ai/tools/scene_composer/probes/behavior_manifest.json: OK
.ai/tools/scene_composer/probes/feature_behavior_probe.gd: OK
```

### Evidence Index

```text
sha256(evidence_index.json) = 0e1f4ab03bab6442045eca3b56c88cf2ddc7116878428c52194196942e1ee910
```

与 Phase 4 / Phase 5 报告及历史记录一致。

---

## 11. Git dirty 变化

| 项目 | Phase 5 执行前 | 审计时 |
|---|---:|---:|
| HEAD | `04f50636...` | `04f50636...` |
| staged | 0 | 0 |
| dirty | 1060 | 1061 |

差额仅为 Phase 5 Batch A 报告：

```text
?? .ai/context/PHASE_1_68_3_1_PHASE_5_BATCH_A_REPORT.md
```

本审计报告生成后，预计 dirty 为 **1062**，唯一新增为本报告。

没有发现：

- 测试修改源码；
- 测试修改 Feature/Registry/Schema/Contract；
- 测试覆盖或删除既有 dirty；
- 测试留下真实场景文件；
- 未跟踪的测试副产物（除专用日志目录）。

---

## 12. 提前执行项目统计

| 分类 | 数量 | 项目 |
|---|---:|---|
| 原始 Batch A 已执行 | 12 | 全部 12 项 |
| 原始 Batch A 未执行 | 0 | — |
| 提前执行的 Batch B 项 | 0 | — |
| 提前执行的 Batch C 项 | 0 | — |
| 提前执行的 Batch D 项 | 0 | — |
| 提前执行的 Batch F 项 | 0 | — |
| 其他提前执行 | 0 | — |

**提前执行总数：0。**

Batch F 的 `test_composite_behavior_evidence.py` 和 `test_slime_contact_arena.py` 均未出现在 `commands.tsv` / `results.tsv` / 日志目录中。

---

## 13. 正式 Batch A 结果统计

- 原始 Batch A：**12 项**
- 正式执行：**12 项**
- VERIFIED_PASS：**12**
- VERIFIED_FAIL：**0**
- EXECUTION_BLOCKED：**0**
- EXECUTION_TIMEOUT：**0**
- UNKNOWN：**0**
- NOT_EXECUTED：**0**
- 正式 Batch A 剩余未执行：**0**
- 总 PASS 行：**733**
- 总 FAIL 行：**0**

Phase 5 Batch A 的全部 12 项结果都可以计入 Batch A，不需要按越界项重新归类，也不存在 Batch F 已完成项。

剩余测试总数：

```text
30 - 12 = 18
```

其中：

- Batch C：7
- Batch B：8
- Batch D：1
- Batch F：2
- 合计：18

---

## 14. 对 Batch C 的建议

### 结论

Batch A 不存在批次越界；12 项均属于原始 Batch A；完整性保护通过；可以正式验收。

### 建议

**可以建议用户授权进入 Batch C。**

建议的下一步：

1. 保留现有 Batch A 日志，不重跑 12 项；
2. Batch F 仍保留原来的 2 项：`test_composite_behavior_evidence.py`、`test_slime_contact_arena.py`；
3. Batch C 按 Phase 3 原始 7 项、串行、Python-only 执行；
4. 不把 `test_composite.py` 从 Batch A 移到 Batch F；
5. 不因 `test_composite.py` 通过而把 Batch F 标记为部分完成。

---

## 15. 最终判定

**ACCEPT**

理由：

- Phase 3 原始 Batch A 明确包含 `test_composite.py`；
- Phase 3 Batch F 明确是两个不同文件；
- Phase 5 实际执行的 12 项与原始 Batch A 完全一致，顺序一致，无重复、无遗漏；
- 没有 Batch F 或其他批次的提前执行；
- `test_composite.py` 的 `VERIFIED_PASS` 可以正式计入 Batch A；
- 临时场景当前无残留，源码有 `finally` 清理；日志没有单独的 cleanup 行，但当前状态和测试源码未显示异常；
- Feature 265/265、Historical Evidence/Attestation 828/828、Critical/Code/Protocol 全部 OK；
- 受保护哈希未变，无 Git 写操作，无进程残留。

审计完成后停止；不自动进入 Batch C，等待用户明确授权。
