# Source:  https://github.com/bitbrain/pandora/blob/godot-4.x/addons/pandora/ui/components/loading_spinner/loading_spinner.gd
# Repo:    bitbrain/pandora (star 1129) | License: MIT | Collected: 2026-10-29
# Commit:  fa48e30e6609
@tool
extends CenterContainer

@onready var rotation_sprite = $Control/RotationSprite


func _ready() -> void:
	_tween()


func _tween() -> void:
	var tween = create_tween()
	rotation_sprite.rotation_degrees = -360
	(
		tween
		. tween_property(rotation_sprite, "rotation_degrees", 360, 1.5)
		. set_ease(Tween.EASE_IN_OUT)
		. set_trans(Tween.TRANS_CUBIC)
		. finished
		. connect(_tween)
	)
