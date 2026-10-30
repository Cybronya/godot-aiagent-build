#!/usr/bin/env python3
"""跨层关卡契约一致性测试（Phase 1.15，C1–C9）。

方法（任务书 5：共享正反例，避免各测试自造配置导致语义漂移）：

    本文件维护**唯一一份**正反例关卡配置（FIXTURES），同一份配置同时经过：
        1. Python 权威实现  gameplay_planner/level_planner.validate_level
        2. Godot 运行时实现 Orchestration/level_config.gd（LevelConfig，真实 headless 探针）
    逐例比较「接受 / 拒绝」判定与错误字段路径，两层不一致即失败。

覆盖：
    C1  合法 waves 配置在两层判断一致（v2）。
    C2  合法 holdout 配置在两层判断一致。
    C3  不支持的 mode 在所有适用层被拒绝。
    C4  未知实体引用（waves 条目与 holdout spawn）不会被任一层静默接受。
    C5  非法波次结构的错误语义一致（同 JSON 字段路径）。
    C6  版本兼容行为一致：v1 遗留配置两层都接受；v1+holdout 两层都拒绝。
    C7  缺少可选配置（exit/victory 缺省块）时默认行为一致（编排器默认值 =
        producer 常量）。
    C8  显式无效配置不会因默认值或兼容路径而被接受。
    C10 boss 模式（Phase 1.20）：合法 Boss 配置一致接受；未知 Boss 实体 /
        existing 缺实例 / 非法 spawn / 非法胜利规则两层一致拒绝。
    C11 多阶段 Boss（Phase 1.21）：合法 clear→boss / clear→boss→complete 两层一致
        接受；空阶段 / 重复 id / 未知类型 / 缺 Boss 引用 / 顺序非法 / 终结规则冲突 /
        waves 或 holdout 声明 stages 两层一致拒绝。
    C9  作用域边界一致：Godot 编排层不消费资源绑定（绑定的权威实现是
        asset_registry/bind_assets.py，由 test_binding_scope.py 覆盖）。

用法:
    python .ai/tools/validator/tests/test_cross_layer_contract.py
全部通过输出 PASS 并退出 0；任一失败输出 FAIL 并退出 1。
Godot 不可用时如实打印 SKIP（不伪装通过，也不算失败）。
"""

from __future__ import annotations

import json
import re
import subprocess
import sys
from pathlib import Path

TEST_DIR = Path(__file__).resolve().parent
VALIDATOR_DIR = TEST_DIR.parent
TOOLS_DIR = VALIDATOR_DIR.parent
PROJECT_ROOT = TOOLS_DIR.parent.parent

if str(TOOLS_DIR) not in sys.path:
    sys.path.insert(0, str(TOOLS_DIR))
if str(TOOLS_DIR / "gameplay_planner") not in sys.path:
    sys.path.insert(0, str(TOOLS_DIR / "gameplay_planner"))
if str(TOOLS_DIR / "runtime") not in sys.path:
    sys.path.insert(0, str(TOOLS_DIR / "runtime"))

from level_planner import validate_level                               # noqa: E402
from runtime_result import find_godot_binary                           # noqa: E402
from testsupport.run_workspace import OwnershipError, RunWorkspace     # noqa: E402

_failures: list[str] = []
_workspaces: list[RunWorkspace] = []          # Phase 1.35：fixtures(user://) + probe(仓库内)

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")


def ok(name: str, condition: bool, detail: str = "") -> None:
    if condition:
        print("PASS: " + name)
    else:
        _failures.append(name + (" | " + detail if detail else ""))


def skip(name: str, reason: str) -> None:
    print("SKIP: %s (%s)" % (name, reason))


# ---------- 共享正反例（唯一来源；C1–C8 全部从这里取输入） ----------

def _base_waves(version: int = 2, with_mode: bool = True) -> dict:
    config = {
        "schema": {"id": "level_orchestration", "version": version},
        "level": {"id": "contract_level", "arena_scene": "res://Scenes/TimedCombatArena.tscn"},
        "mode": "waves",
        "entities": {"enemy": {"scene": "res://Scenes/Enemy.tscn"},
                     "elite_enemy": {"scene": "res://Scenes/EliteEnemy.tscn"}},
        "waves": [{"id": "wave_1", "duration": 30.0,
                   "entries": [{"entity": "enemy", "count": 2}]}],
        "exit": {"unlock_when": "all_waves_cleared"},
        "victory": {"condition": "exit_reached_after_unlock"},
    }
    if not with_mode:
        config.pop("mode")
    return config


def _base_holdout(version: int = 2, with_mode: bool = True) -> dict:
    config = {
        "schema": {"id": "level_orchestration", "version": version},
        "level": {"id": "contract_holdout", "arena_scene": "res://Scenes/SurvivalArena.tscn"},
        "entities": {"enemy": {"scene": "res://Scenes/Enemy.tscn"},
                     "elite_enemy": {"scene": "res://Scenes/EliteEnemy.tscn"}},
        "holdout": {"survival_duration": 30.0, "max_alive": 12,
                    "spawns": [{"entity": "enemy", "interval": 1.2},
                               {"entity": "elite_enemy", "delay": 10.0,
                                "interval": 8.0, "max_alive": 2}]},
        "victory": {"condition": "survive_duration"},
    }
    if with_mode:
        config["mode"] = "holdout"
    return config


def _base_boss(version: int = 2) -> dict:
    config = {
        "schema": {"id": "level_orchestration", "version": version},
        "level": {"id": "contract_boss",
                  "arena_scene": "res://Scenes/BossChallenge.tscn"},
        "mode": "boss",
        "entities": {"boss": {"scene": "res://Scenes/Boss.tscn"}},
        "boss": {"entity": "boss", "instance": "Entities/Boss", "spawn": "existing"},
        "exit": {"unlock_when": "boss_defeated"},
        "victory": {"condition": "exit_reached_after_unlock"},
    }
    if version == 1:
        config.pop("mode")
    return config


def _base_stage_boss(complete: bool = False) -> dict:
    config = _base_boss()
    config["entities"]["grunt"] = {"scene": "res://Scenes/Enemy.tscn"}
    config["stages"] = [
        {"id": "clear_1", "type": "clear_enemies",
         "entries": [{"entity": "grunt", "count": 2}]},
        {"id": "boss", "type": "defeat_boss", "entity": "boss"},
    ]
    config["exit"] = {"unlock_when": "never"}
    config["victory"] = {"condition": "boss_defeated"}
    if complete:
        config["stages"].append({"id": "complete", "type": "complete_level"})
    return config


def _mutated(base: dict, mutate) -> dict:
    import copy
    clone = copy.deepcopy(base)
    mutate(clone)
    return clone


# (name, config, expect_valid, expect_field, check_defaults)
FIXTURES = [
    ("waves_v2_valid", _base_waves(), True, "", False),                     # C1
    ("holdout_v2_valid", _base_holdout(), True, "", False),                 # C2
    ("mode_unsupported", _mutated(_base_waves(),
        lambda c: c.update({"mode": "party_mode"})), False, "mode", False),  # C3
    ("waves_unknown_entity", _mutated(_base_waves(),
        lambda c: c["waves"][0]["entries"][0].update({"entity": "ghost"}),
        ), False, "waves[0].entries[0].entity", False),                      # C4
    ("holdout_unknown_entity", _mutated(_base_holdout(),
        lambda c: c["holdout"]["spawns"][0].update({"entity": "ghost"}),
        ), False, "holdout.spawns[0].entity", False),                        # C4
    ("waves_bad_count", _mutated(_base_waves(),
        lambda c: c["waves"][0]["entries"][0].update({"count": 0}),
        ), False, "waves[0].entries[0].count", False),                       # C5
    ("waves_bad_structure", _mutated(_base_waves(),
        lambda c: c["waves"][0].pop("entries")), False, "waves[0].entries", False),  # C5
    ("v1_legacy_waves", _base_waves(version=1, with_mode=False), True, "", False),   # C6
    ("v1_holdout_rejected", _mutated(_base_holdout(version=1, with_mode=False),
        lambda c: c.update({"mode": "holdout"})), False, "mode", False),     # C6
    ("holdout_missing_duration", _mutated(_base_holdout(),
        lambda c: c["holdout"].pop("survival_duration")),
        False, "holdout.survival_duration", False),                          # C8
    ("holdout_count_rejected", _mutated(_base_holdout(),
        lambda c: c["holdout"]["spawns"][0].update({"count": 3})),
        False, "holdout.spawns[0].count", False),                            # C8
    ("holdout_exit_rejected", _mutated(_base_holdout(),
        lambda c: c.update({"exit": {"unlock_when": "all_waves_cleared"}})),
        False, "exit", False),                                               # C8
    ("waves_survive_victory_rejected", _mutated(_base_waves(),
        lambda c: c.update({"victory": {"condition": "survive_duration"}})),
        False, "victory.condition", False),                                  # C3/C8
    ("no_optional_blocks", _mutated(_base_waves(),
        lambda c: (c.pop("exit"), c.pop("victory"))), True, "", True),       # C7
    ("unreachable_victory", _mutated(_base_waves(),
        lambda c: c["exit"].update({"unlock_when": "never"})),
        False, "victory.condition", False),                                  # C8
    ("boss_v2_valid", _base_boss(), True, "", False),                       # C10
    ("boss_unknown_entity", _mutated(_base_boss(),
        lambda c: c["boss"].update({"entity": "ghost"})),
        False, "boss.entity", False),                                        # C10
    ("boss_missing_instance", _mutated(_base_boss(),
        lambda c: c["boss"].pop("instance")),
        False, "boss.instance", False),                                      # C10
    ("boss_bad_spawn", _mutated(_base_boss(),
        lambda c: c["boss"].update({"spawn": "whenever"})),
        False, "boss.spawn", False),                                         # C10
    ("boss_waves_rejected", _mutated(_base_boss(),
        lambda c: c.update({"waves": [{"id": "wave_1", "duration": 10.0,
                                        "entries": [{"entity": "boss", "count": 1}]}]})),
        False, "waves", False),                                              # C10
    ("boss_exit_victory_unreachable", _mutated(_base_boss(),
        lambda c: c["exit"].update({"unlock_when": "never"})),
        False, "victory.condition", False),                                  # C10
    ("v1_boss_rejected", _base_boss(version=1), False, "mode", False),      # C10
    ("stage_boss_valid", _base_stage_boss(), True, "", False),              # C11
    ("stage_complete_valid", _base_stage_boss(complete=True), True, "", False),  # C11
    ("stage_empty", _mutated(_base_stage_boss(),
        lambda c: c.update({"stages": []})), False, "stages", False),        # C11
    ("stage_duplicate_id", _mutated(_base_stage_boss(),
        lambda c: c["stages"][1].update({"id": "clear_1"})),
        False, "stages[1].id", False),                                       # C11
    ("stage_unknown_type", _mutated(_base_stage_boss(),
        lambda c: c["stages"][1].update({"type": "teleport"})),
        False, "stages[1].type", False),                                     # C11
    ("stage_missing_boss_entity", _mutated(_base_stage_boss(),
        lambda c: c["stages"][1].pop("entity")),
        False, "stages[1].entity", False),                                   # C11
    ("stage_clear_boss_entity", _mutated(_base_stage_boss(),
        lambda c: c["stages"][0]["entries"][0].update({"entity": "boss"})),
        False, "stages[0].entries[0].entity", False),                        # C11
    ("stage_boss_not_last", _mutated(_base_stage_boss(),
        lambda c: c["stages"].append({"id": "clear_2", "type": "clear_enemies",
                                      "entries": [{"entity": "grunt", "count": 1}]})),
        False, "stages[1]", False),                                          # C11
    ("stage_complete_with_exit", _mutated(_base_stage_boss(complete=True),
        lambda c: c["exit"].update({"unlock_when": "boss_defeated"})),
        False, "exit.unlock_when", False),                                   # C11
    ("waves_with_stages", _mutated(_base_waves(),
        lambda c: c.update({"stages": _base_stage_boss()["stages"]})),
        False, "stages", False),                                             # C11
    ("holdout_with_stages", _mutated(_base_holdout(),
        lambda c: c.update({"stages": _base_stage_boss()["stages"]})),
        False, "stages", False),                                             # C11
]

PROBE_TEMPLATE = '''extends SceneTree
## 由 .ai/tools/validator/tests/test_cross_layer_contract.py 生成——跨层契约探针。
## 不要手工编辑；用后即删（生成方 finally 清理）。
## Phase 1.35：夹具合并为单一 bundle 文件（一个 JSON 承载全部夹具配置），
## 探针经 LevelConfig.from_dictionary 内存构建——33 个夹具文件不再各自落盘。

const BUNDLE := "%s"
const DEFAULT_CHECKS := [%s]

func _initialize() -> void:
	var text := FileAccess.get_file_as_string(BUNDLE)
	var parsed: Variant = JSON.parse_string(text)
	if not (parsed is Dictionary) or not (parsed.get("fixtures") is Array):
		printerr("BUNDLE: cannot read %%s" %% BUNDLE)
		quit(1)
		return
	for item in parsed["fixtures"]:
		var name: String = item["name"]
		var config := LevelConfig.from_dictionary(item["config"], "bundle:%%s" %% name)
		var first_error := "-"
		if not config.errors.is_empty():
			first_error = config.errors[0]
		print("CONTRACT: %%s accepted=%%d error=%%s" %% [name, 1 if config.is_valid() else 0, first_error])
		if name in DEFAULT_CHECKS:
			var orchestrator := LevelOrchestrator.new()
			if orchestrator.apply_config(config):
				print("DEFAULTS: %%s exit=%%s victory=%%s mode=%%s"
					%% [name, orchestrator.get_exit_unlock_when(),
					orchestrator.get_victory_condition(), orchestrator.get_mode()])
			else:
				print("DEFAULTS: %%s apply_failed=%%s" %% [name, str(orchestrator.get_config_errors())])
			orchestrator.free()
	quit(0)
'''


def _godot_field(error: str) -> str:
    """Godot 错误格式 `<配置文件>: <字段>: <说明>` -> 字段路径。"""
    parts = error.split(": ")
    return parts[1].strip() if len(parts) >= 3 else ""


def _python_verdict(config: dict) -> tuple[bool, str, str]:
    report = validate_level(config, PROJECT_ROOT)
    failures = report.get("failures") or []
    if failures:
        first = str(failures[0])
        return False, first, first.split(":")[0].strip()
    return True, "", ""


def run() -> int:
    global _workspace
    godot = find_godot_binary(PROJECT_ROOT)
    if godot is None:
        skip("C1-C8: cross-layer Godot probe", "godot executable not found; "
             "Python-side verdicts are still exercised below")
    # Phase 1.32（F4）：所有夹具与探针放进本次运行专属目录，并逐个登记所有权。
    # Phase 1.35：夹具迁入 Godot user://（.test_runs/runs/<token>/，C: 盘）——
    # 33 个夹具的自清理删除不再占用工作区删除预算（环境守卫限制 L-11 的根因缓解）；
    # probe.gd 必须是 res://（godot -s 只接受 res:// 脚本），保留在仓库内的
    # 独立迷你工作区（2 个文件的删除属于预算内）。
    workspace = RunWorkspace.create(base_dir=RunWorkspace.godot_user_runs_base(PROJECT_ROOT))
    probe_workspace = RunWorkspace.create()
    _workspaces.extend((workspace, probe_workspace))
    for stale in workspace.stale_entries():
        print("STALE (not removed): token=%s state=%s files=%d last=%s"
              % (stale["token"], stale["state"], stale["file_count"], stale["last_event"]))
    defaults_names: list[str] = []
    expected: dict[str, dict] = {}
    bundle_items: list[dict] = []
    for name, config, expect_valid, expect_field, check_defaults in FIXTURES:
        if check_defaults:
            defaults_names.append(name)
        accepted, first_failure, field = _python_verdict(config)
        expected[name] = {"accept": accepted, "field": field,
                          "python_first": first_failure,
                          "expect_field": expect_field,
                          "name": name}
        bundle_items.append({"name": name, "config": config})

    # Phase 1.35：33 个夹具合并为单一 bundle 文件（探针经
    # LevelConfig.from_dictionary 内存构建）——本测试的落盘删除从 35 降到 3。
    bundle = workspace.path_for("fixtures/bundle.json")
    _write(bundle, {"fixtures": bundle_items})
    workspace.record(bundle)

    probe_path = probe_workspace.path_for("probe.gd")
    probe_path.write_text(PROBE_TEMPLATE % (
        workspace.user_res("fixtures/bundle.json"),
        ", ".join('"%s"' % n for n in defaults_names)), encoding="utf-8")
    probe_workspace.record(probe_path)
    godot_lines: list[str] = []
    probe_ran = False
    try:
        if godot is not None:
            proc = subprocess.run(
                [str(godot), "--headless", "--path", str(PROJECT_ROOT), "-s",
                 probe_workspace.res_path("probe.gd")],
                capture_output=True, text=True, encoding="utf-8", errors="replace",
                cwd=str(PROJECT_ROOT), stdin=subprocess.DEVNULL, timeout=180)
            godot_lines = [line for line in ((proc.stdout or "") + (proc.stderr or "")).splitlines()
                           if line.startswith("CONTRACT: ") or line.startswith("DEFAULTS: ")]
            probe_ran = bool(godot_lines)
            if not probe_ran:
                _failures.append("C-probe: Godot probe produced no CONTRACT lines (exit %s): %s"
                                 % (proc.returncode, ((proc.stdout or "") + (proc.stderr or ""))[-400:]))
        else:
            # Godot 缺失：仍完成 Python 侧判定（不伪装两层一致，也不算失败）
            pass
    finally:
        # Godot 可能在脚本旁生成 .uid（派生文件）；只登记、随后按所有权清理。
        try:
            probe_workspace.record_if_exists(probe_workspace.path_for("probe.gd.uid"))
        except OwnershipError as exc:
            _failures.append("cleanup: cannot account for probe.gd.uid (%s)" % exc)

    godot_by_name: dict[str, dict] = {}
    for line in godot_lines:
        match = re.match(r"^(CONTRACT|DEFAULTS): (\S+) (.+)$", line)
        if not match:
            continue
        kind, name, rest = match.groups()
        godot_by_name.setdefault(name, {})[kind] = rest

    # ---- 逐例比较两层判定（C1–C8）----
    for name, exp in expected.items():
        label = exp["name"]
        accepted, first_failure, field = _python_verdict(
            next(c for n, c, *_ in FIXTURES if n == name))
        godot = godot_by_name.get(name, {})
        if not probe_ran:
            continue
        contract_line = godot.get("CONTRACT", "")
        match = re.match(r"accepted=(\d) error=(.*)$", contract_line)
        if not match:
            _failures.append("%s: Godot CONTRACT line unparseable: %r" % (label, contract_line))
            continue
        godot_accepted = match.group(1) == "1"
        godot_error = match.group(2)
        verdict = "accepted" if accepted else "rejected"
        ok("%s [%s]: Python and Godot agree (%s)" % (label, verdict.upper(),
            "C1/C2 waves" if exp["name"].startswith("waves_v2") else
            "C2 holdout" if exp["name"].startswith("holdout_v2") else "cross-layer"),
           godot_accepted == accepted,
           "python=%s godot=%s (godot_error=%r)" % (accepted, godot_accepted, godot_error))
        if not accepted:
            python_field_ok = (not exp["expect_field"]) or (exp["expect_field"] in field)
            godot_field_ok = (not exp["expect_field"]) or (exp["expect_field"] in _godot_field(godot_error))
            ok("%s [C4/C5/C6/C8]: both layers point at the same JSON field %r"
               % (label, exp["expect_field"]),
               python_field_ok and godot_field_ok,
               "python_field=%r godot_field=%r" % (field, _godot_field(godot_error)))

    # ---- C7：缺省块默认行为一致 ----
    if probe_ran:
        defaults_name = next((n for n in defaults_names if n in godot_by_name
                              and "DEFAULTS" in godot_by_name[n]), None)
        if defaults_name:
            rest = godot_by_name[defaults_name]["DEFAULTS"]
            match = re.match(r"exit=(\S+) victory=(\S+) mode=(\S+)$", rest)
            ok("C7: Godot orchestrator defaults are parseable",
               bool(match), repr(rest))
            if match:
                from level_planner import (EXIT_ALL_WAVES_CLEARED, MODE_WAVES,
                                           VICTORY_EXIT_REACHED)
                ok("C7: missing optional blocks default identically in both layers",
                   match.group(1) == EXIT_ALL_WAVES_CLEARED
                   and match.group(2) == VICTORY_EXIT_REACHED
                   and match.group(3) == MODE_WAVES,
                   "godot=(%s, %s, %s) python=(%s, %s, %s)"
                   % (match.group(1), match.group(2), match.group(3),
                      EXIT_ALL_WAVES_CLEARED, VICTORY_EXIT_REACHED, MODE_WAVES))
        else:
            _failures.append("C7: no DEFAULTS line for the no-optional-blocks fixture")

    # ---- C9：作用域边界一致（Godot 编排层不消费资源绑定）----
    for source in ("level_orchestrator.gd", "level_config.gd"):
        text = (PROJECT_ROOT / "Orchestration" / source).read_text(encoding="utf-8")
        code_only = "\n".join(line.split("#")[0] for line in text.split("\n"))
        ok("C9: %s does not consume asset bindings (authority = bind_assets.py)"
           % source,
           "binding" not in code_only.lower(),
           "found 'binding' in code of %s" % source)

    # ---- 所有权清理（删前重新验证），再断言无残留 ----
    report = workspace.cleanup()
    ok("cleanup: run workspace removed (ownership verified)",
       report.run_root_removed and not workspace.run_root.exists(),
       repr(report.failures()))
    ok("cleanup: no unaccounted / conflicting test artifacts",
       not report.failures(), repr(report.failures()))
    probe_report = probe_workspace.cleanup()
    ok("cleanup: probe workspace removed (ownership verified)",
       probe_report.run_root_removed and not probe_workspace.run_root.exists(),
       repr(probe_report.failures()))

    print()
    if _failures:
        print("FAIL: %d failing check(s)" % len(_failures))
        for failure in _failures:
            print("  - " + failure)
        return 1
    print("PASS: cross-layer contract consistency verified (C1-C11)")
    return 0


def _write(path: Path, data: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")


def cleanup() -> None:
    """异常路径的兜底清理：只清本运行的所有权账本，绝不按前缀/glob 删除。"""
    global _workspaces
    pending, _workspaces = _workspaces, []
    for workspace in pending:
        report = workspace.cleanup()
        for failure in report.failures():
            print("CLEANUP: " + failure)


if __name__ == "__main__":
    try:
        code = run()
    finally:
        cleanup()
    sys.exit(code)
