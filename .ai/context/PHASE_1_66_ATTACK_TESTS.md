# Phase 1.66 — 攻击测试与安全验证

## 1. 测试总量（真实执行，非累加）

| 类 | 文件 | 检查数 | 结果 |
| --- | --- | --- | --- |
| 新增 Scenario Generator | `tests/test_scenario_generator.py` | 16 | 0 failures |
| 新增 Scenario Validator | `tests/test_scenario_validator.py` | 18 | 0 failures |
| 新增 Execution Planner/Pipeline | `tests/test_scenario_run.py` | 12 | 0 failures |
| 新增 Result Analyzer | `tests/test_result_analysis.py` | 14 | 0 failures |
| 新增 Knowledge Feedback | `tests/test_feedback.py` | 13 | 0 failures |
| 新增 Knowledge-Driven Mutation | `tests/test_mutation_candidates.py` | 16 | 0 failures |
| **新增小计** | 6 文件 | **89** | **89/89 PASS** |
| 1.65 回归 | source_analysis / dependency_graph / knowledge_store / planner | 69 | 69/69 PASS |

唯一检查数 = 89（新增）+ 69（1.65 回归）= 158；每个检查只执行一次，不存在“分批相加冒充唯一数”。
另有 1.56–1.64 回归 15 个文件（6 validator + 9 evaluation），本轮全部首次执行即通过（见 COMPLETION）。

## 2. A. Scenario Generator

| 攻击 | 用例 | 结果 |
| --- | --- | --- |
| 不存在的 Knowledge ID | G15 / V2 | 拒绝（`CONTRACT_NOT_FOUND` / 验证失败） |
| 已撤销 Knowledge | V11 | 拒绝 |
| 已过期 Knowledge | V10 | `KNOWLEDGE_STALE` |
| Contract 不匹配 | V3 | `CONTRACT_MISMATCH` |
| 来源 Digest 不匹配 | V9 | `SOURCE_STALE` |
| 缺少依赖 | V7 / V8 | `INCOMPLETE` / 未知边拒绝 |
| 无法验证的预期 | V6 / G8 / G9 | 拒绝 |
| 硬编码 Behavior 名单 | G14（源码扫描）+ G1/G15 | 无硬编码；未知 Behavior 直接失败 |

## 3. B. Scenario Validator

| 攻击 | 用例 | 结果 |
| --- | --- | --- |
| 路径越界（`..` / 非 Features） | V4 / V14 | 拒绝 |
| 伪造 `file:line` | V9 + 1.64 `_file_digest` | 拒绝 |
| 错误行号 | V9（digest 计算覆盖整文件，行号另由 schema 范围校验） | 拒绝/标记 |
| 源码被修改 | V9 | `SOURCE_STALE` |
| Contract 被替换 | V3 | `CONTRACT_MISMATCH` |
| Knowledge 冲突 | V12 | 阻断 |
| Knowledge 被撤销 | V11 | 拒绝 |
| 符号链接越界 | **未自动化**（Windows 权限受限） | 明确登记为未测 |

## 4. C. Execution Pipeline

| 攻击 | 用例 | 结果 |
| --- | --- | --- |
| Run ID 重复 | R2 / R8（两次规划 ID 不同） | 唯一 |
| Artifact 路径越界 | R4（output_root 必须在 `.ai/tmp/p166`） | 受限 |
| 跨 Run Artifact 混用 | 1.62 `test_run_workspace` W1–W24 | PASS |
| Run Manifest 被修改 | 1.56 `test_run_tests_evidence` E1–E7 | PASS |
| 执行中源码变化 | mutation `repo_guard`（265 文件）+ 执行侧 digest | 未发现变化 |
| Collector 指纹变化 | R3（四指纹非空） | 记录在 plan |
| 测试超时 | `timeout_policy` 记录；真实超时未触发 | 未触发（登记） |
| 进程异常退出 | R10/R11（被拒绝运行不产证据、状态可见） | 通过 |
| 输出目录污染 | R4/R5 + 批次级清理 | 通过 |
| `user://` 状态残留 | R5（run 维度 user dir tag） | 通过 |
| 证据被误删（本阶段真实事故） | R10 复现 + 修复后回归 | 已修 |

## 5. D. Result Analyzer

| 攻击 | 用例 | 结果 |
| --- | --- | --- |
| Execution PASS 但 Validator FAIL | A11/A12 | 不给 PASS；按证据判定 |
| Validator PASS 但 Evaluation FAIL | A11 | BEHAVIOR_VIOLATION / INCONCLUSIVE |
| Attestation 缺失 | A3 | INCONCLUSIVE |
| Evidence 缺失 | A4 | INCONCLUSIVE |
| Artifact 摘要错误 | 1.57 `test_evidence_cross_validation` | PASS |
| 测试设计错误误判为行为失败 | A9 / A10 | TEST_DESIGN_ERROR |
| 环境失败误判为行为失败 | A5 | ENVIRONMENT_BLOCKED |
| INFERENCE 冒充 VERIFIED | 1.64 `test_knowledge_store` | 拒绝 |

## 6. E. Knowledge Feedback

| 攻击 | 用例 | 结果 |
| --- | --- | --- |
| 伪造 Run ID | F5（缺 run_id 拒绝）+ F6（缺 Attestation 拒绝） | 拒绝 |
| 无 Artifact 的执行知识 | F7（execution claimed without evidence） | 拒绝 |
| INVALID Evidence 入库 | 1.64 digest 校验 + F7 | 拒绝 |
| 无效 Mutation 入库 | M10（SURVIVED 不入库）、schema 只认 KILLED | 拒绝 |
| 旧 Knowledge 被覆盖 | F10/F11 + 历史文件保留 | 冲突保留 |
| 冲突自动消失 | F11 / P14 | 保持 OPEN |
| 已撤销知识重新批准 | `approve()` 对 REVOKED 直接报错 | 拒绝 |
| LOCAL_REVIEW 冒充人类审批 | `review.scope = LOCAL_REVIEW` + note | 明确标注 |

## 7. 未覆盖（不得当成已测）

1. 符号链接越界（需要真实 symlink 创建权限）。
2. 真实运行中的测试超时/进程被杀（只有策略与状态机用例）。
3. 独立可信执行环境（`EXTERNAL_TRUSTED_RUNNER`）相关攻击——本阶段未部署该环境。
4. 并发多 Runner 同时写同一输出根（单机顺序执行，未构造并发场景）。
