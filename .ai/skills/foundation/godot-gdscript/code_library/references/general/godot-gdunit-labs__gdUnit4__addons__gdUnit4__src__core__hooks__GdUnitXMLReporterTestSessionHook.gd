# Source:  https://github.com/godot-gdunit-labs/gdUnit4/blob/master/addons/gdUnit4/src/core/hooks/GdUnitXMLReporterTestSessionHook.gd
# Repo:    godot-gdunit-labs/gdUnit4 (star 1283) | License: MIT | Collected: 2026-10-29
# Commit:  e031bd413681
class_name GdUnitXMLReporterTestSessionHook
extends GdUnitBaseReporterTestSessionHook


func _init() -> void:
	super(JUnitXmlReportWriter.new(), "GdUnitXMLTestReporter", "The JUnit XML test reporting hook.", convert_report_message)
	set_meta("SYSTEM_HOOK", true)


func convert_report_message(value: String) -> String:
	return value
