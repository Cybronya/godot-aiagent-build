# Source:  https://github.com/alfredbaudisch/Godello/blob/master/scripts/single_button_popup.gd
# Repo:    alfredbaudisch/Godello (star 890) | License: MIT | Collected: 2026-10-29
# Commit:  4458a143644f
extends WindowDialog


func _on_Button_pressed():
	queue_free()
