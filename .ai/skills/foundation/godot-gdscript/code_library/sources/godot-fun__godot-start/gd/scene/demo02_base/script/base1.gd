extends Node2D


# 导出一个数字
@export var a = 1
# 导出一个节点路径
@export var b:NodePath
# 导出一个文件路径
@export_file var sound_effect_path: String
# 导出一个文件路径，以txt结尾
@export_file("*.txt") var notes_path: String


func _init():
	print("init")
	

# Called when the node enters the scene tree for the first time.
func _ready():
	print("ready")
	print("new一个对象--------------------------------")
	var myClass = MyClass.new()
	print(myClass.to_string())
	
	print("数据类型信息--------------------------------")
	myClass.typeInfo()
	
	print("基础语法if else--------------------------------")
	myClass.if_function(1, 2)
	
	print("基础语法switch--------------------------------")
	myClass.switch_function()
	
	print("基础语法while for--------------------------------")
	myClass.loop_function()
	
	print("数组遍历--------------------------------")	
	myClass.arrayIterator()
	
	print("字典遍历--------------------------------")	
	myClass.dictionaryIterator()
	
	print("访问常量--------------------------------")
	var answer = MyClass.ANSWER
	print("访问const变量，类似于static变量：" + str(answer))
	print("访问静态变量--------------------------------")
	print("访问static变量，类似于static变量：" + str(MyClass.my_static_field))
	print("调用静态方法--------------------------------")
	print("调用静态方法：" + str(MyClass.getAnswer()))

	print("内部类测试--------------------------------")
	myClass.innerClassTest()
	pass
