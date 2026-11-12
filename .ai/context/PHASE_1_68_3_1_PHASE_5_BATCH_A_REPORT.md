# Phase 1.68.3.1 — Phase 5: Regression Batch A Report

## 1. 执行日期和时间

- 执行日期：2026-11-11
- 执行窗口：22:06:39 – 22:07:05（本地时间）
- 报告生成时间：2026-11-11 22:07 之后
- 阶段：Phase 1.68.3.1 / Phase 5 / Batch A（12 个 Python-only 静态与管线测试）

## 2. 当前 HEAD / Branch

| 项目 | 值 |
|---|---|
| HEAD | `04f50636c7d3afb37a2a58454cb4ae16f1a38593` |
| Branch | `master` |
| staged | `0` |
| dirty（执行前） | `1060` |

HEAD 与任务给出的基线一致；没有回退、清理或覆盖任何既有 dirty 内容。

## 3. 执行前工作区基线

### 3.1 Git

- HEAD：`04f50636c7d3afb37a2a58454cb4ae16f1a38593`
- branch：`master`
- staged：`0`
- dirty：`1060`
- 执行前没有 Python / Godot 残留进程。

### 3.2 受保护文件 SHA256

| 文件 | SHA256 |
|---|---|
| `.ai/context/feature_index.json` | `1fdce0264e29c3dabcece0938da33e740be31f8c4d74b3bbe88527760f3b4fe4` |
| `.ai/context/feature_graph.json` | `b4ace8a9b069dfa01a112bc8d4c3af4b7c3f3393ae4642312698799b0de77d47` |
| `Features/FEATURE_SCHEMA.md` | `dca7c57accf7464ccd8f4919741a078c629cdbf661718440a8c5b31f01cb56fc` |
| `.ai/context/behavior_protocol.yaml` | `d2a480b068559124bb51d74782b6ec2d33c29135573f9a9f39aa491559eea778` |
| `.ai/tmp/p168/official/evidence/evidence_index.json` | `0e1f4ab03bab6442045eca3b56c88cf2ddc7116878428c52194196942e1ee910` |

### 3.3 历史快照可用性

| 快照 | 状态 |
|---|---|
| `.ai/tmp/p1683/baseline/features_sha256.txt` | 存在，265 项 |
| `.ai/tmp/p1683/baseline/historical_sha256.txt` | 存在，828 项 |
| `.ai/tmp/p1683/baseline/critical_sha256.txt` | 存在，4 项 |
| `.ai/tmp/p1683/baseline/code_sha256.txt` | 存在，3 项 |
| `.ai/tmp/p1683/baseline/protocol_sha256.txt` | 存在，3 项 |

### 3.4 测试环境

- Python：`3.12.10`
- 超时工具：GNU coreutils `timeout 8.32`
- 项目 Python 测试预算：`run_tests.py` 的 `PYTHON_TIMEOUT_PER_TEST = 300` 秒
- 本次每项测试使用 `PYTHONUNBUFFERED=1` + `timeout 300s python -u`；没有提高项目预算。
- 每项测试独立 Python 进程，严格串行，未并行。

## 4. Batch A 原始 12 项清单

原始清单来自：

`.ai/context/PHASE_1_68_3_1_PHASE_3_REGRESSION_DEPENDENCY_AUDIT.md` §7 Batch A。

严格按原顺序执行：

1. `test_scene_intent_contract.py`
2. `test_scene_builder_intent_input.py`
3. `test_capability_contract_validator.py`
4. `test_scene_validator_intent_input.py`
5. `test_scene_intent_capability.py`
6. `test_scene_intent_runtime.py`
7. `test_plan_generator.py`
8. `test_scene_compatibility_gate.py`
9. `test_feature_capability_pipeline.py`
10. `test_feature_capability_adoption.py`
11. `test_scene_composer.py`
12. `test_composite.py`

实际路径：

```text
.ai/tools/scene_composer/tests/<name>
```

没有增加、删除或替换测试。

### 4.1 逐项风险评估

| # | 测试 | 写入范围 | Godot 依赖 | 共享状态 / 风险 |
|---:|---|---|---|---|
| 1 | `test_scene_intent_contract.py` | 只读 YAML | 无 | 无 |
| 2 | `test_scene_builder_intent_input.py` | 系统临时目录 | 无 | 无 |
| 3 | `test_capability_contract_validator.py` | 系统临时目录 | 无 | 无 |
| 4 | `test_scene_validator_intent_input.py` | 系统临时目录 | 无 | 无 |
| 5 | `test_scene_intent_capability.py` | 系统临时目录 | 无 | 无 |
| 6 | `test_scene_intent_runtime.py` | 系统临时目录 | 无 | 无 |
| 7 | `test_plan_generator.py` | 系统临时目录；子进程调用 `plan_generator` | 无 | 内部 CLI 超时 180 秒；无真实项目写入 |
| 8 | `test_scene_compatibility_gate.py` | 系统临时目录 | 无 | 无 |
| 9 | `test_feature_capability_pipeline.py` | 系统临时目录 | 无 | 读取真实 Feature/index；无写入 |
| 10 | `test_feature_capability_adoption.py` | 系统临时目录 | 无 | 读取真实 Feature/index；无写入 |
| 11 | `test_scene_composer.py` | 系统临时目录 | 无 | 读取真实 Feature/index；无写入 |
| 12 | `test_composite.py` | 系统临时目录；短暂创建真实 `Scenes/E2eCompositeTestPlayer.tscn`，在 `finally` 中删除 | 无 | **已监控**；测试前后均确认该文件不存在，无残留 |

`test_composite.py` 是唯一有真实 `Scenes/` 短暂写入风险的测试；其清理逻辑在 `finally` 中执行，本次执行后文件不存在。没有测试依赖 Godot Runtime，没有测试修改 Feature、Registry、Schema、Contract、Evidence 或 `.ai/tmp/p168/official`。

## 5. 每项测试的独立执行命令

工作目录统一为项目根：

```text
F:\Godot_v4.7-stable\game
```

命令模板：

```bash
PYTHONUNBUFFERED=1 timeout 300s python -u .ai/tools/scene_composer/tests/<test>.py
```

逐项命令：

```text
PYTHONUNBUFFERED=1 timeout 300s python -u .ai/tools/scene_composer/tests/test_scene_intent_contract.py
PYTHONUNBUFFERED=1 timeout 300s python -u .ai/tools/scene_composer/tests/test_scene_builder_intent_input.py
PYTHONUNBUFFERED=1 timeout 300s python -u .ai/tools/scene_composer/tests/test_capability_contract_validator.py
PYTHONUNBUFFERED=1 timeout 300s python -u .ai/tools/scene_composer/tests/test_scene_validator_intent_input.py
PYTHONUNBUFFERED=1 timeout 300s python -u .ai/tools/scene_composer/tests/test_scene_intent_capability.py
PYTHONUNBUFFERED=1 timeout 300s python -u .ai/tools/scene_composer/tests/test_scene_intent_runtime.py
PYTHONUNBUFFERED=1 timeout 300s python -u .ai/tools/scene_composer/tests/test_plan_generator.py
PYTHONUNBUFFERED=1 timeout 300s python -u .ai/tools/scene_composer/tests/test_scene_compatibility_gate.py
PYTHONUNBUFFERED=1 timeout 300s python -u .ai/tools/scene_composer/tests/test_feature_capability_pipeline.py
PYTHONUNBUFFERED=1 timeout 300s python -u .ai/tools/scene_composer/tests/test_feature_capability_adoption.py
PYTHONUNBUFFERED=1 timeout 300s python -u .ai/tools/scene_composer/tests/test_scene_composer.py
PYTHONUNBUFFERED=1 timeout 300s python -u .ai/tools/scene_composer/tests/test_composite.py
```

## 6–9. 逐项结果（开始/结束、耗时、退出码、PASS/FAIL、状态）

| # | 测试 | 开始 | 结束 | 耗时 | 退出码 | PASS | FAIL | 最终状态 |
|---:|---|---|---|---:|---:|---:|---:|---|
| 1 | `test_scene_intent_contract.py` | 22:06:39 | 22:06:40 | 1s | 0 | 68 | 0 | **VERIFIED_PASS** |
| 2 | `test_scene_builder_intent_input.py` | 22:06:41 | 22:06:41 | 0s | 0 | 42 | 0 | **VERIFIED_PASS** |
| 3 | `test_capability_contract_validator.py` | 22:06:42 | 22:06:43 | 1s | 0 | 42 | 0 | **VERIFIED_PASS** |
| 4 | `test_scene_validator_intent_input.py` | 22:06:43 | 22:06:44 | 1s | 0 | 48 | 0 | **VERIFIED_PASS** |
| 5 | `test_scene_intent_capability.py` | 22:06:44 | 22:06:46 | 2s | 0 | 46 | 0 | **VERIFIED_PASS** |
| 6 | `test_scene_intent_runtime.py` | 22:06:46 | 22:06:47 | 1s | 0 | 44 | 0 | **VERIFIED_PASS** |
| 7 | `test_plan_generator.py` | 22:06:48 | 22:06:52 | 4s | 0 | 25 | 0 | **VERIFIED_PASS** |
| 8 | `test_scene_compatibility_gate.py` | 22:06:53 | 22:06:54 | 1s | 0 | 62 | 0 | **VERIFIED_PASS** |
| 9 | `test_feature_capability_pipeline.py` | 22:06:55 | 22:06:56 | 1s | 0 | 37 | 0 | **VERIFIED_PASS** |
| 10 | `test_feature_capability_adoption.py` | 22:06:57 | 22:07:00 | 3s | 0 | 230 | 0 | **VERIFIED_PASS** |
| 11 | `test_scene_composer.py` | 22:07:01 | 22:07:03 | 2s | 0 | 72 | 0 | **VERIFIED_PASS** |
| 12 | `test_composite.py` | 22:07:03 | 22:07:05 | 1s | 0 | 17 | 0 | **VERIFIED_PASS** |

汇总：

- 12 / 12 **VERIFIED_PASS**
- 0 VERIFIED_FAIL
- 0 EXECUTION_BLOCKED
- 0 EXECUTION_TIMEOUT
- 0 UNKNOWN
- 0 NOT_EXECUTED
- PASS 行合计：**733**
- FAIL 行合计：**0**
- 总耗时约 **18 秒**（不含命令启动/日志落盘开销）

## 10. 测试日志位置

本阶段专用日志目录：

```text
.ai/tmp/phase5_batch_a_logs_20261111/
```

每个测试包含：

```text
<NN>_<test>.stdout.log
<NN>_<test>.stderr.log
<NN>_<test>.protected_check.log
```

汇总文件：

```text
results.tsv
commands.tsv
protected_baseline.sha256
git_status_after_tests.txt
integrity_features.log
integrity_historical.log
integrity_critical.log
integrity_code.log
integrity_protocol.log
```

日志目录是本次新建的独立目录，没有覆盖已有内容。

## 11. 超时或中断

- 无超时。
- 无中断。
- 12 项全部正常退出。
- 所有测试的 stderr 文件为空（`stderr_nonempty=0`）。
- 所有测试 stdout 中没有 `SKIP:` 标记。

## 12. 测试执行产生的文件变化

- 测试日志目录：`.ai/tmp/phase5_batch_a_logs_20261111/`（本阶段新增，独立于既有 dirty）。
- `test_composite.py` 临时创建的 `Scenes/E2eCompositeTestPlayer.tscn` 及其 `.uid` 在测试后均不存在；测试前后均确认 absent。
- 没有新增 Feature、Registry、Schema、Contract 或 Evidence 文件变化。
- 测试自己的系统临时目录由测试 `finally` 清理；本阶段没有删除任何既有 dirty 或副产物。

## 13. Feature / Evidence / Attestation 完整性

### Feature

执行：

```text
sha256sum -c .ai/tmp/p1683/baseline/features_sha256.txt
```

结果：

```text
EXIT=0
OK=265
FAILED=0
```

覆盖 23 个 Eligible Feature、8 个 INCOMPLETE 脚手架及 `FEATURE_SCHEMA.md`。预期 265 OK / 0 FAILED，实际一致。

### Historical Evidence / Attestation

执行：

```text
sha256sum -c .ai/tmp/p1683/baseline/historical_sha256.txt
```

结果：

```text
EXIT=0
OK=828
FAILED=0
```

覆盖 p157/p166/p167/p168 official Evidence、Attestation、Bundle、Index 和 Run 文件。预期 828 OK / 0 FAILED，实际一致。

## 14. Registry / Contract / Protocol 完整性

### Registry

| 检查 | 结果 |
|---|---|
| `feature_index.json` 哈希 | 未变：`1fdce0264e29c3dabcece0938da33e740be31f8c4d74b3bbe88527760f3b4fe4` |
| `feature_graph.json` 哈希 | 未变：`b4ace8a9b069dfa01a112bc8d4c3af4b7c3f3393ae4642312698799b0de77d47` |
| Registry 成员数量 | **31** |

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

与执行前及历史记录一致。

## 15. Git dirty 变化

| 项目 | 执行前 | 测试后 / 报告前 |
|---|---:|---:|
| HEAD | `04f50636...` | `04f50636...` |
| staged | 0 | 0 |
| dirty | 1060 | 1060 |

测试执行没有新增 Git dirty 项；日志目录位于既有 `.ai/tmp` 忽略范围内，未改变 `git status --porcelain`。

本阶段新增报告：

```text
?? .ai/context/PHASE_1_68_3_1_PHASE_5_BATCH_A_REPORT.md
```

报告生成后 dirty 为 **1061**。此前既有 dirty（包括 Phase 4 的 3 个测试修改、Phase 4 报告以及更早的 1053 项）均保留，没有被覆盖或清理。

## 16. 进程清理结果

- 执行前无 Python / Godot 残留进程。
- 每项测试完成后检查进程；没有残留 Python 或 Godot 进程。
- 最终 `ps -W` 检查无本阶段遗留测试进程。
- `test_plan_generator.py` 和 `test_composite.py` 启动的 CLI 子进程均随测试退出；没有无法解释的后台任务。

## 17. 未执行测试清单

本阶段只执行 Batch A 的 12 项；以下均未执行：

- Batch C（7 项）
- Batch B（8 项）
- Batch D（1 项）
- Batch F（2 项）
- Batch R / 其他剩余测试

因此未执行测试不能计入 PASS，本报告不对它们作回归结论。

## 18. 风险和遗留问题

1. `test_composite.py` 是 Batch A 中唯一会短暂写入真实 `Scenes/` 的测试；本次已确认清理成功，但后续批次仍应继续保持串行和前后检查。
2. Batch A 仅覆盖 Python-only 静态与管线；Behavior Runtime、Godot 场景加载、Composite Behavior 和 E2E 尚未验证。
3. 2026-11-11 当前工作区 dirty 为 1060（报告前），高于 Phase 1 的 1053；差额来自此前阶段新增的报告和 Phase 4 测试修改，不是本阶段造成的。
4. 本阶段没有修改任何测试或生产代码；如果后续批次出现失败，应按授权范围只读诊断，不自动修复。
5. `test_plan_generator.py` 内部 CLI 自带 180 秒超时；`test_composite.py` 无独立内部超时，但外层按项目 300 秒预算执行，本次远低于预算。

## 19. 最终判定

**PASS**

- 12 / 12 测试为 `VERIFIED_PASS`；
- 全部退出码为 0；
- 全部 PASS 且无 FAIL/超时/跳过；
- Feature 265/265 OK；
- Historical Evidence/Attestation 828/828 OK；
- Critical / Code / Protocol 全部 OK；
- Registry 31 个成员，Registry / Schema / Contract / Evidence Index 哈希未变；
- 无受保护文件变化；
- 无无法解释的工作区污染；
- 无进程残留；
- 未执行 Batch A 之外的测试，未修改任何测试或生产代码，未执行 Git 写操作。

报告完成后停止，等待用户审查并明确授权下一批次。
