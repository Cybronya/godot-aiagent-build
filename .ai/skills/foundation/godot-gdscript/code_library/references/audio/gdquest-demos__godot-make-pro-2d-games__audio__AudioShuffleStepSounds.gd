# Source:  https://github.com/gdquest-demos/godot-make-pro-2d-games/blob/master/audio/AudioShuffleStepSounds.gd
# Repo:    gdquest-demos/godot-make-pro-2d-games (star 1276) | License: MIT | Collected: 2026-10-29
# Commit:  7290681309ff
extends AudioStreamPlayer

# In Godot 3.1 you can export the Array instead
var samples = [
	preload("res://audio/sfx/step_01.wav"),
	preload("res://audio/sfx/step_02.wav")
]

func _ready():
	randomize()

func play_random():
	# In Godot 3.1 you can use Array.shuffle() after going through the sounds
	stream = samples[randi() % samples.size()]
	play()
