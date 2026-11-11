# Phase 1.68.3.1 — Phase 5: Regression Batch B Report

## A. Baseline

### A.1 执行时间与环境

- 执行日期：2026-11-11
- 执行窗口：22:52:11 – 23:01:32（本地时间）
- 阶段：Phase 1.68.3.1 / Phase 5 / Batch B
- 范围：8 个单 Feature Godot Runtime 测试

### A.2 Git

| 项目 | 值 |
|---|---|
| HEAD | `04f50636c7d3afb37a2a58454cb4ae16f1a38593` |
| Branch | `master` |
| staged | `0` |
| dirty（执行前） | `1063` |
| Python / Godot 残留进程（执行前） | 无 |

### A.3 Godot 环境

| 项目 | 值 |
|---|---|
| Godot 可执行文件 | `../Godot_v4.7-stable_win64_console.exe` |
| Godot 文件存在 | 是 |
| `.godot/global_script_class_cache.cfg` | 存在，14768 bytes |
| Python | 3.12.10 |
| 单项外层预算 | `timeout 300s`，与 `run_tests.py` 的 `PYTHON_TIMEOUT_PER_TEST` 一致 |

### A.4 Batch B 原始名单

来源：

`.ai/context/PHASE_1_68_3_1_PHASE_3_REGRESSION_DEPENDENCY_AUDIT.md`

严格按原始顺序：

1. `test_runtime_instance_evidence.py`
2. `test_behavior_time_driven.py`
3. `test_chase_movement_behavior.py`
4. `test_condition_gate_behavior.py`
5. `test_contact_damage_behavior.py`
6. `test_health_behavior.py`
7. `test_health_bar_behavior.py`
8. `test_stun_behavior.py`

`test_manifest.txt` 记录同样 8 项；没有增加、删除、替换或重复测试。没有执行 Batch A、C、D、F 的测试。

### A.5 日志目录

```text
.ai/tmp/phase5_batch_b_logs_20261111/
```

包含：

- `test_manifest.txt`
- `commands.tsv`
- `results.tsv`
- `git_status_before.txt`
- `git_status_after.txt`
- `git_baseline.txt`
- `protected_baseline.sha256`
- `test_sha256_before.txt`
- `test_sha256_after.txt`
- `integrity_before.log`
- `integrity_after.log`
- `process_check.log`
- 每项测试的 `.stdout.log`、`.stderr.log`、`.command.txt`、`.result.txt`、`.protected_check.log`

该目录为本次新建，没有覆盖既有日志。

### A.6 8 个测试修改前 SHA256

| 测试 | SHA256 |
|---|---|
| `test_runtime_instance_evidence.py` | `24f83762b8db0d2331b3c7294f7772dc23d8c8492c80a577fbe7945453e0c872` |
| `test_behavior_time_driven.py` | `50e8ce5e5c840dfe936436677f406d48eba97812fc2a7878a1e50c97c2ce00a2` |
| `test_chase_movement_behavior.py` | `dce38d35f1108c956f19668178bed74e419ccc1c0933843f645e00b0d79bbea5` |
| `test_condition_gate_behavior.py` | `825eb48e0d57a528427b19dfc658ae72bbff6e6e06237adcb2e0a4facb37276b` |
| `test_contact_damage_behavior.py` | `e2cae467fb4a6f3e932448aef69f954db8cfe5f97054155ed29e45a2e9d53949` |
| `test_health_behavior.py` | `a11130ad01897be19806d69f1627afcef09b64f00297761df5e6a20144e1140b` |
| `test_health_bar_behavior.py` | `a56a70e2a34b3cbd15b6e18307f3674e81baa959894cede9d6b7a84b6e819a6e` |
| `test_stun_behavior.py` | `1aec4b01a9486633b5220118461c49c2cd279befb580f368ad0aeea2dc0cfc20` |

执行后 `test_sha256_before.txt` 校验全部 OK；测试文件未被修改。

### A.7 受保护文件基线

| 文件 | SHA256 |
|---|---|
| `.ai/context/feature_index.json` | `1fdce0264e29c3dabcece0938da33e740be31f8c4d74b3bbe88527760f3b4fe4` |
| `.ai/context/feature_graph.json` | `b4ace8a9b069dfa01a112bc8d4c3af4b7c3f3393ae4642312698799b0de77d47` |
| `Features/FEATURE_SCHEMA.md` | `dca7c57accf7464ccd8f4919741a078c629cdbf661718440a8c5b31f01cb56fc` |
| `.ai/context/behavior_protocol.yaml` | `d2a480b068559124bb51d74782b6ec2d33c29135573f9a9f39aa491559eea778` |
| `.ai/tmp/p168/official/evidence/evidence_index.json` | `0e1f4ab03bab6442045eca3b56c88cf2ddc7116878428c52194196942e1ee910` |

执行前后 `protected_baseline.sha256` 校验全部 OK。

---

## B. 测试结果

| # | Test | Status | Exit Code | PASS | FAIL | Duration |
|---:|---|---|---:|---:|---:|---:|
| 1 | `test_runtime_instance_evidence.py` | **VERIFIED_PASS** | 0 | 68 | 0 | 17s |
| 2 | `test_behavior_time_driven.py` | **VERIFIED_PASS** | 0 | 74 | 0 | 125s |
| 3 | `test_chase_movement_behavior.py` | **VERIFIED_PASS** | 0 | 31 | 0 | 44s |
| 4 | `test_condition_gate_behavior.py` | **VERIFIED_PASS** | 0 | 53 | 0 | 66s |
| 5 | `test_contact_damage_behavior.py` | **VERIFIED_PASS** | 0 | 39 | 0 | 68s |
| 6 | `test_health_behavior.py` | **VERIFIED_PASS** | 0 | 107 | 0 | 74s |
| 7 | `test_health_bar_behavior.py` | **VERIFIED_PASS** | 0 | 65 | 0 | 56s |
| 8 | `test_stun_behavior.py` | **VERIFIED_PASS** | 0 | 70 | 0 | 91s |

执行参数：

```text
PYTHONUNBUFFERED=1 timeout 300s python -u .ai/tools/scene_composer/tests/<test>.py
```

每项均为独立 Python 进程，严格串行；上一项退出并确认无残留后才启动下一项。

启动时间：

| # | Start | End |
|---:|---|---|
| 1 | 22:52:11 | 22:52:28 |
| 2 | 22:52:29 | 22:54:34 |
| 3 | 22:54:35 | 22:55:19 |
| 4 | 22:55:20 | 22:56:26 |
| 5 | 22:56:40 | 22:57:48 |
| 6 | 22:57:49 | 22:59:03 |
| 7 | 22:59:04 | 23:00:00 |
| 8 | 23:00:01 | 23:01:32 |

第 4 项结束到第 5 项启动之间有 14 秒间隔，用于进程/受保护哈希检查；这不是并行执行。

---

## C. 汇总

| 状态 | 数量 |
|---|---:|
| VERIFIED_PASS | **8** |
| VERIFIED_FAIL | 0 |
| EXECUTION_BLOCKED | 0 |
| EXECUTION_TIMEOUT | 0 |
| UNKNOWN | 0 |
| NOT_EXECUTED | 0 |
| PASS 行总数 | **507** |
| FAIL 行总数 | **0** |
| 总耗时 | **541s** |

所有测试正常退出，退出码为 0；没有 `SKIP:` 标记，没有 stderr 内容，没有超时。

---

## D. Runtime 副作用

### D.1 预期的 Runtime 证据目录

测试在真实 Godot Runtime 下运行，并产生/更新了预期的测试证据目录：

| 路径 | 状态 | 说明 |
|---|---|---|
| `.ai/tmp/behavior` | 存在，更新时间 23:01:31 | 行为测试 workspace/evidence，预期产物 |
| `.ai/tmp/runtime-instance` | 存在，更新时间 22:52:27 | runtime instance evidence，预期产物 |
| `.ai/tmp/composite` | 存在，时间 2026-11-05 01:39:36 | 本批次未更新 |

这些是测试自身的证据/workspace 路径，不是正式项目资源。本阶段没有删除或清理它们。

### D.2 真实项目文件

- `Scenes/`：没有新文件或修改。
- `Features/`：没有新文件或修改。
- `.ai/context/`：没有新文件或修改。
- `.ai/evidence/`：没有发现新增或修改。
- 没有产生残留 `.tscn`、`.gd`、`.uid` 临时文件。
- 没有修改 Evidence Bundle、Manifest、Attestation 或 Review JSON。

### D.3 未直接审计项

Godot `user://` 的实际用户数据目录位于项目外，本次没有枚举其文件哈希；测试全部通过且无残留 Godot 进程。该外部目录不作为“已证明未修改”的强断言，仅记录为未直接审计项。

---

## E. 完整性

### E.1 Feature

```text
sha256sum -c .ai/tmp/p1683/baseline/features_sha256.txt
EXIT=0
OK=265
FAILED=0
```

### E.2 Historical Evidence / Attestation

```text
sha256sum -c .ai/tmp/p1683/baseline/historical_sha256.txt
EXIT=0
OK=828
FAILED=0
```

### E.3 Critical / Code / Protocol

| 清单 | 结果 |
|---|---|
| `critical_sha256.txt` | EXIT=0，4/4 OK，0 FAILED |
| `code_sha256.txt` | EXIT=0，3/3 OK，0 FAILED |
| `protocol_sha256.txt` | EXIT=0，3/3 OK，0 FAILED |

### E.4 Registry

| 检查 | 结果 |
|---|---|
| Registry Members | **31** |
| Scene Composer Eligible | **23** |
| `feature_index.json` | 哈希未变：`1fdce0264e29c3dabcece0938da33e740be31f8c4d74b3bbe88527760f3b4fe4` |
| `feature_graph.json` | 哈希未变：`b4ace8a9b069dfa01a112bc8d4c3af4b7c3f3393ae4642312698799b0de77d47` |
| `evidence_index.json` | 哈希未变：`0e1f4ab03bab6442045eca3b56c88cf2ddc7116878428c52194196942e1ee910` |

### E.5 进程

- 每项测试后检查 Python / Godot 进程，无残留。
- 批次结束后最终检查无 Python / Godot 进程。
- `process_check.log` 为空，表示未发现残留。
- 没有无法解释的后台任务。

---

## F. Git 工作区

| 项目 | 执行前 | 测试后 / 报告生成前 |
|---|---:|---:|
| HEAD | `04f50636...` | `04f50636...` |
| branch | `master` | `master` |
| staged | 0 | 0 |
| dirty | 1063 | 1063 |

测试执行没有新增 Git dirty；`.ai/tmp/behavior` 和 `.ai/tmp/runtime-instance` 位于既有 `.ai/tmp` 忽略范围，不改变 `git status --porcelain`。

本阶段新增报告：

```text
?? .ai/context/PHASE_1_68_3_1_PHASE_5_BATCH_B_REPORT.md
```

报告生成后 dirty 为 **1064**。既有 dirty（包括 Phase 4/5 报告和更早的 1053 项）全部保留，没有被覆盖或清理。

---

## G. 最终结论

**PASS**

- 8 / 8 项测试均为 `VERIFIED_PASS`；
- 全部退出码为 0；
- 无 FAIL、无超时、无 UNKNOWN、无 BLOCKED；
- Feature 265/265 OK；
- Historical Evidence / Attestation 828/828 OK；
- Critical / Code / Protocol 全部 OK；
- Registry 31 个成员、Scene Composer Eligible 23；
- 三个索引文件哈希未变；
- 无真实 Scenes / Features / `.ai/context` 修改；
- 无 Python / Godot 残留进程；
- 仅执行 Batch B 的 8 项，没有越界执行 Batch D 或 Batch F；
- 没有修改测试、生产代码或 Git 索引。

Batch B 完成。报告完成后停止；不自动进入 Batch D 或 Batch F，等待负责人审查并明确授权。
