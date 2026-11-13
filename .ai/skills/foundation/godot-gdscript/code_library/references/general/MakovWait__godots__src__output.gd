# Source:  https://github.com/MakovWait/godots/blob/main/src/output.gd
# Repo:    MakovWait/godots (star 816) | License: MIT | Collected: 2026-10-31
# Commit:  8e4eb2baa050
extends Node


func push(msg: Variant) -> void:
	print(msg)


func push_array(msg_array: Array) -> void:
	print(msg_array)
