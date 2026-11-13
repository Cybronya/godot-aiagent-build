# Source:  https://github.com/OctoD/godot-gameplay-systems/blob/main/addons/godot_gameplay_systems/attributes_and_abilities/nodes/effected_area3d.gd
# Repo:    OctoD/godot-gameplay-systems (star 746) | License: MIT | Collected: 2026-10-31
# Commit:  9349931cc7a5
@tool
class_name EffectedArea3D extends Area3D

## An extension to base class with automatism for GameplayAttributeMap
## 
## Applies [GameplayEffect]s automatically when a collision is triggered and [method should_apply_effect] returns [code]true[/code].


@export_category("Gameplay Effect Handling")
## Removes the EffectedArea2D if [method should_apply_effect] returns [code]true[/code]
@export var remove_self_on_apply := true
## Removes all child [GameplayEffect]s when colliding and when [method should_apply_effect] returns [code]true[/code]
@export var remove_effects_on_apply := true


## Gets all child GameplayEffect nodes
var effects: Array[GameplayEffect] = []:
	get:
		var _effects: Array[GameplayEffect] = []
		
		for child in get_children():
			if child is GameplayEffect:
				_effects.append(child)
		
		return _effects


func _ready() -> void:
	if not Engine.is_editor_hint():
		area_entered.connect(func (body: Area3D):
			if should_apply_effect(body):
				for effect in effects:
					if remove_effects_on_apply:
						remove_child(effect)
						body.add_child(effect)
					else:
						body.add_child(effect.duplicate())

				if remove_self_on_apply:
					queue_free()
		)
		
		body_entered.connect(func (body: Node3D):
			if should_apply_effect(body):
				for effect in effects:
					if remove_effects_on_apply:
						remove_child(effect)
						body.add_child(effect)
					else:
						body.add_child(effect.duplicate())

				if remove_self_on_apply:
					queue_free()
		)


## Returns true if the effect should be applied to a certain node
func should_apply_effect(node: Node3D) -> bool:
	return true
