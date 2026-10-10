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

---

## AD-006: Feature 引入机器可读元数据 feature.yaml，作为发现与契约索引

- 状态：accepted
- 日期：2026-10-08
- supersedes：null

### 决定

- 每个 Feature 目录增加 `feature.yaml`（格式由 `Features/FEATURE_SCHEMA.md` 定义），声明：身份（id/version/category）、summary、provides/requires 能力标签、interfaces（methods/signals/exports）、ownership（状态所有权）、composition（入口场景与组合方式）、validation（测试入口）。
- 分工：`feature.yaml` 是机器可读的发现与契约索引；README.md 是人类可读复用说明；源码/场景是实现的 canonical 来源。接口签名必须与源码逐字一致；冲突时以 feature.yaml + 源码为准并回写修正另一方。
- `ownership.state` 必须列全 Feature 拥有的状态域，落实 Round 8 结论（Feature 自己拥有状态，Scene Glue 不做仲裁）；状态域重叠须走 Architecture Decision，不得静默并存。
- health 为首个原型实现；存量 Feature 逐步迁移，新 Feature 在 Finalization 时必须随目录交付 feature.yaml。

### 原因

- 此前 Agent 理解一个 Feature 必须依次阅读 README.md → gdscript → test，发现成本高且不可机读；Feature Registry 路线图（P0-1）要求 Agent 能快速匹配「需求 → 已有能力」。
- 选择「每个 Feature 自带元数据」而非先建顶层聚合 Registry，是为了保持 canonical metadata 单一来源、避免 Registry 成为第二份元数据存储（与 skill-registry/skill-schema 的分工原则一致）；聚合索引留作后续加速层。

### 影响

- 新增 `Features/FEATURE_SCHEMA.md` 作为 feature.yaml 的唯一格式规范；新增 category 枚举（component/behavior/logic/interactive/world），新类别须先登记。
- feature-development.md §6 Finalization 实际新增一项交付物（feature.yaml）；Discovery 的能力发现优先读 feature.yaml。
- 后续可为 P0-1 第二步增加顶层聚合 Registry 与 Validator 一致性检查（预留，本次未实现）。

### 验证

- health/feature.yaml 的全部接口签名、导出属性、测试命令逐项对照 health.gd / test_health.gd 核实一致。
- Framework Validator PASS（0 errors / 0 warnings）。

---

## AD-007: Feature 关系元数据与组合规划器（Composition Planner）

- 状态：accepted
- 日期：2026-10-08
- supersedes：null

### 决定

- feature.yaml 增加 relations 节：works_with / commonly_used_with / conflicts（指向 Feature id）/ entity_roles（实体角色）；关系型前置 requires（能力标签）可写在 relations 或顶层。
- 新增 Feature Graph（`.ai/context/feature_graph.json`，由 build_feature_index.py 随索引自动生成，节点=Feature、边=协作关系）与 Composition Planner（compose_features.py）：需求文本 → Discovery → 关系图增强 → 评分（provides×5 + relation×3 + entity_role×2）→ 冲突过滤 → Entity Blueprint（entity.id/role/features/reason/validation.required_tests）。
- Entity Blueprint 是组合计划而非产物：实现仍按 AD-002 组件组合模式（实体场景只做组合），验证按 required_tests 回归。蓝图格式由 `.ai/context/composition_schema.yaml` 定义。
- Validator 新增：relations 引用检查（Unknown Feature relation）、组合 requires 满足检查（Composition incomplete）、conflicts 共存检查。
- 架构禁令：不建 Entity Manager / Gameplay Manager / Feature Controller；Entity 不拥有 Gameplay State，Scene 只负责组合。

### 原因

- Discovery 解决「找到能力」，但未回答「多个 Feature 如何组成实体」；组合知识此前只存在于 AD 与历史结论中，Agent 无法机读。
- 关系图让「Siege Gate 式组合（Health+ContactDamage+ChaseMovement+Stun）」等已验证模式成为可计算数据，组合从临场发挥变为可审查的蓝图。

### 影响

- 新 Feature 交付时需按 FEATURE_SCHEMA 填写 relations；冲突必须指向 Feature id（如 player_movement conflicts chase_movement）。
- 新增 feature-composition Skill（conditional，17 Skills）；feature_graph.json / feature_index.json 均为 Generated Data，feature.yaml 仍是唯一 Source of Truth。

### 验证

- test_composition.py 21 项断言全部 PASS（三用例组合、关系图边、缺前置/冲突/坏引用的 Validator 报告）。
- 全链：build_feature_index PASS（12 节点 27 边）、test_feature_pipeline PASS、Validator PASS（0 errors / 0 warnings）。

## AD-008: Scene Composer（场景自动组装层）

- 状态：accepted
- 日期：2026-10-09
- supersedes：null

### 决定

- 新增 Scene Composer 工具链（`.ai/tools/scene_composer/`）：Entity/Scene Blueprint → 依赖解析 → 生成 Scenes/<RootName>.tscn → 结构校验 → 可选生成 Tests/test_<scene_id>.gd。
- 每个 Feature 可选提供 template.yaml（Feature Scene Template）：声明入口场景、宿主根类型要求（root_type）、生成场景必需节点名（required_nodes）与待断言信号。格式规范见 FEATURE_SCHEMA §7 / `.ai/context/scene_schema.yaml`。
- 索引（feature_index.json）随 relations 下发 relations.requires，供组合满足性检查（build_feature_index.normalize_relations）。
- 场景生成硬约束：组件一律 instance=ExtResource 实例化（禁止复制 Feature 代码）；根节点不挂脚本（Scene 只负责组合，不拥有状态、不做仲裁）；requires 未满足时拒绝生成（Composition Error / Missing dependency）。
- Validator 新增 check_scene_composition.py：Feature 完整性（Missing Feature）、依赖、根类型（Invalid Root Node Type）、组合约束。
- 架构禁令沿用 AD-007：不建 Global/Entity/Feature Manager。

### 原因

- Composition 解决「组合哪些 Feature」，但实现仍靠手写场景，组合契约（组、命名、信号）易被遗漏；把蓝图落盘为标准 .tscn 并机器校验，实现「需求 → 能力发现 → 组合 → 场景 → 验证」完整闭环。

### 影响

- 新 Feature 需随目录交付 template.yaml 方可被 Scene Composer 组合；根类型要求写在 template 的 scene.root_type。
- 新增 scene-composer Skill（conditional，18 Skills）；Scenes/ 与 Tests/ 下生成物由工具产出，人工场景不受自动覆盖语义保护。

### 验证

- test_scene_composer.py 31 项断言 PASS（三用例：Enemy.tscn 组合、缺前置拒绝且不写文件、EnemyBasic.tscn 全链 + Validator PASS）。
- 端到端：compose_features → scene_composer --tests → check_scene_composition PASS；生成 Tests/test_enemy_basic.gd 经 Godot 无头运行 PASS（exit 0）。
- 全链：test_feature_pipeline PASS、test_composition PASS、Validator PASS（18 Skills / 12 metadata，0 errors / 0 warnings）。

## AD-009: Gameplay Loop Composer（需求到玩法循环层）

- 状态：accepted
- 日期：2026-10-10
- supersedes：null

### 决定

- 新增 Gameplay Planner 工具链（`.ai/tools/gameplay_planner/`：planner.py + requirement_parser.py + blueprint_generator.py）：自然语言需求 → Gameplay Blueprint（gameplay.id / entities(features+scene 复用) / systems / loop.start-cycle-end / validation）+ Entity Relationship Graph（`.ai/context/entity_graph.json`，nodes/edges[relation]，如 Enemy -[attack]-> Player）。蓝图格式由 `.ai/context/gameplay_schema.yaml` 定义。
- 新增 System Registry（`Systems/*/system.yaml`：id / provides / requires）描述跨实体流程（enemy_spawn、reward、door_control、platform_service）；System 只描述并校验能力契约，不实现为 Manager 类。
- Entity 表达「role + features(+可选 scene 复用)」，实体场景实物仍由 Scene Composer（AD-008）生成；Gameplay 层不生成实体，也不拥有实体状态。
- Validator 新增 check_gameplay.py：实体场景存在性（Missing Entity Scene）、Feature 满足性（Gameplay incomplete）、循环闭合（缺死亡/奖励时 Warning Gameplay loop incomplete）。
- 流程：planner 蓝图落盘 → 每实体 scene_composer 生成场景 → check_gameplay 校验 → 循环测试（Godot 无头）。
- 架构禁令沿 AD-007/008：禁止 God Object / GameManager / EntityManager / FeatureManager；Gameplay Logic 用独立 System 描述，Entity 只拥有自身状态。

### 原因

- Composition（AD-007）与 Scene Composer（AD-008）解决单实体生成，但未回答「多实体如何构成玩法循环」；实体关系（谁攻击谁）与跨实体流程（生成/奖励）此前无机读载体。

### 影响

- 新增 gameplay-planner Skill（conditional）；entity_graph.json 为 Generated Data。
- Scene Builder 实例机制增强：root.scene 复用 Feature 场景时 root 属性/组覆写写在 [node] header 同行（Godot 不读 instance 行后单独的属性行）；节点允许 parent 指向组件节点（嵌套 shape）；Validator 校验 parent 路径必须指向场景内已声明节点。
- run_tests.py 子进程输出按 utf-8 + errors=replace 解码（GBK 环境下 Godot 输出可致 UnicodeDecodeError 崩溃）。

### 验证

- test_gameplay_planner.py PASS（蓝图生成/实体图/check_gameplay 三类错误语义）；test_scene_composer.py PASS。
- 端到端：planner "create enemy survival game" 落盘 survival_game.yaml（enemy/player 实体 + enemy_spawn/reward 系统 + 循环）→ enemy 场景 Blueprint 经 scene_composer 重建 Scenes/Enemy.tscn（与 HEAD 版结构等价：chase 根 + ContactShape + Visual + HealthBar，实例化根覆写组与 speed）→ check_gameplay PASS。
- SurvivalArena 生存循环 Godot 集成测试 PASS（伤害链路/拾取恢复/死亡移除/重开/胜利路径）。
- 全量 Godot 回归 30/30 PASS；Validator PASS。
