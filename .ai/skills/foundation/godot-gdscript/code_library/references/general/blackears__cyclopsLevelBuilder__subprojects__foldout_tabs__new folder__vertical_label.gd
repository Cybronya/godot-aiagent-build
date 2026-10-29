# Source:  https://github.com/blackears/cyclopsLevelBuilder/blob/master/subprojects/foldout_tabs/new folder/vertical_label.gd
# Repo:    blackears/cyclopsLevelBuilder (star 1639) | License: MIT | Collected: 2026-10-29
# Commit:  ea41feaab5dd
@tool
extends Control

@export var text:String
@export var font:Font
@export var font_size:int  = 16
@export var color:Color = Color.WHITE

func _draw() -> void:
	#TextServer.Orientation = TextServer.ORIENTATION_VERTICAL
	
	
	draw_string(font, Vector2.ZERO, text, HORIZONTAL_ALIGNMENT_LEFT, -1, font_size, color)
