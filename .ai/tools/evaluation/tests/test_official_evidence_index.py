#!/usr/bin/env python3
"""Phase 1.68.3：Official Evidence Index 身份与重复扫描测试（不启动 Godot）。"""

from __future__ import annotations

import json
import os
import sys
import tempfile

HERE = os.path.dirname(os.path.abspath(__file__))
EVALUATION = os.path.dirname(HERE)
TOOLS = os.path.dirname(EVALUATION)
sys.path[:0] = [EVALUATION, TOOLS, os.path.join(TOOLS, "validator"),
                os.path.join(TOOLS, "scene_composer"),
                os.path.join(TOOLS, "learning")]

import check_behavior_evidence as cbe  # noqa: E402
import feature_behavior_evidence as fbe  # noqa: E402
import scenario_run as run  # noqa: E402

checks = 0
failures = 0


def ok(name: str, condition: bool, detail: str = "") -> None:
    global checks, failures
    checks += 1
    if condition:
        print("PASS: %s" % name)
    else:
        failures += 1
        print("FAIL: %s %s" % (name, detail))


def make_bundle(directory: str, name: str, *, bundle_id: str = "",
                behavior: str = "openable_door/open", official: bool = True,
                observed: bool = True) -> str:
    bundle_id = bundle_id or name.replace("-bundle.json", "")
    feature_id, behavior_id = behavior.split("/", 1)
    document = {
        "schema": fbe.BUNDLE_SCHEMA, "schema_version": fbe.BUNDLE_SCHEMA_VERSION,
        "bundle_id": bundle_id, "generated_at": "2026-11-09T00:00:00Z",
        "protocol": {"protocol_version": "fixture"},
        "evidence_level": fbe.EVIDENCE_LEVEL,
        "features": [{"feature": feature_id, "behaviors": [{
            "feature": feature_id, "behavior": behavior_id,
            "status": "PASS", "evidence": fbe.EVIDENCE_BEHAVIOR,
            "action_executed": True, "replay_count": 2, "replay_consistent": True,
            "actual": [{"check": "door.is_open", "target": ".",
                        "observed": observed, "observed_args": []}],
        }]}],
    }
    if official:
        document["official_contract"] = {
            "schema": "official_contract_execution", "schema_version": 1,
            "kind": "OFFICIAL_CONTRACT", "behavior": behavior,
            "feature_id": feature_id, "behavior_id": behavior_id,
            "run_id": "run-" + bundle_id,
        }
    document["integrity"] = {"algorithm": "sha256",
                             "payload_sha256": fbe.bundle_digest(document)}
    path = os.path.join(directory, name)
    with open(path, "w", encoding="utf-8") as handle:
        json.dump(document, handle, ensure_ascii=False, indent=2, sort_keys=True)
    return path


def results_for(*paths: str) -> dict:
    records = []
    for path in paths:
        with open(path, encoding="utf-8") as handle:
            document = json.load(handle)
        block = document.get("official_contract") or {}
        records.append({
            "feature_id": block.get("feature_id"), "behavior_id": block.get("behavior_id"),
            "behavior": block.get("behavior"), "run_id": block.get("run_id"),
            "bundle_path": path,
        })
    return {"schema": "official_contract_execution_index", "schema_version": 1,
            "results": records}


def write_index(directory: str, document: dict) -> str:
    path = os.path.join(directory, cbe.EVIDENCE_INDEX_NAME)
    with open(path, "w", encoding="utf-8") as handle:
        json.dump(document, handle, ensure_ascii=False, indent=2, sort_keys=True)
    return path


def main() -> int:
    tmp_root = os.path.join(os.path.dirname(TOOLS), "tmp")
    os.makedirs(tmp_root, exist_ok=True)
    with tempfile.TemporaryDirectory(dir=tmp_root) as tmp:
        old = make_bundle(tmp, "old-bundle.json", bundle_id="old", observed=False)
        new = make_bundle(tmp, "new-bundle.json", bundle_id="new", observed=True)
        index = run.build_official_evidence_index(tmp, results_for(new), tmp)
        ok("I1: one active bundle is selected", len(index["active"]) == 1 and
           index["active"][0]["bundle_id"] == "new" and not index["conflicts"])
        ok("I2: historical bundle is superseded, not deleted",
           len(index["superseded"]) == 1 and index["superseded"][0]["bundle_id"] == "old"
           and os.path.isfile(old))
        write_index(tmp, index)
        documents, errors, fatal = cbe._bundle_documents(tmp)
        ok("I3: validator consumes only the active bundle",
           len(documents) == 1 and documents[0]["index_entry"]["bundle_id"] == "new"
           and not errors and not fatal)

        twice = run.build_official_evidence_index(tmp, results_for(new), tmp)
        ok("I4: rebuilding the index is idempotent",
           twice["active"] == index["active"] and twice["superseded"] == index["superseded"]
           and not twice["conflicts"])

        duplicate = json.loads(json.dumps(index))
        duplicate["active"].append(dict(duplicate["active"][0]))
        write_index(tmp, duplicate)
        duplicated_docs, duplicated_errors, duplicated_fatal = cbe._bundle_documents(tmp)
        ok("I5: repeated scan of the same active file is not a conflict",
           len(duplicated_docs) == 1 and not duplicated_errors and not duplicated_fatal)

        write_index(tmp, index)
        missing = json.loads(json.dumps(index))
        missing["active"][0]["bundle_path"] = "missing-bundle.json"
        write_index(tmp, missing)
        _, missing_errors, missing_fatal = cbe._bundle_documents(tmp)
        ok("I6: index pointing at a missing file is fatal",
           missing_fatal and any("missing bundle" in item for item in missing_errors))

        write_index(tmp, index)
        unindexed = make_bundle(tmp, "unindexed-bundle.json", bundle_id="unindexed")
        _, unindexed_errors, unindexed_fatal = cbe._bundle_documents(tmp)
        ok("I7: bundle present but unregistered is fatal",
           unindexed_fatal and any("not registered" in item for item in unindexed_errors))
        os.remove(unindexed)
        write_index(tmp, index)

        same_id_a = make_bundle(tmp, "same-a-bundle.json", bundle_id="same",
                                behavior="collect_pickup/collect_on_contact", observed=False)
        same_id_b = make_bundle(tmp, "same-b-bundle.json", bundle_id="same",
                                behavior="collect_pickup/collect_on_contact", observed=True)
        conflict_index = run.build_official_evidence_index(
            tmp, results_for(new, same_id_b), tmp)
        ok("I8: same bundle id with different content is a conflict",
           len(conflict_index["conflicts"]) == 1 and
           "same bundle id" in conflict_index["conflicts"][0]["reason"])
        write_index(tmp, conflict_index)
        _, conflict_errors, conflict_fatal = cbe._bundle_documents(tmp)
        ok("I9: validator refuses an identity conflict",
           conflict_fatal and any("conflict" in item for item in conflict_errors))
        os.remove(same_id_a)
        os.remove(same_id_b)

        scenario = make_bundle(tmp, "scenario-bundle.json", bundle_id="scenario",
                               official=False)
        scenario_index = run.build_official_evidence_index(tmp, results_for(new), tmp)
        ok("I10: a non-official bundle is not silently indexed",
           any(item["bundle_path"] == "scenario-bundle.json"
               for item in scenario_index["unindexed"]))
        write_index(tmp, scenario_index)
        _, scenario_errors, scenario_fatal = cbe._bundle_documents(tmp)
        ok("I11: scenario evidence cannot enter the official index",
           scenario_fatal and any("not registered" in item or "not an official" in item
                                  for item in scenario_errors))
        os.remove(scenario)
        write_index(tmp, index)

        third = make_bundle(tmp, "third-bundle.json", bundle_id="third",
                            behavior="contact_damage/damage_on_contact")
        different_index = run.build_official_evidence_index(
            tmp, results_for(new, third), tmp)
        ok("I12: different bundles keep distinct identities",
           len(different_index["active"]) == 2 and
           {item["bundle_id"] for item in different_index["active"]} ==
           {"new", "third"} and
           different_index["summary"]["superseded"] == 1)

    print("\n===== test_official_evidence_index: %d checks, %d failures ====="
          % (checks, failures))
    return 1 if failures else 0


if __name__ == "__main__":
    raise SystemExit(main())
