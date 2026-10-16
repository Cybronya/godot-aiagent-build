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
- 详见 `.ai/context/scene_schema.yaml`；校验由 check_scene_composition.py 承担。

## 8. 与 Framework 的关系（预留）

- 本规范目前只约束 Features/ 目录内文件；Agent 通过索引（`.ai/context/feature_index.json`，
  由 build_feature_index.py 自动生成）发现能力。
- relations 字段由 Composition Planner（compose_features.py）与 Feature Graph 使用；
  conflicts/requires 由 Feature Metadata Validator 校验。
- Registry 只做索引，canonical metadata 仍在本文件约束的各 `feature.yaml`，
  与 skill-registry.yaml / skill-schema.yaml 的分工原则一致。
