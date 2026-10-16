# Skill Identity

## Skill ID

scene-composer

## Skill Name

Scene Composer

## Version

1.0

## Category

systems

# Registry Metadata

本章节是本 Skill 的 Canonical Metadata。
Registry 仅索引本 Skill，不重复维护这些字段。

## Load Policy

conditional

## Dependencies

### Required

[]

### Related

- asset-discovery

Reason: asset-discovery produces Asset Binding consumed by Scene Composer
（asset-discovery 产出 Scene Composer 消费的 Asset Binding）。

## Ownership

负责「Entity Blueprint → Godot Scene (.tscn)」的自动组装（场景生成、依赖解析、
结构校验、测试生成）；不负责 Feature 的实现、组合规划与测试执行。

# Description

负责根据 Scene Blueprint / Entity Blueprint 自动生成 Godot Scene：加载
Feature Scene Template（Features/*/template.yaml）、解析组合依赖、生成
Scenes/<RootName>.tscn、运行结构校验，并可选生成场景回归测试。
同时消费 **Asset Binding Document**（`.ai/context/asset_binding_schema.yaml`）
把绑定实例化为资源节点（AnimatedSprite2D / Sprite2D / AudioStreamPlayer），
产出 Scene Intent 计划（边界契约：`.ai/context/scene_composer_schema.yaml`）。
工具：`.ai/tools/scene_composer/scene_composer.py`、
`.ai/tools/scene_composer/asset_nodes.py`（Asset Binding → 资源节点）、
`.ai/tools/validator/check_scene_composition.py`、
`.ai/tools/test_generator/generate_scene_test.py`。

# Purpose

让「实体实现」从手写场景变成可验证的自动组装：组合计划落盘为标准 .tscn，
组件一律实例化 Feature 入口场景，Scene 不引入任何自有逻辑。
资源侧同理：Binding 是唯一资源事实来源，Scene Composer 只消费、不重选、不推断。

# Responsibility

## 负责

- 运行 Scene Composer，把 Blueprint 生成 Scenes/<RootName>.tscn。
- 生成前过 Compatibility Gate（Scene Intent 能力闸门）：BLOCKED 即中止，不得写半成品。
- 生成前过 **Capability Contract Validation**（Phase 1.8.13；Gate 之后、Builder 之前）：
  Gate 判定「能力**是否被支持**（availability）」，本层判定「当前生成计划**是否满足**能力
  要求（fulfillment）」——Required Capability + Scene Plan Evidence → PASS / BLOCKED。
  证据 = Scene Plan（components[].instance / root / nodes[] / components[] / resources[]；
  **不解析 .tscn**）；BLOCKED 同样零产物，failures 前缀 `Capability Contract:`。
- 维护 **Component Instance Materialization**（Component instances provide evidence for
  capability contracts.）：组件可选声明 `components[].instance`（node_type / children /
  resources / parent），经 Feature Scene Template（`instance:`）或 Blueprint
  （`components[].instance`）传递，由 `component_instance_resolver.py` 解析为实例计划，
  作为能力契约的**优先证据**（声明式，**不驱动生成**）；未识别 node_type → BLOCKED
  （零产物）。存量 Feature 未声明 → 行为逐字节不变。
- 生成后过 **Artifact Evidence Verification**（Phase 1.8.15/1.8.16；.tscn **写盘之后**）：
  核验「声明 = 计划 = 生成物」——`components[].instance` 声明的结构（类型 / 挂载关系）
  必须能在产物里找到。证据 = **Host Artifact + External Component Artifact**：
  宿主 .tscn 的 `instance=ExtResource(...)` 会被 `external_artifact_resolver.py` 递归解析到
  `res://Features/<id>/<Scene>.tscn`（纯静态文本；不启动 Godot、不加载 PackedScene；
  循环引用 → `External artifact recursion detected`）。失败 → ok=false、failures 前缀
  `Artifact Evidence: `，**保留生成物**供诊断（不删除、不自动修复）；无声明 → 不核验（旧行为）。
- 维护 **Component Instance Ownership**（Phase 1.8.17；Which instance fulfils the declaration）：
  `component_instance_ownership.py` 把每条 `components[].instance` 声明映射到**唯一的产物实例节点**
  （owners[]：component → artifact_path / node_path / confidence）。来源只有三条，按优先级：
  `instance.id`（声明的节点名 / 节点全路径）→ `ext_resource` 路径的 Features/<id>/ 段落 →
  节点 `instance=ExtResource()`。无法唯一确定（id 命中 0 个或 ≥2 个、无 id 但候选 ≥2 个）→
  BLOCKED `Component ownership unresolved: <component>`（禁止按名字 / 关键词 / Registry 猜测）。
  归属成功后，Artifact Evidence 只在该归属的证据池（owner 产物 + 其可达闭包 → 宿主）内核对，
  不借用其它组件的产物；归属层先于结构核对，失败即停（生成物保留供诊断）。
- 维护 **Capability Metadata Layer**（Scene Intent declares required execution capabilities.
  Compatibility Gate validates capability availability.）：Scene Intent 用 `capabilities.required`
  声明所需能力；能力词汇的唯一事实源是 `capability_registry.py`（supported / reserved），
  闸门据此判定，未知 / 预留能力 → BLOCKED（不写文件）。
- 维护 **Capability Producer**（Feature Registry is the source of capability requirements.）：
  能力需求由成员 Feature 的 `feature.yaml → capabilities.required` 声明（读取入口
  `feature_capabilities.py`：只读、不判断、禁止按名字 / category 推断），随组合写入
  Scene Blueprint，再由 Scene Intent 物化（`capabilities.required`）；Feature 未声明 → `[]`
  （存量 Feature 继续合法），BluePrint / CLI 显式声明与 Feature 声明取并集。
- 生成前用 dependency_resolver 拦截缺失前置（Composition Error / Missing dependency）。
- 生成后用 check_scene_composition 校验（Feature 完整性 / 依赖 / 根类型 / 组合约束）。
- 用 test_generator 生成 Tests/test_<scene_id>.gd 并纳入回归。

## Component Ownership Layer（四层职责，Phase 1.8.17）

组件链路从上到下四层，各答一个问题，**职责不得合并**：

| 层 | 回答 | 事实源 | 产物 |
| --- | --- | --- | --- |
| Capability | 「需要什么」 | `feature.yaml → capabilities.required` / `capability_registry.py` | `capabilities.required` |
| Instance | 「声明什么」 | `components[].instance`（`component_instance_resolver.py`） | 实例计划（node_type / children / id） |
| Ownership | 「哪个实例」 | `component_instance_ownership.py` | `owners[]`（component → artifact_path / node_path / confidence） |
| Artifact Evidence | 「产物是否兑现」 | `artifact_evidence_validator.py` + `external_artifact_resolver.py` | `ArtifactEvidenceReport`（status / errors / checked_*） |

- Capability 与 Instance 发生在 **Builder 之前**（只看计划）；Ownership 与 Artifact Evidence 发生在**写盘之后**（只看静态文本）。
- Ownership 不做能力判断、不做结构核验、不读文件；Artifact Evidence 不猜归属，只消费 owners[]。
- 旧 Intent（无 `instance` / 无 `id`）全程合法：归属层返回空 owners，Artifact Evidence 保持旧行为。

## 不负责

- 不创建 Global Manager / Entity Manager（架构禁令）。
- 不修改 Feature 内部实现；Feature 缺口走 feature-development.md Build 分支。
- 不执行测试（由 godot-debug-testing / run_tests.py 管辖）。

# Trigger Conditions

- 已有 Entity Blueprint（compose_features.py 产出）需要落盘为场景。
- 已有 Scene Blueprint（手写或推导）需要生成/再生成 .tscn。
- 场景生成后的组合合法性与回归测试需要检查。

# Input Contract

输入有两类，其中 **Asset Binding Document 是资源事实来源**：

1. Entity Blueprint（entity:/features:，自动推导）或 Scene Blueprint
   （scene:/root:/components:/nodes:/validation:），格式见
   `.ai/context/scene_schema.yaml`。
2. Asset Binding Document（`.ai/context/asset_bindings/<id>.yaml`，
   契约 `.ai/context/asset_binding_schema.yaml`，schema_version=2）：
   资源角色 → 资源 → 场景资源节点的权威解析结果，含 resolved_from /
   compatibility / confidence 等**只读来源字段**。

- 组合成员必须存在于 feature_index.json。
- Binding 的消费字段与边界（输入子集、只读来源字段、缺失降级为警告）
  见 `.ai/context/scene_composer_schema.yaml`（Phase 1.8.3 Contract Freeze）。
- Binding 尚不存在时，先经 asset-discovery Skill 产出 Binding；
  不在场景层自行解析、筛选或补选资源。

# Workflow

冻结流程（Scene Composer 只消费 Binding）：

```text
Entity Requirement
      ↓
Feature Discovery（asset-discovery Skill）
      ↓
Explicit Asset Binding（bind_assets → Asset Binding Document）
      ↓
Scene Composer（消费 Binding → Scene Intent）
      ↓
Scene Intent（计划：root / components / nodes / resources）
      ↓
Scene Builder（scene_builder）
      ↓
.tscn generation（Scenes/<RootName>.tscn）
```

工具内部流程：

```text
Entity Blueprint
      ↓
Feature Template Lookup（Features/*/template.yaml）
      ↓
Capability Producer（Features/<id>/feature.yaml → capabilities.required；
                    只读取、不判断；无声明 → []）
      ↓
Dependency Resolve（requires 硬性拦截）
      ↓
Scene Intent（SceneIntentBuilder：计划层，Scene 层唯一生成输入）
  + capabilities.required（能力声明：需要什么能力，默认 []）
  + components[].instance（组件实例计划：声明式证据，可选；不驱动生成）
      ↓
Compatibility Gate（compatibility_gate；能力词汇 = capability_registry：
                    supported → 放行，reserved / unknown → 零产物中止）
      ↓
Capability Contract Validation（capability_contract_validator；contract 表 =
                    capability_contracts；证据优先级：组件实例
                    （component_instance_resolver：node_type / children）→ 节点 /
                    物理体等价表达；未识别实例或证据不足 → 零产物中止，
                    不降级放行）
      ↓
Scene Generation（scene_builder；只消费 Scene Intent → Scenes/<RootName>.tscn）
      ↓
Validation（scene_validator；同样只消费 Scene Intent，规则与迁移前一致）
      ↓
Artifact Evidence Verification（artifact_evidence_validator；写盘**之后**静态核验：
                    Component Instance Ownership（component_instance_ownership：
                    components[].instance(.id) → 实例节点 → 证据池）
                    → 宿主 .tscn + 经 external_artifact_resolver 递归解析的组件入口场景
                    = Complete Evidence；missing / unresolved → 保留产物 + ok=false，不修复）
      ↓
Test Generation（generate_scene_test；只消费 Scene Intent → Tests/test_<scene_id>.gd）
      ↓
独立复核入口：check_scene_composition（原始 Blueprint → intent_from_blueprint
              → validate_scene(Scene Intent)）
```

标准流程：

1. 由 feature-composition 产出 Entity Blueprint（或直接写 Scene Blueprint）。
2. 经 asset-discovery 产出 / 定位 Asset Binding Document（第 11 节路由）。
3. 运行 `python .ai/tools/scene_composer/scene_composer.py <blueprint.yaml>
   --bindings .ai/context/asset_bindings/<id>.yaml --tests`
   （或 `--bind-assets` 由 Asset Registry 现解析；两者都以 Binding 为准）。
4. 生成失败（依赖缺失/未知 Feature）→ 回到组合层解决，不得在场景层补胶水。
5. Validation PASS 后运行 `python .ai/tools/run_tests.py Tests/test_<scene_id>` 回归。

# Output Contract

- **Scene Intent Document**（正式输出计划层）：节点层级 / 组件位置 / 资源连接计划 /
  节点属性 / 组 / shape；字段与 CURRENT|PLANNED 状态见
  `.ai/context/scene_composer_schema.yaml` 的 `scene_intent` 段
  （当前为内存对象，**不落盘**；provenance / scripts / animations 为 PLANNED）。
- 组件实例计划（`components[].instance`，Phase 1.8.14）：可选的声明式证据（node_type /
  children / resources / parent），供能力契约核对；**不改变 .tscn 输出**（Builder 不读该字段）。
- Artifact Evidence 结论（`artifact_evidence`，Phase 1.8.15/1.8.16/1.8.17）：`{status, errors,
  checked_instances, checked_external_artifacts, checked_ownership}`——产物核验结果
  （第 4 键 1.8.16 / 第 5 键 1.8.17 追加，旧三键语义不变；checked_ownership = 组件 →
  artifact_path / node_path / confidence）；失败时生成物**保留**并随信封返回 scene_path 供诊断。
- Scenes/<RootName>.tscn（根节点 + 组件实例 + 额外结构节点）——由 scene_builder
  **仅消费 Scene Intent** 生成（Phase 1.8.7 输入边界；传规整内部 dict 会报错，
  不存在兼容转换路径）。
- Validation 结论（PASS / Missing Feature / Composition Error / Invalid Root Node Type）。
- Tests/test_<scene_id>.gd（--tests 时）。

# Rules

必须：

- 优先使用 Feature Scene Template（组件 = 实例化 Feature 入口场景）。
- 生成前后都过 Validator：依赖解析拦截 + 结构校验兜底。
- 根节点类型满足成员 template 的 root_type 要求（如 chase_movement → CharacterBody2D）。
- 生成链路上，Scene Intent 是 Scene Builder / scene_validator / test_generator 的
  **唯一输入**（组件节点名 / 场景路径由 Feature Scene Template 在构建期派生，
  不写入契约字段）；旧规整内部 dict 传入即报错，不存在双入口。
- Blueprint → Scene Intent 的转换只发生在生产者入口（compose / intent_from_blueprint）；
  校验与测试不再自行重读蓝图字段。
- 生成前必须过 Compatibility Gate（只在 `scene_builder` 之前；BLOCKED 时**不得**产生
  任何 .tscn）。闸门只判断能力是否被支持，不重复校验器 / 生成器的职责。
- 能力声明必须可被计划证据验证（Capability Contract Validation）：新能力进入词表时必须
  同时登记契约（`capability_contracts.py`），否则该能力只能声明、无法履约。
  契约表不判断支持性，闸门不改判断逻辑——两层职责不得合并。
- 组件自带节点结构必须以 `components[].instance` 声明（Feature `template.yaml` 的
  `instance:` 或 Blueprint `components[].instance`）；声明是**证据**而非生成指令：
  禁止按 component id / 名字 / 目录推断实例，未识别 node_type → Contract BLOCKED
  （词表唯一事实源 `component_instance_resolver.py`；不读引擎、不解析 .tscn）。
- 声明必须能被**产物**确认：`components[].instance` 描述的节点类型 / 挂载关系必须出现在宿主
  .tscn 或（1.8.16 起）ExtResource 指向的组件入口场景里（否则 Artifact Evidence BLOCKED）。
  同一产物内严格核对挂载关系（含逐层后代）；跨产物组合（组件场景提供声明节点、宿主提供子节点）
  只核对存在性。核验只看静态文本，不启动 Godot；外部产物缺失或成环即阻断（证据链不完整不放行）。
- 声明必须先有**唯一归属**（Component Instance Ownership）：`components[].instance.id`（节点名 /
  节点全路径）→ `ext_resource` 路径 → 节点 `instance=ExtResource()`，三者之外一律禁止；
  无法唯一确定即 `Component ownership unresolved: <component>`（BLOCKED，不猜测、不降级）。
  同一组件多实例必须由作者显式 `id` 区分；归属之外产物的结构不得用作该声明的证据。
- 能力声明只能来自 Scene Intent 的 `capabilities.required`（Scene Intent declares required
  execution capabilities）；不得在闸门内反向猜测组件 / Feature id 来推断能力，
  也不得新增第二份能力清单。
- 能力需求只在 Feature 侧声明（Feature Registry is the source of capability requirements.）：
  Binding / Scene 层只传递与去重，不得替 Feature 声明、不得裁剪、也不得推断。

**Feature capability declaration（声明示例）**

```yaml
# Features/<id>/feature.yaml
capabilities:            # 本 Feature 需要的 Scene 能力（默认 []；词汇：capability_registry.py）
  required:
    - Node               # 组件以节点实例化进宿主场景
    - Collision          # 自身场景含 CollisionShape2D，或 metadata 要求宿主提供
```

- 只声明已登记能力（`Node` / `Sprite` / `AnimatedSprite` / `Audio` / `Collision`）；
  预留名（`Script` / `Animation` / … ）→ Gate BLOCKED。
- 命名依据只能是 Feature 自身场景 / metadata 的证据；禁止按 Feature 名或 category 推断。
- 存量 Feature 的迁移结果见 `Features/FEATURE_SCHEMA.md`（Phase 1.8.12 adoption status）。

禁止：

- 复制 Feature 代码进实体场景（只允许 instance=ExtResource 组合）。
- 给根节点挂脚本——Scene 只负责组合，不拥有状态、不做仲裁。
- 创建 Global Manager / Entity Manager / Feature Manager / Global Singleton。

## MUST NOT（Binding 边界，Phase 1.8.4）

Scene Composer MUST NOT:

- query assets（不调用 query_assets、不扫描资源目录、不建第二套 Asset Resolution）
- rank candidates（不对候选打分 / 排序）
- select assets（不做 top1、不做补选）
- modify binding（不覆盖与不改写 asset / role / path / compatibility /
  resolved_from / confidence）
- infer missing assets（missing 只降级为警告，禁止编造 asset id 或 res:// 路径）
- create global manager（禁止任何全局 / 实体 / Feature 管理器）
- attach script to root（根节点禁止挂脚本）

# Validation

## Validation Method

- scene_composer.py 可重复运行，同一输入产出一致 .tscn。
- check_scene_composition.py 独立复核生成物。
- 生成的 test_<scene_id>.gd 经 run_tests.py 回归。

## Success Criteria

- Blueprint 每个成员在场景中有对应实例节点；信号齐全。
- Validator 零失败；场景测试 PASS。

## Status Update

- PASS：场景生成且校验通过。
- WARNING：结构提示（根类型满足成员但非首选）。
- FAIL：依赖缺失、未知 Feature 或结构违规（未写文件或写后校验失败）。

# References

- .ai/context/CONTRACT_INDEX.yaml —— 契约总目录（`scene_composition` 条目：
  Binding 输入 / Scene Intent 输出）
- .ai/context/scene_composer_schema.yaml —— Binding → Scene Intent 边界契约
  （Phase 1.8.3 Contract Freeze 六原则；输入 Binding / 输出计划，不含运行时生成；
  Phase 1.8.7 记录消费边界 scene_intent.consumers：Builder 只吃 Scene Intent）
- .ai/context/asset_binding_schema.yaml —— Asset Binding 契约
  （Scene Composer 的资源事实来源，version 2）
- .ai/context/scene_schema.yaml —— Scene Blueprint / template.yaml 格式
- .ai/context/composition_schema.yaml —— Entity Blueprint 格式（上游）
- .ai/tools/scene_composer/ —— composer / builder / resolver / validator
- .ai/tools/scene_composer/capability_registry.py —— 能力词汇唯一事实源（supported /
  reserved；Phase 1.8.10）——修改必须同步契约 scene_intent.capabilities 与 compatibility_gate
- .ai/tools/scene_composer/component_instance_resolver.py —— 组件实例计划解析（Phase 1.8.14：
  `components[].instance` → 实例计划 = 能力契约的优先证据；静态节点类型词表，未识别即 BLOCKED）
- .ai/tools/scene_composer/artifact_evidence_validator.py —— 生成物证据核验（Phase 1.8.15：
  声明 = 计划 = 生成物；只读静态解析 .tscn 的 name / type / parent / ExtResource）
- .ai/tools/scene_composer/external_artifact_resolver.py —— 外部组件场景解析（Phase 1.8.16：
  ExtResource 递归静态解析 + 循环检测；res://Features/**/*.tscn → 文件系统，缺失即 BLOCKED；
  1.8.17 额外返回引用图 {res://: [直接引用]}）
- .ai/tools/scene_composer/component_instance_ownership.py —— 实例归属解析（Phase 1.8.17：
  `components[].instance.id` → ext_resource → 实例节点唯一映射；二义即 BLOCKED，不改生成）
- .ai/tools/scene_composer/compatibility_gate.py —— 生成前能力闸门（Scene Intent →
  CompatibilityReport：PASS / BLOCKED；能力声明优先，其余检查见契约 compatibility_gate 段）
- .ai/tools/validator/check_scene_composition.py —— 场景组合校验（CLI 入口收原始 Blueprint，
  内部构造成 Scene Intent 后交给 scene_validator）
- .ai/tools/test_generator/generate_scene_test.py —— 测试生成
- .ai/memory/DECISIONS.md —— AD-002（组件组合）/ AD-008（Scene Composer）

# Failure Handling

- Missing dependency → 回到组合层补成员（如 contact_damage 需 health），
  不得在场景层绕过。
- Unknown Feature → 成员 id 错误或 Feature 未建；先 Discovery/Build。
- Invalid Root Node Type → 调整 blueprint root.type 或成员组合。
- Feature 无 template.yaml → 视为未接入 Scene Composer；先补模板再组合。

# Permission Model

允许执行：

- 运行 scene_composer.py / check_scene_composition.py / generate_scene_test.py。
- 写入 Scenes/ 与 Tests/（仅生成物）。

需要确认：

- 覆写已有同名 .tscn（人工创建的场景不被自动覆盖语义保护，需人工确认）。
- 新建 Feature（走 feature-development.md Build 分支）。

# Notes

- 根节点不挂脚本是本 Skill 的硬约束；实体行为完全由组件脚本承担。
- 敌人标准组合（Health + ContactDamage + ChaseMovement [+ Stun]）经
  scene_composer 全链验证，见 .ai/tools/scene_composer/tests/。
