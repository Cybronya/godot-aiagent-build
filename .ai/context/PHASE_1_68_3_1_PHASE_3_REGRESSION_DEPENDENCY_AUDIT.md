# Phase 1.68.3.1 — Phase 3 Regression Dependency Audit

日期：2026-11-10  
范围：Scene Composer Level 3 剩余测试的只读依赖审计与执行矩阵  
最终状态：**AUDIT COMPLETE — EXECUTION NOT STARTED**

---

## 1. Baseline

| 项目 | 值 |
|---|---|
| HEAD | `04f50636c7d3afb37a2a58454cb4ae16f1a38593` |
| Branch | `master` |
| staged | 0 |
| dirty（Phase 3 开始时） | 1054 |
| Godot | `../Godot_v4.7-stable_win64_console.exe` |
| `.godot/global_script_class_cache.cfg` | 存在，14768 bytes |
| Scene Composer 测试文件 | 31 个 |
| 任务清单 | 30 个（含 `test_behavior_protocol_consistency.py`，漏列 `test_artifact_evidence_validator.py`） |
| 已完成基线 | Phase 2 目标测试 PASS，158.245 秒，150 PASS / 0 FAIL |

### 1.1 数量口径

目录实际有 **31** 个 `test_*.py`。任务给出的清单是 **30** 个，其中包含已经在 Phase 2 完成的：

```text
test_behavior_protocol_consistency.py
```

但该清单漏掉了实际存在、且有明确历史 PASS 记录的：

```text
test_artifact_evidence_validator.py
```

因此正确口径是：

- 实际测试文件 **31** 个；
- Phase 2 已完成 target；
- 真正剩余的测试是 **30** 个（31 − target），其中包括清单漏掉的 artifact 测试；
- 报告矩阵采用 **31 行**（30 个剩余 + target 基线行），但覆盖统计把 target 单列，避免重复计数。

后续执行不能按任务清单的 30 个原样照跑，否则会漏掉 artifact 测试；也不能把 target 重复算成新的剩余测试。

---

## 2. Historical Execution Audit

### 2.1 可用证据

| 来源 | 能证明什么 | 限制 |
|---|---|---|
| `.ai/tmp/p168/scene_composer_tests.log` | 只有 `[1/31] PASS test_artifact_evidence_validator.py` | 目标测试启动后没有第二行输出；不能证明后续测试通过 |
| Phase 1.68.3 报告 §5.2 | Level 1 段通过；不含 scene_composer 文件 | 不能据此推断 scene_composer PASS |
| Phase 1.68.3 报告 §5.3 | validator 22/22；明确点名 3 个 scene_composer 测试通过 | 没有逐测试原始日志；属报告级证据 |
| Phase 1.68.3 报告 §5.3 | runtime 5/5 | 该过滤器路径也匹配 2 个 scene_composer 测试，但报告没有点名 |
| Phase 1.68.3 报告 §5.4 | scene_composer 段第 2 个测试被停止，30 个未完成 | 不是 PASS 记录 |
| Phase 2 报告 | target 独立执行 PASS，exit 0 | 只覆盖 target，不覆盖剩余 30 个 |

### 2.2 历史状态判定

状态只使用任务规定的四类。对报告点名但没有逐测日志的项，额外标注证据强度：

- **证据强度 A**：有逐测试 PASS 行；
- **证据强度 B**：报告明确点名通过，但没有原始逐测日志。

| 测试 | 历史状态 | 证据 |
|---|---|---|
| `test_artifact_evidence_validator.py` | **VERIFIED_PASS** | 强度 A：`[1/31] PASS` 直接日志；同时属于 validator 22/22 |
| `test_capability_contract_validator.py` | **VERIFIED_PASS** | 强度 B：Phase 1.68.3 报告明确点名 validator 段通过 |
| `test_scene_validator_intent_input.py` | **VERIFIED_PASS** | 强度 B：Phase 1.68.3 报告明确点名 validator 段通过 |
| `test_runtime_instance_evidence.py` | **UNKNOWN** | runtime 段 5/5 且路径匹配，但报告未点名，不能把批次结果当成逐测 PASS |
| `test_scene_intent_runtime.py` | **UNKNOWN** | 同上；它名字含 runtime，但不能仅凭批次推断 |
| 其余 26 个（含 target 的历史状态） | **NOT_EXECUTED** | 没有有效逐测执行记录 |
| 任意测试 | **VERIFIED_FAIL** | 没有发现明确的逐测失败记录 |

统计：

```text
history_verified_pass = 3
history_verified_fail = 0
history_not_executed = 26   # 含 target
history_unknown      = 2
total                = 31
```

说明：

- `test_artifact_evidence_validator.py` 同时出现在 scene_composer 日志和 validator 段，只计一次。
- `VERIFIED_PASS (B)` 仍是报告级证据，不是逐测日志。若审查要求 A 级证据，这两项应降为 `UNKNOWN`，但本报告不会把它们算成两次执行。
- 不得把 `validator 22/22` 或 `runtime 5/5` 直接当作任何未点名测试的 PASS。

### 2.3 Phase 2 的独立贡献

Phase 2 只覆盖：

```text
test_behavior_protocol_consistency.py
```

结果：

```text
150 PASS / 0 FAIL / exit 0 / 158.245s
```

它不是剩余 30 个测试的通过记录，也不能替代 Level 3 全段结果。报告把它单独列为 `PHASE2_VERIFIED_PASS`，不混入历史 3 个 PASS。

---

## 3. Dependency Model

### 3.1 依赖类型

| 类型 | 审计结论 |
|---|---|
| Python import | 所有测试都按自身路径计算 `PROJECT_ROOT` 并插入 `sys.path`；不依赖外部 `PYTHONPATH` |
| 跨测试 import | 7 个测试导入 `test_scene_builder_intent_input` 的常量/函数；这是模块级复用，不执行其 `main()` |
| 跨测试产物 | 未发现测试读取另一个测试新生成的 Evidence、workspace 或契约文件 |
| Godot Runtime | 30 个剩余文件中 11 个需要真实 Godot（另加已完成的 target，共 12 个）；其余 19 个为 Python-only |
| 项目资源 | `Features/`、`Scenes/`、`Tests/`、`.ai/context/*.yaml`、`feature_index.json`、协议 manifest、probe |
| `.godot` 缓存 | 通过 repo 根启动 Godot 的测试需要；`run_tests.py` 启动时会刷新一次 |
| Evidence 写入 | 只写 `.ai/tmp/behavior`、`.ai/tmp/runtime-instance`、`.ai/tmp/composite` 及若干固定测试目录 |
| Official Evidence | 未发现任何 scene_composer 测试写入 `.ai/tmp/p168/official`、Attestation 或历史 p157/p166/p167/p168 |
| 环境变量 | 测试本身不依赖业务环境变量；Godot 位置由 `find_godot()` 从项目父目录/PATH 解析 |
| 子进程 | 行为/组合测试启动 Godot；`test_composite`、`test_plan_generator` 启动 Python CLI；`test_runtime_instance_evidence` 也启动 CLI |

### 3.2 跨测试模块依赖

以下文件导入 `test_scene_builder_intent_input`：

```text
test_artifact_evidence_validator.py
test_capability_contract_validator.py
test_component_instance_materialization.py
test_component_instance_ownership.py
test_external_artifact_evidence.py
test_feature_capability_adoption.py
test_feature_capability_pipeline.py
test_scene_compatibility_gate.py
test_scene_intent_capability.py
```

该模块只提供常量和函数，不应执行测试；但它是执行顺序中的一个软前置：不要删除、重命名或单独破坏这个测试文件。它本身没有被本阶段执行。

### 3.3 Godot 与 `.godot` 缓存

- `run_tests.py` 在启动时调用 `refresh_import_cache()`；正常从仓库运行会生成/刷新 `.godot`。
- `BehaviorWorkspace` 和 `CompositeWorkspace` 复制项目后各自执行 `--import`，不依赖仓库 `.godot` 的类缓存。
- `test_runtime_instance_evidence.py` 的 Case 1 直接在仓库项目根加载真实 Feature；需要仓库 `.godot` 类缓存。
- `test_feature_behavior_evidence.py` 既使用临时 workspace，也会在部分 Case 对仓库根运行 probe；需要仓库缓存。
- Phase 2 已证明：隔离副本排除 `.godot` 时，`heal_pickup` 的 `Health` 类型会解析失败；执行 `--import` 后全部 PASS。这个缓存依赖必须写入执行前置条件。

### 3.4 Timeout

| 范围 | 超时 |
|---|---|
| `run_tests.py` 默认 | 300 秒/测试 |
| `test_feature_behavior_evidence.py` | **900 秒**（显式覆盖） |
| `test_end_to_end_generation.py` | 1800 秒（不在本矩阵） |
| Phase 2 target 实测 | 158.245 秒，未触发 300 秒 |
| 其他 scene_composer 测试 | 默认 300 秒，无单独覆盖 |

不得用延长超时掩盖外部终止或死锁。`test_feature_behavior_evidence.py` 的 900 秒是现有运行器配置，不是本阶段新增。

---

## 4. Classification

分类按“最重要的执行前置条件”确定；同时属于多个类别的，在备注中注明。

| Group | 含义 | 数量 |
|---|---|---:|
| A | Python-only / 静态契约与 Scene Intent 管线 | 12 |
| B | 单 Feature 的真实 Godot Runtime | 8 |
| C | Component / Instance / Artifact 静态证据 | 7 |
| D | 全 Feature Behavior / Evidence | 1 |
| E | Scene Intent / Scene Integration | 0；相关测试因无 Godot 前置，归入 A |
| F | Composite / End-to-End | 2 |
| 合计 | 不含 target 的 30 个清单 | 30 |

`E` 为 0 不是遗漏：Scene Intent 相关测试虽然领域上属于 E，但其最重要执行前置仍是“Python-only + 临时目录”，因此按任务规则归 A，并在矩阵备注标明领域。

---

## 5. Execution Matrix

说明：

- `Runtime` 列写执行性质与运行器预算；`Python` 表示不启动 Godot。
- `Historical` 只按第 2 节的状态；target 额外标注 Phase 2。
- `Isolation` 写实际临时/证据路径；`repo` 表示读取仓库资源，不表示允许写仓库。
- 所有测试都建议串行；本表没有并行安全结论。

| Test | Historical Result | Runtime | Dependencies | Isolation | Execution Group |
|---|---|---|---|---|---|
| `test_behavior_protocol_consistency.py` | NOT_EXECUTED（P1.68.3）；**Phase2 PASS** | Godot 300s | behavior protocol/evidence/runtime；manifest、probe、23 Feature/60 Behavior | `.ai/tmp/protocol_tests_*`、`.ai/tmp/behavior`；temp project with `--import` | B（基线；已做过一次） |
| `test_behavior_time_driven.py` | NOT_EXECUTED | Godot 300s | behavior protocol/evidence/runtime；moving_platform/player_movement/trigger_switch/openable_door | `.ai/tmp/time_driven_*`、`.ai/tmp/behavior` workspace | B |
| `test_capability_contract_validator.py` | **VERIFIED_PASS (B)** | Python 300s | capability_contract_validator、capability_contracts、registry、gate、scene composer/intent | system temp；repo fixtures read-only | A（契约/管线） |
| `test_chase_movement_behavior.py` | NOT_EXECUTED | Godot 300s | behavior protocol/evidence/runtime；chase fixture、nested fixture | `.ai/tmp/chase_behavior_*`、`.ai/tmp/behavior` | B |
| `test_component_instance_materialization.py` | NOT_EXECUTED | Python 300s | component_instance_resolver、capability contract、scene builder/composer/intent | system temp | C |
| `test_artifact_evidence_validator.py` | **VERIFIED_PASS (A)** | Python 300s | artifact/capability validators、generate/composer/intent、template loader、`test_scene_builder_intent_input` | system temp | C |
| `test_component_instance_ownership.py` | NOT_EXECUTED | Python 300s | component_instance_ownership、external resolver、artifact evidence、scene composer | system temp | C |
| `test_composite.py` | NOT_EXECUTED | Python 300s | composite、scene_composer CLI；feature/resources | system temp **+ transient `Scenes/E2eCompositeTestPlayer.tscn`** | A（Integration；必须单独串行） |
| `test_composite_behavior_evidence.py` | NOT_EXECUTED | Godot 300s | composite/behavior protocol、composite evidence、runtime；project copy | `.ai/tmp/composite*`、`.ai/tmp/composite/workspaces` | F |
| `test_condition_gate_behavior.py` | NOT_EXECUTED | Godot 300s | behavior protocol/evidence/runtime；condition_gate fixture | `.ai/tmp/condition_gate_behavior_*`、`.ai/tmp/behavior` | B |
| `test_contact_damage_behavior.py` | NOT_EXECUTED | Godot 300s | behavior protocol/evidence/runtime；contact/Health fixtures | `.ai/tmp/contact_behavior_*`、`.ai/tmp/behavior` | B |
| `test_entity_root_instance.py` | NOT_EXECUTED | Python 300s | scene builder/composer/validator、entity root、check composition、generator | system temp | C |
| `test_external_artifact_evidence.py` | NOT_EXECUTED | Python 300s | artifact/capability validators、external resolver、scene composer/intent | system temp project | C |
| `test_feature_behavior_evidence.py` | NOT_EXECUTED | **Godot 900s** | behavior protocol/evidence、instance evidence、runtime；23 Feature/60 Behavior；repo probes | `.ai/tmp/behavior_tests_*`、`.ai/tmp/behavior` workspace | D |
| `test_feature_capability_adoption.py` | NOT_EXECUTED | Python 300s | capability contract/registry/gate、feature capabilities、scene composer/intent | system temp Features/index；repo read-only | A（全 Feature 审计；见风险 R1） |
| `test_feature_capability_pipeline.py` | NOT_EXECUTED | Python 300s | gate、feature capabilities、scene composer/intent/validator | system temp Features/index；repo read-only | A（全 Feature 审计；见风险 R1） |
| `test_feature_instance_evidence.py` | NOT_EXECUTED | Python 300s | scene composer、template loader、instance evidence | system temp copy of Features | C |
| `test_health_bar_behavior.py` | NOT_EXECUTED | Godot 300s | behavior protocol/evidence/runtime；health_bar fixture | `.ai/tmp/health_bar_behavior_*`、`.ai/tmp/behavior` | B |
| `test_health_behavior.py` | NOT_EXECUTED | Godot 300s | behavior protocol/evidence/runtime；Health fixture；9 类缺陷注入 | `.ai/tmp/health_behavior_*`、`.ai/tmp/behavior` | B |
| `test_instance_evidence_reconciliation.py` | NOT_EXECUTED | Python 300s | external resolver、instance evidence、validator check | system temp Features；repo read-only | C |
| `test_plan_generator.py` | NOT_EXECUTED | Python 300s | plan_generator、composite、scene_composer CLI | system temp | A（Integration） |
| `test_runtime_instance_evidence.py` | **UNKNOWN** | Godot 300s | instance/runtime evidence、probe；6 runtime Features | `.ai/tmp/runtime_evidence_*`、`.ai/tmp/runtime-instance`；repo root Case 1 | B |
| `test_scene_builder_intent_input.py` | NOT_EXECUTED | Python 300s | scene builder/intent/template loader | system temp | A（helper；被 9 个测试 import） |
| `test_scene_compatibility_gate.py` | NOT_EXECUTED | Python 300s | check composition、gate、scene builder/composer/intent/validator | system temp | A（见风险 R1） |
| `test_scene_composer.py` | NOT_EXECUTED | Python 300s | scene composer、dependency resolver、builder/validator、generator | system temp；读取全部 Features | A（见风险 R1） |
| `test_scene_intent_capability.py` | NOT_EXECUTED | Python 300s | capability registry/gate、feature capabilities、scene builder/composer/intent | system temp | A |
| `test_scene_intent_contract.py` | NOT_EXECUTED | Python 300s | `scene_composer_schema.yaml`、`CONTRACT_INDEX.yaml`、相关 contract | 无临时目录；纯只读 | A |
| `test_scene_intent_runtime.py` | **UNKNOWN** | Python 300s | scene builder/composer/intent/template loader | system temp | A |
| `test_scene_validator_intent_input.py` | **VERIFIED_PASS (B)** | Python 300s | check composition、generator、scene builder/intent/validator | system temp | A |
| `test_slime_contact_arena.py` | NOT_EXECUTED | Godot 300s | composite/behavior protocols、composite evidence、runtime；formal arena | `.ai/tmp/slime_bad_contracts`、`.ai/tmp/composite/workspaces` | F |
| `test_stun_behavior.py` | NOT_EXECUTED | Godot 300s | behavior protocol/evidence/runtime；stun fixture；缺陷注入 | `.ai/tmp/stun_behavior_*`、`.ai/tmp/behavior` | B |

---

## 6. Shared Resource Risks

### R1 — 全 Feature 目录与当前数据不一致（高优先级）

当前静态事实：

```text
Features 目录               31
有 template.yaml            23
有非空 capabilities.required 23
无 template / 无能力声明      8
```

8 个目录：

```text
anima_behaviour
attribute_editor
audio_player_pool
blackboard
clean_copy
flying_letter
pedestal_interaction
pickable_audio
```

以下测试会遍历全部 31 个目录并断言每个目录都有模板或能力声明：

| 测试 | 断言 | 当前静态预期 |
|---|---|---|
| `test_scene_composer.py` | 每个 Feature 目录都有 `template.yaml` | 8 个 `template: ... exists` 失败 |
| `test_feature_capability_pipeline.py` | 每个真实 Feature 都声明至少一个能力 | 8 个目录不满足 |
| `test_feature_capability_adoption.py` | 每个真实 Feature 都声明能力，并与场景证据一致 | 8 个目录不满足，且会产生额外声明/证据失败 |

这不是执行结果，而是**静态预测的执行风险**。本阶段不修改测试，也不修改 Feature 数据。

影响：

- 这三项不能在 Phase 4 中期待“直接绿”；
- 如果执行，必须如实记录 FAIL 或 INCOMPLETE，不能因为历史阶段曾通过就改写结果；
- 需要用户决定：是让测试明确排除无 Scene Template 的 code-library Feature，还是补齐这些 Feature 的数据。两者都属于后续修复/测试维护，必须在 Phase 4 前另行授权；
- 不应为了让测试通过而批量伪造 `template.yaml` 或能力声明。

### R2 — `test_composite.py` 会短暂写入真实仓库

`test_composite.py` 在 P5 段创建：

```text
Scenes/E2eCompositeTestPlayer.tscn
```

并在 `finally` 中删除它及可能的 `.tscn.uid`。异常退出或被外部终止时，仓库会留下未跟踪文件。

要求：

- 单独执行，不与任何读取 `Scenes/` 的测试并行；
- 执行前后对比 `git status` 与该路径；
- 若残留，先保留现场并停止，不在 Phase 3 清理；
- 不能把残留误判为测试通过或产品文件。

### R3 — 固定测试临时目录

以下路径不是随机 run ID，多个运行会复用：

```text
.ai/tmp/composite_protocol_cases
.ai/tmp/composite_bad_contracts
.ai/tmp/composite_invalid_contracts
.ai/tmp/slime_bad_contracts
```

它们只被对应的 composite/slime 测试使用，不读取其他测试的产物；但同一测试不能并行，且上次中断留下的文件可能影响诊断。执行前只记录，不清理；执行后保留。

### R4 — 共享 `.ai/tmp/behavior` / `runtime-instance` / `composite`

三个证据根目录包含随机 run ID 子目录，正常情况下不同测试不会覆盖：

```text
.ai/tmp/behavior
.ai/tmp/runtime-instance
.ai/tmp/composite
```

但仍共享父目录与磁盘/Godot user data。没有证据证明并行安全，因此所有行为/组合测试串行。

### R5 — 共享 Godot `user://`

`BehaviorWorkspace` 默认不传 `user_dir_tag`，多个测试使用同一个 user 目录。虽然没有测试显式传入自定义 tag，但这也是串行执行的额外理由。

### R6 — `.godot` 类缓存

见 §3.3。仓库根加载的真实 Feature 需要 `global_script_class_cache.cfg`；隔离副本必须 `--import`。Phase 2 已证明缺少它会报 `Could not find type "Health"`。

### R7 — stdout 块缓冲

`run_tests.py` 使用 `Popen` 管道且不设置 `-u`/`PYTHONUNBUFFERED`；测试也没有 `flush=True`。运行中日志可能长时间为空。Phase 4 诊断时应使用 `python -u` 或 `PYTHONUNBUFFERED=1`，但不得修改测试/运行器，也不得把“无输出”当成死锁。

### R8 — 历史证据不足

- 只有 1 个明确的逐测 PASS 行；
- 2 个是报告点名；
- 2 个只能确认进入了 runtime 批次，无法确认逐测结果；
- 25 个没有有效记录（不含 target；含 target 的历史未执行数为 26）。

因此本矩阵不能宣称“历史全部已通过”，也不能用 Phase 2 的 target PASS 代替其余测试。

---

## 7. Recommended Execution Order

### P0 — Preflight（不执行测试）

1. 记录 HEAD、staged、dirty、`git status --porcelain`；
2. 记录 31 个测试文件、23 个模板、7 个 instance、6 个 runtime 的静态计数；
3. 确认 Godot 二进制和 `.godot/global_script_class_cache.cfg`；
4. 对 `.ai/tmp/p168/official/evidence/evidence_index.json`、历史 p157/p166/p167/p168 做 SHA256；
5. 确认没有残留 Python/Godot 进程；
6. 记录 `.ai/tmp/behavior`、`runtime-instance`、`composite` 的现有集合；
7. 先决定 R1 的处理方式；否则不要开始全量 Level 3。

### Batch A — Python-only 静态/管线（12 个）

建议顺序：

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

说明：

- 前两个是契约/helper，先建立基线；
- 三个 R1 高风险全 Feature 测试（pipeline/adoption/scene_composer）放在安全静态测试之后；一旦其中一个 FAIL，立即停止，避免后续结果被污染；
- `test_composite.py` 放最后，因为它会短暂写真实 `Scenes/`；
- 不启动 Godot，仍串行执行；没有并行安全证据。

### Batch C — Component / Instance 静态证据（7 个）

```text
test_artifact_evidence_validator.py
test_component_instance_materialization.py
test_component_instance_ownership.py
test_external_artifact_evidence.py
test_entity_root_instance.py
test_feature_instance_evidence.py
test_instance_evidence_reconciliation.py
```

这些测试主要使用 system temp，但依赖相同的 Feature/Blueprint/Scene 输入，串行便于定位；不启动 Godot。

### Batch B — 单 Feature Godot Runtime（8 个）

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

说明：

- 先运行 `runtime_instance_evidence`，验证仓库根 Godot/缓存是否正常；
- 其余 7 个各自使用 workspace + `--import`；
- 每个测试独立退出；不要并行；
- 如果第一个 Godot 测试就失败，停止，不要继续消耗 300 秒。

### Batch D — 全 Feature Behavior（1 个）

```text
test_feature_behavior_evidence.py
```

- 使用现有 900 秒覆盖；
- 预计会运行全部 23 个 Feature / 60 个 Behavior，并包含 instance/runtime evidence 复核；
- 必须单独运行，不与 Batch B/F 重叠；
- 不因 target 的 158 秒而推断本测试耗时。

### Batch F — Composite / End-to-End（2 个）

```text
test_composite_behavior_evidence.py
test_slime_contact_arena.py
```

- 两者共享 `.ai/tmp/composite` 和固定 bad-contract 目录；
- 串行，先 composite 后 slime；
- 每个测试 300 秒外层预算，内部 workspace 有 120/180 秒导入预算；
- 结束后检查 workspace 所有权清理与 evidence 保留。

### Batch R — Target 可选复验（1 个，非重复计数）

```text
test_behavior_protocol_consistency.py
```

- 仅当最终 Level 3 需要一个连续批次记录时重跑；
- Phase 2 已有独立 PASS，不能把这次重跑当作新覆盖；
- 300 秒预算；若重跑失败，先判断是否环境/缓存问题，不能覆盖 Phase 2 结论。

---

## 8. Batch Rules

### 8.1 串行

- 所有批次串行；
- 没有证据支持同一批次内并行；
- 特别是：`test_composite` 的真实 `Scenes/` 写入、Composite workspace、共享 Godot user data、固定 `.ai/tmp` 目录，都不能并行。

### 8.2 临时目录与 Evidence

- Python-only 测试的 system temp 由测试自身清理；异常终止后保留，不自动删除。
- `.ai/tmp/behavior`、`.ai/tmp/runtime-instance`、`.ai/tmp/composite` 的证据目录保留用于审计。
- `.ai/tmp/composite_protocol_cases`、`composite_bad_contracts`、`composite_invalid_contracts`、`slime_bad_contracts` 不清理；只记录。
- 不把任何测试输出写到 `.ai/tmp/p168/official`、历史 p157/p166/p167/p168，或任何 Attestation 路径。
- 执行前后对官方 `evidence_index.json` 和 828 个历史文件做哈希核对；任何变化立即停止。

### 8.3 失败处理

1. 任何一个 FAIL，停止当前批次，不进入后续批次；
2. timeout / SKIP / 无 verdict 记为 INCOMPLETE，不记为 PASS；
3. 外部终止后保留现场，不清理 temp/workspace；
4. 一次失败只做一次独立原因确认；不要在相同环境反复重跑掩盖问题；
5. 环境类问题（Godot 缺失、`.godot` 缓存缺失、`--import` 失败）修复环境后只重跑受影响测试；
6. 代码/测试类问题不在 Phase 4 擅自修改；
7. 不延长 timeout 来换绿；R1 的三个测试不能靠跳过或删除断言处理。

### 8.4 `test_composite` 专属守卫

执行前后：

```text
Scenes/E2eCompositeTestPlayer.tscn
Scenes/E2eCompositeTestPlayer.tscn.uid
```

- 运行前记录是否存在；
- 运行后必须不存在（除非运行前已存在）；
- 若异常残留，保留并停止，不把它当成通过；
- 不修改 `Scenes/` 中的其他文件。

---

## 9. Coverage Statistics

### 9.1 31 个实际测试文件（含 target）

历史原始状态（不把 Phase 2 混入）：

```text
VERIFIED_PASS = 3
VERIFIED_FAIL = 0
NOT_EXECUTED = 26   # 含 target
UNKNOWN       = 2
total         = 31
```

把 Phase 2 的 target 从 NOT_EXECUTED 移入 PASS 后，当前唯一状态：

| 类别 | 数量 |
|---|---:|
| VERIFIED_PASS（历史 3 + Phase2 target 1） | **4** |
| VERIFIED_FAIL | **0** |
| NOT_EXECUTED（不含 target） | **25** |
| UNKNOWN | **2** |
| 合计 | **31** |

### 9.2 排除 target 后的 30 个剩余文件

| 类别 | 数量 |
|---|---:|
| 历史 VERIFIED_PASS | **3** |
| 尚未执行 | **25** |
| UNKNOWN | **2** |
| 已知 VERIFIED_FAIL | **0** |
| 合计 | **30** |

### 9.3 仍需获得明确 PASS 的唯一测试

```text
25 NOT_EXECUTED + 2 UNKNOWN = 27
```

已经拥有有效 PASS 的唯一测试：

```text
3 历史通过 + 1 Phase2 target = 4
```

总计：

```text
27 + 4 = 31
```

其中 3 个“历史通过”包含 2 个报告级证据；如果审查要求逐测原始日志，应将这 2 个降为 UNKNOWN，届时：

```text
明确 PASS = 2（artifact + target）
仍需确认 = 29
```

本报告不擅自改变历史记录，只把证据强度写清楚。

### 9.4 不得重复计算

- `test_artifact_evidence_validator.py` 同时出现在 scene batch 与 validator batch：只算一次；
- target 同时出现在任务清单和 Phase 2：Phase 2 单列，不在历史 3 个 PASS 中重复；
- `validator 22/22`、`runtime 5/5` 是批次数字，不能拆成未点名测试的 PASS。

---

## 10. Unknown Dependencies and Risks

| ID | 风险 | 影响 | 处理建议 |
|---|---|---|---|
| U1 | 8 个无模板/无能力声明的 Feature 目录 | 3 个全 Feature 测试预计失败；原因可能是测试范围过宽或数据迁移未完成 | 先由用户决定测试维护还是数据补齐；不在 Phase 3/4 擅自改 |
| U2 | `test_composite.py` 真实 `Scenes/` 临时写入 | 中断会留下仓库 dirty | 单独串行 + 前后路径检查；异常保留现场 |
| U3 | 固定 `.ai/tmp/composite*` / `slime_bad_contracts` | 复用目录可能含上次残留 | 只记录、不清理；同一测试不并行 |
| U4 | 共享 Godot `user://` | 行为测试可能相互影响 | 串行；不传自定义 tag 时尤其不能并行 |
| U5 | `.godot` 类缓存缺失 | `Health` 等类型解析失败，产生假失败 | 运行前确认缓存；隔离副本先 `--import` |
| U6 | stdout 块缓冲 | 运行中日志为空，误判死锁 | 诊断用 `python -u`/`PYTHONUNBUFFERED`；不改测试 |
| U7 | `test_feature_behavior_evidence.py` 900s、其他 300s | 不能用 target 158s 推断全套耗时 | 保持现有预算；超时先归因，不延长 |
| U8 | 历史只有批次汇总 | 无法证明 25 个剩余测试通过 | 逐测执行；不把批次数字写成 PASS |
| U9 | 实际 31 个；任务清单 30 个含 target、漏 artifact | 容易漏测或重复统计 | 矩阵 31 行含 target 基线；剩余 30 个必须包含 artifact；统计单列 |
| U10 | 测试依赖 `Features`/`Scenes`/`feature_index` 的历史 dirty 状态 | 当前数据与旧测试假设不一致 | 执行前快照；失败按真实结果记录，不修改历史数据 |
| U11 | `test_scene_intent_contract` 读契约与 `CONTRACT_INDEX` | 契约漂移会导致静态失败 | 执行前只读核对；不做契约修改 |
| U12 | `test_composite`/`test_plan_generator` 启动 Python CLI | CLI 回归可能引入额外子进程 | 串行；检查退出码与残留进程 |

---

## 11. Next Phase Recommendation

Phase 3 只完成审计，不执行任何剩余测试。

建议进入 Phase 4 前先做两个决定：

1. **R1 处理决定**：`test_scene_composer.py`、`test_feature_capability_pipeline.py`、`test_feature_capability_adoption.py` 对 31 个 Feature 目录的断言与当前 23 个模板/能力声明不一致。是先修测试范围，还是先补齐 8 个目录的数据？在决定前，直接跑这三项很可能得到真实 FAIL，不能算作产品回归。
2. **目标测试是否重跑**：Phase 2 已有 target PASS；如果 Phase 4 要形成单一连续批次，可在最后重跑一次，但不得重复计入覆盖。

如果用户接受“先执行会暴露 R1 失败”，则按 Batch A → C → B → D → F 串行执行（30 个剩余测试，含清单漏掉的 artifact）；一旦出现 FAIL 立即停止，保留现场，不自动修复、不自动清理、不自动重试。

Phase 3 结束。等待用户审查矩阵与 R1 决策后，才进入 Phase 4。
