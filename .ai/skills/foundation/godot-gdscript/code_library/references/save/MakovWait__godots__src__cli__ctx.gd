# Source:  https://github.com/MakovWait/godots/blob/main/src/cli/ctx.gd
# Repo:    MakovWait/godots (star 816) | License: MIT | Collected: 2026-10-31
# Commit:  8e4eb2baa050
class_name CliContext

var projects: Projects.List
var editors: LocalEditors.List


func _init() -> void:
	editors = LocalEditors.List.new(
		Config.EDITORS_CONFIG_PATH
	)
	projects = Projects.List.new(
		Config.PROJECTS_CONFIG_PATH,
		editors,
		preload("res://assets/default_project_icon.svg")
	)

	editors.load()
	projects.load()


func cleanup() -> void:
	editors.cleanup()
	projects.cleanup()
