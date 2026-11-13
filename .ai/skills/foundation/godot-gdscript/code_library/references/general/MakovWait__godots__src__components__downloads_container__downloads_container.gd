# Source:  https://github.com/MakovWait/godots/blob/main/src/components/downloads_container/downloads_container.gd
# Repo:    MakovWait/godots (star 816) | License: MIT | Collected: 2026-10-31
# Commit:  8e4eb2baa050
class_name DownloadsContainer
extends ScrollContainer


@onready var hbox := $HBoxContainer as HBoxContainer


func _ready() -> void:
	var update_scroll_container_visibility := func() -> void:
		self.visible = hbox.get_child_count() > 0
	hbox.child_entered_tree.connect(func(_node: Control) -> void:
		update_scroll_container_visibility.call_deferred()
	)
	hbox.child_exiting_tree.connect(func(_node: Control) -> void:
		update_scroll_container_visibility.call_deferred()
	)
	update_scroll_container_visibility.call()
	
	theme_changed.connect(_update_theme)


func _update_theme() -> void:
	self.add_theme_stylebox_override("panel", get_theme_stylebox("panel", "Tree"))


func add_download_item(item: Control) -> void:
	hbox.add_child(item)
