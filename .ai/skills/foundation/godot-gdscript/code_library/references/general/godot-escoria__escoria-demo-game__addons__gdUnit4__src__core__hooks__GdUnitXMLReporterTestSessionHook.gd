# Source:  https://github.com/godot-escoria/escoria-demo-game/blob/main/addons/gdUnit4/src/core/hooks/GdUnitXMLReporterTestSessionHook.gd
# Repo:    godot-escoria/escoria-demo-game (star 855) | License: MIT | Collected: 2026-10-29
# Commit:  92e650697717
class_name GdUnitXMLReporterTestSessionHook
extends GdUnitBaseReporterTestSessionHook


func _init() -> void:
	super(JUnitXmlReportWriter.new(), "GdUnitXMLTestReporter", "The JUnit XML test reporting hook.", convert_report_message)
	set_meta("SYSTEM_HOOK", true)


func convert_report_message(value: String) -> String:
	return value
