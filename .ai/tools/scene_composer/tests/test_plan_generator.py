#!/usr/bin/env python3
"""Composition Plan Generator 回归测试（Phase 1.19）。

覆盖（对应任务书 七、测试要求）：
    Q1  两个实体均有场景映射 → 生成合法计划（entity 身份保留，实例名 Pascal，YAML 可解析）
    Q2  多实体不同场景 → 实例名稳定且唯一（同输入两次生成字节一致）
    Q3  缺少某实体的场景映射 → 明确错误（entity id + 预期路径），无产物
    Q4  声明的场景路径不存在 / override 指向不存在的路径 → 拒绝生成，无产物
    Q5  蓝图派生关系（entity_graph.json + --relation）→ 目标引用来自关系图而非猜测
    Q6  目标实体不存在 / 关系名未知 / source 无 target_path 能力 → 明确诊断
    Q7  蓝图未声明目标关系 → 不生成 targets（组合宿主中也没有 target_path）
    Q8  实例名歧义（两个 entity 派生同名）→ 拒绝，不任选其一；未知实体 override 也拒绝
    Q9  生成的计划通过既有组合器校验，并能被正式 CLI `scene_composer --compose-plan` 消费
    Q10 原有手工 composition plan 仍可执行（兼容路径）
    Q11 失败时不存在误导性的最终产物
    Q12 单实体 Scene Intent 生成流程不受影响（--dry-run 通过；--help 两个入口都在）

用法:
    python .ai/tools/scene_composer/tests/test_plan_generator.py
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
PROJECT_ROOT = COMPOSER_DIR.parent.parent.parent      # .ai/tools/scene_composer/tests -> game/

if str(COMPOSER_DIR) not in sys.path:
    sys.path.insert(0, str(COMPOSER_DIR))
import composite                                       # noqa: E402
import plan_generator                                  # noqa: E402

PLAN_CLI = COMPOSER_DIR / "plan_generator.py"
COMPOSER_CLI = COMPOSER_DIR / "scene_composer.py"

ENEMY_SCENE = "res://Scenes/SlimeEnemy.tscn"
PLAYER_SCENE = "res://Features/player_movement/Player.tscn"

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


def _run_cli(script: Path, *argv) -> subprocess.CompletedProcess:
    return subprocess.run([sys.executable, str(script), *[str(a) for a in argv]],
                          capture_output=True, text=True, encoding="utf-8",
                          errors="replace", cwd=str(PROJECT_ROOT),
                          stdin=subprocess.DEVNULL, timeout=180)


def _blueprint(**entities) -> dict:
    return {
        "gameplay": {"id": "plan_test_game"},
        "entities": {key: value for key, value in entities.items()},
        "systems": ["enemy_spawn"],
        "loop": {"start": "player spawned", "cycle": "enemy chases",
                 "end": "enemy defeated"},
    }


def _enemy(entity_id: str = "slime_test", **extra) -> dict:
    entry = {"role": "enemy", "features": ["chase_movement", "contact_damage", "health"],
             "scene": ENEMY_SCENE}
    entry.update(extra)
    return entry


def _player(entity_id: str = "player_test", **extra) -> dict:
    entry = {"role": "player", "features": ["health", "player_movement"],
             "scene": PLAYER_SCENE}
    entry.update(extra)
    return entry


def _write_blueprint(work: Path, name: str, blueprint: dict) -> Path:
    path = work / name
    path.write_text(yaml.safe_dump(blueprint, sort_keys=False, allow_unicode=True),
                    encoding="utf-8")
    return path


def main() -> int:
    work = Path(tempfile.mkdtemp(prefix="plan_generator_tests_"))
    try:
        bp = _write_blueprint(work, "bp.yaml",
                             _blueprint(slime_test=_enemy(), player_test=_player()))

        # ---- Q1: 正向 ----
        out = work / "plan.yaml"
        r = _run_cli(PLAN_CLI, bp, "--host", "PlanHost", "--out", out)
        plan = yaml.safe_load(out.read_text(encoding="utf-8")) if out.is_file() else {}
        ok("Q1: a blueprint with two mapped entities generates a valid plan",
           r.returncode == 0 and out.is_file()
           and "Validation: PASS" in r.stdout, (r.stdout + r.stderr)[-400:])
        ok("Q1: the plan keeps the blueprint entity identity and PascalCase instance names",
           plan.get("document") == "composition_plan"
           and plan.get("schema_version") == 1
           and (plan.get("host") or {}).get("name") == "PlanHost"
           and [(i.get("entity"), i.get("instance_name")) for i in plan.get("instances") or []]
           == [("slime_test", "SlimeTest"), ("player_test", "PlayerTest")]
           and [i.get("scene") for i in plan.get("instances") or []]
           == [ENEMY_SCENE, PLAYER_SCENE],
           repr(plan))
        ok("Q1: an unrequested plan carries no target relations", "targets" not in plan,
           repr(plan.get("targets")))

        # ---- Q2: 稳定性 ----
        out2 = work / "plan2.yaml"
        r2 = _run_cli(PLAN_CLI, bp, "--host", "PlanHost", "--out", out2)
        ok("Q2: the same blueprint produces byte-identical plans (stable ordering)",
           r2.returncode == 0 and out2.is_file()
           and out.read_bytes() == out2.read_bytes(),
           "%s vs %s" % (out.stat().st_size if out.is_file() else -1,
                         out2.stat().st_size if out2.is_file() else -1))
        names = [i.get("instance_name") for i in plan.get("instances") or []]
        ok("Q2: instance names are unique within the plan", len(names) == len(set(names)) == 2,
           repr(names))

        # ---- Q3: 缺少场景映射 ----
        no_scene_bp = _write_blueprint(work, "bp_no_scene.yaml", _blueprint(
            ghost_enemy={"role": "enemy", "features": ["chase_movement", "health"]},
            player_test=_player()))
        ghost_out = work / "ghost_plan.yaml"
        r = _run_cli(PLAN_CLI, no_scene_bp, "--host", "GhostHost", "--out", ghost_out)
        ok("Q3: a missing scene mapping is refused with a locatable diagnostic",
           r.returncode == 1 and "ghost_enemy" in r.stdout
           and "res://Scenes/GhostEnemy.tscn" in r.stdout,
           (r.stdout + r.stderr)[-400:])
        ok("Q3: the failed generation leaves no plan artifact", not ghost_out.exists(),
           str(ghost_out))

        # ---- Q4: 场景路径不存在 ----
        missing_scene = "res://Scenes/No_Such_PlanTest.tscn"
        declared_bp = _write_blueprint(work, "bp_missing_scene.yaml", _blueprint(
            slime_test=_enemy(scene=missing_scene), player_test=_player()))
        declared_out = work / "declared_plan.yaml"
        r = _run_cli(PLAN_CLI, declared_bp, "--host", "MissingHost", "--out", declared_out)
        ok("Q4: a declared scene that does not exist is refused (no silent fallback)",
           r.returncode == 1 and "declared scene not found" in r.stdout
           and not declared_out.exists(), (r.stdout + r.stderr)[-400:])
        override_out = work / "override_plan.yaml"
        r = _run_cli(PLAN_CLI, bp, "--host", "MissingHost",
                     "--entity-scene", "slime_test=%s" % missing_scene, "--out", override_out)
        ok("Q4: an explicit override pointing at a missing scene is refused",
           r.returncode == 1 and "override scene not found" in r.stdout
           and not override_out.exists(), (r.stdout + r.stderr)[-400:])

        # ---- Q5: 蓝图派生关系 -> targets ----
        graph = {"nodes": ["SlimeTest", "PlayerTest"],
                 "edges": [{"from": "SlimeTest", "to": "PlayerTest",
                            "relation": "attack"},
                           {"from": "PlayerTest", "to": "SlimeTest",
                            "relation": "collect"}]}
        graph_path = work / "graph.json"
        graph_path.write_text(yaml.safe_dump(graph, sort_keys=False), encoding="utf-8")
        relation_out = work / "relation_plan.yaml"
        r = _run_cli(PLAN_CLI, bp, "--host", "RelationHost", "--relations", graph_path,
                     "--relation", "attack", "--out", relation_out)
        relation_plan = (yaml.safe_load(relation_out.read_text(encoding="utf-8"))
                         if relation_out.is_file() else {})
        ok("Q5: the blueprint-derived relation becomes an instance-level target reference",
           r.returncode == 0
           and relation_plan.get("targets")
           == [{"source": "SlimeTest", "target": "PlayerTest"}],
           repr(relation_plan.get("targets")))
        ok("Q5: only the explicitly named relation is consumed (collect is not applied)",
           "collect" not in yaml.safe_dump(relation_plan, sort_keys=False)
           and len(relation_plan.get("targets") or []) == 1,
           repr(relation_plan.get("targets")))

        # ---- Q6: 目标诊断 ----
        unknown_target_out = work / "unknown_target_plan.yaml"
        r = _run_cli(PLAN_CLI, bp, "--host", "UnknownHost",
                     "--target", "slime_test:nobody", "--out", unknown_target_out)
        ok("Q6: an unknown target entity is diagnosed with the available entity list",
           r.returncode == 1 and "targets[0].target" in r.stdout
           and "nobody" in r.stdout and "slime_test" in r.stdout
           and not unknown_target_out.exists(), (r.stdout + r.stderr)[-400:])
        r = _run_cli(PLAN_CLI, bp, "--host", "RelationHost", "--relations", graph_path,
                     "--relation", "chase", "--out", work / "bad_relation.yaml")
        ok("Q6: an unknown relation name is refused (never applied implicitly)",
           r.returncode == 1 and "unknown relation" in r.stdout
           and "attack" in r.stdout, (r.stdout + r.stderr)[-400:])
        no_cap_bp = _write_blueprint(work, "bp_no_capability.yaml", _blueprint(
            slime_test=_enemy(), barrel_test={"role": "world_item",
                                              "features": ["health"],
                                              "scene": ENEMY_SCENE}))
        r = _run_cli(PLAN_CLI, no_cap_bp, "--host", "NoCapHost",
                     "--target", "barrel_test:slime_test", "--out", work / "no_cap.yaml")
        ok("Q6: a source entity without a target_path-capable feature is refused",
           r.returncode == 1 and "cannot consume a runtime target" in r.stdout
           and "target_path" in r.stdout and not (work / "no_cap.yaml").exists(),
           (r.stdout + r.stderr)[-400:])
        r = _run_cli(PLAN_CLI, bp, "--host", "NoGraphHost",
                     "--relations", graph_path, "--out", work / "no_relation_name.yaml")
        ok("Q6: --relations without an explicit --relation is refused",
           r.returncode == 1 and "at least one --relation" in r.stdout
           and not (work / "no_relation_name.yaml").exists(),
           (r.stdout + r.stderr)[-400:])

        # ---- Q7: 无关系声明 -> 无 targets，且组合宿主里没有 target_path ----
        plain_plan = yaml.safe_load(out.read_text(encoding="utf-8"))
        compose_dir = work / "compose_plain"
        result = composite.compose_from_plan(plain_plan, out_dir=compose_dir)
        host_text = ((compose_dir / "PlanHost.tscn").read_text(encoding="utf-8")
                     if (compose_dir / "PlanHost.tscn").is_file() else "")
        ok("Q7: a plan without declared relations composes into a host without target_path",
           result["ok"] and host_text
           and "target_path" not in host_text, host_text[:300])

        # ---- Q8: 歧义 ----
        ambiguous_bp = _write_blueprint(work, "bp_ambiguous.yaml", _blueprint(
            enemy_basic=_enemy(scene=ENEMY_SCENE),
            enemyBasic=_player(scene=PLAYER_SCENE)))
        ambiguous_out = work / "ambiguous_plan.yaml"
        r = _run_cli(PLAN_CLI, ambiguous_bp, "--host", "AmbiguousHost", "--out", ambiguous_out)
        ok("Q8: two entities deriving the same instance name are refused (no arbitrary pick)",
           r.returncode == 1 and "collides" in r.stdout
           and "EnemyBasic" in r.stdout and not ambiguous_out.exists(),
           (r.stdout + r.stderr)[-400:])
        r = _run_cli(PLAN_CLI, bp, "--host", "UnknownEntityHost",
                     "--entity-scene", "ghost_entity=res://Scenes/SlimeEnemy.tscn",
                     "--out", work / "unknown_entity.yaml")
        ok("Q8: an override for an entity absent from the blueprint is refused",
           r.returncode == 1 and "ghost_entity" in r.stdout
           and not (work / "unknown_entity.yaml").exists(),
           (r.stdout + r.stderr)[-400:])

        # ---- Q9: 既有组合器校验 + 正式 CLI ----
        r = _run_cli(COMPOSER_CLI, "--compose-plan", relation_out,
                     "--out", work / "formal", "--dry-run")
        ok("Q9: the generated plan passes the formal dry-run entry (no artifact)",
           r.returncode == 0 and "Validation: PASS" in r.stdout
           and not list((work / "formal").glob("*.tscn")),
           (r.stdout + r.stderr)[-400:])
        r = _run_cli(COMPOSER_CLI, "--compose-plan", relation_out,
                     "--out", work / "formal")
        host = work / "formal" / "RelationHost.tscn"
        host_text = host.read_text(encoding="utf-8") if host.is_file() else ""
        ok("Q9: the formal entry composes the host from the generated plan with the target",
           r.returncode == 0 and host.is_file()
           and 'target_path = NodePath("../PlayerTest")' in host_text
           and host_text.count("instance=ExtResource") == 2,
           (r.stdout + r.stderr)[-400:])

        # ---- Q10: 手工 plan 兼容 ----
        manual_plan = work / "manual_plan.yaml"
        manual_plan.write_text(yaml.safe_dump({
            "document": "composition_plan", "schema_version": 1,
            "host": {"name": "ManualHost"},
            "instances": [{"entity": "enemy", "scene": ENEMY_SCENE,
                           "instance_name": "ManualEnemy"},
                          {"entity": "player", "scene": PLAYER_SCENE,
                           "instance_name": "ManualPlayer"}],
            "targets": [{"source": "ManualEnemy", "target": "ManualPlayer"}],
        }, sort_keys=False), encoding="utf-8")
        r = _run_cli(COMPOSER_CLI, "--compose-plan", manual_plan,
                     "--out", work / "manual")
        ok("Q10: a hand-written composition plan still composes unchanged",
           r.returncode == 0 and (work / "manual" / "ManualHost.tscn").is_file(),
           (r.stdout + r.stderr)[-400:])

        # ---- Q11: 失败无产物（汇总）----
        stray = [p.name for p in work.glob("*.yaml")
                 if p.name in {"ghost_plan.yaml", "declared_plan.yaml", "override_plan.yaml",
                               "unknown_target_plan.yaml", "no_cap.yaml",
                               "no_relation_name.yaml", "ambiguous_plan.yaml",
                               "unknown_entity.yaml"}]
        ok("Q11: no misleading plan artifact survives any failed generation", not stray,
           repr(stray))

        # ---- Q12: 单实体 Scene Intent 流程不受影响 ----
        entity_bp = PROJECT_ROOT / "slime_enemy.yaml"
        r = _run_cli(COMPOSER_CLI, entity_bp, "--dry-run")
        ok("Q12: the single-entity Scene Intent flow still validates (dry-run)",
           r.returncode == 0 and "Dry run" in r.stdout, (r.stdout + r.stderr)[-300:])
        r = _run_cli(COMPOSER_CLI, "--help")
        ok("Q12: both pipeline entries remain available in the CLI",
           r.returncode == 0 and "--compose-plan" in r.stdout and "blueprint" in r.stdout,
           r.stdout[:200])
    finally:
        shutil.rmtree(work, ignore_errors=True)

    print()
    if _failures:
        print("FAIL: %d failing check(s)" % len(_failures))
        for failure in _failures:
            print("  - " + failure)
        return 1
    print("PASS: all %d plan generator checks passed" % _checks)
    return 0


if __name__ == "__main__":
    sys.exit(main())
