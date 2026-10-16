# AI_ENTRY

文档版本：6.0

## 项目级 Agent 入口协议

`AI_ENTRY.md` 是项目根目录的 Agent 入口协议与导航文件。

它负责告诉 Agent：

- Framework 从哪里进入
- 配置系统如何解析
- Skill 如何发现、加载和协作
- Validator 何时执行

> `AI_ENTRY.md` 本身不是机器可解析的 Framework 配置。  
> 唯一的 Framework Machine Entry 是 `.ai/config/agent.yaml`。

## 1. Framework Entry

Agent 进入项目后：

1. 读取 `AI_ENTRY.md`
2. 读取 `.ai/config/agent.yaml`
3. 以 `.ai/config/agent.yaml` 为 Framework 的唯一机器入口
4. 按其中定义的相对路径加载 Framework 配置

`agent.yaml` 当前定义：

- `skill-schema.yaml`
- `skill-types.yaml`
- `skill-registry.yaml`
- `skill-loading.yaml`
- `skill-dependency.yaml`
- `skill-collaboration.yaml`
- `../tools/validator/validate.py`

## 2. Skill Discovery

Agent 不得假设 Skill 存在。

必须通过：

`.ai/config/skill-registry.yaml`

完成：

- Skill ID 查询
- Skill 路径解析

Skill 的 category、load policy、dependencies 等 Canonical Metadata 必须从 Registry 指向的 `SKILL.md` 读取，不从 Registry 重复读取。

然后加载 Registry 指向的：

`.ai/skills/{category}/{skill-id}/SKILL.md`

Skill 的具体能力定义以对应的 `SKILL.md` 为准。

## 3. Skill Loading

任务开始后：

1. 分析任务所需能力
2. 查询 Registry
3. 确认 Skill 是否存在且可用
4. 加载对应 `SKILL.md`
5. 根据 Skill 定义加载 references / examples / templates / context / memory
6. 按 dependency 与 collaboration 规则组成执行计划
7. 执行 Skill / Workflow
8. 根据任务需要进行结果验证

创建或修改 Skill 时，使用：

`.ai/config/SKILL_TEMPLATE.md`

作为 Skill 编写模板，并遵循：

`.ai/config/skill-schema.yaml`

定义的结构约束。

## 4. Framework Responsibilities

| 目录 | 职责 |
|---|---|
| `.ai/config/` | Framework contract、Schema、Registry、加载与关系规则 |
| `.ai/skills/` | Agent 专业能力 |
| `.ai/tools/` | 可执行的基础设施与检查工具 |
| `.ai/context/` | 当前任务 / 项目状态 |
| `.ai/memory/` | 长期项目知识 |

职责边界：

- **Workflow** = 任务编排
- **Skill** = 专业能力
- **Tool** = 实际执行操作

## 5. Dependency and Collaboration

**Dependency** 表示正确执行当前 Skill 所必需的能力。

**Collaboration** 表示多个 Skill 可以共同完成任务，但不代表它们互为硬依赖。

Skill 分类不等于运行时模块层级。

同一分类下的 Skill 默认独立，Skill 之间的关系必须由 dependency / collaboration 配置明确声明。

## 6. Validator

Validator 位于：

`.ai/tools/validator/validate.py`

Validator 不是 Skill。

仅当用户明确要求检查或验证 Framework、Skill 配置、Registry、依赖关系或结构完整性时执行。

Validator 负责检查：

- Framework 配置引用
- Schema
- Skill 目录与 `SKILL.md`
- Registry 覆盖与陈旧项
- Skill ID / path / category
- load policy
- dependency existence / direction / cycles
- collaboration consistency
- template / schema alignment
- legacy registry conflicts

当前 Validator **不负责 Git 检查**。

## 7. Entry Flow

```text
USER TASK
    ↓
AI_ENTRY.md
    ↓
.ai/config/agent.yaml
    ↓
Framework Config
    ↓
Skill Registry
    ↓
SKILL.md
    ↓
Dependency / Collaboration
    ↓
Workflow / Skill / Tool
    ↓
Validation
    ↓
Result
```

## 8. Core Rule

Framework 的机器入口、Skill Registry 与 Skill 定义必须保持单一来源：

- **Framework Entry** → `.ai/config/agent.yaml`
- **Skill Registry** → `.ai/config/skill-registry.yaml`
- **Skill Definition** → `.ai/skills/**/SKILL.md`
- **Skill Template** → `.ai/config/SKILL_TEMPLATE.md`
- **Validator** → `.ai/tools/validator/validate.py`

Agent 不应绕过上述入口自行推断 Skill、Registry 或 Framework 结构。

## 9. Before Starting Work

Agent 开始任何修改前，先阅读项目约定与上手指南：

```text
Read: AGENT_ONBOARDING.md
```

> 与第 1 节的关系：第 1 节定义 Framework 的**机器入口链**（agent.yaml → Framework Config → Registry）；
> 本节是**人类/Agent 上手前置阅读**。二者并行，不冲突：首次进入项目时先读本节，
> 再按第 1 节链路加载 Framework 配置。

## 10. Runtime Failure Routing

运行时（真实启动 Godot 后）出现错误、卡死、崩溃，或交付物尚未真实运行过：

```text
Runtime failure
    ↓
runtime-playtest Skill
```

路由规则：

- Runtime 问题只走 `runtime-playtest` Skill（通过 Registry 发现，不假设路径）；
  详细流程、工具链与安全边界全部定义在
  `.ai/skills/quality/runtime-playtest/SKILL.md`。
- 运行契约：`.ai/config/runtime-playtest.yaml`；结果契约：
  `.ai/context/runtime_result_schema.yaml`；修复计划契约：
  `.ai/context/repair_plan_schema.yaml`。
- 职责边界：Validator 只做静态验证（Project / Feature / Scene / Gameplay）；
  Runtime Playtest 负责运行期正确性；Self-Repair 负责修改。
  禁止把 Self-Repair 写进 Validator，禁止把 Runtime 逻辑写进 Feature / Scene。

## 11. Asset / Resource Routing

任务涉及图片、Sprite、SpriteFrames、Animation、Tileset、Audio、Texture、Font、
Shader、Godot Resource，或「使用项目现有的美术 / 音频资源」时：

```text
Asset / Resource task
    ↓
asset-discovery Skill
```

路由规则：

- 资源发现、筛选、推荐与绑定只走 `asset-discovery` Skill（通过 Registry 发现，
  不假设路径）；完整流程、工具链与安全边界定义在
  `.ai/skills/systems/asset-discovery/SKILL.md`。
- 契约：`.ai/context/asset_schema.yaml`（Asset Metadata）、
  `.ai/context/asset_binding_schema.yaml`（Entity → Asset 绑定）、
  `.ai/context/asset_manifest_schema.yaml`（人工确认层）。
- 契约总目录：所有协议入口（schema 文档 / CLI / validator / 版本）集中在
  `.ai/context/CONTRACT_INDEX.yaml`；需要找规则时**先读它**，不要扫描
  `.ai/tools` 或 `.ai/context` 目录。
- 生成物与缓存：`.ai/context/asset_index.json`、`.ai/context/asset_bindings/`
  属 Generated Data，Agent 不得手工维护，也不写入 `.ai/memory/DECISIONS.md`。
- 职责边界：Asset Discovery 负责「发现 / 绑定 / 报告缺失」；Scene Composer 负责把
  绑定实例化为资源节点（AnimatedSprite2D / Sprite2D / AudioStreamPlayer）；
  Validator 只 CHECK / REPORT。禁止视觉识别，禁止 AssetManager / ResourceManager
  之类的全局 Manager。
- 资源节点实例化与场景组装属于场景层，路由见第 12 节。

## 12. Scene Composition Routing

任务涉及创建 / 组装 Godot 场景时（例如 create scene、compose entity scene、
generate Godot scene、build playable scene、convert binding to scene）：

```text
Entity / Asset Requirement
    ↓
asset-discovery Skill（发现 + 显式选择 → 产出 Asset Binding）
    ↓
Asset Binding Document（.ai/context/asset_bindings/<id>.yaml）
    ↓
scene-composer Skill（消费 Binding → Scene Intent / 场景生成）
```

路由规则：

- 场景组装只走 `scene-composer` Skill（通过 Registry 发现，不假设路径）；
  完整流程、工具链与安全边界定义在
  `.ai/skills/systems/scene-composer/SKILL.md`。
- 资源侧前置：Binding 尚不存在时先走第 11 节的 `asset-discovery` Skill；
  **Scene Composer 的输入来源是 Asset Binding Document**
  （`.ai/context/asset_binding_schema.yaml`），不是索引、不是候选列表、
  不是 query 结果。
- 契约：`.ai/context/scene_composer_schema.yaml`（Binding → Scene Intent 边界契约，
  Phase 1.8.3 Contract Freeze 六原则）；蓝图格式
  `.ai/context/scene_schema.yaml`。
- 契约总目录：`.ai/context/CONTRACT_INDEX.yaml`（`scene_composition` 条目）；
  需要找规则时**先读它**，不要扫描 `.ai/tools` 或 `.ai/context` 目录。
- Scene Composer **不负责**：搜索资源、选择资源、替换 Binding、自动取 top1、
  推断或编造缺失资源。
- 职责边界：Asset Discovery 负责「发现 / 绑定 / 报告缺失」；Scene Composer 负责
  「消费 Binding，实例化资源节点与场景树」；Validator 只 CHECK / REPORT。
  禁止在场景层重建第二套 Asset Resolution，禁止 AssetManager / ResourceManager
  之类的全局 Manager，禁止给根节点挂脚本。

> 本节只声明路由，**不引入新的入口体系**：Framework 机器入口仍为
> `.ai/config/agent.yaml`，Skill 发现仍为 `.ai/config/skill-registry.yaml`，
> Skill 定义仍为 `.ai/skills/**/SKILL.md`。
