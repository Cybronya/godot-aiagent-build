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
