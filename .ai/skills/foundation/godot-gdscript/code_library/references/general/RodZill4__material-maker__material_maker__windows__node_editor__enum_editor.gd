# Source:  https://github.com/RodZill4/material-maker/blob/master/material_maker/windows/node_editor/enum_editor.gd
# Repo:    RodZill4/material-maker (star 6030) | License: MIT | Collected: 2026-10-28
# Commit:  master
extends Window

signal ok

func set_value(n, v) -> void:
	$VBoxContainer/GridContainer/name.text = n
	$VBoxContainer/GridContainer/value.text = v

func _on_OK_pressed() -> void:
	emit_signal("ok", $VBoxContainer/GridContainer/name.text, $VBoxContainer/GridContainer/value.text)
	queue_free()
