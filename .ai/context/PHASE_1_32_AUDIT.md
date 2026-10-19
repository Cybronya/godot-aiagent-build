# Phase 1.32 — F4 Owned Cleanup Implementation（实现审计报告）

> 状态：**F4-A 已实施并验证（2026-10-19）**。范围 = 测试运行唯一标识、所有权账本、
> fail-closed 清理、异常残留检测/显式恢复；cross-layer 已迁入每次运行专属目录。
> F5 **未实施**；历史基线未改；未提交、未推送。
> 基线：Phase 1.31 工作区；HEAD = `5e47bfd`，branch = `master`，暂存区为空。

## 0. 范围与结论

| 项 | 状态 |
| --- | --- |
| 每次运行唯一 token + 专属运行根 | **已实施**（`testsupport/run_workspace.py`） |
| 所有权账本（`created` / `removed`，含 sha256/bytes/mtime_ns） | **已实施** |
| 清理前逐项验证（token / 路径 / 符号链接 / 摘要 / 元数据） | **已实施** |
| 所有权缺失 / 损坏 / 冲突默认拒绝删除 | **已实施**（W5–W9、W14） |
| 运行根仅在全部文件入账后递归删除 | **已实施**（W10） |
| 异常残留只报告 + 显式 reclaim 重新验证 | **已实施**（W11、§4 集成实测） |
| cross-layer 夹具/探针迁入运行根 | **已实施**（原 65 项检查不变） |
| `.ai/tmp/` 忽略规则（窄范围） | **已实施** |
| F4-B（e2e + 6 个 GDScript 测试 + `user://`） | **未实施**（未授权） |
| F5（过滤命中数 / 执行证据） | **未实施**（明确不授权） |

## 1. 实施前保护记录

| 项 | 值 |
| --- | --- |
| HEAD | `5e47bfde14d0c20f374994f4dac6479ac6c617c2`（master） |
| 实施前 `git status` | 27 条 = 20 修改 + 7 未跟踪；暂存区 0 |
| 本阶段计划修改 | `test_cross_layer_contract.py`、`run_tests.py`（仅 docstring 计数）、`CONTRACT_INDEX.yaml`、`.gitignore`、三处文档 |
| 本阶段新增 | `testsupport/`（`__init__.py` + `run_workspace.py`）、`test_run_workspace.py`、本文件 |

四个基线在实施前后逐项比对（§8）：sha256 与 mtime **完全一致**。

未执行任何破坏性 Git 操作；未触碰 `.workbuddy/memory/2026-10-18.md` 及 Phase 1.26–1.31
的既有未提交修改。

## 2. 资源所有权模型

### 2.1 运行身份与布局

```
.ai/tmp/runs/<pid>-<uuid8>/          # 运行根（mkdir exist_ok=False：已存在即拒绝接管）
    ownership.jsonl                  # 追加式账本，fsync 每条
    fixtures/<name>.json             # cross-layer 夹具（33 个）
    probe.gd                         # Godot 探针（-s res://... 直接执行）
    probe.gd.uid                     # 仅当 Godot 生成时登记（派生文件）
```

- token 由 `pid + uuid4[:8]` 组成，**不依赖时间戳**；每进程唯一。
- 运行根创建使用 `exist_ok=False`；账本用 `O_CREAT|O_EXCL` 创建 ⇒ 不接管任何已存在目录。
- `.ai/tmp/` 已加入 `.gitignore`（单行、仅该目录）：工作区为易失产物，不承载源码/测试/文档。

### 2.2 账本

```json
{"event":"created","token":"1234-ab12cd34","path":"fixtures/waves_v2_valid.json",
 "sha256":"…","bytes":532,"mtime_ns":1792411377750094400,"at":"2026-10-19T12:02:57+00:00"}
{"event":"removed","token":"1234-ab12cd34","path":"fixtures/waves_v2_valid.json","at":"…"}
```

- 路径为**相对运行根**的 posix 字符串（可移植；绝对路径一律视为越界）。
- `created` 在文件写入完成后登记；`removed` 在成功 unlink 后追加。
- 账本 token 必须等于运行根 token，否则整次清理拒绝（防跨运行账本混用）。

### 2.3 所有权不变量

| 编号 | 不变量 | 验证点 |
| --- | --- | --- |
| I1 | 只删账本中 `created` 的文件 | `cleanup()` 遍历 `_read_ledger()` |
| I2 | 路径必须位于本运行根内 | `is_within(normcase(abspath))`；绝对路径 / `..` 拒绝 |
| I3 | 不跟随符号链接 | `is_symlink()` 直接拒绝；运行根本身是符号链接也拒绝 |
| I4 | 内容与登记一致 | `st_size` + `st_mtime_ns` 预检 → sha256 → 删除前再次 `lstat` 比对 `(size, mtime_ns, ino)` |
| I5 | 账本必须完整可解析 | 缺文件 / 非法 JSON / token 不符 / 字段非法 ⇒ 整次清理不删任何东西 |
| I6 | 运行根只在全部文件入账后删除 | `os.walk` 发现未入账文件 ⇒ `unaccounted`，保留运行根与账本 |

## 3. 清理边界与算法

### 3.1 允许 / 禁止

| 允许 | 禁止 |
| --- | --- |
| 删除账本中、位于本运行根内的**文件** | 按 glob / 文件名前缀 / mtime 推断删除 |
| 删除整个运行根（仅当所有文件已验证入账） | 递归删除任何非运行根目录 |
| 报告其他 token 的运行根（只读） | 自动删除其他 token 的运行根 |
| `reclaim_abandoned()`：显式确认 + 逐文件重新验证后删除 | 将 `.ai/tmp/` 之外的文件纳入运行根 |

### 3.2 单文件清理顺序

```
账本解析 → token 校验 → 相对路径校验 → 运行根包含校验 → 符号链接拒绝
        → lstat(size/mtime) 与登记比对 → sha256 比对 → 再 lstat(ino/size/mtime) 比对
        → unlink → 追加 removed 事件
```

任一步失败：不删该文件、记录 `conflict` / `unsafe` / `incomplete` / `unaccounted`，
**并阻止运行根递归删除**（保留账本作为诊断证据）。

### 3.3 fail-closed 行为表

| 情况 | 行为 | 报告字段 |
| --- | --- | --- |
| 账本缺失 | 不删；保留运行根 | `ledger_error` |
| 账本非法 JSON / token 不符 / 字段非法 | 不删任何东西 | `ledger_error` |
| 文件大小或 mtime 变化 | 不删 | `conflicts` |
| sha256 变化 | 不删 | `conflicts` |
| 删除期间文件被替换（ino/size/mtime 变化） | 不删 | `conflicts` |
| 记录路径越界 / 绝对路径 / `..` | 不删 | `unsafe` |
| 记录路径是符号链接 | 不删、不跟随 | `unsafe` |
| 记录路径变成目录 | 不删 | `incomplete` |
| 其他未入账文件存在 | 不删运行根 | `unaccounted` |
| 文件已不存在 | 幂等跳过 | `missing` |

### 3.4 竞争风险（已知限制）

检查与 unlink 之间仍存在理论 TOCTOU 窗口：Python 在 Windows 上无法以目录句柄原子
`unlinkat`。缓解措施是「摘要 + 删除前再次 `lstat` 比对」；同一权限的攻击者仍可在窗口内
替换路径——这与 Phase 1.30 E-3 的威胁模型一致（同权限攻击者不在防线内），**不宣称**已消除。

## 4. 异常终止与恢复

- `stale_entries()`：列出运行基目录下**其他 token** 的目录（token 命名 + 账本状态 + 文件数 +
  最后一条账本事件），只读、不删除。
- cross-layer 启动时打印 `STALE (not removed): token=…`，**不影响本次测试结论**
  （外来残留不是本次运行的清理契约）。
- `reclaim_abandoned(run_root, acknowledge_abandoned=True)`：
  必须显式确认；重新验证目录名 = token、父目录 = `runs`、账本可解析、目录内每个文件都在
  账本中且摘要一致、无符号链接；任何一项不成立 ⇒ 拒绝并保留。
- 不自动回收：无法证明持有者已死亡（PID 可复用），自动删除会重新制造「删除他人正在使用
  的文件」的风险。

**集成实测（非强杀）**：在真实 `.ai/tmp/runs` 下由独立进程创建并登记一个运行根后不清理 →
cross-layer 运行输出 `STALE (not removed)`、该目录**仍存在**、cross-layer exit 0 →
随后 `reclaim_abandoned(..., True)` 返回 `run_root_removed=True, failures=[]`，
`.ai/tmp/runs` 剩余 0 项。全程未强杀任何真实测试进程。

## 5. 设计与实现差异（相对 PHASE_1_31_AUDIT.md）

| # | 1.31 设计 | 实际实现 | 原因 |
| --- | --- | --- | --- |
| 1 | 在 cross-layer 内新增 O1–O6 自检 | 独立测试文件 `test_run_workspace.py`（W1–W15）+ cross-layer 2 项清理断言 | 所有权逻辑需要大量故障注入（缺账本/篡改/越界/并发）；独立文件可在临时目录完整测试，且保持 cross-layer 65 项检查不变 |
| 2 | 账本含 `intent` → `created` → `removed` | 只有 `created` / `removed` | 「未入账文件阻止运行根删除」已使 `intent` 冗余；崩溃发生在写入后、登记前 ⇒ 文件成为 unaccounted ⇒ 不删（fail-closed），不会误删 |
| 3 | 删除前校验摘要 | 先比对 size/mtime，再算 sha256，删除前再次 `lstat` 比对 `(size, mtime_ns, ino)` | 避免对已被替换的大文件做无意义哈希；收窄检查—删除窗口 |
| 4 | 账本可记录绝对路径 | 只记录相对运行根的路径 | 可移植；绝对路径/`..` 直接判为越界 |
| 5 | 人工恢复流程（文档） | 增加 `reclaim_abandoned()` API（必须显式确认） | 让恢复可测试、可审计；仍不自动执行，也不提供 CLI |
| 6 | `pid + uuid4[:6]` | `pid + uuid4[:8]` | 降低极端碰撞概率，无兼容影响 |
| 7 | 运行根删除后目录树清空 | 保留共享父目录 `.ai/tmp/runs/` | 父目录不属于任何单次运行，删除它会制造跨运行竞争 |
| 8 | 仅登记自己写入的文件 | 额外 `record_if_exists("probe.gd.uid")` | Godot 可能为 `-s` 脚本生成 `.uid`；未登记会触发 unaccounted（实测本机未生成，仍防御） |
| 9 | cross-layer 夹具仍叫 `E2eContract__<name>.json` | 运行根内 `fixtures/<name>.json` | token 已由目录承载，文件名无需再拼前缀；Python 侧夹具查找改为后缀匹配 |
| 10 | 探针位于 `Tests/` | 运行根内 `probe.gd`（`res://.ai/tmp/runs/<token>/probe.gd`） | 隔离；Godot 4.7 实测 `-s` 可执行（Phase 1.31 P2 + 本阶段实跑） |

## 6. 测试矩阵与真实退出码

| # | 命令 / 场景 | 退出码 | 结果 | 证据 |
| --- | --- | --- | --- | --- |
| T1 | `python .ai/tools/validator/tests/test_run_workspace.py` | **0** | **19/19 PASS**（W1–W15，含 W9 符号链接真实执行、W12 两个真实子进程并发） | 终端输出 |
| T2 | `python .ai/tools/validator/tests/test_cross_layer_contract.py` | **0** | **66 行 PASS**（65 项检查 + 汇总）；`SKIP` 0；无 `Levels/` 或 `Tests/` 残留 | `/tmp/cross_layer_132.log` |
| T3 | 残留集成：独立进程留下运行根 → cross-layer | **0** | 打印 `STALE (not removed)`；残留仍在；随后显式 reclaim 删除成功；`.ai/tmp/runs` 余 0 | 终端输出 |
| T4 | `python .ai/tools/run_tests.py validator` | **0** | `completed=9/9 passed=9 failed=0 incomplete=0 unavailable=0 not_executed=0` | 终端输出 |
| T5 | `python .ai/tools/run_tests.py`（全量 82 项） | **0** | `completed=82/82 passed=82 failed=0 incomplete=0 unavailable=0 not_executed=0` | `/tmp/full_132.log` |

### 6.1 全量运行

`python .ai/tools/run_tests.py`（单命令，2026-10-19）→ **exit 0**：

```
[82/82] PASS .ai/tools/validator/tests/test_unified_validator.py
[run_tests] completed=82/82 passed=82 failed=0 incomplete=0 unavailable=0 not_executed=0
[run_tests] ALL PASS
```

其中 `[77/82] PASS test_cross_layer_contract.py`、`[80/82] PASS test_run_workspace.py`。
该次运行覆盖最终代码（运行期间未修改任何代码/测试；仅文档在运行期间写入）。

### 6.2 本阶段未执行（不冒充通过）

| 检查 | 状态 | 原因 |
| --- | --- | --- |
| 强杀真实仓库测试进程制造残留 | **NOT_EXECUTED** | 任务书 §三.4 / §八 禁止；改用 §4 的「独立进程自然退出但不清理」+ 隔离目录验证 |
| 两个真实 cross-layer 进程并发互删 | **NOT_EXECUTED** | cross-layer 会启动真实 Godot、耗时且属破坏性并发实验；隔离与互不删除由 W4/W12 在两个真实子进程 + 临时根中验证 |
| e2e / GDScript 固定名产物的隔离 | **NOT_EXECUTED（F4-B 未授权）** | 本阶段仅授权 cross-layer 范围 |
| Godot 不可用场景 | **UNAVAILABLE 不适用** | 本机 Godot 4.7 可用 |

## 7. 残留与工作区检查

| 检查 | 结果 |
| --- | --- |
| `.ai/tmp/runs/*`（每次测试后） | 0 项（共享父目录保留） |
| `Levels/E2eContract__*.json` | 不存在 |
| `Tests/e2e_level_contract_probe.gd` | 不存在 |
| `probe.gd.uid` 残留 | 不存在 |
| 隔离测试的临时 base | W15 断言已删除 |
| `git status` | 见 §10 最终记录 |

## 8. 基线保护

实施前后逐项一致（未重录、未迁移、未改写）：

| 基线 | sha256 | mtime |
| --- | --- | --- |
| `multi_stage_boss.json` | `5736788cd9efd8668b8958e3d7fdde83e4c8ce85a53d355c58763110f73e22b1` | 2026-10-17 22:19:01.472536400 |
| `single_stage_boss.json` | `d540cfe2226216e076810b4900a0a860057fb247523e3fde664e6e0c04339e15` | 2026-10-17 22:19:01.774880700 |
| `waves.json` | `878691b1d174cbf026a9723d112168f35bce5784b0ea928b11f06de9165506eb` | 2026-10-18 22:39:06.613330400 |
| `holdout.json` | `acf8bfbac8abf774365ac5c7b60565613db228834ddc3c9d998aedcc1d3f3836` | 2026-10-18 23:55:12.178038700 |

## 9. 兼容性影响

| 面 | 变化 | 影响 |
| --- | --- | --- |
| 测试发现数量 | Python 43 → 44；全量 81 → 82；validator 段 8 → 9 | `run_tests.py` docstring 已同步；历史文档中的 81 为历史记录，不追改 |
| 退出码 / 过滤语义 | **无变化** | F5 未实施；空匹配仍 exit 1 |
| cross-layer 断言 | 仍为 65 项检查（2 项清理断言替换旧 glob/探针断言） | 输出 66 行 PASS（含汇总） |
| cross-layer 产物路径 | `Levels/` + `Tests/` → `.ai/tmp/runs/<token>/` | 不再在仓库共享目录写固定名 |
| `run_tests.py` | **仅 docstring** | 无行为变化 |
| `CONTRACT_INDEX.yaml` | 新增 `test_runner.run_workspace` 契约块（附加） | 无消费者变更 |
| `.gitignore` | 新增 `.ai/tmp/`（仅此目录） | 已确认 `git ls-files .ai/tmp` 为 0；不隐藏源码/测试/文档 |
| 新增模块 | `.ai/tools/testsupport/`（不被测试发现器当作测试） | 仅 `**/tests/test_*.py` 被发现 |

## 10. 最终 Git 状态与未解决限制

### 10.1 最终记录

| 项 | 值 |
| --- | --- |
| `git status --porcelain` | **32 条 = 22 修改 + 10 未跟踪**（实施前 27 条；新增 3 个代码/测试文件 + 1 份报告，另 `test_cross_layer_contract.py`、`.gitignore` 进入修改集） |
| 暂存区 | 0 |
| 基线 sha256 / mtime | 与实施前完全一致（§8） |
| `.ai/tmp/runs` | 0 项（共享父目录保留、已被 `.gitignore` 覆盖） |
| `Levels/E2eContract__*` / `Tests/e2e_level_contract_probe.gd` | 不存在 |
| 未触碰 | `.workbuddy/memory/2026-10-18.md`、四个基线、e2e / GDScript 测试 |

### 10.2 未解决限制

| 编号 | 限制 | 说明 |
| --- | --- | --- |
| L-1 | F4-B 未实施 | e2e（约 28 个固定路径）与 6 个 GDScript 测试仍在共享目录写固定名；`user://` trace 强杀后仍不可见。需单独授权 |
| L-2 | 无 janitor CLI | `reclaim_abandoned` 只能由代码/人工显式调用；未提供 `--dry-run` 命令 |
| L-3 | TOCTOU 残余 | 检查与 unlink 非原子；同权限攻击者不在威胁模型内 |
| L-4 | 无跨进程锁 | 依赖 token 唯一 + 运行根独占；`.godot` 导入缓存仍是共享可变状态（并发全量仍可能互相干扰） |
| L-5 | 残留无法证明持有者死亡 | 因此永不自动回收；PID 复用无法排除 |
| L-6 | 账本无签名 | 同权限者可伪造自洽账本；与 Phase 1.30 E-3 一致，不作为本阶段缺陷 |
| L-7 | 只保护文件 | 运行根内的空目录随根删除；不单独删除目录 |

## 11. 停止点

F4-A（cross-layer + 所有权模块 + 隔离测试 + `.ai/tmp` 忽略）已完成并实测。
F4-B、F5 均未开始。等待后续授权；本阶段不做无关重构、不提交、不推送。
