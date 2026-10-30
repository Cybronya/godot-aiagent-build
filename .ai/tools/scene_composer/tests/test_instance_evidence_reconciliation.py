#!/usr/bin/env python3
"""Feature Instance Evidence Reconciliation 测试（Phase 1.38）

链路：template.yaml#instance（声明证据）→ 真实 .tscn（静态场景证据）→ 对账结论
      （runtime 证据不在本层；缺它时必须 INSUFFICIENT，而不是 PASS）。

    Case 1  仓库 6 个声明全部 PASS（真实文件，不造夹具）
    Case 2  声明要求子节点、场景缺失 → MISMATCH（INSTANCE_CHILD_MISSING）
    Case 3  错误场景引用（根类型不符 / 引用了别的 Feature 场景）→ MISMATCH
    Case 4  子节点层级错误 → MISMATCH（带实际节点路径）
    Case 5  多实例数量不符 → MISMATCH（INSTANCE_CHILD_COUNT_MISMATCH）
    Case 6  非法声明（未知类型 / children 非列表 / runtime_children ⊄ children）→ INVALID
    Case 7  合法额外节点不造成误报（额外兄弟节点 / 更深层无关节点）→ PASS
    Case 8  运行时创建的节点 → INSUFFICIENT；声明过期（静态已存在）→ warning
    Case 9  挂载模式：正确挂载 PASS；错误场景引用 / 重复挂载 / 子节点落在别的组件子树 / 缺挂载 → MISMATCH
    Case 10 D8 不回归：菱形引用（Host → A、Host → B → A）不是环
    Case 11 场景不可读 / 无根节点 → INVALID
    Case 12 未声明 instance: → NOT_DECLARED（旧 Feature 合法）
    Case 13 Validator 第 7 阶段：真实仓库 PASS；坏夹具 → failure；INSUFFICIENT → warning

附件：
    - 证据隔离：模块不得 import scene_intent / scene_composer / scene_builder /
      artifact_evidence_validator（不得复用生成器预期对象作为唯一证据）。
    - 只读纪律：不启动 Godot、不写文件；夹具全部在临时目录。
    - 真实仓库负向对照在测试外部执行（见 PHASE_1_38_AUDIT.md）。

只读项目文件、只写临时目录。

用法:
    python .ai/tools/scene_composer/tests/test_instance_evidence_reconciliation.py
全部通过输出 PASS 并退出 0；任一失败输出 FAIL 并退出 1。
"""

import ast
import hashlib
import os
import shutil
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

import external_artifact_resolver                            # noqa: E402
import instance_evidence                                     # noqa: E402

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


def scene_text(root_type: str, children: str = "", script: str = "") -> str:
    """最小 .tscn 文本；children 是节点块片段。"""
    ext = ("[ext_resource type=\"Script\" path=\"%s\" id=\"1_script\"]\n\n" % script
           if script else "")
    return ("[gd_scene load_steps=2 format=3]\n\n" + ext +
            "[node name=\"Probe\" type=\"%s\"]\n\n" % root_type + children)


def child_block(name: str, node_type: str, parent: str = ".") -> str:
    return "[node name=\"%s\" type=\"%s\" parent=\"%s\"]\n\n" % (name, node_type, parent)


def make_feature(root: str, feature: str, declaration: dict, scene: str,
                 source: str = "Probe.tscn", extra_template: str = "") -> str:
    """临时 Features 目录下构造一个 Feature（template + 场景）。"""
    feature_dir = os.path.join(root, "Features", feature)
    write_text(os.path.join(feature_dir, source), scene)
    template = ("feature:\n  id: %s\nscene:\n  source: %s\nvalidation:\n  required_nodes:\n"
                "    - Probe\n%s" % (feature, source, extra_template))
    if declaration is not None:
        template += "instance:\n" + "".join("  %s\n" % line
                                             for line in yaml.safe_dump(
                                                 declaration, sort_keys=False).splitlines())
    write_text(os.path.join(feature_dir, "template.yaml"), template)
    return os.path.join(root, "Features")


def codes(report) -> set:
    return {finding["code"] for finding in report.findings}


def run() -> int:
    sys.path.insert(0, os.path.join(DOTAI, "tools"))
    from validator.check_instance_evidence import check_instance_evidence

    tmp = tempfile.mkdtemp(prefix="instance_evidence_")
    try:
        # ---------------- Case 1: 真实仓库的 7 个声明 ----------------
        # Phase 1.52 起 promote 脚手架自带 instance 声明，projectile 入列后 6 -> 7。
        print("=== Case 1: the repository's declared Features reconcile ===")
        declared = instance_evidence.declared_features()
        ok("case1: seven Features declare instance: evidence", len(declared) == 7, str(declared))
        for feature in declared:
            report = instance_evidence.reconcile_feature(feature)
            ok("case1: %s PASS against its real scene" % feature,
               report.status == instance_evidence.STATUS_PASS,
               str(report.to_dict()))

        # ---------------- Case 2: 子节点缺失 ----------------
        print("=== Case 2: a declared child missing from the scene is MISMATCH ===")
        root_a = os.path.join(tmp, "case2")
        missing_feats = make_feature(
            root_a, "probe_missing",
            {"node_type": "Area2D", "children": ["CollisionShape2D"]},
            scene_text("Area2D", child_block("Visual", "Polygon2D")))
        report = instance_evidence.reconcile_feature("probe_missing", missing_feats)
        ok("case2: status MISMATCH", report.status == instance_evidence.STATUS_MISMATCH,
           str(report.to_dict()))
        ok("case2: the finding is CHILD_MISSING for CollisionShape2D",
           "INSTANCE_CHILD_MISSING" in codes(report)
           and any("CollisionShape2D" in finding["detail"] for finding in report.findings),
           str(report.findings))
        ok("case2: the finding is an error, not a warning",
           [f["severity"] for f in report.findings if f["code"] == "INSTANCE_CHILD_MISSING"]
           == ["error"], str(report.findings))

        # ---------------- Case 3: 错误场景引用 ----------------
        print("=== Case 3: a wrong scene reference is MISMATCH ===")
        root_b = os.path.join(tmp, "case3")
        wrong_feats = make_feature(
            root_b, "probe_wrong_scene",
            {"node_type": "Area2D", "children": ["CollisionShape2D"]},
            scene_text("Node2D", child_block("Shape", "CollisionShape2D")))
        report = instance_evidence.reconcile_feature("probe_wrong_scene", wrong_feats)
        ok("case3: root type mismatch is reported with both types",
           "INSTANCE_ROOT_TYPE_MISMATCH" in codes(report)
           and any("declared root Area2D" in f["detail"] and "scene root Node2D" in f["detail"]
                   for f in report.findings), str(report.findings))
        ok("case3: the mismatch points at the scene root node",
           any(f["code"] == "INSTANCE_ROOT_TYPE_MISMATCH" and f["node_path"] == "Probe"
               for f in report.findings), str(report.findings))

        # ---------------- Case 4: 节点路径 / 层级错误 ----------------
        print("=== Case 4: a declared child at the wrong path is MISMATCH ===")
        root_c = os.path.join(tmp, "case4")
        nested = (child_block("Container", "Node2D")
                  + child_block("Shape", "CollisionShape2D", parent="Container"))
        nested_feats = make_feature(
            root_c, "probe_nested",
            {"node_type": "Area2D", "children": ["CollisionShape2D"]},
            scene_text("Area2D", nested))
        report = instance_evidence.reconcile_feature("probe_nested", nested_feats)
        ok("case4: status MISMATCH with CHILD_PATH_MISMATCH",
           report.status == instance_evidence.STATUS_MISMATCH
           and "INSTANCE_CHILD_PATH_MISMATCH" in codes(report), str(report.findings))
        ok("case4: the actual nested path is locatable",
           any(f["code"] == "INSTANCE_CHILD_PATH_MISMATCH" and f["node_path"] == "Probe/Container/Shape"
               for f in report.findings), str(report.findings))

        # ---------------- Case 5: 多实例数量不符 ----------------
        print("=== Case 5: declared instance count must be met ===")
        root_d = os.path.join(tmp, "case5")
        one_shape = scene_text("Area2D", child_block("ShapeA", "CollisionShape2D"))
        count_feats = make_feature(
            root_d, "probe_count",
            {"node_type": "Area2D", "children": ["CollisionShape2D", "CollisionShape2D"]},
            one_shape)
        report = instance_evidence.reconcile_feature("probe_count", count_feats)
        ok("case5: one of two declared children is a count mismatch",
           report.status == instance_evidence.STATUS_MISMATCH
           and "INSTANCE_CHILD_COUNT_MISMATCH" in codes(report), str(report.findings))
        ok("case5: the finding states declared 2 / found 1",
           any("declared 2, found 1" in f["detail"] for f in report.findings),
           str(report.findings))
        two_shapes = scene_text("Area2D", child_block("ShapeA", "CollisionShape2D")
                                + child_block("ShapeB", "CollisionShape2D"))
        feats_two = make_feature(os.path.join(tmp, "case5b"), "probe_count",
                                 {"node_type": "Area2D",
                                  "children": ["CollisionShape2D", "CollisionShape2D"]},
                                 two_shapes)
        ok("case5: two shapes satisfy a two-instance declaration",
           instance_evidence.reconcile_feature("probe_count", feats_two).status
           == instance_evidence.STATUS_PASS)

        # ---------------- Case 6: 非法声明 ----------------
        print("=== Case 6: illegal declarations are rejected, never guessed ===")
        root_e = os.path.join(tmp, "case6")
        scene = scene_text("Area2D", child_block("Shape", "CollisionShape2D"))
        for label, declaration, needle in [
            ("unknown type", {"node_type": "Area2D", "children": ["NotARealNode"]},
             "unknown node type"),
            ("children not a list", {"node_type": "Area2D", "children": {"a": 1}},
             "must be lists"),
            ("runtime child not declared", {"node_type": "Area2D",
                                            "children": ["CollisionShape2D"],
                                            "runtime_children": ["Sprite2D"]},
             "not declared in children"),
            ("missing node_type", {"children": ["CollisionShape2D"]}, "node_type"),
        ]:
            feats = make_feature(os.path.join(root_e, label.replace(" ", "_")),
                                 "probe_invalid", declaration, scene)
            report = instance_evidence.reconcile_feature("probe_invalid", feats)
            ok("case6: %s -> INVALID" % label,
               report.status == instance_evidence.STATUS_INVALID, str(report.to_dict()))
            ok("case6: %s names the offending field" % label,
               any(needle in f["detail"] for f in report.findings), str(report.findings))

        # ---------------- Case 7: 额外合法节点不误报 ----------------
        print("=== Case 7: legitimate extra nodes never trigger a mismatch ===")
        root_f = os.path.join(tmp, "case7")
        extras = (child_block("Visual", "Polygon2D")
                  + child_block("Shape", "CollisionShape2D")
                  + child_block("Timer", "Timer")
                  + child_block("Decor", "Node2D")
                  + child_block("Deep", "CollisionPolygon2D", parent="Decor"))
        extra_feats = make_feature(
            root_f, "probe_extra",
            {"node_type": "Area2D", "children": ["CollisionShape2D"]},
            scene_text("Area2D", extras))
        report = instance_evidence.reconcile_feature("probe_extra", extra_feats)
        ok("case7: extra siblings and deeper nodes are ignored",
           report.status == instance_evidence.STATUS_PASS, str(report.to_dict()))

        # ---------------- Case 8: 动态创建 / 声明过期 ----------------
        print("=== Case 8: runtime-created nodes stay INSUFFICIENT ===")
        root_g = os.path.join(tmp, "case8")
        dynamic_feats = make_feature(
            root_g, "probe_dynamic",
            {"node_type": "Area2D", "children": ["CollisionShape2D"],
             "runtime_children": ["CollisionShape2D"]},
            scene_text("Area2D", child_block("Visual", "Polygon2D"),
                       script="res://Features/probe_dynamic/probe.gd"))
        report = instance_evidence.reconcile_feature("probe_dynamic", dynamic_feats)
        ok("case8: a runtime-declared child is INSUFFICIENT, not MISMATCH",
           report.status == instance_evidence.STATUS_INSUFFICIENT
           and "INSTANCE_RUNTIME_CHILD_UNVERIFIED" in codes(report), str(report.to_dict()))
        ok("case8: the finding carries runtime evidence provenance",
           any(f["code"] == "INSTANCE_RUNTIME_CHILD_UNVERIFIED"
               and f["evidence"] == instance_evidence.EVIDENCE_RUNTIME
               for f in report.findings), str(report.findings))
        ok("case8: a missing runtime child is only a warning",
           all(f["severity"] == "warning" for f in report.findings
               if f["code"] == "INSTANCE_RUNTIME_CHILD_UNVERIFIED"), str(report.findings))
        stale_feats = make_feature(
            os.path.join(tmp, "case8b"), "probe_stale",
            {"node_type": "Area2D", "children": ["CollisionShape2D"],
             "runtime_children": ["CollisionShape2D"]},
            scene_text("Area2D", child_block("Shape", "CollisionShape2D")))
        stale = instance_evidence.reconcile_feature("probe_stale", stale_feats)
        ok("case8: a stale runtime declaration is flagged as a warning",
           stale.status == instance_evidence.STATUS_INSUFFICIENT
           and "INSTANCE_RUNTIME_CHILD_STALE" in codes(stale), str(stale.findings))

        # ---------------- Case 9: 挂载模式 ----------------
        print("=== Case 9: component mounts in a generated host scene ===")
        root_h = os.path.join(tmp, "case9")
        feats_h = make_feature(
            root_h, "probe_mount",
            {"node_type": "Area2D", "children": ["CollisionShape2D"]},
            scene_text("Area2D", child_block("Shape", "CollisionShape2D")))
        host_dir = os.path.join(root_h, "Scenes")
        good_host = write_text(os.path.join(host_dir, "Good.tscn"),
                               "[gd_scene load_steps=2 format=3]\n\n"
                               "[ext_resource type=\"PackedScene\" "
                               "path=\"res://Features/probe_mount/Probe.tscn\" id=\"1_m\"]\n\n"
                               "[node name=\"Host\" type=\"Node2D\"]\n\n"
                               "[node name=\"Probe\" parent=\".\" instance=ExtResource(\"1_m\")]\n")
        good = instance_evidence.reconcile_component_mounts(good_host, ["probe_mount"], feats_h)
        ok("case9: a single correct mount PASSes", good["status"] == "PASS", str(good))
        ok("case9: the component report lists the verified child",
           "CollisionShape2D:Probe/Shape" in (good["components"]["probe_mount"]["checked"] or []),
           str(good["components"]))

        dup_host = write_text(os.path.join(host_dir, "Dup.tscn"),
                              "[gd_scene load_steps=2 format=3]\n\n"
                              "[ext_resource type=\"PackedScene\" "
                              "path=\"res://Features/probe_mount/Probe.tscn\" id=\"1_m\"]\n\n"
                              "[node name=\"Host\" type=\"Node2D\"]\n\n"
                              "[node name=\"Probe\" parent=\".\" instance=ExtResource(\"1_m\")]\n\n"
                              "[node name=\"Probe2\" parent=\".\" instance=ExtResource(\"1_m\")]\n")
        dup = instance_evidence.reconcile_component_mounts(dup_host, ["probe_mount"], feats_h)
        ok("case9: a duplicated mount is MISMATCH",
           dup["status"] == "MISMATCH"
           and "INSTANCE_MOUNT_DUPLICATED" in {f["code"] for f in dup["findings"]}, str(dup))

        wrong_host = write_text(os.path.join(host_dir, "Wrong.tscn"),
                                "[gd_scene load_steps=2 format=3]\n\n"
                                "[ext_resource type=\"PackedScene\" "
                                "path=\"res://Features/probe_mount/Other.tscn\" id=\"1_m\"]\n\n"
                                "[node name=\"Host\" type=\"Node2D\"]\n\n"
                                "[node name=\"Probe\" parent=\".\" instance=ExtResource(\"1_m\")]\n")
        write_text(os.path.join(root_h, "Features", "probe_mount", "Other.tscn"),
                   scene_text("Area2D", child_block("Shape", "CollisionShape2D")))
        wrong = instance_evidence.reconcile_component_mounts(wrong_host, ["probe_mount"], feats_h)
        ok("case9: mounting another scene of the same Feature is MISMATCH",
           wrong["status"] == "MISMATCH"
           and "INSTANCE_WRONG_SCENE_REFERENCE" in {f["code"] for f in wrong["findings"]},
           str(wrong))

        missing_host = write_text(os.path.join(host_dir, "Missing.tscn"),
                                  "[gd_scene load_steps=1 format=3]\n\n"
                                  "[node name=\"Host\" type=\"Node2D\"]\n")
        missing = instance_evidence.reconcile_component_mounts(missing_host, ["probe_mount"],
                                                               feats_h)
        ok("case9: an absent mount is MISMATCH",
           missing["status"] == "MISMATCH"
           and "INSTANCE_MOUNT_MISSING" in {f["code"] for f in missing["findings"]},
           str(missing))

        # 子节点只在别的组件子树里出现 -> 不接受（这正是 artifact 层 "elsewhere" 的宽松点）
        root_i = os.path.join(tmp, "case9e")
        feats_i = make_feature(
            root_i, "probe_owner",
            {"node_type": "Area2D", "children": ["CollisionShape2D"]},
            scene_text("Area2D"))                       # 自己的场景没有形状
        write_text(os.path.join(root_i, "Features", "probe_other", "Other.tscn"),
                   scene_text("Area2D", child_block("Shape", "CollisionShape2D")))
        write_text(os.path.join(root_i, "Features", "probe_other", "template.yaml"),
                   "feature:\n  id: probe_other\nscene:\n  source: Other.tscn\n"
                   "instance:\n  node_type: Area2D\n  children:\n    - CollisionShape2D\n")
        outside_host = write_text(os.path.join(root_i, "Scenes", "Outside.tscn"),
                                  "[gd_scene load_steps=3 format=3]\n\n"
                                  "[ext_resource type=\"PackedScene\" "
                                  "path=\"res://Features/probe_owner/Probe.tscn\" id=\"1_o\"]\n"
                                  "[ext_resource type=\"PackedScene\" "
                                  "path=\"res://Features/probe_other/Other.tscn\" id=\"2_x\"]\n\n"
                                  "[node name=\"Host\" type=\"Node2D\"]\n\n"
                                  "[node name=\"Probe\" parent=\".\" instance=ExtResource(\"1_o\")]\n\n"
                                  "[node name=\"Other\" parent=\".\" instance=ExtResource(\"2_x\")]\n")
        outside = instance_evidence.reconcile_component_mounts(
            outside_host, ["probe_owner", "probe_other"], feats_i)
        ok("case9: a child that only exists in another component is MISMATCH",
           outside["status"] == "MISMATCH"
           and "INSTANCE_CHILD_OUTSIDE_MOUNT" in {f["code"] for f in outside["findings"]},
           str(outside))

        # ---------------- Case 10: D8 菱形不回归 ----------------
        print("=== Case 10: diamond references are still not cycles (D8) ===")
        root_j = os.path.join(tmp, "case10")
        # 外部场景解析以宿主向上找到的 project.godot 为项目根；否则会退回真实仓库根。
        write_text(os.path.join(root_j, "project.godot"), "config_version=5\n")
        write_text(os.path.join(root_j, "Features", "dia_a", "A.tscn"),
                   scene_text("Area2D", child_block("ShapeA", "CollisionShape2D")))
        write_text(os.path.join(root_j, "Features", "dia_b", "B.tscn"),
                   "[gd_scene load_steps=2 format=3]\n\n"
                   "[ext_resource type=\"PackedScene\" "
                   "path=\"res://Features/dia_a/A.tscn\" id=\"1_a\"]\n\n"
                   "[node name=\"B\" type=\"Area2D\"]\n\n"
                   "[node name=\"A\" parent=\".\" instance=ExtResource(\"1_a\")]\n")
        diamond_host = write_text(os.path.join(root_j, "Scenes", "Diamond.tscn"),
                                  "[gd_scene load_steps=3 format=3]\n\n"
                                  "[ext_resource type=\"PackedScene\" "
                                  "path=\"res://Features/dia_a/A.tscn\" id=\"1_a\"]\n"
                                  "[ext_resource type=\"PackedScene\" "
                                  "path=\"res://Features/dia_b/B.tscn\" id=\"2_b\"]\n\n"
                                  "[node name=\"Host\" type=\"Node2D\"]\n\n"
                                  "[node name=\"A\" parent=\".\" instance=ExtResource(\"1_a\")]\n"
                                  "[node name=\"B\" parent=\".\" instance=ExtResource(\"2_b\")]\n")
        external = external_artifact_resolver.resolve_external_artifacts(diamond_host)
        ok("case10: the resolver still accepts the diamond",
           external["status"] == "PASS" and external["errors"] == [], str(external))

        # ---------------- Case 11: 场景不可读 / 无根节点 ----------------
        print("=== Case 11: unusable scenes are INVALID, never PASS ===")
        root_k = os.path.join(tmp, "case11")
        feats_k = make_feature(root_k, "probe_unreadable",
                               {"node_type": "Area2D", "children": ["CollisionShape2D"]},
                               scene_text("Area2D", child_block("Shape", "CollisionShape2D")))
        os.remove(os.path.join(feats_k, "probe_unreadable", "Probe.tscn"))
        gone = instance_evidence.reconcile_feature("probe_unreadable", feats_k)
        ok("case11: a missing scene is INVALID",
           gone.status == instance_evidence.STATUS_INVALID
           and "INSTANCE_EVIDENCE_UNAVAILABLE" in codes(gone), str(gone.to_dict()))
        feats_k2 = make_feature(os.path.join(tmp, "case11b"), "probe_rootless",
                                {"node_type": "Area2D"}, "[gd_scene format=3]\n\n")
        rootless = instance_evidence.reconcile_feature("probe_rootless", feats_k2)
        ok("case11: a scene without a root node is INVALID",
           rootless.status == instance_evidence.STATUS_INVALID
           and "INSTANCE_SCENE_UNPARSEABLE" in codes(rootless), str(rootless.to_dict()))

        # ---------------- Case 11b: 解析能力受限不判无效 ----------------
        print("=== Case 11b: an unparsed node header degrades to INSUFFICIENT ===")
        # 声明本身的类型都能找到，但场景里多了一行解析器不认识的节点头部：
        # 不得因此判 INVALID/MISMATCH（“解析器看不懂” ≠ “场景无效”）。
        feats_k3 = make_feature(
            os.path.join(tmp, "case11c"), "probe_limited",
            {"node_type": "Area2D", "children": ["CollisionShape2D"]},
            scene_text("Area2D", child_block("Shape", "CollisionShape2D")
                       + "[node name=\"Ghost\" type=\"Node2D\" parent=\".\"\n"))
        limited = instance_evidence.reconcile_feature("probe_limited", feats_k3)
        ok("case11b: a partial parse is INSUFFICIENT, never INVALID",
           limited.status == instance_evidence.STATUS_INSUFFICIENT
           and "INSTANCE_PARSE_LIMITED" in codes(limited), str(limited.to_dict()))
        ok("case11b: the parse gap is only a warning",
           [f["severity"] for f in limited.findings
            if f["code"] == "INSTANCE_PARSE_LIMITED"] == ["warning"],
           str(limited.findings))
        ok("case11b: the validator turns it into a warning, not a failure",
           check_instance_evidence(os.path.join(tmp, "case11c", "Features"))["failures"] == [])

        # ---------------- Case 12: 未声明 ----------------
        print("=== Case 12: Features without instance: stay NOT_DECLARED ===")
        root_l = os.path.join(tmp, "case12")
        feats_l = make_feature(root_l, "probe_plain", None,
                               scene_text("Node2D", child_block("Sprite", "Sprite2D")))
        plain = instance_evidence.reconcile_feature("probe_plain", feats_l)
        ok("case12: no declaration -> NOT_DECLARED (legacy Features stay legal)",
           plain.status == instance_evidence.STATUS_NOT_DECLARED, str(plain.to_dict()))
        ok("case12: a NOT_DECLARED Feature has no findings",
           plain.findings == [], str(plain.findings))

        # ---------------- Case 13: Validator 阶段 ----------------
        print("=== Case 13: the validator stage reports failures and warnings ===")
        repo = check_instance_evidence()
        ok("case13: the repository has no instance evidence failure",
           repo["failures"] == [] and repo["declared"] == 7, str(repo["summary"]))
        bad = check_instance_evidence(os.path.join(tmp, "case2", "Features"))
        ok("case13: a broken declaration becomes a validator failure",
           len(bad["failures"]) == 1 and "probe_missing" in bad["failures"][0],
           str(bad["failures"]))
        warn = check_instance_evidence(os.path.join(tmp, "case8", "Features"))
        ok("case13: INSUFFICIENT becomes a warning, not a failure",
           warn["failures"] == [] and len(warn["warnings"]) == 1, str(warn))

        # ---------------- 附件：证据隔离 / 只读纪律 ----------------
        print("=== Extra: evidence isolation and read-only discipline ===")
        source = open(os.path.join(TOOL_DIR, "instance_evidence.py"), encoding="utf-8").read()
        tree = ast.parse(source)
        top_imports, write_calls, read_modes = set(), [], []
        for node in tree.body:                       # 只看模块级 import；CLI 的惰性 import 在函数内
            if isinstance(node, ast.Import):
                top_imports.update(alias.name.split(".")[0] for alias in node.names)
            elif isinstance(node, ast.ImportFrom):
                top_imports.add((node.module or "").split(".")[0])
        for node in ast.walk(tree):
            if isinstance(node, ast.Call):
                func = node.func
                name = getattr(func, "attr", getattr(func, "id", ""))
                receiver = getattr(getattr(func, "value", None), "id", "")
                if name in ("write", "writelines", "remove", "rmtree", "mkdir", "makedirs",
                            "rename") or (name == "replace" and receiver in ("os", "shutil")):
                    write_calls.append(name)
                if name == "open" and node.args and isinstance(node.args[0], ast.Constant):
                    modes = [arg.value for arg in node.args[1:] if isinstance(arg, ast.Constant)]
                    read_modes.extend(mode for mode in modes if isinstance(mode, str))
        forbidden = {"scene_intent", "scene_composer", "scene_builder",
                     "artifact_evidence_validator", "capability_contract_validator"}
        ok("extra: the reconciler does not import generator/expectation modules at module level",
           not (top_imports & forbidden), str(sorted(top_imports)))
        ok("extra: no source write call exists in the reconciler", write_calls == [],
           str(write_calls))
        ok("extra: every open() is read-only", all("w" not in mode and "a" not in mode
                                                   for mode in read_modes), str(read_modes))
        ok("extra: no Godot process is started", "subprocess" not in top_imports
           and "os.system" not in source)

        # 真实文件未被改动（对账器只读）
        target = os.path.join(PROJECT_ROOT, "Features", "collect_pickup", "CollectPickup.tscn")
        before = hashlib.sha256(open(target, "rb").read()).hexdigest()
        instance_evidence.reconcile_feature("collect_pickup")
        after = hashlib.sha256(open(target, "rb").read()).hexdigest()
        ok("extra: reconciling leaves the real scene byte-identical", before == after)
    finally:
        shutil.rmtree(tmp, ignore_errors=True)

    print()
    if _failures:
        print("FAIL: %d failing check(s)" % len(_failures))
        for failure in _failures:
            print("  - " + failure)
        return 1
    print("PASS: all instance evidence reconciliation checks passed")
    return 0


if __name__ == "__main__":
    sys.exit(run())
