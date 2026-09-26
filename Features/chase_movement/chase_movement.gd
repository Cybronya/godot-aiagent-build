class_name ChaseMovement
extends CharacterBody2D
## 追击移动组件：每物理帧朝目标节点的当前位置移动。
##
## 与 player_controller（读输入）互为镜像：本组件不读任何输入，只朝 target_path
## 指向的节点移动，移动职责单一。目标缺失或已被释放时停止移动，不报错。
## 必须作为 CharacterBody2D 实体的根脚本使用（与 PlayerController 相同的根脚本模式）。

@export var speed := 80.0
@export var target_path: NodePath

var _target: Node2D


func _ready() -> void:
	if not target_path.is_empty():
		_target = get_node_or_null(target_path) as Node2D


func _physics_process(_delta: float) -> void:
	if _target == null or not is_instance_valid(_target):
		_target = _resolve_target()
		if _target == null:
			velocity = Vector2.ZERO
			return
	velocity = (_target.global_position - global_position).normalized() * speed
	move_and_slide()


## 惰性解析目标：无论 target_path 在入树前还是入树后配置，首次物理帧都会生效；
## 目标被释放后按路径重新解析，路径为空或不可达则保持静止。
func _resolve_target() -> Node2D:
	if target_path.is_empty():
		return null
	return get_node_or_null(target_path) as Node2D
