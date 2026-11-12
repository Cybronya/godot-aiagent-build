# Phase 1.68.3.1 — Phase 5: Batch F Pre-Audit

## A. Audit Summary

| 项目 | 值 |
|---|---|
| 最终状态 | **READY_FOR_REVIEW** |
| 审计时间 | 2026-11-12 20:56:37（本地） |
| 当前 HEAD | `71f6eef61c1b203229e93a47a111f5ce040c587f` |
| 当前 branch | `master` |
| 当前 Git dirty | **1065** |
| staged | 0 |
| untracked | 1000 |
| Python / Godot 残留进程 | 无 |
| 技术阻断项 | 0 |
| 文档缺口 | 未发现独立的 `PHASE_1_68_3_1_PHASE_5_REGRESSION_PLAN.md`；Phase 3 §7 是当前仓库内唯一完整的 Batch F 权威计划 |

### 结论边界

本报告只完成 Batch F 的执行前审计。`READY_FOR_REVIEW` **不代表** Batch F 已获执行授权，也不代表 Batch F 会 PASS。

Batch F 测试未执行，未启动 Godot，未运行全量测试，未清理 Runtime 文件，未修改生产代码、测试、Feature、Scene、Protocol、Evidence、Attestation 或索引，未提交或推送 Git。

### 文档缺口说明

任务要求读取独立的 “Phase 5 Regression Plan”。对 `.ai/context`、`.ai/memory`、`.ai/config` 的名称与内容检索未发现该独立文件：

```text
.ai/context/PHASE_1_68_3_1_PHASE_5_REGRESSION_PLAN.md  (不存在)
```

当前仓库内实际存在并承载原始计划的是：

```text
.ai/context/PHASE_1_68_3_1_PHASE_3_REGRESSION_DEPENDENCY_AUDIT.md
```

其 §7 `Recommended Execution Order` 明确定义了 Batch F 名单、顺序和预算，§5 执行矩阵记录了每项依赖和 Runtime 范围。因此 Batch F 的名单、顺序和验收标准并非缺失；缺失的是一个独立命名的计划文件。本次没有创建替代文件来伪造该文档。

如果负责人要求“独立 Phase 5 Regression Plan 文件存在”本身作为执行前置条件，则应把当前状态视为 **BLOCKED**，直到该文件被提供或明确认可 Phase 3 §7 为权威计划。就现有仓库权威数据而言，Batch F 范围完整、可审计，故本报告结论为 `READY_FOR_REVIEW`。

### 已读取的项目依据

- `AI_ENTRY.md`
- `AGENT_ONBOARDING.md`
- `.ai/context/PHASE_1_68_3_1_PHASE_3_REGRESSION_DEPENDENCY_AUDIT.md`
- `.ai/context/PHASE_1_68_3_1_PHASE_5_BATCH_B_REPORT.md`
- `.ai/context/PHASE_1_68_3_1_PHASE_5_BATCH_D_REPORT.md`
- `.ai/context/PHASE_1_68_3_1_PHASE_5_BATCH_A_BOUNDARY_AUDIT.md`
- `.ai/context/WORK_STATE.md`
- `.ai/memory/HISTORY.md`
- `.ai/config/agent.yaml`
- `.ai/config/framework-rules.yaml`
- `.ai/skills/engineering/godot-debug-testing/SKILL.md`
- Batch F 两项测试源码及 `composite_behavior_evidence.py`

`WORK_STATE.md` 和 `HISTORY.md` 没有 Phase 1.68.3.1 的阶段记录；它们不能作为 Batch F 的依据。Batch F 仍以 Phase 3 原始审计及其后续 Batch 报告为准。

---

## B. Authoritative Test Inventory

### B.1 原始来源

主来源：

```text
.ai/context/PHASE_1_68_3_1_PHASE_3_REGRESSION_DEPENDENCY_AUDIT.md
§7 Recommended Execution Order
§7 Batch F — Composite / End-to-End（行 423–433）
§5 Execution Matrix（行 206、227）
```

交叉确认：

```text
.ai/context/PHASE_1_68_3_1_PHASE_5_BATCH_A_BOUNDARY_AUDIT.md
§3.6 Batch F（行 137–144）
Batch F 仍保留原始 2 项（行 250–256）
```

该边界审计明确：

- `test_composite.py` 属于 Batch A，不属于 Batch F；
- Batch F 只有 `test_composite_behavior_evidence.py` 和 `test_slime_contact_arena.py`；
- 不能因为文件名相似把 `test_composite.py` 混入 F；
- Batch F 仍未执行。

### B.2 权威名单与执行顺序

严格按 Phase 3 §7 Batch F 的原始顺序：

1. `test_composite_behavior_evidence.py`
2. `test_slime_contact_arena.py`

实际路径：

```text
.ai/tools/scene_composer/tests/test_composite_behavior_evidence.py
.ai/tools/scene_composer/tests/test_slime_contact_arena.py
```

没有增加、删除、替换或重排测试。

### B.3 每项测试的目标和覆盖范围

#### 1. `test_composite_behavior_evidence.py`

源码声明：Phase 1.46，真实组合场景行为证据。

覆盖：

- Composite protocol、manifest、probe capability 门禁与漂移检测；
- `Scenes/EscapeRoom.tscn` 的四阶段端到端链：
  `closed_door_blocks_traversal`
  → `switch_a_partial_condition_keeps_door_closed`
  → `switch_b_fulfils_gate_and_opens_door`
  → `player_traverses_opened_gap`；
- `Scenes/SurvivalArena.tscn` 的一开关开双门链；
- 非法组合契约、白名单、路径越界、窗口/预算、重复阶段；
- 断开连接、门已报开但仍阻挡、观测目标缺失、前置条件不满足、中间状态错误；
- 零帧/纯否定期望的探针层门禁；
- 重放不一致、CLI 退出码、资源所有权、隔离副本恢复、仓库黄金文件保护。

源码顶部声明 14 个 Case；历史审计记录为 **100 PASS / 0 FAIL**（仅作历史参考，不替代本次执行结果）。

#### 2. `test_slime_contact_arena.py`

源码声明：Phase 1.48，真实 Slime Contact E2E acceptance。

覆盖：

- 正式场景 `Scenes/SlimeContactArena.tscn` 的真实 Player + SlimeEnemy；
- 三阶段链：
  `approach_without_contact_deals_no_damage`
  → `contact_deals_one_tick_of_damage`
  → `leaving_contact_stops_damage`；
- 真实输入移动、物理重叠、ContactDamage 节奏、玩家 Health 扣血与信号；
- 接触形状删除、伤害调用静音、玩家 group 缺失、观测目标缺失、观察窗口不足、无接触却期望伤害；
- 重放不一致、非法/越权场景、CLI 退出码、隔离副本恢复、仓库文件保护。

源码顶部声明 11 个 Case；历史审计记录为 **77 PASS / 0 FAIL**（仅作历史参考，不替代本次执行结果）。

### B.4 预期 PASS / FAIL 判定

两项测试共同的正式判定：

| 结果 | 条件 |
|---|---|
| **VERIFIED_PASS** | 退出码 0；stdout 最终包含对应 `PASS: all ...`；没有 `FAIL:` 行；无 `SKIP:`；无超时 |
| **VERIFIED_FAIL** | 退出码非 0，或 stdout 出现任何 `FAIL:` |
| **EXECUTION_BLOCKED** | Godot 不存在、环境不完整、输出 `SKIP:`，或无法形成可判定结果 |
| **EXECUTION_TIMEOUT** | 外层 `timeout 300s` 返回 124 |
| **UNKNOWN** | 进程被外部终止、输出不完整、无法归因为上述类别 |
| **NOT_EXECUTED** | 未启动或在前序失败后停止 |

终态字符串：

```text
PASS: all composite behavior evidence checks passed
PASS: all slime contact acceptance checks passed
```

不要用历史 `100` 或 `77` 计数代替实际退出码与日志。若实际 PASS 行数不同但测试正常退出且无 FAIL，应先核对测试版本与输出，不应自行改断言或降低判定标准。

### B.5 完整性与预算

| 测试 | 行数 | 大小 | SHA256 | 外层预算 |
|---|---:|---:|---|---:|
| `test_composite_behavior_evidence.py` | 744 | 39734 | `dc1a1ec1ba90d20d4314e6113c6288a0cf87fb62fc2f5d742eb44c2ee87bf004` | 300s |
| `test_slime_contact_arena.py` | 597 | 31891 | `7cb3e03c8593b6fc50c06e7a5f0565263fe0d1f6ab4a34c3119c593090b0fb0a` | 300s |

预算来源：`.ai/tools/run_tests.py` 默认 `PYTHON_TIMEOUT_PER_TEST = 300`；Batch F 两项没有 `PYTHON_TIMEOUT_OVERRIDES`。测试内部的 workspace import 预算分别为 120s、180s，probe 调用还有 60/120s 的内部超时；外层仍按 300s 执行，不自行延长。

---

## C. Dependency Analysis

### C.1 Batch B / D / F 关系

| 批次 | 数量 | 测试文件 | 主要 Runtime 范围 |
|---|---:|---|---|
| Batch B | 8 | `test_runtime_instance_evidence` 等 8 项 | `.ai/tmp/behavior`、`.ai/tmp/runtime-instance` |
| Batch D | 1 | `test_feature_behavior_evidence.py` | `.ai/tmp/behavior`、`.ai/tmp/runtime-instance` |
| Batch F | 2 | `test_composite_behavior_evidence.py`、`test_slime_contact_arena.py` | `.ai/tmp/composite`、`.ai/tmp/composite/workspaces` |

无测试文件重叠：

- Batch F 不含 Batch B 的 8 项；
- Batch F 不含 Batch D 的 `test_feature_behavior_evidence.py`；
- Batch F 不含 Batch A 的 `test_composite.py`；
- Batch F 不执行 Batch F 之外的任何测试。

### C.2 是否依赖 B / D 的 Runtime 产物

**不依赖 B / D 生成的 Evidence 来通过。**

`CompositeWorkspace` 会从当前项目重新复制：

```text
Features/
Scenes/
Orchestration/
Levels/
Systems/
Assets/
icon.svg
```

并写入自己的 `project.godot`，执行 `--import`。它不会读取 `.ai/tmp/behavior` 或 `.ai/tmp/runtime-instance` 的历史结果，也不会把 B/D 的 PASS 当作 F 的输入。

Batch F 依赖的是：

- 当前仓库的正式 `Scenes/`、`Features/`；
- `.ai/context/composite_behavior_protocol.yaml`；
- `.ai/context/composite_scenes/*.yaml`；
- `.ai/tools/scene_composer/probes/` 的 manifest 与 probe；
- Godot 可执行文件和项目内 `.godot`/import 能力；
- 项目内 `.ai/tmp/composite` 的写入权限。

### C.3 执行顺序

Phase 3 原始顺序：

```text
1. test_composite_behavior_evidence.py
2. test_slime_contact_arena.py
```

顺序理由：

- 两项共享 `.ai/tmp/composite` 和 `.ai/tmp/composite/workspaces`；
- 两项都启动真实 Godot，且 `CompositeWorkspace` 默认不设置独立 `user://` 标签；
- 没有并行安全证据；
- 先运行组合基础链，再运行 Slime 接触验收链，便于按失败点定位；
- 每项独立 Python 进程，前一项退出并确认无残留后再启动下一项。

### C.4 共享状态 / 竞争风险

| 共享对象 | 风险 | 结论 |
|---|---|---|
| `.ai/tmp/composite/` | 两项都写 evidence；唯一 run id 降低碰撞，但目录保留 | 串行，快照 |
| `.ai/tmp/composite/workspaces/` | 两项都创建/关闭隔离 workspace；中断会遗留 | 串行，快照，不清理未知目录 |
| `.ai/tmp/composite_protocol_cases/` | 固定目录，9 个文件会被覆盖 | 执行前后哈希，保留 |
| `.ai/tmp/composite_bad_contracts/` | 固定 `escape_room.yaml` 被覆盖 | 执行前后哈希，保留 |
| `.ai/tmp/composite_invalid_contracts/` | 固定 `escape_room.yaml` 被覆盖 | 执行前后哈希，保留 |
| `.ai/tmp/slime_bad_contracts/` | 固定 `slime_contact.yaml` 被覆盖 | 执行前后哈希，保留 |
| Godot `user://` | `CompositeWorkspace` 未启用 per-run custom user dir；默认共享 | 必须重定向到项目内环境目录，严格串行 |
| `.godot` 类缓存 | workspace 复制项目后执行 `--import`，不复制 `.godot` | 必须确认 stdlib 缓存/import 正常 |
| Batch B/D evidence | F 不读取、不覆盖 `.ai/tmp/behavior` / `runtime-instance` | 仍需保护并确认零变化 |

### C.5 与 Batch D 的重复验证判断

- Batch D 验证的是单 Feature 的 Behavior/Evidence 全覆盖；
- Batch F 验证的是 Composite 场景的多阶段端到端链、跨 Feature 交互、场景白名单、资源所有权；
- 两者共享 Behavior/Composite Protocol 和 Godot Runtime，但测试输入、隔离 workspace 和主要输出目录不同；
- 不能因为 D 已 PASS 就删除、跳过或缩减 F；
- F 仍需独立执行并保留自己的日志和证据。

---

## D. Runtime Side-effect Risk

### D.1 预期写入范围

Batch F 的预期项目内写入：

```text
.ai/tmp/composite/                         # evidence 根，保留
.ai/tmp/composite/workspaces/              # 隔离项目副本，测试拥有的会删除
.ai/tmp/composite_protocol_cases/          # 固定非法协议夹具，覆盖
.ai/tmp/composite_bad_contracts/           # 固定坏契约，覆盖
.ai/tmp/composite_invalid_contracts/       # 固定非法契约，覆盖
.ai/tmp/slime_bad_contracts/               # 固定 Slime 坏契约，覆盖
```

测试自身的隔离 workspace：

```text
.ai/tmp/composite/workspaces/<run_id>/
  owner.json
  project/
    Features/
    Scenes/
    Orchestration/
    Levels/
    Systems/
    Assets/
    icon.svg
    project.godot
    .ai/tools/scene_composer/probes/...
```

`CompositeWorkspace.close()` 只在 `owner.json` 的 `run_id` 证明归本运行所有时才 `rmtree`；其他运行目录只报告，不删除。

### D.2 当前已存在的副作用目标

本次审计时：

| 路径 | 当前状态 |
|---|---|
| `.ai/tmp/composite/` | 存在，顶层 1047 项 |
| `.ai/tmp/composite/workspaces/` | 存在，5 个顶层 workspace |
| `.ai/tmp/composite_protocol_cases/` | 存在，9 个固定夹具文件 |
| `.ai/tmp/composite_bad_contracts/` | 存在，`escape_room.yaml` |
| `.ai/tmp/composite_invalid_contracts/` | 存在，`escape_room.yaml` |
| `.ai/tmp/slime_bad_contracts/` | 存在，`slime_contact.yaml` |
| `.ai/tmp/composite/workspaces/999-ffffffffff` | **不存在** |

已经存在 5 个 workspace：

```text
12636-25bdc17e3c-test
12636-5cbe75aff5-cli
532-752811885d-cli
532-7b70d4179e-test
7276-bc3c6d345e-slime
```

不得清理这些历史目录；执行前后必须逐项比较。

### D.3 可能的覆盖 / 删除风险

1. **固定目录覆盖**：`composite_protocol_cases`、`composite_bad_contracts`、`composite_invalid_contracts`、`slime_bad_contracts` 由测试写入，固定文件名会覆盖上一次内容。必须执行前完整快照并保留前后差异。
2. **固定 fake foreign workspace**：`test_composite_behavior_evidence.py` 使用固定名 `999-ffffffffff`；当前不存在，但测试会创建并最后删除它。如果未来在执行前出现同名目录，测试可能覆盖/删除它；执行前检查必须将其视为阻断项或先由负责人处理。不得自行清理。
3. **唯一 workspace**：`CompositeWorkspace` 使用 run id，正常关闭只删自己的目录；中断、崩溃或外部 kill 会留下 workspace。异常时保留现场，不自动清理。
4. **证据目录**：`.ai/tmp/composite/<run_id>` 由 `run_probe` 创建并保留。测试完成或失败都可能留下 evidence；不能把新增 evidence 当污染。
5. **固定 bad contract 写入**：测试写入 `.ai/tmp/...` 的 YAML 文件；这是预期副作用，不是对正式契约的修改。正式 `.ai/context/composite_scenes/*.yaml` 仍需受保护。
6. **共享 `user://`**：`CompositeWorkspace` 没有强制 per-run `custom_user_dir`；默认 Godot user 目录可能跨测试共享。必须用项目内 `APPDATA`/`LOCALAPPDATA`/`TEMP` 重定向，串行执行。
7. **磁盘/IO**：两个 workspace 会复制 `Features`、`Scenes`、`Orchestration`、`Levels`、`Systems`、`Assets`，并执行真实 `--import`；CPU/磁盘压力明显，不能用并行缩短。
8. **B/D 产物隔离**：F 不应写 `.ai/tmp/behavior` 或 `.ai/tmp/runtime-instance`。执行前后必须确认这两棵树没有变化；若变化，停止并保留现场。

### D.4 清理行为风险

- `CompositeWorkspace.close()` 是所有权保护的删除；只处理本 run。
- `stale_workspaces()` 只读，不删除其他运行。
- 测试 Case 13 会创建并删除自己的 fake foreign workspace；必须在快照中检查 `999-ffffffffff` 是否在执行前存在。
- 不允许在 Batch F 执行中清理任何历史 workspace、evidence、固定目录或未知文件。
- 不允许用删除证据的方式让测试变绿。

### D.5 环境隔离要求

执行时应设置项目内路径：

```text
APPDATA       -> <project>/.ai/tmp/phase5_batch_f_logs_20261112/runtime_env/appdata
LOCALAPPDATA  -> <project>/.ai/tmp/phase5_batch_f_logs_20261112/runtime_env/localappdata
TEMP / TMP    -> <project>/.ai/tmp/phase5_batch_f_logs_20261112/runtime_env/temp
TMPDIR        -> <project>/.ai/tmp/phase5_batch_f_logs_20261112/runtime_env/temp
PYTHONPYCACHEPREFIX -> <project>/.ai/tmp/phase5_batch_f_logs_20261112/pycache
```

约束：

- 不向 `C:` 盘写测试工具、中间产物、Godot user data 或日志；
- 测试 stdout/stderr 写入项目日志目录；
- 不把测试结果写入 `.ai/tmp/p168/official` 或历史 Evidence；
- 失败或超时保留 workspace/evidence 和所有日志。

---

## E. Snapshot Plan

### E.1 日志目录结构

建议执行时创建：

```text
.ai/tmp/phase5_batch_f_logs_20261112/
  pre_snapshot/
    runtime_inventory.jsonl
    runtime_summary.json
    protected_inventory.jsonl
    protected_sha256.txt
    test_sha256.txt
    git_status.txt
    git_baseline.txt
    processes.txt
    environment.txt
  post_snapshot/
    runtime_inventory.jsonl
    runtime_summary.json
    protected_inventory.jsonl
    protected_sha256.txt
    git_status.txt
    processes.txt
  diff/
    added.tsv
    removed.tsv
    modified.tsv
    unreadable.tsv
    expected_runtime_changes.md
    unexpected_changes.md
  stdout/
    01_test_composite_behavior_evidence.stdout.log
    01_test_composite_behavior_evidence.stderr.log
    02_test_slime_contact_arena.stdout.log
    02_test_slime_contact_arena.stderr.log
  stderr/
  execution_metadata/
    commands.tsv
    results.tsv
    test_manifest.txt
    run_01_pre_snapshot_sha256.txt
    run_01_post_snapshot_sha256.txt
    run_02_pre_snapshot_sha256.txt
    run_02_post_snapshot_sha256.txt
    final_snapshot_sha256.txt
```

日志目录本身不能位于以下被快照目录内部：

```text
.ai/tmp/behavior/
.ai/tmp/runtime-instance/
.ai/tmp/composite/
.ai/tmp/composite_protocol_cases/
.ai/tmp/composite_bad_contracts/
.ai/tmp/composite_invalid_contracts/
.ai/tmp/slime_bad_contracts/
```

日志目录可位于 `.ai/tmp/` 根下，但快照扫描必须显式排除自身，避免递归自引用。

### E.2 快照根

每个阶段至少完整递归扫描：

```text
.ai/tmp/behavior/
.ai/tmp/runtime-instance/
.ai/tmp/composite/
.ai/tmp/composite/workspaces/
.ai/tmp/composite_protocol_cases/
.ai/tmp/composite_bad_contracts/
.ai/tmp/composite_invalid_contracts/
.ai/tmp/slime_bad_contracts/
```

并记录 `.ai/tmp/` 根下的直接子目录，以发现新的测试目录、`behavior_tests_*` 或未预期 workspace。

### E.3 每条文件记录字段

每个条目记录：

| 字段 | 含义 |
|---|---|
| `relative_path` | 相对项目根或快照根的 POSIX 路径 |
| `type` | `file` / `dir` / `symlink` / `other` |
| `size` | 字节数；目录写 0 并单独标记 |
| `mtime_ns` | `st_mtime_ns` |
| `sha256` | 普通文件内容哈希；其他类型为空 |
| `symlink_target` | `os.readlink` 结果；非 symlink 为空 |
| `link_state` | `not_symlink` / `valid` / `broken` |
| `readable` | 是否成功读取 |
| `error` | 无法读取/哈希的原因 |
| `root` | 所属快照根 |

空目录必须单独记录，不能因无文件而消失；目录本身也保留类型和 mtime。

### E.4 执行前快照步骤

1. 确认日志目录不存在或为空；不覆盖 Batch B/D 日志。
2. 记录 HEAD、branch、staged、dirty、untracked 数量及完整 `git status --porcelain`。
3. 记录当前 Python/Godot 进程；发现测试进程则停止。
4. 记录 Godot 二进制、`.godot/global_script_class_cache.cfg` 和 Python 版本。
5. 计算 Batch F 两个测试文件 SHA256，并确认与预审计值一致。
6. 计算 Batch B 8 项、Batch D 1 项的测试 SHA256，确认未变化。
7. 计算受保护关键文件 SHA256。
8. 递归快照 E.2 的全部 Runtime 根；记录空目录和 symlink 状态。
9. 递归快照：
   - `Features/`
   - `Scenes/`
   - `.ai/context/`（排除未来新增的 Batch F 报告）
   - Protocol / Registry / Evidence / Attestation 文件
10. 保存 `pre_snapshot` 和 `git_status`，并再次确认没有 Batch F 进程运行。

### E.5 执行后快照步骤

1. 测试进程退出并确认无残留 Python/Godot。
2. 立即递归快照同一组根；不要清理任何 workspace/evidence。
3. 记录测试 stdout/stderr、退出码、耗时、PASS/FAIL 计数和 timeout 标志。
4. 分别对比两项测试的 pre/post，避免把第一项证据归因给第二项。
5. 对 Batch F 报告之外的新增/修改做分类。
6. 重新计算全部受保护文件和测试 SHA256。
7. 重新运行历史 Feature / Historical Evidence / Critical / Code / Protocol 哈希清单。
8. 对比 Git 工作区，确认原有 dirty 全部保留。

### E.6 差异分类

按 `relative_path` 建立三组集合：

- **added**：post 有、pre 无；
- **removed**：pre 有、post 无；
- **modified**：同一路径的 type、size、mtime_ns、sha256、symlink target 或 link_state 任一不同。

然后标记：

| 分类 | 处理 |
|---|---|
| `EXPECTED_RUNTIME` | `.ai/tmp/composite` 新 evidence、`workspaces` 新/删自有目录、固定 bad/protocol 夹具覆盖 |
| `EXPECTED_LOG` | 本次独立日志目录下的 stdout/stderr/metadata |
| `PROTECTED_OK` | 受保护文件哈希未变 |
| `UNEXPECTED` | 真实 `Features/`、`Scenes/`、`.ai/context/` 修改，或 B/D evidence 被改写 |
| `UNREADABLE` | 权限/占用/损坏；fail closed，保留现场 |
| `PRE_EXISTING_DIRTY` | 执行前已存在的 dirty，不得归因本次 |

`mtime_ns` 单独变化但内容相同的文件不能直接判为内容污染；应同时比较 SHA256。内容不同或路径新增/删除才是强信号。

### E.7 固定目录保护

执行前必须先检查：

```text
.ai/tmp/composite/workspaces/999-ffffffffff
```

若存在，停止，不执行 Batch F，等待负责人决定；该测试会创建、覆盖并删除同名目录。当前审计结果为 **不存在**。

固定目录的既有内容应在 `pre_snapshot` 中计算 SHA256；执行后允许被测试覆盖，但必须列出变化，不得把它们算作正式 Feature/Scene 污染。

### E.8 只读/不清理原则

- 不删除历史 workspace、Evidence、bad contracts 或 `behavior_tests_*`。
- 测试失败后保留现场；不自动重试。
- 快照失败（无法哈希）时停止，不跳过。
- 不使用 C 盘临时目录；不使用项目外镜像。
- 不在快照脚本中修改测试、源码、协议或 Git 状态。

---

## F. Protected State

### F.1 当前 Git 工作区

| 项目 | 当前值 |
|---|---|
| HEAD | `71f6eef61c1b203229e93a47a111f5ce040c587f` |
| branch | `master` |
| upstream | `origin/master` |
| staged | 0 |
| dirty | 1065 |
| untracked | 1000 |
| 测试进程 | 无 |

既有 dirty 包括用户本轮加入的 `AI_ENTRY.md` §0 规则修改、已生成的 Batch D 报告以及此前历史工作。Batch F 预审计没有修改它们。

本报告新增后，预计 dirty 为 **1066**，唯一新增项应为：

```text
?? .ai/context/PHASE_1_68_3_1_PHASE_5_BATCH_F_PRE_AUDIT.md
```

### F.2 受保护关键文件

| 文件 | 当前 SHA256 |
|---|---|
| `.ai/context/feature_index.json` | `1fdce0264e29c3dabcece0938da33e740be31f8c4d74b3bbe88527760f3b4fe4` |
| `.ai/context/feature_graph.json` | `b4ace8a9b069dfa01a112bc8d4c3af4b7c3f3393ae4642312698799b0de77d47` |
| `Features/FEATURE_SCHEMA.md` | `dca7c57accf7464ccd8f4919741a078c629cdbf661718440a8c5b31f01cb56fc` |
| `.ai/context/behavior_protocol.yaml` | `d2a480b068559124bb51d74782b6ec2d33c29135573f9a9f39aa491559eea778` |
| `.ai/tmp/p168/official/evidence/evidence_index.json` | `0e1f4ab03bab6442045eca3b56c88cf2ddc7116878428c52194196942e1ee910` |

### F.3 测试文件 SHA256

Batch F：

| 测试 | SHA256 |
|---|---|
| `test_composite_behavior_evidence.py` | `dc1a1ec1ba90d20d4314e6113c6288a0cf87fb62fc2f5d742eb44c2ee87bf004` |
| `test_slime_contact_arena.py` | `7cb3e03c8593b6fc50c06e7a5f0565263fe0d1f6ab4a34c3119c593090b0fb0a` |

Batch B：

| 测试 | SHA256 |
|---|---|
| `test_runtime_instance_evidence.py` | `24f83762b8db0d2331b3c7294f7772dc23d8c8492c80a577fbe7945453e0c872` |
| `test_behavior_time_driven.py` | `50e8ce5e5c840dfe936436677f406d48eba97812fc2a7878a1e50c97c2ce00a2` |
| `test_chase_movement_behavior.py` | `dce38d35f1108c956f19668178bed74e419ccc1c0933843f645e00b0d79bbea5` |
| `test_condition_gate_behavior.py` | `825eb48e0d57a528427b19dfc658ae72bbff6e6e06237adcb2e0a4facb37276b` |
| `test_contact_damage_behavior.py` | `e2cae467fb4a6f3e932448aef69f954db8cfe5f97054155ed29e45a2e9d53949` |
| `test_health_behavior.py` | `a11130ad01897be19806d69f1627afcef09b64f00297761df5e6a20144e1140b` |
| `test_health_bar_behavior.py` | `a56a70e2a34b3cbd15b6e18307f3674e81baa959894cede9d6b7a84b6e819a6e` |
| `test_stun_behavior.py` | `1aec4b01a9486633b5220118461c49c2cd279befb580f368ad0aeea2dc0cfc20` |

Batch D：

| 测试 | SHA256 |
|---|---|
| `test_feature_behavior_evidence.py` | `73d7c30518d2d417c9ad94c6188ff03e007084a7a9d51917696c3f850a1fc768` |

### F.4 保护范围

Batch F 执行前/执行后必须保护：

- `Features/`
- `Scenes/`
- `.ai/context/`
- `.ai/context/behavior_protocol.yaml`
- `.ai/context/composite_behavior_protocol.yaml`
- `.ai/context/composite_scenes/*.yaml`
- `.ai/context/feature_index.json`
- `.ai/context/feature_graph.json`
- `.ai/tmp/p168/official/evidence/evidence_index.json`
- Evidence Bundle / Manifest / Attestation / Review
- Batch B 8 个测试
- Batch D 1 个测试
- Batch F 2 个测试
- 所有既有 dirty / untracked 文件

### F.5 必须遵守的措施

1. 不执行 `git reset`、`git clean`、`git stash` 或批量 `git restore`。
2. 不清理任何历史 Runtime 产物。
3. 不修改生产代码、测试断言、Feature、Scene、Protocol、Evidence、Attestation 或索引。
4. 不提交或推送 Git。
5. 执行前先完成独立快照；快照失败则停止。
6. 执行前后重新计算受保护哈希；任何非预期变化立即停止。
7. 两个测试严格串行，前一项退出并确认无残留后再启动下一项。
8. 失败或超时保留现场，不自动重试、不自动修复。

---

## G. Execution Recommendation

### G.1 是否满足进入执行阶段

**满足进入执行阶段的前置审计条件，但仍需负责人单独授权。**

- Phase 3 §7 已提供完整权威名单：2 项；
- 顺序明确：composite → slime；
- 两项测试文件存在且哈希已记录；
- 依赖、共享状态、固定目录和 Runtime 副作用已识别；
- Batch B/D 已 PASS，且不属于 F 的重复执行；
- 当前无 Python/Godot 残留进程；
- 当前固定 fake workspace `999-ffffffffff` 不存在；
- 尚未执行任何 Batch F 测试。

### G.2 阻断项

**当前没有技术阻断项。**

需要负责人注意的文档层问题：

- 独立的 `PHASE_1_68_3_1_PHASE_5_REGRESSION_PLAN.md` 不存在；
- 本报告使用 Phase 3 §7 作为现有权威计划，没有自行创建替代文件；
- 如果负责人要求该独立文件必须存在，则执行状态应改为 **BLOCKED**，直到文件补齐或被明确豁免。

### G.3 需要负责人确认

1. 是否认可 Phase 3 §7 为 Batch F 的权威原始计划。
2. 是否授权按以下顺序执行：
   `test_composite_behavior_evidence.py` → `test_slime_contact_arena.py`。
3. 是否接受每个测试 300 秒外层预算，并使用测试内部现有 120/180 秒 workspace 预算。
4. 是否接受项目内 `APPDATA`/`TEMP`/`PYTHONPYCACHEPREFIX` 隔离方案。
5. 是否接受固定目录 `.ai/tmp/composite_protocol_cases`、`composite_bad_contracts`、`composite_invalid_contracts`、`slime_bad_contracts` 会被覆盖并保留。
6. 是否确认执行前若发现 `999-ffffffffff`，立即停止而不是清理。

### G.4 建议执行顺序和停止条件

建议顺序：

```text
P0  确认授权、HEAD、dirty、无残留进程、固定目录快照
  ↓
01  test_composite_behavior_evidence.py
  ↓
    无残留进程；pre/post 快照；受保护哈希；Git 状态
  ↓
02  test_slime_contact_arena.py
  ↓
    无残留进程；pre/post 快照；受保护哈希；Git 状态
  ↓
    生成 Batch F 执行报告；停止
```

停止条件：

- 任一项退出码非 0；
- 任一项超时；
- 出现 `SKIP:` 或无法判定；
- 受保护哈希变化；
- 出现非预期 `Features/`、`Scenes/`、`.ai/context/` 或 Evidence 变化；
- 出现未知 Runtime 文件竞争；
- 发现 `999-ffffffffff` 或其他固定路径预存冲突；
- 快照无法完整读取/哈希；
- Python/Godot 残留进程无法解释。

出现任一条件时：

1. 保留 stdout/stderr、pre/post 快照、workspace/evidence；
2. 停止后续测试；
3. 不自动重试；
4. 不清理现场；
5. 输出 FAIL / INCOMPLETE 或 BLOCKED 报告，等待负责人。

### G.5 最终状态

**READY_FOR_REVIEW**

这不是执行授权。Batch F 仍未执行；完成本报告后停止，等待负责人审查并单独授权。
