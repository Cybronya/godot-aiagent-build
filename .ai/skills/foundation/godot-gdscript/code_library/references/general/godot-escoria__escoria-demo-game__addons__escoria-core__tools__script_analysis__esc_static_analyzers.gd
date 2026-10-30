# Source:  https://github.com/godot-escoria/escoria-demo-game/blob/main/addons/escoria-core/tools/script_analysis/esc_static_analyzers.gd
# Repo:    godot-escoria/escoria-demo-game (star 855) | License: MIT | Collected: 2026-10-29
# Commit:  92e650697717
class_name ESCStaticAnalyzers
extends RefCounted


var _analyzers = [
	ESCExitSceneScriptAnalyzer.new()
]

var _parsed_statements = []


func _init(parsed_statements: Array) -> void:
	_parsed_statements = parsed_statements


func run() -> void:
	for analyzer in _analyzers:
		analyzer.analyze(_parsed_statements)
		analyzer.print_messages()
