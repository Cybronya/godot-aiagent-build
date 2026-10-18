#!/usr/bin/env python3
"""End-to-End Game Generation integration test（Phase 1.9）。

按目标链路跑**真实 CLI**（不 mock、不伪造产物），每一步都断言输入/输出契约：

    自然语言需求
      → Gameplay Blueprint（planner.py）
      → 每实体 Entity Blueprint（planner.py --emit-entities）
      → Feature Discovery（feature_discovery.py --json）
      → 显式候选选择 → 显式绑定输入（discovery_to_binding.py --select）
      → Resource Binding（bind_assets.py --gameplay --binding）
      → Scene Composer / Scene Intent（scene_composer.py）
      → 静态验证（check_scene_composition.py / check_gameplay.py）
      → 真实 Godot 运行时（run_scene.py / 生成的场景回归测试，环境允许时）
      → 真实玩法行为断言（behavior_probe.py：追踪组件在物理帧中实际接近目标，环境允许时）
      → 真实死亡与胜利闭环断言（death_victory_probe.py：生成的实体在真实游戏场景里
        被真实攻击输入击杀 → 死亡事件 → 击杀计数 → 胜负状态，环境允许时）

覆盖（对应任务验收项）：
    A  自然语言 → Gameplay Blueprint → 每实体 Entity Blueprint（schema 符合性 + 复用不覆盖）
    B  Blueprint 进入现有 Feature Discovery，且发现结果不把玩家专属组件塞进敌方
    C  候选必须显式选择：不选择时适配器拒绝（exit 1），绝不默认 top-1
    D  Resource Binding 产出 schema_version=2 的按实体绑定文档（resolved_from 可区分来源）
    E  Scene Composer 使用契约化 Scene Intent，组件来自 Feature 入口场景，资源来自 Binding
    F  静态验证：check_scene_composition PASS
    G  闭环：Gameplay Blueprint → 生成场景 → check_gameplay PASS → Godot 运行时 PASS
        → 玩法行为断言（G10a–G10e：距离真实缩短 / 无目标静止 / 目标释放后停止）
        → 受控负向（G11 缺少行为时探针必须失败退出非零）
    J  死亡与胜利闭环（Phase 1.12）：生成的实体放进项目真实竞技场场景，经真实攻击输入
        路径死亡（D/N）→ 死亡事件恰好一次、击杀计数恰好减一、实体退出战斗 →
        仍有必需敌人存活时不提前胜利（V2）→ 最后一个敌人死亡后场景自身逻辑开启出口，
        玩家真实输入进出口区 → Completed + arena_finished 一次（V1）
        → 手写实体等价性（同一探针在 Scenes/Enemy.tscn 上得到同样结论）
        → 受控负向（不死变异体在 survive 期望下必须零胜利，在 die 期望下必须失败）
    K  关卡编排生成与运行时消费（Phase 1.13）：Gameplay Blueprint → 关卡配置（生成物，
        引用刚生成的实体场景）→ 独立校验（K4 受控负向：非法数量被拒绝且可定位）→
        真实 Godot：配置驱动的生成数量（K6）/ 两波顺序与只推进一次（K7）/ 出口锁定与
        清场开启（K8）/ 玩家进出口区 Completed + 胜负一次（K9）/ 生成物身份（K10）；
        K12 受控负向：无效配置在运行时被拒绝（零生成 + state=Failed + 可定位诊断）
    M  composition plan 自动生成（Phase 1.19）：Gameplay Blueprint + 真实生成产物 ->
        composition_plan（M1 自动生成、实体身份保留、不凭空造目标；M2 蓝图派生关系
        （entity_graph 的 attack 边）-> 声明式目标引用；M3 缺场景映射拒绝且无产物；
        M4 未知目标拒绝；M5 无关系声明时计划不含 targets）
    T  黄金 Trace 基线（Phase 1.23）：两个场景的已批准基线满足基线契约（版本 / 批准记录 /
        显式策略）；沙箱内重跑真实生成链路 + Godot 探针得到本次真实 trace，逐事件比较
        必须 PASS；注入未批准的 reason 变化 → REGRESSION 且 CLI 退出码 1；run_id /
        timestamp_ms 变化仍 PASS；基线缺失 / 损坏 → BASELINE_MISSING / INVALID_BASELINE
        （绝不 PASS）；E2E 不重写基线、不留残留。
    H  负向：未知 Feature 被拒（零产物）、显式绑定指向不存在的资源时报告缺失而不编造
    I  已知缺口回归：跨实体使用角色级显式覆盖时，被标记 INCOMPATIBLE（或被拒），不静默 COMPATIBLE

环境说明：
    - Godot 二进制缺失时，G 段的运行时断言打印 SKIP 并记录原因（不谎称已运行）。
    - 需要写入项目内 Scenes/ 与 Tests/（Godot 只能运行 res:// 内的资源）：只写唯一命名的
      E2eProbe* 文件并在 finally 中删除；schema 要求生成的 Scenes/<Pascal>.tscn 与既有手工
      场景同名时必须显式复用或改名，因此本测试的实体 id 全部带 e2e_probe_ 前缀。

用法:
    python .ai/tools/e2e/tests/test_end_to_end_generation.py

退出码: 0 = 全部通过；1 = 有失败。
"""

from __future__ import annotations

import json
import re
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

_DOTAI = Path(__file__).resolve().parents[3]              # <project>/.ai
PROJECT_ROOT = _DOTAI.parent                              # <project>
TOOLS = _DOTAI / "tools"

sys.path.insert(0, str(TOOLS / "scene_composer"))
sys.path.insert(0, str(TOOLS / "e2e"))                    # behavior_probe（本目录）
sys.path.insert(0, str(TOOLS / "validator"))              # trace_replay（Phase 1.22）

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")

import yaml                                                # noqa: E402
import trace_replay                                        # noqa: E402

_failures: list[str] = []
_skips: list[str] = []


def ok(name: str, condition: bool, detail: str = "") -> None:
    if condition:
        print("PASS: " + name)
    else:
        _failures.append(name + (" | " + detail if detail else ""))


def skip(name: str, reason: str) -> None:
    _skips.append(name)
    print("SKIP: %s (%s)" % (name, reason))


def run_cli(script_rel: str, *argv, timeout: int = 300) -> subprocess.CompletedProcess:
    """在项目根上以子进程运行真实 CLI。"""
    cmd = [sys.executable, str(TOOLS / script_rel)] + [str(a) for a in argv]
    return subprocess.run(cmd, capture_output=True, text=True, encoding="utf-8",
                          errors="replace", cwd=str(PROJECT_ROOT),
                          stdin=subprocess.DEVNULL, timeout=timeout)


def find_godot():
    """与 .ai/tools/run_tests.py 一致的二进制查找（相邻目录 / PATH）。"""
    for candidate in (PROJECT_ROOT.parent / "Godot_v4.7-stable_win64_console.exe",
                      PROJECT_ROOT.parent / "Godot_v4.7-stable_win64.exe"):
        if candidate.is_file():
            return candidate
    for name in ("godot", "godot4"):
        found = shutil.which(name)
        if found:
            return Path(found)
    return None


def probes_ok_scene_root(tscn: str) -> bool:
    """生成场景的实体根是否就是 chase_movement 的入口场景实例（且未重复为子节点）。"""
    return ('[node name="E2eProbeEnemy" instance=ExtResource("1_root_scene")]' in tscn
            and 'path="res://Features/chase_movement/ChaseMovement.tscn" id="1_root_scene"' in tscn
            and '[node name="ChaseMovement" parent="." instance=' not in tscn)


def write_contact_shape_mutant(source_path: Path, target_path: Path) -> bool:
    """从生成场景派生一个「去掉接触形状」的变异体（用于受控负向断言）。

    只删除 ContactShape 节点块，其余逐字保留（子资源声明留着不影响加载）：
    变异体在物理上仍会被摆到玩家身上，但没有任何碰撞形状 → 不可能重叠。
    """
    if not source_path.is_file():
        return False
    text = source_path.read_text(encoding="utf-8")
    pattern = re.compile(r'\n\[node name="ContactShape"[^\]]*\]\nshape = SubResource\("[^"]*"\)\n')
    mutated, removed = pattern.subn("\n", text)
    if removed != 1:
        return False
    target_path.write_text(mutated, encoding="utf-8", newline="\n")
    return True


def write_immortal_mutant(source_path: Path, target_path: Path, max_health: int = 999) -> bool:
    """从生成场景派生一个「攻击打不死」的变异体（用于受控负向）。

    只改 Health 组件节点的 max_health（其余逐字保留）：敌人在攻击预算内不会死亡，
    因此胜负系统必须保持未胜利。同一变异体在正向期望下必须失败 —— 证明胜利断言
    依赖真实死亡，而不是「探针自己说了算」。
    """
    if not source_path.is_file():
        return False
    text = source_path.read_text(encoding="utf-8")
    match = re.search(r'(?m)^\[node name="Health" parent="\.[^"]*"[^\]]*\]$', text)
    if not match:
        return False
    start = match.end()
    next_node = re.search(r'(?m)^\[', text[start:])
    end = start + next_node.start() if next_node else len(text)
    block = text[start:end]
    patched = re.sub(r'(?m)^max_health = \d+$', "max_health = %d" % max_health, block)
    if patched == block:
        patched = "\nmax_health = %d" % max_health + block
    target_path.write_text(text[:start] + patched + text[end:], encoding="utf-8", newline="\n")
    return True


def run_godot_script(godot: Path, res_path: str, timeout: int = 120):
    return subprocess.run(
        [str(godot), "--headless", "--path", str(PROJECT_ROOT), "-s", res_path],
        capture_output=True, text=True, encoding="utf-8", errors="replace",
        cwd=str(PROJECT_ROOT), stdin=subprocess.DEVNULL, timeout=timeout)


# ---------- 夹具：符合 gameplay_schema.yaml 的 Gameplay Blueprint ----------
# 实体 id 带 e2e_probe_ 前缀：生成的 Scenes/<Pascal(entity_id)>.tscn 与既有手工场景同名时
# schema 要求显式复用或改名，禁止静默覆盖（因此不复用 enemy/player 这类通用 id）。
_PROBE_GAMEPLAY = {
    "gameplay": {"id": "e2e_probe_game"},
    "entities": {
        "e2e_probe_enemy": {
            "role": "enemy",
            "features": ["chase_movement", "contact_damage", "health"],
        },
        "e2e_probe_player": {
            "role": "player",
            "features": ["health", "player_movement"],
            "scene": "res://Features/player_movement/Player.tscn",
        },
    },
    "systems": ["enemy_spawn", "reward"],
    "loop": {
        "start": "player spawned",
        "cycle": "enemy spawn; enemy chase; damage player",
        "end": "enemy defeated; reward gained",
    },
    "validation": {
        "required_entities": ["e2e_probe_enemy", "e2e_probe_player"],
        "required_features": ["damage_source"],
        "required_tests": ["chase_movement", "contact_damage", "health", "player_movement"],
    },
}

_PROBE_SCENE = PROJECT_ROOT / "Scenes" / "E2eProbeEnemy.tscn"
_PROBE_TEST = PROJECT_ROOT / "Tests" / "test_e2e_probe_enemy.gd"
# 受控负向用例的生成场景（仅含 health，没有实现追击行为的组件）
_NOCASE_SCENE = PROJECT_ROOT / "Scenes" / "E2eProbeNochase.tscn"
# 受控负向用例的变异体（从生成场景里移除接触形状：接触下必须**不**产生伤害）
_MUTANT_SCENE = PROJECT_ROOT / "Scenes" / "E2eProbeNoContact.tscn"
# 受控负向用例的变异体（把 Health.max_health 抬到攻击预算之上：攻击打不死 → 不得胜利）
_IMMORTAL_SCENE = PROJECT_ROOT / "Scenes" / "E2eProbeImmortal.tscn"
# Phase 1.17：独立生成的玩家实体场景与多实体宿主（原生 instancing 组合）
_PROBE_PLAYER_SCENE = PROJECT_ROOT / "Scenes" / "E2eProbePlayer.tscn"
_PROBE_DUAL_SCENE = PROJECT_ROOT / "Scenes" / "E2eProbeDualHost.tscn"
_PROBE_BAD_HOST = PROJECT_ROOT / "Scenes" / "E2eProbeBadHost.tscn"
_DUAL_PROBE_SCRIPT = PROJECT_ROOT / "Tests" / "e2e_dual_host_probe.gd"
# Phase 1.20：boss 模式生成链路（生成实体场景 + 自动计划 + 组合宿主 + 关卡配置）
_BOSS_SCENE = PROJECT_ROOT / "Scenes" / "E2eBoss.tscn"
_BOSS_HOST_SCENE = PROJECT_ROOT / "Scenes" / "E2eBossHost.tscn"
_BOSS_LEVEL = PROJECT_ROOT / "Levels" / "E2eBossLevel.json"
_BOSS_BAD_LEVEL = PROJECT_ROOT / "Levels" / "E2eBossLevelBad.json"
# Phase 1.21：多阶段 Boss 链路
_STAGE_GRUNT_SCENE = PROJECT_ROOT / "Scenes" / "StageGrunt.tscn"
_STAGE_BOSS_SCENE = PROJECT_ROOT / "Scenes" / "StageBoss.tscn"
_STAGE_HOST_SCENE = PROJECT_ROOT / "Scenes" / "E2eStageBossHost.tscn"
_STAGE_LEVEL = PROJECT_ROOT / "Levels" / "E2eStageBossLevel.json"
_STAGE_BAD_LEVEL = PROJECT_ROOT / "Levels" / "E2eStageBossLevelBad.json"
# Phase 1.22：真实运行导出的诊断 trace（由 multi_stage_boss_probe 写入，测试读取后清理）
_STAGE_TRACE = PROJECT_ROOT / "Tests" / "e2e_multi_stage_boss_trace.json"

_BOSS_GAMEPLAY = {
    "gameplay": {"id": "e2e_boss_game"},
    "entities": {
        "player": {
            "role": "player",
            "features": ["health", "player_movement"],
            "scene": "res://Features/player_movement/Player.tscn",
        },
        "e2e_boss": {"role": "enemy", "features": ["chase_movement", "health"]},
    },
    "systems": ["enemy_spawn"],
    "loop": {"start": "player spawned", "cycle": "boss chases player",
             "end": "boss defeated"},
    "validation": {"required_entities": ["player", "e2e_boss"],
                   "required_features": [],
                   "required_tests": ["health", "chase_movement"]},
}

_STAGE_BOSS_GAMEPLAY = {
    "gameplay": {"id": "e2e_stage_boss_game"},
    "entities": {
        "player": {
            "role": "player",
            "features": ["health", "player_movement"],
            "scene": "res://Features/player_movement/Player.tscn",
        },
        "stage_grunt": {"role": "enemy", "features": ["chase_movement", "health"]},
        "stage_boss": {"role": "enemy", "features": ["chase_movement", "health"]},
    },
    "systems": ["enemy_spawn"],
    "loop": {"start": "player spawned", "cycle": "clear grunts; boss fights",
             "end": "boss defeated"},
    "validation": {"required_entities": ["player", "stage_grunt", "stage_boss"],
                   "required_features": [],
                   "required_tests": ["health", "chase_movement"]},
}


def _run_compose_plan(plan_path: Path, dry_run: bool = False):
    """正式多实体组合入口（scene_composer --compose-plan，Phase 1.18）。"""
    args = ["scene_composer/scene_composer.py", "--compose-plan", str(plan_path),
            "--out", str(PROJECT_ROOT / "Scenes")]
    if dry_run:
        args.append("--dry-run")
    return run_cli(*args)


def _make_bad_plan(work: Path) -> Path:
    """未知目标实例的组合计划（受控负向：必须被正式入口拒绝且不留产物）。"""
    bad_plan = work / "dual_plan_bad.yaml"
    bad_plan.write_text(yaml.safe_dump({
        "document": "composition_plan",
        "schema_version": 1,
        "host": {"name": "E2eProbeBadHost"},
        "instances": [
            {"entity": "enemy", "scene": "res://Scenes/SlimeEnemy.tscn",
             "instance_name": "Enemy"},
            {"entity": "player", "scene": "res://Features/player_movement/Player.tscn",
             "instance_name": "Player"},
        ],
        "targets": [{"source": "Enemy", "target": "Ghost"}],
    }, sort_keys=False, allow_unicode=True), encoding="utf-8")
    return bad_plan

# 瞬态探针（Phase 1.17/1.18）：加载多实体宿主，断言两个实例存在、运行时资源
# 归属互不覆盖，并验证**运行时交互契约**——enemy 实例根携带宿主声明的 target_path
# 且在真实物理帧中朝目标实例移动（无编排器、探针不指派目标）。
# 机读输出：DUAL: <json>。约定与 level_orchestration_probe 相同——不带 test_ 前缀，
# 由 Python 侧写入/删除并在断言里确认无残留。
DUAL_HOST_PROBE_GD = """extends SceneTree

var frames := 0
var host: Node
var enemy: Node2D
var player: Node2D
var start_dist := -1.0
var min_dist := 1e9
var target_path_value := ""
var enemy_assets: Array = []
var player_assets: Array = []

func _collect(node: Node, out: Array) -> void:
\tout.append(node)
\tfor child in node.get_children():
\t\t_collect(child, out)

func _collect_assets() -> void:
\tvar assets := {"enemy": enemy_assets, "player": player_assets}
\tfor pair in [["enemy", enemy], ["player", player]]:
\t\tvar owner_node: Node = pair[1]
\t\tif owner_node == null:
\t\t\tcontinue
\t\tvar nodes: Array = []
\t\t_collect(owner_node, nodes)
\t\tfor n in nodes:
\t\t\tif n is AnimatedSprite2D and n.sprite_frames != null:
\t\t\t\tassets[pair[0]].append(n.sprite_frames.resource_path)
\t\t\telif n is Sprite2D and n.texture != null:
\t\t\t\tassets[pair[0]].append(n.texture.resource_path)
\t\t\telif n is AudioStreamPlayer and n.stream != null:
\t\t\t\tassets[pair[0]].append(n.stream.resource_path)

func _initialize() -> void:
\tvar packed: PackedScene = load("res://Scenes/E2eProbeDualHost.tscn")
\tif packed == null:
\t\tprint("DUAL: %s" % JSON.stringify({"status": "load_failed"}))
\t\tquit(1)
\t\treturn
\thost = packed.instantiate()
\troot.add_child(host)
\tenemy = host.get_node_or_null("E2eProbeEnemy") as Node2D
\tplayer = host.get_node_or_null("E2eProbePlayer") as Node2D
\tif enemy == null or player == null:
\t\tprint("DUAL: %s" % JSON.stringify({"status": "missing_instance"}))
\t\tquit(1)
\t\treturn
\ttarget_path_value = str(enemy.get("target_path"))
\t_collect_assets()
\t# 把目标实例摆到远处：此后 enemy 是否接近完全取决于宿主声明的 target_path。
\tplayer.position = Vector2(400, 0)

func _process(_delta: float) -> bool:
\tframes += 1
\tif enemy != null and is_instance_valid(enemy) and player != null \\
\t\t\tand is_instance_valid(player):
\t\tvar d: float = enemy.global_position.distance_to(player.global_position)
\t\tif frames == 1:
\t\t\tstart_dist = d
\t\tmin_dist = minf(min_dist, d)
\tif frames >= 90:
\t\tvar names: Array = []
\t\tfor child in host.get_children():
\t\t\tnames.append(String(child.name))
\t\tvar report := {
\t\t\t"status": "ok",
\t\t\t"instance_names": names,
\t\t\t"enemy_present": enemy != null,
\t\t\t"player_present": player != null,
\t\t\t"enemy_assets": enemy_assets,
\t\t\t"player_assets": player_assets,
\t\t\t"target_path": target_path_value,
\t\t\t"start_dist": start_dist,
\t\t\t"min_dist": min_dist,
\t\t\t"approach": start_dist - min_dist,
\t\t}
\t\tprint("DUAL: %s" % JSON.stringify(report))
\t\tquit(0)
\t\treturn true
\treturn false
"""


def main() -> int:
    work = Path(tempfile.mkdtemp(prefix="e2e_gen_"))
    probe_written = False
    probe_test_written = False
    nocase_written = False
    mutant_written = False
    immortal_written = False
    level_written = False
    broken_level_written = False
    probe_player_written = False
    dual_written = False
    godot = None
    try:
        # 防御性清理（Phase 1.23）：上一进程被外部终止（超时 / 中断）时 finally 不会
        # 执行，可能留下**本测试自己的**探针产物，破坏 G4/L9 等断言的「从干净状态
        # 开始」前提。这里只清理本测试声明的产物清单（与 Z1 同一清单），不触碰
        # 任何其他文件；Z1 仍断言本次运行结束后的真实清理。
        for stale in (_PROBE_SCENE, _PROBE_TEST, _NOCASE_SCENE, _MUTANT_SCENE,
                      _IMMORTAL_SCENE, _PROBE_PLAYER_SCENE, _PROBE_DUAL_SCENE,
                      _PROBE_BAD_HOST, _DUAL_PROBE_SCRIPT,
                      PROJECT_ROOT / "Tests" / "e2e_boss_level_trace.json",
                      PROJECT_ROOT / "Tests" / "e2e_multi_stage_boss_trace.json"):
            try:
                stale.unlink(missing_ok=True)
                Path(str(stale) + ".uid").unlink(missing_ok=True)
            except OSError:
                pass
        # ==================== A. 自然语言 -> Gameplay Blueprint -> 每实体蓝图 ====================
        print("--- A. natural language -> gameplay blueprint -> entity blueprints ---")
        gameplay = work / "gameplay.yaml"
        entities_dir = work / "entities"
        r = run_cli("gameplay_planner/planner.py", "create enemy survival game",
                    "--id", "e2e_survival", "--out", gameplay,
                    "--emit-entities", entities_dir, "--no-graph")
        ok("A1: planner CLI exits 0", r.returncode == 0, (r.stderr or r.stdout)[-300:])
        bp = yaml.safe_load(gameplay.read_text(encoding="utf-8")) if gameplay.is_file() else {}
        ok("A2: gameplay blueprint carries gameplay.id / entities / loop",
           bool(bp.get("gameplay", {}).get("id")) and bool(bp.get("entities"))
           and bool((bp.get("loop") or {}).get("end")), repr(list(bp)))
        ok("A3: gameplay id honours --id", bp.get("gameplay", {}).get("id") == "e2e_survival",
           repr(bp.get("gameplay")))

        enemy_bp_path = entities_dir / "enemy.yaml"
        ok("A4: per-entity Entity Blueprint emitted for the non-reuse entity",
           enemy_bp_path.is_file(),
           str(sorted(p.name for p in entities_dir.glob("*.yaml"))) if entities_dir.is_dir() else "<none>")
        enemy_bp = yaml.safe_load(enemy_bp_path.read_text(encoding="utf-8")) if enemy_bp_path.is_file() else {}
        ok("A5: emitted blueprint conforms to the entity blueprint shape",
           str((enemy_bp.get("entity") or {}).get("id") or "") == "enemy"
           and str((enemy_bp.get("entity") or {}).get("role") or "") == "enemy"
           and bool(enemy_bp.get("features"))
           and bool((enemy_bp.get("validation") or {}).get("required_tests")),
           repr(enemy_bp))
        ok("A6: emitted features match the gameplay blueprint entity",
           enemy_bp.get("features") == list(bp["entities"]["enemy"]["features"]),
           repr((enemy_bp.get("features"), bp["entities"]["enemy"]["features"])))
        ok("A7: entities with a reused scene are NOT emitted (no overwrite risk)",
           not (entities_dir / "player.yaml").exists() and bool(bp["entities"]["player"].get("scene")),
           str(sorted(p.name for p in entities_dir.glob("*.yaml"))) if entities_dir.is_dir() else "<none>")
        r = run_cli("scene_composer/scene_composer.py", enemy_bp_path, "--dry-run")
        ok("A8: emitted blueprint is accepted by Scene Composer (dependency resolve, no write)",
           r.returncode == 0 and "Dry run" in r.stdout, (r.stdout + r.stderr)[-300:])

        # ==================== B. Feature Discovery ====================
        print()
        print("--- B. feature discovery ---")
        discovery_json = work / "discovery.json"
        r = run_cli("feature_registry/feature_discovery.py",
                    "slime enemy that chases the player", "--json")
        discovery_json.write_text(r.stdout or "{}", encoding="utf-8")
        ok("B1: discovery CLI exits 0", r.returncode == 0, (r.stderr or r.stdout)[-300:])
        payload = json.loads(r.stdout or "{}")
        ok("B2: payload matches the frozen discovery contract (schema_version + required keys)",
           payload.get("schema_version") == 1
           and all(key in payload for key in ("query", "role", "features", "feature_capabilities",
                                              "requirements", "asset_slots", "optional_slots",
                                              "asset_candidates", "missing", "diagnostics")),
           repr(sorted(payload.keys())))
        ok("B3: role resolved as enemy and discovery does not pull player-only components in",
           payload.get("role") == "enemy" and bool(payload.get("features"))
           and "player_movement" not in payload["features"],
           repr((payload.get("role"), payload.get("features"))))
        ok("B4: required asset slots are discovered with candidates",
           bool(payload.get("asset_slots"))
           and all(slot in payload.get("asset_candidates", {}) for slot in payload["asset_slots"]),
           repr(payload.get("asset_slots")))
        ambiguous = [slot for slot, cands in payload.get("asset_candidates", {}).items()
                     if len(cands) > 1]
        ok("B5: candidates stay lists per slot (choosing is a separate explicit step)",
           isinstance(payload["asset_candidates"], dict)
           and all(isinstance(c, list) for c in payload["asset_candidates"].values()),
           repr({k: type(v).__name__ for k, v in payload.get("asset_candidates", {}).items()}))
        print("      (slots with multiple candidates requiring explicit choice: %s)"
              % (", ".join(ambiguous) if ambiguous else "none in this run"))

        # ==================== C. 显式选择 -> 显式绑定输入 ====================
        print()
        print("--- C. explicit candidate selection ---")
        selections = {}
        for slot, cands in (payload.get("asset_candidates") or {}).items():
            if cands:
                selections[slot] = cands[0]["id"]
        required_slots = list(payload.get("asset_slots") or [])
        ok("C1: every required slot has a candidate available for explicit selection",
           bool(required_slots) and all(slot in selections for slot in required_slots),
           repr((required_slots, sorted(selections))))
        select_args = []
        for slot in sorted(selections):
            select_args += ["--select", "%s=%s" % (slot, selections[slot])]

        override = work / "binding_override.yaml"
        # Phase 1.16：实体身份来源可追溯 —— discovery payload.role + gameplay 蓝图实体清单
        #（恰好一个 enemy 角色实体）；--resolve-entity-from 解析唯一实体并打上 entity 作用域。
        enemy_role_entities = sorted(
            eid for eid, entry in (bp.get("entities") or {}).items()
            if isinstance(entry, dict)
            and str(entry.get("role") or "") == str(payload.get("role") or ""))
        ok("C2a: discovery role resolves to exactly one gameplay entity (traceable identity)",
           len(enemy_role_entities) == 1 and payload.get("role") == "enemy"
           and enemy_role_entities == ["enemy"],
           repr((payload.get("role"), enemy_role_entities, sorted(bp.get("entities") or {}))))
        r = run_cli("feature_registry/discovery_to_binding.py", "--input", discovery_json,
                    *select_args, "--resolve-entity-from", gameplay, "-o", override)
        ok("C2: adapter converts an explicit selection with the resolved entity (exit 0)",
           r.returncode == 0, (r.stderr or r.stdout)[-300:])
        override_doc = (yaml.safe_load(override.read_text(encoding="utf-8"))
                        if override.is_file() else {})
        ok("C3: override carries entity-scoped bindings resolved from the gameplay blueprint",
           bool(override_doc.get("bindings"))
           and all(set(entry) == {"entity", "role", "asset"}
                   and entry["entity"] == enemy_role_entities[0]
                   for entry in override_doc["bindings"])
           and {entry["role"]: entry["asset"] for entry in override_doc["bindings"]} == selections,
           repr(override_doc))

        # 场景 4（单实体旧格式兼容）：缺省（无 --entity / --resolve-entity-from）
        # 仍产出历史 {role, asset} 格式，旧工作流不要求迁移。
        legacy_override = work / "binding_override_legacy.yaml"
        r = run_cli("feature_registry/discovery_to_binding.py", "--input", discovery_json,
                    *select_args, "-o", legacy_override)
        legacy_doc = (yaml.safe_load(legacy_override.read_text(encoding="utf-8"))
                      if legacy_override.is_file() else {})
        ok("C3b: the legacy no-entity-flag output keeps the {role, asset} format",
           r.returncode == 0
           and bool(legacy_doc.get("bindings"))
           and all(set(entry) == {"role", "asset"} for entry in legacy_doc["bindings"])
           and {entry["role"]: entry["asset"] for entry in legacy_doc["bindings"]} == selections,
           repr(legacy_doc))

        # 场景 6（实体发现信息不足）：角色无法唯一对应实体时必须显式失败，不猜测归属。
        ambiguous_bp = work / "ambiguous_gameplay.yaml"
        ambiguous_bp.write_text(yaml.safe_dump({
            "gameplay": {"id": "ambiguous_roles"},
            "entities": {
                "enemy_a": {"role": "enemy", "features": ["health"]},
                "enemy_b": {"role": "enemy", "features": ["health"]},
            },
        }, sort_keys=False), encoding="utf-8")
        r = run_cli("feature_registry/discovery_to_binding.py", "--input", discovery_json,
                    *select_args, "--resolve-entity-from", ambiguous_bp)
        ok("C6: an ambiguous entity role is refused with a diagnosable error (exit 1)",
           r.returncode == 1 and "ambiguous_entity_role" in (r.stderr or "")
           and "enemy_a" in (r.stderr or "") and "enemy_b" in (r.stderr or ""),
           "exit=%s stderr=%s" % (r.returncode, (r.stderr or "")[-300:]))
        nomatch_bp = work / "nomatch_gameplay.yaml"
        nomatch_bp.write_text(yaml.safe_dump({
            "gameplay": {"id": "nomatch_roles"},
            "entities": {"only_player": {"role": "player", "features": ["health"]}},
        }, sort_keys=False), encoding="utf-8")
        r = run_cli("feature_registry/discovery_to_binding.py", "--input", discovery_json,
                    *select_args, "--resolve-entity-from", nomatch_bp)
        ok("C6: a role with no matching entity is refused (exit 1, no guessed identity)",
           r.returncode == 1 and "no_entity_with_role" in (r.stderr or ""),
           "exit=%s stderr=%s" % (r.returncode, (r.stderr or "")[-300:]))

        refused_target = work / "refused.yaml"
        r = run_cli("feature_registry/discovery_to_binding.py", "--input", discovery_json,
                    "-o", refused_target)
        ok("C4: without --select the adapter refuses (exit 1) instead of choosing top-1",
           r.returncode == 1 and "no_explicit_bindings" in (r.stderr or ""),
           "exit=%s stderr=%s" % (r.returncode, (r.stderr or "")[-200:]))
        ok("C5: the refusal writes no binding document", not refused_target.exists(),
           str(refused_target))

        # ==================== D. Resource Binding ====================
        print()
        print("--- D. resource binding (explicit override -> binding document) ---")
        bindings = work / "bindings.yaml"
        r = run_cli("asset_registry/bind_assets.py", "--gameplay", gameplay,
                    "--binding", override, "--out", bindings)
        ok("D1: bind_assets exits 0", r.returncode == 0, (r.stderr or r.stdout)[-300:])
        doc = yaml.safe_load(bindings.read_text(encoding="utf-8")) if bindings.is_file() else {}
        entities = ((doc.get("binding") or {}).get("entities") or [])
        ok("D2: binding document is schema_version 2 with one block per gameplay entity",
           doc.get("schema_version") == 2
           and {e.get("entity") for e in entities} == set(bp["entities"]),
           repr(doc.get("schema_version")))
        enemy_block = next((e for e in entities if e.get("entity") == "enemy"), {})
        by_role = {b["role"]: b for b in enemy_block.get("bindings") or []}
        ok("D3: explicitly selected slots record resolved_from=binding and confidence=high",
           all(by_role.get(slot) and by_role[slot]["resolved_from"] == "binding"
               and by_role[slot]["confidence"] == "high"
               and by_role[slot]["asset"] == selections[slot]
               for slot in required_slots),
           repr({s: (by_role.get(s) or {}).get("resolved_from") for s in required_slots}))
        inferred = [b for b in enemy_block.get("bindings") or [] if b["role"] not in selections]
        ok("D4: unselected (optional) slots stay distinguishable as index inference",
           bool(inferred) and all(b["resolved_from"] == "index" for b in inferred),
           repr([(b["role"], b["resolved_from"]) for b in inferred]))
        ok("D5: no required role is reported missing for the enemy entity",
           not (enemy_block.get("missing") or []), repr(enemy_block.get("missing")))

        # ---- 场景 1：多实体、不同资源——作用域绑定只作用于目标实体，不跨实体覆盖 ----
        player_block = next((e for e in entities if e.get("entity") == "player"), {})
        leaked_into_player = [b for b in player_block.get("bindings") or []
                              if b["role"] in selections
                              and b.get("asset") == selections[b["role"]]]
        ok("D6: entity-scoped bindings do not leak into the other entity (no overwrite)",
           not leaked_into_player,
           repr([(b["role"], b.get("asset")) for b in leaked_into_player]))
        ok("D6b: the target entity records the entity-scoped source on every selected slot",
           all("entity-scoped" in ((by_role.get(slot) or {}).get("note") or "")
               for slot in required_slots),
           repr({s: (by_role.get(s) or {}).get("note") for s in required_slots}))

        # ---- 场景 2：显式实体绑定 vs 索引推断——显式必须获胜，不得被推断覆盖 ----
        conflict_bp = work / "conflict_gameplay.yaml"
        conflict_bp.write_text(yaml.safe_dump({
            "gameplay": {"id": "conflict_game"},
            "entities": {"enemy": {"role": "enemy",
                                   "features": ["chase_movement", "health"]}},
        }, sort_keys=False), encoding="utf-8")
        inferred_out = work / "inferred_bindings.yaml"
        r = run_cli("asset_registry/bind_assets.py", "--gameplay", conflict_bp,
                    "--out", inferred_out)
        ok("D7 setup: the inference-only run exits 0", r.returncode == 0,
           (r.stderr or r.stdout)[-200:])
        inferred_doc = (yaml.safe_load(inferred_out.read_text(encoding="utf-8"))
                        if inferred_out.is_file() else {})
        inferred_enemy = next((e for e in (inferred_doc.get("binding") or {}).get("entities") or []
                               if e.get("entity") == "enemy"), {})
        inferred_idle = next((b.get("asset") for b in inferred_enemy.get("bindings") or []
                              if b.get("role") == "idle"), "")
        explicit_conflict_asset = "slime_idle" if inferred_idle != "slime_idle" else "slime_frames"
        conflict_binding = work / "conflict_binding.yaml"
        conflict_binding.write_text(yaml.safe_dump({
            "bindings": [{"entity": "enemy", "role": "idle",
                          "asset": explicit_conflict_asset}],
        }, sort_keys=False), encoding="utf-8")
        scoped_out = work / "scoped_bindings.yaml"
        r = run_cli("asset_registry/bind_assets.py", "--gameplay", conflict_bp,
                    "--binding", conflict_binding, "--out", scoped_out)
        scoped_doc = (yaml.safe_load(scoped_out.read_text(encoding="utf-8"))
                      if scoped_out.is_file() else {})
        scoped_enemy = next((e for e in (scoped_doc.get("binding") or {}).get("entities") or []
                             if e.get("entity") == "enemy"), {})
        scoped_idle = next((b for b in scoped_enemy.get("bindings") or []
                            if b.get("role") == "idle"), {})
        ok("D7: the explicit entity binding wins over index inference (no override)",
           r.returncode == 0 and inferred_idle != explicit_conflict_asset
           and scoped_idle.get("asset") == explicit_conflict_asset
           and scoped_idle.get("resolved_from") == "binding",
           repr((inferred_idle, explicit_conflict_asset, scoped_idle.get("asset"),
                 scoped_idle.get("resolved_from"))))

        # ---- 场景 3：未知实体——明确诊断 + 非零退出，不产出成功假象 ----
        unknown_binding = work / "unknown_entity_binding.yaml"
        unknown_binding.write_text(yaml.safe_dump({
            "bindings": [{"entity": "ghost_entity", "role": "idle",
                          "asset": "slime_idle"}],
        }, sort_keys=False), encoding="utf-8")
        unknown_out = work / "unknown_entity_bindings.yaml"
        r = run_cli("asset_registry/bind_assets.py", "--gameplay", conflict_bp,
                    "--binding", unknown_binding, "--out", unknown_out)
        combined = (r.stdout or "") + (r.stderr or "")
        ok("D8: an unknown-entity scope fails with a locatable diagnostic (exit 1)",
           r.returncode == 1 and "ghost_entity" in combined
           and "scoped to unknown entity" in combined,
           "exit=%s tail=%s" % (r.returncode, combined[-300:]))
        unknown_doc = (yaml.safe_load(unknown_out.read_text(encoding="utf-8"))
                       if unknown_out.is_file() else {})
        scope_errors = (unknown_doc.get("binding") or {}).get("binding_scope_errors") or []
        ok("D8: the failed run records the scope error instead of faking success",
           bool(scope_errors) and scope_errors[0].get("entity") == "ghost_entity"
           and scope_errors[0].get("location"),
           repr(scope_errors))

        # ==================== E. Scene Composer（Scene Intent 契约） ====================
        print()
        print("--- E. scene composer / scene intent ---")
        out_dir = work / "Scenes"
        r = run_cli("scene_composer/scene_composer.py", enemy_bp_path,
                    "--out", out_dir, "--bindings", bindings)
        ok("E1: composer CLI exits 0 (cross-drive --out/--bindings must not crash)",
           r.returncode == 0, (r.stdout + r.stderr)[-400:])
        scene_file = out_dir / "Enemy.tscn"
        ok("E2: .tscn written and validation reported PASS",
           scene_file.is_file() and "Validation: PASS" in (r.stdout or ""),
           (r.stdout or "")[-300:])
        tscn = scene_file.read_text(encoding="utf-8") if scene_file.is_file() else ""
        ok("E3: every component is instantiated from its Feature entry scene",
           all(('path="res://Features/%s/' % fid) in tscn
               for fid in enemy_bp.get("features") or []),
           tscn[:300])
        bound_nodes = [by_role[slot]["node"] for slot in required_slots
                       if (by_role.get(slot) or {}).get("node")]
        ok("E4: resource nodes and resources come from the binding document",
           bool(bound_nodes)
           and all(('path="%s"' % node["path"]) in tscn for node in bound_nodes)
           and all(('node name="%s"' % node["name"]) in tscn for node in bound_nodes),
           repr([n.get("name") for n in bound_nodes]))
        ok("E5: root node carries no script (the scene only composes)",
           "script = ExtResource" not in tscn and 'type="Script"' not in tscn, tscn[:200])

        import scene_composer as composer_module               # noqa: E402
        result = composer_module.compose(
            yaml.safe_load(enemy_bp_path.read_text(encoding="utf-8")),
            out_dir=str(out_dir), bindings_path=str(bindings))
        intent = result.get("scene_intent") or {}
        ok("E6: the generation input is a contract-conform Scene Intent",
           result.get("ok") is True and intent.get("document") == "scene_intent"
           and intent.get("schema_version") == 1
           and bool((intent.get("root") or {}).get("name"))
           and bool(intent.get("components")),
           repr({k: intent.get(k) for k in ("document", "schema_version", "components")}))
        ok("E7: capabilities travelled from member Features into the Scene Intent",
           bool((intent.get("capabilities") or {}).get("required")),
           repr(intent.get("capabilities")))
        ok("E8: compatibility gate ran before generation and reported PASS",
           (result.get("compatibility") or {}).get("status") == "PASS",
           repr(result.get("compatibility")))
        ok("E9: artifact evidence verified the written scene (declaration == plan == artifact)",
           (result.get("artifact_evidence") or {}).get("status") == "PASS",
           repr(result.get("artifact_evidence")))

        # ==================== F. 静态验证 ====================
        print()
        print("--- F. static validation ---")
        r = run_cli("validator/check_scene_composition.py", enemy_bp_path, "--scene", scene_file)
        ok("F1: independent scene composition validation PASS",
           r.returncode == 0 and "PASS" in (r.stdout or ""), (r.stdout + r.stderr)[-400:])

        # ==================== G. 闭环：gameplay -> 场景 -> check_gameplay -> Godot ==============
        print()
        print("--- G. closed loop: gameplay blueprint -> generated scenes -> checks -> godot ---")
        probe_gameplay = work / "e2e_probe_game.yaml"
        probe_gameplay.write_text(
            yaml.safe_dump(_PROBE_GAMEPLAY, sort_keys=False, allow_unicode=True),
            encoding="utf-8")
        probe_entities = work / "probe_entities"

        r = run_cli("gameplay_planner/planner.py", "--help")
        ok("G1: planner CLI exposes --emit-entities", "--emit-entities" in (r.stdout or ""),
           (r.stdout or "")[:200])
        r = run_cli("scene_composer/scene_composer.py", probe_gameplay, "--dry-run")
        ok("G2: Scene Composer rejects a raw Gameplay Blueprint"
           " (the blueprint layer must go through the per-entity emitter)",
           r.returncode != 0 and "has no components" in (r.stdout or ""), (r.stdout or "")[-200:])

        # Gameplay Blueprint -> 每实体 Entity Blueprint：导入的是唯一实现（planner --emit-entities
        # 走同一函数；planner 只收自然语言需求，夹具蓝图只能走函数入口）。
        sys.path.insert(0, str(TOOLS / "gameplay_planner"))
        import blueprint_generator as bpgen                     # noqa: E402
        written = bpgen.write_entity_blueprints(_PROBE_GAMEPLAY, probe_entities)
        probe_enemy_bp = probe_entities / "e2e_probe_enemy.yaml"
        ok("G3: per-entity blueprint written only for entities without a reused scene",
           [Path(p).name for p in written] == ["e2e_probe_enemy.yaml"] and probe_enemy_bp.is_file(),
           str([Path(p).name for p in written]))

        r = run_cli("validator/check_gameplay.py", probe_gameplay)
        ok("G4: gameplay validation fails while the entity scene does not exist"
           " (the check is real, not a rubber stamp)",
           r.returncode == 1 and "Missing Entity Scene: E2eProbeEnemy" in (r.stdout or ""),
           (r.stdout or "")[-300:])

        probe_bindings = work / "probe_bindings.yaml"
        r = run_cli("asset_registry/bind_assets.py", "--gameplay", probe_gameplay,
                    "--out", probe_bindings)
        ok("G5: index inference binds the probe enemy without an explicit override",
           r.returncode == 0 and probe_bindings.is_file(), (r.stderr or r.stdout)[-300:])

        r = run_cli("scene_composer/scene_composer.py", probe_enemy_bp,
                    "--out", PROJECT_ROOT / "Scenes", "--bindings", probe_bindings, "--tests")
        probe_written = _PROBE_SCENE.is_file()
        probe_test_written = _PROBE_TEST.is_file()
        ok("G6: scene and its regression test composed into the project (res:// runnable)",
           r.returncode == 0 and probe_written and probe_test_written
           and "E2eProbeEnemy.tscn" in (r.stdout or "") and "Validation: PASS" in (r.stdout or ""),
           (r.stdout + r.stderr)[-400:])

        r = run_cli("validator/check_gameplay.py", probe_gameplay)
        ok("G7: gameplay validation PASS once the generated scene exists (loop closed)",
           r.returncode == 0 and "PASS" in (r.stdout or ""), (r.stdout or "")[-300:])

        # ---- G6b–G6d: 生成实体的结构语义（Phase 1.11）----
        # 这些断言不代替行为断言（静态通过 ≠ 玩法通过），只锁定「生成物长什么样」：
        # 实体根必须承担实体运动职责，且接触伤害需要真实的碰撞形状。
        probe_tscn = _PROBE_SCENE.read_text(encoding="utf-8") if probe_written else ""
        ok("G6b: the generated entity root is the chase Feature entry scene instance",
           probes_ok_scene_root(probe_tscn), probe_tscn[:260])
        ok("G6c: the generated entity carries real collision shapes (body + contact)",
           'name="Collision" type="CollisionShape2D" parent="."' in probe_tscn
           and 'name="ContactShape" type="CollisionShape2D" parent="ContactDamage"' in probe_tscn,
           probe_tscn[-300:])
        probe_test_source = _PROBE_TEST.read_text(encoding="utf-8") if probe_test_written else ""
        ok("G6d: the generated regression test asserts the entity root type for the root instance",
           "if not (entity is CharacterBody2D):" in probe_test_source
           and "Missing Feature root: chase_movement" in probe_test_source
           and 'entity.get_node_or_null("ChaseMovement")' not in probe_test_source,
           probe_test_source[:300])

        godot = find_godot()
        if godot is None:
            skip("G8: real Godot runtime playtest of the generated scene",
                 "godot executable not found (set GODOT_BIN / add to PATH)")
            skip("G9: real Godot run of the generated scene regression test",
                 "godot executable not found (set GODOT_BIN / add to PATH)")
        else:
            r = run_cli("runtime/run_scene.py", "--project", PROJECT_ROOT,
                        "--scene", "res://Scenes/E2eProbeEnemy.tscn", timeout=180)
            ok("G8: real Godot headless run of the freshly generated scene reports PASS",
               r.returncode == 0 and "status=PASS" in (r.stdout or "")
               and "errors=0" in (r.stdout or ""), (r.stdout + r.stderr)[-400:])
            r = run_godot_script(godot, "res://Tests/test_e2e_probe_enemy.gd")
            output = (r.stdout or "") + (r.stderr or "")
            ok("G9: the generated scene regression test passes on the generated scene",
               r.returncode == 0 and "PASS" in output, output[-400:])

            # ---- G10: 真实玩法行为断言（Phase 1.10）----
            # 被测对象 = 上面刚生成的实体场景；观察的是真实物理帧里的距离变化。
            import behavior_probe                                 # noqa: E402
            facing = behavior_probe.run_behavior_probe(
                "res://Scenes/E2eProbeEnemy.tscn", project_root=PROJECT_ROOT, godot=godot)
            metrics = facing.metrics
            print("      behavior: %s" % " ".join("%s=%s" % (k, metrics[k])
                                                 for k in sorted(metrics)))
            ok("G10a: the generated scene passes the real gameplay behavior probe (exit 0)",
               facing.ok and facing.exit_code == 0
               and "PASS: 生成场景玩法行为验证通过" in facing.output,
               (facing.output or "")[-400:])
            ok("G10b: the probe observed a real distance change, not structural existence",
               all(key in metrics
                   for key in ("distance_before", "distance_after", "approach", "baseline_drift"))
               and metrics["distance_before"] >= 2 * behavior_probe.MIN_APPROACH
               and metrics["distance_after"] < metrics["distance_before"]
               and metrics["distance_before"] - metrics["distance_after"]
               >= behavior_probe.MIN_APPROACH,
               repr(metrics))
            ok("G10c: without a configured target the entity stays still (assertion is not vacuous)",
               metrics.get("baseline_drift", 1e9) <= behavior_probe.DRIFT_TOLERANCE,
               repr(metrics))
            ok("G10d: after the target is freed the entity stops moving",
               metrics.get("post_free_drift", 1e9) <= behavior_probe.DRIFT_TOLERANCE,
               repr(metrics))
            ok("G10e: the transient probe script is removed from the project",
               facing.script_removed
               and not (PROJECT_ROOT / behavior_probe.PROBE_SCRIPT_REL).exists(),
               behavior_probe.PROBE_SCRIPT_REL)
            # ---- G10f–G10h: Phase 1.11 —— 实体根位移与接触伤害（真实物理帧）----
            ok("G10f: the ENTITY ROOT itself moved towards the target (not only a child component)",
               metrics.get("root_approach", -1.0) >= behavior_probe.MIN_APPROACH,
               repr({k: metrics.get(k) for k in ("root_approach", "approach", "chase_drift")}))
            ok("G10g: no child component moved itself (the root owns the movement)",
               metrics.get("child_max_drift", 1e9) <= behavior_probe.DRIFT_TOLERANCE,
               repr({k: metrics.get(k) for k in ("child_max_drift", "chase_drift")}))
            ok("G10h: physical contact settles damage through the real Health mechanism"
               " (per tick_interval, no per-frame damage, none while out of contact)",
               metrics.get("no_contact_damage", -1.0) == 0.0
               and metrics.get("damage_total", 0.0) >= 1.0
               and metrics.get("damage_total", 1e9) <= metrics.get("damage_ceiling", -1.0)
               and metrics.get("hp_after", 1e9) < metrics.get("hp_before", -1.0),
               repr({k: metrics.get(k) for k in ("no_contact_damage", "damage_total",
                                                 "damage_ceiling", "hp_before", "hp_after",
                                                 "tick_interval", "contact_distance")}))

            # ---- G11: 受控负向 —— 缺少行为时探针必须失败（否则断言无意义）----
            nocase_gameplay = work / "nocase_gameplay.yaml"
            nocase_gameplay.write_text(yaml.safe_dump({
                "gameplay": {"id": "e2e_probe_static"},
                "entities": {"e2e_probe_nochase": {"role": "enemy", "features": ["health"]}},
                "systems": ["enemy_spawn", "reward"],
                "loop": {"start": "player spawned", "cycle": "enemy spawn",
                         "end": "enemy defeated; reward gained"},
                "validation": {"required_entities": ["e2e_probe_nochase"],
                               "required_features": ["damage_source"],
                               "required_tests": ["health"]},
            }, sort_keys=False, allow_unicode=True), encoding="utf-8")
            nocase_entities = work / "nocase_entities"
            bpgen.write_entity_blueprints(yaml.safe_load(
                nocase_gameplay.read_text(encoding="utf-8")), nocase_entities)
            r = run_cli("scene_composer/scene_composer.py",
                        nocase_entities / "e2e_probe_nochase.yaml",
                        "--out", PROJECT_ROOT / "Scenes")
            nocase_written = _NOCASE_SCENE.is_file()
            ok("G11a: a second generated scene (health only, no chase component) was composed",
               r.returncode == 0 and nocase_written, (r.stdout + r.stderr)[-300:])
            nocase = behavior_probe.run_behavior_probe(
                "res://Scenes/E2eProbeNochase.tscn", project_root=PROJECT_ROOT, godot=godot)
            ok("G11: the same probe fails with a precondition diagnostic when the behavior is absent",
               (not nocase.ok) and nocase.exit_code != 0
               and any("Precondition" in message and "ChaseMovement" in message
                       for message in nocase.failure_messages),
               "exit=%s messages=%s" % (nocase.exit_code, nocase.failure_messages[:2]))

            # ---- G12: 受控负向 —— 接触伤害断言依赖真实碰撞形状（否则断言无意义）----
            # 变异体 = 同一生成场景去掉 ContactShape 节点（其余逐字不变）：物理上重合，
            # 但没有任何碰撞形状 → 不应产生伤害；同一探针在 expect=damage 下必须失败。
            mutant_written = write_contact_shape_mutant(_PROBE_SCENE, _MUTANT_SCENE)
            ok("G12a: the contact-damage mutant scene was produced from the generated scene"
               " (ContactShape removed, everything else byte-identical)",
               mutant_written, str(_MUTANT_SCENE))
            if mutant_written:
                mutant_none = behavior_probe.run_behavior_probe(
                    "res://Scenes/E2eProbeNoContact.tscn", project_root=PROJECT_ROOT,
                    godot=godot, contact=behavior_probe.CONTACT_NONE)
                # 同一物理配置（接触间距与正常生成物一致 + 实体根同样移动）+ 无接触形状
                # → 伤害必为 0：证明 G10h 依赖真实碰撞，而不是「探针自己说了算」。
                same_contact = (mutant_none.metrics.get("contact_distance", -1.0)
                                - facing.metrics.get("contact_distance", -2.0)) <= 1.0
                ok("G12b: without a contact shape the probe observes ZERO damage on real overlap"
                   " (same physical configuration, only the mutation differs)",
                   mutant_none.ok and mutant_none.metrics.get("damage_total") == 0.0
                   and same_contact
                   and mutant_none.metrics.get("root_approach", -1.0) >= behavior_probe.MIN_APPROACH,
                   "exit=%s metrics=%s" % (mutant_none.exit_code,
                                           {k: mutant_none.metrics.get(k) for k in
                                            ("damage_total", "contact_distance", "root_approach")}))
                mutant_damage = behavior_probe.run_behavior_probe(
                    "res://Scenes/E2eProbeNoContact.tscn", project_root=PROJECT_ROOT, godot=godot)
                ok("G12c: the same mutant fails the positive contact-damage assertion"
                   " (G10h is not vacuous)",
                   (not mutant_damage.ok) and mutant_damage.exit_code != 0
                   and any("Contact Damage" in message
                           for message in mutant_damage.failure_messages),
                   "exit=%s messages=%s" % (mutant_damage.exit_code,
                                            mutant_damage.failure_messages[:2]))
                ok("G12d: the second entity root movement assertion still holds on the mutant",
                   mutant_damage.metrics.get("root_approach", -1.0) >= behavior_probe.MIN_APPROACH,
                   repr(mutant_damage.metrics.get("root_approach")))

            # ---- J: 死亡与胜利闭环（Phase 1.12）----
            # 被测对象 = 上面刚生成的实体场景；宿主 = 项目真实竞技场场景（承载既有胜负逻辑：
            # 全部必需敌人死亡 → 打开出口门 → 玩家进出口区 → Completed）。伤害只走
            # 真实玩家攻击输入路径（空格攻击 → AttackTrigger → Health.take_damage），
            # 断言的是运行时状态：生命值 / 死亡事件次数 / 存活计数 / 出口门 / 胜负状态。
            import death_victory_probe                            # noqa: E402
            if not probe_written:
                ok("J1: the generated entity scene exists for the death loop", False,
                   str(_PROBE_SCENE))
            else:
                death = death_victory_probe.run_death_victory_probe(
                    "res://Scenes/E2eProbeEnemy.tscn", project_root=PROJECT_ROOT, godot=godot)
                death_metrics = death.metrics
                print("      death: %s" % " ".join("%s=%s" % (k, death_metrics[k])
                                                 for k in sorted(death_metrics)))
                ok("J1: the generated entity walks the real death flow through the player attack path",
                   death.ok and death.exit_code == 0
                   and "PASS: 生成实体死亡与胜利闭环验证通过" in death.output,
                   (death.output or "")[-400:])
                ok("J2: real attacks (not test-set state) drained the health to zero",
                   death_metrics.get("attack_damage", 0.0) == 1.0
                   and death_metrics.get("hp_before", 0.0) == death_metrics.get("max_health", -1.0)
                   and death_metrics.get("hp_after_first", 1e9) < death_metrics.get("hp_before", -1.0)
                   and death_metrics.get("hp_after_kill", -1.0) == 0.0
                   and death_metrics.get("attacks", 0.0) >= death_metrics.get("max_health", 0.0),
                   repr({k: death_metrics.get(k) for k in
                         ("hp_before", "hp_after_first", "hp_after_kill", "attacks")}))
                ok("J3: death reached the existing game system exactly once"
                   " (died once, kill count −1 once, entity left combat, entity state == count)",
                   death_metrics.get("died_events", 0.0) == 1.0
                   and death_metrics.get("alive_before", 0.0) == 2.0
                   and death_metrics.get("alive_after_death", 0.0) == 1.0
                   and death_metrics.get("alive_after_extra", 0.0) == 1.0
                   and death_metrics.get("removed", 0.0) == 1.0
                   and death_metrics.get("live_entities", 0.0) == 1.0,
                   repr({k: death_metrics.get(k) for k in
                         ("died_events", "alive_before", "alive_after_death",
                          "alive_after_extra", "removed", "live_entities")}))
                ok("J4: no premature victory while a required enemy still survives (V2)",
                   death_metrics.get("door_open_with_survivor", 1.0) == 0.0
                   and death_metrics.get("premature_victory", 1.0) == 0.0,
                   repr({k: death_metrics.get(k) for k in
                         ("door_open_with_survivor", "premature_victory")}))
                ok("J5: the game scene itself decides victory after the LAST required enemy dies (V1)",
                   death_metrics.get("door_open_after_last", 0.0) == 1.0
                   and death_metrics.get("state_before_exit", -1.0) == 0.0
                   and death_metrics.get("state_after_exit", -1.0) == 1.0
                   and death_metrics.get("finish_events", 0.0) == 1.0,
                   repr({k: death_metrics.get(k) for k in
                         ("door_open_after_last", "state_before_exit", "state_after_exit",
                          "finish_events")}))
                ok("J6: the transient death/victory probe script is removed from the project",
                   death.script_removed
                   and not (PROJECT_ROOT / death_victory_probe.PROBE_SCRIPT_REL).exists(),
                   death_victory_probe.PROBE_SCRIPT_REL)
                reference = death_victory_probe.run_death_victory_probe(
                    death_victory_probe.DEFAULT_REFERENCE_ENEMY,
                    project_root=PROJECT_ROOT, godot=godot)
                ok("J7: the handwritten Enemy scene gets the same result"
                   " (the generated entity reuses the same death/management interface)",
                   reference.ok and reference.exit_code == 0
                   and reference.metrics.get("died_events", 0.0) == 1.0
                   and reference.metrics.get("alive_after_death", 0.0) == 1.0
                   and reference.metrics.get("finish_events", 0.0) == 1.0,
                   (reference.output or "")[-400:])

                # ---- J8: 受控负向 —— 胜利断言依赖真实死亡（否则断言无意义）----
                # 变异体 = 同一生成场景把 Health.max_health 抬到攻击预算之上（其余逐字保留）：
                # 攻击打不死 → 不得开启出口、不得进入胜负终态；同一变异体在正向期望下必须失败。
                immortal_written = write_immortal_mutant(_PROBE_SCENE, _IMMORTAL_SCENE)
                ok("J8a: the unkillable mutant was produced from the generated scene"
                   " (only Health.max_health patched)", immortal_written, str(_IMMORTAL_SCENE))
                if immortal_written:
                    survive = death_victory_probe.run_death_victory_probe(
                        "res://Scenes/E2eProbeImmortal.tscn", project_root=PROJECT_ROOT,
                        godot=godot, expect=death_victory_probe.EXPECT_SURVIVE)
                    ok("J8b: with an unkillable enemy the probe observes ZERO victory"
                       " (no finish event, state unchanged, door closed)",
                       survive.ok and survive.exit_code == 0
                       and survive.metrics.get("finish_events", -1.0) == 0.0
                       and survive.metrics.get("state_after_exit", -1.0) == 0.0
                       and survive.metrics.get("door_open_with_survivor", 1.0) == 0.0
                       and survive.metrics.get("hp_after_kill", 0.0) > 0.0,
                       (survive.output or "")[-400:])
                    doomed = death_victory_probe.run_death_victory_probe(
                        "res://Scenes/E2eProbeImmortal.tscn", project_root=PROJECT_ROOT,
                        godot=godot)
                    ok("J8c: the same mutant fails the positive expectation"
                       " (J1/J5 are not vacuous)",
                       (not doomed.ok) and doomed.exit_code != 0
                       and any("Death" in message or "Victory" in message
                               for message in doomed.failure_messages),
                       "exit=%s messages=%s" % (doomed.exit_code,
                                                doomed.failure_messages[:2]))

                # ---- J9: 缺少运动能力的生成实体无法满足既有敌人管理接口 ----
                # 对照 G11 的同一生成物（仅含 health）：竞技场生成链路要求实体根可接收
                # target_path，因此它必须失败，且不得被当成「已进入死亡流程」。
                if nocase_written:
                    interface = death_victory_probe.run_death_victory_probe(
                        "res://Scenes/E2eProbeNochase.tscn", project_root=PROJECT_ROOT,
                        godot=godot)
                    ok("J9: an entity missing the motion component cannot enter the existing"
                       " enemy management interface (fails with a diagnostic)",
                       (not interface.ok) and interface.exit_code != 0
                       and (any("Precondition" in message
                                for message in interface.failure_messages)
                            or "SCRIPT ERROR" in interface.output),
                       "exit=%s messages=%s" % (interface.exit_code,
                                                interface.failure_messages[:2]))
            # ---- K: 关卡编排生成与运行时消费（Phase 1.13）----
            # 生成链路的下一层：Gameplay Blueprint -> 关卡配置（生成物）-> 真实 Godot 运行时。
            # 配置里引用的实体场景就是上面刚生成的 E2eProbeEnemy.tscn（未经人工编辑）。
            import level_planner                                   # noqa: E402
            import level_orchestration_probe as level_probe         # noqa: E402
            level_path = PROJECT_ROOT / "Levels" / "E2eProbeLevel.json"
            broken_level_path = PROJECT_ROOT / "Levels" / "E2eProbeLevelBroken.json"
            if not probe_written:
                ok("K1: the generated entity scene exists for level orchestration generation",
                   False, str(_PROBE_SCENE))
            else:
                r = run_cli("gameplay_planner/level_planner.py", probe_gameplay,
                            "--out", level_path, "--level-id", "e2e_probe_level",
                            "--waves", "2", "--wave-size", "2")
                level_written = level_path.is_file()
                ok("K1: the level config is generated from the gameplay blueprint (exit 0, written)",
                   r.returncode == 0 and level_written and "Validation: PASS" in (r.stdout or ""),
                   (r.stdout + r.stderr)[-400:])
                level_doc = (json.loads(level_path.read_text(encoding="utf-8"))
                             if level_written else {})
                declared = level_probe.declared_scenes_of(level_doc)
                counts = level_probe.wave_counts_of(level_doc)
                ok("K2: the config references the GENERATED entity scene and declares 2 waves (2 + 3)",
                   "res://Scenes/E2eProbeEnemy.tscn" in declared and counts == [2, 3],
                   repr((declared, counts)))
                r = run_cli("validator/check_level.py", level_path)
                ok("K3: the independent level validator PASSes the generated config",
                   r.returncode == 0 and "PASS" in (r.stdout or ""),
                   (r.stdout + r.stderr)[-300:])

                # 受控负向（静态）：同一实现必须拒绝非法数量并定位到字段
                broken_doc = json.loads(json.dumps(level_doc))
                broken_doc["waves"][0]["entries"][0]["count"] = 0
                broken_level_path.write_text(json.dumps(broken_doc, ensure_ascii=False, indent=2) + "\n",
                                             encoding="utf-8", newline="\n")
                broken_level_written = True
                r = run_cli("validator/check_level.py", broken_level_path)
                ok("K4: the validator rejects an invalid count with a locatable failure",
                   r.returncode == 1 and "waves[0].entries[0].count" in (r.stdout + r.stderr),
                   "exit=%s %s" % (r.returncode, (r.stdout + r.stderr)[-200:]))

                # ---- K5–K11: 真实运行时（生成的配置 + 生成的实体场景）----
                level_run = level_probe.run_level_probe(
                    "res://Levels/E2eProbeLevel.json", project_root=PROJECT_ROOT, godot=godot,
                    focus_scene="res://Scenes/E2eProbeEnemy.tscn")
                level_metrics = level_run.metrics
                print("      level: %s" % " ".join("%s=%s" % (k, level_metrics[k])
                                                   for k in sorted(level_metrics)))
                ok("K5: the generated level config drives the real Godot runtime (probe exit 0)",
                   level_run.ok and level_run.exit_code == 0
                   and "PASS: 关卡编排配置驱动验证通过" in level_run.output,
                   (level_run.output or "")[-400:])
                ok("K6: spawn counts come from the config (wave 1 = 2), not from any scene data",
                   level_metrics.get("config_errors", -1.0) == 0.0
                   and level_metrics.get("waves", -1.0) == 2.0
                   and level_metrics.get("wave1_count", -1.0) == 2.0
                   and level_metrics.get("spawned_wave1", -1.0) == 2.0,
                   repr({k: level_metrics.get(k) for k in
                         ("config_errors", "waves", "wave1_count", "spawned_wave1")}))
                ok("K7: wave 2 starts only after wave 1 is cleared, and only once",
                   level_metrics.get("index_after_wave1", -1.0) == 1.0
                   and level_metrics.get("alive_after_wave1", -1.0) == 3.0
                   and level_metrics.get("wave2_count", -1.0) == 3.0,
                   repr({k: level_metrics.get(k) for k in
                         ("index_after_wave1", "alive_after_wave1", "wave2_count")}))
                ok("K8: the exit stays closed while enemies survive and opens after the last wave",
                   level_metrics.get("door_open_with_survivor", -1.0) == 0.0
                   and level_metrics.get("door_open_after_all", -1.0) == 1.0,
                   repr({k: level_metrics.get(k) for k in
                         ("door_open_with_survivor", "door_open_after_all")}))
                ok("K9: the player reaching the exit completes the level, victory emitted once",
                   level_metrics.get("state_after_exit", -1.0) == 1.0
                   and level_metrics.get("finish_events", -1.0) == 1.0,
                   repr({k: level_metrics.get(k) for k in ("state_after_exit", "finish_events")}))
                ok("K10: the spawned enemies ARE the generated scene (artifact identity)",
                   level_metrics.get("entity_scene_match", 0.0) == 1.0
                   and level_metrics.get("focus_hits", 0.0) >= 1.0,
                   repr({k: level_metrics.get(k) for k in ("entity_scene_match", "focus_hits")}))
                ok("K11: the transient level probe script is removed from the project",
                   level_run.script_removed
                   and not (PROJECT_ROOT / level_probe.PROBE_SCRIPT_REL).exists(),
                   level_probe.PROBE_SCRIPT_REL)

                # ---- K12: 受控负向（运行时）—— 无效配置必须被拒绝 ----
                invalid_run = level_probe.run_level_probe(
                    "res://Levels/E2eProbeLevelBroken.json", project_root=PROJECT_ROOT,
                    godot=godot, expect=level_probe.EXPECT_INVALID,
                    focus_scene="res://Scenes/E2eProbeEnemy.tscn")
                ok("K12: the runtime refuses the invalid config (zero spawns, locatable diagnostic)",
                   invalid_run.ok and invalid_run.exit_code == 0
                   and invalid_run.metrics.get("spawned_wave1", -1.0) == 0.0
                   and invalid_run.metrics.get("state", -1.0) == 2.0,
                   (invalid_run.output or "")[-400:])

        # ==================== L. 多实体组合与绑定完整性（Phase 1.17） ====================
        # 双实体显式绑定闭环：player 与 enemy 一样走 discovery -> 身份解析 ->
        # 绑定生成 -> bind_assets -> 场景生成；再由 Godot 原生 instancing 组合进同一宿主。
        print()
        print("--- L. multi-entity composition & binding integrity ---")
        player_probe_gameplay = work / "player_probe_game.yaml"
        player_probe_gameplay.write_text(yaml.safe_dump({
            "gameplay": {"id": "e2e_probe_player_game"},
            "entities": {"e2e_probe_player": {"role": "player",
                                              "features": ["health", "player_movement"]}},
            "systems": [],
            "loop": {"start": "player spawned", "cycle": "player moves", "end": "player safe"},
            "validation": {"required_entities": ["e2e_probe_player"], "required_features": [],
                           "required_tests": ["health", "player_movement"]},
        }, sort_keys=False, allow_unicode=True), encoding="utf-8")
        player_probe_entities = work / "player_probe_entities"
        written_player = bpgen.write_entity_blueprints(
            yaml.safe_load(player_probe_gameplay.read_text(encoding="utf-8")),
            player_probe_entities)
        player_bp_path = player_probe_entities / "e2e_probe_player.yaml"
        ok("L1: a player entity blueprint is emitted (traceable id, no reused scene)",
           [Path(p).name for p in written_player] == ["e2e_probe_player.yaml"]
           and player_bp_path.is_file(),
           str([Path(p).name for p in written_player]))

        r = run_cli("feature_registry/feature_discovery.py",
                    "player character that moves and takes damage", "--json")
        ok("L2: player-role discovery exits 0 and resolves role=player", r.returncode == 0,
           (r.stderr or r.stdout)[-200:])
        player_payload = json.loads(r.stdout or "{}")
        player_selections = {}
        for slot, cands in (player_payload.get("asset_candidates") or {}).items():
            if cands:
                player_selections[slot] = cands[0]["id"]
        ok("L3: player discovery yields distinguishable player_* candidates",
           player_payload.get("role") == "player" and "idle" in player_selections
           and str(player_selections["idle"]).startswith("player_"),
           repr(player_selections))
        player_select_args = []
        for slot in sorted(player_selections):
            player_select_args += ["--select", "%s=%s" % (slot, player_selections[slot])]
        player_disc = work / "player_disc.json"
        player_disc.write_text(r.stdout or "{}", encoding="utf-8")
        player_override = work / "player_override.yaml"
        # 实体身份来源：player probe 蓝图中恰好一个 player 角色实体（与 enemy 链路同一机制）。
        r = run_cli("feature_registry/discovery_to_binding.py", "--input", player_disc,
                    *player_select_args, "--resolve-entity-from", player_probe_gameplay,
                    "-o", player_override)
        player_override_doc = (yaml.safe_load(player_override.read_text(encoding="utf-8"))
                               if player_override.is_file() else {})
        ok("L4: --resolve-entity-from stamps the resolved player identity on every binding",
           r.returncode == 0
           and all(set(entry) == {"entity", "role", "asset"}
                   and entry["entity"] == "e2e_probe_player"
                   for entry in player_override_doc.get("bindings") or []),
           repr(player_override_doc))

        player_bindings = work / "player_bindings.yaml"
        r = run_cli("asset_registry/bind_assets.py", "--gameplay", player_probe_gameplay,
                    "--binding", player_override, "--out", player_bindings)
        player_doc = (yaml.safe_load(player_bindings.read_text(encoding="utf-8"))
                      if player_bindings.is_file() else {})
        player_block = next((e for e in (player_doc.get("binding") or {}).get("entities") or []
                             if e.get("entity") == "e2e_probe_player"), {})
        player_by_role = {b["role"]: b for b in player_block.get("bindings") or []}
        ok("L5: bind_assets records the explicit player bindings (resolved_from=binding, high)",
           r.returncode == 0
           and all(player_by_role.get(slot)
                   and player_by_role[slot]["asset"] == player_selections[slot]
                   and player_by_role[slot]["resolved_from"] == "binding"
                   and player_by_role[slot]["confidence"] == "high"
                   for slot in player_selections),
           repr({s: player_by_role.get(s) for s in sorted(player_selections)}))

        r = run_cli("scene_composer/scene_composer.py", player_bp_path,
                    "--out", PROJECT_ROOT / "Scenes", "--bindings", player_bindings)
        probe_player_written = _PROBE_PLAYER_SCENE.is_file()
        ok("L6: the player entity scene is composed with the explicitly bound resources",
           r.returncode == 0 and probe_player_written
           and "Validation: PASS" in (r.stdout or ""),
           (r.stdout + r.stderr)[-300:])
        player_tscn = (_PROBE_PLAYER_SCENE.read_text(encoding="utf-8")
                       if probe_player_written else "")
        ok("L7: final resource attribution — the player scene carries the bound player assets",
           probe_player_written
           and all(('path="%s"' % (player_by_role[slot].get("node") or {}).get("path"))
                   in player_tscn for slot in player_selections
                   if (player_by_role.get(slot) or {}).get("node")),
           repr({s: (player_by_role.get(s) or {}).get("node") for s in sorted(player_selections)}))

        enemy_tscn = (_PROBE_SCENE.read_text(encoding="utf-8") if probe_written else "")
        ok("L8: no cross-entity asset leak — enemy scene has no player assets and vice versa",
           probe_written and probe_player_written
           and "characters/player" not in enemy_tscn
           and "characters/enemy" not in player_tscn,
           "enemy_has_player=%s player_has_enemy=%s"
           % ("characters/player" in enemy_tscn, "characters/enemy" in player_tscn))

        # ---- M. composition plan 自动生成（Phase 1.19）----
        # 计划由 plan_generator 依据**蓝图**与**真实生成产物**产生，不手写：
        #   实体 -> 场景：Scene Composer 的生成命名约定（Scenes/E2eProbeEnemy.tscn）；
        #   目标关系  ：蓝图派生的 entity_graph.json（planner 写出的同一函数）的 attack 边。
        print()
        print("--- M. composition plan generation ---")
        probe_graph = work / "probe_entity_graph.json"
        feature_index = json.loads((_DOTAI / "context" / "feature_index.json")
                                   .read_text(encoding="utf-8")).get("features") or []
        probe_graph.write_text(json.dumps(
            bpgen.build_entity_graph(_PROBE_GAMEPLAY, feature_index),
            ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        ok("M1: the blueprint derives the enemy->player relation (attack) from its features",
           any(edge.get("from") == "E2eProbeEnemy" and edge.get("to") == "E2eProbePlayer"
               and edge.get("relation") == "attack"
               for edge in json.loads(probe_graph.read_text(encoding="utf-8"))["edges"]),
           probe_graph.read_text(encoding="utf-8")[:300])

        # 蓝图对 player 声明了复用 Player.tscn（供前面的 discovery 链路使用）；
        # 本段使用的是 L 段**新生成**的带显式绑定的玩家场景，因此由调用方显式映射
        # （provenance = override，不靠目录扫描或模糊匹配）。
        player_scene_map = ["--entity-scene",
                            "e2e_probe_player=res://Scenes/E2eProbePlayer.tscn"]
        plain_plan = work / "dual_plan_plain.yaml"
        r = run_cli("scene_composer/plan_generator.py", probe_gameplay,
                    *player_scene_map,
                    "--host", "E2eProbePlainHost", "--out", plain_plan)
        plain_doc = (yaml.safe_load(plain_plan.read_text(encoding="utf-8"))
                     if plain_plan.is_file() else {})
        ok("M2: the plan is generated from the blueprint and the generated scenes "
           "(entity identity preserved, unrequested targets absent)",
           r.returncode == 0 and "Validation: PASS" in r.stdout
           and [(i.get("entity"), i.get("scene")) for i in plain_doc.get("instances") or []]
           == [("e2e_probe_enemy", "res://Scenes/E2eProbeEnemy.tscn"),
               ("e2e_probe_player", "res://Scenes/E2eProbePlayer.tscn")]
           and "targets" not in plain_doc,
           (r.stdout + r.stderr)[-400:] + repr(plain_doc.get("instances")))
        ok("M3: without a declared relation the generator invents no target",
           not plain_doc.get("targets")
           and not any("target" in name for name in plain_doc),
           repr(plain_doc))

        dual_plan = work / "dual_plan_generated.yaml"
        r = run_cli("scene_composer/plan_generator.py", probe_gameplay,
                    *player_scene_map,
                    "--host", "E2eProbeDualHost", "--relations", probe_graph,
                    "--relation", "attack", "--out", dual_plan)
        generated_plan = (yaml.safe_load(dual_plan.read_text(encoding="utf-8"))
                          if dual_plan.is_file() else {})
        ok("M4: the blueprint-derived relation becomes the declared target reference",
           r.returncode == 0 and generated_plan.get("targets")
           == [{"source": "E2eProbeEnemy", "target": "E2eProbePlayer"}],
           (r.stdout + r.stderr)[-400:] + repr(generated_plan.get("targets")))

        # 受控负向：缺场景映射 / 未知目标 —— 必须 exit 1 且不留计划产物。
        missing_bp = work / "plan_missing_scene.yaml"
        missing_bp.write_text(yaml.safe_dump({
            "gameplay": {"id": "e2e_plan_missing"},
            "entities": {
                "e2e_probe_missing": {"role": "enemy",
                                      "features": ["chase_movement", "health"]},
                "e2e_probe_player": _PROBE_GAMEPLAY["entities"]["e2e_probe_player"],
            },
        }, sort_keys=False, allow_unicode=True), encoding="utf-8")
        missing_out = work / "plan_missing_scene_out.yaml"
        r = run_cli("scene_composer/plan_generator.py", missing_bp,
                    "--host", "E2eProbeMissingHost", "--out", missing_out)
        ok("M5: a missing entity scene mapping is refused with a locatable diagnostic "
           "and no artifact",
           r.returncode == 1 and "e2e_probe_missing" in r.stdout
           and "res://Scenes/E2eProbeMissing.tscn" in r.stdout
           and not missing_out.exists(), (r.stdout + r.stderr)[-400:])
        r = run_cli("scene_composer/plan_generator.py", probe_gameplay,
                    "--host", "E2eProbeGhostTarget", "--target",
                    "e2e_probe_enemy:ghost_entity",
                    "--out", work / "plan_ghost_target.yaml")
        ok("M6: an unknown target entity is refused without an artifact",
           r.returncode == 1 and "ghost_entity" in r.stdout
           and not (work / "plan_ghost_target.yaml").exists(),
           (r.stdout + r.stderr)[-400:])

        # 自动生成的计划进入既有正式管线（composite.py 是唯一实现）。
        r = _run_compose_plan(dual_plan, dry_run=True)
        ok("L9: the composition plan passes the formal dry-run (validation without artifact)",
           r.returncode == 0 and "Validation: PASS" in r.stdout
           and not _PROBE_DUAL_SCENE.exists(), (r.stdout + r.stderr)[-300:])
        r = _run_compose_plan(dual_plan)
        dual_written = _PROBE_DUAL_SCENE.is_file()
        host_text = (_PROBE_DUAL_SCENE.read_text(encoding="utf-8") if dual_written else "")
        ok("L10: the formal entry composes the host with the declared target reference",
           r.returncode == 0 and dual_written
           and host_text.count("instance=ExtResource") == 2
           and 'target_path = NodePath("../E2eProbePlayer")' in host_text
           and "RectangleShape2D" not in host_text and "sprite_frames" not in host_text,
           host_text[:260])
        r = _run_compose_plan(_make_bad_plan(work))
        ok("L10b: an unknown target instance is refused by the formal entry (exit 1,"
           " no artifact)",
           r.returncode == 1 and "Ghost" in (r.stdout + r.stderr)
           and not _PROBE_BAD_HOST.exists(),
           "exit=%s tail=%s" % (r.returncode, (r.stdout + r.stderr)[-260:]))

        if godot is None:
            skip("L11: real Godot runtime of the multi-entity host scene",
                 "godot executable not found (set GODOT_BIN / add to PATH)")
        elif not (probe_written and probe_player_written and dual_written):
            ok("L11: the multi-entity host runtime check needs both generated scenes",
               False, "probe_written=%s player=%s dual=%s"
               % (probe_written, probe_player_written, dual_written))
        else:
            r = run_cli("runtime/run_scene.py", "--project", PROJECT_ROOT,
                        "--scene", "res://Scenes/E2eProbeDualHost.tscn", timeout=180)
            ok("L11: real Godot headless loads and runs the multi-entity host (status=PASS)",
               r.returncode == 0 and "status=PASS" in (r.stdout or "")
               and "errors=0" in (r.stdout or ""), (r.stdout + r.stderr)[-400:])
            # 瞬态探针：断言两个实例存在、命名不冲突，且运行时资源归属正确
            #（enemy 子树 = slime 资源，player 子树 = player 资源，互不覆盖）。
            _DUAL_PROBE_SCRIPT.write_text(DUAL_HOST_PROBE_GD, encoding="utf-8")
            try:
                rr = run_godot_script(godot, "res://Tests/e2e_dual_host_probe.gd")
                dual_output = (rr.stdout or "") + (rr.stderr or "")
                dual_report = {}
                for line in dual_output.splitlines():
                    if line.startswith("DUAL: "):
                        try:
                            dual_report = json.loads(line[len("DUAL: "):])
                        except ValueError:
                            dual_report = {}
                ok("L12: the host contains both entity instances under unique node names",
                   rr.returncode == 0
                   and dual_report.get("enemy_present") is True
                   and dual_report.get("player_present") is True
                   and len(dual_report.get("instance_names") or []) == 2,
                   dual_output[-400:])
                enemy_assets = [p for p in dual_report.get("enemy_assets") or []
                                if p.endswith((".tres", ".png"))]
                player_assets = [p for p in dual_report.get("player_assets") or []
                                 if p.endswith((".tres", ".png"))]
                ok("L13: at runtime the enemy instance carries the slime resources only",
                   bool(enemy_assets)
                   and all("characters/enemy" in p for p in enemy_assets),
                   repr(dual_report.get("enemy_assets")))
                ok("L14: at runtime the player instance carries the player resources only"
                   " (explicit bindings were not overwritten)",
                   bool(player_assets)
                   and all("characters/player" in p for p in player_assets),
                   repr(dual_report.get("player_assets")))
                # ---- Phase 1.18 运行时交互契约 ----
                ok("L16: the enemy instance resolves the declared target reference"
                   " (target_path travels from the composition plan to the runtime node)",
                   dual_report.get("target_path") == "../E2eProbePlayer",
                   repr(dual_report.get("target_path")))
                ok("L17: the enemy really approaches the declared player instance"
                   " (real physics frames, no orchestrator, probe assigns no target)",
                   float(dual_report.get("approach") or 0.0) >= 20.0
                   and float(dual_report.get("start_dist") or 0.0) > 0.0,
                   repr({k: dual_report.get(k)
                         for k in ("target_path", "start_dist", "min_dist", "approach")}))
            finally:
                try:
                    _DUAL_PROBE_SCRIPT.unlink()
                except OSError:
                    pass
            ok("L15: the transient dual-host probe script is removed from the project",
               not _DUAL_PROBE_SCRIPT.exists(), str(_DUAL_PROBE_SCRIPT))

        # ==================== N. Boss 编排生成链路（Phase 1.20） ====================
        # Gameplay Blueprint -> 生成 Boss 实体场景 -> 绑定解析 -> 自动 composition_plan
        # -> 正式组合宿主 -> boss 模式 LevelConfig -> 真实 Godot Boss 生命周期。
        print()
        print("--- N. boss orchestration chain ---")
        import boss_level_probe as boss_probe                    # noqa: E402
        boss_gameplay = work / "boss_probe_game.yaml"
        boss_gameplay.write_text(
            yaml.safe_dump(_BOSS_GAMEPLAY, sort_keys=False, allow_unicode=True),
            encoding="utf-8")
        boss_entities_dir = work / "boss_probe_entities"
        written_boss = bpgen.write_entity_blueprints(_BOSS_GAMEPLAY, boss_entities_dir)
        boss_bp_path = boss_entities_dir / "e2e_boss.yaml"
        ok("N1: the boss entity blueprint is emitted (player scene is reused, not regenerated)",
           [Path(p).name for p in written_boss] == ["e2e_boss.yaml"]
           and boss_bp_path.is_file(),
           str([Path(p).name for p in written_boss]))

        boss_bindings = work / "boss_bindings.yaml"
        r = run_cli("asset_registry/bind_assets.py", "--gameplay", boss_gameplay,
                    "--out", boss_bindings)
        boss_binding_doc = (yaml.safe_load(boss_bindings.read_text(encoding="utf-8"))
                            if boss_bindings.is_file() else {})
        boss_binding_entities = ((boss_binding_doc.get("binding") or {}).get("entities") or [])
        ok("N2: resource binding resolves the boss entity (index inference, real binding doc)",
           r.returncode == 0
           and any(entry.get("entity") == "e2e_boss"
                   for entry in boss_binding_entities),
           (r.stdout + r.stderr)[-300:])

        r = run_cli("scene_composer/scene_composer.py", boss_bp_path,
                    "--out", PROJECT_ROOT / "Scenes", "--bindings", boss_bindings)
        boss_scene_written = _BOSS_SCENE.is_file()
        ok("N3: the boss entity scene is composed into the project",
           r.returncode == 0 and boss_scene_written
           and "Validation: PASS" in (r.stdout or ""),
           (r.stdout + r.stderr)[-300:])

        boss_plan = work / "boss_plan_generated.yaml"
        r = run_cli("scene_composer/plan_generator.py", boss_gameplay,
                    "--host", "E2eBossHost", "--target", "e2e_boss:player",
                    "--out", boss_plan)
        boss_plan_doc = (yaml.safe_load(boss_plan.read_text(encoding="utf-8"))
                         if boss_plan.is_file() else {})
        ok("N4: the composition plan is generated from the blueprint and generated scenes",
           r.returncode == 0
           and [(i.get("entity"), i.get("scene"))
                for i in boss_plan_doc.get("instances") or []]
           == [("player", "res://Features/player_movement/Player.tscn"),
               ("e2e_boss", "res://Scenes/E2eBoss.tscn")]
           and boss_plan_doc.get("targets")
           == [{"source": "E2eBoss", "target": "Player"}],
           (r.stdout + r.stderr)[-400:] + repr(boss_plan_doc))

        r = _run_compose_plan(boss_plan)
        boss_host_written = _BOSS_HOST_SCENE.is_file()
        boss_host_text = (_BOSS_HOST_SCENE.read_text(encoding="utf-8")
                          if boss_host_written else "")
        ok("N5: the formal compositor builds the multi-entity boss host",
           r.returncode == 0 and boss_host_written
           and boss_host_text.count("instance=ExtResource") == 2
           and 'target_path = NodePath("../Player")' in boss_host_text,
           boss_host_text[:300])

        r = run_cli("gameplay_planner/level_planner.py", boss_gameplay,
                    "--mode", "boss", "--boss", "e2e_boss", "--plan", boss_plan,
                    "--out", _BOSS_LEVEL, "--level-id", "e2e_boss_level")
        boss_level_written = _BOSS_LEVEL.is_file()
        boss_level_doc = (json.loads(_BOSS_LEVEL.read_text(encoding="utf-8"))
                          if boss_level_written else {})
        ok("N6: the boss level config is generated from the real plan (composed host + boss id)",
           r.returncode == 0 and "Validation: PASS" in (r.stdout or "")
           and boss_level_doc.get("mode") == "boss"
           and boss_level_doc.get("level", {}).get("arena_scene")
           == "res://Scenes/E2eBossHost.tscn"
           and boss_level_doc.get("boss")
           == {"entity": "e2e_boss", "instance": "E2eBoss", "spawn": "existing"},
           (r.stdout + r.stderr)[-400:] + repr(boss_level_doc))
        r = run_cli("validator/check_level.py", _BOSS_LEVEL)
        ok("N7: the independent validator passes the generated boss level",
           r.returncode == 0 and "PASS" in (r.stdout or ""),
           (r.stdout + r.stderr)[-300:])

        # 受控负向：静态仍合法的配置，宿主里不存在声明的实例 → 运行时必须拒绝并定位 boss.instance
        bad_doc = json.loads(json.dumps(boss_level_doc))
        bad_doc["boss"]["instance"] = "NoSuchBoss"
        _BOSS_BAD_LEVEL.write_text(json.dumps(bad_doc, ensure_ascii=False, indent=2) + "\n",
                                   encoding="utf-8", newline="\n")
        r = run_cli("validator/check_level.py", _BOSS_BAD_LEVEL)
        ok("N8: the statically valid bad-host config still passes the contract check "
           "(so N9 tests runtime resolution, not validation)",
           r.returncode == 0 and "PASS" in (r.stdout or ""),
           (r.stdout + r.stderr)[-300:])

        if godot is None:
            skip("N9: real Godot boss lifecycle of the generated host",
                 "godot executable not found (set GODOT_BIN / add to PATH)")
        elif not (boss_scene_written and boss_host_written and boss_level_written
                  and _BOSS_BAD_LEVEL.is_file()):
            ok("N9: the boss runtime check needs every generated artifact", False,
               "scene=%s host=%s level=%s"
               % (boss_scene_written, boss_host_written, boss_level_written))
        else:
            boss_run = boss_probe.run_boss_probe(
                "res://Levels/E2eBossLevel.json",
                "res://Levels/E2eBossLevelBad.json",
                project_root=PROJECT_ROOT, godot=godot)
            boss_metrics = boss_run.metrics
            print("      boss: %s" % " ".join("%s=%s" % (k, boss_metrics[k])
                                              for k in sorted(boss_metrics)))
            ok("N9: the generated boss level drives the real Godot runtime"
               " (generated host + LevelHost adapter)",
               boss_run.ok and boss_run.exit_code == 0
               and "PASS: boss 模式生成链路运行时验证通过" in boss_run.output,
               (boss_run.output or "")[-500:])
            ok("N10: the boss is the declared reflected instance and a living boss never wins",
               boss_metrics.get("config_errors", -1.0) == 0.0
               and boss_metrics.get("boss_alias", 0.0) == 1.0
               and boss_metrics.get("state_after_partial", -1.0) == 0.0
               and boss_metrics.get("finish_before_kill", -1.0) == 0.0,
               repr({k: boss_metrics.get(k) for k in
                     ("config_errors", "boss_alias", "state_after_partial",
                      "finish_before_kill")}))
            ok("N11: boss death completes exactly once and duplicate deaths are ignored",
               boss_metrics.get("boss_events", -1.0) == 1.0
               and boss_metrics.get("state_after_kill", -1.0) == 1.0
               and boss_metrics.get("finish_after_kill", -1.0) == 1.0
               and boss_metrics.get("events_after_duplicate", -1.0) == 1.0
               and boss_metrics.get("finish_after_duplicate", -1.0) == 1.0,
               repr({k: boss_metrics.get(k) for k in
                     ("boss_events", "state_after_kill", "finish_after_kill",
                      "events_after_duplicate", "finish_after_duplicate")}))
            ok("N12: an unresolvable boss.instance is refused at runtime with a locatable"
               " diagnostic and zero finish events",
               boss_metrics.get("bad_setup_errors", 0.0) >= 1.0
               and boss_metrics.get("bad_state", -1.0) == 2.0,
               repr({k: boss_metrics.get(k) for k in ("bad_setup_errors", "bad_state")}))
            ok("N13: the transient boss probe script is removed from the project",
               boss_run.script_removed
               and not (PROJECT_ROOT / boss_probe.PROBE_SCRIPT_REL).exists(),
               boss_probe.PROBE_SCRIPT_REL)

        # ==================== P. 多阶段 Boss 编排链路（Phase 1.21） ====================
        # Blueprint -> 两个实体场景 -> 真实绑定 -> 自动 composition_plan -> 正式宿主
        # -> 多阶段 LevelConfig -> 构建期交叉校验 -> 真实 Godot：清理 → Boss → 完成。
        print()
        print("--- P. multi-stage boss orchestration chain ---")
        import multi_stage_boss_probe as stage_probe             # noqa: E402
        stage_gameplay = work / "stage_boss_game.yaml"
        stage_gameplay.write_text(
            yaml.safe_dump(_STAGE_BOSS_GAMEPLAY, sort_keys=False, allow_unicode=True),
            encoding="utf-8")
        stage_entities_dir = work / "stage_boss_entities"
        written_stage = bpgen.write_entity_blueprints(_STAGE_BOSS_GAMEPLAY, stage_entities_dir)
        ok("P1: two enemy entity blueprints are emitted; the player scene is reused",
           {Path(p).name for p in written_stage} == {"stage_grunt.yaml", "stage_boss.yaml"}
           and (stage_entities_dir / "stage_grunt.yaml").is_file()
           and (stage_entities_dir / "stage_boss.yaml").is_file(),
           str([Path(p).name for p in written_stage]))

        stage_bindings = work / "stage_boss_bindings.yaml"
        r = run_cli("asset_registry/bind_assets.py", "--gameplay", stage_gameplay,
                    "--out", stage_bindings)
        stage_binding_doc = (yaml.safe_load(stage_bindings.read_text(encoding="utf-8"))
                             if stage_bindings.is_file() else {})
        stage_binding_entities = ((stage_binding_doc.get("binding") or {}).get("entities") or [])
        ok("P2: real binding resolution covers both the grunt and the boss entity",
           r.returncode == 0
           and {"stage_grunt", "stage_boss"} <= {entry.get("entity")
                                                 for entry in stage_binding_entities},
           (r.stdout + r.stderr)[-300:])

        stage_composed = []
        for bp in sorted(written_stage):
            r = run_cli("scene_composer/scene_composer.py", bp,
                        "--out", PROJECT_ROOT / "Scenes", "--bindings", stage_bindings)
            stage_composed.append(r.returncode == 0 and "Validation: PASS" in (r.stdout or ""))
        ok("P3: both generated entity scenes are composed into the project",
           all(stage_composed) and _STAGE_GRUNT_SCENE.is_file()
           and _STAGE_BOSS_SCENE.is_file(), str(stage_composed))

        stage_plan = work / "stage_boss_plan_generated.yaml"
        r = run_cli("scene_composer/plan_generator.py", stage_gameplay,
                    "--host", "E2eStageBossHost", "--target", "stage_boss:player",
                    "--out", stage_plan)
        stage_plan_doc = (yaml.safe_load(stage_plan.read_text(encoding="utf-8"))
                          if stage_plan.is_file() else {})
        ok("P4: the composition plan is generated from the real blueprint/scenes",
           r.returncode == 0
           and [(i.get("entity"), i.get("scene"))
                for i in stage_plan_doc.get("instances") or []
                ] == [("player", "res://Features/player_movement/Player.tscn"),
                     ("stage_grunt", "res://Scenes/StageGrunt.tscn"),
                     ("stage_boss", "res://Scenes/StageBoss.tscn")]
           and stage_plan_doc.get("targets")
           == [{"source": "StageBoss", "target": "Player"}],
           (r.stdout + r.stderr)[-400:] + repr(stage_plan_doc))

        r = _run_compose_plan(stage_plan)
        stage_host_written = _STAGE_HOST_SCENE.is_file()
        stage_host_text = (_STAGE_HOST_SCENE.read_text(encoding="utf-8")
                           if stage_host_written else "")
        ok("P5: the formal compositor builds the three-instance stage host",
           r.returncode == 0 and stage_host_written
           and stage_host_text.count("instance=ExtResource") == 3,
           stage_host_text[:400])

        r = run_cli("gameplay_planner/level_planner.py", stage_gameplay,
                    "--mode", "boss", "--boss", "stage_boss", "--plan", stage_plan,
                    "--stage", "clear:stage_grunt:2", "--stage", "boss",
                    "--out", _STAGE_LEVEL, "--level-id", "e2e_stage_boss_level")
        stage_level_written = _STAGE_LEVEL.is_file()
        stage_level_doc = (json.loads(_STAGE_LEVEL.read_text(encoding="utf-8"))
                           if stage_level_written else {})
        ok("P6: the multi-stage LevelConfig is generated with explicit stage order",
           r.returncode == 0 and "Validation: PASS" in (r.stdout or "")
           and stage_level_doc.get("mode") == "boss"
           and stage_level_doc.get("level", {}).get("arena_scene")
           == "res://Scenes/E2eStageBossHost.tscn"
           and stage_level_doc.get("boss")
           == {"entity": "stage_boss", "instance": "StageBoss", "spawn": "existing"}
           and [stage.get("type") for stage in stage_level_doc.get("stages") or []
                ] == ["clear_enemies", "defeat_boss"]
           and stage_level_doc["stages"][0]["entries"]
           == [{"entity": "stage_grunt", "count": 2}]
           and stage_level_doc["stages"][1].get("entity") == "stage_boss",
           (r.stdout + r.stderr)[-500:] + repr(stage_level_doc))

        r = run_cli("validator/check_level.py", _STAGE_LEVEL, "--plan", stage_plan)
        ok("P7: build-time cross-contract validation passes the generated host/plan",
           r.returncode == 0 and "PASS" in (r.stdout or "")
           and "Cross-contract: checked" in (r.stdout or ""),
           (r.stdout + r.stderr)[-400:])

        stage_bad_doc = json.loads(json.dumps(stage_level_doc))
        stage_bad_doc["boss"]["instance"] = "NoSuchBoss"
        _STAGE_BAD_LEVEL.write_text(
            json.dumps(stage_bad_doc, ensure_ascii=False, indent=2) + "\n",
            encoding="utf-8", newline="\n")
        r = run_cli("validator/check_level.py", _STAGE_BAD_LEVEL, "--plan", stage_plan)
        ok("P8: a mismatched boss instance is blocked at build time by the cross-check",
           r.returncode == 1 and "boss.instance" in (r.stderr or "")
           and "NoSuchBoss" in (r.stderr or ""),
           (r.stdout + r.stderr)[-400:])

        if godot is None:
            skip("P9: real Godot multi-stage boss lifecycle",
                 "godot executable not found (set GODOT_BIN / add to PATH)")
        elif not (stage_host_written and stage_level_written):
            ok("P9: the multi-stage runtime check needs every generated artifact", False,
               "host=%s level=%s" % (stage_host_written, stage_level_written))
        else:
            stage_run = stage_probe.run_multi_stage_probe(
                "res://Levels/E2eStageBossLevel.json", project_root=PROJECT_ROOT, godot=godot)
            stage_metrics = stage_run.metrics
            print("      stages: %s" % " ".join("%s=%s" % (k, stage_metrics[k])
                                               for k in sorted(stage_metrics)))
            ok("P9: the generated multi-stage level drives the real Godot runtime",
               stage_run.ok and stage_run.exit_code == 0
               and "PASS: 多阶段 Boss 生成链路运行时验证通过" in stage_run.output,
               (stage_run.output or "")[-600:])
            ok("P10: boss stays inactive until every clear-stage enemy is defeated",
               stage_metrics.get("config_errors", -1.0) == 0.0
               and stage_metrics.get("stage0", -1.0) == 0.0
               and stage_metrics.get("alive_after_start", -1.0) == 2.0
               and stage_metrics.get("stage_after_one", -1.0) == 0.0
               and stage_metrics.get("stage_after_clear", -1.0) == 1.0
               and stage_metrics.get("stage_started", -1.0) == 2.0
               and stage_metrics.get("stage_completed", -1.0) == 1.0,
               repr({k: stage_metrics.get(k) for k in
                     ("stage0", "alive_after_start", "stage_after_one",
                      "stage_after_clear", "stage_started", "stage_completed")}))
            ok("P11: a living boss never wins; boss death completes exactly once",
               stage_metrics.get("finish_before_boss", -1.0) == 0.0
               and stage_metrics.get("boss_events", -1.0) == 1.0
               and stage_metrics.get("state_after_boss", -1.0) == 1.0
               and stage_metrics.get("finish_after_boss", -1.0) == 1.0
               and stage_metrics.get("duplicate_events", -1.0) == 1.0
               and stage_metrics.get("duplicate_finish", -1.0) == 1.0
               and stage_metrics.get("stages_done", -1.0) == 1.0
               and stage_metrics.get("history_len", -1.0) == 2.0,
               repr({k: stage_metrics.get(k) for k in
                     ("finish_before_boss", "boss_events", "state_after_boss",
                      "finish_after_boss", "duplicate_events", "duplicate_finish",
                      "stages_done", "history_len")}))
            ok("P12: player death during the clear stage still fails the level",
               stage_metrics.get("player_state", -1.0) == 2.0
               and stage_metrics.get("player_finish_false", -1.0) == 1.0
               and stage_metrics.get("player_stage", -1.0) == 0.0,
               repr({k: stage_metrics.get(k) for k in
                     ("player_state", "player_finish_false", "player_stage")}))
            ok("P13: the transient multi-stage probe script is removed from the project",
               stage_run.script_removed
               and not (PROJECT_ROOT / stage_probe.PROBE_SCRIPT_REL).exists(),
               stage_probe.PROBE_SCRIPT_REL)

            # ---- Phase 1.22：真实 trace 的独立回放（不是测试伪造的事件流） ----
            trace_doc = stage_run.trace_document or {}
            trace_path = Path(stage_run.trace_path) if stage_run.trace_path else None
            replay = trace_replay.replay_document(trace_doc) if trace_doc else {}
            trace_events = trace_doc.get("events") or []
            ok("P14: the exported real trace replays to victory with the true stage chain",
               bool(trace_doc) and stage_run.trace_path is not None
               and replay.get("ok") is True and replay.get("final_state") == "victory"
               and replay.get("boss_death_confirmed") is True
               and [(s["stage_id"], s["stage_index"])
                    for s in replay.get("completed_stages") or []]
               == [("clear_1", 0), ("boss", 1)]
               and (replay.get("event_summary") or {}).get("orchestration_started") == 1
               and (replay.get("event_summary") or {}).get("level_victory") == 1,
               repr(replay.get("errors") if replay else trace_doc)[:400])
            ok("P15: the real trace satisfies sequence / timestamp / stage identity",
               replay.get("ok") is True
               and [e.get("sequence") for e in trace_events] == list(range(len(trace_events)))
               and all(float(trace_events[i]["timestamp_ms"])
                       <= float(trace_events[i + 1]["timestamp_ms"])
                       for i in range(len(trace_events) - 1))
               and all(e.get("stage_id") and isinstance(e.get("stage_index"), int)
                       for e in trace_events
                       if e.get("event_type") in ("stage_started", "stage_completed"))
               and [e.get("stage_index") for e in trace_events
                    if e.get("event_type") == "stage_started"] == [0, 1]
               and replay.get("sequence_gaps") == 0,
               repr(trace_events)[:500])
            ok("P16: replaying the same real trace twice is deterministic",
               bool(trace_events) and replay == trace_replay.replay_document(trace_doc))
            terminal_index = next(
                (index for index, event in enumerate(trace_events)
                 if event.get("event_type") in ("level_victory", "level_failed")),
                len(trace_events))
            prefix_doc = dict(trace_doc)
            prefix_doc["events"] = trace_events[:terminal_index]
            prefix_doc["event_count"] = terminal_index
            prefix_replay = trace_replay.replay_document(prefix_doc)
            ok("P17: dropping the terminal event replays as an unfinished run, not victory",
               prefix_replay.get("ok") is True
               and prefix_replay.get("final_state") == "playing"
               and prefix_replay.get("terminated") is False
               and len(prefix_replay.get("completed_stages") or []) == 2,
               repr(prefix_replay.get("errors"))[:300])
            if trace_path is not None:
                try:
                    trace_path.unlink(missing_ok=True)   # Phase 1.23 起探针读取后自清理，
                except OSError as exc:                   #  这里只是兜底（文件可能已不在）
                    _failures.append("cleanup: cannot remove the exported trace (%s)" % exc)
            ok("P18: the exported trace file is removed after the replay checks",
               trace_path is not None and not trace_path.exists(),
               str(trace_path))

        # ==================== T. 黄金 Trace 基线（Phase 1.23） ====================
        print()
        print("--- T. golden trace baselines ---")
        import trace_baseline_capture as baseline_capture       # noqa: E402
        import trace_baselines as trace_baselines               # noqa: E402

        scenarios = ("multi_stage_boss", "single_stage_boss", "waves", "holdout")
        approved_paths = {sid: trace_baselines.baseline_path_for(sid) for sid in scenarios}
        approved_bytes = {sid: (path.read_bytes() if path.is_file() else b"")
                          for sid, path in approved_paths.items()}
        approved_mtimes = {sid: (path.stat().st_mtime_ns if path.is_file() else 0)
                           for sid, path in approved_paths.items()}
        ok("T1: all four golden trace baselines (two boss modes + waves + holdout)"
           " exist in the validator contract directory",
           all(approved_bytes[sid] for sid in scenarios), str(sorted(approved_paths)))

        baseline_docs, baseline_errors = {}, {}
        for sid in scenarios:
            try:
                baseline_docs[sid] = json.loads(approved_bytes[sid].decode("utf-8"))
                baseline_errors[sid] = trace_baselines.validate_baseline(baseline_docs[sid])
            except (ValueError, UnicodeDecodeError) as exc:
                baseline_docs[sid] = {}
                baseline_errors[sid] = [str(exc)]
        ok("T2: the approved baselines satisfy the golden baseline contract"
           " (schema version / approval record / replayable events)",
           all(not baseline_errors[sid] for sid in scenarios),
           repr({sid: baseline_errors[sid] for sid in scenarios if baseline_errors[sid]}))
        ok("T3: the baselines only normalise explicitly declared dynamic fields"
           " (run_id/timestamp_ms) and keep data strictly compared",
           all((baseline_docs[sid].get("comparison_policy") or {})
               .get("ignored_event_fields") == ["run_id", "timestamp_ms"]
               and ((baseline_docs[sid].get("comparison_policy") or {}).get("data") or {})
               .get("mode") == "strict"
               and not ((baseline_docs[sid].get("comparison_policy") or {}).get("data") or {})
               .get("ignored_fields")
               for sid in scenarios),
           repr({sid: baseline_docs[sid].get("comparison_policy") for sid in scenarios}))

        if godot is None:
            skip("T4-T12: real trace capture and baseline comparison",
                 "godot executable not found (set GODOT_BIN / add to PATH)")
        else:
            captures = {sid: baseline_capture.capture(sid, godot=godot, timeout=300)
                        for sid in scenarios}
            ok("T4: all four scenarios produce a real Godot trace in an isolated sandbox"
               " (generation chain re-run, sandbox removed)",
               all(captures[sid].ok and captures[sid].cleanup_ok
                   and captures[sid].trace_document for sid in scenarios),
               repr({sid: (captures[sid].error or "")[-200:] for sid in scenarios
                     if not captures[sid].ok}))
            for index, sid in enumerate(scenarios):
                label = "T5%s" % chr(97 + index)
                if not captures[sid].ok:
                    ok("%s: the %s trace matches the approved baseline event by event"
                       % (label, sid), False, "capture failed")
                    continue
                result = trace_baselines.compare(baseline_docs[sid],
                                                 captures[sid].trace_document)
                print("      %s: %s" % (sid, result["summary"]))
                ok("%s: the %s trace matches the approved baseline event by event"
                   % (label, sid),
                   result["status"] == "PASS" and result["exit_code"] == 0
                   and result["matched_event_count"] == result["expected_event_count"]
                   == len(captures[sid].trace_document["events"])
                   and not result["differences"], result["summary"])

            multi = captures["multi_stage_boss"]
            ok("T7: the captured trace replays through the Phase 1.22 replayer",
               bool(multi.trace_document)
               and trace_replay.replay_document(multi.trace_document)["ok"],
               str((trace_replay.replay_document(multi.trace_document)
                    if multi.trace_document else {}).get("errors")))

            mutated = json.loads(json.dumps(multi.trace_document))
            mutated["run_id"] = "run-t23-mutant"
            for event in mutated["events"]:
                event["run_id"] = "run-t23-mutant"
            for event in mutated["events"]:
                if event["event_type"] == "level_victory":
                    event["reason"] = "forced"
            mutated_path = work / "trace_baseline_mutant.json"
            mutated_path.write_text(json.dumps(mutated, ensure_ascii=False, indent=2) + "\n",
                                    encoding="utf-8", newline="\n")
            mutant = trace_baselines.compare_files(
                mutated_path, approved_paths["multi_stage_boss"],
                scenario_id="multi_stage_boss")
            ok("T8: an unapproved victory reason change is a REGRESSION with a field path",
               mutant["status"] == "REGRESSION" and mutant["exit_code"] == 1
               and any(difference["category"] == "REASON_CHANGED"
                       and difference["field_path"].endswith(".reason")
                       for difference in mutant["differences"]),
               mutant["summary"])
            cli = run_cli("validator/trace_baselines.py", mutated_path,
                          "--baseline", approved_paths["multi_stage_boss"])
            ok("T9: the comparator CLI exits non-zero for that regression",
               cli.returncode == 1 and "REGRESSION" in (cli.stdout or ""),
               "exit=%d %s" % (cli.returncode, ((cli.stdout or "")
                                                + (cli.stderr or ""))[-300:]))

            shifted = json.loads(json.dumps(multi.trace_document))
            shifted["run_id"] = "run-t23-shifted"
            for index, event in enumerate(shifted["events"]):
                event["run_id"] = "run-t23-shifted"
                event["timestamp_ms"] = 1000 + index
            shifted_result = trace_baselines.compare(baseline_docs["multi_stage_boss"],
                                                     shifted)
            ok("T10: run_id / timestamp_ms changes alone stay PASS (explicit dynamic policy)",
               shifted_result["status"] == "PASS" and shifted_result["exit_code"] == 0,
               shifted_result["summary"])

            missing = trace_baselines.compare_files(
                mutated_path, work / "no_such_baseline.json", scenario_id="multi_stage_boss")
            ok("T11: a missing baseline reports BASELINE_MISSING (exit 2), never PASS",
               missing["status"] == "BASELINE_MISSING" and missing["exit_code"] == 2,
               missing["summary"])
            broken_path = work / "broken_baseline.json"
            broken_path.write_text("{not json", encoding="utf-8", newline="\n")
            broken = trace_baselines.compare_files(mutated_path, broken_path,
                                                   scenario_id="multi_stage_boss")
            ok("T12: a malformed baseline is INVALID_BASELINE (exit 2), never PASS",
               broken["status"] == "INVALID_BASELINE" and broken["exit_code"] == 2,
               broken["summary"])

        ok("T13: no E2E step rewrote the approved baselines (bytes + mtime unchanged)",
           all(approved_paths[sid].read_bytes() == approved_bytes[sid]
               and approved_paths[sid].stat().st_mtime_ns == approved_mtimes[sid]
               for sid in scenarios),
           str(sorted(approved_paths)))
        leftovers = sorted(path.name for path in (PROJECT_ROOT / "Tests").glob("e2e_*trace*.json"))
        ok("T14: the capture left no probe scripts, trace files or candidate dirs in the project",
           not leftovers
           and not (PROJECT_ROOT / "Tests" / "e2e_multi_stage_boss_probe.gd").exists()
           and not (PROJECT_ROOT / "Tests" / "e2e_boss_level_probe.gd").exists()
           and not (PROJECT_ROOT / ".trace_candidates_tmp").exists(),
           repr(leftovers))

        # ==================== H. 负向：无效输入 / 资源问题必须被发现 ====================
        print()
        print("--- H. negative cases ---")
        bad_bp = work / "bad_feature.yaml"
        bad_bp.write_text(yaml.safe_dump({
            "entity": {"id": "e2e_bad_reference", "role": "enemy"},
            "features": ["no_such_feature_exists"],
            "validation": {"required_tests": []},
        }, sort_keys=False), encoding="utf-8")
        bad_out = work / "bad_out"
        r = run_cli("scene_composer/scene_composer.py", bad_bp, "--out", bad_out)
        ok("H1: unknown feature is rejected with a diagnosable message",
           r.returncode != 0 and "no_such_feature_exists" in (r.stdout or ""),
           (r.stdout + r.stderr)[-300:])
        ok("H2: no half-written scene is left behind on failure",
           not bad_out.is_dir() or not list(bad_out.glob("*.tscn")),
           str(list(bad_out.glob("*.tscn")) if bad_out.is_dir() else "<no dir>"))

        missing_binding = work / "missing_binding.yaml"
        missing_binding.write_text(yaml.safe_dump(
            {"bindings": [{"role": "idle", "asset": "e2e_no_such_asset"}]}, sort_keys=False),
            encoding="utf-8")
        r = run_cli("asset_registry/bind_assets.py", "--gameplay", probe_gameplay,
                    "--binding", missing_binding, "--out", work / "missing_out.yaml")
        ok("H3: an explicit binding to a nonexistent asset is reported, never fabricated",
           "e2e_no_such_asset" in (r.stdout or "")
           and "explicit binding references unknown asset" in (r.stdout or ""),
           (r.stdout or "")[-300:])

        # ==================== I. 绑定作用域回归（Phase 1.16 接入主链路） ====================
        print()
        print("--- I. binding scope regression ---")
        # 主链路：实体作用域绑定已接入——玩家实体不再收到敌方显式绑定（场景 1 终态）。
        player_block = next((e for e in entities if e.get("entity") == "player"), {})
        leaked = [b for b in player_block.get("bindings") or []
                  if b["role"] in selections and b.get("asset") == selections[b["role"]]]
        ok("I1: entity-scoped bindings are not applied across entities (main flow)",
           not leaked,
           repr([(b["role"], b.get("asset")) for b in leaked]))
        player_idle = next((b for b in player_block.get("bindings") or []
                            if b.get("role") == "idle"), {})
        ok("I1b: the player entity's own idle stays index-inferred (untouched by the enemy scope)",
           bool(player_idle) and player_idle.get("resolved_from") == "index",
           repr(player_idle))
        # 场景 5：合法旧式 role-level 绑定仍按既有行为工作；跨实体歧义由
        # compatibility 契约给出明确诊断（INCOMPATIBLE，绝不静默 COMPATIBLE）。
        legacy_bindings = work / "legacy_bindings.yaml"
        r = run_cli("asset_registry/bind_assets.py", "--gameplay", gameplay,
                    "--binding", legacy_override, "--out", legacy_bindings)
        legacy_entity_doc = (yaml.safe_load(legacy_bindings.read_text(encoding="utf-8"))
                             if legacy_bindings.is_file() else {})
        legacy_entities = (legacy_entity_doc.get("binding") or {}).get("entities") or []
        legacy_player = next((e for e in legacy_entities if e.get("entity") == "player"), {})
        legacy_leaked = [b for b in legacy_player.get("bindings") or []
                         if b["role"] in selections and b.get("asset") == selections[b["role"]]]
        ok("I2: the legacy role-level override still applies across entities and is "
           "flagged INCOMPATIBLE by the compatibility gate (documented contract)",
           r.returncode == 0 and bool(legacy_leaked)
           and all(b.get("compatibility") == "INCOMPATIBLE" for b in legacy_leaked),
           repr([(b["role"], b.get("compatibility")) for b in legacy_leaked]))
    finally:
        if probe_written:
            try:
                _PROBE_SCENE.unlink()
            except OSError as exc:                              # pragma: no cover - 清理失败要报告
                _failures.append("cleanup: cannot remove %s (%s)" % (_PROBE_SCENE, exc))
        if probe_test_written:
            try:
                _PROBE_TEST.unlink()
                Path(str(_PROBE_TEST) + ".uid").unlink(missing_ok=True)
            except OSError as exc:                              # pragma: no cover
                _failures.append("cleanup: cannot remove %s (%s)" % (_PROBE_TEST, exc))
        if nocase_written:
            try:
                _NOCASE_SCENE.unlink()
            except OSError as exc:                              # pragma: no cover
                _failures.append("cleanup: cannot remove %s (%s)" % (_NOCASE_SCENE, exc))
        if mutant_written:
            try:
                _MUTANT_SCENE.unlink()
            except OSError as exc:                              # pragma: no cover
                _failures.append("cleanup: cannot remove %s (%s)" % (_MUTANT_SCENE, exc))
        if immortal_written:
            try:
                _IMMORTAL_SCENE.unlink()
            except OSError as exc:                              # pragma: no cover
                _failures.append("cleanup: cannot remove %s (%s)" % (_IMMORTAL_SCENE, exc))
        if probe_player_written:
            try:
                _PROBE_PLAYER_SCENE.unlink()
                Path(str(_PROBE_PLAYER_SCENE) + ".uid").unlink(missing_ok=True)
            except OSError as exc:                              # pragma: no cover
                _failures.append("cleanup: cannot remove %s (%s)" % (_PROBE_PLAYER_SCENE, exc))
        if dual_written:
            try:
                _PROBE_DUAL_SCENE.unlink()
                Path(str(_PROBE_DUAL_SCENE) + ".uid").unlink(missing_ok=True)
            except OSError as exc:                              # pragma: no cover
                _failures.append("cleanup: cannot remove %s (%s)" % (_PROBE_DUAL_SCENE, exc))
        try:
            _PROBE_BAD_HOST.unlink(missing_ok=True)
            Path(str(_PROBE_BAD_HOST) + ".uid").unlink(missing_ok=True)
        except OSError as exc:                                  # pragma: no cover
            _failures.append("cleanup: cannot remove %s (%s)" % (_PROBE_BAD_HOST, exc))
        if level_written:
            try:
                (PROJECT_ROOT / "Levels" / "E2eProbeLevel.json").unlink()
            except OSError as exc:                              # pragma: no cover
                _failures.append("cleanup: cannot remove the generated level config (%s)" % exc)
        if broken_level_written:
            try:
                (PROJECT_ROOT / "Levels" / "E2eProbeLevelBroken.json").unlink()
            except OSError as exc:                              # pragma: no cover
                _failures.append("cleanup: cannot remove the broken level config (%s)" % exc)
        for artifact in (_BOSS_SCENE, _BOSS_HOST_SCENE, _BOSS_LEVEL, _BOSS_BAD_LEVEL,
                         _STAGE_GRUNT_SCENE, _STAGE_BOSS_SCENE, _STAGE_HOST_SCENE,
                         _STAGE_LEVEL, _STAGE_BAD_LEVEL, _STAGE_TRACE):
            try:
                if artifact.exists():
                    artifact.unlink()
                Path(str(artifact) + ".uid").unlink(missing_ok=True)
            except OSError as exc:                              # pragma: no cover
                _failures.append("cleanup: cannot remove %s (%s)" % (artifact, exc))
        probe_script = PROJECT_ROOT / "Tests" / "e2e_behavior_probe.gd"
        death_script = PROJECT_ROOT / "Tests" / "e2e_death_victory_probe.gd"
        level_script = PROJECT_ROOT / "Tests" / "e2e_level_orchestration_probe.gd"
        boss_script = PROJECT_ROOT / "Tests" / "e2e_boss_level_probe.gd"
        stage_script = PROJECT_ROOT / "Tests" / "e2e_multi_stage_boss_probe.gd"
        level_configs = [PROJECT_ROOT / "Levels" / "E2eProbeLevel.json",
                         PROJECT_ROOT / "Levels" / "E2eProbeLevelBroken.json",
                         _BOSS_LEVEL, _BOSS_BAD_LEVEL, _STAGE_LEVEL, _STAGE_BAD_LEVEL,
                         _STAGE_TRACE]
        ok("Z1: probe artifacts removed from the project (no leftovers)",
           not _PROBE_SCENE.exists() and not _PROBE_TEST.exists()
           and not _NOCASE_SCENE.exists() and not _MUTANT_SCENE.exists()
           and not _IMMORTAL_SCENE.exists()
           and not _PROBE_PLAYER_SCENE.exists() and not _PROBE_DUAL_SCENE.exists()
           and not _PROBE_BAD_HOST.exists()
           and not _DUAL_PROBE_SCRIPT.exists()
           and not (PROJECT_ROOT / "Tests" / "e2e_boss_level_trace.json").exists()
           and not probe_script.exists() and not death_script.exists()
           and not boss_script.exists() and not stage_script.exists()
           and not _BOSS_SCENE.exists() and not _BOSS_HOST_SCENE.exists()
           and not _STAGE_GRUNT_SCENE.exists() and not _STAGE_BOSS_SCENE.exists()
           and not _STAGE_HOST_SCENE.exists()
           and not level_script.exists()
           and not any(path.exists() for path in level_configs),
           repr([str(p) for p in (_PROBE_SCENE, _PROBE_TEST, _NOCASE_SCENE, _MUTANT_SCENE,
                                  _IMMORTAL_SCENE, _PROBE_PLAYER_SCENE, _PROBE_DUAL_SCENE,
                                  _DUAL_PROBE_SCRIPT, probe_script, death_script, level_script,
                                  boss_script, stage_script, _BOSS_SCENE, _BOSS_HOST_SCENE,
                                  _STAGE_GRUNT_SCENE, _STAGE_BOSS_SCENE, _STAGE_HOST_SCENE)
                 + tuple(level_configs) if p.exists()]))
        # Phase 1.24（任务 C）：本测试创建/删除了多个生成场景，会弄脏 Godot 导入
        # 缓存；刷新一次，让同一轮里随后运行的测试（如 cross-layer 的 Godot 探针）
        # 不必删除陈旧缓存条目——那是批量删除守卫误伤的来源。构建卫生，非守卫规避。
        if godot is not None:
            try:
                subprocess.run(
                    [str(godot), "--headless", "--path", str(PROJECT_ROOT), "--import"],
                    capture_output=True, text=True, encoding="utf-8", errors="replace",
                    timeout=180, stdin=subprocess.DEVNULL)
            except (OSError, subprocess.SubprocessError):
                pass
        shutil.rmtree(work, ignore_errors=True)

    print()
    if _skips:
        print("SKIPPED (environment): %s" % ", ".join(_skips))
    if _failures:
        print("FAILED (%d):" % len(_failures))
        for failure in _failures:
            print("  - " + failure)
        return 1
    print("PASS: end-to-end generation integration test")
    return 0


if __name__ == "__main__":
    sys.exit(main())
