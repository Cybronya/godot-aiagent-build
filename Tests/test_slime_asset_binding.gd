extends SceneTree
## Scene Asset Binding 运行期回归测试（手工维护，Phase 1.7）。
##
## 验证「Asset Binding -> Scene Composer -> 真实 Godot 运行」这一段：
##   1. 生成的资源节点确实存在，且持有可加载的资源（SpriteFrames / AudioStream）
##   2. 绑定声明的角色（idle/move/attack/hurt）在资源里真实存在
##   3. 资源节点没有引入脚本（Scene 只负责组合，不写行为）
##
## 契约来源：
##   .ai/context/asset_binding_schema.yaml
##   .ai/context/asset_bindings/slime_enemy.yaml（由 bind_assets.py 生成）
##
## 用法：godot --headless --path . -s res://Tests/test_slime_asset_binding.gd
## 全部通过输出 PASS 并退出 0；任一失败输出 FAIL 并退出 1。

const SCENE_PATH := "res://Scenes/SlimeEnemy.tscn"
const VISUAL_NODE := "SlimeAnim"
const SFX_NODE := "SlimeHurtSfx"
const REQUIRED_ROLES := ["idle", "move", "attack", "hurt"]

var _failures: PackedStringArray = []


func _initialize() -> void:
	_check_sprite_frames_resource()
	_check_scene_binding()
	_report()


func _check_sprite_frames_resource() -> void:
	# 资源本身必须可加载，且包含绑定声明的全部角色（与 binding 文档同源）
	var frames: SpriteFrames = load("res://Assets/characters/enemy/slime/slime_frames.tres")
	if frames == null:
		_failures.append("Asset Load: slime_frames.tres 加载失败")
		return
	var names := frames.get_animation_names()
	for role in REQUIRED_ROLES:
		if not names.has(role):
			_failures.append("Missing animation %s in slime_frames.tres (got %s)" % [role, names])
		if frames.get_frame_count(role) <= 0:
			_failures.append("Animation %s has no frames" % role)
		else:
			# 帧贴图必须真的被 Godot 导入并可加载
			for index in frames.get_frame_count(role):
				var texture: Texture2D = frames.get_frame_texture(role, index)
				if texture == null:
					_failures.append("Animation %s frame %d texture is null" % [role, index])
					break


func _check_scene_binding() -> void:
	if not ResourceLoader.exists(SCENE_PATH):
		_failures.append("Scene Load: %s 不存在" % SCENE_PATH)
		return
	var packed: PackedScene = load(SCENE_PATH)
	if packed == null:
		_failures.append("Scene Load: %s 加载失败" % SCENE_PATH)
		return
	var entity: Node = packed.instantiate()

	# 1. 视觉资源节点
	var visual := entity.get_node_or_null(VISUAL_NODE)
	if visual == null:
		_failures.append("Missing asset node: %s" % VISUAL_NODE)
	elif not (visual is AnimatedSprite2D):
		_failures.append("Asset node %s is not AnimatedSprite2D" % VISUAL_NODE)
	else:
		if visual.sprite_frames == null:
			_failures.append("Asset node %s has no sprite_frames" % VISUAL_NODE)
		else:
			var names: PackedStringArray = visual.sprite_frames.get_animation_names()
			for role in REQUIRED_ROLES:
				if not names.has(role):
					_failures.append("Bound SpriteFrames lacks animation %s" % role)
		if String(visual.animation) != "idle":
			_failures.append("Asset node %s default animation should be idle, got %s"
				% [VISUAL_NODE, visual.animation])
		if visual.get_script() != null:
			_failures.append("Asset node %s must not own a script (scene composes only)" % VISUAL_NODE)

	# 2. 音频资源节点
	var sfx := entity.get_node_or_null(SFX_NODE)
	if sfx == null:
		_failures.append("Missing asset node: %s" % SFX_NODE)
	elif not (sfx is AudioStreamPlayer):
		_failures.append("Asset node %s is not AudioStreamPlayer" % SFX_NODE)
	elif sfx.stream == null:
		_failures.append("Asset node %s has no stream" % SFX_NODE)

	# 3. 资源节点与 Feature 组件共存，且 Scene 不给根挂脚本
	if entity.get_script() != null:
		_failures.append("Root node must not own a script (scene composes only)")
	for feature_node in ["Health", "ContactDamage", "ChaseMovement"]:
		if entity.get_node_or_null(feature_node) == null:
			_failures.append("Missing Feature node: %s" % feature_node)

	entity.free()


func _report() -> void:
	if _failures.is_empty():
		print("PASS: SlimeEnemy 资源绑定运行期验证通过")
		quit(0)
	else:
		for failure in _failures:
			printerr("FAIL: " + failure)
		quit(1)
