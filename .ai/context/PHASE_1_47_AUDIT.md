# Phase 1.47 审计报告 — contact_damage 行为证据与敌人接触伤害链验证

- 阶段：Phase 1.47（Phase 1.40–1.46 能力的延续，不新增框架）
- 日期：2026-10-24
- 分支：`master`，HEAD：`1c30f94 feat: unified run identity, e2e serial lock and resource ownership hardening (Phases 1.26-1.34)`
- 结论摘要：`contact_damage` 现在有 **3 条真实运行时行为契约**（真实物理重叠 + 物理帧节拍结算 + 真实 Health.tscn），
  20 条 behavior 全部 PASS 且重放一致；6 类负向对照稳定拒绝错误实现；`SlimeEnemy` 组合验证**经审计后不实施**
  （现有组合协议无法在不新增产品场景的前提下表达该链），已给出最小设计与安全影响。

---

## 1. 修改前后的工作区状态

### 1.1 开始前（基线）

- `git status`：工作区**已存在**上一阶段未提交的修改（Phase 1.26–1.46 的产物），包括 38 个已跟踪文件的修改
  （`.ai/context/*`、`.ai/tools/run_tests.py`、`.ai/tools/validator/*`、`Features/*/template.yaml`、
  `Orchestration/level_config.gd`、`Tests/*.gd` 等）与大量未跟踪文件（`.ai/context/PHASE_1_3x-4x_AUDIT.md`、
  `.ai/context/behavior_protocol.yaml`、`.ai/tools/scene_composer/{probes,feature_behavior_evidence.py,…}`、
  `Features/chase_movement/ChaseTargetFixture.tscn` 等）。
- 暂存区：空（没有已 `git add` 的内容）。
- 处理方式：**全部保留**。本阶段没有执行 `git reset` / `git checkout` / `git stash` / `git add` / `git commit`，
  没有删除任何无法证明归属的文件。

### 1.2 本阶段新增 / 修改（仅这些）

| 文件 | 类型 | 作用 |
| --- | --- | --- |
| `Features/contact_damage/template.yaml` | 修改 | 新增 `behavior:` 三条契约（含数值来源注释） |
| `Features/contact_damage/ContactDamageFixture.tscn` | 新增 | 行为证据场景（两个真实 ContactDamage 实例 + 一个远点） |
| `.ai/tools/scene_composer/probes/feature_behavior_probe.gd` | 修改 | 补上既有 `@actor` 目标在**信号观测**上的实现缺口（动作执行后重试连接；见 §2.3） |
| `.ai/tools/scene_composer/tests/test_contact_damage_behavior.py` | 新增 | 本阶段行为测试（正向 + 6 类负向对照 + 重放 + 非法契约 + CLI） |
| `.ai/tools/scene_composer/tests/test_feature_behavior_evidence.py` | 修改 | 17 → 20 条 behavior；新增 Phase 1.47 声明断言 |
| `.ai/tools/scene_composer/tests/test_behavior_protocol_consistency.py` | 修改 | 17 → 20；新增 contact_damage 声明覆盖断言 |
| `.ai/tools/scene_composer/tests/test_feature_capability_adoption.py` | 修改 | 修 `scene_node_types()`：只读入口场景（见下） |
| `.ai/tools/run_tests.py` | 修改 | 文档头计数：scene_composer 26 → 27、Python 56 → 57、合计 94 → 95 |
| `.ai/context/CONTRACT_INDEX.yaml` | 修改 | 行为证据层登记 `test_contact_damage` |
| `.ai/context/PHASE_1_47_AUDIT.md` | 新增 | 本报告 |

`test_feature_capability_adoption.py` 的修改是**必要修正**：其 `scene_node_types()` 原本扫描
`Features/<id>/` 下**所有** `.tscn`，把「只用于行为证据的夹具场景」当成「组件入口场景自带结构」的证据。
新夹具含 `CollisionShape2D`，于是 `owns_shape=True`，而真正的入口场景 `ContactDamage.tscn`（仅 Area2D + 脚本）
并不自带碰撞形状，审计断言自相矛盾（`BLOCKED` 却被要求 `PASS`）。修正后只读
`template.yaml#scene.source`（`template_loader.template_scene_path`），与该函数的文档语义、以及
`behavior[].scene`「只选择证据、不改变组合入口」的原则一致。修正后该测试 100% PASS。

---

## 2. 实现范围与设计依据

### 2.1 被测组件（审计结论）

`Features/contact_damage/contact_damage.gd`：`Area2D`，`@export damage=1 / tick_interval=0.5 / target_group="players"`，
`_physics_process` 里按节拍遍历 `get_overlapping_bodies()`，对「在 `target_group` 组内且拥有名为 `Health` 的子节点」
的实体调用 `Health.take_damage(damage)`。**没有公开方法、没有信号**（`feature.yaml#interfaces.signals: []`）。

因此该组件的唯一真实行为入口是「真实重叠 + 物理帧节拍」，不能用方法调用（`health.take_damage`）代替被测行为——
那会绕过被测代码。这也决定了证据场景的形状。

`Features/health/health.gd`：`take_damage(amount)` 忽略 `amount<=0` 与死亡后伤害；`health_changed(current, amount)`
与 `died` 是唯一可观测事件（伤害量在 `health_changed` 的第二个参数里）。`max_health` 默认 5。

### 2.2 证据场景 `ContactDamageFixture.tscn`（Feature 目录内）

```
ContactDamageFixture (Node2D)
├── ContactDamage (Area2D, script=contact_damage.gd)     36×36 ContactShape，damage=1
│   └── ContactShape (CollisionShape2D)
├── Heavy (Area2D, 同脚本)   position (0,200)，damage=3
│   └── ContactShape (CollisionShape2D)
└── FarPoint (Node2D)        position (400,0)
```

- `Heavy` 是同一脚本的第二实例、**只改配置**（`damage=3`）：用来证明「伤害量被尊重」而不是硬编码 1。
- `FarPoint` 是定位点，离两个接触区都远（400 px）：用来证明「不接触就不掉血」。
- 目标实体由协议动作 `physics.overlap` 生成：真实 `CharacterBody2D` + 真实 `Health.tscn`（`health_max=5`），
  加入 `players` 组，放在目标节点的**全局位置**。**不使用** `physics.overlap` 的 `damage` 参数——那个参数会直接
  调用 `take_damage`，等于替被测组件制造结果。
- 场景只通过 `behavior[].scene` 被选择（相对 Feature 目录的 `.tscn`，Python 侧拒绝绝对路径 / `res://` / `..`），
  不改变 `scene.source`（组合入口仍是 `ContactDamage.tscn`）。

### 2.3 探针的唯一改动：`@actor` 信号监听缺口（不新增能力）

Phase 1.40 起 `@actor` 只用于「动作已执行后才有目标」的观测。但探针的 `_connect_watches()` 在**动作之前**
一次性解析所有 `observe_signal` 目标：`@actor` 此时还不存在（`_resolve` 返回 `null`）→ 直接 `continue`，
信号监听**永远不会建立**。而 `_observe_signal()` 在 `_signals` 里查不到 `watch_key` 时返回
`{"available": false}` → `UNAVAILABLE` → 整个契约 `INSUFFICIENT`。即：`@actor` 上的信号断言此前**不可能 PASS**。

本阶段的最小修复（无新动作、无新观测、无新信号白名单、无新权限）：

```gdscript
var _pending_actor_watches: Array = []          # @actor 目标先登记
# _connect_watches(): target 以 @actor 开头 → _pending_actor_watches.append(entry)
# _run(): 每个动作执行后 → _connect_actor_watches()  # 现在的 _actor 可能已经存在
func _connect_actor_watches() -> void:
    if _actor == null or not is_instance_valid(_actor): return
    for entry in _pending_actor_watches: _connect_watch(entry)
```

失败方向是**保守**的：拿掉重试后，`@actor` 信号断言只会 `INSUFFICIENT / check_unavailable`，绝不会因为
“没连上所以计数 0”而假 PASS。本阶段把它做成可复现对照（测试 Case 7，在隔离项目副本里删掉重试调用后验证）。

### 2.4 未改动的协议层

- `behavior_protocol.yaml`：**零改动**（无新动作/观测/信号/属性）。
- `probes/behavior_manifest.json`：未重新生成，漂移检查通过（`feature_behavior_evidence.py` 每次运行都调
  `behavior_protocol.check_manifest`）。
- `composite_behavior_protocol.yaml` 与组合 manifest：**零改动**（未扩场景白名单，见 §6）。

---

## 3. 正向行为契约与真实运行时证据

命令：`python .ai/tools/scene_composer/feature_behavior_evidence.py --feature contact_damage --json`
（内部 `--replay 2`，隔离工作区 `.ai/tmp/behavior/workspace-*/project`，运行后删除）。

| behavior | 动作（真实） | 前置 | 后置断言 | 实测 | 首次观察帧 | 重放 |
| --- | --- | --- | --- | --- | --- | --- |
| `damage_on_contact` | `physics.overlap(target=ContactDamage, group=players, health_max=5)`；窗口 45 帧 | — | `health.current(@actor/Health)=4`；`signal health.health_changed` count=1 且 `last_args=[4,1]` | health **4**，事件 **1** 次 `[4,1]` | `first_observed_frame=25`（`waited_frames=25`） | **2/2 一致**（waited 25 / 24，绝对帧 63 / 61） |
| `no_damage_without_contact` | `physics.overlap(target=FarPoint, …)` + `simulation.advance_frames(40)`；窗口 5 帧 | — | health=5；事件 count=0 | health **5**，事件 **0** | 0（动作结束即成立） | **2/2 一致**（action_frame 99 / 101，即推进了 40 个物理帧） |
| `damage_amount_is_respected` | `physics.overlap(target=Heavy, …)`（`damage=3`）；窗口 45 帧 | — | health=2（5−3）；事件 count=1 且 `last_args=[2,3]` | health **2**，事件 **1** 次 `[2,3]` | `first_observed_frame=25` | **2/2 一致**（waited 25 / 25，绝对帧 65 / 63） |

契约要求的记录项对应关系：

- **动作与目标**：见上表「动作」列；目标实体是探针生成的真实 `CharacterBody2D`（`group=players`）+ 真实 `Health.tscn`。
- **接触前生命值**：`no_damage_without_contact` 直接断言 5；`damage_on_contact` 的 `physics.overlap` 不带 `damage` 参数，
  接触前 health 一定为 `max_health=5`（探针结果里 `health.current` 首帧观测即 5，见证据 `result.json` 的 `checks`）。
- **实际接触证据**：伤害只能在 `get_overlapping_bodies()` 包含该实体时发生（组件源码唯一入口）；
  反向对照见 §5（删掉重叠遍历后无接触也掉血 → MISMATCH）。
- **伤害事件**：`health.health_changed(current, amount)` 的计数与参数（`[4,1]` / `[2,3]`）。
- **首次观察帧**：`first_observed_frame` 分别为 25 / 0 / 25。
- **重放与证据路径**：`.ai/tmp/behavior/<run_id>/{contract.json,result.json,stdout.log,stderr.log}`，每个行为 2 份（`-r1`/`-r2`）。

### 3.1 为什么窗口是 45 帧（实测，不是拟合）

- `tick_interval=0.5s`，physics 60 Hz → 30 帧一个结算节拍。
- 实测（多次运行）：实体在 `action_frame=1` 加入后，**首次伤害在 `waited_frames=24–25` 被观察到**；第二个节拍约在
  第 54–55 帧。窗口 45 帧因此「只可能看到一次结算」，既不会因第二个节拍变得不可判定，也不会短到看不到首次伤害。
- **先前事实（保留在报告里）**：最初版本把窗口写成 20 帧，CLI 给出 `MISMATCH`（health 仍为 5）。这不是时序抖动：
  20 帧 = 0.33 s < 0.5 s，物理上不可能看到第一个节拍。**没有放宽断言**，而是把窗口改成由 `tick_interval` 推导的
  45 帧，并把这一事实写进 `template.yaml` 注释与 §5 Case 3（5 帧窗口仍必须 MISMATCH）。

---

## 4. 重放一致性

- 每个 behavior 默认 2 次重放；比较键为 `status / reason / action_executed / checks[*].{check,target,entry,expected,observed,status}`，
  忽略 `run_id`、绝对帧号与耗时（Phase 1.41/1.42 既有语义）。
- 三条契约 6 次运行全部 PASS，`replay_consistent=True`。
- 注意：`no_damage_without_contact` 的两次运行 `action_frame` 分别为 99 / 101（进程内绝对帧），关键结果一致，
  说明重放比较没有被绝对帧污染。
- 反向对照（§5 Case 4）证明：两次重放结果不一致时结论是 `INSUFFICIENT / replay_inconsistent`，且两次结果都保留。

---

## 5. 负向对照（隔离副本注入，逐字节恢复）

全部在 `.ai/tools/scene_composer/tests/test_contact_damage_behavior.py` 中，命令：

```
python .ai/tools/scene_composer/tests/test_contact_damage_behavior.py
```

结果：**39 条断言全 PASS，exit 0**。注入只发生在隔离副本（`BehaviorWorkspace` 的 `project/Features/...` 或
`.ai/tmp/.../cli/Features` 副本），每步都用 SHA256 逐字节校验恢复，最后再校验仓库文件未被改动。

| # | 注入的故障（隔离副本） | 预期 | 实际 | 退出码 |
| --- | --- | --- | --- | --- |
| 2a | 删除伤害调用（`health.take_damage(damage)` → `pass`）：等价于「伤害连接被断开/调用未生效」 | `damage_on_contact` → `MISMATCH/state_mismatch`（health 仍 5）；`no_damage_without_contact` 仍 PASS | 与预期一致；脚本恢复 SHA256 一致 | 0 |
| 2b | 伤害量被硬编码（`take_damage(1)`） | **只有** `damage_amount_is_respected` → `MISMATCH`（observed 4 / expected 2）；`damage_on_contact` 仍 PASS | 与预期一致；恢复 SHA256 一致 | 0 |
| 2c | 删除接触前置（`get_overlapping_bodies()` → `get_nodes_in_group(target_group)`） | `no_damage_without_contact` → `MISMATCH`（无接触也掉血，health < 5 且事件 ≥ 1）；`damage_on_contact` 因多余节拍 → `MISMATCH` | 与预期一致（正向契约被多余结算打穿，说明窗口内的“恰好一次”有意义）；恢复 SHA256 一致 | 0 |
| 3a | 观测目标不存在（`@actor/Absent`） | `INSUFFICIENT / check_unavailable`（不得 PASS） | 与预期一致 | 0 |
| 3b | 无有效观察窗口（`window_frames=5`，短于一个节拍） | `MISMATCH / state_mismatch`，`waited_frames=5`，observed health 5 | 与预期一致 | 0 |
| 4 | 重放结果不一致（runner 在第二次重放里篡改 observed） | `INSUFFICIENT / replay_inconsistent`，两次结果都保留（4 / 5） | 与预期一致 | 0 |
| 5a | 非法契约：`window_frames: 0` | `INVALID`（不启动 Godot） | 与预期一致 | 0 |
| 5b | 非法契约：`physics.overlap` 缺 `group` | `INVALID` | 与预期一致 | 0 |
| 5c | 非法契约：`scene: ../…../../escape.tscn`（越界） | `INVALID`（`relative path inside`） | 与预期一致 | 0 |
| 6 | CLI 对真实缺陷的行为（隔离 Features 副本人为静音伤害调用） | 非 0 退出且输出含 `MISMATCH`；副本恢复 SHA256 一致；仓库文件 SHA256 不变 | `exit=1`，输出含 `MISMATCH`；恢复一致 | **1（预期失败）** |
| 7 | 探针缺少 `_connect_actor_watches()` 重试（§2.3） | `@actor` 信号断言 → `INSUFFICIENT / check_unavailable`（不会假 PASS） | 与预期一致；副本恢复 SHA256 一致 | 0 |

状态语义区分（与 Phase 1.40–1.46 一致，未修改）：

- **MISMATCH**：动作真的执行了，但可观测行为与契约不符（含窗口耗尽）。
- **INSUFFICIENT**：证据不足（观测不可用、采集失败、重放不一致、Godot 缺失、动作不可执行）。
- **INVALID**：契约 / 参数 / 协议非法（不执行任何动作）。

`contact_damage` 没有信号，因此「接触信号被断开」这一故障类别在本组件上映射为**伤害调用被移除**（2a）；
这是组件契约决定的等价物，不是省略。

---

## 6. SlimeEnemy 组合场景可行性审计（结论：本阶段不实施）

### 6.1 场景事实（审计）

`Scenes/SlimeEnemy.tscn`：

```
SlimeEnemy  = 实例化 Features/chase_movement/ChaseMovement.tscn（CharacterBody2D 根脚本）
├── Health (Health.tscn, max_health=5)
├── ContactDamage (contact_damage.gd)  + ContactShape 36×36   ← 伤害来源
├── Collision (CollisionShape2D 28×28)
├── SlimeAnim (AnimatedSprite2D) / SlimeHurtSfx (AudioStreamPlayer)
```

- 根节点**没有 `groups`**，`ChaseMovement.target_path` 也未配置 → 该场景里的史莱姆**不会追击、也不会被其它系统按组发现**。
- 伤害方向：`ContactDamage.target_group` 默认 `"players"`，要求目标有名为 `Health` 的子节点
  （`Features/player_movement/Player.tscn` 满足：CharacterBody2D + `Collision` 32×48 + `Health`(max 10)）；
  `Player` 的 `players` 组由**宿主场景数据**声明（EscapeRoom / SurvivalArena / TimedCombatArena 都是
  `groups=["players"]`），`Player.tscn` 自身没有组。
- `ContactDamage` 的重叠列表里**包含史莱姆自己的身体**（Area2D 是 CharacterBody2D 的子节点）：实测先看到
  `overlap=1`，玩家靠近后才 `overlap=2`。自伤被 `target_group` 过滤挡住，这也解释了组过滤为何是必需的。

### 6.2 实测：链本身是真实的（临时场景，未进入仓库）

在 `.ai/tmp/t147_dbg/` 造了一个**临时**宿主场景（Player 在 `(-100,0)`，SlimeEnemy 在 `(0,0)`，`groups=["players"]`），
用 `-s` 脚本按 `move_right` 真实推进物理帧：

```
start player=(-100,0) slime=(0,0) hp=10 slime_hp=5 contact_shape=RectangleShape2D(36×36)
first overlap at frame 0 ...            # 仅史莱姆自身（组过滤使其不受伤害）
15  player_x=-41.33 hp=10 overlap=1
30  player_x=-30.01 hp=10 overlap=2     # 被史莱姆身体挡在 30 px（16+14），接触区 36 已重叠
45  player_x=-30.01 hp=9
75  player_x=-30.01 hp=8
135 player_x=-30.01 hp=6
end x=-30.07 hp=6 slime_hp=5
events=[[9,1,40],[8,1,71],[7,1,102],[6,1,133]]
```

结论：**链真实存在且可观测**——玩家走进敌人，敌人 `ContactDamage` 按 0.5 s 节拍扣玩家血，敌人自身血量不变，
没有任何夹具写状态。首击在物理帧 40（约等于「进入接触区后一个节拍」）。

### 6.3 为什么不能直接写成组合契约（阻塞原因）

1. **组合协议一次只加载一个白名单场景**（`scenes:` → 逐字匹配，单契约单 `scene`）。`SlimeEnemy.tscn` 里没有玩家。
2. **组合探针不支持 `@actor` 目标**：`_resolve()` 只按相对 `_scene` 的路径解析；`physics_overlap` 生成的
   `CompositeActorN` 没有任何可寻址语法，`observe_health_current` 又要求目标节点自己实现 `get_current_health()`。
   → 用 `physics.overlap` 在史莱姆身上生成玩家并观测其血量，在当前组合探针里**不可表达**（只会 INSUFFICIENT）。
3. **没有现成的「玩家 + 静态史莱姆」正式场景**：`SurvivalArena` / `TimedCombatArena` 的敌人由
   `Orchestration` 在运行时生成到 `Entities/`（SurvivalArena 的生成是随机的——正是 Phase 1.46 记录的通行不稳定源），
   `EscapeRoom` 没有敌人。
4. 因此「扩展白名单」并不能只加一行：必须先新增一个产品场景。

### 6.4 最小设计（供后续阶段审批，本阶段不落地）

1. 新增正式场景 `Scenes/SlimeContactArena.tscn`：`Node2D` + `Player`（`groups=["players"]`，`(-160,0)`）+
   `SlimeEnemy`（`(0,0)`）；**无胶水脚本、无额外信号连接**，全部交互来自两个 Feature 的既有物理行为。
2. `composite_behavior_protocol.yaml#scenes` 增加 `slime_contact: Scenes/SlimeContactArena.tscn`（逐字白名单），
   重新生成 `probes/composite_behavior_manifest.json` 并跑漂移检查。
3. 契约 3 段：① 右移 25 帧 → `Player/Health=10` 且 `node2d.position(Player).x ∈ [-60,-34]`（尚未接触）；
   ② 继续 45 帧 → `Player/Health<10`、`Player/Health.health_changed` count≥1、`SlimeEnemy/Health=5`（伤害单向）；
   ③ 左移 45 帧离开接触区后再推 45 帧 → `Player/Health` 不再下降（证明“接触”而不是“靠近即扣血”）。
4. 独立负向对照：在隔离副本里删掉 `SlimeEnemy/ContactDamage/ContactShape` → 第 ② 段必须 `MISMATCH`；
   另一条对照保持 EscapeRoom 链不变（防串扰）。
5. 安全影响：**不新增任何动作 / 观测 / 信号 / 夹具属性**，只新增一个逐字白名单条目与一个场景文件；
   组合契约仍禁止 `state.set_property`，仍不允许任意方法调用或输入注入。
6. 产品影响（本阶段不实施的真正原因）：这会给 `Scenes/` 增加一个**只为证据服务**的场景。
   Phase 1.46 的组合证据刻意使用正式场景（EscapeRoom / SurvivalArena）；新增“为证据而生的竞技场”属于产品决策，
   应由人决定，而不是在验证阶段自行扩权。

---

## 7. SurvivalArena 随机性处理

- Phase 1.46 记录的「随机敌人生成导致通行段不稳定」**保持原状**，本阶段没有任何修改。
- 未放宽任何通行断言、未把不稳定结果标成 PASS、未改动正式游戏的随机生成或碰撞、未把随机差异藏进汇总指标。
- 组合 CLI 本次仍只跑已证明稳定的链：
  `python .ai/tools/scene_composer/composite_behavior_evidence.py --all --require-composite --replay 2`
  → `escape_room 4/4 PASS`、`survival_arena 2/2 PASS`（`both_doors_start_closed`、`reward_switch_opens_both_doors`），
  `replay=2 consistent=True`，exit 0。通行段仍**不在**稳定基线内。

---

## 8. 回归测试清单（逐段命令与退出码）

Godot 4.7 stable headless，Windows；`python` 为 CPython 3.12。

| # | 命令 | 结果 | 退出码 |
| --- | --- | --- | --- |
| 1 | `python .ai/tools/scene_composer/tests/test_contact_damage_behavior.py` | **39 PASS**（含 11 条负向对照断言） | **0** |
| 2 | `python .ai/tools/scene_composer/feature_behavior_evidence.py --all --require-behavior --replay 2` | **pass=20** mismatch=0 insufficient=0 invalid=0 not_declared=0 | **0** |
| 3 | `python .ai/tools/scene_composer/composite_behavior_evidence.py --all --require-composite --replay 2` | escape_room 4/4、survival_arena 2/2，均 `replay=2 consistent=True` | **0** |
| 4 | `python .ai/tools/run_tests.py --godot-only` | **38/38 PASS**（Godot=38） | **0** |
| 5 | `python .ai/tools/scene_composer/tests/test_behavior_protocol_consistency.py` | 全部 PASS（含 20 条 behavior ×2 重放、探针能力门禁、静态/运行时实例证据） | **0** |
| 6 | `python .ai/tools/scene_composer/tests/test_feature_behavior_evidence.py` | 全部 PASS（含 20 条 behavior ×2 重放、13 个 Case） | **0** |
| 7 | `python .ai/tools/run_tests.py test_behavior_time_driven` | 1/1 PASS | **0** |
| 8 | `python .ai/tools/run_tests.py test_chase_movement_behavior` | 1/1 PASS | **0** |
| 9 | `python .ai/tools/run_tests.py test_condition_gate_behavior` | 1/1 PASS | **0** |
| 10 | `python .ai/tools/run_tests.py test_composite_behavior_evidence` | 1/1 PASS | **0** |
| 11 | `python .ai/tools/run_tests.py test_composite.py` | 1/1 PASS | **0** |
| 12 | 其余 19 个 scene_composer 测试（逐文件过滤运行，见 §8.1） | 19/19 PASS（其中 1 个先失败，修正 §1.2 后重跑通过） | **0** |
| 13 | `python .ai/tools/run_tests.py validator` | **10/10 PASS** | **0** |
| 14 | `python .ai/tools/run_tests.py runtime` | 5/5 PASS | **0** |
| 15 | `python .ai/tools/run_tests.py feature_registry` | 4/4 PASS | **0** |
| 16 | `python .ai/tools/run_tests.py gameplay_planner` | 2/2 PASS | **0** |
| 17 | `python .ai/tools/run_tests.py asset_registry` | 11/11 PASS | **0** |
| 18 | `python .ai/tools/run_tests.py evaluation` | 2/2 PASS | **0** |
| 19 | `python .ai/tools/validator/validate.py` | **0 error / 17 warning**（全部是既有资产 manifest 缺图警告，与 Phase 1.46 基线一致） | **0** |
| 20 | `python .ai/tools/run_tests.py e2e` | 2/2 PASS（`test_end_to_end_generation.py` + `test_e2e_ownership.py`） | **0** |

### 8.1 关于「scene_composer 段不能一条命令跑完」

`python .ai/tools/run_tests.py scene_composer`（27 个测试）**单条命令在工具 600 s 上限内没有结束**——不是断言失败，
而是本机执行时间超过工具时限。因此按 Phase 1.47 §7 的分段要求，用**独立命令**逐段跑（表 5–12），并如实记录：

- 先单独跑最贵的三个（5/6/1）；
- 再按 4 组过滤跑其余（7–11 与 12）；
- 12 段逐文件过滤的 19 个文件：**首次运行有 1 个失败** —— `test_feature_capability_adoption.py`
  （`contact_damage bare plan verdict … / a self-declared collider never leaves errors behind`），
  根因是新夹具场景被 `scene_node_types()` 误当作入口场景（见 §1.2）。修正该函数后重跑 **exit 0**。
- 该失败与被测实现无关，但**没有跳过、没有放宽**：修正的是「读取入口场景」的实现，语义未变（仍要求
  「声明 Collision ⇒ 裸计划 BLOCKED，除非入口场景自带形状」）。

### 8.2 e2e 首次运行的失败与复跑（如实记录）

- 第一次 `run_tests.py e2e` **失败**：`test_end_to_end_generation.py` 在 `_make_sandbox` 的 `shutil.copytree`
  复制项目时，`.ai/tmp/behavior/workspace-wq38v677` 正在被**同时运行的** `test_contact_damage_behavior.py`
  创建/删除，`WinError 3 系统找不到指定的路径` → 复制中断。
- 根因是**我在同一条时间窗里并行跑了另一个会创建/删除 `.ai/tmp/behavior/workspace-*` 的测试**，不是产品缺陷，
  也不是 e2e 逻辑问题；该并发在 Phase 1.46 记录的资源所有权约束之外（同一测试套件内是串行的）。
- 复跑：清掉本次运行遗留的两个 workspace 目录后单独运行 e2e → **2/2 PASS, exit 0**（表 20）。

---

## 9. 已知限制与未覆盖行为

1. **`physics.overlap` 是静态近似接触**：在目标位置生成 32×32 的 `CharacterBody2D`，只证明「重叠时按节拍结算」，
   不模拟移动轨迹、速度或多段连续接触。`SlimeEnemy` 的实测（§6.2）用的是真实移动的玩家，但那属于审计实验，不在基线里。
2. **节拍语义只覆盖默认配置**：`tick_interval=0.5`、`damage>0`、存活目标。未覆盖：非默认节拍的边界、`damage<=0`、
   死亡后继续重叠（由 `Health` 的死亡守卫兜底，`health` Feature 自己的契约覆盖）、`tick_interval` 极小时的多次结算。
3. **重放只比较关键结果**：帧号/等待帧/耗时被排除，因此「时序抖动、偶发慢一帧」不会被发现；若将来需要时序契约，
   应新增独立的时序断言，而不是收紧现有比较。
4. **`@actor` 仅 Feature 探针支持**：组合探针没有该语法（§6.3），这类“动作生成实体再观测”的组合链仍不可表达。
5. **组合协议仍是单场景、分阶段、逐字白名单**：不支持「两个场景叠加」，因此玩家 + 敌人的链必须有宿主场景。
6. **行为门禁不在静态 Validator 内**：`validate.py` 不变，最终验收需显式运行
   `feature_behavior_evidence.py --all --require-behavior`；忘记运行不会被静态门禁发现。
7. **环境**：仅 Windows + Godot 4.7 stable headless 实测；隔离工作区的 `--import` 预构建是必要步骤
   （`contact_damage` 依赖 `class_name Health`）。

---

## 10. 临时文件、隔离副本与恢复验证

| 位置 | 内容 | 处置 |
| --- | --- | --- |
| `.ai/tmp/t147_dbg/` | 本阶段临时调试脚本（`probe.gd`、`pos_check.gd`、`slime_contact_probe.gd`）、临时场景 `SlimeContactProbe.tscn`、各段日志 | **已删除**（数值与命令已抄进本报告 §3/§6/§8）；原始日志在删除前已核对 |
| `.ai/tmp/behavior/<run_id>/` | 行为证据（`contract.json` / `result.json` / `stdout.log` / `stderr.log`），每个行为 2 份 | 保留（审查用，`.gitignore` 覆盖） |
| `.ai/tmp/behavior/workspace-*` | 行为测试/CLI 的隔离项目副本 | 工具正常退出时自行删除；本次因工具时限杀掉一个后台段，遗留 `workspace-0e8d2p0r`、`workspace-ws1crmqd`（18:34/18:43，本次运行所有）→ **已删除**并确认；`workspace-eb238eca`（16:57）**归属未知，按规则保留** |
| `.ai/tmp/composite/<run_id>/` | 组合证据 | 保留；`--list-stale` 报告 `no stale workspaces` |
| 注入的缺陷副本 | `BehaviorWorkspace.project/Features/contact_damage/contact_damage.gd`、`.ai/tmp/.../cli/Features/...`、隔离探针副本 | 每步 SHA256 逐字节恢复；工作区销毁；仓库文件 SHA256 断言未变（测试 Case 2/6/7） |

恢复验证：测试内 `sha256(script) == baseline["script"]` 分别在 2a/2b/2c 之后各断言一次，CLI 副本与探针副本各一次，
最后再断言仓库 `contact_damage.gd` / `ContactDamageFixture.tscn` / `template.yaml` 三者 SHA256 未变。

---

## 11. 协议变更与 manifest 漂移

- `behavior_protocol.yaml`：**无变更**（无新动作/观测/信号/属性；`@actor` 语法本就存在，属实现缺口修复）。
- `probes/behavior_manifest.json`：**无变更**，`check_manifest` 无漂移（CLI 与一致性测试均通过）。
- `composite_behavior_protocol.yaml` / `probes/composite_behavior_manifest.json`：**无变更**（未扩白名单）。
- 探针能力一致性：`test_behavior_protocol_consistency.py` 通过（探针实现集合 = 协议声明集合，无多余实现、
  无缺失实现、`denied_actions` 一致）。
- 静态实例证据 / 运行时实例证据 / Validator：未受本阶段影响（§8 表 12/13/19）。

---

## 12. 结论

1. `contact_damage` 现在有 3 条真实接触驱动的行为契约，均为**真实物理重叠 + 物理帧节拍 + 真实 Health.tscn**，
   没有直接调用私有回调、没有手工改血量、没有用 `state.set_property` 冒充行为。
2. 断连等价故障（伤害调用被移除）稳定检出为 `MISMATCH`；伤害量断言有真实区分能力（硬编码 1 只让“伤害量”契约失败）。
3. 观测不可用 / 窗口不足 / 重放不一致 / 契约非法分别得到 `INSUFFICIENT` / `MISMATCH` / `INSUFFICIENT` / `INVALID`，
   没有一条会误报 PASS。
4. Phase 1.40–1.46 的能力全部回归通过（20/20 behavior、组合链 2/2、Godot 38/38、Python 各段、Validator 0 error）。
5. `SlimeEnemy` 组合验证**经审计不实施**：链真实存在（§6.2 实测），但当前组合协议需要一个「玩家 + 静态敌人」的宿主场景，
   而 `Scenes/` 里没有这样的正式场景；最小设计（§6.4）与安全影响已记录，等待人工决定是否新增该产品场景。
6. 未提交、未推送；工作区既有的未提交修改全部保留。
