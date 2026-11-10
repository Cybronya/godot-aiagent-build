# End-to-End Capability Evaluation（Phase 1.36）

回答一个问题：**现有框架能否完成真实的小型游戏开发任务**，以及完成它需要多少次返工。

不是测试套件 —— 单元/契约/回归测试回答「既有行为有没有坏」，本目录回答
「从一句需求出发，到能在 Godot 里跑起来并满足验收标准，需要几步、败在哪」。

报告：`.ai/context/PHASE_1_36_AUDIT.md`（每次正式评估的结论与证据路径）。

## 目录

```
.ai/tools/evaluation/
├── README.md            本文件（方案 + 指标口径 + 用法）
├── tasks.yaml           冻结的固定任务集（输入 / 命令 / 断言 / 清理清单）
├── runner.py            执行器：暂存输入 → 跑命令 → 行为探针 → 所有权清理 → 报告
├── scoring.py           判定与指标（纯函数；口径的唯一事实源）
├── probes/              真实 Godot 行为探针（GDScript，运行时状态断言）
├── fixtures/            任务输入（Blueprint / 手工场景 / 关卡需求）
└── tests/               runner 与 scoring 的自测（run_tests.py 自动发现）
```

## 用法

```bash
python .ai/tools/evaluation/runner.py --list                 # 列出任务与必需阶段
python .ai/tools/evaluation/runner.py --task all             # 全量评估
python .ai/tools/evaluation/runner.py --task T1 T5           # 指定任务
python .ai/tools/evaluation/runner.py --task all --json      # 打印完整报告
```

证据落在 `.ai/tmp/eval/<pid>-<uuid8>/report.json`（`.ai/tmp/` 已在 `.gitignore`），
包含每步 argv、真实退出码、耗时、输出尾部与失败原因。

退出码：`0` = 全部任务 PASS 且清理无拒绝；`1` = 有任务未通过或清理被拒绝；`2` = 输入/环境错误。

## 固定任务集

| 任务 | 需求 | 覆盖维度 |
| --- | --- | --- |
| T1 | a collectible key that disappears when picked up | 单 Feature 生成 + 运行时拾取行为（正/负） |
| T2 | an enemy that chases the target, damages on contact, has health, and can be stunned | 4 Feature 组合 + 追击/伤害/眩晕锁定 |
| T3 | 两把钥匙都拿到后门才打开 | 条件判断 + 信号联动（手工 glue）+ AND 语义负向 |
| T4 | 两波敌人，清空所有波次后打开出口 | 关卡编排 + 真实竞技场胜负/出口门 |
| T5 | 运行时 Node not found 时做最小修复 | 诊断分类 + 受限自修复 + 修复后回归 |

选择原则：**优先复用仓库既有 Feature 与探针**，不为评估新增游戏资产；
每项任务都必须有可在真实 Godot 中观察的行为断言，且带一个受控负向。

## 判定口径（`scoring.py` 是唯一事实源）

阶段：`plan`（需求→计划是否正确）/ `artifacts`（产物与引用）/ `loadable`（能否加载）/
`behavior`（行为是否达标）/ `negative`（受控负向）/ `regression`（是否引入回归）。

状态词表：`PASS` / `FAIL` / `SKIP` / `NOT_EXECUTED` / `INCOMPLETE` / `UNAVAILABLE`。

- 阶段状态 = 其步骤状态的折叠：**任一 FAIL 即 FAIL**，否则取最严重者，无证据 = `NOT_EXECUTED`。
- 任务判定 = `required_phases` **全部 PASS** 才算 PASS；未执行、跳过、中断都**不算通过**。
- 尝试判定（`attempts[].passed`）只看该尝试自己的步骤，不借用其它尝试的证据。
- 阶段回退：某个必需阶段在最终尝试中没有证据时，才回退到前一次尝试（如需求→计划检查只做一次）；
  被后续尝试取代的阶段**不**回退，避免历史失败拖累修好之后的结果。

## 指标与分母

| 指标 | 计算 |
| --- | --- |
| 首次通过率 | `first_pass`（第一次尝试逐步骤通过 **且** 任务 PASS）/ 已尝试任务数 |
| 最终通过率 | 任务 verdict = PASS / 已尝试任务数 |
| 自动修复成功率 | `kind: framework` 的尝试中 passed 的比例（人工改计划**不计入**） |
| 计划修订成功率 | `kind: plan_revision` 的尝试中 passed 的比例 |
| 回归缺陷数 | 回归阶段 FAIL 的次数 / 实际执行的回归检查数 |
| 人工干预次数 | `--human-interventions` 显式传入（默认 0）；任务内的计划修订单独统计 |
| 单任务耗时 | 每次运行的 `duration_s`，含暂存、生成、Godot 运行 |
| 资源/模型成本 | `UNAVAILABLE`：仓库无模型调用与费用计量入口 |

分母固定：`tasks_total` 含跳过的任务；`tasks_attempted` 排除
`NOT_EXECUTED` / `UNAVAILABLE`；比率为 0 分母时输出 `null` 而不是 `0`。

## 所有权与清理

- 共享目录（`Scenes/`、`Levels/`、`Tests/`）里的路径必须在**运行前不存在**，
  否则整次评估拒绝执行（不接管、不覆盖别人的文件）。
- 清理只删账本里登记、且内容包含声明标记的路径：
  - `.gd` / `.yaml` → 文本标记 `EVAL136`；
  - `.tscn` → 标记节点 `Eval136Marker`；
  - 关卡 JSON → 生成的 `level.id`（`eval_wave_level`）。
- 标记不匹配 / 目录位于运行目录之外 ⇒ **拒绝删除** 并记为 `cleanup.refused`，本次运行退出码为 1。
- Godot 派生的 `<script>.gd.uid` 只在「源文件由本次运行创建」且「运行前不存在」时删除。
- 运行目录 `.ai/tmp/eval/<token>/` 以 `exist_ok=False` 独占创建，其内容属于本次运行。

## 任务集版本（Phase 1.37）

| 文件 | 用途 |
| --- | --- |
| `tasks.phase136.yaml` | Phase 1.36 冻结版（T1 首次尝试是**证伪尝试**：断言单 Feature 蓝图必被能力契约拦住） |
| `tasks.yaml` | 当前版。T1 的证伪前提已在 Phase 1.37 修复，因此该尝试退役为正常正向尝试（断言更严：exit 0 + `Validation: PASS` + 产物） |

两次对照都用**未修改的 `scoring.py`**：

```bash
python .ai/tools/evaluation/runner.py --tasks-file .ai/tools/evaluation/tasks.phase136.yaml --task all
python .ai/tools/evaluation/runner.py --task all
```

退役证伪探针不是放宽标准：旧版在修复后会把「缺陷消失」记为 attempt 失败（`exit 0 != expected 1`），
新版用正向断言 + 原有行为探针继续把关；两版结果并存于 `.ai/tmp/eval/<token>/report.json`。

## 已知限制（必须随结论一起读）

1. **不是盲测**：任务按既有工具链的可行性先做过可行性探针才冻结，首次通过率只说明
   「该冻结流程在本次环境里是否一次通过」，不代表任意需求的成功率。
2. **生成的测试可能为空断言**：`scene_composer --tests` 在「根实例」蓝图上不生成组件块，
   PASS 是空洞的；行为证据只来自 `probes/` 中的真实运行探针。
3. **组合工具不会连线**：T3 的 `collected → set_condition`、`fulfilled → set_open`
   是手工写进 `.tscn` 的，因为 Scene Composer 只做实例化，不表达信号连接；
   同一 Feature 的多个实例（两把钥匙）也无法用 `components:` 表达。
4. **成本不可得**：见上表。
5. **T5 使用受控的最小项目副本**（`runtime/tests/fixtures/broken_node_path`），
   不是从生成产物里注入缺陷；它验证的是诊断+修复+回归链路，不是「任意缺陷都能修」。

## 新增任务

1. 在 `tasks.yaml` 追加任务，写清 `requirement`、`required_phases`、`stage`、`attempts`、`verify`。
2. 输入放 `fixtures/`，行为断言放 `probes/`（必须是运行时状态断言，不能只检查节点存在）。
3. 至少包含一个受控负向（`negative`），并说明「去掉什么会导致断言失败」。
4. 产物路径必须可证明归属（标记 + 运行前不存在），清理规则写进任务定义。
5. 跑 `python .ai/tools/evaluation/runner.py --task <id>`，把首次/最终结果与失败原因写进阶段报告。

## Phase 1.58：证据驱动的评估（Mode A / B / C）

上面那套 `runner.py` 是「自己生成 → 自己用探针看一眼 → 自己判定」，与 Validator 的证据链路
没有连接。Phase 1.58 增加一条**消费已验证证据**的评估路径：

```
Features/*/template.yaml#behavior
   → feature_behavior_evidence.py（真实 Godot，写证据包 + result.json）      [采集]
   → validator/check_behavior_evidence.py（重算观测 + 交叉验证执行产物）    [验证]
   → evaluation/evidence_adapter.py（读验证结论，重算任务期望）             [适配]
   → evaluation/evidence_eval.py（逐行为判定 + 报告）                       [评估]
```

```bash
python .ai/tools/evaluation/evidence_eval.py --list
python .ai/tools/evaluation/evidence_eval.py --evidence-dir .ai/tmp/p158/bundles          # Mode A + B
python .ai/tools/evaluation/evidence_eval.py --evidence-dir DIR --no-collect              # 禁采集
python .ai/tools/evaluation/evidence_eval.py --evidence-dir DIR --holdout-dir DIR_HOLDOUT # Holdout
python .ai/tools/evaluation/runner.py --evidence-report .ai/tmp/eval/<token>/evidence_report.json  # Mode C 接入
```

### 三种模式

| 模式 | 触发 | 证据来源 | 计入 `VERIFIED_*` |
| --- | --- | --- | --- |
| A | 任务文件 `mode: evidence`（默认） | 已有证据包，Validator 复核 | 是 |
| B | 任务文件 `mode: probe` | 本次真实采集（每 Feature 一次）后同一链路复核 | 是（采集失败则不是） |
| C | `runner.py`（旧入口） | 自带探针 | **否**，标记 `LEGACY_PROBE_ONLY` |

### 状态模型（`evidence_adapter.evaluation_status`）

`(Validator 结论, 任务期望复算) → 评估结论`，**不允许合并或升级**：

| Validator | 期望满足 | 期望不满足 | 期望无法判定 |
| --- | --- | --- | --- |
| PASS | `VERIFIED_PASS` | `VERIFIED_FAIL` | `INCOMPLETE` |
| FAIL | `INVALID_EVIDENCE` | `INVALID_EVIDENCE` | `INVALID_EVIDENCE` |
| INCOMPLETE | `INCOMPLETE` | `INCOMPLETE` | `INCOMPLETE` |
| ERROR | `EVALUATION_ERROR` | `EVALUATION_ERROR` | `EVALUATION_ERROR` |

补充：`INVALID_EVIDENCE` 的子原因（`validator_rejected_evidence` / `bundle_rejected` /
`unknown_feature` / `unknown_behavior`）只进 `reason`，不改状态；`NOT_EVALUATED` 用于
「没跑」（`collection_skipped` / `holdout_unavailable`），与 `INCOMPLETE`（跑了但证据不足）分开。

关键点：**Validator PASS 不等于 Evaluation PASS**。期望来自**任务文件**，用同一批真实观测
重算（`check_behavior_evidence.expected_holds`），不采信采集侧自报的 `status`。
所以「证据有效但行为不符合需求」会落到 `VERIFIED_FAIL`，而不是被证据包里的 `PASS` 掩盖。

### 报告与退出码

报告 `.ai/tmp/eval/<pid>-<uuid8>/evidence_report.json`（schema `evaluation_evidence_report` v1）
分块：`run` / `supported` / `evidence`（Validator 原结论 + 包级拒绝）/ `collections`（Mode B 采集命令与退出码）
/ `tasks` / `holdout` / `golden_trace` / `metrics` / `limitations`。
`metrics.evidence_validation` 与 `metrics.behavior_evaluation` 是**两个独立计数器**。

退出码：`0` = 全部任务 `VERIFIED_PASS`；`1` = 有 `VERIFIED_FAIL` / `INVALID_EVIDENCE` /
`EVALUATION_ERROR`；`2` = 有 `INCOMPLETE` / `NOT_EVALUATED`；`3` = 输入/环境错误。

### Golden Trace 与 Holdout

- `baselines/*.json` 只有场景级 `scenario_id` + `approved_behavior_version`，**没有 Feature/Behavior
  绑定**。因此逐行为 trace 比较标为 `NOT_APPLICABLE`（`binding: scenario_only`），不伪造绑定；
  真实 Expected/Actual 比较走 `--trace` + `--baseline`（复用 `trace_baselines.compare`）。
  基线审批状态为 `approved` 才接受，未审批 → `BASELINE_UNAPPROVED`，损坏 → `INVALID_BASELINE`。
- Holdout 任务独立成块；用 `--holdout-dir` 指向**另一批**证据。与训练批共用 bundle/run_id →
  `EVALUATION_ERROR` + `violations`；未提供 → `NOT_EVALUATED`（`holdout_unavailable`）。

### 测试

```bash
python .ai/tools/evaluation/tests/test_evidence_adapter.py   # 52 项：A/B/C/D/F/G 矩阵
python .ai/tools/evaluation/tests/test_evidence_eval.py      # 20 项：CLI / 退出码 / Holdout / runner 接入
```

fixture 用**真实契约**（`template.yaml#behavior`）构造证据包与 `result.json`，并用
`bundle_digest` 签名，因此测的是 Adapter/评估的判定，而不是「fixture 能否过校验」。

## Phase 1.59：L5 Mutation Harness（缺陷注入 → 现有链路判定）

`evaluation/mutation/` 是**上层工具**，不重写 Runner / Validator / Evidence Collector：
它只做三件事——在 `Features/` 的**隔离副本**里注入一处真实缺陷、跑一次真实采集+评估、
再逐字节恢复并复跑。判定一律交给 Phase 1.56–1.58 的既有链路。

```bash
# 列出 catalog（Phase 1.64 起 12 条：M01–M12，覆盖 10 个 Behavior）
python .ai/tools/evaluation/mutation/mutation_eval.py --list
# 跑单条 / 跑全部（每条 = control → mutant → recovery 三次真实采集）
python .ai/tools/evaluation/mutation/mutation_eval.py --mutation M05-openable-door-state-signal-dropped
python .ai/tools/evaluation/mutation/mutation_eval.py --all
```

| 产物 | 位置 |
| --- | --- |
| 逐条报告（含 Verdict / effectiveness 观测 / Validator / Evaluation / recovery） | `.ai/tmp/p159/reports/<mutation>.json` |
| 批次汇总（`summary-<id>.json`，退出码据此判定） | `.ai/tmp/p159/reports/` |
| 隔离副本、证据、评估输出 | `.ai/tmp/p159/runs/<mutation>-<runid>/`（默认保留，`--clean` 只删自己的目录） |

**Verdict 与 Evaluation 状态是两个独立字段**：`MUTANT_KILLED` 表示「注入的缺陷被执行链路
拒绝」，`MUTANT_SURVIVED` 表示「注入生效但链路仍然 PASS」，`INVALID_MUTANT` 表示「注入没造成
预期行为变化（探针/契约无分辨力或注入被真实执行绕过）」，`HARNESS_ERROR` / `TIMEOUT` /
`NOT_RUN` 表示这次运行本身不成立。**INVALID_MUTANT 不计入 killed/survived 分母**，
也不能被写成「检出」。

Phase 1.64 新增的两条（追加在 M01–M10 之后，源哈希与锚点唯一性均已核）：

| Mutation | Behavior | 缺陷模型 | 真实触发证据 |
| --- | --- | --- | --- |
| `M11-i-frames-window-close-not-restored` | `i_frames/iframes_expire_and_damage_resumes` | 无敌窗口到期不归还 Health 门（`_on_window_end` 里的 `set_invulnerable(false)` 换成 `pass`） | control `health.current=8` → mutant `9` |
| `M12-openable-door-open-guard-inverted` | `openable_door/open` | 幂等守卫 `==` → `!=`（门永远打不开） | control `door.is_open=true` → mutant `false` |

两条均 `MUTANT_KILLED`（control/recovery 都 `VERIFIED_PASS`、`restored_byte_for_byte=true`、`repo_guard.changed=false`）。
报告目录：`.ai/tmp/p164/mutation2/reports/`（批次汇总 `summary-3de41ad2.json`）。

退出码：`0` 全部 KILLED；`1` 有 SURVIVED / INVALID / ERROR / TIMEOUT；`2` 有 NOT_RUN（前置条件
不成立，如源文件哈希已过期）；`3` 输入/环境错误。

安全边界（`workspace.py` + `harness.py`）：只改副本里的**目标文件**（快照差异必须恰好一个文件）、
锚点必须唯一、源哈希必须匹配 catalog、括号平衡不变、路径不得逃逸 run 目录、拒绝符号链接、
清理只删带自己 ownership 标记的目录；仓库 `Features/**` 全程只读，跑完再比对哈希。
每一次 run 都记录 `repo_guard.changed`，为真直接判 `HARNESS_ERROR`。

测试：

```bash
python .ai/tools/evaluation/mutation/tests/test_mutation_harness.py      # 51 项：算子/副本/目录/verdict/清理
python .ai/tools/evaluation/mutation/tests/test_mutation_integration.py  # 15 项：真实 Godot，2 个 Feature 端到端
```

## Trace / Behavior 绑定 / Baseline 可信门禁 / Holdout 生命周期（Phase 1.60）

`evidence_eval.py` 在 1.58 语义之上叠加三层可信门禁（全部加法式，缺省行为不变）：

1. **绑定诊断**：缺省自动加载 `validator/bindings/behavior_bindings.json`（可用
   `--bindings` 显式指定）。每个任务记录 `binding_status` 诊断字段；未声明
   `expected_source` 的任务不受门禁影响（1.58 兼容）。
2. **期望来源门禁**：任务声明 `expected_source: behavior_contract | golden_trace |
   approved_baseline | combined_approved` 时，期望取自已验证绑定；缺失绑定 →
   `INCOMPLETE(binding_missing)`；失效 / 不可信 Baseline → `NOT_EVALUATED
   (baseline_unapproved / baseline_revoked / baseline_digest_mismatch /
   baseline_approval_mismatch / binding_stale / binding_scenario_mismatch /
   binding_contract_mismatch / binding_invalid)`。声明了来源就绝不静默回落到任务
   自带 expect。
3. **Baseline 使用时复核**：`baseline_report()` 重算内容摘要并与
   `validator/baselines/approval_registry.json` 的登记比对；未登记 / 被撤回 /
   摘要失配的基线不再判 PASS。

**Holdout 数据集生命周期**（`evaluation/holdout_registry.py` +
`evaluation/holdout/holdout_datasets.json`）：Holdout 任务可声明
`holdout_id` / `holdout_dataset_version`——使用前查登记、复核（SEALED + 摘要一致 +
无污染 + 非训练/调优数据），通过后登记消费（SEALED → CONSUMED）。重复使用同一
数据集会被拒绝（需显式封存新版本）；缺失时保留 1.58 的
`NOT_EVALUATED(holdout_unavailable)`，不降级为 VERIFIED_PASS。

报告新增 `binding_reconciliation` 块：正式支持集动态读取，逐场景 Trace 绑定状态、
已绑定 / 未绑定行为、Baseline 覆盖对账。

```bash
python .ai/tools/evaluation/evidence_eval.py --task E1 E2 E3   # 绑定诊断 + 基线复核
python .ai/tools/evaluation/evidence_eval.py --task E5 --holdout-dir <dir> \
    # E5 声明 holdout_id 时走数据集生命周期
```

测试：`evaluation/tests/test_cross_binding.py`（15 项）、
`evaluation/tests/test_holdout_registry.py`（23 项）、
`evaluation/tests/test_phase160_e2e.py`（5 项，真实 Godot 证据，需先采集：
`--evidence-dir .ai/tmp/p160_e2e/evidence`）。

## Provenance 集成（Phase 1.61）

`evidence_eval.py` 新增签名门禁参数（缺省不启用 = 1.58/1.60 语义不变）：

```bash
python .ai/tools/evaluation/evidence_eval.py --task E1 E2 E3 \
    --evidence-dir <dir> --require-signature          # 安全模式：缺签名/无效签名/信任根缺失一律拒绝
python .ai/tools/evaluation/evidence_eval.py --task E1 E2 E3 \
    --evidence-dir <dir> --allow-legacy [--trust-root <path>]  # 诊断模式：无效签名拒绝，缺签名标 LEGACY
```

- Evidence：逐 bundle 重算摘要并验证 sidecar `<bundle>.sig.json`；是 1.56 Integrity 与
  1.57 Artifact Cross-Validation 之后的**追加**门禁。改内容 + 重算 `payload_sha256`
  的逃逸路径被签名层封堵（require 模式 `bundle_rejected`）。
- Holdout：`holdout_registry.seal_dataset_signed()` 封存签名；消费前验证，失败细分
  `holdout_signature_missing / holdout_signature_invalid / holdout_signer_untrusted /
  holdout_digest_mismatch / holdout_revoked`（一律 NOT_EVALUATED，不伪装普通缺口），
  验证通过才 `record_usage`（一次性消费语义不变）。
- Baseline：门禁开启时 `baseline_report()` 走 `use_baseline_trusted()`，信任等级
  `LEGACY_APPROVED / CRYPTOGRAPHICALLY_VERIFIED / SIGNATURE_REQUIRED / SIGNATURE_INVALID`。
- 签名不证明执行真实性；签名者与采集器同权限时证明力等同采集器自报。
- 测试：`evaluation/tests/test_evidence_signature.py`（16）、
  `evaluation/tests/test_holdout_signature.py`（16）。

## Coverage Matrix（Phase 1.63）

```bash
python .ai/tools/evaluation/coverage_matrix.py                 # 报告成功即可存在缺口（exit 0）
python .ai/tools/evaluation/coverage_matrix.py --strict        # 有缺口 -> exit 2
python .ai/tools/evaluation/coverage_matrix.py --feature health --behavior damage
python .ai/tools/evaluation/coverage_matrix.py --include-legacy # legacy 证据计入 Evidence（仍不计 Signature）
```

八维独立状态（contract / binding / evidence / signature / attestation / evaluation /
holdout / mutation），分母 = 动态正式支持集；缺失数据用 NO_* 状态与 null，绝不编造；
INVALID Mutation 永不计入 KILLED。输出 `.ai/context/coverage_matrix.{json,md}`，
每行带 `missing_requirements` 与 `next_recommended_action`。
测试：`evaluation/tests/test_coverage_matrix.py`（15 项）。

### Phase 1.63 其余变更

- Mutation harness：每次采集用隔离 `user://` 目录（M06 修复）；catalog +M09/M10，
  全量 10/10 KILLED、0 INVALID。
- Holdout：`VALIDATED→VALIDATED` 幂等修复；`P163-HOLDOUT` 签名封存可用。
- 1.63 全链 E2E：`python .ai/tools/validator/execution/run_p163_e2e.py`
  （持久化 bundle/签名/manifest/attestation 于 `.ai/tmp/p163_e2e/`）。
