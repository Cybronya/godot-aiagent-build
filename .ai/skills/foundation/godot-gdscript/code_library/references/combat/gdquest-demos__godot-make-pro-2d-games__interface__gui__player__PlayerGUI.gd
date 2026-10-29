# Source:  https://github.com/gdquest-demos/godot-make-pro-2d-games/blob/master/interface/gui/player/PlayerGUI.gd
# Repo:    gdquest-demos/godot-make-pro-2d-games (star 1276) | License: MIT | Collected: 2026-10-29
# Commit:  7290681309ff
extends Control

func initialize(health_node, purse):
	$LifeBar.initialize(health_node)
	$CoinsCounter.initialize(purse)
	health_node.connect('health_depleted', self, '_on_Player_Health_health_depleted')

func _on_Player_Health_health_depleted():
	$AnimationPlayer.play("fade_out")
