#!/usr/bin/env python3
"""Generated Gameplay Behavior Probe（Phase 1.10 / 1.11）。

在**真实 Godot 运行时**对「生成链路产出的实体场景」执行玩法行为断言：
被测对象是 Scene Composer 生成的 .tscn，观察的是运行时状态变化
（实体根位移 / 子节点是否自行移动 / 玩家生命值），而不是节点、信号或脚本是否声明存在。

    python .ai/tools/e2e/behavior_probe.py res://Scenes/E2eProbeEnemy.tscn
    python .ai/tools/e2e/behavior_probe.py res://Scenes/E2eProbeEnemy.tscn \\
        --target res://Features/player_movement/Player.tscn
    python .ai/tools/e2e/behavior_probe.py <被破坏的场景> --expect none   # 受控负向（变异体）

机制（与测试生成器同构，不引入第二套验证体系）：
    1. 由本模块渲染一段临时 GDScript（Tests/e2e_behavior_probe.gd；**不带 test_ 前缀**，
       因此即使清理失败也不会被 run_tests.py 当作长期套件执行）；
    2. 用项目真实 Godot 以 `-s res://...` 运行它；
    3. 断言四组行为：
       a. 实体**根节点**在真实物理帧中向目标移动（不是只有子节点自己动）；
       b. 根节点的直接子节点本地位置不漂移（排除「子组件自己跑掉」）；
       c. 无接触时玩家不受伤害（保证伤害断言非恒真）；
       d. 真实物理接触后，接触伤害按既有机制（ContactDamage + Health、按 tick_interval
          节拍、damage 伤害量）结算 —— 不直接改生命值，不伪造信号；
    4. 返回退出码、原始输出与从 `BEHAVIOR:` 行解析出的度量值；
    5. 无论成败都在 finally 中删除临时脚本。

主行为：敌人实体根节点追踪目标并实际移动；目标默认用项目真实玩家实体场景
（Player.tscn，含 CharacterBody2D 碰撞 + Health），并按游戏约定加入 `players` 组
（SurvivalArena 在场景里对 Player 实例所做的同一件事），不构造与游戏无关的人造探针。

退出码: 0 = 行为断言全部通过；1 = 行为断言失败（含前置条件不成立）；
        2 = 输入 / 环境错误（场景不存在、Godot 缺失）。
"""

from __future__ import annotations

import argparse
import os
import re
import shutil
import subprocess
import sys
from dataclasses import dataclass, field
from pathlib import Path

_DOTAI = Path(__file__).resolve().parents[2]              # <project>/.ai
PROJECT_ROOT = _DOTAI.parent                              # <project>

DEFAULT_TARGET = "res://Features/player_movement/Player.tscn"

# 探针脚本位置（非 test_ 前缀：不会被统一运行器当作长期套件发现）
PROBE_SCRIPT_REL = "Tests/e2e_behavior_probe.gd"
PROBE_SCRIPT_NAME = "e2e_behavior_probe.gd"

# 行为断言的模拟参数（物理帧；60 Hz 下 move_frames=90、speed=80 → 理论位移 120 px）
INITIAL_DISTANCE = 400.0
IDLE_FRAMES = 20          # 基线窗口：未配置目标时必须无位移
MOVE_FRAMES = 90          # 行为窗口
MIN_APPROACH = 30.0       # 必须观察到的最小接近距离（远低于理论值，避免抖动误判）
DRIFT_TOLERANCE = 1.0     # 「静止 / 未自行移动」判定容差（px）
CONTACT_DISTANCE = 20.0   # 强制接触时目标与实体根的间距（远小于目标实体半宽 + 接触范围）
CONTACT_FRAMES = 90       # 接触伤害观察窗口（≈1.5 s）

# 接触伤害期望：damage = 真实接触必须结算伤害；none = 受控负向（去碰撞形状的变异体）
CONTACT_DAMAGE = "damage"
CONTACT_NONE = "none"

# 模板占位符用 {{TOKEN}} 而非 %-format：模板正文里大量使用 GDScript 的 % 格式化，
# 用 % 会让两层格式化互相干扰。
PROBE_SOURCE = '''extends SceneTree
## 由 .ai/tools/e2e/behavior_probe.py 生成——生成场景的玩法行为探针（Phase 1.10/1.11）。
## 不要手工编辑；重新生成请运行:
##   python .ai/tools/e2e/behavior_probe.py {{SCENE}}
##
## 用法：godot --headless --path . -s res://Tests/{{PROBE_NAME}}
## 断言的是真实运行时状态变化（根节点位移 / 接触伤害结算），不是节点或信号存在性。
## 全部通过输出 PASS 并退出 0；任一失败输出 FAIL 并退出 1。

const SCENE_PATH := "{{SCENE}}"
const TARGET_PATH := "{{TARGET}}"
const INITIAL_DISTANCE := {{INITIAL_DISTANCE}}
const IDLE_FRAMES := {{IDLE_FRAMES}}
const MOVE_FRAMES := {{MOVE_FRAMES}}
const MIN_APPROACH := {{MIN_APPROACH}}
const DRIFT_TOLERANCE := {{TOLERANCE}}
const CONTACT_EXPECT := "{{CONTACT}}"
const CONTACT_DISTANCE := {{CONTACT_DISTANCE}}
const CONTACT_FRAMES := {{CONTACT_FRAMES}}
const TICK_FALLBACK := 0.5
const PHYSICS_HZ := 60.0

var _failures: PackedStringArray = []


func _initialize() -> void:
	var packed: PackedScene = load(SCENE_PATH)
	if packed == null:
		_fail("Scene Load: 无法加载被测场景 %s" % SCENE_PATH)
		_report()
		return
	var target_packed: PackedScene = load(TARGET_PATH)
	if target_packed == null:
		_fail("Target Load: 无法加载目标场景 %s" % TARGET_PATH)
		_report()
		return

	# 被测实体 = 生成场景实例；其**根节点**就是实体根（本次修复的判定对象）。
	var entity: Node2D = packed.instantiate()
	root.add_child(entity)
	var target: Node2D = target_packed.instantiate()
	target.position = Vector2(INITIAL_DISTANCE, 0)
	root.add_child(target)
	# 游戏侧约定：玩家实体加入 players 组（SurvivalArena 在场景里对 Player 实例的设置）。
	target.add_to_group("players")
	await physics_frame

	# ---- 前置条件 1：场景中存在实现追击行为的组件，且目标引用可解析 ----
	var chase := _find_chase(entity)
	if chase == null:
		_fail("Precondition: 场景 %s 中不存在 ChaseMovement 组件，无法验证追击行为" % SCENE_PATH)
		_report()
		return
	if not is_instance_valid(target):
		_fail("Precondition: 目标节点 %s 实例化失败" % TARGET_PATH)
		_report()
		return
	var distance_setup: float = entity.global_position.distance_to(target.global_position)
	if distance_setup < MIN_APPROACH * 2.0:
		_fail("Precondition: 初始距离 %.1f 过小（需 >= %.1f），无法观察明显位移"
			% [distance_setup, MIN_APPROACH * 2.0])
		_report()
		return

	# ---- 前置条件 2：接触伤害需要目标侧的真实 Health 组件（组 + 命名约定） ----
	var target_health: Health = target.get_node_or_null("Health") as Health
	if target_health == null:
		_fail("Precondition: 目标 %s 缺少 Health 组件（命名约定），无法验证接触伤害结算" % TARGET_PATH)
		_report()
		return
	var contact := _find_contact(entity)
	if CONTACT_EXPECT == "{{CONTACT_DAMAGE}}" and contact == null:
		_fail("Precondition: 场景 %s 中不存在 ContactDamage 组件" % SCENE_PATH)
		_report()
		return

	# ---- 基线：未配置目标时必须静止（保证「接近」断言不是恒真） ----
	var root_origin: Vector2 = entity.global_position
	var baseline_drift: float = 0.0
	await _wait_frames(IDLE_FRAMES)
	baseline_drift = entity.global_position.distance_to(root_origin)
	if baseline_drift > DRIFT_TOLERANCE:
		_fail("Baseline: 未配置目标时实体根不应移动，实际位移 %.3f" % baseline_drift)

	# ---- 主行为：配置目标后，实体根在真实物理帧中持续接近 ----
	chase.target_path = chase.get_path_to(target)
	var distance_before: float = chase.global_position.distance_to(target.global_position)
	var root_before: Vector2 = entity.global_position
	var children_before := _child_positions(entity)
	var hp_before_approach: int = target_health.get_current_health()
	await _wait_frames(MOVE_FRAMES)
	var root_after: Vector2 = entity.global_position
	var root_approach: float = root_before.distance_to(root_after)
	var distance_after: float = chase.global_position.distance_to(target.global_position)
	var approach: float = distance_before - distance_after
	var chase_drift: float = root_approach
	if chase != entity:
		chase_drift = root_before.distance_to(chase.global_position)
	var child_max_drift: float = _max_child_drift(entity, children_before)
	var no_contact_damage: int = hp_before_approach - target_health.get_current_health()
	print("BEHAVIOR: scene=%s target=%s component=%s root=%s speed=%.1f frames=%d "
		% [SCENE_PATH, TARGET_PATH, chase.name, entity.name, chase.speed, MOVE_FRAMES]
		+ "distance_before=%.1f distance_after=%.1f approach=%.1f root_approach=%.1f "
		% [distance_before, distance_after, approach, root_approach]
		+ "chase_drift=%.1f child_max_drift=%.3f baseline_drift=%.3f no_contact_damage=%d"
		% [chase_drift, child_max_drift, baseline_drift, no_contact_damage])

	# 1. 实体根必须承担运动职责：根位移达到阈值
	if root_approach < MIN_APPROACH:
		_fail("Root Movement: %d 物理帧后实体根 %s 应向目标移动 >= %.1f px，实际 %.1f px"
			% [MOVE_FRAMES, entity.name, MIN_APPROACH, root_approach]
			+ "（根位置 %s -> %s，组件 %s 位置 %s，目标位置 %s）"
			% [root_before, root_after, chase.name, chase.global_position, target.global_position])
	# 2. 移动不能只发生在子节点上：根的直接子节点本地位置不得漂移
	if child_max_drift > DRIFT_TOLERANCE:
		_fail("Root Ownership: 位移应来自实体根，但子节点自行移动了 %.3f px（> %.3f）"
			% [child_max_drift, DRIFT_TOLERANCE])
	# 3. 组件级接近量（与根一致：追击组件即实体根时两者相等）
	if approach < MIN_APPROACH:
		_fail("Chase: %d 物理帧后应接近目标 >= %.1f px，实际 %.1f px（距离 %.1f -> %.1f，"
			% [MOVE_FRAMES, MIN_APPROACH, approach, distance_before, distance_after]
			+ "组件位置 %s，目标位置 %s）"
			% [chase.global_position, target.global_position])
	# 4. 无接触不得造成伤害（目标此时距离 400 px 远）
	if no_contact_damage != 0:
		_fail("No Contact: 未接触时玩家不应受伤，实际减少 %d 点生命值" % no_contact_damage)

	# ---- 接触伤害：把目标放到实体根旁边（真实物理接触），按既有机制结算 ----
	var tick_interval := TICK_FALLBACK
	var damage_per_tick := 1
	if contact != null:
		tick_interval = max(contact.tick_interval, 0.0001)
		damage_per_tick = contact.damage
	target.global_position = entity.global_position + Vector2(CONTACT_DISTANCE, 0)
	await physics_frame
	var contact_distance: float = entity.global_position.distance_to(target.global_position)
	var hp_before_contact: int = target_health.get_current_health()
	var max_distance: float = contact_distance
	for _i: int in CONTACT_FRAMES:
		await physics_frame
		max_distance = max(max_distance, entity.global_position.distance_to(target.global_position))
	var damage_total: int = hp_before_contact - target_health.get_current_health()
	var tick_frames := int(max(tick_interval * PHYSICS_HZ, 1.0))
	var damage_ceiling: int = damage_per_tick * (int(CONTACT_FRAMES / tick_frames) + 2)
	var contact_state := "present"
	if contact == null:
		contact_state = "missing"
	print("BEHAVIOR_CONTACT: scene=%s contact=%s tick_interval=%.3f damage_per_tick=%d "
		% [SCENE_PATH, contact_state, tick_interval, damage_per_tick]
		+ "contact_distance=%.1f contact_max_distance=%.1f window_frames=%d "
		% [contact_distance, max_distance, CONTACT_FRAMES]
		+ "hp_before=%d hp_after=%d damage_total=%d damage_ceiling=%d"
		% [hp_before_contact, target_health.get_current_health(), damage_total, damage_ceiling])

	if CONTACT_EXPECT == "{{CONTACT_DAMAGE}}":
		if damage_total <= 0:
			_fail("Contact Damage: 真实接触 %d 帧后玩家应受到伤害，实际 %d 点"
				% [CONTACT_FRAMES, damage_total]
				+ "（间距 %.1f px，接触组件 %s）" % [contact_distance, contact_state])
		elif damage_total > damage_ceiling:
			_fail("Contact Damage: 伤害应按 tick_interval=%.3f s 节拍结算（上限 %d 点），实际 %d 点"
				% [tick_interval, damage_ceiling, damage_total])
	elif damage_total != 0:
		_fail("Contact Damage (expect none): 变异场景不应结算伤害，实际 %d 点" % damage_total)

	# ---- 目标释放后应停止移动 ----
	target.queue_free()
	await _wait_frames(2)
	var stopped_at: Vector2 = entity.global_position
	await _wait_frames(IDLE_FRAMES)
	var post_free_drift: float = entity.global_position.distance_to(stopped_at)
	print("BEHAVIOR_STOP: post_free_drift=%.3f root_post_free_drift=%.3f"
		% [post_free_drift, post_free_drift])
	if post_free_drift > DRIFT_TOLERANCE:
		_fail("Stop: 目标释放后应停止移动，实际位移 %.3f" % post_free_drift)

	_report()


## 按行为类型递归查找追击组件（实体根或子节点均可）。
func _find_chase(node: Node) -> ChaseMovement:
	if node is ChaseMovement:
		return node
	for child in node.get_children():
		var found := _find_chase(child)
		if found != null:
			return found
	return null


## 按行为类型递归查找接触伤害组件。
func _find_contact(node: Node) -> ContactDamage:
	if node is ContactDamage:
		return node
	for child in node.get_children():
		var found := _find_contact(child)
		if found != null:
			return found
	return null


## 实体根直接子节点的本地位置快照（用于判定「位移是否只发生在子节点」）。
func _child_positions(node: Node) -> Dictionary:
	var snapshot := {}
	for child: Node in node.get_children():
		if child is Node2D:
			snapshot[child.get_path()] = (child as Node2D).position
	return snapshot


func _max_child_drift(node: Node, snapshot: Dictionary) -> float:
	var drift := 0.0
	for key in snapshot.keys():
		var child := node.get_node_or_null(key)
		if child is Node2D:
			drift = max(drift, (child as Node2D).position.distance_to(snapshot[key]))
	return drift


func _fail(message: String) -> void:
	_failures.append(message)


func _wait_frames(count: int) -> void:
	for _i: int in count:
		await physics_frame


func _report() -> void:
	if _failures.is_empty():
		print("PASS: 生成场景玩法行为验证通过 (%s)" % SCENE_PATH)
		quit(0)
	else:
		for failure in _failures:
			printerr("FAIL: " + failure)
		quit(1)
'''


@dataclass
class BehaviorProbeResult:
    """一次行为探针运行的结果（原始输出 + 解析出的度量值）。"""

    ok: bool
    exit_code: int
    scene: str
    target: str
    output: str
    metrics: dict = field(default_factory=dict)
    script_removed: bool = False
    contact: str = CONTACT_DAMAGE

    @property
    def failure_messages(self) -> list:
        return [line.strip() for line in self.output.splitlines()
                if line.strip().startswith("FAIL:")]


def find_godot(project_root: Path = PROJECT_ROOT):
    """与 .ai/tools/run_tests.py 一致的二进制查找（相邻目录 / PATH）。"""
    for candidate in (project_root.parent / "Godot_v4.7-stable_win64_console.exe",
                      project_root.parent / "Godot_v4.7-stable_win64.exe"):
        if candidate.is_file():
            return candidate
    for name in ("godot", "godot4"):
        found = shutil.which(name)
        if found:
            return Path(found)
    return None


def render_probe_source(scene_res: str, target_res: str = DEFAULT_TARGET,
                        contact: str = CONTACT_DAMAGE) -> str:
    """渲染探针 GDScript（{{TOKEN}} 字面替换，模板正文的 % 格式化原样保留）。"""
    if contact not in (CONTACT_DAMAGE, CONTACT_NONE):
        raise ValueError("contact expectation must be %r or %r, got %r"
                         % (CONTACT_DAMAGE, CONTACT_NONE, contact))
    replacements = {
        "{{SCENE}}": scene_res,
        "{{TARGET}}": target_res,
        "{{PROBE_NAME}}": PROBE_SCRIPT_NAME,
        "{{INITIAL_DISTANCE}}": repr(float(INITIAL_DISTANCE)),
        "{{IDLE_FRAMES}}": str(IDLE_FRAMES),
        "{{MOVE_FRAMES}}": str(MOVE_FRAMES),
        "{{MIN_APPROACH}}": repr(float(MIN_APPROACH)),
        "{{TOLERANCE}}": repr(float(DRIFT_TOLERANCE)),
        "{{CONTACT}}": contact,
        "{{CONTACT_DAMAGE}}": CONTACT_DAMAGE,
        "{{CONTACT_DISTANCE}}": repr(float(CONTACT_DISTANCE)),
        "{{CONTACT_FRAMES}}": str(CONTACT_FRAMES),
    }
    source = PROBE_SOURCE
    # CONTACT_DAMAGE 与 CONTACT 两个占位符有前缀关系：先替换长占位符，避免互相吃掉。
    for token in sorted(replacements, key=len, reverse=True):
        source = source.replace(token, replacements[token])
    if "{{" in source or "}}" in source:                   # pragma: no cover - 防占位符拼写错误
        raise RuntimeError("unresolved probe placeholder remains in rendered script")
    return source


def parse_metrics(output: str) -> dict:
    """从 BEHAVIOR / BEHAVIOR_CONTACT / BEHAVIOR_STOP 行解析度量值（供调用方独立断言）。"""
    metrics: dict = {}
    for line in output.splitlines():
        if not line.startswith("BEHAVIOR"):
            continue
        for key, value in re.findall(r"(\w+)=([-\d.]+)", line):
            try:
                metrics[key] = float(value)
            except ValueError:                              # pragma: no cover - 防御
                continue
    return metrics


def run_behavior_probe(scene_res: str, target_res: str = DEFAULT_TARGET,
                       project_root: Path = PROJECT_ROOT, godot=None,
                       timeout: int = 300, contact: str = CONTACT_DAMAGE) -> BehaviorProbeResult:
    """在真实 Godot 中运行行为探针。输入/环境错误抛 RuntimeError（调用方转 exit 2）。

    contact —— CONTACT_DAMAGE（默认：真实接触必须结算伤害）或 CONTACT_NONE
    （受控负向：用于「去掉碰撞形状的变异体」等场景，断言接触下不产生伤害）。
    """
    project_root = Path(project_root)
    scene_path = project_root / scene_res.replace("res://", "")
    if not scene_path.is_file():
        raise RuntimeError("scene not found in project: %s (%s)" % (scene_res, scene_path))
    target_path = project_root / target_res.replace("res://", "")
    if not target_path.is_file():
        raise RuntimeError("chase target scene not found in project: %s" % target_res)
    godot = Path(godot) if godot else find_godot(project_root)
    if godot is None or not Path(godot).is_file():
        raise RuntimeError("godot executable not found; set GODOT_BIN or add it to PATH")

    script_path = project_root / PROBE_SCRIPT_REL
    script_path.parent.mkdir(parents=True, exist_ok=True)
    script_path.write_text(render_probe_source(scene_res, target_res, contact),
                           encoding="utf-8", newline="\n")
    try:
        proc = subprocess.run(
            [str(godot), "--headless", "--path", str(project_root),
             "-s", "res://" + PROBE_SCRIPT_REL.replace(os.sep, "/")],
            capture_output=True, text=True, encoding="utf-8", errors="replace",
            cwd=str(project_root), stdin=subprocess.DEVNULL, timeout=timeout)
        output = (proc.stdout or "") + (proc.stderr or "")
        exit_code = proc.returncode
    finally:
        removed = True
        try:
            script_path.unlink()
        except OSError:                                     # pragma: no cover - 清理失败要报告
            removed = False
    return BehaviorProbeResult(ok=(exit_code == 0 and "PASS:" in output),
                               exit_code=exit_code, scene=scene_res, target=target_res,
                               output=output, metrics=parse_metrics(output),
                               script_removed=removed, contact=contact)


def main(argv=None) -> int:
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
        sys.stderr.reconfigure(encoding="utf-8")
    parser = argparse.ArgumentParser(
        description="Run a real-Godot gameplay behavior probe against a generated scene.")
    parser.add_argument("scene", help="res:// path of the scene under test")
    parser.add_argument("--target", default=DEFAULT_TARGET,
                        help="res:// path of the chase target scene (default: %s)" % DEFAULT_TARGET)
    parser.add_argument("--expect", default=CONTACT_DAMAGE, choices=(CONTACT_DAMAGE, CONTACT_NONE),
                        help="contact damage expectation (default: %s)" % CONTACT_DAMAGE)
    parser.add_argument("--project", default=str(PROJECT_ROOT))
    parser.add_argument("--show-output", action="store_true", help="Print raw Godot output")
    args = parser.parse_args(argv)

    try:
        result = run_behavior_probe(args.scene, target_res=args.target,
                                    project_root=Path(args.project).resolve(),
                                    contact=args.expect)
    except (RuntimeError, subprocess.TimeoutExpired) as exc:
        print("FAIL: %s" % exc, file=sys.stderr)
        return 2

    print("Gameplay Behavior Probe")
    print("Scene:  %s" % result.scene)
    print("Target: %s" % result.target)
    if args.show_output:
        print(result.output)
    print("Result: status=%s exit_code=%d %s"
          % ("PASS" if result.ok else "FAIL", result.exit_code,
             " ".join("%s=%s" % (key, value) for key, value in sorted(result.metrics.items()))))
    for failure in result.failure_messages:
        print("  " + failure, file=sys.stderr)
    return 0 if result.ok else 1


if __name__ == "__main__":
    sys.exit(main())
