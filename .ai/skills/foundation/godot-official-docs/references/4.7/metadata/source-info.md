# Source Info — Godot 4.7 Official Docs

```text
Godot Version: 4.7
Repository:    godotengine/godot-docs
Branch:        4.7
Commit:        unknown（ZIP 下载，无法确认，不伪造）
Source Path:   .ai/skills/godot-official-docs_sources/4.7/
Generated At:  2026-10-07
```

## Source of Truth

```text
.ai/skills/godot-official-docs_sources/4.7/
```

- 只读：禁止删除、移动、重命名、修改或在其中添加生成文件
- 本 Skill 的 references/ 只保存导航与索引（几百 KB），不复制文档正文
- 所有文档正文一律通过统一相对路径读取（基准目录 `references/4.7/`）：

```text
../../../../godot-official-docs_sources/4.7/<path>
```

## Source 顶层结构（与本文档对应关系）

| 上游目录 | 用途 |
|---|---|
| `classes/` | Class Reference（`class_<name>.rst`，1078 个类） |
| `getting_started/` | 入门：introduction、step_by_step、first_2d_game、first_3d_game |
| `tutorials/` | 主题教程：2d、3d、physics、ui、inputs、io、shaders、networking… |
| `tutorials/migrating/` | 版本迁移：upgrading_to_godot_4.1 … 4.7 |
| `engine_details/` | 引擎细节：architecture、editor、engine_api、file_formats |

注意：4.7 上游没有独立的 manual 顶层目录；手册类内容分布在 getting_started/ 与 tutorials/ 中。
