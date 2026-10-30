# Source:  https://github.com/godot-escoria/escoria-demo-game/blob/main/addons/gdUnit4/src/core/hooks/GdUnitHtmlReporterTestSessionHook.gd
# Repo:    godot-escoria/escoria-demo-game (star 855) | License: MIT | Collected: 2026-10-29
# Commit:  92e650697717
class_name GdUnitHtmlReporterTestSessionHook
extends GdUnitBaseReporterTestSessionHook

const GdUnitTools := preload("res://addons/gdUnit4/src/core/GdUnitTools.gd")


func _init() -> void:
	super(GdUnitHtmlReportWriter.new(), "GdUnitHtmlTestReporter", "The Html test reporting hook.", GdUnitTools.richtext_normalize)
	set_meta("SYSTEM_HOOK", true)
