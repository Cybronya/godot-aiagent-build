# Source:  https://github.com/Miziziziz/MizGodotTools/blob/main/effects/hurt_heal_screen_effect/hurt_heal_screen_effect.gd
# Repo:    Miziziziz/MizGodotTools (star 987) | License: MIT | Collected: 2026-10-29
# Commit:  cb548f9035a3
extends CanvasLayer

@onready var base = $Base
@onready var hurt = $Base/Hurt
@onready var heal = $Base/Heal
@onready var animation_player = $AnimationPlayer

func play_heal_effect():
	heal.show()
	hurt.hide()
	animation_player.play("flash")

func play_hurt_effect():
	hurt.show()
	heal.hide()
	animation_player.play("flash")
