# Phase 1.66 — 完成报告

日期：2026-11-07
HEAD：`dd3a0e4d5d0f6f47e3a9c729e3ce89190f019bd8`（分支 `master`，未提交任何改动；`git diff --cached` 为空）

## 1. 一句话结论

Knowledge 已经驱动**真实**测试：5 个 Behavior 的场景真实执行、证据/证据验证/Attestation/评估四层齐全，
结果回流为 15 条已审批知识，第二轮 Planner 因真实结果从 277 降到 276。
同时本阶段发现并修复了 2 个真实链路缺陷（证据被单场景运行误删、归档知识冒充写入）。

## 2. 验收清单

### A. 审计
- [x] 真实仓库状态（HEAD/分支/工作区/环境/Godot 4.7）已对账：`PHASE_1_66_AUDIT.md`
- [x] Phase 1.65 交付已审计（learning 工具、候选结构、planner 路径）
- [x] 复用 1.64 Knowledge Store（无平行 Store）
- [x] 复用 1.56–1.62 执行链（无平行 Runner）
- [x] Phase 1.64 技术债已审计（见 §5）

### B. Scenario Generation
- [x] 知识驱动生成 5 条场景（4 条规则族）
- [x] 每条有 knowledge_refs / source_refs / dependency_refs
- [x] 动作与期望可执行、可验证（1.41 协议词汇）
- [x] 无硬编码 Behavior 名单（G14 源码扫描 + G15 未知 Behavior 失败）
- [x] 无无来源场景（G5/G6 只接受 APPROVED）

### C. Scenario Validation
- [x] Contract / Source Digest / Knowledge 状态 / Dependency / Environment 五类检查
- [x] 无效场景被拒绝（18 项攻击测试）

### D. Execution
- [x] 真实 Godot Runner（非模拟）：5/5 PASSED
- [x] 唯一 Run ID（R2/R8）
- [x] Artifact 与 Run 绑定（1.56 E1–E7 + 1.57 交叉验证）
- [x] 输出目录隔离（run root + user:// tag）
- [x] 结果真实记录（`scenario_results.json` label=P4）
- [x] 失败分类明确（9 分类；本轮无 FAILED）

### E. Evidence / Evaluation
- [x] Evidence 真实采集 5/5
- [x] Artifact Cross-Validation PASS
- [x] 签名状态按实际记录
- [x] Execution Attestation 5/5（LOCAL_ISOLATED）
- [x] Evaluation Adapter 5/5 VERIFIED_PASS
- [x] 四层结果分别记录
- [x] LOCAL_ISOLATED 边界明确（未升级）

### F. Knowledge Feedback
- [x] 真实结果进入候选知识（15 条）
- [x] 来源完整（Evidence + Attestation + run_id + digest）
- [x] 历史版本保留（10 ARCHIVED / 5 SUPERSEDED，未删除）
- [x] 冲突保留（`conflicts_open=0`，历史 5 条 RESOLVED 保留）
- [x] 无效证据无法入库（F5/F6/F7）
- [x] 候选不自动 APPROVED（F2）
- [x] 第二轮 Planner 受真实结果影响（277→276，移除 NO_TEST_SCENARIO 任务）

### G. Mutation
- [x] 生成 19 个知识驱动候选（17 VALID 锚点，2 INVALID 标注保留）
- [x] 隔离副本执行（harness `require_inside`）
- [x] Control / Mutation / Recovery 完整，`restored_byte_for_byte=true`
- [x] Repo Guard 未发现非预期修改（265 文件，`changed=false`）
- [x] INVALID 不计 KILLED（2 个 INVALID 锚点未执行；SURVIVED 不入库）
- [x] 1 个 `MUTANT_KILLED`（`mc-55bda008e9123f41`），知识 `PENDING_REVIEW`

### H. 测试
- [x] 新增测试 89/89 PASS（6 文件）
- [x] 1.65 回归 69/69 PASS（4 文件）
- [x] 1.56–1.64 回归 15 文件 PASS（validator 6 + evaluation 9）
- [x] 攻击测试覆盖 A–E（含 4 项明确未覆盖）
- [x] 真实 Godot E2E 一批 5 场景
- [x] 未执行项已登记（符号链接、真实超时、外部可信 Runner、并发 Runner、其余 52 Behavior）
- [x] 无虚报：未执行不计 PASS，官方契约 FAIL/INCOMPLETE 单独记录

## 3. 交付文档

```text
.ai/context/PHASE_1_66_AUDIT.md
.ai/context/PHASE_1_66_ARCHITECTURE.md
.ai/context/PHASE_1_66_SCENARIO_GENERATION.md
.ai/context/PHASE_1_66_SCENARIO_VALIDATION.md
.ai/context/PHASE_1_66_EXECUTION_REPORT.md
.ai/context/PHASE_1_66_RESULT_ANALYSIS.md
.ai/context/PHASE_1_66_KNOWLEDGE_FEEDBACK.md
.ai/context/PHASE_1_66_MUTATION_REPORT.md
.ai/context/PHASE_1_66_LEARNING_PILOT.md
.ai/context/PHASE_1_66_ATTACK_TESTS.md
.ai/context/PHASE_1_66_COMPLETION.md
```

## 4. 代码与产物清单

新增工具（`.ai/tools/learning/`）：`scenario_generator.py`、`scenario_validate.py`、
`scenario_run.py`、`result_analysis.py`、`feedback.py`、`mutation_candidates.py`。

扩展：`knowledge_v2.py`（4 类型 + `revive()`）、`planner.py`（`scenario_evidence()` /
`--scenario-results` / `_driven_by` 新类型分支）。

新增测试：`tests/test_{scenario_generator,scenario_validator,scenario_run,result_analysis,feedback,mutation_candidates}.py`。

新增产物：`.ai/learning/{scenarios/**,scenarios.json,scenario_validation.json,scenario_results.json,
result_analysis.json,results/**,feedback.json,mutation_candidates.json,learning_plan.json,
learning_plan_before_p166.json}`、`.ai/tmp/p166/**`。

## 5. Phase 1.64 技术债处理

| # | 问题 | 结论 |
| --- | --- | --- |
| 1 | Coverage Matrix 评估归因缺陷 P2 | 仍存在；本阶段 Mutation 复现同类现象（契约数量不匹配 → `INVALID_EVIDENCE` 而非 `VERIFIED_FAIL`）。未修：属 1.64 评估器语义，改动会波及 1.58/1.64 判定；已在 MUTATION_REPORT §4 登记 |
| 2 | `i_frames.gd:78` 缩进异常 | 未修：禁止改产品源码；不影响本阶段场景执行 |
| 3 | 全量入口 3 FAIL / 2 INCOMPLETE | 未重跑全量（耗时 ~57 分钟）；现存 133c 日志为 83/83 ALL PASS，133b 失败源于 ownership 冲突。本阶段改用分套件回归，未虚报全量结果 |

## 6. 剩余风险

1. 5 个场景的官方契约判定为 FAIL/INCOMPLETE（设计差），如果未来把扩展期望写进正式契约，
   需要先修改契约并重新基线化——本阶段**没有**这么做。
2. `MUTATION_OBSERVATION` 仍 `PENDING_REVIEW`，未进入 Planner 的 `DESIGN_MUTATION` 排除逻辑。
3. `driven_by_knowledge` 当前为 0（唯一任务被真实证据消解），指标下降属数据结果，已解释。
4. 15 条反馈知识由单一本地 reviewer 审批（`LOCAL_REVIEW`），不能替代人工复核。
