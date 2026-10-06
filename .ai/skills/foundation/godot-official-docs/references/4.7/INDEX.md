# Godot 4.7 Official Docs Index — Agent Navigation Map

Skill 版本目录：`references/4.7/`
Source of Truth（只读）：`../../../../godot-official-docs_sources/4.7/`

## Quick Routing

| User intent | Read |
|---|---|
| Character movement | `routing/intents.md` → `CharacterBody3D` |
| Input / WASD | `routing/keywords.md` → `Input` / `InputMap` |
| UI / Button | `routing/keywords.md` → `Button` → `BaseButton` |
| Scene switching | `routing/topics.md` → `SceneTree` |
| File I/O / JSON | `routing/topics.md` → `FileAccess` / `JSON` |
| Multiplayer | `routing/topics.md` → `MultiplayerAPI` |
| Shader | `routing/topics.md` → `Shader` / `ShaderMaterial` |
| Version migration | `routing/topics.md` → Migration |

## Lookup Entry Points

- **API question?** → `api/INDEX.md`（常用类 + 继承链规则）
- **Exact class?** → `api/classes.md`（全量 1078 类，Generated）
- **Browse by domain?** → `api/categories.md`
- **Conceptual doc?** → `routing/topics.md`
- **Natural language?** → `routing/keywords.md`
- **Task intent?** → `routing/intents.md`

## Source 信息

见 `metadata/source-info.md`：

```text
godotengine/godot-docs @ 4.7，commit unknown
Source Path: .ai/skills/godot-official-docs_sources/4.7/
```

## Read-Source Rule（重要）

不要搜索整个 Source。先经 routing / api index 定位到具体文件，再读取：

```text
../../../../godot-official-docs_sources/4.7/<path>
```

Skill 目录（本目录）只有导航与索引（< 1MB），不包含文档正文。

## 版本隔离

本目录仅含 Godot 4.7。禁止混入 3.x / 4.6 / master；版本不明时先查项目 `project.godot`，无法判断则请求确认或声明使用 4.7 reference。

## 更新 / 重建

```bash
python .ai/skills/foundation/godot-official-docs/tools/update_docs.py --from-sources --version 4.7
```
