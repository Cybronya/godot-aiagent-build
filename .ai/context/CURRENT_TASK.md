# 当前任务

## 目标

MCP 第二轮独立实战：新增「平台密室」场景（往返渡船 + 钥匙 + 钥匙门 + 出口），验证 Agent 通过 MCP 自主完成 Discovery、能力识别、Runtime 观察与问题定位。

## 当前状态

已完成并通过验证：

- 新 Feature `Features/moving_platform/`：AnimatableBody2D 三角波往返 + RideZone 渡载（位移搬运语义）；**非实体渡载**设计（本体不带碰撞，避免推挤对抗；需要实体化时场景级添加）
- `Scenes/PlatformVault.tscn` + `platform_vault.gd`（胶水仅完成呈现/重开）：隔墙带 110px 缺口，渡船沿缺口轴往返（travel=(300,0), period=6）；Key(collect_pickup) → Gate(All,1) → KeyDoor(openable_door)；2 条 connection 直连
- MCP 实录：headless editor + `--mcp-server` 拉起服务；doctor / get_project_info / list_project_scenes / validate_script×2（0 错误）/ run_project（scene_path + allow_window）/ get_runtime_info（/root/PlatformVault, fps 60, 40 节点）/ get_runtime_scene_tree（Ferry/Key/KeyDoor/ConditionGate 全确认）/ stop_project
- 未修改 Framework / MCP / 既有 Feature

关键经验（供后续任务参考）：

- top-down 渡载与实心墙对抗不兼容：实体甲板扫过墙区会把等待的玩家挤飞；改为「非实体渡载 + 隔墙带缺口」几何自洽
- 测试对比逻辑缺陷模式：循环内每帧重置基线导致只能测出单帧位移（~2px），阈值判断永远失败；基线必须设在循环外
- 类型化函数形参不能接收 freed 对象（第二次确认）
- 编辑器会话会自动重存打开过的场景（main.tscn 曾被重存并丢失 Player2 节点），进程清理后需 git diff 检查并 checkout 恢复
- run_project 会写 MCPRuntimeProbe autoload 到 project.godot，Runtime 检查后需清理

验证结果：

- moving_platform 自身验证（往返/渡载/下车）：PASS
- Platform Vault 集成验证（平台位移/渡运/钥匙消失/门阻挡与解除/完成/重置）：PASS
- 全量回归：22/22 PASS；五场景启动 0 错误；Validator PASS

## 修改文件

- `Features/moving_platform/`（新增 4 文件）
- `Scenes/PlatformVault.tscn`、`Scenes/platform_vault.gd`（新增）
- `Tests/test_platform_vault.gd`（新增）
- `.ai/context/CURRENT_TASK.md`（本文件）

## 下一步

无阻塞事项。成果未提交（等待用户指示）。
