# Skill Identity

## Skill ID

feature-discovery

## Skill Name

Feature Discovery

## Version

2.0

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

负责「需求 → 已有 Feature 能力」的发现与匹配流程；不负责 Feature 的实现、组合或验证。

# Description

定义 Agent 在实现玩法前如何发现并复用已有 Feature：通过 Feature Discovery Tool
（`.ai/tools/feature_registry/discover_feature.py`）查询聚合索引
（由 build_feature_index.py 从 `Features/*/feature.yaml` 自动生成，feature.yaml
是 Source of Truth），把需求描述匹配到声明能力（provides / category / interfaces），
输出推荐 Feature 及匹配理由。

# Purpose

Feature Discovery 用于：

- 查找已有 Feature（能力发现）。
- 避免重复开发已有能力。
- 优先复用能力，减少新代码量。

这是 Feature Registry 路线图（P0-1）的工具化落地。

# Responsibility

## 负责

- 定义何时调用 Feature Discovery。
- 定义查询输入、结果解读与 Reuse 前置检查流程。
- 维护 Discovery 结果与 feature-development.md Reuse or Build 分支的衔接。

## 不负责

- 不做 Feature 的实现、组合或验证（由 godot-scene-system 等相关 Skill 与
  feature-development.md 管辖）。
- 不修改 feature_index.json 的匹配数据来源（canonical 是各 feature.yaml）。
- 不做最终 Reuse/Build 决策——决策属于 feature-development.md §3。

# Trigger Conditions

When implementing gameplay (实现任何玩法/实体/交互之前):

1. Query Feature Discovery —— 用一句需求描述运行 discover_feature.py
2. Check existing Feature —— 核对推荐结果的 feature.yaml 与 README
3. Reuse before creating new code —— 有覆盖即复用，缺口才进入 Build

其他触发：

- 任务描述包含「敌人/玩家/门/平台/拾取/伤害/治疗」等玩法实体或机制词。
- feature-development.md §1 Discovery 要求盘点已有 Features 时。
- 用户询问「项目里是否已有某能力」。

# Input Contract

- 一句需求描述（自然语言，中英皆可；工具按英文关键词/同义词匹配）。
- 可选：已知约束（节点类型、组合契约），用于过滤推荐结果。

# Workflow

```text
User Requirement
      ↓
Feature Discovery（查询索引）
      ↓
Existing Feature Check（读 feature.yaml 确认契约）
      ↓
Implementation Decision（Reuse / Reuse+Build / Build）
```

标准流程：

1. 把需求压缩为一句可匹配的描述（如 "enemy can receive damage"）。
2. 必须优先查询 Feature Registry：运行 `python .ai/tools/feature_registry/discover_feature.py "<需求描述>"`。
3. 阅读输出的 Matched Features、Reason（命中的 provides/interface）与 Interfaces。
4. Existing Feature Check：对每个候选读取 `Features/<id>/feature.yaml`（Source of Truth）确认：
   状态所有权（ownership）是否与本任务冲突、组合契约（composition）是否可满足。
5. Implementation Decision（对接 feature-development.md §3 Reuse or Build）：
   - 覆盖需求 → Reuse 分支
   - 部分覆盖 → Reuse 为主 + Build 补缺，两部分分别走完各自分支验证
   - 无覆盖 → Build 分支；新 Feature 必须按 FEATURE_SCHEMA.md 交付 feature.yaml，
     并重跑 build_feature_index.py 更新索引（否则 Validator FAIL）
6. 把发现结论写入本次任务的 Discovery 简报。

# Rules

必须：

- 优先查询 Feature Registry（任何实现类任务动手前先跑 discover_feature.py）。
- 禁止重复创建已有能力（查询命中且契约满足时不得新建同类实现）。
- 新 Feature 必须添加 feature.yaml（交付即含 metadata，按 FEATURE_SCHEMA.md）。
- metadata 变更后必须重跑 build_feature_index.py（Validator 校验同步）。

禁止：

- 不得绕过索引直接硬编码对 Features/ 目录布局的假设（索引负责数据生成，工具只查询）。
- 不得把 feature_index.json 当作 Source of Truth（它是 Generated Data / 缓存）。

# Output Contract

- Discovery 简报中列出：查询语句、命中 Feature（含 score 与理由）、
  采纳/排除结论及依据（以 feature.yaml 为准）。
- 排除候选时必须给出理由，不得静默丢弃。

# Validation

## Validation Method

- 工具本身：用固定查询回归（见 Tool Usage）。
- 流程层面：本轮任务的 Discovery 简报包含查询记录与采纳/排除结论。

## Success Criteria

- 实现类任务在动手前已执行至少一次 Feature Discovery 查询。
- 结论引用了候选 Feature 的 feature.yaml 字段，而非仅凭命名推断。

## Status Update

- PASS：查询已执行且结论进入 Discovery 简报。
- WARNING：工具无结果（按 Workflow 第 5 步进入 Build 分支并记录）。
- FAIL：未查询即开始实现。

# References

- .ai/tools/feature_registry/README.md —— 流水线架构与工具用法
- .ai/tools/feature_registry/build_feature_index.py —— 索引生成器
- .ai/context/feature_index.json —— Generated Data（缓存）
- Features/FEATURE_SCHEMA.md —— feature.yaml 格式规范（Source of Truth 的格式）
- .ai/workflows/feature-development.md —— Reuse or Build 决策
- .ai/tools/validator/check_feature_metadata.py —— metadata 契约与索引同步校验

# Examples

需求「创建一个会攻击玩家的敌人」：

```text
1. python discover_feature.py "enemy can attack player and has health"
2. 命中: health(provides: damage_receiver) / contact_damage(damage_source)
        / chase_movement(chase_behavior)
3. 组合: Enemy
         ├ Health
         ├ ContactDamage
         └ ChaseMovement
4. 复用三分支均零修改；缺口（如攻击触发）才进入 Build。
```

# Failure Handling

- 索引缺失或查询报错 → 提示先运行 build_feature_index.py；仍失败则按旧路径扫描
  `Features/` 目录读 feature.yaml，并在 Discovery 简报中记录工具失败。
- 查询无结果 → 不视为失败，按 Workflow 第 5 步进入 Build 分支。
- 命中结果与实际源码不符（feature.yaml 过期）→ 以源码为准回写修正 metadata，
  并重跑 build_feature_index.py。

# Permission Model

允许执行：

- 运行 discover_feature.py（只读工具）。
- 读取 Features/ 下任何 feature.yaml 与 README。

需要确认：

- 修改 feature_index.json 结构或匹配权重。
- 修改 FEATURE_SCHEMA.md 规范。

# Notes

- 第一版匹配是关键词 + 同义词 + 加权评分，无 LLM；同义词表见工具源码 SYNONYMS。
- 需求描述用英文短语匹配效果最好（如 "player loses hp when touching enemy"）。
