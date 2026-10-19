# Phase 1.34 — Unified Run Identity & E2E Concurrency Safety（审计报告）

> 状态：**已实施并验证（2026-10-19）**。范围 = L-9（E2E 串行互斥锁，覆盖共享产物
> 完整生命周期）、L-8（Python/GDScript 统一运行标识契约 + 旧格式受限识别）、
> L-10（`user://runtime-fixture-*` 记录保留，不清理）。F5 **未实施**；janitor CLI
> **未引入**；四条黄金基线未改；**未提交、未推送**。
> 基线：Phase 1.33 工作区；HEAD = `5e47bfd`（master），暂存区为空。

## 0. 范围与结论

| 项 | 状态 |
| --- | --- |
| L-9 E2E 并发互删风险 | **已解决**（串行互斥锁 + 完整生命周期覆盖 + 双真实进程竞争实测） |
| L-8 运行标识不统一 | **已解决**（canonical `<pid>-<16 hex>` 两侧统一；legacy 8-hex 受限识别、永不自动回收） |
| L-10 `user://runtime-fixture-*` | **保持保留**（只记录；按任务书 §五 不得伪造所有权，自动回收需单独授权） |
| F4-A / F4-B 现有行为 | **未破坏**（W1–W23 + L1–L8 = 36/36；cross-layer 66；e2e 173/173；6 GD 全 exit 0） |
| F5 / janitor CLI | **未实施**（未授权） |

## 1. 实施前保护记录

| 项 | 值 |
| --- | --- |
| HEAD | `5e47bfd`（master） |
| `git status --short` | 38 条（Phase 1.26–1.33 的全部未提交工作 + 本阶段新增）；暂存区 0 |
| 四条基线 | sha256/mtime 与 Phase 1.33 记录完全一致（§6） |

本阶段修改：`run_workspace.py`（token 契约）、`run_lock.py`（新增）、
`test_run_workspace.py`（W20–W23、L1–L8）、6 个 GDScript 测试（token 格式 + 冲突拒绝）、
`test_end_to_end_generation.py`（锁集成）、`CURRENT_TASK.md`、`WORK_STATE.md`、本文件。
未触碰：四个基线、`.workbuddy/memory/2026-10-18.md`、其他会话的既有修改。

## 2. L-9：E2E 并发安全（任务 A）

### 2.1 方案选择

| 方案 | 评估 | 结论 |
| --- | --- | --- |
| 每次运行独立产物 | `Scenes/<Pascal>.tscn` 是生产解析约定（check_gameplay.py / level_planner.py），迁出需改生产逻辑（未授权） | 不可行（1.33 已论证） |
| 完整生命周期互斥锁 | 锁必须覆盖创建→使用→签名清理的全过程；失败模式复杂（正常/失败/启动异常/进程死亡/陈旧锁） | **采用**（可证明：锁存在 = 互斥成立；锁获取/释放/回收都有确定性契约） |
| 串行入口保护（明确拒绝） | 最小改动；并发启动直接失败而非等待 | **作为锁的拒绝语义实现**（等待会延长总时长且掩盖问题；拒绝让冲突可见） |

**设计要点**：锁内容 = 持有者身份 JSON（`pid` / `holder_id`(uuid) / `host` / `scope` /
`created_at` / `schema_version`）；锁路径（`.ai/tmp/runs/e2e.lock`）即作用域——不同
base_dir / 工作目录互不影响。**文件内容签名相同不构成所有权证明**——互斥由锁的存在性
（O_EXCL）保证，与产物内容无关；两个运行不可能同时进入共享产物的任何生命周期阶段。

### 2.2 生命周期契约（`testsupport/run_lock.py`）

| 场景 | 行为 |
| --- | --- |
| 正常完成 | `finally` 中 release：锁内容与本运行 holder 记录（holder_id/pid/scope 三元组）完全一致才删除；不一致 = fail-closed 不删 |
| 测试失败 | 同上（finally 覆盖） |
| 启动过程异常 | 同上（acquire 后、try 前无失败路径；try 内异常经 finally 释放） |
| 持锁进程异常退出 | 锁残留（含 pid）→ 下一次运行读取时探测：**pid 已无任何进程**（Windows `OpenProcess` 失败于 `ERROR_INVALID_PARAMETER`；POSIX `kill(pid,0)` → `ProcessLookupError`）⇒ 持有者死亡可证 ⇒ 记录回收原因（"stale lock reclaimed: holder pid N no longer exists"）→ 重建锁并继续 |
| PID 复用 / 无法证明死亡 | `OpenProcess` 成功或 `GetExitCodeProcess` 不可判 ⇒ 按**存活**处理 ⇒ 拒绝（fail-closed） |
| 陈旧锁识别 | 内容非法 / 缺字段 / schema 不符 ⇒ 拒绝 + 人工恢复说明（"verify no e2e process is running, then remove <path> by hand"）——绝不仅凭"过期"删除 |
| 并发启动 | 明确**拒绝**（exit 2 + 持有者信息），不等待 |

威胁模型边界（不宣称已消除）：同权限攻击者伪造锁内容；`GetExitCodeProcess` 把"以
259 退出的进程"误判为存活（方向安全 = fail-closed）；锁获取与回收之间的竞争窗口由
`O_EXCL` 重试覆盖（回收后重建失败 = refused）。

### 2.3 验证（`test_run_workspace.py` L1–L8，全部真实执行）

| # | 场景 | 结果 |
| --- | --- | --- |
| L1 | 全新锁获取 + holder 记录写入 | PASS |
| L2 | 持有期间第二次获取 → 拒绝 + 持有者信息 | PASS |
| L3 | 持有者释放 → 锁消失 → 下一次获取成功 | PASS |
| L4 | 释放身份不匹配（伪造 holder）→ 拒绝释放、锁保留 | PASS |
| L5 | 持有者 pid 可证死亡 → 回收（原因入日志）→ 重建 | PASS |
| L6 | 锁内容非法 → 拒绝 + 人工恢复说明（fail-closed） | PASS |
| L7 | **两个真实子进程**：持有者存活期间竞争者被拒（stdout 含 serial-only）；持有者释放后（"released" in 输出） | PASS |
| L8 | 持有者退出后锁空闲 → 新获取成功 | PASS |

e2e 全量（含锁）真实运行：**173/173 PASS（exit 0）**，运行后 `e2e.lock` 不存在
（锁已释放）。

## 3. L-8：统一运行标识契约（任务 B）

### 3.1 契约

| 项 | 契约 |
| --- | --- |
| canonical 语法 | `^[0-9]+-[0-9a-f]{16}$`（`<pid>-<16 小写十六进制>`） |
| 创建方与唯一性 | Python：`uuid4().hex[:16]`；GDScript：`"%08x%08x" % [randi(), randi()]`（64-bit 随机）。运行根 `mkdir` 已存在 = 拒绝接管（Python `exist_ok=False`；GD `dir_exists` 检查 → 重试下一个候选） |
| 运行根命名 | `.ai/tmp/runs/<token>/`（两侧一致） |
| 账本关联 | Python 运行根含 `ownership.jsonl`；GDScript 运行根**无账本**（内容哈希自校验清理）→ 无账本的 canonical 目录 `stale_entries` 报 "no ledger"，`reclaim` 拒绝 |
| 状态与结束标记 | Python：账本 `removed` 事件 + 运行根删除；GD：运行根目录删除（自清理成功 = 结束） |
| 异常残留识别条件 | 格式匹配 + 位于 `runs/` 内 = **可识别**；格式匹配 + 合法账本 + 摘要一致 = **可证明所有权**；以上全部成立 = **可安全回收**。三者严格递进，不是同一条件 |

### 3.2 兼容性（不放宽 TOKEN_RE）

| 格式 | stale_entries | reclaim_abandoned |
| --- | --- | --- |
| canonical（16-hex） | 报告（含账本状态） | 账本完整且摘要一致才回收 |
| legacy（8-hex，Phase 1.32/1.33 旧格式） | 报告，state = "legacy token format (recognized, NOT reclaimable)" | **一律拒绝**（unsafe + 理由） |
| 畸形（其余） | 忽略（不是运行根） | 拒绝（unsafe） |

纠正 Phase 1.33 报告的一处表述：GD 侧实际生成的是 `pid-<8hex>`（usec+randi 混合）而非
十进制 `pid-<usec>`（1.33 §2.2/§5.2 L-8 的描述不准）；本阶段已统一为 16-hex，该笔误
不再影响现状。旧格式 8-hex 目录（如已存在的）按上表受限处理。

### 3.3 验证（W20–W23 + 6 个 GD 测试）

| # | 场景 | 结果 |
| --- | --- | --- |
| W20 | Python token 使用 canonical 格式 | PASS |
| W21 | legacy 运行根被识别且显式标记 NOT reclaimable | PASS |
| W22 | reclaim 拒绝 legacy 运行根（所有权不可证） | PASS |
| W23 | 畸形目录名被 stale_entries 忽略、被 reclaim 拒绝 | PASS |
| T-G1～G6 | 6 个 GD 测试以新 token 格式运行 | 全部 exit 0；`.ai/tmp/runs` 0 项；共享目录零残留 |

## 4. L-10：`user://runtime-fixture-*`（任务 C）

保持 Phase 1.33 结论：7 个目录（各 9–21K）为 Phase 1.6 Runtime Playtest 夹具的引擎
日志，**无运行清单、所有权不可证 → 保留**。本阶段未重命名、未补造清单、未改时间戳。
未来如需自动回收，须单独提出迁移方案与授权（PHASE_1_33 §9 L-10）。

## 5. 仍未验证的风险（延续 + 新增）

| 编号 | 风险 | 状态 |
| --- | --- | --- |
| L-3 | TOCTOU 残余窗口（检查—unlink 非原子；锁 acquire—reclaim 之间同理） | 保持开放；fail-closed 缓解，同权限攻击者不在威胁模型内 |
| L-4 | `.godot` 缓存共享可变状态（并发全量不安全） | 保持开放；串行仍是唯一被验证模式 |
| L-5 | 残留无法证明持有者死亡时永不自动回收（PID 复用） | 保持开放（设计意图） |
| L-6 | 账本/锁无签名（同权限伪造自洽） | 保持开放 |
| N-1 | e2e 双进程并发竞争**未用真实 e2e 全量跑**（锁原语以双真实子进程在临时目录验证 L7；完整 e2e×2 并发 ≈ 30 分钟且必然一方拒绝） | NOT_EXECUTED；锁拒绝路径已由 L2/L7 覆盖 |
| L-11 | F4-B 迁移使全量 turn 的真实删除计数增加（GD 运行根自清理），cross-layer 与 evidence 在全量中更早触发环境守卫 | 环境限制延续；缓解需下一阶段授权（运行根移出监视范围 / 排序调整） |
| N-2 | POSIX 侧 `_pid_alive` 未在非 Windows 实机验证 | NOT_EXECUTED（本机 Windows；代码含 POSIX 分支） |

## 6. 验证矩阵（原始命令、真实退出码、状态分类）

| # | 命令 | 退出码 | 结果 | 状态 |
| --- | --- | --- | --- | --- |
| T1 | `python .ai/tools/validator/tests/test_run_workspace.py` | 0 | **36/36 PASS**（W1–W23 + L1–L8） | PASS |
| T2 | `python .ai/tools/validator/tests/test_cross_layer_contract.py` | 0 | 66 PASS（新 token 格式下夹具/探针/清理不变） | PASS |
| T3 | `Godot -s res://Tests/test_orchestration_trace.gd` | 0 | PASS | PASS |
| T4 | `-s res://Tests/test_boss_orchestration.gd` | 0 | PASS | PASS |
| T5 | `-s res://Tests/test_generic_level_orchestration.gd` | 0 | PASS（本阶段曾因插入缩进错误 Parse Error → 修复后复跑通过） | PASS（修复后） |
| T6 | `-s res://Tests/test_level_orchestration.gd` | 0 | PASS | PASS |
| T7 | `-s res://Tests/test_holdout_trace.gd` | 0 | PASS | PASS |
| T8 | `-s res://Tests/test_waves_exit_gate.gd` | 0 | PASS | PASS |
| T9 | `python .ai/tools/e2e/tests/test_end_to_end_generation.py` | 0 | **173/173 PASS**（含锁获取/释放、O1/O2、T5a–d） | PASS |
| T10 | `python .ai/tools/validator/validate.py` | 0 | 0 error / 17 warning（与基线一致） | PASS |
| T11 | 四条基线 sha256/mtime 前后比对 | — | 完全一致（§6） | PASS |
| T12 | 双真实 e2e 进程并发 | — | 见 §5 N-1 | NOT_EXECUTED |
| T13 | POSIX `_pid_alive` 实机 | — | 见 §5 N-2 | NOT_EXECUTED |
| T14 | `user://runtime-fixture-*` 回收 | — | 拒绝（设计意图） | SKIP |
| T15 | F5 / janitor CLI | — | 未授权 | NOT_EXECUTED |
| T16 | `python .ai/tools/run_tests.py`（全量单命令） | 见报告附注 | 以 `/tmp/rt_p134.log` 为准 | 见附注 |

> 附注（全量最终结果，`python .ai/tools/run_tests.py` → exit 1）：
> **82 项中 80 PASS + 1 FAIL + 1 INCOMPLETE**。两个非 PASS 均为**环境删除守卫**
> （SAFE_DELETE_BULK_CONFIRM_REQUIRED，50 次/命令）在 turn 计数超限后终止进程：
> - `test_cross_layer_contract.py` = INCOMPLETE（守卫在 `.ai/tmp/runs/<token>/fixtures/`
>   清理阶段终止进程；其断言在到达清理前全部 PASS）；
> - `test_run_tests_evidence.py` = FAIL（其自建临时目录 `run_tests_evidence_*` 的
>   清理被守卫阻止；独立运行 **11/11 PASS、exit 0**）。
> 交互说明：F4-B 把 GD 测试产物迁入工作区内的运行根后，每次 GD 运行根自清理的真实
> 删除计入全量 turn 计数，使后段测试更早触线（1.32 全量 82/82 全绿时尚未如此）。
> 这是环境守卫限制的延续，不是本阶段行为回归——两个受影响测试独立运行均全过
> （T1/T2 分段证据）。缓解方向（下一阶段授权项）：GD 运行根移出守卫监视范围、
> 或守卫白名单，或测试排序调整。

## 7. 黄金基线保护

| 基线 | sha256（前 16 位） | mtime |
| --- | --- | --- |
| `multi_stage_boss.json` | `5736788cd9efd866` | 2026-10-17 22:19 |
| `single_stage_boss.json` | `d540cfe2226216e0` | 2026-10-17 22:19 |
| `waves.json` | `878691b1d174cbf0` | 2026-10-18 22:39 |
| `holdout.json` | `acf8bfbac8abf774` | 2026-10-18 23:55 |

实施前后两次采样一致；未重录、未修改事件、未改写 run_id。

## 8. 最终工作区与变更清单

| 项 | 值 |
| --- | --- |
| HEAD | `5e47bfd`（master）；未 commit、未 push |
| `git status --short` | 38 条（26 修改 + 12 未跟踪；含本阶段新增 `run_lock.py` 与本报告） |
| 暂存区 | 0 |
| `.ai/tmp/runs/` | 0 项运行根；`e2e.lock` 已释放 |
| 四条基线 | sha256/mtime 与实施前一致 |
| 未触碰 | 其他会话的既有未提交修改、`.workbuddy/memory/2026-10-18.md`、F5/janitor |

本阶段变更明细：
`testsupport/run_lock.py`（新增）；`testsupport/run_workspace.py`（token 契约 +
stale/reclaim 三分类）；`test_run_workspace.py`（+W20–W23、+L1–L8、imports）；
6 × `Tests/test_*.gd`（16-hex token + 冲突拒绝重试）；`test_end_to_end_generation.py`
（锁获取/释放集成 + testsupport 路径）；`CURRENT_TASK.md`、`WORK_STATE.md`、本报告。

## 9. 停止点

L-8、L-9 的完成标准逐项满足（§2.3/§3.3 + §5 未验证项明确标注）；L-10 保持保留。
F5、janitor CLI、`.godot` 缓存并发改造均未启动。本阶段到此停止，等待后续授权。
