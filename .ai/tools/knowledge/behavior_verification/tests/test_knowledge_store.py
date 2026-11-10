#!/usr/bin/env python3
"""Phase 1.64：Behavior Verification Knowledge store 测试（手写 ok() harness）。

覆盖：来源类型强制、历史不覆盖、事实不得被静默丢弃、契约版本漂移拒绝、
统计口径、以及「推测不能写成已验证事实」。
"""
from __future__ import annotations

import json
import os
import shutil
import sys
import tempfile

HERE = os.path.dirname(os.path.abspath(__file__))
MODULE_DIR = os.path.dirname(HERE)
sys.path.insert(0, MODULE_DIR)

import store  # noqa: E402

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


def base_record(**overrides) -> dict:
    record = {
        "feature_id": "health",
        "behavior_id": "damage",
        "contract_version": "abc123",
        "behavior_category": "A",
        "implementation_references": ["Features/health/health.gd"],
        "dependency_references": ["health"],
        "facts": [{
            "claim": "damage 后 current 减少",
            "source_type": "CONTRACT_FACT",
            "source_ref": "Features/health/template.yaml#behavior=damage.expected",
        }],
        "last_verified_run_id": "run-1",
    }
    record.update(overrides)
    return record


def main() -> int:
    root = tempfile.mkdtemp(prefix="p164_knowledge_")
    try:
        # K1 合法记录
        ok("K1: valid record passes validation", store.validate(base_record()) == [])

        # K2 未知来源类型被拒
        bad = base_record(facts=[{"claim": "x", "source_type": "GUESS",
                                  "source_ref": "somewhere"}])
        problems = store.validate(bad)
        ok("K2: unknown source_type rejected",
           any("source_type invalid" in p for p in problems), str(problems))

        # K3 缺 source_ref / claim 被拒
        bad = base_record(facts=[{"claim": "", "source_type": "INFERENCE",
                                  "source_ref": ""}])
        problems = store.validate(bad)
        ok("K3: empty claim and empty source_ref rejected",
           any("claim empty" in p for p in problems)
           and any("source_ref empty" in p for p in problems), str(problems))

        # K4 CONTRACT_FACT 必须指向契约或 binding
        bad = base_record(facts=[{"claim": "x", "source_type": "CONTRACT_FACT",
                                  "source_ref": ".ai/tmp/notes.txt"}])
        problems = store.validate(bad)
        ok("K4: CONTRACT_FACT must reference Features/ or binding:",
           any("must reference" in p for p in problems), str(problems))

        # K5 写入 + updated_at 由 store 填
        saved = store.save(base_record(), change_reason="K5 first write", root=root)
        ok("K5: save writes updated_at", bool(saved.get("updated_at")))
        ok("K5b: file exists",
           os.path.isfile(store.record_path("health", "damage", root)))
        ok("K5c: no history before second write",
           not os.path.isfile(store.history_path("health", "damage", root)))

        # K6 追加事实 → 旧记录进 history，最新记录保留全部事实
        second = base_record()
        second["facts"] = saved["facts"] + [{
            "claim": "真实证据 EVALUATION VERIFIED_PASS",
            "source_type": "TEST_OBSERVATION",
            "source_ref": ".ai/tmp/p164/batch1/evaluation/x/evidence_report.json",
        }]
        second["last_verified_run_id"] = "run-2"
        store.save(second, change_reason="K6 append fact", root=root)
        latest = store.load("health", "damage", root)
        ok("K6: latest keeps both facts", len(latest["facts"]) == 2)
        history_file = store.history_path("health", "damage", root)
        ok("K6b: history file created", os.path.isfile(history_file))
        lines = open(history_file, encoding="utf-8").read().strip().split("\n")
        archived = json.loads(lines[-1])
        ok("K6c: history keeps the previous version (1 fact)",
           len(archived["record"]["facts"]) == 1)
        ok("K6d: history records the reason",
           archived.get("change_reason") == "K6 append fact")

        # K7 静默丢弃旧事实被拒
        dropped = base_record()
        dropped["facts"] = [saved["facts"][0]]
        try:
            store.save(dropped, change_reason="K7 drop", root=root)
            ok("K7: silently dropping facts is rejected", False)
        except store.KnowledgeError as exc:
            ok("K7: silently dropping facts is rejected",
               "silently dropped" in str(exc), str(exc))

        # K8 契约版本变化被拒（不得静默升级）
        bumped = base_record(contract_version="def456")
        bumped["facts"] = latest["facts"]
        try:
            store.save(bumped, change_reason="K8 contract drift", root=root)
            ok("K8: contract_version change is rejected", False)
        except store.KnowledgeError as exc:
            ok("K8: contract_version change is rejected",
               "contract_version changed" in str(exc), str(exc))

        # K9 非法记录不落盘
        before = open(store.record_path("health", "damage", root),
                      encoding="utf-8").read()
        try:
            store.save(base_record(behavior_category="Z"), change_reason="K9",
                       root=root)
        except store.KnowledgeError:
            pass
        after = open(store.record_path("health", "damage", root),
                     encoding="utf-8").read()
        ok("K9: invalid record leaves the stored file untouched", before == after)

        # K10 统计口径
        summary = store.summary(root)
        ok("K10: summary counts records", summary["records"] == 1, str(summary))
        ok("K10b: summary counts sources",
           summary["source_distribution"].get("CONTRACT_FACT") == 1
           and summary["source_distribution"].get("TEST_OBSERVATION") == 1,
           str(summary))

        # K11 真实知识库（若已生成）可被校验
        real_root = store.DEFAULT_ROOT
        real_records = []
        if os.path.isdir(real_root):
            for feature in os.listdir(real_root):
                directory = os.path.join(real_root, feature)
                if not os.path.isdir(directory):
                    continue
                for name in os.listdir(directory):
                    if name.endswith(".json"):
                        real_records.append(json.load(
                            open(os.path.join(directory, name), encoding="utf-8")))
        if real_records:
            bad = [(r["feature_id"], r["behavior_id"], store.validate(r))
                   for r in real_records if store.validate(r)]
            ok("K11: every stored knowledge record validates", not bad, str(bad[:3]))
            ok("K11b: every stored record has at least one sourced fact",
               all(r.get("facts") for r in real_records))
        else:
            print("SKIP K11: no stored knowledge records yet")
    finally:
        shutil.rmtree(root, ignore_errors=True)

    print()
    print("===== test_knowledge_store: %d checks, %d failures =====" % (checks, failures))
    return 0 if not failures else 1


if __name__ == "__main__":
    raise SystemExit(main())
