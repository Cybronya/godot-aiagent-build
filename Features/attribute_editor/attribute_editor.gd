class_name AttributeTable
extends Resource
## 属性表：管理一组游戏属性（如生命值、体力），支持定义、查询、更新、范围验证。
##
## 抽象自 OctoD/godot-gameplay-systems (MIT)，简化：
## - 去掉编辑器 UI 依赖，改为纯数据模型
## - 保留核心：属性定义（名称/值/范围/类型）+ 增删改查
## - 可序列化，方便存档/配置

@export var attributes: Array[Dictionary] = []


## 添加属性。重复名称被忽略。attr_type: "int" / "float" / "bool" / "string"
func add_attribute(name: String, value: Variant = 0, min_value: float = 0.0, max_value: float = 100.0, attr_type: String = "int") -> void:
	if get_attribute(name) != null:
		return
	attributes.append({
		"name": name,
		"value": value,
		"min_value": min_value,
		"max_value": max_value,
		"type": attr_type,
	})


## 获取属性字典（内部引用），null 表示不存在。
func get_attribute(name: String) -> Variant:
	for attr in attributes:
		if attr["name"] == name:
			return attr
	return null


func remove_attribute(name: String) -> void:
	for i in attributes.size():
		if attributes[i]["name"] == name:
			attributes.remove_at(i)
			return


## 更新属性值。返回是否成功（属性不存在返回 false）。
func update_attribute(name: String, value: Variant) -> bool:
	var attr: Variant = get_attribute(name)
	if attr == null:
		return false
	attr["value"] = value
	return true


func get_attribute_value(name: String) -> Variant:
	var attr: Variant = get_attribute(name)
	if attr == null:
		return null
	return attr["value"]


## 验证属性值是否在合法范围内。bool/string 类型恒为 true。
func is_value_valid(name: String) -> bool:
	var attr: Variant = get_attribute(name)
	if attr == null:
		return false
	if attr["type"] == "bool" or attr["type"] == "string":
		return true
	var num: float = float(attr["value"])
	var min_val: float = float(attr["min_value"])
	var max_val: float = float(attr["max_value"])
	return num >= min_val and num <= max_val


func get_attribute_names() -> Array[String]:
	var names: Array[String] = []
	for attr in attributes:
		names.append(attr["name"])
	return names
