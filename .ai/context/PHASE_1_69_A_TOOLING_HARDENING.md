# Phase 1.69-A — External Code Library Tooling Hardening

日期：2026-11-12
阶段：Phase 1.69-A
最终判定：**PASS**

## A. Initial State

### Git 与工作区

本轮重新开始前记录的状态：

- 当前 HEAD：`726cc30112855ab45c1a7fd27466ba9b2514b5df`
- 分支：`master`
- `HEAD` 已推送到 `origin/master`，内容是 Phase 5 closure 文档，不是本阶段工具修改。
- 工作区为 dirty，共约 `1,061` 条 `git status --short` 记录，包含：
  - 已有 `sources/`、`references/`、`catalog.yaml`、`INDEX.md` 更新；
  - 已有 `feature_index.json`、learning/context 文件修改；
  - 33 个已存在的 `RodZill4` GUT reference 删除；
  - 本阶段修改的两个工具文件；
  - 本阶段新增的测试和报告。

本轮没有执行 `git reset`、`git checkout`、`git restore`、`git clean`、`git commit` 或 `git push`。

### 现有数据状态（Phase 1.69 只读审计）

- `catalog.yaml`：4,257,885 bytes，7,270 条记录，6,813 个唯一片段。
- `INDEX.md`：1,628,554 bytes，6,966 行。
- `origin/master` 的 `catalog.yaml`：3,674,164 bytes，6,381 条记录，非空。
- `sources/`：77 个仓库。
- Source `.gd`：7,059；shader：211。
- `references/`：6,610 个 `.gd` + 203 个 shader，共 6,813 个唯一片段。
- `_meta.json`：77 个。
- LICENSE/COPYING：51 个。
- 1 个空 `.gdignore`，0 个空代码文件。
- 7,270 个 source 文件全部存在且 SHA 匹配。
- 6,813 个唯一 reference 全部存在。
- 0 个重复 ID、0 个坏 duplicate 指针、0 个孤 reference。
- 457 条 duplicate records。
- Catalog 状态：6,610 条 OK、203 条 skipped_shader、457 条 duplicate。
- 11 个 domains，77 个 repos。

本轮重新复核 `catalog.yaml` 与 `INDEX.md` 的大小仍为 4,257,885 与 1,628,554 bytes，与审计值一致。

## B. Implementation

### B.1 Collector 安全加固

文件：`.ai/skills/foundation/godot-gdscript/tools/github_collector.py`

#### 移除先删除行为

原 `cmd_catalog()` 在生成前执行：

```python
_rmtree_force(REFERENCES_DIR)
```

该调用已从 `cmd_catalog()` 移除。现在不存在“先清空 references，再开始生成”的路径。

#### 预检

新增并接入 `_preflight_sources()`、`_load_repo_meta()`、`_candidate_files()`：

- `Sources` 目录不存在 → 非零 `SystemExit`，明确输出原因。
- `Sources` 下没有仓库目录 → 非零失败。
- 所有仓库均没有 `.gd` / `.gdshader` 候选 → 非零失败。
- 任一仓库缺少 `_meta.json`，或 JSON 无法解析、不是对象，或缺少 `full_name` / `slug` / `commit_sha` → 非零失败。
- 所有候选都超过 `MAX_FILE_BYTES` → 非零失败。
- 生成结果没有 Catalog entries → 非零失败。

预检发生在临时目录创建、任何目标写入或替换之前。

#### 临时生成、验证后替换

`cmd_catalog()` 支持可选路径参数，便于测试使用独立临时数据：

```python
cmd_catalog(
    args,
    sources_dir=...,
    references_dir=...,
    catalog_path=...,
    index_path=...,
)
```

默认仍使用原有常量，因此现有 CLI 行为保持兼容。

流程：

1. 对 sources 和 metadata 做完整预检。
2. 在 `references_dir.parent` 下创建同文件系统临时目录 `.catalog-stage-*`。
3. 在临时目录生成 `references/`。
4. 在临时目录生成 `catalog.yaml`。
5. 在临时目录生成 `INDEX.md`。
6. 调用 `_validate_catalog_output()` 验证：
   - entries 非空；
   - ID 非空且不重复；
   - 必要字段存在；
   - `duplicate_of` 目标存在；
   - 每个唯一片段确实有对应临时 reference 文件；
   - 临时 Catalog 可重新解析且条目数一致；
   - 临时 INDEX 非空；
   - 去重后至少有一个有效片段。
7. 只有全部验证通过后，才按 `references → catalog.yaml → INDEX.md` 顺序替换正式目标。
8. 替换失败时按已成功替换的目标逆序回滚。
9. 生成失败时清理临时目录，不触碰正式目标。

#### 回滚与异常保留

新增：

- `CatalogCommitError`
- `_catalog_fail()`
- `_validate_catalog_output()`
- `_commit_catalog_stage()`
- `_remove_path()`

替换阶段会把旧目标先移动到临时 `rollback/` 目录，再安装新目标。失败时：

- 尽可能把已安装的新目标移走；
- 尽可能把旧目标恢复回原位置；
- 如果回滚本身失败，抛出 `CatalogCommitError(..., preserve_stage=True)`；
- 保留临时目录和旧数据备份，供人工恢复；
- 不会在失败路径上静默删除唯一可恢复的旧数据。

这里不宣称三文件替换具有天然原子性。代码只保证：生成完成前不删除旧 references；替换阶段失败时尝试回滚；无法确认回滚时保留临时备份并明确失败。

### B.2 Search 诊断与来源追溯

文件：`.ai/tools/feature_registry/search_assets.py`

#### 统一故障类型

新增：

```python
class SearchSystemError(RuntimeError):
    ...
```

索引缺失、空文件、解析失败、schema 错误、Feature Index 缺失/无效都抛出该异常。`main()` 捕获后向 stderr 输出：

```text
[search] ERROR: ...
```

并以非零状态 `2` 退出，而不是打印空结果并返回 0。

#### Catalog 状态诊断

新增 `_load_catalog_entries()`：

- 文件不存在 → `Catalog Missing`。
- 文件大小为零 → `Catalog Empty`。
- YAML 解析失败 → `Catalog Invalid`。
- 解析成功但无 entries → `Catalog Empty`。
- 缺少 `id`、`domain`、`repo`、`repo_path`、`license`、`source_url`、`commit_sha`、`parse_status` → `Catalog Schema Error`。
- `duplicate_of` 指向不存在的 ID → `Catalog Schema Error`。
- 合法且无关键词匹配 → 返回空列表，属于正常 `No Search Results`。

#### Feature Index 状态诊断

新增 `_load_feature_index()`：

- 文件不存在 → `Feature Index Missing`。
- 文件大小为零 → `Feature Index Invalid`。
- JSON 解析失败 → `Feature Index Invalid`。
- 顶层不是对象，或 `features` 不是数组 → `Feature Index Invalid`。
- feature entry 不是对象或缺少 `id` → `Feature Index Invalid`。
- 合法且无匹配 → 空列表，属于正常无结果。

#### 来源字段

`search_snippets()` 的 JSON 结果现在包含：

- `id`
- `domain`
- `repo`
- `repo_path`
- `lines`
- `stars`
- `license`
- `source_url`
- `commit_sha`
- `reference_path`
- `parse_status`
- `duplicate_of`
- 兼容字段 `file`（与 `reference_path` 相同）

`reference_path` 由 Catalog 的 `domain` 和 `id` 构造；duplicate 记录没有独立 reference 文件，因此其 `reference_path` 为 `null`，并保留 `duplicate_of`，不会把重复代码伪装成独立文件。

字段直接来自 Catalog，没有生成或伪造 commit SHA、license 或 source URL。

#### 普通文本输出

文本模式增加独立字段行：

```text
repo=... license=... commit_sha=...
source_url=...
```

保留简短摘要、参考路径和 `duplicate_of` 提示，没有把完整 JSON 塞进文本输出。

#### `--all` 语义

- 默认模式：排除 `duplicate_of` 非空记录；只保留 `parse_status` 为 `OK` 或 `skipped_shader` 的有效片段；继续应用 `--domain`。
- `--all`：保留所有 Catalog 记录，包括 duplicate 和所有 `parse_status`；duplicate 仍保留 `duplicate_of`，`reference_path` 仍为空。
- `--kind feature`、`--kind snippet`、`--kind all` 的边界保持不变。
- `--domain` 仍只用于片段搜索，不改变 Feature 搜索语义。

## C. Safety Verification

### 已实际验证的保护

隔离测试全部通过，覆盖：

1. `cmd_catalog()` 不再先删除 references。
2. Sources 缺失时失败，旧 references/catalog/INDEX 保持不变。
3. Sources 为空时失败，旧数据保持不变。
4. 没有候选文件时失败，旧数据保持不变。
5. 所有候选被大小过滤时失败，旧数据保持不变。
6. `_meta.json` 缺失时失败，旧数据保持不变。
7. Catalog 写入异常时，旧 references/catalog/INDEX 保持不变。
8. INDEX 写入异常时，旧 references/catalog/INDEX 保持不变。
9. 替换阶段注入异常时，旧数据回滚。
10. 正常生成时，Catalog 条目、唯一 reference、INDEX 三者一致。
11. SHA256 去重和 `duplicate_of` 保持原有语义。
12. 临时目录位于目标父目录下，清理不影响原始数据。

### 限制

- 没有在真实 77 仓库数据上执行完整 Catalog 重建；任务明确禁止本阶段执行真实 `catalog`。
- 没有验证真实磁盘满、权限拒绝、进程强杀等 OS 级异常；这些路径通过代码审查和隔离注入测试覆盖了主要异常分支。
- 多文件替换不被宣称为原子操作；失败时依靠回滚和保留临时备份降低风险。

## D. Search Verification

以下均为对真实本地数据的只读搜索结果。

### Feature 搜索

命令：

```bash
python .ai/tools/feature_registry/search_assets.py --query "health" --kind feature
```

结果摘要：

```text
== Features 资产（可直接复用）: 10 ==
  [7] health (component) provides=health_state,damage_receiver,heal_receiver,death_event
  [6] health_bar (component)
  [3] hit_flash, i_frames, stun
  ...
== 参考片段（需抽象 Feature 化）: 0 ==
```

### External Code 搜索

命令：

```bash
python .ai/tools/feature_registry/search_assets.py --query "camera follow" --kind snippet --limit 5
```

结果摘要：

```text
== 参考片段（需抽象 Feature 化）: 5 ==
  [9.36] ramokz__phantom-camera__...__path_follow.gd general/15L
       repo=ramokz/phantom-camera license=MIT commit_sha=9874dfe68827
       source_url=https://github.com/ramokz/phantom-camera/blob/main/...
  [8.97] godotengine__godot-demo-projects__3d__kinematic_character__player__follow_camera.gd general/47L
       repo=godotengine/godot-demo-projects license=MIT commit_sha=b761b4cd5718
       source_url=https://github.com/godotengine/godot-demo-projects/blob/master/...
```

### JSON 来源字段

`--kind snippet --json` 的真实结果包含：

```json
{
  "id": "godotengine__godot-demo-projects__2d__role_playing_game__combat__combatants__health.gd",
  "domain": "combat",
  "repo": "godotengine/godot-demo-projects",
  "repo_path": "2d/role_playing_game/combat/combatants/health.gd",
  "license": "MIT",
  "source_url": "https://github.com/godotengine/godot-demo-projects/blob/master/...",
  "commit_sha": "b761b4cd5718",
  "reference_path": "...\\references\\combat\\...health.gd",
  "parse_status": "OK"
}
```

### `--all` 与 duplicate

真实数据中 `autofree`：

```text
默认模式: 1 条
--all:   3 条
```

`--all` 输出中的 duplicate 示例：

```text
RodZill4__material-maker__addons__gut__autofree.gd
  reference_path=None
  duplicate_of=ceceppa__anima__addons__gut__autofree.gd
```

`--kind all` 和 `--domain movement` 也已运行：

- `--kind all` 保留 Feature 与 snippet 两个分区。
- `--domain movement` 只返回 movement 片段。
- 默认可正常返回无匹配提示；索引故障则通过 `SearchSystemError` 非零退出。

### 真实 Catalog 统计

```text
catalog_entries 7270
unique 6813
duplicates 457
missing_commit 0
missing_source_url 0
```

## E. Test Results

### 语法检查

命令：

```bash
python -m py_compile \
  .ai/skills/foundation/godot-gdscript/tools/github_collector.py \
  .ai/tools/feature_registry/search_assets.py \
  .ai/tools/feature_registry/tests/test_phase169_tooling.py
```

结果：

```text
PY_COMPILE_EXIT=0
```

### 隔离测试

命令：

```bash
python .ai/tools/feature_registry/tests/test_phase169_tooling.py
```

结果：

```text
TEST_EXIT=0
PASS: Phase 1.69-A tooling hardening tests
```

共 40 项断言通过，覆盖 Collector 22 项和 Search 18 项：

#### Collector

1. Sources 缺失时失败。
2. Sources 缺失时旧数据不变。
3. Sources 为空时失败。
4. Sources 为空时旧数据不变。
5. 无代码候选时失败。
6. 无代码候选时旧数据不变。
7. 所有候选被过滤时失败。
8. 所有候选被过滤时旧数据不变。
9. metadata 缺失时失败。
10. metadata 缺失时旧数据不变。
11. 正常数据成功生成。
12. Catalog entries 数量正确。
13. SHA256 去重保留唯一片段。
14. duplicate 指向保留的 id。
15. 每个唯一条目有一个 reference 文件。
16. INDEX 非空。
17. Catalog 写入异常时失败。
18. Catalog 写入异常时旧数据不变。
19. INDEX 写入异常时失败。
20. INDEX 写入异常时旧数据不变。
21. 替换异常时失败。
22. 替换异常时回滚旧数据。

#### Search

1. Catalog 缺失 → `Catalog Missing`。
2. Catalog 空文件 → `Catalog Empty`。
3. Catalog 损坏 → `Catalog Invalid`。
4. Catalog 合法但无匹配 → 空结果。
5. 默认排除 duplicate。
6. `--all` 包含 duplicate。
7. duplicate 的 `reference_path` 为空。
8. JSON 来源字段完整。
9. Catalog Schema Error。
10. Feature Index Missing。
11. Feature Index Invalid。
12. Feature 搜索可用。
13. Feature 合法但无匹配。
14. CLI JSON 包含片段。
15. CLI JSON 包含 `commit_sha`。
16. 文本输出包含 repo。
17. 文本输出包含 license。
18. 文本输出包含 source URL。

测试只使用 `.ai/tmp/` 下的独立临时目录，不触碰真实 `code_library`。

## F. Regression Results

### 已验证

- 真实 Feature 搜索正常：`health` 返回 10 个 Feature。
- 真实 External Code 搜索正常：`camera follow` 返回 5 个片段。
- JSON 输出包含全部来源字段。
- 普通文本输出包含 repo、license、source_url、commit_sha。
- 默认模式排除 duplicate（`autofree`: 1 条）。
- `--all` 包含 duplicate（`autofree`: 3 条）。
- `--kind feature`、`--kind snippet`、`--kind all` 保持边界。
- `--domain movement` 正常工作。
- 真实 Catalog 统计保持 7,270 / 6,813 / 457。
- 真实 Catalog 的 `commit_sha` 和 `source_url` 没有缺失。
- `git diff --check` 返回 0（仅 Git 的 LF/CRLF 提示，没有 whitespace error）。
- 未执行 `catalog`、`check`、`backfill-meta` 或 `promote`。
- 未执行任何 Git 写操作。

### 兼容性

代码搜索确认：

- `_read_catalog_entries()`、`_write_catalog_yaml()`、`_write_index_md()` 的无参数调用仍然有效。
- `cmd_check()`、`cmd_backfill_meta()` 和 reindex 入口继续使用默认路径。
- `cmd_catalog()` 的现有 CLI 参数没有被删除。
- Catalog 字段集合、SHA256 去重、domain 分类和 references 命名规则没有改变。
- Feature Registry 数据结构没有改变。
- Search 的 `--kind` / `--domain` 没有被扩展成新的 Feature 管理系统。

## G. Files Changed

本阶段实际修改/新增：

1. `.ai/skills/foundation/godot-gdscript/tools/github_collector.py`
   - 移除 `cmd_catalog()` 先删除 references 的行为。
   - 新增预检、临时生成、验证、替换和回滚辅助函数。
   - 为 `_write_catalog_yaml()`、`_write_index_md()`、`_read_catalog_entries()` 增加可选路径参数。

2. `.ai/tools/feature_registry/search_assets.py`
   - 新增 `SearchSystemError`。
   - 新增 Catalog / Feature Index 状态诊断。
   - 增加 JSON 和文本来源字段。
   - 调整 `--all` 语义。
   - 保持 `--kind` / `--domain` 边界。

3. `.ai/tools/feature_registry/tests/test_phase169_tooling.py`
   - 新增隔离测试，共 40 项断言。

4. `.ai/context/PHASE_1_69_A_TOOLING_HARDENING.md`
   - 本报告。

本阶段没有写入或重建（工作区中的既有 dirty 状态不属于本阶段修改）：

- `sources/` 内容
- `references/` 内容
- `catalog.yaml` 内容
- `INDEX.md` 内容
- `feature_index.json`
- 任何已有 Feature
- Feature Registry 数据结构
- GitHub 采集策略
- 现有 domain 分类规则
- Godot 官方文档 Skill
- 其他已完成 Phase 的文件

## H. Final Verdict

**PASS**

同时满足：

- Collector 不再先删除后生成。
- 空数据无法覆盖有效索引。
- 生成失败时原始数据得到保护。
- 成功生成时 Catalog、INDEX、References 保持一致。
- Search 能区分索引故障与正常无结果。
- 搜索结果包含来源追溯信息。
- `--all` 行为符合新定义。
- Feature 搜索没有回归。
- 40 项自动化断言全部通过。
- 真实代码库只读搜索通过，Catalog/INDEX 大小与审计值一致。
- 最终报告已创建。
