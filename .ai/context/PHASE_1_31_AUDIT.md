# Phase 1.31 — Execution Isolation & Safe Cleanup Design（只读审计 + 设计）

> 状态：**审计与设计完成（2026-10-19）**。本阶段**未实施 F4 / F5**，未修改任何生产代码或测试代码，
> 仅新增本文件并更新 `CURRENT_TASK.md` / `WORK_STATE.md` / `validator/README.md` 的阶段性记录。
> 后续：F4-A（cross-layer + 所有权模块）已在 **Phase 1.32** 实施，见 `PHASE_1_32_AUDIT.md`；
> 本文件保留 1.31 时点的现状与设计，不再回写实现细节。
> 基线：Phase 1.30 工作区（未提交）。HEAD = `5e47bfd`，branch = `master`，暂存区为空。
> 未重录基线、未强杀任何真实测试进程、未删除任何无法证明所有权的文件。

## 0. 结论摘要

| 编号 | 结论 | 证据等级 |
| --- | --- | --- |
| F4-1 | cross-layer 的清理**按 glob 前缀删除**，会删掉不属于本次运行的文件；默认行为是「删除」而不是「拒绝」 | **已实测**（§2.4 P1，临时目录模拟，仓库零写入） |
| F4-2 | cross-layer / e2e / 6 个 GDScript 测试都用**固定文件名**写进 `Levels/`、`Tests/`、`Scenes/`、`user://`，没有任何 run token 或所有权记录 | **代码证据**（§2.1） |
| F4-3 | 并发互删、残留断言误报、强杀残留均为**静态推导**（未并发执行、未强杀，遵守 §八 禁止事项） | 静态推导（§2.3） |
| F4-4 | Tier-1 隔离布局 `res://.ai/tmp/runs/<token>/` **在真实 Godot 4.7 上可行**：`-s` 可执行该目录下的脚本，`LevelConfig.from_file` 可读同目录夹具，无 `.uid` 副作用，清理后 git 状态不变 | **已实测**（§2.4 P2） |
| F5-1 | 过滤串**不出现在任何输出或证据中**；`total` 是过滤后的数量，发现总数被丢弃 | **已实测**（§4.1，真实命令） |
| F5-2 | 过滤后只跑 1 个测试仍打印 `ALL PASS` 与 `completed=1/1`，日志无法自证「这是子集」 | **已实测**（§4.1 F5-2） |
| F5-3 | 空匹配返回 1（正确）；但 `run_tests.py` 自身被中断时**没有摘要、没有状态文件**，执行完整性只能靠退出码/日志缺失推断 | 代码证据 + 推导（§4.2） |
| 基线 | 四个黄金基线的 sha256 与 mtime 在审计开始/结束**完全一致** | **已实测**（§8） |

**未做**：F4/F5 的任何实现；并发复现；强杀复现；历史基线重录；退出码变更。

## 1. 当前工作区保护清单（审计时实测）

| 项 | 值 |
| --- | --- |
| HEAD | `5e47bfde14d0c20f374994f4dac6479ac6c617c2`（master） |
| 暂存区 | 空（`git diff --cached --name-only` → 0 行） |
| 工作区变更总量 | 26 条 = 20 修改 + 6 未跟踪 |

20 个已修改文件（均为 Phase 1.26–1.30 的既有未提交增量，本阶段**未触碰**）：

```
.ai/context/CONTRACT_INDEX.yaml                  .ai/tools/validator/tests/test_orchestration_trace.py
.ai/context/CURRENT_TASK.md                      .ai/tools/validator/tests/test_trace_baselines.py
.ai/context/WORK_STATE.md                        .ai/tools/validator/trace_baselines.py
.ai/context/level_schema.yaml                    .ai/tools/validator/trace_replay.py
.ai/context/orchestration_trace_schema.yaml      .workbuddy/memory/2026-10-18.md
.ai/tools/e2e/README.md                          Orchestration/level_orchestrator.gd
.ai/tools/e2e/approve_trace_baselines.py         .ai/tools/validator/baselines/holdout.json
.ai/tools/e2e/holdout_trace_probe.py             .ai/tools/validator/baselines/waves.json
.ai/tools/e2e/tests/test_end_to_end_generation.py
.ai/tools/e2e/trace_baseline_capture.py
.ai/tools/run_tests.py
.ai/tools/validator/README.md
```

6 个未跟踪文件：

```
.ai/context/PHASE_1_30_AUDIT.md                  Tests/test_holdout_trace.gd
.ai/tools/validator/tests/test_run_tests_evidence.py   Tests/test_holdout_trace.gd.uid
                                                 Tests/test_waves_exit_gate.gd
                                                 Tests/test_waves_exit_gate.gd.uid
```

> 其中 `holdout.json` / `waves.json` 相对 HEAD 的差异是 Phase 1.27–1.28 的既有改动；
> 本阶段**没有写入**这两个文件（mtime 仍为 2026-10-18）。

四个黄金基线（审计开始 = 结束，见 §8）：

| 基线 | sha256 | mtime |
| --- | --- | --- |
| `multi_stage_boss.json` | `5736788c…f73e22b1` | 2026-10-17 22:19:01 |
| `single_stage_boss.json` | `d540cfe2…04339e15` | 2026-10-17 22:19:01 |
| `waves.json` | `878691b1…165506eb` | 2026-10-18 22:39:06 |
| `holdout.json` | `acf8bfba…1d3f3836` | 2026-10-18 23:55:12 |

禁止事项执行情况：未执行 `git reset` / `checkout` / `clean`；未提交、未推送；未修改
`.workbuddy/`（用户自有 agent 工作区）；未关闭任何清理守卫。

## 2. F4 现状：唯一令牌与所有权清理

### 2.1 谁在什么时候创建了什么、由谁清理

| 创建者 | 工作区 / 用户目录产物 | 命名 | 清理者 | 启动期残留处理 |
| --- | --- | --- | --- | --- |
| `validator/tests/test_cross_layer_contract.py` | 33 个 `Levels/E2eContract__<fixture>.json` + `Tests/e2e_level_contract_probe.gd` | **固定名**（`res_path` 行 292，`PROBE_REL` 行 62） | `finally`（行 327）+ `cleanup()`（行 439–452，glob 前缀） | **无** |
| `e2e/tests/test_end_to_end_generation.py` | 约 28 个固定路径（19 个模块级常量 + 9 个函数内路径）：`Scenes/E2eProbe*.tscn`、`Scenes/Stage*.tscn`、`Scenes/E2eBoss*.tscn`、`Levels/E2e*Level*.json`、`Tests/e2e_*_probe.gd`、`Tests/e2e_*_trace.json`、`Tests/test_e2e_probe_enemy.gd`（常量行 209–234） | **固定名** | `finally` 按 `*_written` 标志（行 1940–2055）+ `Z1` 断言 | 有，但**按固定清单全删**（行 401–412），不区分归属 |
| `Tests/test_generic_level_orchestration.gd` | 13 个 `Levels/E2eGeneric*.json` | 固定名（行 41–54） | `_cleanup()`（行 898，脚本末尾调用行 82） | 无 |
| `Tests/test_level_orchestration.gd` | 3 个 `Levels/E2eLevel*.json` | 固定名（行 26–28） | `_cleanup()`（行 339） | 无 |
| `Tests/test_boss_orchestration.gd` | `Levels/E2eBossLifecycleTest.json` | 固定名（行 27） | `_remove_temp()`（行 764） | 无 |
| `Tests/test_orchestration_trace.gd` | `Levels/E2eOrchestrationTraceTest.json`、`Tests/e2e_trace_export_test.json` | 固定名（行 22–23） | `_remove_temp()`（行 607） | 无 |
| `Tests/test_holdout_trace.gd` | `Levels/E2eHoldoutTraceTest.json`、`user://e2e_holdout_trace_probe.json` | 固定名（行 25–26） | `_cleanup()`（行 301）+ `H7` 残留断言 | 无 |
| `Tests/test_waves_exit_gate.gd` | `Levels/E2eWavesExitGateTest.json`、`user://e2e_waves_exit_gate_trace.json` | 固定名（行 24–25） | `_cleanup()`（行 390）+ `G6` 断言 | 无 |
| `runtime/tests/test_asset_self_repair.py` | `Scenes/_AssetRepairBroken.tscn` | 固定名 | `finally` unlink | 有（`assert not exists`，fail-closed） |
| 多数 Python 单测 | `tempfile.mkdtemp(...)` | **唯一名**（系统临时目录；`test_run_tests_evidence.py` 例外，在项目根） | `shutil.rmtree(..., ignore_errors=True)` | 无（唯一名，残留只占空间） |
| `e2e/*_probe.py`、`trace_baseline_capture.py` | `%TEMP%` 沙箱项目副本 + 探针脚本 + trace | 唯一名前缀 | 读回后自删（脚本 / trace / `.uid`） | 沙箱目录 `rmtree` |

关键事实：

1. **没有任何 run token**。全仓库产物名都不含 pid / uuid / 时间戳；唯一例外是
   `tempfile.mkdtemp()` 生成的系统临时目录（唯一，但生命周期只在单进程内）。
2. **没有任何所有权记录**。没有 `(path, digest, owner)` 清单，也没有落盘的 ledger。
3. cross-layer 的 `cleanup()` 是**前缀匹配**：`(PROJECT_ROOT / "Levels").glob("E2eContract__*.json")`（行 440）。
4. e2e 的启动期清理同样按**固定名字**删除，因此也会删掉「另一次并发运行」的产物（行 401–412）。
5. `user://` trace（holdout / waves gate）不在仓库内，强杀后**不会出现在 `git status`**，
   只能靠人工去 Godot 用户目录检查——这类残留目前完全不可见。

### 2.2 四种资源的区分能力（现状）

| 需要区分 | 现状判定手段 | 结论 |
| --- | --- | --- |
| 当前运行创建的资源 | 仅部分：e2e 的 `*_written` 布尔标志（进程内） | **cross-layer 完全不能区分**（无标志、无清单，只靠名字） |
| 其他并发运行创建的资源 | 无 | **不能区分**；名字相同 ⇒ 互相覆盖 |
| 历史残留 | 无 | **不能区分**；e2e 启动期直接按名单删除 |
| 不属于测试系统的用户资源 | 无 | **不能区分**；只要叫 `E2eContract__*.json` 就会被删 |

「所有权无法证明时的默认行为」= **删除**（cross-layer `cleanup()`、e2e 启动期清理）。
这与 §三.2「不得删除无法证明由当前运行创建的资源」直接冲突，是 F4 的核心风险。

### 2.3 并发 / 重复 / 异常退出 / 强杀 / 清理重试的行为推演

| 场景 | 现状行为（代码推导） | 后果 | 等级 |
| --- | --- | --- | --- |
| 两个 run 同时写 fixture | 33 个固定名被后者覆盖；两者内容相同（同一 fixture 表），暂时「看起来正常」 | 一旦两次运行的 fixture 版本不同（代码更新中途启动），后者读到前者的文件 ⇒ 语义错配 | 中 |
| A 结束清理时 B 仍在用 | `cleanup()` 删除**全部** `E2eContract__*.json`（含 B 的）；B 的 Godot 探针随后读到「无法读取关卡配置文件」（`level_config.gd:89-92`）⇒ `accepted=0` 与 Python 判定不一致 | **B 假失败**（FAIL，不是 SKIP） | 高（并发下） |
| A 的残留断言遇到 B 的文件 | 行 420 的 `residue` 对**所有** `E2eContract__*.json` 取 glob | **A 假失败**：`cleanup: contract fixtures removed` 断言不通过，即使 A 自己已清干净 | 高（并发下） |
| 测试进程被强杀（SIGKILL / 超时） | `finally` 不执行；GDScript 的 `_cleanup()` 在脚本末尾（例如 `test_generic…gd:82`），被中断则完全不执行 | 33 个 fixture + 探针脚本 + e2e 的 ~28 个固定产物留在仓库；`user://` trace 留在用户目录 | 中（可见性差） |
| 清理过程被强杀 | 部分文件已删、部分未删；无 ledger 可判断「哪些是本运行的」 | 下一次运行覆盖同名文件；`Levels/` 残留可能混入 `git status` | 中 |
| 清理重试 | cross-layer 对探针 `.gd` 有 5 次重试（Windows 句柄），失败即 FAIL；`cleanup()` 的 `except OSError: pass` **静默吞掉**失败 | 二次清理（`finally` 后的 `cleanup()`）掩盖真实清理失败，证据不可信 | 低–中 |
| 用户手工创建同名文件 | 被 glob 删除 | **越权删除用户数据** | 中（需显式授权才可接受） |

> 以上除「用户同名文件被删」外均为**静态推导**：本阶段没有并发运行、没有强杀真实进程
> （§八 明令禁止），只在 §2.4 用临时目录模拟了 glob 清理语义。

### 2.4 本阶段实际执行的两个非破坏性探针

**P1（所有权语义，临时目录模拟，仓库零写入）**

```python
# 仅把 cleanup() 的目标根指向临时目录；写入 own / foreign / unrelated 三个文件
m.PROJECT_ROOT = tmp_root
m.cleanup()
```

真实输出（`exit=0`）：

```
before: ['E2eContract__runA__waves_v2_valid.json', 'E2eContract__runB__holdout_v2_valid.json', 'KeepMe.json'] probe_exists= True
after : ['KeepMe.json'] probe_exists= False
foreign_removed= True
own_removed= True
unrelated_removed= False
```

结论（**已实测**）：清理器**不区分 own / foreign**，只按 `E2eContract__` 前缀删除；
非匹配名字保留。即：一旦有第二个运行或用户文件使用该前缀，就会被本次运行删除。

**P2（Tier-1 隔离布局可行性，真实 Godot 4.7）**

在 `res://.ai/tmp/p131_<uuid>/` 下写 `probe.gd` + `fixture.json`，
`godot --headless --path . -s res://.ai/tmp/p131_<uuid>/probe.gd`：

```
exit= 0
PROBE line: ['PROBE131: valid=1 errors=[]']
created: ['fixture.json', 'probe.gd']      # 未生成 .uid
dir_removed= True
tmp_parent_empty= True
git status 条数 = 26（不变），无 p131 残留
```

结论（**已实测**）：`-s` 可执行 `Tests/` 之外的 `res://` 脚本；`LevelConfig.from_file`
可读同目录夹具；该布局不会触发 `.uid` 生成。**Tier-1 方案在本机 Godot
4.7.stable.official.5b4e0cb0f 上可行**（跨平台/跨版本仍需在实施阶段复验）。

## 3. F4 候选设计（待授权，未实施）

### 3.1 运行身份与目录布局

**token**：`f"{os.getpid()}-{uuid.uuid4().hex[:8]}"`（一次进程一个，进程内所有产物共用）。
不得只用时间戳或 pid（pid 可复用）；token 必须是小写字母/数字/连字符。

**Tier 1（默认，首选）**：所有生成物放进运行专属目录：

```
.ai/tmp/runs/<token>/
    ownership.jsonl          # 追加式所有权账本（本运行）
    fixtures/<name>.json     # 替代 Levels/E2eContract__<name>.json
    probe.gd                 # 替代 Tests/e2e_level_contract_probe.gd
    ...
```

- 用 `Path.mkdir(parents=False, exist_ok=False)` 创建运行根；**已存在即中止**并给出诊断
  （不「接管」别人的目录，避免把别人的内容误判为自己的）。
- Godot 侧路径 `res://.ai/tmp/runs/<token>/...`（P2 已验证 `-s` 可用）。
- `.gitignore` 需新增 `.ai/tmp/`（当前**未忽略**，`git check-ignore` 实测 "NOT ignored"）。
  否则残留会污染 `git status`；加上忽略后残留仍可通过目录本身显式检查，不会消失。

**Tier 2（后备）**：对必须留在既有目录的产物（GDScript 测试的 `res://Levels/*.json`、
`user://` trace），改用**含 token 的文件名**：`Levels/E2eGeneric__<token>__waves.json`、
`user://e2e_holdout_trace__<token>.json`。仍是固定目录，但名字唯一 ⇒ 并发互不可见。

> 选择顺序：能用 Tier 1 的（cross-layer、e2e 的 Python 侧生成物）一律 Tier 1；
> GDScript 测试里硬编码 `res://Levels` 的路径改造成本高，先 Tier 2。

### 3.2 所有权账本

追加式 JSONL，每条一行，`fsync` 后再继续（崩溃安全；半行可丢弃）：

```json
{"event":"intent","token":"1234-ab12cd34","path":".ai/tmp/runs/1234-ab12cd34/fixtures/a.json","kind":"file","at":"..."}
{"event":"created","token":"1234-ab12cd34","path":"...","sha256":"...","bytes":512,"at":"..."}
{"event":"removed","token":"1234-ab12cd34","path":"...","at":"..."}
```

规则：

1. 只有账本里出现 `created` 的路径才允许删除；`intent` 无 `created` ⇒ 视为「未创建」，不删。
2. 删除前重算 `sha256`，必须等于 `created.sha256`；否则**跳过并报告冲突**（内容已被他人改写）。
3. 运行根的删除是唯一的递归操作：仅当路径 == 本运行根、且其下所有文件都能在账本中找到
   （或已被本次删除）时才 `rmtree`。
4. 账本本身不删除（保留到运行根被删除为止），用于事后审计。

### 3.3 清理算法（实现规格）

```
def cleanup(token, run_root, ledger, allowlist):
    # 1) 逐条删除账本中的 file
    for rec in ledger.created_files():
        p = normalize(resolve(rec.path))
        if not p.exists():                       continue          # 幂等
        if not is_within(p, run_root) and p not in allowlist:      report("foreign"); continue
        if is_symlink_or_reparse(p):                               report("symlink"); continue
        if sha256(p) != rec.sha256:                                report("content_changed"); continue
        unlink(p); ledger.removed(p)

    # 2) 删除运行根（唯一允许的递归删除）
    if run_root.exists():
        if not is_run_root(run_root, token):     report("not_run_root"); return
        if not all_files_accounted(run_root, ledger): report("unaccounted"); return
        rmtree(run_root)

    # 3) 自身产物未能删除 ⇒ FAIL；外来残留 ⇒ 只报告
```

约束：

- **禁止 glob / 前缀 / mtime / 通配符**作为删除依据（P1 正是当前实现的反例）。
- 路径必须 `resolve()` 后仍位于 `run_root`（Tier 1）或命中**显式白名单**（Tier 2 的文件名精确匹配）。
- Windows：大小写不敏感比较；拒绝 `..`；拒绝盘符根 / 项目根 / `Levels` / `Tests` / `Scenes` 本身。
- 符号链接 / reparse point：不跟随、不删除。
- 只删文件；目录只删「本运行根」。

### 3.4 所有权缺失 / 损坏 / 不匹配时的默认行为（fail-closed）

| 情况 | 行为 | 测试结果影响 |
| --- | --- | --- |
| 账本缺失 / 不可读 | 不删除任何东西；报告 `ledger_missing` | 若本运行确实创建过产物 ⇒ **FAIL**（无法证明清理完整性） |
| 记录缺 `sha256` | 跳过该条；报告 `record_incomplete` | 该条视为未清理 ⇒ FAIL |
| token 不匹配（他运行目录） | 不删除、不进入；只列清单 | 不影响本次结果（外来残留） |
| 内容摘要不匹配 | 跳过；报告 `content_changed`（可能被并发运行/用户改写） | FAIL（本运行产物未按预期清理） |
| 路径越界 / 符号链接 | 拒绝；报告 `unsafe_path` | FAIL（实现缺陷，必须暴露） |
| 文件已不存在 | 幂等跳过 | 不影响 |

### 3.5 强杀后的残留识别与人工恢复

- 启动时扫描 `.ai/tmp/runs/*`：非当前 token 的目录一律**只报告不删除**，输出
  `token / mtime / 文件数 / 账本最后一条事件`。
- **不自动回收**：无法证明持有者已死亡（pid 可复用；跨机器/容器更无法判定）。
  自动回收会重新制造「S2：A 删掉 B 正在用的文件」。
- 人工恢复流程（写入 README）：`ls .ai/tmp/runs` → 确认无进程在用 → 手工删除目录；
  仓库内 Tier-2 文件按 `git status` 精确核对后逐个删除，禁止通配符。
- 可选（需单独授权）：`run_tests.py --janitor --dry-run` 只列清单与建议命令，不执行删除。

### 3.6 并发竞争分析

| 竞争点 | 新设计下的状态 |
| --- | --- |
| 产物文件名 | 消除（token 唯一） |
| 清理范围 | 消除（只碰本运行根 / 精确白名单） |
| 残留断言 | 只看本运行根（不再 glob 全目录） ⇒ 不会把别人的文件当自己的残留 |
| `user://` trace | 需要 Tier-2 token 文件名，否则仍冲突 |
| `.godot` 导入缓存 | **未解决**：`run_tests.py` 的 `--import` 刷新与 Godot 自身缓存写入是共享可变状态；并发全量运行仍可能互相干扰。本阶段不引入锁，明确列为已知限制 |
| 账本文件 | 每运行独立目录 ⇒ 无共享写 |
| `.ai/tmp` 目录创建 | `exist_ok=False` + 唯一 token ⇒ 无 TOCTOU 接管 |

### 3.7 安全边界

允许的写入/删除根：`.ai/tmp/runs/<token>/`；Tier-2 白名单：`Levels/`、`Tests/`、`Scenes/`
下**精确文件名**（含 token）与 `user://` 下**精确文件名**（含 token）。

明确禁止：删除 `Levels/`、`Tests/`、`Scenes/`、`.ai/`、项目根、盘符根；递归删除任何非运行根目录；
按前缀/时间/通配符删除；跟随符号链接；删除 `.ai/tools/validator/baselines/` 下任何文件。

## 4. F5 现状：过滤命中数与执行完整性

### 4.1 代码证据与实测

| 事实 | 位置 | 实测 |
| --- | --- | --- |
| 过滤在「发现」阶段完成，过滤前的数量被丢弃 | `run_tests.py:154 filter_tests()`，调用点 143/151 | — |
| 头部只打印**过滤后**的 total，不含过滤串 | `run_tests.py:281` | F5-2：`1 tests (Godot=0, Python=1)` |
| 汇总的 `completed/total` 中 total 也是过滤后数量 | `run_tests.py:325` | F5-2：`completed=1/1` |
| 子集运行同样打印 `ALL PASS` | `run_tests.py:347` | F5-2 实测 |
| 空匹配：`no selected test scripts found` + exit 1 | `run_tests.py:255-256` | F5-1 实测 exit 1 |
| 子进程被中断 → INCOMPLETE | `classify()` 行 169–186 | Phase 1.29 E1/E4 覆盖 |
| **`run_tests.py` 自身被中断**：无摘要、无状态文件、无 `run_end` | 无实现 | 代码证据（只有 stdout，无落盘） |
| 过滤串大小写不敏感、按 posix 相对路径子串匹配；段之间有重叠 | `run_tests.py:154-161` | 文档已注明（validator 段 8 项含 3 个 scene_composer 文件） |

真实命令与输出（本阶段执行）：

```
$ python .ai/tools/run_tests.py --python-only zz_no_such_filter_phase_1_31
[run_tests] no selected test scripts found
exit=1

$ python .ai/tools/run_tests.py --python-only test_run_tests_evidence
[run_tests] import cache refresh: ok
[run_tests] 1 tests (Godot=0, Python=1), godot=Godot_v4.7-stable_win64_console.exe
[run_tests] --- Python suite (1 tests) ---
[1/1] PASS .ai/tools/validator/tests/test_run_tests_evidence.py
[run_tests] completed=1/1 passed=1 failed=0 incomplete=0 unavailable=0 not_executed=0
[run_tests] ALL PASS
exit=0
```

F5-2 是关键证据：**这条日志与「全量 81 项全部通过」在文本形态上不可区分**——
只能靠 `Godot=0, Python=1` 与「刚才用了过滤」这一外部记忆。日志本身不记录过滤串，
也不记录「发现 43 个 Python 测试、命中 1 个」。

### 4.2 场景现状表

| 场景 | 现状 | 退出码 | 证据是否准确 |
| --- | --- | --- | --- |
| 过滤串无匹配 | 明确提示 | 1 | 是（但不知道请求了什么过滤串） |
| 部分匹配（一个 family 命中 0） | 静默继续 | 0（若其余通过） | **否**：`Godot=0` 不区分「过滤排除」与「不存在」 |
| 发现阶段目录不可读 | `glob` 返回空 → 视作无测试 | 1 | 是（fail-closed） |
| 测试执行中断（子进程） | INCOMPLETE | 1 | 是 |
| **入口自身被中断** | 无摘要；日志截断 | shell 的 130/137/超时 | **否**：需要下游根据「没有 run_end」自行推断 |
| `--stop-on-fail` | `not_executed` 计数 | 1 | 是 |
| Godot 不可用（显式请求） | `unavailable` + 打印 | 2（仅 godot）/ 1（混合） | 是 |

### 4.3 兼容性风险（任何改动前必须列出）

| 影响面 | 现状依赖 | 变更风险 |
| --- | --- | --- |
| 退出码 | 0 = 全部 PASS；1 = FAIL/INCOMPLETE/无匹配；2 = 仅 Godot 缺失 | **不得新增/改变**（E3、E7、CONTRACT_INDEX 已锁定） |
| stdout 行 | `no selected test scripts found`（唯一被文档与 E7 引用） | 改动该句可能影响人工/脚本匹配 ⇒ 保持原句不变，只在后面追加 |
| `[run_tests] N tests (Godot=…)` | 无测试解析（grep 未发现解析者） | 可追加新行，但不改既有行 |
| 证据文件 | 目前不存在（零依赖） | 新增 opt-in 参数 ⇒ 无迁移成本 |
| 契约 | `CONTRACT_INDEX.yaml` 的 `test_runner` 段、README E1–E7 | 实施时需同步更新，并补 E8+ |

## 5. F5 最小兼容方案（待授权，未实施）

**P0 — `--evidence <path>`（opt-in，默认关闭）**

- 追加式 JSONL（每行 `flush + os.fsync`），事件：

```json
{"event":"run_start","argv":[...],"filter":"validator","mode":"python-only","discovered":{"godot":38,"python":43},"matched":{"godot":0,"python":8},"started_at":"..."}
{"event":"test_start","path":".ai/tools/validator/tests/test_cross_layer_contract.py"}
{"event":"test_end","path":"...","status":"PASS","detail":"exit=0"}
{"event":"run_end","executed":8,"passed":8,"failed":0,"incomplete":0,"unavailable":0,"not_executed":0,"exit_code":0,"finished_at":"..."}
```

- 不变量：`run_end` 存在 ⇔ 本次运行完整；`executed == count(test_end)`；
  `matched == executed + not_executed`；中断的运行只有 `run_start`/部分 `test_end`。
- 默认**不写任何文件**（避免引入需要 F4 清理的新产物）；需要证据时显式指定路径。
- 与 `--stop-on-fail` 兼容：`run_end.not_executed > 0`。

**P1 — 选择行（纯追加）**

```
[run_tests] selection: filter='validator' matched Godot=0/38 Python=8/43 (total 8)
```

保留此前所有输出行与其顺序；不改 `ALL PASS` 的语义，只是在上面多一行「这是子集」。

**P2 — 空匹配诊断（保留原句）**

```
[run_tests] no selected test scripts found (filter='x'; 0 of 81 discovered tests matched)
```

退出码仍为 1。

**不做**：新增退出码；把 `ALL PASS` 改成 `SUBSET PASS`（会影响既有日志检索）；
默认写证据文件；改变 PASS 分类语义（Phase 1.29 已锁定）。

**测试设计（实施时）**：

| 编号 | 断言 |
| --- | --- |
| E8 | 过滤命中 1 个探针 → `run_end` 存在、`matched.python=1`、`executed=1`、`discovered.python>1`、exit 0 |
| E9 | 过滤无命中 → 原句存在 + `matched=0` + exit 1 + `run_end.state=complete` |
| E10 | 子进程运行 `run_tests.py` 跑一个会 sleep 的探针，在首个 `test_end` 前 SIGTERM/KILL → 证据无 `run_end`，状态可判 INCOMPLETE（**不涉及真实测试进程**，只用自建探针） |
| E11 | 证据文件写入失败（只读目录）→ 显式诊断 + 非 0，**不得**静默当成功 |

## 6. 并发 / 强杀 / 清理失败的安全场景矩阵

> 说明：S1–S6 是**新设计**下应成立的期望；「当前」列来自 §2 的代码证据或实测。
> 本阶段**没有**执行 S1–S6 的破坏性复现（§八 禁止）。

| # | 场景 | 新设计期望 | 观测证据 | 失败条件（判定不通过） | 当前状态 |
| --- | --- | --- | --- | --- | --- |
| S1 | 两个 run 同时创建资源 | 两个 token 目录并存，互不可见；两次都 PASS | 两个运行根的账本、各自 fixture 名单 | 任一运行看到另一 token 的路径 / 任一运行根被对方写入 | 固定名 ⇒ 互相覆盖（推导） |
| S2 | A 清理时 B 仍在用 | A 只删自己的账本条目；B 的文件仍在 | A 的 `removed` 事件；B 的 `created` 摘要未变 | A 删除了非本 token 路径 / B 读到 `无法读取` | **已实测同类**：P1 证明 foreign 会被删 |
| S3 | 测试进程异常终止 | 运行根完整保留；下次启动**只报告** stale token | 目录 + 账本最后事件 + 无 `removed` | 自动删除 stale 目录 / 把残留当成 PASS | 无启动期检查（cross-layer） |
| S4 | 清理过程异常终止 | 部分删除后账本仍有 `created` 无 `removed`；重跑只补删自己且摘要匹配的条目 | 账本事件序列 | 依据名字/前缀「补删」未知文件 | `cleanup()` 的 `except OSError: pass` 静默失败 |
| S5 | 所有权标记缺失 / 被篡改 | 拒绝删除 + 报告 `ledger_missing` / `record_incomplete` / `content_changed` | 报告行；本运行判 FAIL | 缺标记仍然删除，或静默跳过而不影响结论 | 无标记概念 |
| S6 | 清理遇到不属于本运行的资源 | 保留 + 报告 `foreign`；不影响本运行结论（除自身产物未清理） | 外来路径仍存在；报告含原因 | 删除任一外来路径 | **已实测**：P1 `foreign_removed=True` |

## 7. 过滤命中数与执行完整性证据（设计要点）

1. **三种计数必须分开记录**：`discovered`（过滤前）、`matched`（过滤后）、`executed`（实际启动）。
   当前三者中只有 `total`（= matched）被打印，`discovered` 完全丢失。
2. **请求必须落盘**：`argv`、`filter`、`mode`、`cwd`、`started_at`。没有请求记录的日志无法证明
   「这是全量还是子集」。
3. **完整性靠 `run_end` 的存在性**，不靠日志里是否出现 `PASS` 文本：
   - `run_end` 缺失 ⇒ INCOMPLETE（即使 stdout 里有很多 PASS 行）；
   - `run_end.exit_code != 0` ⇒ 非 PASS；
   - `not_executed > 0` ⇒ 非 PASS（与当前退出码语义一致）。
4. **崩溃一致性**：JSONL 追加 + `fsync`；只丢弃最后一行不完整记录；不允许重写整个文件。
5. **证据文件不放进** `baselines/`（那是审批内核）；默认放在用户指定路径，未来接 F4 的运行根。
6. **不得用日志文本替代退出码**：报告与自动化判断仍以进程退出码 + `run_end` 为准。

## 8. 基线保护结果

审计开始与结束各测一次，四项**完全一致**：

| 基线 | sha256（开始 = 结束） | mtime（开始 = 结束） |
| --- | --- | --- |
| `multi_stage_boss.json` | `5736788cd9efd8668b8958e3d7fdde83e4c8ce85a53d355c58763110f73e22b1` | 2026-10-17 22:19:01.472536400 |
| `single_stage_boss.json` | `d540cfe2226216e076810b4900a0a860057fb247523e3fde664e6e0c04339e15` | 2026-10-17 22:19:01.774880700 |
| `waves.json` | `878691b1d174cbf026a9723d112168f35bce5784b0ea928b11f06de9165506eb` | 2026-10-18 22:39:06.613330400 |
| `holdout.json` | `acf8bfbac8abf774365ac5c7b60565613db228834ddc3c9d998aedcc1d3f3836` | 2026-10-18 23:55:12.178038700 |

本阶段未重录、未迁移、未改写任何基线；历史 `events[*].run_id` 的不可恢复性仍是
Phase 1.30 已记录的**历史限制**（修复只对未来候选生效）。

## 9. 已执行命令与真实结果

执行环境：Windows / Git Bash / Python 3；Godot `4.7.stable.official.5b4e0cb0f`（可用，无 UNAVAILABLE）。

| # | 命令 | 退出码 | 结果 | 证据 |
| --- | --- | --- | --- | --- |
| V1 | `git rev-parse HEAD` / `git status --porcelain` / `git diff --cached --name-only` | 0 | HEAD `5e47bfd`；26 条变更；暂存 0 | 本文件 §1 |
| V2 | `sha256sum` + `stat -c '%n %Y'` 四个基线 | 0 | 四次哈希/mtime 一致（§8） | 开始/结束各一次 |
| V3 | F4-P1：临时目录内 own/foreign/unrelated + `cleanup()` | 0 | own/foreign 均删，unrelated 保留 | §2.4 P1 |
| V4 | F4-P2：`godot -s res://.ai/tmp/p131_<uuid>/probe.gd` | 0 | `valid=1`，无 `.uid`，目录已删，git 状态 26 不变 | §2.4 P2 |
| V5 | `python .ai/tools/validator/tests/test_cross_layer_contract.py` | 0 | **66 行 `PASS:`**（65 项检查 + 1 汇总），`SKIP` 0，无残留 | `/tmp/f4probe/cross_layer.log` |
| V6 | `python .ai/tools/run_tests.py validator` | 0 | `completed=8/8 passed=8 failed=0 incomplete=0 unavailable=0 not_executed=0` | 终端输出 |
| V7 | `python .ai/tools/run_tests.py --python-only zz_no_such_filter_phase_1_31` | 1 | `no selected test scripts found` | §4.1 F5-1 |
| V8 | `python .ai/tools/run_tests.py --python-only test_run_tests_evidence` | 0 | 过滤子集 `1/1 PASS` + `ALL PASS`（无过滤串记录） | §4.1 F5-2 |
| V9 | `git status --porcelain`（V4/V5 之后） | 0 | 26 条，无 `E2eContract__*` / `level_contract_probe` 残留 | 终端输出 |

**本阶段未执行**（不冒充通过）：

| 检查 | 状态 | 原因 |
| --- | --- | --- |
| `python .ai/tools/run_tests.py`（全量 81 项单命令） | **NOT_EXECUTED（本阶段）** | 本阶段只改文档，未改任何被测代码；Phase 1.30 的 81/81 exit 0 属**历史结果**，不作为本阶段证据 |
| `run_tests.py e2e`（含真实 Godot 基线捕获，约 19 分钟） | **NOT_EXECUTED（本阶段）** | 同上；且不属 F4/F5 审计必需 |
| `run_tests.py --godot-only`（38 项） | **NOT_EXECUTED（本阶段）** | 同上 |
| 并发运行 cross-layer / e2e 两次 | **NOT_EXECUTED** | 会产生真实互删（§八 禁止破坏性复现）；改用 §2.4 P1 临时目录模拟 |
| 强杀真实测试进程制造残留 | **NOT_EXECUTED** | §八 明令禁止 |
| Godot 不可用场景 | **UNAVAILABLE 不适用** | 本机 Godot 可用，未构造缺失环境 |

## 10. 未验证假设与已知限制

| 编号 | 内容 | 状态 |
| --- | --- | --- |
| A-1 | Godot `-s` 能执行 `res://.ai/tmp/runs/<token>/` 下的脚本，且能读取同目录夹具 | **已验证**（§2.4 P2，本机 4.7.stable） |
| A-2 | 该布局在 Linux/macOS、其他 Godot 4.x 版本、以及 `--import` 扫描下同样不产生 `.uid`/缓存问题 | 未验证（需实施阶段跨环境复验） |
| A-3 | 并发两运行的实际互删/误报（S1/S2） | 未执行（静态推导 + P1 语义证明） |
| A-4 | `.ai/tmp/` 未在 `.gitignore` 中 | **已实测**（`git check-ignore` → NOT ignored）；实施前必须补 |
| A-5 | 两个并发全量运行的 `.godot` 导入缓存竞争 | 未解决、未验证；明确列为已知限制 |
| A-6 | Windows 大小写/8.3 短名/长路径对 `resolve()` 白名单的影响 | 未验证；设计已要求规范化 + 拒绝越界 |
| A-7 | `--evidence` 在网络盘/同步盘上的 `fsync` 延迟 | 未验证；实现时需失败即报错（E11） |
| A-8 | 强杀后 stale 目录的人工回收流程 | 未演练（禁止制造残留）；仅设计 |
| L-1 | 无跨进程锁；并发安全依赖 token 唯一性 + 精确白名单，不依赖互斥 | 设计取舍 |
| L-2 | 无法证明持有者已死 ⇒ 永不自动回收 | 设计取舍（避免 S2） |
| L-3 | 同权限攻击者可伪造 token 目录/账本 | 超出本阶段威胁模型（与 Phase 1.30 E-3 一致） |
| L-4 | 历史基线 `run_id` 不可恢复 | 历史限制，禁止重录 |

## 11. 建议实施顺序与所需授权

| 步骤 | 内容 | 触及文件 | 风险 | 所需授权 |
| --- | --- | --- | --- | --- |
| **Step 1（F5-A）** | `--evidence`（JSONL）+ `selection:` 行 + 空匹配追加计数；E8–E11 | `run_tests.py`、`test_run_tests_evidence.py`、`CONTRACT_INDEX.yaml`、README | 低（纯追加；退出码不变） | 授权 A |
| **Step 2（F4-A）** | cross-layer 改 Tier-1：token 运行根 + 账本 + fail-closed 清理 + 启动期只报告；`O1–O6` 自检；`.gitignore` 增 `.ai/tmp/` | `test_cross_layer_contract.py`、`.gitignore`、README | 中（测试内部；断言 65 项不变） | 授权 B |
| **Step 3（F4-B）** | e2e + 6 个 GDScript 测试改 token 命名（含 `user://`），启动期只报告 stale | e2e 测试、`Tests/*.gd`（测试文件） | 中（涉及 GDScript 测试与 Z1/G6/H7 断言） | 授权 C |
| **Step 4（F4-C，可选）** | `--janitor --dry-run`：列 stale token 与建议命令，不删除 | `run_tests.py` + 新测试 | 低 | 授权 D |
| **Step 5（F5-B，可选）** | 默认把证据写入 `.ai/tmp/runs/<token>/`（依赖 Step 2） | `run_tests.py` | 中（默认行为变化） | 授权 E |

**永不做**：强杀真实测试制造残留；删除无法证明所有权的文件；重录/改写历史基线；
为让校验通过而关闭清理守卫；新增/改变既有退出码含义。

## 12. 停止点

审计与设计到此为止。F4 / F5 **均未实施**；工作区仅新增本文件并更新三处文档
（`CURRENT_TASK.md` / `WORK_STATE.md` / `validator/README.md`）。
下一步需明确授权（A–E 中任一项）后才能进入实现阶段。

### 12.1 收尾实测（2026-10-19）

| 项 | 值 |
| --- | --- |
| `git status --porcelain` | **27 条 = 20 修改 + 7 未跟踪**（较审计开始时新增本文件） |
| 暂存区 | 0（`git diff --cached --name-only` 为空） |
| 四个基线 sha256 | 与 §8 完全一致（未重录、未改写） |
| `.ai/tmp` / 测试残留 | 不存在；无 `Levels/E2eContract__*`、无 `Tests/e2e_level_contract_probe.gd` |
| 本阶段写入的文件 | 新增 `.ai/context/PHASE_1_31_AUDIT.md`；追加 `.ai/context/CURRENT_TASK.md`、`.ai/context/WORK_STATE.md`、`.ai/tools/validator/README.md` |
| 未触碰 | `.workbuddy/memory/2026-10-18.md`、全部基线、全部生产代码与测试代码 |
