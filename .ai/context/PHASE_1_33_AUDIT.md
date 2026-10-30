# Phase 1.33 — F4-B Integration & Resource Ownership（审计报告）

> 状态：**F4-B 已验证（2026-10-19）**。范围 = E2E 入口所有权、6 个 GDScript 测试迁移、
> `user://` 资源审计、`.godot` 缓存与 TOCTOU 风险评估（延续 Phase 1.32 §3.4/§10）。
> F5 **未实施**；janitor CLI **未引入**；历史基线未改；**未提交、未推送**。
> 基线：Phase 1.32 工作区；HEAD = `5e47bfd`（master），暂存区为空。
> 注：F4-B 代码由并行会话实施；本阶段完成的是**逐项验证、`user://` 与 `.godot` 审计、
> 文档同步与交付报告**（验证证据见 §6，代码非本会话编写处已注明）。
>
> **2026-10-20 复核补记见 §11**：在 Phase 1.34（HEAD=`1c30f94`）与未提交的
> Phase 1.35 之后的当前工作区上做了一次独立复核，修复了复核中发现的**一处所有权
> 记账缺陷**（§11.1），并更正了被后续阶段改写的 §2.2 / §5.2 / §9 事实（§11.2）。

## 0. 范围与结论

| 项 | 状态 |
| --- | --- |
| E2E 入口资源所有权 | **已实施 + 已验证**（清单 + 内容签名 + 本次运行缺席证明，O1/O2 断言；e2e 173/173 PASS） |
| 6 个 GDScript 测试迁入 `.ai/tmp/runs/<pid>-<usec>/` | **已实施 + 已验证**（6/6 exit 0，共享目录零残留） |
| `user://` 资源审计与隔离结论 | **已审计**（隔离已天然成立；不清理任何 `user://` 内容——所有权不可证的目录一律保留） |
| `.godot` 缓存风险评估 | **已评估**（延续 1.32 L-4；本阶段补充运行时写路径核实） |
| TOCTOU 评估 | **已评估**（延续 1.32 §3.4；e2e 清单方案补充了启动期签名证明，见 §5.1） |
| F4-A 现有行为 | **未破坏**（run_workspace W1–W19 全过；validator 段 9/9 PASS） |
| F5（过滤命中数 / 执行证据） | **未实施**（未授权） |
| janitor CLI | **未引入**（`reclaim_abandoned` 仍仅代码级显式调用） |

## 1. 实施前保护记录

| 项 | 值 |
| --- | --- |
| HEAD | `5e47bfd feat: golden trace baselines, …（Phases 1.19-1.25）`（master） |
| `git status --short` | 36 条 = 26 修改 + 10 未跟踪（即 Phase 1.26–1.32 的全部未提交工作）；暂存区 0 |
| 本阶段新增 | 本文件；`.workbuddy/memory/2026-10-19.md`（工作日志） |
| 本阶段修改 | `CURRENT_TASK.md`、`WORK_STATE.md`（F4-B 状态同步） |

四条黄金基线（实施前 → 验证后）逐项比对：sha256 与 mtime **完全一致**（§7）。
未执行任何破坏性 Git 操作；未清理任何"未知文件"。

## 2. 资源生命周期图（F4-B 范围）

### 2.1 E2E 入口（`.ai/tools/e2e/tests/test_end_to_end_generation.py`）

```
创建者：e2e 主进程（python）+ 其 Godot 子进程（探针）
资源（19 个固定名 + 6 个探针脚本 + 3 个 trace + 派生 .uid）：
    Scenes/E2eProbe*.tscn, E2eBoss*.tscn, E2eStageBoss*.tscn, StageGrunt/Boss.tscn
    Levels/E2eProbeLevel*.json, E2eBossLevel*.json, E2eStageBossLevel*.json
    Tests/e2e_*_probe.gd, Tests/test_e2e_probe_enemy.gd(+.uid), Tests/e2e_*_trace.json
所有者：本次 e2e 运行（由清单声明 + 内容签名证明）
清理者：finally 的所有权清理（O1/O2/Z1 断言）
异常终止后：下次运行的启动期扫描按签名识别 → 匹配则删除并报告；
            不匹配 = 无法证明归属 ⇒ 拒绝删除并使本次运行失败（fail-closed）
并发共享：同名固定路径 → 并发两个 e2e 会互相视为"签名匹配的残留"（已知限制，§5.3）
```

**为什么不能迁入 `.ai/tmp/runs/<token>/`**（代码注释已固化，PHASE_1_32 §10.1 L-1 的回答）：
实体场景的解析路径是**生产约定**——`check_gameplay.py:91-93` 与 `level_planner.py:153`
按 `Scenes/<PascalEntity>.tscn` 解析；宿主/关卡配置被组合计划（`--entity-scene` 映射）、
探针模板与断言按 `res://` 固定路径引用。迁出 `Scenes/`、`Levels/` 需要修改生产解析逻辑
（未授权，且会改变生成链契约）。因此采用「显式声明清单 + 启动期内容签名 + 本次运行缺席
证明」的**资源映射隔离**（任务书 §4.1 允许的替代方案）。

### 2.2 六个 GDScript 测试

| 测试 | 迁移前产物 | 迁移后产物位置 | 清理责任 |
| --- | --- | --- | --- |
| `test_orchestration_trace.gd` | `Levels/` 固定名配置 | `.ai/tmp/runs/<pid>-<usec>/` | 本运行自清理（内容未变才删） |
| `test_boss_orchestration.gd` | 同上 | 同上 | 同上 |
| `test_generic_level_orchestration.gd` | 同上 | 同上 | 同上 |
| `test_level_orchestration.gd` | 同上 | 同上 | 同上 |
| `test_holdout_trace.gd`（1.26–1.32 新增） | `Levels/` + `user://` | `.ai/tmp/runs/<pid>-<usec>/` | 同上 + 残留只报告不删除 |
| `test_waves_exit_gate.gd`（1.26–1.32 新增） | 同上 | 同上 | 同上 |

- 运行标识：`res://.ai/tmp/runs` 下以 `pid-<usec>` 命名的目录（GDScript 侧 `Time.get_ticks_usec()`；
  与 Python 侧 `pid-uuid8` 格式不同但语义一致：每运行唯一、独占目录）。
- 清理边界：只有「本运行写入且内容未变」的资源允许删除；
  `res://Levels` / `user://` 中前缀命中但不属于本运行的残留**只报告不删除**。
- 验证：6/6 exit 0；`.ai/tmp/runs/` 运行后 0 项；共享目录无 E2e* 残留（§6 T 组）。

### 2.3 `user://` 资源（实机审计 `%APPDATA%/Godot/app_userdata/`）

| 目录 | 大小 | 内容 | 所有权判定 | 处置 |
| --- | --- | --- | --- | --- |
| `game/` | 65K | `logs/godot.log`（引擎滚动日志）、`mcp_server.log`、`mcp_settings.cfg`、`mcp_tool_state.cfg` | **Godot 引擎 + godot_mcp 插件管理的基础设施**，非测试产物 | 不清理（引擎管理的缓存/日志） |
| `runtime-fixture-*`（7 个：broken-node-path / hangs / missing-resource / multiple-node-paths / parser-error / revert-case / script-error） | 各 9–21K | Phase 1.6 Runtime Playtest 夹具的引擎日志（每个夹具以独立 project name 运行 → 独立 user:// 子目录） | 属于 Phase 1.6 夹具运行；**无法证明属于本次运行** | 不删除（任务书 §4.3：无法证明所有权时拒绝删除） |
| `[unnamed project]/` | 0 | 空 | 无主 | 不删除（任务书 §4.3） |

生产代码中写 `user://` 的位置：仅 `addons/godot_mcp/`（config_manager.gd:37 配置、
mcp_server_core_legacy.gd:894 工具日志、mcp_runtime_probe.gd:401/1389 截图捕获）——
全部是插件基础设施，不属于测试资源。**测试侧已不再写 `user://`**（test_holdout_trace /
test_waves_exit_gate 迁移后仅写运行根）。

**隔离结论**：`user://` 的隔离已经天然成立——(a) runtime fixtures 按 project name
天然分目录；(b) GD 测试迁移后不再写共享 `user://`；(c) 引擎日志与 MCP 配置归引擎/插件
管理。本阶段**不清理任何 `user://` 内容**；若未来需要回收 `runtime-fixture-*`，应作为
Phase 1.6 夹具生命周期的独立决策（带显式清单），而非测试清理的一部分。

### 2.4 资源分类汇总

| 分类 | 资源 |
| --- | --- |
| 当前运行独占 | `.ai/tmp/runs/<token>/`（cross-layer / run_workspace）；GD 测试运行根；e2e 清单内产物（签名证明后） |
| 多个运行共享 | `Scenes/`、`Levels/`、`Tests/`（仅 e2e 清单内固定名产物；由签名机制仲裁）；`res://` 源码与场景（只读使用） |
| Godot 引擎管理的缓存 | `.godot/`（导入缓存、shader_cache）；`user://game/logs/` |
| 无法确认所有权的历史残留 | `user://runtime-fixture-*`（Phase 1.6 夹具目录）、`user://[unnamed project]/`（空）——**保留，不删除** |

## 3. 已实施迁移 / 未实施迁移与原因

### 3.1 已实施（本阶段验证）

| 范围 | 方案 | 验证证据 |
| --- | --- | --- |
| 6 个 GDScript 测试 | 运行根 `.ai/tmp/runs/<pid>-<usec>/` + 内容未变才删 + 外来残留只报告 | §6 T-G1～T-G6：6/6 exit 0；`.ai/tmp/runs` 0 项；共享目录零残留 |
| e2e 固定名产物 | 显式清单 + 启动期内容签名（匹配=上轮残留→删除；不匹配=拒绝删除并失败）+ 本次运行缺席证明 + O1/O2 清理断言 | §6 T-E1：e2e 173/173 PASS（含 O1/O2/Z1），退出码 0，共享目录零残留 |
| `user://` | 审计 + 拒绝清理（所有权不可证） | §2.3（实机目录枚举与写入者定位） |

### 3.2 未实施迁移及原因

| 项 | 原因 |
| --- | --- |
| e2e 产物迁入 `.ai/tmp/runs/<token>/` | 生产解析约定固定 `Scenes/<Pascal>.tscn` 与 `res://` 配置路径（§2.1）；强迁需修改 `check_gameplay.py` / `level_planner.py` 生产逻辑（未授权），且会改变生成链契约。已采用任务书允许的「资源映射隔离」替代 |
| `user://runtime-fixture-*` 回收 | 无法证明所有权（Phase 1.6 夹具、无运行清单）；任务书 §4.3 明确禁止 |
| `.godot` 清理/迁移/重建 | 见 §4；未证明安全前不动 |

## 4. `.godot` 缓存风险评估（单独审计）

**性质**：`.godot/` 是引擎管理的导入缓存（`imported/` 6,793 文件 / 7MB + shader_cache 50 文件
+ editor 元数据），不是普通临时目录——删除的后果是下次运行全量重导入（当前项目实测
约 26.5s），并可能丢失 editor 会话状态。

**并发行为**：
- 多个 Godot 进程以同一项目为 `--path` 并发运行（当前架构：run_tests 串行测试、
  e2e 沙箱内单 Godot、cross-layer 探针单 Godot——**串行是现状保证**）；
- 并发时的风险：导入缓存的部分写入（`.godot/imported/*` 非原子写）被另一进程读取
  → 偶发资源加载失败；这与 Phase 1.32 L-4 一致，本阶段**未做并发实验**（任务书 §5.3
  禁止修改共享缓存的不受控实验）→ `NOT_EXECUTED`；
- 沙箱已通过「不拷贝 `.godot` + 沙箱内 `--import` 重建」（Phase 1.25 性能优化）消除了
  捕获场景对主缓存的最主要写路径。

**结论与边界**：
1. `.godot` 不纳入任何测试清理范围（run_workspace 的运行根本就不含它；e2e 清单不含它）；
2. 并发全量运行仍然不安全（L-4 保持开放）——串行执行是当前唯一被验证的模式；
3. 若未来必须并发，最小方案是「每运行独立项目副本（复用 1.25 沙箱机制）+ 汇总结果」，
   留待后续授权。

## 5. 已知风险处理

### 5.1 TOCTOU（延续 Phase 1.32 §3.4）

- **run_workspace（cross-layer / 通用）**：检查（size/mtime → sha256 → 删除前再次
  `lstat(ino/size/mtime)`）与 `unlink` 之间仍存在理论窗口；Python/Windows 无法原子
  `unlinkat`。防御范围 = 误删内容已被改写的文件（fail-closed）；不防御同权限攻击者
  在窗口内替换路径（威胁模型外，**不宣称已消除**）。
- **e2e 清单方案（本阶段新评估）**：启动期「签名匹配才删残留」把 TOCTOU 窗口限定在
  「签名读取 → unlink」之间；且删除对象被清单 + 内容签名双重限定。与 run_workspace
  相同的威胁模型边界。新增保障：签名不匹配时**拒绝删除并失败**（fail-closed），
  把「上轮残留混入本轮断言」从静默错误变为显式失败。
- **GDScript 运行根（本阶段新评估）**：`pid-<usec>` 目录由本运行创建（独占）；
  清理仅针对本运行写入且内容未变的资源；窗口与上同。GDScript 无 sha256 基础设施，
  以「内容未变」（写后读取比对）作次级校验，弱于 Python 侧 sha256——记录为已知差异。

### 5.2 异常退出与残留回收

- **现状**（延续 1.32）：`stale_entries()` 只报告；`reclaim_abandoned` 显式确认 +
  逐文件重验；无 janitor CLI（未授权，不新增）。
- **e2e（本阶段新评估）**：异常退出后，固定名产物残留在共享目录；下一轮启动期扫描
  按签名识别并删除（自带恢复闭环，无需 janitor）——签名不匹配的残留会**阻塞后续运行**
  （fail-closed），需要人工判断（这是设计意图：无法证明归属就不动）。
- **GDScript 运行根**：异常退出后目录残留在 `.ai/tmp/runs/<pid>-<usec>/`；
  1.32 的 `detect_stale()/reclaim_abandoned()` 只识别 `pid-uuid8` 格式的 Python 侧
  token（`TOKEN_RE = ^[0-9]+-[0-9a-f]{8}$`），**不识别 GD 侧 `pid-<usec>` 目录**
  → 已知限制 L-8：GD 侧残留只能人工识别删除（无自动回收）。影响范围 = 仅
  `.ai/tmp/runs/` 内的测试产物目录，不影响仓库工作区。
- **重复清理 / 运行标识冲突**：GD 侧 `pid-<usec>` 理论上可能碰撞（同进程同微秒；
  实际不可能——两次写入间隔远大于 1µs）；Python 侧 token 冲突由 `exist_ok=False`
  拒绝。重复清理：所有清理路径均为幂等（文件已不存在 → 跳过并报告 missing）。

### 5.3 并发安全

- 已验证：run_workspace W12（两个真实子进程 + 独立临时根并发，互不干扰）——1.32 实测。
- 本阶段新验证：6 个 GD 测试顺序运行后 `.ai/tmp/runs/` 0 项（各自运行根自清理）；
  e2e 单运行 O1/O2（清单内产物全部删除、无本运行产物遗留）。
- `NOT_EXECUTED`：两个真实 e2e 进程并发（同名固定路径会互相视为"签名匹配的残留"
  → 并发不安全，**已作为已知限制写入 §5.1**；串行执行是当前契约）；修改共享
  `.godot` 缓存的并发实验。

## 6. 验证矩阵（原始命令、真实退出码、状态分类）

| # | 命令 / 场景 | 退出码 | 结果 | 状态 |
| --- | --- | --- | --- | --- |
| T-A1 | `python .ai/tools/validator/tests/test_run_workspace.py` | 0 | PASS（W1–W19，输出尾行 `PASS: run workspace ownership (W1-W19)`） | PASS |
| T-G1 | `Godot --headless -s res://Tests/test_orchestration_trace.gd` | 0 | PASS | PASS |
| T-G2 | `-s res://Tests/test_boss_orchestration.gd` | 0 | PASS | PASS |
| T-G3 | `-s res://Tests/test_generic_level_orchestration.gd` | 0 | PASS | PASS |
| T-G4 | `-s res://Tests/test_level_orchestration.gd` | 0 | PASS | PASS |
| T-G5 | `-s res://Tests/test_holdout_trace.gd` | 0 | PASS | PASS |
| T-G6 | `-s res://Tests/test_waves_exit_gate.gd` | 0 | PASS | PASS |
| T-G7 | T-G1～G6 后 `ls .ai/tmp/runs/` | — | 0 项（各运行根自清理） | PASS |
| T-G8 | T-G1～G6 后 `Levels/`、`Tests/` 残留扫描 | — | 仅已跟踪的测试文件本身，零 E2e* 产物 | PASS |
| T-E1 | `python .ai/tools/e2e/tests/test_end_to_end_generation.py` | 0 | **173/173 PASS**（含 O1/O2 所有权断言、T4 沙箱、T5a–d 基线比较、Z1）；共享目录零残留 | PASS |
| T-U1 | `user://` 目录枚举与写入者定位（grep `user://` + 实机目录遍历） | 0 | 见 §2.3；未删除任何内容 | PASS |
| T-V1 | `python .ai/tools/run_tests.py validator` | 0 | `completed=9/9 passed=9 failed=0`（F4-A 未破坏） | PASS |
| T-V2 | `python .ai/tools/validator/validate.py` | 0 | `0 error(s), 17 warning(s)`（与基线一致） | PASS |
| T-B1 | 四条基线 sha256/mtime 前后比对 | — | 完全一致（§7） | PASS |
| T-C1 | 两个真实 e2e 进程并发 | — | 并发会互删签名匹配的同名产物 → 已知限制（§5.3） | NOT_EXECUTED |
| T-C2 | 多 Godot 进程并发读写 `.godot` 缓存 | — | 见 §4（破坏性并发实验被禁止） | NOT_EXECUTED |
| T-U2 | `user://runtime-fixture-*` 回收 | — | 所有权不可证 → 拒绝（设计意图） | SKIP |
| T-J1 | janitor CLI 试点 | — | 未授权 | NOT_EXECUTED |
| T-F5 | 过滤命中数 / 执行证据（F5） | — | 未授权 | NOT_EXECUTED |

## 7. 黄金基线保护

实施前 → 验证后（本阶段两次采样，逐字节比对一致；未重录、未迁移、未改写 run_id）：

| 基线 | sha256（前 16 位） | mtime |
| --- | --- | --- |
| `multi_stage_boss.json` | `5736788cd9efd866` | 2026-10-17 22:19 |
| `single_stage_boss.json` | `d540cfe2226216e0` | 2026-10-17 22:19 |
| `waves.json` | `878691b1d174cbf0` | 2026-10-18 22:39 |
| `holdout.json` | `acf8bfbac8abf774` | 2026-10-18 23:55 |

## 8. 最终工作区与变更清单

| 项 | 值 |
| --- | --- |
| HEAD | `5e47bfd`（master）；未 commit、未 push |
| `git status --short` | 36 条修改 + 10 未跟踪（F4-B 代码由并行会话引入；本阶段仅新增本报告与工作日志、修改 CURRENT_TASK/WORK_STATE 的 F4-B 状态段落） |
| 暂存区 | 0 |
| `.ai/tmp/runs/` | 0 项 |
| 共享目录残留（E2e*/e2e_*probe/e2e_*trace） | 0 |
| `user://` | 未删除任何内容 |
| 四条基线 | sha256/mtime 与实施前一致 |

## 9. 未解决风险与下一阶段所需授权

| 编号 | 风险 / 限制 | 下一阶段所需授权 |
| --- | --- | --- |
| L-8 | GDScript 运行根 `pid-<usec>` 不被 Python 侧 `stale_entries()/reclaim_abandoned()` 识别（TOKEN_RE 不匹配） | 授权扩展 TOKEN_RE 或统一 token 格式（最小改动：GD 侧改用 uuid4 后缀，或 Python 侧新增 `^[0-9]+-[0-9]+$` 分支） |
| L-9 | 两个 e2e 并发会互删"签名匹配"的同名产物 | 授权 e2e 单实例互斥（如 runs/ 下锁文件）或文档化"e2e 禁止并发" |
| L-4 | `.godot` 导入缓存共享可变状态（并发全量不安全） | 授权"每运行独立项目副本"方案（复用 1.25 沙箱机制）的试点 |
| L-2 | 无 janitor CLI（残留回收仍需代码级显式调用） | 授权 `python -m testsupport.reclaim --dry-run` 形式的只读清单命令 |
| L-10 | `user://runtime-fixture-*`（7 个目录）无运行清单，只能人工处置 | 授权 Phase 1.6 夹具生命周期的专项清理决策（带显式清单） |
| — | F5（过滤命中数 / 执行证据） | 未授权，未实施 |

## 10. 停止点

F4-B（e2e 资源映射隔离 + 6 个 GDScript 测试运行根迁移 + `user://` 审计）已实施并逐项
验证；F4-A 行为未破坏；`.godot` 未被当作临时目录处理；四条黄金基线原样保留；
F5 与 janitor CLI 未实施。本阶段到此停止，等待下一阶段授权。

## 11. 复核补记（2026-10-20，本会话在当前工作区上的独立复核）

> 背景：Phase 1.33 的实现与首轮验证由并行会话完成（§0 已注明）。随后 Phase 1.34
> （统一运行标识 + e2e 串行锁）已提交（HEAD = `1c30f94`，Phases 1.26–1.34），
> 未提交的 Phase 1.35 继续把运行根迁入 Godot `user://` 侧。本节只做两件事：
> (a) 在**当前工作区**上重新验证 Phase 1.33 的范围（命令 / 真实退出码 / 状态分类）；
> (b) 修复复核中发现的一处所有权记账缺陷，并给出针对性测试。
> 本节不引入 janitor CLI、不实施 F5、不动 `.godot`。

### 11.1 复核发现的缺陷与最小修复（e2e 所有权记账）

- **现象**：工作区里存在上一次**被中断**的 e2e 运行残留（16 个清单内产物：
  `Scenes/E2e*.tscn`、`Levels/E2e*.json`、`Tests/test_e2e_probe_enemy.gd`）时，
  下一轮 e2e 的启动期扫描按内容签名**成功回收**了它们（`stale_removed=19`、
  `stale_refused=0`），但本轮结束清理却以「运行前就存在」为由**拒绝**删除本轮
  重建的同名产物（`refused=18`）→ O1 / Z1 失败 → e2e `exit=1`。
- **根因**：`test_end_to_end_generation.py::_ownership_scan_start()` 只把「扫描开始时
  就不存在」的路径写入可拥有集合（`absent`），**被扫描回收的残留没有重新登记**。
  于是「一次成功的残留回收」反而变成「下一轮的自我阻塞」——与本报告 §5.2 声称的
  「下一轮自动回收且不阻塞后续运行」不符。
- **最小修复**：`_ownership_scan_start()` 中，回收后确认路径已不存在的目标追加进
  可拥有集合。删除前仍重新校验内容签名、删除范围不变、外来文件仍然拒绝删除
  （fail-closed 语义不变）；只修记账，不放宽任何删除前提。
- **针对性测试**：新增 `.ai/tools/validator/tests/test_e2e_ownership.py`（E1–E4）——
  E1 扫描前不存在 ⇒ 可拥有 ⇒ 结束清理可删；E2 可验证残留被回收 ⇒ **重新登记**
  ⇒ 本轮重建的同名产物可删；E3 外来文件不删、不登记、结束清理仍拒绝（文件存活）；
  E4 可拥有产物在清理前被改写 ⇒ 拒绝删除。全部在系统临时目录内运行，只替换 e2e
  的「清单 / 签名判定 / 删除原语」三个接缝，不触碰仓库资源。

### 11.2 更正（被 Phase 1.34 / 1.35 改写的事实）

| 报告位置 | 原表述 | 当前事实（复核于当前工作区） | 依据 |
| --- | --- | --- | --- |
| §2.2 | GD 运行根 = `res://.ai/tmp/runs/<pid>-<usec>/` | `user://.test_runs/runs/<pid>-<16 hex>`（token 与 Python 侧 canonical 格式统一） | 6 个 `Tests/*.gd` 的 `_make_run_dir()`；`testsupport/run_workspace.py` 的 `TOKEN_RE` |
| §2.3 | `user://` 无测试写入 | GD 测试现在**写入** `user://.test_runs/runs/<token>/`（token 独占子目录，只删本运行自有文件）；引擎日志 / MCP 配置 / Phase 1.6 夹具目录仍不清理 | 同上；`%APPDATA%/Godot/app_userdata/game/.test_runs/runs/` |
| §5.2 L-8 | GD 运行根不被 Python 侧 stale 识别 | **已解决**：两侧 token 格式统一（`^[0-9]+-[0-9a-f]{16}$`），legacy 8-hex 只识别不回收 | W20–W23 |
| §5.3 L-9 | 两个 e2e 并发会互删同名产物 | **已解决**：`.ai/tmp/runs/e2e.lock`（`O_EXCL` 获取 + 持有者身份校验 + 可证死亡回收） | `testsupport/run_lock.py`；L1–L8 |
| §6 T-A1 | W1–W19 | 当前 **W1–W24 + L1–L8 = 37 项**（含 W4b/W9b/W11b/W11c 等分项） | `test_run_workspace.py` 实测输出 |

### 11.3 复核验证矩阵（当前工作区，2026-10-20）

| # | 命令 / 场景 | 退出码 | 结果 | 状态 |
| --- | --- | --- | --- | --- |
| R-A1 | `python .ai/tools/validator/tests/test_run_workspace.py` | 0 | 37 项全过（尾行 `PASS: run workspace ownership (W1-W24, L1-L8)`） | PASS |
| R-E1 | `python .ai/tools/e2e/tests/test_end_to_end_generation.py`（**修复后**，工作区存在 16 个中断残留） | 0 | **173/173 PASS**；`stale_removed=19 stale_refused=0 removed=18 refused=0`；O1/O2/Z1 全过；结束后工作区清单内产物 **0** | PASS |
| R-E2 | 同上（修复前，基线复现） | 1 | 18 个产物以「运行前就存在」被拒删 → O1/Z1 失败 | FAIL（已定位并修复，见 §11.1） |
| R-O1 | `python .ai/tools/validator/tests/test_e2e_ownership.py` | 0 | E1–E4 全过（针对性测试） | PASS |
| R-V1 | `python .ai/tools/run_tests.py validator` | 0 | `completed=10/10 passed=10 failed=0`（含 cross-layer、run_workspace、e2e 所有权 E1–E4） | PASS |
| R-F1 | `python .ai/tools/run_tests.py`（全量） | 0 | `completed=83/83 passed=83 failed=0 incomplete=0`（含 38 个 GDScript 测试、e2e 173/173、本新增 E1–E4） | PASS |
| R-B1 | 四条黄金基线 sha256/mtime 复核 | — | 与 Phase 1.31 记录逐项一致（§7） | PASS |
| R-C1 | 两个真实 e2e 进程并发 | — | Phase 1.34 已用串行锁解决（L-9） | SKIP（已由后续阶段关闭） |
| R-C2 | 多 Godot 进程并发读写 `.godot` | — | 禁止修改共享缓存的并发实验 | NOT_EXECUTED |
| R-U1 | `user://runtime-fixture-*` 回收 | — | 所有权不可证 → 拒绝 | SKIP |
| R-J1 | janitor CLI | — | 未授权 | NOT_EXECUTED |
| R-F5 | F5（过滤命中数 / 执行证据） | — | 未授权 | NOT_EXECUTED |

### 11.4 复核期间观察到的残留与恢复证据

复核开始时工作区同时存在三类残留（全部来自被中断的运行）：

| 残留 | 识别方式 | 处置 | 结果 |
| --- | --- | --- | --- |
| `.ai/tmp/runs/e2e.lock`（持有者 pid 7620 已死亡） | 锁内持有者身份 + 进程存活校验 | 可证死亡 ⇒ 回收 | PASS（后续 e2e 正常取得锁） |
| `.ai/tmp/runs/13776-ce1ab482e6d140ac/`（`ownership.jsonl` + `probe.gd`） | canonical token 目录 + 账本 | **只报告、不自动删**（fail-closed，保留可诊断证据） | 保留（需显式 reclaim 授权） |
| 16 个 e2e 清单内产物（`Scenes/E2e*.tscn` / `Levels/E2e*.json` / `Tests/test_e2e_probe_enemy.gd`） | 清单 + 内容签名 | 启动期签名验证后回收并重新登记 ⇒ 本轮结束时按所有权删除 | PASS（工作区归零） |

这三条正是本阶段要求区分的三类：**当前运行独占**（本轮重建的同名产物）、
**引擎/插件管理**（`user://` 日志与配置）、**所有权不可证的残留**（stale 运行根）——
最后一类一律保留，未做任何"顺手清理"。

### 11.5 最终验证与工作区快照（2026-10-20，末轮）

| # | 命令 | 退出码 | 结果 | 状态 |
| --- | --- | --- | --- | --- |
| R-A2 | `python .ai/tools/validator/tests/test_run_workspace.py` | 0 | 尾行 `PASS: run workspace ownership (W1-W24, L1-L8)` | PASS |
| R-V2 | `python .ai/tools/run_tests.py validator` | 0 | `completed=10/10 passed=10 failed=0` | PASS |
| R-F2 | `python .ai/tools/run_tests.py`（全量，最终工作区） | 0 | `completed=83/83 passed=83 failed=0 incomplete=0`，尾行 `ALL PASS`；日志 `.ai/tmp/full_regression_133_verify.log`（Godot 38 + Python 45） | PASS |
| R-B2 | 四条基线 sha256/mtime（全量回归后复核） | — | 与 §7 逐项一致（`BASELINES_UNCHANGED: True`） | PASS |
| R-R1 | 全量后 `Scenes/E2e*.tscn` / `Levels/E2e*.json` / `Tests/e2e_*probe.gd` / `Tests/e2e_*trace.json` 扫描 | — | **0 项** | PASS |
| R-R2 | `.ai/tmp/runs/` 枚举 | — | 仅 `13776-ce1ab482e6d140ac`（外来 stale，**保留不删**）；`e2e.lock` 不存在 | PASS |

最终工作区快照：

| 项 | 值 |
| --- | --- |
| HEAD | `1c30f94`（master）；**未 commit、未 push**，暂存区 0 |
| 已修改 | 19 个文件：`CURRENT_TASK.md`、`PHASE_1_33_AUDIT.md`、`WORK_STATE.md`、`CONTRACT_INDEX.yaml`、`validator/README.md`、`run_tests.py`、`testsupport/run_workspace.py`、`e2e/tests/test_end_to_end_generation.py`、`validator/tests/test_cross_layer_contract.py`、`validator/tests/test_run_tests_evidence.py`、`validator/tests/test_run_workspace.py`、`Orchestration/level_config.gd`、6 个 `Tests/*.gd`、`.workbuddy/memory/2026-10-19.md` |
| 未跟踪 | 1 个：`.ai/tools/validator/tests/test_e2e_ownership.py`（本阶段新增，尚未 `git add`） |
| `.godot/` | 未触碰（未清理、未迁移、未重建）；未做并发实验 |
| `user://` | 未删除任何内容（引擎日志 / MCP 配置 / Phase 1.6 夹具目录全部保留） |

文档同步（本会话，仅改真实变化的描述）：`.ai/tools/validator/README.md`（W 计数 → 37、
F4-B 段落改为当前 `user://.test_runs/runs/<token>/` 与 e2e 串行锁事实、新增 e2e 所有权测试
说明）、`.ai/context/CONTRACT_INDEX.yaml`（`run_workspace` 契约的 `test` / `owner_test` /
`consumer2` / `gdscript_roots`）、`.ai/tools/run_tests.py` 文档字符串（e2e 173 断言、
validator 10、Python 45 / 全量 83）。

**顺带观察（未修，记录为限制）**：`python .ai/tools/run_tests.py --help` 在 Windows GBK
控制台下抛 `UnicodeEncodeError`（文档字符串中的 `⇒`，HEAD 已存在，非本阶段引入）。
属工具可用性小缺陷，修复需改输出编码而非测试逻辑，留待后续授权。

### 11.6 本次复核未做的事

- 未清理 `.godot/`（引擎缓存，单独评估见 §4）；未做任何共享缓存并发实验。
- 未删除 `user://runtime-fixture-*`（所有权不可证，§2.3）。
- 未引入 janitor CLI、未实施 F5（未授权）。
- 未 commit、未 push、未重录基线、未改写历史 `run_id`。
