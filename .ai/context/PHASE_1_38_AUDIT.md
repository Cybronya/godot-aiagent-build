# Phase 1.38 — Feature Instance Evidence Reconciliation（审计报告）

> 状态：**已完成（2026-10-21）**。新增独立的声明 ↔ 真实 `.tscn` 对账层，
> 接入 Validator 第 7 阶段；声明不再等于证据，但也不冤枉合法结构。
> 全量 **87/87 PASS**；声明 → 实景负向对照实测可被抓住并已解压还原（sha256 一致）；
> 四条黄金基线未变；未 commit / 未 push。

## 0. 结论速览

| 项 | 结果 |
| --- | --- |
| 缺口 | `template.yaml#instance` 只是**声明证据**；1.37 之后它直接喂契约，却从未与真实场景核对 |
| 新增证据层 | `.ai/tools/scene_composer/instance_evidence.py`（声明 / 静态场景 / 运行时 三级分离） |
| 门禁 | Validator 第 7 阶段 `validator/check_instance_evidence.py`：MISMATCH/INVALID → failure；INSUFFICIENT → warning |
| 新增测试 | `test_instance_evidence_reconciliation.py`（**53 checks**，Case 1–13 + 解析受限边界 + 证据隔离附件） |
| 负向对照 | 删除真实 `CollectPickup.tscn` 的 `PickupShape` → 测试 exit 1（2 项失败）、Validator exit 1；还原后 sha256 一致、测试 exit 0 |
| 相关模块 | 10 个测试全部 exit 0（41/58/42/49/68/131/45/39/39/53 checks） |
| 全量测试 | 改动前 86/86 → 改动后 **87/87 PASS（exit 0）** |
| Validator | **0 error / 17 warning（exit 0）**，警告数与 1.37 收尾一致 |
| 黄金基线 | sha256 / mtime **未变化** |
| 兼容性 | 未声明 `instance:` 的 Feature 仍 `NOT_DECLARED`（不强制迁移、无新增失败） |

## 1. 执行前审计

| 项 | 值（实测） |
| --- | --- |
| 仓库根 | `F:\Godot_v4.7-stable\game` |
| HEAD / 分支 | `1c30f94` / `master` |
| 暂存区 | **空**（`git diff --cached` 无输出） |
| 工作区 | 30 修改 + 6 未跟踪（36 项）——Phase 1.26–1.37 的未提交增量 + 1.37 新增文件 |
| 黄金基线 | holdout `acf8bfbac8abf774` / multi_stage_boss `5736788cd9efd866` / single_stage_boss `d540cfe2226216e0` / waves `878691b1d174cbf0` |
| 全量测试（改动前） | **86/86 PASS**（1.37 收尾时点，`regression_137_after2.log`） |

审计读过的关键文件：`Features/FEATURE_SCHEMA.md` §7.1、6 个 `template.yaml`、
`external_artifact_resolver.py`、`artifact_evidence_validator.py`、
`component_instance_ownership.py`、`scene_composer.py`、`scene_intent.py`、
`validator/check_scene_composition.py`、`validator/validate.py`、`PHASE_1_37_AUDIT.md`。

前序报告的风险条目与实际一致：`instance:` 的证据仍是声明、运行时未核验。

## 2. 现有契约与证据链分析

现状（1.37 之后）：

```
Feature template.yaml#instance  ──声明（未核验）──►  Scene Intent  ──►  Capability Contract
                                                                    （只读计划，不读 .tscn）
生成物 .tscn  ──►  Artifact Evidence（compose 时，写盘后核验声明与**生成物**）
```

已存在的核验（`artifact_evidence_validator._verify_declared_instance`）有两个结构性缺口：

1. **只在组合时发生**：未参与组合的 Feature 声明永远不会被核对；
2. **子节点可以「在别处」**：只要某个证据池里存在同类型节点就算满足 —— 于是
   「A 声明 CollisionShape2D，形状其实来自 B 的场景」也会 PASS。

1.37 新增的 `test_feature_instance_evidence.py` 虽然在测试期解析 `.tscn`，但那是**测试**，
不是门禁：任何人直接改模板 + 场景不同步，仍能让 Validator 全绿。

结论：需要一个**独立于生成流程**的、以真实 `.tscn` 为输入的对账层，并且必须能区分
「已证实缺失」与「静态证据不足」。

## 3. 证据模型（设计决策）

| 证据 | 来源 | 能证明 | 不能证明 | 缺失时 |
| --- | --- | --- | --- | --- |
| declaration | `template.yaml#instance` | 预期（需要哪些节点结构） | 实例真的存在 | 声明非法 → `INVALID` |
| static_scene | `.tscn` 文本（复用 `parse_scene_text`） | 文件里实际写着的节点类型 / 层级 / 场景实例 / 引用 | 运行时场景树 | 不可读 → `INVALID`；结构不认识 → `INSUFFICIENT` |
| runtime | Godot 探针 / `runtime_result` | 加载后的真实对象与行为 | 本层不产生 | 需要它时结论必须是 `INSUFFICIENT` |

### 3.1 状态语义

| 状态 | 触发条件 | Validator |
| --- | --- | --- |
| `PASS` | 根类型一致；每个声明子类型（含重复计数）都能在根的直接子节点找到 | 计数 |
| `MISMATCH` | 根类型不符 / 子节点缺失 / 层级错误 / 数量不符 / 重复节点路径 | **failure** |
| `INSUFFICIENT` | 声明为运行时创建（`runtime_children`）却静态找不到；或解析器不认识部分节点头部；或 runtime 声明已过期 | warning |
| `INVALID` | 声明非法（未知类型 / 字段形态错 / `runtime_children ⊄ children`）、场景不可读、无根节点 | **failure** |
| `NOT_DECLARED` | 旧 Feature 没有 `instance:` | 计数（不强制迁移） |

### 3.2 被拒绝的替代方案

| 方案 | 拒绝理由 |
| --- | --- |
| 用 Godot 原生加载（`--headless` + PackedScene）作唯一证据 | 会得到真正的运行时结构，但 Validator 必须能在没有 Godot / 未导入缓存的环境运行；把它作为唯一证据会让门禁依赖引擎。**保留为后续 runtime 层**，本层只做静态部分并如实标注缺口。 |
| 「场景里有脚本 ⇒ 缺节点算证据不足」 | 会把真实缺失全部洗白：负向对照中的 `collect_pickup` 恰好带脚本，若按此规则就会变成 warning。改为**显式列名** `runtime_children`。 |
| 把声明扩展成「节点名 + 路径 + 资源」全量契约 | 现有声明只表达类型结构；擅自扩充语义会迫使批量改写 Feature（本阶段非目标）。保持向后兼容的最小增量。 |
| 直接改写 `artifact_evidence_validator` 的返回结构 | 既有测试对 `artifact_evidence` 报告做**逐字比较**；加键会迫使放宽断言（禁止）。改为新增独立层 + 门禁。 |
| 让生成器把预期对象交给核对器 | 会形成「自己核对自己」。核对器只读 Feature 模板与 `.tscn` 文本；测试用 AST 锁定它不 import 生成链模块。 |

## 4. 实施

| 文件 | 目的 |
| --- | --- |
| `.ai/tools/scene_composer/instance_evidence.py`（新增） | 对账核心：`reconcile_declaration` / `reconcile_feature` / `reconcile_component_mounts` / `reconcile_all` / `summarize` + 诊断 CLI |
| `.ai/tools/validator/check_instance_evidence.py`（新增） | Validator 第 7 阶段封装：failure / warning 映射，`--json` 可机读 |
| `.ai/tools/validator/validate.py` | 接入 `report_instance_evidence`（阶段 7，输出 `Feature instance evidence: 6 declared / 12 checked`） |
| `.ai/context/scene_composer_schema.yaml` | 新增 `feature_instance_evidence_reconciliation` 契约段（三级证据 / 状态 / 字段 / 规则 / 集成点） |
| `Features/FEATURE_SCHEMA.md` | §7.2：对账结论表、`runtime_children` 用法、CLI/Validator 入口 |
| `.ai/context/CONTRACT_INDEX.yaml` | 新增 `instance_evidence` 条目；Validator 集成阶段 + 独立 CLI 列表 |
| `.ai/tools/scene_composer/tests/test_instance_evidence_reconciliation.py`（新增） | 53 checks 回归（见 §5） |

### 4.1 核对规则（实现即契约）

- 根类型：`instance.node_type` 必须等于**真实场景根节点类型**（根不可能由脚本动态创建）。
- 子节点：按**直接子节点类型**计数；同一类型出现 n 次 = 需要 n 个。
- 层级错误：类型存在但在更深层 → `INSTANCE_CHILD_PATH_MISMATCH`，附实际路径。
- 重复路径：同一节点路径出现两次 → 失败（避免「重复挂载/重复实例」被静默接受）。
- 解析受限：`[node ...]` 行多于解析结果 → warning，**不判无效**（不因解析能力不足冤枉场景）。
- 运行时可确认性：只有显式 `runtime_children` 的类型允许 `INSUFFICIENT`。
- 挂载模式（生成物）：组件必须**恰好挂载一次**、引用的必须是模板声明的入口场景；
  声明子节点只能出现在「该组件挂载子树」或「组件自身场景」，不接受别的组件的同名节点。

## 5. 测试与负向对照

新增测试 `test_instance_evidence_reconciliation.py`，**53 checks**：

| Case | 覆盖 | 断言要点 |
| --- | --- | --- |
| 1 | 仓库 6 个声明 | 全部 `PASS`（真实文件，非夹具） |
| 2 | 声明要求子节点、场景缺失 | `MISMATCH` / `INSTANCE_CHILD_MISSING`，severity=error |
| 3 | 错误场景引用（根类型不符） | `INSTANCE_ROOT_TYPE_MISMATCH`，含两种类型与根路径 |
| 4 | 节点层级错误 | `INSTANCE_CHILD_PATH_MISMATCH`，`node_path=Probe/Container/Shape` |
| 5 | 多实例数量不符 | `INSTANCE_CHILD_COUNT_MISMATCH`（declared 2, found 1）；两个形状则 PASS |
| 6 | 非法声明 ×4 | 未知类型 / children 非列表 / runtime ⊄ children / 缺 node_type → `INVALID` 且指出字段 |
| 7 | 合法额外节点 | 额外兄弟、`Timer`、深层节点均不误报 |
| 8 | 动态创建 / 声明过期 | 缺 runtime 子节点 → `INSUFFICIENT`（warning，evidence=runtime）；静态已存在 → 过期 warning |
| 9 | 挂载模式 ×5 | 正确挂载 PASS；重复挂载 / 错误场景引用 / 缺挂载 / 子节点只在别的组件里 → `MISMATCH` |
| 10 | D8 不回归 | 菱形引用（Host → A、Host → B → A）解析仍 `PASS` |
| 11 | 场景不可用 | 缺文件 / 无根节点 → `INVALID` |
| 11b | 解析能力受限 | 多一行无法解析的节点头部 → `INSUFFICIENT`（仅 warning），Validator 不报 failure |
| 12 | 旧 Feature | 未声明 → `NOT_DECLARED`，零 findings |
| 13 | Validator 阶段 | 仓库无 failure；坏夹具 → failure；INSUFFICIENT → warning（不入 failure） |
| 附件 | 证据隔离 / 只读 | 不 import `scene_intent`/`scene_composer`/`scene_builder`/`artifact_evidence_validator`；无写调用；`open()` 只读；不启动 Godot；对账后真实场景字节不变 |

### 5.1 真实仓库负向对照（针对最终版本重做）

```text
sha256(Features/collect_pickup/CollectPickup.tscn)
  = a55453953a240838246f727ddd7debc9b68d235ade24dd7b82baacf55064191d   （对照前）

# 删除场景中的 PickupShape 节点（模板声明仍要求 CollisionShape2D）
python .ai/tools/scene_composer/tests/test_instance_evidence_reconciliation.py
  -> exit 1；2 failing check(s)
     - case1: collect_pickup PASS against its real scene | status=MISMATCH ...
     - case13: the repository has no instance evidence failure

python .ai/tools/validator/check_instance_evidence.py
  -> exit 1
     collect_pickup  MISMATCH  .../CollectPickup.tscn
       - [error] Instance evidence mismatch: CollisionShape2D missing
     Feature instance evidence: collect_pickup Instance evidence mismatch: CollisionShape2D missing (CollectPickup)

# 还原
sha256sum -c before.sha  -> Features/collect_pickup/CollectPickup.tscn: OK
测试 -> exit 0（53 PASS）；Validator -> exit 0；git diff 该文件为空
```

负向对照在**最终版本（含 Case 11b）上重做了一次**，结论相同：测试 exit 1
（`2 failing check(s)`，日志计 3 行 FAIL 含汇总行），Validator exit 1，还原后 53 PASS。

注意：该场景**带有脚本**，但缺失的 `CollisionShape2D` 未声明为 `runtime_children`，
所以结论是 `MISMATCH` 而不是 `INSUFFICIENT` —— 这正是「脚本存在不等于可以洗白」的证明。

## 6. 验证矩阵

| 命令 | 退出码 | 结果 |
| --- | --- | --- |
| `scene_composer/tests/test_instance_evidence_reconciliation.py` | 0 | **53 PASS / 0 FAIL** |
| `scene_composer/instance_evidence.py --all` | 0 | 6 declared，全部 PASS |
| `scene_composer/instance_evidence.py --blueprint slime_enemy.yaml --scene Scenes/SlimeEnemy.tscn` | 0 | 挂载模式 PASS |
| `validator/check_instance_evidence.py` | 0 | 12 checked / 6 declared / 0 failure |
| `scene_composer/tests/test_feature_instance_evidence.py` | 0 | 41 PASS（1.37 回归） |
| `scene_composer/tests/test_component_instance_materialization.py` | 0 | 58 PASS |
| `scene_composer/tests/test_capability_contract_validator.py` | 0 | 42 PASS |
| `scene_composer/tests/test_scene_composer.py` | 0 | 49 PASS |
| `scene_composer/tests/test_scene_intent_contract.py` | 0 | 68 PASS |
| `scene_composer/tests/test_feature_capability_adoption.py` | 0 | 131 PASS |
| `scene_composer/tests/test_external_artifact_evidence.py` | 0 | 45 PASS（D8 Case 5c 仍通过） |
| `scene_composer/tests/test_artifact_evidence_validator.py` | 0 | 39 PASS |
| `scene_composer/tests/test_component_instance_ownership.py` | 0 | 39 PASS |
| `python .ai/tools/run_tests.py` | 0 | **87/87 PASS**（`regression_138_final2.log`，最终代码） |
| `python .ai/tools/validator/validate.py` | 0 | **0 error / 17 warning**（`p138_validator_final.log`） |

黄金基线（与开工前一致）：

```
holdout.json           acf8bfbac8abf774 1792338912178038700
multi_stage_boss.json  5736788cd9efd866 1792246741472536400
single_stage_boss.json d540cfe2226216e0 1792246741774880700
waves.json             878691b1d174cbf0 1792334346613330400
```

## 7. 已知限制与剩余风险

| 编号 | 限制 / 风险 | 影响 | 后续 |
| --- | --- | --- | --- |
| R1 | **纯静态**：不加载 PackedScene，运行时增删的节点不可见 | 需要运行时证据的声明只能到 `INSUFFICIENT` | 后续用 `--runtime-scene` 探针补运行时对账 |
| R2 | `runtime_children` 是**声明式豁免**：作者可滥用它把缺失降级成 warning | 会把问题从 failure 变成 warning（仍可见，不会 PASS） | 后续可要求运行时证据与豁免项一一对应；或在报告中列出豁免清单 |
| R3 | 挂载模式**未接入 compose 门禁**（只进 Validator 测试与 CLI） | 生成阶段仍沿用 `artifact_evidence` 的「子节点可在别处」宽松规则 | 若允许改变 artifact 报告形态，可在下一个阶段把挂载对账并入 compose |
| R4 | 解析器只认标准 `[node ...]` 头部；不读 `[connection]`、脚本内容、`sub_resource` | 信号连线 / 脚本动态节点无法静态证明 | 明确记录；信号连线属 1.37 D4 范围 |
| R5 | `template.scene.source` 与 `feature.yaml composition.entry_scene` 不一致时未交叉校验 | 声明可能对着错误的入口场景对账 | 候选：下一阶段加入入口一致性检查 |
| R6 | `INSUFFICIENT` 不影响 `run_tests.py` 退出码（只由 Validator 报 warning） | 静态证据不足不会阻断 CI | 需与团队约定是否升级为 failure |
| R7 | 重复实例检测只在「同一路径重复」层面 | 不同名字、同一资源的重复挂载由挂载模式的计数覆盖，Feature 级不覆盖 | 已由 mount 模式补足一半 |

非目标（本项目阶段未做，按任务书）：F5 / janitor CLI、`.godot` 并发治理、大规模 Feature 重构、
`--waves` / 通用信号连线 / 通用多实例系统、Planner/Orchestrator 重写。

## 8. 最终 Git 状态

- 实测 `git status --porcelain`：**41 项（30 修改 + 11 未跟踪）**，相比开工前的 36 项净增
  4 个本阶段新文件 + `validate.py` 集成。
- 暂存区：**空**；未 commit、未 push。
- 本阶段新增（未跟踪）：
  - `.ai/context/PHASE_1_38_AUDIT.md`（本文件）
  - `.ai/tools/scene_composer/instance_evidence.py`
  - `.ai/tools/validator/check_instance_evidence.py`
  - `.ai/tools/scene_composer/tests/test_instance_evidence_reconciliation.py`
- 本阶段修改：
  - `.ai/tools/validator/validate.py`（阶段 7）
  - `.ai/context/scene_composer_schema.yaml`（新契约段）
  - `.ai/context/CONTRACT_INDEX.yaml`（条目 + Validator 阶段）
  - `Features/FEATURE_SCHEMA.md`（§7.2）
  - `.ai/context/CURRENT_TASK.md`、`.ai/context/WORK_STATE.md`、`.ai/context/SESSION.md`（同步）
- 既有未提交增量（Phase 1.26–1.37、用户自有文件 `.workbuddy/memory/*`）**未触碰**；
  唯一一次写入既有文件是负向对照删除/还原 `Features/collect_pickup/CollectPickup.tscn`，
  已用 `sha256sum -c` 证明与原始内容一致，`git diff` 为空。
- 共享产物目录（`Scenes/`、`Tests/`、`Levels/`）无探针/评估残留；`.ai/tmp/` 下日志为易失证据。
