extends Node2D


func _ready():
	# new一个Sprite节点
	var sprite = Sprite2D.new()
	# 设置图片
	var icon = preload("res://icon.svg")
	sprite.set_texture(icon)
	
	# 修改名称
	sprite.name = "mynode"
	
	# 修改坐标居中
	sprite.position.x = 200
	sprite.position.y = 200
	
	# 添加到当前的场景中
	add_child(sprite)
	pass
	


func _process(delta):
	var sprite: Sprite2D = $mynode
	sprite.rotate(0.1)
	pass
