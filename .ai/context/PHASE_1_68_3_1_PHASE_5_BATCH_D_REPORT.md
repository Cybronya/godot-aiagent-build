# Phase 1.68.3.1 — Phase 5: Regression Batch D Report

## 1. 执行时间和环境

- 执行日期：2026-11-11
- 基线建立：23:47:40（本地时间）
- 测试开始：23:49:01
- 测试结束：23:52:54
- 阶段：Phase 1.68.3.1 / Phase 5 / Batch D
- 范围：全 Feature Behavior / Evidence，共 **1** 项
- 项目目录：`F:\Godot_v4.7-stable\game`

### 环境

| 项目 | 值 |
|---|---|
| Python | 3.12.10 |
| Godot | `../Godot_v4.7-stable_win64_console.exe` |
| Godot 文件 | 存在，198152 bytes |
| `.godot/global_script_class_cache.cfg` | 存在，14768 bytes |
| 测试预算 | 900 秒；来自 `run_tests.py` 的 `PYTHON_TIMEOUT_OVERRIDES` |
| stdout/stderr | 已重定向到项目日志目录 |
| Godot/Python 运行环境 | `APPDATA`、`LOCALAPPDATA`、`TEMP`、`TMP`、`TMPDIR`、`PYTHONPYCACHEPREFIX` 均指向项目内日志目录 |
| 串行性 | 单项测试，独立 Python 进程，无并行 |

## 2. 执行前 Git 基线

| 项目 | 值 |
|---|---|
| HEAD | `71f6eef61c1b203229e93a47a111f5ce040c587f` |
| Branch | `master` |
| Upstream | `origin/master` |
| staged | 0 |
| dirty | 1064 |
| untracked | 999 |
| 修改/删除等非 untracked 项 | 65 |
| 执行前 Python / Godot 进程 | 无 |

本地 HEAD 与任务给出的 GitHub 最新 HEAD 一致。当前工作区存在大量历史 dirty，全部保留；未执行 `git reset`、`git clean`、`git stash` 或批量 `git restore`。

## 3. Batch D 原始测试名单及来源

来源：

`.ai/context/PHASE_1_68_3_1_PHASE_3_REGRESSION_DEPENDENCY_AUDIT.md` §7

原始清单：

```text
test_feature_behavior_evidence.py
```

原始依赖审计口径：

- Group D：全 Feature Behavior / Evidence，**1 项**；
- 使用现有 **900 秒**覆盖；
- 预计运行全部 23 个 Feature / 60 个 Behavior，并包含 instance/runtime evidence 复核；
- 必须单独运行，不与 Batch B / Batch F 重叠；
- 不根据 target 的 158 秒推断本测试耗时。

实际路径：

```text
.ai/tools/scene_composer/tests/test_feature_behavior_evidence.py
```

### 与 Batch B / Batch F 的关系

- Batch D 不包含 Batch B 的 8 个测试，未重复执行 Batch B；
- Batch D 共享 `.ai/tmp/behavior` 与仓库 `.godot` 缓存，已按串行执行；
- Batch B 的 PASS 只作为环境/前置基线，不作为 Batch D 的结果；
- Batch F 的 2 项测试未执行，没有把 Batch F 混入 Batch D。

## 4. 执行前审计

### 4.1 测试文件

| 项目 | 值 |
|---|---|
| 路径 | `.ai/tools/scene_composer/tests/test_feature_behavior_evidence.py` |
| 存在 | 是 |
| 大小 | 35950 bytes |
| SHA256 | `73d7c30518d2d417c9ad94c6188ff03e007084a7a9d51917696c3f850a1fc768` |

### 4.2 受保护文件 SHA256

| 文件 | SHA256 |
|---|---|
| `.ai/context/feature_index.json` | `1fdce0264e29c3dabcece0938da33e740be31f8c4d74b3bbe88527760f3b4fe4` |
| `.ai/context/feature_graph.json` | `b4ace8a9b069dfa01a112bc8d4c3af4b7c3f3393ae4642312698799b0de77d47` |
| `Features/FEATURE_SCHEMA.md` | `dca7c57accf7464ccd8f4919741a078c629cdbf661718440a8c5b31f01cb56fc` |
| `.ai/context/behavior_protocol.yaml` | `d2a480b068559124bb51d74782b6ec2d33c29135573f9a9f39aa491559eea778` |
| `.ai/tmp/p168/official/evidence/evidence_index.json` | `0e1f4ab03bab6442045eca3b56c88cf2ddc7116878428c52194196942e1ee910` |

### 4.3 Batch B 测试文件

执行前后均校验通过，8 个 SHA256 未变：

```text
test_runtime_instance_evidence.py       24f83762b8db0d2331b3c7294f7772dc23d8c8492c80a577fbe7945453e0c872
test_behavior_time_driven.py            50e8ce5e5c840dfe936436677f406d48eba97812fc2a7878a1e50c97c2ce00a2
test_chase_movement_behavior.py         dce38d35f1108c956f19668178bed74e419ccc1c0933843f645e00b0d79bbea5
test_condition_gate_behavior.py         825eb48e0d57a528427b19dfc658ae72bbff6e6e06237adcb2e0a4facb37276b
test_contact_damage_behavior.py         e2cae467fb4a6f3e932448aef69f954db8cfe5f97054155ed29e45a2e9d53949
test_health_behavior.py                 a11130ad01897be19806d69f1627afcef09b64f00297761df5e6a20144e1140b
test_health_bar_behavior.py             a56a70e2a34b3cbd15b6e18307f3674e81baa959894cede9d6b7a84b6e819a6e
test_stun_behavior.py                   1aec4b01a9486633b5220118461c49c2cd279befb580f368ad0aeea2dc0cfc20
```

### 4.4 完整性基线

| 清单 | 结果 |
|---|---|
| Feature `features_sha256.txt` | 265 OK / 0 FAILED |
| Historical Evidence / Attestation `historical_sha256.txt` | 828 OK / 0 FAILED |
| Critical `critical_sha256.txt` | 4 OK / 0 FAILED |
| Code `code_sha256.txt` | 3 OK / 0 FAILED |
| Protocol `protocol_sha256.txt` | 3 OK / 0 FAILED |

### 4.5 受保护目录基线

对以下路径生成 496 个文件的 SHA256 快照：

```text
Features/
Scenes/
.ai/context/
.ai/tmp/p168/official/
```

`.ai/evidence/` 当前不存在；没有把它误报为已审计路径。

### 4.6 Runtime 副作用预判

该测试的临时目录与 workspace 明确位于项目内：

- 测试临时目录：`.ai/tmp/behavior_tests_*`（运行后由测试删除）；
- 行为证据：`.ai/tmp/behavior/`（保留）；
- runtime instance 证据：`.ai/tmp/runtime-instance/`（保留）；
- composite 目录：`.ai/tmp/composite/`，本测试不应写入；
- Godot `user://`：通过项目内 `APPDATA` / `LOCALAPPDATA` 重定向。

执行前预存的 `behavior_tests_*` 目录数量为 **7**，没有清理。

## 5. 每项测试的执行命令

实际命令：

```text
env APPDATA=<project>/.ai/tmp/phase5_batch_d_logs_20261111/runtime_env/appdata \
    LOCALAPPDATA=<project>/.ai/tmp/phase5_batch_d_logs_20261111/runtime_env/localappdata \
    TEMP=<project>/.ai/tmp/phase5_batch_d_logs_20261111/runtime_env/temp \
    TMP=<project>/.ai/tmp/phase5_batch_d_logs_20261111/runtime_env/temp \
    TMPDIR=<project>/.ai/tmp/phase5_batch_d_logs_20261111/runtime_env/temp \
    PYTHONPYCACHEPREFIX=<project>/.ai/tmp/phase5_batch_d_logs_20261111/pycache \
    PYTHONUNBUFFERED=1 timeout 900s python -u \
    .ai/tools/scene_composer/tests/test_feature_behavior_evidence.py
```

标准命令模板：

```bash
PYTHONUNBUFFERED=1 timeout 900s python -u .ai/tools/scene_composer/tests/test_feature_behavior_evidence.py
```

## 6. 每项结果、退出码、PASS/FAIL、耗时

| # | 测试 | 状态 | 退出码 | PASS | FAIL | 开始 | 结束 | 耗时 |
|---:|---|---|---:|---:|---:|---|---|---:|
| 1 | `test_feature_behavior_evidence.py` | **VERIFIED_PASS** | 0 | 391 | 0 | 23:49:01 | 23:52:54 | 233s |

补充结果：

- 测试终态输出：`PASS: all behavior evidence checks passed`
- stderr：0 bytes
- stdout：403 行，其中 391 行为 PASS，0 行为 FAIL
- 没有 `SKIP` 标记
- 没有超时

## 7. 总体执行统计

| 状态 | 数量 |
|---|---:|
| VERIFIED_PASS | **1** |
| VERIFIED_FAIL | 0 |
| EXECUTION_BLOCKED | 0 |
| EXECUTION_TIMEOUT | 0 |
| UNKNOWN | 0 |
| NOT_EXECUTED | 0 |
| PASS 行总数 | **391** |
| FAIL 行总数 | **0** |
| 总耗时 | **233 秒** |

测试实际覆盖：

- 23 个带 `template.yaml` 的 Feature；
- 60 个 Behavior 契约；
- Case 1 的 60 个 `feature/behavior PASS` 检查；
- 6 个 Case 12 runtime instance 复核；
- Case 2–11、13 的负向对照、重放、CLI 与契约校验。

## 8. Runtime 副作用

### 8.1 预期产物

执行后：

| 路径 | 结果 |
|---|---|
| `.ai/tmp/behavior/` | 顶层条目 24761；相对测试开始有 **131** 个顶层条目为新增/更新，属于本次行为证据 |
| `.ai/tmp/runtime-instance/` | 顶层条目 2381；相对测试开始有 **6** 个顶层条目为新增/更新，对应 6 个 runtime instance 复核 |
| `.ai/tmp/composite/` | 顶层条目 1047；测试开始后新增 **0** |
| `.ai/tmp/behavior_tests_*` | 执行前后均为 **7** 个，预存目录未清理，测试自己的临时 workspace 已由测试删除 |
| `.ai/tmp/workspace-*` | 测试开始后新增/保留的运行中 workspace 数 **0** |
| 项目内 `runtime_env/` | 14 个 Godot/Python 运行文件，全部位于本次日志目录 |

### 8.2 C 盘隔离

测试进程使用项目内以下环境路径：

```text
APPDATA       -> .ai/tmp/phase5_batch_d_logs_20261111/runtime_env/appdata
LOCALAPPDATA  -> .ai/tmp/phase5_batch_d_logs_20261111/runtime_env/localappdata
TEMP / TMP    -> .ai/tmp/phase5_batch_d_logs_20261111/runtime_env/temp
PYTHONPYCACHEPREFIX -> .ai/tmp/phase5_batch_d_logs_20261111/pycache
```

项目内实际产生了 Godot `app_userdata` 日志与存档，说明 `user://` 重定向生效。测试自身的 stdout/stderr 和所有证据均位于项目内。

限制：Freebuff 后台命令包装器自身的宿主捕获文件不由测试代码控制，本次没有把它计入测试产物；该包装器输出不包含测试结果，结果以项目内日志为准。

### 8.3 真实项目文件

- `Features/`：496 文件受保护快照无变化；
- `Scenes/`：无变化；
- `.ai/context/`：无变化；
- `.ai/tmp/p168/official/`：无变化；
- 没有写入 Evidence Bundle、Manifest、Attestation 或 Review；
- 没有生成残留 `Scenes/E2eCompositeTestPlayer.tscn`；
- 没有删除或覆盖既有 dirty。

### 8.4 Runtime 前值限制

执行前保存了预存 `behavior_tests_*` 数量（7），但 `runtime_dirs_before.txt` 的完整 `behavior/`、`runtime-instance/` 顶层清单被后续写入覆盖，未能保留精确的 before 集合。执行后使用顶层计数与 `-newermt` 统计新增/更新时间，结论仅限“本次产生了行为/runtime 证据，未修改受保护项目文件”，不宣称已恢复完整 before 列表。这是本次审计的记录限制，不影响 PASS 判定。

## 9. Feature / Evidence / Attestation 完整性

### 9.1 Feature

```text
sha256sum -c .ai/tmp/p1683/baseline/features_sha256.txt
EXIT=0
OK=265
FAILED=0
```

### 9.2 Historical Evidence / Attestation

```text
sha256sum -c .ai/tmp/p1683/baseline/historical_sha256.txt
EXIT=0
OK=828
FAILED=0
```

### 9.3 Critical / Code / Protocol

| 清单 | 结果 |
|---|---|
| Critical | 4 OK / 0 FAILED |
| Code | 3 OK / 0 FAILED |
| Protocol | 3 OK / 0 FAILED |

### 9.4 Registry / 索引

| 检查 | 结果 |
|---|---|
| Registry Members | **31** |
| Scene Composer Eligible | **23** |
| `feature_index.json` | `1fdce026...4fe4`，未变 |
| `feature_graph.json` | `b4ace8a9...7d47`，未变 |
| `evidence_index.json` | `0e1f4ab0...e910`，未变 |

`.ai/evidence/` 不存在，因此没有可审计的该目录内容；历史 Evidence 由 828 项快照覆盖。

## 10. 受保护文件 SHA256 对比

### 10.1 关键文件

执行后：

```text
.ai/context/feature_index.json: OK
.ai/context/feature_graph.json: OK
Features/FEATURE_SCHEMA.md: OK
.ai/context/behavior_protocol.yaml: OK
.ai/tmp/p168/official/evidence/evidence_index.json: OK
```

### 10.2 受保护目录树

```text
before files = 496
after files  = 496
diff lines   = 0
```

`Features/`、`Scenes/`、`.ai/context/`、`.ai/tmp/p168/official/` 的逐文件 SHA256 完全一致。

### 10.3 测试文件

- Batch D 测试：`sha256sum -c` 通过；
- Batch B 8 个测试：`sha256sum -c` 通过；
- 测试没有被修改。

## 11. Git 工作区变化

| 项目 | 执行前 | 测试后 / 报告前 |
|---|---:|---:|
| HEAD | `71f6eef6...` | `71f6eef6...` |
| branch | `master` | `master` |
| staged | 0 | 0 |
| dirty | 1064 | 1064 |

测试执行没有新增或删除 Git 工作区条目。日志目录位于既有 `.ai/tmp` 忽略范围内，不改变 `git status --porcelain`。

当前 dirty 1064 包含：

- 本轮之前已有的历史 dirty；
- 用户刚加入的 `AI_ENTRY.md` §0 规则修改；
- 其他 Agent 的工作成果；
- 未跟踪的 Phase 1.68.3.1 历史报告。

本次报告新增后预计 dirty 为 **1065**：

```text
?? .ai/context/PHASE_1_68_3_1_PHASE_5_BATCH_D_REPORT.md
```

没有提交或推送 Git；没有修改 Batch B 报告。

## 12. 进程残留检查

- 执行前：无 Python / Godot 进程；
- 测试结束后：无 Python / Godot 残留进程；
- `process_after.log` 为空；
- 测试启动的 Godot 子进程、behavior workspace 和 CLI 子进程均随测试退出；
- 没有发现无法解释的后台任务。

## 13. 未直接审计的项目和风险

1. `.ai/evidence/` 路径不存在，无法对该目录做内容审计；历史 Evidence 已由 828 项快照覆盖。
2. 完整执行前 `.ai/tmp/behavior`、`.ai/tmp/runtime-instance` 顶层清单未保留，只保留了预存 `behavior_tests_*` 数量和执行后计数/时间统计。
3. Freebuff 后台命令包装器自身的宿主捕获目录不属于测试产物，未纳入项目内审计；测试自身的 stdout/stderr 和 Godot/Python 运行环境已重定向到项目内。
4. 测试使用共享 `.ai/tmp/behavior` 与 Godot `user://` 隔离目录；虽然本次串行执行且通过，后续批次仍需保持串行，不能据此推断并行安全。
5. 测试通过不等同于 Batch F 的 Composite/End-to-End 已通过；Batch F 仍未执行。

## 14. 最终判定

**PASS**

理由：

- Batch D 原始清单只有 1 项，实际只执行了该 1 项；
- `test_feature_behavior_evidence.py` 为 `VERIFIED_PASS`；
- 退出码 0，PASS 391，FAIL 0，耗时 233 秒；
- 无超时、无 SKIP、无 stderr、无残留进程；
- 23 个 Feature / 60 个 Behavior 全部纳入测试并通过；
- Feature 265/265 OK；
- Historical Evidence / Attestation 828/828 OK；
- Critical / Code / Protocol 全部 OK；
- Registry 31、Scene Composer Eligible 23；
- 496 个受保护目录文件哈希无变化；
- Batch D 测试文件与 Batch B 的 8 个测试文件哈希均未变；
- Git HEAD、branch、staged 未变，既有 dirty 全部保留；
- 未执行 Batch F，未自动修复、未自动重试、未提交或推送 Git。

报告完成后停止，等待负责人审查；不自动进入 Batch F 或其他批次。
