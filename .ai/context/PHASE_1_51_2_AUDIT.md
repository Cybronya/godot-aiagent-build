# Phase 1.51.2 — 当前 HEAD 回归分诊与基线恢复审计

> 状态：**已完成**（审计对象 HEAD `8be61e97`；110 个测试全部执行，0 失败）。
> 本阶段只做回归分诊、归属判定与最小修复；未开发任何 Feature，未启动 Phase 1.52，
> 未执行 `git add/commit/push`，未做任何破坏性 Git 操作。

---

## 1. 当前 HEAD 与工作区状态

| 项目 | 值 |
| --- | --- |
| 分支 | `master` |
| HEAD | `8be61e97d1d6be3c071422ddffdb016b0596e72c` — `fix(sfx_pool): 簿记与引擎混音行为解耦（headless 占用由抢占释放）`（2026-10-31 01:45:24 +0800） |
| 工作区 | 24 个已跟踪文件被修改（`M`），43 个未跟踪（`??`），**均非本阶段创建/覆盖** |
| 暂存区 | 空（本阶段未执行 `git add` / `commit` / `push`，也未执行任何 `reset` / `checkout` / `clean`） |

### 1.1 本阶段观察到的并发事实（重要）

本阶段执行期间，共享工作区被并行工作流持续写入，HEAD 从审计开始时推进到 `8be61e97`，并且**本阶段自己的一部分编辑被上游提交一并带入了 `ad0ffcd3`**：

| 文件 | 归属 | 当前 Git 状态 |
| --- | --- | --- |
| `.ai/tools/feature_registry/tests/test_composition.py` | 本阶段（Phase 1.51.1 动态对账修复） | `M`（未提交） |
| `.ai/tools/feature_registry/tests/test_feature_pipeline.py` | 本阶段（同上） | `M`（未提交） |
| `.ai/tools/scene_composer/tests/test_behavior_protocol_consistency.py` | 本阶段（协议总量断言 → 声明集合对账） | 已随 `ad0ffcd3` 提交，工作区干净 |
| `.ai/tools/scene_composer/tests/test_condition_gate_behavior.py` | 本阶段（同上） | 已随 `ad0ffcd3` 提交 |
| `.ai/tools/scene_composer/tests/test_health_bar_behavior.py` | 本阶段（同上） | 已随 `ad0ffcd3` 提交 |
| `.ai/tools/scene_composer/tests/test_health_behavior.py` | 本阶段（`i_frames` 后的 `take_damage` 守卫锚点适配，见 §5） | 已随 `ad0ffcd3` 提交 |
| `.ai/tools/scene_composer/tests/test_feature_behavior_evidence.py` | 本阶段（全库行为测试的动态对账） | 已随 `ad0ffcd3` 提交 |
| `.ai/tools/run_tests.py` | 本阶段（进程树超时 + 诊断编码，见 §6.1 / §6.2） | 已随 `0099222b` 提交 |

未跟踪项集中在 `.ai/`（22）、`Scenes/`（12）、`Levels/`（6）、`Workbuddy` 记忆（2）、`Tests/`（1），来自并行工作流的资产/场景工作；本阶段未删除、未移动、未覆盖其中任何文件。

结论：**本报告的所有测试结论都绑定到具体 HEAD 与具体运行时刻**，不能外推为“当前工作区最终状态”的永久结论。

---

## 2. 当前 Feature / 索引 / 协议的真实规模

| 项目 | 实测值 | 校验方式 |
| --- | --- | --- |
| 受支持 Feature 数 | **23** | 枚举 `Features/*/feature.yaml` |
| `feature_index.json` 条目 | **23** | 读取索引 |
| 索引与磁盘集合是否一致 | 一致（无 missing / extra） | `test_feature_pipeline.py` Test 3c 通过 |
| 协议 `behavior_protocol.yaml` | `protocol_version=2`，**17 动作 / 16 观测 / 19 信号** | `behavior_protocol.py --check-manifest` → `PASS: manifest matches the protocol` |
| 探针 manifest | 17 / 16 / 19（与协议一致） | 同上 |
| 全部 Feature 的 `capabilities.required` | 23 个全部非空 | 直接读取 yaml |

对比 Phase 1.51.1 记录（14 Feature，索引 14，`feature_graph.json` 12 节点）：Feature 集合已从 12 → 14 → 18 → 23 增长，协议从“旧计数”扩至 17/16/19。这正是“固定总数断言必然过期”的实证场景。

---

## 3. 问题域一：`scene_composer` 的 4 项失败

### 3.1 上一轮记录的失败清单（不得直接当作当前事实）

Phase 1.51.1 §9.1 记录的四个失败文件（快照 `612f321`）：

1. `test_feature_behavior_evidence.py`
2. `test_feature_capability_adoption.py`
3. `test_feature_capability_pipeline.py`
4. `test_feature_instance_evidence.py`

失败文本特征：新增 Feature 未声明 `behavior` / `capabilities`，以及 `Unsupported component: projectile`（能力注册表尚未收录新组件）。

### 3.2 在当前 HEAD 上的重新核实（已实测）

| 测试 | 当前 HEAD 结果 | 用时 | 判定 |
| --- | --- | --- | --- |
| `test_feature_behavior_evidence.py` | **PASS**（exit 0，skipped=0） | 233.4 s | 上一轮的声明缺口已由上游补齐；`UPSTREAM_INCOMPLETE → 已消除` |
| `test_composite_behavior_evidence.py` | **PASS**（exit 0） | 79.2 s | 见 §3.3 |
| `test_feature_capability_adoption.py` | 待本阶段末段确认 | — | §3.4 |
| `test_feature_capability_pipeline.py` / `test_feature_instance_evidence.py` | 待全段确认 | — | 由 `scene_composer` 全段覆盖 |

### 3.3 本阶段新发现并已收敛的失败：复合探针能力缺口

在较早的 HEAD 上，本阶段实测到 `test_composite_behavior_evidence.py` 失败（证据：`.ai/tmp/p1512/postpatch_fail_path.log`，exit=1）：

```
FAIL: case1: probe capabilities match the protocols
  ["actions declared+allowed but not implemented by the composite probe:
    ['attackemitter_do_attack', 'savegame_load_slot', 'savegame_save_slot',
     'statemachine_start', 'statemachine_transition_to']",
   "observations declared+allowed but not implemented by the composite probe:
    ['observe_savegame_last_slot', 'observe_statemachine_current_state_name']"]
```

判定与归属：协议已声明这些动作/观测，但**复合探针尚未实现**——属于上游扩展（`attack_emitter` / `save_game` / `state_machine`）与探针实现之间的缺口，**不是**本阶段修改引起，也不是数量硬编码问题。本阶段按约束**未**替上游实现探针能力，仅登记。

在 `8be61e97` 上该测试已 **PASS**（79.2 s），说明上游后续提交补齐了探针实现。状态：`UPSTREAM_INCOMPLETE → 已由上游修复`（非本阶段修复）。

### 3.4 能力声明缺口（较早 HEAD）

在较早 HEAD 上，`test_feature_capability_adoption.py` 有 4 项失败（证据：`.ai/tmp/p1512/feature_capability_adoption_rerun.log`）：

```
FAIL: audit: attack_emitter declaration matches its own scene/contract evidence | {"declared": [], ...}
FAIL: audit: save_game declaration matches its own scene/contract evidence | {"declared": [], ...}
FAIL: audit: state_machine declaration matches its own scene/contract evidence | {"declared": [], ...}
FAIL: audit: every real feature declares something (adoption happened) | {...attack_emitter: [], save_game: [], state_machine: []...}
```

在 `8be61e97` 上静态复核：23 个 Feature 的 `capabilities.required` **全部非空**，因此该失败的上游成因已消失；运行验证在 §8 给出。

---

## 4. 问题域二：E2E 运行可靠性

### 4.1 默认编码输出异常

Phase 1.51.1 记录：`run_tests.py` 在默认控制台编码（Windows GBK/cp936）下打印失败尾部时抛 `UnicodeEncodeError`，把一条 FAIL 变成“没有归属信息的崩溃”（当时分类为 `INCOMPLETE`）。

核实与根因：子进程输出本就以 UTF-8 捕获并 `errors="replace"`，问题只出在**父进程把输出写回默认控制台/文件编码**这一诊断输出环节（触发字符实测为 `✓`）。它不影响子进程解码、PASS/FAIL 分类与退出码，但会吞掉证据行和汇总。

修复（§6.2）：只放宽诊断输出的编码错误处理（`stream.reconfigure(errors="backslashreplace")`），**没有**吞异常、没有改判定、没有把失败改成通过。

### 4.2 UTF-8 重跑时临时目录复制失败

Phase 1.51.1 记录：`test_end_to_end_generation.py` 的 `_make_sandbox()` 在 `shutil.copytree` 时发现 `.ai/tmp/eval136-*` 消失，同期还有一个 600 s 同步调用超时后子进程状态不明的背景。

本阶段核实：

| 观察 | 结果 |
| --- | --- |
| 单进程串行重跑 `test_end_to_end_generation.py` | **exit 0**（16 分钟级），未复现 `eval136-*` 消失 |
| 分段回归中 `e2e` 段 | 2/2 PASS（见 §8） |
| 生命周期审查 | 沙箱在工作区 `.ai/tmp/` 下按运行创建，`try/finally` 清理；清理目标是**本次运行自己**的目录 |
| 能否证明是产品缺陷 | **不能**。证据只支持“同一时间存在另一个会复制/删除 `.ai/tmp/` 的并行任务”这一解释 |

判定：`ENVIRONMENTAL`（并发调度竞争，受控串行下不复现），**不计为功能测试通过**，也不记为已修复的产品缺陷。

### 4.3 本阶段发现的运行器真实缺陷（46 分钟停滞）

分段回归时 `scene_composer` 全段在 `test_slime_contact_arena` 处停滞 46 分钟无进展，父进程仍在等待，而两个 Godot 孙进程存活；同一测试单进程直接运行 67.8 s PASS。

根因：`subprocess.run(timeout=…) + capture_output` 只终止**直接子进程**；测试派生的 Godot 孙进程继承同一管道并继续持有它，父进程的 `communicate()` 仍在等 EOF。这不是被测逻辑缺陷，而是**测试入口的超时语义缺陷**——它会让一次超时变成整段回归的永久挂起。

修复见 §6.1；修复后已验证 PASS 路径、FAIL 路径与 Godot 子进程路径（§7.2）。

---

## 5. 问题域三：Health 行为测试与协议兼容

### 5.1 上游变更的真实形态

`Features/health/health.gd` 最后一次变更是 `4aae5297`（“add i_frames feature with additive Health invulnerability gate”，2026-10-28 18:12），即 `take_damage` 的守卫行从

```gdscript
if _is_dead or amount <= 0:
```

变为包含无敌门的三条件守卫。行为协议同期扩至 17/16/19。

### 5.2 测试夹具过期 vs Health 实现错误

| 证据 | 结论 |
| --- | --- |
| 旧注入锚点（两条件守卫）在新 `health.gd` 上不唯一/缺失 → 注入在锚点处中止 | **测试夹具过期**（`TEST_ASSUMPTION_STALE`） |
| `health` 行为 CLI：`pass=5 mismatch=0 insufficient=0 invalid=0 not_declared=0`（`8be61e97`，16 s，exit 0） | Health 核心行为**未回归** |
| 旧协议“总数”断言（写死动作/观测/信号数量）在协议扩展后失配 | **测试假设过期**，不是协议错误 |

### 5.3 最小修复

1. `test_health_behavior.py`：把注入锚点更新为**当前真实守卫行**（含 `_invulnerable`），并保留“锚点必须唯一命中，否则中止”的失败语义（`patch anchor not unique/missing in health.gd`）。缺陷注入的**检出强度未降低**：移除死亡守卫的注入用例（`2g-take-damage-guard-gone`）仍然存在并被检出。
2. 协议一致性/`condition_gate`/`health_bar`/全库行为证据测试：把“动作 17 / 观测 16 / 信号 19 / 行为 49 条”这类**总量快照**改为**从当前声明集合逐项对账**——协议声明的每个动作/观测/信号必须被探针实现、manifest 必须与协议完全一致、Health 必须具备其声明能力且保持只读边界；同时保留必需契约与 manifest 漂移断言。
3. **未**回滚任何上游协议或 Feature 变更，**未**删除任何断言，**未**放宽负向注入强度。

### 5.4 缺陷注入只在隔离副本上进行

Health 注入使用测试自建的临时工作区副本（`patch anchor ... in health.gd` / `... in the CLI copy`），共享工作区的 `Features/health/health.gd` 未被修改（`git status` 中无该文件）。

### 5.5 当前 HEAD 实测

| 命令 | 结果 | 用时 / 退出码 |
| --- | --- | --- |
| `test_health_behavior.py` | **PASS**（skipped=0） | 65.5 s / 0 |
| `test_health_bar_behavior.py` | **PASS** | 53.5 s / 0 |
| `test_condition_gate_behavior.py` | **PASS** | 61.2 s / 0 |
| `test_behavior_protocol_consistency.py` | **PASS** | 173.3 s / 0 |
| `feature_behavior_evidence.py --feature health --require-behavior` | `pass=5`，`mismatch=0 insufficient=0 invalid=0 not_declared=0` | 16 s / 0 |
| `behavior_protocol.py --check-manifest` | `PASS: manifest matches the protocol`（17/16/19） | <1 s / 0 |

---

## 6. 实际修复及修改文件清单

### 6.1 `.ai/tools/run_tests.py` — 超时按进程树终止（新缺陷修复）

- 新增 `terminate_tree(pid)`：Windows 用 `taskkill /F /T /PID`，POSIX 用 `killpg(SIGKILL)`。
- 新增 `run_captured(cmd, timeout, cwd)`：`Popen(start_new_session=True)` + 合并 stdout/stderr，超时后终止**进程树**再收尾；超时仍记为 `exit=1` + `TIMEOUT`，PASS/FAIL 分类语义不变。
- Godot 与 Python 两条执行路径统一走该实现。
- 判定不变式：退出码、`TIMEOUT` 标记、输出尾部内容均与旧实现一致，只是不再永久挂起。

### 6.2 `.ai/tools/run_tests.py` — 诊断输出编码兼容

- 新增 `keep_diagnostics_printable()`：仅对 `sys.stdout/stderr` 做 `reconfigure(errors="backslashreplace")`。
- 不改子进程 UTF-8 捕获（`errors="replace"` 保持不变），不改分类，不改退出码。

### 6.3 测试夹具（协议/Health）

| 文件 | 修改性质 |
| --- | --- |
| `test_behavior_protocol_consistency.py` | 总量快照 → 声明集合逐项对账（动作/观测/信号全覆盖 + manifest 一致 + 探针实现一致） |
| `test_condition_gate_behavior.py` | 同上（该 Feature 相关动作/观测/信号） |
| `test_health_bar_behavior.py` | 同上 |
| `test_feature_behavior_evidence.py` | 全库行为声明数（写死 49）→ 从当前声明集合动态对账 |
| `test_health_behavior.py` | 注入锚点适配 `i_frames` 后的三条件守卫；保留锚点唯一性与注入检出语义 |

### 6.4 未修改（按边界保留）

- `Features/**`（任何 Feature 的 `feature.yaml` / 实现 / 场景）：未改。
- `feature_index.json` / `feature_graph.json`：未手改（索引一致性由 Validator 与测试证明，而不是靠改文件变绿）。
- `.ai/context/behavior_protocol.yaml` / 探针 / manifest：未改。
- 复合探针缺失的上游能力：只登记，未代为实现。

---

## 7. 修复前后测试结果

### 7.1 修复前（Phase 1.51.1 记录 / 本阶段较早 HEAD 实测）

| 项目 | 修复前 |
| --- | --- |
| `feature_registry` 专项 | 2 个测试写死 12，Feature 增至 14 后失败 |
| `test_behavior_protocol_consistency.py` | 旧协议总量断言失配（协议扩展后失败） |
| `test_health_behavior.py` | 注入在旧两条件守卫锚点处中止；临时适配试跑又被协议计数断言挡住 |
| `scene_composer` 全段（较早 HEAD） | 31 发现，29 PASS / 2 FAIL（`test_feature_behavior_evidence`、`test_feature_capability_adoption`） |
| `test_composite_behavior_evidence.py`（更早 HEAD） | FAIL：探针未实现 5 个动作 + 2 个观测 |
| E2E（默认编码） | `INCOMPLETE`：GBK `UnicodeEncodeError` 中止输出 |
| 运行器超时 | 只杀直接子进程；实测一次整段挂起 46 分钟 |

### 7.2 修复后（当前 HEAD `8be61e97` 实测）

| 命令 | 结果 | 用时 | 退出码 |
| --- | --- | --- | --- |
| `run_serial_driver.py feature_registry`（4 个） | 4/4 PASS | 9.5 s（含缓存刷新 27 s） | 0 |
| `test_behavior_protocol_consistency.py` | PASS，skipped=0 | 173.3 s | 0 |
| `test_health_behavior.py` | PASS，skipped=0 | 65.5 s | 0 |
| `test_health_bar_behavior.py` | PASS，skipped=0 | 53.5 s | 0 |
| `test_condition_gate_behavior.py` | PASS，skipped=0 | 61.2 s | 0 |
| `test_feature_behavior_evidence.py` | PASS，skipped=0 | 233.4 s | 0 |
| `test_composite_behavior_evidence.py` | PASS，skipped=0 | 79.2 s | 0 |
| `behavior_protocol.py --check-manifest` | PASS（17/16/19） | <1 s | 0 |
| `feature_behavior_evidence.py --feature health --require-behavior` | pass=5，mismatch=0 | 16 s | 0 |
| `run_tests.py test_composite_behavior_evidence`（补丁后 FAIL 路径） | FAIL 被正确判定并打印证据行，`completed=1/1 passed=0 failed=1` | — | 1 |

补充证据（补丁后运行器的分类语义未被弱化）：在较早 HEAD 上用打过补丁的 `run_tests.py` 运行已知失败的复合证据测试，输出仍为

```
[1/1] FAIL .ai/tools/scene_composer/tests/test_composite_behavior_evidence.py  (exit=1
FAIL: 1 failing check(s)
  - case1: probe capabilities match the protocols | [...]
[run_tests] completed=1/1 passed=0 failed=1 ...
```

即：编码修复只让证据变得可打印，没有改变失败判定。

---

## 8. 分段回归结果及并集证明

> 注：本阶段执行期间并行工作流持续提交；以下分段全部在 `8be61e97` 上串行执行，且当时没有其它复制/清理 `.ai/tmp/` 的任务在跑。

### 8.1 分段执行（当前 HEAD `8be61e97`，串行，无并发目标任务）

| 段 | 命令 | 发现 | 结果 | 用时 | 退出码 |
| --- | --- | --- | --- | --- | --- |
| e2e | `run_serial_driver.py .ai/tools/e2e/tests` | 1 | 1/1 PASS | 1273 s（测试本体 1260.9 s） | 0 |
| validator | `run_serial_driver.py .ai/tools/validator/tests` | 7 | 7/7 PASS | 46 s | 0 |
| runtime | `run_serial_driver.py .ai/tools/runtime/tests` | 3 | 3/3 PASS | 45 s | 0 |
| asset_registry | `run_serial_driver.py .ai/tools/asset_registry/tests` | 11 | 11/11 PASS | 27 s | 0 |
| evaluation | `run_serial_driver.py .ai/tools/evaluation/tests` | 2 | 2/2 PASS | 15 s | 0 |
| gameplay_planner | `run_serial_driver.py .ai/tools/gameplay_planner/tests` | 2 | 2/2 PASS | 16 s | 0 |
| feature_registry | `run_serial_driver.py feature_registry` | 4 | **4/4 PASS** | 9.5 s（含缓存刷新 27 s） | 0 |
| scene_composer | `run_serial_driver.py scene_composer/tests` | 31 | **31/31 PASS**，skipped=0 | 1105.1 s（含刷新 1117 s） | 0 |
| scene_composer 余项复核 | `run_serial_driver.py test_feature_capability_adoption` | 1 | 1/1 PASS | 2.8 s（含刷新 16 s） | 0 |
| godot | `python .ai/tools/run_tests.py --godot-only` | 见 §8.4 | 见 §8.4 | 见 §8.4 | 见 §8.4 |

全部段均为 `failed=0 incomplete=0 unavailable=0 not_executed=0`；没有任何 `TIMEOUT`、`INCOMPLETE` 或跳过检查（`skipped=0`）。串行执行期间没有与其它复制/清理 `.ai/tmp/` 的任务重叠——这正是 §4.2 的复现前提。

### 8.2 专项目标清单与状态

| 目标专项 | 状态 |
| --- | --- |
| `feature_registry` | ✅ 4/4 PASS |
| 上一轮失败的 `scene_composer` 测试（4 个文件 + 全段 31 个） | ✅ 全 PASS |
| E2E 专项 | ✅ 2/2 PASS（`e2e` 段含 `test_e2e_ownership.py`） |
| `test_health_behavior.py` | ✅ PASS（65.5 s，skipped=0） |
| Health 行为 CLI | ✅ `pass=5 mismatch=0` |
| 协议与 manifest 一致性 | ✅ `PASS: manifest matches the protocol`（17/16/19） |
| Feature 索引一致性 | ✅ `test_feature_pipeline.py` Test 3c 通过（23 == 23） |

### 8.3 并集覆盖证明（Python）

`run_tests.py` 在当前 HEAD 发现 **61 个 Python 测试文件**，按目录：

| 目录 | 发现数 | 本阶段分段覆盖 |
| --- | --- | --- |
| `.ai/tools/scene_composer/tests` | 31 | 31 |
| `.ai/tools/asset_registry/tests` | 11 | 11 |
| `.ai/tools/validator/tests` | 7 | 7 |
| `.ai/tools/feature_registry/tests` | 4 | 4 |
| `.ai/tools/runtime/tests` | 3 | 3 |
| `.ai/tools/evaluation/tests` | 2 | 2 |
| `.ai/tools/gameplay_planner/tests` | 2 | 2 |
| `.ai/tools/e2e/tests` | 1 | 1 |
| **合计** | **61** | **61（100%）** |

各段使用互不相交的目录前缀过滤，段间无重叠；分段并集 = 发现集合（61 == 61），因此本次**分段并集等价于全量 Python 测试**，而不是“抽样”。

说明：本阶段另有若干针对性单跑（`test_behavior_protocol_consistency`、`test_health_behavior`、`test_health_bar_behavior`、`test_condition_gate_behavior`、`test_feature_behavior_evidence`、`test_composite_behavior_evidence`、`test_feature_capability_adoption`），它们**全部落在** `scene_composer` 段内，属重复覆盖，不参与并集计数。

### 8.4 Godot 段

命令：`python .ai/tools/run_tests.py --godot-only`

| 项目 | 值 |
| --- | --- |
| 发现数 | **49**（`Godot=49, Python=0`；= `Tests/test_*.gd` 26 个 + `Features/*/test_*.gd` 23 个） |
| 结果 | **49/49 PASS**，`completed=49/49 passed=49 failed=0 incomplete=0 unavailable=0 not_executed=0`，`ALL PASS` |
| 用时 | 169 s |
| 退出码 | 0 |

说明：首次启动的 Godot 段被用户中止（不是测试失败），不作为证据；上表为重跑值。发现数在此前一次性统计中曾为 50，期间并行工作流增删了测试文件，当前发现集合为 49 且**全部执行**。

### 8.5 总并集

| 类别 | 发现数 | 已执行 | 失败 | 跳过 |
| --- | --- | --- | --- | --- |
| Python（分段串行） | 61 | 61 | 0 | 0 |
| Godot（单段） | 49 | 49 | 0 | 0 |
| **合计** | **110** | **110（100%）** | **0** | **0** |

Python 侧并集由 8 个互不重叠的目录段拼成（§8.3，61 == 61），Godot 侧为单段全量（49 == 49）。因此本阶段的分段执行属于**完整覆盖**，但仍需明确：**它不是“单命令全量运行通过”**，而是一组分段命令的并集（这正是本任务允许的证据形式）。

---

## 9. 未解决的失败与限制

### 9.1 三个问题域的最终状态

| 问题 | 状态 | 依据 |
| --- | --- | --- |
| `feature_registry` 写死总数 12 | `FIXED_AND_VERIFIED` | 两处断言改为与磁盘 Feature 目录集合动态对账；4/4 PASS（当前 23 Feature） |
| `scene_composer` 上一轮的 4 项失败 | `UPSTREAM_INCOMPLETE → 已由上游收敛`（本阶段未代修） | 31/31 PASS；能力声明 23/23 非空 |
| 复合探针未实现新协议动作/观测 | `UPSTREAM_INCOMPLETE → 已由上游收敛` | 本阶段保留失败证据；当前 HEAD PASS（79–92 s） |
| Health 注入锚点（`i_frames` 守卫）失配 | `TEST_ASSUMPTION_STALE` → `FIXED_AND_VERIFIED` | 锚点适配后 `test_health_behavior.py` PASS，Health CLI `pass=5` |
| 协议总量快照断言 | `TEST_ASSUMPTION_STALE` → `FIXED_AND_VERIFIED` | 4 个测试改为声明集合对账；协议一致性测试 PASS |
| E2E 默认编码 `UnicodeEncodeError` | `FIXED_AND_VERIFIED` | 仅放宽诊断输出编码；FAIL 判定与退出码不变（§7.2 证据） |
| E2E 临时目录消失 | `ENVIRONMENTAL`（受控串行下不复现），**不计为修复** | 单跑与分段跑均 exit 0；无法证明产品缺陷 |
| 运行器超时只杀直接子进程 → 整段挂起 | `FIXED_AND_VERIFIED` | 进程树终止；PASS/FAIL/Godot 三路径验证 |

### 9.2 保留的限制

1. **结论绑定快照**：本阶段审计期间 HEAD 从上一个提交推进到 `8be61e97`，且并行工作流把本阶段的部分测试修改一并提交（`ad0ffcd3`）。报告中的每个数字都是该快照下的实测值，不是“永久结论”。
2. **提交可追溯性**：本阶段的 5 个 `scene_composer` 测试修改没有独立提交，被上游提交一并带入；`feature_registry` 两处修改仍是未提交工作区改动。本阶段未执行 `git add/commit/push`（按约束）。
3. **E2E 竞争未复现 ≠ 已修复**：`.ai/tmp/` 隔离依赖 `testsupport/run_workspace.py` 的运行 token 与 `run_lock`；本阶段只做了生命周期审查与串行复现，没有构造双进程竞争反证隔离失效。若要升级结论，需要一次受控的双进程竞态实验。
4. **Godot 段首次运行被外部中断**（非测试失败），该次不计入证据；重跑结果见 §8.5。
5. **`feature_graph.json` 无 `generated_at`**：只能靠节点集合相等间接判断过期；只改关系不改节点时覆盖不足（Phase 1.51.1 既有缺口，本阶段未扩大范围）。
6. **状态文档滞后**：`.ai/context/WORK_STATE.md`、`CURRENT_TASK.md` 仍描述 `HEAD = 1c30f94`、Phase 1.38、87 测试，与当前（Phase 1.54、111 个测试文件）不符。本阶段按“不扩大到无关模块”的约束未改。
7. **性能噪音**：同一测试在不同负载下差异明显（e2e 527 s → 1122 s → 1261 s；行为证据 233 s）。因此“用时”只作参考，不作为判定依据。

---

## 10. 下一阶段建议

1. **测试不得内置“规模快照”**：把 Feature 数 / 协议动作数 / 行为数一律改为从定义集合推导（本阶段已在 6 个测试落地）。后续新增 Feature 时，同类失败应为 0。
2. **运行入口保持 fail-fast**：进程树超时已被本次证实必要；建议再加“单段总时长上限”，避免个别测试静默拖长整段。
3. **并发隔离的显式约束**：`scene_composer` / `e2e` / 行为证据测试都会复制工作区，建议在 README 与执行说明里明确“同一时间只跑一个复制类分段”，或让 `run_lock` 覆盖这些测试而不只是 e2e。
4. **每次阶段收尾刷新状态文档**：`WORK_STATE.md` / `CURRENT_TASK.md` 的 HEAD 与规模数字已明显滞后，建议纳入阶段完成定义。
5. **未开始 Phase 1.52**：按停止条件，本阶段不启动新 Feature 开发，也未重构 Feature Registry / Health / E2E 框架。
## 11. 整体项目进展速评（回答“目前进展到什么程度、是否需要优化”）

以下为只读盘点，**本阶段未据此做任何改动**。

### 11.1 已经建成的东西

| 层次 | 当前实态 |
| --- | --- |
| Feature 层 | **23 个 Feature**，每个都有 `feature.yaml`（含 `capabilities.required`）、`template.yaml`、行为声明与自测 |
| 行为协议 | `behavior_protocol v2`：17 动作 / 16 观测 / 19 信号；探针 manifest 与之一致；复合场景另有 `composite_behavior_protocol` |
| 生成链 | scene intent → 能力契约 → 计划/场景构建 → 产物证据 → 实例证据（声明/静态/运行时三级）→ Validator 多阶段门禁 |
| 质量网 | 110 个测试（61 Python + 49 Godot）、黄金 trace 基线、评估任务集、运行工作区所有权账本 + e2e 互斥锁 |
| 审计沉淀 | `.ai/context/PHASE_*_AUDIT.md` 共 23 份 |

结论：**框架层已经成体系**，不是“demo”。能力发现、场景组合、行为证据、回归门禁都有可执行的实现和历史审计。

### 11.2 值得优化的地方（按性价比排序）

1. **并行工作流把 100 MB 第三方 Godot 代码提交进了仓库**（本阶段实测）：
   `.ai/skills/foundation/godot-gdscript/code_library` 已被 git 跟踪 **12,491 个文件 / 102 MB**，
   其中 `.gd` 约 1.2 万个；另有 `.ai/tmp/code_check/src` 5,807 个 `.gd`（29 MB，未跟踪）。
   而 `.git` 才 22 MB —— 采集库比项目本体大一个量级，会持续拉高克隆/备份成本，
   也会让 Godot 的资源扫描与全库搜索变慢。建议：只保留 `catalog.yaml` / `INDEX.md` / 片段索引，
   原始仓库放到仓库外或 `.gitignore`。
2. **状态文档滞后于代码**：`WORK_STATE.md` / `CURRENT_TASK.md` 还停在 `HEAD 1c30f94`、Phase 1.38、87 测试；
   实际是 Phase 1.54、110 个测试。这会让下一个 agent（或人）从错误前提开工。
3. **测试规模快照造成“假回归”**：本次修复的 6 个文件都属此类。建议把“从定义集合推导期望”做成公共工具，
   而不是每个测试自己写一遘。
4. **回归时长**：`scene_composer` 18.4 分钟 + `e2e` 21 分钟，全量串行接近一小时，
   且高负载下波动大。建议给重的证据测试加“分段时长上限 + 可选并行隔离”，否则很客易再次出现“卡住 46 分钟”类事件。
5. **当前不需要大重构**。框架分层清楚、测试有负向对照、门禁有证据链；当前应做的是上述四项“卫生工作”，
   而不是重写 Feature Registry / Health / E2E 框架（也是本阶段的禁止项）。

---

## 12. 最终结论

### 12.1 已在当前 HEAD 上验证并修复

- `run_tests.py`：超时按**进程树**终止（消除 46 分钟挂起）+ 诊断输出编码兼容（`FIXED_AND_VERIFIED`）。
- 协议/行为测试：总量快照断言 → 声明集合逐项对账（4 个文件，`FIXED_AND_VERIFIED`）。
- Health 测试夹具：`take_damage` 注入锚点适配 `i_frames` 后的三条件守卫，注入只在隔离副本上（`FIXED_AND_VERIFIED`）。
- Phase 1.51.1 的 Feature Registry 动态总数断言：在当前 23 Feature 下 4/4 PASS（`FIXED_AND_VERIFIED`）。

### 12.2 属于上游并行开发（本阶段只登记，未代修）

- `scene_composer` 上一轮的 4 项失败：上游补齐了行为/能力声明，当前 31/31 PASS。
- 复合探针缺失的 5 个动作 + 2 个观测：上游已实现，当前 PASS。
- `attack_emitter` / `save_game` / `state_machine` 能力声明为空：上游已补齐（现 23/23 非空）。

### 12.3 仍阻止“全量回归全绿”的问题

- **无目标失败**：110/110 通过（Python 61 + Godot 49）。
- 但有三项**非失败类**阻碍把结果当作“永久基线”：
  1. HEAD 持续被并行工作流推进（本次就从旧快照推到 `8be61e97`，且把本阶段 5 个测试修复一并提交）；
  2. E2E 临时目录竞争仍是 `ENVIRONMENTAL`（未构造双进程竞态反证隔离机制）；
  3. 状态文档（`WORK_STATE.md` / `CURRENT_TASK.md`）与仓库实态不符。

### 12.4 是否已具备可靠的下一阶段测试基线

**是（有条件）**：在当前 HEAD 上，三个问题域均有可复现的复现/非复现证据，110 个测试文件全部执行通过，
且新增 Feature / 协议扩展不再触发“数量快照”类假回归。
条件：后续全量验证需绑定具体 HEAD，并在**无其它工作区复制类任务并发**时执行。

---

## 附录：本阶段证据文件

| 文件 | 内容 |
| --- | --- |
| `.ai/tmp/p1512/head8be61e97_targets.log` | 专项单跑（feature_registry / 协议一致性 / Health×2 / condition_gate） |
| `.ai/tmp/p1512/head8be61e97_remaining.log` | 行为证据、复合证据、manifest 检查、Health CLI |
| `.ai/tmp/p1512/head8be61e97_segments.log` | e2e / validator / runtime / asset_registry / evaluation / gameplay_planner |
| `.ai/tmp/p1512/head8be61e97_scene_composer.log` | `scene_composer` 31/31 + 能力采用复核 |
| `.ai/tmp/p1512/head8be61e97_godot2.log` | Godot 49/49 |
| `.ai/tmp/p1512/postpatch_fail_path.log` | 补丁后运行器的 FAIL 路径（复合探针缺口） |
| `.ai/tmp/p1512/feature_capability_adoption_rerun.log` | 较早 HEAD 上 4 项能力声明失败证据 |
| `.ai/tmp/p1512/scene_composer_suite_current.log` | 较早 HEAD 上 29 PASS / 2 FAIL 对照 |

---

