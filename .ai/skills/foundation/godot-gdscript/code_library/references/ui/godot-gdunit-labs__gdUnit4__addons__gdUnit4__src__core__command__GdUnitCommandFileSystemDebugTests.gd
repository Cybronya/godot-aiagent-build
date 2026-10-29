# Source:  https://github.com/godot-gdunit-labs/gdUnit4/blob/master/addons/gdUnit4/src/core/command/GdUnitCommandFileSystemDebugTests.gd
# Repo:    godot-gdunit-labs/gdUnit4 (star 1283) | License: MIT | Collected: 2026-10-29
# Commit:  e031bd413681
class_name GdUnitCommandFileSystemDebugTests
extends GdUnitCommandFileSystem

const ID := "Debug FileSystem Tests"


func _init() -> void:
	super(ID, GdUnitShortcut.ShortCut.RUN_TESTSUITE_DEBUG)
	icon = GdUnitUiTools.get_icon("PlayStart")


func execute(...parameters: Array) -> void:
	if parameters.is_empty():
		return
	var selected_paths: PackedStringArray = parameters[0]
	execute_tests(selected_paths, true)
