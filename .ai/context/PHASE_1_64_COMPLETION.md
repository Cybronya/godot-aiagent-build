# Phase 1.64 执行完成报告 — Systematic L5 Behavioral Coverage Expansion

完成时间：2026-11-04。分支 `master`，HEAD `dd3a0e4d5d0f6f47e3a9c729e3ce89190f019bd8`（**未提交**）。
未执行任何 git 写操作（无 add/commit/push/reset/checkout/clean/restore/rebase）。

配套文档：

- `PHASE_1_64_AUDIT.md` — 只读审计（仓库状态、1.63 交付核对、四个发现）
- `PHASE_1_64_INITIAL_COVERAGE.md` + `.ai/tmp/p164/initial/coverage_matrix.json` — 初始覆盖基线
- `PHASE_1_64_BEHAVIOR_INVENTORY.md` — 60 条 Behavior 的分类与风险排序（生成器产出）
- `PHASE_1_64_VERIFICATION_PLAN.md` — 风险公式、分批计划、16 步流水线
- `PHASE_1_64_BATCH_1_REPORT.md` — 第一批真实验证
- `PHASE_1_64_COVERAGE_TREND.md` — 同口径前后对比
- `PHASE_1_64_ATTACK_TESTS.md` — 攻击/安全边界

---

## 1. 仓库状态

| 项 | 值 |
| --- | --- |
| HEAD | `dd3a0e4d5d0f6f47e3a9c729e3ce89190f019bd8`（与审计时一致） |
| 分支 | `master` |
| 已跟踪修改 | 53（与审计时一致，**本阶段未新增对既有文件的修改**，只改了 §2 列出的两个 Runner） |
| 未跟踪 | 978 → 987（新增全部来自本阶段：`env_paths.py`、`run_p164_batch.py`、`knowledge/**`、`PHASE_1_64_*`、`.ai/tmp/p164/**`、`.ai/knowledge/**`） |
| 暂存区 | 0 |
| 其他 Agent 工作 | 未覆盖：1.60–1.63 的产物目录（`p159`/`p160_e2e`/`p161_e2e`/`p162`/`p163_e2e`）只读，本阶段所有运行写自己的目录 |

## 2. 本阶段修改文件清单

新增：

| 文件 | 作用 |
| --- | --- |
| `.ai/tools/validator/execution/env_paths.py` | 项目根 + Godot 统一解析；显式 `GODOT_BIN` → 项目配置 → 相邻目录 → PATH；缺失即环境错误 |
| `.ai/tools/validator/execution/run_p164_batch.py` | 分批验证 Runner：复用 1.63 全链，expected 来自已审批 Binding，逐 Behavior 出评估结论 |
| `.ai/tools/validator/tests/test_env_paths.py` | 18 项（项目根/优先级/无回退/环境错误/Runner 回归） |
| `.ai/tools/knowledge/behavior_verification/store.py` | Knowledge 存储与强制校验（来源类型、历史不覆盖、契约版本、事实不得静默丢弃） |
| `.ai/tools/knowledge/behavior_verification/build_records.py` | 从真实产物生成 Knowledge 记录（契约/绑定/证据/评估/mutation/历史失败） |
| `.ai/tools/knowledge/behavior_verification/tests/test_knowledge_store.py` | 18 项 |
| `.ai/knowledge/behavior_verification/**` | 7 条 Knowledge 记录 + 历史版本文件 |
| `.ai/context/PHASE_1_64_*.md` | 本阶段文档（7 份） |
| `.ai/tmp/p164/**` | 全部运行产物（before/after 矩阵、mutation、E2E 日志、batch1 证据与 runs） |

修改（仅两处，均为 1.62 缺陷的最小修复）：

| 文件 | 改动 |
| --- | --- |
| `validator/execution/run_execution_e2e.py` | `_PROJECT_ROOT` → `env_paths.project_root(__file__)`；Godot → `env_paths.require_godot()`（保留 20 checks 口径） |
| `validator/execution/run_multi_feature_e2e.py` | 同上；`assert godot not found` → 明确环境错误（exit 2） |

`evaluation/mutation/mutation_catalog.yaml` 追加 M11/M12 两条（加法，未改动既有条目）。

未触碰：`Features/**`、`validator/bindings/**`、`validator/provenance/**`、`evaluation/*.py`、
`.ai/skills/**`、1.59–1.63 的任何产物。

## 3. Behavior 分类

动态读取：**23 Feature / 60 Behavior**（`Features/*/template.yaml#behavior`）。
分类依据是契约的 actions/preconditions/expected + 实现源码（不是 ID/名称），逐条依据见
`PHASE_1_64_BEHAVIOR_INVENTORY.md` §3。

| 主类 | 数量 | 代表 |
| --- | --- | --- |
| A 状态转换 | 27 | `health/damage`、`state_machine/*`、`stun/hit_stuns_and_freezes_host` |
| B 事件传播 | 3 | `knockback/knockback_applies_and_signals`、`screen_shake/trauma_starts_shake`、`hit_flash/hit_flashes_host` |
| C 持久化 | 2 | `save_game/*` |
| D 资源生命周期 | 4 | `collect_pickup/collect_on_contact`、`projectile/lifetime_expiry_frees_projectile`、`sfx_pool/*` |
| E 交互 | 7 | `attack_emitter/raycast_hit_deals_damage`、`contact_damage/*`、`player_movement/*` |
| F 守卫与条件 | 17 | `i_frames/iframes_block_damage_within_window`、`condition_gate/*`、`trigger_switch/latch_once` |

- 多标签：26 条有次类（如 `stun/hit_stuns_and_freezes_host` = A + E + B）。
- 未能分类：**0**；生成器在契约新增未登记 Behavior 时会直接失败（MAPPING MISMATCH），不会给默认分类。
- 风险排序：`risk = 2I + 2S + 3D + 1E + 2R + 2G + (readiness?0:1)`，前 8 名见
  `PHASE_1_64_VERIFICATION_PLAN.md` §2 与 INVENTORY §2。风险分**不是**正确性证明。

## 4. 覆盖变化（同口径 before → after）

| 维度 | Before | After | Δ |
| --- | --- | --- | --- |
| Evidence Verified | 8 | **12** | +4 |
| Signature Verified | 8 | **12** | +4 |
| Attestation Verified | 8 | **12** | +4 |
| Evaluation VERIFIED_PASS | 8 | **12** | +4 |
| Holdout Available | 1 | 1 | 0 |
| L5 Mutation Killed（Behavior 数） | 9 | **10** | +1 |
| Knowledge 记录 | 0 | **7** | +7 |
| **Fully Covered** | **0** | **1** | **+1** |

比例：Evidence/Signature/Attestation/Evaluation 各 **20%**（12/60）、Mutation **16.7%**（10/60）、
Knowledge **11.7%**（7/60）、Fully Covered **1.7%**（1/60）。

Fully Covered 的那一条是 `openable_door/open`（契约 + 绑定 + 证据 + 签名 + attestation +
评估 + Holdout + L5 KILLED 八维齐全）。其余 59 条都有 `missing_requirements`。

## 5. 真实 E2E（Batch 1，6 条 Behavior / 3 个 Feature）

| Feature | Behaviors | Run ID | Artifacts | Signature | Attestation | Evaluation |
| --- | --- | --- | --- | --- | --- | --- |
| `save_game` | 2（C） | `c8d79878-1056-4af5-b245-3f09422dd573` | 16 | SIGNATURE_VERIFIED | ATTESTED_VERIFIED | 2/2 PASS |
| `i_frames` | 3（F/A/F） | `5bfa2856-ea71-4f25-834b-43ab0644b3b0` | 24 | SIGNATURE_VERIFIED | ATTESTED_VERIFIED | 3/3 PASS |
| `openable_door` | 1（A+B） | `d99530a9-0502-4759-8eaa-98d3429aed02` | 8 | SIGNATURE_VERIFIED | ATTESTED_VERIFIED | 1/1 PASS |

- 环境：Godot `4.7.stable.official.5b4e0cb0f`，**未设置 `GODOT_BIN`**（验证 §2 的修复），项目根 `F:\Godot_v4.7-stable\game`。
- 21 项链路检查 0 失败：契约 → 门禁 → 真实采集（replay=2）→ bundle integrity → Ed25519 签名 → manifest → attestation → 验签 → Evaluation。
- 逐 Behavior 的 Run/Digest 见 `PHASE_1_64_BATCH_1_REPORT.md` §2。
- Evidence Signature 与 Execution Attestation 是**两个独立证明对象**，分别验证；本批两者都通过，但没有把"有签名"当成"执行已被证明"。

## 6. Mutation

| Mutation | 目标 Behavior | 缺陷模型 | 真实触发证据 | 判定 | 恢复 |
| --- | --- | --- | --- | --- | --- |
| M01–M10（1.59/1.63 既有） | 8 个 Behavior | 见 catalog | 重跑全部复现 | **10/10 KILLED** | 逐字节 true |
| M11 | `i_frames/iframes_expire_and_damage_resumes` | 窗口到期不归还 Health 无敌门 | control `current=8` → mutant `9` | **KILLED** | true |
| M12 | `openable_door/open` | 幂等守卫 `==`→`!=`（门永远打不开） | control `is_open=true` → mutant `false` | **KILLED** | true |

- 10 条复现批次：`mutations: total=10 effective=10 killed=10 survived=0 invalid=0 error=0 timeout=0 not_run=0`（`summary-71c00e8b.json`，`.ai/tmp/p164/mutation/`）。
- 新增批次：`total=2 effective=2 killed=2 ...`（`summary-3de41ad2.json`，`.ai/tmp/p164/mutation2/`）。
- 每条 KILLED：control `VERIFIED_PASS` + recovery `VERIFIED_PASS`、`restored_byte_for_byte=true`、`repo_guard.changed=false`。
- catalog 12 条覆盖 10 个 Behavior；INVALID 不计入 KILLED，SURVIVED 本阶段为 0（没有出现"注入生效但链路没发现"）。
- 矩阵需要单一 mutation 目录，因此把两个批次的报告 JSON **复制**到 `.ai/tmp/p164/mutation_all/`（共 12 份，只复制、不改内容）；
  Knowledge 记录仍引用**原始**报告路径（`mutation/reports`、`mutation2/reports`），避免复制品让事实漂移。

## 7. Knowledge

- 位置：`.ai/knowledge/behavior_verification/<feature>/<behavior>.json`（+ `.history.jsonl`）。
- 记录：**7**（Batch 1 的 6 条 + `trigger_switch/latch_once`）。
- 来源分布：CONTRACT_FACT 31、TEST_OBSERVATION 12、MUTATION_OBSERVATION 8、INFERENCE 7。
- 历史版本：每次写入把旧记录整条追加到 `.history.jsonl`；store 拒绝丢弃既有事实、拒绝契约版本静默升级。
- 失败知识：2 条（M04 latch 守卫走不到、M06 `user://` 残留），都含失败场景/输入/预期/实际/产物/源码位置/根因/修复/修复后验证，状态 `RESOLVED`。
- 置信度：`VERIFIED_EXECUTION` 5、`PARTIAL` 2（`killing_blow_still_dies` 无 mutation；`latch_once` 无本轮证据）。
- 未解决：6 条记录带未解决问题（缺 Holdout、缺 mutation 或本轮证据），明确标注，不当成 PASS。

## 8. 测试

### 新增

| 套件 | 项数 | 结果 |
| --- | --- | --- |
| `validator/tests/test_env_paths.py` | 18 | **18/18 PASS** |
| `knowledge/behavior_verification/tests/test_knowledge_store.py` | 18 | **18/18 PASS** |

### 回归（本次真实重跑）

| 套件 | 项数 | 结果 |
| --- | --- | --- |
| `validator/execution/tests/test_attacks.py`（1.62 攻击） | 31 | 31/31 PASS |
| `validator/provenance/tests/test_provenance_attacks.py`（1.61 攻击） | 32 | 32/32 PASS |
| `validator/tests/test_binding_candidates.py`（1.63） | 26 | ALL PASS |
| `evaluation/tests/test_coverage_matrix.py`（1.63） | 15 | ALL PASS |
| 1.62 单 Feature E2E（修复后，无 `GODOT_BIN`） | 20 | 20 checks / 0 failures / exit 0 |
| 1.62 多 Feature E2E（同上） | 3 features | 3 attestations verified / 0 failures / exit 0 |
| 1.63 三 Feature 全链 E2E（同上） | 24 | 24 checks / 0 failures / exit 0（含 holdout + evaluation） |
| Mutation 全量复现 | 10 | 10/10 KILLED |
| Mutation 新增 | 2 | 2/2 KILLED |
| Coverage Matrix 重算（before/after） | 2 次 | 均 exit 0，`rows=60` |
| `run_tests.py` 全量入口 | 138 | **133 PASS / 3 FAIL / 2 INCOMPLETE（见 §8.1）** |

### 8.1 `run_tests.py` 全量入口（完整结果，不掩饰失败）

启动：`python .ai/tools/run_tests.py`（无过滤，日志 `.ai/tmp/p164/run_tests_full.log`）。
**跑完全部 138 个文件**，汇总行：

```
[run_tests] completed=138/138 passed=133 failed=3 incomplete=2 unavailable=0 not_executed=0
```

**INCOMPLETE（2）**

| 文件 | 原因 | 归因 |
| --- | --- | --- |
| `.ai/tools/e2e/tests/test_end_to_end_generation.py` | 单文件超 1800s 被 harness 判 TIMEOUT（期间持续有 Godot 子进程 churn；日志中 T2–T5a 已 PASS 到 `multi_stage_boss` 11/11 事件） | **未完成**，不算通过，也不算失败 |
| `.ai/tools/evaluation/tests/test_phase160_e2e.py` | `exit=2`：`error: the following arguments are required: --evidence-dir` | **既有 harness 缺陷（1.60 遗留）**：该套件本身就是需要参数的 E2E 入口，被当成单元测试调用；与本阶段改动无关 |

**FAILED（3，均为既有环境问题，非本阶段引入）**

| 文件 | 失败检查 | 归因 |
| --- | --- | --- |
| `scene_composer/tests/test_scene_composer.py` | 8 项 `template: <name> exists` | 仓库里有 8 个**未跟踪**的 Feature 脚手架（`anima_behaviour`、`attribute_editor`、`audio_player_pool`、`blackboard`、`clean_copy`、`flying_letter`、`pedestal_interaction`、`pickable_audio`），有 `feature.yaml`/`.gd` 但**没有 `template.yaml`**；composer 的模板完备性检查于是失败 |
| `scene_composer/tests/test_feature_capability_adoption.py` | 同源模板/能力断言 | 同上 |
| `scene_composer/tests/test_feature_capability_pipeline.py` | 同源 | 同上 |

核查依据：

- `git status --short Features` 显示这 8 个目录都是 `??`（未跟踪，本阶段未创建、也未修改）；
  `git ls-files Features | wc -l` = 217，本阶段没有对这些路径做过任何写入。
- `ls Features/anima_behaviour` 只有 `README.md / *.gd / feature.yaml / test_*.gd`，确认无 `template.yaml`。
- 本阶段的写入清单（§2）只涉及 `.ai/**`，不含 `Features/**`、不含 `scene_composer`。

因此：**全量入口不是全绿**，其中 3 个失败与 2 个未完成都如实记录；只有属于本阶段改动的测试（新增 36 项、
回归 7 套、mutation 12 条、矩阵重算、三 Runner）是有真实 PASS 记录的。
第 70 个文件曾长时间无输出，是因为该套件确实需要 30 分钟量级的真实采集；重启期间进程存活，未做清理。

## 9. 未完成 / 明确没做的事

1. **只做了第一批**（3 Feature / 6 Behavior）。原计划 B2–B6 未做——本阶段按"先小批、验收后再扩张"执行，没有为了数字跳过验收。
2. **48 条 Behavior 仍无证据、50 条无 mutation、59 条无 Holdout**；这些是缺口，不是 PASS。
3. **1.63 矩阵的 Evaluation 归因缺陷未修**（审计 P2）：本阶段用显式 `--eval-dir` 规避，修复留给独立任务。
4. **全量入口不全绿**：133/138 PASS，3 个 `scene_composer` 失败来自 8 个未跟踪、缺 `template.yaml` 的 Feature 脚手架；
   2 个 INCOMPLETE（`test_end_to_end_generation.py` 超时、`test_phase160_e2e.py` 需要 `--evidence-dir` 被当单元测试调用）。
   两者都**未修复**：前者是 30 分钟级真实采集，后者是 1.60 遗留 harness 口径，均超出本阶段授权范围（未要求修它们）。
5. 审批者身份真实性、执行过程真实性仍是 `LOCAL_ISOLATED` 边界，未解决。
6. `Features/i_frames/i_frames.gd` 的 `_on_window_end` 里 `_active = false` 只有 1 个 tab（在 `if` 块外），
   与相邻行的 2 tab 不一致。M11 为了不改语义按原样保留锚点；这是**观察到的可疑缩进**，未修改源码，登记待评审。

## 10. 限制与风险

- **断连影响**：运行期间发生过一次桌面端断连与 Cloud runner 重启；`run_tests.py` 进程跳重启存活并继续跑了约 57 分钟，
  最终输出完整汇总（133/3/2）。重启前后没有丢结论：所有数字都来自可重读的日志与产物文件。
- **评估归因**：矩阵默认扫描 `.ai/tmp/eval` 会串批次（P2）；本阶段所有结论都用 p164 自己的目录重算。
- **bundle 粒度**：同一 Feature 的所有 Behavior 共享一个 evidence bundle 与一份签名，无法单独为某个 Behavior 签名。
- **mutation 与 Behavior 计数**：12 条 mutation / 10 个 Behavior，报告中始终分开表述。

## 11. 下阶段建议

1. 继续 Batch 2（`i_frames` 剩余已覆盖，可转向 `stun/*`、`condition_gate/*`），每批 3–5 条、先证据后 mutation。
2. 修 P2（矩阵评估归因按 run/批次绑定），否则覆盖数字仍会被临时评估污染。
3. 补 `killing_blow_still_dies` 的 mutation（致死豁免类），把它从 PARTIAL 升为 VERIFIED_EXECUTION。
4. 为 `i_frames`/`save_game` 建 Holdout，推进 Fully Covered（当前只有 `openable_door/open`）。
5. 让 `run_tests.py` 的生成链路套件可分段/可超时，避免单个 30 分钟级文件阻塞整个入口。
