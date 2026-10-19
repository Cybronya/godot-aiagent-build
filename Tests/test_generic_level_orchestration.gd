extends SceneTree
## Phase 1.14 通用关卡编排管线验证（G1–G13，真实 Godot 运行）。
##
## 覆盖（对应任务书编号）：
##   G1  通用编排组件（Orchestration/）不依赖 TimedCombatArena 专属节点路径：
##       静态（无 NodePath / 无场景名引用，剔除注释后检查）+ 运行时（程序化合成宿主
##       驱动完整波次→出口→胜利闭环，宿主不是任何 .tscn 场景）。
##   G2  TimedCombatArena 迁移后行为与 Phase 1.13 一致（发布场景 + 发布配置全清单）。
##   G3  第二个场景（SurvivalArena）确实调用同一套通用编排实现（同一脚本、holdout 模式、
##       配置驱动生成节奏与胜利）。
##   G4  第二个场景核心原有玩法不回归（持续生成/精英延迟/上限/生存胜利/玩家失败/
##       拾取物与陷阱保留）。
##   G5  首波未完成时不启动第二波。
##   G6  必需波次全部完成前出口不提前开启。
##   G7  全部波次完成后按配置启用出口。
##   G8  重复死亡信号不重复计数。
##   G9  胜利事件只触发一次。
##   G10 显式无效配置被拒绝，不发生静默回退（waves 与 holdout 两类规则集）。
##   G11 缺失可选配置时旧场景兼容路径正常（手写 waves / 遗留导出 / v1 配置 / 缺省块）。
##   G12 手写 waves 兼容路径继续可用（与 Phase 1.13 D 段同强断言）。
##   G13 运行时错误能定位到关卡配置、错误字段、消费场景与失败编排阶段。
##
## 用法：godot --headless --path . -s res://Tests/test_generic_level_orchestration.gd
## 全部通过输出 PASS 并退出 0；任一失败输出 FAIL 并退出 1。

const ARENA_SCENE := "res://Scenes/TimedCombatArena.tscn"
const SURVIVAL_SCENE := "res://Scenes/SurvivalArena.tscn"
const ENEMY_SCENE := "res://Scenes/Enemy.tscn"
const ELITE_SCENE := "res://Scenes/EliteEnemy.tscn"
const PICKUP_SCENE := "res://Features/heal_pickup/HealPickup.tscn"
const PLAYER_SCENE := "res://Features/player_movement/Player.tscn"
const DOOR_SCENE := "res://Features/openable_door/OpenableDoor.tscn"
const ORCHESTRATOR_SCRIPT := "res://Orchestration/level_orchestrator.gd"
const CONFIG_SCRIPT := "res://Orchestration/level_config.gd"
const ARENA_ADAPTER := "res://Scenes/timed_combat_arena.gd"
const SURVIVAL_ADAPTER := "res://Scenes/survival_arena.gd"
const SHIPPED_LEVEL := "res://Levels/timed_combat_arena.json"
const SHIPPED_SURVIVAL := "res://Levels/survival_arena.json"

## Phase 1.33（F4-B）：本运行专属目录。14 个临时关卡配置不再写入共享的 `res://Levels`，
## 而是落在 `.ai/tmp/runs/<pid>-<16 位十六进制随机后缀，与 Python run_workspace 同一契约>/`；只有「本运行写入且内容未变」的资源才允许删除。
var _run_dir := _make_run_dir()
var TEMP_WAVES := _run_dir + "/E2eGenericWavesTest.json"          # 2 波 2/3（G5–G7）
var TEMP_HOLDOUT := _run_dir + "/E2eGenericHoldoutTest.json"      # 短时长生存（G3/G4）
var TEMP_INVALID_COUNT := _run_dir + "/E2eGenericInvalidCount.json"
var TEMP_INVALID_ENTITY := _run_dir + "/E2eGenericInvalidEntity.json"
var TEMP_INVALID_EXIT := _run_dir + "/E2eGenericInvalidExit.json"
var TEMP_INVALID_VICTORY := _run_dir + "/E2eGenericInvalidVictory.json"
var TEMP_HOLDOUT_WITH_WAVES := _run_dir + "/E2eGenericHoldoutWaves.json"
var TEMP_HOLDOUT_NO_BLOCK := _run_dir + "/E2eGenericHoldoutNoBlock.json"
var TEMP_HOLDOUT_BAD_SPAWN := _run_dir + "/E2eGenericHoldoutBadSpawn.json"
var TEMP_V1_HOLDOUT := _run_dir + "/E2eGenericV1Holdout.json"
var TEMP_V1_LEVEL := _run_dir + "/E2eGenericV1Level.json"          # 遗留 v1 waves 配置
var TEMP_NO_OPTIONAL := _run_dir + "/E2eGenericNoOptional.json"   # 缺 exit/victory 选填块
var TEMP_MISSING_SCENE := _run_dir + "/E2eGenericMissingScene.json"
var TEMP_MISSING_FILE := _run_dir + "/E2eGenericDoesNotExist.json"
var _owned: Dictionary = {}

const ATTACK_ACTION := "p1_attack"
const MOVE_ACTION := "move_right"
const EXIT_BUDGET := 300
const EXIT_START := Vector2(560, 0)

var _failures: PackedStringArray = []
var _finish_events: Array = []
var _temp_files: PackedStringArray = [
    TEMP_WAVES, TEMP_HOLDOUT, TEMP_INVALID_COUNT, TEMP_INVALID_ENTITY,
    TEMP_INVALID_EXIT, TEMP_INVALID_VICTORY, TEMP_HOLDOUT_WITH_WAVES,
    TEMP_HOLDOUT_NO_BLOCK, TEMP_HOLDOUT_BAD_SPAWN, TEMP_V1_HOLDOUT,
    TEMP_V1_LEVEL, TEMP_NO_OPTIONAL, TEMP_MISSING_SCENE, TEMP_MISSING_FILE,
]


func _initialize() -> void:
    await _case_g1_generic_components()
    await _case_g2_arena_parity()
    await _case_g3_g4_second_scene()
    await _case_g5_g6_g7_wave_and_exit_gates()
    await _case_g8_death_idempotent()
    await _case_g9_victory_once()
    await _case_g10_invalid_configs_rejected()
    await _case_g11_legacy_compat()
    await _case_g12_legacy_waves_compat()
    await _case_g13_diagnostics()
    _cleanup()
    _report()


# ---------- G1：通用编排组件不依赖 TimedCombatArena 专属节点路径 ----------


func _case_g1_generic_components() -> void:
    # 静态：剔除注释后，通用组件不得出现任何场景名 / 硬编码节点路径
    for path in [ORCHESTRATOR_SCRIPT, CONFIG_SCRIPT]:
        var code := _code_without_comments(_read(path))
        for forbidden in ["TimedCombatArena", "timed_combat_arena", "SurvivalArena",
                "survival_arena", "NodePath(", "$Player", "$Entities", "Mechanism", "HUD/"]:
            if code.contains(forbidden):
                _fail("G1: 通用组件 %s 的代码不得依赖专属引用 %s" % [path, forbidden])

    # 运行时：程序化合成宿主（不是任何 .tscn 场景）驱动完整 波次→出口→胜利 闭环
    var host := Node2D.new()
    host.name = "GenericOrchestrationHost"
    var player: CharacterBody2D = load(PLAYER_SCENE).instantiate()
    player.add_to_group("players")
    var entities := Node2D.new()
    entities.name = "Entities"
    var door: StaticBody2D = load(DOOR_SCENE).instantiate()
    door.position = Vector2(660, 0)
    var zone := Area2D.new()
    zone.name = "ExitZone"
    zone.position = Vector2(720, 0)
    var zone_shape := CollisionShape2D.new()
    var rect := RectangleShape2D.new()
    rect.size = Vector2(140, 260)
    zone_shape.shape = rect
    zone.add_child(zone_shape)
    host.add_child(player)
    host.add_child(entities)
    host.add_child(door)
    host.add_child(zone)
    root.add_child(host)
    await process_frame
    if host.scene_file_path != "":
        _fail("G1: 合成宿主不应来自打包场景（实际 %s）" % host.scene_file_path)

    var orchestrator := LevelOrchestrator.new()
    host.add_child(orchestrator)
    orchestrator.player = player
    orchestrator.entities = entities
    orchestrator.exit_door = door
    orchestrator.exit_zone = zone
    orchestrator.spawn_offset = func() -> Vector2: return Vector2(-400, 0)
    orchestrator.finished.connect(_on_finished)
    if not _write_json(TEMP_WAVES, _base_config("generic_host_level", [
            _wave("wave_1", 1)])):
        _fail("G1: 无法写入临时配置 %s" % TEMP_WAVES)
        return
    if not orchestrator.apply_config(LevelConfig.from_file(TEMP_WAVES)):
        _fail("G1: 合成宿主应接受合法配置，实际 %s" % str(orchestrator.get_config_errors()))
        return
    orchestrator.start()
    if orchestrator.alive_count != 1:
        _fail("G1: 配置声明 1 个敌人，合成宿主生成 %d 个" % orchestrator.alive_count)
    var enemies := _live_enemies(host)
    if enemies.size() != 1:
        _fail("G1: 合成宿主应生成 1 个敌人节点，实际 %d" % enemies.size())
    else:
        var enemy_health: Health = enemies[0].get_node("Health")
        enemy_health.take_damage(9999)
    await process_frame
    if not door.is_open():
        _fail("G1: 合成宿主中清空唯一波次后出口应开启（配置 exit=all_waves_cleared）")
    if orchestrator.state != LevelOrchestrator.State.Playing:
        _fail("G1: 出口开启但玩家未进入出口区时应仍为 Playing")
    player.global_position = EXIT_START
    await physics_frame
    Input.action_press(MOVE_ACTION)
    for _i: int in EXIT_BUDGET:
        if orchestrator.state == LevelOrchestrator.State.Completed:
            break
        await physics_frame
    Input.action_release(MOVE_ACTION)
    if orchestrator.state != LevelOrchestrator.State.Completed:
        _fail("G1: 合成宿主中玩家走进出口区后应进入 Completed，实际 %d" % int(orchestrator.state))
    if _finish_events != [true]:
        _fail("G1: 合成宿主的胜负事件应恰好一次且成功，实际 %s" % str(_finish_events))
    _finish_events.clear()
    host.queue_free()
    await process_frame


# ---------- G2：TimedCombatArena 迁移后行为与 Phase 1.13 一致 ----------


func _case_g2_arena_parity() -> void:
    var arena := await _load_arena(SHIPPED_LEVEL)
    if arena == null:
        return
    var door: StaticBody2D = arena.get_node("Mechanism/ExitDoor")
    var player: CharacterBody2D = arena.get_node("Player")
    # 发布配置：3 波（3 / 3 / 5），首波 3 个普通敌人
    if arena.waves.size() != 3:
        _fail("G2: 发布配置声明 3 波，运行时读到 %d 波" % arena.waves.size())
    if arena.alive_count != 3:
        _fail("G2: 发布配置首波 3 个敌人，运行时生成 %d 个" % arena.alive_count)
    if door.is_open():
        _fail("G2: 出口门初始应关闭")
    # 逐波清空：每波清除前出口保持关闭，清除后按配置生成下一波
    for wave_no in arena.waves.size():
        var enemies := _live_enemies(arena)
        for enemy in enemies:
            if is_instance_valid(enemy):
                enemy.get_node("Health").take_damage(9999)
            await process_frame
            if _live_enemies(arena).size() > 0 and door.is_open():
                _fail("G2: 第 %d 波仍有敌人存活时出口不应打开" % (wave_no + 1))
        if wave_no + 1 < arena.waves.size():
            if arena.wave_index != wave_no + 1:
                _fail("G2: 第 %d 波清空后应进入第 %d 波，实际 index %d"
                    % [wave_no + 1, wave_no + 2, arena.wave_index])
    if not door.is_open():
        _fail("G2: 全部必需波次清空后出口应开启")
    if arena.state != arena.State.Playing:
        _fail("G2: 出口开启但玩家未进出口区时应仍为 Playing，实际 %d" % int(arena.state))
    # 玩家进入出口 → Completed，胜负事件恰好一次
    player.global_position = EXIT_START
    await physics_frame
    Input.action_press(MOVE_ACTION)
    for _i: int in EXIT_BUDGET:
        if arena.state == arena.State.Completed:
            break
        await physics_frame
    Input.action_release(MOVE_ACTION)
    if arena.state != arena.State.Completed:
        _fail("G2: 玩家进入出口后应进入 Completed，实际 %d" % int(arena.state))
    if _finish_events != [true]:
        _fail("G2: 胜负事件应恰好一次且 success=true，实际 %s" % str(_finish_events))
    _finish_events.clear()
    arena.queue_free()
    await process_frame
    # 无效配置不得生成敌人或误判胜利（发布场景 + 临时非法配置）
    if not _write_json(TEMP_INVALID_COUNT, _with_invalid_count(_base_config("g2_invalid", [
            _wave("wave_1", 2)]))):
        _fail("G2: 无法写入临时配置 %s" % TEMP_INVALID_COUNT)
        return
    var refused := await _load_arena(TEMP_INVALID_COUNT)
    if refused == null:
        return
    if refused.state != refused.State.Failed:
        _fail("G2: 无效配置应拒绝开始（state=Failed），实际 %d" % int(refused.state))
    if refused.alive_count != 0 or _live_enemies(refused).size() != 0:
        _fail("G2: 无效配置不得生成敌人（alive=%d 存活 %d）"
            % [refused.alive_count, _live_enemies(refused).size()])
    if refused.waves.size() != 0:
        _fail("G2: 无效配置不得静默回退到场景内数据（waves=%d）" % refused.waves.size())
    refused.queue_free()
    await process_frame


# ---------- G3/G4：第二个场景复用同一套通用编排实现且核心玩法不回归 ----------


func _case_g3_g4_second_scene() -> void:
    # 静态：两个适配层都接线到同一通用编排实现
    var arena_code := _read(ARENA_ADAPTER)
    var survival_code := _read(SURVIVAL_ADAPTER)
    if not arena_code.contains("LevelOrchestrator") or not survival_code.contains("LevelOrchestrator"):
        _fail("G3: 两个适配层都应引用 LevelOrchestrator")
    if not survival_code.contains("holdout"):
        _fail("G3: SurvivalArena 适配层应使用 holdout 编排模式")

    # 运行时：两个场景的编排器是同一脚本；SurvivalArena 走 holdout 模式
    var arena := await _load_arena(SHIPPED_LEVEL)
    var survival := await _load_survival(SHIPPED_SURVIVAL)
    if arena == null or survival == null:
        return
    var arena_orchestrator := _find_orchestrator(arena)
    var survival_orchestrator := _find_orchestrator(survival)
    if arena_orchestrator == null or survival_orchestrator == null:
        _fail("G3: 两个场景都应挂载 LevelOrchestrator")
        return
    if arena_orchestrator.get_script().resource_path != survival_orchestrator.get_script().resource_path:
        _fail("G3: 两个场景应使用同一编排脚本，实际 %s vs %s"
            % [arena_orchestrator.get_script().resource_path,
               survival_orchestrator.get_script().resource_path])
    if str(arena_orchestrator.get_mode()) != "waves":
        _fail("G3: TimedCombatArena 应处于 waves 模式，实际 %s" % arena_orchestrator.get_mode())
    if str(survival_orchestrator.get_mode()) != "holdout":
        _fail("G3: SurvivalArena 应处于 holdout 模式，实际 %s" % survival_orchestrator.get_mode())
    if not survival.get_config_errors().is_empty():
        _fail("G3: 发布生存配置应被接受，实际 %s" % str(survival.get_config_errors()))
    # 场景专属玩法保留：开局拾取物与陷阱仍在
    if _count_scene(survival, PICKUP_SCENE) != 1:
        _fail("G4: 开局应仍生成 1 个拾取物（场景专属），实际 %d" % _count_scene(survival, PICKUP_SCENE))
    if survival.get_node("Traps").get_child_count() != 3:
        _fail("G4: 场景内 3 个陷阱应保留，实际 %d" % survival.get_node("Traps").get_child_count())
    arena.queue_free()
    survival.queue_free()
    await process_frame

    # 配置驱动：临时 holdout 配置（生存 1.0s / 敌间隔 0.2s / 精英延迟 0.5s / 总上限 3）
    var config := _base_holdout_config("generic_holdout_level", 1.0, 3, [
        {"entity": "enemy", "interval": 0.2},
        {"entity": "elite_enemy", "delay": 0.5, "interval": 0.3, "max_alive": 1},
    ])
    if not _write_json(TEMP_HOLDOUT, config):
        _fail("G3: 无法写入临时配置 %s" % TEMP_HOLDOUT)
        return
    var fast := await _load_survival(TEMP_HOLDOUT)
    if fast == null:
        return
    # 生成节奏来自配置：0.3s 时已有普通敌人、精英未到延迟
    await _wait_physics(18)
    if fast.alive_count < 1:
        _fail("G3: 配置 interval=0.2，0.3s 时应已生成敌人，实际 %d" % fast.alive_count)
    if _count_scene(fast, ELITE_SCENE) != 0:
        _fail("G4: 精英延迟 0.5s 未到，不应生成精英，实际 %d" % _count_scene(fast, ELITE_SCENE))
    # 精英延迟来自配置：0.7s 时精英出现且受 per-schedule 上限约束
    await _wait_physics(24)
    if _count_scene(fast, ELITE_SCENE) != 1:
        _fail("G4: 精英延迟 0.5s 后应生成 1 个精英，实际 %d" % _count_scene(fast, ELITE_SCENE))
    # 总上限来自配置：holdout.max_alive=3，同时存活永不超过 3
    var max_seen: int = fast.alive_count
    for _i: int in 24:
        max_seen = maxi(max_seen, fast.alive_count)
        await physics_frame
    if max_seen > 3:
        _fail("G4: 总上限 max_alive=3 被突破，实测峰值 %d" % max_seen)
    if fast.alive_count != 3:
        _fail("G4: 达到总上限后存活应稳定为 3，实际 %d" % fast.alive_count)
    # 生存胜利来自配置：survival_duration=1.0 → Won，胜负事件恰好一次
    var won := false
    for _i: int in 30:
        if fast.state == fast.State.Won:
            won = true
            break
        await physics_frame
    if not won:
        _fail("G3: 生存到配置时长后应胜利（Won），实际 state=%d alive=%d"
            % [int(fast.state), fast.alive_count])
    if _finish_events != [true]:
        _fail("G3: 生存胜利事件应恰好一次且成功，实际 %s" % str(_finish_events))
    _finish_events.clear()
    fast.queue_free()
    await process_frame

    # 玩家死亡 → Lost（原有失败路径不回归）
    var doomed := await _load_survival(TEMP_HOLDOUT)
    if doomed == null:
        return
    doomed.get_node("Player/Health").take_damage(9999)
    await process_frame
    if doomed.state != doomed.State.Lost:
        _fail("G4: 玩家死亡后应进入 Lost，实际 %d" % int(doomed.state))
    if not doomed.get_node("HUD/StatusLabel").text.contains("死亡"):
        _fail("G4: 死亡后状态栏应提示死亡，实际 %s" % doomed.get_node("HUD/StatusLabel").text)
    doomed.queue_free()
    await process_frame


# ---------- G5/G6/G7：波次门控与出口门控 ----------


func _case_g5_g6_g7_wave_and_exit_gates() -> void:
    if not _write_json(TEMP_WAVES, _base_config("generic_waves_level", [
            _wave("wave_1", 2), _wave("wave_2", 3)])):
        _fail("G5: 无法写入临时配置 %s" % TEMP_WAVES)
        return
    var arena := await _load_arena(TEMP_WAVES)
    if arena == null:
        return
    var door: StaticBody2D = arena.get_node("Mechanism/ExitDoor")
    var player: CharacterBody2D = arena.get_node("Player")
    # G5：首波未完成时不启动第二波
    if arena.waves.size() != 2 or arena.alive_count != 2:
        _fail("G5: 配置声明 2 波且首波 2 个敌人，实际 waves=%d alive=%d"
            % [arena.waves.size(), arena.alive_count])
    var wave1 := _live_enemies(arena)
    wave1[0].get_node("Health").take_damage(9999)
    await process_frame
    if arena.alive_count != 1:
        _fail("G5: 击杀 1 个敌人后存活应为 1，实际 %d" % arena.alive_count)
    if arena.wave_index != 0 or _live_enemies(arena).size() != 1:
        _fail("G5: 首波未清空时不应生成第二波（index=%d 存活 %d）"
            % [arena.wave_index, _live_enemies(arena).size()])
    # G6：第二波仍有存活敌人时出口保持关闭（清首波 → 生成第二波 → 逐个击杀复查）
    wave1[1].get_node("Health").take_damage(9999)
    await process_frame
    if arena.wave_index != 1:
        _fail("G5: 首波清空后应进入第二波（index 1），实际 %d" % arena.wave_index)
    if arena.alive_count != 3:
        _fail("G5: 第二波应按配置生成 3 个敌人，实际 %d" % arena.alive_count)
    var wave2 := _live_enemies(arena)
    if wave2.size() != 3:
        _fail("G5: 第二波应生成 3 个敌人节点，实际 %d" % wave2.size())
    for enemy in wave2:
        if not is_instance_valid(enemy):
            continue
        if door.is_open():
            _fail("G6: 第二波清除途中出口不应打开")
        enemy.get_node("Health").take_damage(9999)
        await process_frame
    # G7：全部波次完成后按配置启用出口（状态仍 Playing）
    if not door.is_open():
        _fail("G7: 全部必需波次清空后出口应开启（alive=%d index=%d）"
            % [arena.alive_count, arena.wave_index])
    if arena.state != arena.State.Playing:
        _fail("G7: 出口开启但玩家未进出口区时应仍为 Playing，实际 %d" % int(arena.state))
    # 走入出口 → 完成（确认 G7 的出口真实可用）
    player.global_position = EXIT_START
    await physics_frame
    Input.action_press(MOVE_ACTION)
    for _i: int in EXIT_BUDGET:
        if arena.state == arena.State.Completed:
            break
        await physics_frame
    Input.action_release(MOVE_ACTION)
    if arena.state != arena.State.Completed:
        _fail("G7: 玩家走进出口区后应进入 Completed，实际 %d" % int(arena.state))
    _finish_events.clear()
    arena.queue_free()
    await process_frame


# ---------- G8：重复死亡信号不重复计数 ----------


func _case_g8_death_idempotent() -> void:
    if not _write_json(TEMP_WAVES, _base_config("generic_idempotent_level", [
            _wave("wave_1", 2)])):
        _fail("G8: 无法写入临时配置 %s" % TEMP_WAVES)
        return
    var arena := await _load_arena(TEMP_WAVES)
    if arena == null:
        return
    var enemies := _live_enemies(arena)
    if enemies.size() != 2:
        _fail("G8: 配置声明 2 个敌人，实际 %d" % enemies.size())
        arena.queue_free()
        await process_frame
        return
    var victim_health: Health = enemies[0].get_node("Health")
    victim_health.take_damage(9999)          # 真实伤害接口 → died 一次
    var alive_after_death: int = arena.alive_count
    var index_after_death: int = arena.wave_index
    victim_health.died.emit()                # 同一帧重复通知（受控负向输入）
    if arena.alive_count != alive_after_death:
        _fail("G8: 重复 died 通知造成了重复计数（%d -> %d）"
            % [alive_after_death, arena.alive_count])
    if arena.wave_index != index_after_death:
        _fail("G8: 重复 died 通知造成了重复推进（index %d -> %d）"
            % [index_after_death, arena.wave_index])
    if alive_after_death != 1:
        _fail("G8: 一次有效死亡应使计数恰好减一，实际 %d" % alive_after_death)
    arena.queue_free()
    await process_frame


# ---------- G9：胜利事件只触发一次 ----------


func _case_g9_victory_once() -> void:
    if not _write_json(TEMP_WAVES, _base_config("generic_victory_once_level", [
            _wave("wave_1", 1)])):
        _fail("G9: 无法写入临时配置 %s" % TEMP_WAVES)
        return
    var arena := await _load_arena(TEMP_WAVES)
    if arena == null:
        return
    var player: CharacterBody2D = arena.get_node("Player")
    var enemies := _live_enemies(arena)
    enemies[0].get_node("Health").take_damage(9999)
    await process_frame
    player.global_position = EXIT_START
    await physics_frame
    Input.action_press(MOVE_ACTION)
    for _i: int in EXIT_BUDGET:
        if arena.state == arena.State.Completed:
            break
        await physics_frame
    Input.action_release(MOVE_ACTION)
    if arena.state != arena.State.Completed:
        _fail("G9: 玩家应能走入出口区完成挑战，实际 %d" % int(arena.state))
    # 完成后的重复触发路径：再次进入出口区 / 玩家死亡 / 波次死亡都不得再产生事件
    player.global_position = Vector2(0, 300)
    await physics_frame
    player.global_position = EXIT_START
    await physics_frame
    for _i: int in 20:
        await physics_frame
    player.get_node("Health").take_damage(9999)
    await process_frame
    if _finish_events != [true]:
        _fail("G9: 胜利事件应只触发一次，实际 %s" % str(_finish_events))
    _finish_events.clear()
    arena.queue_free()
    await process_frame


# ---------- G10：显式无效配置被拒绝，不发生静默回退 ----------


func _case_g10_invalid_configs_rejected() -> void:
    var base := _base_config("generic_invalid_level", [_wave("wave_1", 2)])
    var cases := [
        {
            "path": TEMP_INVALID_COUNT, "config": _with_invalid_count(base),
            "field": "count", "label": "非法数量",
        },
        {
            "path": TEMP_INVALID_ENTITY,
            "config": _with_mutation(base, func(level: Dictionary) -> void:
                level["waves"][0]["entries"][0]["entity"] = "ghost"),
            "field": "entity", "label": "未声明实体",
        },
        {
            "path": TEMP_INVALID_EXIT,
            "config": _with_mutation(base, func(level: Dictionary) -> void:
                level["exit"] = {"unlock_when": "whenever"}),
            "field": "exit.unlock_when", "label": "非法出口规则",
        },
        {
            "path": TEMP_INVALID_VICTORY,
            "config": _with_mutation(base, func(level: Dictionary) -> void:
                level["victory"] = {"condition": "win_the_game"}),
            "field": "victory.condition", "label": "非法胜利条件",
        },
        {
            "path": TEMP_HOLDOUT_WITH_WAVES,
            "config": _with_mutation(_base_holdout_config("generic_holdout_waves", 5.0, 0, [
                    {"entity": "enemy", "interval": 1.0}]),
                func(level: Dictionary) -> void: level["waves"] = [_wave("wave_1", 1)]),
            "field": "waves", "label": "holdout 混入顺序波次",
        },
        {
            "path": TEMP_HOLDOUT_NO_BLOCK,
            "config": _with_mutation(_base_holdout_config("generic_holdout_noblock", 5.0, 0, [
                    {"entity": "enemy", "interval": 1.0}]),
                func(level: Dictionary) -> void: level.erase("holdout")),
            "field": "holdout", "label": "holdout 缺配置块",
        },
        {
            "path": TEMP_HOLDOUT_BAD_SPAWN,
            "config": _with_mutation(_base_holdout_config("generic_holdout_badspawn", 5.0, 0, [
                    {"entity": "enemy", "interval": 1.0}]),
                func(level: Dictionary) -> void:
                    level["holdout"]["spawns"][0]["count"] = 3),
            "field": "count", "label": "holdout 调度误用 count",
        },
        {
            "path": TEMP_V1_HOLDOUT,
            "config": _with_mutation(_base_holdout_config("generic_v1_holdout", 5.0, 0, [
                    {"entity": "enemy", "interval": 1.0}]),
                func(level: Dictionary) -> void: level["schema"]["version"] = 1),
            "field": "mode", "label": "v1 配置使用 holdout",
        },
    ]
    for case_item in cases:
        var path: String = case_item["path"]
        var level: Dictionary = case_item["config"]
        var field: String = case_item["field"]
        var label: String = case_item["label"]
        if not _write_json(path, level):
            _fail("G10: 无法写入临时配置 %s" % path)
            continue
        var arena := await _load_arena(path)
        if arena == null:
            continue
        var errors: PackedStringArray = arena.get_config_errors()
        if errors.is_empty():
            _fail("G10: %s 必须被运行时拒绝" % label)
        elif not String(errors[0]).contains(field):
            _fail("G10: %s 的错误信息应定位到字段 %s，实际 %s" % [label, field, errors[0]])
        if arena.state != arena.State.Failed:
            _fail("G10: %s 应拒绝开始（state=Failed），实际 %d" % [label, int(arena.state)])
        if arena.alive_count != 0 or _live_enemies(arena).size() != 0:
            _fail("G10: %s 不得生成任何敌人（alive=%d 存活 %d）"
                % [label, arena.alive_count, _live_enemies(arena).size()])
        if arena.waves.size() != 0:
            _fail("G10: %s 不得静默回退到场景内数据（waves=%d）" % [label, arena.waves.size()])
        arena.queue_free()
        await process_frame


# ---------- G11：缺失可选配置时旧场景兼容路径正常 ----------


func _case_g11_legacy_compat() -> void:
    # 11a：TimedCombatArena 无配置路径 + 场景内手写 waves → 原有行为
    var packed: PackedScene = load(ARENA_SCENE)
    var arena: Node2D = packed.instantiate()
    var legacy: Array[Dictionary] = [{
        "enemy_scene": load(ENEMY_SCENE),
        "enemy_count": 1,
        "duration": 30.0,
    }]
    arena.level_config_path = ""
    arena.waves = legacy
    root.add_child(arena)
    await process_frame
    if arena.alive_count != 1:
        _fail("G11: 手写 waves 兼容路径应生成 1 个敌人，实际 %d" % arena.alive_count)
    if not arena.get_config_errors().is_empty():
        _fail("G11: 未配置 level_config_path 时不应报配置错误")
    arena.queue_free()
    await process_frame

    # 11b：v1（遗留版本）waves 配置仍被接受并完整运行
    if not _write_json(TEMP_V1_LEVEL, _base_config_v1("generic_v1_level", [_wave("wave_1", 1)])):
        _fail("G11: 无法写入临时配置 %s" % TEMP_V1_LEVEL)
    else:
        var legacy_v1 := await _load_arena(TEMP_V1_LEVEL)
        if legacy_v1 != null:
            if not legacy_v1.get_config_errors().is_empty():
                _fail("G11: v1 配置应被运行时接受，实际 %s" % str(legacy_v1.get_config_errors()))
            if legacy_v1.alive_count != 1:
                _fail("G11: v1 配置应生成 1 个敌人，实际 %d" % legacy_v1.alive_count)
            legacy_v1.queue_free()
            await process_frame

    # 11c：缺失选填块（exit / victory）→ 按契约默认值运行并走到胜利
    if not _write_json(TEMP_NO_OPTIONAL, _base_config_no_optional("generic_no_optional", [
            _wave("wave_1", 1)])):
        _fail("G11: 无法写入临时配置 %s" % TEMP_NO_OPTIONAL)
    else:
        var defaults := await _load_arena(TEMP_NO_OPTIONAL)
        if defaults != null:
            if defaults.get_exit_unlock_when() != "all_waves_cleared" \
                    or defaults.get_victory_condition() != "exit_reached_after_unlock":
                _fail("G11: 缺失选填块应使用契约默认值，实际 exit=%s victory=%s"
                    % [defaults.get_exit_unlock_when(), defaults.get_victory_condition()])
            var enemies := _live_enemies(defaults)
            if not enemies.is_empty():
                enemies[0].get_node("Health").take_damage(9999)
            await process_frame
            if not defaults.get_node("Mechanism/ExitDoor").is_open():
                _fail("G11: 默认 exit=all_waves_cleared 下清场后出口应开启")
            defaults.queue_free()
            await process_frame

    # 11d：SurvivalArena 无配置路径 + 遗留导出 → 既有生存语义（短时长加速）
    var survival_packed: PackedScene = load(SURVIVAL_SCENE)
    var survival: Node2D = survival_packed.instantiate()
    survival.level_config_path = ""
    survival.survival_duration = 0.5
    survival.spawn_interval = 0.2
    root.add_child(survival)
    await process_frame
    if not survival.get_config_errors().is_empty():
        _fail("G11: 遗留导出通道不应报配置错误，实际 %s" % str(survival.get_config_errors()))
    if _count_scene(survival, PICKUP_SCENE) != 1:
        _fail("G11: 遗留通道开局应生成拾取物，实际 %d" % _count_scene(survival, PICKUP_SCENE))
    var spawned := false
    for _i: int in 24:
        if survival.alive_count >= 1:
            spawned = true
            break
        await physics_frame
    if not spawned:
        _fail("G11: 遗留通道应按 spawn_interval 生成敌人")
    var won := false
    for _i: int in 40:
        if survival.state == survival.State.Won:
            won = true
            break
        await physics_frame
    if not won:
        _fail("G11: 遗留通道生存到时限应胜利，实际 state=%d" % int(survival.state))
    survival.queue_free()
    await process_frame


# ---------- G12：手写 waves 兼容（与 Phase 1.13 D 段同强断言） ----------


func _case_g12_legacy_waves_compat() -> void:
    var packed: PackedScene = load(ARENA_SCENE)
    var arena: Node2D = packed.instantiate()
    var mixed: Array[Dictionary] = [{
        "enemy_scene": load(ENEMY_SCENE),
        "enemy_count": 1,
        "elite_scene": load(ELITE_SCENE),
        "elite_count": 1,
        "duration": 30.0,
    }]
    arena.level_config_path = ""
    arena.waves = mixed
    root.add_child(arena)
    await process_frame
    if arena.alive_count != 2:
        _fail("G12: 手写 waves（普通+精英混编）应生成 2 个敌人，实际 %d" % arena.alive_count)
    var has_elite := false
    for enemy in _live_enemies(arena):
        if String(enemy.scene_file_path) == ELITE_SCENE:
            has_elite = true
    if not has_elite:
        _fail("G12: 手写 waves 的精英条目应生效")
    # 清空 → 单波配置下出口开启（兼容路径的出口/胜利机制不变）
    for enemy in _live_enemies(arena):
        if is_instance_valid(enemy):
            enemy.get_node("Health").take_damage(9999)
    await process_frame
    if not arena.get_node("Mechanism/ExitDoor").is_open():
        _fail("G12: 手写 waves 清空后出口应开启")
    arena.queue_free()
    await process_frame


# ---------- G13：运行时错误能定位到关卡配置及对应阶段 ----------


func _case_g13_diagnostics() -> void:
    if not _write_json(TEMP_INVALID_COUNT, _with_invalid_count(_base_config("g13_invalid", [
            _wave("wave_1", 2)]))):
        _fail("G13: 无法写入临时配置 %s" % TEMP_INVALID_COUNT)
        return
    var arena := await _load_arena(TEMP_INVALID_COUNT)
    if arena == null:
        return
    var diagnostics: Dictionary = arena.get_diagnostics()
    if str(diagnostics.get("stage", "")) != "config_validate":
        _fail("G13: 规则校验失败的阶段应为 config_validate，实际 %s"
            % str(diagnostics.get("stage", "")))
    if str(diagnostics.get("config_path", "")) != TEMP_INVALID_COUNT:
        _fail("G13: 诊断应指向关卡配置文件 %s，实际 %s"
            % [TEMP_INVALID_COUNT, str(diagnostics.get("config_path", ""))])
    if str(diagnostics.get("consumer_scene", "")) != ARENA_SCENE:
        _fail("G13: 诊断应指向消费场景 %s，实际 %s"
            % [ARENA_SCENE, str(diagnostics.get("consumer_scene", ""))])
    var errors: PackedStringArray = arena.get_config_errors()
    if errors.is_empty() or not String(errors[0]).contains(TEMP_INVALID_COUNT) \
            or not String(errors[0]).contains("count"):
        _fail("G13: 错误信息应同时定位配置文件与字段，实际 %s" % str(errors))
    arena.queue_free()
    await process_frame

    # 读取失败（文件不存在）→ 阶段 config_load
    var missing := await _load_arena(TEMP_MISSING_FILE)
    if missing == null:
        return
    var missing_diag: Dictionary = missing.get_diagnostics()
    if str(missing_diag.get("stage", "")) != "config_load":
        _fail("G13: 读取失败的阶段应为 config_load，实际 %s" % str(missing_diag.get("stage", "")))
    var missing_errors: PackedStringArray = missing.get_config_errors()
    if missing_errors.is_empty() or not String(missing_errors[0]).contains(TEMP_MISSING_FILE):
        _fail("G13: 读取失败应定位到配置文件，实际 %s" % str(missing_errors))
    missing.queue_free()
    await process_frame

    # 实体场景缺失 → 错误信息带实体 id 与场景路径（相关实体引用可定位）
    if not _write_json(TEMP_MISSING_SCENE, _with_mutation(
            _base_config("g13_missing_scene", [_wave("wave_1", 1)]),
            func(level: Dictionary) -> void:
                level["entities"]["enemy"]["scene"] = "res://Scenes/NoSuchEnemy.tscn")):
        _fail("G13: 无法写入临时配置 %s" % TEMP_MISSING_SCENE)
        return
    var missing_scene := await _load_arena(TEMP_MISSING_SCENE)
    if missing_scene == null:
        return
    var scene_errors: PackedStringArray = missing_scene.get_config_errors()
    if scene_errors.is_empty() or not String(scene_errors[0]).contains("enemy") \
            or not String(scene_errors[0]).contains("res://Scenes/NoSuchEnemy.tscn"):
        _fail("G13: 实体场景缺失应定位到实体 id 与场景路径，实际 %s" % str(scene_errors))
    missing_scene.queue_free()
    await process_frame


# ---------- 辅助 ----------


func _base_config(level_id: String, waves: Array) -> Dictionary:
    return {
        "schema": {"id": "level_orchestration", "version": 2},
        "level": {"id": level_id, "arena_scene": ARENA_SCENE},
        "mode": "waves",
        "entities": {"enemy": {"scene": ENEMY_SCENE}, "elite_enemy": {"scene": ELITE_SCENE}},
        "waves": waves,
        "exit": {"unlock_when": "all_waves_cleared"},
        "victory": {"condition": "exit_reached_after_unlock"},
    }


func _base_config_v1(level_id: String, waves: Array) -> Dictionary:
    var config := _base_config(level_id, waves)
    config["schema"]["version"] = 1
    config.erase("mode")
    return config


func _base_config_no_optional(level_id: String, waves: Array) -> Dictionary:
    var config := _base_config(level_id, waves)
    config.erase("exit")
    config.erase("victory")
    return config


func _base_holdout_config(level_id: String, survival_duration: float, max_alive: int,
        spawns: Array) -> Dictionary:
    var holdout: Dictionary = {"survival_duration": survival_duration, "spawns": spawns}
    if max_alive > 0:
        holdout["max_alive"] = max_alive
    return {
        "schema": {"id": "level_orchestration", "version": 2},
        "level": {"id": level_id, "arena_scene": SURVIVAL_SCENE},
        "mode": "holdout",
        "entities": {"enemy": {"scene": ENEMY_SCENE}, "elite_enemy": {"scene": ELITE_SCENE}},
        "holdout": holdout,
        "victory": {"condition": "survive_duration"},
    }


func _wave(wave_id: String, count: int) -> Dictionary:
    return {"id": wave_id, "duration": 30.0, "entries": [{"entity": "enemy", "count": count}]}


func _with_mutation(level: Dictionary, mutate: Callable) -> Dictionary:
    var clone: Dictionary = level.duplicate(true)
    mutate.call(clone)
    return clone


func _with_invalid_count(level: Dictionary) -> Dictionary:
    return _with_mutation(level, func(config: Dictionary) -> void:
        config["waves"][0]["entries"][0]["count"] = 0)


func _load_arena(level_path: String = "") -> Node2D:
    var packed: PackedScene = load(ARENA_SCENE)
    if packed == null:
        _fail("无法加载竞技场场景 %s" % ARENA_SCENE)
        return null
    var arena: Node2D = packed.instantiate()
    if not level_path.is_empty():
        arena.level_config_path = level_path      # 必须在 _ready 之前设置
    arena.arena_finished.connect(_on_finished)
    root.add_child(arena)
    await process_frame
    return arena


func _load_survival(level_path: String = "") -> Node2D:
    var packed: PackedScene = load(SURVIVAL_SCENE)
    if packed == null:
        _fail("无法加载生存场景 %s" % SURVIVAL_SCENE)
        return null
    var survival: Node2D = packed.instantiate()
    if not level_path.is_empty():
        survival.level_config_path = level_path  # 必须在 _ready 之前设置
    survival.arena_finished.connect(_on_finished)
    root.add_child(survival)
    await process_frame
    return survival


func _find_orchestrator(scene: Node) -> LevelOrchestrator:
    for child in scene.get_children():
        if child is LevelOrchestrator:
            return child as LevelOrchestrator
    return null


func _live_enemies(host: Node) -> Array[Node]:
    var result: Array[Node] = []
    var entities := host.get_node_or_null("Entities")
    if entities == null:
        return result
    for child in entities.get_children():
        if child.is_in_group("enemies") and is_instance_valid(child) \
                and not child.is_queued_for_deletion():
            result.append(child)
    return result


func _count_scene(host: Node, scene_path: String) -> int:
    var count := 0
    var entities := host.get_node_or_null("Entities")
    if entities == null:
        return count
    for child in entities.get_children():
        if String(child.scene_file_path) == scene_path:
            count += 1
    return count


func _wait_physics(frames: int) -> void:
    for _i: int in frames:
        await physics_frame


## 剔除行注释后的代码文本（静态检查只针对代码，不针对文档注释）
func _code_without_comments(source: String) -> String:
    var kept: PackedStringArray = []
    for line in source.split("\n"):
        var hash := line.find("#")
        if hash >= 0:
            line = line.substr(0, hash)
        kept.append(line)
    return "\n".join(kept)


func _read(path: String) -> String:
    return FileAccess.get_file_as_string(path)


func _on_finished(success: bool) -> void:
    _finish_events.append(success)


func _make_run_dir() -> String:
    var base := "res://.ai/tmp/runs"
    DirAccess.make_dir_recursive_absolute(ProjectSettings.globalize_path(base))
    for attempt in 16:
        var id := "%d-%08x%08x" % [OS.get_process_id(), randi(), randi()]
        var candidate := base + "/" + id
        if DirAccess.dir_exists_absolute(ProjectSettings.globalize_path(candidate)):
            continue                       # 标识冲突：拒绝接管，重试下一个候选
        if DirAccess.make_dir_recursive_absolute(ProjectSettings.globalize_path(candidate)) == OK:
            return candidate
    return ""


func _write_json(path: String, data: Dictionary) -> bool:
    if _run_dir.is_empty():
        return false
    if DirAccess.open(_run_dir) == null:
        if DirAccess.make_dir_recursive_absolute(ProjectSettings.globalize_path(_run_dir)) != OK:
            return false
    var text := JSON.stringify(data, "  ") + "\n"
    var file := FileAccess.open(path, FileAccess.WRITE)
    if file == null:
        return false
    file.store_string(text)
    file.close()
    _owned[path] = text.sha256_text()
    return true


func _cleanup() -> void:
    # 只删「本运行写入且内容未变」的资源；内容不符 = 所有权无法证明 ⇒拒绝并报告。
    for path: String in _owned.keys():
        if not FileAccess.file_exists(path):
            continue
        var current := FileAccess.get_file_as_string(path)
        if current.sha256_text() != _owned[path]:
            _fail("ownership: 内容与本运行写入不一致，拒绝删除 %s" % path)
            continue
        DirAccess.remove_absolute(ProjectSettings.globalize_path(path))
        if FileAccess.file_exists(path):
            _fail("cleanup: 无法删除 %s" % path)
    if not _run_dir.is_empty() and DirAccess.dir_exists_absolute(ProjectSettings.globalize_path(_run_dir)):
        if DirAccess.remove_absolute(ProjectSettings.globalize_path(_run_dir)) != OK:
            _fail("cleanup: 运行目录非空或无法删除 %s" % _run_dir)


## 只报告不删除：`res://Levels` 中前缀命中但**不属于本运行**的残留。
func _report_foreign_leftovers() -> void:
    var dir := DirAccess.open("res://Levels")
    if dir == null:
        return
    for file_name in dir.get_files():
        if not file_name.begins_with("E2e"):
            continue
        var path := "res://Levels/" + file_name
        if not _owned.has(path):
            print("LEFTOVER (not owned by this run, not removed): %s" % path)


func _fail(message: String) -> void:
    _failures.append(message)


func _report() -> void:
    for path in _temp_files:
        if FileAccess.file_exists(path):
            _failures.append("Z: 临时关卡配置未清理 %s" % path)
    if not _run_dir.is_empty() and DirAccess.dir_exists_absolute(ProjectSettings.globalize_path(_run_dir)):
        _failures.append("Z: 运行目录未清理 %s" % _run_dir)
    _report_foreign_leftovers()
    if _failures.is_empty():
        print("PASS: 通用关卡编排管线验证通过（G1–G13）")
        quit(0)
    else:
        for failure in _failures:
            printerr("FAIL: " + failure)
        quit(1)
