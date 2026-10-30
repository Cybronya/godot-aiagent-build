# Feature Metadata Schema

定义所有 Feature 的机器可读元数据格式（`feature.yaml`）。

目的：让 Agent 无需依次阅读 README.md → gdscript → test 才能理解一个 Feature，
而是先读 `feature.yaml` 快速获得：Feature 身份、提供能力、依赖条件、公共接口、
信号、测试入口；需要实现细节时再进入源码与 README。

规范版本：1（2026-10-08 确立，health 为首个原型实现）。

---

## 1. 文件与分工

| 文件 | 角色 |
|---|---|
| `feature.yaml` | 机器可读的发现与契约索引（本规范定义） |
| `README.md` | 人类可读的复用说明 |
| 源码 / 场景 | 实现的 canonical 来源 |

规则：

- `feature.yaml` 是发现索引，不是第二份实现说明；不复制 README 的使用教程。
- `feature.yaml` 与 README.md / 源码冲突时，以 `feature.yaml` + 源码为准，并回写修正另一方。
- 接口签名必须与源码逐字一致（方法名、参数、类型）。

## 2. 必需字段

```yaml
id: health              # Feature id，必须等于目录名
version: 1              # 正整数；接口破坏性变更时递增
category: component     # 见 §3 枚举
summary: 一句话职责描述
provides:               # 能力标签（kebab/snake_case），供需求→能力匹配
  - health_state
requires: []            # 依赖的其它 Feature 的 provides 标签或 feature id
capabilities:           # 可选：本 Feature 需要的 Scene 能力（Phase 1.8.11，默认 []）
  required: []          # 能力名必须已在 capability_registry.py 登记（禁止推断）
interfaces:             # 公共接口（methods / signals / exports，可按需省略空类别）
  methods: []
  signals: []
  exports: []
ownership:              # 状态所有权（Round 8 原则：Feature 自己拥有状态）
  state: []             # 本 Feature 拥有的状态域
  rules: []             # 语义规则（守卫、钳制、幂等等）
relations:              # 关系元数据（Composition Planner 使用，全部指向 Feature id）
  works_with: []        # 显式协作机制（如 collect_pickup ↔ condition_gate 直连）
  commonly_used_with: [] # 常同层组合（如 health + contact_damage + chase_movement）
  conflicts: []         # 不能同时入同一实体的 Feature id（如 player_movement vs chase_movement）
  entity_roles: []      # 适合的实体角色（enemy/player/trap/world_item/level_geometry/logic 等）
  # requires: [能力标签] —— 关系型前置（可写在本节，也可写在顶层 requires）
composition:            # 组合入口
  entry_scene: Health.tscn
  usage: 一句话复用方式
  related_features: []  # 常与之组合的其它 Feature id
validation:             # 测试入口
  self_test: test_health.gd
  command: <可重复执行的无头验证命令>
  expectations: []
```

## 3. category 枚举（v1）

- `component`：组件节点，实例化进实体（health、stun、health_bar）
- `behavior`：行为控制（player_movement、chase_movement）
- `logic`：纯逻辑、无场景依赖（condition_gate、trigger_switch）
- `interactive`：Area2D 触发交互（contact_damage、heal_pickup、collect_pickup、openable_door）
- `world`：世界元素（moving_platform）

新增类别需先在本文件登记再使用。

## 4. provides / requires 约定

- `provides` 是能力标签，粒度为「一个可被需求命名的最小能力」（如 `death_event`）。
- `requires` 引用其它 Feature 的能力标签或 id；引用不存在的标签视为 schema 错误。
- 需求匹配方向：Agent 拿到需求关键词 → 对照各 Feature 的 provides/summary → 得出
  Reuse 清单；无法覆盖的部分即 Build 缺口（对接 feature-development.md §3）。

### capabilities（能力声明；可选字段，Phase 1.8.11）

有些 Feature 组合在生成实体场景时需要声明「这份计划需要哪些 Scene 能力」
（Node / Sprite / AnimatedSprite / Audio / Collision）。声明源头是本文件的
`capabilities.required`；链路：

```text
Features/<id>/feature.yaml  capabilities.required   Feature 声明（Source of Truth）
      ↓  feature_capabilities.py                   只读取，不判断
Scene Blueprint.capabilities.required              规整时汇总 + 去重（只传递）
      ↓  SceneIntentBuilder
Scene Intent.capabilities.required                 物化（默认 []）
      ↓  compatibility_gate                        能力可用性唯一判定者
PASS / BLOCKED（Unsupported capability: <name>，BLOCKED 即零 .tscn 产物）
```

规则：

- 字段名固定为 `capabilities.required`，默认 `[]`；未声明的存量 Feature 继续合法。
- **禁止自动推断**：不得按 Feature id / category / provides 标签猜测能力
  （不得因为名为 EnemyAttack 就补 `Script`）。没有声明就是没有需求。
- 能力名必须已在 `.ai/tools/scene_composer/capability_registry.py` 登记；
  预留 / 未知能力由 Compatibility Gate 判定为 BLOCKED（本文件不判断支持性）。
- 本字段是**需求**，不是能力地图：Binding / Scene 层不得裁剪，也不得替 Feature 声明。
- 与 Blueprint / CLI 显式声明取并集（需求只能叠加，不得互相削弱）。

#### Existing Feature capability adoption status（Phase 1.8.12）

Feature authors should explicitly declare required capabilities.
（能力声明是 Feature 作者的责任：新增 / 修改 Feature 时必须显式声明，不依赖推断。）

存量 Feature 已按「自身场景 + 自身 metadata」的证据完成迁移：

| Feature | 迁移前 | 迁移后 | 依据 |
|---|---|---|---|
| health, stun, condition_gate, health_bar, chase_movement | `[]` | `[Node]` | 组件以节点实例化进宿主场景 |
| contact_damage | `[]` | `[Node, Collision]` | `composition.usage` 要求宿主提供 CollisionShape2D |
| collect_pickup, heal_pickup | `[]` | `[Node, Collision]` | 自身场景含 PickupShape (CollisionShape2D) |
| moving_platform | `[]` | `[Node, Collision]` | 自身场景含 RideShape (CollisionShape2D) |
| openable_door, player_movement | `[]` | `[Node, Collision]` | 自身场景含 Collision (CollisionShape2D) |
| trigger_switch | `[]` | `[Node, Collision]` | 自身场景含 TriggerShape (CollisionShape2D) |

判定规则（由 `test_feature_capability_adoption.py` 审计强制）：

- 只声明已登记能力（`capability_registry.py`）；禁止根据 Feature 名 / category 推断。
- `Collision` 有且仅有在「自身场景含 CollisionShape2D」或「metadata 明确要求宿主提供」时声明。
- 无明确需求时保持 `[]`（不强行填充）。

## 5. 状态所有权（Round 8 原则）

`ownership.state` 必须列全本 Feature 拥有的状态域；Scene Glue 不拥有状态、不做仲裁。
若一个 feature.yaml 声明的状态域与另一个重叠，属于架构问题，须走 Architecture Decision，不得静默并存。

## 6. 迁移计划

存量 Feature 按下表逐步补齐 `feature.yaml`（不要求一次全部完成）：

- 已完成：health（原型）
- 待迁移：stun、health_bar、contact_damage、heal_pickup、collect_pickup、
  condition_gate、trigger_switch、openable_door、player_movement、chase_movement、moving_platform

新 Feature 自本规范发布起必须在 Finalization 时随目录交付 `feature.yaml`。

## 7. Feature Scene Template（template.yaml）

每个 Feature 目录可选提供 `template.yaml`，描述「如何被实例化进实体场景」
（Scene Composer 使用；入口场景的 Source of Truth 仍是本规范 `composition.entry_scene`，
template 与之保持一致）。格式：

```yaml
feature:
  id: health
scene:
  source: Health.tscn          # Feature 入口场景（相对 Feature 目录）
  root_type: CharacterBody2D   # 可选：宿主实体根必须的节点类型
attach:
  parent: root                 # 实例化位置（v1 仅支持 root）
  root_instance: true          # 可选：本 Feature 入口场景即宿主实体根（见下）
instance:                      # 可选：本组件入口场景自带的节点结构（能力契约证据）
  node_type: Area2D            # 必须等于入口场景真实根类型
  children:                    # 入口场景中真实存在的直接子节点类型
    - CollisionShape2D
validation:
  required_nodes:
    - Health                   # 生成的实体场景必须存在的节点名
interfaces:
  signals:                     # 生成的场景测试将逐一 has_signal 断言
    - health_changed
    - died
```

规则：

- 组件一律以 `instance=ExtResource` 实例化进实体场景，禁止复制 Feature 代码。
- 组合成员声明的 `root_type` 决定实体根类型（如 chase_movement → CharacterBody2D）。
- 无 template.yaml 的 Feature 视为未接入 Scene Composer。

### 7.1 `instance:` —— 组件实例证据（Phase 1.37）

能力契约（`capability_contract_validator.py`）只能看到 Scene Intent 里**已声明**的
节点结构。组件入口场景内部的节点（如 `Area2D` + `PickupShape`）若未声明，
依赖 `Collision` 等能力的组合会被误判为 `BLOCKED` —— 这是 Phase 1.36 评估 T1 的
首次失败原因（单 Feature 实体蓝图无法交付）。

规则：

- **凡是入口场景自带碰撞形状（`CollisionShape2D` / `CollisionPolygon2D`）的 Feature，
  必须**在 `template.yaml` 声明 `instance:`（覆盖该形状或其物理体根）；没有自带形状的
  Feature 不必声明——它的碰撞形状由宿主实体提供（例：`contact_damage` 的
  `ContactDamage.tscn` 只有 `Area2D`，接触形状写在实体上）。
  判定由场景推导而非硬编码名单（`test_feature_instance_evidence.py` E1）。
- `instance.node_type` 必须**等于**入口场景真实根类型；`instance.children` 必须是
  入口场景中真实存在的直接子节点类型（不得声明不存在的节点）。
- `instance:` 是**证据**，不是生成指令：Scene Builder 不消费它，生成的 `.tscn`
  不因此多出任何节点。
- 两条不变量由 `.ai/tools/scene_composer/tests/test_feature_instance_evidence.py`
  锁定（E1 完整性 / E2 真实性 / E3 fail-closed 未被削弱 / E4 端到端 / E5 输出不变）。

### 7.2 声明与真实场景的对账（Phase 1.38）

`instance:` 是**声明**，不是实例存在的证明。独立对账器会读取入口 `.tscn` 文本逐项核对：

| 结论 | 含义 | Validator |
| --- | --- | --- |
| `PASS` | 声明与真实场景一致 | 通过 |
| `MISMATCH` | 已证实矛盾（根类型 / 子节点缺失 / 层级错误 / 数量 / 重复路径） | **failure** |
| `INSUFFICIENT` | 静态无法确认（运行时创建 / 解析受限） | warning（需运行时证据） |
| `INVALID` | 声明非法、场景不可读或无根节点 | **failure** |
| `NOT_DECLARED` | 未声明 `instance:` | 通过（不强制迁移） |

动态创建的节点必须在声明里显式列名，不得靠「脚本存在」猜测：

```yaml
instance:
  node_type: Area2D
  children: [CollisionShape2D]      # 期望的直接子节点类型（数量按重复次数计）
  runtime_children: []              # 仅列出确实由脚本在运行时创建的子节点类型
```

- `runtime_children` 必须 ⊆ `children`；其中的类型静态找不到 → `INSUFFICIENT`；
  静态找到了 → 提示声明过期（warning）。
- 手动检查：`python .ai/tools/scene_composer/instance_evidence.py --all`；
  Validator 第 7 阶段为同一实现（`validator/check_instance_evidence.py`）。
- 契约详见 `.ai/context/scene_composer_schema.yaml#feature_instance_evidence_reconciliation`。
- 详见 `.ai/context/scene_schema.yaml`；校验由 check_scene_composition.py 承担。

### 7.3 运行时实例证据（Phase 1.39）

静态对账只能证明「`.tscn` 文本里写了这个节点」。要证明「加载后对象确实存在」，
在 `instance:` 下增加 `runtime:`（可选；不写 = 不要求运行时证据）：

```yaml
instance:
  node_type: Area2D
  children: [CollisionShape2D]
  runtime:
    when: after_load        # after_load | after_frames:<N> | after_action:<name>
    timeout_frames: 0       # 0 = 不轮询；>0 = 观察窗口帧数（最多 600）
    # scene: res://...      # 可选；缺省 = 模板入口场景
    # expectations:         # 可选；缺省由 node_type + children 推导
    #   - {path: PickupShape, type: CollisionShape2D, count: 1, runtime: true}
```

| 结论 | 含义 | 门禁 |
| --- | --- | --- |
| `PASS` | 真实加载后，目标在观察时机符合契约 | 通过 |
| `MISMATCH` | 加载失败 / 节点缺失 / 类型或数量不符 | **failure** |
| `INSUFFICIENT` | 采集失败、探针超时、需动作才能生成 | warning（`--require-runtime` 时 failure） |
| `INVALID` | `runtime:` 契约非法 | **failure** |
| `NOT_DECLARED` | 未声明 `runtime:` | 通过（不强制迁移） |

- 观察时机：`after_load` = `_ready` 执行完并稳定 2 帧；`after_frames:<N>` 再等 N 帧；
  `timeout_frames > 0` 时仅在尚未满足时继续轮询 —— 不会在动作/时机之前判缺失。
- `after_action:<name>` 一律 `INSUFFICIENT`：验证器**不**为了测试自动按键或改变游戏状态。
- 窗口超时只说明「窗口内未出现」（reason `missing_after_timeout`），不是「永不存在」。
- 四层证据互不顶替：文件可解析 / 资源可加载 / 节点存在 / 行为正确。本层只到第三层。
- 手动检查：`python .ai/tools/scene_composer/runtime_instance_evidence.py --all`；
  Validator 显式入口：`--instance-runtime <feature|all> [--require-runtime]`（默认不跑 Godot）。
- 契约详见 `.ai/context/scene_composer_schema.yaml#runtime_instance_evidence`。

### 7.4 行为证据（Phase 1.40 / 1.42）

结构证据证明「节点存在」，不证明「逻辑正确」。可选顶层 `behavior:` 声明真实动作与
后置断言；验证器在隔离场景副本中执行**受限注册动作**，再逐帧观测真实状态与信号。
Phase 1.42 起可以在动作序列中推进真实 physics 帧，并观测时间驱动的状态变化：

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
    window_frames: 12          # 动作后观测窗口（physics frames，1..600）

  # 时间驱动（Phase 1.42）：动作之间可以推进真实 physics 帧，再在检查点观测位移
  - id: travel
    actions:
      - {type: simulation.advance_frames, params: {frames: 60}}
    expected:
      - {check: node2d.displacement, target: ".", axis: x, min: 98.0, max: 102.0}
    window_frames: 1
```

- 动作与观测的唯一权威是 `.ai/context/behavior_protocol.yaml`（Phase 1.41 / 1.42）：
  动作 `door.set_open` / `health.take_damage` / `health.heal` / `physics.overlap` /
  `simulation.advance_frames` / `state.set_property` / `input.press` / `input.release`；
  观测 `door.is_open` / `health.current` / `health.is_dead` / `pickup.is_collected` /
  `node.freed` / `node.exists` / `trigger.is_triggered` / `node2d.position` /
  `node2d.displacement` / `signal`；信号白名单与可设置属性同在该文件。探针读取由协议
  生成的 `probes/behavior_manifest.json`，不再另存一份能力定义。
- 帧推进：`simulation.advance_frames{frames, phase}` 只支持 `phase: physics`
  （固定 delta、可重放）；`process` 帧在 headless 下不受节流、delta 非确定，因此
  未声明，使用即 `INVALID`。帧预算来自协议 `limits`：单次 ≤ 300，单契约
  （所有推进 + `window_frames`）≤ 600。帧推进是真实 `_physics_process` 时间，
  不调用私有回调，也不直接改写被测状态。
- 时间点观测：`node2d.position` 读 `global_position` 的单轴分量（绝对），
  `node2d.displacement` 读相对**动作前基线**的位移（基线由探针采集，不由预期反推）；
  布尔/整数观测用 `equals`，浮点观测用 `equals[+tolerance]` 或 `min`/`max` 区间。
- 受约束的状态设置：`state.set_property` 是**夹具**，只能写协议 `properties:`
  声明的导出属性（当前仅 `trigger_switch.trigger_mode`），必须带 `fixture` 语义、
  必须排在所有行为动作之前、每契约 ≤ 4 次，并且不能是唯一动作 —— 状态设置不得
  用于制造最终预期结果。记录 `before` / `value` / `after`，运行时校验目标脚本
  全局类名与属性 hint。
- 受控输入：`input.press` / `input.release` 走 `Input.action_press/release`，
  动作名必须存在于项目 InputMap（隔离副本会继承源 `project.godot` 的 `[input]`
  与 `[physics]` 段）；探针退出时释放本次按下的所有动作。
  注意 `action_press` 在一次输入刷新后生效，契约里应先推进 1 帧再观察位移。
- 行为级证据场景（Phase 1.43）：`behavior[].scene` 可选，只能是**同一 Feature 目录**
  内的相对 `.tscn`（绝对路径 / `res://` / `..` / 非 `.tscn` / 缺失文件 → `INVALID`）。
  缺省使用模板入口场景；它只选择证据场景（例如 `chase_movement` 需要一个静止目标），
  不改变组合入口，也不增加动作、观测或写入能力。
- 不接受任意方法名、表达式或 GDScript 注入；`physics.overlap` 生成真实
  `CharacterBody2D`（可带真实 `Health` 实例），由物理帧触发 `body_entered`，
  不直接调用私有回调。新增能力必须同时更新协议与探针实现映射，
  一致性测试会拒绝声明未实现 / 实现未声明的漂移。
- 时间驱动断言的判定仍由 Python 完成：Godot 只返回真实读数与帧号，
  `PASS` 需要动作真实执行 + 全部后置断言成立 + 重放关键结果一致；
  窗口耗尽只是 `MISMATCH`（看到了与契约冲突的读数），观测不可用才是
  `INSUFFICIENT`。不要要求跨重放的绝对帧号/耗时完全相同，只比较关键状态。
- `PASS` 要求动作**确实执行**且窗口内全部后置断言成立；动作没执行、前置不满足、
  采集失败或两次重放不一致都不得判 `PASS`。
- 前置条件不满足 → `INSUFFICIENT`（`precondition_unmet`），不擅自改状态凑结果。
- 未被本阶段接入的 Feature 不需要声明 `behavior:`（`NOT_DECLARED`，合法）。
- 独立入口：`python .ai/tools/scene_composer/feature_behavior_evidence.py --all`；
  默认重放 2 次（`--replay`），最终验收加 `--require-behavior`。静态 Validator 行为不变。
- 契约详见 `.ai/context/scene_composer_schema.yaml#feature_behavior_evidence`。

## 8. 与 Framework 的关系（预留）

- 本规范目前只约束 Features/ 目录内文件；Agent 通过索引（`.ai/context/feature_index.json`，
  由 build_feature_index.py 自动生成）发现能力。
- relations 字段由 Composition Planner（compose_features.py）与 Feature Graph 使用；
  conflicts/requires 由 Feature Metadata Validator 校验。
- Registry 只做索引，canonical metadata 仍在本文件约束的各 `feature.yaml`，
  与 skill-registry.yaml / skill-schema.yaml 的分工原则一致。
