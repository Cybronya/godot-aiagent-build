# Skill Identity

## Skill ID

gameplay-planner

## Skill Name

Gameplay Planner

## Version

1.0

## Category

gameplay

# Registry Metadata

本章节是本 Skill 的 Canonical Metadata。
Registry 仅索引本 Skill，不重复维护这些字段。

## Load Policy

conditional

## Dependencies

### Required

[]

### Related

[]

## Ownership

负责「游戏需求 → Gameplay Blueprint（实体清单、跨实体系统、循环）」的规划与
校验（Gameplay 层）；不负责单实体组合（feature-composition）、场景生成
（scene-composer）与测试执行。

# Description

负责把自然语言游戏需求转换为 Gameplay Blueprint：分析需要的实体、为每个实体
复用 Feature Discovery/Composition 遴选 Feature、声明跨实体 System 与循环语义，
并生成 Entity Relationship Graph（entity_graph.json）。
工具：`.ai/tools/gameplay_planner/planner.py`、
`.ai/tools/validator/check_gameplay.py`。

# Purpose

让「整局游戏」的组装有据可查：实体从哪来（Entity/Scene Composer）、跨实体流程
归谁（System Registry）、循环是否闭合（Validator）——把 Gameplay 层从隐式约定
变成可校验的蓝图。

# Responsibility

## 负责

- 运行 Gameplay Planner 生成 Gameplay Blueprint 与 entity_graph.json。
- 声明跨实体 System（Systems/*/system.yaml 为登记处）并检查循环闭合。
- 用 check_gameplay.py 校验：实体场景存在、能力覆盖需求、loop 闭环、System 引用。
- 把每实体的 Entity Blueprint 交接给 scene-composer 落盘。

## 不负责

- 不创建 God Object / GameManager / EntityManager / FeatureManager。
- 不拥有 Gameplay State——实体状态归 Feature，跨实体流程归 System（流程归
  System 所有，状态仍归 Feature）。
- 不实现 Feature 内部逻辑；缺口走 feature-development.md Build 分支。

# Trigger Conditions

- 需求描述一局游戏/玩法循环（生存、竞技场、解谜房间、平台闯关）。
- 需要多个实体与跨实体流程（生成、奖励、机关控制）。
- 已有实体蓝图需要检查循环闭合与 System 引用。

# Input Contract

- 一句游戏需求（如 "create enemy survival game"）。
- 可选：明确 gameplay id（--id）、Blueprint 落盘路径（--out）。

# Workflow

```text
User Requirement
      ↓
Gameplay Analysis（requirement_parser）
      ↓
Required Entities + Feature Discovery（compose_features 内核）
      ↓
Gameplay Blueprint（gameplay_schema.yaml）
      ↓
Entity Composition（逐实体 Entity Blueprint -> scene-composer）
      ↓
Scene Generation + Validation（scene-composer + check_gameplay）
      ↓
Gameplay Test（循环测试，Godot 无头）
```

标准流程：

1. 运行 `python .ai/tools/gameplay_planner/planner.py "<需求>" [--out <path>]`。
2. 审查 Blueprint：实体清单是否覆盖需求、System 引用是否已登记、loop 三段是否
   语义完整。
3. 逐实体交接 scene-composer：复用场景（entry.scene）或生成 Scenes/<Pascal>.tscn。
4. 运行 `python .ai/tools/validator/check_gameplay.py <blueprint.yaml>`。
5. 生成/运行 Gameplay 循环测试（实体存在、伤害生效、死亡生效、循环闭合）。

# Output Contract

- Gameplay Blueprint（gameplay.id / entities / systems / loop / validation）。
- entity_graph.json（实体关系图，自动生成）。
- 校验结论（PASS / Missing Entity Scene / Gameplay incomplete / loop incomplete）。

# Rules

必须：

- 优先复用 Feature（实体 = Feature 组合；需求缺口先 Discovery 后 Build）。
- Gameplay Logic 使用独立 System（Systems/*/system.yaml 登记），System 是流程
  归属而非节点/单例。
- Entity 只拥有自身状态；跨实体流程归 System。
- loop.end 必须有结算语义；结算依赖的能力/系统必须真实存在。

禁止：

- 创建 God Object / GameManager / EntityManager / FeatureManager。
- 在 System 中拥有实体状态或复写 Feature 所有权。

# Validation

## Validation Method

- planner.py 可重复运行，同一需求产出一致蓝图。
- check_gameplay.py 独立校验蓝图与落盘结果。
- 成员 Feature 回归 + Gameplay 循环测试（Godot 无头）。

## Success Criteria

- 每个实体有场景（复用或生成）且组合校验通过。
- required_features 全覆盖；loop 闭合；systems 引用全部登记。
- 循环测试 PASS。

## Status Update

- PASS：蓝图校验通过。
- WARNING：循环语义不完整（loop incomplete）。
- FAIL：实体场景缺失、能力缺口或 System 引用不存在。

# References

- .ai/context/gameplay_schema.yaml —— Gameplay Blueprint / system.yaml 格式
- .ai/context/entity_graph.json —— Entity Relationship Graph（Generated）
- .ai/tools/gameplay_planner/ —— parser / generator / planner
- .ai/tools/validator/check_gameplay.py —— Gameplay 校验
- Systems/ —— System Registry
- .ai/memory/DECISIONS.md —— AD-009（Gameplay Loop Composer）

# Failure Handling

- Missing Entity Scene → 先由 scene-composer 生成实体场景或修正 scene 复用声明。
- Gameplay incomplete → 组合缺口回到 feature-composition / Build 分支。
- Gameplay loop incomplete → 补结算系统（Systems 登记）或修正 loop 描述。
- Unknown System → 新建 system.yaml 登记（跨实体流程确需存在时）。

# Permission Model

允许执行：

- 运行 planner.py / check_gameplay.py（只读 + entity_graph.json 写入）。

需要确认：

- 蓝图实体/系统增删偏离 Planner 结果。
- 新建 System 登记、新建 Feature（走 feature-development.md）。

# Notes

- 需求解析是规则式（英文关键词）；"survival/arena" 隐含玩家实体与
  enemy_spawn/reward 系统。
- 与 scene-composer 的分工：本 Skill 决定「有哪些实体、循环怎么转」；
  scene-composer 决定「单个实体如何实例化」。
