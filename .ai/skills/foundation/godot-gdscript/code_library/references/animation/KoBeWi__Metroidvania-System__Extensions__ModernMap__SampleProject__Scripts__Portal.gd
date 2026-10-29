# Source:  https://github.com/KoBeWi/Metroidvania-System/blob/master/Extensions/ModernMap/SampleProject/Scripts/Portal.gd
# Repo:    KoBeWi/Metroidvania-System (star 1596) | License: MIT | Collected: 2026-10-26
# Commit:  0065ae897429
# A portal object that transports to another world layer.
extends Area2D
# The target map after entering the portal.
@export_file("room_link") var target_map: String

func _on_body_entered(body: Node2D) -> void:
	# If player entered and isn't doing an event (event in this case is entering the portal).
	if body.is_in_group(&"player") and not body.event:
		body.event = true
		body.velocity = Vector2()
		# Tween the player position into the portal.
		var tween := create_tween()
		tween.tween_property(body, ^"position", position, 0.5).set_ease(Tween.EASE_IN).set_trans(Tween.TRANS_SINE)
		await tween.finished
		# After tween finished, change the map.
		# Use the special teleport method that handles map fog.
		Game.get_singleton().teleport_to_room(target_map)
		# A trick to reset player's event variable when it's safe to do so (i.e. after some frames).
		get_tree().create_timer(0.2).timeout.connect(body.set.bind(&"event", false))
