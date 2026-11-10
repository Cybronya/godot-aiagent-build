# Phase 1.68.2 — 官方 Contract 执行接入、真实 P5 执行与覆盖复核报告

日期：2026-11-09  
范围：Phase 1.68.2（只做到本阶段，不进入 1.68.3）  
结论：**实现完成；4 条 P5 官方契约真实执行全部 PASS；Door 回归 PASS；官方覆盖独立计数 5/60；原 `fully_covered` 仍为 0；未执行任何 Git 写操作。**

---

## 1. 基线

| 项目 | 值 |
|---|---|
| HEAD | `541696593994345f916b2aaf42462cf6fc8247c7`（短 `54169659`） |
| 暂存区 | 0 个 staged 文件 |
| 工作区 | 进入本阶段时 dirty 1095；完成报告时 dirty 1119（含本报告，新增内容见第 9 节） |
| Python | 3.12（`F:\Program Files\Python3.12\python.exe`） |
| Godot | `Godot_v4.7-stable_win64_console.exe` |
| Feature 目录 | 32 个 |
| 官方 Contract | 60 个 Behavior，145 条 expected check |
| Scenario 状态 | 9 个 Scenario 已执行；原 7 维 `fully_covered = 0` |
| 历史对照 | `.ai/tmp/p157/bundles_real/p157-real.json` 存在，60/60 PASS，HEAD `dd3a0e4d`，无 Attestation |

本阶段开始时确认：`judge_record()`、Scenario Intent/内容、Generator、Validator 既有规则、Knowledge Registry、历史 p157/p166 Evidence/Evaluation 均未改动。

---

## 2. 实现

### 2.1 新判定器（不替换旧判定器）

文件：`.ai/tools/validator/check_behavior_evidence.py`

新增：

- `judge_record_keyed(record, contract)`
- `_observation_key(...)`
- `_key_text(...)`
- keyed 结果字段：`checks`、`required_keys`、`extra_keys`、`duplicate_actual_keys`、`duplicate_contract_keys`、`reason`。

行为：

| 情形 | 结论 |
|---|---|
| 按 key 匹配、顺序任意 | 正常判定 |
| 额外观测 | 记录到 `extra_keys`，不单独导致 FAIL |
| 缺失观测 | `INCOMPLETE` |
| 重复实际 key | `INCOMPLETE`，并明确报告重复 |
| 重复 contract key | `INCOMPLETE`，不静默去重 |
| 值不匹配 | `FAIL` |
| 非法/不完整字段 | `INCOMPLETE` |
| 空观测 | `INCOMPLETE` |

旧 `judge_record()` 保持原有调用与语义，未被删除或替换。

### 2.2 官方执行入口

文件：`.ai/tools/learning/scenario_run.py`

新增：

- 官方目录：`.ai/tmp/p168/official/{evidence,runs,records}`，索引 `results.json`
- `official_plan(feature_id, behavior_id, ...)`
- `run_official_contract(feature_id, behavior_id, ...)`
- `run_official_batch(...)`
- CLI：`--official feature/behavior`（可重复）
- 官方执行失败也写记录：缺契约、Godot 启动失败、超时、Evidence 缺失、判定失败均可见，不静默丢记录。

隔离原则：

- 官方执行只读取 `Features/<feature>/feature.yaml` 的 Contract（actions + expected）。
- 不读取 Scenario，不从 Scenario Expected 推导。
- 每次 Behavior 独立 Run、独立隔离 workspace、串行执行。
- 不复用 Scenario 的 Evidence Bundle 或 Attestation。

### 2.3 Evidence v1 的附加块

未引入 Evidence v2。官方 Bundle 仍为 v1；顶层新增可选 `official_contract` 块：

```text
kind, schema, schema_version, feature_id, behavior_id, behavior,
contract_source, contract_version, contract_digest,
contract_actions, contract_expected, run_id,
observations, observation_digest,
judge_version, judge_digest, judge_status
```

该块不包含 evidence 自身的 digest，避免自引用；外层 Bundle 的 `integrity` 仍按 v1 规则重算，旧消费者可忽略该附加块。

### 2.4 Attestation 复用

文件：`.ai/tools/validator/execution/*` 的既有签名封套未升级 Schema。

每次官方执行生成独立 Manifest + Attestation；Attestation 增加 `official_contract` 块，含：

```text
contract_digest, contract_actions, contract_expected,
observation_digest, judge_digest, judge_status,
evidence_payload_sha256, bundle_payload_sha256, manifest_digest
```

`trust_level` 为 `LOCAL_ISOLATED`，`attestation_scope` 为 `attest_execution`。

### 2.5 覆盖维度

文件：`.ai/tools/evaluation/coverage_matrix.py`

新增独立维度 `official_contract`，不修改原 7 维 `fully_covered` 公式：

- 只有官方执行且 keyed 判定 PASS 才计 `OFFICIAL_PASS`。
- Scenario 执行 PASS、Scenario Evaluation PASS、Scenario Attestation 均不能抬升该维度。
- 校验顺序：执行记录 → 自报状态 → Bundle integrity → behavior 绑定 → contract digest → observation digest → keyed PASS → Evidence 签名 → Attestation 绑定。
- 新增摘要字段、Markdown 列、`--official-results` 参数；`official_contract_dimension` 不参与 `missing_and_next()`。

### 2.6 测试文件

- `.ai/tools/validator/tests/test_keyed_judge.py`：K1–K14
- `.ai/tools/learning/tests/test_official_contract_run.py`：O1–O11 + O6b
- `.ai/tools/evaluation/tests/test_official_contract_coverage.py`：C1–C12

---

## 3. 官方执行结果

四条 P5 官方契约 + 一条 Door 回归，均为真实 Godot 执行、replay=2、独立 workspace。

| Behavior | run_id（前 8 位） | 执行 | Evidence | Attestation | keyed | 官方覆盖 | 时长 |
|---|---|---|---|---|---|---|---|
| `collect_pickup/collect_on_contact` | `d58ed649` | PASSED | EVIDENCE_VERIFIED | ATTESTED_VERIFIED | PASS | OFFICIAL_PASS | 12.27s |
| `contact_damage/damage_amount_is_respected` | `b0a72130` | PASSED | EVIDENCE_VERIFIED | ATTESTED_VERIFIED | PASS | OFFICIAL_PASS | 16.42s |
| `contact_damage/damage_on_contact` | `6519d2e8` | PASSED | EVIDENCE_VERIFIED | ATTESTED_VERIFIED | PASS | OFFICIAL_PASS | 13.24s |
| `heal_pickup/heal_damaged_target` | `f5f88ab5` | PASSED | EVIDENCE_VERIFIED | ATTESTED_VERIFIED | PASS | OFFICIAL_PASS | 12.29s |
| `openable_door/open`（Door 回归） | `573173f3` | PASSED | EVIDENCE_VERIFIED | ATTESTED_VERIFIED | PASS | OFFICIAL_PASS | 15.57s |

汇总：

- 请求的 4 条 P5：4/4 PASS。
- Door 回归：1/1 PASS。
- 执行失败：0。
- keyed FAIL：0。
- 官方 Attestation 验签失败：0。

索引：`.ai/tmp/p168/official/results.json`，5 条记录，5 PASS / 5 attestation / 5 fully covered。

独立产物：

- Evidence：`.ai/tmp/p168/official/evidence/`
- Run 目录：`.ai/tmp/p168/official/runs/`
- 记录：`.ai/tmp/p168/official/records/`
- Attestation/Manifest：随各 Run 目录保存，路径记录在 `results.json`。

说明：evidence 目录中有 6 个 Bundle，其中 `13224-1ffe73ec` 是修复 Evidence 字段前的首轮 `collect_pickup` 产物；索引只使用修复后的 `8188-b20b350e`。首轮产物未删除（保留审计痕迹），因此全目录旧 Validator 扫描会看到同一 Behavior 的 2 条记录并报 `duplicate_conflict`；官方覆盖读取索引，不受影响。该现象已作为遗留项记录。

---

## 4. Evidence / Attestation 详情

每条官方记录均通过：

1. Bundle v1 解析。
2. `integrity` 重算。
3. `official_contract` 块 behavior/feature 绑定。
4. `contract_digest == sha256(canonical(contract actions + expected))`。
5. `observation_digest == sha256(canonical(observations))`。
6. keyed judge 重新计算，要求 `PASS`。
7. Evidence 签名验证。
8. Attestation 签名验证，并核对：
   - `evidence_payload_sha256`
   - `bundle_payload_sha256`
   - `manifest_digest`
   - `contract_digest`
   - `observation_digest`
   - `judge_digest`

| Behavior | bundle digest（前 12） | attestation digest（前 16） | manifest digest（前 16） |
|---|---|---|---|
| `collect_pickup/collect_on_contact` | `5713c2043674` | `72343997b185f0d8` | `69e536b4436760e6` |
| `contact_damage/damage_amount_is_respected` | `c300642c258d` | `c9aae72cc9324647` | `b0724b3478b0f570` |
| `contact_damage/damage_on_contact` | `de87819708d4` | `e18502dfc57f2198` | `9bee006fd87e95f5` |
| `heal_pickup/heal_damaged_target` | `93e45d094b16` | `2bbd06a9cbc61a3b` | `06f3c1f8e64f6bcb` |
| `openable_door/open` | `2defd95a81ad` | `aa646af244f8dcc2` | `425c73bcbbc29542` |

覆盖验证不信任记录中的自报 `PASS`；以上结果均为重新验证后的状态。

---

## 5. keyed 判定器验证

### 5.1 单元测试

`test_keyed_judge.py`：14 checks，全部 PASS。

覆盖：

- 正常 PASS
- 每条 contract check 均有 verdict
- 额外观测
- 乱序
- 额外观测不导致 FAIL
- 缺失 → INCOMPLETE
- 重复实际 key → INCOMPLETE
- 重复 key 被报告而非静默去重
- 重复 contract key → INCOMPLETE
- 值不匹配 → FAIL
- 非法观测 → INCOMPLETE
- 空观测 → INCOMPLETE
- 旧判定器保持原语义
- 新判定器未替换旧语义

### 5.2 对历史 P5 Scenario 证据的只读复核

对 `.ai/tmp/p166` 的只读记录运行新判定器（不写回）：

| Behavior | 旧 `judge_record` | 新 `judge_record_keyed` | 说明 |
|---|---|---|---|
| `openable_door/open` | PASS | PASS | 一致 |
| `collect_pickup/collect_on_contact` | FAIL | FAIL | 一致 |
| `contact_damage/damage_on_contact` | INCOMPLETE | FAIL | keyed 现在能作出明确判定 |
| `contact_damage/damage_amount_is_respected` | INCOMPLETE | FAIL | 同上 |
| `heal_pickup/heal_damaged_target` | INCOMPLETE | FAIL | 同上 |
| `health/damage` | INCOMPLETE | FAIL | 额外观测 + 契约不匹配 |
| `i_frames/iframes_expire_and_damage_resumes` | INCOMPLETE | FAIL | 额外观测 + 契约不匹配 |
| `save_game/save_slot_persists_world_state` | FAIL | FAIL | 一致 |
| `trigger_switch/latch_once` | FAIL | FAIL | 一致 |

这证明 keyed 判定器不是“放水判定”：历史 P5 记录并未因为新判定器变成 PASS；真正的 PASS 来自第 3 节的官方独立执行。

---

## 6. 覆盖结果

生成：

```text
.ai/tmp/p168/coverage/coverage_matrix.json
.ai/tmp/p168/coverage/coverage_matrix.md
```

摘要：

| 指标 | 值 |
|---|---:|
| rows | 60 |
| 原 `fully_covered` | **0** |
| `with_gaps` | 60 |
| `official_contract_total` | 60 |
| `official_contract_executed` | 5 |
| `official_contract_passed` | 5 |
| `official_contract_failed` | 0 |
| `official_contract_incomplete` | 0 |
| `official_contract_not_decided` | 55 |
| `official_attestation_verified` | 5 |
| `official_contract_fully_covered` | 5 |

原 7 维覆盖仍为 0；官方契约覆盖 5/60 是独立维度，未把任何 Scenario PASS 当成官方 PASS。

Scenario 侧矩阵当前仍为 `evidence_verified=8`、`evaluation_verified=9`、`attestation_verified=8`、`fully_covered=0`；这些数字没有因官方执行被抬高。

---

## 7. Phase 1.56 历史对照

对照文件：`.ai/tmp/p157/bundles_real/p157-real.json`

| 项目 | 结果 |
|---|---|
| Bundle 解析 | 成功 |
| schema | 1 |
| integrity | 通过（无错误） |
| features | 23 |
| behaviors | 60 |
| 历史 HEAD | `dd3a0e4d5d0f6f47e3a9c729e3ce89190f019bd8` |
| generated_at | 2026-11-01T17:54:14Z |
| 签名/Attestation | 目录内只有 Bundle，无 Attestation 文件 |

四条 P5 对照：

| Behavior | expected | actions | actual |
|---|---|---|---|
| `collect_pickup/collect_on_contact` | 一致 | 一致（历史 `action_parameters`） | 一致 |
| `contact_damage/damage_on_contact` | 一致 | 一致 | 一致 |
| `contact_damage/damage_amount_is_respected` | 一致 | 一致 | 仅 `first_observed_frame` 23→24；`observed`/`expected`/args 全一致 |
| `heal_pickup/heal_damaged_target` | 一致 | 一致 | 一致 |
| `openable_door/open`（回归） | 一致 | 一致 | 一致 |

结论：当前官方执行与 Phase 1.56 的 P5 结论一致；唯一差异是帧号从 23 到 24，属于运行时采样时序差异，不改变判定。历史 p157 仍是历史证据，不作为本阶段官方 Attestation 使用。

---

## 8. 回归与验证

### 8.1 新增测试

| 测试 | 结果 |
|---|---|
| `test_keyed_judge.py` | 14/14 PASS |
| `test_official_contract_run.py` | 12/12 PASS（含 O6b Godot 启动失败可见性） |
| `test_official_contract_coverage.py` | 12/12 PASS（C1–C12） |
| `run_tests.py --python-only official_contract` | 2/2 PASS |
| `run_tests.py --python-only keyed_judge` | 1/1 PASS |

### 8.2 分段 Python 回归

| 命令 | 结果 |
|---|---|
| `run_tests.py --python-only validator` | 22/22 PASS |
| `run_tests.py --python-only learning` | 11/11 PASS |
| `run_tests.py --python-only evaluation` | 12/13 PASS；1 个 INCOMPLETE |

`evaluation` 的唯一 INCOMPLETE 是既有 `.ai/tools/evaluation/tests/test_phase160_e2e.py`：直接运行缺少必填参数 `--evidence-dir`，退出码 2。不是本阶段改动导致的失败，也未伪造为 PASS。

### 8.3 全量 Python 套件

尝试执行 `python .ai/tools/run_tests.py --python-only`，被既有 `test_end_to_end_generation.py`（2209 行、真实 Godot 闭环）阻塞超过 8 分钟，未产生最终摘要。为避免留下不确定进程，已停止该自启运行；日志 `.ai/tmp/p168/python_tests.log` 为空，不能作为全量回归通过依据。因此本报告只声明上述分段与新增测试结果，**不声称全量 Python 套件通过**。

### 8.4 静态检查

- `python -m py_compile`：6 个改动/新增 Python 文件全部通过。
- `git diff --check`：无空白错误。
- 旧行为证据测试 `test_behavior_evidence_stage.py`：ALL PASS（含真实 Godot 缺陷注入与恢复）。
- `test_scenario_run.py`：12/12 PASS。

---

## 9. 兼容性、Repo Guard 与工作区

### 9.1 兼容性

| 项目 | 状态 |
|---|---|
| 官方 Contract | 未修改 |
| 产品源码 / Features | 未修改 |
| Scenario Intent / 内容 | 未修改 |
| Generator 行为 | 未修改 |
| Validator 既有规则 | 未修改 |
| 旧 `judge_record()` | 保留，未替换 |
| Evidence v1 | 保持；只加顶层可选 `official_contract` 块 |
| Evidence v2 | 未引入 |
| Attestation Schema | 未升级；复用签名封套并附加块 |
| 原 `fully_covered` 7 维公式 | 未修改 |
| Knowledge Registry / 审批 | 未触碰 |
| 历史 Evidence/Attestation/Evaluation | 未写回 |
| 信任级别 | 未升级；官方 Attestation 仍为 `LOCAL_ISOLATED` |

### 9.2 Repo Guard

只读检查：

```text
HEAD    = 541696593994345f916b2aaf42462cf6fc8247c7
STAGED  = 0
DIRTY   = 1119
```

本阶段新增/修改的代码与测试：

```text
 M .ai/tools/learning/scenario_run.py
?? .ai/tools/evaluation/coverage_matrix.py
?? .ai/tools/evaluation/tests/test_official_contract_coverage.py
?? .ai/tools/learning/tests/test_official_contract_run.py
?? .ai/tools/validator/check_behavior_evidence.py
?? .ai/tools/validator/tests/test_keyed_judge.py
```

本阶段新增的产物：

```text
.ai/tmp/p168/official/
.ai/tmp/p168/coverage/
.ai/tmp/p168/python_tests.log
.ai/context/PHASE_1_68_2_OFFICIAL_EXECUTION_REPORT.md
```

未执行：

- `git commit`
- `git push`
- `git reset`
- `git clean`
- `git add`
- 任何删除/移动历史 Evidence 的操作

说明：工作区在阶段开始前已有 1095 个 dirty 条目（包括 `.ai/context`、`.ai/learning`、部分 `Features/*/feature.yaml` 等历史遗留修改）。本阶段没有编辑这些文件；dirty 从 1095 增至 1119，增量来自上述新代码、测试、p168 产物与本报告。

---

## 10. 遗留问题与结论

### 遗留问题

1. **全量 Python 套件未完成**：既有 e2e 生成测试运行超过 8 分钟仍无摘要，已停止；本报告仅以分段回归和新增测试为依据。
2. **`test_phase160_e2e.py` 需参数**：单独运行时报缺少 `--evidence-dir`，归类 INCOMPLETE；属于既有测试入口约定，不是本阶段回归失败。
3. **官方 evidence 目录有一个首轮旧 Bundle**：`13224-1ffe73ec`（修复前 `collect_pickup`）未删除，保留审计痕迹；官方索引使用修复后 Bundle。全目录旧 Validator 会报重复冲突，覆盖验证按索引工作正常。
4. **`OFFICIAL_EVIDENCE_INVALID` 未单独计入摘要的 failed/incomplete**：当前 5 条全 PASS，未触发；后续若出现被篡改/损坏的官方 Bundle，摘要分类需要补充 `invalid` 计数才能完全闭合。
5. **原 Scenario 覆盖仍为 0 fully covered**：本阶段只新增官方独立维度，未提升原 7 维，也未执行剩余 55 条官方契约。
6. **未进入 Phase 1.68.3**：没有 Knowledge 审批、B2、剩余 42 规则族、信任级别升级。

### 结论

Phase 1.68.2 已完成：

- 官方 Contract 执行链独立于 Scenario 执行链。
- 4 条 P5 官方契约真实执行全部 PASS，Door 回归 PASS。
- Evidence v1 + Attestation + keyed judge + 独立覆盖维度全部接通。
- 原 `fully_covered` 保持 0，未被官方结果污染。
- 历史 p157 对照一致，唯一差异为 `damage_amount_is_respected` 的采样帧 23→24。
- 未修改官方 Contract、产品源码、Scenario、旧判定器或历史证据；未执行 Git 写操作。

**Phase 1.68.2 完成，停在此处。**
