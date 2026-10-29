# Source:  https://github.com/godot-gdunit-labs/gdUnit4/blob/master/addons/gdUnit4/src/core/command/GdUnitCommandFileSystemRunTests.gd
# Repo:    godot-gdunit-labs/gdUnit4 (star 1283) | License: MIT | Collected: 2026-10-29
# Commit:  e031bd413681
class_name GdUnitCommandFileSystemRunTests
extends GdUnitCommandFileSystem

const ID := "Run FileSystem Tests"


func _init() -> void:
	super(ID, GdUnitShortcut.ShortCut.RUN_TESTSUITE)
	icon = GdUnitUiTools.get_icon("Play")


func execute(...parameters: Array) -> void:
	var selected_paths: PackedStringArray = parameters[0]
	execute_tests(selected_paths, false)
