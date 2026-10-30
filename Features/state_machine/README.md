# state_machine

> 状态：**正式 Feature**（自 escoria patterns/state_machine 抽象重写，自测通过）。

## 职责

通用有限状态机：把「当前状态是什么、如何切换」从业务代码里剥离出来。
子节点即状态（继承 `StateNode`），节点名即状态名；状态机把物理帧与输入转发给
当前状态，切换由状态自身的 `finished` 信号或外部 `transition_to()` 驱动。

## 接口速览

| 成员 | 说明 |
|---|---|
| `start(first_state)` | 显式启动（`autostart=false` 时） |
| `set_active(value)` | 开关；关闭 exit 当前状态并停止转发，重开重新 enter |
| `transition_to(name)` | 切换；`"previous"` 回退历史；未知名报错保持；同状态幂等 |
| `state_changed(state)` | 切换广播 |
| `has_state(name)` / `is_active()` | 查询 |

exports：`start_state_name`（起始状态）、`autostart`（默认 true）。

## 与来源片段的差异（抽象要点）

1. **剥除框架耦合**：原版 `escoria.logger` 全部替换为 `push_error`；去掉
   animation_finished 转发链（动画订阅属于 Scene Glue）。
2. **修复回退越界**：原版 `previous` 弹栈后可能取空栈首；改为显式
   `_history` 历史栈，耗尽时安全保持当前状态。
3. **注册方式简化**：原版需手工维护 `states_map`；现子节点自动注册、
   节点名即状态名，无第二份映射可失步。
4. **开关语义明确**：`set_active(false)` 不再清空状态（原版清栈置 null），
   而是退出当前状态；重新开启重新 enter，恢复现场。

## 复用方式

```gdscript
var machine := preload("res://Features/state_machine/StateMachine.tscn").instantiate()
machine.start_state_name = "patrol"
entity.add_child(machine)
machine.add_child(preload("res://states/patrol.gd").new())  # patrol.gd extends StateNode
machine.add_child(preload("res://states/chase.gd").new())
# patrol.gd 内部：finished.emit("chase") 请求切换
```

来源片段许可证：MIT（godot-escoria/escoria-demo-game，对外发布需附署名）。
