# Source:  https://github.com/MakovWait/godots/blob/main/src/cli/commands/editor/editor_routes.gd
# Repo:    MakovWait/godots (star 816) | License: MIT | Collected: 2026-10-31
# Commit:  8e4eb2baa050
class_name EditorsRoutes
extends Routes.List

func _init(ctx: CliContext) -> void:
	self._items = [
		#EditorCfgCommand.Route.new(ctx),
		EditorListCommand.Route.new(ctx)
	]

func match(cmd: CliParser.ParsedCommandResult, user_args: PackedStringArray) -> bool:
	return cmd.namesp == "editor" and super.match(cmd, user_args)
