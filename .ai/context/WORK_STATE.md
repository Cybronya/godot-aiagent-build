# Work State


当前工程状态。（最近一次直接更新：Phase 1.68.3.1 / Phase 5 Final Closure；本文件在 Phase 1.38 之后**未逐阶段回溯**，
Phase 1.39–1.63 的事实以其审计/完成报告为准，最新见 `PHASE_1_62_COMPLETION.md`、
`PHASE_1_63_COMPLETION.md` 与 `PHASE_1_64_COMPLETION.md`。）

## Phase 1.68.3.1：Phase 5 Final Closure（已完成并正式关闭，未提交）

- **范围**：负责人接受 Phase 3 Dependency Audit §7 作为 Phase 5 权威回归范围；独立
  `PHASE_1_68_3_1_PHASE_5_REGRESSION_PLAN.md` 不存在，未追溯创建。
- **结果**：Batch A/B/C/D/F 全部 PASS，30/30 tests、2,124 PASS、0 FAIL、0 timeout/SKIP/BLOCKED；
  Batch E 为 NOT_APPLICABLE；Batch R 为 NOT_EXECUTED – Optional。
- **完整性**：Feature 265、Historical Evidence/Attestation 828、Critical 4、Code 3、Protocol 3
  全部 OK；Batch D 496 个受保护文件无变化；历史 workspace 5→5。
- **Batch D 限制**：测试 PASS，但执行前 Runtime 完整顶层清单未保留，无法对全部临时文件
  做完整前后归因；负责人接受该限制，不要求重跑，且不宣称 Runtime 完全无变化。
- **Batch R**：保持 NOT_EXECUTED；Phase 2 target PASS 不等同于 Phase 5 Batch R 已执行。
- **关闭**：技术回归已完成并正式关闭；未执行测试、未清理 Runtime、未修改受保护文件、
  未提交/推送 Git、未进入下一 Phase。详见 `PHASE_1_68_3_1_PHASE_5_FINAL_CLOSURE.md`。

## Phase 1.66：Knowledge-Driven Test Generation & Execution（已实施并实测，未提交）

- **审计**：HEAD `dd3a0e4` 未变；`git diff --cached` 为空；Godot 4.7-stable console；
  详见 `PHASE_1_66_AUDIT.md`。
- **生成**：5 个 Behavior / 4 条规则族，全部 VALID；无硬编码 Behavior 名单，
  每条场景带 knowledge_refs + source_refs（依赖场景另有 dependency_refs）。
- **验证**：7 状态验证（VALID/INVALID/INCOMPLETE/ENVIRONMENT_BLOCKED/SOURCE_STALE/
  KNOWLEDGE_STALE/CONTRACT_MISMATCH），18 项攻击用例。
- **真实执行**：label `P4`，5/5 真实 Godot（11.6–12.5s/场景），Execution PASSED、
  Evidence EVIDENCE_VERIFIED、Attestation ATTESTED_VERIFIED（LOCAL_ISOLATED）、
  Evaluation VERIFIED_PASS；官方契约 PASS 1 / FAIL 2 / INCOMPLETE 2（单独记录，不冒充）。
- **分析**：CONTRACT_CONFIRMED 1 / SOURCE_CONFIRMED 3 / BEHAVIOR_CONFIRMED 1；无 FAILED。
- **回流**：15 条候选（场景/执行/行为各 5）全部 APPROVED（`phase_1_66_local_review`，
  LOCAL_REVIEW）；知识库 71 条（55 APPROVED / 5 SUPERSEDED / 10 ARCHIVED / 1 PENDING）。
- **计划**：277 → 276（移除 `NO_TEST_SCENARIO` 设计任务），`scenario_evidenced_behaviors=5`；
  `driven_by_knowledge` 非空任务 1 → 0（唯一一条被真实证据消解，已解释）。
- **Mutation**：19 候选（17 VALID / 2 INVALID 保留未执行）；`mc-55bda008e9123f41`
  `MUTANT_KILLED`（control 1 / mutant 2，恢复逐字节一致，repo_guard 265 文件未变），
  知识 `PENDING_REVIEW`；KILLED 的判定依据是 `INVALID_EVIDENCE`（P2 归因问题，已登记）。
- **测试**：新增 89/89（6 文件）；1.65 回归 69/69；1.56–1.64 回归 15 文件全过。
- **修复的真实缺陷**：单场景运行误清 evidence 目录（已改为批次级清理）；
  归档知识冒充写入（新增 `revive()` + 引用刷新）。
- **未做**：其余 52 个 Behavior、失败/变异驱动场景模板、1.64 三项技术债、人类审批、
  全量 `run_tests.py` 重跑（~57 分钟）。

## Phase 1.65：Behavior Learning & Knowledge Expansion（已实施并实测，未提交）

- **审计**：仓库 HEAD 未变；工作区 20 修改 + 33 删除 + 981 未跟踪（删除/修改均来自其他 Agent 的
  skills 清理等，本阶段未改任何既有文件）。确认只有 1 个 Knowledge Store、无现成 Learning Planner。
- **Source Analysis**：60/60 分析（5 COMPLETE、50 PARTIAL、5 `SOURCE_ENTRY_AMBIGUOUS`），
  入口 57 条；每条带 `file:line`，全部 `static_only=true`；契约/源码命名不一致、harness 驱动、
  动态调用都进 `unresolved_questions`。
- **Dependency Graph**：60 节点 / 118 边（97 源码 + 21 契约），类型含 EMITS/RECEIVES 各 21、
  REQUIRES_PRECONDITION 21、SHARES_STATE 50、WRITES_STATE 3、PERSISTS/RESTORES 各 1；
  2 个 SCC（Health `hub_component`、save `persistence_pair`），1 条未解析契约依赖。
- **Knowledge**：`.ai/knowledge/behavior_learning/**`（45 条，40 APPROVED + 5 SUPERSEDED，
  5 冲突已显式解决），门禁：CONTRACT_FACT→Features/、SOURCE→文件+digest、MUTATION→仅 KILLED、
  INFERENCE→derivations 且不得 VERIFIED、冲突未解决拒绝审批；旧记录/被撤销记录不删除。
- **Planner**：`priority = 3*severity + risk/2 + upstream + failure_bonus - cost`，任务 277，
  排除已完成 10，矩阵必须显式给出（不接受默认扫描）。
- **Pilot**：5 个 Behavior（A/C/F），4 个关联 1.64 真实 Run（签名+attestation+评估均通过），
  `trigger_switch/latch_once` 无 Run 则保留缺口；12 条候选场景全部 `executed=false`；
  隔离根演示 287→277 任务、`excluded 0→10`、5/5 行为任务集合变化。
- **测试**：新增 68 项全过（17+16+20+15）；回归 77 项全过（1.64 knowledge 18、matrix 15、
  bindings 26、env_paths 18）。**未跑**：`run_tests.py` 全量、新 Godot 采集、mutation 重跑。
- **未做**：其余 55 条 Behavior 知识、5 条入口歧义、1.64 的 P2/缩进/全量入口三项技术债、
  候选场景实际执行、人类审批。

## Phase 1.64：系统性扩大 L5 行为覆盖（已实施并实测，未提交）

- **前置修复**：1.62 两个 E2E Runner 的 `_PROJECT_ROOT` 少算一层（得到 `.ai`），Godot 只能靠
  `GODOT_BIN`。新增 `validator/execution/env_paths.py` 统一解析（GODOT_BIN → 项目配置
  `runtime_playtest.godot_binary` → 项目相邻目录 → PATH），缺失时明确 `ENVIRONMENT ERROR`；
  两个 Runner 改用它，check 数量与语义不变。回归：单 Feature 20 checks / 多 Feature 3 条 /
  1.63 三 Feature 24 checks，全部 0 失败，均未设 `GODOT_BIN`。
- **分类与计划**：60 条 Behavior 全部有主类/次类/依据（A 27、B 3、C 2、D 4、E 7、F 17），
  风险分公式写进 `PHASE_1_64_VERIFICATION_PLAN.md`；清单由生成器产出，契约新增未登记行为
  会让生成器直接失败（不给默认分类）。
- **Batch 1（3 Feature / 6 Behavior）**：`run_p164_batch.py` 复用 1.63 全链，expected 逐字来自
  已审批 Binding；真实 Godot（replay=2，per-run `user://`）→ bundle → 签名 → manifest →
  attestation → 逐 Behavior Evaluation，21 项检查 0 失败，6/6 `VERIFIED_PASS`。
- **同口径趋势**：Evidence/Signature/Attestation/Evaluation 8→12，Mutation Killed（Behavior）
  9→10，Fully Covered 0→1（`openable_door/open`）；数字由两次同脚本矩阵快照得出，
  不使用 1.63 的默认评估扫描（会串批次，审计 P2）。
- **Mutation**：catalog 10→12（M11 无敌窗口不归还门、M12 门幂等守卫反转），两条真实 KILLED；
  1.59/1.63 的 10 条全量复现 KILLED；control/recovery 均 PASS、逐字节恢复、`repo_guard.changed=false`。
- **Knowledge**：`.ai/knowledge/behavior_verification/`，7 条记录（含 `latch_once`），事实分
  CONTRACT_FACT / TEST_OBSERVATION / MUTATION_OBSERVATION / INFERENCE；store 拒绝未知来源、
  丢弃旧事实、契约版本静默升级；历史版本追加到 `.history.jsonl`；M04/M06 失败根因保存为 RESOLVED。
- **全量入口**：`run_tests.py` 跑完 138 个文件 → 133 PASS / 3 FAIL / 2 INCOMPLETE。3 个 FAIL 是
  `scene_composer` 对 8 个未跟踪、缺 `template.yaml` 的 Feature 脚手架的模板完备性断言；
  2 个 INCOMPLETE 是 `test_end_to_end_generation.py`（>1800s 超时）与 `test_phase160_e2e.py`
  （需 `--evidence-dir`，被当单元测试调用）。均非本阶段引入，未修。
- **未做**：B2–B6 批次、48 条无证据 Behavior、1.63 矩阵评估归因修复。

## Phase 1.63：Behavior Binding Expansion & Coverage Reconciliation（已实施并实测，未提交）

- **Binding 全覆盖**：`validator/binding_candidates.py`——候选生成（expected 只来自契约，
  缺失即 BLOCKED_MISSING_EXPECTED）→ 显式审批（DRAFT→PENDING_REVIEW→APPROVED，
  独立登记表 + Ed25519 签名，scope=approve_binding）→ 晋升（旧绑定 SUPERSEDED 不双活）。
  6→60 条绑定（覆盖整个动态支持集，23F/60B 动态读取）。契约漂移/候选篡改/跳步审批全部拒绝。
- **M04/M06 根因修复**：M04=探针「满足即停」+ 契约缺尾部帧推进 → latch_once 契约补
  advance_frames（BND-005 走重审）；M06=user:// 跨 run 残留 → 采集器 per-run
  `--user-dir-tag` 隔离（缺省不变）。全量 mutation **10/10 KILLED、0 INVALID**
  （新增 M09 i_frames、M10 contact_damage 同样 KILLED）。
- **覆盖矩阵**：`evaluation/coverage_matrix.py`——八维独立状态（contract/binding/
  evidence/signature/attestation/evaluation/holdout/mutation）、动态分母、null 不造假、
  --strict 退出码 2。快照：Evidence/Signature/Attestation 各 8/60、Holdout 1/60、
  Mutation Killed 9/60、Fully Covered 0/60（每行带缺失原因与下一步）。
- **真实 E2E（持久化版）**：`run_p163_e2e.py`——3 Feature（状态转换/事件传播/持久化）
  全链 24 checks 0 failures，产物（bundle+签名+manifest+attestation）持久化于
  `.ai/tmp/p163_e2e/`；真实独立信任根（区别于 1.62 的临时信任根）。
  Holdout：P163-HOLDOUT v2 签名封存。
- **修复**：trace_bindings 放宽检查的同目标多检查覆盖缺陷（x/y 轴误报）；
  holdout VALIDATED→VALIDATED 幂等；test_trace_bindings/test_cross_binding 断言改动态口径。
- 新增测试 41 项全过；回归 519 项全过（1.56–1.62 全套 + validate.py 0e/17w）。
- 信任边界：审批记录密码学完整性 ✔；**审批者人类身份真实性仍属流程审计**（同权限
  边界，LOCAL_ISOLATED）。
- 报告：`PHASE_1_63_COMPLETION.md`、`PHASE_1_63_COVERAGE_REPORT.md`、
  `PHASE_1_63_ATTACK_TESTS.md`、审计 `PHASE_1_63_AUDIT.md`。

## Phase 1.61：独立信任根与来源签名（已实施并实测，未提交）

- **缺口**：Phase 1.60 之后系统仍无法证明审批者/签发者身份真实性——同权限攻击者可
  同时改写 Baseline 内容、摘要、审批登记表、Evidence 与 Holdout 封存记录。
- **做法（全加法）**：新增 `validator/provenance/`（signature_schema / trust_store /
  key_metadata / signing / verification / provenance_cli）：Ed25519（PyNaCl 1.6.2，
  不自研原语）detached 规范化封套签名，对象类型/ID/版本/摘要/scope 全部在签名消息内。
  独立信任根 = **工作区之外**的用户级文件 `~/.provenance_trust/<项目 slug>/`（本机已
  真实建立，密钥 `PROVKEY-696f89a140eba658`）；信任根路径解析进工作区 → 拒收
  （fail-closed）。接入：Baseline `use_baseline_trusted()`（登记条目内封套 + 审批元数据
  交叉核对）、Evidence sidecar `<bundle>.sig.json` + `load_verified(provenance_policy=)`
  追加门禁（封堵"改内容+重算 integrity 哈希"逃逸路径）、Holdout `seal_dataset_signed()`
  + 消费前验证（失败细分 holdout_signature_*，验证不过不发生 record_usage）。
  密钥生命周期 ACTIVE/RETIRED/REVOKED + 轮换 + 撤销（撤销只降级、不可复活）。
- **实测（2026-11-04，HEAD `dd3a0e4`）**：新增 5 套测试 142 项全过（core 57 + baseline
  签名 21 + evidence 签名 16 + holdout 签名 16 + 攻击模拟 32）；A01–A18 攻击场景全拒
  （A16 核心：工作区内伪造公钥/env 指入工作区一律拒收，外部信任根不受影响）；私钥泄露
  检查 K1–K6 全过。回归 485 项全过（1.60 四套+E2E 97、1.58 四套 124、1.57 34、1.56 54、
  比较器 100、1.59 两套 66）、validate.py 0 error / 17 warning 不变。真实 Godot 端到端：
  4 Feature 新鲜采集 → 真实密钥签署 → `--require-signature` E1/E2/E3 全 VERIFIED_PASS/
  exit 0；篡改副本（重算哈希）→ INVALID_EVIDENCE；真实基线 allow-legacy→LEGACY_APPROVED、
  require→SIGNATURE_REQUIRED（不伪造升级）。
- **信任边界**：A 内容完整性 ✔；B 审批流程完整性 ✔；**C 审批者/签发者身份真实性 ✔**
  （Ed25519 + 外部信任根；签名**不**证明执行过程真实——独立采集器/可信执行环境仍属
  DEFERRED）。遗留：无 CI/KMS 自动化撤销设施（撤销依赖用户管理信任根文件）；历史数据
  保持 LEGACY_APPROVED（require 模式如实拒绝）。
- **报告**：[PHASE_1_61_COMPLETION_REPORT.md](PHASE_1_61_COMPLETION_REPORT.md)、
  审计 [PHASE_1_61_AUDIT.md](PHASE_1_61_AUDIT.md)。

## Phase 1.60：Golden Trace / Holdout / Baseline 可信绑定（已实施并实测，未提交）

- **缺口**：场景级 Golden Trace ≠ 逐行为 Golden Trace；Baseline 审批后改内容可逃过
  `baseline_report()` 的结构校验（使用时不重算摘要）；Holdout 无数据集身份与生命周期。
- **做法（全加法，零重写）**：新增 `validator/baseline_lifecycle.py`（状态机
  DRAFT/PENDING_REVIEW/APPROVED/REJECTED/SUPERSEDED/REVOKED + 规范化 SHA256 内容摘要
  + 审批登记表 + 使用时复核）、`validator/trace_bindings.py`（Binding Schema、精确 ID
  匹配、SCENARIO_ONLY/BEHAVIOR_BOUND/PARTIALLY/UNBOUND、10 类绑定验证状态）、
  `evaluation/holdout_registry.py`（CREATED/VALIDATED/SEALED/CONSUMED/INVALIDATED +
  封存摘要 + usage_history + 污染记录）。`evidence_adapter.py` / `evidence_eval.py`
  加法式集成：任务声明 `expected_source` 时期望取自已验证绑定，缺失绑定 →
  INCOMPLETE、失效/不可信 Baseline → NOT_EVALUATED；未声明来源的任务保持 1.58 语义。
- **数据**：4 条既有基线以显式迁移登记入表（内容字节未动）；6 条契约级逐行为绑定
  （BND-001…006，expected 复制自正式契约，契约摘要为版本）；Holdout 真实数据集
  EVAL160-HOLDOUT v2/v3（独立批次真实采集 openable_door）。4 条编排场景 Trace 保持
  SCENARIO_ONLY 不升级。
- **实测（2026-11-03，HEAD `dd3a0e4`）**：新增 5 套测试 97 项全过（26+28+23+15+5，
  含真实 Godot 端到端 5 用例：正常链 VERIFIED_PASS/exit 0、篡改证据 INVALID_EVIDENCE/
  exit 1、绑定缺失 INCOMPLETE、基线篡改 DIGEST_MISMATCH 门禁、Holdout 消费→
  VERIFIED_PASS、重复消费被拒、缺失 NOT_EVALUATED）；1.56–1.59 回归全过
  （52+20+24+28+51+15+比较器+1.56 套件）；validate.py 0 error / 17 warning 不变。
  实施中发现并修复 E5 的 `last_args` 期望缺 `count` 的欠定（首次真实评估即暴露，
  加严修复）。
- **信任边界**：A 内容完整性 ✔；B 审批流程完整性 ✔；**C 审批者身份真实性未完成**
  ——approver 自报、登记表同权限可改，同权限攻击者仍可同时改写内容、摘要与登记；
  独立签名属后续阶段。
- **未做**：扩绑定到全部 60 行为（54 个如实未绑定）、签名基础设施、Holdout 来源签名。
- **报告**：[PHASE_1_60_COMPLETION_REPORT.md](PHASE_1_60_COMPLETION_REPORT.md)、
  审计 [PHASE_1_60_AUDIT.md](PHASE_1_60_AUDIT.md)。

## Phase 1.59：L5 缺陷注入 harness（已实施并实测，未提交）

- **缺口**：Phase 1.51 的 L5 是「一次性注入脚本」，只覆盖 `health`，不可重复、不可审计、
  也不区分「检出」「注入无效」「harness 自己跑错」；无法回答「现有链路到底能不能拒绝
  真实实现缺陷」。
- **做法（上层工具，不重写任何一侧）**：新增 `evaluation/mutation/`：`catalog.py`（读
  `mutation_catalog.yaml` + 从 `template.yaml#behavior` 动态取支持集）、`operators.py`
  （`replace_exact` / `delete_statement`，锚点唯一、空 diff、括号平衡、语句边界全部硬校验）、
  `workspace.py`（隔离副本 + ownership 标记 + 受限清理 + 快照差异 + 路径/符号链接守卫）、
  `harness.py`（control → mutant → recovery 三次真实执行 + effectiveness + verdict）、
  `mutation_eval.py`（CLI + 退出码 + 批次汇总）。
- **判定**：缺陷注入只发生在 `Features/` 的**副本**里，判定完全交给 Phase 1.56–1.58 的
  采集器 / Validator / Evaluation；每个 mutation 用一份临时 `tasks.yaml`（**不改**
  `evidence_tasks.yaml`）。Verdict 独立于 Evaluation 状态：`MUTANT_KILLED` /
  `MUTANT_SURVIVED` / `INVALID_MUTANT` / `HARNESS_ERROR` / `TIMEOUT` / `NOT_RUN`。
- **实测（真实 Godot，`--all`）**：8 条注入 → 6 `MUTANT_KILLED`（5 Feature / 6 Behavior）、
  2 `INVALID_MUTANT`、0 `SURVIVED` / `ERROR` / `TIMEOUT` / `NOT_RUN`；每条 KILLED 都有
  control `VERIFIED_PASS` + recovery `VERIFIED_PASS`（逐字节恢复），仓库 `Features/**`
  哈希前后一致。
- **两条无效注入暴露的缺口**：M04（`trigger_switch/latch_once` 的 Latching 守卫在真实执行里
  走不到）、M06（`save_game` 的 `user://` last_slot 跨 run 残留），如实记 `INVALID_MUTANT`，
  不计入分母，保留在 catalog 作为待补探针的凭据。
- **未做**：扩到全部 23 Feature / 60 Behavior、重写 Validator/Runner、改 Baseline 审批、
  签名/可信执行、自动改 Feature。

## Phase 1.58：Evaluation 接入已验证证据（已实施并实测，未提交）

- **缺口**：Phase 1.57 让 Validator 能拒绝无效证据，但 Evaluation（`runner.py` +
  `scoring.py`）完全不读它——评估结论仍然只来自自带探针，「证据有效」与「行为符合需求」
  两件事没法在一个结论里同时被证明。
- **做法（Adapter，不重写任何一侧）**：新增 `evaluation/evidence_adapter.py`，调用
  `check_behavior_evidence.check_evidence()` 取逐行为结论（不解析 CLI 文本、不重实现验证），
  再用 `expected_holds()` 在**同一批观测**上重算**任务文件**的期望；新增入口
  `evaluation/evidence_eval.py` 承载 Mode A（存量证据）/ Mode B（本次采集后同一链路复核），
  任务定义在 `evaluation/evidence_tasks.yaml`（E1–E5：4 个正向 + 1 个 Holdout）。
- **状态模型**：`VERIFIED_PASS` / `VERIFIED_FAIL` / `INVALID_EVIDENCE` / `INCOMPLETE` /
  `EVALUATION_ERROR` / `NOT_EVALUATED` 分开统计，转换表写死在 `evaluation_status()`；
  非法转换与「PASS 但缺期望」一律 `EVALUATION_ERROR`，**Validator PASS ≠ Evaluation PASS**。
- **包级拒绝传播**：证据包摘要不符 / 过期 / 协议变更会让 Validator 总体 FAIL，但逐条
  复算可能仍 PASS——此时按包级结论把包内每条 behavior 降为 `FAIL(bundle_rejected)`，
  不因逐条通过而放行。
- **Mode C 兼容**：`runner.py` 默认行为与退出码不变；新增可选 `--evidence-report`，接入后
  旧任务标 `LEGACY_PROBE_ONLY` 且不进 `VERIFIED_*` 统计。
- **Golden Trace**：`baselines/*.json` 实测只有场景级 `scenario_id` +
  `approved_behavior_version`，**无 Feature/Behavior 绑定**，因此逐行为比较标
  `NOT_APPLICABLE(binding: scenario_only)`，不伪造绑定；真实 Expected/Actual 比较走
  `--trace` + `--baseline`（复用 `trace_baselines.compare`）。未审批 → `BASELINE_UNAPPROVED`，
  损坏 → `INVALID_BASELINE`。
- **实测（2026-11-03，HEAD `dd3a0e4`）**：真实采集 collect_pickup / health / save_game
  （8 行为全 PASS）后 Mode A+B 一次跑通，E1–E3 `VERIFIED_PASS`、E4（Mode B 真实采集
  trigger_switch）`VERIFIED_PASS`，`behavior_evaluation: VERIFIED_PASS=4`，退出码 0；
  同批真实证据 + 更严期望 → `VERIFIED_FAIL`（`behavior_mismatch`）退出码 1；
  真实证据包篡改 → `INVALID_EVIDENCE`（包级 `integrity mismatch`）退出码 1。
  报告：`.ai/tmp/eval/10856-84242ddd/evidence_report.json`。
- **测试**：新增 `evaluation/tests/test_evidence_adapter.py`（52 项）与
  `test_evidence_eval.py`（20 项），共 72 项全过；fixture 用真实契约构造并用
  `bundle_digest` 签名。
- **未做**：证据来源真实性（需签名 / 可信执行环境）；逐行为 Golden Trace（仓库无绑定）；
  Holdout 自动生成与评估的自动化串联（本轮只做隔离判定）。
- **报告**：[PHASE_1_58_COMPLETION_REPORT.md](PHASE_1_58_COMPLETION_REPORT.md)。

## Phase 1.57：证据 ↔ 执行产物交叉验证（已实施并实测，未提交）

- **缺口**：Phase 1.56 的复核只读证据包。包里的 `action_executed` / `replay_count` /
  `replay_consistent` 仍是采集侧自报——把证据包写得自洽就能通过。
- **做法**：新增 `validator/execution_artifacts.py`
  （`ArtifactResolver` / `parse_execution_record` / `cross_validate`），由 Validator 侧
  从 `evidence_paths` 指向的**真实 `result.json`**（每次重放一份）重算：执行标识、
  Feature/Behavior 归属、重放条数与序号、动作是否真的执行、产物观测是否等于证据
  `actual[]`、重放一致性；采集侧同时记录 `artifact_digests`（每份产物的 sha256）。
- **路径边界**：只允许 `.ai/tmp/behavior`（或 `--artifact-root` 显式授权）内的
  `result.json`；解析前 `realpath` 再判归属，拒绝 `../`、越界绝对路径与符号链接、
  目录、非 `result.json`、以及证据目录自身。
- **判定**：矛盾 → `FAIL`（`artifact_*_mismatch`、`replay_count_mismatch`、
  `observation_mismatch`、`artifact_reused`…）；缺产物 / 不可读 / 坏 JSON / 缺摘要 /
  旧格式无 `evidence_paths` → `INCOMPLETE`。二者不会升级为 PASS。
- **实测（2026-11-02，HEAD `dd3a0e4`）**：真实采集 23 Feature / 60 行为全 PASS；
  Validator `PASS (pass=60, artifacts=120, cross_validated=60)`，退出码 0。
  真实产物篡改测试 9 例：基线 0、改自报 replay_count/consistent→1、改产物内容→1、
  换用他条产物→1、删产物→2、去摘要→2、跨批次→1；同步改写证据+产物+摘要仍 PASS
  （已记为信任边界，不算检测成功）。
- **测试**：新增 `validator/tests/test_evidence_cross_validation.py`（A1–A6 / B1–B15 /
  C1–C7 / D1–D3，ALL PASS）；1.56 的 `test_behavior_evidence_stage.py` 仍全绿，
  其中 N14/N15/N16/N19 因交叉验证发现矛盾而从 INCOMPLETE 升级为 FAIL（更严，非遗漏）。
- **未做**：执行来源真实性（哈希只覆盖内容）；Evaluation 消费证据（Phase 1.58）。
- **分段回归（2026-11-02，共 121 个测试文件）**：63 Python + 58 Godot 全部执行，
  118 PASS / 3 FAIL。validator 9/9、feature_registry 4/4、evaluation 2/2、asset_registry 11/11、
  gameplay_planner 2/2、runtime 3/3、e2e 1/1、Godot Features 31/31、Godot Tests 26/26
  与生成型探针 1/1 均 PASS；scene_composer 28/31，3 个失败全指向上游 8 个未跟踪 Feature。
  一次 `run_tests.py Tests` 批次在 Python 阶段被外部终止（`[37/89]`），**未计为通过**。
- **报告**：[PHASE_1_57_COMPLETION_REPORT.md](PHASE_1_57_COMPLETION_REPORT.md)。

## Phase 1.56：L4 行为证据接入 Validator（已实施并实测，未提交；1.57 在其上增加交叉验证）

- **缺口**：Phase 1.40–1.54 已能产生真实 L4 行为证据（60 条契约、真实 Godot 动作 +
  重放 2 次），但结论只打印在终端——Validator 与 Evaluation 读不到，也无法拒绝「证据
  存在但观测不达标」。
- **做法**：采集侧 `feature_behavior_evidence.py --evidence-out DIR` 落盘
  `feature_behavior_evidence_bundle`（schema_version 1，`evidence_level: L4`，含每条
  check 的 expected/observed/observed_args、重放次数与一致性、证据路径、协议版本与
  协议文件 sha256、`integrity.payload_sha256`）；复核侧新增
  `validator/check_behavior_evidence.py`，经 `validate.py --behavior-evidence` 显式启用
  （默认不执行，旧阶段与退出码不变）。
- **判定纪律**：不采信证据自报 `status`，用 `template.yaml#behavior` 与观测重算；
  L2/L5 不得冒充 L4；`observed: null` 是「没观测到」→ `INCOMPLETE`（不是违反）；
  未知 Feature/Behavior、协议版本或内容变化、内容被篡改 → `FAIL`；退出码
  PASS=0 / FAIL=1 / INCOMPLETE=2 / ERROR=3。
- **实测（2026-11-01，HEAD `dd3a0e4`）**：采集 23 Feature / 60 行为全 PASS
  （`pass=60 mismatch=0 insufficient=0 invalid=0`）；Validator 复核
  `PASS (bundles=1, features=23, pass=60, fail=0, incomplete=0)`、退出码 0；
  篡改真实观测 → `FAIL integrity mismatch`；删除一条行为记录并重签 →
  `INCOMPLETE behavior_uncovered`。
- **测试**：新增 `validator/tests/test_behavior_evidence_stage.py`（P1–P5 / N1–N20 /
  E1–E2 / C1–C5 / D0–D5，54 处断言，**ALL PASS**），其中 D 段在隔离副本上做真实缺陷注入
  （基线 PASS → `set_open` 不再改变状态 → 采集器 FAIL、Validator `FAIL
  contract_violation` → 伪造 PASS 并重签仍被拒 → 逐字节恢复后重新 PASS）。
- **回归**：`run_tests.py validator` 11/11、`feature_registry` 4/4、`evaluation` 2/2、
  `e2e` 1/1（29 min）全过；`scene_composer` 28/31，3 个失败全部来自他人未完成的 8 个
  未跟踪 Feature（缺 `template.yaml` / 能力声明），已登记为上游未完成、未代为补齐；
  `validate.py` 默认运行仍是 0 error / 17 warning 且不输出 Behavior evidence 行。
- **未做**：Evaluation 消费证据（留 Phase 1.58）；来源真实性（哈希只证明内容完整）；
  未新增 Feature、未改协议、未改任何 L2/L3/L5 结论。
- **报告**：[PHASE_1_56_COMPLETION_REPORT.md](PHASE_1_56_COMPLETION_REPORT.md)。

Git 事实（2026-10-20 实测）：HEAD = `1c30f94`（Phase 1.19–1.25 已提交）；Phase 1.26–1.37
为**本地未提交增量**（含 Phase 1.30/1.31/1.33/1.36/1.37 审计报告与对应实现/测试）。
仓库内的用户自有修改 `.workbuddy/memory/2026-10-18.md` 未触碰。

## Phase 1.32：F4 所有权清理（已实施并实测）

- **新增 `testsupport/run_workspace.py`**：每次运行一个 `pid-uuid8` token 与专属运行根
  （`.ai/tmp/runs/<token>/`，`mkdir exist_ok=False`）；`ownership.jsonl` 追加式记录
  `created` / `removed`（相对路径 + sha256 + bytes + mtime_ns，fsync）。
- **fail-closed 清理**：只删账本中 `created` 的文件；删除前校验 token、路径在运行根内、
  非符号链接、size/mtime 与 sha256 一致，并在 unlink 前再次 `lstat` 比对；账本缺失 /
  非法 JSON / token 不符 / 字段非法 ⇒ 整次拒绝；存在未入账文件 ⇒ 保留运行根与账本。
- **cross-layer 迁移**：33 个夹具 → `fixtures/<name>.json`，探针 → `probe.gd`，均位于
  运行根内（`res://.ai/tmp/runs/<token>/...`）；旧 `Levels/E2eContract__*` glob 清理已删除；
  断言仍 65 项（66 行 PASS）。启动时对其它 token 只打印 `STALE (not removed)`。
- **新增 `test_run_workspace.py`（W1–W15，19 项）**：正常清理 / 幂等 / 两运行隔离 /
  内容篡改拒绝 / 账本缺失或损坏 / 路径越界 / 符号链接与目录替换 / 未入账文件 /
  异常残留只报告 + 显式 reclaim / 两个真实子进程并发 / 失败保留诊断。实测 **exit 0**。
- **实测**：`run_tests.py validator` **9/9 PASS，exit 0**；cross-layer **exit 0，66 PASS**；
  全量 `run_tests.py` **82/82 PASS（exit 0，failed=0 incomplete=0 not_executed=0）**；
  残留集成（独立进程留下运行根）→ `STALE` 报告、目录保留、reclaim 后 `.ai/tmp/runs` 余 0。
- **未做**：F4-B（e2e + 6 个 GDScript 测试 + `user://`）、F5；未强杀真实测试进程；
  四个基线 sha256/mtime 未变。
- **已知限制**：无 janitor CLI（reclaim 需显式调用）；检查—删除仍有理论 TOCTOU 窗口；
  `.godot` 缓存并发未加锁；残留不自动回收（无法证明持有者已死亡）。

## Phase 1.38：实例证据对账（已实施并实测）

- **缺口**：`template.yaml#instance` 是声明证据，1.37 后直接喂能力契约，但从未与真实
  `.tscn` 核对（`artifact_evidence` 只在组合时核对，且允许子节点“在别处”）。
- **新增** `scene_composer/instance_evidence.py`：三级证据（declaration / static_scene /
  runtime），状态 PASS / MISMATCH / INSUFFICIENT / INVALID / NOT_DECLARED；
  根类型、直接子节点类型与计数、层级错误、重复路径、解析受限、`runtime_children` 豁免。
  另含挂载模式（恰好一次、引用正确入口场景、子节点不得来自别的组件）。
- **门禁**：`validator/check_instance_evidence.py` 作为 Validator 第 7 阶段；
  MISMATCH/INVALID → failure，INSUFFICIENT → warning。未声明仍是 NOT_DECLARED（向后兼容）。
- **实测**：新测试 **53 checks** exit 0；相关 10 个测试全过；全量 **87/87 PASS**；
  Validator **0 error / 17 warning**；真实负向对照（删 PickupShape）→ 测试 exit 1、
  Validator exit 1，sha256 还原后一致；四条黄金基线未变。
- **报告**：[PHASE_1_38_AUDIT.md](PHASE_1_38_AUDIT.md)。
- **未接入**：挂载模式不进 compose（artifact_evidence 报告形态已冻结）；运行时对账未实现。

## Phase 1.37：评估驱动的能力改进（已实施并实测）

- **瓶颈**：Phase 1.36 的 T1 首次尝试被 `Capability contract failed: Collision requires
  CollisionShape2D` 拦住，必须人工改计划才能交付单 Feature 场景。
- **根因**：能力契约只读 Scene Intent 中**已声明**的结构；6 个 Feature 的入口场景
  自带碰撞形状却未在 `template.yaml` 声明 `instance:`，于是证据缺失。
- **修复**：`collect_pickup` / `heal_pickup` / `openable_door` / `trigger_switch` /
  `moving_platform` / `player_movement` 的 `template.yaml` 补 `instance:` 声明；
  `contact_damage` 有意不声明（其入口场景无碰撞形状，接触形状由宿主提供）。
  **未改**契约判定、Resolver、生成器、Validator；生成产物逐字节不变。
- **新增测试** `test_feature_instance_evidence.py`（E1–E5，41 checks）：声明与 `.tscn`
  一致、去掉声明必须仍 BLOCKED（防放宽）、生成物不变、无声明的 Feature 不被推断。
  修复前 **10 项 FAIL**（负向对照），修复后 exit 0。
- **附带修复（被激活的旧缺陷）**：① 外部产物环判定把**菱形引用**当环
  （`Health.tscn` 经 `Player.tscn` 二次可达 → e2e L6 误报）→ 改为祖先链判定，
  Case 5c 锁定菱形放行、环 Case 5/5b 仍 BLOCKED；② adoption 审计断言写死了
  「声明 Collision ⇒ 裸计划必须 BLOCKED」→ 改为按真实场景碰撞形状判定，
  `contact_damage`（声明了 Collision 但场景无形状）仍必须 BLOCKED。
- **实测（同一 `scoring.py`，最终态 token `10160-5db19546` / `7648-1d43424a`）**：
  v2 首次通过 **4/5**、计划修订 **1/1**；v1 冻结任务集与 1.36 完全一致（3/5、2/2）；
  最终 5/5；自动修复 1/1；回归缺陷 0/5；清理 24 项 / 拒绝 0 / 残留 0；基线未变。
- **全量测试**：86/86 PASS（exit 0）；中途 84/86（上述两个被激活的缺陷）已如实记录在报告。
- **报告**：[PHASE_1_37_AUDIT.md](PHASE_1_37_AUDIT.md)。
- **未修**：D3（`--waves` 被静默忽略，T4 仍需计划修订）、D4（信号连线/同 Feature 多实例）、
  D5（`--tests` 在根实例蓝图上产出空断言）。

## Phase 1.36：端到端能力评估（已实施并实测）

- **新增评估套件** `.ai/tools/evaluation/`：`tasks.yaml`（5 个冻结任务）+ `runner.py`
  （暂存 → 执行 → 真实 Godot 探针 → 所有权清理 → 报告）+ `scoring.py`（判定与指标口径
  唯一事实源）+ 4 个行为/加载探针 + 5 个固定输入。
- **阶段判定**：`plan / artifacts / loadable / behavior / negative / regression`；
  任一 FAIL 即 FAIL，无证据 = NOT_EXECUTED；任务 PASS 要求必需阶段全部 PASS（未执行不算通过）。
- **归因分离**：`initial` / `plan_revision` / `framework` 三类尝试分别统计；
  标 `expect_failure` 的证伪尝试按预期跑完也不算通过，并继续后续尝试。
- **实测（两次正式运行，token 5112-08e78d96 / 7656-e9c85412）**：5/5 PASS；
  首次通过率 3/5（T1 单 Feature 需计划修订、T4 波次参数需显式 `--wave`）；
  自动修复 1/1（T5：`Node not found` → `node_path_literal` 修复 → 运行时 PASS）；
  回归缺陷 0/5；单次全量耗时 115.0 s / 117.2 s。
- **资源纪律**：清理 24 项 / 拒绝 0 / 共享目录残留 0；产物路径启动前不存在、
  内容标记匹配才删；标记不匹配或运行目录之外的目录一律拒绝删除。
- **实测回归**：全量 `run_tests.py` **85/85 PASS**（83 + 2 个评估器自测：28 + 24 checks）；
  四条黄金基线 sha256/mtime 未变。
- **报告**：[PHASE_1_36_AUDIT.md](PHASE_1_36_AUDIT.md)。
- **未做**：F5、janitor CLI、`.godot` 并发治理；成本/模型计量（UNAVAILABLE）；并行评估。

## Phase 1.34：统一运行标识与 E2E 并发安全（已实施并验证）

- **L-9 已解决**：`testsupport/run_lock.py`——O_EXCL 互斥锁覆盖 e2e 共享产物完整
  生命周期；持有者存活拒绝、可证死亡回收、锁内容非法 fail-closed + 人工恢复说明；
  释放需 holder_id/pid/scope 三元组匹配。双真实子进程竞争实测（L7）。
- **L-8 已解决**：canonical token = `<pid>-<16 hex>`（Python uuid4 / GD randi×2，
  同一 TOKEN_RE）；legacy 8-hex 受限识别、reclaim 拒绝；畸形目录名忽略/拒绝；
  「可识别 / 可证明所有权 / 可安全回收」三条件分离。W20–W23 锁定。
- **L-10 保持保留**：`user://runtime-fixture-*` 不伪造所有权、不自动回收。
- **修复**：1.33 遗留的 CONTRACT_INDEX.yaml 结构损坏（`- id:` 误嵌 `test_runner:`
  mapping，曾致 scene_intent_contract / run_tests_evidence 失败）；GD 侧运行根
  描述更正为 `.ai/tmp/runs/`（16-hex token）。
- **实测**：test_run_workspace **36/36**；cross_layer 66；6 GD exit 0；e2e 173/173；
  validate.py 0 error / 17 warning；四条基线未变。全量单命令 82 项中 80 PASS——
  两个非 PASS 为环境删除守卫（L-11 新记录：F4-B 运行根自清理计入全量 turn 计数）。
- **报告**：[PHASE_1_34_AUDIT.md](PHASE_1_34_AUDIT.md)。

## Phase 1.33：F4-B 集成与资源所有权（已实施并验证）

- **6 个 GDScript 测试**（orchestration_trace / boss / generic / level / holdout_trace /
  waves_exit_gate）迁入 `.ai/tmp/runs/<pid>-<usec>/` 运行根：内容未变才删、
  `res://Levels` / `user://` 前缀命中但不属于本运行的残留只报告不删除。
- **e2e**：产物无法迁入运行根（`Scenes/<Pascal>.tscn` 是生产解析约定），采用
  「显式声明清单 + 启动期内容签名 + 本次运行缺席证明」——签名匹配的上轮残留删除、
  不匹配则拒绝删除并失败（fail-closed）；O1/O2 所有权断言纳入 e2e（173/173 PASS）。
- **`user://` 审计**：`game/`（引擎/MCP 日志配置，不清理）、`runtime-fixture-*` ×7
  （Phase 1.6 夹具，所有权不可证 → 保留）、`[unnamed project]`（空）——未删除任何内容。
- **`.godot`**：单独风险评估（引擎缓存，非临时目录）；串行是当前唯一被验证的并发边界。
- **实测**：6/6 GD exit 0；e2e 173/173（exit 0）；validator 段 9/9；`validate.py`
  0 error / 17 warning；四条基线 sha256/mtime 与实施前一致。
- **报告**：[PHASE_1_33_AUDIT.md](PHASE_1_33_AUDIT.md)（含验证矩阵、NOT_EXECUTED/SKIP、
  L-8～L-10 新已知限制）。
- **2026-10-20 复核补记（§11）**：当前工作区（Phase 1.34 已提交 + 1.35 未提交）上
  独立复核，修复**一处 e2e 所有权记账缺陷**：启动期扫描回收的残留未重新登记为
  「本运行可拥有」⇒ 结束清理拒删本轮重建的同名产物 ⇒ e2e exit 1（残留回收反而
  阻塞下一轮）。最小修复 + 新增 `validator/tests/test_e2e_ownership.py`（E1–E4）。
  修复后：e2e 173/173（含回收 19 个中断残留、工作区归零）、validator 段 10/10、
  全量 83/83；基线 sha256/mtime 未变；`.godot` 未清理；F5 与 janitor 仍未实施。

## Phase 1.31：执行隔离与安全清理（审计/设计完成，F4-A 已在 1.32 实施）

- **只读审计 + 设计**（2026-10-19）：报告见 `.ai/context/PHASE_1_31_AUDIT.md`。
  本阶段**未修改任何代码或测试**，只新增报告并更新文档。
- **F4 现状（实测 + 代码证据）**：`test_cross_layer_contract.py` 的 `cleanup()` 按
  `Levels/E2eContract__*.json` 前缀删除；临时目录模拟实测 own/foreign 均被删、无关文件保留；
  cross-layer / e2e / 6 个 GDScript 测试全部使用固定文件名，无 run token、无所有权账本；
  e2e 启动期清理按固定名单删除（行 401–412）。强杀后的 cross-layer 残留无启动期检查。
- **Tier-1 隔离可行性（实测）**：在 `res://.ai/tmp/p131_<uuid>/` 写脚本 + 夹具，
  `godot -s` 执行成功（`valid=1`），无 `.uid` 副作用，清理后 `git status` 仍为 26 条。
  注意 `.ai/tmp/` 当前**未**被 `.gitignore` 忽略（实施前需补）。
- **F5 现状（实测）**：`run_tests.py --python-only test_run_tests_evidence` 输出
  `1 tests (Godot=0, Python=1)` + `completed=1/1` + `ALL PASS`（exit 0），日志不含过滤串；
  空匹配 exit 1 正确；入口自身被中断时无摘要/证据文件。
- **候选方案（未实施）**：F5 加法式 `--evidence` JSONL + `selection:` 行（退出码不变）；
  F4 token 运行根 + `(path, sha256)` 账本 + fail-closed 清理 + 启动期只报告 stale。
  安全场景矩阵（S1–S6）与授权清单见报告 §6/§11。
- **未做的项**：F4/F5 实现；并发/强杀复现（禁止）；基线未改动（sha256/mtime 四次一致）。

## Phase 1.30：执行隔离与证据来源（实测，未提交）

- **只读审计**（2026-10-19）：报告见 `.ai/context/PHASE_1_30_AUDIT.md`（信任边界图 /
  证据数据流图 / 字段性质表 / 风险排序 / 方案比较）。审计阶段未改任何代码。
- **P0-1 全量守卫根因**：`SAFE_DELETE_BULK_CONFIRM_REQUIRED` 只出现在文档中（仓库无代码
  产生它），是 WorkBuddy 宿主钩子（50 次删除/命令）；当前 Freebuff 运行时**不复现**：
  单命令内 2000 次工作区 `unlink()` 不被终止，`run_tests.py` 单命令 **81/81 PASS、exit 0**
  （`[77/81] PASS test_cross_layer_contract.py`）。文档已改为「环境条件观测」，保留分段兜底。
  仍真实的隔离问题（共享固定路径 / glob 清理 / 强杀残留）已记录，本轮未改（F4 未授权）。
- **P0-2 高严重度缺陷 E-1**：`approve._validate_candidate` 原地把调用方文档的事件 `run_id`
  改成 `candidate-check`，`apply` 随后落盘 ⇒ 四个已批准基线的 `events[*].run_id` 全部被污染，
  `source.trace_run_id` 成为孤证；同一进程复用该 trace 还会误报 `run_id_mismatch`。
  修复：只在**副本**上规范化。E-2：新增 `source.trace_run_id` / `trace_event_count` 与内容
  的一致性校验。生产 GDScript 未改、基线未重录。
- **新增测试**：`test_trace_baselines.py` U95–U99（不修改输入 / run_id 不一致拒 / 缺声明拒 /
  计数不一致与截断捕获拒 / apply 写入后仍保留真实 run_id）；U39 夹具补 `trace_run_id`。
  修复前对照：U95 段在旧实现上以 `BaselineError: run_id_mismatch` 中止（exit 1）。
- **不做的项**：本地 manifest / 签名（需新的可信根，对同权限攻击者收益有限）；
  cross-layer 唯一令牌 + 所有权清理（F4，未授权）。

## Phase 1.29：验证器信任边界与证据完整性（实测，未提交）

- **审计（只读）**：重读 trace_replay / trace_baselines / approve_trace_baselines / run_tests
  与全部调用方，输出信任边界图与入口清单；三条不变量（I1 合法性 / I2 审批绑定 /
  I3 证据完整）逐条验证。所有复现均在临时目录或内存中完成，未触碰正式基线。
- **已证实缺陷（均带实测）**：H1 classify 把自报 `SKIP` 的测试归为 PASS（e2e 的
  T4–T12 在 Godot 缺失时整段跳过仍 return 0；`--python-only` 可输出 ALL PASS）；
  M2 缺 scheme 声明的候选被批准后记录方案与指纹不符（`matching_fingerprint_schemes`=[1]）；
  M3 同一「文件不存在」在回放 CLI=2、比较器=1；L1 CLI `--scenario` 被静默忽略；
  L2 apply 读坏 JSON 抛回溯；L3 `--candidate <文件> --scenario <id>` 被当目录。
- **修复**：`classify` 的 PASS 新增「未自报 SKIP」条件（skip 不得把 FAIL 降级）；新候选强制
  声明当前指纹方案；`--scenario` 与内容 `scenario_id` 必须一致；候选读取统一 exit 2；
  `--candidate` 仅在其确为目录时才拼接 `--scenario`。M3 选**锁定现状 + 文档化**
  （CLI 兼容优先），不改变退出码。生产 GDScript 未改。
- **新增测试**：`validator/tests/test_run_tests_evidence.py`（E1–E7，含真实
  `run_python_test` 子进程路径、`main()` 空选择必须非 0 与无残留断言）；`test_trace_baselines.py` U86–U93
  （方案必须声明 / 身份不一致 / 输入错误统一 / 退出码映射锁定，含正向对照）。
- **不做的项（经评估）**：候选来源自报文本无密码学证明（需外部签名）；
  `expected_final_state` 与自身事件的一致性未加校验（fail-safe 方向，不会掩盖回归）。

## Phase 1.28：跨模式 trace 语义一致性（实测，未提交）

- **审计**（只读，先行）：构造跨模式事件矩阵（11 类事件 × 产生模式 / 载荷 / 前置 / 重复策略 /
  测试与基线覆盖），确认五处可复现缺陷：C1 阶段事件无模式门、C2 阶段数与
  `data.stage_count` 不一致、C3 终结 reason 无模式校验、C4 `data.mode` 缺失时所有模式门失效、
  C5 `validate_baseline` 不回放（实测：由不可达 trace 构造的基线被接受，
  `compare(同一条非法 trace)` = PASS / exit 0）。
- **修复最小必要**：`invalid_start_mode`（mode 必须显式声明）／
  `stage_event_outside_boss_stages`／`stage_start_outside_declared_count`／
  `victory_reason_outside_mode`／`failure_reason_outside_mode`；终结原因白名单取自
  LevelOrchestrator 实际写入点。生产 GDScript 未改。
- **基线契约**：`validate_baseline` 结构校验通过后必须回放（`events must replay:`）；
  非法基线 → `INVALID_BASELINE`（exit 2），不再把基线自身的不可能行为归给 trace。
- **公共 vs 模式特有边界**：公共 = 结构 / 序号 / 时间戳 / started 唯一居首且声明 mode /
  终结互斥且之后只允许 `duplicate_event_ignored`；模式特有 = boss 的 `stage_*` 与
  `boss_death_confirmed`、waves 的 `wave_*` 与 `exit_unlocked`、holdout 的
  `spawn_schedule_started`，以及各模式的可达终结原因。不为统一而强迫相同事件序列。
- **测试**：R68–R80（回放契约）、U77–U85（回放器与比较器一致拒绝、非法基线、黄金集合无
  跨模式泄漏）。真实 Godot 证据仍来自四个捕获基线与既有 H / G / boss 用例。
- **兼容性**：零重录；四个基线事件字节未变，仍可回放且自比较 PASS。

## Phase 1.27：holdout 生成调度的事件级保护（实测，未提交）

- **审计**：holdout 真实转换只有 start / 计时 / 调度产出 / 终结；调度产出与失败路径
  此前无事件级保护，也无 trace 级测试。
- **新事件** `spawn_schedule_started`（`_run_spawn_schedules` 真实产出边界 + 幂等守卫；
  data = schedule/entity/interval/max_alive）；不虚构未到点的调度（H2 锁定）。
- **回放规则**：holdout 模式限定、payload 形状、阶段身份禁止、索引不得重复；
  结果新增 `spawn_schedules_started`；R62–R67（含 legacy 兼容）。
- **真实 Godot 测试** `Tests/test_holdout_trace.gd` H1–H7：正常完成 / 不可达调度 /
  提前失败（level_failed(player_died) 唯一）/ 终结后重复（duplicate_event_ignored）/ 
  期满前不结算 / 序号与时间戳契约 / 清理；带用例完成计数防假通过。
- **holdout 基线重批 v2**：真实捕获 → candidate → review → apply --i-approve；
  3 事件链（捕获 run-675705；独立复核 run-679135 亦 3/3 PASS）；指纹 b62cb26f…（scheme 2）、
  previous_baseline_version 1。
- **探针证据修正**：`probe_metrics.trace_events` 改由导出文档统计（此前恒为 0）。
- **比较器用例** U71–U76：v2 链与覆盖声明、自回放 PASS、旧 v1 形态 EVENT_MISSING、
  interval 变更 DATA_FIELD_CHANGED、重复调度 TRACE_INVALID。
- 实测：godot 38/38；回放 68；比较器 77；独立 E2E 171 PASS（T5d 3/3）；
  holdout 真实捕获 3 事件；validate.py 0 error / 17 warning 不变。

## Phase 1.26：状态一致性 + 出口锁定语义闭环（实测，未提交）

- **文档一致性**：Phase 1.25 的代码已随 `5e47bfd` 提交，旧文档中的「未 commit」已纠正；
  状态与 `git log` / `git status` 对齐，不再用提交说明代替测试证据。
- **waves 覆盖声明**：`baselines/waves.json` 的 `coverage` 改为真实事件链描述
  （wave_started/wave_cleared/exit_unlocked 属事件级保护；探针度量断言单独列）；
  事件与指纹字节未变，批准记录加 `coverage_revised_at` / `coverage_revision_note`。
- **回放契约**：`victory_without_exit_unlock`（waves + 含波次事件 + reason=
  exit_reached_after_unlock 时必须已有 exit_unlocked）；旧 trace 不被追溯套用；R58–R60。
- **真实 Godot 注入**：`Tests/test_waves_exit_gate.gd`（G1–G7）：锁定期间注入出口区不结算
  （trace 记 invalid_transition_rejected(exit_locked)）→ 清空最后一波解锁 → 真实输入走进
  出口区才胜利；事件取自生产导出接口。G7 额外发现并修复了「宿主不注入 exit_door 时可提前
  胜利」的缺口：出口胜利现在要求 `_waves_all_cleared()`（只读编排状态，不依赖门对象），
  解锁边界（信号 + trace）也不再要求门存在；boss / holdout / 直接胜利路径不变。
  负向对照：临时移除守卫后 G7 以 exit 1 失败（0 波次未清即 level_victory），随后按字节
  还原（sha256 一致）并重跑 G1–G7 = PASS。
- **指纹方案化**：scheme 1（Phase 1.23，含 scenario_id）/ scheme 2（Phase 1.24+）；
  两条 boss 历史基线现可复算（U66/U67）。
- **测试入口**：`run_tests.py` 区分 PASS / FAIL / INCOMPLETE（超时 / 外部终止 / 无判定），
  非 PASS 一律退出 1；输出 completed/passed/failed/incomplete/unavailable/not_executed。
- **E2E 残留**：探针删除 .gd 后遗留的孤儿 `.uid`（实测 `Tests/e2e_behavior_probe.gd.uid`）
  已纳入清理与 Z1 断言。
- 实测：全量入口 79/79 PASS（exit 0，0 INCOMPLETE）；godot 37/37；回放 62；比较器 71；
  独立 E2E 171 PASS（T5a–T5d 四模式全过）；cross_layer 66；level_planner 134；unified 36；
  validate.py 0 error / 17 warning 不变。
- 真实捕获复核：waves 在编排器守卫修复前后各捕获一次（均 7 事件、与 v2 基线 7/7 PASS），
  基线无需重录。

## Phase 1.25：waves 语义事件与事件级回归（实测，已随 5e47bfd 提交）

## Project Stage

Feature-based Agent Development —— Phase 1.26（状态一致性 + 出口锁定语义闭环）已在本地
实测通过（未提交）；Phase 1.25（waves 语义事件 + 事件级回归覆盖，已提交于 5e47bfd）、
Phase 1.24（黄金基线覆盖补齐 + 审批安全 + 质量门禁）、Phase 1.23（黄金
Trace 基线与回归检测）、Phase 1.22（可回放诊断事件 + 只读回放器）、Phase 1.21（多阶段
Boss 编排 + 跨契约身份校验）、Phase 1.20（通用关卡编排 + BossChallenge 接入）、
Phase 1.19（蓝图 → 组合计划生成）、Phase 1.18（Scene Intent 集成与运行时交互编排）、
Phase 1.17（多实体场景组合与绑定完整性）、Phase 1.16（实体绑定端到端接入）、Phase 1.15
（跨层契约与统一校验）、Phase 1.14（通用关卡编排管线）、Phase 1.13（关卡编排生成）、
Phase 1.12（死亡与胜负闭环）、Phase 1.11（实体根运动 + 接触伤害）、Phase 1.10（行为验证）、
Phase 1.9（端到端生成）、Runtime Playtest & Self-Repair（Phase 1.6，AD-010）与 Gameplay
Loop Composer（Phase 1.5，AD-009）已完成。

## Phase 1.25：waves 语义事件与事件级回归（实测）

- **生产端**：LevelOrchestrator 新增 wave_started / wave_cleared / exit_unlocked
  （真实转换边界 + 幂等守卫）；schema v1 加性扩展（旧 trace/基线完全兼容，boss 基线
  零重录）。
- **回放端**：波次事件模式约束、索引/清空/解锁顺序规则、waves 胜利前置条件；
  R44–R57（14 项）锁定。
- **基线**：waves 重批 v2（7 事件链，真实捕获 + 显式批准）；holdout 保持 v1
  （不虚构不存在的状态——审计结论已记录）。
- 验证：e2e 171 项 PASS（四模式逐事件比较）；回放 58/58；比较器 64/64；
  Godot 八专项 exit 0；validate.py 0 error / 17 warning 不变。

## Phase 1.24：黄金基线覆盖补齐 + 审批安全 + 质量门禁（实测）

- **四条黄金基线**：boss 单/多阶段（Phase 1.23）+ waves + holdout（Phase 1.24，
  真实 Godot 沙箱捕获 + 显式批准 v1，批准记录含指纹与来源链路）。
- **审批安全**：review/apply 从候选文件内容重算指纹；篡改/替换 = 拒绝（exit 1）；
  apply 原子写入；U49–U56 锁定。
- **配套修复**：level_planner `--mode holdout` CLI；两个适配层 `export_trace_json`
  转发器；level 探针 trace 导出；holdout_trace_probe。
- **删除守卫**：根因与分段执行结论如实记录于 run_tests.py 文档头；
  低删除量策略（导入缓存刷新 ×2、探针自清理、%TEMP% 沙箱）已实施。
- 验证：e2e 独立 171 项 PASS（T5a–T5d 四模式逐事件比较）；trace_baselines 57；
  godot-only 36/36；各分段全过；validate.py 0 error / 17 warning 不变。

## Phase 1.23：黄金 Trace 基线与回归检测（实测）

- **黄金基线**：`.ai/tools/validator/baselines/{multi_stage_boss,single_stage_boss}.json`
  （baseline_schema_version 1；事件来自真实 Godot 沙箱捕获；批准记录完整）。
- **比较器** `validator/trace_baselines.py`（只读）：先 trace 校验 + 回放，后按序逐事件
  对齐比较；严格字段 7 个，动态字段仅 run_id/timestamp_ms（显式策略），data 默认 strict；
  PASS(0)/REGRESSION·INCOMPLETE·INVALID_TRACE(1)/BASELINE_MISSING·INVALID_BASELINE(2)。
- **批准流程** `e2e/approve_trace_baselines.py`：candidate → review → apply --i-approve；
  测试/比较器永不写基线（T13 断言）。
- **E2E T 段 T1–T14**：沙箱真实捕获 → 逐事件比较 → 差异注入（exit 1 + 字段路径）→
  动态字段 PASS → 基线缺失/损坏 exit 2 → 基线不可改写 → 无残留。
- 验证：`run_tests.py` **78/78 PASS（exit 0）**；e2e 独立 169 项 PASS；trace_baselines
  单测 49 项；回放单测 44 项；validate.py 0 error / 17 warning 不变。

## Phase 1.22：诊断事件 + 只读回放（实测）

`LevelOrchestrator` 在真实状态变更边界写入 `OrchestrationTrace`（schema v1，纯数据）；
序号 0 起严格 +1，`timestamp_ms` 相对启动且非递减；重复通知与非法转换可观测但不改状态；
`trace_enabled = false` 零事件。`validator/trace_replay.py` 只读回放（不驱动游戏），
重建最终状态 / 阶段链 / Boss 死亡确认，并拒绝违反契约的序列；真实 E2E trace 由探针从
Godot 运行导出（`Tests/e2e_multi_stage_boss_trace.json`）并经独立回放后清理。

| 量 | 实测值 |
| --- | --- |
| 事件类型 | orchestration_started / stage_started / stage_completed / stage_transitioned / boss_death_confirmed / level_victory / level_failed / duplicate_event_ignored / invalid_transition_rejected |
| 契约 | 序号 +1 无缺口；时间戳非递减；阶段字段 null 策略；事件纯数据（is_json_safe） |
| 幂等 | Boss 重复死亡 = duplicate_event_ignored(boss_death)；终结后只允许 duplicate_event_ignored |
| 回放器 | trace_replay.py CLI 0/1/2；R1–R43；拒绝未知版本/类型、序号缺口、阶段跳跃、终结冲突、Boss 未确认死亡即胜利 |
| 真实 E2E | P14–P18：真实 trace → victory + [clear_1@0, boss@1]；重复回放一致；去终结事件重建为 playing |
| 关闭开关 | trace_enabled = false → 零事件且游戏结果不变（T5） |

新增：`Orchestration/orchestration_trace.gd`、`Tests/test_orchestration_trace.gd`（T1–T8）、
`validator/trace_replay.py`、`validator/tests/test_orchestration_trace.py`（R1–R43）、
`.ai/context/orchestration_trace_schema.yaml`；多阶段探针新增 trace 导出与 E2E P14–P18。

## Phase 1.21：多阶段 Boss + 跨契约校验（实测）

`mode: boss` 新增可选 `stages`（Phase 1.20 单阶段配置不写该字段即完全兼容）。
阶段顺序只由数组决定；`clear_enemies` 清空后进入 `defeat_boss`，Boss 死亡后完成，
可选 `complete_level` 作为显式终结阶段。`LevelHost` 改为 deferred start，避免在宿主
`_ready` 组装期间生成子节点触发 Godot「Parent node is busy」。

| 量 | 实测值 |
| --- | --- |
| 阶段契约 | `stages` >= 2；id 唯一；至少一个 clear_enemies；恰好一个 defeat_boss 且最后；complete_level 只能最后且要求 exit=never / victory=boss_defeated |
| 清理阶段 | 引用真实实体/条目；不能引用 boss.entity；Boss 未激活前不得完成关卡 |
| 转换 | clear 的 `alive_count` 归零 → 激活 Boss 阶段（只一次）；defeat 阶段内 Boss 死亡 → 完成该阶段 |
| 提前死亡 | 清理阶段击杀 Boss 只记录一次，不跳阶段；进入 Boss 阶段时立即结算且不重复 |
| 幂等 | stage_started / stage_completed / boss_defeated / finished 各恰好一次；重复 died / 重复帧不重复 |
| 交叉校验 | `arena_scene` 根名 == plan.host.name；根级 instance 集合 == plan.instance_name 集合；Boss instance 与 plan 一致；stage 实体均在 plan；缺 plan → INCOMPLETE |
| Python/Godot 一致 | C11 共 11 例（合法 clear→boss / +complete；空/重复/未知类型/缺 Boss 引用/顺序非法/终结冲突/waves+holdout 携带 stages） |
| 真实 E2E | P1–P13：蓝图 → 两个实体场景 → bind_assets → 自动 plan → `--compose-plan` 三实例宿主 → `--stage clear:stage_grunt:2 --stage boss` → check_level --plan → Godot 清理→Boss→完成 / 玩家失败 |

新增：`e2e/multi_stage_boss_probe.py`（临时 GDScript，机读 `STAGE:` 行）、
`Tests/test_boss_orchestration.gd` B6（多阶段生命周期/非法配置）。
交叉校验实现仍只有一份：`level_planner.validate_level(level, plan=...)`；
`check_level.py --plan`、`validate.py --level --level-plan` 均调用它。

## Phase 1.20：Boss 编排接入（实测）

`BossChallenge` 不再维护第二套胜负状态机：`Levels/boss_challenge.json`（boss 模式）+
`LevelConfig` + `LevelOrchestrator` 驱动世界状态；适配层只保留 HUD/表现与 Boss 停摆。
`level_schema.yaml` version 2 追加 `mode: boss` / `boss` 块 / `boss_defeated`，
现有 waves / holdout / v1 语义未改。

| 量 | 实测值 |
| --- | --- |
| Boss 身份 | `boss.entity` 必须已在 entities 声明；`boss.instance` 是相对宿主根的显式实例路径（拒绝绝对路径 / `..`）；不按 role / 节点名猜 |
| 实例来源 | `spawn: existing`（适配层 `bind_boss(entity_id, node)`，需带 Health）或 `spawn: on_start`（编排器从配置场景生成） |
| Boss 存活 | 出口区进入被显式拒绝（即使门已开）；Boss 不计入 alive_count |
| Boss 死亡 | 只结算一次：按 exit.unlock_when 开门，按 victory.condition 完成；重复 died 不重复开门/完成 |
| 玩家死亡 | Failed + finished(false) 恰一次；终态重复事件无效 |
| 失败路径 | 未知 boss 实体 / existing 缺 instance / 非法 spawn / 非法胜利规则 → 配置层拒绝（字段路径）；宿主实例解析失败 → `fail_setup`（stage=bind） |
| 跨层一致性 | `test_cross_layer_contract.py` C10：合法 boss + 未知实体 / existing 缺实例 / 非法 spawn / 含 waves / v1 boss 共 7 例，Python 与 Godot 判定及字段路径一致 |
| 真实 E2E | e2e N1–N13：蓝图 → 生成 Boss 实体场景 → bind_assets → 自动 plan → `--compose-plan` 宿主 → `level_planner --mode boss` → Godot headless（身份 / 存活零胜利 / 一次完成 / 重复忽略 / 玩家失败 / 非法实例拒绝） |

新增：`Orchestration/level_host.gd`（通用宿主适配器：按配置给组合宿主接线，
`existing` 时按 `boss.instance` 绑定），`Tests/test_boss_orchestration.gd`（B1–B5），
`e2e/boss_level_probe.py`（临时 GDScript，机读 `BOSS:` 行，用后删除），
`gameplay_planner/level_planner.py --mode boss --boss E --plan PLAN`（从真实 plan 生成，
默认 arena_scene = `res://Scenes/<host>.tscn` 且必须已存在；失败不写盘）。

## Phase 1.19：蓝图 → 组合计划生成（实测）

composition plan 不再手写：Gameplay Blueprint + **真实生成产物** →
`scene_composer/plan_generator.py` → plan 文档 → 既有正式入口
`scene_composer --compose-plan` → 宿主 `.tscn` → 真实 Godot headless。
生成器只生成声明，组合仍由 `composite.compose_from_plan`（唯一实现）承担；
校验也复用同一实现（临时目录真实试组合）→ **不新增** 独立 plan Validator 层。

| 量 | 实测值 |
| --- | --- |
| 实体 → 场景 | override > 蓝图 `entities.<id>.scene`（declared）> `Scenes/<Pascal>.tscn`（convention），逐实例可追溯 |
| 实例名 | `Pascal(entity_id)`；同名冲突 → 拒绝（不静默消歧） |
| 目标关系 | 只接受 `--target` 或 `--relations <entity_graph.json> --relation <name>`；source 必顶 Feature 声明 `target_path`（feature_index interfaces） |
| 自动生成的计划 | `instances` 保留蓝图 entity id + 真实生成场景；无关系声明时计划**不含** `targets` |
| 正式入口 | `--compose-plan` dry-run PASS；宿主含 `target_path = NodePath("../E2eProbePlayer")`，2 个 ext_resource 实例 |
| 真实 Godot | status=PASS/errors=0；双实例命名唯一；enemy 子树仅 enemy 资源、player 子树仅 player 资源；target_path 解析一致且 90 物理帧内真实接近 ≥20px |
| 受控负向 | 缺场景映射 / 未知目标 / 未知关系名 / source 无 target_path 能力 / 同名歧义 / 未知实体 override → 均 exit 1 且**无产物** |

宿主级组件职责审计（任务 E）：出生点、出口门/出口区、宿主级触发器均在
**场景 + LevelConfig/编排层**（`LevelOrchestrator` 注入式契约、`LevelConfig` 的
spawn/exit/victory）；composition plan 只声明「实例 + 目标引用」。本阶段不扩宿主组件
schema（DEFERRED）—— 职责重叠会破坏 4 份契约的边界。

## 本次变更（Phase 1.20）

- `Orchestration/level_config.gd`：新增 boss 模式归一化字段（arena_scene / boss_entity /
  boss_instance_path / boss_spawn / boss_scene）与镜像校验；waves/holdout 拒绝 boss 块。
- `Orchestration/level_orchestrator.gd`：boss 模式（existing 绑定 / on_start 生成）、
  `boss_defeated` 信号、只结算一次、出口区在 Boss 存活时拒绝胜利、`_started` 守卫
  （配置应用前不推进超时/重开）、`fail_setup` bind 阶段诊断。
- `Orchestration/level_host.gd`（新增）：通用组合宿主适配器（配置 → 编排器接线）。
- `Scenes/boss_challenge.gd` + `Levels/boss_challenge.json`：BossChallenge 改用统一编排器。
- `gameplay_planner/level_planner.py`：`validate_level` boss 规则 + `build_boss_level`
  （真实 plan → boss 配置）+ CLI `--mode boss --boss --plan`。
- `level_schema.yaml`：boss 契约、合法值、规则、generator_scope 与示例。
- 测试：`Tests/test_boss_orchestration.gd`（B1–B5）、`test_level_planner.py` L9、
  `test_cross_layer_contract.py` C10、`e2e/boss_level_probe.py` 与 e2e N1–N13。

## 本次变更（Phase 1.19）

- 新增 `scene_composer/plan_generator.py`：Gameplay Blueprint + 实体场景映射 →
  composition plan（映射优先级 override>declared>convention / `Pascal(entity_id)` 实例名 /
  目标只来自 `--target` 或点名 `--relation` / source 必须有 `target_path` 能力 /
  复用 `compose_from_plan` 校验 / 原子写入）；CLI 退出码 0-1-2。
- 新增 `scene_composer/tests/test_plan_generator.py`：Q1–Q12（24 项），含 6 类负向与兼容。
- e2e `test_end_to_end_generation.py`：新增 M1–M6（计划生成 / 蓝图派生关系 / 无关系不造目标 /
  缺映射与未知目标负向）；L9/L10/L16/L17 改为消费**自动生成**的计划（不再手写 dual_plan）。
- `scene_composer_schema.yaml` / `CONTRACT_INDEX.yaml` / e2e README：计划生成产物与入口同步。

## Phase 1.18：Scene Intent 集成与运行时交互编排（实测）

- **composition_plan 正式入口**（契约 scene_composer_schema.yaml#composition_plan）：
  `scene_composer.py --compose-plan <plan.yaml>`（dry-run 只校验不落盘）；
  composite.py `compose_from_plan` 唯一实现；Scene Intent 保持单实体契约不变（并列文档方案）。
- **运行时交互契约**：实体身份 ≠ 宿主实例名 ≠ target 引用（NodePath）；目标由计划显式
  声明（写追击方实例的 `target_path = NodePath("../<实例>")`），构建期拒绝无效目标，
  运行时由 chase_movement 既有相对解析契约消费；真实 Godot L16–L17 验证。
- **统一 Validator 新增 binding 层**：`run_binding_layer` 复用 check_bindings；
  `validate.py --bindings-dir`；信息不足 = info 诊断（不进基线），未知实体 = BINDING_* error。
- 验证：`run_tests.py` **73/73 PASS（exit 0）**；e2e 独立 118 项 PASS；
  composite 单测 16 项；unified validator 29 项；validate.py 0 error / 17 warning 不变。

## Phase 1.17：多实体场景组合与绑定完整性（实测）

- **双实体显式绑定闭环**（e2e L1–L8）：player 与 enemy 走同一条
  discovery → `--resolve-entity-from` → bind_assets → scene_composer 链路；
  player_* 资源全部 `resolved_from=binding`；静态断言最终资源归属与双向无泄漏。
- **多实体组合最小实现** `scene_composer/composite.py`：Godot 原生 instancing
  （宿主只声明 ext_resource + instance 节点），输入场景字节不变，实例名唯一（冲突消歧），
  返回实体→实例映射；CLI `--scene ... --name Host [-o dir] [--json]`。
- **真实 Godot 运行证据**（e2e L11–L15）：宿主 `E2eProbeDualHost.tscn` 由 run_scene
  运行 `status=PASS, errors=0`；瞬态探针断言两实例存在、命名唯一、运行时子树资源归属
  互不覆盖（enemy=slime / player=player）；探针与生成物由 finally + Z1 清理。
- **check_binding_schema.py 增强**（S1–S9）：记录级 role/asset/entity 健康检查、
  `--gameplay` 实体存在性（未知实体 = ERROR）、`binding_scope_errors` 契约字段检查、
  无蓝图 = note（信息不足）。既有版本检查与旧格式完全兼容；业务规则权威仍是 bind_assets。
- 验证：`run_tests.py` **72/72 PASS（exit 0）**；e2e 独立 115 项 PASS；
  validate.py 0 error / 17 warning（与基线逐项相同）。

## Phase 1.16：实体绑定端到端接入（实测）

实体作用域绑定进入**真实生成链路**，实体身份全程可追溯：

```
feature_discovery（payload.role=enemy）
  + gameplay 蓝图实体清单（恰好一个 enemy 角色实体）
  → discovery_to_binding --resolve-entity-from   # 解析唯一实体 id，打上 {entity, role, asset}
  → bind_assets --gameplay --binding             # 作用域路由：目标实体 resolved_from=binding
  → scene_composer --bindings                    # 绑定文档的节点名/资源路径落盘进生成的 .tscn
  → 真实 Godot headless（G8/G9/G10a）            # 生成场景 + 行为探针 PASS
```

零匹配 → `no_entity_with_role`（exit 1）；多匹配 → `ambiguous_entity_role`（exit 1，
诊断含全部候选 id）——归属不可猜测。`--entity` 显式优先。

| 场景 | 证据（e2e C/D/I 段 + test_binding_scope S6） |
| --- | --- |
| 1 多实体不同资源 | C2a/C3/D6/D6b/I1/I1b：作用域只路由到 enemy；玩家实体 idle 仍为 index 推断；生成场景带显式绑定节点（E4）+ 真实 Godot 行为探针 PASS |
| 2 显式 vs 推断冲突 | D7：无绑定推断得 idle=X，实体作用域绑定指向 Y≠X → 最终应用 Y（resolved_from=binding） |
| 3 未知实体 | D8：exit 1 + `binding_scope_errors`（location/entity/reason），不伪造成功 |
| 4 单实体旧格式 | C3b：适配器缺省输出保持 `{role, asset}` |
| 5 多实体 role-level | I2：既有行为保留，跨实体歧义由 compatibility 门禁标记 INCOMPATIBLE |
| 6 发现信息不足 | C6/S6：零匹配 `no_entity_with_role`、多匹配 `ambiguous_entity_role`（exit 1，含候选 id） |

验证：`run_tests.py` → **71/71 PASS（exit 0）**；E2E 独立 → exit 0（100 项 PASS）；
`test_binding_scope.py` → exit 0（29 项）；`validate.py` → 0 error / 17 warning（基线不变）；
真实 Godot（v4.7.stable headless）：G8/G9/G10a + C1–C9 跨层探针全 PASS。

## Phase 1.15：跨层契约与统一校验（实测）

| 交付 | 实现 | 证据 |
| --- | --- | --- |
| I1 绑定 entity 作用域 | `bind_assets.parse_explicit_bindings`（权威实现）：`{entity, role, asset}` 作用域路由 / 未知实体 → `binding_scope_errors`（exit 1，可定位）/ 类型门禁（audio↔visual 错配拒绝且不回退）/ 多实体角色级绑定按既有规则处理 + note 标注 / 结构非法不静默跳过；`discovery_to_binding.py --entity`（可选） | `asset_registry/tests/test_binding_scope.py`（I1-A…I1-G，24 项 PASS）；既有绑定测试 53 项 PASS（无回归） |
| 统一 Validator | `validator/unified.py` 编排既有四层检查器；`validate.py --scene-blueprint/--gameplay-blueprint/--level/--runtime-scene/--runtime-result`（opt-in，缺省兼容）；结构化诊断 `{layer,code,severity,location,path,reason,hint}` + 稳定代码；Runtime Godot 缺失 → UNAVAILABLE/INCOMPLETE（非零） | `validator/tests/test_unified_validator.py`（C10，24 项 PASS）；`validate.py --runtime-scene` 真实 Godot PASS |
| 跨层一致性 | 共享正反例（15 例）同时经 Python `validate_level` 与 Godot `LevelConfig`（真实探针）逐例比较判定与字段路径；C7 缺省值两层一致；C9 绑定边界 | `validator/tests/test_cross_layer_contract.py`（C1–C9，33 项 PASS，15/15 一致） |

命令与退出码（Phase 1.15 时点）：

- `python .ai/tools/run_tests.py` → **71/71 PASS（exit 0）**（新增
  `asset_registry/tests/test_binding_scope.py`、`validator/tests/test_unified_validator.py`、
  `validator/tests/test_cross_layer_contract.py` 均由统一入口自动发现）。
- `python .ai/tools/validator/validate.py` → 0 error / 17 warning（与基线逐项相同）。
- `python .ai/tools/validator/validate.py --level Levels/timed_combat_arena.json --level
  Levels/survival_arena.json --gameplay-blueprint survival_game.yaml --scene-blueprint
  slime_enemy.yaml` → exit 0（scene/gameplay/level×2 全 PASS）。
- `python .ai/tools/validator/validate.py --runtime-scene res://Scenes/EnemyBasic.tscn`
  → exit 0（runtime 层真实 Godot PASS）。
- `python .ai/tools/e2e/tests/test_end_to_end_generation.py` → exit 0（含 I1 回归段）。
- 独立层检查：`check_level.py`（两个发布配置 PASS）、`check_scene_composition.py
  slime_enemy.yaml` PASS、`check_gameplay.py survival_game.yaml` PASS、
  `check_runtime.py --scene`（真实 Godot）PASS。

## Phase 1.14：通用关卡编排管线（实测）

关卡编排从 `TimedCombatArena` 专属实现整理为场景无关管线，**两个真实场景使用同一套实现**：

| 场景 | 模式 | 配置 | 编排职责 |
| --- | --- | --- | --- |
| `Scenes/TimedCombatArena.tscn` | `waves` | `Levels/timed_combat_arena.json`（v2） | 顺序波次、清波推进、出口解锁、进出口区胜利 |
| `Scenes/SurvivalArena.tscn` | `holdout` | `Levels/survival_arena.json`（v2） | 持续生成调度（interval/delay/max_alive）、生存计时、生存胜利 |

通用实现（不依赖任何场景节点路径，全部经注入）：

- `Orchestration/level_config.gd`（`LevelConfig`）：解析 + 校验 + 归一化；错误带配置文件路径 /
  字段路径 / 失败阶段（`config_load` / `config_validate`）。
- `Orchestration/level_orchestrator.gd`（`LevelOrchestrator`）：状态机、生成与登记
  （幂等死亡结算）、waves 顺序波次、holdout 持续生成、出口解锁、胜利判定、胜负一次、
  重开轮询、结构化诊断。
- 场景适配层只做节点引用与表现：`Scenes/timed_combat_arena.gd`（公开 API 原样保留）、
  `Scenes/survival_arena.gd`（保留拾取物 / 陷阱 / 奖励机关 / HUD / 结束冻结 / 遗留导出）。

| 量（真实 Godot，`Tests/test_generic_level_orchestration.gd` G1–G13） | 实测值 |
| --- | --- |
| G1 通用性 | 静态：通用组件无 `NodePath(` / 无场景名（剔除注释）；运行时：程序化合成宿主（非 `.tscn`）完整跑通 波次→开门→入区→Completed，`finish_events=[true]` |
| G2 行为一致 | 发布场景 + 发布配置：3 波（3/3/5）逐波推进、清除途中门关闭、全清后门开、入区 Completed、胜负一次、无效配置零生成 + Failed |
| G3 同一实现 | 两场景编排器同一脚本；survival=`holdout` / arena=`waves`；发布生存配置零错误 |
| G4 玩法不回归 | 0.3s 出敌（interval=0.2）、精英 delay 前不出现、delay 后 1 个、`max_alive=3` 峰值锁死、1.0s 生存胜利（事件一次）、玩家死亡 → Lost、开局拾取物 1 个、陷阱 3 个 |
| G5–G7 | 首波剩敌不启动第二波；第二波清除途中出口关闭；全清后出口开启且状态仍 Playing |
| G8 | 重复 `died` 通知不重复计数 / 不重复推进 |
| G9 | Completed 后再入区 / 玩家死亡：胜负事件仍 `[true]` |
| G10 | 8 类非法配置（waves 与 holdout 规则集）全部拒绝：Failed + 零生成 + `waves=0` + 字段可定位 |
| G11 | 手写 waves / v1 配置 / 缺 exit+victory 选填块 / 遗留导出生存通道均正常 |
| G12 | 手写 waves 混编（普通+精英）生成 2 敌、清空后开门 |
| G13 | 诊断定位：`stage=config_validate` + `config_path` + 字段 + `consumer_scene`；读取失败 `config_load`；实体场景缺失带实体 id 与路径 |

Schema 与校验：version 2（新增 `mode` / `holdout` / `spawns` / `survive_duration`）；
version 1 遗留配置继续有效（v1 + holdout 一律拒绝）。`level_planner.validate_level` 与
GDScript 运行时校验为同一规则集的两个镜像实现（producer/validator 共用前者）。

验证：`python .ai/tools/run_tests.py` → **69/69 PASS（exit 0）**；
`python .ai/tools/e2e/tests/test_end_to_end_generation.py` → exit 0；
`python .ai/tools/validator/validate.py` → 0 error / 17 warning（与基线逐项相同）；
`python .ai/tools/gameplay_planner/tests/test_level_planner.py` → PASS（L1–L8 + 生成器 + CLI）；
临时资源无残留（`Levels/E2eGeneric*` 由测试自身清理并断言）。

## 本次变更（Phase 1.14）

- 新增 `Orchestration/level_config.gd`、`Orchestration/level_orchestrator.gd`（通用编排管线）。
- 重写 `Scenes/timed_combat_arena.gd`（薄适配层，公开 API 与 Phase 1.13 一致）、
  `Scenes/survival_arena.gd`（holdout 适配层 + 场景专属逻辑保留）。
- `Scenes/SurvivalArena.tscn` 增加 `level_config_path`；新增 `Levels/survival_arena.json`；
  `Levels/timed_combat_arena.json` 升级 version 2 + 显式 `mode: waves`。
- `.ai/context/level_schema.yaml`：契约升级（v2 / mode / holdout / 版本兼容 / 生成器边界）。
- `.ai/context/CONTRACT_INDEX.yaml`：`level_orchestration` 条目更新（version 2、两种模式、
  runtime_impl / config_impl、known_limits、generic_test）。
- `gameplay_planner/level_planner.py`：版本兼容 + holdout 校验（`_validate_holdout` /
  `_validate_victory_holdout`）；`build_level` 产出 v2 waves 配置。
- 新增 `Tests/test_generic_level_orchestration.gd`（G1–G13）；
  `gameplay_planner/tests/test_level_planner.py` 增加 L7/L8；
  `Tests/test_survival_arena.gd` 阶段 F 显式走遗留导出通道（断言不变）。
- `.ai/tools/e2e/README.md`：Phase 1.14 证据归位说明（不新增探针，避免复制证据）。

## Phase 1.13：关卡编排生成（实测）

关卡编排层进入生成链路：Gameplay Blueprint → `gameplay_planner/level_planner.py` →
`Levels/<id>.json`（声明式：实体 / 数量 / 波次 / 出口规则 / 胜利条件）→
`Scenes/timed_combat_arena.gd` **运行时消费**。生成数量、波次顺序、出口门与胜利条件全部由配置驱动；
无效配置在运行时被拒绝并给出可定位诊断；手写 `waves` 通道保持兼容。

| 量 | 实测值（真实 Godot） |
| --- | --- |
| 发布配置（`TimedCombatArena.tscn` + `Levels/timed_combat_arena.json`） | 3 波 / 首波 3 敌人，既有 `test_timed_combat_arena.gd` 全 PASS |
| 生成配置（`level_planner` 为 `e2e_probe_enemy` 生成，2 波 2/3） | `spawned_wave1=2`、`index_after_wave1=1`、`alive_after_wave1=3`、`wave2_count=3` |
| 首波未清 → 次波不启动（L9） | 首波存活时 `index` 不推进、`spawned` 不增加 |
| 出口门 | `door_open_with_survivor=0` → 全清后 `door_open_after_all=1` |
| 胜利 | 玩家真实输入进出口区 → `state_after_exit=1`（Completed）、`finish_events=1` |
| 生成物身份 | `entity_scene_match=1`、`focus_hits=5`（全部生成敌人来自 `E2eProbeEnemy.tscn`） |
| 无效配置 | 拒绝：`spawned_wave1=0`、`state=2`（Failed）、诊断定位 `waves[0].entries[0].count` |
| 幂等（L15） | 重复 died 通知不重复计数、不重复推进波次（移除守卫后对应测试立即失败） |
| 直接胜利变体 | `victory=all_waves_cleared` → 清场即 Completed，且出口门不开 |

审计结论（现有系统如何生成敌人 / 管理波次 / 统计死亡 / 控制出口）：

- 敌人在**运行时实例化**（`_spawn_enemy` / `_spawn`），但生成数据此前硬编码在 `.tscn` 导出属性中
  —— 本轮把「配置」外化为关卡 JSON，代码保持既有生成路径。
- 计数与全清：`alive_count`（`died` 递减）+ `waves` + `wave_index`；SurvivalArena 实时统计
  （`_count_enemies()`），BossChallenge 用 tscn `[connection]`。
- 出口与胜利：最后必需波次清空 → 开门 → `ExitZone.body_entered`（需门已开）→ `_finish(true)`。
- 生成实体与手写实体在竞技场中的接口相同：入口场景根 CharacterBody2D + 子节点 `Health` 命名约定
  （Phase 1.11 / 1.12 已验证）。

为什么是 JSON：Godot 无 YAML 解析；项目已有 JSON 产物先例（`feature_index.json`、
`gameplay_blueprints/*.json`）。契约文档仍是 YAML（`.ai/context/level_schema.yaml`）。

## Phase 1.12：死亡与胜利闭环（实测）

生成的敌人被**真实攻击输入路径**（空格 → `AttackTrigger` → `Health.take_damage`）打死，
死亡语义完全由既有 `Health` 拥有（`died` 信号）；场景编排层接收后递减击杀计数并让实体
退出战斗；最后一个必需敌人清空时由**场景自身逻辑**打开出口，玩家真实输入走进出口区完成。

| 量（生成物 `Scenes/E2eProbeEnemy.tscn`，宿主 `TimedCombatArena.tscn`） | 实测值 |
| --- | --- |
| 真实攻击结算 | `damage=1`、`max_health=5`、hp `5 → 4 → 0`（5 次攻击） |
| 死亡事件 | `died_events=1`（重复攻击 / 再次 take_damage 仍为 1） |
| 击杀计数 | `2 → 1`，重复攻击后仍 1；`live_entities=1 == alive_count` |
| 退出战斗 | `removed=1`（`died → queue_free` 既有规则） |
| 不提前胜利 | `door_open_with_survivor=0`、`premature_victory=0` |
| 胜利条件 | 最后一个敌人死后出口门由场景逻辑打开；玩家进出口区 → Completed、`finish_events=1` |

关键机制与产物：

- 审计结论：死亡由 `Features/health` 拥有（`died` 信号）；清理/计数/胜负全在场景编排胶水
  （TimedCombatArena / SurvivalArena / BossChallenge 的 tscn `[connection]`），**无**全局死亡或
  敌人管理器；奖励只有击杀计数与 `Systems/reward` 注册表契约，没有货币/掉落。
- 真实缺口 = 数据：`Scenes/TimedCombatArena.tscn` 的 `AttackTrigger` 未配 `target_group`，
  空格攻击解析不到目标；与 InterruptRange/SiegeGate/StunTraining 对齐加上
  `target_group = "enemies"`。
- 运行时闸门：新增 `.ai/tools/e2e/death_victory_probe.py`（N1/D1/D2/N2/V1/V2 断言 +
  `DEATH:` / `VICTORY:` 机读行 + `--expect survive` 受控负向），把生成场景放进**真实竞技场**。
- 永久回归：`Tests/test_timed_combat_arena.gd` M 段（真实攻击输入路径 → died → 计数/退出战斗）。
- 生成链路未改动：审计表明生成实体的死亡/管理接口已达到既有敌人同等水平
  （实体根可接收 `target_path`、子节点 `Health`、分组由编排层添加），缺口在游戏侧接线。

## Phase 1.11：生成实体的玩法闭环（实测）

修复后，Scene Composer 生成的敌人**实体根**真正在物理帧中移动，并在与玩家真实物理接触后
按现有 `ContactDamage + Health` 机制结算伤害（不修改生命值、不伪造信号）。

| 被测物（真实 Godot） | root_approach | child_max_drift | damage_total | HP |
| --- | --- | --- | --- | --- |
| 修复前旧生成物 `Scenes/SlimeEnemy.tscn`（现已重新生成） | 0.0 px | 120.0 px | 0 | 10 → 10 |
| 修复后生成物（e2e 场景 / 重新生成的 SlimeEnemy） | 120.0 px | 0.0 px | 3（节拍上限 5） | 10 → 7 |

关键机制：

- Feature Scene Template 声明 `attach.root_instance`（`chase_movement`）——实体根就是追击
  组件的入口场景实例，追击脚本驱动实体本身（不再作为子节点“自己跑”）。
- Feature Scene Template 声明 `attach.nodes`（`chase_movement` 的体积形状、`contact_damage`
  的接触形状）——Entity Blueprint 推导把作者 nodes + 成员模板节点写入 `nodes[]`；
  契约 known gap `entity_blueprint_nodes_dropped` 因此关闭。
- 静态闸门：`scene_validator` 在计划声明根实例时要求根必须是该实例、且该组件不得再作为
  子节点出现（旧结构会被拒）；`test_generator` 对根实例组件断言根节点类型。
- 运行时闸门：`.ai/tools/e2e/behavior_probe.py` v2（实体根位移 / 子节点不自移 / 无接触不受伤 /
  接触伤害节拍 / 目标释放后停止），配合变异体（去掉 ContactShape）做受控负向。

## Phase 1.10：玩法行为验证（实测；Phase 1.11 已扩展为实体根 + 接触伤害）

新增 `.ai/tools/e2e/behavior_probe.py`：对生成链路的产物在真实 Godot 中执行行为断言
（观察位置/距离变化，不是节点/信号存在性）。主行为 = 敌人追踪目标并实际移动，
目标使用项目真实玩家实体场景 `Features/player_movement/Player.tscn`。

实测（物理帧 60 Hz，speed=80）：距离 `400.0 -> 280.0`（approach=120.0 px）、
`baseline_drift=0.0`（未配置目标时静止）、`post_free_drift=0.0`（目标释放后停止）。
受控负向：只含 `health` 的生成场景 → 探针 `exit_code=1` +
`Precondition: ... 不存在 ChaseMovement 组件`。
独立复用：`Scenes/Enemy.tscn`（追击组件为根）与 `Scenes/SlimeEnemy.tscn`（为子节点）
两种结构均 PASS，说明探针不绑定单一生成形状。

断言阈值与诊断约定见 `.ai/tools/e2e/README.md`（断言表 + `BEHAVIOR:` 行机读字段）。

## Phase 1.9：端到端闭环现状（实测，非推测）

| 阶段 | 状态 | 证据 |
| --- | --- | --- |
| 自然语言 → Gameplay Blueprint | IMPLEMENTED_AND_TESTED | `gameplay_planner/planner.py`；e2e A1–A3 |
| Gameplay → 每实体 Entity Blueprint | IMPLEMENTED_AND_TESTED（本次新增） | `blueprint_generator.write_entity_blueprints` + `planner --emit-entities`；e2e A4–A8/G3 |
| Feature Discovery | IMPLEMENTED_AND_TESTED | `feature_registry/feature_discovery.py`；e2e B1–B5 |
| 显式候选选择 | IMPLEMENTED_AND_TESTED | `discovery_to_binding.py --select`；e2e C1–C5 |
| Resource Binding | IMPLEMENTED_AND_TESTED（作用域缺口） | `bind_assets.py --gameplay --binding`；e2e D1–D5、I1 |
| Scene Intent / 场景生成 | IMPLEMENTED_AND_TESTED | `scene_composer.py`（Gate + Capability Contract + Artifact Evidence）；e2e E1–E9 |
| 静态验证 | IMPLEMENTED_AND_TESTED | `check_scene_composition.py`、`check_gameplay.py`；e2e F1、G4/G7。`validate.py` 不调用后两者 |
| Godot 运行时 | IMPLEMENTED_AND_TESTED | `runtime/run_scene.py`；e2e G8/G9（真实 headless） |
| 玩法行为验证 | IMPLEMENTED_AND_TESTED（实体根追踪 + 接触伤害，Phase 1.11） | `e2e/behavior_probe.py` 在真实 Godot 中对**生成场景**断言实体根位移、子节点不自移、接触前后玩家生命值变化与节拍上限；e2e G10a–G10h、G11、G12 |
| 死亡与胜负闭环 | IMPLEMENTED_AND_TESTED（Phase 1.12） | `e2e/death_victory_probe.py` 把生成场景放进真实 `TimedCombatArena.tscn`，经真实攻击输入击杀 → `died` 一次 → 计数减一 → 实体退出战斗 → 全清后场景自身开门 → 进出口区 Completed；e2e J1–J9 + `Tests/test_timed_combat_arena.gd` M 段 |
| 失败诊断与自修复 | IMPLEMENTED_AND_TESTED（既有） | `runtime/self_repair.py` + `test_self_repair.py` / `test_asset_self_repair.py`（本轮未改） |

## 本次变更（Phase 1.13）

- 新增 `.ai/context/level_schema.yaml`：关卡编排契约（字段含义 / 合法值 / 默认值 / 校验规则 +
  可运行示例）；JSON 为运行时表示、YAML 为契约档案，两者字段一致。
- 新增 `.ai/tools/gameplay_planner/level_planner.py`：Gameplay Blueprint → 关卡配置；
  `validate_level` 为唯一校验实现（producer 与 validator 共用）；CLI 支持 `--emit` / `--check`。
- 新增 `.ai/tools/validator/check_level.py`：独立校验 CLI（与 check_gameplay / check_scene_composition 同构）。
- 新增 `Levels/timed_combat_arena.json`：随仓库发布的真实关卡配置。
- `Scenes/timed_combat_arena.gd`：改为 `level_config_path` 驱动（加载 + 运行时校验 + entries 生成 +
  出口 / 胜利规则 + 按实例幂等的 `died` 结算 + 可定位诊断）；配置无效拒绝开始；手写 `waves` 兼容。
- `Scenes/TimedCombatArena.tscn`：移除硬编码 `waves` 与敌人场景引用，改指向配置文件。
- 新增 `Tests/test_level_orchestration.gd`（发布配置消费 + L7–L15 + 直接胜利变体 + 无效配置拒绝
  + 手写 waves 兼容）；新增 `gameplay_planner/tests/test_level_planner.py`（L1–L6 + 生成器 + CLI）。
- 新增 `.ai/tools/e2e/level_orchestration_probe.py`（生成配置的运行时消费）；
  `e2e/tests/test_end_to_end_generation.py` 新增 K 段（K1–K12）。
- `CONTRACT_INDEX.yaml` / `e2e/README.md`：契约与探针文档同步。

## 本次变更（Phase 1.12）

- `Scenes/TimedCombatArena.tscn`：`AttackTrigger.target_group = "enemies"`（真实攻击路径接线，
  纯数据修正；此前空格攻击解析不到目标）。
- 新增 `.ai/tools/e2e/death_victory_probe.py`：生成实体的死亡/胜利闭环探针
  （真实竞技场宿主 + 真实攻击输入；`--expect die|survive`；临时脚本 `Tests/e2e_death_victory_probe.gd`
  非 `test_` 前缀并在 finally 删除）。
- `Tests/test_timed_combat_arena.gd`：新增 M 段（真实攻击输入路径驱动死亡与计数）+
  `_press_attack` / `_on_enemy_died` 辅助（死亡后不触碰已释放节点，改用信号镜像）。
- e2e：新增 J1–J9（正向、手写等价性、不死变异体双向负向、缺少运动能力的实体、清理断言），
  Z1 扩展至新探针脚本与变异体场景；README 补探针断言表。

## 本次变更（Phase 1.11）

- `Features/chase_movement/template.yaml`：`attach.root_instance: true` + `attach.nodes`
  （默认体积形状 28×28）；`Features/contact_damage/template.yaml`：`attach.nodes`
  （接触形状 36×36）。Feature 使用说明同步（feature.yaml composition.usage）。
- `template_loader.derive_scene_blueprint`：Entity Blueprint 推导 root.scene（根实例）与
  nodes[]（作者 nodes + 成员模板节点，作者优先；冲突/歧义报错）。
- `scene_builder`：入口场景 == root.scene 的组件不再实例化为子节点。
- `scene_validator`：计划声明根实例时改判根实例（静态解析被引用场景根类型；缺根实例 /
  重复子节点为失败）；`test_generator`：根实例组件断言根节点类型。
- 新增 `scene_composer/tests/test_entity_root_instance.py`（5 组契约回归）。
- e2e：新增 G6b–G6d（结构语义）、G10f–G10h（实体根位移 / 子节点不自移 / 接触伤害）、
  G12（去接触形状变异体的受控负向）；探针 v2 支持 `--expect damage|none`。
- 产物重新生成：`Scenes/SlimeEnemy.tscn`、`Tests/test_slime_enemy.gd`（同一 blueprint）；
  `Tests/test_slime_asset_binding.gd` 改为断言实体根即追击组件 + 碰撞形状。

## 本次变更（Phase 1.9 + 1.10）

- 新增 `.ai/tools/e2e/behavior_probe.py`（Phase 1.10）：生成场景的真实玩法行为探针
  （可独立运行；渲染临时 GDScript → 真实 Godot → 断言距离变化 → 清理）。
- 新增 `planner --emit-entities`：Gameplay Blueprint → 每实体 Entity Blueprint（复用声明的实体不产出）。
- 修 `scene_composer` / `test_generator` 跨盘符 `os.path.relpath` 崩溃（生成成功却 exit 1）。
- 修 `feature_discovery` 词匹配路径缺反混淆（敌方需求不再拖入 `player_movement`）。
- 新增 `.ai/tools/e2e/`（跨工具集成套件，自动被 run_tests.py 发现）+ README。

## 待解决（阻塞项）

- ~~显式绑定无 entity 作用域~~（Phase 1.15 已关闭：`{entity, role, asset}` 作用域 +
  可定位错误 + 类型门禁 + I1-A…G 回归测试）。
- ~~`validate.py` 未串联 Scene/Gameplay/Runtime 三个 check~~（Phase 1.15 已关闭：
  `unified.py` 编排 + Layer Checks flags + 稳定诊断代码；Runtime 缺失如实 INCOMPLETE）。
- Asset Manifest 17 条既有 missing-path 警告。
- ~~e2e 生成链路尚未改用适配层 `--entity`~~（Phase 1.16 已关闭：主链路经
  `--resolve-entity-from` 打上实体作用域并实际消费；旧格式路径保留为兼容通道）。
- 统一诊断错误代码依赖检查器失败文本前缀（未识别文本回退层默认代码；检查器文案
  改动需同步前缀表）。
- Runtime 层探针耗时，为显式 opt-in；缺省 Validator 只做快速静态检查（按层区分覆盖）。
- 实体身份解析以 role 为粒度：同角色多实体时必须由调用方 `--entity` 显式消歧
  （发现阶段 query 为自然语言，不感知实体 id——契约设计如此）。
- ~~多实体「合并场景」的运行时绑定验证不在当前链路覆盖内~~（Phase 1.17 已关闭：
  `composite.py` 原生 instancing 组合 + L11–L14 真实 Godot 运行时资源归属断言）。
  仍开放的部分：合并场景的**物理/逻辑交互**（碰撞、目标指派）不在 composite 职责内，
  由关卡编排层或后续阶段承担。
- 宿主组合器不解析实体场景内部结构（不做 Scene Intent 第二套管线）；实例冲突只按
  根名消歧，无节点级去重语义。
- 宿主级组件（出生点 / 出口区 / 宿主触发器）仍在场景 + LevelConfig/编排层；
  composition plan 不承载它们（Phase 1.19 已审计，扩展 DEFERRED）。
- 计划生成器的目标关系只支持**点名消费**（`--relation`）；relation → target 无语义映射表，
  且 source 必须确有输出 `target_path` 的 Feature（否则拒绝）。
- ~~`BossChallenge` 未接入通用编排~~（Phase 1.20 已关闭：使用同一 LevelConfig + LevelOrchestrator）。
  仍开放：`BossChallenge` 只使用单阶段 boss；多阶段组合宿主由生成链路覆盖。
- holdout 模式无出口概念；顺序波次仅 waves 模式支持；并行刷怪、随机刷怪、动态难度、
  按时间调度仍不支持。
- 拾取物 / 陷阱 / 奖励机关由场景适配层管理，不纳入关卡编排配置。
- 生成器（`level_planner.py`）产出 waves / boss / 多阶段 boss 配置；holdout 配置仍为手工编写。
- 遗留上限语义差异：原 `SurvivalArena` 的 `max_enemies` 为组计数（含精英）；通用化后
  `holdout.max_alive` 为编排层登记总上限，仅手工注入未登记实体时计数口径不同。
- Scene Composer 仍只生成实体场景，不生成关卡场景本身（竞技场宿主仍是手写场景）。
- 奖励经济不存在（只有击杀计数 + 胜负结算），未发明货币/掉落机制。
- 死亡表现即「按既有规则移除」（`queue_free`），无死亡动画/终结状态机可验证。
- 其他手写场景（EnemyBasic.tscn / Boss / EliteEnemy 等）未重新生成；它们的
  追击根归属与新规则一致与否由静态闸门（声明根实例时）与探针分别把关。
- 多阶段 `on_start` Boss 没有宿主实例，故不参与 composition_plan 的实例交叉校验；
  这是显式策略，不是遗漏。
- 阶段类型目前只有 clear_enemies / defeat_boss / complete_level；没有血量阈值、
  限时阶段或通用状态机（按任务范围刻意保持最小）。

## Current Capabilities

### 可复用 Feature（Features/，12 个）

- player_movement、health、health_bar、contact_damage、heal_pickup
- collect_pickup、condition_gate、trigger_switch、openable_door
- chase_movement、moving_platform、stun

### 验证场景（Scenes/ + Tests/）

- 场景组合实验：survival_arena、escape_room、boss_challenge、timed_combat_arena、interrupt_range、stun_training、siege_gate 等
- 对应集成测试位于 Tests/（test_siege_gate.gd、test_timed_combat_arena.gd 等）

## Round 8 结论（详见 CURRENT_TASK.md）

多机制汇聚于同一实体：各 Feature 自有状态 + 公开行为接口，Scene Glue 只做事件连接与路由，不引入跨 Feature 仲裁器。

## Round 9 结论（Gameplay Loop Composer，详见 DECISIONS.md AD-009）

自然语言 → Gameplay Blueprint（entity/scene 复用 + systems + loop）→ Entity/Scene 生成 → check_gameplay → 循环测试：多实体玩法;i循环全链机读化。跨实体流程用 System Registry 描述（Systems/*/system.yaml），不实现 Manager。

## Round 10 / Phase 1.6 结论（Runtime Playtest & Self-Repair，详见 DECISIONS.md AD-010）

静态验证通过 ≠ 项目能跑。新增 Runtime Correctness 层：真实启动 Godot 运行 Scene，观测事实
（exit_code / duration / stdout / stderr / parsed events）→ 诊断（12 类 classification + likely_cause
+ related feature/scene + confidence）→ 修复计划（安全边界硬约束）→ 最小修复（单点字面量替换）→
静态验证 → 重跑；修复无效或引入新错误自动回滚，最多 max_repair_attempts 次。
Validator 增加第 5 阶段（check_runtime.py，只判定不修复），Validator 本身仍只做静态验证。

## Framework

- 入口：AI_ENTRY.md → .ai/config/agent.yaml → skill-registry.yaml
- Validator：.ai/tools/validator/validate.py（仅按需执行）；Runtime Validation（第 5 阶段）：
  .ai/tools/validator/check_runtime.py
- Runtime Playtest：.ai/tools/runtime/（run_scene / run_project / capture_output / runtime_result /
  diagnose_runtime / repair_plan / repair_engine / self_repair）；契约 .ai/config/runtime-playtest.yaml
- 决策记录：.ai/memory/DECISIONS.md（AD-001 ~ AD-010）

## Test Status（最近一次全量验证，Phase 1.24 时点）

- 统一入口 `python .ai/tools/run_tests.py`（最终验证，2026-10-18）：**79 项中 78 PASS
  （exit 1）**——唯一失败 `test_cross_layer_contract.py` 为**环境删除守卫终止**
  （SAFE_DELETE_BULK_CONFIRM_REQUIRED：同一命令内工作区删除达 50 次上限后终止进程，
  恰逢其自清理阶段；其 C1–C9 契约断言全部 PASS，独立运行 4 次均 66/66）。分段运行
  （每段独立命令 = 独立删除预算）**全部通过**：--godot-only 36/36、asset_registry
  11/11、e2e 1/1、feature_registry 4/4、gameplay_planner 2/2、runtime 4/4、
  scene_composer 17/17、validator 7/7。根因与分段命令清单见 run_tests.py 文档头。
- E2E 独立运行：`python .ai/tools/e2e/tests/test_end_to_end_generation.py` →
  exit 0，**171 项 PASS**（T5a–T5d：四种编排模式 trace 与各自批准基线逐事件比较全过；
  T8/T9 差异注入 REGRESSION + exit 1；T13 基线不可被运行改写；T14 无残留）。
- 黄金基线专项：`validator/tests/test_trace_baselines.py` → exit 0（**57 项**，
  含 Phase 1.24 的 U49–U56 审批安全：篡改/替换/无指纹/追加事件全部拒绝且基线不动）；
  回放器单测 `test_orchestration_trace.py` → exit 0（44 项）。
- Godot 专项（适配层转发器与 holdout CLI 改动后复跑，全部 exit 0）：
  test_orchestration_trace / test_boss_orchestration / test_boss_challenge /
  test_survival_arena / test_timed_combat_arena / test_generic_level_orchestration /
  test_elite_enemy。
- 其他套件独立运行（全部 exit 0）：composite（17）、binding_scope（29）、
  binding_schema_checks（14）、unified_validator（36）、cross_layer_contract（66）、
  level_planner（134，含 holdout CLI）、plan_generator（25）；`check_level.py`
  两个发布配置 PASS。
- Framework Validator：PASS（0 error / 17 warning；与基线逐项相同）。
- 真实 Godot：4.7.stable.official.5b4e0cb0f（headless）；T4 四场景沙箱捕获、
  P14–P18、G8/G9/G10a、L11/L16–L17 均以真实二进制执行。

> 注意：本文件记录「最后一次验证时的快照」。如需最新逐项状态，以 git log 与 Tests/ 为准。
