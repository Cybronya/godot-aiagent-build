# Source:  https://github.com/godotengine/godot-demo-projects/blob/master/networking/multiplayer_bomber/rock.gd
# Repo:    godotengine/godot-demo-projects (star 9711) | License: MIT | Collected: 2026-10-26
# Commit:  b761b4cd5718
extends CharacterBody2D

@rpc("call_local")
func exploded(by_who: int) -> void:
	$"../../Score".increase_score(by_who)
	$"AnimationPlayer".play(&"explode")
