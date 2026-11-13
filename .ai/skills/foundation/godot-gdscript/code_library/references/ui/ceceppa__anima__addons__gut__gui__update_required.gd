# Source:  https://github.com/ceceppa/anima/blob/main/addons/gut/gui/update_required.gd
# Repo:    ceceppa/anima (star 769) | License: MIT | Collected: 2026-10-31
# Commit:  f4a454ebd4d5
@tool
extends AcceptDialog

var should_continue = false
var _check_for_update_ctrl = null

signal closed

func _ready():
	add_cancel_button("Cancel Loading GUT")


func _on_confirmed() -> void:
	should_continue = true
	closed.emit.call_deferred()


func _on_canceled() -> void:
	should_continue = false
	closed.emit.call_deferred()


func _on_close_requested() -> void:
	should_continue = false
	closed.emit.call_deferred()


func set_check_for_update_control(ctrl):
	_check_for_update_ctrl = ctrl
	add_child(ctrl)
