# Source:  https://github.com/MakovWait/godots/blob/main/src/components/misc/item_tag_container.gd
# Repo:    MakovWait/godots (star 816) | License: MIT | Collected: 2026-10-31
# Commit:  8e4eb2baa050
class_name ItemTagContainer
extends HBoxContainer

signal tag_clicked(tag: String)

@export var _tag_scene: PackedScene = preload("res://src/components/tags/tag/tag.tscn")


func set_tags(tags: Array) -> void:
	for child in get_children():
		child.queue_free()
	for tag: String in tags:
		var tag_control: TagControl = _tag_scene.instantiate()
		add_child(tag_control)
		tag_control.init(tag)
		tag_control.pressed.connect(func() -> void: tag_clicked.emit(tag))
