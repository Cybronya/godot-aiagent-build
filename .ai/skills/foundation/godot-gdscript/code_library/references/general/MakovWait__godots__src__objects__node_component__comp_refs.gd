# Source:  https://github.com/MakovWait/godots/blob/main/src/objects/node_component/comp_refs.gd
# Repo:    MakovWait/godots (star 816) | License: MIT | Collected: 2026-10-31
# Commit:  8e4eb2baa050
class_name CompRefs


class Simple:
	var value: Variant
	
	func _init(value: Variant = null) -> void:
		self.value = value


class Transient:
	var _on_set: Callable
	var value: Variant:
		set(v): 
			_on_set.call(v)
	
	func _init(on_set: Callable) -> void:
		_on_set = on_set


class Field extends Transient:
	func _init(obj: Object, field_key: String) -> void:
		super._init(func(v: Variant) -> void: obj.set(field_key, v))
