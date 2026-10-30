class_name InstancedNodeFixture
extends Node
## instanced 存档协议夹具：模拟掉落物、弹坑等运行时实例化节点。
## get_save_data 自带 instance_uid（指向本场景），恢复时由 SaveGame 重建。

var stored_value := 0


func get_save_data() -> Dictionary:
	return {
		SaveData.INSTANCE_UID_KEY: "res://Features/save_game/InstancedNodeFixture.tscn",
		"value": stored_value,
	}


func load_save_data(data: Dictionary) -> void:
	stored_value = data.get("value", 0)
