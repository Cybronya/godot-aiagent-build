---
name: godot-art-assets
version: 3.0
description: Godot project art asset organization, metadata, scanning, review, validation, and safe organization skill.
---

# Godot Art Assets Skill v3

## 1. Purpose

本 Skill 用于帮助 AI Agent 管理 Godot 项目中的艺术资源（Art Assets）。

目标：

1. 保持稳定、可预测的资源目录。
2. 保持统一文件命名。
3. 为资源建立稳定的语义 ID 和 metadata。
4. 自动发现新增、修改、删除和重复资源。
5. 不进行视觉识别；语义判断通过规则 + 人工确认完成。
6. 在移动、重命名或删除资源前保护 Godot 引用。
7. 让 Agent 能够安全地初始化、检查、整理和维护资源库。

---

## 2. Project Layout

推荐：

```text
MyGame/
├── project.godot
├── README.md
├── assets/
│   ├── characters/
│   ├── environments/
│   ├── tilesets/
│   ├── backgrounds/
│   ├── props/
│   ├── items/
│   ├── vfx/
│   ├── ui/
│   ├── portraits/
│   └── fonts/
├── scenes/
├── scripts/
└── .ai/
    ├── skills/
    │   └── godot-art-assets/
    ├── tools/
    │   └── godot-art-assets/
    └── context/
        ├── asset_manifest.json
        └── asset_reviews/
```

如果标准目录不存在，优先运行：

```bash
python .ai/tools/godot-art-assets/scan_assets.py init
```

---

## 3. Tool Commands

```bash
python .ai/tools/godot-art-assets/scan_assets.py init
python .ai/tools/godot-art-assets/scan_assets.py scan
python .ai/tools/godot-art-assets/scan_assets.py review
python .ai/tools/godot-art-assets/scan_assets.py apply
python .ai/tools/godot-art-assets/scan_assets.py sync
python .ai/tools/godot-art-assets/scan_assets.py check
python .ai/tools/godot-art-assets/scan_assets.py organize
```

### init

创建缺失的标准 Art Asset 目录。

默认不会删除已有目录。

### scan

扫描 `assets/`，收集：

- relative path
- filename
- extension
- size_bytes
- modified_at
- sha256
- width
- height
- path_hints
- filename_hints

并比较 manifest，发现：

- new
- changed
- deleted
- unchanged

### review

为需要人工确认的资源生成 `.review.json`。

### apply

读取人工确认结果并更新 manifest。

### sync

执行扫描 + 生成 review。

### check

检查：

- 标准目录
- 文件命名
- 重复资源
- manifest 状态
- pending review
- 动画帧连续性
- 明显非法路径

### organize

仅整理高置信度、规则明确的资源。

不确定资源必须进入 pending，而不是强行分类。

---

## 4. Scanner Is Not Vision

这是本 Skill 的硬规则。

Scanner 不理解图片内容，不进行：

- 图像分类
- OCR
- 角色识别
- 场景识别
- 风格识别
- 自动视觉语义判断

Scanner 可以根据：

- 路径
- 文件名
- 扩展名
- 文件尺寸
- hash

产生 `path_hints` / `filename_hints`。

这些是 hints，不是最终语义。

---

## 5. Semantic Confirmation

最终语义字段由人确认：

```json
{
  "id": "character_goblin",
  "type": "character",
  "category": "enemy",
  "tags": ["goblin", "attack"],
  "status": "candidate",
  "character": "goblin",
  "action": "attack",
  "direction": null,
  "frame": 0,
  "description": "Goblin attack frame",
  "source": null,
  "notes": null
}
```

最少要求：

- id
- type
- category
- status

---

## 6. Stable IDs

路径不是资源的稳定身份。

例如：

```text
characters/enemies/goblin/goblin_attack_00.png
```

可以拥有：

```text
character_goblin
```

如果以后路径改变，ID 尽量保持不变。

推荐：

```text
character_player
character_goblin
item_sword_iron
prop_forest_tree_01
vfx_fireball_hit
ui_inventory_slot
```

---

## 7. Status

允许：

```text
draft
candidate
approved
deprecated
archived
```

不要把 `final`、`new`、`old` 当作长期状态。

---

## 8. Naming

统一使用：

```text
lowercase_snake_case
```

避免：

```text
Final.png
NewPlayer.png
image1.png
test.png
player_final2.png
```

动画推荐：

```text
[object]_[action]_[direction]_[frame].png
```

例如：

```text
player_walk_down_00.png
player_walk_down_01.png
player_walk_down_02.png
```

帧号固定宽度，从 `00` 开始。

---

## 9. Classification

标准顶层类型：

```text
character
environment
tileset
background
prop
item
vfx
ui
portrait
font
```

分类优先参考：

1. 已确认 metadata
2. 已知路径
3. 文件名规则
4. 人工 review

不能仅凭文件名猜测就覆盖已确认 metadata。

---

## 10. Folder Rules

推荐：

```text
assets/characters/
assets/environments/
assets/tilesets/
assets/backgrounds/
assets/props/
assets/items/
assets/vfx/
assets/ui/
assets/portraits/
assets/fonts/
```

可以进一步细分：

```text
assets/characters/player/
assets/characters/enemies/goblin/
assets/props/forest/
assets/vfx/fireball/
assets/ui/inventory/
```

但不要为了“看起来整齐”产生过度嵌套。

---

## 11. Automatic Organization Rules

Agent 可以自动执行：

- 创建缺失标准目录
- 扫描资源
- 生成 hints
- 更新 scanner facts
- 生成 review
- 对规则明确的新增资源进行组织

Agent 不应自动执行：

- 删除未知资源
- 覆盖已确认语义
- 猜测不确定资源类型
- 大规模移动已有 Godot 资源而不检查引用
- 任意重命名已经被场景、脚本或资源引用的文件

---

## 12. Godot Safety

在移动 / 重命名 / 删除已有资源之前：

1. 查找 Godot 场景和资源引用。
2. 检查 `.tscn`、`.tres`、`.godot` 相关导入/引用情况。
3. 检查脚本中的路径字符串。
4. 执行变更。
5. 再次扫描。
6. 运行项目或至少检查相关场景。

优先采用“新增规范目录 + 明确迁移计划”，而不是盲目批量移动。

---

## 13. New / Changed / Deleted

新文件：

```text
path 不在 manifest
```

修改文件：

```text
path 相同
sha256 不同
```

删除文件：

```text
manifest 有
scan 不再发现
```

因此，即使：

```text
player.png
```

被替换成另一个内容完全不同的 `player.png`，也会被检测为 changed。

---

## 14. Manifest

Manifest 是项目级资产索引，不是图片本身。

推荐结构：

```json
{
  "schema_version": 3,
  "project": "MyGame",
  "assets": [],
  "pending": []
}
```

每个 asset 分为：

```text
auto
human
```

`auto` 是 Scanner 管理的事实。

`human` 是人工确认的语义。

不要让 Agent 手工改写 Scanner facts。

---

## 15. Review Workflow

```text
assets/
   ↓
scan
   ↓
new / changed / deleted
   ↓
pending
   ↓
review
   ↓
human edits asset.human
   ↓
apply
   ↓
asset_manifest.json
   ↓
check
```

如果语义不确定：

```text
不要猜
↓
pending
↓
等待人工确认
```

---

## 16. Agent Decision Policy

处理 Art Asset 时：

### Step 1
读取本 Skill。

### Step 2
读取相关 reference：

- folder_structure.md
- naming.md
- metadata.md
- workflow.md
- godot_safety.md
- classification.md
- animation.md
- organization.md

### Step 3
读取 manifest。

### Step 4
运行 scan/check。

### Step 5
对于新增资源：

- 能确定 → 按规则组织
- 不能确定 → pending/review

### Step 6
涉及已有 Godot 引用时先执行安全检查。

### Step 7
变更后再次 scan/check。

---

## 17. Do Not Guess

如果一个文件：

```text
assets/mystery_01.png
```

无法可靠判断是：

- prop
- item
- character
- background

不要把它强行放入某一类。

应保持：

```text
pending
```

并等待人工确认。

---

## 18. Recommended Agent Operations

Agent 可以自然语言执行：

```text
初始化艺术资源目录
扫描所有艺术资源
检查资源规范
找出新增资源
找出重复资源
整理明显符合规范的新资源
生成待确认资源列表
更新资源 manifest
检查某个角色的动画帧
检查命名问题
```

---

## 19. Definition of Done

Art Asset 管理任务完成时：

- 标准目录存在
- 文件路径符合规则
- 命名符合规则
- 新资源已扫描
- changed/deleted 已发现
- 不确定资源进入 pending
- manifest 可用
- review 已应用的资源有稳定 ID
- 移动/删除操作经过 Godot 安全检查
- 最终重新 scan/check

---

## 20. Future Extensions

未来可以增加：

- Godot EditorPlugin
- `.import` / import settings 检查
- SpriteFrames 自动检查
- Atlas / sprite sheet metadata
- 动画组一致性检查
- 资源使用频率分析
- 未引用资源报告
- AI Agent 与 Godot Editor MCP/插件联动

这些属于扩展，不应破坏当前的文件、manifest 和 review 规范。
