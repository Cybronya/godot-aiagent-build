# Source:  https://github.com/dialogic-godot/dialogic/blob/main/addons/dialogic/Resources/dialogic_style_layer.gd
# Repo:    dialogic-godot/dialogic (star 6121) | License: MIT | Collected: 2026-10-26
# Commit:  701b67bbe601
@tool
class_name DialogicStyleLayer
extends Resource

@export var scene: PackedScene = null
@export var overrides := {}


func _init(scene_path:Variant=null, scene_overrides:Dictionary={}):
	if scene_path is PackedScene:
		scene = scene_path
	elif scene_path is String and ResourceLoader.exists(scene_path):
		scene = load(scene_path)
	overrides = scene_overrides


func _to_string() -> String:
	if scene:
		return "<Layer:" + scene.resource_path + " {" + str(len(overrides)) + " overrides} >"
	else:
		return "<Layer:no-scene>"
