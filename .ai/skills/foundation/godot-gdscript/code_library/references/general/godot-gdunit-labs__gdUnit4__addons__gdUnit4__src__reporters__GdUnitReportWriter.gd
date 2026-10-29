# Source:  https://github.com/godot-gdunit-labs/gdUnit4/blob/master/addons/gdUnit4/src/reporters/GdUnitReportWriter.gd
# Repo:    godot-gdunit-labs/gdUnit4 (star 1283) | License: MIT | Collected: 2026-10-29
# Commit:  e031bd413681
class_name GdUnitReportWriter
extends RefCounted


func write(_report_path: String, _report: GdUnitReportSummary) -> String:
	assert(false, "'write' is not implemented!")
	return ""


func output_format() -> String:
	assert(false, "'output_format' is not implemented!")
	return ""
