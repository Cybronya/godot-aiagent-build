# Phase 1.39 审计报告 — Runtime Instance Evidence & Verification Gate

日期：2026-10-22（实现与回归执行）
分支：`master`　HEAD：`1c30f94`（本阶段未提交、未推送）

---

## 1. Git 初始状态与最终状态

### 1.1 初始状态（审计时）

- 分支 `master`，HEAD `1c30f94`。
- 工作区**在 Phase 1.39 开始前就已经是脏的**：Phase 1.36–1.38 的成果尚未提交，包括
  - 已跟踪修改：`.ai/context/CONTRACT_INDEX.yaml`、`.ai/context/scene_composer_schema.yaml`、
    `.ai/tools/validator/validate.py`、`.ai/tools/run_tests.py`、`Features/FEATURE_SCHEMA.md`、
    `Orchestration/level_config.gd`、若干 `Tests/*.gd` 等；
  - 未跟踪：`PHASE_1_36/1_37/1_38_AUDIT.md`、`scene_composer/instance_evidence.py`、
    `validator/check_instance_evidence.py`、`.ai/tools/evaluation/`、
    `test_feature_instance_evidence.py`、`test_instance_evidence_reconciliation.py` 等。
- 本阶段**没有**执行 `git reset` / `git clean` / 批量恢复 / 覆盖未知文件；上述改动全部保留。

### 1.2 最终状态

- HEAD 仍为 `1c30f94`，`master`，**未 commit、未 push**。
- 与初始状态相比只有本阶段新增/修改（见 §4）。
- 关键保护事实：`git status` 中没有任何 `Features/**/*.tscn` 被修改，也没有黄金基线
  （`.ai/tools/validator/tests/` 下的 trace / e2e 基线文件）被重新生成或改写。

---

## 2. Phase 1.38 证据链审计结论

Phase 1.38 的 `instance_evidence.py` + `validator/check_instance_evidence.py` 完成的是
**声明 ↔ 静态 `.tscn` 文本**的对账：

- 6 个 Feature（collect_pickup / heal_pickup / moving_platform / openable_door /
  player_movement / trigger_switch）声明 `instance.node_type / children`；
- 53 项断言（13 项 reconciliation + 40 项 feature instance evidence）覆盖菱形引用、
  挂载模式、解析受限、额外节点、声明校验；
- 它能回答「`.tscn` 里写了什么」，**不能**回答「Godot 加载后对象树里有什么」；
  对 `runtime_children` 只能给出 `INSUFFICIENT`（静态证据不足），不能证明运行时存在。

因此 Phase 1.39 复用同一套 `PASS / MISMATCH / INSUFFICIENT / INVALID / NOT_DECLARED`
状态语义与同一份 `template.yaml` 声明，只补运行时一层，不另建对账体系。

---

## 3. 运行时验证架构与关键设计决策

### 3.1 四层证据，互不顶替

| 层级 | 问题 | 本阶段证据来源 | 失败表达 |
| --- | --- | --- | --- |
| 1 文件解析 | `.tscn` 文本是否可解析 | 静态 `instance_evidence` 解析器 | `INSTANCE_SCENE_UNPARSEABLE` 等静态 code |
| 2 资源加载 | `PackedScene` 能否被 Godot 加载 | 真实 Godot 进程 + stderr | `MISMATCH / load_error` |
| 3 节点存在 | 加载后的对象树是否有目标节点、类型、数量 | 探针读取真实节点树 | `missing` / `type_mismatch` / `count_mismatch` / `missing_after_timeout` |
| 4 行为正确 | 节点运行行为是否符合预期 | **不在本阶段**（e2e / behavior probe） | — |

第 2 层必须读 stderr：Godot 在场景部分损坏时会「加载成功并继续跑」，
只看探针自述会把加载失败误当 PASS。判定器因此有独立降级规则：
`PASS` + stderr 命中 `Failed loading resource:` / `referenced non-existent resource` /
`Attempt to open script` 等真实引擎报错 → 降级 `MISMATCH / load_error`；
`PASS` + `SCRIPT ERROR:` → 降级 `MISMATCH / script_error`。

### 3.2 契约（向后兼容的最小扩展）

`Features/<id>/template.yaml`：

```yaml
instance:
  node_type: Area2D
  children: [CollisionShape2D]
  runtime_children: [CollisionShape2D]   # 1.38 语义；1.39 起不再单独充当存在性证明
  runtime:                               # 新增；缺省 = NOT_DECLARED
    when: after_load                     # after_load | after_frames:<0..600> | after_action:<name>
    timeout_frames: 0                    # 0..600；0 = 不轮询
    scene: res://...                     # 可选，默认模板入口场景
    expectations:                        # 可选，缺省由 node_type/children 推导
      - {path: "PickupShape", type: CollisionShape2D, count: 1}
```

- 未写 `runtime:` → `NOT_DECLARED`，不凭空要求运行时证据（1.38 及更早 Feature 合法）。
- `expectations` 缺省时，根 + 直接子节点（按重复次数计数量）由 `node_type / children`
  推导，与静态对账同口径；`runtime_children` 只给推导出的条目打 `runtime: true` 标记
  （来源标识保留，便于审计）。
- 契约校验（`build_contract`）拒绝：未知 `when`、`timeout_frames` 非整数/超范围/布尔、
  `scene` 非 `res://`、`expectations` 空或非列表、未知节点类型、`count` 不在 1..64、
  `path` 与 `parent` 同时给出、缺 `node_type`。任一命中 → `INVALID / contract_invalid`，
  **不启动 Godot、不猜测**。

### 3.3 探针与判定分离

- 探针 `.ai/tools/scene_composer/probes/instance_runtime_probe.gd`（`extends SceneTree`，
  `godot --headless --path <root> -s res://... -- --contract=... --result=...`）只负责
  「加载 + 观察 + 写原始观测」，不做最终状态判定；
- `runtime_instance_evidence.py` 负责契约构建、进程编排、证据落盘与判定；
- 探针把每个目标的 `status / expected_count / found_count / found_paths / actual_types /
  first_seen_frame` 写进 `result.json`，并在 stdout 追加 `EVIDENCE_RESULT: {...}` 作为
  result 文件缺失时的**同一份**机器可读回退（解析失败但仍不算 PASS，仅用于区分原因）。

### 3.4 证据落盘（可追踪运行标识）

```
.ai/tmp/runtime-instance/<run_id>/
  contract.json   # 本次核验的契约（含 when/timeout/expectations）
  result.json     # 探针原始观测
  stdout.log
  stderr.log
```

`run_id = <pid>-<uuid8>`，同时出现在报告、合同与目录名中。目录在 `.gitignore`
（`.ai/tmp/`）内，不进入版本库。

---

## 4. 修改、新增文件清单

### 新增

| 文件 | 作用 |
| --- | --- |
| `.ai/tools/scene_composer/probes/instance_runtime_probe.gd` | headless 运行时探针（加载、观察、等待、写原始结果） |
| `.ai/tools/scene_composer/runtime_instance_evidence.py` | 契约构建 / Godot 启动 / 证据落盘 / 判定 / CLI |
| `.ai/tools/scene_composer/tests/test_runtime_instance_evidence.py` | 14 个用例、67 项断言（含真实负向对照） |
| `.ai/context/PHASE_1_39_AUDIT.md` | 本报告 |

### 修改

| 文件 | 改动 |
| --- | --- |
| `Features/{collect_pickup,heal_pickup,moving_platform,openable_door,player_movement,trigger_switch}/template.yaml` | 各 +18 行：`instance.runtime` 声明（`after_load`、`timeout_frames: 0`）与说明 |
| `.ai/tools/validator/validate.py` | 新增 `report_instance_runtime` 与 `--instance-runtime` / `--require-runtime` |
| `.ai/tools/validator/README.md` | 运行时门禁入口、成本、状态/退出码表 |
| `Features/FEATURE_SCHEMA.md` | §7 增补运行时证据契约、状态与退出码 |
| `.ai/context/scene_composer_schema.yaml` | `runtime_instance_evidence` 契约段（探针、时机、状态、原因、门禁） |
| `.ai/context/CONTRACT_INDEX.yaml` | 索引条目、输入/输出、状态、validator flag、测试入口 |
| `.ai/tools/run_tests.py` | 段计数与全量计数说明（Python 50 / 全量 88），运行时测试纳入 `scene_composer` 段 |

上述 tracked 文件的 diff 中同时含有 Phase 1.36–1.38 的既有未提交内容，本阶段只做增量，
未回退或改写前序工作。

---

## 5. 证据状态与退出码映射

### 5.1 状态语义

| 状态 | 含义 | 何时产生 |
| --- | --- | --- |
| `PASS` | 观察时机/窗口内，真实对象树满足契约 | 探针加载成功且全部目标满足，stderr 无加载/脚本错误 |
| `MISMATCH` | 实际对象与契约明确冲突 | `load_error` / `script_error` / `missing` / `type_mismatch` / `count_mismatch` / `missing_after_timeout` |
| `INSUFFICIENT` | 不能下结论 | `probe_timeout`、`evidence_unavailable`、`action_not_triggerable`、Godot 缺失 |
| `INVALID` | 契约本身无效 | `contract_invalid`（见 §3.2） |
| `NOT_DECLARED` | 未声明 `runtime:` | `runtime_not_declared` |

未新增顶层 `LOAD_ERROR` / `TIMEOUT`：它们语义上分别属于 `MISMATCH`（明确冲突）与
`INSUFFICIENT`（无法下结论），作为 `reason` + `detail` 表达即可，避免两套消费者对同一
事实给出矛盾解释。

### 5.2 退出码

| 入口 | 0 | 1 | 2 |
| --- | --- | --- | --- |
| `runtime_instance_evidence.py` | `PASS` / `NOT_DECLARED`；无 `--require-runtime` 时的 `INSUFFICIENT` | `MISMATCH` / `INVALID`；`--require-runtime` 下的 `INSUFFICIENT` | 输入错误（未知 feature / 无 Godot 且显式要求等） |
| `validate.py --instance-runtime ...` | 无 failure（`INSUFFICIENT` 仅 warning） | 任一 `MISMATCH` / `INVALID`；`--require-runtime` 下任一 `INSUFFICIENT` | — |

`INSUFFICIENT` 在任何路径下都**不会**被计为 PASS。

---

## 6. 静态 / 加载 / 存在性证据的区别

- **静态解析通过**（1.38）：只证明 `.tscn` 文本结构与声明一致；不证明 Godot 能加载。
- **加载通过**（1.39 第 2 层）：证明 `PackedScene` 与依赖资源/脚本可被引擎实例化；
  仍不证明目标节点存在（脚本可在 `_ready` 里删除/替换节点）。
- **节点存在**（1.39 第 3 层）：探针读取加载后的真实节点树，逐目标核对路径、实际类型、
  数量；这才是 `instance.runtime` 的 `PASS` 依据。
- **行为正确**：不在本阶段；`PASS` 只声称「此刻存在且结构符合契约」。

回归报告据此分列 Python 测试、静态 Validator、Godot 场景实际加载、运行时实例检查四项
（§8），不用其中一项替代其余。

---

## 7. 动态实例验证时机与超时策略

### 7.1 `runtime_children` 的重新界定

- 语义：解释「为什么静态 `.tscn` 证据看不到该子节点」，**不是**存在性证明；
- 必须同时出现在 `children` 中（⊆ 约束沿用 1.38），并在 `runtime:` 下给出观察时机；
- 静态能看到的类型若仍列在 `runtime_children`，静态对账会提示声明过期（既有 warning）。

### 7.2 时机

| `when` | 行为 |
| --- | --- |
| `after_load` | 场景加入树后稳定 2 帧（`_ready` 已执行）再判定 |
| `after_frames:<N>` | 稳定后再等 N 帧（0..600） |
| `after_action:<name>` | **不执行任何游戏动作**，直接 `INSUFFICIENT / action_not_triggerable`，且不启动 Godot |

### 7.3 轮询与超时

- `timeout_frames: 0` → 到达观察时机后单次判定，不空转；
- `timeout_frames: N > 0` → 逐帧重查，**全部满足立即结束**；`waited_frames` 记录实际等待帧数；
- 窗口耗尽 → `MISMATCH / missing_after_timeout`，`detail` 只声称「在约定观察窗口内未出现」，
  不声称「永远不会出现」；
- 进程级超时（默认 90s）与窗口超时分离：进程超时 → `INSUFFICIENT / probe_timeout`，
  不是 `MISMATCH`（可能是首帧导入/大场景慢，不能据此断言缺失）；
- 每个检查条目带 `first_seen_frame`，动态节点「何时出现」可审计。

---

## 8. 测试矩阵与真实负向对照

### 8.1 新增测试（`test_runtime_instance_evidence.py`，14 个用例 / 67 项断言，全部 PASS）

| 用例 | 场景 | 断言重点 |
| --- | --- | --- |
| 1 | 仓库 6 个 Feature 真实加载 | 全部 `PASS`，`observed_frame` 为整数（证据来自真实加载） |
| 2 | 缺失脚本资源 | `MISMATCH / load_error`，detail 引用真实引擎报错 |
| 3 | 节点缺失 | `MISMATCH / missing`，检查项给出期望类型/数量 |
| 4 | 实际类型不符 | `MISMATCH / type_mismatch`，报出 `actual_types` |
| 5 | 数量不符 | `MISMATCH / count_mismatch`，expected 2 / found 1 |
| 6 | 动态节点第 5 帧生成 | `PASS`，`waited_frames > 0`（未提前判缺失），`first_seen_frame > 0` |
| 7 | 动态节点窗口内未生成 | `MISMATCH / missing_after_timeout`，`waited_frames == 12`，失败项 `runtime: true` |
| 8 | `after_action` | `INSUFFICIENT / action_not_triggerable`，未启动 Godot |
| 9 | 4 类非法契约 | 均 `INVALID / contract_invalid`，均未执行 |
| 10 | 采集失败 / 无 Godot | `INSUFFICIENT / evidence_unavailable`，绝不 PASS |
| 11 | 未声明 runtime | `NOT_DECLARED`，不启动 Godot |
| 12 | CLI | MISMATCH=1；INSUFFICIENT 默认 0 / `--require-runtime` 1；窗口超时=1；JSON 含 status/reason/run_id/checks |
| 13 | Phase 1.38 静态对账回归 | 6 个 Feature 仍全部 `PASS` |
| 14 | 真实黄金 Feature 副本负向对照 | 见 §8.2 |

测试夹具全部位于 `.ai/tmp/` 下的临时 Godot 项目（含 `project.godot` 与探针副本），
结束即删除；不写仓库 `Features/`。

### 8.2 真实负向对照（Case 14，基于最终代码）

对 `Features/openable_door`（真实黄金 Feature）做隔离副本，操作前记录 `sha256`：

1. **加载失败**：把副本场景的脚本引用改为不存在的 `MissingRuntimeControl.gd`
   → `MISMATCH / load_error`，CLI 退出码 1；恢复后哈希与基线一致。
2. **移除被要求实例**：删除副本的 `Collision` 节点及其 `shape` 行
   → `MISMATCH / missing`，检查项明确 `CollisionShape2D / MISSING`；恢复后哈希一致。
3. **动态创建条件失败**：删除静态 `Collision`，挂一个 `_ready` 不做任何事的脚本，
   声明 `runtime_children: [CollisionShape2D]` + `timeout_frames: 10`
   → `MISMATCH / missing_after_timeout`，`waited_frames == 10`，CLI 退出码 1。

对照结束时断言副本逐字节恢复，且仓库 `OpenableDoor.tscn` / `openable_door.gd` 的
`sha256` 与操作前完全一致（黄金基线未被触碰）。对照 3 中曾出现「声明只写
`runtime_children` 而未写 `children`」导致推导不到该目标、错误返回 PASS 的情况；
已按契约（`runtime_children ⊆ children`）修正夹具，并在报告中保留该事实——它说明
契约推导必须由测试覆盖，而不是靠日志阅读。

### 8.3 完整回归结果（最终代码上重跑）

| 检查 | 命令 | 结果 |
| --- | --- | --- |
| 新增运行时测试 | `python .ai/tools/scene_composer/tests/test_runtime_instance_evidence.py` | 67/67 PASS，exit 0 |
| Phase 1.38 静态对账 | `test_instance_evidence_reconciliation.py` + `test_feature_instance_evidence.py` | 13 + 40 = 53 项全部 PASS |
| Scene Composer 段 | `python .ai/tools/run_tests.py scene_composer` | 20/20 PASS |
| Validator 段 | `python .ai/tools/run_tests.py validator` | 10/10 PASS |
| Godot headless 全量 | `python .ai/tools/run_tests.py --godot-only` | 38/38 PASS |
| 全量 | `python .ai/tools/run_tests.py` | 88/88 PASS（exit 0） |
| 静态 Validator | `python .ai/tools/validator/validate.py` | 0 error / 17 warning，exit 0 |
| 运行时门禁 | `validate.py --instance-runtime all --require-runtime` | 6 checked，pass=6 / mismatch=0 / insufficient=0，exit 0 |

17 条 warning 全部是既有的「资产清单指向缺失图片」（`assets/...png` 不在当前检出中），
与 Phase 1.39 无关，本阶段未修改资产基线。

---

## 9. 未解决问题、限制与风险

1. **不验证行为**：`PASS` 只代表「加载后存在且类型/数量符合契约」，不代表交互逻辑正确；
   行为证据仍归 e2e / behavior probe。
2. **生产 Feature 未使用动态路径**：仓库 6 个声明都是 `after_load` + `timeout_frames: 0`
   的静态结构；动态生成/轮询能力目前只在测试夹具与负向对照中被真实验证，
   尚无真实 Feature 依赖它。
3. **动作门控永远 INSUFFICIENT**：`after_action:*` 不触发输入，因此需要按键/交互才生成的
   节点无法在本阶段获得 PASS；若将来把它用于最终验收，必须先引入受控动作夹具
   （明确动作、可回放、不改游戏状态），否则该 Feature 只能停留在 INSUFFICIENT。
4. **进程超时固定 90s**：不随 `timeout_frames` 缩放；首次导入或大场景可能
   `probe_timeout → INSUFFICIENT`（不会误报 PASS，但会拖慢或需调大超时）。
5. **证据目录只增不删**：`.ai/tmp/runtime-instance/` 当前约 2.7MB，无自动清理策略；
   目录已被 gitignore，不影响仓库。
6. **环境耦合**：Godot 可执行文件按「项目根父目录」候选名查找，回退 `PATH`；
   仅在 Windows + Godot 4.7 stable headless 实测，未验证 Linux/macOS 与其它 4.x 版本。
7. **真实加载会刷新 `.godot` 导入缓存**：属于引擎正常行为，本阶段未改并发/清理机制。
8. **静态 Validator 默认不跑运行时**：若验收者忘记加 `--instance-runtime`，运行时缺失不会被
   发现；这是刻意的成本取舍（见 §10），最终验收流程必须显式使用该入口。

---

## 10. `INSUFFICIENT`、`runtime_children` 与最终门禁策略

- **`INSUFFICIENT` 永远不是成功**：CLI 默认退出 0 只是「未要求证据」的兼容行为；
  最终验收必须加 `--require-runtime`，此时任何 INSUFFICIENT 都是 failure（退出 1）。
- **`runtime_children` 不产生 PASS**：它只解释静态不可见；存在性必须由 `runtime:` 的
  观察时机 + 探针证据证明。窗口内未出现 → `MISMATCH`；动作门控 → `INSUFFICIENT`。
- **门禁边界**：静态 Validator（第 7 阶段 `check_instance_evidence`）保持零 Godot 启动、
  零额外成本；运行时证据由 `--instance-runtime <feature|all>` 显式开启，
  `--require-runtime` 收紧 INSUFFICIENT。静态失败与运行时失败的策略在 README 与
  `scene_composer_schema.yaml` 中分别列明，二者共用同一状态词汇，不产生矛盾解释。
- **未纳入 `run_tests.py` 全量默认路径之外的额外门禁**：运行时测试随
  `scene_composer` 段执行（会真实启动 Godot），但不改变 `validate.py` 的默认行为。

---

## 11. 黄金基线与用户既有修改的保护

- 未运行任何 `git reset` / `git clean` / 检出覆盖；Phase 1.36–1.38 的未提交修改与未跟踪文件
  全部保留（`git status` 可核对）。
- 没有修改、删除或重新生成任何 `.tscn`、trace 基线、e2e 基线。
- 测试对仓库 Feature 只做**只读加载**；所有破坏性对照都在 `.ai/tmp/` 的隔离副本上进行，
  并以 `sha256` 断言副本恢复、仓库文件未变。
- 唯一的声明性修改是 6 个 `template.yaml` 增加 `instance.runtime`（不改生成结果，
  Builder 不消费该字段）。

---

## 12. 结论

Phase 1.39 建立了最小、可重复、可负向验证的运行时实例证据闭环：

- 运行时 `PASS` 来自 Godot 真实加载后的对象树（探针读取），不由 YAML、生成器预期或静态解析伪造；
- 加载失败、节点缺失、类型/数量不符、窗口内未生成、采集失败均有独立且经断言的失败路径，
  退出码与机器可读结果一致；
- 三项真实负向对照在最终代码上稳定失败，且黄金基线哈希不变；
- 全量回归 88/88、Godot 38/38、静态 Validator 0 error、运行时门禁 6/6 PASS。

限制（行为未验证、动作门控 INSUFFICIENT、动态路径尚无生产用例、仅 Windows/4.7 实测、
证据目录无清理）已在 §9 如实记录，未以任何一项回归结果替代其余证据层级。
