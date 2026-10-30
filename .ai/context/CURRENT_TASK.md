# 当前任务

> 历史实验档案（Round 5 → 8 全部结论，含 Siege Gate 状态所有权、Round 7 Do Not Reuse、
> 测试证据与后续处置记录）已归档至 `.ai/memory/HISTORY.md`。

## 当前状态

Phase 1.38（Feature Instance Evidence Reconciliation）**已完成并实测**：新增
`.ai/tools/scene_composer/instance_evidence.py`，用真实入口 `.tscn` 核对 `template.yaml#instance`
（区分声明 / 静态场景 / 运行时 三级证据与 PASS/MISMATCH/INSUFFICIENT/INVALID/NOT_DECLARED），
并接入 Validator 第 7 阶段。新增 53 checks 回归测试；真实仓库负向对照（删除 PickupShape）
被抓住并 sha256 还原；相关 10 个测试与全量 **87/87 PASS**、Validator 0 error / 17 warning；
四条黄金基线未变；未提交、未推送。报告：[PHASE_1_38_AUDIT.md](PHASE_1_38_AUDIT.md)。
剩余风险：静态解析看不到运行时创建；`runtime_children` 可被滥用为 warning 豁免；挂载模式未进 compose。

Phase 1.37（Evaluation-Driven Capability Improvement）**已完成并实测**：基于 1.36 评估
证据定位主瓶颈为「单 Feature / 自包含实体生成第一跳被能力契约误判拦截」，根因是
Feature 元数据未声明入口场景自带的碰撞结构（`template.yaml` 缺 `instance:`）。
修复为 6 个 Feature 的数据声明 + 文档 + 新增回归测试（`test_feature_instance_evidence.py`），
**未改判定逻辑、生成产物零漂移**。评估：v2 任务集首次通过 **3/5 → 4/5**、计划修订
**2/2 → 1/1**、最终 **5/5**；v1 冻结任务集指标 **不变**（无回归）；自动修复 1/1、
回归缺陷 0/5 不变；四条黄金基线未变；未提交、未推送。
报告：[PHASE_1_37_AUDIT.md](PHASE_1_37_AUDIT.md)。全量测试 **86/86 PASS**。
顺带修复 D8（外部产物环判定误报菱形引用）；
未修复：D3（`--waves` 被忽略）、D4（信号连线/多实例）、D5（`--tests` 空断言）。

Phase 1.36（End-to-End Capability Evaluation）**已完成并实测**：新增
`.ai/tools/evaluation/`（固定 5 任务集 T1–T5 + 判定/指标口径 + 4 个真实 Godot 探针 +
所有权清理）。两次全量评估 **5/5 PASS**、首次通过率 **3/5**、框架自动修复 **1/1**、
计划修订 **2/2**、回归缺陷 **0**；全量回归 **85/85 PASS**；四条黄金基线未变；
未提交、未推送。报告：[PHASE_1_36_AUDIT.md](PHASE_1_36_AUDIT.md)。
F5 与 janitor CLI 仍未实施；`.godot` 并发治理仍未实施。

Phase 1.34（Unified Run Identity & E2E Concurrency Safety）此前已实施并验证：
L-9 = e2e 串行互斥锁（`testsupport/run_lock.py`：O_EXCL 获取 + 持有者身份校验 +
可证死亡回收 + fail-closed，覆盖创建→使用→清理完整生命周期，双真实进程竞争实测）；
L-8 = 统一运行标识契约（canonical `<pid>-<16 hex>`，Python/GD 同一格式；legacy 8-hex
受限识别、reclaim 一律拒绝）；L-10 保持保留。报告：[PHASE_1_34_AUDIT.md](PHASE_1_34_AUDIT.md)。

- **实测**：`test_run_workspace.py` **36/36 PASS**（W20–W23 契约 + L1–L8 锁，含双真实
  子进程竞争 L7）；6 个 GD 测试以新 token 全部 exit 0；e2e **173/173 PASS**（锁贯穿
  生命周期）；cross_layer 66；validate.py 0 error / 17 warning；四条基线 sha256/mtime
  未变。
- **全量单命令**：82 项中 80 PASS + 1 FAIL（evidence）+ 1 INCOMPLETE（cross_layer）
  ——均为环境删除守卫在 turn 计数超限后终止进程（两个测试独立运行均全过）；另修复
  了 1.33 会话遗留的 CONTRACT_INDEX.yaml 结构损坏（曾致 scene_intent_contract 与
  evidence 失败）。
- **未实施**：F5、janitor CLI、`.godot` 缓存并发改造（均未授权）。

Phase 1.33（F4-B Integration & Resource Ownership）**已实施并验证**：E2E 产物所有权
（显式清单 + 内容签名 + 本次运行缺席证明，fail-closed，O1/O2 断言）、6 个 GDScript
测试迁入 `.ai/tmp/runs/<pid>-<usec>/` 运行根（内容未变才删、外来残留只报告）、
`user://` 审计（runtime-fixture-* 所有权不可证 → 一律不清理）、`.godot` 缓存单独
风险评估（不纳入清理范围）。报告：[PHASE_1_33_AUDIT.md](PHASE_1_33_AUDIT.md)。

- **实测**：e2e **173/173 PASS（exit 0，含 O1/O2）**；6 个 GDScript 测试全部 exit 0
  且 `.ai/tmp/runs` 运行后 0 项、共享目录零残留；`run_tests.py validator` 9/9；
  `validate.py` 0 error / 17 warning；四条基线 sha256/mtime 与实施前一致。
- **新已知限制**：L-8 GD 侧运行根不被 Python 侧 stale 识别；L-9 两个 e2e 并发会互删
  签名匹配的同名产物（e2e 禁止并发）；F5 与 janitor CLI 仍未实施。
- 详见报告 §5（风险）、§9（未解决风险与所需授权）、§6（验证矩阵，含 NOT_EXECUTED/SKIP）。
- **2026-10-20 复核补记（报告 §11）**：在 Phase 1.34/1.35 之后的当前工作区上做了
  一次独立复核，修复了**一处所有权记账缺陷**——启动期扫描被签名验证后回收的残留
  没有重新登记为「本运行可拥有」，导致结束清理以「运行前就存在」为由拒删本轮
  重建的同名产物（e2e exit 1，一次成功的残留回收反而阻塞下一轮）；最小修复 +
  新增针对性测试 `validator/tests/test_e2e_ownership.py`（E1–E4）。修复后实测：
  e2e **173/173 PASS**（回收 19 个中断残留、工作区归零）、validator 段 **10/10**、
  全量 **83/83 PASS**；报告 §2.2 / §5.2 / §9 中被 1.34/1.35 改写的事实已在 §11.2 更正。

Phase 1.32（F4 Owned Cleanup）**F4-A 已实施并实测**：cross-layer 迁入每次运行专属目录，
所有权账本 + fail-closed 清理 + 残留报告/显式恢复。报告：[PHASE_1_32_AUDIT.md](PHASE_1_32_AUDIT.md)。
F4-B（e2e + 6 个 GDScript 测试 + `user://`）与 F5 **未实施**。

- 新增 `testsupport/run_workspace.py`：token = `pid-uuid8`；运行根 `.ai/tmp/runs/<token>/`；
  `ownership.jsonl` 追加记录 created/removed（sha256/bytes/mtime_ns）；删除前校验 token /
  路径 / 符号链接 / 摘要 / 元数据；账本缺失、损坏或冲突 ⇒ 拒绝删除；运行根仅在全部文件
  入账并验证后递归删除。
- cross-layer：33 个夹具 + 探针移入运行根；旧的 glob/前缀清理已删除；断言仍 65 项
  （输出 66 行 PASS）；启动时对其他 token 只打印 `STALE (not removed)`。
- 新增 `test_run_workspace.py` W1–W15（19 项）：隔离 / 幂等 / 篡改 / 越界 / 符号链接 /
  未入账 / 异常残留 / 显式 reclaim / 两个真实子进程并发 / 失败诊断。
- `.gitignore` 新增 `.ai/tmp/`；测试计数 Python 43→44、全量 81→82、validator 段 8→9。
- **实测**：`run_tests.py validator` 9/9 PASS（exit 0）；全量 `run_tests.py` **82/82 PASS，
  failed=0 incomplete=0 not_executed=0（exit 0）**；残留集成：`STALE` 只报告、reclaim 后余 0。
- **未做**：F4-B、F5；未强杀真实测试进程；四个基线 sha256/mtime 未变。

Phase 1.31（Execution Isolation & Safe Cleanup Design）为 F4 的审计与设计阶段，报告
[PHASE_1_31_AUDIT.md](PHASE_1_31_AUDIT.md)；本阶段按该报告 Step 2 实施 F4-A（未做 F5）。

Phase 1.30（Execution Isolation & Evidence Provenance）**F1–F3 + 文档已实施（实测）**，
F4（cross-layer 唯一令牌 / 所有权清理）与 F5 未获授权，未做。
审计报告与方案：[PHASE_1_30_AUDIT.md](PHASE_1_30_AUDIT.md)。

- **P0-1 守卫根因**：「单命令全量必被删除守卫终止」在当前运行时**不复现**——实测单命令
  2000 次工作区 `unlink()` 不被终止，`run_tests.py` 单命令 **81/81 PASS（exit 0）**。
  该守卫（`SAFE_DELETE_BULK_CONFIRM_REQUIRED`）属 WorkBuddy 宿主，不在仓库代码内；
  文档已改为「环境条件观测」，分段执行仍作为会触发守卫的宿主的兜底。
- **P0-2 E-1（高）**：`approve._validate_candidate` 原地覆写事件 `run_id`，`apply` 落盘 ⇒
  四个已批准基线的 `events[*].run_id` 全为 `candidate-check`，`source.trace_run_id`（run-xxxxxx）
  成为孤证；现已只在副本上规范化（U95/U99 守护）。
- **P0-2 E-2（中）**：`source.trace_run_id` 必须等于每个事件的 `run_id`，
  `trace_event_count`（存在时）必须等于事件数（U96–U98）。这是**一致性**校验，不是来源
  真实性证明；指纹无密钥，`--i-approve` 无身份认证——边界已写入 README。
- **未修复**：历史四个基线的 `run_id` 不可恢复且禁止重录，修复只对此后候选生效。

### Phase 1.29（已完成并实测）

Phase 1.29（Validator Trust Boundary & Evidence Integrity）**已完成并实测**
（本地工作区，未 commit；HEAD = `5e47bfd`，Phase 1.19–1.25 已在其中提交）。

### Phase 1.29 变更（信任边界与证据完整性）

**审计先行（只读）**：重读 trace_replay / trace_baselines / approve_trace_baselines /
run_tests 与全部调用方，输出信任边界图与入口清单（三条应成立的不变量：I1 合法性、
I2 审批绑定、I3 证据完整）。审计确认四处缺陷，另在实施中发现第五处（L3），全部有实测复现：

- **H1（高）证据完整性**：`run_tests.classify(0, "SKIP: …\nPASS: …")` = **PASS**——e2e 集成
  套件在 Godot 缺失时跳过 T4–T12（黄金基线捕获与比较整段）仍 `return 0`，
  cross-layer 跳过 C1–C8 后也 `return 0`；`--python-only` 下 `unavailable` 恒为空，
  甚至可输出 ALL PASS（exit 0）。实测 `classify(0, "")` 也是 PASS。
- **M2（中）审批绑定**：候选若不带 `candidate_fingerprint_scheme`、且指纹只能在 scheme 1 下
  复算，review/apply 均 exit 0，而 apply 按当前方案写入记录 → 写入后的基线
  `matching_fingerprint_schemes` = `[1]`（记录方案无法复算内容）；与文档「scheme 1 仅用于
  验证历史基线」矛盾。
- **M3（低–中）跨入口退出码不一致**：同一「trace 文件不存在」在 `trace_replay.main()` 是
  输入错误 **2**，在 `trace_baselines.compare_files()` 是 `INVALID_TRACE` **1**。
- **L1（低）候选身份未绑定**：`apply --candidate <目录> --scenario waves` 配一个名为
  `waves.candidate.json`、内容 `single_stage_boss` 的候选 → exit 0 且写入
  `single_stage_boss.json`（CLI 声明被静默忽略）。
- **L2（低）apply 读候选异常**：非法 JSON 候选→ `JSONDecodeError` 回溯；review 同一输入是
  干净诊断 + exit 2。
- **L3（低，实施中发现）**：`--candidate <文件> --scenario <id>` 被当成目录拼接成
  `<文件>/<id>.candidate.json`，文档化的用法静默失败（exit 2 “not found”）。

修复（均为最小必要；生产 GDScript 未改）：

1. `run_tests.classify`：**退出码 0 且自报 `SKIP:` ⇒ INCOMPLETE**；非 0 仍先看失败标记判
   FAIL（skip 不得把断言失败降级）；诊断带上跳过条数（`reported N skipped check(s)`），
   使 PASS/INCOMPLETE 可追溯到实际执行。
2. 审批入口：新候选**必须声明当前指纹方案**（缺失/未知/废弃 ⇒ 拒绝）；`--scenario` 必须与
   候选内容 `scenario_id` 一致（不一致 ⇒ 输入错误 exit 2）；候选读取统一为干净诊断 +
   exit 2；`--candidate <文件> --scenario <id>` 按文件处理。
3. M3：**不改变退出码**，而是把映射写进 docstring 与 README 并用测试锁定（CLI 兼容优先）。

未修复且经评估不做的项：`source.captured_by` / `trace_run_id` 是自报文本，仓库内无密码学
来源证明（需外部签名机制）；`expected_final_state` 与自身事件的一致性未加校验（属
fail-safe 方向：元数据不一致只会多报差异，不会掩盖回归）。两者均如实记录，不引入新机制。

### 本次实测（Phase 1.29，2026-10-19，全部为真实退出码）

| 入口 | 结果 | 退出码 |
| --- | --- | --- |
| `validator/tests/test_orchestration_trace.py` | R1–R80 全 PASS | 0 |
| `validator/tests/test_trace_baselines.py` | U1–U94 全 PASS（含新增 U86–U94） | 0 |
| `validator/tests/test_run_tests_evidence.py`（新增） | E1–E7 全 PASS（含真实 run_python_test 子进程路径、main() 空选择非 0 与无残留断言） | 0 |
| `run_tests.py`（全量入口） | completed=81/81 passed=81 failed=0 incomplete=0 unavailable=0 not_executed=0 | 0 |
| 独立 E2E `e2e/tests/test_end_to_end_generation.py` | 171 PASS，0 FAIL，0 SKIP（T5a–T5d 四基线逐事件 PASS） | 0 |
| H1 端到端负向对照（临时 skip-reporting 测试，用后删除） | `INCOMPLETE …(exit=0; reported 1 skipped check(s))`，passed=0 incomplete=1（修复前为 PASS/0） | 1（预期非 0） |
| `validator/validate.py` | 0 error / 17 warning（与 Phase 1.27/1.28 一致） | 0 |
| `test_cross_layer_contract.py` / `test_unified_validator.py` | 66 PASS / 36 PASS | 0 |
| 基线核对 | 四个基线可回放 + 自比较 PASS + 指纹可复算（U66/U67/U84；T13 断言 bytes+mtime 未变） | 0 |

### Phase 1.28 变更（跨模式语义一致性）

**审计先行**：先做只读审计（跨模式事件矩阵 + 规则冲突清单），确认可复现缺陷后只改校验器
与文档，不改 GDScript 生产行为，不重录任何基线。审计发现的越权缝隙：

- **C1** 阶段事件无模式门：waves / holdout trace 可携带 `stage_*` 并被接受；
- **C2** boss 未校验阶段数与 `data.stage_count` 的一致性；
- **C3** 终结 `reason` 无模式校验（holdout 可声称 `boss_defeated` 胜利）；
- **C4** `data.mode` 缺失 / 非法时**所有**模式门失效（同一条 trace 可同时装下 boss 死亡 +
  完整波次链 + 生成调度 + 阶段链 + victory）；
- **C5** `validate_baseline` 只做结构校验、不回放 → 由不可达 trace 构造的基线可被批准，
  `compare(同一条非法 trace)` = **PASS / exit 0**。

修复（最小必要，四个新拒绝码 + 一个基线契约）：

1. `orchestration_started.data.mode` 必须显式声明为 boss / waves / holdout
   （`invalid_start_mode`，模式未知即停止解释）——旧 trace 均在首事件声明 mode，四个真实
   基线一律声明。
2. 阶段事件仅 boss 且 `data.stage_count > 0`（`stage_event_outside_boss_stages`）；
   `stage_index` 必须小于声明阶段数（`stage_start_outside_declared_count`）。
3. 终结原因白名单（取值来自 `LevelOrchestrator` 实际写入点）：
   `victory_reason_outside_mode` / `failure_reason_outside_mode`；boss = `boss_defeated`，
   waves = `exit_reached_after_unlock` / `all_waves_cleared`，holdout = `survive_duration`；
   失败共有 `player_died` / `setup_failed` / `forced`，`wave_timeout` 仅 waves。
4. `validate_baseline` 结构校验通过后必须回放事件（错误前缀 `events must replay:`）：
   手改 / 拼接出的非法基线 → `INVALID_BASELINE`（exit 2），不再把「基线不可能发生」错报成
   真实 trace 的回归。

测试与证据：R68–R80（回放契约：三向跨模式拒绝、模式门正例、阶段数一致性、reason 白名单、
无 mode 逃逸口回归守卫、四条真实捕获链仍可回放）、U77–U85（回放器与比较器对同一非法语义
给出同一可解释理由；非法基线拒绝；黄金集合无跨模式泄漏）。真实 Godot 证据仍由四个真实捕获
基线与 `Tests/test_holdout_trace.gd` / `Tests/test_waves_exit_gate.gd` / boss 编排用例承担——
不拿手工 JSON 充当生产行为证据。

兼容性：**零重录**。boss / waves 事件字节不变；`single_stage_boss`（stage_count = 0、不含
阶段事件）与 holdout v1 / v2 兼容策略均不受影响；四个基线下仍可回放且自比较 PASS。

### 本次实测（Phase 1.28，2026-10-19，全部为真实退出码）

| 入口 | 结果 | 退出码 |
| --- | --- | --- |
| `validator/tests/test_orchestration_trace.py` | 80 项 PASS（R1–R80，含新增 R68–R80） | 0 |
| `validator/tests/test_trace_baselines.py` | 85 项 PASS（U1–U85，含新增 U77–U85） | 0 |
| `run_tests.py --godot-only` | 38/38 PASS（0 FAIL / 0 INCOMPLETE） | 0 |
| `run_tests.py --python-only` | 42/42 PASS（含 E2E） | 0 |
| `run_tests.py`（全量入口） | 80/80 PASS，completed=80 passed=80 failed=0 incomplete=0 unavailable=0 not_executed=0 | 0 |
| 独立 E2E `e2e/tests/test_end_to_end_generation.py` | 171 PASS，0 FAIL，0 SKIP（T5a–T5d 四个基线逐事件 PASS） | 0 |
| `validator/validate.py` | 0 error / 17 warning（与 Phase 1.27 一致） | 0 |

修复前的负向对照（共享口，均在临时脚本中复现，未写入仓库）：C1–C4 的非法 trace
`ok=True`；C5 的 `compare(不可达基线, 同一条非法 trace)` = **PASS / exit 0**；
修复后同样输入分别得到 `stage_event_outside_boss_stages` 等新拒绝码与
`INVALID_TRACE` / `INVALID_BASELINE`（exit 1 / exit 2）。

### Phase 1.27 变更（holdout 事件级回归保护）

**审计结论（先读代码、后改代码）**：holdout 真实状态机只有四个转换——`start()`
（→ Playing，计时归零）、每帧计时、`_run_spawn_schedules` 产出敌人、以及终结
（期满 → `level_victory(survive_duration)` / 玩家死亡 → `level_failed(player_died)`）。
Phase 1.26 前 trace 里只有 `orchestration_started` 与终结事件，**生成调度完全没有
事件级保护**（生成停止 / 间隔与上限被改不可检测），失败路径也无 trace 级测试。

1. **新增一个语义事件** `spawn_schedule_started`（`LevelOrchestrator._run_spawn_schedules`
   真实产出边界 + `_spawn_schedule_started` 幂等守卫，每条调度至多一次）：只覆盖
   有明确业务语义的转换；**不虚构**holdout 不存在的中期状态（delay 未到点的调度
   不产生事件，测试 H2 锁定）。
2. **回放规则**：`spawn_event_outside_holdout_mode`（只允许 holdout）、
   `invalid_spawn_event`（data 形状 / 不得携带阶段身份）、`duplicate_spawn_schedule`
   （同一索引不得重复）；回放结果新增 `spawn_schedules_started`。R62–R67 锁定，
   含 legacy holdout trace（无调度事件）仍可回放的兼容性。
3. **真实 Godot 测试** `Tests/test_holdout_trace.gd`（H1–H7）：正常完成链
   （started → schedule0 → victory）、不可达调度不产生事件、期满前玩家死亡 →
   `level_failed(player_died)` 唯一且最后、胜利后再死亡 →
   `duplicate_event_ignored(player_death)` 且终结仍唯一、期满前不结算、序号/时间戳契约、
   临时配置与导出文件清理。事件均经生产导出接口 `export_trace_json` 读取；
   用例带「完成计数」守卫，运行时错误导致的协程中断会被记为失败（不假通过）。
4. **holdout 黄金基线重批为 v2**（3 事件：started → spawn_schedule_started(0) → victory）：
   真实沙箱捕获 → candidate → review（展示 approved→candidate 差异）→ apply --i-approve 显式批准；
   新内容指纹 `b62cb26f…`（scheme 2）、`previous_baseline_version: 1`、捕获 run `run-675705`
   （另有独立复核捕获 `run-679135`，3/3 PASS）。旧 v2 比较前的
   捕获对新事件报 `EVENT_EXTRA / REGRESSION exit 1`——即新保护确实生效。
5. **探针证据修正**：`holdout_trace_probe.py` 的 `probe_metrics.trace_events` 此前恒报 0
   （与 `trace_event_count` 矛盾）；现由导出 trace 文档统计，基线证据自洽（3 = 3）。
6. **比较器用例** U71–U76：holdout v2 事件链与覆盖声明、自定义事件回放 PASS、
   旧 v1 形态（无调度事件）= `EVENT_MISSING` exit 1、改 interval = `DATA_FIELD_CHANGED`
   exit 1、重复调度事件 = `TRACE_INVALID(duplicate_spawn_schedule)` exit 1。

### 本次实测（2026-10-18，Godot 4.7.stable.official.5b4e0cb0f）

| 入口 | 结果 | 退出码 |
| --- | --- | --- |
| `Tests/test_holdout_trace.gd`（新增） | H1–H7 通过 | 0 |
| `run_tests.py --godot-only` | 38/38 PASS（含新增测试） | 0 |
| `test_orchestration_trace.py` | 68 PASS（R1–R67） | 0 |
| `test_trace_baselines.py` | 77 PASS（U1–U76） | 0 |
| 独立 E2E | 171 PASS，0 SKIP（T5d holdout v2 逐事件 3/3） | 0 |
| `trace_baseline_capture.py holdout` | 3 事件真实捕获（run-679135），metrics.trace_events=3 | 0 |
| 全量入口 `run_tests.py` | 80 PASS / 0 FAIL / 0 INCOMPLETE（80 项） | 0 |
| `validator/validate.py` | 0 error / 17 warning（历史基线不变） | 0 |

---

Phase 1.26（Semantic Trace Closure & Repository State Consistency）**已完成并实测**
（本地工作区，未 commit；HEAD = `5e47bfd`，Phase 1.19–1.25 已在其中提交）。

Phase 1.25 的实际状态更正：其代码**已随 `5e47bfd` 提交**，此前文档标注的「未 commit」
不成立；当前唯一未提交的用户自有修改是 `.workbuddy/memory/2026-10-18.md`（本阶段未触碰）。

### Phase 1.26 变更

0. **状态一致性**：状态文档按 `git log` / `git status` 实际结果改写，不再把「已提交」写成
   「未提交」，也不把提交说明当成测试通过的证据。
1. **waves v2 覆盖声明修正**：`.ai/tools/validator/baselines/waves.json` 的 `coverage`
   不再声称「trace 契约当前不含波次事件」，改为按真实事件链描述（事件级保护与探针度量
   断言分开写）；**事件内容与指纹未变**（未重录、未重新批准），批准记录新增
   `coverage_revised_at` / `coverage_revision_note` 说明这次只改了声明文本。
2. **回放契约收紧**：waves（仅当 trace 含波次事件）中 `reason = exit_reached_after_unlock`
   的 `level_victory` 必须已有 `exit_unlocked`（`victory_without_exit_unlock` 拒绝）；
   旧 trace（无波次事件）不被事后套用；`all_waves_cleared` 直接胜利路径不经过出口，
   不受影响。R58–R61 锁定这两条语义（含向后兼容与“只删最后一个 wave_cleared”）。
3. **真实 Godot 逃逸注入**：新增 `Tests/test_waves_exit_gate.gd`（G1–G7）。出口锁定时把
   玩家注入出口区（真实 `Area2D` body_entered 路径）→ state 仍 Playing、无 `level_victory`、
   门不开、trace 记 `invalid_transition_rejected(exit_locked)`；清空最后一波后
   `exit_unlocked` 晚于最后一个 `wave_cleared`；随后经真实输入走进出口区才产生唯一的
   `level_victory(exit_reached_after_unlock)` 并位于最后一个事件。事件全部来自生产导出
   接口 `TimedCombatArena.export_trace_json`，不手工拼装。
   **G7 同时发现并修复了一个真实缺口**：原守卫只检查「门未开」，宿主不注入
   `exit_door`（`exit_door == null`）时该检查被跳过 → 波次未清空也能胜利，且 trace
   里会出现「无 `exit_unlocked` 的出口胜利」。修复（最小边界改动，
   `Orchestration/level_orchestrator.gd`）：新增 `_waves_all_cleared()` 语义判定并在
   出口区入口强制 wave 完成条件（不依赖门对象）；全波次清空时的解锁边界（信号 +
   trace 事件）也不再要求门存在。boss / holdout / 直接胜利路径行为不变。
   **负向对照（2026-10-18）**：临时移除该守卫后 G7 以 exit 1 失败（trace 变为
   started→wave_started→level_victory，即 0 波次未清即胜利），证明用例对守卫有负载；
   随后按字节还原文件（sha256 一致 0b36f63e…）并重跑 G1–G7 = PASS。
4. **批准记录可追溯**：指纹方案版本化（scheme 1 = Phase 1.23 含 `scenario_id`；scheme 2 =
   Phase 1.24+ 不含）。两条 boss 基线的历史指纹此前无法用当前工具复算，现按 scheme 1
   验证通过；新候选记录 `approval.candidate_fingerprint_scheme`。U66/U67 锁定。
5. **测试入口分类**：`.ai/tools/run_tests.py` 区分 PASS / FAIL / INCOMPLETE（超时、被外部
   终止、无判定输出），三者中任一非 PASS 都使总入口退出 1；汇总打印
   `completed/passed/failed/incomplete/unavailable/not_executed`。清理守卫保持不变。
6. **E2E 残留修复**：实测发现探针删除 `.gd` 后遗留 `Tests/e2e_behavior_probe.gd.uid`（孤儿
   `.uid` 未被任何断言覆盖）。清理与 Z1 断言已补齐（`.uid` 一并删除并纳入断言）。

### 本次实测（2026-10-18，本机 Godot 4.7.stable.official.5b4e0cb0f）

| 入口 | 结果 | 退出码 |
| --- | --- | --- |
| `Tests/test_waves_exit_gate.gd`（新增） | G1–G7 通过（含无门宿主） | 0 |
| `run_tests.py --godot-only` | 37/37 PASS（含新增测试） | 0 |
| `run_tests.py`（全量单命令，79 项） | 79 PASS / 0 FAIL / 0 INCOMPLETE | 0 |
| `test_orchestration_trace.py`（回放单测） | 62/62 PASS（R1–R61） | 0 |
| `test_trace_baselines.py`（比较器/批准） | 71/71 PASS（U1–U70） | 0 |
| 独立 E2E | 171 PASS，0 SKIP（T5a–T5d 四模式逐事件比较全过） | 0 |
| `test_level_planner.py` | 134 PASS | 0 |
| `test_cross_layer_contract.py` | 66 PASS | 0 |
| `test_plan_generator.py` / `test_composite.py` | 25 / 17 PASS | 0 |
| `test_binding_scope.py` / `test_binding_schema_checks.py` | 29 / 14 PASS | 0 |
| `test_unified_validator.py` | 36 PASS | 0 |
| `validator/check_level.py`（三个发布关卡） | 全部通过 | 0 |
| `validator/validate.py` | 0 error / 17 warning（历史基线不变） | 0 |

真实捕获复验：`trace_baseline_capture.py waves` 在**编排器守卫修复前后各跑一次**
（run-626807 / run-588990），两次都是 7 事件且与 waves v2 基线逐事件 PASS（7/7）——
说明修复不改变正常路径的事件流，无需重录基线。

全量单命令本次实测未被环境的批量删除守卫终止（历史记录中的该限制本次未复现）；
即使复现，入口也会把被杀的测试归为 INCOMPLETE 并返回 1，不会误报通过。

### Phase 1.25 变更摘要（已提交于 5e47bfd）

1. **waves 语义事件（v1 加性扩展，schema_version 仍为 1）**：LevelOrchestrator 在真实
   转换边界新增三种事件——`wave_started`（_start_wave，data: wave/total/enemies）、
   `wave_cleared`（_advance_wave，_traced_cleared_wave 幂等守卫）、`exit_unlocked`
   （exit_door.set_open(true) 边界）。真实捕获 trace 从 2 事件升至 7 事件语义链：
   started→wave0→clear→wave1→clear→exit_unlocked→victory。
2. **回放规则**：波次事件仅限 waves 模式（wave_event_outside_waves_mode）；索引递增
   与清空约束（wave_start_before_clear / wave_start_out_of_order / wave_clear_mismatch）；
   exit_unlocked 至多一次且须在全部波次清空后（duplicate_exit_unlock /
   exit_unlocked_before_final_clear）；waves 胜利前须清完全部波次
   （victory_before_all_waves_cleared）；data.total 首现后固定（wave_total_mismatch）。
   **向后兼容**：旧 trace（无波次事件）回放行为不变——四条既有基线全部验证仍可回放。
3. **holdout 审计结论**：开始与计时是同一原子转换（orchestration_started reason=holdout），
   完成已有 level_victory(survive_duration)——按「不虚构不存在的状态」原则不新增事件，
   holdout 基线保持 v1。boss 基线零重录。
4. **基线**：waves 经 candidate→review→apply 显式重批为 **v2**（7 事件）；boss/holdout
   不变。批准记录含指纹与来源。
5. **测试**：回放器 R44–R57（14 项新规则，58/58）；比较器 U57–U63（分层语义：回放非法
   突变 = INVALID_TRACE、回放合法语义变化 = REGRESSION，均 exit 1；64/64）；e2e 独立
   **171/171 PASS**（T5a–T5d 四模式逐事件比较，含 waves v2）；全量单命令 79 项中
   78 PASS（e2e 超时覆盖提至 1800s 后通过；唯一失败 = 环境守卫杀 cross_layer 清理阶段，
   其断言全过）；Godot 八个编排专项全部 exit 0（行为兼容）；unified 36、cross_layer 66、
   composite 17、level_planner 134；
   validate.py 0 error / 17 warning（基线不变）。

## 下一阶段方向

路线图已记录于 `.ai/context/ROADMAP.md`（P0：Feature Registry / Game Design Skill / Scene Composer；
P1：Runtime Debug Agent / Asset Intelligence；P2：Feature Migration System / Multi-Agent Workflow）。
P0-1 Feature Registry（Metadata Pipeline + Composition Planner）与
P0-3 Scene Composer 与 P1 前置的 Gameplay Loop Composer 均已完成；下一任务候选：P0-2
Game Design Skill、提交成果（Phase 1.5 全链成果待 commit），
或直接串联「自然语言 → Gameplay Blueprint → 全部实体场景 → 验证」的多实体生成演示。

P1-4 Runtime Debug Agent 已由 Phase 1.6（AD-010）覆盖（运行期错误捕获 → 定位 → 修复 → 复验闭环）。

Phase 1.21 之后的建议（按价值排序）：

1. **阶段条件扩展**：在 `clear_enemies` / `defeat_boss` 之外增加可校验的条件（如 Boss 血量阈值、
   限时生存阶段），仍由 `LevelConfig` 声明、`LevelOrchestrator` 执行，不引入通用状态机框架。
2. **Boss 生成链路产物化**：让组合器/生成器输出可直接挂 `LevelHost` 的宿主（或在计划中
   声明宿主适配器入口），避免调用方手工挂载适配节点。
3. **交叉校验前移到 producer**：`build_boss_level` 接受 `plan` 后直接拒绝宿主根/实例不一致，
   不必等到 `check_level --plan`；同时把 `on_start` Boss 的“不参与宿主实例校验”写成显式策略。
4. **Holdout 生成器**（可选）：当前只手工编写 holdout 配置；若确有需求再扩 `generator_scope`，
   不为了对称性虚构能力。

## AD 候选（挂起，观察中）

当多个触发路径作用于同一个状态域时，应优先由该状态的 Feature 定义冲突语义，而不是让 Scene Glue 仲裁。
与既有 AD（002/005）方向一致，暂不升格；待出现第一个需要在 Glue 层仲裁的真实案例再评估。
