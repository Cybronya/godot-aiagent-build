# Phase 1.66 — Result Analyzer

## 1. 输入

场景 JSON、`scenario_results.json`（Execution/Validator/Attestation/Evaluation 四层）、
Evidence Bundle 与 Manifest、契约、源码分析、依赖图、历史知识。

## 2. 分类（9 种）

| 分类 | 判定依据 |
| --- | --- |
| `CONTRACT_CONFIRMED` | 期望项来自正式契约且真实观测满足 |
| `SOURCE_CONFIRMED` | 期望项来自源码守卫分析且真实观测满足 |
| `BEHAVIOR_CONFIRMED` | 行为级结论（依赖/后置）被真实观测满足 |
| `BEHAVIOR_VIOLATION` | Evidence 通过校验且某检查真实失败 |
| `TEST_DESIGN_ERROR` | 动作未执行 / 前置不满足 / 场景自算与执行矛盾 |
| `ENVIRONMENT_BLOCKED` | 环境不满足 |
| `RUNNER_ERROR` | 超时或 Runner 异常 |
| `RESOURCE_ERROR` | 场景/资源缺失 |
| `INCONCLUSIVE` | 证据不足（缺 Attestation、缺 Evidence、状态不可判定） |

推导来源与结论分离：`_derivation_is_contract()` 依据场景期望是否逐条匹配契约来区分
CONTRACT_/SOURCE_，不按 Behavior 名猜测。

## 3. 本轮真实结论（label `P4`）

| scenario | 分类 | 依据 |
| --- | --- | --- |
| `s-16f6576c8683f7bc` door | CONTRACT_CONFIRMED | evidence/attestation/validator/evaluation 全通过；期望与契约一致 |
| `s-37cd4dc9f084950e` trigger | SOURCE_CONFIRMED | 全链通过；期望由守卫知识推导 |
| `s-7771e41885fcd58e` health | SOURCE_CONFIRMED | 全链通过；期望含终态守卫条目 |
| `s-8b9f108ecb56beb2` save | SOURCE_CONFIRMED | 全链通过；非法槽位观测满足 |
| `s-e6eb3fc5c8e82e32` i_frames | BEHAVIOR_CONFIRMED | 全链通过；依赖后置观测满足 |

```json
{"CONTRACT_CONFIRMED": 1, "SOURCE_CONFIRMED": 3, "BEHAVIOR_CONFIRMED": 1}
```

无 FAILED、无 INCONCLUSIVE、无 ENVIRONMENT_BLOCKED。

## 4. 分析门禁（14 项测试全绿）

- 缺 Attestation → INCONCLUSIVE（A3）；缺 Evidence → INCONCLUSIVE（A4）。
- 环境阻塞 → ENVIRONMENT_BLOCKED（A5）；超时 → RUNNER_ERROR（A6）；场景缺失 → RESOURCE_ERROR（A7）。
- 动作未执行 / 前置不满足 → TEST_DESIGN_ERROR（A9/A10），不误判为行为缺陷。
- 执行 FAILED 但场景自算 PASS → INCONCLUSIVE（A8）。
- 只有 Evidence 通过且确有失败检查 → BEHAVIOR_VIOLATION（A11）。
- FAIL 但找不到失败检查 → INCONCLUSIVE（A12）——不强行给根因。
- 分类集合封闭（A14），不允许临时新造分类。

## 5. 失败知识

本阶段没有真实 FAILED 场景，因此未生成 `FAILURE_KNOWLEDGE` 候选（现存 2 条来自 1.64/1.65，
未被本阶段修改）。这是“没有证据就不造知识”的预期结果，不是遗漏。
