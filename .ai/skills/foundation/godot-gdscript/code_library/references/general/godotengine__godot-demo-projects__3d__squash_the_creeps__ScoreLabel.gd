# Source:  https://github.com/godotengine/godot-demo-projects/blob/master/3d/squash_the_creeps/ScoreLabel.gd
# Repo:    godotengine/godot-demo-projects (star 9711) | License: MIT | Collected: 2026-10-26
# Commit:  b761b4cd5718
extends Label

var score = 0

func _on_Mob_squashed():
	score += 1
	text = "Score: %s" % score
