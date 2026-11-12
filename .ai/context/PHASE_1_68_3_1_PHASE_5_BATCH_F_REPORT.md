# Phase 1.68.3.1 — Phase 5: Batch F Report

## 1. 结论

| 项目 | 结果 |
|---|---|
| 阶段 | Phase 1.68.3.1 / Phase 5 / Batch F |
| 最终判定 | **PASS** |
| 执行测试数 | **2 / 2** |
| 通过测试数 | **2 / 2** |
| 失败测试数 | 0 |
| 超时 | 0 |
| BLOCKED | 0 |
| 总 PASS 检查数 | **177** |
| 总 FAIL 检查数 | **0** |
| 测试执行总耗时 | **156.638 秒** |
| 执行前 HEAD | `71f6eef61c1b203229e93a47a111f5ce040c587f` |
| 执行后 HEAD | `71f6eef61c1b203229e93a47a111f5ce040c587f` |
| 执行前 dirty | 1066 |
| 执行后 dirty | 1066 |
| staged | 0 |
| 残留 Python / Godot 进程 | 无 |

Batch F 严格按 Phase 3 §7 的原始名单和顺序执行，没有加入 `test_composite.py`，没有执行全量测试或其他 Batch，没有修改生产代码、测试、Feature、Scene、Protocol、Evidence、Attestation 或索引，没有提交或推送 Git。

执行后立即停止，等待负责人审查。

---

## 2. 授权与前置依据

负责人已明确单独授权执行 Phase 5 Batch F。执行前重新读取并核对：

- `AI_ENTRY.md`
- `AGENT_ONBOARDING.md`
- `.ai/context/PHASE_1_68_3_1_PHASE_5_BATCH_F_PRE_AUDIT.md`
- `.ai/context/PHASE_1_68_3_1_PHASE_3_REGRESSION_DEPENDENCY_AUDIT.md`
- `.ai/context/PHASE_1_68_3_1_PHASE_5_BATCH_B_REPORT.md`
- `.ai/context/PHASE_1_68_3_1_PHASE_5_BATCH_D_REPORT.md`

权威来源：

```text
.ai/context/PHASE_1_68_3_1_PHASE_3_REGRESSION_DEPENDENCY_AUDIT.md
§7 Batch F — Composite / End-to-End（2 个）
```

原始顺序：

```text
1. test_composite_behavior_evidence.py
2. test_slime_contact_arena.py
```

`test_composite.py` 属于 Batch A，未执行。

### 2.1 文档缺口

独立文件

```text
.ai/context/PHASE_1_68_3_1_PHASE_5_REGRESSION_PLAN.md
```

仍不存在。本次授权明确要求按 Phase 3 §7 执行，因此该文档缺口不构成执行阻断；没有自行创建替代计划，也没有扩大测试范围。

---

## 3. 执行前检查

### 3.1 工作区

| 项目 | 值 |
|---|---|
| HEAD | `71f6eef61c1b203229e93a47a111f5ce040c587f` |
| branch | `master` |
| upstream | `origin/master` |
| staged | 0 |
| porcelain dirty | 1066 |
| porcelain normal untracked | 1001 |
| untracked（all files） | 1953 |
| Python / Godot 进程 | 无 |
| 固定 fake workspace `999-ffffffffff` | **ABSENT** |

`untracked` 的两个计数口径不同：

- normal mode 以目录折叠显示，1001 项；
- all-files mode 展开目录内文件，1953 项。

这解释了与 Pre-Audit 中 `untracked 1000` 的差异：Pre-Audit 报告本身增加了 1 个 normal untracked 项，没有发现新增污染。

### 3.2 快照

执行前完成完整递归快照，覆盖：

```text
.ai/tmp/behavior/
.ai/tmp/runtime-instance/
.ai/tmp/composite/
.ai/tmp/composite_protocol_cases/
.ai/tmp/composite_bad_contracts/
.ai/tmp/composite_invalid_contracts/
.ai/tmp/slime_bad_contracts/
.ai/tmp/behavior_tests_*（7 个）
```

并保护：

```text
Features/
Scenes/
Orchestration/
Levels/
Systems/
Assets/
.ai/context/
.ai/tools/
.ai/tmp/p168/official/
project.godot
icon.svg
```

每条记录包含：

- 相对路径；
- 类型（dir / file / symlink / other / missing）；
- 大小；
- SHA256（普通文件）；
- `mtime_ns`；
- symlink target 与 link state；
- 可读性与错误原因；
- 空目录记录。

### 3.3 执行前快照结果

| 项目 | 结果 |
|---|---|
| stage | `pre_batch` |
| 时间 | 2026-11-12 22:20:11 — 22:23:56 |
| Runtime entries | 157,358 |
| Protected entries | 1,231 |
| 总 entries | 158,589 |
| Runtime bytes | 284,772,525 |
| 不可读项 | **0** |
| snapshot exit | 0 |

固定 `999-ffffffffff` 在快照前和快照后均不存在。

---

## 4. 隔离与执行方式

### 4.1 串行与独立进程

- 每项测试由独立 Python 进程执行；
- 第一项完全退出并完成 post 快照、哈希和差异检查后，才启动第二项；
- 未并行运行任何测试；
- 外层预算 300 秒；
- 测试内部 workspace import 预算按源码为 120 秒 / 180 秒。

### 4.2 项目内环境重定向

两项测试均在项目内运行，进程环境重定向为：

```text
APPDATA              -> .ai/tmp/phase5_batch_f_logs_20261112/runtime_env/appdata
LOCALAPPDATA         -> .ai/tmp/phase5_batch_f_logs_20261112/runtime_env/localappdata
TEMP / TMP / TMPDIR  -> .ai/tmp/phase5_batch_f_logs_20261112/runtime_env/temp
HOME / USERPROFILE   -> .ai/tmp/phase5_batch_f_logs_20261112/runtime_env/home
XDG_DATA_HOME        -> .ai/tmp/phase5_batch_f_logs_20261112/runtime_env/xdg_data
XDG_CACHE_HOME       -> .ai/tmp/phase5_batch_f_logs_20261112/runtime_env/xdg_cache
XDG_CONFIG_HOME      -> .ai/tmp/phase5_batch_f_logs_20261112/runtime_env/xdg_config
PYTHONPYCACHEPREFIX  -> .ai/tmp/phase5_batch_f_logs_20261112/runtime_env/pycache
PYTHONDONTWRITEBYTECODE = 1
```

Godot 4.7 console executable：

```text
F:\Godot_v4.7-stable\Godot_v4.7-stable_win64_console.exe
```

Python：

```text
F:\Program Files\Python3.12\python.exe
Python 3.12.10
```

没有使用 C 盘作为测试工作区、源码目录、日志目录或 Runtime 输出目录。

---

## 5. 测试结果

### 5.1 逐项结果

| # | 测试 | 状态 | Exit | PASS | FAIL | SKIP | 超时 | 开始 | 结束 | 耗时 |
|---:|---|---|---:|---:|---:|---:|---|---|---|---:|
| 1 | `test_composite_behavior_evidence.py` | **VERIFIED_PASS** | 0 | 100 | 0 | 0 | 否 | 22:25:27 | 22:26:52 | **84.458s** |
| 2 | `test_slime_contact_arena.py` | **VERIFIED_PASS** | 0 | 77 | 0 | 0 | 否 | 22:33:57 | 22:35:09 | **72.180s** |

合计：

- PASS：**177**
- FAIL：**0**
- SKIP：**0**
- 超时：**0**
- 测试执行总耗时：**156.638 秒**

### 5.2 终态输出

Composite：

```text
PASS: all composite behavior evidence checks passed
```

Slime：

```text
PASS: all slime contact acceptance checks passed
```

### 5.3 stdout / stderr

| 测试 | stdout | stderr |
|---|---|---|
| composite | `.ai/tmp/phase5_batch_f_logs_20261112/stdout/01_test_composite_behavior_evidence.stdout.log` | `.ai/tmp/phase5_batch_f_logs_20261112/stderr/01_test_composite_behavior_evidence.stderr.log` |
| slime | `.ai/tmp/phase5_batch_f_logs_20261112/stdout/02_test_slime_contact_arena.stdout.log` | `.ai/tmp/phase5_batch_f_logs_20261112/stderr/02_test_slime_contact_arena.stderr.log` |

- composite stdout：116 行，100 个 PASS，0 个 FAIL；
- slime stdout：91 行，77 个 PASS，0 个 FAIL；
- 两份 stderr 均为 **0 字节**；
- 没有 `SKIP:`；
- 没有 traceback / SCRIPT ERROR。

### 5.4 Runner 元数据

- `.ai/tmp/phase5_batch_f_logs_20261112/execution_metadata/01_test_composite_behavior_evidence.json`
- `.ai/tmp/phase5_batch_f_logs_20261112/execution_metadata/02_test_slime_contact_arena.json`
- `.ai/tmp/phase5_batch_f_logs_20261112/execution_metadata/01_runner.log`
- `.ai/tmp/phase5_batch_f_logs_20261112/execution_metadata/02_runner.log`

---

## 6. Git 状态

### 6.1 执行前后

| 项目 | 执行前 | 执行后 |
|---|---|---|
| HEAD | `71f6eef61c1b203229e93a47a111f5ce040c587f` | `71f6eef61c1b203229e93a47a111f5ce040c587f` |
| branch | `master` | `master` |
| staged | 0 | 0 |
| dirty（porcelain） | 1066 | 1066 |
| normal untracked | 1001 | 1001 |

`git_before.txt` 与 `git_after_02.txt` 的 `diff` 为空：Git 跟踪状态和未跟踪路径完全一致。

### 6.2 日志位置

```text
.ai/tmp/phase5_batch_f_logs_20261112/execution_metadata/git_before.txt
.ai/tmp/phase5_batch_f_logs_20261112/execution_metadata/git_after_01.txt
.ai/tmp/phase5_batch_f_logs_20261112/execution_metadata/git_after_02.txt
```

`.ai/tmp/` 被 `.gitignore` 忽略，因此测试日志和快照不会进入 Git 状态。报告生成后 dirty 预计变为 **1067**，唯一新增项应为 Batch F 报告。

没有执行：

```text
git reset
git clean
git stash
git restore
git commit
git push
```

---

## 7. 受保护文件 SHA256 比较

### 7.1 关键文件

| 文件 | 执行后 SHA256 | 是否变化 |
|---|---|---|
| `.ai/context/feature_index.json` | `1fdce0264e29c3dabcece0938da33e740be31f8c4d74b3bbe88527760f3b4fe4` | 否 |
| `.ai/context/feature_graph.json` | `b4ace8a9b069dfa01a112bc8d4c3af4b7c3f3393ae4642312698799b0de77d47` | 否 |
| `Features/FEATURE_SCHEMA.md` | `dca7c57accf7464ccd8f4919741a078c629cdbf661718440a8c5b31f01cb56fc` | 否 |
| `.ai/context/behavior_protocol.yaml` | `d2a480b068559124bb51d74782b6ec2d33c29135573f9a9f39aa491559eea778` | 否 |
| `.ai/tmp/p168/official/evidence/evidence_index.json` | `0e1f4ab03bab6442045eca3b56c88cf2ddc7116878428c52194196942e1ee910` | 否 |
| `test_composite_behavior_evidence.py` | `dc1a1ec1ba90d20d4314e6113c6288a0cf87fb62fc2f5d742eb44c2ee87bf004` | 否 |
| `test_slime_contact_arena.py` | `7cb3e03c8593b6fc50c06e7a5f0565263fe0d1f6ab4a34c3119c593090b0fb0a` | 否 |

### 7.2 完整受保护集合

| 比较 | added | removed | modified |
|---|---:|---:|---:|
| pre_batch → post_01 | 0 | 0 | 0 |
| post_01 → post_02 | 0 | 0 | 0 |
| pre_batch → post_02 | 0 | 0 | 0 |

受保护集合共 1,231 个条目（1,076 个普通文件、155 个目录），两次测试前后完全一致。

相关文件：

```text
.ai/tmp/phase5_batch_f_logs_20261112/pre_batch/protected_sha256.txt
.ai/tmp/phase5_batch_f_logs_20261112/post_01/protected_sha256.txt
.ai/tmp/phase5_batch_f_logs_20261112/post_02/protected_sha256.txt
.ai/tmp/phase5_batch_f_logs_20261112/diff/protected_added.tsv
.ai/tmp/phase5_batch_f_logs_20261112/diff/protected_removed.tsv
.ai/tmp/phase5_batch_f_logs_20261112/diff/protected_modified.tsv
```

---

## 8. Composite Runtime 差异

### 8.1 每项测试差异

| 区间 | added | removed | modified | protected changed | workspace removed |
|---|---:|---:|---:|---:|---:|
| pre_batch → post_01 | 59 | 0 | 17 | 0 | 0 |
| post_01 → post_02 | 60 | 0 | 7 | 0 | 0 |
| pre_batch → post_02 | **119** | **0** | **22** | **0** | **0** |

`post_01` 同时作为第二项的 pre-state：第一项结束后到第二项启动前，没有 Runtime 写入，第二项差异使用 `post_01 → post_02`。

### 8.2 累计新增

累计新增 **119** 个条目：

- 25 个新的 evidence run 目录；
- 94 个 evidence 文件（contract / result / stdout / stderr）。

全部位于：

```text
.ai/tmp/composite/<run_id>/
```

新增目录：

```text
.ai/tmp/composite/10584-11e30c4103-no_health-r1
.ai/tmp/composite/10584-1b7cdc1ece-slime_ok-r1
.ai/tmp/composite/10584-1b7cdc1ece-slime_ok-r2
.ai/tmp/composite/10584-2101d726c9-no_target-r1
.ai/tmp/composite/10584-6d64768b64-no_move-r1
.ai/tmp/composite/10584-ae6fa76d08-slime_contact-r1
.ai/tmp/composite/10584-b5d1a078eb-restored-r1
.ai/tmp/composite/10584-ced23b0704-slime_contact-r1
.ai/tmp/composite/10584-d8eee22539-no_group-r1
.ai/tmp/composite/10584-dbcae909bd-short-r1
.ai/tmp/composite/10584-ea9345222f-no_shape-r1
.ai/tmp/composite/10584-f2cb460bc3-muted-r1
.ai/tmp/composite/9800-1c67827029-escape_room-r1
.ai/tmp/composite/9800-1e14f27cab-stuck_door-r1
.ai/tmp/composite/9800-402f283d78-escape-r1
.ai/tmp/composite/9800-402f283d78-escape-r2
.ai/tmp/composite/9800-7b3052cc27-wrong_expectation-r1
.ai/tmp/composite/9800-bddd64f32c-escape_room-r1
.ai/tmp/composite/9800-c3ade75473-missing-r1
.ai/tmp/composite/9800-c5b5d1d781-escape_room-r1
.ai/tmp/composite/9800-e018502b97-precondition-r1
.ai/tmp/composite/9800-e5e6407b53-broken_link-r1
.ai/tmp/composite/9800-e7fa44d7bf-arena-r1
.ai/tmp/composite/9800-e7fa44d7bf-arena-r2
.ai/tmp/composite/9800-f290b4a48d-escape_room-r1
```

这些是测试证据保留，不是仓库源码；未清理。

### 8.3 累计修改

累计修改 **22** 个条目：

- 2 个目录的 mtime 因新增 evidence 改变：
  - `.ai/tmp/composite`
  - `.ai/tmp/composite/workspaces`
- 20 个文件内容被测试固定夹具覆盖。

文件列表：

```text
.ai/tmp/composite/zero-window-1/contract.json
.ai/tmp/composite/zero-window-1/result.json
.ai/tmp/composite/zero-window-1/stderr.log
.ai/tmp/composite/zero-window-1/stdout.log
.ai/tmp/composite/slime-path-escape/contract.json
.ai/tmp/composite/slime-path-escape/result.json
.ai/tmp/composite/slime-path-escape/stderr.log
.ai/tmp/composite/slime-path-escape/stdout.log
.ai/tmp/composite_bad_contracts/escape_room.yaml
.ai/tmp/composite_invalid_contracts/escape_room.yaml
.ai/tmp/composite_protocol_cases/bad_extends.yaml
.ai/tmp/composite_protocol_cases/bad_limit.yaml
.ai/tmp/composite_protocol_cases/bad_version.yaml
.ai/tmp/composite_protocol_cases/drifted_manifest.json
.ai/tmp/composite_protocol_cases/duplicate_key.yaml
.ai/tmp/composite_protocol_cases/limit_order.yaml
.ai/tmp/composite_protocol_cases/path_escape.yaml
.ai/tmp/composite_protocol_cases/unknown_denied_action.yaml
.ai/tmp/composite_protocol_cases/unknown_scene.yaml
.ai/tmp/slime_bad_contracts/slime_contact.yaml
```

解释：

- `zero-window-1` 与 `slime-path-escape` 是测试固定 evidence 目录，测试会覆盖其 contract/result/log；
- `composite_bad_contracts`、`composite_invalid_contracts`、`composite_protocol_cases`、`slime_bad_contracts` 是测试固定夹具；
- 覆盖属于预期 Runtime 副作用，不是正式 Feature/Scene/Protocol 修改；
- 没有删除任何既有 Runtime 文件。

### 8.4 未变化区域

以下区域在两次测试前后均无差异：

```text
.ai/tmp/behavior/
.ai/tmp/runtime-instance/
.ai/tmp/behavior_tests_49ypbs3j/
.ai/tmp/behavior_tests_7jtzqmb8/
.ai/tmp/behavior_tests_auh2pmtd/
.ai/tmp/behavior_tests_bdcvsk4v/
.ai/tmp/behavior_tests_caswmzhw/
.ai/tmp/behavior_tests_io0eph6s/
.ai/tmp/behavior_tests_rovyo_36/
```

没有把 Batch B / D 的 evidence 改写为 Batch F 的结果。

### 8.5 差异明细文件

```text
.ai/tmp/phase5_batch_f_logs_20261112/diff/runtime_added.tsv
.ai/tmp/phase5_batch_f_logs_20261112/diff/runtime_removed.tsv
.ai/tmp/phase5_batch_f_logs_20261112/diff/runtime_modified.tsv
.ai/tmp/phase5_batch_f_logs_20261112/execution_metadata/diff_01.json
.ai/tmp/phase5_batch_f_logs_20261112/execution_metadata/diff_02.json
.ai/tmp/phase5_batch_f_logs_20261112/execution_metadata/diff_cumulative.json
```

---

## 9. 历史 Workspace 保留

执行前、执行后和最终状态均为以下 5 个：

```text
12636-25bdc17e3c-test
12636-5cbe75aff5-cli
532-752811885d-cli
532-7b70d4179e-test
7276-bc3c6d345e-slime
```

| 检查 | 结果 |
|---|---|
| 历史 workspace 数量 | 5 → 5 |
| removed | 0 |
| added | 0 |
| 固定 `999-ffffffffff` | ABSENT → ABSENT |
| 测试自有 workspace 清理 | 两项均报告已清理 |

没有删除或覆盖任何历史 Composite workspace，也没有清理既有 Runtime 数据。

---

## 10. 进程与清理检查

| 时点 | Python / Godot 残留 |
|---|---|
| 执行前 | 无 |
| 第一项结束后 | 无 |
| 第二项结束后 | 无 |
| 最终 | 无 |

没有自动重试，没有清理现场，没有删除 evidence、workspace、固定夹具或日志。

---

## 11. 快照汇总

| stage | 时间 | Runtime entries | Protected entries | 总 entries | 不可读 | exit |
|---|---|---:|---:|---:|---:|---:|
| pre_batch | 22:20:11–22:23:56 | 157,358 | 1,231 | 158,589 | 0 | 0 |
| post_01 | 22:28:12–22:31:14 | 157,417 | 1,231 | 158,648 | 0 | 0 |
| post_02 | 22:35:57–22:40:06 | 157,477 | 1,231 | 158,708 | 0 | 0 |

Runtime inventory 已包含：

- 所有文件与目录；
- 空目录；
- symlink 类型、目标与状态；
- SHA256；
- `mtime_ns`；
- 不可读项（本次均为 0）。

完整快照与校验：

```text
.ai/tmp/phase5_batch_f_logs_20261112/pre_batch/
.ai/tmp/phase5_batch_f_logs_20261112/post_01/
.ai/tmp/phase5_batch_f_logs_20261112/post_02/
.ai/tmp/phase5_batch_f_logs_20261112/execution_metadata/final_checksums.txt
```

---

## 12. 异常、限制和未执行项

### 12.1 异常

没有发现：

- 测试失败；
- 超时；
- `SKIP:`；
- 受保护文件变化；
- 非预期 Runtime 变化；
- 历史 workspace 丢失；
- 残留测试进程；
- Git 状态变化；
- 无法解释的文件新增、删除或修改。

### 12.2 记录限制

- 独立的 Phase 5 Regression Plan 文件仍不存在；本次使用授权指定的 Phase 3 §7。该缺口不改变执行结果，但应在后续阶段文档中补齐或明确归档关系。
- 第二项的 pre-state 使用第一项的 `post_01` 快照；第一项结束到第二项启动之间没有 Runtime 写入，因此该快照就是第二项的准确前置状态。
- `.ai/tmp/` 被 Git 忽略，日志和快照不会出现在 `git status` 中；这是预期行为。

### 12.3 未执行

- 未执行 `test_composite.py`；
- 未执行 Batch A / B / C / D / R 的其他测试；
- 未执行全量测试；
- 未执行其他 Batch；
- 未提交、未推送；
- 未清理任何既有 Runtime 数据。

---

## 13. 最终判定

**PASS**

依据：

- Batch F 原始名单 2 项，实际执行 2 项；
- 两项 exit code 均为 0；
- 两项最终 PASS 输出完整；
- 100 + 77 = **177 PASS**；
- **0 FAIL**；
- 无超时、无 SKIP、无 BLOCKED；
- 受保护文件 0 变化；
- Git before/after 完全一致；
- 5 个历史 workspace 全部保留；
- 固定 fake workspace `999-ffffffffff` 未出现；
- 无 Python / Godot 残留进程。

Batch F 完成并停止。等待负责人审查最终报告并决定下一步。
