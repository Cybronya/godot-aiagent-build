# Source:  https://github.com/godotengine/godot-demo-projects/blob/master/2d/custom_drawing/custom_drawing.gd
# Repo:    godotengine/godot-demo-projects (star 9711) | License: MIT | Collected: 2026-10-26
# Commit:  b761b4cd5718
extends Control


func _on_msaa_2d_item_selected(index: int) -> void:
	get_viewport().msaa_2d = index as Viewport.MSAA


func _on_draw_antialiasing_toggled(toggled_on: bool) -> void:
	var nodes: Array[Node] = %TabContainer.get_children()
	nodes.push_back(%AnimationSlice)
	for tab: Control in nodes:
		tab.use_antialiasing = toggled_on
		# Force all tabs to redraw so that the antialiasing updates.
		tab.queue_redraw()
