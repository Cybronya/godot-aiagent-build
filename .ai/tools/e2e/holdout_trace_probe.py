#!/usr/bin/env python3
"""Holdout 模式的真实 Godot trace 探针（Phase 1.24）。

与 `multi_stage_boss_probe.py` / `boss_level_probe.py` 同构：生成一个**瞬态**
GDScript（`Tests/e2e_holdout_trace_probe.gd`，不带 test_ 前缀），在真实 Godot
headless 中实例化 holdout 适配层场景（`Scenes/SurvivalArena.tscn`）+ 生成的
holdout 关卡配置，验证：

    H1  配置被运行时接受（零 config errors）
    H2  存活期满前不结算（finish_events 为空）
    H3  survive_duration 到点后恰好一次胜利（finish_events == [true]）
    H4  生产代码导出的编排诊断 trace 可写、可读（读取后自清理）

证据字段 `probe_metrics.trace_events` 由 Python 侧从**导出的 trace 文档**统计
（Phase 1.27：此前 GDScript 侧恒报 0，与 trace_event_count 矛盾）。

机读输出：`MODE: <json>`（status / finish_events / trace_events）。退出码
0 = PASS；1 = 断言失败；2 = 输入 / 环境错误。
"""

from __future__ import annotations

import json
import os
import re
import subprocess
import sys
from dataclasses import dataclass, field
from pathlib import Path

_DOTAI = Path(__file__).resolve().parents[2]
PROJECT_ROOT = _DOTAI.parent

PROBE_SCRIPT_REL = "Tests/e2e_holdout_trace_probe.gd"
PROBE_TRACE_REL = "Tests/e2e_holdout_trace.json"
DEFAULT_ARENA = "res://Scenes/SurvivalArena.tscn"
WAIT_BUDGET_FRAMES = 1800          # 存活等待的物理帧上限（survival_duration 通常 <= 3s）

PROBE_SOURCE = '''extends SceneTree
## 由 .ai/tools/e2e/holdout_trace_probe.py 生成——holdout 模式诊断 trace 探针。
## 不要手工编辑。断言运行时状态，全部通过输出 MODE: 行并退出 0。

const ARENA_SCENE := "{{ARENA}}"
const LEVEL_CONFIG := "{{LEVEL}}"
const TRACE_PATH := "{{TRACE_PATH}}"
const WAIT_BUDGET := {{WAIT_BUDGET}}

var _failures: PackedStringArray = []
var _finish_events: Array = []
var _alive_seen := 0


func _on_finished(player_won: bool) -> void:
\t_finish_events.append(player_won)


func _fail(message: String) -> void:
\t_failures.append(message)


func _report(arena) -> void:
\tif not arena.export_trace_json(TRACE_PATH):
\t\t_fail("holdout: exporting the orchestration diagnostic trace failed")
\tvar report := {
\t\t"status": "PASS" if _failures.is_empty() else "FAIL",
\t\t"finish_events": _finish_events.size(),
\t\t"finish_success": 1 if (_finish_events == [true]) else 0,
\t\t"alive_seen": _alive_seen,
\t}
\tprint("MODE: %s" % JSON.stringify(report))
\tif _failures.is_empty():
\t\tquit(0)
\telse:
\t\tfor failure in _failures:
\t\t\tprinterr("FAIL: " + failure)
\t\tquit(1)


func _initialize() -> void:
\tvar packed: PackedScene = load(ARENA_SCENE)
\tif packed == null:
\t\t_fail("holdout: cannot load the arena scene %s" % ARENA_SCENE)
\t\t_report(null)
\t\treturn
\tvar arena: Node2D = packed.instantiate()
\tarena.level_config_path = LEVEL_CONFIG
\tarena.arena_finished.connect(_on_finished)
\troot.add_child(arena)
\tawait physics_frame
\tawait physics_frame

\tif not arena.get_config_errors().is_empty():
\t\t_fail("holdout: the generated config was rejected: %s"
\t\t\t% str(arena.get_config_errors()))
\t\t_report(arena)
\t\treturn
\tif not _finish_events.is_empty():
\t\t_fail("holdout: the level finished before the survival duration elapsed (%s)"
\t\t\t% str(_finish_events))
\t\t_report(arena)
\t\treturn

\t# 存活等待：物理帧推进由真实运行驱动；到点结算来自生产代码（survive_duration）。
\tvar waited := 0
\twhile _finish_events.is_empty() and waited < WAIT_BUDGET:
\t\tawait physics_frame
\t\twaited += 1
\t\t_alive_seen = maxi(_alive_seen, arena.alive_count)
\tif _finish_events != [true]:
\t\t_fail("holdout: survival duration must settle victory exactly once (events=%s)"
\t\t\t% str(_finish_events))
\t_report(arena)
'''


@dataclass
class HoldoutProbeResult:
    ok: bool
    exit_code: int
    level: str
    arena: str
    output: str = ""
    metrics: dict = field(default_factory=dict)
    script_removed: bool = False
    trace_path: str = ""
    trace_document: dict = field(default_factory=dict)
    trace_removed: bool = False

    @property
    def failure_messages(self) -> list:
        return [line.strip() for line in self.output.splitlines()
                if line.strip().startswith("FAIL:")]


def find_godot(project_root: Path = PROJECT_ROOT):
    for candidate in (project_root.parent / "Godot_v4.7-stable_win64_console.exe",
                      project_root.parent / "Godot_v4.7-stable_win64.exe"):
        if candidate.is_file():
            return Path(candidate)
    for name in ("godot", "godot4"):
        found = __import__("shutil").which(name)
        if found:
            return Path(found)
    return None


def parse_metrics(output: str) -> dict:
    metrics: dict = {}
    for line in output.splitlines():
        if not line.startswith("MODE:"):
            continue
        match = re.search(r"MODE: (\{.*\})", line)
        if not match:
            continue
        try:
            metrics = json.loads(match.group(1))
        except ValueError:                                  # pragma: no cover - 防御
            continue
    return metrics


def run_holdout_probe(level_res: str, project_root: Path = PROJECT_ROOT, godot=None,
                      arena_res: str = DEFAULT_ARENA,
                      timeout: int = 180) -> HoldoutProbeResult:
    """在真实 Godot headless 中运行 holdout 探针；trace 读取后自清理。"""
    project_root = Path(project_root)
    level_path = project_root / level_res.replace("res://", "")
    if not level_path.is_file():
        raise RuntimeError("level config not found in project: %s" % level_res)
    arena_path = project_root / arena_res.replace("res://", "")
    if not arena_path.is_file():
        raise RuntimeError("arena game scene not found in project: %s" % arena_res)
    godot = Path(godot) if godot else find_godot(project_root)
    if godot is None or not Path(godot).is_file():
        raise RuntimeError("godot executable not found; set GODOT_BIN or add it to PATH")

    script_path = project_root / PROBE_SCRIPT_REL
    trace_path = project_root / PROBE_TRACE_REL
    script_path.parent.mkdir(parents=True, exist_ok=True)
    if trace_path.exists():                                 # 不把旧 trace 当成本次结果
        trace_path.unlink()
    source = (PROBE_SOURCE
              .replace("{{ARENA}}", arena_res)
              .replace("{{LEVEL}}", level_res)
              .replace("{{TRACE_PATH}}", "res://" + PROBE_TRACE_REL)
              .replace("{{WAIT_BUDGET}}", str(WAIT_BUDGET_FRAMES)))
    script_path.write_text(source, encoding="utf-8", newline="\n")
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
        except OSError:                                     # pragma: no cover
            removed = False
    trace_document: dict = {}
    trace_removed = False
    if trace_path.is_file():
        try:
            trace_document = json.loads(trace_path.read_text(encoding="utf-8"))
        except (OSError, ValueError) as exc:                # pragma: no cover - 防御
            trace_document = {"parse_error": str(exc)}
        try:                                                # 读取后即清理（工具自清理）
            trace_path.unlink()
            Path(str(trace_path) + ".uid").unlink(missing_ok=True)
            trace_removed = True
        except OSError:                                     # pragma: no cover
            trace_removed = False
    metrics = parse_metrics(output)
    # 证据统计由导出文档计算（单一事实来源）；探针脚本不自行声明事件数
    metrics["trace_events"] = len(trace_document.get("events") or [])
    ok = (exit_code == 0 and metrics.get("status") == "PASS")
    return HoldoutProbeResult(ok=ok,
                              exit_code=exit_code, level=level_res, arena=arena_res,
                              output=output, metrics=metrics,
                              script_removed=removed, trace_path=str(trace_path),
                              trace_document=trace_document,
                              trace_removed=trace_removed)


def main(argv=None) -> int:
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
        sys.stderr.reconfigure(encoding="utf-8")
    parser = argparse.ArgumentParser(
        description="Run a real-Godot holdout trace probe against a generated holdout level.")
    parser.add_argument("level", help="res:// path of the generated holdout level config")
    parser.add_argument("--arena", default=DEFAULT_ARENA)
    parser.add_argument("--project", default=str(PROJECT_ROOT))
    parser.add_argument("--show-output", action="store_true")
    args = parser.parse_args(argv)
    try:
        result = run_holdout_probe(args.level, project_root=Path(args.project).resolve(),
                                   arena_res=args.arena)
    except RuntimeError as exc:
        print("FAIL: %s" % exc, file=sys.stderr)
        return 2
    if args.show_output:
        print(result.output)
    print("Holdout trace probe: level=%s ok=%s exit=%d events=%d"
          % (result.level, result.ok, result.exit_code,
             len(result.trace_document.get("events") or [])))
    return 0 if result.ok else 1


if __name__ == "__main__":
    sys.exit(main())
