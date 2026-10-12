# Skill Identity

## Skill ID

runtime-playtest

## Skill Name

Runtime Playtest & Self-Repair

## Version

1.0

## Category

quality

# Registry Metadata

本章节是本 Skill 的 Canonical Metadata。
Registry 仅索引本 Skill，不重复维护这些字段。

## Load Policy

conditional

## Dependencies

### Required

- godot-debug-testing

### Related

- scene-composer
- gameplay-planner
- godot-gdscript
- feature-composition

## Ownership

负责「Runtime Correctness」：运行 Godot Project / Scene、捕获运行期错误、
把错误分类定位到 Feature / Scene / Script、产出 Repair Plan 并在安全边界内执行修复与复验。
不负责静态正确性（Validator）、不负责 Feature 实现、不负责 Scene 组合、不负责测试脚本编写。

# Description

在「生成 → 静态验证」之后补上「运行 → 观测 → 诊断 → 修复 → 复验」这一层能力。
本 Skill 编排以下 Tool（工具才是实际执行者）：

- `.ai/tools/runtime/run_scene.py` —— 运行指定 Scene，产出 runtime_result
- `.ai/tools/runtime/run_project.py` —— 运行项目主场景，产出 runtime_result
- `.ai/tools/runtime/capture_output.py` —— Godot 输出解析（ERROR / SCRIPT ERROR / WARNING）
- `.ai/tools/runtime/diagnose_runtime.py` —— 错误分类、定位、likely_cause、confidence
- `.ai/tools/runtime/repair_plan.py` —— Repair Plan 与修复安全策略
- `.ai/tools/runtime/self_repair.py` —— 修复控制器（最大尝试次数 + 修复历史 + 回滚）
- `.ai/tools/validator/check_runtime.py` —— Validator 第 5 阶段：Runtime Validation（只判定）

契约与 Schema：

- `.ai/config/runtime-playtest.yaml` —— timeout / max_repair_attempts / fail_on_error / 安全边界
- `.ai/context/runtime_result_schema.yaml` —— runtime_result 契约
- `.ai/context/repair_plan_schema.yaml` —— repair plan 契约

# Purpose

解决的问题：静态验证通过 ≠ 项目能跑。

Validator 只能证明「结构正确」：Feature 元数据齐备、组合依赖闭合、场景实例化合法、
Gameplay 循环有结算语义。它无法证明 `_ready()` 里 `get_node("Helth")` 不会炸，
也无法证明脚本能编译、资源能加载、场景不会卡死。

因此需要独立的一层：真实启动 Godot、运行 Scene、观测运行期事实、诊断、最小修复、复验。

# Responsibility

## 负责

- 判定「何时需要 Runtime Playtest」（见 Trigger Conditions）。
- 运行 Scene / Project 并产出 runtime_result（不做静态结构校验）。
- 解析 Godot 输出（ERROR / WARNING / SCRIPT ERROR / Invalid call / Invalid get index /
  Node not found / Null instance / Parser Error / Cannot load resource / Failed to load）。
- 诊断：classification + file/line + likely_cause + related_feature / related_scene + confidence。
- 产出 Repair Plan，并在 repair_safety 允许范围内执行最小修复。
- 记录修复历史（attempt / timestamp / error / diagnosis / changed_files /
  validation_result / runtime_result）。
- 修复无效或引入新错误时回滚。

## 不负责

- 不替代 Validator：静态正确性仍由 Validator 负责（Project / Feature / Scene / Gameplay）。
- 不修改 Project Settings、AI Framework、Skill Registry、Validator，不删除 Feature / Scene。
- 不修改无关 Feature；不把 Runtime 逻辑写进 Feature、Scene 或 Validator。
- 不创建 Godot 单例、FeatureManager / EntityManager / GameManager / RuntimeManager。
- 不为通过测试而修改测试预期。
- 不把普通运行期错误写进 `.ai/memory/DECISIONS.md`（架构决策与修复历史必须分开）。

# Trigger Conditions

需要进行 Runtime Playtest 的场合：

- Scene 刚由 Scene Composer 生成（新场景第一次落地）。
- Feature / Scene / System 的实现被修改（尤其是脚本、节点路径、信号连接、导出参数）。
- 静态 Validator 全部 PASS，但交付物尚未真实运行过。
- 用户报告「场景打不开 / 卡死 / 报错 / 行为不对」。
- 修复完成后需要复验（Repair 之后必须重新 Runtime Playtest）。

不需要 Runtime Playtest 的场合：

- 只改文档 / Skill 描述 / 配置注释（无运行期影响）。
- 静态 Validator 已经 FAIL（先修静态问题，再进运行期）。

# Input Contract

- Godot 项目根（含 `project.godot`）与 Godot 可执行文件（可用 `GODOT_BIN` 或
  `runtime_playtest.godot_binary` 指定）。
- 被验证场景的 `res://` 路径（缺省时运行项目主场景）。
- Runtime Playtest 契约（`.ai/config/runtime-playtest.yaml`）。
- 可选：既有 runtime_result.json 用于单点诊断。

# Workflow

```text
Gameplay Generation
        ↓
Static Validation（Validator：Project / Feature / Scene / Gameplay）
        ↓
Runtime Launch（run_scene.py / run_project.py）
        ↓
Runtime Observation（exit code / duration / stdout / stderr / parsed events）
        ↓
Failure Diagnosis（diagnose_runtime.py）
        ↓
Repair（repair_plan.py → self_repair.py，受 repair_safety 约束）
        ↓
Re-validation（脚本解析 / 场景结构 / Framework Validator）
        ↓
Runtime Playtest（重跑，直到 PASS 或达到 max_repair_attempts）
```

标准流程：

1. 运行 `python .ai/tools/runtime/run_scene.py --project . --scene res://Scenes/<X>.tscn --out runtime_result.json`。
2. `status: PASS` → Runtime Correctness 成立，进入交付；`FAIL / TIMEOUT / CRASH` 继续。
3. 运行 `python .ai/tools/runtime/diagnose_runtime.py runtime_result.json` 得到 diagnosis。
4. 需要自动修复：`python .ai/tools/runtime/self_repair.py --project . --scene res://Scenes/<X>.tscn --max-attempts 3`。
5. 修复后必须复验：`python .ai/tools/validator/check_runtime.py runtime_result.json`
   （或 `--project . --scene ...` 直接触发一次新的 Runtime Validation）。
6. 修复历史落盘 `.ai/memory/runtime-repairs/repair-00N.yaml`；只有长期架构经验才写 DECISIONS.md。

Validator 与本 Skill 的关系（必须保持）：

```text
Validator          → 静态结果（static correctness）
Runtime Runner     → 运行结果（runtime correctness）
Diagnosis          → 分析
Repair Plan        → 修改计划
Self Repair        → 最小修改
```

# Output Contract

- `runtime_result`（JSON，`runtime_result_schema.yaml`）：status / exit_code / duration /
  scene / stdout / stderr / errors / warnings / crash / timeout。
- `diagnosis`（YAML 或 JSON）：每条错误含 type、file、line、likely_cause、
  related_feature、related_scene、confidence。
- `repair plan`（`repair_plan_schema.yaml`）：error / target / reason / changes /
  validation / risk / repairable。
- repair history（`.ai/memory/runtime-repairs/repair-00N.yaml`）。
- 运行日志（`.ai/memory/runtime-logs/`，可通过契约关闭）。

# Validation

## Validation Method

- `run_scene.py` / `run_project.py`：exit 0 = PASS，1 = FAIL/TIMEOUT/CRASH，2 = 输入错误。
- `diagnose_runtime.py`：诊断必须给出 classification；无法判断时输出 unknown_runtime_error。
- `self_repair.py`：每次尝试都有 attempt 记录；无效修复回滚；不超过 max_repair_attempts。
- `check_runtime.py`：Runtime Validation 阶段，只判定不修复。
- 回归：`.ai/tools/runtime/tests/`（Runtime Playtest 五类用例）+ `.ai/tools/run_tests.py`。

## Success Criteria

- Runtime Playtest PASS（status=PASS，无 error 事件）。
- 修复场景：attempt 1 起 diagnosis / repair / validator / runtime 全部 PASS，修复历史落盘。
- 现有测试保持通过；Validator 零错误。

## Status Update

- PASS：Runtime Playtest 通过。
- WARNING：Runtime 通过但存在无法定位/无法分类的 warning。
- FAIL：存在 error / TIMEOUT / CRASH，或修复后仍失败。

# References

- `.ai/context/runtime_result_schema.yaml` —— runtime_result 契约
- `.ai/context/repair_plan_schema.yaml` —— repair plan 契约
- `.ai/config/runtime-playtest.yaml` —— 运行契约与修复安全边界
- `.ai/tools/runtime/README.md` —— 工具链与流水线说明
- `.ai/memory/DECISIONS.md` —— AD-010（Runtime Correctness 分层）/ AD-002 / AD-008
- `.ai/skills/engineering/godot-debug-testing/SKILL.md` —— 无头运行与日志排查

# Failure Handling

- 无法启动 Godot → 报输入错误，不猜测运行结果；提示设置 `GODOT_BIN`。
- 场景不存在 → 不启动 Godot，直接产出 `scene_load_error` 的 FAIL 结果。
- 错误无法分类 → `unknown_runtime_error` + confidence: low；禁止编造原因。
- 无确定性修复策略（如 parser_error / resource_missing / timeout）→ plan 输出
  `repairable: false` + reason，交回人工或上游 Skill，不做试探性修改。
- 修复无效或引入新错误 → 回滚并停止，不做无界重试。
- 到达 `max_repair_attempts` 仍未通过 → 输出失败报告与最后一次诊断，交回用户。

# Permission Model

允许执行：

- 启动 Godot（headless）运行项目 / 场景。
- 写入 `.ai/memory/runtime-logs/`、`.ai/memory/runtime-repairs/`。
- 在 repair_safety 允许范围内修改「报错脚本 / 被验证场景 / 相关 Feature 内文件」，
  且每次尝试只允许一处字面量替换。

需要确认：

- 修改报错点之外的文件、跨 Feature 修改。
- 任何删除操作（Feature / Scene / 资源）。
- 修改 Project Settings、AI Framework、Skill Registry、Validator。
- 接受 medium confidence 的候选修复（使用 `--allow-medium`）。

# Notes

- Runtime Playtest 与 Validator 有明确分工：本 Skill 不重写静态校验规则。
- Runtime 结果里每一个 error 都必须可分类或有明确的「无法分类」结论；
  「看起来像是……」这种推测不写入 diagnosis。
- 修复历史是过程记录，不是架构决策；只有真正具长期价值的经验才进入
  `.ai/memory/DECISIONS.md`。
- 测试用例使用临时项目副本，保证修复测试不污染真实项目。
