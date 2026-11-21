# Phase 1.57 — Evidence Cross-Validation 完成报告

> **FACT** = 有代码、命令输出或测试结果直接证明；**INFERENCE** = 基于实现得出的推断；
> **UNKNOWN** = 当前无法确认。

## 1. 审计基准与工作区状态

| 项 | 值 |
| --- | --- |
| HEAD | `dd3a0e4d5d0f6f47e3a9c729e3ce89190f019bd8`（与 Phase 1.56 报告基准一致） |
| 分支 | `master` |
| 任务开始时的未提交改动 | Phase 1.56 的产物（`M` validate.py / feature_behavior_evidence.py / probe / README，`??` check_behavior_evidence.py、test_behavior_evidence_stage.py）＋他人并行修改的 code_library / feature_index 等 |
| 是否触碰他人工作 | 否。未修改任何 `Features/`、`feature_index.json`、`code_library/`、`*.yaml` 协议或别的 Agent 的产物 |
| 是否执行 git add / commit / push | **均未执行** |
| 临时产物位置 | `.ai/tmp/p157/`（日志、真实证据包、篡改测试副本），未写入项目源码目录 |

另有 8 个上游未跟踪 Feature（anima_behaviour 等）仍在仓库中；本阶段不读取、不修改、不为其补声明。

## 2. 实际修改文件清单

| 文件 | 变更 |
| --- | --- |
| `.ai/tools/validator/execution_artifacts.py` | **新增**。`ArtifactResolver`（路径边界/解析）、`parse_execution_record`（产物 schema）、`cross_validate`（交叉核对） |
| `.ai/tools/validator/check_behavior_evidence.py` | 接入 `cross_validate`；`merge_verdicts`（FAIL > INCOMPLETE > PASS）；`artifact_roots` 参数与 `--artifact-root` CLI；`summary` 增加 `artifacts` / `cross_validated`；每条 check 记录 `artifacts` 计数 |
| `.ai/tools/validator/validate.py` | 新增 `--evidence-artifact-root`（透传授权根）；L4 阶段摘要行增加 artifacts / cross_validated |
| `.ai/tools/scene_composer/feature_behavior_evidence.py` | 采集侧记录 `artifact_digests`（每次重放产物的 sha256，被证据包 `payload_sha256` 覆盖） |
| `.ai/tools/validator/tests/test_evidence_cross_validation.py` | **新增** 交叉验证测试（A/B/C/D 四段） |
| `.ai/tools/validator/tests/test_behavior_evidence_stage.py` | fixture 现在附带真实结构的 `result.json` 与摘要；N14/N15/N16/N19 改为断言更严格的 FAIL；D 段授权根同时包含真实产物根 |
| `.ai/tools/validator/README.md`、`.ai/context/WORK_STATE.md`、`.ai/context/CURRENT_TASK.md` | 文档同步（新增能力、路径规则、信任边界） |
| `.ai/context/PHASE_1_57_COMPLETION_REPORT.md` | 本报告 |

未改：Evidence Schema 版本（仍为 `feature_behavior_evidence_bundle` / `schema_version: 1`）、协议文件、
`check_behavior_evidence.py` 的既有判定顺序、任何 Feature 实现。

## 3. Evidence 原始结构（FACT，读自真实证据包）

`bundle`：`schema` / `schema_version` / `bundle_id` / `generated_at` / `git_head` / `tool` /
`protocol{protocol_version, sha256}` / `evidence_level` / `summary` / `features[]` /
`integrity{algorithm, payload_sha256}`。

`features[].behaviors[]` 记录字段：`feature`、`behavior`、`action_id`、`scene_id`、`run_id`、
`status`、`reason`、`detail`、`evidence`、`action_executed`、`preconditions`、`action_parameters`、
`observation_window`、`expected[]`、`actual[]`、`first_observed_frame`、`replay_count`、
`replay_consistent`、`runs[]`、`evidence_paths{}`、**`artifact_digests{}`（本阶段新增）**。

`evidence_paths` 形如 `{ "<run_id>": {"contract": ..., "result": ...} }`，键是**单次重放**的
run_id（`<contract run_id>-r<index>`），值为该次运行的产物绝对路径。

## 4. result.json 原始结构（FACT，由 `probes/feature_behavior_probe.gd` 写出）

必需：`run_id`、`replay_index`、`feature`、`behavior`、`status`、`action_executed`、`actions[]`
（每条含 `type`/`params`/`executed`）、`checks[]`（`check`/`target`/`entry`/`expected`/`observed`/
`status`/`first_observed_frame`）。
可选：`scene`、`action_frame`、`observed_frame`、`waited_frames`、`window_frames`、
`advanced_frames`、`frame_budget`、`signals`、`baselines`、`preconditions`。

**关键事实**：一次 `--all` 采集里，每条 behavior 的每次重放各写一份 `result.json`，因此
“重放条数”和“逐次观测”在产物侧是可数的，不需要相信证据包。

## 5. evidence_paths 解析方式（FACT）

```text
evidence_paths[run_id]["result"]
        |
        v
ArtifactResolver._resolve_raw   （相对路径以 project_root 为基准）
        |
        v
os.path.realpath               （跟随符号链接后再判归属）
        |
        v
授权根包含判定（默认 <project>/.ai/tmp/behavior；可 --artifact-root 追加）
        |  越界 -> FAIL artifact_path_rejected
        v
证据目录自身禁用 / 文件名必须 == result.json / 必须是文件且 <= 8 MiB
        |
        v
JSON 解析 -> parse_execution_record（缺字段 -> INCOMPLETE artifact_invalid_schema）
```

## 6. 新增交叉验证架构（FACT）

```text
Evidence record ──┬─> judge_record（契约复算，Phase 1.56，不变）
                  └─> cross_validate（新）
                        ├── 产物解析（resolver）
                        ├── 执行标识 / Feature / Behavior 归属
                        ├── replay_count / replay_index
                        ├── action_executed + 动作序列（与契约 actions 对齐）
                        ├── 产物 checks ↔ 证据 actual[]
                        ├── 重算 replay_consistent
                        └── artifact_digests（内容完整性）
                  └─> merge_verdicts：FAIL > INCOMPLETE > PASS
```

`merge_verdicts` 的语义：契约复算已 FAIL（如 `contract_violation`）时保留更具体的结论；否则
交叉验证 FAIL 直接定为 FAIL；双方都无法判定时 INCOMPLETE；两者都通过才 PASS，detail 写明
`cross-validated against N execution artifact(s)`。

## 7. replay_count 验证（FACT）

- 从 `len(evidence_paths)` 与成功解析的产物条数得到**实际**重放次数（不读自报值做结论）。
- `replay_count != 产物条数` → `FAIL replay_count_mismatch`。
- `replay_index` 集合 ≠ `1..N` → `FAIL replay_index_mismatch`。
- 有产物读不出来时**不再**用条数判矛盾（否则会把“读不到”误报成矛盾），保留读取错误 → INCOMPLETE。

真实证据篡改 `t1`：`replay_count` 2→3，退出码 1，`FAIL replay_count_mismatch`。

## 8. replay_consistent 验证（FACT）

- 用每份产物的 `checks` 投影 `(check, target, entry, expected, observed, status)`（与采集侧
  `BehaviorRun.fingerprint` 同一组键，避免把帧号/耗时差异误判为不一致）。
- `len(set(fingerprints)) == 1` 即一致；与证据自报值不同 → `FAIL replay_consistency_mismatch`。

`t2`：自报 `replay_consistent: false`（产物一致），退出码 1，`FAIL replay_consistency_mismatch`。

## 9. action_executed 验证（FACT）

- 产物 `action_executed` 必须为 `true`；`actions[]` 非空且每条 `executed` 不得为 `false`。
- 产物记录的动作 `type` 序列必须与契约 `actions` 的前缀一致 → `FAIL action_sequence_mismatch`。
- 因此“只在证据里写 `action_executed: true`”不再够用：产物必须留下执行记录。

`t3`/真实重跑已覆盖；单测 B11 用 `action_executed: false` 的产物验证 `FAIL action_not_executed`。

## 10. 路径安全测试（FACT，`test_evidence_cross_validation.py` C 段）

| 用例 | 结果 |
| --- | --- |
| C1 `../evil/result.json` | `FAIL artifact_path_rejected` |
| C2 越界绝对路径 | `FAIL artifact_path_rejected` |
| C3 越界符号链接（`link -> ../evil`） | `FAIL artifact_path_rejected` |
| C4 指向目录 | `FAIL artifact_unsupported` |
| C5 指向证据目录自身 | `FAIL artifact_path_rejected` |
| C6 指向 `contract.json` | `FAIL artifact_unsupported` |
| C7 无 `evidence_paths`（旧格式） | `INCOMPLETE execution_paths_missing`（退出码 2） |

缺失文件 → `INCOMPLETE artifact_missing`；空文件 / 坏 JSON → `INCOMPLETE artifact_invalid_json`。

## 11. Evidence 篡改测试（FACT）

单测 D1：只把证据 `replay_count` 改成 3，产物不动 → `FAIL replay_count_mismatch`。
单测 B8/B9/B12/B13/B14 覆盖自报次数、自报一致性、摘要伪造、去摘要、跨 Feature 复制。
`t7`（真实证据，改 `run_id` 冒充新批次）→ 退出码 1 `FAIL artifact_run_mismatch`。

## 12. result.json 篡改测试（FACT）

单测 D2：只改产物 `checks`（证据与摘要不动）→ `FAIL artifact_digest_mismatch`。
`t3`（真实证据，改 `observed`）→ 退出码 1 `FAIL artifact_digest_mismatch`。
`t4`（把 `health/death` 的产物复制给 `health/damage`）→ 退出码 1 `FAIL artifact_run_mismatch`。
`t5`（删除产物）→ 退出码 2 `INCOMPLETE artifact_missing`。
`t6`（去掉 `artifact_digests`，模拟旧格式）→ 退出码 2 `INCOMPLETE artifact_digests_missing`。

## 13. 同时篡改的信任边界（FACT，不算检测成功）

单测 D3 / 真实证据 `t8`：同时改写证据 `actual[]`、产物 `checks` 与 `artifact_digests`，并重算
证据包 `payload_sha256` → Validator 仍返回 **PASS**（退出码 0）。

这是**预期未检出**：`SHA256` 与交叉验证只保证「内容一致 + 记录自洽」，不保证「来源真实」。
能同时改写实现、产物与证据包的人仍可伪造。回归测试把这一结果写成断言，并在输出中显式标注
`TRUST BOUNDARY`，**不把它计入检出率**（t8 被统计为 `undetected_by_design`）。

## 14. 真实端到端执行结果（FACT）

```bash
python .ai/tools/scene_composer/feature_behavior_evidence.py --all \
    --evidence-out .ai/tmp/p157/bundles_real --bundle-id p157-real
# -> summary {'checked': 60, 'pass': 60, 'mismatch': 0, 'insufficient': 0, 'invalid': 0}
#    23 features

python .ai/tools/validator/check_behavior_evidence.py \
    --evidence-dir .ai/tmp/p157/bundles_real --json .ai/tmp/p157/validator_real.json
# -> Behavior Evidence (L4): PASS
#    pass=60 fail=0 incomplete=0 (checked=60, artifacts=120, cross_validated=60)
#    EXIT=0
```

即：60 条行为全部由**真实 Godot 执行**产生，120 份 `result.json` 全部被 Validator 独立读取并
重算通过；这不是“静态读取旧证据”。

真实证据篡改套件（`.ai/tmp/p157/tamper_real.py`，隔离副本）：

| 用例 | 期望 | 实际退出码 | 结论 |
| --- | --- | --- | --- |
| t0 基线 | 0 | 0 | `PASS verified` |
| t1 改自报 replay_count | 1 | 1 | `FAIL replay_count_mismatch` |
| t2 改自报 replay_consistent | 1 | 1 | `FAIL replay_consistency_mismatch` |
| t3 改产物内容 | 1 | 1 | `FAIL artifact_digest_mismatch` |
| t4 换用他条产物 | 1 | 1 | `FAIL artifact_run_mismatch` |
| t5 删除产物 | 2 | 2 | `INCOMPLETE artifact_missing` |
| t6 去掉摘要（旧格式） | 2 | 2 | `INCOMPLETE artifact_digests_missing` |
| t7 冒充执行批次 | 1 | 1 | `FAIL artifact_run_mismatch` |
| t8 同步改写三者 | 0（设计上未检出） | 0 | `PASS verified` + 信任边界说明 |

`cases=9 detected=7 undetected_by_design=1 failed=0`。

## 15. 兼容性回归结果（FACT）

| 项 | 结果 |
| --- | --- |
| `test_behavior_evidence_stage.py`（1.56，含真实 Godot 缺陷注入 D 段） | **ALL PASS**（exit 0） |
| `test_evidence_cross_validation.py`（1.57） | **ALL PASS**（30 项检查） |
| `run_tests.py .ai/tools/validator/tests` | **9/9 PASS**（含上述两个文件） |
| `run_tests.py .ai/tools/feature_registry/tests` | **4/4 PASS** |
| `run_tests.py .ai/tools/evaluation/tests` | **2/2 PASS** |
| `validate.py` 默认运行 | 不执行 L4 阶段，输出无 `Behavior evidence` 行（C2 断言） |
| `validate.py --behavior-evidence` | 新增 `--evidence-artifact-root`，旧参数与退出码（0/1/2/3）不变 |
| 23 Feature / 60 Behavior 验证能力 | 未退化：真实全量 60/60 仍 PASS，且额外获得 120 份产物交叉核对 |

1.56 中有四条负向用例的**结论升级**（更严，不是放宽）：

| 用例 | 1.56 | 1.57 |
| --- | --- | --- |
| N14 证据 `actual[]` 被删减 | INCOMPLETE `observation_count_mismatch` | FAIL `observation_mismatch`（与产物矛盾） |
| N15 自报 1 次重放（产物 2 份） | INCOMPLETE `replay_missing` | FAIL `replay_count_mismatch` |
| N16 自报不一致（产物一致） | INCOMPLETE `replay_inconsistent` | FAIL `replay_consistency_mismatch` |
| N19 记录把观测抹成 null | INCOMPLETE `observation_insufficient` | FAIL `observation_mismatch` |

判定依据：这些都是「证据与独立产物互相矛盾」，属于 Phase 1.57 规定的 FAIL 语义；
`judge_record` 的原判定逻辑没有改动，无法判定的情形（如产物缺失）仍是 INCOMPLETE。

## 16. 测试发现与执行统计（FACT）

| 项 | 数值 |
| --- | --- |
| Python 测试文件（`.ai/tools/*/tests/test_*.py`） | 63 |
| Godot 测试文件（`Features/*/test_*.gd` + `Tests/test_*.gd`） | 58（Features 31 + Tests 27） |
| 测试文件合计 | 121 |
| 本阶段新增测试文件 | 1（`test_evidence_cross_validation.py`） |
| 本阶段新增/更新断言 | 30 项（A6 + B16 + C8 + D3 计 30 条 `ok()`） |
| validator 段 | DISCOVERED 9 / EXECUTED 9 / PASS 9 / FAIL 0 / INCOMPLETE 0 |
| feature_registry 段 | 4 / 4 / 4 / 0 / 0 |
| evaluation 段 | 2 / 2 / 2 / 0 / 0 |
| scene_composer 段 | 31 / 31 / 28 / 3 / 0（3 项上游未完成，见 §16.1） |
| e2e 段 | 1 / 1 / 1 / 0 / 0 |

> **FACT（与 1.55/1.56 计数差异）**：Godot 测试文件此刻为 **58** 而非 57。差额来自
> `Tests/test_e2e_probe_enemy.gd`——它是**未跟踪**（`??`）的自动生成文件
> （`test_generator/generate_scene_test.py` 输出），本阶段开始时不存在，运行期间被生成。
> 本阶段不删除、不 `git add` 它，只在执行统计中如实列出并单独跑一次（§16.2 第 11 段）。

### 16.1 慢段结果

- `scene_composer`：31 个测试文件，28 PASS / 3 FAIL（`test_feature_capability_adoption.py`、
  `test_feature_capability_pipeline.py`、`test_scene_composer.py`），退出码 1。
  三项失败的断言内容完全一致：8 个**未跟踪**的上游 Feature
  （`anima_behaviour`、`attribute_editor`、`audio_player_pool`、`blackboard`、`clean_copy`、
  `flying_letter`、`pedestal_interaction`、`pickable_audio`）声明为空且没有 `template.yaml`。
  磁盘上 32 个 Feature 目录中只有 23 个有 `template.yaml`。
- `e2e`：`test_end_to_end_generation.py` 1/1 PASS（退出码 0）。
  Phase 1.51.2 记录的两类失败（默认编码 `UnicodeEncodeError`、UTF-8 重跑时临时目录消失）
  在当前 HEAD 上**未复现**；本次以 `PYTHONIOENCODING=utf-8 PYTHONUTF8=1` 运行并通过，
  trace baseline 阶段在临时目录中完成 `--import` 后正常回收。

### 16.2 分段串行回归与并集证明（FACT）

所有段均以 `python -u .ai/tools/run_tests.py <filter>` 串行执行（`PYTHONIOENCODING=utf-8`），
逐段记录命令、发现数、执行数、结论与退出码：

| # | 段 | 命令（filter） | 发现 | 执行 | PASS | FAIL | INCOMPLETE | 退出码 | 日志 |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| 1 | validator | `.ai/tools/validator/tests` | 9 | 9 | 9 | 0 | 0 | 0 | `seg_validator.log` |
| 2 | feature_registry | `.ai/tools/feature_registry/tests` | 4 | 4 | 4 | 0 | 0 | 0 | `seg_feature_registry.log` |
| 3 | evaluation | `.ai/tools/evaluation/tests` | 2 | 2 | 2 | 0 | 0 | 0 | `seg_evaluation.log` |
| 4 | asset_registry | `.ai/tools/asset_registry/tests` | 11 | 11 | 11 | 0 | 0 | 0 | `seg_asset_registry.log` |
| 5 | gameplay_planner | `.ai/tools/gameplay_planner/tests` | 2 | 2 | 2 | 0 | 0 | 0 | `seg_gameplay_planner.log` |
| 6 | runtime | `.ai/tools/runtime/tests` | 3 | 3 | 3 | 0 | 0 | 0 | `seg_runtime.log` |
| 7 | scene_composer | `.ai/tools/scene_composer/tests` | 31 | 31 | 28 | 3 | 0 | 1 | `seg_scene_composer.log` |
| 8 | e2e | `.ai/tools/e2e/tests` | 1 | 1 | 1 | 0 | 0 | 0 | `seg_e2e.log` |
| 9 | Godot Features | `Features` | 31 | 31 | 31 | 0 | 0 | 0 | `seg_godot_features.log` |
| 10 | Godot Tests（批次被外部终止） | `Tests` | 89 | 37 | 37 | 0 | — | — | `seg_godot_tests.log` |
| 11 | 生成型探针测试 | `test_e2e_probe_enemy` | 1 | 1 | 1 | 0 | 0 | 0 | `seg_probe_enemy.log` |

Python 侧：9 + 4 + 2 + 11 + 2 + 3 + 31 + 1 = **63**，与 `.ai/tools/*/tests/test_*.py` 实际文件数一致；
PASS 60，FAIL 3（全部为段 7 的上游未完成 Feature）。

Godot 侧：31（段 9）+ 26（段 10 的 Godot 部分）+ 1（段 11）= **58**，与实际文件数一致，全部 PASS。

**并集**：121 个测试文件 = 63 Python + 58 Godot，全部至少执行一次；PASS 118 / FAIL 3。

**关于段 10（必须如实说明）**：`run_tests.py` 的 `filter_tests` 是路径子串匹配，filter `Tests`
同时命中 `.ai/tools/*/tests/*`，所以该批次实际发现 26 个 Godot + 63 个 Python（共 89）。
该批次在 Godot 26/26 全 PASS、Python 跑到 `asset_registry` 11/11 后**被外部终止**
（进程消失，日志停在 `[37/89]`），因此**不计为通过**；它执行过的文件已由段 4 与段 7 覆盖。
这里记录的是「26 个 `Tests/*.gd` 在本次 HEAD 上逐项 PASS」这一事实，而不是一次全量通过。

**去重与重叠**：段 4（asset_registry 11）与段 10 的 Python 部分重叠 11 个文件；
段 1/2/3/5/6/7/8 与段 10 **无**执行重叠（段 10 在到达它们之前已终止）。
并集按文件去重后即为上表 121 个文件，不存在未被任何段覆盖的测试文件。

**未覆盖/未执行**：无。`INCOMPLETE` / `unavailable` / `not_executed` / `TIMEOUT` 在执行记录中均为 0；
唯一的非正常终止（段 10）已在上文标注为**未完成批次**。

## 17. 未解决的信任问题（FACT / INFERENCE）

1. **来源真实性未解决（FACT）**：没有任何独立签发者，`SHA256` 只能证明内容一致。同步改写
   证据 + 产物 + 摘要仍 PASS（D3 / t8）。
2. **旧证据包不可复算（FACT）**：`schema_version 1` 且无 `evidence_paths` / `artifact_digests`
   的证据一律 INCOMPLETE——这是刻意的，不是回归。
3. **产物可被同权限者替换（INFERENCE）**：`artifact_digests` 存在证据包里，篡改者若能同时
   改证据包并重签，就能让任意产物“自洽”。要真正解决需要密钥管理与签名，本阶段明确不引入
   伪签名。
4. **执行环境未被记录**（INFERENCE）：当前 `result.json` 不含可核验的执行环境指纹
   （二进制哈希、宿主标识），因此无法区分“同一机器上的不同二进制”。

## 18. 验收矩阵

| 验收项 | 状态 | 证据 |
| --- | --- | --- |
| Validator 能解析 `evidence_paths` | ✅ | `ArtifactResolver`、A1/A5 |
| Validator 能读取真实 `result.json` | ✅ | §14 真实全量 120 份产物 |
| 执行标识交叉验证 | ✅ | B4/B5/t7 |
| Feature / Behavior 交叉验证 | ✅ | B6/B7/B14/t4 |
| `replay_count` 由产物重算 | ✅ | B8/t1 |
| `replay_consistent` 由观测重算 | ✅ | B9/t2 |
| `action_executed` 有真实记录支撑 | ✅ | B11/§9 |
| 执行批次验证 | ✅ | B5/t7 |
| 路径遍历被拒绝 | ✅ | C1 |
| 越界绝对路径被拒绝 | ✅ | C2 |
| 越界符号链接被拒绝 | ✅ | C3 |
| 缺失文件 → INCOMPLETE | ✅ | B1/t5 |
| 非法格式不会 PASS | ✅ | B2/B3/C6 |
| 只改 Evidence 能检测 | ✅ | D1 |
| 只改 result.json 能检测 | ✅ | D2/t3 |
| 同时改两者：明确揭示信任边界 | ✅ | D3/t8（记 PASS，标注未检出） |
| 不依赖采集器自报字段 | ✅ | judge + cross 双路，FAIL 不因自报而 PASS |
| 1.56 测试全部通过 | ✅ | §15 |
| 原有 Validator / Evidence 测试通过 | ✅ | validator 段 9/9 |
| 23 Feature / 60 Behavior 未退化 | ✅ | §14 |
| CLI 默认行为与退出码不变 | ✅ | C2/C3/C5 |
| 无意外修改他人产物 | ✅ | §1、git status 仅列本阶段文件 |
| 分段回归并集覆盖全部 121 个测试文件 | ✅（3 项上游失败） | §16.2 |

未满足项：**无**（“来源真实性”不在本阶段验收范围内，且已在 §17 明确标为未解决）。
已知非本阶段失败：`scene_composer` 3 项因 8 个未跟踪上游 Feature 缺 `template.yaml` /
能力声明而失败（UPSTREAM_INCOMPLETE）。失败原因不在 Phase 1.57 改动路径上（本阶段只改
Validator / 采集侧证据字段），且失败断言名与未跟踪目录一一对应（FACT）。

## 19. 下一阶段建议

1. **Phase 1.58 — Evaluation 消费证据**：让 `evaluation/runner.py` 读取 L4 结论与
   `summary.cross_validated`，把“行为正确性 / 证据完整性 / 交叉验证覆盖”分开计入指标，
   而不是只看测试是否通过。
2. **执行环境指纹（小改动，高收益）**：在 `result.json` 写入 Godot 二进制路径 + sha256 + 协议
   manifest 哈希，跨机器复核时能识别“换了二进制却仍说 PASS”。
3. **产物保留策略**：`.ai/tmp/behavior` 已积累 2 万+ 目录；证据包引用的是绝对路径，清理会
   让旧证据变 INCOMPLETE。建议按 bundle 归档产物（bundle 目录内 `artifacts/`），并在
   Validator 侧支持 `--artifact-root` 指向归档。
4. **签名留待有密钥管理方案时再做**：不要引入无密钥的伪签名。

## 20. 证据文件与命令

| 用途 | 路径 / 命令 |
| --- | --- |
| 真实证据包 | `.ai/tmp/p157/bundles_real/p157-real.json` |
| 真实采集日志 | `.ai/tmp/p157/collect_real.log` |
| Validator 机读结果 | `.ai/tmp/p157/validator_real.json` |
| 真实篡改测试脚本 | `.ai/tmp/p157/tamper_real.py` |
| 交叉验证单测日志 | `.ai/tmp/p157/xval_test.log` |
| 1.56 回归日志 | `.ai/tmp/p157/stage156_test.log` |
| 分段回归日志 | `.ai/tmp/p157/seg_{validator,feature_registry,evaluation,asset_registry,gameplay_planner,runtime,scene_composer,e2e,godot_features,godot_tests,probe_enemy}.log` |
| 未完成批次说明 | `seg_godot_tests.log` 停在 `[37/89]`（外部终止），不作为通过证据，仅证明 26 个 `Tests/*.gd` 逐项 PASS |

```bash
python .ai/tools/scene_composer/feature_behavior_evidence.py --all \
    --evidence-out .ai/tmp/p157/bundles_real
python .ai/tools/validator/check_behavior_evidence.py \
    --evidence-dir .ai/tmp/p157/bundles_real --json .ai/tmp/p157/validator_real.json
python .ai/tools/validator/tests/test_evidence_cross_validation.py
python .ai/tools/validator/tests/test_behavior_evidence_stage.py
python .ai/tmp/p157/tamper_real.py
python .ai/tools/run_tests.py .ai/tools/validator/tests
```
