#!/usr/bin/env python3
"""Generated Multi-Stage Boss Probe（Phase 1.21）。

在**真实 Godot 运行时**验证自动生成的「多阶段 Boss」链路，并把本次运行的真实
诊断事件 trace 导出到 `Tests/e2e_multi_stage_boss_trace.json`（纯数据 JSON，供
`validator/trace_replay.py` 独立回放；由调用方读取后清理）：

    被测配置 = `gameplay_planner/level_planner.py --mode boss --stage ...` 生成的
              `Levels/<id>.json`（实体场景来自 Scene Composer，宿主来自
              `scene_composer --compose-plan`）；
    宿主适配 = `Orchestration/level_host.gd`（配置 → 编排器接线）；
    观测对象 = 清理阶段不激活 Boss / 清理完成只激活一次 / Boss 存活不胜利 /
               Boss 死亡只完成一次 / 重复死亡幂等 / 玩家死亡仍 Failed。

用法:
    python .ai/tools/e2e/multi_stage_boss_probe.py res://Levels/<id>.json

机制与其它探针同构：渲染临时 GDScript（Tests/e2e_multi_stage_boss_probe.gd；
不带 test_ 前缀）→ 项目真实 Godot `-s` 运行 → 解析 `STAGE:` 机读行 →
finally 删除脚本。退出码: 0 = 断言通过；1 = 断言失败；2 = 输入 / 环境错误。
"""

from __future__ import annotations

import argparse
import json
import os
import re
import shutil
import subprocess
import sys
from dataclasses import dataclass, field
from pathlib import Path

_DOTAI = Path(__file__).resolve().parents[2]              # <project>/.ai
PROJECT_ROOT = _DOTAI.parent                              # <project>

PROBE_SCRIPT_REL = "Tests/e2e_multi_stage_boss_probe.gd"
PROBE_SCRIPT_NAME = "e2e_multi_stage_boss_probe.gd"
## 真实运行导出的诊断事件 trace（res:// 内唯一命名；由调用方读取并清理）
PROBE_TRACE_REL = "Tests/e2e_multi_stage_boss_trace.json"

PROBE_SOURCE = '''extends SceneTree
## 由 .ai/tools/e2e/multi_stage_boss_probe.py 生成——多阶段 Boss 真实运行时探针。
## 不要手工编辑；用后即删（生成方 finally 清理）。

const LEVEL := "{{LEVEL}}"
const ARENA := "{{ARENA}}"
const BOSS_INSTANCE := "{{BOSS_INSTANCE}}"
const CLEAR_INSTANCE := "{{CLEAR_INSTANCE}}"
const LEVEL_HOST := "res://Orchestration/level_host.gd"
const TRACE_PATH := "{{TRACE_PATH}}"

var _failures: PackedStringArray = []
var _finish_events: Array = []


func _initialize() -> void:
\tvar config := LevelConfig.from_file(LEVEL)
\tif not config.is_valid():
\t\t_fail("config: generated multi-stage config was rejected: %s" % str(config.errors))
\t\t_report()
\t\treturn
\tif config.mode != LevelConfig.MODE_BOSS:
\t\t_fail("config: generated config is not boss mode (%s)" % config.mode)
\tif config.stages.size() != 2:
\t\t_fail("config: expected exactly 2 stages, got %d" % config.stages.size())
\t\t_report()
\t\treturn
\tif str(config.stages[0].get("type", "")) != LevelConfig.STAGE_CLEAR_ENEMIES \\
\t\t\tor str(config.stages[1].get("type", "")) != LevelConfig.STAGE_DEFEAT_BOSS:
\t\t_fail("config: unexpected stage order %s" % str(config.stages))
\tif config.arena_scene != ARENA:
\t\t_fail("config: arena_scene %s != composed host %s" % [config.arena_scene, ARENA])

\t# ---- 正向：清理普通敌人 → Boss 激活 → 击败 Boss → 完成 ----
\tvar host := _instantiate_host(ARENA)
\tif host == null:
\t\t_report()
\t\treturn
\tvar adapter = load(LEVEL_HOST).new()
\tadapter.level_config_path = LEVEL
\tadapter.level_finished.connect(func(success: bool) -> void: _finish_events.append(success))
\thost.add_child(adapter)
\tawait process_frame
\tawait physics_frame
\tif not adapter.is_setup_ok():
\t\t_fail("runtime: LevelHost rejected the generated config/host: %s" % str(adapter.setup_errors))
\t\t_report()
\t\treturn
\tvar orchestrator: LevelOrchestrator = adapter.orchestrator
\tvar boss: Node = orchestrator.get_boss()
\tif boss == null or boss != host.get_node_or_null(BOSS_INSTANCE):
\t\t_fail("runtime: configured boss instance was not resolved from the composed host")
\tif orchestrator.get_stage_index() != 0 \\
\t\t\tor orchestrator.get_stage_type() != LevelConfig.STAGE_CLEAR_ENEMIES:
\t\t_fail("runtime: level must start in the clear_enemies stage (index=%d type=%s)"
\t\t\t% [orchestrator.get_stage_index(), orchestrator.get_stage_type()])
\tvar stage0 := orchestrator.get_stage_index()
\tvar stage0_type := orchestrator.get_stage_type()
\tvar alive_after_start := orchestrator.alive_count
\tif alive_after_start != 2:
\t\t_fail("runtime: clear stage must spawn 2 enemies, got %d" % alive_after_start)
\tif orchestrator.state != LevelOrchestrator.State.Playing or not _finish_events.is_empty():
\t\t_fail("runtime: a live boss during the clear stage must not finish the level")
\tboss.process_mode = Node.PROCESS_MODE_DISABLED
\tvar clear_enemies := _spawned_enemies(orchestrator)
\tif clear_enemies.size() != 2:
\t\t_fail("runtime: expected 2 spawned clear enemies, got %d" % clear_enemies.size())
\t\t_report()
\t\treturn
\tfor enemy in clear_enemies:
\t\tenemy.process_mode = Node.PROCESS_MODE_DISABLED

\tvar first_health: Health = clear_enemies[0].get_node("Health")
\tfirst_health.take_damage(9999)
\tawait process_frame
\tvar stage_after_one := orchestrator.get_stage_index()
\tvar type_after_one := orchestrator.get_stage_type()
\tif stage_after_one != 0:
\t\t_fail("runtime: clearing one of two enemies advanced the stage (%d)" % stage_after_one)
\tif orchestrator.state != LevelOrchestrator.State.Playing or not _finish_events.is_empty():
\t\t_fail("runtime: partial clear must not complete the level")

\tclear_enemies[1].get_node("Health").take_damage(9999)
\tawait process_frame
\tvar stage_after_clear := orchestrator.get_stage_index()
\tvar type_after_clear := orchestrator.get_stage_type()
\tvar stage_counts := orchestrator.get_stage_event_counts()
\tvar finish_before_boss := _finish_events.size()
\tif stage_after_clear != 1 or type_after_clear != LevelConfig.STAGE_DEFEAT_BOSS:
\t\t_fail("runtime: clearing all enemies must activate the boss stage once (index=%d type=%s)"
\t\t\t% [stage_after_clear, type_after_clear])
\tif stage_counts.get("started", 0) != 2 or stage_counts.get("completed", 0) != 1:
\t\t_fail("runtime: stage activation/completion counts are wrong: %s" % str(stage_counts))
\tif orchestrator.state != LevelOrchestrator.State.Playing or finish_before_boss != 0:
\t\t_fail("runtime: a living boss must keep the level Playing")

\tvar boss_health: Health = boss.get_node("Health")
\tboss_health.take_damage(1)
\tawait process_frame
\tvar state_after_partial := int(orchestrator.state)
\tif boss_health.is_dead() or state_after_partial != LevelOrchestrator.State.Playing:
\t\t_fail("runtime: a damaged but living boss must not complete the level")
\tboss_health.take_damage(9999)
\tawait process_frame
\tvar state_after_boss := int(orchestrator.state)
\tvar boss_events := orchestrator.get_boss_defeated_events()
\tvar finish_after_boss := _finish_events.size()
\tvar stages_done := orchestrator.are_stages_done()
\tvar history := orchestrator.get_stage_history()
\tif not boss_health.is_dead():
\t\t_fail("runtime: boss should die after lethal damage")
\tif boss_events != 1:
\t\t_fail("runtime: boss death settled %d times (expected 1)" % boss_events)
\tif state_after_boss != LevelOrchestrator.State.Completed:
\t\t_fail("runtime: multi-stage boss death must complete the level (state=%d)" % state_after_boss)
\tif finish_after_boss != 1 or _finish_events != [true]:
\t\t_fail("runtime: multi-stage victory must emit finished(true) exactly once, got %s"
\t\t\t% str(_finish_events))
\tif not stages_done or history != ["clear_1", "boss"]:
\t\t_fail("runtime: stage completion history mismatch (done=%s history=%s)"
\t\t\t% [str(stages_done), str(history)])

\tboss_health.died.emit()
\tboss_health.died.emit()
\tawait process_frame
\tvar duplicate_events := orchestrator.get_boss_defeated_events()
\tvar duplicate_finish := _finish_events.size()
\tif duplicate_events != 1 or duplicate_finish != 1:
\t\t_fail("runtime: duplicate boss deaths were settled twice (events=%d finish=%d)"
\t\t\t% [duplicate_events, duplicate_finish])
\tif not orchestrator.export_trace_json(TRACE_PATH):
\t\t_fail("runtime: exporting the orchestration diagnostic trace failed")
\thost.queue_free()
\tawait process_frame

\t# ---- 玩家死亡：清理阶段仍须 Failed，且不得产生胜利 ----
\t_finish_events.clear()
\tvar host_fail := _instantiate_host(ARENA)
\tif host_fail == null:
\t\t_report()
\t\treturn
\tvar adapter_fail = load(LEVEL_HOST).new()
\tadapter_fail.level_config_path = LEVEL
\tadapter_fail.level_finished.connect(func(success: bool) -> void: _finish_events.append(success))
\thost_fail.add_child(adapter_fail)
\tawait process_frame
\tvar player: Node = host_fail.get_node_or_null("Player")
\tvar player_stage: int = -1
\tvar player_state: int = -1
\tvar player_finish_false: int = 0
\tif player == null:
\t\t_fail("runtime: composed host has no Player instance (test precondition)")
\telse:
\t\tplayer.get_node("Health").take_damage(9999)
\t\tawait process_frame
\t\tif adapter_fail.orchestrator.state != LevelOrchestrator.State.Failed:
\t\t\t_fail("runtime: player death must fail the multi-stage level (state=%d)"
\t\t\t\t% int(adapter_fail.orchestrator.state))
\t\tif _finish_events != [false]:
\t\t\t_fail("runtime: player death must emit finished(false) once, got %s"
\t\t\t\t% str(_finish_events))
\t\tplayer_stage = adapter_fail.orchestrator.get_stage_index()
\t\tplayer_state = int(adapter_fail.orchestrator.state)
\t\tplayer_finish_false = _finish_events.size()

\tif player_stage != 0:
\t\t_fail("runtime: player death must not advance the stage (index=%d)" % player_stage)
\thost_fail.queue_free()
\tawait process_frame

\tprint("STAGE: config_errors=%d stage_count=%d stage0=%d alive_after_start=%d "
\t\t% [config.errors.size(), config.stages.size(), stage0, alive_after_start]
\t\t+ "stage_after_one=%d stage_after_clear=%d stage_started=%d stage_completed=%d "
\t\t% [stage_after_one, stage_after_clear, stage_counts.get("started", 0),
\t\t   stage_counts.get("completed", 0)]
\t\t+ "finish_before_boss=%d boss_events=%d state_after_boss=%d finish_after_boss=%d "
\t\t% [finish_before_boss, boss_events, state_after_boss, finish_after_boss]
\t\t+ "duplicate_events=%d duplicate_finish=%d stages_done=%d history_len=%d "
\t\t% [duplicate_events, duplicate_finish, 1 if stages_done else 0, history.size()]
\t\t+ "player_state=%d player_finish_false=%d player_stage=%d"
\t\t% [player_state, player_finish_false, player_stage])
\t_report()


func _spawned_enemies(orchestrator: LevelOrchestrator) -> Array[Node]:
\tvar result: Array[Node] = []
\tfor child in orchestrator.entities.get_children():
\t\tif child.is_in_group("enemies") and is_instance_valid(child) \\
\t\t\t\tand not child.is_queued_for_deletion():
\t\t\tresult.append(child)
\treturn result


func _instantiate_host(arena_path: String) -> Node2D:
\tvar packed: PackedScene = load(arena_path)
\tif packed == null:
\t\t_fail("runtime: cannot load composed host %s" % arena_path)
\t\treturn null
\tvar host: Node2D = packed.instantiate()
\troot.add_child(host)
\treturn host


func _fail(message: String) -> void:
\t_failures.append(message)


func _report() -> void:
\tif _failures.is_empty():
\t\tprint("PASS: 多阶段 Boss 生成链路运行时验证通过 (%s)" % LEVEL)
\t\tquit(0)
\telse:
\t\tfor failure in _failures:
\t\t\tprinterr("FAIL: " + failure)
\t\tquit(1)
'''


@dataclass
class MultiStageProbeResult:
    ok: bool
    exit_code: int
    level: str
    arena: str
    boss_instance: str
    output: str = ""
    metrics: dict = field(default_factory=dict)
    script_removed: bool = False
    ## 真实运行导出的 trace 文档（不存在或非法 JSON 时为空 dict）
    trace_path: str = ""
    trace_document: dict = field(default_factory=dict)

    @property
    def failure_messages(self) -> list:
        return [line.strip() for line in self.output.splitlines()
                if line.strip().startswith("FAIL:")]


def find_godot(project_root: Path = PROJECT_ROOT):
    for candidate in (project_root.parent / "Godot_v4.7-stable_win64_console.exe",
                      project_root.parent / "Godot_v4.7-stable_win64.exe"):
        if candidate.is_file():
            return candidate
    for name in ("godot", "godot4"):
        found = shutil.which(name)
        if found:
            return Path(found)
    return None


def parse_metrics(output: str) -> dict:
    metrics: dict = {}
    for line in output.splitlines():
        if not line.startswith("STAGE:"):
            continue
        for key, value in re.findall(r"(\w+)=(-?[\d.]+)", line):
            try:
                metrics[key] = float(value)
            except ValueError:                              # pragma: no cover - 防御
                continue
    return metrics


def render_probe_source(level_res: str, arena_res: str, boss_instance: str,
                        clear_instance: str, trace_res: str) -> str:
    replacements = {
        "{{LEVEL}}": level_res,
        "{{ARENA}}": arena_res,
        "{{BOSS_INSTANCE}}": boss_instance,
        "{{CLEAR_INSTANCE}}": clear_instance,
        "{{TRACE_PATH}}": trace_res,
    }
    source = PROBE_SOURCE
    for token in sorted(replacements, key=len, reverse=True):
        source = source.replace(token, replacements[token])
    if "{{" in source or "}}" in source:                   # pragma: no cover - 防拼写错误
        raise RuntimeError("unresolved probe placeholder remains in rendered script")
    return source


def run_multi_stage_probe(level_res: str, project_root: Path = PROJECT_ROOT,
                          godot=None, timeout: int = 300,
                          trace_res: str = "res://" + PROBE_TRACE_REL) -> MultiStageProbeResult:
    project_root = Path(project_root)
    level_path = project_root / level_res.replace("res://", "")
    if not level_path.is_file():
        raise RuntimeError("multi-stage boss level config not found: %s" % level_res)
    try:
        level = json.loads(level_path.read_text(encoding="utf-8"))
    except (OSError, ValueError) as exc:
        raise RuntimeError("cannot read boss level config %s: %s" % (level_res, exc))
    arena_res = str((level.get("level") or {}).get("arena_scene") or "")
    boss_instance = str((level.get("boss") or {}).get("instance") or "")
    stages = level.get("stages") or []
    clear_instance = ""
    if stages and isinstance(stages[0], dict):
        entries = stages[0].get("entries") or []
        if entries and isinstance(entries[0], dict):
            # 生成器使用 Pascal(entity) 作为宿主实例名；探针只用它做身份对照。
            clear_instance = "".join(part[:1].upper() + part[1:]
                                     for part in str(entries[0].get("entity") or "")
                                     .replace("-", "_").split("_") if part)
    if not arena_res:
        raise RuntimeError("boss level config declares no level.arena_scene: %s" % level_res)
    if not (project_root / arena_res.replace("res://", "")).is_file():
        raise RuntimeError("composed host scene not found: %s" % arena_res)
    if not boss_instance:
        raise RuntimeError("boss level config declares no boss.instance: %s" % level_res)
    godot = Path(godot) if godot else find_godot(project_root)
    if godot is None or not Path(godot).is_file():
        raise RuntimeError("godot executable not found; set GODOT_BIN or add it to PATH")

    script_path = project_root / PROBE_SCRIPT_REL
    script_path.parent.mkdir(parents=True, exist_ok=True)
    trace_path = project_root / trace_res.replace("res://", "")
    if trace_path.exists():                                 # 不把旧 trace 当成本次结果
        trace_path.unlink()
    script_path.write_text(
        render_probe_source(level_res, arena_res, boss_instance, clear_instance,
                            trace_res),
        encoding="utf-8", newline="\n")
    try:
        try:
            proc = subprocess.run(
                [str(godot), "--headless", "--path", str(project_root),
                 "-s", "res://" + PROBE_SCRIPT_REL.replace(os.sep, "/")],
                capture_output=True, text=True, encoding="utf-8", errors="replace",
                cwd=str(project_root), stdin=subprocess.DEVNULL, timeout=timeout)
            output = (proc.stdout or "") + (proc.stderr or "")
            exit_code = proc.returncode
        except subprocess.TimeoutExpired as exc:
            partial = exc.stdout or exc.stderr or ""
            if isinstance(partial, bytes):                    # pragma: no cover - 平台差异
                partial = partial.decode("utf-8", "replace")
            output = str(partial) + "\nTIMEOUT after %ss" % timeout
            exit_code = -1
    finally:
        removed = True
        try:
            script_path.unlink()
        except OSError:                                     # pragma: no cover - 清理失败要报告
            removed = False
    trace_document: dict = {}
    if trace_path.is_file():
        try:
            trace_document = json.loads(trace_path.read_text(encoding="utf-8"))
        except (OSError, ValueError) as exc:                 # pragma: no cover - 防御
            trace_document = {"parse_error": str(exc)}
        try:                                                 # 读取后即清理（工具自清理：
            trace_path.unlink()                              #  不把本次诊断产物留给项目）
            Path(str(trace_path) + ".uid").unlink(missing_ok=True)
        except OSError:                                      # pragma: no cover
            pass
    return MultiStageProbeResult(ok=(exit_code == 0 and "PASS:" in output),
                                 exit_code=exit_code, level=level_res, arena=arena_res,
                                 boss_instance=boss_instance, output=output,
                                 metrics=parse_metrics(output), script_removed=removed,
                                 trace_path=str(trace_path), trace_document=trace_document)


def main(argv=None) -> int:
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
        sys.stderr.reconfigure(encoding="utf-8")
    parser = argparse.ArgumentParser(
        description="Run a real-Godot multi-stage boss probe against a generated level.")
    parser.add_argument("level", help="res:// path of the generated multi-stage boss config")
    parser.add_argument("--project", default=str(PROJECT_ROOT))
    parser.add_argument("--show-output", action="store_true")
    parser.add_argument("--keep-trace", action="store_true",
                        help="keep the exported diagnostic trace for inspection")
    args = parser.parse_args(argv)

    try:
        result = run_multi_stage_probe(args.level, project_root=Path(args.project).resolve())
    except (RuntimeError, subprocess.TimeoutExpired) as exc:
        print("FAIL: %s" % exc, file=sys.stderr)
        return 2

    print("Multi-Stage Boss Probe")
    print("Level: %s" % result.level)
    print("Arena: %s (boss instance: %s)" % (result.arena, result.boss_instance))
    if args.show_output:
        print(result.output)
    print("Result: status=%s exit_code=%d %s"
          % ("PASS" if result.ok else "FAIL", result.exit_code,
             " ".join("%s=%s" % (key, value) for key, value in sorted(result.metrics.items()))))
    if result.trace_document:
        print("Trace: %s (events=%s)"
              % (result.trace_path,
                 result.trace_document.get("event_count", "?")))
    if not args.keep_trace and result.trace_path:
        try:
            Path(result.trace_path).unlink(missing_ok=True)
        except OSError as exc:                              # pragma: no cover - 防御
            print("WARNING: cannot remove trace %s: %s" % (result.trace_path, exc),
                  file=sys.stderr)
    for failure in result.failure_messages:
        print("  " + failure, file=sys.stderr)
    return 0 if result.ok else 1


if __name__ == "__main__":
    sys.exit(main())
