# Source:  https://github.com/blackears/cyclopsLevelBuilder/blob/master/subprojects/foldout_tabs/test_inset_window.gd
# Repo:    blackears/cyclopsLevelBuilder (star 1639) | License: MIT | Collected: 2026-10-29
# Commit:  ea41feaab5dd
extends Control

func _ready() -> void:
	%PopupPanel.show()
	
	%Popup.show()


func _on_gui_input(event: InputEvent) -> void:
	print(event)
	
#	if event.is_action_pressed("ui_accept"):
	if event is InputEventMouseButton:
		%PopupPanel.show()
		
		%Popup.show()
		
	pass # Replace with function body.
