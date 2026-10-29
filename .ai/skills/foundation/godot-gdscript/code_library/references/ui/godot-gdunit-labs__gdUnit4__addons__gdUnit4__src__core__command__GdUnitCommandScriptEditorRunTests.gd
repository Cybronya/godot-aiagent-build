# Source:  https://github.com/godot-gdunit-labs/gdUnit4/blob/master/addons/gdUnit4/src/core/command/GdUnitCommandScriptEditorRunTests.gd
# Repo:    godot-gdunit-labs/gdUnit4 (star 1283) | License: MIT | Collected: 2026-10-29
# Commit:  e031bd413681
class_name GdUnitCommandScriptEditorRunTests
extends GdUnitCommandScriptEditor

const ID := "Run ScriptEditor Tests"


func _init() -> void:
	super(ID, GdUnitShortcut.ShortCut.RUN_TESTCASE)
	icon = GdUnitUiTools.get_icon("Play")


func execute(..._parameters: Array) -> void:
	execute_tests(false)
