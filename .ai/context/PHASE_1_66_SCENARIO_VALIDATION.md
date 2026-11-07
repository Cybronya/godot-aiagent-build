# Phase 1.66 — Scenario Validation

## 1. 验证状态（7 种）

| 状态 | 含义 |
| --- | --- |
| `VALID` | 所有检查通过，可进入 Execution Planner |
| `INVALID` | Schema/结构/动作/期望/清理不可执行 |
| `INCOMPLETE` | 结构可执行但缺少必需来源（知识引用、依赖边、来源引用） |
| `ENVIRONMENT_BLOCKED` | 环境不支持（Godot 缺失、场景不存在） |
| `SOURCE_STALE` | 来源文件 digest 与记录不一致 |
| `KNOWLEDGE_STALE` | 知识契约版本过期 |
| `CONTRACT_MISMATCH` | 目标 Behavior 不存在或契约版本不匹配 |

验证失败必须给出具体原因；不存在“自动降级换 PASS”的路径。

## 2. 检查项

| 维度 | 检查 |
| --- | --- |
| Contract | Behavior 在支持集；`contract_version` 与当前契约一致；期望不违反契约；不变量存在 |
| Source | 引用文件存在且位于 `Features/`；行号有效；文件 digest 与记录一致 |
| Knowledge | ID 存在；未 REVOKED；未被替代；无 OPEN 冲突；类型允许驱动测试 |
| Dependency | 依赖场景必须有边引用；边必须在真实图中；上游未验证时标 INCOMPLETE |
| Execution | 场景文件存在；动作类型在允许集合；帧预算上限；cleanup 非空；Runner 可用（环境检查） |

## 3. 本轮结果

```text
total=5  valid=5  invalid=0  incomplete=0  blocked=0
```

5 条场景全部通过：契约版本、来源 digest、知识状态、依赖边、动作/期望可验证性、cleanup。

## 4. 攻击测试（18 项，全绿）

| 检查 | 攻击面 |
| --- | --- |
| V2 | 伪造 Knowledge ID |
| V3 | 错误 Contract Version |
| V4 / V14 | 场景/来源路径越界（非 `Features/`、`..`） |
| V5 / V6 / V15 | 空动作、空期望、未知动作类型 |
| V7 / V8 | 依赖场景缺边引用、引用不存在的边 |
| V9 | 来源 digest 不匹配（SOURCE_STALE） |
| V10 | 知识契约版本过期（KNOWLEDGE_STALE） |
| V11 | 已撤销知识 |
| V12 | 未解决冲突阻断 |
| V13 / V18 | 缺 SOURCE_REFERENCE / 缺 knowledge_refs（INCOMPLETE） |
| V16 | 帧预算溢出 |
| V17 | 缺 cleanup |

未覆盖（明确登记，不得当成已测）：
- 符号链接越界（Windows 上需真实 symlink 权限；路径规范化逻辑已有，但无自动化用例）。
- 源码在“验证后、执行前”被替换的竞态（执行侧用 digest 复核，见 Execution Report §4）。

## 5. 与 Execution Planner 的契约

`scenario_run.plan_scenario()` 只接受 `validation_status == "VALID"`；
任何其他状态返回 `BLOCKED`，并保留 validator 状态可见（R9/R12），不生成 evidence（R11）。
