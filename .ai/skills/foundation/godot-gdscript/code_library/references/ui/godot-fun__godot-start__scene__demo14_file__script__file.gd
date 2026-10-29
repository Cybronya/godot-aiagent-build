# Source:  https://github.com/godot-fun/godot-start/blob/main/scene/demo14_file/script/file.gd
# Repo:    godot-fun/godot-start (star 1106) | License: MIT | Collected: 2026-10-29
# Commit:  115fc06e42f3
extends Node2D

const TimeUtils = preload("res://zfoo/util/TimeUtils.gd")
const FileUtils = preload("res://zfoo/util/FileUtils.gd")


# Dictionary
var content = "hello file!!!"

# path string
var filePath: String = "user://playerData.txt"


func _ready() -> void:
	print("Original Data: ", content)
	self.loadData()
	print("Altered Data: ", content)


func saveData() -> void:
	FileUtils.writeStringToFile(filePath, content)


func loadData() -> void:
	content = FileUtils.readFileToString(filePath)


# 退出的时候回调
func _notification(what):
	if what == NOTIFICATION_WM_CLOSE_REQUEST:
		content = content + str(TimeUtils.currentTimeMillis())
		self.saveData()
		get_tree().quit() # quitting the game
