# Source:  https://github.com/gdquest-demos/godot-open-rpg/blob/main/src/combat/combat_arena.gd
# Repo:    gdquest-demos/godot-open-rpg (star 3028) | License: MIT | Collected: 2026-10-26
# Commit:  d59f2f71bc04
## An arena is the editor-configured environment for a battle. It is a Control node that contains 
## the combat participants and details (such as background, foreground, music, etc.).
class_name CombatArena extends Control

## The music that will be automatically played during this combat instance.
@export var music: AudioStream


## Retrieve the list of the combat participants, in [BattlerRoster] form.
func get_battler_roster() -> BattlerRoster:
	return $Battlers as BattlerRoster
