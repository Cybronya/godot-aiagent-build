extends Button

func _ready():
	self.connect("pressed", Callable(self, "onButton2"))
	
func onButton2():
	var myThread = Thread.new()
	
	print("Create Thread Id: ", myThread)
	print("Thread Active: ", myThread.is_alive())
	
	myThread.start(Callable(self, "threadTest"))
	
	print("Thread Active: ", myThread.is_alive())
	
	var waitForThread = myThread.wait_to_finish() # wait for our thread to finish before moving on
	
	print()
	print("Thread is Finished with result: ", waitForThread)
	print("Thread Active: ", myThread.is_alive())
	



# 使用thread运行的函数必须有一个参数，要不然无法运行
func threadTest():
	print("thread test start")
	return 999
