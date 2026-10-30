# Source:  https://github.com/godot-escoria/escoria-demo-game/blob/main/addons/gdUnit4/src/reporters/GdUnitReportWriter.gd
# Repo:    godot-escoria/escoria-demo-game (star 855) | License: MIT | Collected: 2026-10-29
# Commit:  92e650697717
class_name GdUnitReportWriter
extends RefCounted


func write(_report_path: String, _report: GdUnitReportSummary) -> String:
	assert(false, "'write' is not implemented!")
	return ""


func output_format() -> String:
	assert(false, "'output_format' is not implemented!")
	return ""
