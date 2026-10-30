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
