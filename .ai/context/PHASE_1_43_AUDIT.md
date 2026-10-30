# Phase 1.43 审计报告 — Chase Movement Behavior Evidence

日期：2026-10-23
分支：`master`　HEAD：`1c30f94`（本阶段未提交、未推送）

---

## 1. 开始状态、未提交修改与测试基线

- 起点：`master` / `1c30f94`；`git status` = 33 modified + 22 untracked
  （Phase 1.36–1.42 的未提交成果，含 1.42 的协议 v2、探针、6 个时间驱动 behavior
  与 `PHASE_1_42_AUDIT.md`）。
- 未执行 reset / clean / checkout / 批量 restore。对 tracked 文件的改动都是**追加式**：
  `chase_movement/template.yaml` 末尾追加 `behavior:`，`CONTRACT_INDEX.yaml` /
  `scene_composer_schema.yaml` / `FEATURE_SCHEMA.md` / `validator/README.md` /
  `run_tests.py` 增加字段与计数说明；没有删除或重写既有语义。
- 测试基线（1.42 结束时的全量）：**92/92 PASS**（Godot 39 + Python 53）。
  其中 Godot 39 含 1 个 **上一轮 e2e 中断残留**的 `Tests/test_e2e_probe_enemy.gd`；
  1.42 末尾的 e2e 所有权清理已把它删除，因此本阶段的稳态基线是
  **91 = Godot 38 + Python 53**。新增 1 个追击测试后，全量为 **92 = Godot 38 + Python 54**。
  计数口径不同不代表用例丢失（§7 详述）。
- 最终：34 modified（比起点新增 `chase_movement/template.yaml`；其余 33 个是 1.36–1.42
  的既有修改，本阶段只在其上追加文档字段）+ 25 untracked（新增夹具、测试、本报告）；
  无 tracked 删除、无基线改写。

---

## 2. `chase_movement` 实际实现与契约依据

`Features/chase_movement/chase_movement.gd`（`class_name ChaseMovement extends CharacterBody2D`）：

```gdscript
func _physics_process(_delta: float) -> void:
    if _target == null or not is_instance_valid(_target):
        _target = _resolve_target()
        if _target == null:
            velocity = Vector2.ZERO
            return
    velocity = (_target.global_position - global_position).normalized() * speed
    move_and_slide()
```

- 纯 `_physics_process` 驱动；**不使用** Timer、`_process`，也不读输入；
  移动不依赖碰撞体（夹具与组件都不需要 CollisionShape2D）。
- `target_path` 是 `NodePath` 导出属性，`_ready` 解析一次；目标无效/被释放时
  每物理帧按路径惰性重解析；路径为空或不可达 ⇒ `velocity = ZERO` 并**不移动**。
- 速度由 `speed`（默认 80）与到目标的单位向量决定；`move_and_slide()` 的真实位移
  依赖物理 delta（项目默认 60 Hz，固定 1/60）。
- 既有自测 `test_chase_movement.gd` 覆盖：接近目标、目标释放后停止、无目标静止；
  本阶段不重复其断言，而是把它变成**可重放的 evidence 契约**。

Feature 文档明确的行为规则（契约依据）：

1. 只朝 `target_path` 指向的节点移动，不读输入；
2. 目标缺失/未配置/已释放时保持静止，不报错；
3. 必须作为 `CharacterBody2D` 实体根使用。

本阶段据此只声明两条可证明的契约：**向有效目标接近**、**无目标保持静止**。
不把速度曲线、路径最优、目标切换或目标释放后的细节写成契约（§9）。

---

## 3. 能力缺口与最小扩展（先报告，再实施）

### 3.1 缺口

入口场景 `ChaseMovement.tscn` 只有一个 `CharacterBody2D` 根，没有目标，也没有配置
`target_path`（组件本身不应内置目标）。现有能力无法构造"带有效目标的追击者"：

| 现有能力 | 为什么不够 |
| --- | --- |
| `simulation.advance_frames` | 只能推进时间；没有目标时追击者不动 |
| `state.set_property` | 只支持协议 `properties:` 的**枚举**属性（当前仅 `trigger_switch.trigger_mode`）；`target_path` 是 `NodePath`，加入它需要新的属性类型/解析语义，属于扩大能力 |
| `physics.overlap` | 在**被观测节点自身位置**生成实体并挂在探针根下（名字固定 `BehaviorActor`）；它只能作为接触夹具，且现有动作无法设置 `target_path`（`NodePath`），所以不能把生成的实体变成追击目标 |
| `node2d.position/displacement` | 只能观测，不能提供目标 |

若只用入口场景，唯一可声明的是"无目标保持静止"。这**不能**发现"追击逻辑被禁用"这类
真实缺陷——冻结的追击者同样静止，会错误 PASS。因此必须先补足证据场景，而不是把
"没有观察到移动"解释成正确。

### 3.2 选择的最小扩展

新增**行为级证据场景**字段（不是协议能力）：

```yaml
behavior:
  - id: approach_target
    scene: ChaseTargetFixture.tscn     # 可选；相对本 Feature 目录的 .tscn
```

约束（Python 侧校验，违反 → `INVALID`）：

- 只能是**同一 Feature 目录**内的相对路径；拒绝绝对路径、`res://`、`.`/`..` 段、
  路径分隔异常与非 `.tscn`；
- 文件必须真实存在（`scene not found`）；
- 缺省时沿用模板入口场景；现有 12 个 behavior 的行为不变；
- 它只选择**证据场景**，不改变组合入口、不增加动作/观测/信号/参数、不写任何状态。

协议侧零改动：`behavior_protocol.yaml` 仍为 v2（8 动作 / 10 观测 / 5 信号），
`behavior_manifest.json` 未重新生成，`--check-manifest --capabilities` 仍 PASS。

### 3.3 证据夹具

`Features/chase_movement/ChaseTargetFixture.tscn`（仅证据使用，不参与组合）：

```
ChaseFixture (Node2D)
├── Chaser (CharacterBody2D, chase_movement.gd, speed=60, target_path="../Target")
└── Target (Node2D, position=(300,0))
```

- 容器根让 Chaser 与 Target 成为**同级**节点；若 Target 是 Chaser 的子节点，
  目标会随追击者一起移动，距离永远不变，断言会退化为"有没有速度"。
- `speed=60` 使位移恰为 **1 px/物理帧**，两次重放的观测值可稳定为 `59.0`
  （不需要放宽重放比较的浮点等价）。
- 夹具是静态文本、随 `Features/` 一起复制到隔离工作区；仓库场景不被写入。

---

## 4. 使用的协议能力与观测方法

| 能力 | 用途 |
| --- | --- |
| `simulation.advance_frames` | 真实 physics 帧（60 / 30），固定 delta；记录 `started_frame` / `ended_frame` / `advanced_frames` |
| `node2d.position` | 前置/后置确认 Target 静止在 `x=300`（区间 ±0.5） |
| `node2d.displacement` | 相对**动作前真实基线**的单轴位移：Chaser 的 x/y |
| `node.exists` | 追击者仍在树中且有效（排除"节点被释放但位移凑巧为 0"） |

未使用：`state.set_property`、`input.*`、`signal`、`physics.overlap`。
帧预算：`approach_target` = 60 + 1 = 61；`hold_without_target` = 30 + 1 = 31；
均远低于 600。无夹具动作。

---

## 5. 正向结果与重放一致性

| behavior | 前置条件 | 动作 | 后置断言 | 实测 | 重放 |
| --- | --- | --- | --- | --- | --- |
| `approach_target`（夹具场景） | Target `x=300±0.5`；Chaser 位移 `x=0±0.01` | 推进 60 physics 帧 | Chaser `displacement(x) ∈ [57.5, 62.5]`；`y=0±0.5`；Target 仍 `x=300±0.5`；Chaser 存在 | `59.0` / `0.0` / `300.0` / `true` | **2/2 一致（均 59.0）** |
| `hold_without_target`（入口场景） | — | 推进 30 physics 帧 | 根节点 `displacement(x)=0±0.01`、`y=0±0.01` | `0.0` / `0.0` | **2/2 一致（均 0.0）** |

- 60 次 `await physics_frame` 后，检查点位于物理帧边界，账户上只累计了 **59 次可观测位移**
  （`59.0 px`）；这是帧边界语义，不是丢帧。契约区间 `57.5..62.5` 明确覆盖 ±一帧的
  边界（58–61 px），不是"为了通过而放宽到任意值"。
- 两次重放的 `started_frame` 分别为 7 与 8（`ended_frame` 67/68），绝对帧号被重放比较
  忽略；关键状态（59.0 / 0.0 / 300.0 / true）完全一致。
- 位移来自真实 `CharacterBody2D.global_position`，不是 Python 推导；目标位置也在动作后
  重读，证明"Chaser +x 位移 = 与静止目标距离缩短"。

---

## 6. PASS / MISMATCH / INSUFFICIENT 的判定依据

沿用 1.40–1.42 的语义，未改判定代码：

- **PASS**：动作真实执行（`action_executed=true`）＋ 窗口内全部后置断言成立 ＋
  重放关键结果一致。本阶段两个 behavior 均满足。
- **MISMATCH**：动作执行了，但真实读数与契约冲突（含窗口耗尽仍未满足）。
  "只推进 1 帧却期望 60 帧的位移"属于此类：真实读数是 ~1.0 px，明确冲突，
  不是证据不足。
- **INSUFFICIENT**：观测目标/方法不可用、前置不满足、采集失败或重放不一致。
  "位移观测指向不存在的节点"属于此类：无法得到读数，不能判 PASS。
- **INVALID**：契约/协议非法（未知动作、参数越界、非法 `scene` 等），不执行动作。

选择原则：**能看到真实读数且不符 → MISMATCH；根本读不到 → INSUFFICIENT；两者都绝不 PASS。**

---

## 7. 负向对照与恢复校验

全部在隔离工作区或本次拥有的临时目录内进行；每项前后比 `sha256`。

| # | 对照（隔离副本） | 预期 | 实际 | 恢复 |
| --- | --- | --- | --- | --- |
| N1 | 冻结追击：`velocity = Vector2.ZERO`，删除 `move_and_slide()` | `approach_target` 不得 PASS | `MISMATCH / state_mismatch`；`hold_without_target` 仍 PASS（对照有针对性） | 脚本 `sha256` 与基线一致 |
| N2 | 无目标乱走：null 分支设置 `velocity=(speed,0)` 并 `move_and_slide()` | `hold_without_target` 不得 PASS | `MISMATCH`；`approach_target` 仍 PASS | 脚本 `sha256` 一致 |
| N3 | 目标不可达：夹具 `target_path` 改为 `../Absent` | `approach_target` 不得 PASS | `MISMATCH`；无目标行为仍 PASS | 夹具 `sha256` 一致 |
| N4 | 观测目标不存在：`node2d.displacement` 指向 `Absent` | 不得 PASS | `INSUFFICIENT / check_unavailable` | 无文件改动 |
| N5 | 观测窗口不足：只推进 1 帧，仍断言 60 帧位移 | 不得 PASS | `MISMATCH`（实测 ~1 px << 57.5） | 无文件改动 |
| N6 | 证据场景非法：`../`、绝对路径、`res://`、缺失文件、非 `.tscn` | `INVALID` | 5/5 `INVALID`，detail 指出具体原因 | 仅临时模板 |
| N6b | 合法嵌套场景 `fixtures/Nested.tscn` | 接受 | `res://Features/scene_nested/fixtures/Nested.tscn`，无错误 | 临时目录已删除 |
| N7 | CLI：真实缺陷（冻结追击）经 `--feature chase_movement --features-dir <copy>` | 非 0 且 `MISMATCH` | `exit=1`，输出含 `MISMATCH` | 副本脚本 `sha256` 一致 |

另外：`hold_without_target` 是 N1 的**特异性对照**（追击坏了它仍应通过），
`approach_target` 是 N2 的特异性对照——避免"一个缺陷让所有 behavior 一起失败"
这种没有定位能力的假象。

---

## 8. 回归矩阵与计数口径

**独立套件**（各自单独运行，断言计数不可相加为全量）：

| 检查 | 结果 |
| --- | --- |
| 新增追逐行为测试（Case 1–6） | **31/31 PASS**，exit 0 |
| Phase 1.40 行为证据测试 | **145/145 PASS**，exit 0（1.42 为 134；新增 2 个 behavior 的逐项检查与计数断言） |
| 协议一致性（1.41/1.42/1.43） | **96/96 PASS**，exit 0（1.42 为 92） |
| 时间驱动测试（1.42） | **72/72 PASS**，exit 0 |
| Phase 1.38 静态实例证据 | **41/41 PASS**，exit 0 |
| Phase 1.39 运行时实例证据 | **67/67 PASS**，exit 0 |
| 行为 CLI `--all --require-behavior`（每行为 2 次重放） | **14/14 PASS**（6 既有 + 6 时间驱动 + 2 追逐），exit 0 |
| 协议 manifest / 能力门禁 | PASS（8 动作 / 10 观测 / 5 信号，manifest 无漂移） |

**全量入口**（`python .ai/tools/run_tests.py`，按测试**文件**计数，包含上述套件）：

| 检查 | 结果 |
| --- | --- |
| 全量 `run_tests.py` | **92/92 PASS**，exit 0（Godot 38 + Python 54） |
| 静态 Validator `validate.py` | **0 error / 17 warning**，exit 0 |
| Godot headless | 38/38 PASS（含 `Features/chase_movement/test_chase_movement.gd`） |

计数口径说明：

- 全量的 92 是**测试文件数**，不是断言数；上表独立套件的 31/145/96/… 是各自的断言数，
  两者不应相加。
- Godot 从 1.42 的 39 变为 38，是因为 `Tests/test_e2e_probe_enemy.gd` 是 e2e 运行时
  **生成并在结束时删除**的产物；1.42 的 39 计入了上一轮中断残留。e2e 测试本身仍在本轮
  全量中 PASS（它内部生成、运行并清理该文件）。Python 从 53 增至 54，新增的正是本阶段
  的追逐测试。
- 17 条 warning 与 1.40–1.42 完全相同（`assets/**.png` 不在当前检出），与本阶段无关。

证据（临时日志，仅用于逐项追溯）：
`.ai/tmp/p143_chase_final.log`、`p143_final_test_behavior_protocol_consistency.log`、
`p143_final_test_feature_behavior_evidence.log`、`p143_test_behavior_time_driven.log`、
`p143_test_feature_instance_evidence.log`、`p143_test_runtime_instance_evidence.log`、
`p143_cli_all.log`、`phase143_full_clean.log`、`p143_validator.log`。

---

## 9. SHA256 恢复与工作区清理

- 对照基线（仓库文件）：
  - `Features/chase_movement/chase_movement.gd`
  - `Features/chase_movement/ChaseTargetFixture.tscn`
  - `Features/chase_movement/template.yaml`
- 每次注入缺陷/改夹具后都恢复原字节，并立即断言 `sha256 == 基线`；
  CLI 使用的 Features 副本同样恢复后比对；测试结束后删除本次创建的临时目录。
- 运行完整测试后仓库 `git status` 仍为 34 modified + 24 untracked（本报告加入后 25），
  没有新增/删除 tracked 文件；e2e 只清理它自己生成的文件。
- 未修改黄金 trace 基线、e2e 基线或 `Scenes/*.tscn`。

---

## 10. 尚未支持的行为与不能据此得出的结论

1. **目标被释放后停止**：文档有此规则，但协议没有"释放节点"的动作，本阶段未把它写成
   behavior 契约；仅由既有自测覆盖。不要声称行为证据已证明该规则。
2. **距离观测**：协议没有 `distance` 观测。本阶段用"Target 静止 + Chaser 位移"间接证明
   接近，不能据此断言任意时刻的距离曲线。
3. **速度契约**：夹具用 `speed=60`（1 px/帧）保证可重放；默认 80 仅由自测覆盖。
   不能据 `59.0 px` 得出"默认速度精确正确"。
4. **路径/避障/碰撞**：夹具无碰撞形状与障碍；不能证明绕行、推挤或卡住时的行为。
5. **目标切换/多目标/多追击者**：未声明、未测试。
6. **组合场景**：证据只覆盖组件在夹具场景中的行为，不覆盖 `SlimeEnemy.tscn` 等组合
   （组合层由 1.38/1.39 的结构/实例证据负责，层次不同）。
7. **process 帧或输入驱动的追击**：实现不使用，协议也未声明 process 帧。
8. 行为证据仍是独立入口，不嵌入静态 Validator；本阶段没有改变该边界。

---

## 11. 结论

- `chase_movement` 的两个 behavior 在真实 Godot 运行时 PASS，关键结果 2/2 重放一致；
  真实缺陷（冻结、无目标乱走、目标不可达）分别稳定产生 `MISMATCH`，
  观测不可用产生 `INSUFFICIENT`，没有出现虚假 PASS。
- 现有协议动作表**未扩展**：缺口是"证据场景无法自带目标"，用可选的、受目录约束的
  `behavior[].scene` 解决；它只选择证据场景，不增加动作/观测/参数或写入权限。
- Phase 1.40 的 6 个 behavior 与 Phase 1.42 的 6 个 behavior 全部继续通过
  （CLI 14/14），协议 manifest 无漂移。
- 全量 92/92、Godot 38/38、静态 Validator 0 error；限制与不能得出的结论已在 §10 列明。
