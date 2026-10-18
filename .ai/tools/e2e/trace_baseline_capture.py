#!/usr/bin/env python3
"""Sandboxed real-trace capture for golden baselines（Phase 1.23）

在**临时沙箱副本**里跑完整生成链路 + 真实 Godot 探针，产出本次运行的真实编排
诊断 trace，供「候选生成 / 人工批准」使用。沙箱副本保证：

  - 生成物（实体场景 / 宿主 / 关卡配置 / trace）全部落在临时目录，项目内零残留；
  - 测试与候选生成都不会碰到已批准的黄金基线（基线目录只被读取）。

链路（与正式 E2E 完全一致，不复制粘贴手写 trace）：

    Gameplay Blueprint
      → blueprint_generator（实体蓝图）
      → bind_assets.py（真实绑定）
      → scene_composer.py（实体场景）
      → plan_generator.py（composition plan）
      → scene_composer.py --compose-plan（宿主场景）
      → level_planner.py（LevelConfig）
      → check_level.py（构建期契约）
      → Godot headless 探针（LevelHost + LevelOrchestrator 真实运行）
      → export_trace_json（生产代码导出的真实事件流）

用法：
    python .ai/tools/e2e/trace_baseline_capture.py multi_stage_boss --out trace.json
    python .ai/tools/e2e/trace_baseline_capture.py --list

退出码：0 = 采集成功；1 = 采集/探针失败；2 = 输入或环境错误。
"""

from __future__ import annotations

import argparse
import json
import os
import shutil
import subprocess
import sys
import tempfile
import time
from dataclasses import dataclass, field
from pathlib import Path

_DOTAI = Path(__file__).resolve().parents[2]              # <project>/.ai
PROJECT_ROOT = _DOTAI.parent                              # <project>
TOOLS = _DOTAI / "tools"

for _path in (str(TOOLS / "e2e"), str(TOOLS / "gameplay_planner"),
              str(TOOLS / "validator")):
    if _path not in sys.path:
        sys.path.insert(0, _path)

import blueprint_generator                                  # noqa: E402
import boss_level_probe                                     # noqa: E402
import holdout_trace_probe                                  # noqa: E402
import level_orchestration_probe                            # noqa: E402
import multi_stage_boss_probe                               # noqa: E402

# 保留 .godot（Godot 全局类名缓存 / 导入缓存）：否则沙箱内 `LevelOrchestrator` 等
# `class_name` 未注册，探针脚本解析失败 —— 那不是产品缺陷。
# .workbuddy（agent 工作区数据）与历史沙箱目录与运行无关，一并忽略。
SANDBOX_IGNORE = (".git", "skills", "memory", "__pycache__",
                  ".freebuff", ".vscode", "*.pyc", ".workbuddy",
                  "trace_baseline_sandbox_*")

# Phase 1.25 性能审计结论（实测，11.7k 文件 / 265MB 项目）：
#   copytree 到 %TEMP%（跨盘真拷贝）≈ 51s + rmtree ≈ 125s ≈ 每次捕获 ~176s 纯开销；
#   同盘硬链接拷贝 ≈ 18.5s + rmtree ≈ 5.3s ≈ ~24s（4 场景累计省 ~10 分钟）。
# 安全性：硬链接共享 inode——只有「原地改写既有文件」才会污染原项目。
#   生成链路只**新建**文件（场景 / 配置 / 绑定 / trace / 探针脚本）；
#   Godot 运行只写 .godot/*（真实拷贝区，见下）→ 唯一的共享写风险被排除。

def _hardlink_or_copy(src: str, dst: str) -> None:
    try:
        os.link(src, dst)
    except OSError:
        shutil.copy2(src, dst)


def _real_copy_dir(src: Path, dst: Path) -> None:
    """真实拷贝一个目录（字节级独立副本）。"""
    shutil.copytree(src, dst, dirs_exist_ok=True)

# 沙箱里生成的场景 / 关卡名字带 trace_baseline_ 前缀：与既有产物不重名。
SCENARIOS = {
    "multi_stage_boss": {
        "description": "多阶段 Boss：清理普通敌人 → Boss 阶段开始 → Boss 死亡确认 → Victory",
        "coverage": [
            "orchestration_started（boss 模式，2 个阶段）",
            "stage_started/stage_completed 两次（clear_1 → boss）",
            "stage_transitioned（stage_completed → stages_exhausted）",
            "boss_death_confirmed 恰好一次（重复 died 被忽略）",
            "level_victory（boss_defeated）且为最后一个事件",
        ],
        "gameplay": {
            "gameplay": {"id": "trace_baseline_multi_stage_game"},
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
                           "required_features": [], "required_tests": ["health",
                                                                      "chase_movement"]},
        },
        "host": "TraceBaselineStageHost",
        "target": "stage_boss:player",
        "level_id": "trace_baseline_multi_stage_boss",
        "planner_args": ["--mode", "boss", "--boss", "stage_boss",
                         "--stage", "clear:stage_grunt:2", "--stage", "boss"],
        "probe": "multi_stage",
    },
    "single_stage_boss": {
        "description": "单阶段 Boss：Boss 存活不胜利 → Boss 死亡确认 → Victory",
        "coverage": [
            "orchestration_started（boss 模式，无阶段链）",
            "boss_death_confirmed 恰好一次（非致命伤害不结算、重复 died 被忽略）",
            "level_victory（boss_defeated）且为最后一个事件",
        ],
        "gameplay": {
            "gameplay": {"id": "trace_baseline_single_stage_game"},
            "entities": {
                "player": {
                    "role": "player",
                    "features": ["health", "player_movement"],
                    "scene": "res://Features/player_movement/Player.tscn",
                },
                "trace_boss": {"role": "enemy", "features": ["chase_movement", "health"]},
            },
            "systems": ["enemy_spawn"],
            "loop": {"start": "player spawned", "cycle": "boss chases player",
                     "end": "boss defeated"},
            "validation": {"required_entities": ["player", "trace_boss"],
                           "required_features": [], "required_tests": ["health",
                                                                      "chase_movement"]},
        },
        "host": "TraceBaselineBossHost",
        "target": "trace_boss:player",
        "level_id": "trace_baseline_single_stage_boss",
        "planner_args": ["--mode", "boss", "--boss", "trace_boss"],
        "probe": "boss",
    },
    # Phase 1.24：waves / holdout 黄金基线场景。两者都不消费 composition plan
    # （敌人来自关卡配置的运行时生成，宿主用既有 waves/holdout 适配层场景），
    # 因此生成链路省略 plan_generator / --compose-plan——架构事实，不是偷工。
    "waves": {
        "description": "waves：按配置进入波次 → 清一波才起下一波 → 清场解锁出口 → "
                       "玩家到出口结算 Victory",
        "coverage": [
            "orchestration_started（waves 模式）",
            "第一波按配置生成；首波未清空时第二波不生成（探针度量断言，trace 契约"
            "当前不含波次事件——已知限制）",
            "全部波次清空后出口才解锁、玩家进入出口区才结算（探针度量断言）",
            "level_victory（exit_reached_after_unlock）且为最后一个事件",
        ],
        "gameplay": {
            "gameplay": {"id": "trace_baseline_waves_game"},
            "entities": {
                "player": {
                    "role": "player",
                    "features": ["health", "player_movement"],
                    "scene": "res://Features/player_movement/Player.tscn",
                },
                "trace_grunt": {"role": "enemy", "features": ["chase_movement", "health"]},
            },
            "systems": ["enemy_spawn"],
            "loop": {"start": "player spawned", "cycle": "clear waves; reach exit",
                     "end": "all waves cleared"},
            "validation": {"required_entities": ["player", "trace_grunt"],
                           "required_features": [], "required_tests": ["health",
                                                                       "chase_movement"]},
        },
        "arena": "res://Scenes/TimedCombatArena.tscn",
        "focus_scene": "res://Scenes/TraceGrunt.tscn",
        "level_id": "trace_baseline_waves",
        "planner_args": ["--mode", "waves", "--waves", "2", "--wave-size", "1"],
        "probe": "level",
        "plan": False,
    },
    "holdout": {
        "description": "holdout：持续生成 → 存活期满前不结算 → survive_duration 到点"
                       "恰好一次 Victory",
        "coverage": [
            "orchestration_started（holdout 模式）",
            "持续生成按配置调度（探针度量 alive_seen > 0）",
            "存活期满前不结算（探针断言 finish_events 为空）",
            "level_victory（survive_duration）恰好一次且为最后一个事件",
        ],
        "gameplay": {
            "gameplay": {"id": "trace_baseline_holdout_game"},
            "entities": {
                "player": {
                    "role": "player",
                    "features": ["health", "player_movement"],
                    "scene": "res://Features/player_movement/Player.tscn",
                },
                "trace_grunt": {"role": "enemy", "features": ["chase_movement", "health"]},
            },
            "systems": ["enemy_spawn"],
            "loop": {"start": "player spawned", "cycle": "survive the assault",
                     "end": "survival duration elapsed"},
            "validation": {"required_entities": ["player", "trace_grunt"],
                           "required_features": [], "required_tests": ["health",
                                                                       "chase_movement"]},
        },
        "arena": "res://Scenes/SurvivalArena.tscn",
        "level_id": "trace_baseline_holdout",
        "planner_args": ["--mode", "holdout", "--survival-duration", "2.0",
                         "--spawn-interval", "0.3", "--max-alive", "3"],
        "probe": "holdout",
        "plan": False,
    },
}

_GODOT_VERSION: dict = {}


class CaptureError(RuntimeError):
    """生成链路 / 探针 / 环境失败（CLI 退出码 2 用于输入错误，1 用于采集失败）。"""


@dataclass
class CaptureResult:
    ok: bool
    scenario_id: str
    trace_document: dict = field(default_factory=dict)
    evidence: dict = field(default_factory=dict)
    output: str = ""
    sandbox: str = ""
    cleanup_ok: bool = False
    duration_s: float = 0.0
    error: str = ""


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


def godot_version(godot) -> str:
    key = str(godot)
    if key in _GODOT_VERSION:
        return _GODOT_VERSION[key]
    try:
        proc = subprocess.run([str(godot), "--version"], capture_output=True, text=True,
                              encoding="utf-8", errors="replace", timeout=60,
                              stdin=subprocess.DEVNULL)
        version = (proc.stdout or proc.stderr or "").strip().splitlines()
        _GODOT_VERSION[key] = version[0].strip() if version else ""
    except (OSError, subprocess.SubprocessError):
        _GODOT_VERSION[key] = ""
    return _GODOT_VERSION[key]


def _run(sandbox: Path, script_rel: str, *argv, timeout: int = 300) -> subprocess.CompletedProcess:
    cmd = [sys.executable, str(sandbox / ".ai" / "tools" / script_rel)] + [str(a) for a in argv]
    proc = subprocess.run(cmd, capture_output=True, text=True, encoding="utf-8",
                          errors="replace", cwd=str(sandbox), stdin=subprocess.DEVNULL,
                          timeout=timeout)
    if proc.returncode != 0:
        raise CaptureError("generation step failed (%s, exit %d):\n%s"
                           % (script_rel, proc.returncode,
                              ((proc.stdout or "") + (proc.stderr or ""))[-1200:]))
    return proc


def _make_sandbox(scenario_id: str, godot=None) -> Path:
    """创建沙箱并重建导入缓存（Phase 1.25 性能优化）。

    实测（11.7k 文件 / 265MB 项目；环境守卫对同盘（F:）真实删除计数并终止进程，
    %TEMP%（C:）不计数——见 SANDBOX_IGNORE 注释与 WORK_STATE）：

        拷整个项目到 %TEMP%          = 51s + rmtree 125s = 176s/次
        拷 567 文件（.godot 除外）    =  4.3s + godot --import 26.5s + rmtree 11s
                                     =  42s/次（4.2x）

    .godot 完全不拷贝：`--import` 在沙箱内从源文件重建导入缓存与
    global_script_class_cache（class_name 注册），探针可正常加载场景与脚本。
    删除发生在 C:（守卫的监视盘之外），不会触发批量删除守卫。
    """
    sandbox = Path(tempfile.mkdtemp(prefix="trace_baseline_%s_" % scenario_id))
    shutil.copytree(PROJECT_ROOT, sandbox, ignore=shutil.ignore_patterns(*SANDBOX_IGNORE),
                    dirs_exist_ok=True)
    if godot is not None:
        proc = subprocess.run([str(godot), "--headless", "--path", str(sandbox),
                               "--import"], capture_output=True, text=True,
                              encoding="utf-8", errors="replace", timeout=300,
                              stdin=subprocess.DEVNULL)
        if proc.returncode != 0:
            raise CaptureError("sandbox import rebuild failed (exit %d):\n%s"
                               % (proc.returncode,
                                  ((proc.stdout or "") + (proc.stderr or ""))[-800:]))
    return sandbox


def _generate(sandbox: Path, scenario: dict) -> dict:
    """在沙箱内跑完整生成链路；返回产物与命令证据。"""
    level_id = scenario["level_id"]
    work = sandbox / "tmp" / ("trace_baseline_%s" % level_id)
    work.mkdir(parents=True, exist_ok=True)
    gameplay_path = work / "gameplay.yaml"
    gameplay_path.write_text(
        json.dumps(scenario["gameplay"], ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8", newline="\n")
    # gameplay 是 JSON（合法 YAML 子集），避免沙箱内额外的 YAML 序列化差异。
    blueprint_generator.write_entity_blueprints(scenario["gameplay"], work / "entities")
    bindings_path = work / "bindings.yaml"
    _run(sandbox, "asset_registry/bind_assets.py", "--gameplay", gameplay_path,
         "--out", bindings_path)

    blueprint_paths = sorted((work / "entities").glob("*.yaml"))
    if not blueprint_paths:
        raise CaptureError("blueprint generation produced no entity blueprints")
    for blueprint in blueprint_paths:
        _run(sandbox, "scene_composer/scene_composer.py", blueprint,
             "--out", sandbox / "Scenes", "--bindings", bindings_path)

    plan_path = ""
    if scenario.get("plan", True):
        # boss 模式专属：waves / holdout 的敌人来自关卡配置的运行时生成，
        # 宿主用既有适配层场景，不消费 composition plan（架构事实，见场景注释）。
        plan_path = work / "plan.yaml"
        _run(sandbox, "scene_composer/plan_generator.py", gameplay_path,
             "--host", scenario["host"], "--target", scenario["target"], "--out", plan_path)
        _run(sandbox, "scene_composer/scene_composer.py", "--compose-plan", plan_path,
             "--out", sandbox / "Scenes")

    level_path = sandbox / "Levels" / ("%s.json" % level_id)
    plan_args = ["--plan", plan_path] if plan_path else []
    _run(sandbox, "gameplay_planner/level_planner.py", gameplay_path,
         *plan_args, *scenario["planner_args"],
         "--out", level_path, "--level-id", level_id)
    _run(sandbox, "validator/check_level.py", level_path, *(
        ["--plan", plan_path] if plan_path else []))

    return {
        "work": work,
        "gameplay": gameplay_path,
        "bindings": bindings_path,
        "blueprints": blueprint_paths,
        "plan": plan_path,
        "level": level_path,
        "level_res": "res://Levels/%s.json" % level_id,
        "arena_scene": ("res://Scenes/%s.tscn" % scenario["host"]) if scenario.get("host")
                       else scenario["arena"],
        "focus_scene": scenario.get("focus_scene", ""),
    }


def _probe(sandbox: Path, scenario: dict, artifacts: dict, godot, timeout: int) -> dict:
    """运行真实 Godot 探针；返回 trace 文档与运行时度量。"""
    level_res = artifacts["level_res"]
    if scenario["probe"] == "level":
        result = level_orchestration_probe.run_level_probe(
            level_res, project_root=sandbox, godot=godot, timeout=timeout,
            arena_res=artifacts["arena_scene"], focus_scene=artifacts["focus_scene"])
        if not result.ok:
            raise CaptureError("level probe failed (exit %d):\n%s"
                               % (result.exit_code, (result.output or "")[-1500:]))
        return {"trace": result.trace_document, "metrics": result.metrics,
                "output": result.output, "trace_path": result.trace_path,
                "script_removed": result.script_removed}
    if scenario["probe"] == "holdout":
        result = holdout_trace_probe.run_holdout_probe(
            level_res, project_root=sandbox, godot=godot, timeout=timeout,
            arena_res=artifacts["arena_scene"])
        if not result.ok:
            raise CaptureError("holdout probe failed (exit %d):\n%s"
                               % (result.exit_code, (result.output or "")[-1500:]))
        return {"trace": result.trace_document, "metrics": result.metrics,
                "output": result.output, "trace_path": result.trace_path,
                "script_removed": result.script_removed}
    if scenario["probe"] == "multi_stage":
        result = multi_stage_boss_probe.run_multi_stage_probe(
            level_res, project_root=sandbox, godot=godot, timeout=timeout)
        if not result.ok:
            raise CaptureError("multi-stage probe failed (exit %d):\n%s"
                               % (result.exit_code, (result.output or "")[-1500:]))
        return {"trace": result.trace_document, "metrics": result.metrics,
                "output": result.output, "trace_path": result.trace_path,
                "script_removed": result.script_removed}

    # 受控负向配置（宿主不存在该实例）：只用于探针的运行时拒绝分支，不参与 trace。
    level_doc = json.loads(artifacts["level"].read_text(encoding="utf-8"))
    bad_doc = json.loads(json.dumps(level_doc))
    bad_doc["boss"]["instance"] = "NoSuchBoss"
    bad_path = artifacts["level"].with_name("%s_bad.json" % scenario["level_id"])
    bad_path.write_text(json.dumps(bad_doc, ensure_ascii=False, indent=2) + "\n",
                        encoding="utf-8", newline="\n")
    result = boss_level_probe.run_boss_probe(
        level_res, "res://Levels/%s" % bad_path.name, project_root=sandbox,
        godot=godot, timeout=timeout)
    if not result.ok:
        raise CaptureError("boss probe failed (exit %d):\n%s"
                           % (result.exit_code, (result.output or "")[-1500:]))
    return {"trace": result.trace_document, "metrics": result.metrics,
            "output": result.output, "trace_path": result.trace_path,
            "script_removed": result.script_removed}


def capture(scenario_id: str, *, godot=None, keep_sandbox: bool = False,
            timeout: int = 300, project_root: Path = PROJECT_ROOT) -> CaptureResult:
    """跑一次真实采集；任何失败都返回 ok=False（不抛异常给调用方做退出码决定）。"""
    if scenario_id not in SCENARIOS:
        raise CaptureError("unknown scenario %r (known: %s)"
                           % (scenario_id, ", ".join(sorted(SCENARIOS))))
    scenario = SCENARIOS[scenario_id]
    godot = Path(godot) if godot else find_godot(project_root)
    if godot is None or not Path(godot).is_file():
        raise CaptureError("godot executable not found; set GODOT_BIN or add it to PATH")

    started = time.time()
    sandbox = _make_sandbox(scenario_id, godot=godot)
    result = CaptureResult(ok=False, scenario_id=scenario_id, sandbox=str(sandbox))
    try:
        artifacts = _generate(sandbox, scenario)
        probe = _probe(sandbox, scenario, artifacts, godot, timeout)
        trace = probe["trace"]
        if not isinstance(trace, dict) or not trace.get("events"):
            raise CaptureError("probe produced no orchestration trace (no real events to compare)")
        result.trace_document = trace
        result.output = probe.get("output") or ""
        result.evidence = {
            "scenario_id": scenario_id,
            "description": scenario["description"],
            "coverage": list(scenario["coverage"]),
            "godot_version": godot_version(godot),
            "probe": {"multi_stage": "multi_stage_boss_probe.py",
                      "boss": "boss_level_probe.py",
                      "level": "level_orchestration_probe.py",
                      "holdout": "holdout_trace_probe.py"}[scenario["probe"]],
            "level_config": artifacts["level_res"],
            "arena_scene": artifacts["arena_scene"],
            "generation_chain": [
                "blueprint_generator.write_entity_blueprints",
                "asset_registry/bind_assets.py",
                "scene_composer/scene_composer.py (per entity)",
                "scene_composer/plan_generator.py",
                "scene_composer/scene_composer.py --compose-plan",
                "gameplay_planner/level_planner.py",
                "validator/check_level.py --plan",
                scenario["probe"] + " probe (real Godot headless)",
            ],
            "probe_metrics": probe.get("metrics") or {},
            "trace_event_count": len(trace.get("events") or []),
            "probe_script_removed": bool(probe.get("script_removed")),
        }
        result.ok = True
    except (CaptureError, OSError, subprocess.SubprocessError) as exc:
        result.error = str(exc)
    finally:
        result.duration_s = round(time.time() - started, 2)
        if keep_sandbox:
            result.cleanup_ok = True
        else:
            try:
                shutil.rmtree(sandbox)
                result.cleanup_ok = not sandbox.exists()
            except OSError as exc:                           # pragma: no cover - 清理失败要报告
                result.cleanup_ok = False
                if result.ok:
                    result.ok = False
                    result.error = "sandbox cleanup failed: %s" % exc
    return result


def main(argv=None) -> int:
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
        sys.stderr.reconfigure(encoding="utf-8")
    parser = argparse.ArgumentParser(
        description="Capture a real Godot orchestration trace in an isolated sandbox.")
    parser.add_argument("scenario", nargs="?", help="scenario id (see --list)")
    parser.add_argument("--list", action="store_true", help="list known scenarios")
    parser.add_argument("--out", default="", help="write the captured trace JSON here")
    parser.add_argument("--evidence", default="", help="write the capture evidence JSON here")
    parser.add_argument("--project", default=str(PROJECT_ROOT))
    parser.add_argument("--keep-sandbox", action="store_true")
    parser.add_argument("--timeout", type=int, default=300)
    args = parser.parse_args(argv)

    if args.list:
        for scenario_id in sorted(SCENARIOS):
            print("%s: %s" % (scenario_id, SCENARIOS[scenario_id]["description"]))
        return 0
    if not args.scenario:
        parser.error("a scenario id is required (or use --list)")

    try:
        result = capture(args.scenario, keep_sandbox=args.keep_sandbox,
                         timeout=args.timeout, project_root=Path(args.project).resolve())
    except CaptureError as exc:
        print("FAIL: %s" % exc, file=sys.stderr)
        return 2

    if not result.ok:
        print("FAIL: %s" % result.error, file=sys.stderr)
        return 1
    if args.out:
        Path(args.out).write_text(
            json.dumps(result.trace_document, ensure_ascii=False, indent=2) + "\n",
            encoding="utf-8", newline="\n")
    if args.evidence:
        Path(args.evidence).write_text(
            json.dumps(result.evidence, ensure_ascii=False, indent=2) + "\n",
            encoding="utf-8", newline="\n")
    print("Capture: scenario=%s events=%d duration=%.2fs cleanup=%s"
          % (result.scenario_id, len(result.trace_document.get("events") or []),
             result.duration_s, "ok" if result.cleanup_ok else "FAILED"))
    print("Trace: run_id=%s schema=%s"
          % (result.trace_document.get("run_id"),
             result.trace_document.get("schema_version")))
    for line in (result.output or "").splitlines():
        if line.startswith(("PASS:", "STAGE:", "BOSS:")):
            print("  " + line)
    return 0


if __name__ == "__main__":
    sys.exit(main())
