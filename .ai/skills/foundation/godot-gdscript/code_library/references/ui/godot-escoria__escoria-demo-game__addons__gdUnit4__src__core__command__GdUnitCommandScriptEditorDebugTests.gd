# Source:  https://github.com/godot-escoria/escoria-demo-game/blob/main/addons/gdUnit4/src/core/command/GdUnitCommandScriptEditorDebugTests.gd
# Repo:    godot-escoria/escoria-demo-game (star 855) | License: MIT | Collected: 2026-10-29
# Commit:  92e650697717
class_name GdUnitCommandScriptEditorDebugTests
extends GdUnitCommandScriptEditor


const ID := "Debug ScriptEditor Tests"


func _init(test_session_command: GdUnitCommandTestSession) -> void:
	super(ID, GdUnitShortcut.ShortCut.RUN_TESTCASE_DEBUG, test_session_command)
	icon =  GdUnitUiTools.get_icon("PlayStart")


func execute(..._parameters: Array) -> void:
	execute_tests(true)
