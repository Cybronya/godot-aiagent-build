# Source:  https://github.com/godot-gdunit-labs/gdUnit4/blob/master/addons/gdUnit4/src/core/command/GdUnitCommandScriptEditorDebugTests.gd
# Repo:    godot-gdunit-labs/gdUnit4 (star 1283) | License: MIT | Collected: 2026-10-29
# Commit:  e031bd413681
class_name GdUnitCommandScriptEditorDebugTests
extends GdUnitCommandScriptEditor

const ID := "Debug ScriptEditor Tests"


func _init() -> void:
	super(ID, GdUnitShortcut.ShortCut.RUN_TESTCASE_DEBUG)
	icon = GdUnitUiTools.get_icon("PlayStart")


func execute(..._parameters: Array) -> void:
	execute_tests(true)
