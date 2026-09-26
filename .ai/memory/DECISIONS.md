# Decisions

本文件是本项目 Architecture Decision 的唯一物理归宿。

格式：

日期：

状态：

决定：

原因：

影响：

supersedes：

---

## AD-001: 建立顶层 `Features/` 目录，可复用 Feature 自包含管理

- 状态：accepted
- 日期：2026-09-25
- supersedes：null

### 决定

- 新增顶层 `Features/` 目录（PascalCase，符合 folder-structure 规则），每个 Feature 一个子目录，场景、脚本、测试自包含。
- 首个 Feature：`Features/player_movement/`（`Player.tscn` + `player_controller.gd` + `test_player_movement.gd` + `README.md`）。
- 主场景 `Scenes/main.tscn` 保留在 `Scenes/`：它是游戏侧组合层，负责实例化 Feature，不属于可复用单元。

### 原因

- 已验证的移动功能需要沉淀为可复用单元；Feature 内聚（场景 + 逻辑 + 验证 + 说明）使整个目录可被其他场景或项目直接复用。
- godot-project-architecture 的架构模型中 Feature 是独立组织层级，不应散落在分类目录（Scripts/、Scenes/）中。

### 影响

- 后续新 Feature 放入 `Features/<feature_name>/`。
- 引用 Feature 内资源使用 `res://Features/<feature_name>/...` 路径。
- 同步更新了 development-standard 的 folder-structure.md，补充 `Features/` 目录约定。

### 验证

- 迁移后资源导入、运行时四向移动测试、主场景启动全部通过，游戏功能不变。

---

## AD-002: 实体能力以组件节点 Feature 复用，实体场景只做组合

- 状态：accepted
- 日期：2026-09-25
- supersedes：null

### 决定

- 跨实体能力（首个：health）实现为独立组件 Feature（`Features/<name>/`），根节点为普通 Node，通过信号对外暴露事件，不依赖宿主节点类型。
- 实体场景（`Scenes/Player.tscn`、`Player2.tscn`）通过实例化 Feature 场景组合能力，差异用导出属性覆写表达；实体不继承、不复制能力实现。

### 原因

- 移动天然属于 CharacterBody2D，而生命值与节点类型正交（敌人、可破坏物也需要）；若绑死 CharacterBody2D，复用面被锁死在角色类节点。
- 信号是 Godot 的解耦事件接口，满足「死亡时其他逻辑可响应」且组件无需知道订阅方。

### 影响

- 后续实体能力优先按「组件 Feature + 场景组合」实现，不建立实体基类继承链。
- 能力事件一律通过信号暴露；宿主死亡后的表现由订阅方决定。

### 验证

- Health 组件验证、Player/Player2 双角色集成验证、移动回归、主场景启动全部通过。

---

## AD-003: 场景级组合胶水在出现第二个消费者之前不提升为 Feature

- 状态：accepted
- 日期：2026-09-25
- supersedes：null

### 决定

- 场景级组合/胶水逻辑（首个案例：Damage Interaction 的攻击触发器 `Scenes/attack_trigger.gd`）在出现真实的第二个消费者之前保持为游戏侧实现，不提升为 Feature。
- 判定为「暂不 Feature 化」时，必须同时记录其提升条件（例如：出现多攻击者、多场景复用等真实复用需求）。
- Feature Development Workflow 的 Discovery 阶段包含「待再评估的胶水」检查项，每次发现时对提升条件做再评估。

### 原因

- 本轮 Damage Interaction 任务实际采用并验证了这一判断：触发动作→伤害路由是游戏侧组合（谁打谁、用什么键是场景设计），受击/死亡规则已由 health Feature 封装；为一键交互新建攻击 Feature 属过度抽象。
- 现在将该判断正式持久化为项目 Architecture Decision，使后续 Discovery 能基于记录再评估提升时机，而不是依赖会话记忆。

### 影响

- 场景级组合逻辑的「暂不提升」判定必须附带提升条件并持久化。
- Discovery 检查项引用本决策；满足提升条件时按 Feature Development Workflow 的 Build 分支执行提升。

### 验证

- 伤害交互验证（真实 main.tscn）一次通过；全量回归（Health/移动/集成）与主场景启动全部通过，胶水方案未破坏任何既有能力。

---

## AD-004: 与 Health 交互的跨实体组件使用「目标组 + Health 子节点命名」组合契约

- 状态：accepted
- 日期：2026-09-26
- supersedes：null

### 决定

- 新增 4 个组件 Feature：`chase_movement`（CharacterBody2D 根脚本，朝 `target_path` 移动）、`contact_damage`（Area2D，重叠节拍伤害）、`heal_pickup`（Area2D，接触恢复后自移除）、`health_bar`（Node2D 显示，纯只读）。
- 与 Health 独立组件交互的组件不反向依赖实体类型：通过「目标组名（默认 `players`）+ 实体 Health 子节点统一命名 `Health`」的组合契约解耦；实体场景通过组合（groups 覆写、组件实例化）满足契约，不满足时组件静默跳过、不报错。
- 显示类组件（health_bar）与行为组件同层组合；player_movement 等既有 Feature 不因显示需求引入依赖，玩家血条在场景层挂载。
- 场景编排（生成、计时、胜负、重开）保持游戏侧胶水（`Scenes/survival_arena.gd`），沿用 AD-003：其提升条件记录为「出现第二个玩法场景复用同一编排需求」。

### 原因

- Survival Arena 需要追击、接触伤害、恢复、显示等与 Health 相关的跨实体能力；若各自依赖具体实体脚本将形成双向依赖并锁死复用面。
- 组 + 约定命名是 Godot 场景组合的原生解耦方式：组件可在不依赖游戏侧场景的前提下完成自包含验证（contact_damage / heal_pickup 测试均以本地构建目标通过）。

### 影响

- 后续与 Health 交互的组件（毒圈、吸血、护盾等）沿用同一契约，不新建第二套目标解析机制。
- 敌人类游戏实体 = Feature 组件的场景组合（见 `Scenes/Enemy.tscn`）；实体场景负责满足组合契约（加入组、Health 命名）。
- Health 组件新增 `heal()` 接口（上限钳制），未改变既有伤害/死亡语义，回归验证通过。

### 验证

- 4 个新 Feature 自身验证 + health 扩展回归（5/5）；SurvivalArena 集成验证（真实场景全链路）；全量回归 9/9；主场景启动无错误；Framework Validator PASS（0 errors / 0 warnings）。

---

## AD-005: 布尔状态机关用「同签名 (bool) 契约 + 场景连接」组合；AND 聚合为独立逻辑 Feature

- 状态：accepted
- 日期：2026-09-27
- supersedes：null

### 决定

- 状态机关类组件遵循统一布尔契约：触发源广播 `activated(triggered: bool)`，目标暴露 `set_open(bool)` / `set_condition(value, id)` 形式的方法，关系一律由场景 `[connection]` 数据表达，不写胶水脚本、不依赖节点名。
- 多条件 AND 聚合沉淀为独立逻辑 Feature `condition_gate`（Node 根，纯状态，无场景依赖）；OR 关系不新建能力（多个信号连同一目标即天然 OR）。
- 目标方法 API 的参数顺序遵循「信号参数在前、连接绑定（binds）在后」，使 tscn connection 可直连（如 `activated(bool)` 直连 `set_condition(value, id)` + `binds=["id"]`）。
- 一次性玩法逻辑（胜利反馈、场景专属重开轮询）保持场景胶水，不 Feature 化（沿用 AD-003）。

### 原因

- Escape Room 验证任务发现能力缺口：既有机关能力只有「一对一/多对一的 OR 传递」，缺少「N 个条件共同满足」的 AND 聚合；该聚合是纯逻辑、与具体实体无关，具备独立复用价值（解谜门、成就系统、多钥开门）。
- Manager 型胶水（如 EscapeRoomManager）会把关系硬编码进代码，丧失场景数据的可组合性；信号直连已验证可表达全部当前需求。

### 影响

- 后续布尔状态机关（按钮、拉杆、闸门、平台）优先套用「同签名契约 + 场景连接」；新交互类型先检查是否能用 condition_gate 或现有契约表达。
- 需要动态重评（条件可失效失效）或 OR/NOT 等其它聚合时，扩展 condition_gate 而非新建第二套逻辑门。
- 场景连接的 binds 参数顺序约定适用于所有未来被场景直连的目标 API。

### 验证

- condition_gate 自身验证（聚合/数量约束/回落/幂等/reset/多实例）通过；EscapeRoom 集成验证（真实物理阻挡与穿出、双条件、状态保持、重置）通过；全量回归 17/17；双场景启动无错误；Validator PASS。
