# Source:  https://github.com/godot-escoria/escoria-demo-game/blob/main/addons/escoria-core/_test/test_migrations.gd
# Repo:    godot-escoria/escoria-demo-game (star 855) | License: MIT | Collected: 2026-10-29
# Commit:  92e650697717
extends Control



func _on_CheckESCMigrationManager_pressed() -> bool:
	var savegame: ESCSaveGame = ESCSaveGame.new()

	savegame.globals["test"] = "testa"

	var migration_manager: ESCMigrationManager = ESCMigrationManager.new()
	savegame = migration_manager.migrate(
		savegame,
		"1.0.0",
		"2.0.0",
		"res://addons/escoria-core/_test/testversions"
	)

	assert(savegame.globals["test"] == "testc")

	return true
