# Source:  https://github.com/nathanhoad/godot_sound_manager/blob/main/addons/sound_manager/sound_effects.gd
# Repo:    nathanhoad/godot_sound_manager (star 830) | License: MIT | Collected: 2026-10-31
# Commit:  1c041582db80
extends "./abstract_audio_player_pool.gd"


func play(resource: AudioStream, override_bus: String = "") -> AudioStreamPlayer:
	var player: AudioStreamPlayer = prepare(resource, override_bus)
	player.call_deferred("play")
	return player


func stop(resource: AudioStream) -> void:
	for player: AudioStreamPlayer in busy_players:
		if player.stream == resource:
			player.call_deferred("stop")
