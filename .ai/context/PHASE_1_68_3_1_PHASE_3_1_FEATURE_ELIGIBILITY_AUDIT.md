# Phase 1.68.3.1 — Phase 3.1：Feature Eligibility & Contract Audit

- 阶段：Phase 1.68.3.1 / Phase 3.1
- 日期：2026-11-10
- 基线 HEAD：`04f50636c7d3afb37a2a58454cb4ae16f1a38593`（master）
- 审计性质：**只读架构审计与决策**。本阶段未修改源码、测试、Feature 数据、Registry、Evidence/Attestation，未执行测试，未执行任何 Git 写操作。
- 审计对象：8 个缺少 `template.yaml` 且 `capabilities.required` 为 `[]` 的 Feature 目录。
- 结论先行：这 8 个目录是 **Registry 已索引、但未进入 Scene Composer 正式支持集的未完成/上游脚手架**。推荐采用**方案 C（两级资格：Registry 成员资格 ≠ Scene Composer 资格）**；不建议为它们批量补模板和能力声明。详见 §4–§6。

---

## 1. 架构权威来源

### 1.1 权威文件与职责

| 文件/模块 | 在本问题中的职责 | 关键事实 |
|---|---|---|
| `Features/FEATURE_SCHEMA.md` | Feature 元数据、目录、模板、能力声明、行为声明的规范 | `feature.yaml` 是 Feature 交付物；`template.yaml` **可选**；`capabilities.required` **可选，默认 `[]`**；`behavior:` 可选 |
| `Features/<id>/feature.yaml` | Feature 的 Source of Truth | 当前 31 个目录都有合法 `feature.yaml` |
| `.ai/tools/feature_registry/README.md` | Registry 的生成、查询、校验边界 | `feature.yaml → feature_index.json → discovery → validation`；索引是缓存 |
| `.ai/tools/feature_registry/build_feature_index.py` | 索引生成器 | 扫描 `Features/*/feature.yaml`，收录所有含合法必填字段的目录；**不要求 template、capability 或 behavior** |
| `.ai/tools/feature_registry/feature_discovery.py` | Feature Discovery | 只查询 `feature_index.json`；**不扫描目录、不判断 Scene Composer 资格** |
| `.ai/tools/feature_registry/README.md` Validator 节 | Feature Metadata / Index 校验 | 只检查 metadata 存在、id 一致、必填字段、测试路径、索引同步；**不检查 template/capability** |
| `.ai/tools/scene_composer/template_loader.py` | Scene Composer 的模板入口 | `load_template()` 找不到 `template.yaml` 返回 `{}`；`template_scene_path()` 在无模板时回退 `feature.yaml.composition.entry_scene`，再回退 `<Pascal>.tscn` 约定 |
| `.ai/tools/scene_composer/feature_behavior_evidence.py` | 行为支持集的实际读取方式 | `declared_features()` 只收集 `template.yaml` 中声明了非空 `behavior` 的 Feature；无模板即不进入行为支持集 |
| `.ai/context/feature_index.json` | Registry 的生成缓存 | 当前 31 条，生成时间 `2026-10-31T13:29:04Z`；8 个目标目录均在索引中 |
| `.ai/context/feature_graph.json` | Feature 关系图缓存 | 当前 31 个节点、80 条边；8 个目标目录大多为孤立节点 |
| `.ai/context/feature_discovery_schema.yaml` | Discovery 输出契约 | 只描述 `features`、`feature_capabilities` 等输出；**没有 `status` / `eligible` / `enabled` 字段** |

### 1.2 逐条回答 Phase 3.1.1 的 8 个问题

#### Q1. 正式 Feature 的权威定义在哪里？

分层回答：

1. **Feature Metadata 的权威来源**是 `Features/<id>/feature.yaml`，格式由 `Features/FEATURE_SCHEMA.md` 定义。`feature_index.json` 只是生成缓存，不是 Source of Truth。
2. **Scene Composer 接入资格**的权威来源是 `template.yaml`。`FEATURE_SCHEMA.md` §7 明确：无 `template.yaml` 的 Feature 视为**未接入 Scene Composer**。
3. **行为/运行时支持集**的权威来源是 `template.yaml` 中的 `behavior:`、`instance:`、`runtime:` 等声明；`feature_behavior_evidence.declared_features()` 只读取有非空 `behavior` 模板的 Feature。
4. 当前**不存在**一个统一的 `enabled` / `status` / `eligible` 字段来同时表达以上三层。Registry 收录不等于 Scene Composer 接入，也不等于行为支持。

因此，“Feature 目录存在”只能证明它可能是 Registry 成员；不能证明它是正式启用的 Scene Composer Feature。

#### Q2. 是否要求每个 Feature 目录必须有 `template.yaml`？

**不要求。**

`Features/FEATURE_SCHEMA.md` §7 原文：

> 每个 Feature 目录**可选**提供 `template.yaml`，描述「如何被实例化进实体场景」……
>
> 无 `template.yaml` 的 Feature 视为**未接入 Scene Composer**。

所以“缺模板”本身不是 metadata 错误，也不构成“不是 Feature”。它只说明该 Feature 没有进入 Scene Composer 的实例化契约。

#### Q3. 是否要求每个 Feature 必须提供非空 Capability 声明？

**不要求。**

`Features/FEATURE_SCHEMA.md` §4 原文：

> 字段名固定为 `capabilities.required`，默认 `[]`；未声明的存量 Feature 继续合法。
>
> 没有声明就是没有需求。

但同一节又有 Phase 1.8.12 的“Existing Feature capability adoption status”和“由 `test_feature_capability_adoption.py` 审计强制”的文字。这形成了两个不同层次：

- **读取器/组合器契约**：缺声明 = `[]`，合法；不得推断。
- **迁移完成度审计**：对已经接入 Scene Composer 的 Feature，要求声明与自身场景/契约证据一致，并推动“adoption happened”。

后者是**迁移审计**，不是“所有目录必须有非空能力”的永久架构契约。对没有场景、没有模板的 code-only Feature，`[]` 是合法的“没有 Scene 能力需求”。

#### Q4. Feature Registry 是否有明确的启用状态？

**没有。**

- `build_feature_index.py` 只按目录扫描并检查 `REQUIRED_FIELDS`；没有 `status` / `enabled` / `eligible` 过滤。
- `feature_index.json` 的每条记录只有 `id/version/category/provides/requires/interfaces/signals/validation/relations`。
- `feature_discovery.py` 与 `feature_discovery_schema.yaml` 也没有生命周期或资格字段。
- Validator 的 Feature Metadata 检查项不包含“启用状态”。

因此当前 Registry 的状态只能描述为：

> **INDEXED（已索引）**，不是 **ACTIVE/ENABLED（已启用）**。

#### Q5. 是否存在实验性、归档或未完成 Feature 的正式表达方式？

**没有正式的机器可读字段。**

当前可用的“事实表达”只有：

- `README.md` 的自由文本状态（本批 8 个均写“状态：脚手架……尚未完成抽象”）；
- Git 跟踪状态（本批 8 个均为未跟踪 `??`）；
- 是否存在 `template.yaml` / 非空 `capabilities` / `behavior`；
- 历史报告中的文字标签，例如 `UPSTREAM_INCOMPLETE`、“未纳入正式支持集”。

历史证据已经明确使用这些标签：

- `.ai/context/PHASE_1_59_AUDIT.md` 第 29–34 行：这 8 个目录“为未跟踪目录。本阶段不把它们加入支持集”，并记录正式支持集动态读取为 **23 Feature / 60 Behavior**。
- `.ai/context/PHASE_1_56_COMPLETION_REPORT.md` 第 283–310 行：三个失败断言“与这 8 个目录逐一对应，没有第 9 个”，归属 `UPSTREAM（并行工作）`。
- `.ai/context/WORK_STATE.md` 第 106–107 行：`run_tests.py` 的 3 个 FAIL 是“`scene_composer` 对 8 个未跟踪、缺 `template.yaml` 的 Feature 脚手架的模板完备性断言”。

结论：项目**事实上**有两级 Feature 集合，但没有**形式上**的生命周期字段。这个缺口是本次审计要解决的核心架构问题之一。

#### Q6. Scene Composer 是否应该扫描所有磁盘目录？

**不应把“扫描所有目录”当作资格判断。**

正确的层次是：

- **发现/索引层**可以扫描所有目录，生成 Registry；
- **Scene Composer 资格层**必须以 `template.yaml`（及入口场景存在）为准；无模板的 Feature 不参与实例化；
- **测试层**如果要验证模板完备性，应只遍历“已声明模板”的集合，或明确把它作为“支持集完整性审计”，而不是把每个磁盘目录都当成必须可组合的 Feature。

当前 `test_scene_composer.py` 第 174–182 行确实遍历 `FEATURES_DIR` 的**所有目录**，并对每个 `fid` 断言 `template_loader.load_template(fid)` 非空。这是“所有目录都必须有模板”的**隐含完整性假设**，不是 `FEATURE_SCHEMA.md` 的规则。该测试上方注释还写着“12 个 Feature 均有 template.yaml”，说明它形成于更小的 Feature 集，未随 31 个目录的现状更新。

#### Q7. Capability Pipeline 是否应该扫描所有磁盘目录？

**核心 Pipeline 不应以“所有目录”为输入。**

`feature_capabilities.py` 是“按 Feature 读取声明”的模块：缺声明返回 `{"required": []}`；`scene_composer` 只对 Blueprint 中显式选择的 Feature 读取能力。它不负责“发现所有 Feature”，也不应强制所有目录都有非空声明。

当前 `test_feature_capability_pipeline.py` 第 143–153 行把 `os.listdir(template_loader.FEATURES_DIR)` 当作 `real_features`，并要求每个 Feature 的能力声明非空。这是 **Phase 1.8.12 的数据迁移断言**（变量名 `real_features`、断言名 `adopted`），不是 Capability Pipeline 的运行时契约。它把“迁移已完成”误写成了“所有目录永久必须已迁移”。

#### Q8. 当前三个测试的遍历方式是否符合项目架构约定？

**不符合。**

三个测试都直接从磁盘枚举 `Features/` 目录，没有 Registry 过滤，也没有 `template.yaml` 资格过滤：

- `test_scene_composer.py`：要求所有目录有模板；
- `test_feature_capability_pipeline.py`：要求所有目录有非空能力声明；
- `test_feature_capability_adoption.py`：要求所有目录有能力声明，并进一步用“自身场景/契约证据”审计。

而架构约定是：

- `template.yaml` 可选；
- `capabilities.required` 默认 `[]`；
- 无模板 = 未接入 Scene Composer；
- 行为/实例/运行时证据只在声明后参与。

因此三个测试的遍历范围**大于正式 Scene Composer 支持集**，其断言反映的是“目录结构完整性/一次性迁移完成”的隐含假设，而不是当前 Schema 的正式契约。详细代码见 §3。

---

## 2. 8 个目录逐项审计

### 2.1 共同事实（全部 8 个）

以下事实来自只读检查；**没有执行任何 Feature 自测，也没有执行三个 Scene Composer 测试**。

| 检查项 | 结果 |
|---|---|
| `feature.yaml` | 存在且可解析；`id == 目录名`；有 `version/category/summary/provides/requires/interfaces/ownership/relations/composition/validation` |
| 源码 | 存在同名 `.gd`；有 `class_name`；文件头写明“抽象自某开源项目（MIT），简化……”；不是空占位文件 |
| 场景资源 | **无任何 `.tscn`**；`composition.entry_scene` 为 `''` |
| `template.yaml` | **不存在** |
| `capabilities.required` | **`[]`** |
| 自测文件 | 存在 `test_<id>.gd`；包含真实断言和 PASS/FAIL 输出逻辑，不是单纯 `pass` 占位 |
| README | 均写“状态：**脚手架**（由 `github_collector.py promote` 生成，尚未完成抽象）” |
| Registry | 均被 `feature_index.json` 收录；索引当前共 31 条 |
| Git | 均为未跟踪目录（`git status --porcelain` 显示 `??`；`git ls-files Features/<id>` 为 0）；`git log --follow` 无历史 |
| Skill / Workflow 引用 | 未发现对这些 Feature id 的正式引用；未发现 `.ai/skills` 中的消费点 |
| 真实使用场景 | 未发现项目内 `.tscn`、业务脚本或其他 Feature 对这些类的调用；引用仅限自身测试/元数据，以及 `audio_player_pool` / `pickable_audio` / `sfx_pool` 的 Registry relations（关系元数据不等于运行时集成） |
| 明确完成状态 | README 明确写“脚手架/尚未完成抽象”；没有 Finalization 记录、没有模板、没有场景、没有能力声明 |

补充事实：

- 历史报告记录其创建时间为 **2026-10-31 20:54**，并明确称其为“未跟踪”“上游未完成”。（`.ai/context/PHASE_1_56_COMPLETION_REPORT.md` 第 288–290 行）
- `feature_graph.json` 中，除 `audio_player_pool` 与 `pickable_audio` 之间存在关系边外，其余 6 个在图中没有入边/出边；这只能说明“没有已登记的 Feature 关系”，不能单独证明生命周期。
- README 说“当前是 FAIL 占位”，但实际测试文件包含真实断言。这是**文档与代码不一致**，不能据此断言测试通过，也不能据此把 Feature 判为 ACTIVE；需要在未解决问题中登记。

### 2.2 逐目录明细

| Feature | Category | 主要 `provides` | 源码/测试（行数） | 场景 | Template | Capability | 外部引用 | Git | README 状态 | 建议分类 |
|---|---|---|---|---|---:|---:|---|---|---|---|
| `anima_behaviour` | `animation` | `animation_trigger`, `motion_entry_exit`, `auto_animation_playback` | 48 / 53 | 无 `.tscn` | 缺 | `[]` | 仅自身目录/测试 | 未跟踪 | 脚手架，未完成抽象 | **INCOMPLETE** |
| `attribute_editor` | `combat` | `gameplay_attributes`, `stat_management`, `attribute_validation` | 74 / 71 | 无 `.tscn` | 缺 | `[]` | 仅自身目录/测试 | 未跟踪 | 脚手架，未完成抽象 | **INCOMPLETE** |
| `audio_player_pool` | `audio` | `audio_pool`, `sfx_playback`, `volume_fade` | 128 / 86 | 无 `.tscn` | 缺 | `[]` | `relations` 指向 `sfx_pool`；`pickable_audio` 声明 `works_with: audio_player_pool`；均无场景调用 | 未跟踪 | 脚手架，未完成抽象 | **INCOMPLETE** |
| `blackboard` | `ai` | `behavior_tree_blackboard`, `shared_data_store` | 60 / 74 | 无 `.tscn` | 缺 | `[]` | 仅 `cooldown` README 的泛称“blackboard”；无代码引用 | 未跟踪 | 脚手架，未完成抽象 | **INCOMPLETE** |
| `clean_copy` | `general` | `project_settings_registry`, `path_list_management`, `string_replacement_map` | 54 / 63 | 无 `.tscn` | 缺 | `[]` | 仅自身目录/测试 | 未跟踪 | 脚手架，未完成抽象 | **INCOMPLETE** |
| `flying_letter` | `animation` | `floating_text`, `damage_number`, `experience_popup` | 65 / 67 | 无 `.tscn` | 缺 | `[]` | 仅自身目录/测试 | 未跟踪 | 脚手架，未完成抽象 | **INCOMPLETE** |
| `pedestal_interaction` | `ui` | `puzzle_interaction`, `item_placement`, `puzzle_group_coordinator` | 80 / 88 | 无 `.tscn` | 缺 | `[]` | 仅自身目录/测试 | 未跟踪 | 脚手架，未完成抽象 | **INCOMPLETE** |
| `pickable_audio` | `audio` | `3d_spatial_audio`, `interaction_sound`, `velocity_volume_attenuation` | 56 / 70 | 无 `.tscn` | 缺 | `[]` | `relations.works_with: audio_player_pool`；无场景调用 | 未跟踪 | 脚手架，未完成抽象 | **INCOMPLETE** |

### 2.3 为什么统一判为 `INCOMPLETE`，而不是 `ACTIVE` / `EXPERIMENTAL` / `ARCHIVED`

- **不是 `ACTIVE`**：
  - 没有 `template.yaml`，按 Schema 视为未接入 Scene Composer；
  - 没有 `.tscn`，没有场景证据，没有项目内消费点；
  - 没有 Finalization 记录；
  - README 明确写“脚手架……尚未完成抽象”；
  - Git 未跟踪，说明它们不属于已提交的正式 Feature 集。
- **不是 `EXPERIMENTAL`（当前证据不足）**：
  - 没有实验记录表明它们被有意保留为实验特性；
  - 历史报告将其归为“上游未完成/未纳入支持集”，而不是“实验分支”；
  - 如果未来确认它们是“code-only 资产库候选”，可以由 owner 重新标记为 `EXPERIMENTAL` 或 `ACTIVE (code-only)`，但当前没有这样的正式声明。
- **不是 `ARCHIVED`**：
  - 没有归档标记；
  - 仍在 `feature_index.json` 中；
  - 仍被三个全量测试当作“real feature”扫描，说明尚未从当前工作集移除；
  - 历史报告还称其为“并行工作/上游未完成”，不是已退役。
- **`INCOMPLETE` 的依据最直接**：
  - README 的“脚手架/尚未完成抽象”是明确状态；
  - 缺模板、缺场景、缺能力声明、缺行为/实例证据；
  - 没有与游戏场景的集成；
  - 历史报告已使用 `UPSTREAM_INCOMPLETE` 标签。

保留意见：源码与测试并非空壳，README 的“FAIL 占位”与测试实际内容不一致。因此 `INCOMPLETE` 的含义是“**生命周期/集成未完成**”，不是“源码完全不可运行”。本阶段未执行其自测，不能对其功能正确性下结论。

---

## 3. 三个测试的契约分析

### 3.1 逐测试事实

#### 3.1.1 `test_scene_composer.py`

代码位置：`.ai/tools/scene_composer/tests/test_scene_composer.py` 第 174–182 行。

```python
feature_ids = sorted(d for d in os.listdir(FEATURES_DIR)
                     if os.path.isdir(os.path.join(FEATURES_DIR, d)))
for fid in feature_ids:
    template = template_loader.load_template(fid)
    ok("template: %s exists" % fid, bool(template))
    if template:
        scene_rel = ((template.get("scene") or {}).get("source") or "").replace("\\", "/")
        ok("template: %s source exists" % fid,
           os.path.isfile(os.path.join(FEATURES_DIR, fid, scene_rel)), scene_rel)
```

| 问题 | 结论 |
|---|---|
| 数据来源 | 直接 `os.listdir(FEATURES_DIR)`，即所有磁盘目录 |
| 是否扫描磁盘 | 是 |
| Registry 过滤 | 无（未读 `feature_index.json`） |
| 是否要求每个目录有模板 | 是；`bool(template)` 对每个 `fid` 断言 |
| 断言性质 | “所有目录都必须有 `template.yaml`”的完整性断言；不是“组合一个显式选择的 Feature 时模板可用”的运行时断言 |
| 重复验证 | 与另外两个测试重复扫描同一批 31 个目录；模板检查本身不重复 |
| 范围一致性 | 与 Schema 不一致：`template.yaml` 是可选的；测试把可选能力当成全体必填 |
| 其他证据 | 第 173 行注释仍写“12 个 Feature 均有 template.yaml”，而当前是 31 个目录；说明该断言形成于更小的 Feature 集 |

#### 3.1.2 `test_feature_capability_pipeline.py`

代码位置：第 143–153 行。

```python
real_features = sorted(name for name in os.listdir(template_loader.FEATURES_DIR)
                       if os.path.isdir(os.path.join(template_loader.FEATURES_DIR, name)))
declared_map = {
    fid: feature_capabilities.feature_capabilities(
        feature_capabilities.load_feature_definition(fid) or {})["required"]
    for fid in real_features}
ok("case1: reader output equals each real Feature's own metadata declaration",
   all(feature_capabilities.capabilities_for_feature(fid) == declared_map[fid]
       for fid in real_features), str(declared_map))
ok("case1: every real project feature declares at least one capability (adopted)",
   all(declared_map[fid] for fid in real_features), str(declared_map))
```

| 问题 | 结论 |
|---|---|
| 数据来源 | 直接 `os.listdir(template_loader.FEATURES_DIR)`，即所有磁盘目录 |
| 是否扫描磁盘 | 是 |
| Registry 过滤 | 无 |
| 是否要求每个目录有非空能力 | 是；`all(declared_map[fid] for fid in real_features)` |
| 断言性质 | 第一部分是“读取器输出 == 自身 metadata 声明”的合法一致性检查；第二部分是 Phase 1.8.12 的“adoption 已完成”迁移断言 |
| 重复验证 | 与 `test_feature_capability_adoption.py` 的“every real feature declares something”重复；两处都扫描全部目录 |
| 范围一致性 | 与 Schema 的“`capabilities.required` 默认 `[]`、未声明继续合法”冲突；把“已迁移”当成所有目录的永久条件 |
| 其他证据 | 第 137–142 行注释明确说这是 Phase 1.8.12 的数据迁移背景，不是通用架构契约 |

#### 3.1.3 `test_feature_capability_adoption.py`

代码位置：

- `real_feature_ids()`：第 127–131 行，直接 `os.listdir(template_loader.FEATURES_DIR)`；
- 真实 Feature 审计：第 294–320 行左右。

关键逻辑：

```python
def real_feature_ids() -> list:
    base = template_loader.FEATURES_DIR
    return sorted(name for name in os.listdir(base)
                  if os.path.isdir(os.path.join(base, name)))
...
for fid in real_feature_ids():
    declared_caps = feature_capabilities.capabilities_for_feature(fid)
    types = scene_node_types(fid)
    ...
    ok("audit: %s declares only registered capabilities" % fid, registered, ...)
    ok("audit: %s declaration matches its own scene/contract evidence" % fid,
       ("Node" in declared_caps)
       and (("Collision" in declared_caps) == owns_collision), ...)
ok("audit: every real feature declares something (adoption happened)",
   all(audit[fid]["declared"] for fid in audit), ...)
```

| 问题 | 结论 |
|---|---|
| 数据来源 | 直接 `os.listdir(template_loader.FEATURES_DIR)` |
| 是否扫描磁盘 | 是 |
| Registry 过滤 | 无 |
| 是否要求每个目录有模板/能力 | 能力：要求非空；模板：通过 `scene_node_types(fid)` 隐式要求入口场景存在；无模板时 `types=[]`，后续 `("Node" in declared_caps)` 必然失败 |
| 断言性质 | “所有真实 Feature 已完成 adoption，且能力声明与自身场景/契约证据一致”的迁移完成度审计 |
| 重复验证 | 与 `pipeline` 的“every real feature declares something”重复；此外还重复扫描所有目录 |
| 范围一致性 | 对没有场景、没有模板的 code-only Feature 也要求“Node + 场景证据”，与 Schema 的模板可选/能力可选直接冲突 |
| 其他证据 | 该测试的审计注释与 Phase 1.8.12 的迁移规则一致；它是迁移审计，不是永久适用于所有目录的通用契约 |

### 3.2 三个测试的共同问题

1. **数据来源相同且过宽**：三者都直接枚举 `Features/` 的所有子目录，没有从 `feature_index.json`、支持集或模板资格中取候选。
2. **没有 Registry / 资格过滤**：Registry 只被当作隐式背景；测试不检查 Feature 是否具备 `template.yaml`、是否有场景，也不区分 code-only Feature。
3. **把“目录存在”当成“Feature 必须已完成 Scene Composer 接入”**：这正是 `FEATURE_SCHEMA.md` 明确否定的推断。
4. **重复验证**：
   - `pipeline` 与 `adoption` 都要求“每个 real feature 有非空能力声明”；
   - 三者都重复遍历同一批目录；
   - `adoption` 又在 `pipeline` 基础上重复做能力一致性，并额外要求场景证据。
5. **范围不一致**：
   - `test_scene_composer` 只要求模板；
   - `pipeline` 只要求能力；
   - `adoption` 同时要求能力 + 场景证据 + 链路；
   - 三者对同一个 8 目录集合给出不同程度的失败，但都没有区分“未接入 Scene Composer”和“未完成迁移”。
6. **测试注释/命名已过时**：
   - `test_scene_composer` 注释写“12 个 Feature”；
   - `pipeline` 的 `real_features` 和 `adopted` 命名把“当前磁盘目录”误当成“正式支持集”；
   - `adoption` 的审计把“迁移阶段的全体”当成“永久全体”。

### 3.3 与历史失败的一致性

历史报告已确认：

- `.ai/context/PHASE_1_56_COMPLETION_REPORT.md` 第 283–310 行：3 个测试的失败项与这 8 个目录**逐一对应，没有第 9 个**；
- `.ai/context/PHASE_1_64_COMPLETION.md` 第 162–199 行：全量 `run_tests.py` 为 **133 PASS / 3 FAIL / 2 INCOMPLETE**，3 个 FAIL 即这三个测试对 8 个脚手架的断言；
- `.ai/context/WORK_STATE.md` 第 106–107、285、314–315 行：同样记录“8 个未跟踪、缺 `template.yaml` 的 Feature 脚手架”。

这与本报告的静态判断一致：**失败不是产品回归，而是测试范围与 Feature 资格不一致**。

---

## 4. 决策矩阵

| Feature | Current Structure | Registry Status | Capability | Template | Recommended Status | Required Action |
|---|---|---|---|---|---|---|
| `anima_behaviour` | `feature.yaml` + `anima_behaviour.gd` + 自测；无 `.tscn`；`entry_scene: ''` | **INDEXED**（无 status/enabled 字段） | `[]`（合法；无场景能力需求） | **MISSING** | **INCOMPLETE** | 不加入 Scene Composer 支持集；不补模板/能力；由 owner 决定“code-only 资产 / 正式场景 Feature / 归档” |
| `attribute_editor` | `feature.yaml` + `attribute_editor.gd` + 自测；无 `.tscn`；`entry_scene: ''` | **INDEXED**（无 status/enabled 字段） | `[]`（合法；纯数据 Resource） | **MISSING** | **INCOMPLETE** | 同上；若作为纯数据资产，应明确 code-only 资格，而不是补场景模板 |
| `audio_player_pool` | `feature.yaml` + `audio_player_pool.gd` + 自测；无 `.tscn`；`entry_scene: ''` | **INDEXED**（无 status/enabled 字段） | `[]`（合法；无场景能力需求） | **MISSING** | **INCOMPLETE** | 同上；与 `pickable_audio` 的关系不构成 Scene Composer 接入证据 |
| `blackboard` | `feature.yaml` + `blackboard.gd` + 自测；无 `.tscn`；`entry_scene: ''` | **INDEXED**（无 status/enabled 字段） | `[]`（合法；code-only 数据节点） | **MISSING** | **INCOMPLETE** | 同上；不要因 `cooldown` README 的泛称“blackboard”而误判为已集成 |
| `clean_copy` | `feature.yaml` + `clean_copy.gd` + 自测；无 `.tscn`；`entry_scene: ''` | **INDEXED**（无 status/enabled 字段） | `[]`（合法；静态工具） | **MISSING** | **INCOMPLETE** | 同上；纯 ProjectSettings 工具不应被强制场景化 |
| `flying_letter` | `feature.yaml` + `flying_letter.gd` + 自测；无 `.tscn`；`entry_scene: ''` | **INDEXED**（无 status/enabled 字段） | `[]`（合法；无场景能力需求） | **MISSING** | **INCOMPLETE** | 同上；若要做正式特效，需要独立完成场景、模板、能力、证据，不得批量伪造 |
| `pedestal_interaction` | `feature.yaml` + `pedestal_interaction.gd` + 自测；无 `.tscn`；`entry_scene: ''` | **INDEXED**（无 status/enabled 字段） | `[]`（合法；无场景能力需求） | **MISSING** | **INCOMPLETE** | 同上；玩法组件若转正，必须补齐入口场景和组合契约 |
| `pickable_audio` | `feature.yaml` + `pickable_audio.gd` + 自测；无 `.tscn`；`entry_scene: ''` | **INDEXED**（无 status/enabled 字段） | `[]`（合法；无场景能力需求） | **MISSING** | **INCOMPLETE** | 同上；与 `audio_player_pool` 的关系不代表可被 Scene Composer 实例化 |

**矩阵读法**：

- `Registry Status = INDEXED` 只说明“可被索引/发现”，不是 `ACTIVE`。
- `Capability = []` 不是缺陷；Schema 明确允许默认空。
- `Template = MISSING` 是 Scene Composer 资格的分界线，不是 Feature Metadata 的失败。
- `Recommended Status = INCOMPLETE` 是生命周期/集成判断，不是对其源码正确性的断言。

---

## 5. 两种架构方案比较（及第三方案）

### 5.1 方案 A：所有 31 个目录都是正式 Feature，补齐模板和能力声明

做法：

- 为 8 个目录新增 `template.yaml`、入口 `.tscn`、`capabilities.required`；
- 让三个测试继续按“所有目录”断言；
- 可能还要补 `behavior` / `instance` / `runtime` 证据。

优点：

- 测试表面最简单：所有目录都有模板/能力，旧断言自然通过；
- Registry、Discovery、Scene Composer 看起来“统一”。

缺点/风险：

- 直接违反 `FEATURE_SCHEMA.md`：`template.yaml` 和 `capabilities.required` 都是可选项；
- 对 `attribute_editor` / `clean_copy` 这类纯数据/工具 Feature，强制场景化没有架构意义；
- 需要为 8 个互不相关的 Feature 伪造或新建入口场景，扩大修改范围；
- 需要相应的场景证据、能力证据、行为/实例证据，不能只放空模板；
- 会把“未完成/上游脚手架”变成正式支持集，改变 23 Feature / 60 Behavior 的现有分母；
- 没有 owner 授权，也没有使用场景证据。

**结论：不推荐。** 它解决的是“让旧测试变绿”，不是“让架构正确”。

### 5.2 方案 B：只有符合 Registry Eligibility 的 Feature 参与正式 Pipeline

做法：

- 先定义 Registry Eligibility；
- 只有 eligible Feature 进入 Scene Composer / Capability Pipeline / Adoption；
- 其他目录不参与正式断言。

问题：

- **当前 Registry 没有 eligibility 字段**；
- 如果把 eligibility 定义为“有合法 `feature.yaml`”，则 31 个全部符合，8 个仍然进入，问题没有解决；
- 如果把 eligibility 定义为“有 `template.yaml`”，则实际上已经采用了“Scene Composer 资格 = 模板存在”，这就是方案 C 的核心；
- 如果新增 `enabled` / `eligible` 字段，则需要改 Schema、索引生成器、Validator、Discovery 和现有数据，影响面远大于当前测试范围。

**结论：B 的方向正确，但作为独立方案不完整。** 它必须回答“Eligibility 由什么字段/事实定义”；在现有架构下，最自然、最少的定义就是 `template.yaml` + 入口场景存在。

### 5.3 方案 C（推荐）：两级资格，Registry 成员 ≠ Scene Composer 支持集

定义四个可推导的集合，不新增状态字段：

| 集合 | 判定条件 | 当前数量 | 用途 |
|---|---|---:|---|
| **Registry Members** | 存在合法 `feature.yaml`（`build_feature_index.py` 可收录） | **31** | Discovery / 资产目录 / 元数据查询 |
| **Scene Composer Eligible** | 存在 `template.yaml`，且 `scene.source` 指向的入口场景存在 | **23** | Scene Composer 组合、模板完整性、场景契约 |
| **Capability Adopted** | 在 Scene Composer Eligible 基础上，Feature 作者声明了与自身场景/契约一致的能力（可为 `[]`，但不得推断） | **23**（当前均有非空声明） | Capability Pipeline / Adoption 审计 |
| **Behavior Supported** | `template.yaml` 中声明了非空 `behavior` | **23**（60 Behavior） | 行为证据 / Runtime 验证 |

这解释了当前所有事实：

- 31 个 Registry 成员：全部有 `feature.yaml`；
- 23 个模板/能力/行为支持集：有 `template.yaml` 的那批；
- 8 个 INCOMPLETE 脚手架：Registry 成员，但不在 Scene Composer/Capability/Behavior 支持集；
- 3 个测试的失败：把“Registry Members”误当成“Scene Composer Eligible”，并对 8 个目录套用了 23 个目录的契约。

方案 C 的关键不是“删除 8 个目录”，而是**把两个集合分开表达**：

> **所有 Feature 都可以被 Registry 索引；只有声明了 Scene 模板的 Feature 才参与 Scene Composer 全量契约。**

这与 `FEATURE_SCHEMA.md` 的“template 可选 / 无 template 未接入 Scene Composer”逐字一致，也不需要新增未定义的 `enabled` 字段。

---

## 6. 最终推荐方案及证据

### 6.1 推荐

**采用方案 C。**

具体决策：

1. 31 个目录继续作为 **Registry Members**；不删除、不改 `feature.yaml`、不重生成索引来“隐藏”它们。
2. 8 个目标目录判定为 **INCOMPLETE**，不进入 **Scene Composer / Capability Adoption / Behavior** 正式支持集。
3. 不要求它们补 `template.yaml`，不要求补非空 `capabilities`；`[]` 是合法的“无 Scene 能力需求”。
4. 三个全量测试的断言范围应改为 **Scene Composer Eligible**（有模板且入口场景存在）的 23 个 Feature，而不是所有磁盘目录。
5. 如果 owner 确认其中某个是 code-only 资产，应允许其长期保持“Registry Member + 无模板 + `[]`”，但必须通过文档或显式资格规则表达，而不是靠测试隐式放行。
6. 如果 owner 要将某个转为正式 Scene Feature，必须单独完成：入口 `.tscn` → `template.yaml` → 能力声明 → 场景/实例证据 → 行为/运行时证据 → 测试；不得批量补空模板。

### 6.2 证据链

| 证据 | 支持结论 |
|---|---|
| `FEATURE_SCHEMA.md` §4：“`capabilities.required` 默认 `[]`；未声明的存量 Feature 继续合法” | 8 个空能力不是错误 |
| `FEATURE_SCHEMA.md` §7：“每个 Feature 目录**可选**提供 `template.yaml`”；“无 template.yaml 的 Feature 视为未接入 Scene Composer” | 8 个缺模板不是 Feature 失败，只是未接入 |
| `FEATURE_SCHEMA.md` §6：新 Feature 在 Finalization 交付 `feature.yaml` | 8 个只有脚手架 README，没有 Finalization 证据 |
| `build_feature_index.py` 第 102 行起：扫描所有目录，只校验必填 metadata | Registry 的 31 条不代表 31 个全部启用 |
| `feature_behavior_evidence.declared_features()`：只收集有非空 `behavior` 的模板 | 实际支持集天然是 23，不是 31 |
| `PHASE_1_59_AUDIT.md` 第 29–34 行：“未纳入支持集”“23 Feature / 60 Behavior” | 历史架构已经按两级集合运行 |
| `PHASE_1_56_COMPLETION_REPORT.md` 第 283–310 行：3 个失败与 8 个目录逐一对应，无第 9 个 | 失败是范围问题，不是产品回归 |
| `WORK_STATE.md` 第 106–107 行：“8 个未跟踪、缺 template.yaml 的 Feature 脚手架” | 这是已知的上游未完成项 |
| 8 个目录的 README：“脚手架……尚未完成抽象”；Git 未跟踪；无 `.tscn`；无外部引用 | 支持 `INCOMPLETE`，不支持 `ACTIVE` |

### 6.3 为什么不是“删除/归档这 8 个目录”

- 本阶段严格禁止修改 Feature 目录；
- 它们仍被 Registry 索引，且可能是 owner 有意保留的 code-library 候选；
- 没有 owner 的归档决定；
- 删除会改变索引、测试分母和历史可追溯性；
- 当前问题可以通过“资格分层 + 测试范围”解决，不需要破坏数据。

---

## 7. 影响范围

| 模块 | 推荐方案下的影响 | 必须保持不变 |
|---|---|---|
| **Feature Registry** | 不修改 Schema、不新增 `status` 字段；31 条索引可以保留；`build_feature_index.py` 行为不变 | `feature.yaml` 作为 Source of Truth；索引是缓存；23 个正式 Feature 的 metadata |
| **Scene Composer** | 生产代码不需要改；资格边界本来就是 `template.yaml`；测试改为遍历 Eligible 集合 | `template_loader` 的“无模板返回 `{}`”语义；23 个模板/场景；组合产物 |
| **Capability Pipeline** | 核心读取器不变；缺声明仍返回 `[]`；测试不再要求所有目录非空 | `feature_capabilities.py` 的默认 `[]` 语义；能力名必须登记的规则 |
| **Capability Adoption** | 测试范围改为 Eligible 的 23 个；8 个 code-only 不参与“Node + 场景证据”审计 | 对 23 个 Feature 的“声明 == 自身场景/契约证据”检查；不得推断能力 |
| **Feature Discovery** | 无需改动；仍可返回 31 个 Registry 成员；文档应说明其中 8 个不是 Scene Composer 候选 | `feature_discovery_schema.yaml` 的现有输出契约；评分逻辑 |
| **Skill Discovery / Skill Registry** | 无影响；未发现这 8 个 Feature 被 Skill/Workflow 引用 | `.ai/config/skill-registry.yaml` 和 `.ai/skills/**` 不变 |
| **Feature Validator** | 无影响；它本来就不检查 template/capability；8 个 metadata 仍可通过其现有检查 | Validator 的 Feature Metadata / Index 同步检查；不新增隐式规则 |
| **现有测试** | Phase 4 需要调整 3 个测试的候选集合；其余 27 个（剩余测试中的其他项）不应因本决策改变 | 23 个 Feature 的既有断言；fixture 中“legacy 空能力合法”的测试；不降低断言强度 |
| **历史 Feature 数据** | 8 个未跟踪目录原样保留；索引仍为 31；不修改 Evidence/Attestation | `.ai/context/feature_index.json` 现有数据；`.ai/context/feature_graph.json`；历史报告 |
| **Git/工作区** | 本阶段无写操作；Phase 4 也不应删除/移动这 8 个目录，除非 owner 单独授权 | 当前 HEAD、staged=0、未跟踪状态；不执行 add/commit/push/reset/clean |

### 7.1 明确不需要修改的部分

- `Features/FEATURE_SCHEMA.md`：现有“template 可选 / capabilities 可选”已经足够支持方案 C；本阶段不需要改规范。
- `.ai/tools/feature_registry/build_feature_index.py`：继续索引所有合法 `feature.yaml`；不要为了排除 8 个目录而加过滤（会破坏 Registry 的“资产目录”定位）。
- `.ai/tools/scene_composer/scene_composer.py` / `template_loader.py` / `feature_capabilities.py`：生产逻辑不变。
- `.ai/tools/feature_registry/feature_discovery.py`：发现逻辑不变；如未来要区分“可组合候选”，应另立显式资格，不在本阶段偷偷加过滤。
- 23 个正式 Feature 的 `feature.yaml`、`template.yaml`、`.tscn`、能力声明、行为声明。
- Evidence / Attestation / mutation catalog / 历史报告。

---

## 8. 未解决问题

这些问题不能在 Phase 3.1 擅自决定；需要 owner 审查。

1. **8 个目录的最终归属**
   - 是“暂时不接入 Scene Composer 的 code-only 资产”？
   - 是“等待完成的正式 Feature”？
   - 是“应归档/删除的实验产物”？
   - 当前证据只支持 `INCOMPLETE`，不能替代 owner 的产品决策。

2. **缺少正式生命周期字段**
   - Registry 没有 `status` / `enabled` / `eligible`；
   - README 是自由文本，不能机器校验；
   - 方案 C 用 `template.yaml` 作为结构性资格，解决了 Scene Composer 范围，但没有解决“Registry 成员是否 active”的语义。
   - 是否要在未来引入显式状态字段，需要单独架构决策；本阶段不建议顺手加。

3. **README 与源码/测试不一致**
   - README 说“当前是 FAIL 占位”，但测试包含真实断言；
   - 无法从静态证据判断是 README 过时，还是测试/源码由后续并行工作补充；
   - 本阶段未执行这 8 个自测，不能宣称它们 PASS/FAIL。

4. **Category 枚举不合规**
   - 8 个目录使用 `animation` / `combat` / `audio` / `ai` / `general` / `ui`，不在 `FEATURE_SCHEMA.md` §3 的 v1 枚举中；
   - 现有 Validator 不强制 category 枚举，且 `patrol_movement` 也使用未登记的 `movement`；
   - 这说明 category 不是可靠的资格信号，也暴露了数据卫生问题；是否登记新 category 需单独决定。

5. **`feature_index.json` 包含未跟踪目录**
   - 索引生成时间 `2026-10-31T13:29:04Z`，8 个目录均在索引中；
   - 如果未来删除/归档这些目录，索引和 Discovery 结果会改变；
   - 当前不应为了让索引“看起来干净”而重生成或过滤，否则会掩盖真实工作区状态。

6. **Discovery 的语义**
   - `feature_discovery.py` 会把 8 个 code-only Feature 当作可推荐候选；
   - 如果 Discovery 的使用者是 Scene Composer，这可能产生“可发现但不可组合”的误导；
   - 本阶段不建议改 Discovery；应在文档中明确“Registry 候选 ≠ Scene Composer 可组合”，或未来增加显式 `scene_composer` 资格。

7. **测试修复的边界**
   - 是只改 3 个测试的候选集合，还是抽一个共享的 `scene_composer_eligible_features()` 辅助函数？
   - 前者改动最小，后者避免三处重复；
   - 无论哪种，都必须保持 23 个 Feature 的断言强度，不能把测试改成“只检查存在的模板”而失去意义。

8. **8 个 Feature 的真实功能状态**
   - 源码有实现、测试有断言，但未执行；
   - 不能把“静态看起来完整”当成“已验证”；
   - 如果 owner 要转正，必须先跑各自 `validation.command`，再补场景/组合/行为证据。

---

## 9. Phase 4 修改建议

> 本节只是建议，Phase 3.1 不执行任何修改。Phase 4 开始前需要 owner 对 §6 的方案 C 作出确认。

### 9.1 推荐的最小修改集（方案 C）

**目标**：让 3 个测试只对 Scene Composer Eligible 的 Feature 施加 Scene Composer 契约；不碰 8 个目录和 23 个正式 Feature 的数据。

1. **增加一个派生资格辅助**
   - 在测试侧（优先）或 `template_loader` 的只读辅助中定义：
     ```text
     scene_composer_eligible(fid) :=
         feature.yaml exists
         AND template.yaml exists
         AND template.scene.source 指向的入口场景存在
     ```
   - 不硬编码 23，不按目录名白名单；由数据推导。
   - 若放在生产模块，必须保持只读、无副作用；若只服务测试，放在测试辅助模块，避免扩大生产 API。

2. **修改 `test_scene_composer.py`**
   - 将第 174–182 行的 `feature_ids` 从“所有目录”改为“Eligible 集合”；
   - 保留 `template: <id> exists` 与 `source exists` 两个断言，但只对 Eligible 的 Feature 执行；
   - 删除/更新“12 个 Feature”的过时注释；
   - 不新增“所有目录都必须有模板”的断言。

3. **修改 `test_feature_capability_pipeline.py`**
   - 将 `real_features` 改为 Eligible 集合；
   - 保留“reader 输出 == 自身 metadata”的一致性断言；
   - 保留 fixture 中 `legacy` 无声明 → `[]` 的合法测试；
   - 删除“每个 real feature 必须非空”的全局断言，或把它限定为“已 adoption 的 Eligible 集合”，且不要把它推广到 code-only Feature；
   - 不改变 Capability Pipeline 生产代码。

4. **修改 `test_feature_capability_adoption.py`**
   - 将 `real_feature_ids()` 改为 Eligible 集合；
   - 保留 23 个 Feature 的“声明只含已登记能力 / 声明与自身场景证据一致 / 单 Feature 链路”检查；
   - 删除对 8 个无场景目录的隐式 `Node + 场景证据` 要求；
   - 保留对 fixture 的迁移测试，不要用 fixture 结果替代真实 23 个 Feature 的审计。

5. **不改 8 个目录**
   - 不新增 `template.yaml`；
   - 不新增能力声明；
   - 不添加 `.tscn`；
   - 不修改 README 状态（除非 owner 单独要求）；
   - 不删除、不移动、不 Git add。

6. **不改 Registry / Discovery / Validator**
   - `build_feature_index.py` 继续收录 31 个；
   - `feature_index.json` 保持现状（除非另有数据变更需求）；
   - `feature_discovery.py` 不改；
   - Validator 不加 template/capability 的隐式必填规则。

7. **验收**
   - Phase 4 修改后，分别运行：
     - `.ai/tools/run_tests.py .ai/tools/scene_composer/tests/test_scene_composer.py`
     - `.ai/tools/run_tests.py .ai/tools/scene_composer/tests/test_feature_capability_pipeline.py`
     - `.ai/tools/run_tests.py .ai/tools/scene_composer/tests/test_feature_capability_adoption.py`
   - 期望：三项通过，且不再把 8 个目录计为失败；
   - 不执行 8 个 Feature 自测（除非 owner 要求转正评估）；
   - 不修改 Evidence/Attestation；不做 Git 写操作；
   - 若任何一项仍失败，先检查是否还有其它“所有目录”假设，而不是放宽断言。

### 9.2 如果 owner 选择方案 A

- 为每个 Feature 单独立项，不批量生成空模板；
- 每个 Feature 至少需要：真实入口 `.tscn`、`template.yaml`、场景可实例化证明、能力声明及证据、必要的 `instance`/`behavior`/`runtime` 声明、自测通过；
- 这会改变 23 Feature / 60 Behavior 的分母，必须单独做影响评估；
- 不建议在当前 Phase 4 范围内执行。

### 9.3 如果 owner 选择方案 B（显式 Registry Eligibility）

- 需要新增正式资格字段（例如 `lifecycle.status` 或 `scene_composer.eligible`）；
- 需要同步修改 Schema、索引生成器、Validator、Discovery、所有消费方；
- 需要迁移 31 条数据并决定 8 个目录的初始状态；
- 影响面明显大于方案 C，不建议在本阶段顺带实施；
- 若未来实施，应作为独立架构阶段，不与本次回归修复混合。

### 9.4 Phase 4 不应做的事

- 不为让测试变绿而伪造模板/能力；
- 不删除 8 个目录；
- 不把 `test_scene_composer` 改成“只检查存在的模板”而没有 Eligible 过滤；
- 不把 `adoption` 的非空能力断言无条件删除（对 23 个 Feature 仍需保留证据一致性）；
- 不修改 Registry 以隐藏 8 个目录；
- 不执行 Git add/commit/push/reset/clean；
- 不修改 Evidence/Attestation。

---

## 10. 审计结论摘要

1. **权威规则**：`feature.yaml` 定义 Feature Metadata；`template.yaml` 可选；无模板 = 未接入 Scene Composer；`capabilities.required` 可选，默认 `[]`。
2. **Registry 事实**：31 个 Feature 被索引；Registry 没有 `enabled/status` 字段；索引收录 ≠ Scene Composer 启用。
3. **8 个目录事实**：有 `feature.yaml`、源码、真实断言测试；无 `.tscn`、无模板、能力 `[]`、无外部引用、Git 未跟踪、README 明示脚手架。
4. **生命周期判断**：8 个均为 **INCOMPLETE**；不是 ACTIVE，也没有足够证据判为 EXPERIMENTAL/ARCHIVED。
5. **测试问题**：3 个测试都直接扫描所有目录，无 Registry/模板过滤；把“所有目录”当成“Scene Composer 支持集”；`pipeline` 与 `adoption` 还重复要求非空能力。
6. **方案选择**：A 违反可选性并扩大范围；B 缺少 Eligibility 定义；**C（两级资格）最小、最符合现有 Schema，推荐**。
7. **Phase 4 最小动作**：只改 3 个测试的候选集合为 Scene Composer Eligible；保留 23 个 Feature 的断言强度；不碰 8 个目录、Registry、生产 Scene Composer/Capability 代码。
8. **当前状态**：本阶段只读完成；报告生成后停止，等待用户审查；未进入 Phase 4，未执行剩余 30 个测试。

---

**停止点**：Phase 3.1 审计完成。建议用户先确认 §6 的方案 C 与 §9.1 的最小修改集，再授权 Phase 4。
