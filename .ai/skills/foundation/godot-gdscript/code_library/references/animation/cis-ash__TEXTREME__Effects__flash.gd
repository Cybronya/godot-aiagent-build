# Source:  https://github.com/cis-ash/TEXTREME/blob/master/Effects/flash.gd
# Repo:    cis-ash/TEXTREME (star 801) | License: MIT | Collected: 2026-10-31
# Commit:  673dc09d9132
extends Control

var letter = ""


func destroy(dummyarg = ""):
	queue_free()
	pass