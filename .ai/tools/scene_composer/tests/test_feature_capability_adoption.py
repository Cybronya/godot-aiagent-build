#!/usr/bin/env python3
"""Existing Feature Capability Adoption 测试（Phase 1.8.12）

本阶段是**数据迁移**：把 Features/<id>/feature.yaml 从「无能力声明」迁移到
`capabilities.required`，从而在真实生产链上验证 Phase 1.8.11 的声明链：

    Feature（feature.yaml）→ Feature Capability Reader → Blueprint → Scene Intent
        → Compatibility Gate → Scene Builder

    Case 1  无声明 Feature（迁移未强填）→ Scene Intent.required = []，行为与 1.8.11 一致
    Case 2  Feature 声明 Node → Intent 含 Node，Gate 记录并放行
    Case 3  Feature 声明 Sprite + Collision → Intent 同时包含二者
    Case 4  Feature A: Node + Feature B: Sprite → Intent 去重为 [Node, Sprite]
    Case 5  非法能力（UnknownCapability）→ Gate BLOCKED 且零 .tscn 产物
    Case 6  真实 Feature 生成链：迁移后 .tscn / .gd 与既有产物逐字节相同
    附件    Feature 数据审计：12 个真实 Feature 的声明与自身场景/契约一致，且全链 Gate PASS

Case 1–5 用**临时 Features 目录 + 临时索引**驱动真实 compose()，不改动项目 Feature。
只读项目文件、只写临时目录；不生成仓库内 .tscn、不启动 Godot。

用法:
    python .ai/tools/scene_composer/tests/test_feature_capability_adoption.py
全部通过输出 PASS 并退出 0；任一失败输出 FAIL 并退出 1。
"""

import copy
import json
import os
import re
import shutil
import sys
import tempfile

import yaml

_HERE = os.path.dirname(os.path.abspath(__file__))                 # .ai/tools/scene_composer/tests
TOOL_DIR = os.path.dirname(_HERE)                                  # .ai/tools/scene_composer
TOOLS_DIR = os.path.dirname(TOOL_DIR)                              # .ai/tools
TEST_GEN_DIR = os.path.join(TOOLS_DIR, "test_generator")
DOTAI = os.path.dirname(TOOLS_DIR)                                 # .ai
PROJECT_ROOT = os.path.dirname(DOTAI)

for path in (TOOL_DIR, TOOLS_DIR, TEST_GEN_DIR, _HERE):
    if path not in sys.path:
        sys.path.insert(0, path)

import capability_contract_validator                           # noqa: E402
import capability_registry                                     # noqa: E402
import compatibility_gate                                      # noqa: E402
import feature_capabilities                                    # noqa: E402
import generate_scene_test                                     # noqa: E402
import scene_composer                                          # noqa: E402
import scene_intent                                            # noqa: E402
import template_loader                                         # noqa: E402
import test_scene_builder_intent_input as goldens              # noqa: E402

_failures = []


def ok(name: str, condition: bool, detail: str = "") -> None:
    if condition:
        print("PASS: " + name)
    else:
        _failures.append(name + (" | " + detail if detail else ""))
        print("FAIL: " + name + (" | " + detail if detail else ""))


# ---------------------------------------------------------------- 临时 Feature fixtures

FIXTURE_FEATURES = {
    # id: capabilities.required（None = 无声明，迁移未强填的形态）
    "undeclared": None,
    "node_only": ["Node"],
    "sprite_collider": ["Sprite", "Collision"],
    "sprite_only": ["Sprite"],
    "unknown_cap": ["UnknownCapability"],
}


def write_fixtures(root: str) -> tuple:
    """生成临时 Features 目录（feature.yaml + template.yaml）与临时索引。"""
    features_dir = os.path.join(root, "Features")
    os.makedirs(features_dir, exist_ok=True)
    records = []
    for fid, required in FIXTURE_FEATURES.items():
        feature_dir = os.path.join(features_dir, fid)
        os.makedirs(feature_dir, exist_ok=True)
        meta = {
            "id": fid, "version": 1, "category": "component", "summary": "adoption fixture",
            "provides": [], "requires": [],
            "interfaces": {"methods": [], "signals": [], "exports": []},
            "validation": {"self_test": "test_%s.gd" % fid},
        }
        if required is not None:
            meta["capabilities"] = {"required": list(required)}
        with open(os.path.join(feature_dir, "feature.yaml"), "w",
                  encoding="utf-8", newline="\n") as handle:
            handle.write(yaml.safe_dump(meta, sort_keys=False, allow_unicode=True))
        with open(os.path.join(feature_dir, "template.yaml"), "w",
                  encoding="utf-8", newline="\n") as handle:
            handle.write(yaml.safe_dump(
                {"feature": {"id": fid}, "scene": {"source": "%s.tscn" % fid},
                 "validation": {"required_nodes": [fid]}}, sort_keys=False, allow_unicode=True))
        records.append({"id": fid, "version": "1", "category": "component",
                        "provides": [], "requires": [], "interfaces": [], "signals": [],
                        "relations": {"requires": []}})
    index_path = os.path.join(root, "feature_index.json")
    with open(index_path, "w", encoding="utf-8", newline="\n") as handle:
        json.dump({"registry_version": 2, "features": records}, handle, indent=2)
    return features_dir, index_path


def entity_blueprint(feature_ids) -> dict:
    return {"entity": {"id": "adoption_probe", "role": "enemy"}, "features": list(feature_ids)}


def scene_blueprint(feature_ids, nodes=(), root_type: str = "CharacterBody2D",
                    scene_id: str = "adoption_probe") -> dict:
    """Scene Blueprint（带结构节点，用于提供 Capability Contract 的证据）。"""
    return {"scene": {"id": scene_id},
            "root": {"type": root_type, "name": "AdoptionProbe"},
            "components": [{"feature": fid} for fid in feature_ids],
            "nodes": [dict(node) for node in nodes],
            "validation": {"required_tests": list(feature_ids)}}


def real_feature_ids() -> list:
    base = template_loader.FEATURES_DIR
    return sorted(name for name in os.listdir(base)
                  if os.path.isdir(os.path.join(base, name)))


def scene_node_types(feature_id: str) -> list:
    """Feature 入口场景（*.tscn）中出现的节点类型（用于声明审计）。"""
    feature_dir = os.path.join(template_loader.FEATURES_DIR, feature_id)
    types = []
    for name in sorted(os.listdir(feature_dir)):
        if not name.endswith(".tscn"):
            continue
        text = open(os.path.join(feature_dir, name), encoding="utf-8").read()
        types.extend(re.findall(r"\[node [^\]]*type=\"([^\"]+)\"", text))
    return types


def run() -> int:
    tmp = tempfile.mkdtemp(prefix="feature_adoption_")
    try:
        features_dir, index_path = write_fixtures(tmp)

        # ---------------- Case 1: 无声明 Feature 保持 [] ----------------
        print("=== Case 1: undeclared feature keeps required=[] ===")
        undeclared = scene_composer.compose(entity_blueprint(["undeclared"]),
                                            out_dir=os.path.join(tmp, "case1_out"),
                                            features_dir=features_dir, index_path=index_path)
        ok("case1: chain still composes", undeclared["ok"] is True,
           str(undeclared.get("failures")))
        ok("case1: Intent.required stays [] (no forced fill)",
           undeclared["scene_intent"]["capabilities"] == {"required": []},
           str(undeclared["scene_intent"].get("capabilities")))
        ok("case1: gate passes and records nothing",
           undeclared["compatibility"]["status"] == "PASS"
           and undeclared["compatibility"]["checked_capabilities"] == [],
           str(undeclared["compatibility"]))

        # ---------------- Case 2: Feature 声明 Node ----------------
        print("=== Case 2: feature declaring Node reaches the Intent ===")
        node_chain = scene_composer.compose(entity_blueprint(["node_only"]),
                                            out_dir=os.path.join(tmp, "case2_out"),
                                            features_dir=features_dir, index_path=index_path)
        ok("case2: Intent.required carries Node",
           node_chain["scene_intent"]["capabilities"] == {"required": ["Node"]},
           str(node_chain["scene_intent"].get("capabilities")))
        ok("case2: gate records Node and passes",
           node_chain["ok"] is True
           and node_chain["compatibility"]["checked_capabilities"] == ["Node"],
           str(node_chain["compatibility"]))

        # ---------------- Case 3: Feature 声明 Sprite + Collision ----------------
        print("=== Case 3: feature declaring Sprite + Collision ===")
        # 声明 Sprite + Collision：计划必须给出证据（Sprite2D / 碰撞体）——Phase 1.8.13
        both_chain = scene_composer.compose(
            scene_blueprint(["sprite_collider"], nodes=[{"type": "Sprite2D", "name": "Body"}]),
            out_dir=os.path.join(tmp, "case3_out"),
            features_dir=features_dir, index_path=index_path)
        ok("case3: Intent.required carries both, in declaration order",
           both_chain["scene_intent"]["capabilities"] == {"required": ["Sprite", "Collision"]},
           str(both_chain["scene_intent"].get("capabilities")))
        ok("case3: gate records both and passes",
           both_chain["ok"] is True
           and both_chain["compatibility"]["checked_capabilities"] == ["Sprite", "Collision"],
           str(both_chain["compatibility"]))
        ok("case3: contract is satisfied by the plan evidence (Sprite2D + body root)",
           both_chain["capability_contract"] == {
               "status": "PASS", "errors": [],
               "checked_capabilities": ["Sprite", "Collision"]},
           str(both_chain.get("capability_contract")))
        no_evidence_out = os.path.join(tmp, "case3_no_evidence")
        no_evidence = scene_composer.compose(
            scene_blueprint(["sprite_collider"], root_type="Node2D",
                            scene_id="adoption_probe_no_evidence"),
            out_dir=no_evidence_out, features_dir=features_dir, index_path=index_path)
        ok("case3: without evidence the chain is BLOCKED by the contract layer",
           no_evidence["ok"] is False
           and no_evidence["failures"] == [
               "Capability Contract: Capability contract failed: Sprite requires "
               "Sprite2D_or_AnimatedSprite2D",
               "Capability Contract: Capability contract failed: Collision requires "
               "CollisionShape2D"],
           str(no_evidence.get("failures")))
        ok("case3: BLOCKED produces zero .tscn",
           not os.path.isdir(no_evidence_out)
           or [f for f in os.listdir(no_evidence_out) if f.endswith(".tscn")] == [])

        # ---------------- Case 4: 多 Feature 去重 ----------------
        print("=== Case 4: multiple features are merged and deduplicated ===")
        merged_chain = scene_composer.compose(
            scene_blueprint(["node_only", "sprite_only"],
                            nodes=[{"type": "Sprite2D", "name": "Body"}]),
            out_dir=os.path.join(tmp, "case4_out"),
            features_dir=features_dir, index_path=index_path)
        ok("case4: union is deduplicated and order-preserving",
           merged_chain["scene_intent"]["capabilities"] == {"required": ["Node", "Sprite"]},
           str(merged_chain["scene_intent"].get("capabilities")))
        ok("case4: the deduplicated union also satisfies the contract layer",
           merged_chain["ok"] is True
           and merged_chain["capability_contract"]["checked_capabilities"] == ["Node", "Sprite"],
           str(merged_chain.get("capability_contract")))
        ok("case4: reader-level merge agrees",
           feature_capabilities.capabilities_for_features(["node_only", "sprite_only"],
                                                          features_dir) == ["Node", "Sprite"])

        # ---------------- Case 5: 非法能力 -> BLOCKED 零产物 ----------------
        print("=== Case 5: unregistered capability blocks the chain ===")
        blocked_out = os.path.join(tmp, "case5_out")
        blocked = scene_composer.compose(entity_blueprint(["unknown_cap"]), out_dir=blocked_out,
                                        features_dir=features_dir, index_path=index_path)
        ok("case5: gate BLOCKED with the capability message",
           blocked["ok"] is False
           and blocked["failures"] == ["Compatibility Gate: Unsupported capability: "
                                       "UnknownCapability"],
           str(blocked.get("failures")))
        ok("case5: zero .tscn produced",
           not os.path.isdir(blocked_out)
           or [f for f in os.listdir(blocked_out) if f.endswith(".tscn")] == [],
           str(os.listdir(blocked_out) if os.path.isdir(blocked_out) else "<no dir>"))

        # ---------------- Case 6: 真实链路产物逐字节相同 ----------------
        print("=== Case 6: real generation chain is byte-identical ===")
        binding_path = goldens.write_binding(tmp, goldens.BINDING_SLIME)
        real = scene_composer.compose(copy.deepcopy(goldens.SCENE_BLUEPRINT_SLIME),
                                      out_dir=os.path.join(tmp, "case6_out"),
                                      bindings_path=binding_path)
        ok("case6: real chain still passes", real["ok"] is True, str(real.get("failures")))
        declared = feature_capabilities.capabilities_for_features(goldens.FEATURES)
        ok("case6: real chain carries the migrated declarations",
           real["scene_intent"]["capabilities"] == {"required": declared}
           and real["compatibility"]["checked_capabilities"] == declared,
           str(real["scene_intent"].get("capabilities")))
        ok("case6: generated .tscn byte-identical to the pre-migration baseline",
           open(real["scene_path"], "rb").read() == goldens.GOLDEN_F3.encode("utf-8"),
           os.path.basename(real["scene_path"]))
        intent_document = scene_intent.intent_document(real["scene_intent"])
        generated_gd = generate_scene_test.build_test_source(
            intent_document, template_loader.load_templates(goldens.FEATURES),
            "Scenes/SlimeEnemy.tscn")
        repo_gd = open(os.path.join(PROJECT_ROOT, "Tests", "test_slime_enemy.gd"),
                       encoding="utf-8", newline="").read()
        ok("case6: generated .gd byte-identical to the committed test",
           generated_gd == repo_gd, "%d vs %d chars" % (len(generated_gd), len(repo_gd)))
        # 既有产物回归：仓库蓝图 slime_enemy.yaml + 既有 Binding 重新生成同一个场景，
        # 必须与已提交的 Scenes/SlimeEnemy.tscn 逐字节相同（数据迁移不得改变产物）。
        repo_chain = scene_composer.compose(
            yaml.safe_load(open(os.path.join(PROJECT_ROOT, "slime_enemy.yaml"),
                                encoding="utf-8")),
            out_dir=os.path.join(tmp, "case6_repo_out"),
            bindings_path=os.path.join(DOTAI, "context", "asset_bindings", "slime_enemy.yaml"))
        ok("case6: repo blueprint chain still passes", repo_chain["ok"] is True,
           str(repo_chain.get("failures")))
        repo_scene = open(os.path.join(PROJECT_ROOT, "Scenes", "SlimeEnemy.tscn"), "rb").read()
        ok("case6: regenerated Scenes/SlimeEnemy.tscn is byte-identical to the committed file",
           open(repo_chain["scene_path"], "rb").read() == repo_scene,
           "sha256=%s" % __import__("hashlib").sha256(repo_scene).hexdigest()[:16])

        # ---------------- 附件：真实 Feature 数据审计 ----------------
        print("=== Audit: every real Feature declaration is evidenced and chain-valid ===")
        audit = {}
        for fid in real_feature_ids():
            declared_caps = feature_capabilities.capabilities_for_feature(fid)
            types = scene_node_types(fid)
            meta = feature_capabilities.load_feature_definition(fid) or {}
            usage = str(((meta.get("composition") or {}).get("usage") or ""))
            owns_collision = "CollisionShape2D" in types or "CollisionShape2D" in usage
            audit[fid] = {"declared": declared_caps, "node_types": types,
                          "owns_collision": owns_collision}
            registered = all(capability_registry.is_supported(name) for name in declared_caps)
            ok("audit: %s declares only registered capabilities" % fid, registered,
               str(declared_caps))
            ok("audit: %s declaration matches its own scene/contract evidence" % fid,
               ("Node" in declared_caps)
               and (("Collision" in declared_caps) == owns_collision),
               json.dumps(audit[fid]))
        ok("audit: every real feature declares something (adoption happened)",
           all(audit[fid]["declared"] for fid in audit),
           json.dumps({fid: audit[fid]["declared"] for fid in audit}))

        # 每个真实 Feature 走「Feature → Blueprint → Intent → Gate → Contract」并与其声明一致。
        # 计划证据：声明 Collision 的 Feature 在探针里给一个 CollisionShape2D 节点（Phase 1.8.13）。
        for fid in real_feature_ids():
            declared_caps = audit[fid]["declared"]
            evidence = [{"type": "CollisionShape2D", "name": "ProbeShape"}] \
                if "Collision" in declared_caps else []
            probe = scene_blueprint([fid], nodes=evidence, root_type="Node2D",
                                    scene_id="probe_%s" % fid)
            intent, errors = scene_intent.intent_from_blueprint(copy.deepcopy(probe))
            ok("audit: %s single-feature chain builds an Intent" % fid,
               not errors and intent is not None, str(errors))
            if intent is None:
                continue
            report = compatibility_gate.check_scene_compatibility(intent)
            ok("audit: %s Intent.required equals the Feature declaration" % fid,
               intent.document["capabilities"] == {"required": declared_caps},
               str(intent.document.get("capabilities")))
            ok("audit: %s gate PASS and records the declaration" % fid,
               report.ok and report.checked_capabilities == declared_caps,
               str(report.to_dict()))
            contract = capability_contract_validator.validate_capability_contract(intent)
            ok("audit: %s contract PASS with plan evidence" % fid,
               contract.ok and contract.checked_capabilities == declared_caps,
               str(contract.to_dict()))
            bare = scene_blueprint([fid], root_type="Node2D", scene_id="probe_bare_%s" % fid)
            bare_intent, _ = scene_intent.intent_from_blueprint(copy.deepcopy(bare))
            bare_contract = capability_contract_validator.validate_capability_contract(
                bare_intent)
            ok("audit: %s contract verdict matches its declared requirements" % fid,
               ("Collision" in declared_caps) == (bare_contract.status == "BLOCKED"),
               str((bare_contract.status, bare_contract.errors)))

        # 12 个真实 Feature 的声明汇总（打印迁移结果，便于报告核对）
        print()
        print("Feature capability declarations (Phase 1.8.12):")
        for fid in real_feature_ids():
            print("  %-16s %s" % (fid, audit[fid]["declared"]))
    finally:
        shutil.rmtree(tmp, ignore_errors=True)

    print()
    if _failures:
        print("FAIL: %d failing check(s)" % len(_failures))
        for failure in _failures:
            print("  - " + failure)
        return 1
    print("PASS: all feature capability adoption checks passed")
    return 0


if __name__ == "__main__":
    sys.exit(run())
