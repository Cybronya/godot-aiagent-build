# Source:  https://github.com/godot-escoria/escoria-demo-game/blob/main/addons/gdUnit4/src/core/command/GdUnitCommandFileSystemDebugTests.gd
# Repo:    godot-escoria/escoria-demo-game (star 855) | License: MIT | Collected: 2026-10-29
# Commit:  92e650697717
class_name GdUnitCommandFileSystemDebugTests
extends GdUnitCommandFileSystem


const ID := "Debug FileSystem Tests"


func _init(test_session_command: GdUnitCommandTestSession) -> void:
	super(ID, GdUnitShortcut.ShortCut.RUN_TESTSUITE_DEBUG, test_session_command)
	icon =  GdUnitUiTools.get_icon("PlayStart")


func execute(...parameters: Array) -> void:
	if parameters.is_empty():
		return
	var selected_paths: PackedStringArray = parameters[0]
	execute_tests(selected_paths, true)
