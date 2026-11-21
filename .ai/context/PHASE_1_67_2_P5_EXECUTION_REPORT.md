# Phase 1.67.2 — P5 低风险 Behavior 接入执行报告

日期：2026-11-07
阶段边界：只执行 P5（4 个已确认语义安全的 Behavior）。**未进入 P6，未接入 B2，未扩展到其余规则族。**
Git：**未 commit / push / reset / clean**；HEAD 保持 `54169659`，暂存区为空。

---

## A. 基线信息

| 项 | 值 |
| --- | --- |
| 当前 HEAD | `54169659`（Phase 1.66 已提交） |
| 工作区 | 审计前已有约 1030 项其他阶段未提交变更；P5 后共 1094 项，差额为 P5 产物 |
| Behavior 总数 | **60**（`Features/*/template.yaml#behavior` 动态读取） |
| 已覆盖（场景链，P5 前） | 5 |
| 未覆盖（P5 前） | 55 |
| 信任级别 | `LOCAL_ISOLATED`（未升级） |
| P5 目标 | 4 个场景 |
| Godot | `4.7.stable.official.5b4e0cb0f`（`Godot_v4.7-stable_win64_console.exe`） |
| 执行标签 | `P5` |
| 执行时间 | 4 个场景各约 11–13 秒（含 2 次 replay） |

### A.1 Matrix 输入来源审计

| 文件 | 生成时间 / 来源 | SHA256 | 是否作为 P5 权威输入 |
| --- | --- | --- | --- |
| `.ai/tmp/p164/batch1/matrix_after/coverage_matrix.json` | `2026-11-04T17:10:54Z`，1.64 期产物；**无 git_head 字段**；summary: evidence 12 / eval 12 / mutation 10 | `05d01c64…2e1703` | 否。早于 1.66 提交，且为 gitignored 本地产物，无法证明对应 HEAD；仅用于对照 |
| `.ai/tmp/p167/matrix_p5/coverage_matrix.json` | **本次在 HEAD `54169659` 现场生成**（2026-11-07），`coverage_matrix.py` 默认输入；60 行全部 `CONTRACT_PRESENT`；4 个目标的 `contract_version` 与当前契约逐字一致 | `6321f09b…d3c09d` | **是**（仅用于 `extract.py` 的契约/行为行；其 evidence 字段不参与生成） |
| `.ai/tmp/p167/matrix_p5_full/coverage_matrix.json` | 同上，追加 `--evidence-dir .ai/tmp/p166/evidence --runs-dir .ai/tmp/p166/runs --eval-dir .ai/tmp/p166/evaluation` | `3f24a8e2…ec2241` | 仅用于 Planner 对照，**未**作为覆盖结论 |

结论：P5 生成使用的 Matrix 来源可确认（当前 HEAD 现场生成、60/60 契约存在、版本一致）。旧 p164 Matrix 的过期性与不可复现性已记录，未直接沿用作权威输入。

已知限制：`--eval-dir .ai/tmp/p166/evaluation` 是**聚合** `evaluation.json`，`coverage_matrix.py` 期望逐任务评估报告，因此该次矩阵 `evaluation_verified=0`；这是矩阵与场景链的集成缺口，不是 P5 执行失败。P5 的 Evaluation 结论以 `scenario_results.json` / P5 结果文件为准。

---

## B. Knowledge 结果

### B.1 候选与审批

| 项 | 数量 |
| --- | --- |
| 本次 `extract.py` 生成候选 | 19（4 目标） |
| `feedback.py` 新增候选（P5 执行回流） | 12 |
| 显式审批 | **4**（仅 `SOURCE_OBSERVATION:guards`） |
| 审批者记录 | `user:p167`，scope `LOCAL_REVIEW` |
| 仍为 `PENDING_REVIEW` | 28（P5 前 1 + 本轮其余 27） |
| APPROVED（全库） | 59（55 + 4） |
| SUPERSEDED / ARCHIVED | 5 / 10（未新增） |
| OPEN 冲突 | **0** |

### B.2 实际使用的 Knowledge Ref

| Behavior | Knowledge ID | 引用源码 |
| --- | --- | --- |
| `collect_pickup/collect_on_contact` | `k-875dbe2de3b9fca9` | `Features/collect_pickup/collect_pickup.gd:29` |
| `contact_damage/damage_on_contact` | `k-af3decf8ebc135bd` | `Features/contact_damage/contact_damage.gd:20/28/31` |
| `contact_damage/damage_amount_is_respected` | `k-8423097baa8ec620` | 同上 |
| `heal_pickup/heal_damaged_target` | `k-e219d71a96f8bd0d` | `Features/heal_pickup/heal_pickup.gd:18/21/23` |

审批前逐行核对：4 条候选的每条 `condition` 与源码对应行**逐字一致**，`source_references` 均带 64 位 SHA256，契约 `actions/expected` 形状与 `foreign_group_ignored` 规则匹配。

**机制缺口（如实记录）**：`knowledge_v2.approve()` 只写入 `reviewer` 字符串、`reason` 与 `LOCAL_REVIEW` scope，无法在密码学或流程上区分 Agent 与人类 Reviewer。本次 4 条审批由用户在对话中显式选择“批准”，Agent 仅执行写入；但该审批**不能被系统证明为人类身份**，与 Phase 1.61 已记录的信任边界一致。

---

## C. Scenario 结果

| Behavior | Scenario | Validation | Execution | Evidence | Attestation | Evaluation | Official Contract |
| --- | --- | --- | --- | --- | --- | --- | --- |
| `collect_pickup/collect_on_contact` | `s-eef9972034da734b` | VALID | PASSED | EVIDENCE_VERIFIED | ATTESTED_VERIFIED | VERIFIED_PASS | **FAIL** |
| `contact_damage/damage_on_contact` | `s-d2fe30d380537d07` | VALID | PASSED | EVIDENCE_VERIFIED | ATTESTED_VERIFIED | VERIFIED_PASS | **INCOMPLETE** |
| `contact_damage/damage_amount_is_respected` | `s-d503c62564c391ef` | VALID | PASSED | EVIDENCE_VERIFIED | ATTESTED_VERIFIED | VERIFIED_PASS | **INCOMPLETE** |
| `heal_pickup/heal_damaged_target` | `s-9efdc90351f7112e` | VALID | PASSED | EVIDENCE_VERIFIED | ATTESTED_VERIFIED | VERIFIED_PASS | **INCOMPLETE** |

每条场景均由 `foreign_group_ignored` 规则生成：把 `physics.overlap` 的接触体改到非目标组 `p166_foreign`，期望信号为 0、布尔终态保持 false。4 条场景动作均为 `physics.overlap` + `simulation.advance_frames(1)`（见 §D.1 修复）。

### C.1 官方契约为什么没有 PASS

- `collect_pickup`：官方期望 `node.freed=True`，本次证据观测 `False` → **FAIL**。这是场景语义（外来组不应收集）与官方契约（目标组应收集）的**有意差异**，不是产品缺陷。
- 其余 3 条：`observed 1 check(s), contract declares 2` → **INCOMPLETE**。生成场景只为自己的否定断言采集观测；官方契约要求的 `health.current` 未被场景请求，因此证据里没有该观测。官方判定在**同一份证据**上无法完成，故为 INCOMPLETE，而不是 FAIL。

结论：这 4 条证明的是“新增知识可以驱动真实执行并产生可验证的场景结论”，**不能**证明官方契约已被覆盖；官方契约 PASS 数仍为 0。按任务要求，FAIL/INCOMPLETE **不计入**成功覆盖。

---

## D. Generator 修复（已获授权的最小变更）

### D.1 失败现象与根因

首次生成后 4 条全部 `INVALID`，原始错误（4 条相同）：

```text
INVALID: Invalid behavior contract: behavior[0].expected only asserts absence of
behaviour while no action advances frames; PASS would be decided without any
observation window
```

根因链：

1. `_rule_foreign_group` 把契约期望反转成否定断言（signal 0 / bool false）。
2. 这 4 个契约的动作只有 `physics.overlap`，本身不含 `simulation.advance_frames`。
3. `feature_behavior_evidence.py:393-403` 的 Phase 1.45 最小证据规则要求：只断言“什么都没发生”时，动作序列必须至少推进一帧，否则拒绝。
4. P4 的 `trigger_switch/latch_once` 同样用该规则却通过，因为它的契约动作里已有 2 个 `simulation.advance_frames`；因此该缺陷只在“契约无帧推进”的目标上暴露。

### D.2 修复

`scenario_generator.py` / `_rule_foreign_group`，在动作构造后、期望构造前：

```python
if not any(action.get("type") == "simulation.advance_frames" for action in actions):
    actions.append({"type": "simulation.advance_frames", "params": {"frames": 1}})
```

不改期望、不改契约、不改 Validator/Evaluation、不改产品源码。既有场景若已含帧推进则**不追加**，保证 P4 `s-37cd4dc9f084950e` 的 ID 稳定。

### D.3 回归测试

`test_scenario_generator.py` 新增 G17–G20：

| 检查 | 内容 |
| --- | --- |
| G17 | 无帧契约 → 追加且仅追加 1 帧（`frames=1`） |
| G18 | 追加帧不改变反转后的否定期望（signal=0 / equals=false） |
| G19 | 已有帧推进的契约 → 不出现第二个帧动作 |
| G20 | P4 `trigger_switch/latch_once` 场景 ID 仍为 `s-37cd4dc9f084950e` |

结果：**20/20 PASS**。

---

## E. Regression / Repo Guard

| 检查 | 结果 |
| --- | --- |
| `test_scenario_generator.py` | 20/20 PASS |
| `test_scenario_validator.py` | 18/18 PASS |
| `test_scenario_run.py` | 12/12 PASS |
| `test_result_analysis.py` | 14/14 PASS |
| `test_feedback.py` | 13/13 PASS |
| `test_knowledge_store.py` | 20/20 PASS |
| `test_planner.py` | 16/16 PASS |
| 学习链合计 | **113 checks / 0 failures** |
| `scenario_validate.py --all` | **9/9 VALID**（exit 0） |
| `validator/validate.py` | **0 error / 17 warning**（与 P4 一致，exit 0） |
| P4 执行记录 | 5 条 `scenario_results.json` 记录 **deep-equal** 保留 |
| P4 场景索引 | 5 条条目逐字未变 |
| 历史证据 | 9/9 bundle digest 与签名复验通过（P4 5 + P5 4） |
| 历史 Knowledge | `.ai/knowledge/behavior_verification` 无改动 |
| 产品源码 / 契约 / Baseline | 未修改 |
| Validator / Evaluation / Matrix 代码 | 未修改 |
| HEAD / 暂存区 | `54169659` / 空 |

工作区中 `Features/attack_emitter/feature.yaml`、`Features/trigger_switch/template.yaml` 及其他 6 个 `.ai/tools/**` 文件在 P5 开始前已是修改状态（1.67.1 审计已记录），P5 未触碰；P5 的代码改动只有 `scenario_generator.py` 与 `test_scenario_generator.py`。

---

## F. 变更审计

### F.1 新增文件

- `.ai/learning/scenarios/`：4 个 P5 场景（`s-eef997…`、`s-d2fe30…`、`s-d503c6…`、`s-9efdc9…`）
- `.ai/learning/validation/`：4 份验证报告
- `.ai/learning/results/`：4 份 P5 结果分析文件
- `.ai/tmp/p166/results/`：4 份 P5 执行记录
- `.ai/tmp/p166/evidence/`：4 个证据 bundle + 4 个签名 sidecar
- `.ai/tmp/p166/runs/<run_id>/`：4 组 manifest + attestation + 签名
- `.ai/knowledge/behavior_learning/records/`：4 条已批准 guards 记录
- `.ai/knowledge/behavior_learning/candidates/`：12 条新反馈候选
- `.ai/tmp/p167/p5/**`、`.ai/tmp/p167/matrix_p5*`：本阶段审计/执行临时产物（gitignored）

### F.2 修改文件

| 文件 | 变化 |
| --- | --- |
| `.ai/tools/learning/scenario_generator.py` | 条件补 1 帧（唯一生成器改动） |
| `.ai/tools/learning/tests/test_scenario_generator.py` | 新增 G17–G20 |
| `.ai/learning/scenarios.json` | 合并 9 条（P4 条目逐字未变；4 条新条目状态 VALID） |
| `.ai/learning/scenario_validation.json` | 合并 9 条报告（9 VALID） |
| `.ai/learning/scenario_results.json` | 合并 9 条（P4 记录 deep-equal，P5 4 条追加） |
| `.ai/learning/result_analysis.json` | 对 9 条重算（P5 4 条 SOURCE_CONFIRMED） |
| `.ai/learning/feedback.json` | 对 9 条重算（27 candidates，0 rejected） |
| `.ai/learning/source_analysis/…`（4 份） | `extract.py` 刷新为当前契约版本 |
| `.ai/learning/results/s-<P4>.json`（5 份） | 重算分析（仅时间戳/派生字段变化，记录语义不变） |
| `.ai/knowledge/behavior_learning/` | 4 条候选 → 记录（APPROVED），12 条新候选 |

### F.3 未修改

- 所有 `Features/**` 契约、场景、产品 GDScript。
- `validator/**`、`evaluation/**`、`scene_composer/**` 的判定逻辑。
- Baseline、Holdout、历史 Evidence、历史 Knowledge（`behavior_verification`）。
- `learning_plan.json` / `.md`：P5 的 Planner 对照曾生成 275 任务版本，因矩阵 evaluation 维度失真，已**恢复为 P4 的 276 任务版本**；对照结果只保存在 `.ai/tmp/p167/p5/`。

### F.4 Planner 对照（仅观察，不持久化）

使用 `matrix_p5_full` 运行后：

- 4 个目标均**不再**出现 `DESIGN_TEST_SCENARIO`（`contact_damage/damage_on_contact` 无任务；其余只剩依赖分析或 mutation 设计）。
- 总任务 276 → 275，但 `DESIGN_TEST_SCENARIO` 47 → 51，原因是该矩阵的 evaluation 维度为 0，导致其他已评估 Behavior 被重新排入设计任务。该数字**不能**作为“计划改善”的证据；正式计划已回滚到 P4 版本。

---

## G. 最终统计

| 项 | 数量 |
| --- | --- |
| 成功执行（execution PASSED） | **4** |
| 失败执行（FAILED） | 0 |
| 阻塞（ENVIRONMENT_BLOCKED） | 0 |
| 未执行 | 0 |
| Evidence 验证通过 | 4/4 |
| Attestation 验证通过 | 4/4 |
| 场景 Evaluation `VERIFIED_PASS` | 4/4 |
| 官方契约 PASS | **0/4** |
| 官方契约 FAIL / INCOMPLETE | 1 / 3 |
| 实际新增“覆盖”（按官方契约，严格口径） | **0** |
| 场景链覆盖 | **5/60 → 9/60**（+4 条真实执行、可追溯的场景） |
| 官方契约 Fully Covered | 0/60（未变） |
| 当前总覆盖率（官方口径） | **0/60** |

P5 的成功标准按任务书执行：证明新增 Knowledge 能在不破坏原有契约语义的前提下驱动真实 Godot 执行，并产生可信、可追溯的结果。该目标已达成；**没有**把 INCOMPLETE/FAIL 计入覆盖，也没有把场景 PASS 冒充官方契约 PASS。

---

## H. 已知限制与风险

1. **官方契约判定受证据形状限制**：生成场景只采集自己的期望，官方契约的额外观测不在证据里，导致 INCOMPLETE。若要让官方契约也得到公平判定，需要让场景同时采集官方检查，或单独跑官方契约采集；这属于生成/执行链扩展，未在本阶段授权。
2. **`foreign_group_ignored` 会丢弃非布尔契约期望**：例如 `health.current` 的数值断言不会被反转或保留，P5 的 3 条场景因此只断言“无信号”。否定信号仍能证明守卫路径未触发，但断言强度低于原契约；这是既有规则的限制，建议后续单独评估。
3. **审批身份不可验证**：`LOCAL_REVIEW` 只记录字符串；本次 `user:p167` 是用户显式授权，但系统无法证明人类身份。
4. **矩阵与场景链未打通**：`coverage_matrix.py` 不能消费 `.ai/tmp/p166/evaluation/evaluation.json` 的聚合格式，P5 证据需显式 `--evidence-dir/--runs-dir`；evaluation 维度仍为 0。
5. **Registry 状态双权威**：场景文件仍 `execution_status=NOT_EXECUTED`，真实状态在 `scenario_results.json`。本阶段未改变该约定（与 1.67.1 审计一致）。
6. **P4 派生分析文件被重算**：`result_analysis --all` 覆盖了 5 个 P4 分析文件的时间戳/派生字段；P4 执行记录与证据未变。

---

## I. 停止点

P5 已完成并停止。**未启动 P6，未接入 B2，未处理其余 42 个规则族缺口，未提交/推送。** 等待下一阶段授权。
