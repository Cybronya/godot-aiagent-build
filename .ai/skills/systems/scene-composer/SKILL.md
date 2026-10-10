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

[]

## Ownership

负责「Entity Blueprint → Godot Scene (.tscn)」的自动组装（场景生成、依赖解析、
结构校验、测试生成）；不负责 Feature 的实现、组合规划与测试执行。

# Description

负责根据 Scene Blueprint / Entity Blueprint 自动生成 Godot Scene：加载
Feature Scene Template（Features/*/template.yaml）、解析组合依赖、生成
Scenes/<RootName>.tscn、运行结构校验，并可选生成场景回归测试。
工具：`.ai/tools/scene_composer/scene_composer.py`、
`.ai/tools/validator/check_scene_composition.py`、
`.ai/tools/test_generator/generate_scene_test.py`。

# Purpose

让「实体实现」从手写场景变成可验证的自动组装：组合计划落盘为标准 .tscn，
组件一律实例化 Feature 入口场景，Scene 不引入任何自有逻辑。

# Responsibility

## 负责

- 运行 Scene Composer，把 Blueprint 生成 Scenes/<RootName>.tscn。
- 生成前用 dependency_resolver 拦截缺失前置（Composition Error / Missing dependency）。
- 生成后用 check_scene_composition 校验（Feature 完整性 / 依赖 / 根类型 / 组合约束）。
- 用 test_generator 生成 Tests/test_<scene_id>.gd 并纳入回归。

## 不负责

- 不创建 Global Manager / Entity Manager（架构禁令）。
- 不修改 Feature 内部实现；Feature 缺口走 feature-development.md Build 分支。
- 不执行测试（由 godot-debug-testing / run_tests.py 管辖）。

# Trigger Conditions

- 已有 Entity Blueprint（compose_features.py 产出）需要落盘为场景。
- 已有 Scene Blueprint（手写或推导）需要生成/再生成 .tscn。
- 场景生成后的组合合法性与回归测试需要检查。

# Input Contract

- Scene Blueprint（scene:/root:/components:/nodes:/validation:）或
  Entity Blueprint（entity:/features:，自动推导），格式见
  .ai/context/scene_schema.yaml。
- 组合成员必须存在于 feature_index.json。

# Workflow

```text
Entity Blueprint
      ↓
Feature Template Lookup（Features/*/template.yaml）
      ↓
Dependency Resolve（requires 硬性拦截）
      ↓
Scene Generation（scene_builder → Scenes/<RootName>.tscn）
      ↓
Validation（check_scene_composition）
      ↓
Test Generation（Tests/test_<scene_id>.gd）
```

标准流程：

1. 由 feature-composition 产出 Entity Blueprint（或直接写 Scene Blueprint）。
2. 运行 `python .ai/tools/scene_composer/scene_composer.py <blueprint.yaml> --tests`。
3. 生成失败（依赖缺失/未知 Feature）→ 回到组合层解决，不得在场景层补胶水。
4. Validation PASS 后运行 `python .ai/tools/run_tests.py Tests/test_<scene_id>` 回归。

# Output Contract

- Scenes/<RootName>.tscn（根节点 + 组件实例 + 额外结构节点）。
- Validation 结论（PASS / Missing Feature / Composition Error / Invalid Root Node Type）。
- Tests/test_<scene_id>.gd（--tests 时）。

# Rules

必须：

- 优先使用 Feature Scene Template（组件 = 实例化 Feature 入口场景）。
- 生成前后都过 Validator：依赖解析拦截 + 结构校验兜底。
- 根节点类型满足成员 template 的 root_type 要求（如 chase_movement → CharacterBody2D）。

禁止：

- 复制 Feature 代码进实体场景（只允许 instance=ExtResource 组合）。
- 给根节点挂脚本——Scene 只负责组合，不拥有状态、不做仲裁。
- 创建 Global Manager / Entity Manager / Feature Manager / Global Singleton。

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

- .ai/context/scene_schema.yaml —— Scene Blueprint / template.yaml 格式
- .ai/context/composition_schema.yaml —— Entity Blueprint 格式（上游）
- .ai/tools/scene_composer/ —— composer / builder / resolver / validator
- .ai/tools/validator/check_scene_composition.py —— 场景组合校验
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
