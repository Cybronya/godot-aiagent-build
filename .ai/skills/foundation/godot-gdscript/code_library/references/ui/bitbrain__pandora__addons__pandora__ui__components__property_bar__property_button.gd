# Source:  https://github.com/bitbrain/pandora/blob/godot-4.x/addons/pandora/ui/components/property_bar/property_button.gd
# Repo:    bitbrain/pandora (star 1129) | License: MIT | Collected: 2026-10-29
# Commit:  fa48e30e6609
class_name PandoraPropertyButton extends Button

@export var scene: PackedScene


func _ready():
	if scene:
		var scene_instance = scene.instantiate()
		var path = ""
		if PandoraSettings.extensions_types.has(scene_instance.type):
			path = PandoraSettings.extensions_types[scene_instance.type]
		var property_type = PandoraPropertyType.lookup(scene_instance.type, path)
		icon = load(property_type.get_type_icon_path())
		scene_instance.queue_free()
