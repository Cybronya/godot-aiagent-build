extends Button


# 自定义信号
signal mySignal(a, b)

# 发送信号
# emit_signal("mySignal", 1, 2)
# disconnect("mySignal", 1, 2)

# 类似于设计模式中的观察者
func _ready():
	self.connect("mySignal", Callable(self, "onMySingalCallback"))
	self.connect("pressed", Callable(self, "onButton"))


func onMySingalCallback(a, b):
	print("a:" + str(a))
	print("b:" + str(b))
	
func onButton():
	emit_signal("mySignal", 1, 2)
