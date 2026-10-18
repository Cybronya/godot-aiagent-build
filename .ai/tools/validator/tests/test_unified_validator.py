#!/usr/bin/env python3
"""Unified Validator 回归测试（Phase 1.15，C10）。

覆盖：
    C10-a  稳定错误代码：各层失败文本映射到稳定 code（GAMEPLAY_/SCENE_/LEVEL_/RUNTIME_*），
           原始原因原样保留（不丢错误位置）。
    C10-b  统一汇总：run_layers 聚合多层的结构化诊断；局部失败不阻断其他层
           （无效 level 与合法 gameplay 同批请求时两层都有结果）。
    C10-c  Runtime 不可用如实报告：Godot 二进制缺失时 runtime 层标记 unavailable
           （INCOMPLETE 语义），绝不伪装成 PASS。
    C10-d  CLI 集成：validate.py --level 正例 exit 0 且输出 [level] PASS；
           反例 exit 1 且诊断带稳定代码与位置。
    C10-e  输出格式：format_layer_report 保留 layer/code/location/path/reason/hint。

用法:
    python .ai/tools/validator/tests/test_unified_validator.py
全部通过输出 PASS 并退出 0；任一失败输出 FAIL 并退出 1。
"""

from __future__ import annotations

import io
import json
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

import yaml

TEST_DIR = Path(__file__).resolve().parent
VALIDATOR_DIR = TEST_DIR.parent
TOOLS_DIR = VALIDATOR_DIR.parent
PROJECT_ROOT = TOOLS_DIR.parent.parent

if str(VALIDATOR_DIR) not in sys.path:
    sys.path.insert(0, str(VALIDATOR_DIR))
if str(TOOLS_DIR) not in sys.path:
    sys.path.insert(0, str(TOOLS_DIR))
if str(TOOLS_DIR / "gameplay_planner") not in sys.path:
    sys.path.insert(0, str(TOOLS_DIR / "gameplay_planner"))

import unified                                                          # noqa: E402
from level_planner import validate_level                                # noqa: E402

_failures: list[str] = []
_temp_dirs: list[Path] = []

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")


def ok(name: str, condition: bool, detail: str = "") -> None:
    if condition:
        print("PASS: " + name)
    else:
        _failures.append(name + (" | " + detail if detail else ""))


def _temp_project() -> Path:
    temp = Path(tempfile.mkdtemp(prefix="unified_validator_"))
    _temp_dirs.append(temp)
    # 最小实体场景（level 层的 res:// 存在性检查需要）
    (temp / "Scenes").mkdir(parents=True, exist_ok=True)
    (temp / "Scenes" / "Enemy.tscn").write_text("[gd_scene format=3]\n", encoding="utf-8")
    return temp


def _write_level(path: Path, config: dict) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(config, ensure_ascii=False, indent=2), encoding="utf-8")
    return path


def _write(path: Path, text: str) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")
    return path


def _stage_fixture(project: Path) -> tuple:
    """临时项目：真实宿主文件 + composition_plan + 多阶段 LevelConfig。"""
    (project / "Scenes").mkdir(parents=True, exist_ok=True)
    for name in ("Boss", "Enemy", "Player"):
        (project / "Scenes" / (name + ".tscn")).write_text(
            "[gd_scene format=3]\n", encoding="utf-8")
    (project / "Scenes" / "StageHost.tscn").write_text(
        "[gd_scene format=3]\n\n"
        '[node name="StageHost" type="Node2D"]\n\n'
        '[node name="Player" parent="." instance=ExtResource("1_p")]\n\n'
        '[node name="Boss" parent="." instance=ExtResource("2_b")]\n\n'
        '[node name="Grunt" parent="." instance=ExtResource("3_g")]\n',
        encoding="utf-8")
    plan = {
        "document": "composition_plan", "schema_version": 1,
        "host": {"name": "StageHost"},
        "instances": [
            {"entity": "player", "scene": "res://Scenes/Player.tscn",
             "instance_name": "Player"},
            {"entity": "boss", "scene": "res://Scenes/Boss.tscn",
             "instance_name": "Boss"},
            {"entity": "grunt", "scene": "res://Scenes/Enemy.tscn",
             "instance_name": "Grunt"},
        ],
    }
    plan_path = _write(project / "plan.yaml", yaml.safe_dump(plan, sort_keys=False))
    level = {
        "schema": {"id": "level_orchestration", "version": 2},
        "level": {"id": "unified_stage_level", "arena_scene": "res://Scenes/StageHost.tscn"},
        "mode": "boss",
        "entities": {"boss": {"scene": "res://Scenes/Boss.tscn"},
                     "grunt": {"scene": "res://Scenes/Enemy.tscn"}},
        "boss": {"entity": "boss", "instance": "Boss", "spawn": "existing"},
        "stages": [
            {"id": "clear_1", "type": "clear_enemies",
             "entries": [{"entity": "grunt", "count": 2}]},
            {"id": "boss", "type": "defeat_boss", "entity": "boss"},
        ],
        "exit": {"unlock_when": "never"},
        "victory": {"condition": "boss_defeated"},
    }
    level_path = _write_level(project / "Levels" / "stage.json", level)
    return level_path, plan_path, level


def _valid_waves_config(project_root: Path) -> dict:
    return {
        "schema": {"id": "level_orchestration", "version": 2},
        "level": {"id": "unified_valid_level", "arena_scene": "res://Scenes/TimedCombatArena.tscn"},
        "mode": "waves",
        "entities": {"enemy": {"scene": "res://Scenes/Enemy.tscn"}},
        "waves": [{"id": "wave_1", "duration": 30.0,
                   "entries": [{"entity": "enemy", "count": 2}]}],
        "exit": {"unlock_when": "all_waves_cleared"},
        "victory": {"condition": "exit_reached_after_unlock"},
    }


def run() -> int:
    # ---- C10-a：稳定错误代码 ----
    cases = [
        ("gameplay", "Missing Entity Scene: Enemy", "GAMEPLAY_ENTITY_SCENE_MISSING"),
        ("gameplay", "Gameplay incomplete: no entity provides damage_source", "GAMEPLAY_INCOMPLETE"),
        ("gameplay", "Unknown System: enemy_spawn", "GAMEPLAY_UNKNOWN_SYSTEM"),
        ("scene", "Missing Feature: chase_movement (node Enemy)", "SCENE_FEATURE_MISSING"),
        ("scene", "Invalid Root Node Type", "SCENE_ROOT_TYPE"),
        ("runtime", "Runtime playtest TIMEOUT after 30s", "RUNTIME_TIMEOUT"),
        ("runtime", "Runtime playtest CRASH: exit_code=-1073741819", "RUNTIME_CRASH"),
        ("level", "waves[0].entries[0].count: must be an integer >= 1, got 0", "LEVEL_WAVES"),
        ("level", "mode: unsupported value 'party'", "LEVEL_MODE"),
        ("level", "holdout.spawns[0].interval: must be a number > 0", "LEVEL_HOLDOUT"),
        ("level", "boss.instance: required when boss.spawn is 'existing'", "LEVEL_BOSS"),
        ("level", "stages[1].type: unsupported stage type 'teleport'", "LEVEL_STAGES"),
    ]
    for layer, message, expected_code in cases:
        diag = unified.diagnose(layer, message, "somewhere")
        ok("C10-a: %r -> %s" % (message[:40], expected_code),
           diag["code"] == expected_code and diag["reason"] == message
           and diag["layer"] == layer and diag["severity"] == "error",
           repr(diag))
    fallback = unified.diagnose("gameplay", "something entirely new happened")
    ok("C10-a: unrecognized text falls back to a stable layer code without losing the reason",
       fallback["code"] == "GAMEPLAY_FAILURE" and fallback["reason"] == "something entirely new happened",
       repr(fallback))

    # ---- C10-b：统一汇总 + 局部失败不阻断其他层 ----
    project = _temp_project()
    valid_level = _write_level(project / "Levels" / "valid.json", _valid_waves_config(project))
    bad_level = _write_level(project / "Levels" / "bad.json", {
        "schema": {"id": "level_orchestration", "version": 2},
        "level": {"id": "unified_bad_level"},
        "mode": "party_mode",
        "entities": {"enemy": {"scene": "res://Scenes/Enemy.tscn"}},
        "waves": [],
    })
    gameplay_blueprint = _write(
        project / "gameplay.yaml",
        "gameplay:\n  id: unified_game\n"
        "entities:\n  enemy:\n    role: enemy\n    features: [health]\n"
        "    scene: res://Scenes/Enemy.tscn\n"
        "loop:\n  start: a\n  cycle: b\n  end: enemy defeated\n")
    # Gameplay 正例直接指向真实仓库的 survival_game.yaml（临时项目无 feature_index）。
    unified_result = unified.run_layers(
        str(PROJECT_ROOT),
        level_configs=[str(valid_level), str(bad_level)],
        gameplay_blueprints=[str(PROJECT_ROOT / "survival_game.yaml")],
    )
    layers = {result["layer"] + str(i): result for i, result in enumerate(unified_result["results"])}
    level_results = [r for r in unified_result["results"] if r["layer"] == "level"]
    gameplay_results = [r for r in unified_result["results"] if r["layer"] == "gameplay"]
    ok("C10-b: every requested layer produced a result (no silent skips)",
       len(level_results) == 2 and len(gameplay_results) == 1,
       repr([(r["layer"], r.get("checked")) for r in unified_result["results"]]))
    ok("C10-b: valid level passes with zero diagnostics",
       level_results[0]["ok"] and not level_results[0]["diagnostics"],
       repr(level_results[0]["diagnostics"]))
    bad_diag_codes = [d["code"] for d in level_results[1]["diagnostics"]]
    ok("C10-b: invalid level fails with stable codes",
       not level_results[1]["ok"] and "LEVEL_MODE" in bad_diag_codes and "LEVEL_WAVES" in bad_diag_codes,
       repr(bad_diag_codes))
    ok("C10-b: invalid level diagnostics keep the config location",
       all(d["location"].endswith("bad.json") for d in level_results[1]["diagnostics"]),
       repr([d["location"] for d in level_results[1]["diagnostics"]]))
    ok("C10-b: the independent gameplay layer still ran and passed",
       gameplay_results[0]["ok"] and gameplay_results[0]["checked"] == 2,
       repr(gameplay_results[0]))
    ok("C10-b: aggregated diagnostics flatten every layer's findings",
       len(unified_result["diagnostics"]) == sum(len(r["diagnostics"]) for r in unified_result["results"]),
       repr(len(unified_result["diagnostics"])))

    # ---- C10-c：Runtime 不可用如实报告 ----
    original = unified._godot_binary
    unified._godot_binary = lambda project_root: None
    try:
        runtime_result = unified.run_runtime_layer(str(PROJECT_ROOT), scene="res://Scenes/Enemy.tscn")
        aggregated = unified.run_layers(str(PROJECT_ROOT), runtime_scenes=["res://Scenes/Enemy.tscn"])
    finally:
        unified._godot_binary = original
    ok("C10-c: missing Godot is reported as unavailable, not PASS",
       runtime_result.get("unavailable") and not runtime_result.get("ok")
       and runtime_result.get("diagnostics") == [],
       repr(runtime_result))
    runtime_layer = aggregated["results"][0]
    fake_layer = {"layer": "runtime", "checked": 0, "diagnostics": [], "errors": [],
                  "warnings": [], "ok": False, "unavailable": "forced", "note": ""}
    ok("C10-c: run_layers surfaces the unavailable reason for INCOMPLETE reporting",
       bool(aggregated["unavailable"]) and aggregated["unavailable"][0]["layer"] == "runtime",
       repr(aggregated["unavailable"]))
    report_lines = unified.format_layer_report({"results": [runtime_layer, fake_layer],
                                                "unavailable": aggregated["unavailable"]})
    ok("C10-c: the layer report marks the runtime row UNAVAILABLE",
       any("UNAVAILABLE" in line and "runtime" in line for line in report_lines),
       repr(report_lines))

    # ---- C10-e：Binding 层（Phase 1.18）----
    # 权威实现复用 check_binding_schema.check_bindings；无 gameplay blueprint 时
    # 「信息不足」必须以 info 诊断呈现（不虚构成功，也不计为错误）。
    binding_dir = _temp_project() / "bindings"
    binding_dir.mkdir(parents=True, exist_ok=True)
    (binding_dir / "binding.yaml").write_text(yaml.safe_dump({
        "schema_version": 2,
        "binding": {"source": "gameplay_blueprint", "gameplay": "demo",
                    "entities": [{"entity": "enemy",
                                  "bindings": [{"entity": "ghost", "role": "idle",
                                                "asset": "slime_idle"}]}],
                    }},
        sort_keys=False, allow_unicode=True), encoding="utf-8")
    binding_result = unified.run_binding_layer(str(binding_dir))
    ok("C10-e: the binding layer runs via the shared checker implementation",
       binding_result["layer"] == "binding" and binding_result.get("checked") == 1,
       repr(binding_result))
    ok("C10-e: missing gameplay blueprint yields an info diagnostic (insufficient"
       " input, never a fake pass)",
       not binding_result["errors"]
       and any(d["code"] == "BINDING_INFO_INSUFFICIENT_INPUT"
               and d["severity"] == "info" for d in binding_result["diagnostics"]),
       repr(binding_result["diagnostics"]))
    blueprint_path = binding_dir.parent / "gameplay.yaml"
    blueprint_path.write_text(yaml.safe_dump(
        {"gameplay": {"id": "demo"},
         "entities": {"enemy": {"role": "enemy", "features": ["health"]}}},
        sort_keys=False, allow_unicode=True), encoding="utf-8")
    binding_result = unified.run_binding_layer(str(binding_dir),
                                               gameplay_blueprint=str(blueprint_path))
    ok("C10-e: an unknown entity scope becomes a locatable error diagnostic",
       len(binding_result["errors"]) == 1
       and "ghost" in binding_result["errors"][0]["reason"]
       and binding_result["errors"][0]["code"].startswith("BINDING"),
       repr(binding_result["errors"]))
    ok("C10-e: the layer reports FAIL with the stable BINDING code",
       not binding_result["ok"], repr(binding_result["ok"]))
    aggregated = unified.run_layers(str(PROJECT_ROOT), bindings_dirs=[str(binding_dir)],
                                    binding_gameplay=str(blueprint_path))
    ok("C10-e: run_layers aggregates the binding layer with the others",
       any(result["layer"] == "binding" for result in aggregated["results"])
       and "binding" in aggregated["layers_run"],
       repr(aggregated["layers_run"]))

    # ---- C10-f：LevelConfig ↔ composition_plan 交叉校验（Phase 1.21）----
    cross_project = _temp_project()
    stage_level, stage_plan, stage_doc = _stage_fixture(cross_project)
    cross_result = unified.run_level_layer(str(stage_level), str(cross_project),
                                           str(stage_plan))
    ok("C10-f: level layer cross-checks the host/plan identities",
       cross_result["ok"] and not cross_result["errors"]
       and cross_result["checked"] > 0, repr(cross_result))
    skipped_result = unified.run_level_layer(str(stage_level), str(cross_project))
    ok("C10-f: multi-stage config without a plan reports INCOMPLETE as info, not PASS/error",
       skipped_result["ok"]
       and any(d["code"] == "LEVEL_INFO_CROSS_CHECK_SKIPPED"
               and d["severity"] == "info" for d in skipped_result["diagnostics"])
       and not skipped_result["errors"], repr(skipped_result["diagnostics"]))
    aggregated = unified.run_layers(
        str(cross_project), level_configs=[str(stage_level)],
        level_plans=[str(stage_plan)])
    ok("C10-f: run_layers pairs --level with --level-plan",
       aggregated["results"][0]["ok"]
       and not any(d["code"] == "LEVEL_INFO_CROSS_CHECK_SKIPPED"
                   for d in aggregated["diagnostics"]), repr(aggregated))

    # ---- C10-d：validate.py CLI 集成 ----
    proc = subprocess.run(
        [sys.executable, str(VALIDATOR_DIR / "validate.py"), "--level", str(valid_level)],
        capture_output=True, text=True, encoding="utf-8", errors="replace",
        cwd=str(PROJECT_ROOT), stdin=subprocess.DEVNULL, timeout=300)
    ok("C10-d: validate.py --level (valid) exits 0 and reports the layer PASS",
       proc.returncode == 0 and "[level] PASS" in (proc.stdout or ""),
       "exit=%s tail=%s" % (proc.returncode, (proc.stdout + proc.stderr)[-300:]))
    proc = subprocess.run(
        [sys.executable, str(VALIDATOR_DIR / "validate.py"), "--level", str(bad_level)],
        capture_output=True, text=True, encoding="utf-8", errors="replace",
        cwd=str(PROJECT_ROOT), stdin=subprocess.DEVNULL, timeout=300)
    combined = (proc.stdout or "") + (proc.stderr or "")
    ok("C10-d: validate.py --level (invalid) exits 1 with stable codes and location",
       proc.returncode == 1 and "LEVEL_MODE" in combined and "bad.json" in combined,
       "exit=%s tail=%s" % (proc.returncode, combined[-400:]))
    proc = subprocess.run(
        [sys.executable, str(VALIDATOR_DIR / "validate.py"), "--level", str(stage_level),
         "--level-plan", str(stage_plan), "--project-root", str(cross_project)],
        capture_output=True, text=True, encoding="utf-8", errors="replace",
        cwd=str(PROJECT_ROOT), stdin=subprocess.DEVNULL, timeout=300)
    ok("C10-f: validate.py --level --level-plan (matching) exits 0",
       proc.returncode == 0 and "[level] PASS" in (proc.stdout or ""),
       "exit=%s tail=%s" % (proc.returncode, (proc.stdout + proc.stderr)[-400:]))
    bad_stage_doc = json.loads(json.dumps(stage_doc))
    bad_stage_doc["boss"]["instance"] = "Ghost"
    bad_stage = _write_level(cross_project / "Levels" / "stage_bad.json", bad_stage_doc)
    proc = subprocess.run(
        [sys.executable, str(VALIDATOR_DIR / "validate.py"), "--level", str(bad_stage),
         "--level-plan", str(stage_plan), "--project-root", str(cross_project)],
        capture_output=True, text=True, encoding="utf-8", errors="replace",
        cwd=str(PROJECT_ROOT), stdin=subprocess.DEVNULL, timeout=300)
    combined = (proc.stdout or "") + (proc.stderr or "")
    ok("C10-f: validate.py blocks a mismatched boss.instance with LEVEL_BOSS",
       proc.returncode == 1 and "LEVEL_BOSS" in combined and "Ghost" in combined,
       "exit=%s tail=%s" % (proc.returncode, combined[-400:]))

    # ---- C10-e：输出格式字段完整 ----
    sample = unified._diag("level", "LEVEL_MODE", "error", location="cfg.json",
                           path="mode", reason="unsupported value", hint="use waves or holdout")
    ok("C10-e: diagnostics carry layer/code/severity/location/path/reason/hint",
       set(sample) == {"layer", "code", "severity", "location", "path", "reason", "hint"},
       repr(sorted(sample)))

    print()
    if _failures:
        print("FAIL: %d failing check(s)" % len(_failures))
        for failure in _failures:
            print("  - " + failure)
        return 1
    print("PASS: all unified validator checks passed (C10)")
    return 0


def cleanup() -> None:
    for temp in _temp_dirs:
        shutil.rmtree(temp, ignore_errors=True)


if __name__ == "__main__":
    try:
        code = run()
    finally:
        cleanup()
    sys.exit(code)
