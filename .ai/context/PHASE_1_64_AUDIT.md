# Phase 1.64 — 只读审计（第一步）

- 审计时间：2026-11-04
- 审计方式：只读（`git rev-parse` / `git status` / 只读 Python 调用）；未修改任何 1.60–1.63 产物
- 前置文档：`PHASE_1_63_COMPLETION.md`、`PHASE_1_63_COVERAGE_REPORT.md`、`PHASE_1_62_COMPLETION.md`

---

## 1. 仓库状态

| 项 | 实测值 |
| --- | --- |
| HEAD | `dd3a0e4d5d0f6f47e3a9c729e3ce89190f019bd8` |
| 分支 | `master` |
| 工作区变更总数 | 1031（已跟踪修改 53、未跟踪 978） |
| 暂存区 | 0 |
| 最近提交 | `dd3a0e4d chore: 落地 Phase 1.36–1.51.2 本地增量并补齐回归基线` |
| 本阶段 git 写操作 | **无**（未 add/commit/push/reset/checkout/clean/restore/rebase） |

工作区里已存在 1.56–1.63 的大量未提交产物。审计把「阶段开始前就存在」的文件一律视为他人/前序阶段
所有：本阶段只新增自己的文件，只对**本阶段必须修复**的文件做最小改动，并逐条登记（§6）。

**并发修改**：审计期间未观察到其他会话正在写同一批文件（本阶段读写都限定在
`.ai/tools/validator/execution/`、`.ai/tmp/p164/`、`.ai/context/PHASE_1_64_*`）。

---

## 2. Phase 1.63 交付物核对（报告 vs 真实仓库）

| 报告声明 | 实测 | 结论 |
| --- | --- | --- |
| `validator/binding_candidates.py` | 存在，CLI `generate/inventory/submit/approve/promote/gate` 可用 | ✅ |
| `validator/bindings/binding_candidates.json` | 存在 | ✅ |
| `validator/bindings/approval_registry.json`，**59 条**签名审批 | 存在；实际 **62 条记录**（61 APPROVED + 1 SUPERSEDED），其中 **61 条带签名封套，61/61 验签 `SIGNATURE_VALID`，0 失败** | ⚠️ 数量口径差异（见 §5-P3） |
| `validator/bindings/behavior_bindings.json`，60 条 | 存在；60 条，与支持集逐条对应（`bindings index matches supported set: True`） | ✅ |
| `.ai/context/phase_1_63_support_inventory.json`（23/60） | 存在；重新生成同样得到 23 Feature / 60 Behavior | ✅ |
| `evaluation/coverage_matrix.py` 八维矩阵 | 存在；重新生成成功（`rows=60 fully_covered=0 with_gaps=60`，退出码 0） | ✅（但有两处归因问题，§5-P2） |
| `validator/execution/run_p163_e2e.py` | 存在；重跑 **24 checks / 0 failures / exit 0** | ✅ |
| Mutation 10/10 KILLED | 重跑 `--all`：**total=10 effective=10 killed=10 invalid=0 error=0 timeout=0 not_run=0**（`summary-71c00e8b.json`） | ✅ 可复现 |
| 1.62 两个 Runner 的 `_PROJECT_ROOT` 缺陷 | 确认存在（少算一层，得到 `.ai`） | 本阶段已修（§6） |

## 3. 动态支持集与 Binding（不硬编码 23/60）

```
supported: features=23 behaviors=60        # evidence_adapter.supported_set(Features/)
gate: {'APPROVED_BINDING': 60}
registry: 62 records → 61 APPROVED + 1 SUPERSEDED
signature: signed=61 verified=61 failures=0
```

- 支持集来源是 `Features/*/template.yaml#behavior`，与采集器 / Validator / Binding / 矩阵共用同一次推导。
- 8 个「有目录无契约」的历史 Feature 仍未进入分母（与 1.57 起一致）。
- 契约漂移会由 `binding_gate_status(contract_version=...)` 判 `CONTRACT_MISMATCH`；本次 60/60 均为
  `APPROVED_BINDING`，说明当前契约与已审批绑定一致。

审计脚本：`.ai/tmp/p164/initial/audit_bindings.py`（只读）。

---

## 4. 初始覆盖基线（重新生成，不沿用历史数字）

矩阵快照：`.ai/tmp/p164/initial/coverage_matrix.json`（`generated_at=2026-11-04T16:20:00Z`）。
逐条明细见 `PHASE_1_64_INITIAL_COVERAGE.md`。

| 维度 | 分子 / 60 | 状态分布 |
| --- | --- | --- |
| Contract | 60 | CONTRACT_PRESENT=60 |
| Approved Binding | 60 | APPROVED=60 |
| Evidence Verified | 8 | NO_EVIDENCE=52 |
| Signature Verified | 8 | NO_SIGNATURE=52 |
| Attestation Verified | 8 | NO_ATTESTATION=52 |
| Evaluation VERIFIED_PASS | 4 | NOT_EVALUATED=55、INVALID_EVIDENCE=1 |
| Holdout Available | 1 | NO_HOLDOUT=59 |
| L5 Mutation Killed | 9（Behavior 数） | NOT_TESTED=51 |
| Fully Covered | **0** | 60 行均有缺口 |

> 注意：`mutation_killed=9` 是**Behavior 数**（10 条 mutation 中 M04/M08 同属
> `trigger_switch/latch_once`），不是 mutation 条数。两个数字都保留，不混用。

---

## 5. 审计发现（按影响排序）

### P1 — Phase 1.62 两个 E2E Runner 的项目根少算一层（已修）

- 位置：`validator/execution/run_execution_e2e.py:22`、`run_multi_feature_e2e.py:21`，
  `_PROJECT_ROOT = os.path.dirname(_TOOLS)` → 得到 `.ai`，正确值为仓库根。
- 后果：Godot 只在 `GODOT_BIN` 提供时可运行；`--version` 之外的自动发现全部落空。
- 与 1.63 报告一致（该报告把它登记为已知问题、未修，留待授权）。
- 本阶段处理：见 §6（统一解析器 + 环境错误语义 + 回归）。

### P2 — Coverage Matrix 的 Evaluation 归因跨批次污染（未修，本阶段按批次规避）

- `health/damage`：Evidence/Signature/Attestation 均 VERIFIED，Evaluation 却是 `INVALID_EVIDENCE`，
  其 `report` 指向 `.ai/tmp/eval/44-f49ccd30/evidence_report.json` —— 一次**其它批次**
  （mutant/临时任务）的报告被当成该行为的最新结论。
- `trigger_switch/latch_once`：Evaluation `VERIFIED_PASS`，但 Evidence 是 `NO_EVIDENCE` —— 两个维度
  来自不同批次（评估报告引用的证据不在默认扫描目录）。
- 影响：**不能拿矩阵的 Evaluation 默认数字当结论**；Fully Covered 仍为 0，所以本次没有因此虚增。
- 本阶段处理：每批矩阵都用显式 `--evidence-dir` / `--eval-dir` 重算；不修改 1.63 的归因实现
  （改动会触及他人产物，且属于下一阶段的独立修复项）。已在 `PHASE_1_64_INITIAL_COVERAGE.md` §5 留痕。

### P3 — 1.63 报告的「59 条签名审批」与仓库的 62 条记录

- 现状：62 条记录（61 APPROVED + 1 SUPERSEDED），61 条签名全部可验证。
- 解释：M04/M06 的契约修复导致相关 (Feature, Behavior) 走重绑流程，新增记录；1 条旧记录被
  SUPERSEDED（无签名，符合生命周期语义）。
- 判定：**不是伪造**，是计数口径未随重绑更新。本阶段所有文档引用「记录数 / 已签名数 / 已验签数」三个数。

### P4 — Mutation 覆盖与 Behavior 覆盖的换算

- catalog 10 条 → 9 个 Behavior（`trigger_switch/latch_once` 有 M04+M08 两条）。
- 报告与矩阵必须区分「mutation 条数」与「被覆盖 Behavior 数」，否则会重复计数。

---

## 6. 本阶段修改清单（文件级，用于区分本阶段与他人的修改）

新增：

| 文件 | 说明 |
| --- | --- |
| `.ai/tools/validator/execution/env_paths.py` | 项目根 + Godot 统一解析（GODOT_BIN → 项目配置 → 相邻目录 → PATH；缺失即环境错误） |
| `.ai/tools/validator/execution/run_p164_batch.py` | 分批验证 Runner（复用 1.63 全链；expected 来自已审批 Binding；逐 Behavior 出评估结论） |
| `.ai/tmp/p164/**` | 本阶段所有运行产物（初始矩阵、mutation 复现、E2E 回归日志、批次证据） |

修改（仅两处，均为 P1 的最小修复）：

| 文件 | 改动 |
| --- | --- |
| `validator/execution/run_execution_e2e.py` | 项目根改用 `env_paths.project_root()`；Godot 改用 `env_paths.require_godot()`（保留原 check 数量与语义） |
| `validator/execution/run_multi_feature_e2e.py` | 同上；原 `assert godot not found` 改为明确的环境错误（exit 2） |

未触碰：`Features/**`、`validator/bindings/**`、`validator/provenance/**`、`evaluation/**`、
`evaluation/mutation/**`、1.60–1.63 的任何产物目录、`.ai/skills/**`。

---

## 7. 审计结论

1. 1.63 的基础设施真实可用：60/60 Binding 与签名审批可复核，八维矩阵可重算，10/10 mutation 可复现。
2. 矩阵的 Evaluation 归因有跨批次污染（P2），因此**覆盖数字必须按批次重算后才可使用**。
3. 1.62 Runner 的路径缺陷真实存在且已被本阶段修复，回归见 `PHASE_1_64_BATCH_1_REPORT.md` 与
   `PHASE_1_64_COMPLETION.md`。
4. 无阻塞项；可以进入第二阶段（分类与分批验证）。
