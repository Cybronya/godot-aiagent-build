# Skill Identity

## Skill ID

asset-discovery

## Skill Name

Asset Discovery

## Version

1.0

## Category

systems

# Registry Metadata

本章节是本 Skill 的 Canonical Metadata。
Registry 仅索引本 Skill，不重复维护这些字段。

## Load Policy

conditional

## Dependencies

### Required

[]

### Related

[]

## Ownership

负责「Requirement / Entity Blueprint → Candidate Assets → Compatibility → Asset Binding」
的资源侧链路：发现、筛选、推荐、绑定资源，并给出缺失清单。

不负责：修改 / 移动 / 重命名资源文件，不负责视觉识别，不负责场景生成
（scene-composer），不负责绑定合法性判定（validator/check_assets.py）。

# Description

在 Asset Registry（`.ai/context/asset_index.json`，Generated Cache）上完成资源发现与绑定：

- 扫描并索引项目资源（`.ai/tools/asset_registry/scan_assets.py` /
  `build_asset_index.py`）
- 按关键词 / tag / 路径 / 类型检索候选（`query_assets.py`）
- 判定 Feature / Entity 与资源的搭配等级（`check_compatibility.py`）
- 把实体的资源角色解析为具体资源（`bind_assets.py` → `.ai/context/asset_binding_schema.yaml`）
- 把绑定交给 Scene Composer 实例化为资源节点（AnimatedSprite2D / Sprite2D /
  AudioStreamPlayer）

资源分类只依据客观事实：文件路径、目录结构、文件名、扩展名、Godot 资源类型、
`.import` 旁车、既有 metadata、人工确认层（`.ai/context/asset_manifest.yaml`）。

# Purpose

让「生成一个使用项目现有资源的实体」成为可复现的链路，而不是人工翻目录：

    Requirement → Asset Query → Candidate Assets → Compatibility → Asset Binding
                                              → Entity → Scene Composer

Asset Registry 是 Query / Index，不是 Runtime Manager。

# Responsibility

## 负责

- 维护 Generated Cache（asset_index.json）与扫描事实的一致性（--check 可判定陈旧）。
- 回答「项目里有没有能用的资源」，并给出确定性排序与理由。
- 解析实体资源角色（idle / move / attack / hurt / *_sfx）→ 具体 asset id。
- 明确区分 Agent 推断（confirmed: false）与人工确认（confirmed: true）。
- 资源缺失时输出 missing 清单，交由 Validator 决定 WARNING / ERROR。

## 不负责

- 不移动、不重命名、不删除、不改写任何资源文件（只读资源）。
- 不做视觉识别 / 图像分类 / 用图片内容猜语义。
- 不硬编码资源路径进 Feature；Feature 只声明能力，资源由 Entity / Scene 层绑定。
- 不创建 AssetManager / ResourceManager / 全局单例。
- 不生成场景（scene-composer）也不修改项目（Validator 只 CHECK / REPORT）。

# Trigger Conditions

- 任务涉及图片、Sprite、SpriteFrames、Animation、Tileset、Audio、Texture、Font、
  Shader、Godot Resource，或「使用项目现有美术/音频资源」。
- 需求要求某个实体「看起来/听起来像」什么（需要从既有资源中选）。
- Entity Blueprint 需要补齐资源槽位，或 Scene Composer 需要资源节点。
- 资源缺失、绑定可疑、索引与实际磁盘不一致需要核对。

# Input Contract

- Requirement 文本，或 Entity Blueprint（`entity:` / `features:`），
  或 Gameplay Blueprint（`entities:`）。
- 可选：Entity Blueprint 的 `assets:` 节（`subject` / `required` / `optional` /
  `bindings:` 显式绑定）。
- 资源根目录（默认按存在性扫描 `Assets` / `assets` / `resources` / `Resources` /
  `Audio` / `Textures` / `Sprites` / `Animations` / `Tilesets`）。

# Workflow

```text
Requirement / Entity Blueprint
        ↓
Scan + Index（scan_assets.py → build_asset_index.py → .ai/context/asset_index.json）
        ↓
Asset Query（query_assets.py；keyword / tag / path / type，无 LLM）
        ↓
Candidate Assets（打分排序 + reasons）
        ↓
Compatibility Check（check_compatibility.py：COMPATIBLE / WARNING / INCOMPATIBLE / UNKNOWN）
        ↓
Asset Selection（bind_assets.py 解析角色 → asset）
        ↓
Asset Binding（.ai/context/asset_bindings/<id>.yaml）
        ↓
Scene Composer（scene_composer.py --bind-assets → 资源节点）
        ↓
Asset Validation（validator/check_assets.py：路径 / 类型 / 绑定 / 缺失）
```

标准流程：

1. `python .ai/tools/asset_registry/build_asset_index.py`（首次或资源变动后）。
2. `python .ai/tools/asset_registry/query_assets.py "slime attack animation"` 找候选。
3. 需要判断搭配是否合理 → `check_compatibility.py --entity enemy --asset slime_attack`。
4. 生成绑定 → `bind_assets.py --entity <blueprint.yaml> --out <binding.yaml>`，
   或直接 `scene_composer.py <blueprint.yaml> --bind-assets`。
5. 校验 → `python .ai/tools/validator/check_assets.py`。

# Output Contract

- Asset Metadata / Asset Scan Result（textures / animations / audio / ... 计数）。
- `.ai/context/asset_index.json`（Generated Cache，禁止手工维护）。
- Asset Query 结果（id / path / type / tags / score / reasons）。
- Compatibility 等级（COMPATIBLE / WARNING / INCOMPATIBLE / UNKNOWN + 理由）。
- `.ai/context/asset_bindings/<entity>.yaml`（按 asset_binding_schema.yaml）。
- missing / optional_missing 清单（禁止编造资源）。

# Rules

必须：

- 分类只依据客观事实（路径 / 文件名 / 扩展名 / Godot 资源类型 / .import / 人工确认）。
- 资源缺失必须显式列出，禁止编造 asset id 或 res:// 路径。
- Asset Binding 是计划层（Entity → Asset）；Feature 不得硬编码资源路径。
- 兼容性等级复用 `check_compatibility.py`（单一事实来源）：WARNING / UNKNOWN 只告警，
  INCOMPATIBLE 由 Validator 报 ERROR；不把低兼容性一律当错误。
- 资源只读：任何整理/重命名都必须由人工确认后另行执行（不属本 Skill 自动范围）。

禁止：

- 引入视觉识别 / LLM 猜测作为分类依据。
- 引入 AssetManager / ResourceManager / 全局单例。
- 让 Agent 手工维护 asset_index.json（它是生成物）。
- 把普通扫描结果写入 `.ai/memory/DECISIONS.md`。
- 用 Asset 系统承载 Gameplay State（状态仍归 Feature）。

# Validation

## Validation Method

- `build_asset_index.py --check`：索引与磁盘是否同步（陈旧 = 退出码 1）。
- `validate_asset.py <asset>`：单资源自洽（存在性 / 类型 / 元数据 / 依赖）。
- `check_compatibility.py`：单对 (Feature|Entity, Asset) 等级。
- `validator/check_assets.py`：索引 / 绑定 / 场景资源引用 / 缺失清单。
- `scene_composer.py --bind-assets` 生成的 .tscn 经 Godot 实际运行验证。

## Success Criteria

- Asset Schema 校验通过；索引可重建且 `--check` 同步。
- 绑定每个必填角色要么解析到真实存在的资源，要么出现在 missing。
- 生成的场景资源节点指向可加载资源（Godot 运行无 load 错误）。
- 资源缺失/类型不符时 Validator 报 WARNING 或 ERROR，且不修改项目。

## Status Update

- PASS：索引同步、绑定齐备、Validator 零错误。
- WARNING：可选角色缺失、元数据未人工确认、低兼容性（WARNING 级绑定）。
- FAIL：必填角色缺失（蓝图显式声明 required 时）、资源路径不存在、类型不符。

# References

- .ai/context/asset_schema.yaml —— Asset Metadata 契约
- .ai/context/asset_binding_schema.yaml —— Feature/Entity → Asset 绑定契约
- .ai/context/asset_manifest_schema.yaml —— 人工确认层契约
- .ai/tools/asset_registry/README.md —— 工具与流程说明
- .ai/skills/engineering/godot-art-assets/SKILL.md —— 资源规范与人工确认流程
- .ai/skills/systems/scene-composer/SKILL.md —— 资源节点实例化（下游）

# Failure Handling

- 无资源根目录 → 报告「未找到资源目录」，不得虚构资源；改为请求人工提供资源或降级为占位。
- 索引为空/陈旧 → 先 `build_asset_index.py`，再重跑查询；禁止直接读磁盘猜资源。
- 必填角色缺失 → 输出 missing，交给人工或 Feature 层决策（不自动生成美术）。
- 绑定与实体角色冲突（如 player 资源配 enemy）→ INCOMPATIBLE，
  由 Validator 报错；不得静默替换为低兼容资源。
- 资源类型与期望节点不符 → 记 WARNING 并说明（如 animation 组无 SpriteFrames，
  退化为首帧静态贴图），不得伪造 SpriteFrames。

# Permission Model

允许执行：

- 运行 asset_registry 全部工具（扫描 / 建索引 / 查询 / 校验 / 绑定）。
- 写入 `.ai/context/asset_index.json` 与 `.ai/context/asset_bindings/`（生成物）。
- 写入 `.ai/context/asset_manifest.yaml` 中**人工已确认**的条目（需人工提供语义）。

需要确认：

- 移动 / 重命名 / 删除资源文件，或改写 Godot 引用。
- 覆盖已存在的人工维护 manifest 条目。
- 引入新的资源分类目录约定。

# Notes

- asset_index.json 是 Generated Cache，永远可以从磁盘 + manifest 重建。
- 既有 `.ai/tools/godot-art-assets/scan_assets.py` 保留为「原始文件事实 + 人工确认」链路；
  本 Skill 的 Registry 在其之上提供 Agent 可查询的语义索引与绑定，两者不重复实现。
- 资源缺失不是「Agent 该生成美术」的理由：缺资源应显式暴露。
