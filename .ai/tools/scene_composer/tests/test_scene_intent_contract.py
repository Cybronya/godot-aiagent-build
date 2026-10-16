#!/usr/bin/env python3
"""Scene Intent 契约测试（Phase 1.8.5）

保护 .ai/context/scene_composer_schema.yaml 的 Scene Intent 契约不被静默漂移：

    1. Scene Intent 是一等概念，字段状态完备 —— 每个文档块都在
       internal_to_document 中有 CURRENT / PLANNED 归属。
    2. provenance 只读携带规则存在且未被削弱（禁止计算 / 升级 / 覆盖 / 发明）。
    3. 单一事实源 —— Scene Intent 只在本契约中定义（禁止第二事实源）。
    4. CONTRACT_INDEX.scene_composition 与契约版本一致，且指向同一文件。

本测试只读 YAML，不生成 .tscn，不启动 Godot，不修改项目。

用法:
    python .ai/tools/scene_composer/tests/test_scene_intent_contract.py
全部通过输出 PASS 并退出 0；任一失败输出 FAIL 并退出 1。
"""

import glob
import os
import sys

try:
    import yaml
except ImportError:  # pragma: no cover
    print("FAIL: PyYAML is required. Install with: pip install pyyaml", file=sys.stderr)
    raise SystemExit(2)

_HERE = os.path.dirname(os.path.abspath(__file__))          # .ai/tools/scene_composer/tests
DOTAI = os.path.dirname(os.path.dirname(os.path.dirname(_HERE)))   # .ai
CONTEXT_DIR = os.path.join(DOTAI, "context")
CONTRACT_PATH = os.path.join(CONTEXT_DIR, "scene_composer_schema.yaml")
INDEX_PATH = os.path.join(CONTEXT_DIR, "CONTRACT_INDEX.yaml")

REQUIRED_PROVENANCE_FIELDS = {"resolved_from", "compatibility", "confidence", "runners_up", "note"}
REQUIRED_FORBIDDEN = {"asset path", "role", "compatibility", "resolved_from", "confidence", "top1"}
REQUIRED_GAP_IDS = {
    "entity_blueprint_nodes_dropped",
    "compatibility_not_gated_at_scene_layer",
    "scene_intent_persistence_undefined",
    "bind_assets_auto_inference_entry",
}
# 文档块 -> 必须覆盖的 Scene Intent 结构键
REQUIRED_STRUCTURE_KEYS = ["scene", "root", "components", "nodes", "resources",
                           "scripts", "animations", "validation", "metadata"]

_failures = []


def ok(name: str, condition: bool, detail: str = "") -> None:
    if condition:
        print("PASS: " + name)
    else:
        _failures.append(name + (" | " + detail if detail else ""))
        print("FAIL: " + name + (" | " + detail if detail else ""))


def load(path: str) -> dict:
    with open(path, encoding="utf-8") as handle:
        return yaml.safe_load(handle) or {}


def run() -> int:
    raw = open(CONTRACT_PATH, encoding="utf-8").read()
    contract = load(CONTRACT_PATH)
    index = load(INDEX_PATH)

    # ---- 1. 契约身份与版本 ----
    print("=== 1. Contract identity ===")
    schema = contract.get("schema") or {}
    ok("contract schema.id == scene_composer", schema.get("id") == "scene_composer", repr(schema.get("id")))
    ok("contract schema.version == 2 (Phase 1.8.5)", schema.get("version") == 2, repr(schema.get("version")))
    ok("status vocabulary documented (CURRENT + PLANNED)",
       "CURRENT" in raw and "PLANNED" in raw)

    # ---- 2. Identity 三方区分 ----
    print("=== 2. Identity (Binding / Scene Intent / .tscn) ===")
    identity = contract.get("identity") or {}
    for key in ("binding_document", "scene_intent", "tscn", "rule"):
        ok("identity.%s present" % key, key in identity)
    ok("identity.rule forbids conflation",
       isinstance(identity.get("rule"), str) and "不可混淆" in identity["rule"])

    # ---- 3. Scene Intent 一等概念 ----
    print("=== 3. Scene Intent is first-class ===")
    intent = contract.get("scene_intent")
    ok("scene_intent section exists", isinstance(intent, dict))
    if not isinstance(intent, dict):
        return _summary()
    ok("scene_intent.document == scene_intent", intent.get("document") == "scene_intent")
    ok("scene_intent.version == 1", intent.get("version") == 1, repr(intent.get("version")))
    ok("scene_intent.plan_only is True", intent.get("plan_only") is True)
    ok("scene_intent.not_a_runtime_object is True", intent.get("not_a_runtime_object") is True)

    # ---- 4. 单一事实源 ----
    print("=== 4. Single source of truth ===")
    sst = intent.get("single_source_of_truth") or {}
    ok("no_second_source declared", sst.get("no_second_source") is True)
    ok("binding_fields authority points to asset_binding_schema.yaml",
       sst.get("binding_fields") == "asset_binding_schema.yaml", repr(sst.get("binding_fields")))
    ok("intent_fields authority points to this contract",
       str(sst.get("intent_fields", "")).startswith("scene_composer_schema.yaml"))
    ok("contract does not redefine a Binding document (no binding/bindings root key)",
       "binding" not in contract and "bindings" not in contract,
       str([k for k in contract.keys() if k in ("binding", "bindings")]))
    declaring = [os.path.basename(p) for p in sorted(glob.glob(os.path.join(CONTEXT_DIR, "*_schema.yaml")))
                 if isinstance(load(p), dict) and "scene_intent" in load(p)]
    ok("only this contract declares a scene_intent section",
       declaring == ["scene_composer_schema.yaml"], str(declaring))

    # ---- 5. 字段状态完备（CURRENT / PLANNED 全覆盖） ----
    print("=== 5. Field status completeness ===")
    i2d = intent.get("internal_to_document") or {}
    rows = i2d.get("mapping") or []
    ok("internal_to_document.mapping non-empty", bool(rows))
    bad_rows = [r for r in rows
                if not isinstance(r, dict) or r.get("status") not in ("CURRENT", "PLANNED")
                or not r.get("document") or not r.get("internal")]
    ok("every mapping row has document/internal/status in {CURRENT,PLANNED}",
       not bad_rows, str(bad_rows))
    structure = intent.get("structure") or {}
    declared = {str(r.get("document", "")).split(".")[0].split("[")[0]
                for r in rows if isinstance(r, dict)}
    uncovered = [k for k in REQUIRED_STRUCTURE_KEYS if k not in structure or k not in declared]
    ok("every structure block is mapped with a status", not uncovered, str(uncovered))
    ok("mapping covers components[].node status (no silent CURRENT claim)",
       any(str(r.get("document", "")).startswith("components[].node") for r in rows))
    ok("mapping states metadata is not yet produced",
       any(str(r.get("document", "")) == "metadata"
           and r.get("status") == "PLANNED" for r in rows))

    # ---- 6. Provenance 只读携带 ----
    print("=== 6. Provenance (carry-only) ===")
    prov = intent.get("provenance") or {}
    ok("provenance.fields == the 5 Binding provenance fields",
       set(prov.get("fields") or []) == REQUIRED_PROVENANCE_FIELDS, repr(prov.get("fields")))
    ok("provenance field authority is the Binding contract",
       str(prov.get("field_authority", "")).startswith("asset_binding_schema.yaml"),
       repr(prov.get("field_authority")))
    must_not = prov.get("rules", {}).get("must_not") or []
    must_not_text = " ".join(str(x) for x in must_not)
    for verb in ("计算", "升级", "覆盖", "发明"):
        ok("provenance forbids %s" % verb, verb in must_not_text, must_not_text[:80])
    may = prov.get("rules", {}).get("may") or []
    ok("provenance allows verbatim carry", "原样携带" in " ".join(str(x) for x in may))
    ok("provenance ships correct + incorrect examples",
       bool(prov.get("correct_example")) and bool(prov.get("incorrect_example")))
    ok("provenance status is PLANNED (not implemented yet)",
       prov.get("status") == "PLANNED", repr(prov.get("status")))

    # ---- 7. Scene Intent 规则 ----
    print("=== 7. Scene Intent rules ===")
    rules = intent.get("rules") or {}
    forbidden_text = " ".join(str(x) for x in (rules.get("forbidden") or []))
    for token in REQUIRED_FORBIDDEN:
        ok("forbidden list covers %r" % token, token in forbidden_text)
    allowed_text = " ".join(str(x) for x in (rules.get("allowed") or []))
    for token in ("node hierarchy", "resource connection plan", "ext_resource planning"):
        ok("allowed list covers %r" % token, token in allowed_text)

    # ---- 8. Input contract 仍指向 Binding ----
    print("=== 8. Input contract ===")
    inp = contract.get("input") or {}
    ok("input.schema_ref == asset_binding_schema.yaml",
       inp.get("schema_ref") == "asset_binding_schema.yaml", repr(inp.get("schema_ref")))
    ok("input.schema_version == 2", inp.get("schema_version") == 2, repr(inp.get("schema_version")))
    ok("provenance_only fields match provenance design",
       set((inp.get("provenance_only") or {}).get("fields") or []) == REQUIRED_PROVENANCE_FIELDS)
    ok("consumed fields are declared as binding.* references",
       all(str(x).startswith("binding.") for x in (inp.get("consumed") or [])),
       str(inp.get("consumed")))

    # ---- 9. Known gaps ----
    print("=== 9. Known gaps ===")
    gaps = contract.get("known_gaps") or []
    gap_ids = {g.get("id") for g in gaps if isinstance(g, dict)}
    ok("required gap ids present", REQUIRED_GAP_IDS <= gap_ids,
       "missing=%s" % sorted(REQUIRED_GAP_IDS - gap_ids))
    ok("every gap carries a status", all(isinstance(g, dict) and g.get("status") for g in gaps))
    ok("persistence gap marked decided_in_1_8_5",
       any(g.get("id") == "scene_intent_persistence_undefined"
           and g.get("status") == "decided_in_1_8_5" for g in gaps))
    ok("nodes-dropped gap carries target_behavior",
       any(g.get("id") == "entity_blueprint_nodes_dropped" and g.get("target_behavior")
           for g in gaps))

    # ---- 10. Persistence 决策 ----
    print("=== 10. Persistence decision ===")
    pers = intent.get("persistence") or {}
    ok("persistence.current == memory_only", pers.get("current") == "memory_only",
       repr(pers.get("current")))
    ok("persistence reason documented", bool(pers.get("reason")))
    ok("persistence upgrade_condition documented", bool(pers.get("upgrade_condition")))
    ok("persistence rejects both dir and .tmp alternatives",
       len(pers.get("rejected_alternatives") or []) >= 2)
    ok("persistence grants no write authority", pers.get("write_authority") == "none",
       repr(pers.get("write_authority")))

    # ---- 11. CONTRACT_INDEX 一致 ----
    print("=== 11. CONTRACT_INDEX consistency ===")
    entry = (index.get("scene_composition") or {})
    oc = entry.get("output_contract") or {}
    ok("index output == scene_intent", entry.get("output") == "scene_intent", repr(entry.get("output")))
    ok("index boundary_contract points to this contract file",
       entry.get("boundary_contract") == "scene_composer_schema.yaml")
    ok("index boundary_contract_version == contract schema.version",
       entry.get("boundary_contract_version") == schema.get("version"),
       "%r vs %r" % (entry.get("boundary_contract_version"), schema.get("version")))
    ok("index output_contract.schema is the same single file",
       oc.get("schema") == "scene_composer_schema.yaml", repr(oc.get("schema")))
    ok("index output_contract.section == scene_intent", oc.get("section") == "scene_intent")
    ok("index output_contract.version == scene_intent.version",
       oc.get("version") == intent.get("version"))
    ok("index output_contract.plan_only is True", oc.get("plan_only") is True)
    ok("index output_contract.persistence matches contract",
       oc.get("persistence") == pers.get("current"), repr(oc.get("persistence")))
    ok("index input is the Binding contract",
       entry.get("input") == "asset_binding_schema.yaml", repr(entry.get("input")))
    ok("index contract_test path exists",
       os.path.isfile(os.path.join(DOTAI, "tools", str(oc.get("contract_test", "")))))
    ok("referenced contract files exist",
       all(os.path.isfile(os.path.join(CONTEXT_DIR, str(entry.get(k, ""))))
           for k in ("schema", "boundary_contract", "input")),
       str({k: entry.get(k) for k in ("schema", "boundary_contract", "input")}))

    return _summary()


def _summary() -> int:
    print()
    if _failures:
        print("FAIL: %d failing check(s)" % len(_failures))
        for failure in _failures:
            print("  - " + failure)
        return 1
    print("PASS: all scene intent contract checks passed")
    return 0


if __name__ == "__main__":
    sys.exit(run())
