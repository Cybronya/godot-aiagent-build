# Godot Folder Structure Rules

本项目顶层目录采用 PascalCase（与项目现状一致，如 Scenes/、addons/）：

```
project/
├── Scenes/
├── Features/
├── Scripts/
├── Assets/
├── Resources/
├── Systems/
├── UI/
├── Audio/
└── Data/
```

规则：

- 项目文件必须分类管理，禁止散落在根目录
- 例外：`.ai/`、`addons/` 保持既有名称（.ai 为 AI 框架约定，addons/ 为 Godot 引擎生成）
- 可复用 Feature 统一放在 `Features/<feature_name>/`，场景、脚本与测试自包含（见 `.ai/memory/DECISIONS.md` AD-001）
- 艺术资源目录由 godot-art-assets Skill 管理，遵循其规范（`assets/` 下小写子目录），两套体系以 `.ai/tools/godot-art-assets/scan_assets.py` 的行为为准

冲突处理：

- 保留已有目录名称，不强制重命名（参考本项目已有的 `Scenes/`）
- 新增顶层目录遵循 PascalCase
- 如需迁移已有目录，先按 Godot Safety 检查引用，再提交用户确认
