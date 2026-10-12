extends Node2D
## Runtime fixture: 修复节点路径后仍会暴露另一个运行期错误（用于回滚路径验证）。


func _ready() -> void:
	var health = get_node("Helth")
	health.do_something()
