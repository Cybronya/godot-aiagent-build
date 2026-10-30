# save_game

> 状态：**正式 Feature**（自 MizGodotTools save_manager 抽象重写，自测通过）。

## 职责

槽位存档：把「玩家 + 场景静态节点 + 运行时实例」三类状态快照成 JSON 文件，
恢复时清场回放。只拥有快照的收集、落盘与应用；触发节奏（快捷键/自动存档点）
与跨场景切换编排不属于本组件。

## 存档协议

任意节点实现两个方法即可参与存档：

```gdscript
func get_save_data() -> Dictionary: ...   # 保存时收集
func load_save_data(data: Dictionary) -> void: ...  # 恢复时回填
```

配合组约定使用：

| 组 | 含义 | 记账方式 |
|---|---|---|
| `player` | 全局玩家实体（唯一） | 存入 `player_data` |
| `serializable` | 场景静态节点（门、开关） | `node_path` 记账 |
| `instanced` | 运行时实例（掉落物、弹坑） | 数据自带 `instance_uid` 字段（指向场景路径），恢复时重建 |

## 接口速览

`save_to_slot(name)` / `load_from_slot(name)`（核心）、
`autosave` / `quicksave` / `load_autosave` / `load_quicksave`（固定槽位）、
`get_slot_list()`（按时间新→旧）、`get_last_slot()`、
`add_deleted_node_path(path)`（拾取/销毁记账）、
信号 `game_saved` / `game_loaded`。

## 与来源片段的差异（抽象要点）

1. **剥除框架耦合**：原版是 autoload Global + `_process` 快捷键轮询 +
   LevelManager/ScreenFader 依赖；改为普通 Node 组件，触发与场景切换
   全部交还组合层（符合项目 Scene Glue 边界）。
2. **数据类合并**：原 GameSaveData + LevelSaveData 两类合并为单个
   `SaveData`（RefCounted），per-scene 结构改为普通字典字段。
3. **场景切换职责剥离**：原版 load 内嵌 change_scene/reload 逻辑；
   本组件只应用快照到当前树。跨场景恢复：组合层先切场景，再 `load_from_slot`。
4. **槽位名校验**：新增非法字符防护与 `get_last_slot` 失效自愈（文件被删返回空串）。

## 复用方式

```gdscript
var saver := preload("res://Features/save_game/SaveGame.tscn").instantiate()
add_child(saver)
saver.save_to_slot("slot1")
saver.load_from_slot("slot1")
```

来源片段许可证：MIT（Miziziziz/MizGodotTools，对外发布需附署名）。
