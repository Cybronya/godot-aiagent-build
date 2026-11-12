# Phase 1.68.3.1 — Phase 2 Root Cause Report

日期：2026-11-10  
范围：仅调查 `.ai/tools/scene_composer/tests/test_behavior_protocol_consistency.py`  
最终状态：**NOT_REPRODUCED**（原始“卡住/无输出”未复现；目标测试在隔离副本中独立执行并 PASS）

---

## A. Baseline

| 项目 | 值 |
|---|---|
| HEAD | `04f50636c7d3afb37a2a58454cb4ae16f1a38593` |
| Branch | `master` |
| staged | 0 |
| dirty | 1053 |
| origin/master | `04f50636c7d3afb37a2a58454cb4ae16f1a38593` |
| Phase 1 快照 | `.ai/tmp/p1683/baseline/` |

Phase 1 快照包含：

- `git_status_porcelain.txt`：1053 条完整 dirty 清单；
- `historical_sha256.txt`：p157 / p166 / p167 / p168 official 共 828 个文件；
- `features_sha256.txt`：Features 共 265 个文件；
- `protocol_sha256.txt`：Protocol / manifest / probe；
- `code_sha256.txt`：`run_tests.py`、Validator、Coverage。

Phase 2 开始和结束时的 dirty 均为 1053，`git status --porcelain` 与快照逐行比较差异为 0。

---

## B. Test Execution

### 最终有效运行

| 项目 | 值 |
|---|---|
| 隔离副本 | `.ai/tmp/p1683/repro_20261110_231838/` |
| 启动命令 | `PYTHONUNBUFFERED=1 python -u .ai/tools/scene_composer/tests/test_behavior_protocol_consistency.py` |
| 工作目录 | 隔离副本根目录 |
| 开始时间 | `2026-11-10 23:24:47.442` |
| 结束时间 | `2026-11-10 23:27:25.687` |
| 实际耗时 | **158.245 秒** |
| Python 主进程 PID | `12640` |
| 退出码 | **0** |
| 是否正常退出 | **是** |
| 600 秒安全上限 | 未触发，无需停止 |
| 最终日志 | `.ai/tmp/p1683/phase2/run_04.log` |
| 退出码文件 | `.ai/tmp/p1683/phase2/run_04.exit` |

结果：

```text
150 PASS 行
0 FAIL 行
PASS: all behavior protocol consistency checks passed
exit=0
```

`150 PASS` 包含 149 个 `caseN` 检查加最后一行总 PASS；不是 150 个 Case。

### 前置隔离运行的记录

| 运行 | 文件 | 结果 | 说明 |
|---|---|---|---|
| run_01 | `phase2/run_01_godot_missing.log` | 入口退出 | 隔离副本把 Godot 放在项目根，`find_godot()` 查找父目录；不是测试执行 |
| run_02 | `phase2/run_02_missing_tmp.log` | 入口异常 | 副本未创建 `.ai/tmp`，`mkdtemp` 失败；不是测试执行 |
| run_03 | `phase2/run_03_isolated_no_cache.log` | 149 PASS / 1 FAIL | 副本未包含 `.godot/global_script_class_cache.cfg`，`heal_pickup` 的 `Health` 类型无法解析；是隔离环境缺陷 |
| run_04 | `phase2/run_04.log` | **150 PASS / 0 FAIL，exit 0** | 先执行一次 Godot `--import` 生成类缓存，再运行；用于本报告结论 |

run_03 的失败不是本阶段要调查的测试缺陷，也不能作为原始阻塞的证据。它证明隔离副本必须预热 Godot 类缓存，不能直接忽略 `.godot`。

---

## C. Case Timeline

测试自身没有输出时间戳；以下时间由最终日志顺序、行为证据目录 mtime、进程持续时间和日志边界共同确定。Case 1–7 的输出没有逐行时间，不能伪造更细的秒数。

| Case | 执行情况 | 结果 | 时间证据 |
|---|---|---|---|
| Case 1 | 协议版本、能力族、limits、fixture/frames 声明 | 9 PASS | 在 Case 8 首个 probe 前完成 |
| Case 2 | manifest 漂移与逐字再生成 | 4 PASS | 同上 |
| Case 3 | probe 真实实现映射 | 5 PASS | 同上 |
| Case 4 | 非法协议拒绝 | 19 PASS | 同上 |
| Case 5 | 声明但未实现、缺失/损坏协议、manifest 漂移 | 8 PASS | 同上 |
| Case 6 | Python / Godot 对未知动作、参数、检查、信号一致拒绝 | 12 PASS | 同上 |
| Case 7 | 真实协议漂移与逐字节恢复 | 7 PASS | 同上；Case 8 前最后一段 |
| Case 8 | 60 个 Behavior × 2 次重放 | **70 PASS**（60 行为结果 + 10 个声明检查） | 首个 `12640-*-r1` 证据目录 `23:25:17.278`；最后 `23:27:20.648` |
| Case 9 | no-op 动作仍为 MISMATCH，脚本逐字节恢复 | 2 PASS | Case 8 之后，约 23:27:21–23:27:24 |
| Case 10 | 7 个静态 reconciliation + 6 个 runtime instance | 13 PASS | 最后到 23:27:25 |

Case 8 的关键实际数据：

- 声明的 Behavior 总数：**60**（23 个 Feature）；
- 每 Behavior 重放次数：**2**；
- 实际 Behavior probe：**120**；
- 最终有效运行新增行为证据目录：**121**（120 个 Case 8 probe + 1 个 Case 9 使用）；
- Case 8 行为证据写入窗口：`23:25:17.278` 至 `23:27:20.648`，约 **123.4 秒**；
- Case 8 平均每 Behavior（两次重放）约 **2.06 秒**；
- Case 8 全部 60 个行为结果均 PASS，未发现单个 Behavior 异常慢或无限重试。

---

## D. Process Analysis

### 主进程

- Python PID：`12640`
- 启动时间：`23:24:47`
- 结束：正常退出，`exit=0`
- 结束时 CPU 时间约 6 秒，实际墙钟约 158 秒，主要时间在等待真实 Godot 子进程，不是 Python 自旋。

### Godot 子进程

观测到的 Godot 子进程包括：

```text
PID 12920  （运行早期采样）
PID 10548  （运行中期采样）
```

Godot 进程生命周期很短，按固定间隔采样无法保证捕获全部 120 个瞬时 PID；因此本报告不声称上面的列表是完整集合。可以确认：

- 每个 probe 都有真实的 `Godot_v4.7-stable_win64_console` 执行；
- 进程不断更替，未出现同一子进程长时间占用；
- 测试结束时 `Get-Process python,Godot_v4.7-stable_win64_console` 无输出；
- 没有孤儿进程；
- 没有观察到文件锁等待或子进程管道等待。

### 进程回收

- 最终有效运行正常退出，测试的 `finally` 执行；
- 隔离副本中的 `protocol_tests_*` 临时目录已被删除；
- `BehaviorWorkspace` 的 `workspace-*` 目录已被删除；
- 保留的只是测试证据目录 `behavior` / `runtime-instance`，用于审计，未清理；
- 原始工作区未产生本阶段测试临时产物。

### 与 Phase 1.68.3 的差异

Phase 1.68.3 残留的 `.ai/tmp/protocol_tests_kxc8cpmv` 没有被 `finally` 清理，说明当时进程被外部终止；本次正常运行的对应临时目录不存在。这个差异是“外部终止”而非“测试死锁”的直接旁证。

---

## E. Buffering Analysis

已确认存在 stdout 块缓冲影响：

- 测试源码的 `print()` 没有 `flush=True`；
- `run_tests.py` 的 Python 运行路径使用 `Popen(..., stdout=PIPE, stderr=STDOUT)`，没有 `-u`，也没有设置 `PYTHONUNBUFFERED`；
- Python 在管道模式下使用块缓冲，Case 1–8 的进度可能长时间不写入日志；
- 本次使用 `python -u` 后，Case 1–7 和 Case 8 标题在运行中实时出现，证明“无输出”不是测试没有执行，而是输出没有及时刷新。

原始日志只显示到：

```text
[1/31] PASS test_artifact_evidence_validator.py
```

没有第二行，并不意味着第二个测试没有启动；Phase 1 已确认它创建了测试临时目录和约 105 个行为证据目录。

结论：**stdout 缓冲是误判为死锁的直接原因之一，但不是测试停止的全部原因。**

---

## F. Root Cause

### 有证据支持的结论

1. **目标测试没有死锁。**  
   在隔离副本中，同一测试以 `python -u` 完成全部 Case 1–10，耗时 **158.245 秒**，退出码 **0**，150 个 PASS，0 个 FAIL。

2. **Case 8 是主要耗时来源，但工作量可完成。**  
   23 个 Feature 的 60 个 Behavior，每个 2 次真实 Godot 重放，共 120 个 probe；Case 8 证据写入约 123 秒，未发现某个 Behavior 卡住。

3. **原始“超过 300 秒”的说法没有得到现有证据支持。**  
   Phase 1.68.3 的残留临时目录创建于 `20:32:22`，最新行为证据写入到 `20:34:23`；进程在约 121 秒后已经没有继续写入，且临时目录没有执行 `finally` 清理。现有现场数据不能证明它运行到了 300 秒。

4. **原始批次是被外部终止的。**  
   残留 `protocol_tests_kxc8cpmv` 和未清理的 `workspace-ynjqvijp` 说明测试没有正常退出；测试本身在独立运行中能够正常清理。外部终止的具体触发者（人工停止、外层 shell 超时或其他包装器）无法从现有文件恢复。

5. **无输出由 stdout 块缓冲放大。**  
   测试输出经过 `run_tests.py` 管道捕获，未使用无缓冲模式，因此运行期间看不到进度，容易被误判为挂死。

### 无法确定的部分

- 原始停止命令的实际发起者与准确退出码：**UNKNOWN**；
- 是否有外层包装器设置了约 120 秒限制：**UNKNOWN**；
- 原始运行在停止前是否还存在其他环境异常：没有证据。

因此最终根因分类为：

```text
PRIMARY:  EXTERNAL_PREMATURE_TERMINATION
SECONDARY: STDOUT_BLOCK_BUFFERING
NOT:      TEST_DEADLOCK
NOT:      PROVEN_300S_TIMEOUT
```

原阻塞本身 **NOT_REPRODUCED**；目标测试执行本身已独立 **REPRODUCED 且 PASS**。

---

## G. Integrity

使用 Phase 1 的 SHA256 快照逐文件核对：

| 快照 | 文件数 | 失败数 |
|---|---:|---:|
| 历史 p157/p166/p167/p168 official | 828 | **0** |
| Features | 265 | **0** |
| Protocol / manifest / probe | 3 | **0** |
| run_tests / Validator / Coverage | 3 | **0** |

额外核对：

- `evidence_index.json` SHA256：`0e1f4ab03bab6442045eca3b56c88cf2ddc7116878428c52194196942e1ee910`，未变化；
- Official Contract 源数据未修改；
- Official Evidence / Attestation 未修改；
- 原七维 `fully_covered` 公式未修改；
- Scenario 语义未修改；
- Phase 2 测试前后 `git status --porcelain` 差异：**0 行**；
- 测试结束时 dirty 为 **1053**，staged 为 **0**；
- 生成本报告后 dirty 为 **1054**，唯一新增项是 `?? .ai/context/PHASE_1_68_3_1_PHASE_2_ROOT_CAUSE_REPORT.md`；
- 原有 1053 条 dirty 内容未被覆盖或清理；
- 本阶段测试仅写入隔离副本 `.ai/tmp/p1683/`，未写入项目正式资源目录。

---

## H. Recommendation

本阶段不修改任何代码。基于复现结果，建议后续修复阶段只做最小基础设施改动：

1. **保留测试本身，不降低断言，不删除 Case。**  
   目标测试在 158 秒内完整通过，不存在需要删除或跳过的 Case。

2. **诊断运行时使用无缓冲输出。**  
   在测试入口或运行器诊断路径使用 `python -u` / `PYTHONUNBUFFERED=1`，避免把块缓冲误判为死锁；这是诊断改进，不是延长超时。

3. **隔离副本必须预热 `.godot` 类缓存。**  
   复制项目时排除 `.godot` 后，应执行一次 `--import`，否则 `heal_pickup` 的 `Health` 类型会解析失败。该失败是隔离环境缺陷，不是目标测试缺陷。

4. **保留异常终止的临时目录用于审计。**  
   当前测试正常退出会清理 `protocol_tests_*`；被外部终止时残留目录是有价值的证据，不应自动删除。

5. **不调整 300 秒超时。**  
   本阶段实测 158 秒，300 秒不是本次阻塞原因；在没有新的更长运行证据前，延长超时会掩盖真正的外部终止问题。

6. **若后续需要修复运行器，应单独获得授权。**  
   可考虑为测试进程增加明确的进度心跳和退出原因记录，但不得在本阶段直接修改。

---

## I. Final Status

**NOT_REPRODUCED**

含义：

- 原始“无输出/疑似挂死”的现象没有在独立环境中复现为死锁或 300 秒超时；
- 目标测试独立执行成功：150 PASS / 0 FAIL / exit 0 / 158.245 秒；
- 原阻塞的可证据解释是外部提前终止，加上 stdout 块缓冲造成的误判；
- 外部终止的准确触发者仍为 UNKNOWN；
- 本阶段没有进入修复，也没有执行其余 30 个测试，不得将本结果冒充完整 Scene Composer 回归。
