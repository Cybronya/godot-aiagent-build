# Phase 1.59 — L5 Behavioral Verification Expansion（完成报告）

- 执行日期：2026-11-03
- 基线：HEAD `dd3a0e4d5d0f6f47e3a9c729e3ce89190f019bd8`（`master`，**未提交任何内容**）
- 运行环境：Windows / Python 3.12 / Godot `F:\Godot_v4.7-stable\Godot_v4.7-stable_win64_console.exe`
- 审计文档：[PHASE_1_59_AUDIT.md](PHASE_1_59_AUDIT.md)

---

## 1. 结论摘要（先给结论，再给证据）

| 项 | 结果 |
| --- | --- |
| L5 机制 | 新建 `.ai/tools/evaluation/mutation/`：在 `Features/` 的**隔离副本**里注入一处真实缺陷 → 真实采集 → **既有** Validator + Evaluation 判定 → 逐字节恢复 → 再跑一次 |
| 执行范围 | 8 条 catalog mutation，覆盖 **5 个 Feature / 7 个 Behavior**（其中 `trigger_switch/latch_once` 有两条注入） |
| 真实结果（`--all`，session `summary-69ccc04c`） | `MUTANT_KILLED=6`、`INVALID_MUTANT=2`、`SURVIVED=0`、`HARNESS_ERROR=0`、`TIMEOUT=0`、`NOT_RUN=0` |
| 可信 L5 覆盖（本轮新增） | **5 Feature / 6 Behavior**（见 §11） |
| 控制组 | 8/8 control `VERIFIED_PASS`（副本未改，同一 tasks 文件与探针参数） |
| 恢复 | 8/8 `restored_byte_for_byte=true` 且 recovery `VERIFIED_PASS` |
| 仓库完整性 | 8/8 `repo_guard.changed=false`；`Features/**` 前后哈希快照完全一致 |
| 测试 | 新增 66 项（51 单元/安全 + 15 真实端到端）**全过**；既有 evaluation 四套回归 **124 项全过** |
| 未做 | 未扩到全部 23 Feature / 60 Behavior；未重写 Validator/Runner/Collector/Registry/Baseline 审批；未改 `evidence_tasks.yaml`；未动 `.ai/skills/**` 与 8 个未纳入支持集的 Feature |

一句话：**「真实实现缺陷 → 真实执行 → 现有 Evidence/Validator/Evaluation 链路识别」这条链在 5 个 Feature / 6 条 Behavior 上被真实证明可用**；另有 2 条注入被证明**不会**造成可观测行为差异，如实记为 `INVALID_MUTANT` 并暴露了探针的分辨力缺口。

---

## 2. 审计基线与前置条件（§2 要求的「先审计」）

审计（`PHASE_1_59_AUDIT.md`）在执行前完成并落盘，其中记录：支持集 = 23 Feature / 60 Behavior（协议 v2，动态读取）、Godot 路径、单次 `--feature` 采集实测 11.98s、Phase 1.56–1.58 的可用接口与缺口、不可触碰清单。审计后**未发现新的冲突**，故未暂停。

复用而**未重写**的既有能力：

| 能力 | 复用方式 |
| --- | --- |
| 证据采集 | `scene_composer/feature_behavior_evidence.py --features-dir <副本>`（本阶段唯一的「新用法」是把 `--features-dir` 指向自己复制的 `Features/` 副本；仓库 `Features/**` 全程只读） |
| 证据验证 | `validator/check_behavior_evidence.py`（经 `evidence_eval.py` 间接调用，未改一行） |
| 行为评估 | `evaluation/evidence_eval.py --tasks-file <临时文件> --evidence-dir … --no-collect --runs-dir … --json` |
| 谓词语义 | `check_behavior_evidence.expected_holds()`（effectiveness 的观测比较复用同一实现，注入 `check` 字段） |
| 任务定义 | 每条 mutation 生成**独立临时** `tasks.yaml`；仓库 `evaluation/evidence_tasks.yaml` 未改 |

---

## 3. 新增 / 修改文件

新增（`2072` 行）：

| 文件 | 行 | 作用 |
| --- | --- | --- |
| `.ai/tools/evaluation/mutation/catalog.py` | 167 | 读 catalog、结构校验、从 `template.yaml#behavior` 动态取支持集、前置检查、谓词比较 |
| `.ai/tools/evaluation/mutation/operators.py` | 105 | `replace_exact` / `delete_statement` + 锚点唯一性 / 空 diff / 括号平衡 / 语句边界校验 |
| `.ai/tools/evaluation/mutation/workspace.py` | 170 | 隔离副本 + ownership 标记 + 受限清理 + 快照差异 + 路径逃逸 / 符号链接守卫 |
| `.ai/tools/evaluation/mutation/harness.py` | 545 | control → mutant → recovery 三次真实执行、effectiveness、verdict、repo guard |
| `.ai/tools/evaluation/mutation/mutation_eval.py` | 176 | CLI（`--list` / `--mutation` / `--all`）、批次汇总、退出码 |
| `.ai/tools/evaluation/mutation/mutation_catalog.yaml` | 257 | 8 条 mutation（含 `source_sha256` 锚点哈希与 effectiveness 谓词） |
| `.ai/tools/evaluation/mutation/tests/test_mutation_harness.py` | 488 | 51 项：算子 / 副本 / 目录 / verdict / 清理 / 真实子进程分支 |
| `.ai/tools/evaluation/mutation/tests/test_mutation_integration.py` | 164 | 15 项：真实 Godot，2 个 Feature 端到端 |
| `.ai/context/PHASE_1_59_AUDIT.md` | — | 审计（执行前） |
| `.ai/context/PHASE_1_59_COMPLETION_REPORT.md` | — | 本报告 |

修改（仅文档，未改任何实现或测试断言）：

- `.ai/context/FEATURE_BEHAVIOR_COVERAGE.md`：新增「Phase 1.59：L5 缺陷注入扩展」一节（8 条注入逐条判定 + 覆盖口径）。
- `.ai/context/WORK_STATE.md`、`.ai/context/CURRENT_TASK.md`：新增 Phase 1.59 段。
- `.ai/tools/evaluation/README.md`：新增「Phase 1.59：L5 Mutation Harness」用法/口径/安全边界/测试。

**未改**：`Features/**`、`evaluation/evidence_tasks.yaml`、`evaluation/baselines/**`、`validator/**`、`scene_composer/**`、`.ai/skills/**`、`.ai/tools/evaluation/{runner,evidence_eval,evidence_adapter}.py`。

---

## 4. 架构与数据流（三条真实执行，一条判定链）

```
catalog (yaml)  ──►  preconditions ──失败──► NOT_RUN（不创建 run 目录）
                        │
                   create_run_dir(run) + copy_features(Features→run/Features) + owner 标记
                        │
   ┌────────────────────┴─────────────────────────────────────────────┐
   │ control：副本原样  → collector --features-dir 副本 → evidence/control │
   │                    → evidence_eval --tasks-file run/tasks.yaml       │
   │ mutant ：副本改目标文件（operator）→ 同上 → evidence/mutant            │
   │ recovery：写回原字节 → 同上 → evidence/recovery                        │
   └────────────────────┬─────────────────────────────────────────────┘
                        ▼
   effectiveness（同一 (check,target,entry) 的 control/mutant 运行时观测必须不同，
                  且 mutant 满足 catalog 谓词）→ repo_guard（Features/** 快照对比）→ verdict
```

`--replay 2` 与仓库固定任务一致（Validator 要求 `replay_count>=2`，否则 `INCOMPLETE` —— 实测见 §10 的 `test_mutation_harness.py` D12b 项）。

---

## 5. Operator 列表与拒绝规则

| operator | 语义 | 拒绝条件（拒绝即 `INVALID_MUTANT`，不是「检出」） |
| --- | --- | --- |
| `replace_exact` | 把唯一锚点替换为给定文本 | `anchor_not_unique`（0 或 >1 次）、`empty_diff`（替换文本与锚点相同）、`structure_changed`（括号平衡变化） |
| `delete_statement` | 删除唯一整行语句 | 上述三条 + `anchor_not_a_single_line`、`anchor_not_line_aligned`（锚点必须独占整行，避免删掉半条表达式） |

另有两道与 operator 无关的硬闸：

1. **只允许改目标文件**：副本快照差异必须恰好是 `target_file`（`unexpected_changes()` 检查；实测 `test_..._harness.py` D9）。
2. **源哈希必须匹配 catalog**：`source_sha256` 不符 → `NOT_RUN(source_hash_mismatch)`，避免在「已经不是当初那版实现」的代码上宣称结论。

---

## 6. Catalog（8 条，`mutation_catalog.yaml`）

| # | Feature / Behavior | 类型 | 目标函数 | operator | 源文件 sha256（前 12） |
| --- | --- | --- | --- | --- | --- |
| M01 | `health` / `damage` | `state_update_omitted` | `take_damage` | replace_exact | `a436c28bbea1` |
| M02 | `health` / `post_death_guard` | `lifecycle_guard_missing` | `take_damage` | replace_exact | `a436c28bbea1` |
| M03 | `collect_pickup` / `collect_on_contact` | `resource_release_omitted` | `_collect` | delete_statement | `3c16f890deee` |
| M04 | `trigger_switch` / `latch_once` | `state_latch_broken` | `_on_body_entered` | replace_exact | `6efb06505437` |
| M05 | `openable_door` / `open` | `event_emit_omitted` | `open` | delete_statement | `8df8e057…` |
| M06 | `save_game` / `save_slot_persists_world_state` | `persistence_record_omitted` | `save_to_slot` | delete_statement | `9aaa19de77b5` |
| M07 | `save_game` / `load_slot_restores_world_state` | `persistence_read_omitted` | `load_from_slot` | replace_exact | `9aaa19de77b5` |
| M08 | `trigger_switch` / `latch_once` | `state_transition_wrong_value` | `_on_body_entered` | replace_exact | `6efb06505437` |

每条都声明 `precondition`（只改这一处、其余分支/广播不动）、`expected_behavior_change`、`effectiveness`（`check` / `target` / `entry` / `baseline` 谓词 / `mutant` 谓词）、`evaluation.expect`（与临时 tasks 文件同源）、`risk_level`。

**过程中修正的两个 catalog 级错误（如实记录）**：

- M07 原本用 `delete_statement` 删除 `load_from_slot()` 里 `if` 块的**唯一**语句 → 空块 → 脚本解析失败，采集侧报 `action_unavailable`（`INSUFFICIENT`）。虽然被判 `INVALID_MUTANT`，但根因是「跑不起来」而不是行为差异，故改为 `replace_exact` → `pass`（保留块结构，真正跳过回填）。
- M08 的 `_triggered = true` 在 Repeat 分支也出现（同缩进），单行锚点不唯一（实测 `found 0 occurrence(s)`）；锚点改为带 Latching 独有 `return` 的两行 → 唯一。

---

## 7. Verdict 模型（与 Evaluation 状态分离，两者都保留）

| Verdict | 含义 | 判定位置 |
| --- | --- | --- |
| `MUTANT_KILLED` | 缺陷注入生效（effectiveness 成立）且 Evaluation 判 `VERIFIED_FAIL` / `INVALID_EVIDENCE` 等非 PASS | `_verdict()` |
| `MUTANT_SURVIVED` | effectiveness 成立但 Evaluation 仍 `VERIFIED_PASS`（链路没拒绝） | `_verdict()` |
| `INVALID_MUTANT` | 注入未造成预期行为变化 / operator 拒绝 / 改动了非目标文件 | `_execute()`、`_verdict()` |
| `HARNESS_ERROR` | 子进程启动失败、控制组不成立（非 PASS）、恢复未通过、仓库哈希变化、状态不可判 | `_execute()`、`_verdict()` |
| `TIMEOUT` | 采集/评估子进程超时 | `_execute()`、`_verdict()` |
| `NOT_RUN` | 前置条件不成立（哈希过期 / 未声明 Feature·Behavior / 结构问题） | `_execute()` |

判定顺序（`_verdict()`）：TIMEOUT → HARNESS_ERROR(启动失败) → 仓库变化 → control 未 PASS → effectiveness 未成立 → recovery 未通过 → mutant 状态。**「先证控制组成立，再谈检出」**：控制组只要不是 `VERIFIED_PASS` 就一律 `HARNESS_ERROR`（实测 D12b：`--replay 1` 让 Validator 报 `INCOMPLETE`，该情形**不会**被误记成 `INVALID_MUTANT` 或检出）。

报告里 Verdict 与 `controls.mutant.evaluation.{evaluation_status,validator_status}` 是**两个独立字段**，killed 只是 verdict，Evaluation/Validator 的原始结论原样保留（例如 §10 中 6 条 KILLED 的 mutant 都是 `INVALID_EVIDENCE` + Validator `FAIL`）。

---

## 8. Effectiveness：由运行时观测判定，不采信配置

`_effectiveness()` 从两次真实证据包里取出**同一个** `(check, target, entry)` 观测：

- control 观测必须满足 `baseline` 谓词；
- mutant 观测必须**与 control 不同**且满足 `mutant` 谓词；
- 任一观测缺失 → 记录失败原因并附采集侧 `status/reason`（例如 M07 早期版本的 `control=PASS/ok, mutant=INSUFFICIENT/action_unavailable`），判 `INVALID_MUTANT`。

谓词比较复用 `check_behavior_evidence.expected_holds()`，不另写一套「看起来相等」的判断。

---

## 9. Pos/Neg Control（同场景、同探针、同 tasks 文件）

- **Negative Control**：隔离副本**未改**，与 mutant 使用同一 `--feature`、同一 `tasks.yaml`、同一 `--replay 2`。8/8 `VERIFIED_PASS`。
- **Positive Control**：同一副本注入缺陷后再执行。6/8 被拒绝（killed）。
- 两者**共用**同一探针场景与同一份期望（不存在「控制组换一套更松的期望」）。
- 对照组的差异只允许来自目标文件的一处改动（快照差异硬校验）。

---

## 10. 真实 Godot 端到端结果（`--all`，`summary-69ccc04c`）

| # | Verdict | control | mutant（Evaluation / Validator） | recovery | 恢复逐字节 | 时长 | repo 变化 |
| --- | --- | --- | --- | --- | --- | --- | --- |
| M01 `health/damage` | `MUTANT_KILLED` | `VERIFIED_PASS` | `INVALID_EVIDENCE` / `FAIL` | `VERIFIED_PASS` | ✅ | 58.1s | ❌ |
| M02 `health/post_death_guard` | `MUTANT_KILLED` | `VERIFIED_PASS` | `INVALID_EVIDENCE` / `FAIL` | `VERIFIED_PASS` | ✅ | 58.2s | ❌ |
| M03 `collect_pickup/collect_on_contact` | `MUTANT_KILLED` | `VERIFIED_PASS` | `INVALID_EVIDENCE` / `FAIL` | `VERIFIED_PASS` | ✅ | 47.8s | ❌ |
| M04 `trigger_switch/latch_once` | `INVALID_MUTANT` | `VERIFIED_PASS` | `VERIFIED_PASS` / `PASS` | `VERIFIED_PASS` | ✅ | 50.6s | ❌ |
| M05 `openable_door/open` | `MUTANT_KILLED` | `VERIFIED_PASS` | `INVALID_EVIDENCE` / `FAIL` | `VERIFIED_PASS` | ✅ | 46.0s | ❌ |
| M06 `save_game/save_slot_persists_world_state` | `INVALID_MUTANT` | `VERIFIED_PASS` | `VERIFIED_PASS` / `PASS` | `VERIFIED_PASS` | ✅ | 52.1s | ❌ |
| M07 `save_game/load_slot_restores_world_state` | `MUTANT_KILLED` | `VERIFIED_PASS` | `INVALID_EVIDENCE` / `FAIL` | `VERIFIED_PASS` | ✅ | 51.9s | ❌ |
| M08 `trigger_switch/latch_once` | `MUTANT_KILLED` | `VERIFIED_PASS` | `INVALID_EVIDENCE` / `FAIL` | `VERIFIED_PASS` | ✅ | 53.7s | ❌ |

批次：`total=8 effective=6 killed=6 survived=0 invalid=2 error=0 timeout=0 not_run=0`，8 条合计 418.3s（每条约 46–58s = 3 次真实采集 + 3 次评估）。退出码：有 `INVALID_MUTANT` → **1**（按设计，`INVALID_MUTANT` 不是成功）。

关键观测（control → mutant，均为真实运行时读数）：

| # | check / target | control | mutant |
| --- | --- | --- | --- |
| M01 | `health.current` / `.` | `1`（PASS） | `5`（`STATE_MISMATCH`） |
| M02 | `signal health.health_changed` / `.` | `count=1`，`[0,5]` | `count=2`，`[0,2]`（`SIGNAL_MISMATCH`） |
| M03 | `node.freed` / `.` | `true` | `false`（`STATE_MISMATCH`） |
| M04 | `signal trigger.activated` / `.` | `count=1`，`[true]` | `count=1`，`[true]`（**无差异**） |
| M05 | `signal door.state_changed` / `.` | `count=1`，`[true]` | `count=0`（`SIGNAL_MISMATCH`） |
| M06 | `savegame.last_slot` / `Saver` | `behavior_save` | `behavior_save`（**无差异**） |
| M07 | `health.current` / `World/Player/Health` | `3` | `1`（`STATE_MISMATCH`） |
| M08 | `trigger.is_triggered` / `.` | `true` | `false`（`STATE_MISMATCH`） |

---

## 11. L5 覆盖矩阵（本阶段实际证明的范围）

| Feature | Behavior | L5（本轮） | mutation | 说明 |
| --- | --- | --- | --- | --- |
| `health` | `damage` | ✅ KILLED | M01 | 不扣血只发信号 → 被 `STATE_MISMATCH` 拒绝 |
| `health` | `post_death_guard` | ✅ KILLED | M02 | 死后重复扣血 → 信号计数 2 |
| `collect_pickup` | `collect_on_contact` | ✅ KILLED | M03 | 拾取物不释放 → `node.freed=false` |
| `openable_door` | `open` | ✅ KILLED | M05 | 状态变了但信号被吞 → `count=0` |
| `save_game` | `save_slot_persists_world_state` | ⚠️ 无有效注入 | M06 | `INVALID_MUTANT`（`user://` 残留），**不计 L5** |
| `save_game` | `load_slot_restores_world_state` | ✅ KILLED | M07 | 读档不回填 → `health.current=1` |
| `trigger_switch` | `latch_once` | ✅ KILLED | M08（M04 无效） | 状态写错值被拒；M04 守卫走不到 |
| 其余 18 Feature / 53 Behavior | — | `NOT_EVALUATED` | — | 本阶段未做，**不是 PASS** |

统计口径（与任务书 §7 一致）：未测试 53 / 已测且有有效注入 6（6 KILLED、0 SURVIVED）/ 已测但无有效注入 2（INVALID_MUTANT，不计分母）/ Harness Error 0 / 不适用 0。

---

## 12. 恢复与「仓库未变」证明

三层证据：

1. **逐字节恢复**：`recovery.restored_byte_for_byte=true` 且副本快照与注入前快照相等（8/8）。
2. **恢复后重新通过**：recovery 那次采集+评估 `VERIFIED_PASS`（8/8），证明「恢复」不是只把文件写回去，而是恢复后的实现重新满足契约。
3. **仓库看守**：每次 run 前后对 `Features/**` 做 sha256 快照并比较（含增删改），`repo_guard.changed=false`（8/8）；批次结束时 `workspace.diff_snapshots()` 为空（测试 `Z1`/`I3` 独立复核）。仓库 `Features/**` 全程**只读**：所有注入都发生在 `.ai/tmp/p159/runs/<mutation>-<runid>/Features/` 里。

git 侧：HEAD 仍 `dd3a0e4d…`，未执行任何 `git add/commit/push/reset/checkout/clean/restore/rebase`；`git status --short` 从 993 行变为 995 行（本报告写入前），新增的两条未跟踪条目都来自本阶段（`.ai/context/PHASE_1_59_AUDIT.md`、`.ai/tools/evaluation/mutation/`），未触碰他人未提交的修改。

---

## 13. 安全边界测试（要求 ≥16 项，实际 51 项）

`test_mutation_harness.py` 覆盖（真实文件系统，不用 mock 冒充安全边界）：

| 要求项 | 覆盖 |
| --- | --- |
| 锚点缺失 / 重复 | A3 / A4（`anchor_not_unique`，含 count 明细） |
| 源哈希不符 | C8（`NOT_RUN(source_hash_mismatch)`，真实 catalog 条目 + 篡改哈希） |
| 非目标文件被改 | D9（`unexpected_changes()`）、`_execute()` 硬闸 |
| 空 diff | A5（`empty_diff`） |
| 无行为差异 | D12/M04/M06（`INVALID_MUTANT`，不当作检出） |
| 超时 | D11（真实子进程 `--timeout 1` → `TIMEOUT`） |
| 子进程启动失败 | D4/D7 的判定路径 + `HARNESS_ERROR` 分支 |
| Evidence 失败 | D11/D12b（控制组未 PASS → `HARNESS_ERROR`） |
| Validator 非 PASS | D12b（`INCOMPLETE` 控制组不得进入判定） |
| Evaluation 非预期 | D1–D8（KILLED/SURVIVED/不可判的分派） |
| 仓库哈希不变 | Z1（`Features/**` 前后快照相同） |
| 路径逃逸 | B4 / B5（兄弟前缀、`..` 逃逸均被拒） |
| 符号链接 | B6 / B7（符号链接源 / 目标文件一律拒绝）——**此项发现并修掉一个真实缺陷**：`copy_features()` 原先在 `realpath` 之后判断 `islink`，符号链接被解析掉后检查永远为真，实测「符号链接源被接受」；改为 realpath 之前判断 |
| 不清理他人文件 | B8 / B9 / B10 / D15（无 owner 标记、runs root 之外、他人 run_id、外来目录都不删） |
| 逐字节恢复 | §12（`restored_byte_for_byte`） |
| 其它 | A1/A2/A6–A10（算子正确性与 diff）、B1–B3/B11–B13（副本、ownership、清理、快照差异）、C1–C11（catalog 结构/支持集/前置）、D12b（控制组 INCOMPLETE） |

---

## 14. 测试清单与真实结果

| 套件 | 项数 | 结果 | 说明 |
| --- | --- | --- | --- |
| `mutation/tests/test_mutation_harness.py` | 51 | **ALL PASS**（exit 0） | 含 3 次真实子进程（NOT_RUN / TIMEOUT / INVALID_MUTANT / 控制组 INCOMPLETE） |
| `mutation/tests/test_mutation_integration.py` | 15 | **ALL PASS**（exit 0） | 真实 Godot：`collect_pickup` + `openable_door`，KILLED + control/recovery PASS + 仓库未变 |
| `evaluation/tests/test_evidence_eval.py` | 20 | ALL PASS | 既有回归（Phase 1.58） |
| `evaluation/tests/test_evidence_adapter.py` | 52 | ALL PASS | 既有回归 |
| `evaluation/tests/test_evaluation_runner.py` | 24 | ALL PASS | 既有回归 |
| `evaluation/tests/test_evaluation_scoring.py` | 28 | ALL PASS | 既有回归 |

合计：新增 66 项 + 既有回归 124 项 = **190 项，0 失败**。

未执行 / 未计入：`test_behavior_evidence_stage.py` 与 Godot 侧 `Tests/**` 全量批次本阶段**未运行**（本阶段未改采集器/Validator/Godot 脚本，故未扩大范围）；本报告**不**声称这些套件通过。

---

## 15. 两条 `INVALID_MUTANT` 的根因（如实登记，不修饰）

**M04 — `trigger_switch/latch_once`，删 Latching 分支的 `if _triggered: return`**

- 现象：control 与 mutant 的 `trigger.activated` 观测完全相同（`count=1, [true]`）。
- 根因：契约用两次 `physics.overlap` 触发，但第二次调用**不会**产生第二次 `body_entered`，因此那行守卫在真实执行里根本走不到。
- 结论：这是**探针/契约的分辨力缺口**，不是「契约检出了缺陷」，也不是「实现无缺陷」。记 `INVALID_MUTANT`，保留在 catalog。
- 已用 M08（状态写错值）在同一 Behavior 上取得有效 KILLED，但**不因此**声称 M04 被检出。

**M06 — `save_game/save_slot_persists_world_state`，删 `_record_last_slot(slot_path)`**

- 现象：mutant 的 `savegame.last_slot` 仍为 `behavior_save`。
- 根因：`user://saved_games/_last.txt` 在 control 那次运行里已经被写下，跨 run 残留；mutant「忘记记录」时回读到的仍是上次的值。
- 结论：该契约对「忘记记录」没有分辨力（存在顺序依赖）。记 `INVALID_MUTANT`，保留在 catalog。
- 未采取的「捷径」：没有清空 `user://` 后再跑、没有改期望、没有改 Evidence —— 那样会把「环境残留」伪装成检出。

---

## 16. 明确未做（与本阶段边界一致）

- 未扩到全部 23 Feature / 60 Behavior 的 L5；未扩正式支持集；未动 8 个未纳入支持集的 Feature 目录。
- 未重写 Runner / Validator / Evidence Collector / Feature Registry / Baseline 审批；未改 `evidence_tasks.yaml`、`validator/baselines/**`。
- 未做 Holdout 新系统、签名/可信执行（Phase 1.57 已把「来源真实性」列为未解决，本阶段同样未解决）。
- 未治理历史临时目录（`%TEMP%` 下 2 个 `trace_baseline_*` 沙箱、仓库内 `Scenes/E2e*.tscn` 等 E2E 孤儿）——只登记，不删除。
- 未自动修改 Feature 实现或探针；M04/M06 的探针缺口只作为建议记录（§17）。
- 未提交任何内容（无 `git add/commit/push`）。

---

## 17. 已知缺口与风险

1. **探针分辨力**：M04、M06 证明「契约没覆盖到的实现细节」存在。这类缺口不会表现为 SURVIVED，而表现为 INVALID_MUTANT —— 本阶段的选择是**如实记无效**，而不是把它算成通过。
2. **`user://` 顺序依赖**：`save_game` 的 last_slot 档在 run 之间残留，会影响「忘记记录」类注入；当前结论已显式标注受此影响。
3. **catalog 漂移**：`source_sha256` 与锚点绑定了实现文本；任何人改了 `Features/**` 都会让相关 mutation 变成 `NOT_RUN`（这是**设计**：宁可 NOT_RUN，也不要对着旧结论宣称覆盖）。
4. **执行成本**：每条 mutation 3 次真实采集（≈50s），全 60 Behavior 全量 L5 约需数小时；本阶段刻意只做 8 条。
5. **单机可信边界**：注入、采集、评估在同一权限下完成，仍无法证明证据未被同步改写（与 Phase 1.57 相同的信任边界限制）。
6. **`--clean` 默认关闭**：run 目录保留以便审计，`.ai/tmp/p159` 会持续增长。

---

## 18. 下阶段建议（按性价比排序）

1. **补 `save_game` 探针的隔离**：每个行为 run 前清空自己的 `user://` 局部目录（或在独立 `--user-dir` 下跑），使 M06 变成可判定；顺带给 M04 增加「第二次真实接触」的驱动方式（重新进入 area / 移动后再进入），让 Latching 守卫可被走到。
2. **按 Feature 批量扩 L5**：优先 `stun`、`i_frames`、`cooldown`、`state_machine`、`projectile`（都有清晰的状态/信号观测），把 catalog 从 8 扩到 ~20。
3. **把 L5 结论接进 `FEATURE_BEHAVIOR_COVERAGE.md` 的 VERIFIED 口径**：当前 VERIFIED 要求「至少一条 L5」，但矩阵尚未逐 Feature 绑定 mutation_id；建议让 harness 输出 `feature→mutation_id→verdict` 的机器可读索引，由文档生成。
4. **CI 化**：把 8 条 mutation 固定成一条 `--all` 的快速回归（约 7 分钟），只在 `Features/**` 或契约变更时触发；哈希漂移自动转 `NOT_RUN` 并提示重签。

---

## 19. 复现命令（全部真实退出码）

```bash
export PYTHONIOENCODING=utf-8 PYTHONUTF8=1

# 1) 列出 catalog
python .ai/tools/evaluation/mutation/mutation_eval.py --list

# 2) 全量 L5（8 条 × 3 次真实采集，约 7 分钟；有 INVALID_MUTANT → 退出码 1）
python .ai/tools/evaluation/mutation/mutation_eval.py --all

# 3) 单条
python .ai/tools/evaluation/mutation/mutation_eval.py \
  --mutation M05-openable-door-state-signal-dropped

# 4) 测试
python .ai/tools/evaluation/mutation/tests/test_mutation_harness.py       # 51 项
python .ai/tools/evaluation/mutation/tests/test_mutation_integration.py   # 15 项（真实 Godot）
```

产物：`.ai/tmp/p159/reports/<mutation>.json`、`summary-<id>.json`（本报告引用 `summary-69ccc04c.json`）、`.ai/tmp/p159/runs/<mutation>-<runid>/`。

---

## 20. 任务书 §17 的 11 项汇报

| # | 问题 | 回答 |
| --- | --- | --- |
| 1 | 是否先审计后动手？ | 是。`PHASE_1_59_AUDIT.md` 在执行前完成，审计后未发现需暂停的冲突。 |
| 2 | 是否重写了既有链路？ | 否。Runner / Validator / Collector / Registry / Baseline 审批全部未改；只新增 `evaluation/mutation/` 上层工具，复用 `--features-dir` 与 `evidence_eval.py`。 |
| 3 | 是否只改隔离副本？ | 是。8/8 `repo_guard.changed=false`，`Features/**` 快照前后一致；注入都在 `.ai/tmp/p159/runs/*/Features/`。 |
| 4 | 缺陷是否真实生效？ | 6 条由**运行时观测差异**证明（§10 表）；2 条（M04/M06）证明**未**生效 → `INVALID_MUTANT`。 |
| 5 | 是否真实执行（非 mock/stub）？ | 是。每条 mutation 3 次真实 Godot 采集 + 3 次真实 `evidence_eval`；测试里也用真实子进程（含真实超时）。 |
| 6 | 链路是否识别缺陷？ | 6/6 有效注入均被拒绝：Evaluation `INVALID_EVIDENCE` + Validator `FAIL`；control 与 recovery 均 `VERIFIED_PASS`。 |
| 7 | Verdict 与 Evaluation 是否分开？ | 是。报告同时保留 verdict 与 `evaluation_status` / `validator_status`（§7、§10）。 |
| 8 | 无效注入是否计入分母？ | 不计。`effective=6`、`invalid=2`，`INVALID_MUTANT` 既不进 killed 也不进 survived。 |
| 9 | 是否有 Pos/Neg Control？ | 有，同场景同探针同 tasks 文件（§9）。 |
| 10 | 是否覆盖多类型 / 多 Feature？ | 5 个 Feature、8 个 Behavior、7 类缺陷；两个不同类型 Feature（`collect_pickup`、`openable_door`）由真实端到端测试独立复核。 |
| 11 | 是否有未验证却声称通过的内容？ | 无。未测试的 18 Feature / 53 Behavior 明确标 `NOT_EVALUATED`；未运行的测试套件在 §14 明确列出「未运行」。 |
