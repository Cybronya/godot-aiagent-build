# Phase 1.40 审计报告 — Controlled Action Replay & Behavioral Evidence

日期：2026-10-22
分支：`master`　HEAD：`1c30f94`（本阶段未提交、未推送）

---

## 1. Git 初始状态与最终状态

### 1.1 初始状态

- 分支 `master`，HEAD `1c30f94`。
- 工作区在 Phase 1.40 开始前已是脏的：Phase 1.36–1.39 的成果全部未提交，
  包括 `.ai/tools/scene_composer/{instance_evidence,runtime_instance_evidence}.py`、
  两个探针、对应的三套测试、`validator/validate.py` 的运行时入口、
  `Features/*/template.yaml` 的 `instance.runtime` 等。
- `Tests/test_holdout_trace.gd`、`Tests/test_orchestration_trace.gd` 等前序阶段的修改也在工作区。

### 1.2 最终状态

- HEAD 仍为 `1c30f94`，未 commit、未 push、未执行任何回滚/清理命令。
- 与初始状态相比只有本阶段新增/修改（见 §4）。
- 没有任何 `Features/**/*.tscn`、trace 基线或 e2e 基线被修改或重新生成
  （`git status` 可核对；`Tests/*.gd` 的两处改动属于前序阶段，本阶段未触碰）。

---

## 2. 运行时证据体系复用情况

本阶段**不新建**并行证据体系，而是沿用 1.38/1.39 的词汇与基础设施：

| 复用项 | 来源 | 用法 |
| --- | --- | --- |
| 状态词汇 `PASS/MISMATCH/INSUFFICIENT/INVALID/NOT_DECLARED` | `instance_evidence.py` | 行为层直接别名，不新增顶层状态 |
| Godot 二进制发现 | `runtime_instance_evidence.find_godot` | 同一候选名 / PATH 回退 |
| 探针形态 | `instance_runtime_probe.gd` | `extends SceneTree` + `-s` + `--contract/--result` JSON |
| 证据落盘 | 1.39 的 `.ai/tmp/runtime-instance/<run_id>/` 约定 | 行为证据用 `.ai/tmp/behavior/<run_id>/`，同构四件套 |
| 判定器职责分离 | 1.39 `run_probe`（采集） / `judge`（判定） | 行为层同构：探针只观测，Python 判定 |
| 加载错误识别 | `LOAD_ERROR_MARKERS` / `SCRIPT_ERROR_MARKERS` | 行为层继续读 stderr，不只信探针自述 |

1.39 探针与 `instance.runtime` 契约**未改动**；1.38 静态对账**未改动**。
行为证据是**独立一层**，不并入结构 `PASS`。

---

## 3. 行为证据结构与状态语义

### 3.1 契约（`Features/<id>/template.yaml` 顶层 `behavior:`）

```yaml
behavior:
  - id: open
    actions:
      - {type: door.set_open, target: ".", params: {value: true}}
    preconditions:
      - {check: door.is_open, target: ".", equals: false}
    expected:
      - {check: door.is_open, target: ".", equals: true}
      - {check: signal, entry: door.state_changed, target: ".", count: 1, last_args: [true]}
    window_frames: 12
```

放在顶层而非 `instance:` 下，避免改变 1.38 的「声明 = 结构」语义与既有 declared 集合。

### 3.2 注册表（唯一允许的动作 / 观测）

| 动作 | 参数 | 真实入口 |
| --- | --- | --- |
| `door.set_open` | `value: bool` | `OpenableDoor.set_open(bool)` |
| `health.take_damage` | `amount: 1..100` | `Health.take_damage(int)` |
| `health.heal` | `amount: 1..100` | `Health.heal(int)` |
| `physics.overlap` | `group`，可选 `health_max`/`damage` | 生成真实 `CharacterBody2D`（可带真实 `Health` 实例），由物理帧触发 `Area2D.body_entered` |

| 观测 | 含义 |
| --- | --- |
| `door.is_open` / `health.current` / `health.is_dead` / `pickup.is_collected` | 调用真实查询方法 |
| `node.freed` | 目标节点已释放或 `queued_for_deletion` |
| `signal` | 注册信号（`door.state_changed` / `pickup.collected` / `health.health_changed` / `health.died`）的计数与可选 `last_args` |

探针与 Python 各有一份注册表（`ACTIONS/CHECKS/SIGNALS` 与 `ACTION_SPECS/STATE_CHECKS/SIGNAL_ENTRIES`）；
任一侧未注册即拒绝。**不接受任意方法名、表达式或 GDScript 注入**。

### 3.3 证据字段

每份报告包含：`feature / behavior / scene_id / run_id`、`actions`（含每个动作的 `executed`）、
`preconditions`（实际观测）、`observation_window {frames, unit: physics_frames}`、
`expected`、`actual`（逐条 `check/expected/observed/status/first_observed_frame`）、
`action_executed`、`first_observed_frame`、`replay_count`、`replay_consistent`、
`runs[]`（每次重放的 run_id / status / waited_frames / 证据路径）。

### 3.4 状态语义（限定在行为层）

| 状态 | 含义 |
| --- | --- |
| `PASS` | 动作**确实执行**，窗口内全部后置断言成立，且重放一致 |
| `MISMATCH` | 动作已执行，但状态/信号与契约冲突（含节点未被释放） |
| `INSUFFICIENT` | 动作入口不可用 / 前置不满足 / 观测不可用 / 采集失败 / 重放不一致 / Godot 缺失 |
| `INVALID` | 契约非法（未知动作、参数、检查、信号、目标、重复 id、窗口越界） |
| `NOT_DECLARED` | 未声明 `behavior:` |

`PASS` 的硬性条件在 `judge()` 中强制：`action_executed == true` 且 `checks` 非空；
否则即使观测值凑巧符合，也降级为 `INSUFFICIENT`（reason `action_unavailable` /
`evidence_unavailable`）。

---

## 4. 修改、新增文件清单

### 新增

| 文件 | 作用 |
| --- | --- |
| `.ai/tools/scene_composer/probes/feature_behavior_probe.gd` | 受限动作执行 + 逐帧观测 + 原始结果落盘 |
| `.ai/tools/scene_composer/feature_behavior_evidence.py` | 契约校验 / 隔离项目 / 探针编排 / 判定 / 重放 / CLI |
| `.ai/tools/scene_composer/tests/test_feature_behavior_evidence.py` | 12 组用例、102 项断言 |
| `.ai/context/PHASE_1_40_AUDIT.md` | 本报告 |

### 修改

| 文件 | 改动 |
| --- | --- |
| `Features/openable_door/template.yaml` | `behavior: open`（+31 行） |
| `Features/health/template.yaml` | `behavior: damage / heal_clamped / death`（+34 行） |
| `Features/heal_pickup/template.yaml` | `behavior: heal_damaged_target`（+31 行） |
| `Features/collect_pickup/template.yaml` | `behavior: collect_on_contact`（+31 行） |
| `Features/FEATURE_SCHEMA.md` | 新增 §7.4 行为证据契约与门禁 |
| `.ai/context/scene_composer_schema.yaml` | 新增 `feature_behavior_evidence` 段 |
| `.ai/context/CONTRACT_INDEX.yaml` | 索引条目 + 独立 CLI 入口 |
| `.ai/tools/validator/README.md` | 明确行为证据不在 Validator 内 |
| `.ai/tools/run_tests.py` | 段计数（scene_composer 21 / Python 51 / 全量 89） |

---

## 5. 首批 Feature、真实动作入口与后置断言

| Feature | behavior | 动作（真实入口） | 前置 | 后置 |
| --- | --- | --- | --- | --- |
| `openable_door` | `open` | `OpenableDoor.set_open(true)` | `is_open() == false` | `is_open() == true`；`state_changed` ×1，参数 `[true]` |
| `health` | `damage` | `Health.take_damage(4)` | 当前 5、未死亡 | 当前 1；`health_changed` ×1，参数 `[1, 4]` |
| `health` | `heal_clamped` | `take_damage(4)` → `heal(99)` | 当前 5 | 当前 5（上限钳制）；`health_changed` ×2 |
| `health` | `death` | `take_damage(5)` | 未死亡 | 当前 0、`is_dead()`；`died` ×1 |
| `heal_pickup` | `heal_damaged_target` | 物理接触：真实 `CharacterBody2D` + 真实 `Health`（max 5，先 `take_damage(3)`）进入 `HealPickup` 区域 | 无 | 目标生命 4（3 伤 + 2 恢复）；拾取物已释放 |
| `collect_pickup` | `collect_on_contact` | 物理接触：组内 `CharacterBody2D` 进入 `CollectPickup` 区域 | `is_collected() == false` | 拾取物已释放；`collected` ×1 |

动作来源全部是 Feature 自身脚本的公开入口/真实物理信号，**没有**直接写 `_is_open`、
`_current_health`、`_collected` 或调用 `_on_body_entered` 私有回调。

未接入行为证据的 `moving_platform` / `player_movement` / `trigger_switch` 保持
`NOT_DECLARED`；它们需要时间/输入驱动的前置条件，本阶段不强行覆盖。

---

## 6. 重放一致性结果

最终代码上 `feature_behavior_evidence.py --all --json`（默认 `--replay 2`）：

| Feature / behavior | 结果 | 重放 | 一致 | 等待帧 |
| --- | --- | --- | --- | --- |
| collect_pickup / collect_on_contact | PASS | 2 | ✅ | 1 / 1 |
| heal_pickup / heal_damaged_target | PASS | 2 | ✅ | 1 / 1 |
| health / damage | PASS | 2 | ✅ | 0 / 0 |
| health / heal_clamped | PASS | 2 | ✅ | 0 / 0 |
| health / death | PASS | 2 | ✅ | 0 / 0 |
| openable_door / open | PASS | 2 | ✅ | 0 / 0 |

- 比较的是 `status / reason / action_executed / 每条 check 的 expected+observed+status`；
  忽略 `run_id`、帧号与耗时（避免调度抖动造成假不一致）。
- 任一重放不一致 → `INSUFFICIENT / replay_inconsistent`，永不 PASS
  （由 Case 9 用交替结果的 stub 验证）。

---

## 7. 负向对照与恢复校验

### 7.1 真实黄金 Feature 副本（Case 11）

以 `Features/openable_door` 的隔离副本为基线，操作前后记录 `sha256`：

| 对照 | 破坏方式 | 期望 / 实际 | 恢复 |
| --- | --- | --- | --- |
| baseline | 无 | `PASS` | — |
| 1 | `set_open` 改为 no-op | `MISMATCH / state_mismatch`；等满 5 帧窗口 | 逐字节恢复，哈希一致 |
| 2 | `_apply(value)` 改为 `_apply(false)` | `MISMATCH`；`observed == false` | 逐字节恢复，哈希一致 |
| 3 | `set_open` 重命名（入口消失） | `INSUFFICIENT / action_unavailable` | 逐字节恢复，哈希一致 |

结束断言：副本场景 + 脚本哈希与基线一致；仓库 `OpenableDoor.tscn` / `openable_door.gd`
哈希与操作前一致；场景文件从未被重写。

### 7.2 其他负向 / 边界用例

- **动作没执行但状态凑巧符合**（Case 2）：场景 `start_open = true`、入口被移除、断言
  `is_open == true` → `INSUFFICIENT / action_unavailable`，`action_executed == false`，
  不因观测值匹配而 PASS。
- **前置条件不满足**（Case 5）：断言门已开但实际关闭 → `INSUFFICIENT /
  precondition_unmet`，动作未执行，前置观测被记录。
- **非法契约**（Case 6）：未知动作、错误参数类型、多余参数、未知检查、缺 `equals`、
  非法目标（`../outside`）、窗口为 0、`physics.overlap` 缺 `group`、重复 behavior id
  → 全部 `INVALID / contract_invalid`，且不启动 Godot。
- **采集失败**（Case 8）：runner 返回无结果 → `INSUFFICIENT / evidence_unavailable`；
  Godot 发现被临时置空 → `INSUFFICIENT`，都不可能是 PASS。
- **重放不一致**（Case 9）：交替返回 PASS / MISMATCH → `INSUFFICIENT /
  replay_inconsistent`，两次结果均保留。
- **观察窗口**（Case 3）：动作执行但状态不变 → `MISMATCH`，`waited_frames == window_frames`；
  窗口耗尽从不 PASS。

---

## 8. 完整回归测试矩阵（最终代码）

| 检查 | 命令 | 结果 |
| --- | --- | --- |
| 新增行为测试 | `test_feature_behavior_evidence.py` | 102/102 PASS，exit 0 |
| 行为 CLI 全量 | `feature_behavior_evidence.py --all` | 6/6 PASS，重放一致，exit 0 |
| Phase 1.38 静态实例证据 | `test_instance_evidence_reconciliation.py` + `test_feature_instance_evidence.py` | 53 项 PASS |
| Phase 1.39 运行时实例证据 | `test_runtime_instance_evidence.py` | 67/67 PASS |
| Scene Composer 段 | `run_tests.py scene_composer` | 21/21 PASS |
| Validator 段 | `run_tests.py validator`（含于全量） | 10/10 PASS |
| Godot headless | `run_tests.py --godot-only` | 38/38 PASS |
| 全量 | `run_tests.py` | 89/89 PASS，exit 0 |
| 静态 Validator | `validate.py` | 0 error / 17 warning（既有资产清单缺失），exit 0 |

17 条 warning 仍是 `assets/**.png` 缺失（当前检出未包含这些图片），与 1.40 无关。

---

## 9. 证据目录与资源所有权

```
.ai/tmp/behavior/
  workspace-<pid>-<rand>/project/     # 每次 CLI 调用一份：Features 副本 + 探针 + project.godot
  <run_id>/contract.json              # 每个 behavior 的每次重放各一份
  <run_id>/result.json
  <run_id>/stdout.log
  <run_id>/stderr.log
```

- `run_id = <pid>-<uuid8>-<behavior>-r<replay>`，报告、契约与目录名三方一致。
- 工作区在 `BehaviorWorkspace.__init__` 中创建，`finally` 中只删除**本次调用创建**的目录；
  不按名称匹配删除，不触碰 `.ai/tmp` 下其他运行的产物。
- 探针只写 `--result` 指定的 JSON；Godot 在副本内写自己的 `.godot` 导入缓存，随副本一起删除。
- 证据目录只增不删（当前约数 MB），已由 `.gitignore`（`.ai/tmp/`）排除。

---

## 10. 未解决问题、限制与后续建议

1. **覆盖面**：4/17 个 Feature、6 个 behavior。`moving_platform`、`trigger_switch`、
   `player_movement` 需要持续帧推进/输入驱动，尚未接入；`contact_damage` 需要宿主实体，
   属于下一批候选。
2. **注册表双份维护**：探针与 Python 各有一份动作/观测注册表，新增能力必须同时改两处；
   当前由测试的「未注册即拒绝」与 CLI 的全量 PASS 共同约束，但没有自动一致性校验。
   后续可用同一份 JSON/Python 生成 GDScript 常量，或在测试中断言两侧键集合相等。
3. **物理接触是近似但真实的**：`physics.overlap` 在目标位置生成 32×32 的
   `CharacterBody2D`，依赖默认碰撞层/掩码与真实物理帧；它不模拟移动轨迹、速度或多帧接触，
   因此不能替代完整的场景级玩法测试。
4. **重放只比较关键结果**：帧号、等待帧与耗时被排除，故「时序抖动 / 偶发慢一帧」不会被发现；
   若将来需要时序契约，应新增独立的时序断言，而不是收紧现有比较。
5. **不可逆动作**：本阶段没有通用逆操作；回滚靠销毁隔离副本。对会写全局状态（存档、
   单例、文件）的动作，必须先有隔离机制再注册。
6. **行为门禁不在 Validator 内**：`validate.py` 行为不变，最终验收需显式运行
   `feature_behavior_evidence.py --all --require-behavior`；忘记运行不会被静态门禁发现。
7. **环境**：仅在 Windows + Godot 4.7 stable headless 实测；`--import` 预构建
   脚本类缓存是必要步骤（`heal_pickup` 依赖 `class_name Health`）。
8. **信号观测范围**：只注册了 4 个信号；未覆盖 `state_changed` 的重复发射、参数边界等更细行为。

建议下一阶段：把注册表生成/一致性校验做成单一事实源；为需要帧推进的 Feature
（`moving_platform`、`trigger_switch`）增加「等待 N 帧」的显式受控步骤；
并考虑把行为证据接入统一的验收脚本，同时保持静态 Validator 零 Godot 启动。

---

## 11. 结论

Phase 1.40 建立了最小、可重复、可负向验证的行为证据闭环：

- 动作通过 Feature 自身公开入口或真实物理接触触发，后置状态由探针逐帧独立观测；
- `PASS` 需要 `action_executed`、窗口内全部断言成立、两次重放一致，三者缺一不可；
- 真实 Feature 副本上的三项负向对照稳定失败，副本与仓库文件均按 `sha256` 验证未被改写；
- 全量回归 89/89、Godot 38/38、1.38 的 53 项与 1.39 的 67 项全部继续通过。

限制（覆盖 4 个 Feature、注册表双份维护、物理接触为近似、时序不比较、无通用逆操作、
行为门禁需显式调用）已在 §10 如实记录。
