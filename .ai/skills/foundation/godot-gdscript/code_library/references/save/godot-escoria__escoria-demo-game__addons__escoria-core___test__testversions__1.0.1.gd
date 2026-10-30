# Source:  https://github.com/godot-escoria/escoria-demo-game/blob/main/addons/escoria-core/_test/testversions/1.0.1.gd
# Repo:    godot-escoria/escoria-demo-game (star 855) | License: MIT | Collected: 2026-10-29
# Commit:  92e650697717
extends ESCMigration

func migrate():
	self._savegame.globals["test"] = "testb"

