# Script Template

```gdscript
class_name NewComponent
extends Node
## 一句话说明组件职责。
##
## 详细描述、使用示例、注意事项。
signal state_changed(new_state: String)

const MAX_COUNT = 10

@export var display_name := ""

var _count := 0


func _ready() -> void:
	_setup()


func _setup() -> void:
	pass
```

规则（依据 Godot 4.7 官方 GDScript 风格指南）：

- 声明顺序：`@tool` → `class_name` → `extends` → `##` 文档注释 → `signal` → `enum` → `const` → 静态变量 → `@export` 变量 → 普通变量 → `@onready` 变量 → `_init`/`_ready` 等虚方法 → 普通方法（public 在前，private 在后）→ 内部类
- `class_name` 写在 `extends` 之前，声明区连续排列，函数定义之间用两个空行分隔
- 每个类和公开方法用 `##` 文档注释说明用途
- 类型标注：类型与赋值在同一行时优先用 `:=` 推断；类型有歧义（如 `var health: int = 0`、`get_node` 返回值）才显式标注；函数一律写返回类型 `-> void`
- 信号按事件命名（过去式 snake_case），带参数名与类型，不要用裸 `changed` 这类泛化名
- 私有成员用下划线前缀（`_count`、`_setup`）
- 缩进使用 Tab（Godot 默认）
