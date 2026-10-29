# Source:  https://github.com/gdquest-demos/godot-open-rpg/blob/main/src/field/cutscenes/templates/combat/roaming_combat_trigger.gd
# Repo:    gdquest-demos/godot-open-rpg (star 3028) | License: MIT | Collected: 2026-10-26
# Commit:  d59f2f71bc04
@tool
extends CombatTrigger


# If the player has defeated this 'roaming encounter', remove the encounter.
func _run_victory_cutscene() -> void:
	queue_free()


# If the player has lost to this 'roaming encounter', play the game-over screen.
func _run_loss_cutscene() -> void:
	await get_tree().process_frame
