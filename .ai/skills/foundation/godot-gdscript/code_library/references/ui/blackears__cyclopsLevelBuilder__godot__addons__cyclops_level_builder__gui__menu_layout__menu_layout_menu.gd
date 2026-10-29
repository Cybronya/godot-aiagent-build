# Source:  https://github.com/blackears/cyclopsLevelBuilder/blob/master/godot/addons/cyclops_level_builder/gui/menu_layout/menu_layout_menu.gd
# Repo:    blackears/cyclopsLevelBuilder (star 1639) | License: MIT | Collected: 2026-10-29
# Commit:  ea41feaab5dd
@tool
extends MenuLayoutElement
class_name MenuLayoutMenu

@export var name:String
@export var children:Array[MenuLayoutElement]
