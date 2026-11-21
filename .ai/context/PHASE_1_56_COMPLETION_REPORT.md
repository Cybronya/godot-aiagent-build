# Phase 1.56 — Evidence Integration 完成报告

> 口径：本报告只写**实测到的东西**。每条结论标注 `FACT`（有命令输出 / 代码 / 文件为证）、
> `INFERENCE`（由现有实现推断）、`UNKNOWN`（当前无法确认）。不接受「有文件即已实现」。
>
> 执行日期：2026-11-01（本地时间）。所有命令均在 `F:\Godot_v4.7-stable\game` 下执行。

---

## 1. 审计基准 HEAD 与工作区状态

| 项 | 值 | 证据 |
| --- | --- | --- |
| HEAD | `dd3a0e4d5d0f6f47e3a9c729e3ce89190f019bd8` | `git rev-parse HEAD`（FACT） |
| 分支 | `master` | `git branch --show-current`（FACT） |
| 与 Phase 1.55 审计基准 | 一致（未移动） | 同上（FACT） |
| 工作区条目数 | 960 行 `git status --short` | `git status --short \| wc -l`（FACT） |

工作区并非只有本阶段改动。**本阶段没有触碰、也没有清理**下列并行工作产物（FACT）：

- 未跟踪的新 Feature：`Features/anima_behaviour/`、`attribute_editor/`、`audio_player_pool/`、
  `blackboard/`、`clean_copy/`、`flying_letter/`、`pedestal_interaction/`、`pickable_audio/`
  （`git ls-files` 均为 0；创建时间 2026-10-31 20:54；**均无 `template.yaml`**）。
- `.ai/skills/foundation/godot-gdscript/code_library/sources/**` 等约 900 条第三方抓取文件。
- 5 个被修改的 `Features/*/feature.yaml`（attack_emitter / knockback / save_game / sfx_pool /
  state_machine）、`project.godot`、`feature_index.json`、`feature_graph.json`。

本阶段**自己**的文件（FACT，`git status` / `git diff --stat`）：

| 文件 | 变化 |
| --- | --- |
| `.ai/tools/scene_composer/feature_behavior_evidence.py` | +111 行（证据包构建 / 规范化哈希 / CLI `--evidence-out`、`--bundle-id`） |
| `.ai/tools/scene_composer/probes/feature_behavior_probe.gd` | +16 / −6（信号观测补 `observed_args`，`last_args` 改由同一份观测判定） |
| `.ai/tools/validator/check_behavior_evidence.py` | **新增**（L4 复核阶段，591 行） |
| `.ai/tools/validator/validate.py` | +81 行（`--behavior-evidence` 等 5 个 opt-in 参数 + 退出码） |
| `.ai/tools/validator/tests/test_behavior_evidence_stage.py` | **新增**（54 处断言调用） |
| `.ai/tools/validator/README.md` | +46 行（阶段文档） |
| `.ai/context/FEATURE_BEHAVIOR_COVERAGE.md` | +28 行（Phase 1.56 增量） |
| `.ai/context/WORK_STATE.md` / `CURRENT_TASK.md` | 顶部加本阶段状态块（保留原文） |
| `.ai/context/PHASE_1_56_COMPLETION_REPORT.md` | **新增**（本文件） |

未执行 `git add` / `commit` / `push`；未执行 `reset` / `checkout` / `clean` / `rebase`；
未删除或重命名任何既有文件（FACT：本次会话未运行这些命令）。

---

## 2. Evidence 原有结构（改造前）

`FACT`（读 `feature_behavior_evidence.py` 改造前代码）：

- 采集端产出 `BehaviorReport` 对象（`feature` / `behavior` / `scene` / `status` / `reason` /
  `detail` / `actual[]`，每条 `actual` = `{check, target, entry, expected, observed, status,
  first_observed_frame}`），状态集 `PASS / MISMATCH / INSUFFICIENT / INVALID / NOT_DECLARED`。
- **没有任何持久化格式**：结论只 `print` 到 stdout；`--json` 也只是把当次结果打到 stdout。
- **没有执行标识、时间戳、协议版本、内容摘要**；Validator 无法发现它，Evaluation 也读不到。
- Validator 侧只有静态阶段 + `--instance-evidence` / `--instance-runtime`（L2/L3），
  **没有**任何 L4 消费路径。

因此 Phase 1.55 的结论「Evidence 与 Validator 之间没有真实数据连接」在本阶段开始时仍然成立（FACT）。

---

## 3. 新增集成架构

```
Feature 实现（.gd / .tscn）
  → probes/feature_behavior_probe.gd（真实动作 + 真实 physics 帧 + 重放 2 次）
  → feature_behavior_evidence.py#verify_contract → BehaviorReport
  → feature_behavior_evidence.py#build_bundle  ── 证据包（JSON，L4，带完整性摘要）
  → validator/check_behavior_evidence.py#check_evidence ── 用 template.yaml#behavior 重算
  → validate.py --behavior-evidence（PASS/FAIL/INCOMPLETE/ERROR + 退出码 + 机器可读 JSON）
```

关键设计（FACT，见两个模块的 docstring 与代码）：

1. **采集与判定分家**：`build_bundle` 只记录观测；`check_evidence` 独立复算。
   采集侧不自证成功，这是本阶段的实质性变化，而不只是多一个 CLI 参数。
2. **不信任自报 `status`**：`judge_record()` 用契约 `expected` 与观测逐条比对；
   `record["status"]` 只在「观测满足契约但采集侧自称非 PASS」时用来产生
   `INCOMPLETE/evidence_self_contradiction`（冲突必须暴露，不能升级为 PASS）。
3. **等级隔离**：`SUPPORTED_LEVEL = "L4"`；证据包声明 L2/L5 → `FAIL`（实测 N7）。
4. **`observed: null` 不是违规**：`expected_holds()` 对缺失观测返回 `None` →
   `INCOMPLETE/observation_insufficient`（避免把「没测到」当成「行为错了」）。

---

## 4. 新增 CLI 参数

采集端（`feature_behavior_evidence.py`）：

| 参数 | 语义 |
| --- | --- |
| `--evidence-out DIR` | 把本次真实执行的证据写成证据包（JSON） |
| `--bundle-id ID` | 显式批次 id（默认 `<pid>-<uuid8>`） |

复核端（`validate.py`，全部 opt-in，默认不执行）：

| 参数 | 语义 |
| --- | --- |
| `--behavior-evidence` | 启用 L4 证据阶段 |
| `--evidence-dir DIR` | 证据包目录（默认 `.ai/tmp/behavior_bundles`） |
| `--evidence-feature ID`（可重复） | 只验证这些 Feature（其余记为 `summary.skipped_features`） |
| `--evidence-max-age-hours H` | 证据有效期，默认 24 |
| `--behavior-evidence-json PATH` | 机器可读结果落盘 |

独立入口：`python .ai/tools/validator/check_behavior_evidence.py --evidence-dir DIR
[--feature ID] [--json PATH] [--max-age-hours H] [--features-dir DIR] [--protocol PATH]`。

退出码（FACT，`exit_code_for()` 与 `validate.py` 分支）：PASS=0 / FAIL=1 / INCOMPLETE=2 /
ERROR=3；INCOMPLETE 在 `validate.py` 里不会被算作 0（`if not r.failures: exit_code = 2`）。

---

## 5. 新增验证规则（`check_behavior_evidence.py`）

证据包级（`check_evidence`）：

1. 证据目录不存在 / 为空 → `INCOMPLETE`（`evidence_unavailable` / `no_evidence`）。
2. `schema` / `schema_version` / `features` / `protocol` 结构非法 → `FAIL`。
3. `integrity.payload_sha256` **重算**比对（`verify_integrity`），不符 → `FAIL integrity mismatch`。
4. `protocol.protocol_version` 与当前协议不符 → `FAIL`；协议文件 `sha256` 不符 → `FAIL`。
5. `evidence_level != "L4"` → `FAIL`。
6. `generated_at` 缺失 → `INCOMPLETE`；超过 `max_age_hours` → `INCOMPLETE`。
7. 同一 `bundle_id` 内容不同 → `FAIL`；内容相同 → `INCOMPLETE`（duplicate execution）。
8. `Features/` 目录本身不可读 → `INCOMPLETE features_unavailable`（环境问题，不是证据缺陷）。

行为记录级（`judge_record`）：

9. 目标 Feature 不存在于 `Features/` → `FAIL unknown_feature`；
   存在于磁盘但未被 `--evidence-feature` 请求 → 跳过（`summary.skipped_features`，不连坐）。
10. `template.yaml` 未声明的 behavior → `FAIL unknown_behavior`。
11. 契约非法（`build_contracts` 返回 INVALID）→ `FAIL contract_invalid`。
12. 同一 behavior 有多条**冲突**记录 → `FAIL duplicate_conflict`；完全相同的重复记录 → 接受。
13. `action_executed != true` → `INCOMPLETE action_not_executed`（只有状态不算行为证据）。
14. `replay_count < 2` → `INCOMPLETE replay_missing`；`replay_consistent != true` →
    `INCOMPLETE replay_inconsistent`。
15. 观测条数与契约不一致 → `INCOMPLETE observation_count_mismatch`；
    check/target/entry 与契约不符 → `FAIL contract_violation`。
16. 观测值不满足 `equals` / `min` / `max` / `signal count` / `last_args` →
    `FAIL contract_violation`；无法判定 → `INCOMPLETE observation_insufficient`。
17. 未在契约中声明、又没有证据的 behavior → `INCOMPLETE behavior_uncovered`。

---

## 6. Evidence 完整性机制

`FACT`（`feature_behavior_evidence.py`）：

- `canonical_json()`：`json.dumps(..., sort_keys=True, separators=(",", ":"))`，UTF-8。
- `bundle_payload()`：除 `integrity` 之外的全部字段（**哈希不包含自己**）。
- `bundle_digest()`：对 `payload` 的规范化 JSON 求 SHA-256。
- 证据包同时记录 `protocol.protocol_version` 与协议文件 `sha256`、`git_head`、
  `generated_at`、`tool.module_version`。

`FACT`（`check_behavior_evidence.py#verify_integrity`）：Validator **重新计算**摘要，
不采信 `integrity` 里声明的期望值。

实测（真实 60 条证据包，`81d6666c446f69d7…`）：

```
# 篡改一条真实观测（不重签）
bundle tamper.json: FAIL integrity mismatch: payload sha256 d4630d19a3e35cc7 != declared 81d6666c446f69d7
pass=59 fail=1 incomplete=0 (checked=60)

# 删除一条行为记录并重签（攻击者知道规范化算法）
health post_death_guard INCOMPLETE behavior_uncovered | no evidence for this declared behavior
pass=59 fail=0 incomplete=1 (checked=60)
```

**信任边界（未解决，必须写清楚）**：摘要只证明「内容自生成后未变」。
能同时修改实现与证据包并重算摘要的人（同一权限、同一主机）仍可伪造。
本阶段**不声称**具备来源可信性证明；要解决需要外部签名 / 可信执行环境，架构上尚不存在。
另外，重放一致性、`action_executed` 都是**采集侧自报**的字段——它们提高伪造成本，但不构成证明。

---

## 7. L2 / L4 / L5 验证结果

| 层 | 本阶段状态 | 依据 |
| --- | --- | --- |
| L2 静态实例证据 | **未改变**（仍由 `check_instance_evidence` 负责，Validator 内既有阶段） | FACT：本阶段未改该模块 |
| L3 运行时实例证据 | **未改变** | FACT：同上 |
| L4 行为证据 | **首次进入 Validator**：23 Feature / 60 条行为全部被独立复核为 PASS | FACT：见 §9.1 |
| L5 缺陷注入 | **未批量声明**。本阶段只新增一条**可重复的 L5 式缺陷注入测试**（隔离副本内注入 `openable_door.set_open` 缺陷 → 采集器 FAIL → Validator `FAIL contract_violation` → 伪造 PASS 重签仍被拒 → 逐字节恢复后重新 PASS） | FACT：`test_behavior_evidence_stage.py` D0–D5 |

明确不做的声明：

- 证据包声明 L2/L5 → `FAIL`（L2/L5 不得冒充 L4），实测 N7。
- **不把 23 个 Feature 写成 L5 VERIFIED**。`FEATURE_BEHAVIOR_COVERAGE.md` §3 的逐 Feature
  状态未重新评级；`PARTIAL` 仍是 `PARTIAL`（本阶段没有为任何 Feature 补 L5 注入）。
- `PASS (L4)` 只表示「契约声明的行为在真实运行时符合」，不等于 `VERIFIED`。

---

## 8. 新增测试与结果

`.ai/tools/validator/tests/test_behavior_evidence_stage.py`（54 处断言调用，**ALL PASS**；最近一次 2026-11-01 18:08 运行 exit 0）：

| 组 | 覆盖 |
| --- | --- |
| P1–P5 | 合法证据 PASS；多 Feature；单 Feature 限定；同 Feature 多 behavior；两包相同记录不冲突 |
| N1–N20 | 未知 Feature / 未知 Behavior / 跨 Feature 关联 / 目录不存在 / 空目录 / 非法 JSON / L2·L5 冒充 / 协议版本 / 协议内容 / 内容篡改 / 过期 / bundle_id 复用 / 自报 PASS 但观测违规 / 观测条数 / 重放不足 / 重放不一致 / 动作未执行 / 自相矛盾 / 观测不可判定 / 未注册来源 |
| E1–E2 | 协议非法 → ERROR（exit 3）；`Features/` 不存在 → INCOMPLETE |
| C1–C5 | 独立 CLI 退出码 0/1/2；机器可读 JSON 字段完整；`validate.py` 默认不执行本阶段；`--behavior-evidence` 通过 0 / 被篡改 1 / **缺证据 2（不当作 PASS）** |
| D0–D5 | 真实 Godot 缺陷注入（隔离副本，不触碰 `Features/`） |

D 段实测输出要点（FACT）：

```
PASS: D0 夹具是隔离副本（不触碰真实 Features/）
PASS: D1 基线副本采集 -> 采集器 exit 0
PASS: D1b 基线证据被 Validator 复核为 PASS
PASS: D2b 缺陷副本采集器判为失败（exit 1，不静默 PASS）
PASS: D2d Validator 拒绝缺陷行为 -> FAIL contract_violation
PASS: D3 缺陷证据伪造 status=PASS 并重签摘要后仍被拒绝
PASS: D4b 恢复后采集器与 Validator 重新 PASS
PASS: D5 真实 Features/ 未被修改
  采集产物 run 目录清理：6 个
```

D 段的注入方式：在**临时副本**的 `openable_door.gd` 里把 `set_open()` 改成「入口存在但不再
改变状态」，随后重新采集。测试结束删除副本、按 sha256 校验真实 `Features/openable_door/openable_door.gd`
未被改动（FACT）。这不是「改 JSON 冒充缺陷注入」。

---

## 9. 真实证据链端到端结果

### 9.1 全量采集 + 复核（真实 Godot）

```
python .ai/tools/scene_composer/feature_behavior_evidence.py --all \
    --evidence-out .ai/tmp/p156/bundles_full
→ pass=60 mismatch=0 insufficient=0 invalid=0 not_declared=0
→ bundle: .ai/tmp/p156/bundles_full/9292-67ef7282-bundle.json (integrity sha256 81d6666c446f69d7)

python .ai/tools/validator/validate.py --behavior-evidence \
    --evidence-dir .ai/tmp/p156/bundles_full \
    --behavior-evidence-json .ai/tmp/p156/validator_evidence_full.json
→ Behavior evidence (L4): PASS (bundles=1, features=23, pass=60, fail=0, incomplete=0)
→ WARNING: 0 error(s), 17 warning(s)
→ exit 0
```

证据包内容（FACT）：`schema=feature_behavior_evidence_bundle`、`schema_version=1`、
`evidence_level=L4`、`protocol={protocol_version: 2, sha256: d2a480b0…}`、`git_head=dd3a0e4…`、
23 个 feature 块 / 60 条 behavior 记录，每条含 `action_executed`、`replay_count: 2`、
`replay_consistent: true`、`actual[]`（`expected` / `observed` / `observed_args`）、`evidence_paths`。

### 9.2 反向（真实数据上的拒绝）

| 操作 | 结果 |
| --- | --- |
| 未请求 Feature 的记录（`--evidence-feature health` 面对 23 Feature 的证据包） | 跳过并记入 `summary.skipped_features`，不判失败（P4 实测） |
| 删除 1 条行为记录并重签摘要 | `INCOMPLETE behavior_uncovered`（59 PASS + 1 INCOMPLETE） |
| 篡改 1 条真实观测 | `FAIL integrity mismatch`（且该行为本身也 `contract_violation`） |

---

## 10. 原有 Validator 兼容性回归

| 检查 | 命令 | 结果 |
| --- | --- | --- |
| 默认运行不执行新阶段、结果不变 | `python .ai/tools/validator/validate.py` | `exit 0`，`0 error(s), 17 warning(s)`，输出中 **0** 行 `Behavior evidence`（FACT） |
| 七/八阶段与静态检查 | 同上 | 0 error / 17 warning（FACT，本次实测）；新阶段默认关闭，不新增 error/warning 类型 |
| Validator 测试段（11 文件） | `python .ai/tools/run_tests.py validator` | **11/11 PASS**（含新测试 `test_behavior_evidence_stage.py`；补 C5 用例后单文件重跑 `ALL PASS`） |
| Feature Registry 段（4 文件） | `python .ai/tools/run_tests.py feature_registry` | **4/4 PASS** |
| Evaluation 段（2 文件） | `python .ai/tools/run_tests.py evaluation` | **2/2 PASS** |
| Scene Composer 段（31 文件） | `python .ai/tools/run_tests.py scene_composer` | **28 PASS / 3 FAIL**，3 个失败全部归属并行工作（见 §11） |

CLI 默认行为未被改动（FACT，`git diff validate.py`：所有新参数均为 `store_true` / 带默认值的
opt-in，且 `behavior_result` 仅在 `args.behavior_evidence` 为真时计算）。

---

## 11. 未归属本阶段的失败（如实记录）

`run_tests.py scene_composer`（31 文件，日志 `.ai/tmp/p156/scene_composer_regression.log`）：

| 失败测试 | 失败断言（原文摘要） | 归属 |
| --- | --- | --- |
| `test_feature_capability_adoption.py` | `audit: attribute_editor declaration matches its own scene/contract evidence`（另有 audio_player_pool / blackboard / clean_copy / flying_letter / pedestal_interaction / pickable_audio，以及 `every real feature declares something` 列出 `anima_behaviour: []`） | **UPSTREAM（并行工作）** |
| `test_feature_capability_pipeline.py` | `case1: every real project feature declares at least one capability (adopted)`，值为同一批 8 个 Feature → `[]` | **UPSTREAM（并行工作）** |
| `test_scene_composer.py` | `template: anima_behaviour exists` …（同一批 8 个 Feature 缺 `template.yaml`） | **UPSTREAM（并行工作）** |

证据（FACT）：

- 这 8 个目录 `git ls-files Features/<id>` 均为 **0**（未跟踪），创建时间 2026-10-31 20:54，
  且**都没有 `template.yaml`**。
- 三个失败断言的差异内容与这 8 个目录**逐一对应**，没有第 9 个。
- 本阶段改动不涉及 `feature_capabilities.py` / `capability_registry.py` / `template_loader.py`
  / `scene_composer.py`（`git diff --stat` 可证）。
- 同一天更早（2026-10-30 02:34）的 scene_composer 分段日志为 30 PASS / 1 FAIL，
  失败项与本批 8 个 Feature 无关。

**单独复现（FACT，2026-11-01 18:06 重跑三次，单文件执行）**：

```
python .ai/tools/run_tests.py .ai/tools/scene_composer/tests/test_feature_capability_adoption.py  → exit 1
python .ai/tools/run_tests.py .ai/tools/scene_composer/tests/test_feature_capability_pipeline.py  → exit 1
python .ai/tools/run_tests.py .ai/tools/scene_composer/tests/test_scene_composer.py               → exit 1
```

失败断言与 §11 表格逐字一致，日志在 `.ai/tmp/p156/rerun_*.log`。

限制：不能在**不触碰**并行工作目录的前提下做 HEAD-only 复跑（那需要 `git stash`/`clean`/
删除未跟踪目录，本阶段明令禁止）。因此「归属并行工作」的依据是：
（a）失败断言的差异集合恰好是这 8 个未跟踪目录，无第 9 项（FACT）；
（b）这 8 个目录 `git ls-files` = 0 且无 `template.yaml`（FACT）；
（c）本阶段 diff 不涉及 `feature_capabilities.py` / `capability_registry.py` /
`template_loader.py` / `scene_composer.py`（FACT）。
「这 3 个失败在干净的 HEAD 上不存在」仍是 `INFERENCE`，未做隔离复跑。

其余失败：**无**。`test_feature_behavior_evidence.py`（真实 23 Feature / 60 行为）在本次
分段中 **PASS**（FACT，`[14/31] PASS`），即本阶段改动未破坏既有真实行为证据采集。

---

## 12. 测试统计（区分文件数 / 用例数 / 执行状态）

发现（FACT，本次统计）：

- Python 测试文件 **62**（`.ai/tools/**/tests/test_*.py`）。
- Godot 测试文件 **57**（`Tests/test_*.gd` + `Features/*/test_*.gd`；其中 8 个来自并行新增 Feature）。
- Python 测试内的 `test_*` 函数只有 **22** 个（4 个文件），主流风格是 `ok()` 断言函数：
  `ok()/check()/expect()` 调用点 **2371** 处。**文件数不等于用例数**，本报告不把两者相加。

执行（FACT）：

| 段 | 命令 | 文件 | 结果 |
| --- | --- | --- | --- |
| validator | `run_tests.py validator` | 11 | 11 PASS / 0 FAIL |
| feature_registry | `run_tests.py feature_registry` | 4 | 4 PASS |
| evaluation | `run_tests.py evaluation` | 2 | 2 PASS |
| scene_composer | `run_tests.py scene_composer` | 31 | 28 PASS / 3 FAIL（UPSTREAM） |
| asset_registry | `run_tests.py asset_registry` | 11 | 11 PASS |
| runtime | `run_tests.py runtime` | 5（含 2 个 scene_composer 文件） | 5 PASS |
| gameplay_planner | `run_tests.py gameplay_planner` | 2 | 2 PASS |
| e2e | `run_tests.py <test_end_to_end_generation.py>` | 1 | 1 PASS（exit 0，29 min，§12.1） |

并集证明（去重后）：

- 段文件集合存在重叠：`validator` 段与 `scene_composer` 段重叠 3 个
  （`test_artifact_evidence_validator.py` / `test_capability_contract_validator.py` /
  `test_scene_validator_intent_input.py`），`runtime` 段与 `scene_composer` 段重叠 2 个。
- 去重后**已执行 Python 文件 = 62 / 62**（全部发现的 Python 测试文件都被至少一段覆盖）。
- **Godot SceneTree 测试 57 个文件本次未执行**（本阶段改动不涉及 `.gd` 生产代码；真实 Godot
  运行时通过 L4 探针执行了 60 条行为 + D 段缺陷注入 3 轮，但这不能算作 SceneTree 测试通过）。
- **不宣称「全量单命令通过」**：上述结果是 8 个分段串行执行的并集，任何一段的
  INCOMPLETE/FAIL 都没有被其它段抵消。

### 12.1 e2e 段

`python .ai/tools/run_tests.py .ai/tools/e2e/tests/test_end_to_end_generation.py`（2026-11-01 18:08 启动，
18:37 结束，约 29 min）：

```
[run_tests] 1 tests (Godot=0, Python=1)
[1/1] PASS .ai/tools/e2e/tests/test_end_to_end_generation.py
completed=1/1 passed=1 failed=0 incomplete=0 unavailable=0 not_executed=0
ALL PASS
EXIT=0
```

（FACT，日志 `.ai/tmp/p156/e2e_current.log`。该测试内部自己调用真实 Godot 完成生成→验证→探针
全链路；`Godot=0` 只表示它不是 SceneTree 测试文件，不表示没有 Godot 参与。）

之前一轮 `.ai/tmp/p156/e2e_regression.log` 里的 `INCOMPLETE (exit=1073807364)` 是我在上一会话
手动终止进程造成的（`0x40010004` = 进程被终止），**不是测试失败**（FACT）。本次为完整跑完的结果。

---

## 13. 验收矩阵

| 编号 | 验收项 | 状态 | 证据 |
| --- | --- | --- | --- |
| A1 | Validator 能发现 Evidence | ✅ | `--evidence-dir` 扫描 `*.json`，实测 1 个 bundle |
| A2 | 能解析 Evidence | ✅ | `load_bundle` + schema 校验，N6 非法 JSON → FAIL |
| A3 | 能关联 Feature | ✅ | 23 Feature 覆盖；N1 未知 Feature → FAIL |
| A4 | 能关联 Behavior | ✅ | 60 行为；N2 未知 Behavior → FAIL |
| A5 | 能校验 Evidence Level | ✅ | N7 L2/L5 → FAIL |
| A6 | 能检查完整性 | ✅ | N10 / 真实篡改 → `integrity mismatch` |
| A7 | 能按观测验证契约 | ✅ | `judge_record` 复算；N13 自报 PASS + 违规观测 → FAIL |
| A8 | 机器可读输出 | ✅ | `--behavior-evidence-json` / `check_behavior_evidence.py --json`（C1d 断言字段） |
| B1 | 合法证据 PASS | ✅ | P1/P2/P3/P4/P5 + 真实 60 条 PASS |
| B2 | 明确违规 FAIL | ✅ | N13、D2d、真实篡改 |
| B3 | 缺证据 INCOMPLETE | ✅ | N5、N14、真实删记录 |
| B4 | 缺 Godot 环境 INCOMPLETE | ✅（结构性） | 采集端无 Godot 时报告 `insufficient`，不会产出 PASS 证据包；D 段在无 Godot 时**测试显式判 FAIL（记为未执行）**，不伪装通过 |
| B5 | 验证器异常 ERROR | ✅ | E1 协议非法 → exit 3 |
| B6 | L2/L4/L5 正确区分 | ✅ | N7 + §7；不批量声明 L5 |
| C1 | 篡改可检测 | ✅ | N10 + 真实篡改 |
| C2 | 错误 Feature 关联拒绝 | ✅ | N1 |
| C3 | 错误 Behavior 关联拒绝 | ✅ | N2 / N3 |
| C4 | 旧证据重复使用可识别/限制 | ⚠️ 部分 | 过期 → INCOMPLETE（N11）；`bundle_id` 复用不同内容 → FAIL（N12）；但**同一份合法证据在有效期内可以被重复提交**（当前只在 `summary` 里体现 bundle 数），没有「批次唯一性」强制 |
| C5 | 自报 PASS 不绕过实际检查 | ✅ | N13、D3 |
| C6 | 记录来源真实性未解决 | ✅（如实记录） | §6 信任边界 |
| D1 | 原有七/八阶段全部通过 | ✅ | 默认 `validate.py` 0 error / 17 warning |
| D2 | 原有 CLI 默认行为不变 | ✅ | C2 实测 |
| D3 | Feature Registry 回归 | ✅ | 4/4 |
| D4 | Scene Composer 无**新增**失败 | ⚠️ 见下 | 28 PASS / 3 FAIL，3 个失败归并行工作（§11），既有 L4 测试仍 PASS |
| D5 | Evaluation 原有测试通过 | ✅ | 2/2 |
| D6 | 测试统计准确 | ✅ | §12（文件数 / 用例风格 / 执行状态分开） |
| E1 | 新增独立测试 | ✅ | `test_behavior_evidence_stage.py` 54 处断言 |
| E2 | 至少一个真实行为缺陷注入端到端 | ✅ | D0–D5（真实 Godot，隔离副本） |
| E3 | 临时产物隔离 | ✅ | 夹具在 `.ai/tmp/bev_stage_*`，结束删除；采集 run 目录按证据登记清理（6 个） |
| E4 | 无意外工作区修改 | ✅ | §1；未触碰并行产物 |
| E5 | 文档与实现一致 | ✅ | validator/README、FEATURE_BEHAVIOR_COVERAGE、WORK_STATE、CURRENT_TASK |

**D4 的诚实结论**：本阶段**没有**引入 Scene Composer 的新失败（既有 `test_feature_behavior_evidence.py`
等仍 PASS），但该段当前**不是全绿**；失败原因是他人在本工作区未完成的 8 个 Feature。
按本阶段的完成定义，这不构成本阶段的失败，但也**不能**写成「Scene Composer 全绿」。

---

## 14. 尚未解决的问题

1. **来源可信性未解决**：内容哈希不能证明证据由谁产生；同一权限可同时改实现与证据并重签。
2. **采集侧自报字段**：`action_executed` / `replay_count` / `replay_consistent` 由采集端写入，
   Validator 只能校验其内部一致性（例如 `replay_count` 与 `evidence_paths` 数量）
   ——本阶段**没有**做这一项交叉校验，是下一步最便宜的加固点。
3. **批次唯一性/新鲜度**：目前只按 `generated_at` + 24 h 判定，没有「本次执行批次」概念；
   合法证据可在有效期内重复提交。
4. **Evaluation 未接入**：Parser/评分器尚未消费 `--behavior-evidence-json`（Phase 1.58）。
5. **`observed: null` 语义**：当前一律 INCOMPLETE；对「契约要求不存在」的场景（如
   `equals: false`）是否应改为「null 即满足」尚未定义，本阶段保守处理。
6. **并行工作导致的 Scene Composer 段 3 个失败**（§11），不属本阶段但当前阻塞该段全绿。
7. **Godot SceneTree 57 个测试文件本阶段未执行**（改动不涉及 `.gd` 生产代码，但这是真实缺口）。

---

## 15. 下一阶段建议

按「最便宜的加固点 → 最大收益」排序：

1. **（Phase 1.57 候选）采集侧自报字段的交叉校验**：用 `evidence_paths` 中真实存在的
   `result.json` 复核 `replay_count` / `replay_consistent`；缺失即 INCOMPLETE。
   成本低、直接抬高伪造门槛，仍不声称来源可信。
2. **批次语义**：证据包与一次 CI 运行绑定（例如 `run_id` + 同批次所有 Feature 必须来自
   同一 `git_head`），解决「合法证据重复提交」。
3. **（Phase 1.58）Evaluation 消费证据**：让评分器读 `--behavior-evidence-json`，
   把「行为契约覆盖率 / L4 PASS 率」纳入指标，而不是只看任务是否完成。
4. **L5 缺口补齐**：按 `FEATURE_BEHAVIOR_COVERAGE.md` §7 的优先级（`player_movement` →
   `collect_pickup` / `heal_pickup`）补缺陷注入，仍然一个 Feature 一个 Feature 地做，
   不要批量声称。
5. **等并行 Feature 落地后重跑 scene_composer 段**，确认 §11 的 3 个失败消失（回归基线恢复）。

不做的事：不为「全绿」放宽断言；不用 L4 冒充 L5；不改协议词汇来迁就测试。

---

## 16. 证据文件与可复现命令

| 内容 | 路径 |
| --- | --- |
| 全量采集日志 | `.ai/tmp/p156/collect_full.log` |
| 证据包（23 Feature / 60 行为） | `.ai/tmp/p156/bundles_full/9292-67ef7282-bundle.json` |
| Validator 复核日志 / JSON | `.ai/tmp/p156/validate_with_evidence.log`、`.ai/tmp/p156/validator_evidence_full.json` |
| 默认运行（无证据阶段） | `.ai/tmp/p156/validate_default.log` |
| 反向（删记录 / 篡改） | `.ai/tmp/p156/neg_drop/`、`.ai/tmp/p156/neg_tamper/` |
| Scene Composer 回归 | `.ai/tmp/p156/scene_composer_regression.log` |
| 3 个失败测试的单文件复现 | `.ai/tmp/p156/rerun_test_feature_capability_adoption.log` 等 3 个 |
| 证据阶段测试（含 C5） | `.ai/tmp/p156/stage_test_c5.log` |
| 证据包在当前协议下重校 | `.ai/tmp/p156/revalidate_full.log`（`pass=60 fail=0 incomplete=0`，exit 0） |
| e2e 回归 | `.ai/tmp/p156/e2e_current.log`（ALL PASS，exit 0） |

```bash
# 0) 新阶段测试（含真实缺陷注入，约 66 s）
python .ai/tools/validator/tests/test_behavior_evidence_stage.py

# 1) 采集真实 L4 证据（真实 Godot，约 5 min）
python .ai/tools/scene_composer/feature_behavior_evidence.py --all --evidence-out .ai/tmp/p156/bundles_full

# 2) Validator 独立复核
python .ai/tools/validator/validate.py --behavior-evidence \
    --evidence-dir .ai/tmp/p156/bundles_full --behavior-evidence-json .ai/tmp/p156/validator_evidence_full.json

# 3) 回归分段
python .ai/tools/run_tests.py validator
python .ai/tools/run_tests.py feature_registry
python .ai/tools/run_tests.py evaluation
python .ai/tools/run_tests.py scene_composer
```
