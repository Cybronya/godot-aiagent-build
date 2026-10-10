# Skill Identity

## Skill ID

feature-composition

## Skill Name

Feature Composition

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

[]

## Ownership

负责「多 Feature → Gameplay Entity」的组合规划（Entity Blueprint）；不负责 Feature 的实现、场景实例化与验证执行。

# Description

负责将多个 Feature 组合成 Gameplay Entity：基于 Feature Discovery 结果与关系元数据
（relations / Feature Graph），产出 Entity Blueprint（实体角色、成员 Feature、
组合理由、回归测试清单）。工具：`.ai/tools/feature_registry/compose_features.py`。

# Purpose

让 Agent 在实现实体前先得到一张可审查的组合蓝图：哪些 Feature 成员、为什么、
缺什么前置、跑哪些测试——把「组合」从临场发挥变成有据可查的规划。

# Responsibility

## 负责

- 运行 Composition Planner，生成并解读 Entity Blueprint。
- 校验组合合法性（成员存在、requires 满足、conflicts 不共存）。
- 把蓝图传达给实现步骤（场景组合）与验证步骤（回归测试清单）。

## 不负责

- 不创建 Entity Manager / Gameplay Manager / Feature Controller（架构禁令）。
- 不拥有 Gameplay State——状态由组成 Feature 各自管理（Round 8 结论）。
- 不执行场景实例化与测试（由 godot-scene-system / godot-debug-testing 管辖）。

# Trigger Conditions

- 需求要求创建由多个能力组成的实体（敌人、玩家、机关、拾取物）。
- Feature Discovery 命中多个 Feature 且需要确认组合关系。
- 实体组合的 requires/conflicts 合法性需要检查。

# Input Contract

- 一句需求描述（如 "enemy follows player and deals damage"）。
- 可选：明确的实体 id（--id）。

# Workflow

```text
Requirement
      ↓
Feature Discovery（discover_feature.py）
      ↓
Composition Planning（compose_features.py）
      ↓
Entity Blueprint
      ↓
Implementation（场景组合）
```

标准流程：

1. 先执行 Feature Discovery（feature-discovery Skill）确认候选能力。
2. 运行 `python .ai/tools/feature_registry/compose_features.py "<需求>" [--id <entity_id>]`。
3. 审查 Entity Blueprint：
   - features 成员是否恰当地覆盖需求（不过组合、不缺组合）；
   - reason 是否成立；conflicts/requires 是否被 Validator 报告为问题。
4. 组合合法性检查（check_feature_metadata.check_composition 或 Validator 集成项）通过后才进入实现。
5. Implementation：按 AD-002 组件组合模式实例化 Feature 场景；实体场景只做组合，
   满足组合契约（组、命名）；关系用信号连接表达，不写仲裁器。
6. Validation：对 blueprint.validation.required_tests 中的每个成员 Feature 执行回归验证，
   再做项目级集成验证。

# Output Contract

- Entity Blueprint（entity.id / role / features / reason / validation.required_tests）。
- 组合合法性结论（PASS / 缺前置 / 冲突）。
- 对蓝图偏差的说明（如人工增删成员的理由）。

# Rules

必须：

- 优先组合已有 Feature（先 Discovery 后 Composition，先组合后新建）。
- 禁止创建重复 Feature（组合无法满足的缺口才进入 Build，按 feature-development.md）。
- Entity 不拥有 Gameplay State——Feature 管理自身状态。
- Scene 只负责组合（实例化 + 信号连接 + 契约满足），不拥有状态、不做仲裁。
- 组合内 conflicts 冲突与 requires 缺口必须先解决或说明，再实现。

禁止：

- 创建 Entity Manager / Gameplay Manager / Feature Controller。
- 绕过蓝图直接手写实体组合（除非单 Feature 简单场景）。

# Validation

## Validation Method

- compose_features.py 可重复运行，同一输入产出一致蓝图。
- check_composition 对蓝图做成员/前置/冲突检查。
- 蓝图成员的 self_test 回归 + 项目级集成验证。

## Success Criteria

- 每个成员都有 reason；无 Validator 报告的 requires 缺口与 conflicts 冲突。
- 实现后成员 Feature 回归全部 PASS。

## Status Update

- PASS：蓝图生成且组合检查通过。
- WARNING：蓝图含未满足前置（已列出 missing capability）。
- FAIL：组合冲突未解决。

# References

- .ai/context/composition_schema.yaml —— Entity Blueprint 格式
- .ai/context/feature_graph.json —— Feature 关系图（Generated）
- .ai/tools/feature_registry/compose_features.py —— Composition Planner
- Features/FEATURE_SCHEMA.md —— relations 字段规范
- .ai/memory/DECISIONS.md —— AD-002（组件组合）/ AD-004（组合契约）/ AD-005（布尔契约）

# Failure Handling

- Planner 无结果 → 需求超出当前能力图；按 feature-development.md Build 分支，
  缺口逐项记录。
- 组合检查报冲突 → 先调整成员或扩展 Feature 冲突语义（属 Feature 自身所有权），
  不得在场景层写仲裁。
- 蓝图与实际源码不符 → 以源码为准修正 feature.yaml 并重跑 build_feature_index.py。

# Permission Model

允许执行：

- 运行 compose_features.py（只读）。
- 读取索引、关系图与 feature.yaml。

需要确认：

- 蓝图成员增删偏离 Planner 结果。
- 新建 Feature（走 feature-development.md Build 分支）。

# Notes

- 组合算法（v1，无 LLM）：关键词提取 → Discovery 匹配 → 关系图增强 → 评分排序
  （provides×5 + relation×3 + entity_role×2）→ 冲突过滤 → Blueprint。
- 敌人类实体的最小组合模式（Siege Gate 验证）：Health + ContactDamage + ChaseMovement [+ Stun]。
