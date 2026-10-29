# Source:  https://github.com/HungryProton/scatter/blob/main/addons/proton_scatter/src/stack/inspector_plugin/ui/modifier_list_popup/category.gd
# Repo:    HungryProton/scatter (star 3017) | License: MIT | Collected: 2026-10-28
# Commit:  7198cc00078e
@tool
extends VBoxContainer


@onready var label: Label = $Header/Label


func set_category_name(text) -> void:
	label.text = text
