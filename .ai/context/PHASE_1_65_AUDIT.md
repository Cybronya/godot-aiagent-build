# Phase 1.65 只读审计 — Behavior Learning & Knowledge Expansion

审计时间：2026-11-06。审计期间未修改任何项目文件；所有数字来自当前磁盘与命令输出。

## 1. 仓库基线

| 项 | 值 |
| --- | --- |
| HEAD | `dd3a0e4d5d0f6f47e3a9c729e3ce89190f019bd8` |
| 分支 | `master` |
| 已跟踪修改（` M`） | 20 |
| 已跟踪删除（` D`） | 33 |
| 未跟踪（`??`） | 971 |
| 暂存区 | 0 |
| 本阶段 Git 写操作 | 无（不 add/commit/push/reset/checkout/clean/restore/rebase） |

**与 Phase 1.64 完成报告的差异（重要）**：1.64 记录的是「53 tracked-modified / 987 untracked」。
当前是 20 修改 + 33 删除 + 971 未跟踪。差异来自**其他 Agent 对 `.ai/skills/foundation/godot-gdscript/code_library`
的清理**（删除 33 个 `references/**/RodZill4__material-maker__addons__gut__*.gd`，并改了 `INDEX.md`/`catalog.yaml`），
与本阶段无关。本阶段不触碰 `.ai/skills/**`，也不还原这些删除。

其他 Agent 修改范围（只读观察）：`.ai/skills/**`、`.ai/context/feature_graph.json`、`.ai/context/feature_index.json`、
`Features/{attack_emitter,knockback,save_game,sfx_pool,state_machine}/feature.yaml`、`Features/trigger_switch/template.yaml`、
`project.godot`、`.ai/tools/{evaluation/runner.py,scene_composer/feature_behavior_evidence.py,validator/validate.py}`。
这些是本阶段必须只读的既有工作。

Phase 1.64 交付（磁盘上确认存在）：`validator/execution/env_paths.py`、`run_p164_batch.py`、
`knowledge/behavior_verification/{store.py,build_records.py}`、`.ai/knowledge/behavior_verification/**`（7 条记录）、
`.ai/context/PHASE_1_64_*.md`（8 份）、`.ai/tmp/p164/**`。

当前测试状态：最近一次全量 `run_tests.py`（1.64 期间）为 **133 PASS / 3 FAIL / 2 INCOMPLETE**（138 个文件）。
3 个 FAIL 全部来自 `scene_composer` 对 8 个**未跟踪且缺 `template.yaml`** 的 Feature 脚手架的模板完备性断言；
2 个 INCOMPLETE 是 `test_end_to_end_generation.py`（>1800s 超时）与 `test_phase160_e2e.py`（需要 `--evidence-dir`）。
本阶段会重跑相关子集，不假设该结果仍然成立。

## 2. Knowledge Store 架构（现状）

只有一个实现：`.ai/tools/knowledge/behavior_verification/{store.py,build_records.py}`。

| 能力 | 现状 | 结论 |
| --- | --- | --- |
| 统一 Store | 有，但**一个 Behavior 一个文件**（`<feature>/<behavior>.json`） | 只能容纳「该 Behavior 的最新汇总记录」，不能按知识类型独立成条 |
| 数据模型 | schema `behavior_verification_knowledge` v1：`facts[]` 为扁平的 `{claim, source_type, source_ref}` | 无 knowledge_id、无单条状态、无 supersedes |
| ID 体系 | 无（以 `feature_id/behavior_id` 为键） | 缺 |
| 历史版本 | 有：覆盖前把旧记录整条 append 到 `*.history.jsonl`；且拒绝静默丢 fact | 可复用（这是本阶段要保留的硬约束） |
| 来源追溯 | 有：每条 fact 必须带 `source_type` + 非空 `source_ref`；`CONTRACT_FACT` 必须是 `Features/` 或 `binding:` | 可复用 |
| 内容摘要 | 仅 evidence 维度有 `bundle_digest`（来自矩阵），fact 级无 digest | 缺 |
| 事实/观察/推断区分 | 6 类：`CONTRACT_FACT / SOURCE_OBSERVATION / TEST_OBSERVATION / MUTATION_OBSERVATION / INFERENCE / UNKNOWN` | 缺 `RUNTIME_OBSERVATION / FAILURE_KNOWLEDGE / DEPENDENCY_KNOWLEDGE` |
| 冲突处理 | 无 | 缺 |
| 过期处理 | 只拒绝 contract_version 变更后的静默升级，无 stale 标记 | 部分 |
| 审批 | 无状态字段；`build_records.py` 直接写入 | 缺（自动生成即权威，这是 1.64 的已知弱点） |
| 调度 | 无 | 缺 |

现有 7 条记录：`VERIFIED_EXECUTION` 5 / `PARTIAL` 2；fact 来源 `CONTRACT_FACT 31 / TEST_OBSERVATION 12 /
MUTATION_OBSERVATION 8 / INFERENCE 7`；2 条含失败知识；6 条带未解决问题。

## 3. 已有学习相关模块（搜索结论）

搜索方向：Knowledge Graph / Knowledge Registry / Learning Memory / Workflow Knowledge / Pattern Knowledge /
Behavior Index / Learning Scheduler / Evaluation Knowledge / Provenance Store（`.ai/tools/**`、`.ai/skills/**`）。

| 候选 | 实际内容 | 可否复用 |
| --- | --- | --- |
| `knowledge/behavior_verification/` | 上述 Store | **复用**（来源类型、历史纪律、校验） |
| `gameplay_planner/` | 关卡/场景编排规划，不是学习规划 | 否（只借用「产出 plan.json + 明确 rationale」的形态） |
| `evaluation/coverage_matrix.py` | 八维覆盖矩阵，已含 evidence/signature/attestation/evaluation/holdout/mutation | **复用**（Planner 的覆盖输入） |
| `validator/provenance/**` | Ed25519 签名与信任根 | **复用**（来源可信度，不重造） |
| `validator/execution/**` + `env_paths.py` | 真实 Godot 执行 | **复用**（Pilot 的 Runtime 证据来源） |
| `.ai/memory/HISTORY.md`、`.ai/context/*.md` | 人类可读阶段记录，非机器可读知识 | 否 |

**结论**：不存在第二个 Knowledge Store，也不存在 Learning Planner。无需重建数据库；本阶段是**在现有
Store 之上做最小扩展**（按知识类型的记录层 + 审批/冲突/版本生命周期），并**继续使用同一个知识根目录约定**
（`.ai/knowledge/`），不去建第三个体系。

## 4. 正式 Behavior 集合（动态读取）

`Features/*/template.yaml#behavior` → **23 Feature / 60 Behavior**（不硬编码 60；生成器在契约新增未登记
Behavior 时会失败）。分类沿用 1.64 的 `phase_1_64_behavior_taxonomy.json`（A27/B3/C2/D4/E7/F17）。
每个 Behavior 的可用输入：

| 输入 | 位置 | 覆盖 |
| --- | --- | --- |
| Contract | `Features/<f>/template.yaml#behavior[id=…]` | 60/60 |
| Contract version | 矩阵 `contract_version`（内容哈希） | 60/60 |
| Binding | `validator/bindings`（61 条 APPROVED） | 60/60 |
| Implementation | `Features/<f>/*.gd`（排除 `test_*.gd`） | 60/60 存在 |
| Dependencies | `Features/<f>/feature.yaml#requires/provides` | 部分 |
| Tests | `Features/<f>/test_*.gd` | 存在但不参与八维判定 |
| Evidence / Signature / Attestation / Evaluation | 矩阵 | 各 12/60 |
| Mutation | `.ai/tmp/p164/mutation*/reports`（12 条，10 Behavior） | 10/60 |
| Holdout | 1（`openable_door/open`） | 1/60 |
| Knowledge | Store | 7/60 |

## 5. Knowledge 数据质量

- **可信**：所有 fact 都有 `source_ref`，`CONTRACT_FACT` 指向真实 `template.yaml#behavior=…`，evidence fact 带
  bundle digest + run_id。
- **弱点 1（本阶段必须解决）**：记录是「汇总」，无法表达「这条结论是 2026-11-04 从 M11 学到的，之后被新 Run 取代」。
- **弱点 2**：`confidence` 用的是 `VERIFIED_EXECUTION / PARTIAL`（覆盖语义），不是知识可信度
  （`VERIFIED / HIGH / MEDIUM / LOW / UNKNOWN`），二者被混在同一个字段里。
- **弱点 3**：`INFERENCE` 没有 `derivations`（从哪几条事实推出），无法审计。
- **弱点 4**：自动生成即权威。1.64 的 7 条记录没有任何审批记录。
- **观察**：`openable_door/open` 的 fact 中 `MUTATION_OBSERVATION` 指向 `M05`，而矩阵最新用的是 `M12`；
  这不是错误（两条都 KILLED），但说明「同一 Behavior 多条 mutation」缺少显式排序/取代语义。

## 6. 来源追溯与可信度边界

可追溯：fact→`source_ref`；evidence→bundle+digest+sidecar 签名；attestation→attestation_digest。
**不可声称**：签名通过 ≠ 源码分析正确；SHA256 存在 ≠ 内容已验证；本地证据 ≠ 执行者身份真实
（`LOCAL_ISOLATED` 边界未解）。本阶段所有静态分析结论必须标 `SOURCE_OBSERVATION`，且带
`static_only=true`，禁止写成 Runtime。

## 7. 遗留技术债审计（Phase 1.64 三项）

| # | 事项 | 是否仍存在 | 影响学习结果 | 影响来源可信度 | 本阶段处置 |
| --- | --- | --- | --- | --- | --- |
| 1 | 矩阵评估归因 P2（`eval_dirs = args.eval_dir or [EVAL_REPORT_DIR]`，`glob("<dir>/*/evidence_report.json")`） | **是**（`coverage_matrix.py:564`、`:285`） | 会：Planner 若读默认矩阵，评估状态可能被别的批次污染，进而错判 `NO_TEST_SCENARIO` | 是（会把无关报告的 PASS 归给某 Behavior） | **修**：Planner 只接受显式矩阵路径，并在读入时校验每行 `evaluation.report` 与 `run_id` 归属；不改 1.63 矩阵实现（避免扩大范围），在 Planner 侧做归属校验并新增回归测试 |
| 2 | `i_frames.gd::_on_window_end` 的 `_active = false` 缩进异常（1 tab，其余在 if 内） | **是**（`Features/i_frames/i_frames.gd:78`） | 轻微：Source Analysis 会把它记为「get 到但不在守卫块内」的观察 | 否（源码事实仍真实） | **不修源码**（语义未证明有缺陷，且改产品源码超出本阶段授权）；作为 `SOURCE_OBSERVATION` 记录 + 登记 |
| 3 | 全量入口 3 FAIL / 2 INCOMPLETE | **是**（FAIL 来自 8 个未跟踪缺 `template.yaml` 的脚手架；INCOMPLETE 为超时与参数要求） | 否（与本阶段模块无关） | 否 | **不修**；回归时只跑相关子集并如实标注未执行 |

结论：只有 #1 是学习链路的直接风险，本阶段最小化处理（Planner 侧校验 + 测试），不重写矩阵。

## 8. 推荐架构

```text
Features/*/template.yaml#behavior  ──┐
Features/*/*.gd (真实源码)          ──┼─→ source_analysis.py ──→ .ai/learning/source_analysis/<f>/<b>.json
feature.yaml (requires/provides)    ──┘            │
                                                  ↓
                     dependencies.py ──→ .ai/learning/behavior_dependency_graph.json
                                                  │
Matrix(八维) + mutation reports + store(1.64) ─────┼─→ extract.py ──→ candidates (PENDING_REVIEW)
                                                  │                        │
                                                  │                    knowledge_v2.py（审批/冲突/版本/撤销）
                                                  │                        ↓
                                                  └─→ planner.py ──→ .ai/learning/learning_plan*.json
                                                                           ↑
                                                          pilot.py 用两轮 plan diff 证明数据流
```

扩展而非重建：

- `knowledge_v2.py` **import** `behavior_verification.store` 的 `SOURCE_TYPES`/`validate` 规则，新增 3 类来源与按类型
  记录（`knowledge_id`、`verification_status`、`supersedes`、`lifecycle_events`）。1.64 的 7 条记录保留原样、不迁移、不覆盖。
- 所有静态结论 `static_only=true`；无 Run/Evidence 时不得写 `RUNTIME_OBSERVATION`。
- 自动产出默认 `PENDING_REVIEW`；`approve()` 必须带 reviewer + reason，且拒绝审批来源不合法的记录。
- 冲突保留双方（`conflicts/*.json`），不自动选最新。

## 9. 本阶段范围声明

做：Source Analysis、Dependency Graph、Knowledge 扩展与审批、Learning Planner、3–5 个 Behavior 的真实 Pilot、
攻击测试、9 份文档。

不做：批量处理 60 个 Behavior、自动改产品源码/契约/Binding、自动批准 Baseline/Holdout、迁移或删除 1.64 知识、
修 1.63 矩阵实现、修 `i_frames.gd` 缩进、提交 Git。
