# Phase 1.68.3.1 — Phase 5: Regression Batch C Report

## 1. 执行时间

- 执行日期：2026-11-11
- 执行窗口：22:45:05 – 22:45:17（本地时间）
- 阶段：Phase 1.68.3.1 / Phase 5 / Batch C
- 范围：Component / Instance / Artifact 静态测试，共 7 项

## 2. HEAD / Branch

| 项目 | 值 |
|---|---|
| HEAD | `04f50636c7d3afb37a2a58454cb4ae16f1a38593` |
| Branch | `master` |
| staged | `0` |
| dirty（执行前） | `1062` |

HEAD 与任务预期一致，没有回退或清理任何内容。

## 3. 执行前 Git 状态

### 3.1 Git

- HEAD：`04f50636c7d3afb37a2a58454cb4ae16f1a38593`
- branch：`master`
- staged：`0`
- dirty：`1062`
- 执行前没有 Python / Godot 残留进程。

### 3.2 7 个目标测试 SHA256

| 测试 | SHA256 |
|---|---|
| `test_artifact_evidence_validator.py` | `3c645162fe703d5011071e090470cca99476146e43ddf2fbb95bda96cd049aff` |
| `test_component_instance_materialization.py` | `255b84f717ae3f8783e3f381b37dd30ac5086ee85bd80b72caa13070ca172758` |
| `test_component_instance_ownership.py` | `a2b2447508ffb4aff791aa040826dfcd0930d90b3ecd9b5b28f7a54ed1d98785` |
| `test_external_artifact_evidence.py` | `4a2cdf0dd2a457136fcce9ff108b0721b6012531d623a821d73b3cd7fb33901b` |
| `test_entity_root_instance.py` | `7636865b9b143b2d4945bc6d64b8268551fd8348c8c3705f4d7dfbc243fbe0c7` |
| `test_feature_instance_evidence.py` | `5a73a6eb99c28ce7c0d66f81794c381ed59303b461f692277a6623f9e05a16c0` |
| `test_instance_evidence_reconciliation.py` | `615db1f20bc523603a5f4e08fbf70fad82140200b4db20afd28514cc803feb9a` |

### 3.3 受保护文件基线 SHA256

| 文件 | SHA256 |
|---|---|
| `.ai/context/feature_index.json` | `1fdce0264e29c3dabcece0938da33e740be31f8c4d74b3bbe88527760f3b4fe4` |
| `.ai/context/feature_graph.json` | `b4ace8a9b069dfa01a112bc8d4c3af4b7c3f3393ae4642312698799b0de77d47` |
| `Features/FEATURE_SCHEMA.md` | `dca7c57accf7464ccd8f4919741a078c629cdbf661718440a8c5b31f01cb56fc` |
| `.ai/context/behavior_protocol.yaml` | `d2a480b068559124bb51d74782b6ec2d33c29135573f9a9f39aa491559eea778` |
| `.ai/tmp/p168/official/evidence/evidence_index.json` | `0e1f4ab03bab6442045eca3b56c88cf2ddc7116878428c52194196942e1ee910` |

### 3.4 历史快照

以下文件均存在并可用：

- `.ai/tmp/p1683/baseline/features_sha256.txt`：265 项
- `.ai/tmp/p1683/baseline/historical_sha256.txt`：828 项
- `.ai/tmp/p1683/baseline/critical_sha256.txt`：4 项
- `.ai/tmp/p1683/baseline/code_sha256.txt`：3 项
- `.ai/tmp/p1683/baseline/protocol_sha256.txt`：3 项

## 4. Phase 3 原始 Batch C 的 7 项名单

来源：

`.ai/context/PHASE_1_68_3_1_PHASE_3_REGRESSION_DEPENDENCY_AUDIT.md`

严格按原始顺序：

1. `test_artifact_evidence_validator.py`
2. `test_component_instance_materialization.py`
3. `test_component_instance_ownership.py`
4. `test_external_artifact_evidence.py`
5. `test_entity_root_instance.py`
6. `test_feature_instance_evidence.py`
7. `test_instance_evidence_reconciliation.py`

实际文件全部存在，没有增加、删除或替换测试。

## 5. 每项测试的执行命令

工作目录：`F:\Godot_v4.7-stable\game`

命令模板：

```bash
PYTHONUNBUFFERED=1 timeout 300s python -u .ai/tools/scene_composer/tests/<test>.py
```

实际命令：

```text
PYTHONUNBUFFERED=1 timeout 300s python -u .ai/tools/scene_composer/tests/test_artifact_evidence_validator.py
PYTHONUNBUFFERED=1 timeout 300s python -u .ai/tools/scene_composer/tests/test_component_instance_materialization.py
PYTHONUNBUFFERED=1 timeout 300s python -u .ai/tools/scene_composer/tests/test_component_instance_ownership.py
PYTHONUNBUFFERED=1 timeout 300s python -u .ai/tools/scene_composer/tests/test_external_artifact_evidence.py
PYTHONUNBUFFERED=1 timeout 300s python -u .ai/tools/scene_composer/tests/test_entity_root_instance.py
PYTHONUNBUFFERED=1 timeout 300s python -u .ai/tools/scene_composer/tests/test_feature_instance_evidence.py
PYTHONUNBUFFERED=1 timeout 300s python -u .ai/tools/scene_composer/tests/test_instance_evidence_reconciliation.py
```

每项使用独立 Python 进程，串行执行；使用项目现有 300 秒 Python 测试预算，没有提高超时。

## 6–9. 逐项耗时、退出码、PASS/FAIL、最终状态

| # | 测试 | 开始 | 结束 | 耗时 | 退出码 | PASS | FAIL | 最终状态 |
|---:|---|---|---|---:|---:|---:|---:|---|
| 1 | `test_artifact_evidence_validator.py` | 22:45:05 | 22:45:06 | 2s | 0 | 39 | 0 | **VERIFIED_PASS** |
| 2 | `test_component_instance_materialization.py` | 22:45:06 | 22:45:07 | 1s | 0 | 58 | 0 | **VERIFIED_PASS** |
| 3 | `test_component_instance_ownership.py` | 22:45:08 | 22:45:09 | 1s | 0 | 39 | 0 | **VERIFIED_PASS** |
| 4 | `test_external_artifact_evidence.py` | 22:45:09 | 22:45:10 | 1s | 0 | 45 | 0 | **VERIFIED_PASS** |
| 5 | `test_entity_root_instance.py` | 22:45:11 | 22:45:12 | 1s | 0 | 26 | 0 | **VERIFIED_PASS** |
| 6 | `test_feature_instance_evidence.py` | 22:45:13 | 22:45:15 | 2s | 0 | 55 | 0 | **VERIFIED_PASS** |
| 7 | `test_instance_evidence_reconciliation.py` | 22:45:15 | 22:45:17 | 2s | 0 | 54 | 0 | **VERIFIED_PASS** |

汇总：

- 7 / 7 **VERIFIED_PASS**
- VERIFIED_FAIL：0
- EXECUTION_BLOCKED：0
- EXECUTION_TIMEOUT：0
- UNKNOWN：0
- NOT_EXECUTED：0
- PASS 行合计：**316**
- FAIL 行合计：**0**
- 总执行时间约 **12 秒**（不含命令启动和日志落盘开销）

说明：`PASS` 行数是测试输出中的 `PASS` 行计数，包含部分测试的最终“全部通过”汇总行；判定仍以实际退出码、FAIL 行和测试输出共同确认。

## 10. 日志路径

本阶段专用日志目录：

```text
.ai/tmp/phase5_batch_c_logs_20261111/
```

包含：

```text
01_test_artifact_evidence_validator.stdout.log
01_test_artifact_evidence_validator.stderr.log
01_test_artifact_evidence_validator.protected_check.log
...
07_test_instance_evidence_reconciliation.stdout.log
07_test_instance_evidence_reconciliation.stderr.log
07_test_instance_evidence_reconciliation.protected_check.log
commands.tsv
results.tsv
protected_baseline.sha256
git_status_after_tests.txt
integrity_features.log
integrity_historical.log
integrity_critical.log
integrity_code.log
integrity_protocol.log
```

日志目录为新建目录，没有覆盖既有内容。

## 11. 超时和中断记录

- 无超时。
- 无中断。
- 所有测试正常退出，退出码均为 0。
- 所有 `stderr` 文件均为空（`stderr_nonempty=0`）。
- 所有测试 `stdout` 中没有 `SKIP:` 标记。
- 7 个测试后的受保护哈希检查均无失败。

## 12. 副产物记录

- 本阶段唯一新增的测试产物是专用日志目录 `.ai/tmp/phase5_batch_c_logs_20261111/`。
- 7 个测试均未写入真实 `Scenes/`、`Features/` 或 `.ai/context/` 文件。
- `test_feature_instance_evidence.py` 对 `Features/` 的复制与检查发生在系统临时目录；测试结束后已清理。
- `test_instance_evidence_reconciliation.py` 对真实场景做只读哈希核对，未产生修改。
- 没有发现残留的临时场景、测试项目或未解释的测试文件。
- 没有删除或覆盖任何既有 dirty 文件。

## 13. Feature 完整性

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

预期 265 OK / 0 FAILED，实际一致。23 个正式 Feature 和 8 个 INCOMPLETE 脚手架均未被修改。

## 14. Historical Evidence / Attestation 完整性

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

预期 828 OK / 0 FAILED，实际一致。没有 Evidence、Attestation、Bundle 或历史 Run 文件被修改。

## 15. Registry / Contract / Protocol 完整性

### Registry

| 检查 | 结果 |
|---|---|
| `feature_index.json` | 哈希未变：`1fdce0264e29c3dabcece0938da33e740be31f8c4d74b3bbe88527760f3b4fe4` |
| `feature_graph.json` | 哈希未变：`b4ace8a9b069dfa01a112bc8d4c3af4b7c3f3393ae4642312698799b0de77d47` |
| Registry 成员数量 | **31** |
| `evidence_index.json` | 哈希未变：`0e1f4ab03bab6442045eca3b56c88cf2ddc7116878428c52194196942e1ee910` |

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

## 16. Git dirty 变化

| 项目 | 执行前 | 测试后 / 报告前 |
|---|---:|---:|
| HEAD | `04f50636...` | `04f50636...` |
| staged | 0 | 0 |
| dirty | 1062 | 1062 |

测试执行没有新增 Git dirty；日志目录位于 `.ai/tmp`，没有改变 `git status --porcelain` 的既有集合。

本阶段新增报告：

```text
?? .ai/context/PHASE_1_68_3_1_PHASE_5_BATCH_C_REPORT.md
```

报告生成后 dirty 为 **1063**。此前既有 dirty（包括 Phase 5 Batch A、Boundary Audit、Phase 4 和更早的 1053 项）均保留。

## 17. 进程清理结果

- 执行前无 Python / Godot 残留进程。
- 每项测试结束后均检查进程；没有残留测试进程。
- 最终检查无 Python / Godot 进程。
- 7 个测试均为单进程 Python 测试，没有启动 Godot 或持久后台任务。

## 18. 未执行测试

本阶段只执行 Batch C 的 7 项，以下均未执行：

- Batch B：8 项
- Batch D：1 项
- Batch F：2 项

剩余未执行总计：**11 项**。

没有执行 Phase 2 target 或其他测试。

## 19. 风险和遗留问题

1. Batch C 全部是静态测试，不覆盖真实 Godot Runtime、Behavior、Composite E2E；这些仍属于 Batch B / D / F。
2. `test_instance_evidence_reconciliation.py` 明确依赖当前仓库的 7 个 instance 声明；如果 Feature 数据后续变化，该静态断言会相应变化，本阶段没有修改数据。
3. `test_feature_instance_evidence.py` 会复制 Features 到临时目录；本次测试通过且未发现真实 Feature 变化。
4. 当前 dirty 1063（报告生成后）中，原先 1053 项 dirty 与之前阶段的报告均保留；没有清理或覆盖。
5. 本阶段没有修改源码、测试或测试运行器；没有执行自动修复。
6. 若后续 Batch B 出现 Godot 环境问题，不能以 Batch C 的静态 PASS 替代 Runtime 验证。

## 20. 最终判定

**PASS**

理由：

- 7 / 7 项测试均为 `VERIFIED_PASS`；
- 全部退出码为 0；
- 全部 PASS，无 FAIL、无超时、无跳过；
- 每项测试后受保护哈希检查通过；
- Feature 265/265 OK；
- Historical Evidence / Attestation 828/828 OK；
- Critical / Code / Protocol 全部 OK；
- Registry 31 个成员，Registry、Schema、Contract、Evidence Index 哈希未变；
- 没有测试修改真实项目文件或留下副产物；
- 没有 Python / Godot 残留进程；
- 只执行了原始 Batch C 的 7 项，没有越界执行 Batch B/D/F；
- 未执行 Git 写操作，未修改任何源码或测试。

报告完成后停止。等待用户审查后，才决定是否进入 Batch B。
