# Source:  https://github.com/bitbrain/pandora/blob/godot-4.x/addons/pandora/ui/components/notification_label/notification_label.gd
# Repo:    bitbrain/pandora (star 1129) | License: MIT | Collected: 2026-10-29
# Commit:  fa48e30e6609
@tool
extends Label

var tween: Tween


func _ready() -> void:
	self_modulate.a = 0.0


func popup() -> void:
	visible = true
	if tween and tween.is_running():
		tween.stop()
	self_modulate.a = 1.0
	tween = create_tween().set_ease(Tween.EASE_OUT).set_trans(Tween.TRANS_CUBIC)
	tween.finished.connect(func(): visible = false)
	tween.tween_property(self, "self_modulate:a", 0.0, 1.5).set_delay(2.0)
