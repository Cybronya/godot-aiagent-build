# Phase 1.51.1 审计报告 — Feature Registry 动态计数回归修复

日期：2026-10-28
环境：Windows，Godot 4.7 stable headless，CPython 3.12
仓库：`F:\Godot_v4.7-stable\game`，分支 `master`

---

## 0. 结论

两处「Feature 总数写死为 12」的断言已改为**与磁盘上受支持 Feature 集合动态对账**：

| 文件 | 断言 | 结果 |
| --- | --- | --- |
| `.ai/tools/feature_registry/tests/test_composition.py` | `len(nodes) == 12` → 图节点集合 == `Features/*/feature.yaml` 的 id 集合 | PASS |
| `.ai/tools/feature_registry/tests/test_feature_pipeline.py` | `real["checked"] == 12` → `checked == 磁盘上的 Feature 数` | PASS |

在开发迭代中，磁盘 Feature 集从 14 增至 18；当前最终实现（独立枚举目录的版本）在 18 个 Feature 上再次通过两个目标测试及 `feature_registry` 4/4。期间的旧版本也曾在 14、16 个 Feature 快照下通过；最终代码在 18 个 Feature 状态下已重新完整验证。

验证过程中发现的其它失败均未扩大本阶段修复范围：Health 行为测试夹具与上游改动不兼容，最终保留原文件；
`scene_composer` 的新 Feature 声明/实例失败与 E2E 回归失败分别记录于 §7、§9。

---

## 1. 当前仓库状态（本次实测）

### 1.1 Git

```
HEAD（修复开始时）  a851ce2  feat: add hit_flash feature - second snippet-to-Feature asset
HEAD（报告完成时）  f0c0c7c  fix: bring six code-library Features into behavior-evidence protocol (Phase 1.52)
分支                master
staged              0 项
modified            40 项（Phase 1.26–1.51 的既有未提交修改 + 本次 2 个测试文件）
untracked           71 → 91 项（并行工作流在此期间新增的资产/测试）
```

HEAD 在本阶段内前进至 `f0c0c7c`；期间 `e462cfd`（cooldown）、`4aae529`（i_frames）、
`612f321`（projectile + patrol_movement）及 `f0c0c7c`（行为证据能力更新）等并行提交落地，
Feature 数量变化成为动态断言的真实压力测试。

### 1.2 Feature 与索引

| 时刻 | `Features/` 受支持数 | `feature_index.json` | `checked` | 修复后测试 |
| --- | --- | --- | --- | --- |
| 修复前（Phase 1.51 末） | 14 | 14 条 | 14 | **FAIL**（`== 12`） |
| 修复后首次 | 14 | 14 条 | 14 | PASS |
| `a851ce2` 落地 | 16 | 16 条 | 16 | PASS（4/4） |
| `projectile` 半成品期 | 16（`projectile` 无 `feature.yaml`） | 16 条 | 16 | FAIL，**唯一原因** `Feature missing metadata: Features/projectile` |
| `projectile` 补完 `feature.yaml` 后 | 17 | 16 条（未重建） | 17 | 数量断言 PASS，FAIL 仅剩 `projectile not in index` |
| `612f321` + 索引重建（18:34:48） | 18 | 18 条 | 18 | PASS（4/4） |
| 最终检查（`f0c0c7c`） | **18** | **18 条** | **18** | **PASS（4/4）** |

`FEATURE_SCHEMA.md` 不是 Feature 目录，`build_index()` 会跳过；因此「目录数 19」与「受支持 18」
的差是 1，属正常。

### 1.3 Phase 1.51 §6.2.1 的复核

复读 `PHASE_1_51_AUDIT.md` §6.2.1 后，在本次运行时重新确认：

1. 失败点确实只有两处：`test_composition.py:88`（`len(nodes) == 12`）与
   `test_feature_pipeline.py:219`（`real["checked"] == 12`）。
2. 两处都是「Feature 总数」快照，而 `Features/` 已经从 12 增长到 14（之后继续增长）。
3. 当时另有瞬时现象（`e7fb31a` 落地时索引尚无 `screen_shake`，报
   `Feature index outdated: screen_shake not in index`），后由 `a851ce2` 重建索引自然消失。
   **该现象在本阶段又出现了一次**（`projectile not in index`，见 §1.2），同样由上游重建索引后消失
   ——两次都不是数量断言的问题，也就都不是本次修复该碰的地方。

补充审计：在 `feature_registry/tests/` 与 `validator/tests/` 内对 `== 12`、`== 13`、`== 14`、
`12 nodes`、`checked 12` 全量搜索，**没有第三处**同类硬编码（后来 Phase 1.51 发现的
`test_behavior_time_driven.py` 第三处硬编码已在 1.51 内修掉，见 §6.3）。

---

## 2. 两处原始断言的真实意图

| 位置 | 原断言 | 真实意图（由生成链路与上下文判定） |
| --- | --- | --- |
| `test_composition.py:88` | `len(nodes) == 12` | `feature_graph.json` 由 `build_feature_index.build_graph(records)` 生成，节点应等于注册表里**每一个** Feature。意图是「图没有漏掉 Feature」，数字只是当时的事实。 |
| `test_feature_pipeline.py:219` | `real["checked"] == 12` | `check_features()` 的 `checked` = 成功解析 metadata 的 Feature 数。意图是「Validator 真的走遍了真实项目，而不是 0 个或部分」，同样拿当时总数当替身。 |

两者语义**不同**（前者「集合完整性」，后者「遍历完整性」），因此分别修复，不强行合并成一个 helper。

---

## 3. 最小修复的设计依据

### 3.1 共同原则

期望集合直接独立枚举 **`Features/` 下的子目录名**，并单独断言每个目录有 `feature.yaml`；不复用被测图、索引构建器或 Validator 的 Feature 发现逻辑：

- 对 `feature_graph.json`：期望集合从目录名独立取得，因此图节点被删/替换会报告具体 missing/extra。
- 对 `check_features()`：期望数同样来自目录枚举，与被测 `check_feature_metadata.py` 独立；Validator 少检一个时，期望不会随之缩小。索引新鲜度另由 `real["failures"] == []` 和 Validator 独立检查负责。

### 3.2 具体改动

`test_composition.py`：

```python
features_root = os.path.join(PROJECT_ROOT, "Features")
feature_dirs = {name for name in os.listdir(features_root)
                if os.path.isdir(os.path.join(features_root, name))}
directories_without_metadata = sorted(
    name for name in feature_dirs
    if not os.path.isfile(os.path.join(features_root, name, "feature.yaml")))
)
ok("graph: every Feature directory has metadata", not directories_without_metadata, ...)
ok("graph: every Feature directory is a node (%d)" % len(feature_dirs),
   nodes == feature_dirs,
   "missing=%s extra=%s" % (sorted(feature_dirs - nodes), sorted(nodes - feature_dirs)))
ok("graph: core features present",
   {"health", "contact_damage", "stun", "player_movement", "trigger_switch"} <= nodes,
   str(sorted(nodes)))
```

`test_feature_pipeline.py`：

```python
features_root = os.path.join(PROJECT_ROOT, "Features")
feature_dirs = {name for name in os.listdir(features_root)
                if os.path.isdir(os.path.join(features_root, name))}
ok("validator(real project): every Feature directory has metadata", ...)
ok("validator(real project): checked every Feature directory (%d)" % len(feature_dirs),
   real["checked"] == len(feature_dirs),
   "checked=%d expected=%d (%s)" % (real["checked"], len(feature_dirs), sorted(feature_dirs)))
ok("validator(real project): core features were checked",
   {"health", "contact_damage", "stun"} <= feature_dirs, str(sorted(feature_dirs)))
```

### 3.3 比原断言更强，而不是更弱

| 维度 | 原断言 | 新断言 |
| --- | --- | --- |
| 图节点 | 只比数量（多一个、少一个且数量不变时漏检） | **集合完全相等** + 指名 `missing` / `extra` |
| 遍历完整性 | 只比数量 | 数量对齐磁盘真源；另由 `real["failures"] == []` 逐条比对索引条目与版本 |
| 真空风险 | `Features/` 为空时 `12 != 0` 仍失败（安全） | 独立检查每个 Feature 目录有 `feature.yaml`，并保留核心 Feature 存在断言 |
| 增长成本 | 每加一个 Feature 就要改测试 | 不需要改测试 |

没有删除断言、没有跳过测试、没有放宽阈值；被替换的只是「拿快照数字当不变量」。

---

## 4. 修复前后的测试结果

| 阶段 | 命令 | 结果 | 退出码 | 用时 |
| --- | --- | --- | --- | --- |
| 修复前 | `python .ai/tools/feature_registry/tests/test_composition.py` | `FAIL: graph: 12 nodes \| [14 个 id]` | 1 | — |
| 修复前 | `python .ai/tools/feature_registry/tests/test_feature_pipeline.py` | `FAIL: validator(real project): checked 12 features \| 14` | 1 | — |
| 修复前 | `python .ai/tools/run_tests.py feature_registry` | `completed=4/4 passed=2 failed=2` | **1** | — |
| 修复后 @14 | 同上 | `completed=4/4 passed=4 failed=0` | **0** | 17 s |
| 修复后 @16（`a851ce2`） | 同上 | `completed=4/4 passed=4 failed=0` | **0** | 16 s |
| 修复后 @18（独立目录枚举最终版，`f0c0c7c`） | `python .ai/tools/run_tests.py feature_registry` | `completed=4/4 passed=4 failed=0 incomplete=0 unavailable=0 not_executed=0` | **0** | 约 21 s |
| 修复后 @18（最终独立目录枚举版） | `test_composition.py` 直跑 | `PASS: all composition checks passed`（含图节点集合对账） | **0** | <1 s |
| 修复后 @18（最终独立目录枚举版） | `test_feature_pipeline.py` 直跑 | `checked every Feature directory (18)` / all feature pipeline checks passed | **0** | 3 s |
| 修复后 @18（最终独立目录枚举版） | `run_tests.py feature_registry` | 4/4 PASS；incomplete=0, unavailable=0, not_executed=0 | **0** | 约 21 s |

（「修复前 4/4 passed=2 failed=2」是实测：第一次复跑只有 `test_feature_pipeline` 失败，随后
`a851ce2` 让图也变成 14 节点，`test_composition` 才开始失败。两次失败原因都是同一个 12，一起修。）

`projectile` 半成品期（§1.2 第 4 行）真实项目 Validator 报 `Features/projectile` 缺 metadata；最终实现中的独立目录完整性断言也会对任一缺失 `feature.yaml` 的目录报错，避免把它静默排除在期望集合之外。当前完整索引复核通过。

---

## 5. 区分能力验证（新断言仍能拒绝真实回归）

脚本：`.ai/tmp/p151_1_discrimination.py`。每个注入都在**真实文件**上做，`try/finally` 写回原始
字节，并断言哈希/工作区恢复（逐字节恢复）。期望规模从 `Features` 子目录动态枚举，
不调用生成器，也不写死 Feature 总数。

| # | 注入 | 期望失败原因 | 实测（@18，最终独立枚举断言） | 恢复 |
| --- | --- | --- | --- | --- |
| D1 | `feature_graph.json` 删掉 `hit_flash` 节点 | `graph: every Feature directory is a node` + `missing=['hit_flash']` | ✅ exit 1，两条原因均报告 | ✅ 逐字节 |
| D2 | `feature_index.json` 删掉 `screen_shake` 条目 | `Feature index outdated: screen_shake not in index` | ✅ exit 1 | ✅ 逐字节 |
| D3 | `check_feature_metadata.py` 静默跳过 `hit_flash` | `checked=17 expected=18` | ✅ exit 1，`checked every Feature directory (18)` + `checked=17 expected=18` | ✅ 逐字节 |

```
supported features on disk: 18 (injections below expect 17)
PASS: all discrimination checks passed
```

D3 是关键证据：Validator 少检一个 Feature 时，独立目录枚举的期望仍为 18，测试报告 `checked=17 expected=18`。

---

## 6. Phase 1.51 核心证据是否稳定

### 6.1 契约与协议本身

| 检查 | 结果 | 退出码 | 用时 |
| --- | --- | --- | --- |
| `python .ai/tools/scene_composer/feature_behavior_evidence.py --feature health --require-behavior --replay 2` | `pass=5 mismatch=0 insufficient=0 invalid=0 not_declared=0` | **0** | 21 s |
| Phase 1.52 之前协议快照 | `actions 8 / observations 12 / signals 7 / properties 1` | **0** | 1 s |
| Phase 1.52 之前 manifest 漂移 | `check_manifest(load_protocol())` → `[]` | **0** | 1 s |
| 最终 HEAD 协议能力计数 | `actions 10 / observations 13 / signals 13 / properties 1`（来自最终 Health 测试诊断） | — | — |
| 最终 HEAD manifest 专项一致性 | 本轮未单独执行 | 未验证 | — |
| 索引一致性 `check_feature_metadata.py`（@18） | `PASS: validator(real project): no failures` | **0** | 2 s |

本阶段**没有**改协议、manifest、任何 Feature 目录或索引文件，Phase 1.51 的 `health → VERIFIED`
结论不受影响。

### 6.2 Health 行为测试的上游漂移（本阶段未修改）

在 `4aae529` 的 `i_frames` 扩展后，`health.gd` 的真实守卫是
`if _is_dead or _invulnerable or amount <= 0:`，而旧 Health 测试中的 `TAKE_GUARD` 仍查找
`if _is_dead or amount <= 0:`。因此 Health 专项第一次运行在缺陷注入阶段因锚点失配退出 1。

我曾临时适配测试锚点，且在该代码快照上得到一次 82 s 全 PASS；但更晚的上游 `f0c0c7c`
将共享行为协议扩展至 10 actions / 13 observations / 13 signals / 1 property。随后复跑旧 Health
测试在旧的协议数量断言与旧 `TAKE_GUARD` 处失败（exit 1，46 s）。为避免将 Phase 1.52 的协议
维护纳入本阶段，已撤回临时适配；最终 `test_health_behavior.py` 与本阶段开始时保持一致，未留下 diff。

独立的真实运行时 Health CLI 在最终快照通过：
`feature_behavior_evidence.py --feature health --require-behavior --replay 2` →
`pass=5 mismatch=0 insufficient=0 invalid=0 not_declared=0`，exit 0 / 20 s。
这只证明现有 5 条契约可重放，不替代完整的 9 类缺陷注入专项测试；后者需由 Phase 1.52 同步测试夹具后复验。

### 6.3 Phase 1.51 期间已修的第三处硬编码（回顾）

`test_behavior_time_driven.py` Case 7 曾写死「legacy 6 条行为」，Phase 1.51 内已改为当前真实
声明数。本轮回归 `scene_composer` 的失败文件列表里**不再包含它**，说明那次修复仍有效。

---

## 7. 完整分段回归（串行）

单命令全量超出工具时限（`scene_composer` ≈ 930 s、`e2e` ≈ 530 s），按项目既有方式分段串行。
两轮完整回归分别在 `a851ce2`（16 Feature）与 `612f321`（18 Feature）上进行；脚本
`.ai/tmp/p151_1_run.sh` / `.ai/tmp/p151_1b_run.sh`，结果
`.ai/tmp/RESULTS_p151_1.txt` / `.ai/tmp/RESULTS_p151_1b.txt`。

### 7.1 第一轮 @ `a851ce2`（09:01:18 → 09:30:44）

| 段 | 命令 | 退出码 | 用时 | 结果 |
| --- | --- | --- | --- | --- |
| godot_only | `run_tests.py --godot-only` | **0** | 151 s | 40/40 PASS，`incomplete=0 unavailable=0 not_executed=0` |
| scene_composer | `run_tests.py scene_composer` | **1** | 927 s | 3 个文件失败（上游新 Feature 未声明 behavior/capabilities，见 §9.1） |
| asset_registry | `run_tests.py asset_registry` | **0** | 25 s | 11/11 |
| feature_registry | `run_tests.py feature_registry` | **0** | 16 s | **4/4**（本次修复） |
| gameplay_planner | `run_tests.py gameplay_planner` | **0** | 15 s | 2/2 |
| runtime | `run_tests.py runtime` | **0** | 55 s | 5/5 |
| evaluation | `run_tests.py evaluation` | **0** | 13 s | 2/2 |
| validator | `run_tests.py validator` | **0** | 35 s | 10/10 |
| e2e | `run_tests.py e2e` | **0** | 527 s | 2/2 |

`scene_composer` 段失败的三个文件：
`test_feature_behavior_evidence.py`、`test_feature_capability_adoption.py`、
`test_feature_capability_pipeline.py`。

### 7.2 第二轮（18 Feature；分段测试基线 HEAD `612f321`）

分段执行开始于 `612f321`（18:35:51）；测试期间并行上游继续写入，随后 HEAD 推进到
`f0c0c7c`。以下失败结果针对当时启动的测试快照，不能外推为 `f0c0c7c` 的全量结果；中途索引在
18:34:48 已重建为 18 项。`run_tests.py` 各段共计 8 个 Python 分组 + Godot：

| 段 | 命令 | 退出码 | 用时 | 结果 / 分类 |
| --- | --- | --- | --- | --- |
| godot_only | `python .ai/tools/run_tests.py --godot-only` | **0** | 170 s | 45/45 PASS，failed=0 incomplete=0 unavailable=0 not_executed=0 |
| scene_composer | `python .ai/tools/run_tests.py scene_composer` | **1** | 1063 s | 31 个发现，27 PASS / 4 FAIL；行为/能力声明及实例审计未随新增 Feature 更新，见 §9.1 |
| asset_registry | `python .ai/tools/run_tests.py asset_registry` | **0** | 29 s | 11/11 PASS |
| feature_registry | `python .ai/tools/run_tests.py feature_registry` | **0** | 20 s | **4/4 PASS**，四项均无 skip |
| gameplay_planner | `python .ai/tools/run_tests.py gameplay_planner` | **0** | 16 s | 2/2 PASS |
| runtime | `python .ai/tools/run_tests.py runtime` | **0** | 59 s | 5/5 PASS |
| evaluation | `python .ai/tools/run_tests.py evaluation` | **0** | 15 s | 2/2 PASS |
| validator | `python .ai/tools/run_tests.py validator` | **0** | 41 s | 10/10 PASS |
| e2e（默认编码） | `python .ai/tools/run_tests.py e2e` | **1** | 341 s | **INCOMPLETE**：控制台 GBK `UnicodeEncodeError` 在输出阶段中止，不能计为通过 |
| e2e（`PYTHONIOENCODING=utf-8`） | 同上 | **1** | 约 490 s | 3 个发现，2 PASS / 1 FAIL；`test_end_to_end_generation.py` 的 `_make_sandbox()` 在 `shutil.copytree` 时发现 `.ai/tmp/eval136-*` 临时目录消失。由于前一条 600 s 同步调用超时后是否仍有子进程未能确认，可能与本次重跑重叠；因此归类为**验证调度/隔离目录竞争，责任来源未确定**，不归咎于上游，也未改 E2E 范围代码 |

在 `612f321` 快照的 4 个 `scene_composer` 失败文件：`test_feature_behavior_evidence.py`、
`test_feature_capability_adoption.py`、`test_feature_capability_pipeline.py`、
`test_feature_instance_evidence.py`。前三者日志显示新 Feature 缺少 behavior/capability 声明；
第 4 个也失败，但当前证据不足以把原因归到特定 Feature。它们均非 Feature Registry 数量断言；
上游 `f0c0c7c` 后没有重跑整段 scene_composer，故最终 HEAD 的该段结果未知。

### 7.3 专项、索引及 Health 复核（最终 HEAD `f0c0c7c`）

| 命令 | 结果 | 退出码 / 用时 |
| --- | --- | --- |
| `python .ai/tools/feature_registry/tests/test_composition.py` | PASS；输出 `every supported Feature is a node (18)` | 0 / <1 s |
| `python .ai/tools/feature_registry/tests/test_feature_pipeline.py` | PASS；`checked every supported Feature (18)` | 0 / 3 s |
| `python .ai/tools/run_tests.py feature_registry` | 4/4 PASS，incomplete=0 unavailable=0 not_executed=0 | 0 / 21 s |
| `python .ai/tools/validator/check_feature_metadata.py` | checked 18，0 error / 0 warning | 0 / 3 s |
| 磁盘 `feature.yaml` ID 集合 vs `feature_index.json` | 18 == 18，ids_equal=True，无 missing/extra | 0 / <1 s |
| `python .ai/tools/scene_composer/feature_behavior_evidence.py --feature health --require-behavior --replay 2` | pass=5 mismatch=0 insufficient=0 invalid=0 not_declared=0 | 0 / 20 s |
| `python .ai/tools/scene_composer/tests/test_health_behavior.py`（最终未适配状态） | 注入在旧 `TAKE_GUARD` 锚点处中止；另一次临时适配试跑因旧协议数量断言失败 | 1 / 46 s（未完成全部 Health 注入契约） |

Health 测试锚点问题来自 `i_frames` 的 `_invulnerable` 守卫扩展。临时适配曾在较早协议快照得到一次全 PASS；
随后协议增至 10/13/13/1 后，同一旧测试在「协议未变化」断言处失败。最终已撤回本阶段对该非目标文件的临时修改
（`git diff` 为空），并在未适配状态复跑确认旧锚点失败。Health CLI 正常重放仍 5/5 PASS；完整
`test_health_behavior.py` 不能宣称通过，需在协议更新后的工作流里同步测试后复验。

### 7.4 分段并集完整性证明（去重，脚本化）

用 `run_tests.py` 自己的 `discover_python_tests()` / `discover_godot_tests()` / `filter_tests()`
复算，而不是手抄文件清单：

```
all python tests: 61
scene_composer      31
asset_registry      11
feature_registry     4
gameplay_planner     2
runtime              5
evaluation           2
validator           10
e2e                  2
union: 61   sum-memberships: 67
overlapping files: 6
uncovered python tests: []
godot tests at second-round discovery: 45; final discovery after upstream change: 44
```

- 8 段累计计入 67 次，去重后并集 **61 = 全部 Python 测试数**，**无遗漏**。
- 6 个文件被两段同时选中（例如 `test_runtime_instance_evidence.py` 同时匹配
  `scene_composer` 与 `runtime`），因此**不能**把 67 当作覆盖数重复计算。
- Godot 测试由 `--godot-only` 一段覆盖；第二轮运行时发现 45 个（45/45 PASS），最终 HEAD 上发现 44 个。Python 测试分组并集仍覆盖当前全部 61 项。

**限制（如实记录）**：本环境无法用**单命令**跑完整全量，因此「全量单命令通过」这句话不成立；
上面证明的是「9 段串行执行的并集 == 全量发现集合」。

---

## 8. 工作区与 Git 状态

本阶段最终保留 **3 个有意修改的文件**：两个 Feature Registry 测试和新增审计报告。Phase 1.51 的 Health 行为测试本来就是既有未跟踪文件；本阶段短暂适配已撤回，文件不计入本次修改。

| 文件 | 状态 | 变更 | sha256 |
| --- | --- | --- | --- |
| `.ai/tools/feature_registry/tests/test_composition.py` | `M` | 动态目录集合对账 | `e50b7c9b719c0addf321deff50a920691ced4603654d0e8f5231fa73169ea463` |
| `.ai/tools/feature_registry/tests/test_feature_pipeline.py` | `M` | 动态目录数与 Validator checked 对账 | `a4596454868cc5f5c310c1d6f652b29e29740924ec33ffd6f291514274985129` |
| `.ai/context/PHASE_1_51_1_AUDIT.md` | `??` | 本阶段审计报告 | （最终保存时计算） |

- **未**修改 `Features/`、`feature_index.json`、`feature_graph.json`、`check_feature_metadata.py`、
  `build_feature_index.py`、`behavior_protocol.yaml`、`behavior_manifest.json` 等并行工作流的成果。
- 最终状态（采样时）：HEAD `f0c0c7c`，`master`；staged=0，modified=40，untracked=65（均含既有/并行工作流内容；审计报告与 Phase 1.51 的 Health 测试均为未跟踪）。曾观察到一个参数显示异常的 Python 测试进程，归属无法确认；未终止，亦不声称所有外部进程都已结束。
  本次实际修改为两个已跟踪测试文件及新增审计报告；其它状态未清理、未覆盖。
- D1–D3 的临时注入均逐字节恢复：注入后 `git status` 对这三个文件无输出，哈希见 §5 与上文。
- **未**执行 `git reset` / `git checkout` / `git clean` / `git add` / `git commit` / `git push`。
- Phase 1.26–1.51 的既有未提交修改完整保留；当前 40 个 modified 文件中，本次增加的已跟踪修改为 2 个目标测试文件。

---

## 9. 未解决的问题与限制

### 9.1 `scene_composer` 段在 `612f321` 快照仍红（最终 HEAD 未重验）

失败文本（仅对 `612f321` 启动的第二轮回归有证据）：

```
FAIL: case1: every Feature with a template now declares behavior
  templated 含 cooldown / hit_flash / i_frames / patrol_movement / screen_shake（+projectile），declared 不含
FAIL: audit: cooldown|hit_flash|i_frames|patrol_movement|projectile|screen_shake declaration matches ...
FAIL: case1: every real project feature declares at least one capability
FAIL: audit: projectile gate PASS and records the declaration  ('Unsupported component: projectile')
```

判定：在 `612f321` 这组运行快照中，这些是新 Feature 的声明缺口，不是数量硬编码，也不是本次修改引起。
按本阶段约束未改生产 Feature 或其它并行成果。随后 `f0c0c7c` 是上游行为证据更新提交，但本阶段没有在该 HEAD
重跑 `scene_composer`，所以不能断言这些失败仍然存在或已修复。

### 9.2 索引新鲜度的瞬时失败（上游节奏，已自愈）

`projectile` 落地与 `feature_index.json` 重建之间有约 8 分钟窗口，期间 Validator 报
`Feature index outdated: projectile not in index`。索引由提交方重建后自然消失，与 Phase 1.51
记录的 `screen_shake` 现象同类。本次**没有**为了变绿去手改索引文件。

### 9.3 Health 与 E2E 的相邻验证限制

- Health CLI 的 5 个正式行为契约当前重放一致；完整 `test_health_behavior.py` 因旧注入锚点和旧协议计数断言失配而未通过。本阶段没有保留对该测试的修改。
- E2E 默认编码运行因 GBK 输出异常而被入口中止（对应失败文件未获完成状态，视为 `INCOMPLETE`）；UTF-8 重跑执行到 3/3，其中 `test_end_to_end_generation.py` 在项目复制期间遭遇临时目录消失。由于超时调用之后的子进程状态无法确认，竞争来源未定，exit 1；不把它计作通过。

### 9.4 保留的限制

1. 两个测试仍依赖真实项目路径（`PROJECT_ROOT`）。这是既有设计：`Test 3c` 本来就是「真实项目
   检查」；本次只把「真实项目的规模」从快照改为实测。
2. `feature_graph.json` 没有 `generated_at`，`test_composition.py` 只能靠「节点集合相等」间接
   判断图是否过期；若某次只改关系（edges）不改节点，现有两条边断言未必覆盖。属新的覆盖缺口，
   不在本阶段范围。
3. 单命令全量受工具时限限制，分段并集覆盖证明见 §7.4；E2E 本轮没有得到通过结果。
4. 并行工作流提交节奏很快（本阶段 HEAD 从 `a851ce2` 推进到 `f0c0c7c`，Feature 14 → 18）。
   本次动态断言在增长期间稳定通过；`scene_composer` 的红色需上游补齐声明/实例证据后才能收敛。
5. E2E 临时目录复制冲突需要在不并发运行其它隔离工作区任务时单独重验。
6. Health 行为测试中的旧协议数量与守卫注入锚点需在协议更新后的工作流同步；本阶段确认 Health CLI 为 5/5 PASS，完整 Health 注入测试失败原因见 §6.2 / §7.3。
