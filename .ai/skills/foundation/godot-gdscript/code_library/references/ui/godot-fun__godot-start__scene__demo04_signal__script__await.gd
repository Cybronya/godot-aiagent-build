# Source:  https://github.com/godot-fun/godot-start/blob/main/scene/demo04_signal/script/await.gd
# Repo:    godot-fun/godot-start (star 1106) | License: MIT | Collected: 2026-10-29
# Commit:  115fc06e42f3
extends Button


func _ready():
	self.connect("pressed", Callable(self, "onButton"))

func onButton():
	var yieldResult1 = await doSomething1()
	
	var yieldResult2 = await doSomething2()
	# 等待yieldResult2执行完毕
	print("end")
	

func doSomething1():
	await print("doSomething")

func doSomething2():
	print(1)
	await get_tree().create_timer(1).timeout
	print(2)
	await get_tree().create_timer(1).timeout
	print(3)
	await get_tree().create_timer(1).timeout
	pass
