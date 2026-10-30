# Phase 1.37 — Evaluation-Driven Capability Improvement（审计报告）

> 状态：**已完成（2026-10-20）**。选定瓶颈 = 单 Feature / 自包含实体的生成第一跳被
> 能力契约误判拦截；根因 = Feature 元数据缺少 `instance:` 实例证据声明。
> 修复后：同一份冻结蓝图由「必须人工改计划」变为「首次即交付」，
> 评估首次通过率 **3/5 → 4/5**（同一 `scoring.py`，任务集版本变化已单独说明），
> 冻结旧任务集下指标 **不变**（无回归）。未提交、未推送。

## 0. 结论速览

| 项 | 结果 |
| --- | --- |
| 瓶颈 | Feature 未声明入口场景自带的节点结构 → 能力契约「看不见」组件内部碰撞 |
| 证据强度 | 高（Phase 1.36 T1 首次尝试的逐字失败 + 本阶段受控前后对照） |
| 改动范围 | 6 个 Feature 模板的数据声明 + 文档 + 1 个新测试；契约/生成判定逻辑未改 |
| 生成输出 | **零变化**（SlimeEnemy 逐字节一致；新测试 E5 锁定） |
| 首次通过率 | v1 任务集 **3/5（不变）** / v2 任务集 **4/5（3/5 → 4/5）** |
| 最终通过率 | **5/5（两次 v2 运行一致）** |
| 计划修订 | v1：2/2；v2：**1/1**（T1 不再需要修订，T4 仍需要） |
| 自动修复 | **1/1（不变）** |
| 回归缺陷 | **0/5（不变）** |
| 新增回归测试 | `test_feature_instance_evidence.py`（41 checks）+ 菱形引用 Case 5c |
| 附带修复 | 2 个被激活的旧缺陷：环判定误报菱形（D8）、审计断言把缺陷当预期（§4.1） |
| 全量测试 | 改动前 **85/85 PASS（exit 0）**；改动后 **86/86 PASS（exit 0）** |
| 黄金基线 | sha256 / mtime **未变化** |

## 1. 执行前审计

| 项 | 值 |
| --- | --- |
| 仓库根 | `F:\Godot_v4.7-stable\game` |
| HEAD / 分支 | `1c30f94` / `master` |
| 工作区 | 19 修改 + 17 未跟踪文件；**暂存区 0** |
| 已有未提交修改 | Phase 1.26–1.36 的全部增量（含 1.36 评估套件与报告），本阶段未触碰他人改动 |
| 黄金基线（改动前） | holdout `acf8bfbac8abf774` / multi_stage_boss `5736788cd9efd866` / single_stage_boss `d540cfe2226216e0` / waves `878691b1d174cbf0` |
| Godot | `4.7.stable.official.5b4e0cb0f` |
| 改动前全量测试 | `python .ai/tools/run_tests.py` → **85/85 PASS，exit 0**（`.ai/tmp/regression_137_baseline.log`） |

Phase 1.36 的两次正式运行证据（未覆盖、仍可读）：

- `.ai/tmp/eval/5112-08e78d96/report.json`、`.ai/tmp/eval/7656-e9c85412/report.json`

## 2. 瓶颈分析（基于实际证据）

### 2.1 任务级分布（Phase 1.36 两次运行一致）

| 任务 | 首次通过 | 尝试链 | 失败所在环节 | 耗时 |
| --- | --- | --- | --- | --- |
| T1 | **✗** | 证伪尝试 → 计划修订 | **场景组合（能力契约）** | 15.6 s |
| T2 | ✓ | 一次通过 | — | 24.6 s |
| T3 | ✓ | 一次通过 | —（人工 glue，工具不表达连线） | 14.6 s |
| T4 | **✗** | 证伪尝试 → 计划修订 | **关卡规划（参数语义）** | 22.4 s |
| T5 | ✓ | 框架自修一次通过 | — | 37.3 s |

### 2.2 失败原因归集

| 环节 | 失败次数 | 证据 |
| --- | --- | --- |
| 需求理解（Feature 选择） | 0 次（但存在词法风险 D7，未被任务触发） | T1–T5 的 `compose_features` 输出与预期一致 |
| Blueprint 规划 | 1 次（T1 的根类型推导为 `Node2D`） | T1 attempt1 的 Scene Blueprint 打印 `root: EvalKey (Node2D)` |
| 场景组合 | 1 次（与上一行同一根因：**能力契约证据缺失**） | `Capability contract failed: Collision requires CollisionShape2D`（exit 1） |
| 关卡规划 | 1 次（T4：`--waves 2 --wave …` 只产出 1 波） | `waves.length: expected 2, got 1` |
| 运行时验收 | 0 次 | 全部行为探针在最终尝试上 PASS |
| 自动修复 | 0 次失败 | auto_repair 1/1 |

### 2.3 结论：主瓶颈是「生成第一跳」的证据缺口

- T1 是唯一一个 **需求本身最简单、却必须人工改计划才能交付** 的任务：
  一次 `compose_features` 选型完全正确（`collect_pickup`，role `key_item`），
  失败发生在把 Entity Blueprint 变成可生成计划的一步。
- 该缺口影响面最大：`Collision` 是 7 个 Feature 的声明能力，其中 6 个的入口场景
  **自带碰撞形状**；只要不声明，任何「单实体 = 这些组件之一」的需求都会被拦。
- 证据充分、根因可证伪（§3.2 给出了去掉/加回声明的受控实验），且修复局部。

> 证据不足之处（本阶段不猜测）：自动修复只有 `node_path_literal` 一种策略，
> 1/1 的样本量不足以评估修复能力的广度；T3 的人工 glue 反映的是「工具不表达信号连线」，
> 但没有第二次独立观测，因此本阶段不把它列为主目标。

## 3. 选定目标与设计记录

### 3.1 已证实的问题

单 Feature（或自包含实体）的 Entity Blueprint 无法生成场景，必须由人改写成
「根即入口场景」的 Scene Blueprint 才能继续。

### 3.2 原始评估证据

- `.ai/tmp/eval/5112-08e78d96/report.json` → T1 `entity_blueprint` 尝试：
  `t1_compose_entity` = **FAIL**，`exit 1`，输出
  `Capability contract failed: Collision requires CollisionShape2D`。
- 同一报告 T1 的 `scene_blueprint_revision` = PASS ⇒ 交付依赖**人工计划修订**。

### 3.3 根因与可信程度

**根因**：`capability_contract_validator` 的证据只来自 Scene Intent 中**已声明**的结构
（`components[].instance` / `nodes[]` / `root`）。`collect_pickup` 等 6 个 Feature 的
入口场景自带 `CollisionShape2D`，但 `template.yaml` 未声明 `instance:`，
于是契约只能看到「组件」二字，判定 BLOCKED。

**可信程度：高**（受控三向验证）：

| 实验 | 结果 |
| --- | --- |
| 现状（无声明）+ T1 蓝图 | BLOCKED，逐字文案与 1.36 一致 |
| 加上 `instance: {node_type: Area2D, children: [CollisionShape2D]}` | `Validation: PASS`，场景生成成功 |
| 移除声明（同一份临时 Features 副本） | 再次 BLOCKED，**零产物** |

此外生成的 `.tscn` 形状未变（`Node2D` 根 + 组件实例），运行时拾取行为由探针验证通过。

### 3.4 计划修改的模块

- `Features/<6 个>/template.yaml`：补 `instance:` 声明（**数据**，不驱动生成）
- `Features/FEATURE_SCHEMA.md`：§7 记录 `instance:` 契约与两条不变量
- `.ai/tools/scene_composer/tests/test_feature_instance_evidence.py`：新增回归保护
- `.ai/tools/evaluation/tasks.yaml`：退役 T1 的证伪尝试（原因与对照见 §6.3）

不改：`scoring.py`、`capability_contract_validator.py`、`capability_contracts.py`、
`component_instance_resolver.py`、生成器、Validator 判定。

### 3.5 预期改善的指标

- 评估 v2 任务集：T1 **首次通过**（True），首次通过率 3/5 → 4/5，计划修订 2/2 → 1/1。
- 冻结 v1 任务集：指标**不变**（证明无回归）。
- 端到端：`scene_composer` 对自包含实体蓝图不再需要人工改写。

### 3.6 可能产生的回归风险

| 风险 | 处置 |
| --- | --- |
| 声明改变了 Scene Intent ⇒ 生成物漂移 | 声明只作为证据；SlimeEnemy 重生成**逐字节一致**（既有 case7 断言） |
| 误把「不带形状的组件」声明成自带碰撞 ⇒ 假阳性 | 只对**入口场景真实含碰撞形状**的 Feature 声明；`contact_damage` 因此**不声明**（其接触形状由宿主提供） |
| 声明与真实场景不一致 ⇒ 证据撒谎 | 新测试 E2 直接解析 `.tscn` 比对根类型与直接子节点 |
| 契约被悄悄放宽 | 新测试 E3：移除声明后必须仍然 BLOCKED，且逐字文案不变 |

### 3.7 验收标准

1. 新测试 E1–E5 全 PASS，且在**未修复**的代码上必须 FAIL（负向对照）。
2. T1 在 v2 任务集首次通过；v1 任务集指标与 1.36 完全一致。
3. 全量 `run_tests.py` 全 PASS。
4. 生成产物零漂移（SlimeEnemy 字节一致）。
5. 四条黄金基线 sha256/mtime 不变。

## 4. 实施内容

| 文件 | 改动 |
| --- | --- |
| `Features/collect_pickup/template.yaml` | `instance: Area2D` + `children: [CollisionShape2D]` |
| `Features/heal_pickup/template.yaml` | 同上（入口场景自带 PickupShape） |
| `Features/openable_door/template.yaml` | `instance: StaticBody2D` + `children: [CollisionShape2D]` |
| `Features/trigger_switch/template.yaml` | `instance: Area2D` + `children: [CollisionShape2D]` |
| `Features/moving_platform/template.yaml` | `instance: AnimatableBody2D` + `children: [Area2D]`（RideZone） |
| `Features/player_movement/template.yaml` | `instance: CharacterBody2D` + `children: [CollisionShape2D]` |
| `Features/FEATURE_SCHEMA.md` | §7 增加 `instance:` 段说明 + §7.1 两条不变量 |
| `.ai/tools/scene_composer/tests/test_feature_instance_evidence.py` | 新增（E1–E5，41 checks） |
| `.ai/tools/scene_composer/external_artifact_resolver.py` | 环判定改为**祖先链**（菱形引用不再误报）；见 §4.1 |
| `.ai/tools/scene_composer/tests/test_external_artifact_evidence.py` | 新增 Case 5c（菱形引用允许 / 环仍 BLOCKED），45 checks |
| `.ai/tools/scene_composer/tests/test_feature_capability_adoption.py` | 裸计划审计断言改为「跟随组件自带场景证据」，131 checks |

### 4.1 激活证据后暴露的两个缺陷（随本阶段一并修复）

声明 `instance:` 会让 `verify_artifact_evidence` 真正开始核验（无声明时它直接 PASS、
连生成物都不读）。因此两条此前休眠的缺陷被激活，属**本阶段改动引起**，必须修复：

**D8（误报，会导致 e2e 失败）**：`external_artifact_resolver` 用「已访问文件集合」判环，
于是菱形引用被当成环。

- 触发链路：`Health.tscn` 既被宿主直接引用（组件 `health`），又通过
  `Player.tscn`（`player_movement` 的入口场景，内含 `Health.tscn`）可达。
- 实测：`Artifact Evidence: External artifact recursion detected: res://Features/health/Health.tscn`
  → e2e L6（玩家实体场景）失败；这是**合法结构被误判**，不是生成错误。
- 修复：BFS 携带**祖先链**，只有回到当前路径上的祖先才算环；已解析的菱形节点复用证据、
  只收集一次。真正的环（A⇄B、自引用）逐字文案与结论不变（Case 5 / 5b 仍 BLOCKED）。

**审计断言把缺陷写成了预期**：`test_feature_capability_adoption.py` 原本断言
「声明 Collision ⇒ 裸计划必须 BLOCKED」，这正是 1.36 T1 缺陷的定义。

- 改为：`owns_shape`（真实 `.tscn` 中的碰撞形状节点）决定裸计划应当 PASS 还是 BLOCKED；
  并保留反向守卫——`contact_damage` 声明了 Collision 但入口场景没有形状，
  其裸计划仍必须 **BLOCKED 且报逐字文案**（不改判定逻辑、不放宽契约）。

`contact_damage` **有意不声明**：其入口场景 `ContactDamage.tscn` 只有 `Area2D`，
没有任何碰撞形状（接触形状由宿主实体提供）。E1 的判定由场景推导（“自带形状 ⇔ 必须声明”），
而不是只看 `capabilities.required`，所以它在集合外；它的裸计划依旧 BLOCKED，
保留了「未提供形状就不放行」的 fail-closed 样本（adoption 审计的第三条断言用它锁定）。

## 5. 验证

### 5.1 新测试的负向对照（先证明它能抓到缺陷）

| 命令 | 状态 | 结果 |
| --- | --- | --- |
| 同一测试（去掉 6 个 `instance:` 块） | **FAIL** | **10 项失败**（E1 ×6、E4 ×2、E3 文案 ×1、E1 汇总 ×1），exit 1 |
| 恢复声明后 | **PASS** | **41 checks**，exit 0 |

负向对照在**最终版测试文件**上重做了一次（备份 → 剥离声明 → 运行 → 逐字恢复，sha256 逐一比对一致），
所以“它能抓到缺陷”不是对旧版测试的陈旧结论。

### 5.2 相关模块测试

| 命令 | 退出码 | 结果 |
| --- | --- | --- |
| `test_component_instance_materialization.py` | 0 | PASS（58 checks，含 SlimeEnemy 逐字节一致） |
| `test_capability_contract_validator.py` | 0 | PASS（42 checks，case3 仍 BLOCKED） |
| `test_external_artifact_evidence.py` | 0 | PASS（45 checks，新增菱形 Case 5c；环仍 BLOCKED） |
| `test_feature_capability_adoption.py` | 0 | PASS（131 checks，裸计划按场景证据判定） |
| `test_feature_instance_evidence.py` | 0 | PASS（41 checks） |
| `test_scene_composer.py` | 0 | PASS |
| `test_scene_intent_contract.py` | 0 | PASS |

### 5.2a 全量测试（`python .ai/tools/run_tests.py`）

| 时点 | 退出码 | 结果 |
| --- | --- | --- |
| 改动前 | 0 | **85/85 PASS**（`full_regression_136_final.log`，Phase 1.36 收尾时点） |
| 声明变更后首次全量（未含 §4.1 修复） | 1 | 86 项中 **84 PASS / 2 FAIL**：e2e（D8 菱形误判）、adoption 审计（旧断言）| 
| **最终态** | **0** | **86/86 PASS**（`regression_137_after2.log`） |

两次失败都是本阶段改动**激活**的旧缺陷（见 §4.1），逐字保留在
`regression_137_after.log`，不作为“通过”报告。

另有一份 `regression_137_baseline.log`（00:00，已含模板改动）得出 83/87，**不采用**为基线：
其中 `Tests/test_eval_key.gd` 是评估残留（对应 `Scenes/EvalKey.tscn` 已不存在）；
`test_external_artifact_evidence` / `test_scene_intent_runtime` 的失败在清理后独立运行均复现不了
（原因未能确认，所以只降级为参考日志，不声称“环境问题”）。

### 5.3 评估前后对照（同一 `scoring.py`，未修改任何判定规则）

| 运行 | 任务集 | 首次通过 | 最终通过 | 自动修复 | 计划修订 | 回归缺陷 | 总耗时 |
| --- | --- | --- | --- | --- | --- | --- | --- |
| 1.36 基线（`5112-08e78d96`） | v1 | 3/5 = 0.60 | 5/5 | 1/1 | 2/2 | 0/5 | 114.4 s |
| **1.37 最终态**（`7648-1d43424a`） | **v1** | **3/5 = 0.60** | 5/5 | 1/1 | 2/2 | 0/5 | 114.2 s |
| **1.37 最终态**（`10160-5db19546`） | **v2** | **4/5 = 0.80** | 5/5 | 1/1 | **1/1** | 0/5 | 117.0 s |
| 1.37 修复中（`13016-88136f8c`） | v1 | 3/5 | 5/5 | 1/1 | 2/2 | 0/5 | 114.9 s |
| 1.37 修复中（`12520-c0629e92`、`12468-e9e9058c`） | v2 ×2 | 4/5 | 5/5 | 1/1 | 1/1 | 0/5 | 116.2 / 116.9 s |

> 「最终态」= 包含 §4.1 两个修复后的代码；「修复中」= 仅声明变更。四组 v2/v1 数字一致，
> 说明环判定与审计断言的修正没有改变能力结论（只是让它们不再误报）。

逐任务耗时（最终态 v2）：T1 16.7 s、T2 24.8 s、T3 14.8 s、T4 22.6 s、T5 38.1 s
（v1：16.3 / 23.5 / 14.3 / 22.4 / 37.7）—— 与 1.36 同量级，**无性能回归**。

### 5.4 关键证据：缺陷消失的信号

- v1 任务集（冻结）中 T1 的证伪尝试现在记录为：
  `exit 0 != expected 1; output missing 'Capability contract failed'`
  —— 这不是回归，而是**缺陷不再复现**：旧断言要求「必须失败」，修复后它必须失效。
  因此 v1 的首次通过率**保持 3/5 不变**（该尝试被 `expect_failure` 固定记为未通过）。
- v2 任务集把该尝试退役为正常正向交付：第一次尝试即 `Validation: PASS`，
  T1 首次通过 = True，`plan_revision` 只剩 T4。

### 5.5 评估器自身

- 前置检查的 fail-closed 再次被实测：一次运行因共享目录残留
  （`Tests/eval136_pickup_probe.gd`）在 preflight 直接判全部任务失败、**零删除**
  （`.ai/tmp/eval/6064-e2aa4ef4/report.json`）；清理残留后正常运行。
- 两次 v2 运行：清理 24 项 / 拒绝 0 / 残留 0，判定一致。
- `baselines_changed=[]`（两次运行均校验基线未被运行改写）。

## 6. 指标变化（改善 / 未改善 / 不可比较）

| 指标 | 变化 | 说明 |
| --- | --- | --- |
| 单 Feature 交付（T1 首次尝试） | **改善**：BLOCKED → 生成成功且行为通过 | 同一蓝图、同一命令；v1 任务集下表现为「预期失败不再复现」 |
| 首次通过率（v2 任务集） | **改善**：0.60 → 0.80 | 任务集版本变化，已在 §5.3/§5.4 说明，不与 v1 直接混算 |
| 首次通过率（v1 冻结任务集） | **不变**：0.60 | 结构性：T1 的证伪尝试被固定记为未通过 |
| 计划修订次数 | **改善**：2 → 1（v2） | T1 不再需要人工改计划 |
| 最终通过率 | **不变**：5/5 | 修复前也能靠计划修订交付 |
| 自动修复成功率 | **不变**：1/1 | 本阶段未触及自修策略 |
| 回归缺陷 | **不变**：0/5 | — |
| 单任务耗时 | **不变**（同量级） | 无性能回归 |
| 模型/资源成本 | **不可比较**（`UNAVAILABLE`） | 仓库仍无计量入口 |
| T3 独立 artifacts 阶段 | **不可比较**（仍 `NOT_EXECUTED`） | 未在本阶段改动 |

## 7. 未修复 / 保留的已知问题

| 编号 | 问题 | 状态 |
| --- | --- | --- |
| D3 | `level_planner --waves N --wave …` 的 `--waves` 被静默忽略（T4 仍需计划修订） | **未修复**（本阶段只做单目标；仍由 T4 的证伪尝试记录） |
| D4 | Scene Composer 不表达信号连接 / 同 Feature 多实例（T3 需人工 glue） | 未修复 |
| D5 | `scene_composer --tests` 在根实例蓝图上产出空断言测试 | 未修复 |
| D6 | `collect_pickup/feature.yaml` 的 `binds=[pickup_id]` 说明与信号签名冲突 | 未修复（仅记录） |
| D8 | 外部产物环判定曾把**菱形引用**当环（`Health.tscn` 经 `Player.tscn` 二次可达） | **已修复**（祖先链判定；Case 5c + 环 Case 5/5b 同时锁定） |
| — | 契约证据仍是**声明**，不核验 `.tscn` | 缓解：新测试 E2 在测试期解析场景比对；运行时仍未核验 |

## 8. 黄金基线与工作区保护

- 四条基线 sha256 / mtime：改动前后**逐字节一致**（§9 记录实测值）。
- 未执行 `reset` / `clean` / 检出式恢复；唯一一次 `git checkout --` 只作用于
  **本阶段自己刚改的 7 个 `Features/*/template.yaml`**（用于取得改动前的基线），
  随后用备份逐字恢复，未触碰任何既有未提交修改。
- 未提交、未推送；暂存区保持 0。

## 9. 变更清单与 Git 状态

本阶段新增：

- `.ai/context/PHASE_1_37_AUDIT.md`（本文件）
- `.ai/tools/scene_composer/tests/test_feature_instance_evidence.py`
- `.ai/tools/evaluation/tasks.phase136.yaml`（v1 任务集冻结副本，用于对照）

本阶段修改：

- `Features/{collect_pickup,heal_pickup,openable_door,trigger_switch,moving_platform,player_movement}/template.yaml`
- `Features/FEATURE_SCHEMA.md`
- `.ai/tools/evaluation/tasks.yaml`（T1 证伪尝试退役为正向尝试）
- `.ai/tools/evaluation/README.md`（任务集版本说明）
- `.ai/tools/scene_composer/external_artifact_resolver.py`（D8：祖先链环判定）
- `.ai/tools/scene_composer/tests/test_external_artifact_evidence.py`（Case 5c）
- `.ai/tools/scene_composer/tests/test_feature_capability_adoption.py`（裸计划审计断言）
- `.ai/context/scene_composer_schema.yaml`（cycle_guard 口径）
- `.ai/context/CONTRACT_INDEX.yaml`、`.ai/context/CURRENT_TASK.md`、`.ai/context/WORK_STATE.md`、
  `.ai/context/SESSION.md`（同步）

黄金基线（改动前后实测，未变）：

```
holdout.json          acf8bfbac8abf774  1792338912178038700
multi_stage_boss.json 5736788cd9efd866  1792246741472536400
single_stage_boss.json d540cfe2226216e0 1792246741774880700
waves.json            878691b1d174cbf0  1792334346613330400
```

最终 Git 状态见本文件末尾的实测记录（每次运行后刷新）。

Git 状态（本阶段结束时实测，`git status --porcelain`）：

- 暂存区：**空**（未 `git add`，未 commit，未 push）。
- 本阶段新增（未跟踪）：`.ai/context/PHASE_1_37_AUDIT.md`、
  `.ai/tools/scene_composer/tests/test_feature_instance_evidence.py`、
  `.ai/tools/evaluation/tasks.phase136.yaml`。
- 本阶段修改：6 个 `Features/*/template.yaml`、`Features/FEATURE_SCHEMA.md`、
  `external_artifact_resolver.py`、`test_external_artifact_evidence.py`、
  `test_feature_capability_adoption.py`、`evaluation/tasks.yaml`、`evaluation/README.md`、
  `scene_composer_schema.yaml`、`CONTRACT_INDEX.yaml`、`CURRENT_TASK.md`、`WORK_STATE.md`、
  `SESSION.md`。
  （`evaluation/` 整个目录仍是未跟踪状态：由 1.36 新增、尚未提交，本阶段只改其中的
  `tasks.yaml` 与 `README.md`，并新增 `tasks.phase136.yaml`。）
- 其余修改（`Orchestration/*`、`Tests/*`、`.ai/tools/validator/*`、`.ai/tools/e2e/*`、
  `.ai/tools/run_tests.py`、`.ai/tools/testsupport/*`、`.workbuddy/memory/*`、
  `PHASE_1_33_AUDIT.md`、`validator/README.md`、`PHASE_1_36_AUDIT.md`）
  属于 Phase 1.26–1.36 的既有未提交增量或用户自有改动，**未触碰**。
- 共享产物目录 `Scenes/`、`Tests/`、`Levels/` 无评估/探针残留（0 项）。
