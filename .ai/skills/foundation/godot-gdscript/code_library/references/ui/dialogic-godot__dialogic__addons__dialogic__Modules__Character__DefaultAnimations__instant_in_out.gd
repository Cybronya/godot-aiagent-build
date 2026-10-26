# Source:  https://github.com/dialogic-godot/dialogic/blob/main/addons/dialogic/Modules/Character/DefaultAnimations/instant_in_out.gd
# Repo:    dialogic-godot/dialogic (star 6121) | License: MIT | Collected: 2026-10-26
# Commit:  main
extends DialogicAnimation

func animate() -> void:
	await node.get_tree().process_frame
	finished.emit()


func _get_named_variations() -> Dictionary:
	return {
		"instant in": {"reversed": false, "type": AnimationType.IN},
		"instant out": {"reversed": true, "type": AnimationType.OUT},
	}
