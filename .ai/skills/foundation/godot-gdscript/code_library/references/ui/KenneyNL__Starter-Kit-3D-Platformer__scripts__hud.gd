# Source:  https://github.com/KenneyNL/Starter-Kit-3D-Platformer/blob/main/scripts/hud.gd
# Repo:    KenneyNL/Starter-Kit-3D-Platformer (star 1264) | License: MIT | Collected: 2026-10-29
# Commit:  3fa8a04b1c01
extends Control

func _on_coin_collected(coins):
	
	$Coins.text = str(coins)
