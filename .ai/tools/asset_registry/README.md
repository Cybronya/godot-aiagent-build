# Asset Registry（Phase 1.7 — Asset / Resource Intelligence）

让 Agent 能够**查询、筛选、绑定、校验** Godot 项目里的资源，把「使用项目现有资源」
变成可复现、可验证的链路，而不是人工翻目录或猜文件名。

Registry 是 **Query / Index**，不是 Runtime Manager：没有 AssetManager，
没有全局单例，不产生 Gameplay State。

```text
Game Requirement
      ↓
Gameplay Blueprint        survival_game.yaml
      ↓
Entity / Feature Blueprint  slime_enemy.yaml（features + assets 角色声明）
      ↓
Asset Discovery           query_assets.py / check_compatibility.py
      ↓
Resource Binding          bind_assets.py → .ai/context/asset_bindings/*.yaml
      ↓
Scene Composition         scene_composer.py --bind-assets → Scenes/*.tscn
      ↓
Static Validation         validator/check_assets.py（+ 既有 1~4 段）
      ↓
Runtime Playtest          runtime/run_scene.py（真实启动 Godot）
      ↓
Diagnosis / Self-Repair   runtime/diagnose_runtime.py, self_repair.py
```

## 工具

| 工具 | 职责 | 退出码 |
|---|---|---|
| `scan_assets.py` | 扫描资源根，输出标准 Asset Metadata（类型 / 尺寸 / 帧 / 动画名 / tags） | 0；输入错误 2 |
| `build_asset_index.py` | 扫描结果 → `.ai/context/asset_index.json`（Generated Cache）；`--check` 判定同步 | 0；陈旧/缺失 1 |
| `query_assets.py` | 关键词 / tag / 路径 / 类型检索（确定性打分，无 LLM） | 0 有结果；1 无结果；2 无索引 |
| `validate_asset.py` | 单资源自洽：存在性 / 类型 / 元数据 / 依赖 | 0 PASS；1 FAIL |
| `check_compatibility.py` | Feature / Entity ↔ Asset 搭配等级 | 0 COMPATIBLE；1 WARNING/INCOMPATIBLE；2 UNKNOWN |
| `bind_assets.py` | Entity 资源角色 → 具体 asset（Feature→Entity→Asset 绑定计划） | 0；`--strict` 且必填缺失 1 |
| `asset_metadata.py` | 元数据层（类型判定 / Godot 资源解析 / 组聚合 / id / 人工确认层合并） | — |
| `tests/` | Asset Registry 回归测试（见下） | 0 PASS；1 FAIL |

Validator 侧：`.ai/tools/validator/check_assets.py`（Asset Validation 阶段，只 CHECK / REPORT），
已接入 `.ai/tools/validator/validate.py` 的 Framework 校验链。

## 契约

- `.ai/context/asset_schema.yaml` —— Asset Metadata
- `.ai/context/asset_binding_schema.yaml` —— Feature / Entity → Asset 绑定
- `.ai/context/asset_manifest_schema.yaml` —— 人工确认层（`.ai/context/asset_manifest.yaml`）

## Source of Truth 与 Generated Data

| 文件 | 性质 | 能否手工维护 |
|---|---|---|
| 资源文件（`Assets/**`） | **Source of Truth** | 是（资源本身由人/美术决定） |
| `.ai/context/asset_manifest.yaml` | 人工确认层（语义覆盖） | 是（只写已确认条目） |
| `.ai/context/asset_index.json` | **Generated Cache** | **否**（`build_asset_index.py` 生成） |
| `.ai/context/asset_bindings/*.yaml` | 绑定计划（生成物） | 否（由 `bind_assets.py` 产出） |

**版本控制策略：** `asset_index.json` 被 `.gitignore` 忽略（不进仓库）。它是
Generated Cache，随时可由 `build_asset_index.py` 重建，不作为 Source of
Truth 提交；`--check` 能区分四种状态（index exists / missing / stale /
synchronized），Consumer（query/bind/check_assets）在索引缺失时给出明确
重建提示而不是失败数据。普通扫描/查询结果不写入 `.ai/memory/DECISIONS.md`：
只有长期架构决策才进 Memory。

## 快速开始

```bash
# 1. 索引资源（资源变动后重跑；--check 可判定是否陈旧）
python .ai/tools/asset_registry/build_asset_index.py
python .ai/tools/asset_registry/build_asset_index.py --check

# 2. 找资源（确定性排序 + 打分理由）
python .ai/tools/asset_registry/query_assets.py "slime attack animation"
python .ai/tools/asset_registry/query_assets.py "hurt" --type audio --explain

# 3. 判断搭配是否合理（不改动任何东西）
python .ai/tools/asset_registry/check_compatibility.py \
    --entity enemy --role move --asset slime_frames

# 4. 解析资源角色 -> 绑定文档
python .ai/tools/asset_registry/bind_assets.py --entity slime_enemy.yaml \
    --out .ai/context/asset_bindings/slime_enemy.yaml

# 5. 生成带资源节点的场景（实例化 + 连接资源，不写行为）
python .ai/tools/scene_composer/scene_composer.py slime_enemy.yaml --bind-assets --tests

# 6. 校验（只报告，不修改项目）
python .ai/tools/validator/check_assets.py
python .ai/tools/validator/validate.py
```

## 分类规则（禁止视觉识别）

资源分类只依据**客观事实**：文件路径、目录结构、文件名 token、扩展名、
Godot 资源类型（`.tres`/`.tscn` 头）、`.import` 旁车事实、既有 metadata、
人工确认层。

```text
Assets/characters/enemy/slime/idle/slime_idle_00.png
    └─ chars/enemy/slime/idle  ⇒ category=enemy, subject=slime, role=idle
```

「这张图看起来像敌人」不是分类依据。不确定的语义留在 `confirmed: false`，
由 `asset_manifest.yaml` 人工确认。

## Binding 语义

- 实体的 `assets.required` / `assets.optional` 声明角色槽位；未声明时按实体角色使用默认槽位
  （enemy：idle/move/attack/hurt；player：idle/run/attack/hurt；外加可选 `*_sfx`）。
- 解析优先级：显式绑定 > SpriteFrames 内含该动画 > animation 组 > texture > audio。
- 主体保护：声明了 `subject` 时不会把别的角色资源（player/enemy/character 类）当成本实体资源，
  而是进入 `missing`（宁可报缺失，不猜）。
- 缺少 SpriteFrames 的动画组会退化为首帧静态 `Sprite2D`，并在绑定里写明 `note`。
- 多个角色指向同一资源时合并为一个场景节点（如 `SlimeAnim`），记录 `roles` 与默认 `animation`；
  播放哪一段属于 Gameplay。
- 兼容性等级与绑定使用同一判定（`check_compatibility.py`）：
  COMPATIBLE 正常；WARNING / UNKNOWN 只告警；INCOMPATIBLE 由 Validator 报 ERROR。

## 测试

```bash
python .ai/tools/asset_registry/tests/test_scan_assets.py    # Test 1/2 + 类型/聚合/人工确认层
python .ai/tools/asset_registry/tests/test_asset_index.py    # Test 6 链路 + Generated Cache 语义
python .ai/tools/asset_registry/tests/test_asset_query.py    # Test 3 + 排序确定性
python .ai/tools/asset_registry/tests/test_asset_binding.py  # Test 4/5 + 绑定/缺失/退化
python .ai/tools/asset_registry/tests/test_check_assets.py   # Validator 阶段（含只读断言）
```

测试全部在临时项目副本上运行（`tests/fixture_project.py` 生成 PNG/WAV/SpriteFrames/TileSet
等真实资源），不修改仓库中的资源与 fixture。

## 与既有资源工具的关系

`.ai/tools/godot-art-assets/scan_assets.py`（v3 Skill 工具）保留为
「原始文件事实 + 人工确认（review/apply）」链路；本 Registry 在其之上提供
Agent 可查询的语义索引与绑定，并**复用**同一套分类词表与人工确认产物
（`.ai/context/asset_manifest.json` 与本目录的 `asset_manifest.yaml` 会合并读取）。
两者不重复实现：Registry 不重写 review 流程，art-assets 不承载绑定与索引。

## 演示资源

`Assets/**` 是 Phase 1.7 的**确定性占位美术**（32x32 纯色帧、正弦波音效 /
2x2 TileSet），由 `tests/fixture_project.py` 生成，用于验证
「索引 → 发现 → 绑定 → 场景 → 运行」全链路。像素内容不是最终美术；
分类语义经 `asset_manifest.yaml` 人工确认。
