# Skill Framework Validator

这是 Godot Agent Skill Framework 的按需机器验证器。

Validator 只检查，不自动修改 Framework 文件。第一阶段只在用户明确要求检查/验证时由 Agent 执行。

## 执行

```bash
python .ai/tools/validator/validate.py
```

也可以显式指定配置目录：

```bash
python .ai/tools/validator/validate.py --config-dir .ai/config
```

依赖：Python 3 + PyYAML（`pip install pyyaml`）。

## Trace Replay（Phase 1.22）

编排诊断事件 trace 的**只读**回放（不调用 Godot、不驱动游戏状态）：

```bash
python .ai/tools/validator/trace_replay.py <trace.json> [--json]
# 退出码: 0 = 合法可回放；1 = 违反契约；2 = 输入错误（缺文件 / 非法 JSON / 未知版本）
```

契约见 `.ai/context/orchestration_trace_schema.yaml`；真实 trace 由
`e2e/multi_stage_boss_probe.py` 从 Godot 运行导出，单测在
`validator/tests/test_orchestration_trace.py`（R1–R43）。

## 检查范围

- Agent 入口与 Framework 版本
- Agent 配置路径
- Registry 注册项
- Registry 与 canonical SKILL.md 一致性
- Skill ID、目录名、必需 Metadata
- Category 与 Load Policy
- Required / Related Dependencies
- Dependency Category Direction
- Circular Required Dependencies
- Schema / Template 基础对齐
- Collaboration 中的重复 canonical metadata
- Framework 内部路径的 root-independent 约束

## Layer Checks（Phase 1.15）

在 Framework 静态检查之外，validate.py 可以**编排既有检查器**执行分层校验（缺省不执行，
行为与历史版本兼容）。各层独立运行，局部失败不阻断其他层；诊断统一为结构化格式
`{layer, code, severity, location, path, reason, hint}`，带稳定错误代码。

```bash
# Scene 层（Scene/Entity Blueprint + 生成的 .tscn，场景按 root.name 推导）
python .ai/tools/validator/validate.py --scene-blueprint slime_enemy.yaml
# Gameplay 层
python .ai/tools/validator/validate.py --gameplay-blueprint survival_game.yaml
# Level 层（关卡编排配置）
python .ai/tools/validator/validate.py --level Levels/timed_combat_arena.json
# Runtime 层（真实 Godot headless playtest，耗时；显式 opt-in）
python .ai/tools/validator/validate.py --runtime-scene res://Scenes/EnemyBasic.tscn
# Runtime 层（只判定既有 runtime_result，不启动 Godot）
python .ai/tools/validator/validate.py --runtime-result runtime_result.json
# Binding 层（Phase 1.18：资产绑定文档静态健康检查；复用 check_binding_schema）
python .ai/tools/validator/validate.py --bindings-dir .ai/context/asset_bindings
# Binding 层 + 实体存在性（entity-scoped 绑定必须指向蓝图中声明的实体）
python .ai/tools/validator/validate.py --bindings-dir .ai/context/asset_bindings \
    --gameplay-blueprint survival_game.yaml
# 组合 + 自定义项目根
python .ai/tools/validator/validate.py --level Levels/survival_arena.json \
    --gameplay-blueprint survival_game.yaml --project-root .
```

编排实现在 `validator/unified.py`（各层调用既有独立检查器，不重新实现规则）。

**Binding 层约定（Phase 1.18）**：无 `--gameplay-blueprint` 时无法判断实体存在性，
输出 `BINDING_INFO_INSUFFICIENT_INPUT` **info 诊断**（如实展示，不计入
error/warning 基线——既不虚构校验成功，也不夸大为告警）；给出蓝图后，
entity-scoped 绑定指向未知实体会成为稳定 `BINDING_*` error 诊断（整层 FAIL）。

**Runtime 可用性约定**：`--runtime-scene` 需要 Godot 二进制（相邻目录或 PATH）；
Godot 不可用时该层标记 `UNAVAILABLE` 并输出 `INCOMPLETE`，整体退出码非零——
Runtime 检查缺失永远不会被伪装成通过。耗时的 Runtime 探针为显式 opt-in，
缺省 Validator 只做快速静态检查（输出按层区分覆盖范围）。

## 输出

- **PASS**：无错误或警告
- **WARNING**：无阻断错误，但有需要人工确认的问题
- **FAIL**：违反 Framework 契约
- **INCOMPLETE**：被请求的层（如 Runtime）不可用，未真正执行

发现问题后由 Agent 决定如何修复，修复后再次运行 Validator。当前不接 Git hooks、GitHub Actions 或后台自动检查。
