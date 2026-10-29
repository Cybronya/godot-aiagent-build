# Source:  https://github.com/godotengine/godot-demo-projects/blob/master/2d/role_playing_game/combat/combatants/opponent.gd
# Repo:    godotengine/godot-demo-projects (star 9711) | License: MIT | Collected: 2026-10-26
# Commit:  b761b4cd5718
extends Combatant

func set_active(value: bool) -> void:
	super.set_active(value)
	if not active:
		return

	if not $Timer.is_inside_tree():
		return

	$Timer.start()
	await $Timer.timeout

	var target: Node
	for actor in get_parent().get_children():
		if not actor == self:
			target = actor
			break

	attack(target)
