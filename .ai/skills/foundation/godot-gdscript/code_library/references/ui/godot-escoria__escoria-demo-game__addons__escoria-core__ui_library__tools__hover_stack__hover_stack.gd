# Source:  https://github.com/godot-escoria/escoria-demo-game/blob/main/addons/escoria-core/ui_library/tools/hover_stack/hover_stack.gd
# Repo:    godot-escoria/escoria-demo-game (star 855) | License: MIT | Collected: 2026-10-29
# Commit:  92e650697717
extends CanvasLayer

@onready var list = $VBoxContainer/hover_stack

func update() -> void:
	for e in list.get_children():
		list.remove_child(e)
		e.queue_free()
	if escoria.inputs_manager.hover_stack.is_empty():
		return
	for e in escoria.inputs_manager.hover_stack.get_all():
		var l = Label.new()
		l.text = e.global_id
		list.add_child(l)
