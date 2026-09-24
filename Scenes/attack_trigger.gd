extends Node
## 游戏侧伤害触发器：监听攻击动作，对配置的目标 Health 调用既有接口。
##
## 本脚本属于游戏组合层，不是 Feature：目标与动作由场景配置决定，
## 受击与死亡规则完全复用 health Feature，本脚本不实现任何生命值逻辑。

@export var attack_action := "p1_attack"
@export var target_health_path: NodePath
@export var damage := 1

var _target: Health


func _ready() -> void:
	_target = get_node(target_health_path)


func _physics_process(_delta: float) -> void:
	if _target != null and Input.is_action_just_pressed(attack_action):
		_target.take_damage(damage)
