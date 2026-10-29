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
