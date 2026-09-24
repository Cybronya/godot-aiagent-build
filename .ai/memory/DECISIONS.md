# Decisions

本文件是本项目 Architecture Decision 的唯一物理归宿。

格式：

日期：

状态：

决定：

原因：

影响：

supersedes：

---

## AD-001: 建立顶层 `Features/` 目录，可复用 Feature 自包含管理

- 状态：accepted
- 日期：2026-09-25
- supersedes：null

### 决定

- 新增顶层 `Features/` 目录（PascalCase，符合 folder-structure 规则），每个 Feature 一个子目录，场景、脚本、测试自包含。
- 首个 Feature：`Features/player_movement/`（`Player.tscn` + `player_controller.gd` + `test_player_movement.gd` + `README.md`）。
- 主场景 `Scenes/main.tscn` 保留在 `Scenes/`：它是游戏侧组合层，负责实例化 Feature，不属于可复用单元。

### 原因

- 已验证的移动功能需要沉淀为可复用单元；Feature 内聚（场景 + 逻辑 + 验证 + 说明）使整个目录可被其他场景或项目直接复用。
- godot-project-architecture 的架构模型中 Feature 是独立组织层级，不应散落在分类目录（Scripts/、Scenes/）中。

### 影响

- 后续新 Feature 放入 `Features/<feature_name>/`。
- 引用 Feature 内资源使用 `res://Features/<feature_name>/...` 路径。
- 同步更新了 development-standard 的 folder-structure.md，补充 `Features/` 目录约定。

### 验证

- 迁移后资源导入、运行时四向移动测试、主场景启动全部通过，游戏功能不变。

---

## AD-002: 实体能力以组件节点 Feature 复用，实体场景只做组合

- 状态：accepted
- 日期：2026-09-25
- supersedes：null

### 决定

- 跨实体能力（首个：health）实现为独立组件 Feature（`Features/<name>/`），根节点为普通 Node，通过信号对外暴露事件，不依赖宿主节点类型。
- 实体场景（`Scenes/Player.tscn`、`Player2.tscn`）通过实例化 Feature 场景组合能力，差异用导出属性覆写表达；实体不继承、不复制能力实现。

### 原因

- 移动天然属于 CharacterBody2D，而生命值与节点类型正交（敌人、可破坏物也需要）；若绑死 CharacterBody2D，复用面被锁死在角色类节点。
- 信号是 Godot 的解耦事件接口，满足「死亡时其他逻辑可响应」且组件无需知道订阅方。

### 影响

- 后续实体能力优先按「组件 Feature + 场景组合」实现，不建立实体基类继承链。
- 能力事件一律通过信号暴露；宿主死亡后的表现由订阅方决定。

### 验证

- Health 组件验证、Player/Player2 双角色集成验证、移动回归、主场景启动全部通过。
