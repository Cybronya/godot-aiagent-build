# Source:  https://github.com/protongraph/protongraph/blob/main/proton_graph_app.gd
# Repo:    protongraph/protongraph (star 1749) | License: MIT | Collected: 2026-10-29
# Commit:  1e2411a29464
class_name ProtonGraphApp
extends Node


@onready var _view_container: ViewContainer = $%ViewContainer


func _ready():
	get_tree().auto_accept_quit = false

	_view_container.quit_completed.connect(_on_quit_completed)

	await get_tree().process_frame


func _notification(event):
	if event == NOTIFICATION_WM_CLOSE_REQUEST:
		_view_container.save_all_and_quit()


func _on_quit_completed() -> void:
	get_tree().quit()

