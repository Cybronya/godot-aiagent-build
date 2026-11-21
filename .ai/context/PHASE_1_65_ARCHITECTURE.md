# Phase 1.65 架构 — Behavior Learning Engine

## 1. 结论

不新建平行知识体系。本阶段在 Phase 1.64 的 Knowledge Store 之上做**最小扩展**，并把
「读源码 → 建依赖 → 抽知识 → 排任务 → 跑 Pilot」串成一条可审计的链路。

```text
Features/*/template.yaml#behavior ─┐
Features/*/*.gd（真实源码）        ─┼→ source_analysis.py ─→ .ai/learning/source_analysis/<f>/<b>.json
feature.yaml（requires/provides）   ─┘                                │
                                                                     ↓
                                        dependencies.py ─→ .ai/learning/behavior_dependency_graph.json
                                                                     │
Matrix(八维) + mutation 报告 + 1.64 Store ──┬─→ extract.py ─→ candidates (PENDING_REVIEW)
                                            │                       │
                                            │            knowledge_v2.py（门禁/审批/冲突/版本/撤销）
                                            │                       ↓
                                            └─→ planner.py ─→ .ai/learning/learning_plan.json
                                                                    ↑
                                                    pilot.py 两轮 plan diff（数据流证明）
```

## 2. 模块

| 模块 | 职责 | 不做什么 |
| --- | --- | --- |
| `learning/gd_parse.py` | GDScript 轻量解析：类/信号/变量/函数体、调用、emit/connect、set_deferred、FileAccess、守卫、动态调用 | 不做类型推导，不用名称猜语义 |
| `learning/paths.py` | 项目根、正式契约、契约版本（复用 `binding_candidates.contract_digest`）、实现文件定位、分类与风险 | 不猜源码路径，不硬编码 60 |
| `learning/source_analysis.py` | 逐 Behavior 的入口/状态/条件/事件/副作用/失败路径 + `unresolved_questions` | 不把静态观察写成运行事实（`static_only=true`） |
| `learning/dependencies.py` | 行为依赖图、类型化边、来源、SCC/循环分类、查询 | 不按名字建边；循环不自动判错 |
| `learning/knowledge_v2.py` | 类型化知识记录、来源门禁、审批、冲突、版本（SUPERSEDED/REVOKED/ARCHIVED）、过期 | 不删除历史；不自动解决冲突；不把推断标 VERIFIED |
| `learning/extract.py` | 契约/源码/依赖/矩阵/mutation/历史失败 → 候选知识 | 无证据不造 Test/Runtime 观察 |
| `learning/planner.py` | 缺口识别、任务生成、优先级与解释、阻塞、已完成排除 | 不执行高风险动作；不自动改源码 |
| `learning/pilot.py` | 3–5 个 Behavior 的闭环、候选场景、评审日志、两轮计划 diff | 不新跑 Godot 冒充新证据；不自动批准 |

## 3. 与 1.64 的关系

| 1.64 资产 | 本阶段用法 |
| --- | --- |
| `knowledge/behavior_verification/store.py` | 保留不变；`knowledge_v2` 沿用其来源类型语义与「历史不覆盖」纪律 |
| 7 条汇总记录（`.ai/knowledge/behavior_verification/**`） | 只读引用（FAILURE_KNOWLEDGE 提取失败模式），不迁移、不改写 |
| 覆盖矩阵 | Planner 的唯一覆盖输入（必须显式给路径） |
| Provenance / Attestation | 作为 `TEST_OBSERVATION` / `RUNTIME_OBSERVATION` 的来源门禁 |
| Mutation 报告 | `MUTATION_OBSERVATION` 的唯一来源，只接受 `MUTANT_KILLED` |
| `env_paths.py` | Planner 的环境探测（Godot 不可用 → 执行类任务 BLOCKED） |

为什么扩展而不是重建：1.64 的 Store 已经把「来源类型 + 历史不覆盖 + 契约版本」做对了，
缺的是**按类型的记录粒度**、**审批状态**与**冲突/撤销语义**。新增一个按类型的记录层比迁移已有
7 条记录风险小，也避免出现两个互不兼容的知识库。

## 4. 知识记录（Schema v1）

文件：`.ai/knowledge/behavior_learning/{candidates,records,conflicts}/<id>.json`

| 字段 | 说明 |
| --- | --- |
| `knowledge_id` | `k-` + sha256(feature, behavior, type, key, content_digest)[:16]，内容决定 id |
| `knowledge_type` | 9 类：CONTRACT_FACT / SOURCE_OBSERVATION / TEST_OBSERVATION / RUNTIME_OBSERVATION / MUTATION_OBSERVATION / FAILURE_KNOWLEDGE / DEPENDENCY_KNOWLEDGE / INFERENCE / UNKNOWN |
| `key` | 槽位（`entry_points` / `guards` / `events` / `persistence` / `dependencies` / `mutation:<id>` / `legacy_failure:<n>` …），冲突与去重都按 (feature, behavior, type, key) |
| `content` + `content_digest` | 结论本体与规范化摘要 |
| `source_references[]` | `{kind, reference, digest}`；kind ∈ CONTRACT/SOURCE/EVIDENCE/ATTESTATION/MUTATION_REFERENCE |
| `contract_version` / `implementation_digest` / `evidence_digest` / `run_id` | 适用时必填；不适用为空 |
| `confidence` | VERIFIED / HIGH / MEDIUM / LOW / UNKNOWN（知识可信度，不是覆盖率） |
| `verification_status` | PENDING_REVIEW → APPROVED → SUPERSEDED / REVOKED / ARCHIVED |
| `supersedes` / `superseded_by` | 版本链，旧记录不删除 |
| `derivations` | INFERENCE 的推导来源（必须是已存在的 knowledge_id） |
| `review` | reviewer / reason / at / scope=`LOCAL_REVIEW` |
| `lifecycle_events[]` | CREATE / APPROVE / SUPERSEDE / REVOKE / ARCHIVE（带时间与理由） |

## 5. 门禁（代码强制，不可绕过）

| 知识类型 | 必需来源 | 额外规则 |
| --- | --- | --- |
| CONTRACT_FACT | CONTRACT_REFERENCE | 引用必须以 `Features/` 开头 |
| SOURCE_OBSERVATION | SOURCE_REFERENCE | 文件必须存在；提供 digest 时必须匹配当前文件 |
| TEST_OBSERVATION | EVIDENCE_REFERENCE | 必须有 `run_id` |
| RUNTIME_OBSERVATION | ATTESTATION_REFERENCE | 必须有 `run_id` |
| MUTATION_OBSERVATION | MUTATION_REFERENCE | `mutation_verdict` 必须 `MUTANT_KILLED` |
| FAILURE_KNOWLEDGE | MUTATION/TEST/EVIDENCE 之一 | 必须能追溯失败产物 |
| DEPENDENCY_KNOWLEDGE | SOURCE 或 CONTRACT 引用 | — |
| INFERENCE | 无（但必须有 `derivations`） | 不能标 VERIFIED；derivation 必须存在 |
| UNKNOWN | 无 | 必须写 `reason` |

审批：`approve(id, reviewer, reason)`；未解决冲突时拒绝；新记录审批会把同槽旧记录标
`SUPERSEDED` 并写 `superseded_by`（保留文件）。`revoke` 后不能再次审批。

## 6. 安全边界

- 学习系统只读产品源码/契约/Binding/证据；**唯一写入**是 `.ai/learning/**`、`.ai/knowledge/behavior_learning/**`。
- 不自动改 `Features/**`、不自动改契约/Binding/Baseline/Holdout、不做 Git 写操作。
- Pilot 不新跑 Godot：`TEST_OBSERVATION` / `RUNTIME_OBSERVATION` 只关联 1.64 已签名、已出 attestation 的真实 Run；
  没有证据的 Behavior 明确留 `NO_RUNTIME_OBSERVATION`。
- 「本地审批」（`LOCAL_REVIEW`）不等于人类审批者身份已验证，记录里写清。

## 7. 输出物

| 路径 | 内容 |
| --- | --- |
| `.ai/learning/source_analysis/<feature>/<behavior>.json` | 每个 Behavior 的源码分析（60 份） |
| `.ai/learning/behavior_dependency_graph.json` | 节点/边/循环/未解析依赖/统计 |
| `.ai/learning/learning_plan.json` + `.md` | 学习计划（任务/优先级/阻塞/排除） |
| `.ai/learning/pilot/{selection,scenarios,review_log,plan_v1,plan_v2,plan_diff,pilot_result}` | Pilot 全链产物 |
| `.ai/tmp/p165/pilot_sandbox/**` | 隔离知识根里的可重复 Plan v1→v2 演示 |
| `.ai/knowledge/behavior_learning/**` | 类型化知识（45 条：40 APPROVED + 5 SUPERSEDED） |
