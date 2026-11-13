# Source:  https://github.com/MakovWait/godots/blob/main/src/auto_close.gd
# Repo:    MakovWait/godots (star 816) | License: MIT | Collected: 2026-10-31
# Commit:  8e4eb2baa050
extends Node


func close_if_should() -> void:
	if Config.AUTO_CLOSE.ret():
		get_tree().quit()
