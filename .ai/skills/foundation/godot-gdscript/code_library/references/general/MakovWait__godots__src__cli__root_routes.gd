# Source:  https://github.com/MakovWait/godots/blob/main/src/cli/root_routes.gd
# Repo:    MakovWait/godots (star 816) | License: MIT | Collected: 2026-10-31
# Commit:  8e4eb2baa050
class_name RootRoutes
extends Routes.List

func _init(ctx: CliContext) -> void:
	self._items = [
		DefaultRoutes.new(ctx),
		EditorsRoutes.new(ctx),
		ExecCommand.Route.new(ctx)
	]
