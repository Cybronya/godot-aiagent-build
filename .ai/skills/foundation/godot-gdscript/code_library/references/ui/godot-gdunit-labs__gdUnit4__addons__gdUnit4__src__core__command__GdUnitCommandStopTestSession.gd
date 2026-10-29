# Source:  https://github.com/godot-gdunit-labs/gdUnit4/blob/master/addons/gdUnit4/src/core/command/GdUnitCommandStopTestSession.gd
# Repo:    godot-gdunit-labs/gdUnit4 (star 1283) | License: MIT | Collected: 2026-10-29
# Commit:  e031bd413681
class_name GdUnitCommandStopTestSession
extends GdUnitBaseCommand

const ID := "Stop Test Session"


func _init() -> void:
	super(ID, GdUnitShortcut.ShortCut.STOP_TEST_RUN)
	icon = GdUnitUiTools.get_icon("Stop")


func execute(..._parameters: Array) -> void:
	push_error("No not call `GdUnitCommandStopTestSession` direcly!")


func _do_stop() -> void:
	pass
