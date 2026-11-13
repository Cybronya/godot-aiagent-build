# Source:  https://github.com/cis-ash/TEXTREME/blob/master/Scenes/Main/FilePopupSpawner.gd
# Repo:    cis-ash/TEXTREME (star 801) | License: MIT | Collected: 2026-10-31
# Commit:  673dc09d9132
extends Control

func on_save_completed(is_success : bool):
	#TODO spawn window effect
	print("Save effect, success = ", is_success)
	pass 

func on_load_completed(is_success : bool):
	#TODO spawn window effect
	print("Load effect, success = ", is_success)
	pass