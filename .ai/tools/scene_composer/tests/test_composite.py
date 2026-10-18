#!/usr/bin/env python3
"""Composite Scene Builder 回归测试（Phase 1.17/1.18）。

覆盖：
    P1  合法 --scene 模式组合（原生 instancing，宿主不复制实体内容）
    P2  composition_plan 正向：实例映射 + 目标声明落盘（target_path 覆盖）
    P3  plan 结构校验：document/schema_version/host.name/instances 数量
    P4  负向：未知目标实例 / 实例名冲突 / 重复场景 / 缺失场景 → exit 1 且不写盘
    P5  输入争用契约：两个实例场景都引用 player_controller.gd → 拒绝
    P6  正式管线入口：scene_composer --compose-plan（dry-run 与正式落盘）
    P7  旧格式兼容：--scene/--name 模式行为不变（无 targets）

用法:
    python .ai/tools/scene_composer/tests/test_composite.py
全部通过输出 PASS 并退出 0；任一失败输出 FAIL 并退出 1。
"""

from __future__ import annotations

import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

import yaml

TEST_DIR = Path(__file__).resolve().parent
COMPOSER_DIR = TEST_DIR.parent
TOOLS_DIR = COMPOSER_DIR.parent
PROJECT_ROOT = TOOLS_DIR.parent.parent          # .ai/tools/scene_composer -> game/

if str(COMPOSER_DIR) not in sys.path:
    sys.path.insert(0, str(COMPOSER_DIR))
import composite                                            # noqa: E402

ENEMY_SCENE = "res://Scenes/SlimeEnemy.tscn"
PLAYER_SCENE = "res://Features/player_movement/Player.tscn"
COMPOSER_CLI = COMPOSER_DIR / "scene_composer.py"

_failures: list[str] = []
_checks = 0


def ok(name: str, condition, detail: str = "") -> None:
    global _checks
    _checks += 1
    if condition:
        print("PASS: %s" % name)
    else:
        message = "FAIL: %s" % name
        if detail:
            message += " | %s" % detail
        print(message)
        _failures.append(message)


def _plan(host: str = "PlanHost", instances=None, targets=None,
          document: str = "composition_plan", version: int = 1) -> dict:
    return {
        "document": document, "schema_version": version,
        "host": {"name": host},
        "instances": instances if instances is not None else [
            {"entity": "enemy", "scene": ENEMY_SCENE, "instance_name": "Enemy"},
            {"entity": "player", "scene": PLAYER_SCENE, "instance_name": "Player"},
        ],
        "targets": targets if targets is not None else [],
    }


def _run_cli(*args) -> subprocess.CompletedProcess:
    return subprocess.run([sys.executable, str(COMPOSER_CLI), *args],
                          capture_output=True, text=True, encoding="utf-8",
                          cwd=str(PROJECT_ROOT))


def main() -> int:
    work = Path(tempfile.mkdtemp(prefix="composite_tests_"))
    try:
        # ---- P1: --scene 模式（旧格式兼容）----
        result = composite.compose_entities(
            [ENEMY_SCENE, PLAYER_SCENE], "P1Host", out_dir=work)
        ok("P1: legacy --scene/--name mode still composes without targets",
           result["ok"] and len(result["instances"]) == 2
           and result["targets"] == []
           and "RectangleShape2D" not in (work / "P1Host.tscn").read_text(encoding="utf-8"),
           repr(result["failures"]))

        # ---- P2: plan 正向 + 目标声明 ----
        result = composite.compose_from_plan(
            _plan(targets=[{"source": "Enemy", "target": "Player"}]), out_dir=work)
        host_text = (work / "PlanHost.tscn").read_text(encoding="utf-8") \
            if (work / "PlanHost.tscn").is_file() else ""
        ok("P2: plan composition writes the declared target_path on the source instance",
           result["ok"] and len(result["targets"]) == 1
           and 'target_path = NodePath("../Player")' in host_text
           and '[node name="Enemy" parent="." instance=ExtResource("1_enemy")]'
           in host_text, repr((result["targets"], host_text[:200])))
        ok("P2: the host still does not splice entity content",
           "RectangleShape2D" not in host_text and "sprite_frames" not in host_text,
           host_text[:200])

        # ---- P3: plan 结构校验 ----
        for name, plan, fragment in [
            ("document", _plan(document="wrong_document"), "plan.document"),
            ("version", _plan(version=9), "plan.schema_version"),
            ("host", _plan(host="not a name!"), "host.name"),
            ("instances", _plan(instances=[{"scene": ENEMY_SCENE}]), "instances"),
        ]:
            result = composite.compose_from_plan(plan, out_dir=work / "never")
            ok("P3: invalid %s is refused with a locatable diagnostic" % name,
               not result["ok"] and any(fragment in f for f in result["failures"]),
               repr(result["failures"]))

        # ---- P4: 负向（不写盘）----
        out_dir = work / "neg"
        result = composite.compose_from_plan(
            _plan(targets=[{"source": "Enemy", "target": "Ghost"}]), out_dir=out_dir)
        ok("P4: an unknown target instance is refused (locatable, exit-mapped failure)",
           not result["ok"]
           and any("targets[0].target" in f and "Ghost" in f for f in result["failures"])
           and not (out_dir / "PlanHost.tscn").exists(), repr(result["failures"]))
        result = composite.compose_from_plan(
            _plan(instances=[{"scene": ENEMY_SCENE, "instance_name": "Same"},
                             {"scene": PLAYER_SCENE, "instance_name": "Same"}]),
            out_dir=out_dir)
        ok("P4: an instance name conflict is refused",
           not result["ok"]
           and any("instance name conflict" in f for f in result["failures"]),
           repr(result["failures"]))
        result = composite.compose_from_plan(
            _plan(instances=[{"scene": ENEMY_SCENE, "instance_name": "A"},
                             {"scene": ENEMY_SCENE, "instance_name": "B"}]),
            out_dir=out_dir)
        ok("P4: a duplicate entity scene is refused",
           not result["ok"] and any("duplicate entity scene" in f
                                    for f in result["failures"]),
           repr(result["failures"]))
        result = composite.compose_from_plan(
            _plan(instances=[{"scene": ENEMY_SCENE, "instance_name": "A"},
                             {"scene": "res://Scenes/No_Such_Scene.tscn"}]),
            out_dir=out_dir)
        ok("P4: a missing entity scene is refused",
           not result["ok"] and any("not found" in f for f in result["failures"]),
           repr(result["failures"]))

        # ---- P5: 输入争用契约 ----
        # 同路径重复场景已被 P4 以 duplicate 拒绝；真正的争用判定 = 两条**不同路径**
        # 但都引用 player_controller.gd 的实例（P5b 走真实判定逻辑）。
        player_text = (PROJECT_ROOT / PLAYER_SCENE[len("res://"):]).read_text(encoding="utf-8")
        temp_scene = PROJECT_ROOT / "Scenes" / "E2eCompositeTestPlayer.tscn"
        try:
            temp_scene.write_text(player_text, encoding="utf-8")
            failures_probe: list[str] = []
            composite._resolve_instances(
                [{"scene": PLAYER_SCENE, "instance_name": "P1"},
                 {"scene": "res://Scenes/E2eCompositeTestPlayer.tscn",
                  "instance_name": "P2"}],
                PROJECT_ROOT, failures_probe)
            ok("P5b: two player_controller instances are refused (input claim conflict)",
               any("input claim conflict" in f for f in failures_probe),
               repr(failures_probe))
        finally:
            temp_scene.unlink(missing_ok=True)
            temp_scene.with_suffix(".tscn.uid").unlink(missing_ok=True)

        # ---- P6: 正式管线入口 ----
        dry_dir = work / "dry"
        formal_dir = work / "formal"
        plan_path = work / "plan.yaml"
        plan_path.write_text(yaml.safe_dump(
            _plan(targets=[{"source": "Enemy", "target": "Player"}]),
            sort_keys=False, allow_unicode=True), encoding="utf-8")
        r = _run_cli("--compose-plan", str(plan_path), "--out", str(dry_dir), "--dry-run")
        ok("P6: the formal entry validates the plan in dry-run (no artifact)",
           r.returncode == 0 and "Validation: PASS" in r.stdout
           and "no scene written" in r.stdout
           and not list(dry_dir.glob("*.tscn")), (r.stdout + r.stderr)[-300:])
        r = _run_cli("--compose-plan", str(plan_path), "--out", str(formal_dir))
        ok("P6: the formal entry composes the host via the plan",
           r.returncode == 0 and "Artifact:" in r.stdout
           and (formal_dir / "PlanHost.tscn").is_file(), (r.stdout + r.stderr)[-300:])
        bad_plan = work / "plan_bad.yaml"
        bad_plan.write_text(yaml.safe_dump(
            _plan(targets=[{"source": "Enemy", "target": "Ghost"}]),
            sort_keys=False, allow_unicode=True), encoding="utf-8")
        r = _run_cli("--compose-plan", str(bad_plan), "--out", str(formal_dir))
        ok("P6: the formal entry fails with exit 1 and no artifact on an invalid plan",
           r.returncode == 1 and "FAILURES" in r.stdout
           and not (formal_dir / "PlanHostBad.tscn").exists()
           and len(list(formal_dir.glob("*.tscn"))) == 1,
           (r.stdout + r.stderr)[-300:])

        # ---- P7: 单实体生成流程不受影响（scene_composer 正常入口回归）----
        r = _run_cli("--help")
        ok("P7: the blueprint entry remains the default (help shows both)",
           r.returncode == 0 and "--compose-plan" in r.stdout
           and "blueprint" in r.stdout, r.stdout[:200])
    finally:
        shutil.rmtree(work, ignore_errors=True)

    print()
    if _failures:
        print("FAILED (%d):" % len(_failures))
        for failure in _failures:
            print("  - " + failure)
        return 1
    print("PASS: all %d checks" % _checks)
    return 0


if __name__ == "__main__":
    sys.exit(main())
