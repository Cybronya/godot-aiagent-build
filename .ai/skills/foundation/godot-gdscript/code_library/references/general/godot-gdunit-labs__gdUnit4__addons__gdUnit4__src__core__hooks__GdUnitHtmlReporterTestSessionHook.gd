# Source:  https://github.com/godot-gdunit-labs/gdUnit4/blob/master/addons/gdUnit4/src/core/hooks/GdUnitHtmlReporterTestSessionHook.gd
# Repo:    godot-gdunit-labs/gdUnit4 (star 1283) | License: MIT | Collected: 2026-10-29
# Commit:  e031bd413681
class_name GdUnitHtmlReporterTestSessionHook
extends GdUnitBaseReporterTestSessionHook

const GdUnitTools := preload("res://addons/gdUnit4/src/core/GdUnitTools.gd")


func _init() -> void:
	super(GdUnitHtmlReportWriter.new(), "GdUnitHtmlTestReporter", "The Html test reporting hook.", GdUnitTools.richtext_normalize)
	set_meta("SYSTEM_HOOK", true)
