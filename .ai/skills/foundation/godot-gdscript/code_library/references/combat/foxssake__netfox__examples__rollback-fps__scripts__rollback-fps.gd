# Source:  https://github.com/foxssake/netfox/blob/main/examples/rollback-fps/scripts/rollback-fps.gd
# Repo:    foxssake/netfox (star 1121) | License: MIT | Collected: 2026-10-29
# Commit:  cf5189d18e98
extends Object
class_name ExampleRollbackFPS

const Player := preload("res://examples/rollback-fps/scripts/player.gd")
const PlayerInput := preload("res://examples/rollback-fps/scripts/player-input.gd")
const PlayerWeapon := preload("res://examples/rollback-fps/scripts/player-weapon.gd")
const HUD := preload("res://examples/rollback-fps/ui/fps-hud.gd")
