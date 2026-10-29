# Source:  https://github.com/blackears/cyclopsLevelBuilder/blob/master/subprojects/foldout_tabs/tabs_test.gd
# Repo:    blackears/cyclopsLevelBuilder (star 1639) | License: MIT | Collected: 2026-10-29
# Commit:  ea41feaab5dd
extends Control

func _ready() -> void:
	var g = preload("res://grid_content.tscn").instantiate()
	
	%side_tabs.add_control(g)
	#%side_tabs.active_tab = 0


	var h = preload("res://grid_content.tscn").instantiate()
	%side_tabs.add_control(h)
	
