extends Node2D
## Runtime fixture: 两个硬编码节点路径都有拼写错误（用于多轮修复验证）。


func _ready() -> void:
	var health := get_node("Helth")
	var mana := get_node("Manah")
	print("resolved: ", health.name, " ", mana.name)
