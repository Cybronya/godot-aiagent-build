# Skill Framework Validator

这是 Godot Agent Skill Framework 的按需机器验证器。

Validator 只检查，不自动修改 Framework 文件。第一阶段只在用户明确要求检查/验证时由 Agent 执行。

## 执行

```bash
python .ai/tools/validator/validate.py
```

也可以显式指定配置目录：

```bash
python .ai/tools/validator/validate.py --config-dir .ai/config
```

依赖：Python 3 + PyYAML（`pip install pyyaml`）。

## Trace Replay（Phase 1.22）

编排诊断事件 trace 的**只读**回放（不调用 Godot、不驱动游戏状态）：

```bash
python .ai/tools/validator/trace_replay.py <trace.json> [--json]
# 退出码: 0 = 合法可回放；1 = 违反契约；2 = 输入错误（缺文件 / 非法 JSON / 未知版本）
```

契约见 `.ai/context/orchestration_trace_schema.yaml`；真实 trace 由
`e2e/multi_stage_boss_probe.py` 从 Godot 运行导出，单测在
`validator/tests/test_orchestration_trace.py`（R1–R80；R44+ 波次语义，R58+ 出口解锁前置，
R62+ holdout 生成调度激活，R68+ 跨模式语义：模式门 / 阶段数一致性 / 终结 reason 白名单 /
mode 显式声明，并验证三条合法链不被误拒、四个真实基线仍可回放）。

## Golden Trace Baselines（Phase 1.23–1.26）

已批准基线在 `validator/baselines/<scenario_id>.json`（真实 Godot 沙箱捕获 + 显式批准）。
比较器只读，先回放后逐事件比较：

```bash
python .ai/tools/validator/trace_baselines.py <trace.json> --scenario waves [--json]
# 退出码: 0 = PASS；1 = REGRESSION/INCOMPLETE/INVALID_TRACE；2 = BASELINE_MISSING/INVALID_BASELINE
```

动态字段仅 `run_id` / `timestamp_ms`（显式策略）；`data` 默认 strict。基线只能通过
`e2e/approve_trace_baselines.py`（candidate → review → apply --i-approve）更新，
测试与比较器永不写基线。Phase 1.28 起基线也必须能通过回放：结构合法但语义不合法
（跨模式事件 / 模式外终结原因 / 重复终结）的基线 → `INVALID_BASELINE`（exit 2），
不会把「基线不可能发生」错报成真实 trace 的回归。

### 输入类错误的退出码（Phase 1.29 锁定）

同一「文件不存在 / 不可读」在两个入口的映射**不同且已显式锁定**（测试 U91–U93 守护，
不得为“统一码”而静默改变）：

| 条件 | `trace_replay.py` | `trace_baselines.py` |
| --- | --- | --- |
| trace 缺失 / 不可读 / 非法 JSON | 输入错误 exit 2 | `INVALID_TRACE` exit 1 |
| 基线缺失 | — | `BASELINE_MISSING` exit 2 |
| 基线不可读 / 非法 / 不符契约 | — | `INVALID_BASELINE` exit 2 |

两者均非 0：输入问题与非法语义永远不会变成 PASS。

## Cross-Mode Semantics（Phase 1.28）

公共语义只覆盖真正跨模式成立的约束：结构 / 序号 / 时间戳、`orchestration_started` 唯一
居首且 `data.mode` 显式声明（`invalid_start_mode`）、终结互斥且终结后只允许
`duplicate_event_ignored`。模式特有语义显式限定模式：

- boss：`stage_*`（需 `data.stage_count > 0`，`stage_event_outside_boss_stages`；
  索引必须小于声明阶段数，`stage_start_outside_declared_count`）与 `boss_death_confirmed`；
- waves：`wave_started` / `wave_cleared` / `exit_unlocked`；
- holdout：`spawn_schedule_started`；
- 终结原因必须属于该模式的可达集合（`victory_reason_outside_mode` /
  `failure_reason_outside_mode`，取值来自生产写入点）。

三种模式各自的事件链互不要求对方的事件（不为统一而强迫相同序列）。
验证：`validator/tests/test_orchestration_trace.py`（R68–R79）与
`validator/tests/test_trace_baselines.py`（U77–U85，回放器与比较器对同一非法语义给出
一致可解释结果）。Phase 1.29 追加 U86–U94（审批信任边界 + 候选→审查→批准闭环）。

## 信任边界与调用链（Phase 1.29）

```
不可信输入                       校验塔（唯一入口）                              信任内核（版本控制内）
trace JSON   ──► trace_replay.load_trace ─► replay() ─┐
基线 JSON    ──► load_baseline ─► validate_baseline（结构 + 回放）─┴─► compare() ─► 状态 / 退出码
候选 JSON    ──► approve: review / apply ─► resolve_candidate_target ─► load_candidate（身份一致）
                      └─► _validate_candidate + verify_candidate_fingerprint（当前方案）
                      └─► apply 是唯一写入者（先校验现有基线，再原子写）
真实捕获      ──► trace_baseline_capture ─► build_baseline（先校验 trace 再构造）
测试入口      ──► run_tests.py：发现 → 子进程执行 → classify（退出码 + 失败/跳过标记）
```

三条应成立的不变量（Phase 1.29 逐条审计）：

| 不变量 | 含义 | 结论 |
| --- | --- | --- |
| I1 合法性 | 进入比较的事件流 / 基线都先过 schema + 回放 | 成立（Phase 1.28 后；U77–U85 守护） |
| I2 审批绑定 | 审批只对「内容未变且声明当前方案」的候选生效 | 修复后成立（U86–U88；连同身份一致性） |
| I3 证据完整 | 报 PASS 的测试确实执行了断言 | 修复后成立（SKIP ⇒ INCOMPLETE；E1–E7） |

残余风险（已评估、不引入新机制；Phase 1.30 复核后区分措辞）：候选的 `source.captured_by`
/ `probe` / `generation_chain` 是**声明**（硬编码字符串 / 静态列表），仓库内没有能把
「候选 = 真实捕获」做密码学绑定的手段；`source.trace_run_id` 现在是**一致性**约束
（必须等于每个事件的 `run_id`，见下节），但仍不是来源真实性证明——两个字段在同一文件里，
伪造者可一起改。防线是内容必须过 schema + 回放 + 指纹，加人工 `--i-approve`。

## 审批与执行入口的信任边界（Phase 1.29）

- 新候选必须声明**当前**指纹方案；缺少声明或声明已废弃的 scheme 1 → review/apply 拒绝，
  scheme 1 仅用于验证历史已批准基线。
- `--scenario` 必须与候选内容 `scenario_id` 一致；写入目标始终跟随内容。
- 候选不可读 → review 与 apply 同为 exit 2 + 同一诊断；`--candidate <文件> --scenario <id>`
  按文件处理。
- 测试执行入口 `run_tests.py`：**自报 `SKIP:` 的测试不再算无条件 PASS**（归为 INCOMPLETE，
  总入口 exit 1），因为“PASS”意味着断言确实执行过；分类语义与真实子进程路径由
  `validator/tests/test_run_tests_evidence.py`（E1–E7）锁定；E7 直接走 `main()` 断言
  「选中 0 个测试」时入口返回 1（未执行不得表现为成功）。

## 证据来源与内容绑定（Phase 1.30）

- **已复现缺陷（E-1）**：`_validate_candidate` 曾把调用方文档的事件 `run_id` **原地**改成
  `candidate-check`，`apply` 随后把它落盘 ⇒ 四个已批准基线的 `events[*].run_id` 全是
  `candidate-check`，而 `source.trace_run_id` 记的是 `run-xxxxxx`；来源变成无法交叉验证的
  孤证。更严重的是同一进程内再次使用那份 trace 会误报 `run_id_mismatch`（已被污染的
  内存对象不再是一份合法 trace）。现改为只在**副本**上规范化（U95 / U99 守护）。
- **已补齐的一致性约束（E-2）**：候选必须写 `source.trace_run_id` 且等于每个事件的
  `run_id`；`source.trace_event_count`（存在时）必须等于事件数（U96–U98，含截断捕获用例）。
- **边界（必须如实说明）**：以上是**内容自洽性**，不是来源真实性。拥有本机同权限的攻击者
  可同时改写内容与来源字段并自行传 `--i-approve`；`--approver` 是自由文本，不是身份认证。
  指纹无密钥，只防意外改动，不防伪造。
- **历史基线不可补救**：四个基线的 `run_id` 已被旧校验器覆写，且**禁止重录**，因此修复
  只对此后生成的候选生效。

## 检查范围

- Agent 入口与 Framework 版本
- Agent 配置路径
- Registry 注册项
- Registry 与 canonical SKILL.md 一致性
- Skill ID、目录名、必需 Metadata
- Category 与 Load Policy
- Required / Related Dependencies
- Dependency Category Direction
- Circular Required Dependencies
- Schema / Template 基础对齐
- Collaboration 中的重复 canonical metadata
- Framework 内部路径的 root-independent 约束

## Behavior Evidence 阶段（Phase 1.56）

把 Phase 1.40–1.54 产生的**真实执行**行为证据（L4）接到 Validator 上。默认不执行；
只有显式传 `--behavior-evidence` 才运行，旧调用方式与旧的七/八阶段结果完全不变。

```bash
# 1) 采集真实行为证据（真实 Godot 动作 + 重放 2 次）并落盘为证据包
python .ai/tools/scene_composer/feature_behavior_evidence.py --all \
    --evidence-out .ai/tmp/behavior_bundles --replay 2

# 2) 由 Validator 独立复核证据包（默认目录 .ai/tmp/behavior_bundles，默认有效期 24h）
python .ai/tools/validator/validate.py --behavior-evidence
python .ai/tools/validator/validate.py --behavior-evidence \
    --evidence-dir .ai/tmp/behavior_bundles --evidence-feature health
python .ai/tools/validator/validate.py --behavior-evidence --behavior-evidence-json report.json
```

实现分两件：`scene_composer/feature_behavior_evidence.py#build_bundle` 负责**记录观测**，
`validator/check_behavior_evidence.py#check_evidence` 负责**独立判定**。分成两件是刻意的：
采集侧不自证成功。

| 结论 | 含义 | 退出码 |
| --- | --- | --- |
| `PASS` | 每条被请求的 behavior 都有可复核观测，且**由契约重算**成立 | 0 |
| `FAIL` | 内容被篡改 / 协议不兼容 / 等级冒充 / 未知 Feature·Behavior / 观测违反契约 | 1 |
| `INCOMPLETE` | 证据缺失、过期、观测不足、重放不足、目标 Feature 无证据 | 2 |
| `ERROR` | 协议非法或验证器自身异常 | 3 |

判定规则（细节见模块 docstring 与 `PHASE_1_56_COMPLETION_REPORT.md`）：

- **不信任证据自报的 `status`**：用 `template.yaml#behavior` 的 `expected` 与证据里的
  `observed` / `observed_args` 重算；`status: PASS` 不能替代观测。
- **等级不互相冒充**：本阶段只复核 `evidence_level: L4`。L2 归 `check_instance_evidence`，
  L5 需要缺陷注入证明，这里不代其声明。
- **`observed: null` 是「没观测到」而不是「违反」** → `INCOMPLETE`（`observation_insufficient`）。
- **重放**：`replay_count >= 2` 且 `replay_consistent == true`，否则 `INCOMPLETE`。
- **`--evidence-feature` 是范围**：只验证被请求的 Feature，同一证据包里其他 Feature 的
  记录记入 `summary.skipped_features`（不连坐为失败）；指向不存在 Feature 的证据仍拒绝。

协议与完整性：证据包携带 `protocol.protocol_version` 与协议文件 `sha256`，版本或内容
不符即 `FAIL`；`integrity.payload_sha256` 覆盖除 `integrity` 外的全部字段（规范化 JSON），
Validator 端**重新计算**而不采信声明值，因此能发现「生成后被改动」。

**信任边界（未解决）**：哈希只证明内容完整，不证明来源可信——能同时改实现并重签的人仍可
伪造证据包。真正的来源可信需要外部签名/可信执行环境，当前架构不具备，本阶段不声称具备。

### 执行产物交叉验证（Phase 1.57）

Phase 1.56 的复核只能读证据包本身，而 `action_executed` / `replay_count` /
`replay_consistent` 都是**采集侧自报**。Phase 1.57 起，Validator 还会打开
`evidence_paths` 指向的**真实执行产物**（每次重放一份 `result.json`，由 Godot 探针写出），
在验证器侧重新计算：

| 检查 | 矛盾时的结论 |
| --- | --- |
| 产物存在 / 可读 / 合法 JSON / 字段齐全 | `INCOMPLETE`（`artifact_missing`、`artifact_invalid_json`、`artifact_invalid_schema`） |
| `evidence_paths` 键 = 产物 `run_id`，且属于证据的执行批次 | `FAIL artifact_run_mismatch` |
| 产物 `feature` / `behavior` = 证据归属 | `FAIL artifact_feature_mismatch` / `artifact_behavior_mismatch` |
| 产物条数 = `replay_count`，序号 = 1..N | `FAIL replay_count_mismatch` / `replay_index_mismatch` |
| 产物 `checks` 与证据 `actual[]` 逐项一致 | `FAIL observation_mismatch` |
| 由产物重算的重放一致性与自报值一致 | `FAIL replay_consistency_mismatch` |
| 动作确有执行记录，且序列与契约一致 | `FAIL action_not_executed` / `action_sequence_mismatch` |
| 产物 sha256 = 证据记录的 `artifact_digests` | `FAIL artifact_digest_mismatch` |
| 同一产物不被另一条记录引用 | `FAIL artifact_reused` |

路径安全：只读授权根目录（默认 `.ai/tmp/behavior`，可用 `--artifact-root` /`--evidence-artifact-root` 追加）内的 `result.json`；解析先做 `realpath`
（跟随符号链接）再判包含关系，拒绝 `../`、越界绝对路径、越界符号链接、目录、非
`result.json`、以及证据目录自身。缺少 `evidence_paths` 的旧格式证据包一律
`INCOMPLETE execution_paths_missing`，**不会**因为“读不到”而 PASS。

仍未解决的是**来源真实性**：改实现、改产物、改证据包并重算全部摘要的人依然能构造出自洽的
证据（回归测试 D3 明确记录该边界，不算检测成功）。

## Layer Checks（Phase 1.15）

在 Framework 静态检查之外，validate.py 可以**编排既有检查器**执行分层校验（缺省不执行，
行为与历史版本兼容）。各层独立运行，局部失败不阻断其他层；诊断统一为结构化格式
`{layer, code, severity, location, path, reason, hint}`，带稳定错误代码。

```bash
# Scene 层（Scene/Entity Blueprint + 生成的 .tscn，场景按 root.name 推导）
python .ai/tools/validator/validate.py --scene-blueprint slime_enemy.yaml
# Gameplay 层
python .ai/tools/validator/validate.py --gameplay-blueprint survival_game.yaml
# Level 层（关卡编排配置）
python .ai/tools/validator/validate.py --level Levels/timed_combat_arena.json
# Runtime 层（真实 Godot headless playtest，耗时；显式 opt-in）
python .ai/tools/validator/validate.py --runtime-scene res://Scenes/EnemyBasic.tscn
# Runtime 层（只判定既有 runtime_result，不启动 Godot）
python .ai/tools/validator/validate.py --runtime-result runtime_result.json
# Binding 层（Phase 1.18：资产绑定文档静态健康检查；复用 check_binding_schema）
python .ai/tools/validator/validate.py --bindings-dir .ai/context/asset_bindings
# Binding 层 + 实体存在性（entity-scoped 绑定必须指向蓝图中声明的实体）
python .ai/tools/validator/validate.py --bindings-dir .ai/context/asset_bindings \
    --gameplay-blueprint survival_game.yaml
# 组合 + 自定义项目根
python .ai/tools/validator/validate.py --level Levels/survival_arena.json \
    --gameplay-blueprint survival_game.yaml --project-root .
```

### 运行时实例证据（Phase 1.39，显式 opt-in）

第 7 阶段（Feature Instance Evidence）是**静态**的：只证明 `.tscn` 文本与声明一致。
要证明「真实加载后对象存在且类型/数量符合契约」，单独调用运行时入口：

```bash
python .ai/tools/validator/validate.py --instance-runtime collect_pickup
python .ai/tools/validator/validate.py --instance-runtime all --require-runtime
```

| 状态 | 含义 | 默认 | `--require-runtime` |
| --- | --- | --- | --- |
| `PASS` | 加载后满足契约 | 通过 | 通过 |
| `MISMATCH` | 加载失败 / 缺失 / 类型或数量不符 | failure | failure |
| `INSUFFICIENT` | 探针超时、采集失败、需动作才能生成 | warning | **failure** |
| `INVALID` | 契约非法 | failure | failure |
| `NOT_DECLARED` | 未声明 `instance.runtime` | 不检查 | 不检查 |

**运行成本**：每个 Feature 启动一次真实 Godot headless（进程级超时 90s，默认窗口 0 帧），
因此缺省不执行；静态 Validator 行为与历史版本一致。证据文件落在
`.ai/tmp/runtime-instance/<run_id>/`（contract / result / stdout / stderr），可逐次追踪。

**失败语义区分**：静态 `MISMATCH`（文本与声明矛盾）与运行时 `MISMATCH`（加载/对象矛盾）
是不同层的证据，都可定位到具体 check；`INSUFFICIENT` 一律表示「无法下结论」，
最终验收必须加 `--require-runtime`，不允许把「没跑成」当成功。

**行为证据（Phase 1.40 / 1.42 / 1.43）不在 Validator 内**：真实动作 + 后置状态由独立入口
`scene_composer/feature_behavior_evidence.py` 负责（隔离场景副本、默认重放 2 次、
`--require-behavior` 收紧 `INSUFFICIENT`；Phase 1.42 起可在动作序列中推进真实
physics 帧并观测位移/区间，能力仍由 `behavior_protocol.yaml` 唯一定义；
Phase 1.43 起单个 behavior 可用 `scene:` 指向同一 Feature 目录内的证据夹具场景，
不增加任何动作/观测能力；Phase 1.44 起条件门控（`condition_gate`）以真实接触 →
聚合 → 下游动作的链路取证，同样只复用 v2 既有能力）；本 README 描述的静态 /
运行时实例命令与失败语义保持不变。

编排实现在 `validator/unified.py`（各层调用既有独立检查器，不重新实现规则）。

**Binding 层约定（Phase 1.18）**：无 `--gameplay-blueprint` 时无法判断实体存在性，
输出 `BINDING_INFO_INSUFFICIENT_INPUT` **info 诊断**（如实展示，不计入
error/warning 基线——既不虚构校验成功，也不夸大为告警）；给出蓝图后，
entity-scoped 绑定指向未知实体会成为稳定 `BINDING_*` error 诊断（整层 FAIL）。

**Runtime 可用性约定**：`--runtime-scene` 需要 Godot 二进制（相邻目录或 PATH）；
Godot 不可用时该层标记 `UNAVAILABLE` 并输出 `INCOMPLETE`，整体退出码非零——
Runtime 检查缺失永远不会被伪装成通过。耗时的 Runtime 探针为显式 opt-in，
缺省 Validator 只做快速静态检查（输出按层区分覆盖范围）。

## 输出

- **PASS**：无错误或警告
- **WARNING**：无阻断错误，但有需要人工确认的问题
- **FAIL**：违反 Framework 契约
- **INCOMPLETE**：被请求的层（如 Runtime）不可用，未真正执行

发现问题后由 Agent 决定如何修复，修复后再次运行 Validator。当前不接 Git hooks、GitHub Actions 或后台自动检查。

## 执行隔离与清理所有权（Phase 1.31 审计，未实施）

- **现状（已实测）**：`validator/tests/test_cross_layer_contract.py` 的 `cleanup()` 按
  `Levels/E2eContract__*.json` **前缀**删除；在临时目录模拟中 own 与 foreign 文件都被删除、
  无关文件保留（`foreign_removed=True`）。cross-layer / e2e / 6 个 GDScript 测试全部使用
  固定文件名，**没有 run token，也没有所有权账本**；e2e 的启动期清理同样按固定名单删除。
- **已实施（Phase 1.32，见下节）**：每次运行一个 token 运行根（`res://.ai/tmp/runs/<token>/`）
  + 追加式 `(path, sha256)` 账本；
  清理只删「账本中已创建、摘要匹配、位于本运行根/精确白名单」的路径；标记缺失、摘要不符、
  路径越界一律**不删并报告**；stale 运行根只报告、不自动回收（无法证明持有者已死亡）。
- **过滤证据（F5，未实施）**：过滤串目前不出现在输出中，过滤后只跑 1 项仍打印
  `ALL PASS` / `completed=1/1`；入口自身被中断时没有摘要或证据文件。候选方案是加法式
  `--evidence <path>`（JSONL：`run_start` / `test_end` / `run_end`）与 `selection:` 行，
  退出码不变。
- **边界**：不按文件名/时间/通配符删除；不重录基线；不关闭清理守卫。安全场景矩阵
  （S1–S6）、兼容性影响与授权清单见 `.ai/context/PHASE_1_31_AUDIT.md`。

## 运行工作区与所有权清理（Phase 1.32，已实施）

- **模块**：`.ai/tools/testsupport/run_workspace.py`（标准库，不驱动 Godot）。
  `RunWorkspace.create()` 生成 `pid-uuid8` token 与 `.ai/tmp/runs/<token>/`，账本为
  `ownership.jsonl`（`created` / `removed`，含相对路径、sha256、bytes、mtime_ns，fsync）。
- **清理只信账本**：不按文件名前缀 / glob / mtime 判断；删除前校验 token、路径在运行根内、
  非符号链接、size/mtime 与 sha256 一致，并在 unlink 前再次 `lstat` 比对。
  账本缺失 / 损坏 / 字段非法 ⇒ **整次拒绝删除**；存在未入账文件 ⇒ 保留运行根与账本。
- **残留**：启动时列出其他 token 的运行根并打印 `STALE (not removed)`，**不自动删除**；
  `reclaim_abandoned(..., acknowledge_abandoned=True)` 才逐个重新验证并删除。
- **消费者**：`validator/tests/test_cross_layer_contract.py` 的 33 个夹具与探针已迁入运行根，
  旧的 `Levels/E2eContract__*` 前缀清理已删除；断言仍 65 项（66 行 PASS）。
- **测试**：`validator/tests/test_run_workspace.py`（W1–W24 + L1–L8，37 项）覆盖隔离、幂等、篡改、
  越界、符号链接、未入账、异常残留 + reclaim、两进程并发、诊断保留、删除前再校验、
  账本中断行、token 冲突、GDScript 迁移静态锁定、token 格式统一与 e2e 串行锁；
  全部在系统临时目录运行。
- **e2e 所有权**：`validator/tests/test_e2e_ownership.py`（E1–E4）只替换 e2e 的
  「清单 / 签名判定 / 删除原语」三个接缝，覆盖「扫描期回收的残留重新登记」
  「外来文件拒绝删除」「清理前被改写则拒删」。

## 下游消费方：Evaluation（Phase 1.58）

本 Validator 的行为证据结论现在被评估器直接消费，不再只看终端输出：

```bash
python .ai/tools/evaluation/evidence_eval.py --evidence-dir .ai/tmp/p158/bundles
```

`evaluation/evidence_adapter.py` 调用本目录的 `check_behavior_evidence.check_evidence()`
取得逐行为结论（不解析 CLI 文本），再用 `expected_holds()` 在**同一批观测**上重算任务期望。
口径约定：Validator `FAIL` → 评估 `INVALID_EVIDENCE`；`VERIFIED_FAIL` 只能由
「Validator PASS + 任务期望不满足」产生；包级拒绝（`integrity mismatch` / 过期 /
协议变更）会传到该包内**每一条** behavior，哪怕逐条复算仍然是 PASS。
从证据包读出的 `run_id` / `artifact_digests` / `evidence_paths` 只作用在报告的可追溯字段。
- **忽略**：`.gitignore` 新增 `.ai/tmp/`（只覆盖易失运行工作区；`git ls-files .ai/tmp` = 0）。
- **F4-B（Phase 1.33）**：e2e 固定名产物采用「显式清单 + 启动期内容签名 + 本次运行缺席证明」
  （生产解析约定要求 `Scenes/<Pascal>.tscn`，不能迁入运行根）；6 个 GDScript 测试各自创建
  `user://.test_runs/runs/<pid>-<16hex>/`（token 与 Python 侧 canonical 格式统一），只删
  本运行自有文件，共享目录残留只报告；e2e 串行锁 `.ai/tmp/runs/e2e.lock`（`O_EXCL` +
  持有者可证死亡才回收）。`user://` 引擎日志 / MCP 配置 / Phase 1.6 夹具目录一律不清理
  （所有权不可证）。详见 `.ai/context/PHASE_1_33_AUDIT.md`；F5 与 janitor 未实施。

## Baseline 生命周期与逐行为绑定（Phase 1.60）

**审批之后不等于永远可信**：使用基线时必须重算内容摘要并与审批登记比对
（`validator/baseline_lifecycle.py` + `baselines/approval_registry.json`）。

- 状态机：`DRAFT → PENDING_REVIEW → APPROVED`；`APPROVED → SUPERSEDED / REVOKED`；
  跳步与终态转换被拒。只有 APPROVED 可用于正式评估。
- 摘要（`baseline-content-digest-v1`）：规范化 JSON（sort_keys + 紧凑分隔符）的 SHA256，
  覆盖全部评估相关载荷（events / comparison_policy / expected_final_state /
  scenario_id / schema 版本 / approved_behavior_version / coverage）；不含 approval 块
  （合法的 coverage 修订先例）与 scenario_description——这两者由登记时固化的
  approver / approved_at / 指纹一致性核对覆盖。
- 使用时复核 `use_baseline()`：`APPROVED_OK / DIGEST_MISMATCH / UNAPPROVED /
  MISSING_REGISTRATION / REVOKED / SUPERSEDED / APPROVAL_MISMATCH / INVALID_BASELINE`。
  基线内容变化 → 旧审批失效；自报 `approved=true` 不能绕过登记。
- 4 条既有基线已**显式迁移登记**（依据 = 文件内审批块 + 指纹可复算；内容字节未动）。
  新基线走 `e2e/approve_trace_baselines.py` 批准后**必须**在登记表注册才能被
  Evaluation 使用。
- 逐行为绑定：`validator/bindings/behavior_bindings.json`（schema 见
  `validator/trace_bindings.py`）。精确 ID 匹配；绑定 expected 不得宽于当前契约
  （契约内容摘要即版本）；编排场景 Trace 保持 `SCENARIO_ONLY`，不自动升级为逐行为
  Golden Trace。验证状态：`VALID_BINDING / MISSING_BINDING / STALE_BINDING /
  INVALID_BINDING / UNAPPROVED_BASELINE / REVOKED_BASELINE / DIGEST_MISMATCH /
  CONTRACT_MISMATCH / SCENARIO_MISMATCH / NOT_APPLICABLE`。
- 信任边界（Phase 1.60 §16）：内容完整性与审批流程完整性已交付；**审批者身份真实性
  未交付**——同权限攻击者仍可同时改写内容、摘要与登记记录，独立签名属后续阶段。
- 测试：`validator/tests/test_baseline_lifecycle.py`（26 项）、
  `validator/tests/test_trace_bindings.py`（28 项）。

## Provenance：独立信任根与来源签名（Phase 1.61）

`validator/provenance/`：Ed25519（PyNaCl/libsodium，不自研密码学原语）来源签名验证，
信任根来自**项目工作区写权限边界之外**的用户级文件
（`~/.provenance_trust/<项目 slug>/trust_root.json`，或 `$PROVENANCE_TRUST_ROOT`）。
信任根路径解析到工作区内 → 拒收（fail-closed）；工作区内的自报公钥/撤销记录一律无效。

```bash
python .ai/tools/validator/provenance/provenance_cli.py keygen \
    --subject "release-manager" --scopes approve_baseline,issue_evidence,seal_holdout
python .ai/tools/validator/provenance/provenance_cli.py status
python .ai/tools/validator/provenance/provenance_cli.py sign baseline \
    --baseline-id waves --baseline-version 2 --key-id PROVKEY-xxx
python .ai/tools/validator/provenance/provenance_cli.py verify baseline \
    --baseline-id waves --baseline-version 2 [--require-signature]
```

- 私钥种子只存 `~/.provenance_trust/<slug>/keys/`（0600），永不入仓/入日志/入报告。
- 密钥生命周期：`ACTIVE`（可签发）/ `RETIRED`（不可签发，历史签名可验）/ `REVOKED`
  （按撤销策略拒绝，终态）。轮换 = 新 ACTIVE + 旧 RETIRED，历史签名不受影响。
- 签名封套绑定对象类型/ID/版本/内容摘要/scope（全部在签名消息内）→ 跨对象/跨类型/
  跨版本/跨 scope 复用必然失败。
- **边界**：签名证明"谁签署了什么摘要"，不证明执行过程真实；Baseline 登记条目、
  Evidence sidecar（`<bundle>.sig.json`）、Holdout 登记记录各自承载封套。
- 历史 4 条基线保持 `LEGACY_APPROVED`，不伪造签名、不自动升级；require 模式下
  无签名对象一律拒绝。
- 测试：`provenance/tests/test_provenance_core.py`（57）、
  `provenance/tests/test_provenance_attacks.py`（32，A01–A18 + 私钥泄露检查）、
  `validator/tests/test_baseline_signature.py`（21）。

## Binding 候选生成与显式审批（Phase 1.63）

```bash
python .ai/tools/validator/binding_candidates.py inventory --out .ai/context/phase_1_63_support_inventory.json
python .ai/tools/validator/binding_candidates.py generate            # 生成/刷新候选（永不自动批准）
python .ai/tools/validator/binding_candidates.py submit   --binding-id BND-XXX
python .ai/tools/validator/binding_candidates.py approve  --binding-id BND-XXX --reviewer <人> \
    --reference "<依据>" [--key-id PROVKEY-...]                      # 重核候选+契约摘要，可选签名
python .ai/tools/validator/binding_candidates.py promote  --binding-id BND-XXX   # 写入正式绑定库，旧绑定 SUPERSEDED
python .ai/tools/validator/binding_candidates.py gate --feature health --behavior damage
```

- expected 只能**逐字复制**自契约；契约缺 expected → `BLOCKED_MISSING_EXPECTED`，永不猜测填充。
- 审批时重算候选摘要与契约摘要：候选被改或契约漂移 → 拒绝并退回 DRAFT。
- 登记表：`validator/bindings/approval_registry.json`（每条记录含签名封套，scope=approve_binding）。
- 门禁状态：NO_BINDING / DRAFT_BINDING / PENDING_REVIEW / APPROVED_BINDING / BINDING_REVOKED / CONTRACT_MISMATCH / BINDING_INVALID（精确 ID 匹配，无子串）。
- 测试：`validator/tests/test_binding_candidates.py`（26 项，含篡改/漂移/跳步/撤销攻击）。

## 运行时路径解析与分批验证（Phase 1.64）

`execution/env_paths.py` 是唯一的 Godot 定位入口，1.62 的两个 E2E Runner 已改用它：

```bash
python .ai/tools/validator/execution/env_paths.py        # 打印解析结果（项目根 / Godot / 来源）
python .ai/tools/validator/execution/run_execution_e2e.py          # 单 Feature 全链（20 checks）
python .ai/tools/validator/execution/run_multi_feature_e2e.py      # 多 Feature（3 attestations）
python .ai/tools/validator/execution/run_p163_full_chain.py        # 1.63 三 Feature（24 checks）
```

解析优先级：`GODOT_BIN` → `.ai/config/runtime-playtest.yaml#runtime_playtest.godot_binary` →
项目相邻的 `../Godot_v*_console.exe` → `PATH`。全部失败时打印 `ENVIRONMENT ERROR` 并 `exit 2`
（不再抛 `FileNotFoundError` 或静默跳过采集）。**不需要导出 `GODOT_BIN`。**

分批验证（Phase 1.64 引入，按已审批 Binding 逐 Behavior 出 Evaluation）：

```bash
python .ai/tools/validator/execution/run_p164_batch.py \
  --label B1 --features save_game,i_frames,openable_door \
  --out-root .ai/tmp/p164/batch1 --replay 2
```

| 产物 | 位置 |
| --- | --- |
| 证据 bundle / 签名 / manifest / attestation | `<out-root>/evidence/<feature>/<run-id>/` |
| 采集 runs（隔离工作区） | `<out-root>/runs/<run-id>/` |
| 逐 Behavior Evaluation | `<out-root>/evaluation/<feature>/<behavior>/evidence_report.json` |
| 批次汇总（每 Behavior 的 evaluation_status / 失败原因） | `<out-root>/summary.json` |

`expected` 逐字取自 `validator/bindings` 的已审批记录（不是硬编码），因此契约或绑定被改会直接
`CONTRACT_MISMATCH` 而不是悄悄通过。评估报告**必须**放在运行目录的子目录里，矩阵的
`evaluation_dimension` 用 `<dir>/*/evidence_report.json` 收集；直接用某个 run 目录会收集不到。
