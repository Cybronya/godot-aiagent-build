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
