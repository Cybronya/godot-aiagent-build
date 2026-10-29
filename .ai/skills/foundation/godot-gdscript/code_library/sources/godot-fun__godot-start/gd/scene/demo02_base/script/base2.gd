extends Node2D

const CNode = preload("res://scene/demo02_base/script/CNode.gd")
const CReference = preload("res://scene/demo02_base/script/CReference.gd")

# monitor初探
func _ready():
	#nodeTest()
	#nodeFreeTest()
	#nodeQueueFreeTest()
	#referenceTest()
	#referenceFreeTest()
	referencUnreferenceTest()
	pass


func nodeTest():
	for i in range(10000):
		var _instance = CNode.new()


func nodeFreeTest():
	for i in range(10000):
		var instance = CNode.new()
		instance.free()

# queue_free效率更高
func nodeQueueFreeTest():
	for i in range(10000):
		var instance = CNode.new()
		instance.queue_free()
		
func referenceTest():
	for i in range(10000):
		var _instance = CReference.new()


func referenceFreeTest():
	for i in range(10000):
		var instance = CReference.new()
		instance.free()

# 4.x主动调用unreference会导致没有被回收对象
func referencUnreferenceTest():
	for i in range(10000):
		var instance = CReference.new()
		instance.reference()
		instance.unreference()
