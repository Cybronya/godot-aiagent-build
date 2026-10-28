# patrol_movement

巡逻移动组件：沿预设路径点循环（或往返）行进。与 `player_movement`（读输入）
和 `chase_movement`（追目标）互为镜像——不读输入、不追目标，只沿 waypoints 走，
移动职责单一。

## 来源（片段 → Feature）

抽象自代码库参考片段（教学示例，未直接拷贝）：

- 片段：`.ai/skills/foundation/godot-gdscript/code_library/references/movement/gdquest-demos__godot-open-rpg__src__field__gamepieces__controllers__path_loop_ai_controller.gd`
  （[gdquest-demos/godot-open-rpg](https://github.com/gdquest-demos/godot-open-rpg)，MIT，star 3028）——沿路径点循环行进 + 循环间等待的思路

抽象取舍：去掉 Gameboard 寻路、Line2D 路径与 Gamepiece 框架依赖，改为导出
**本地偏移点数组**——实体摆好后填几个偏移即工作；等待逻辑从 Timer 简化为
`loop`/往返两种模式（等待需求可由组合层在 waypoint_reached 后处理）。

## 复用方式

1. 场景中把 `PatrolMovement.tscn` 设为巡逻敌人的根（根脚本模式，与
   ChaseMovement 相同），加 CollisionShape2D。
2. Inspector 填 `points`（相对初始位置的偏移，如 (120,0)、(120,80)）。
3. `loop=true` 绕圈巡逻；`false` 往返折返。
4. `waypoint_reached(index)` 可挂转向动画、脚印、声音；驻留状态不重复广播。

## 契约要点

- **根脚本模式**：与 `chase_movement` / `player_movement` 互斥（同为
  CharacterBody2D 根脚本，同一实体只能挂其一；巡逻→追击的切换由组合层做）。
- **步长钳制**：抵达判定带步长上限，高速下贴点而不越点。
- **本地偏移**：points 相对实体初始位置，拖动实体整条路径跟随。
- points 为空时静止不报错。

## 测试

```bash
godot --headless --path . -s res://Features/patrol_movement/test_patrol_movement.gd
```

覆盖：空路径静止、循环绕回（完整两圈）、往返端点折返、waypoint_reached
信号与去重、单点驻留。等待策略为条件轮询（信号计数），不依赖固定帧数。
