#!/usr/bin/env python3
"""Runtime Instance Evidence 测试（Phase 1.39）

真实 Godot 加载场景 → 观察加载后的对象树 → 核对 instance.runtime 契约。

    Case 1  仓库 6 个 Feature 的运行时契约 → 真实加载 PASS
    Case 2  场景资源引用无效（缺失脚本）→ MISMATCH（load_error，来自 stderr 真实报错）
    Case 3  目标节点缺失 → MISMATCH（missing）
    Case 4  节点类型不符 → MISMATCH（type_mismatch）
    Case 5  数量不符 → MISMATCH（count_mismatch）
    Case 6  动态节点在窗口内生成 → PASS（waited_frames > 0，未被提前判缺失）
    Case 7  动态节点窗口内未生成 → MISMATCH（missing_after_timeout，只声称窗口内未出现）
    Case 8  after_action 契约 → INSUFFICIENT（不自动触发游戏动作，且不启动 Godot）
    Case 9  非法运行时契约 → INVALID（when / count / expectations / path+parent）
    Case 10 采集失败（探针无结果）→ INSUFFICIENT，绝不 PASS
    Case 11 未声明 runtime → NOT_DECLARED（不凭空要求）
    Case 12 机器可读结果与 CLI 退出码（MISMATCH=1；INSUFFICIENT 仅在 --require-runtime 时为 1）
    Case 13 Phase 1.38 回归：静态对账 6 个 Feature 仍 PASS（菱形/挂载/解析受限由既有测试覆盖）
    Case 14 真实黄金 Feature（openable_door）副本上的负向对照：加载失败 / 移除要求实例 /
            动态创建条件失败，均需失败退出；每步恢复并校验 sha256，仓库文件不被改写

所有夹具位于临时 Godot 项目（`.ai/tmp/` 内，含 project.godot 与探针副本），
不触碰仓库 Features / 黄金基线；测试结束删除临时目录。

用法:
    python .ai/tools/scene_composer/tests/test_runtime_instance_evidence.py
全部通过输出 PASS 并退出 0；任一失败输出 FAIL 并退出 1。
"""

import hashlib
import json
import os
import shutil
import subprocess
import sys
import tempfile

import yaml

_HERE = os.path.dirname(os.path.abspath(__file__))
TOOL_DIR = os.path.dirname(_HERE)
TOOLS_DIR = os.path.dirname(TOOL_DIR)
DOTAI = os.path.dirname(TOOLS_DIR)
PROJECT_ROOT = os.path.dirname(DOTAI)

for path in (TOOL_DIR, TOOLS_DIR, _HERE):
    if path not in sys.path:
        sys.path.insert(0, path)

import instance_evidence                                      # noqa: E402
import runtime_instance_evidence as runtime_evidence          # noqa: E402

_failures = []


def ok(name: str, condition: bool, detail: str = "") -> None:
    if condition:
        print("PASS: " + name)
    else:
        _failures.append(name + (" | " + detail if detail else ""))
        print("FAIL: " + name + (" | " + detail if detail else ""))


def write_text(path: str, text: str) -> str:
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf-8", newline="\n") as handle:
        handle.write(text)
    return path


def scene(root_type: str, children: str = "", script: str = "") -> str:
    ext = ("[ext_resource type=\"Script\" path=\"%s\" id=\"1_script\"]\n\n" % script
           if script else "")
    script_line = "script = ExtResource(\"1_script\")\n\n" if script else ""
    return ("[gd_scene load_steps=2 format=3]\n\n" + ext +
            "[node name=\"Root\" type=\"%s\"]\n\n" % root_type + script_line + children)


def child(name: str, node_type: str, parent: str = ".") -> str:
    return "[node name=\"%s\" type=\"%s\" parent=\"%s\"]\n\n" % (name, node_type, parent)


def feature(project: str, feature_id: str, declaration: dict, scene_text: str,
            source: str = "Scene.tscn", extra_files=None) -> str:
    """在临时 Godot 项目里构造 Feature（template.yaml + 场景 + 可选脚本）。"""
    directory = os.path.join(project, "Features", feature_id)
    write_text(os.path.join(directory, source), scene_text)
    for name, text in (extra_files or {}).items():
        write_text(os.path.join(directory, name), text)
    template = ("feature:\n  id: %s\nscene:\n  source: %s\nvalidation:\n"
                "  required_nodes:\n    - Root\n" % (feature_id, source))
    template += "instance:\n" + "".join(
        "  %s\n" % line for line in yaml.safe_dump(declaration, sort_keys=False).splitlines())
    write_text(os.path.join(directory, "template.yaml"), template)
    return os.path.join(project, "Features")


def codes(report) -> set:
    return {check.get("status") for check in report.checks}


def sha256(path: str) -> str:
    digest = hashlib.sha256()
    with open(path, "rb") as handle:
        for chunk in iter(lambda: handle.read(65536), b""):
            digest.update(chunk)
    return digest.hexdigest()


def runtime_template(feature_id: str, source: str, declaration: dict) -> str:
    text = ("feature:\n  id: %s\nscene:\n  source: %s\nvalidation:\n"
            "  required_nodes:\n    - %s\n" % (feature_id, source, feature_id))
    text += "instance:\n" + "".join(
        "  %s\n" % line for line in yaml.safe_dump(declaration, sort_keys=False).splitlines())
    return text


def run_case(project: str, feature_id: str, godot: str):
    return runtime_evidence.verify_feature(feature_id, os.path.join(project, "Features"),
                                           project_root=project, godot=godot, timeout_s=60)


def run() -> int:
    godot = runtime_evidence.find_godot(PROJECT_ROOT)
    if not godot:
        print("SKIP: godot executable not found; runtime evidence cannot be verified")
        return 1

    temp = tempfile.mkdtemp(prefix="runtime_evidence_", dir=os.path.join(DOTAI, "tmp"))
    project = os.path.join(temp, "project")
    try:
        # ---------------- 临时 Godot 项目（探针 + 夹具） ----------------
        write_text(os.path.join(project, "project.godot"),
                   "config_version=5\n\n[application]\nconfig/name=\"runtime-evidence-fixture\"\n")
        probe_target = os.path.join(project, ".ai", "tools", "scene_composer", "probes",
                                    "instance_runtime_probe.gd")
        os.makedirs(os.path.dirname(probe_target), exist_ok=True)
        shutil.copyfile(os.path.join(TOOL_DIR, "probes", "instance_runtime_probe.gd"),
                        probe_target)

        # ---------------- Case 1: 仓库真实 Feature ----------------
        print("=== Case 1: the repository's declared Features load in real Godot ===")
        declared = runtime_evidence.declared_features()
        ok("case1: six Features declare a runtime contract", len(declared) == 6, str(declared))
        for feature_id in declared:
            report = runtime_evidence.verify_feature(feature_id)
            ok("case1: %s PASS on the loaded scene" % feature_id,
               report.status == runtime_evidence.STATUS_PASS,
               str(report.to_dict())[:400])
            ok("case1: %s evidence came from a real load (observed_frame)" % feature_id,
               isinstance(report.observed_frame, int), str(report.observed_frame))

        # ---------------- Case 2: 加载失败（缺失脚本） ----------------
        print("=== Case 2: a scene with a broken resource reference fails ===")
        feats = feature(project, "rt_broken",
                        {"node_type": "Area2D", "runtime": {"when": "after_load"}},
                        scene("Area2D", script="res://Features/rt_broken/Missing.gd"))
        report = run_case(project, "rt_broken", godot)
        ok("case2: status MISMATCH with reason load_error",
           report.status == runtime_evidence.STATUS_MISMATCH
           and report.reason == "load_error", str(report.to_dict())[:500])
        ok("case2: the detail quotes the real engine error",
           "Missing.gd" in report.detail or "non-existent resource" in report.detail,
           report.detail)
        ok("case2: a partially loaded scene never becomes PASS",
           report.status != runtime_evidence.STATUS_PASS)

        # ---------------- Case 3: 节点缺失 ----------------
        print("=== Case 3: a missing instance is MISMATCH, not INSUFFICIENT ===")
        feature(project, "rt_missing",
                {"node_type": "Area2D", "children": ["CollisionShape2D"],
                 "runtime": {"when": "after_load"}},
                scene("Area2D", child("Visual", "Polygon2D")))
        report = run_case(project, "rt_missing", godot)
        ok("case3: status MISMATCH / missing",
           report.status == runtime_evidence.STATUS_MISMATCH and report.reason == "missing",
           str(report.to_dict())[:400])
        ok("case3: the failing check names the expected type and count",
           any(check.get("type") == "CollisionShape2D"
               and check.get("status") == "MISSING" for check in report.checks),
           str(report.checks))

        # ---------------- Case 4: 类型不符 ----------------
        print("=== Case 4: a wrong node type is MISMATCH ===")
        feature(project, "rt_wrong_type",
                {"node_type": "Area2D",
                 "runtime": {"when": "after_load",
                             "expectations": [{"path": "Shape",
                                               "type": "CollisionShape2D"}]}},
                scene("Area2D", child("Shape", "Sprite2D")))
        report = run_case(project, "rt_wrong_type", godot)
        ok("case4: status MISMATCH / type_mismatch",
           report.status == runtime_evidence.STATUS_MISMATCH
           and report.reason == "type_mismatch", str(report.to_dict())[:400])
        ok("case4: the check reports the actual type",
           any(check.get("status") == "TYPE_MISMATCH"
               and "Sprite2D" in (check.get("actual_types") or []) for check in report.checks),
           str(report.checks))

        # ---------------- Case 5: 数量不符 ----------------
        print("=== Case 5: a count mismatch is MISMATCH ===")
        feature(project, "rt_count",
                {"node_type": "Area2D", "children": ["CollisionShape2D", "CollisionShape2D"],
                 "runtime": {"when": "after_load"}},
                scene("Area2D", child("ShapeA", "CollisionShape2D")))
        report = run_case(project, "rt_count", godot)
        ok("case5: status MISMATCH / count_mismatch",
           report.status == runtime_evidence.STATUS_MISMATCH
           and report.reason == "count_mismatch", str(report.to_dict())[:400])
        ok("case5: expected 2 / found 1 is visible in the check",
           any(check.get("expected_count") == 2 and check.get("found_count") == 1
               for check in report.checks), str(report.checks))

        # ---------------- Case 6: 动态节点在窗口内生成 ----------------
        print("=== Case 6: a dynamic child generated inside the window passes ===")
        spawner = ("extends Area2D\n\nconst SPAWN_AFTER := 5\n\n"
                   "func _ready() -> void:\n\t_spawn()\n\n"
                   "func _spawn() -> void:\n\tfor _i in SPAWN_AFTER:\n"
                   "\t\tawait get_tree().process_frame\n"
                   "\tvar shape := CollisionShape2D.new()\n\tshape.name = \"Delayed\"\n"
                   "\tadd_child(shape)\n")
        feature(project, "rt_dynamic",
                {"node_type": "Area2D", "children": ["CollisionShape2D"],
                 "runtime_children": ["CollisionShape2D"],
                 "runtime": {"when": "after_load", "timeout_frames": 30}},
                scene("Area2D", script="res://Features/rt_dynamic/Spawner.gd"),
                extra_files={"Spawner.gd": spawner})
        report = run_case(project, "rt_dynamic", godot)
        ok("case6: status PASS",
           report.status == runtime_evidence.STATUS_PASS, str(report.to_dict())[:400])
        ok("case6: the verifier waited for the node instead of failing early",
           (report.waited_frames or 0) > 0, str(report.waited_frames))
        ok("case6: first_seen_frame records when the node appeared",
           any(isinstance(check.get("first_seen_frame"), int)
               and check.get("first_seen_frame") > 0 for check in report.checks),
           str(report.checks))

        # ---------------- Case 7: 动态节点窗口内未生成 ----------------
        print("=== Case 7: a dynamic child that never appears is a window timeout ===")
        idle = "extends Area2D\n\nfunc _ready() -> void:\n\tpass\n"
        feature(project, "rt_dynamic_never",
                {"node_type": "Area2D", "children": ["CollisionShape2D"],
                 "runtime_children": ["CollisionShape2D"],
                 "runtime": {"when": "after_load", "timeout_frames": 12}},
                scene("Area2D", script="res://Features/rt_dynamic_never/Idle.gd"),
                extra_files={"Idle.gd": idle})
        report = run_case(project, "rt_dynamic_never", godot)
        ok("case7: status MISMATCH / missing_after_timeout",
           report.status == runtime_evidence.STATUS_MISMATCH
           and report.reason == "missing_after_timeout", str(report.to_dict())[:400])
        ok("case7: the whole window was observed before the conclusion",
           report.waited_frames == 12, str(report.waited_frames))
        ok("case7: the failing check is the runtime-declared child",
           any(check.get("status") == "MISSING" and check.get("runtime") is True
               for check in report.checks), str(report.checks))

        # ---------------- Case 8: after_action 不自动触发 ----------------
        print("=== Case 8: action-gated contracts stay INSUFFICIENT ===")
        feature(project, "rt_action",
                {"node_type": "Area2D", "children": ["CollisionShape2D"],
                 "runtime_children": ["CollisionShape2D"],
                 "runtime": {"when": "after_action:open", "timeout_frames": 10}},
                scene("Area2D", child("Shape", "CollisionShape2D")))
        report = run_case(project, "rt_action", godot)
        ok("case8: status INSUFFICIENT / action_not_triggerable",
           report.status == runtime_evidence.STATUS_INSUFFICIENT
           and report.reason == "action_not_triggerable", str(report.to_dict()))
        ok("case8: no Godot run is performed for action-gated contracts",
           report.artifacts == {} and report.observed_frame is None, str(report.artifacts))

        # ---------------- Case 9: 非法契约 ----------------
        print("=== Case 9: invalid runtime contracts are INVALID, never guessed ===")
        feature(project, "rt_bad_when",
                {"node_type": "Area2D", "runtime": {"when": "later"}},
                scene("Area2D"))
        feature(project, "rt_bad_count",
                {"node_type": "Area2D", "runtime": {"when": "after_load", "timeout_frames": 5,
                                                    "expectations": [{"type": "Area2D",
                                                                      "path": ".",
                                                                      "count": 0}]}},
                scene("Area2D"))
        feature(project, "rt_bad_both",
                {"node_type": "Area2D", "runtime": {"when": "after_load",
                                                    "expectations": [{"type": "CollisionShape2D",
                                                                      "path": "A",
                                                                      "parent": "."}]}},
                scene("Area2D"))
        feature(project, "rt_bad_type",
                {"node_type": "Area2D", "runtime": {"when": "after_load",
                                                    "expectations": [{"type": "NotANode",
                                                                      "path": "."}]}},
                scene("Area2D"))
        for feature_id in ("rt_bad_when", "rt_bad_count", "rt_bad_both", "rt_bad_type"):
            report = run_case(project, feature_id, godot)
            ok("case9: %s -> INVALID / contract_invalid" % feature_id,
               report.status == runtime_evidence.STATUS_INVALID
               and report.reason == "contract_invalid", str(report.to_dict())[:300])
            ok("case9: %s is not executed" % feature_id,
               report.artifacts == {} and report.observed_frame is None)

        # ---------------- Case 10: 采集失败不得 PASS ----------------
        print("=== Case 10: evidence collection failure is INSUFFICIENT, never PASS ===")
        feature(project, "rt_collect_fail",
                {"node_type": "Area2D", "runtime": {"when": "after_load"}},
                scene("Area2D", child("Shape", "CollisionShape2D")))
        report = runtime_evidence.verify_feature(
            "rt_collect_fail", os.path.join(project, "Features"), project_root=project,
            godot=godot,
            runner=lambda *args, **kwargs: {"result": None, "stdout": "", "stderr": "",
                                            "exit_code": 0, "duration": 0.1, "timed_out": False,
                                            "artifacts": {}})
        ok("case10: no result -> INSUFFICIENT / evidence_unavailable",
           report.status == runtime_evidence.STATUS_INSUFFICIENT
           and report.reason == "evidence_unavailable", str(report.to_dict()))
        ok("case10: a collector failure is never PASS", report.status != "PASS")
        missing_godot = runtime_evidence.verify_feature(
            "rt_collect_fail", os.path.join(project, "Features"), project_root=project,
            godot="")
        ok("case10: a missing Godot binary cannot become PASS",
           missing_godot.status == runtime_evidence.STATUS_INSUFFICIENT,
           str(missing_godot.to_dict()))

        # ---------------- Case 11: 未声明 runtime ----------------
        print("=== Case 11: Features without runtime stay NOT_DECLARED ===")
        feature(project, "rt_plain",
                {"node_type": "Area2D", "children": ["CollisionShape2D"]},
                scene("Area2D", child("Shape", "CollisionShape2D")))
        report = run_case(project, "rt_plain", godot)
        ok("case11: NOT_DECLARED / runtime_not_declared",
           report.status == runtime_evidence.STATUS_NOT_DECLARED
           and report.reason == "runtime_not_declared", str(report.to_dict()))
        ok("case11: no Godot run is performed when runtime is not required",
           report.artifacts == {})

        # ---------------- Case 12: 机器可读结果 + CLI 退出码 ----------------
        print("=== Case 12: machine-readable result and CLI exit codes ===")
        cli = [sys.executable, os.path.join(TOOL_DIR, "runtime_instance_evidence.py"),
               "--features-dir", os.path.join(project, "Features"),
               "--project-root", project, "--godot", godot, "--json"]
        proc = subprocess.run(cli + ["--feature", "rt_missing"], capture_output=True,
                              text=True, encoding="utf-8", errors="replace",
                              timeout=120, stdin=subprocess.DEVNULL)
        payload = json.loads(proc.stdout or "{}")
        ok("case12: mismatch exits 1", proc.returncode == 1, str(proc.returncode))
        ok("case12: JSON exposes status / reason / run_id / checks",
           payload.get("reports") and payload["reports"][0]["status"] == "MISMATCH"
           and payload["reports"][0]["reason"] == "missing"
           and payload["reports"][0]["run_id"]
           and isinstance(payload["reports"][0]["checks"], list), str(payload)[:400])
        proc = subprocess.run(cli + ["--feature", "rt_action"], capture_output=True,
                              text=True, encoding="utf-8", errors="replace",
                              timeout=120, stdin=subprocess.DEVNULL)
        ok("case12: INSUFFICIENT exits 0 without --require-runtime", proc.returncode == 0,
           str(proc.returncode))
        proc = subprocess.run(cli + ["--feature", "rt_action", "--require-runtime"],
                              capture_output=True, text=True, encoding="utf-8",
                              errors="replace", timeout=120, stdin=subprocess.DEVNULL)
        ok("case12: INSUFFICIENT exits 1 under --require-runtime", proc.returncode == 1,
           str(proc.returncode))
        proc = subprocess.run(cli + ["--feature", "rt_dynamic_never"], capture_output=True,
                              text=True, encoding="utf-8", errors="replace",
                              timeout=120, stdin=subprocess.DEVNULL)
        ok("case12: window timeout exits 1", proc.returncode == 1, str(proc.returncode))

        # ---------------- Case 14: 真实黄金 Feature 副本上的负向对照 ----------------
        print("=== Case 14: negative controls on a copy of a real Feature scene ===")
        source_feature = "openable_door"
        source_dir = os.path.join(PROJECT_ROOT, "Features", source_feature)
        source_scene = os.path.join(source_dir, "OpenableDoor.tscn")
        source_script = os.path.join(source_dir, "openable_door.gd")
        # 操作前记录黄金基线校验和；负向对照只作用于临时副本。
        baseline_hashes = {source_scene: sha256(source_scene),
                           source_script: sha256(source_script)}

        copy_dir = os.path.join(project, "Features", source_feature)
        shutil.copytree(source_dir, copy_dir)
        copy_scene = os.path.join(copy_dir, "OpenableDoor.tscn")
        copy_template = os.path.join(copy_dir, "template.yaml")
        copy_script = os.path.join(copy_dir, "openable_door.gd")
        scene_bytes = open(copy_scene, "rb").read()
        script_bytes = open(copy_script, "rb").read()
        static_declaration = {"node_type": "StaticBody2D", "children": ["CollisionShape2D"],
                              "runtime": {"when": "after_load", "timeout_frames": 0}}

        def write_copy(text: str) -> None:
            with open(copy_scene, "w", encoding="utf-8", newline="\n") as handle:
                handle.write(text)

        def copy_hashes() -> dict:
            return {copy_scene: sha256(copy_scene), copy_script: sha256(copy_script)}

        try:
            # 基线：真实场景的副本在临时项目中应当 PASS（证明副本本身有效）。
            write_text(copy_template, runtime_template(
                source_feature, "OpenableDoor.tscn", static_declaration))
            report = run_case(project, source_feature, godot)
            ok("case14: the untouched copy of the real scene loads and PASSes",
               report.status == runtime_evidence.STATUS_PASS, str(report.to_dict())[:400])
            valid_copy_hashes = copy_hashes()

            # Control 1: 确定的加载失败（脚本资源不存在）。
            write_copy(scene_bytes.decode("utf-8").replace(
                "openable_door.gd", "MissingRuntimeControl.gd"))
            report = run_case(project, source_feature, godot)
            ok("case14-control1: load failure -> MISMATCH / load_error",
               report.status == runtime_evidence.STATUS_MISMATCH
               and report.reason == "load_error", str(report.to_dict())[:400])
            proc = subprocess.run(
                [sys.executable, os.path.join(TOOL_DIR, "runtime_instance_evidence.py"),
                 "--features-dir", os.path.join(project, "Features"),
                 "--project-root", project, "--godot", godot, "--json",
                 "--feature", source_feature],
                capture_output=True, text=True, encoding="utf-8", errors="replace",
                timeout=120, stdin=subprocess.DEVNULL)
            ok("case14-control1: CLI exits 1 on a load failure", proc.returncode == 1,
               proc.stdout[-300:])
            write_copy(scene_bytes.decode("utf-8"))
            ok("case14-control1: scene bytes restored to the baseline copy",
               sha256(copy_scene) == valid_copy_hashes[copy_scene])

            # Control 2: 移除契约要求的实例（Collision）。
            write_copy("\n".join(line for line in scene_bytes.decode("utf-8").splitlines()
                                 if "[node name=\"Collision\"" not in line)
                       .replace("shape = SubResource(\"RectangleShape2D_door\")", ""))
            report = run_case(project, source_feature, godot)
            ok("case14-control2: removed instance -> MISMATCH / missing",
               report.status == runtime_evidence.STATUS_MISMATCH
               and report.reason == "missing", str(report.to_dict())[:400])
            ok("case14-control2: the missing check names CollisionShape2D",
               any(check.get("type") == "CollisionShape2D"
                   and check.get("status") == "MISSING" for check in report.checks),
               str(report.checks))
            write_copy(scene_bytes.decode("utf-8"))
            ok("case14-control2: scene bytes restored to the baseline copy",
               sha256(copy_scene) == valid_copy_hashes[copy_scene])

            # Control 3: 动态创建条件失败（静态 Collision 已移除，脚本也不再生成）。
            write_text(os.path.join(copy_dir, "Spawner.gd"),
                       "extends StaticBody2D\n\nfunc _ready() -> void:\n\tpass\n")
            dynamic_scene = "\n".join(line for line in scene_bytes.decode("utf-8").splitlines()
                                       if "[node name=\"Collision\"" not in line)
            dynamic_scene = dynamic_scene.replace(
                "shape = SubResource(\"RectangleShape2D_door\")", "")
            write_copy(dynamic_scene.replace("openable_door.gd", "Spawner.gd"))
            write_text(copy_template, runtime_template(source_feature, "OpenableDoor.tscn",
                                                       {"node_type": "StaticBody2D",
                                                        "children": ["CollisionShape2D"],
                                                        "runtime_children": ["CollisionShape2D"],
                                                        "runtime": {"when": "after_load",
                                                                    "timeout_frames": 10}}))
            report = run_case(project, source_feature, godot)
            ok("case14-control3: failed dynamic creation -> MISMATCH / missing_after_timeout",
               report.status == runtime_evidence.STATUS_MISMATCH
               and report.reason == "missing_after_timeout", str(report.to_dict())[:400])
            ok("case14-control3: the observation window was fully waited",
               report.waited_frames == 10, str(report.waited_frames))
            proc = subprocess.run(
                [sys.executable, os.path.join(TOOL_DIR, "runtime_instance_evidence.py"),
                 "--features-dir", os.path.join(project, "Features"),
                 "--project-root", project, "--godot", godot, "--json",
                 "--feature", source_feature],
                capture_output=True, text=True, encoding="utf-8", errors="replace",
                timeout=120, stdin=subprocess.DEVNULL)
            ok("case14-control3: CLI exits 1 when a dynamic node never appears",
               proc.returncode == 1, proc.stdout[-300:])

            # 恢复副本并校验哈希；然后确认仓库金标文件从未被写。
            write_copy(scene_bytes.decode("utf-8"))
            write_text(copy_template, runtime_template(
                source_feature, "OpenableDoor.tscn", static_declaration))
            ok("case14: the copy is restored byte-for-byte",
               copy_hashes() == valid_copy_hashes,
               str(copy_hashes()) + " vs " + str(valid_copy_hashes))
            ok("case14: the repository golden scene is untouched",
               sha256(source_scene) == baseline_hashes[source_scene]
               and sha256(source_script) == baseline_hashes[source_script])
        finally:
            write_text(copy_scene, scene_bytes.decode("utf-8"))
            with open(copy_script, "wb") as handle:
                handle.write(script_bytes)

        # ---------------- Case 13: Phase 1.38 静态对账回归 ----------------
        print("=== Case 13: Phase 1.38 reconciliation still passes ===")
        for feature_id in instance_evidence.declared_features():
            report = instance_evidence.reconcile_feature(feature_id)
            ok("case13: %s static reconciliation still PASS" % feature_id,
               report.status == instance_evidence.STATUS_PASS, str(report.to_dict())[:200])
    finally:
        shutil.rmtree(temp, ignore_errors=True)

    print()
    if _failures:
        print("FAIL: %d failing check(s)" % len(_failures))
        for failure in _failures:
            print("  - " + failure)
        return 1
    print("PASS: all runtime instance evidence checks passed")
    return 0


if __name__ == "__main__":
    sys.exit(run())
