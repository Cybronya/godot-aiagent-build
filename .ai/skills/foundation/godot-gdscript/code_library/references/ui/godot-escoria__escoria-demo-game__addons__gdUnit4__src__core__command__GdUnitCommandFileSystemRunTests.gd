# Source:  https://github.com/godot-escoria/escoria-demo-game/blob/main/addons/gdUnit4/src/core/command/GdUnitCommandFileSystemRunTests.gd
# Repo:    godot-escoria/escoria-demo-game (star 855) | License: MIT | Collected: 2026-10-29
# Commit:  92e650697717
class_name GdUnitCommandFileSystemRunTests
extends GdUnitCommandFileSystem


const ID := "Run FileSystem Tests"


func _init(test_session_command: GdUnitCommandTestSession) -> void:
	super(ID, GdUnitShortcut.ShortCut.RUN_TESTSUITE, test_session_command)
	icon =  GdUnitUiTools.get_icon("Play")


func execute(...parameters: Array) -> void:
	var selected_paths: PackedStringArray = parameters[0]
	execute_tests(selected_paths, false)
