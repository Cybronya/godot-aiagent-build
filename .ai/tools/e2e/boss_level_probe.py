#!/usr/bin/env python3
"""Generated Boss Level Probe（Phase 1.20）。

在**真实 Godot 运行时**验证「自动生成的 boss 模式关卡配置 + 组合宿主场景」：

    被测配置 = `gameplay_planner/level_planner.py --mode boss` 生成的
              `Levels/<id>.json`（实体场景来自 Scene Composer 生成物，
              arena_scene = `scene_composer --compose-plan` 产出的组合宿主）；
    宿主适配 = `Orchestration/level_host.gd`（通用 LevelHost：配置 → 编排器接线）；
    观测对象 = Boss 实例身份 / 存活不胜利 / 死亡一次完成 / 重复死亡不重复结算 /
              玩家死亡失败 / 无效 boss.instance 被拒绝（可定位诊断、零完成事件）。

用法:
    python .ai/tools/e2e/boss_level_probe.py res://Levels/<id>.json \
        --bad-config res://Levels/<id>_bad.json

机制与其它探针同构：渲染临时 GDScript（Tests/e2e_boss_level_probe.gd；不带 test_ 前缀）
→ 项目真实 Godot `-s` 运行 → 解析 `BOSS:` 机读行 → finally 删除脚本。

Phase 1.23 起，正向流程在结算末尾把生产代码生成的诊断 trace 导出到
`Tests/e2e_boss_level_trace.json`（纯数据 JSON，供黄金基线比较 / 回放使用；由调用方读取
后清理）。trace 只来自本次真实运行，探针不会伪造事件。

退出码: 0 = 断言通过；1 = 断言失败；2 = 输入 / 环境错误。
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

PROBE_SCRIPT_REL = "Tests/e2e_boss_level_probe.gd"
PROBE_SCRIPT_NAME = "e2e_boss_level_probe.gd"
## 真实运行导出的诊断事件 trace（res:// 内唯一命名；由调用方读取并清理）
PROBE_TRACE_REL = "Tests/e2e_boss_level_trace.json"

PROBE_SOURCE = '''extends SceneTree
## 由 .ai/tools/e2e/boss_level_probe.py 生成——boss 模式真实运行时探针（Phase 1.20）。
## 不要手工编辑；用后即删（生成方 finally 清理）。

const LEVEL := "{{LEVEL}}"
const BAD_LEVEL := "{{BAD_LEVEL}}"
const ARENA := "{{ARENA}}"
const BOSS_INSTANCE := "{{BOSS_INSTANCE}}"
const LEVEL_HOST := "res://Orchestration/level_host.gd"
const TRACE_PATH := "{{TRACE_PATH}}"

var _failures: PackedStringArray = []
var _finish_events: Array = []


func _initialize() -> void:
\tvar config := LevelConfig.from_file(LEVEL)
\tif not config.is_valid():
\t\t_fail("N: generated boss config was rejected: %s" % str(config.errors))
\t\t_report()
\t\treturn
\tif config.mode != LevelConfig.MODE_BOSS:
\t\t_fail("N: generated config is not boss mode (%s)" % config.mode)
\tif config.arena_scene != ARENA:
\t\t_fail("N: generated config arena_scene %s != composed host %s"
\t\t\t% [config.arena_scene, ARENA])
\tif config.boss_instance_path != BOSS_INSTANCE:
\t\t_fail("N: boss.instance %s != composed instance %s"
\t\t\t% [config.boss_instance_path, BOSS_INSTANCE])

\t# ---- 正向：真实配置 + 真实组合宿主 ----
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
\t\t_fail("N: LevelHost rejected the generated config/host: %s" % str(adapter.setup_errors))
\t\t_report()
\t\treturn
\tvar orchestrator: LevelOrchestrator = adapter.orchestrator
\tvar boss: Node = adapter.get_boss()
\tvar boss_in_host: Node = host.get_node_or_null(BOSS_INSTANCE)
\tif boss == null or boss != boss_in_host:
\t\t_fail("N: configured boss instance was not resolved from the composed host")
\tif orchestrator.get_mode() != LevelConfig.MODE_BOSS:
\t\t_fail("N: orchestrator mode %s != boss" % orchestrator.get_mode())
\tif orchestrator.state != LevelOrchestrator.State.Playing:
\t\t_fail("N: boss level did not start Playing (state=%d)" % int(orchestrator.state))
\tif not _finish_events.is_empty():
\t\t_fail("N: boss level emitted a finish event before any death (%s)" % str(_finish_events))

\tvar boss_alias := 1 if boss == boss_in_host else 0
\tvar finish_before_kill := _finish_events.size()
\tvar boss_health: Health = boss.get_node("Health")
\tboss_health.take_damage(1)
\tawait process_frame
\tvar state_after_partial := int(orchestrator.state)
\tif boss_health.is_dead() or state_after_partial != LevelOrchestrator.State.Playing:
\t\t_fail("N: a damaged but living boss must not complete the level")
\tif not _finish_events.is_empty():
\t\t_fail("N: partial boss damage emitted a finish event")

\tboss_health.take_damage(9999)
\tawait process_frame
\tvar state_after_kill := int(orchestrator.state)
\tvar events_after_kill := orchestrator.get_boss_defeated_events()
\tvar finish_after_kill := _finish_events.size()
\tif not boss_health.is_dead():
\t\t_fail("N: boss should die after lethal damage")
\tif events_after_kill != 1:
\t\t_fail("N: boss death settled %d times (expected 1)" % events_after_kill)
\tif state_after_kill != LevelOrchestrator.State.Completed:
\t\t_fail("N: victory=boss_defeated must complete once the boss dies (state=%d)"
\t\t\t% state_after_kill)
\tif finish_after_kill != 1 or _finish_events != [true]:
\t\t_fail("N: boss victory must emit finished(true) exactly once, got %s"
\t\t\t% str(_finish_events))

\tboss_health.died.emit()
\tboss_health.died.emit()
\tawait process_frame
\tvar events_after_duplicate := orchestrator.get_boss_defeated_events()
\tvar finish_after_duplicate := _finish_events.size()
\tif events_after_duplicate != 1 or finish_after_duplicate != 1:
\t\t_fail("N: duplicate died notifications were settled twice (events=%d finish=%d)"
\t\t\t% [events_after_duplicate, finish_after_duplicate])
\tif not orchestrator.export_trace_json(TRACE_PATH):
\t\t_fail("N: exporting the orchestration diagnostic trace failed")
\thost.queue_free()
\tawait process_frame

\t# ---- 玩家死亡：Failed 且只发一次；不得产生胜利 ----
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
\tif player == null:
\t\t_fail("N: composed host has no Player instance (test precondition)")
\telse:
\t\tplayer.get_node("Health").take_damage(9999)
\t\tawait process_frame
\t\tif adapter_fail.orchestrator.state != LevelOrchestrator.State.Failed:
\t\t\t_fail("N: player death must fail the boss level (state=%d)"
\t\t\t\t% int(adapter_fail.orchestrator.state))
\t\tif _finish_events != [false]:
\t\t\t_fail("N: player death must emit finished(false) once, got %s" % str(_finish_events))
\thost_fail.queue_free()
\tawait process_frame

\t# ---- 无效 boss.instance：配置合法但宿主不匹配 → 拒绝开始 + 可定位诊断 ----
\t_finish_events.clear()
\tvar host_bad := _instantiate_host(ARENA)
\tif host_bad == null:
\t\t_report()
\t\treturn
\tvar adapter_bad = load(LEVEL_HOST).new()
\tadapter_bad.level_config_path = BAD_LEVEL
\thost_bad.add_child(adapter_bad)
\tawait process_frame
\tvar bad_errors: PackedStringArray = adapter_bad.setup_errors
\tvar bad_has_field := false
\tfor error in bad_errors:
\t\tif String(error).contains("boss.instance"):
\t\t\tbad_has_field = true
\tif bad_errors.is_empty() or not bad_has_field:
\t\t_fail("N: unresolvable boss.instance must be reported at boss.instance, got %s"
\t\t\t% str(bad_errors))
\tif adapter_bad.is_setup_ok():
\t\t_fail("N: unresolvable boss.instance must not be accepted")
\tvar bad_state := int(adapter_bad.orchestrator.state) if adapter_bad.orchestrator != null else -1
\tif bad_state != LevelOrchestrator.State.Failed:
\t\t_fail("N: invalid boss.instance must leave the orchestrator Failed")
\tif not _finish_events.is_empty():
\t\t_fail("N: invalid boss.instance must not emit finish events")
\thost_bad.queue_free()
\tawait process_frame

\tprint("BOSS: config_errors=%d boss_alias=%d state_after_partial=%d finish_before_kill=%d "
\t\t% [config.errors.size(), boss_alias, state_after_partial, finish_before_kill]
\t\t+ "boss_events=%d state_after_kill=%d finish_after_kill=%d "
\t\t% [events_after_kill, state_after_kill, finish_after_kill]
\t\t+ "events_after_duplicate=%d finish_after_duplicate=%d bad_setup_errors=%d "
\t\t% [events_after_duplicate, finish_after_duplicate, bad_errors.size()]
\t\t+ "bad_state=%d" % bad_state)
\t_report()


func _instantiate_host(arena_path: String) -> Node2D:
\tvar packed: PackedScene = load(arena_path)
\tif packed == null:
\t\t_fail("N: cannot load composed host %s" % arena_path)
\t\treturn null
\tvar host: Node2D = packed.instantiate()
\troot.add_child(host)
\treturn host


func _fail(message: String) -> void:
\t_failures.append(message)


func _report() -> void:
\tif _failures.is_empty():
\t\tprint("PASS: boss 模式生成链路运行时验证通过 (%s)" % LEVEL)
\t\tquit(0)
\telse:
\t\tfor failure in _failures:
\t\t\tprinterr("FAIL: " + failure)
\t\tquit(1)
'''


@dataclass
class BossProbeResult:
    ok: bool
    exit_code: int
    level: str
    bad_level: str
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
        if not line.startswith("BOSS:"):
            continue
        for key, value in re.findall(r"(\w+)=(-?[\d.]+)", line):
            try:
                metrics[key] = float(value)
            except ValueError:                              # pragma: no cover - 防御
                continue
    return metrics


def render_probe_source(level_res: str, bad_level_res: str, arena_res: str,
                        boss_instance: str, trace_res: str) -> str:
    replacements = {
        "{{LEVEL}}": level_res,
        "{{BAD_LEVEL}}": bad_level_res,
        "{{ARENA}}": arena_res,
        "{{BOSS_INSTANCE}}": boss_instance,
        "{{PROBE_NAME}}": PROBE_SCRIPT_NAME,
        "{{TRACE_PATH}}": trace_res,
    }
    source = PROBE_SOURCE
    for token in sorted(replacements, key=len, reverse=True):
        source = source.replace(token, replacements[token])
    if "{{" in source or "}}" in source:                   # pragma: no cover - 防拼写错误
        raise RuntimeError("unresolved probe placeholder remains in rendered script")
    return source


def run_boss_probe(level_res: str, bad_level_res: str, project_root: Path = PROJECT_ROOT,
                   godot=None, timeout: int = 300,
                   trace_res: str = "res://" + PROBE_TRACE_REL) -> BossProbeResult:
    project_root = Path(project_root)
    level_path = project_root / level_res.replace("res://", "")
    bad_path = project_root / bad_level_res.replace("res://", "")
    if not level_path.is_file():
        raise RuntimeError("boss level config not found: %s" % level_res)
    if not bad_path.is_file():
        raise RuntimeError("bad boss level config not found: %s" % bad_level_res)
    try:
        level = json.loads(level_path.read_text(encoding="utf-8"))
    except (OSError, ValueError) as exc:
        raise RuntimeError("cannot read boss level config %s: %s" % (level_res, exc))
    arena_res = str((level.get("level") or {}).get("arena_scene") or "")
    boss_instance = str((level.get("boss") or {}).get("instance") or "")
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
        render_probe_source(level_res, bad_level_res, arena_res, boss_instance, trace_res),
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
            # 脚本运行时错误可能让 SceneTree 不 quit：如实报告超时，不伪装 PASS
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
    return BossProbeResult(ok=(exit_code == 0 and "PASS:" in output),
                           exit_code=exit_code, level=level_res, bad_level=bad_level_res,
                           arena=arena_res, boss_instance=boss_instance, output=output,
                           metrics=parse_metrics(output), script_removed=removed,
                           trace_path=str(trace_path), trace_document=trace_document)


def main(argv=None) -> int:
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
        sys.stderr.reconfigure(encoding="utf-8")
    parser = argparse.ArgumentParser(
        description="Run a real-Godot boss orchestration probe against a generated boss level.")
    parser.add_argument("level", help="res:// path of the generated boss level config")
    parser.add_argument("--bad-config", required=True,
                        help="res:// path of a config with an unresolvable boss.instance")
    parser.add_argument("--project", default=str(PROJECT_ROOT))
    parser.add_argument("--show-output", action="store_true")
    parser.add_argument("--keep-trace", action="store_true",
                        help="keep the exported diagnostic trace for inspection")
    args = parser.parse_args(argv)

    try:
        result = run_boss_probe(args.level, args.bad_config,
                                project_root=Path(args.project).resolve())
    except (RuntimeError, subprocess.TimeoutExpired) as exc:
        print("FAIL: %s" % exc, file=sys.stderr)
        return 2

    print("Boss Level Probe")
    print("Level: %s" % result.level)
    print("Arena: %s (boss instance: %s)" % (result.arena, result.boss_instance))
    if args.show_output:
        print(result.output)
    print("Result: status=%s exit_code=%d %s"
          % ("PASS" if result.ok else "FAIL", result.exit_code,
             " ".join("%s=%s" % (key, value) for key, value in sorted(result.metrics.items()))))
    if result.trace_document:
        print("Trace: %s (events=%s)"
              % (result.trace_path, result.trace_document.get("event_count", "?")))
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
