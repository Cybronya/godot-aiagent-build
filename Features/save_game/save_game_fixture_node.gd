class_name SaveGameFixtureNode
extends Node
## save_game 行为夹具节点：实现 node_save_protocol（get_save_data/load_save_data），
## 数据载荷为子节点 Health 的当前生命值。恢复走 Health 公开接口（heal/take_damage），
## 与 health Feature 的真实组件联动。


func get_save_data() -> Dictionary:
	var health := _health()
	if health == null:
		return {}
	return {"hp": health.get_current_health()}


func load_save_data(data: Dictionary) -> void:
	var health := _health()
	if health == null:
		return
	var diff := int(data.get("hp", 0)) - health.get_current_health()
	if diff > 0:
		health.heal(diff)
	elif diff < 0:
		health.take_damage(-diff)


func _health() -> Health:
	return get_node_or_null("Health") as Health
