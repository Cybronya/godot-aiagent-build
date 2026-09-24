class_name PlayerController
extends CharacterBody2D
## 角色控制器：读取方向输入动作，驱动 CharacterBody2D 移动。
##
## 本脚本只负责「输入 → 速度 → 移动」这一条职责链；
## 外观与碰撞形状由场景结构承担，动画等后续功能应拆分为独立组件。
## 输入动作名通过导出属性自定义，多个角色可复用同一移动逻辑。

@export var speed := 220.0
@export var action_left := "move_left"
@export var action_right := "move_right"
@export var action_up := "move_up"
@export var action_down := "move_down"


func _physics_process(_delta: float) -> void:
	var direction := Input.get_vector(action_left, action_right, action_up, action_down)
	velocity = direction * speed
	move_and_slide()
