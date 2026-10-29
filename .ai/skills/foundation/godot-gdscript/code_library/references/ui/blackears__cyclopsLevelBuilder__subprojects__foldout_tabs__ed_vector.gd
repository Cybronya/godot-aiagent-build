# Source:  https://github.com/blackears/cyclopsLevelBuilder/blob/master/subprojects/foldout_tabs/ed_vector.gd
# Repo:    blackears/cyclopsLevelBuilder (star 1639) | License: MIT | Collected: 2026-10-29
# Commit:  ea41feaab5dd
extends Control


func _ready() -> void:
	var ss = EditorSpinSlider.new()
	$VBoxContainer.add_child(ss)
	
	$VBoxContainer.add_child(CheckButton.new())
