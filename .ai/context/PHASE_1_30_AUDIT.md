# Phase 1.30 — Execution Isolation & Evidence Provenance（只读审计报告）

> 状态：审计完成（2026-10-19）；经授权已实施 **F1–F3 + 文档**（见 §9），F4/F5 未授权未做。
> 基线：Phase 1.29（工作区未提交）。HEAD = `5e47bfd`，branch = `master`。
> 本次审计未写入任何基线、未改动 GDScript、未执行破坏性 Git 操作。

## 0. 审计方法与证据来源

| 动作 | 命令 | 结果 |
| --- | --- | --- |
| 记录工作区 | `git rev-parse --abbrev-ref HEAD` / `git log --oneline -3` / `git status --porcelain` | master / `5e47bfd` / 20 修改 + 5 未跟踪，暂存区为空 |
| 全量入口实跑 | `python .ai/tools/run_tests.py` | **completed=81/81 passed=81 failed=0 incomplete=0 unavailable=0 not_executed=0，exit 0** |
| 删除规模探针 A | 单命令内工作区 `unlink()` 80 次 | 未被终止，exit 0 |
| 删除规模探针 B | 单命令内工作区 `unlink()` 2000 次 | 未被终止，exit 0 |
| 删除规模探针 C | 单命令内 `%TEMP%` 2000 次（e2e 沙箱同路径） | 未被终止，exit 0 |
| 来源字段核对 | 读取四个已批准基线的 `source` / `events[*].run_id` | 见 §3.2 |
| 覆写行为复现 | 直接调用 `approve._validate_candidate(doc)` 观察输入对象 | 见 §3.3（原地篡改已复现） |

## 1. 信任边界与调用链

```
                         ┌──────────────────────────────┐
   真实 Godot headless ──▶│ *_probe.run_*_probe()        │  exit_code + metrics(PASS/FAIL)
   （沙箱副本内运行）      │  写 trace JSON → 读回 → 自删  │  trace_document（事件流）
                         └───────────────┬──────────────┘
                                         ▼
                         ┌──────────────────────────────┐
                         │ trace_baseline_capture.capture│  ok = exit==0 && status==PASS
                         │  _make_sandbox/_generate/_probe│  evidence{godot_version, probe,
                         └───────────────┬──────────────┘           generation_chain, ...}
                                         ▼
                         ┌──────────────────────────────┐
                         │ approve.build_candidate       │  + captured_by（硬编码字符串）
                         │  trace_baselines.build_baseline│  再次 validate_trace（schema+回放）
                         └───────────────┬──────────────┘   + scheme 2 指纹 + trace_run_id
                                         ▼
   ┌──────────┐  写文件   ┌──────────────────────────────┐
   │ FS 任意  │─────────▶│ <out>/<scenario>.candidate.json│  approval.status = "candidate"
   │ 可写者   │          └───────────────┬──────────────┘
   └──────────┘                          ▼
                         ┌──────────────────────────────┐
                         │ review  ：_validate_candidate  │  重算指纹（scheme 2）
                         │           + verify_fingerprint │  打印逐事件表 + 与现有基线差异
                         └───────────────┬──────────────┘  ← 人工判断（无技术强制）
                                         ▼
                         ┌──────────────────────────────┐
                         │ apply   ：--i-approve + approver│  再校验一次 → 原子写入基线
                         │            + note              │  baseline_version + 1
                         └───────────────┬──────────────┘
                                         ▼
                         ┌──────────────────────────────┐
                         │ baselines/<scenario>.json      │
                         └───────────────┬──────────────┘
                                         ▼
                         ┌──────────────────────────────┐
                         │ trace_baselines.compare(_files)│  validate_baseline → 逐事件比较
                         │  → run_tests / trace_replay    │
                         └──────────────────────────────┘
```

信任边界（谁能让什么成真）：

| 边界 | 信任内容 | 谁控制 | 技术强制手段 |
| --- | --- | --- | --- |
| B1 Godot 执行 | 事件流确实由该进程产生 | 本机任意进程 | 无（沙箱只隔离路径，不隔离身份） |
| B2 capture → candidate | 候选内容 = 本次捕获内容 | 调用 capture 的进程 | `build_baseline` 的 schema+回放校验；无内容摘要绑定 |
| B3 candidate → apply | 批准的是同一份字节 | 文件系统任意可写者 | scheme 2 指纹（**无密钥**，见 §3.4） |
| B4 apply → baseline | 基线 = 已批准字节 | 文件系统任意可写者 | 原子写 + `validate_baseline` |
| B5 baseline → compare | 基线自身合法 | 文件系统任意可写者 | `validate_baseline`（结构 + 回放） |

## 2. P0-1：全量测试执行隔离与删除守卫

### 2.1 复现与实测

1. 单命令全量：`python .ai/tools/run_tests.py` → **81/81 PASS，exit 0**（日志 `F:\audit_tmp_130_full.log`）。
   其中 `[77/81] PASS .ai/tools/validator/tests/test_cross_layer_contract.py`、
   `[?/81] PASS .ai/tools/e2e/tests/test_end_to_end_generation.py` 均在同一条命令内通过。
2. 删除规模探针：同一命令内对**工作区**文件执行 2000 次 `unlink()` → 进程未被终止，exit 0。
   对 `%TEMP%` 同样的 2000 次 → 同样未被终止。

### 2.2 根因

守卫**不在仓库代码中**：`SAFE_DELETE_BULK_CONFIRM_REQUIRED` 只出现在文档
（`run_tests.py` docstring、`WORK_STATE.md`、`.workbuddy/memory/2026-10-17.md`），
没有任何仓库代码产生或解释该字符串。

历史观测（`.workbuddy/memory/2026-10-17.md:34`）记录的是 **WorkBuddy 宿主运行时**的钩子：
「对同一命令内超过 50 次文件删除的进程终止」。当前运行时（Freebuff，2026-10-19）中：

- 2000 次工作区删除不被终止；
- 全量单命令 81/81 PASS，`incomplete=0`。

⇒ **结论：全量入口 INCOMPLETE 的根因是宿主环境的删除守卫，属环境限制而非产品缺陷。该限制在当前
运行时已不存在，`run_tests.py` / README / WORK_STATE 中「单命令全量必被终止」的表述已过期。**
分类逻辑本身是正确的：被外部终止的进程会得到非 0 退出且无失败标记 → `INCOMPLETE`，总入口 1。

### 2.3 仍然真实存在的隔离问题（与守卫无关）

| 编号 | 问题 | 证据 | 严重度 |
| --- | --- | --- | --- |
| I-1 | 测试把产物写进**共享** `Levels/`、`Tests/` 目录且用**固定名字**（`Levels/E2eContract__*.json`、`Tests/e2e_level_contract_probe.gd`、`Levels/E2eProbeLevel.json`） | `test_cross_layer_contract.py:PROBE_REL`、`_write(PROJECT_ROOT/"Levels"/...)` | 中：两个并发运行的同一测试会互删对方的夹具，产生假失败 |
| I-2 | 清理按 **glob 前缀**而非**所有权清单**：`cleanup()` 删除所有 `Levels/E2eContract__*.json` | `test_cross_layer_contract.py:cleanup()` | 中：会删除非本次运行创建的文件（跨线程/跨进程） |
| I-3 | 进程被强杀（SIGKILL/超时）时 cross-layer **没有启动期防御性清理**，残留夹具 + 探针脚本留在仓库 | 对比 `e2e/.../test_end_to_end_generation.py:401-412` 有声明式清单清理，cross-layer 无 | 低：残留 `Tests/*probe*.gd` 会被 Godot 扫描；实测本次审计前后**无残留**（全量 81/81 后 `git status` 仍只有 5 个已知未跟踪文件） |
| I-4 | e2e 的防御性清单同样是固定路径，并发运行仍冲突 | 同上 | 低 |

### 2.4 隔离方案（建议，未实施）

保持守卫原样、不关闭任何检查。最小改法（仅测试文件，不动生产代码）：

1. **唯一运行令牌**：夹具/探针名加 `pid + uuid4[:6]`（如 `Levels/E2eContract__<token>__<name>.json`，
   探针 `Tests/e2e_level_contract_probe_<token>.gd`）⇒ 并发运行互不可见。
2. **显式所有权清单**：写入时记录 `(path, sha256)`；清理只遍历清单，且**仅当磁盘内容摘要仍与写入时一致**
   才删除；内容被他人改写则跳过并报告（拒绝越权删除）。
3. **启动期残留检查**：若存在**其他令牌**的 `E2eContract__*`（疑似上一次被强杀的运行），
   只报告、不删除（删除才需要所有权）。
4. 回滚：改动全部在测试文件内，`git checkout -- <file>` 即回滚；不涉及基线、不涉及 GDScript。

## 3. P0-2：证据来源与内容绑定

### 3.1 字段职责表

| 字段 | 生成者 | 可修改者 | 当前校验 | 能否独立验证 | 性质 |
| --- | --- | --- | --- | --- | --- |
| `events[]` | 真实 Godot 探针（生产 `export_trace_json`） | 任意 | schema + 回放 + 指纹 | 能（回放语义可复算） | **证据（内容）** |
| `approval.candidate_fingerprint` | `approve.build_candidate` | 任意 | review/apply 重算比对 | 能，但**无密钥** | 防意外改动，非防伪造 |
| `approval.approver` / `note` / `approved_at` | CLI 参数 | 任意 | 仅非空 | 不能 | **声明** |
| `source.captured_by` | `build_candidate` 硬编码字符串 | 任意 | 仅非空 | 不能 | **声明** |
| `source.trace_run_id` | `capture.trace_document["run_id"]` | 任意 | **无任何交叉校验** | 不能（与内容脱钩） | **声明** |
| `source.godot_version` | `godot --version` 输出 | 任意 | 无 | 部分（可复跑比对） | 弱证据 |
| `source.probe` / `generation_chain` | 代码内静态映射/静态列表 | 任意 | 无 | 不能 | **声明** |
| `source.probe_metrics` | 探针 stdout 解析 | 任意 | 无 | 与 `capture.output` 一致但未落盘 | 弱证据 |
| `source.probe_script_removed` | 探针清理结果 | 任意 | 无；清理失败**不影响** `ok` | 不能 | 诊断字段 |
| `expected_final_state` | 由回放结果计算 | 任意 | 与自身事件一致性未校验（fail-safe 方向） | 能（回放） | 弱证据 |

### 3.2 关键发现 E-1：审批校验**原地覆写**了事件的 `run_id`，把来源链条从内容里抹掉

`approve_trace_baselines._validate_candidate()` 中：

```python
trace_document = {"document": ..., "run_id": "candidate-check",
                  "events": document.get("events") or []}   # ← 同一批 dict 对象
for event in trace_document["events"]:
    event["run_id"] = "candidate-check"                      # ← 原地改写调用方文档
```

`command_apply` 随后 `approved = copy.deepcopy(document)` 再写入 ⇒ **正式基线的事件里
`run_id` 全部变成 `candidate-check`**。

实测（四个已批准基线，只读检查）：

| 基线 | `source.trace_run_id` | `events[*].run_id` 实际值 |
| --- | --- | --- |
| `multi_stage_boss.json` | `run-602775` | `candidate-check` |
| `single_stage_boss.json` | `run-571545` | `candidate-check` |
| `waves.json` | `run-791975` | `candidate-check` |
| `holdout.json` | `run-675705` | `candidate-check` |

最小复现（真实事件带真实 run_id，调用校验函数后观察输入对象）：

```
before : ['run-571545']
errors : []
after  : ['candidate-check']
MUTATED: True
```

后果：
1. 基线的**唯一内容级来源线索**被校验器自己删除 ⇒ `source.trace_run_id` 变成无法交叉验证的孤证；
2. 事件记录自相矛盾（声称 run_id=`candidate-check` 的运行从未存在）；
3. 因为 `run_id` 属比较器的 `ignored_event_fields`，这个污染**不会**被比较器发现。
   （已批准基线**不得重录**，故修复只能向前生效。）

### 3.3 关键发现 E-2：`source.trace_run_id` / `trace_event_count` 与内容完全脱钩

`_validate_candidate` 只检查 `captured_by` 非空。任何候选可声明任意 `trace_run_id`
与任意事件流，review/apply 都接受。§七 的「manifest 与 trace 不匹配时拒绝」当前没有对应实现。

### 3.4 关键发现 E-3：指纹是「完整性」而非「真实性」

`normalized_fingerprint` = 对 `trace_schema_version + events`（去 `run_id`/`timestamp_ms`）做
**无密钥 SHA-256**，且指纹值就写在同一个文件里。因此：
- 能检测「review 之后内容被改而指纹没改」——已由 U49/U50 锁定，成立；
- **不能**检测「内容与指纹一起被改」——没有密钥、没有外部锚点、没有透明日志。

`--i-approve` 同理：它是一次**人类意图的显式声明**，不是身份认证（`--approver` 是自由文本）。

### 3.5 五种性质的当前状态

| 性质 | 问题 | 现状 |
| --- | --- | --- |
| 内容完整性（文件 = 摘要） | 内容与指纹是否一致 | **成立**（scheme 2 重算；U49/U50/U52） |
| 来源真实性（内容来自声称的 Godot 执行） | 是否真是该次运行产出 | **不成立**（无签名/无外部锚点；`captured_by` 为字符串） |
| 执行完整性（进程正常结束、捕获完整） | `ok = exit==0 && status==PASS`，空 trace 拒绝 | **成立**（探针非 0 不产候选；`capture` 空事件即失败） |
| 审批授权（批准者确实批了当前内容） | 批准对象是否 = 写入对象 | **成立**（apply 前重算指纹）；**但** E-1 使基线内的事件来源被改写 |
| 可追溯性（基线 → 捕获 → 审核 → 应用） | 能否从基线回到具体运行 | **部分**：`trace_run_id` 是孤证；事件 `run_id` 已被覆写；无候选文件留存 |

## 4. 方案比较（证据绑定）

| 方案 | 做法 | 复杂度 | 能防 | 不能防 |
| --- | --- | --- | --- | --- |
| A 现状 | 不绑定 | 0 | 意外改动 | 一切有意伪造 |
| **B 内容一致性（建议）** | ①校验器改为对**副本**规范化，不再原地改写；②候选必须满足 `source.trace_run_id` 非空且 = 每个事件的 `run_id`（且事件 run_id 一致）；③`source.trace_event_count`（若存在）必须 = 事件数 | **小**（单文件 ~15 行 + 测试） | 自相矛盾的候选、校验器破坏证据、事件数与声明不符 | 有意伪造（两处一起改） |
| C 本地 manifest + 内容摘要 | capture 额外产出 `manifest.json`（命令数组、退出码、trace 原始字节 sha256、schema 版本），candidate 引用其摘要 | 中（新文件格式 + 兼容旧候选 + 文档） | 捕获后/传输中被替换、证据与内容错配（对**诚实**的流程） | 同一用户权限的恶意进程（可重算摘要） |
| D 签名 / HMAC | 用长期密钥对 manifest 签名 | 大（密钥托管、轮换、丢失恢复、验证方信任根） | 无私钥的伪造 | 持有私钥者；本机被控 |

结论：**只做 B**。C/D 都需要新的可信根（密钥或外部服务），与本阶段「不引入第二套审批体系、
不新增强依赖」的约束冲突，且收益（对同权限攻击者）有限。B 的收益是把「可交叉验证的一致性」
做到位，并止住 E-1 的证据破坏。

**不宣称**：即使实施 B，`source.captured_by` / `probe` 仍是声明；拥有本机同权限的攻击者
仍可生成一份自洽的假候选并通过 `--i-approve`。这一点写入文档，不再作为「待修缺陷」。

## 5. P1：CLI 与测试结果语义

| 场景 | 入口 | 当前语义 | 退出码 | 评价 |
| --- | --- | --- | --- | --- |
| 空选择（过滤串无匹配） | `run_tests.py` | `no selected test scripts found` | 1 | 正确（E7 锁定） |
| `--python-only` + 无 Python 测试 | `run_tests.py` | 同上 | 1 | 正确 |
| 仅 `--godot-only` 且无 Godot | `run_tests.py` | 打印 FAIL | 2 | 正确 |
| Godot 缺失 + 混合模式 | `run_tests.py` | `unavailable=[...]` | 1 | 正确 |
| 自报 `SKIP:` 且 exit 0 | `run_tests.py` | `INCOMPLETE` + 跳过条数 | 1 | 正确（Phase 1.29 H1） |
| 子进程非 0 且无失败标记 | `run_tests.py` | `INCOMPLETE` | 1 | 正确 |
| 超时 | `run_tests.py` | `INCOMPLETE (TIMEOUT …)` | 1 | 正确 |
| `--scenario` 与候选内容不一致 | `approve review/apply` | 拒绝（身份不一致） | 2 | 正确（1.29 L1） |
| `--scenario` 仅作标签（给了 `--baseline`） | `trace_baselines` | 报告上的 scenario 取 CLI 值，不校验与基线 `scenario_id` 一致 | 0 | **仅标签，无安全影响**；改它会动既有 CLI 语义 ⇒ 不改，文档说明 |
| trace 文件不存在 | `trace_replay` / `trace_baselines` | 2 / 1（`INVALID_TRACE`） | 2 / 1 | 已文档化并锁定（1.29 M3） |

## 6. 风险排序

| 级别 | 编号 | 风险 | 证据 |
| --- | --- | --- | --- |
| 高 | E-1 | 校验器原地覆写 `run_id`，把污染写进正式基线，来源链不可恢复 | §3.2（四个基线 + 复现） |
| 中 | I-1/I-2 | 共享固定路径 + glob 清理 ⇒ 并发互删、越权删除 | §2.3 |
| 中 | E-2 | `trace_run_id`/`trace_event_count` 与内容无交叉校验 | §3.3 |
| 中（文档） | D-1 | `run_tests.py`/README/WORK_STATE 宣称的「单命令全量必被终止」在当前运行时已不成立 | §2.1/2.2（81/81 exit 0） |
| 低 | E-3 | 指纹无密钥；`--i-approve` 无身份认证 | §3.4（设计事实，需文档化而非修复） |
| 低 | I-3 | 强杀后 cross-layer 无启动期清理 | §2.3 |
| 低 | D-2 | `trace_baselines --scenario` 仅为标签 | §5 |

## 7. 最小实施方案（待授权）

| 步骤 | 文件 | 改动 | 兼容性 |
| --- | --- | --- | --- |
| F1 | `.ai/tools/e2e/approve_trace_baselines.py` `_validate_candidate` | 对事件做 `deepcopy` 后再规范化 `run_id`，**不再修改调用方文档** | 行为对合法候选不变；新写入基线的事件保留真实 `run_id`（`run_id` 属比较忽略字段，指纹不变） |
| F2 | 同上 | 新增：`source.trace_run_id` 必须非空且与所有事件 `run_id` 一致；若存在 `source.trace_event_count` 必须等于事件数 | 真实候选（`build_candidate` 产物）天然满足；U39 夹具需补 `trace_run_id`（更贴近真实候选） |
| F3 | `validator/tests/test_trace_baselines.py` | 新增 U95–U98：校验不修改输入；`run_id` 不一致被拒（含诊断）；`trace_event_count` 不一致被拒；真实候选正对照 | 只增测试 |
| F4 | `validator/tests/test_cross_layer_contract.py` | 唯一令牌 + 所有权清单（`path, sha256`）+ 只删自己且内容未变的文件 + 启动期只报告他人残留；新增自检 O1–O4 | 测试内部改动，断言仍 66 项 + 4 |
| F5 | `validator/tests/test_run_tests_evidence.py` | 新增 E8：过滤串命中的测试文件数 = 实际执行数（`run_tests.main()` 子进程路径已有 E4；此处锁定「分段/过滤不会把未执行算成通过」） | 只增测试 |
| F6 | `run_tests.py` docstring、`validator/README.md`、`WORK_STATE.md`、`CURRENT_TASK.md` | 把守卫表述改为**环境条件观测**（`2026-10-17 WorkBuddy 宿主；2026-10-19 Freebuff 实测 81/81 exit 0`），保留分段命令作为兜底；新增证据性质表与 E-1/E-2 结论 | 文档 |

**不做**：重录/改写任何基线；改 GDScript；引入签名/密钥；改变任何既有退出码；第二套审批体系。

验证计划：`validator` 段 + `e2e` 段 + `run_tests.py` 全量（单命令），并记录真实退出码与
基线 sha256/mtime 不变。

## 8. 未覆盖 / 无法验证

1. 无法证明历史上四个基线的事件确实来自 `source.trace_run_id` 所记的运行（`run_id` 已被覆写，
   且不允许重录）——只能向前修复。
2. 无签名时不可防御同权限攻击者伪造自洽候选；`--i-approve` 的授权是流程约束而非技术约束。
3. 宿主删除守卫是否会在其他运行时回归，只能按环境分别记录；仓库代码无法感知它。
4. 并发冲突（I-1/I-2）的修复只能通过唯一令牌 + 所有权检查降低概率，无法做跨进程锁
   （项目未引入锁机制，且不属本阶段目标）。

## 9. 实施记录（F1–F3 + 文档）

| 步骤 | 文件 | 实际改动 |
| --- | --- | --- |
| F1 | `e2e/approve_trace_baselines.py` `_validate_candidate` | 校验前 `copy.deepcopy(events)`，只在副本上写 `run_id="candidate-check"`；不再改写调用方文档 |
| F2 | 同上 | 新增 `source.trace_run_id` 非空 + 等于每个事件 `run_id`；`source.trace_event_count`（存在时）= 事件数 |
| F3 | `validator/tests/test_trace_baselines.py` | U95–U99；U39 夹具补 `trace_run_id` / `trace_event_count` |
| F6（文档） | `run_tests.py`、`validator/README.md`、`WORK_STATE.md`、`CURRENT_TASK.md`、本文件 | 守卫改为环境条件观测；证据性质与边界写入 README |

**修复前对照（实测）**：把 `_validate_candidate` 临时还原为旧实现后跑同一测试文件 →
**exit 1**，在 U95 段前中止：`BaselineError: cannot build a baseline from this trace:
INVALID_TRACE (run_id_mismatch: event run_id 'candidate-check' != document run_id 'run-unit')`
——旧实现把共享的 trace 文档本身改坏，后续复用同一 trace 直接失效。恢复新实现后
`test_trace_baselines.py` → **exit 0，100 PASS**（含 U95–U99）。

**未实施**：F4（cross-layer 唯一令牌 + 所有权清理）、F5（E8 过滤命中数）——未获授权。
基线 sha256/mtime 未变（见 §3 与交付说明）。
