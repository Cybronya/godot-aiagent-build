# 当前任务

## 目标

MCP 工具链实战验证：新增「钥匙与宝箱」独立场景（三把钥匙任意顺序收集 → 宝箱打开 → 进入宝箱完成），必须真实使用项目 godot_mcp 插件的工具完成 Discovery/检查/Runtime 检查。

## 当前状态

已完成并通过验证：

- 新 Feature `Features/collect_pickup/`：接触拾取（收集广播 + 自移除 + 一次性幂等）；`collected(value, pickup_id)` 与 `ConditionGate.set_condition(value, id)` 签名完全一致，场景直连零 binds
- `Scenes/ChestVault.tscn` + `chest_vault.gd`（胶水仅完成呈现/重开）：三把 CollectPickup 钥匙 → ConditionGate(All, 3) → Chest（openable_door 旋转 90° 参数化变体）→ CompleteZone；4 条 connection 直连，零胶水接线
- 未修改 Framework / MCP / 既有 Feature

MCP 实录（全部真实调用，curl → godot_mcp CLI API）：

- 无编辑器时 9080 无监听；headless editor + `-- --mcp-server` 参数强制启动成功（持久化设置 auto_start=false 会覆盖 plugin.cfg 的 true）
- doctor / catalog（155 工具）/ get_project_info / list_project_scenes / list_project_input_actions / get_scene_structure 均成功
- run_project 需 arguments.allow_window=true（Vibe Coding 防护）；get_runtime_info/scene_tree 需 envelope 级 allow_open_world=true
- get_runtime_info 实证：current_scene=/root/ChestVault，fps 145，37 节点；scene_tree 确认 3 把钥匙 + ConditionGate；stop_project 正常
- get_runtime_node_properties 对 StaticBody 路径仍 404（已知边界，用 scene_tree 覆盖）

关键经验：

- MCP 参数两层：arguments（工具参数，含 allow_window）+ envelope（allow_open_world/limit 等 API 级控制）
- 类型化函数形参不能接收 freed 对象（协程中断挂起）；需等待释放的判定用无类型形参 + is_instance_valid
- run_project 会临时写入 MCPRuntimeProbe autoload 到 project.godot（引擎自动行为），提交前需剥离

验证结果：20/20 测试 PASS；四场景启动 0 错误；Validator PASS。

## 下一步

无阻塞事项。
