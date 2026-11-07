#!/usr/bin/env python3
"""Phase 1.66：Knowledge-Driven Mutation Candidate 测试。

覆盖：只从已审批知识生成、无行为硬编码、锚点校验、安全约束字段完整、
候选不自动获批、只有 MUTANT_KILLED 入库且仍是 PENDING_REVIEW、
Control/Mutation/Recovery 证据字段（含逐字节恢复与 repo_guard）。

执行链不在这里跑：用注入的假 harness 验证**判定与入库边界**，
真实 harness 执行见 .ai/context/PHASE_1_66_MUTATION_REPORT.md。
"""

from __future__ import annotations

import hashlib
import json
import os
import sys
import tempfile
import types

HERE = os.path.dirname(os.path.abspath(__file__))
LEARNING = os.path.dirname(HERE)
sys.path[:0] = [LEARNING, os.path.join(os.path.dirname(LEARNING), "scene_composer")]

import knowledge_v2  # noqa: E402
import mutation_candidates  # noqa: E402
import paths  # noqa: E402

checks = 0
failures = 0
TMP: list[str] = []
ANCHOR_FILE = "Features/trigger_switch/trigger_switch.gd"
ANCHOR_LINE = 41


def ok(name: str, condition: bool, detail: str = "") -> None:
    global checks, failures
    checks += 1
    if condition:
        print("PASS: %s" % name)
    else:
        failures += 1
        print("FAIL: %s %s" % (name, detail))


def isolate() -> None:
    root = tempfile.mkdtemp(prefix="p166_mutation_")
    TMP.append(root)
    knowledge_v2.BASE = root
    knowledge_v2.RECORDS = os.path.join(root, "records")
    knowledge_v2.CANDIDATES = os.path.join(root, "candidates")
    knowledge_v2.CONFLICTS = os.path.join(root, "conflicts")
    for name in (knowledge_v2.RECORDS, knowledge_v2.CANDIDATES, knowledge_v2.CONFLICTS):
        os.makedirs(name, exist_ok=True)
    mutation_candidates.OUT_PATH = os.path.join(root, "mutation_candidates.json")
    mutation_candidates.EXEC_DIR = os.path.join(root, "mutations")


def spare_behavior(index: int) -> tuple[str, str]:
    """从真实分类表里取一个与主用 Behavior 不同的对象（不写死名单）。"""
    entries = paths.supported_behaviors()
    others = [item for item in entries
              if (item["feature_id"], item["behavior_id"]) != ("trigger_switch", "latch_once")]
    item = others[index % len(others)]
    return item["feature_id"], item["behavior_id"]


def condition(**overrides) -> dict:
    base = {"file": ANCHOR_FILE, "line": ANCHOR_LINE, "function": "on_body_entered",
            "condition": "_triggered", "text": "if _triggered:"}
    base.update(overrides)
    return base


def add_guard_record(*, behavior_id: str = "latch_once", feature_id: str = "trigger_switch",
                     conditions: list[dict] | None = None,
                     knowledge_type: str = "SOURCE_OBSERVATION", key: str = "guards") -> str:
    record = knowledge_v2.make_record(
        feature_id=feature_id, behavior_id=behavior_id, knowledge_type=knowledge_type,
        key=key, content={"conditions": conditions or [condition()]},
        source_references=[{"kind": "SOURCE_REFERENCE", "reference": ANCHOR_FILE,
                            "line": ANCHOR_LINE, "symbol": "on_body_entered",
                            "digest": hashlib.sha256(open(os.path.join(
                                paths.ROOT, ANCHOR_FILE.replace("/", os.sep)), "rb").read())
                            .hexdigest()}],
        contract_version="source-scan", confidence="HIGH", reason="unit fixture")
    return knowledge_v2.add_candidate(record)["knowledge_id"]


class FakeHarness(types.ModuleType):
    def __init__(self, verdict: str):
        super().__init__("harness")
        self.verdict = verdict
        self.calls: list[dict] = []

    def run_mutation(self, entry: dict, options: dict) -> dict:
        self.calls.append({"entry": entry, "options": options})
        run_root = os.path.join(options["runs_root"], options["run_id"])
        os.makedirs(run_root, exist_ok=True)
        return {"verdict": self.verdict,
                "verdict_reason": "unit fixture",
                "run_id": options["run_id"],
                "repo_guard": {"changed": False, "files": 265},
                "recovery": {"restored_byte_for_byte": True, "verified": True},
                "effectiveness": {
                    "control_observation": {"count": 1, "status": "PASS"},
                    "mutant_observation": {"count": 2, "status": "SIGNAL_MISMATCH"}}}


def install(verdict: str) -> FakeHarness:
    fake = FakeHarness(verdict)
    sys.modules["harness"] = fake
    return fake


def main() -> int:
    isolate()
    approved = add_guard_record()
    knowledge_v2.approve(approved, reviewer="phase_1_66_local_review", reason="fixture")

    # 未审批知识不得驱动候选
    spare0 = spare_behavior(0)
    spare1 = spare_behavior(1)
    spare2 = spare_behavior(2)
    spare3 = spare_behavior(3)
    pending = add_guard_record(feature_id=spare0[0], behavior_id=spare0[1])
    # 已撤销知识不得驱动候选
    revoked = add_guard_record(feature_id=spare1[0], behavior_id=spare1[1])
    knowledge_v2.approve(revoked, reviewer="phase_1_66_local_review", reason="fixture")
    knowledge_v2.revoke(revoked, reviewer="phase_1_66_local_review", reason="fixture")
    # 非守卫知识 / 非 SOURCE_OBSERVATION 不得驱动候选
    other_type = add_guard_record(feature_id=spare2[0], behavior_id=spare2[1],
                                  knowledge_type="UNKNOWN")
    knowledge_v2.approve(other_type, reviewer="phase_1_66_local_review", reason="fixture")
    other_key = add_guard_record(feature_id=spare3[0], behavior_id=spare3[1],
                                 key="entry_points")
    knowledge_v2.approve(other_key, reviewer="phase_1_66_local_review", reason="fixture")

    document = mutation_candidates.generate()
    candidates = document["candidates"]
    behaviors = {item["behavior_id"] for item in candidates}
    ok("M1: only APPROVED guard knowledge drives candidates",
       behaviors == {"latch_once"}, str(sorted(behaviors)))
    ok("M2: candidate ids and content come from records (no behavior allowlist)",
       all(item["mutation_candidate_id"].startswith("mc-") and
           item["knowledge_refs"] == [approved] for item in candidates))
    ok("M3: anchor validation is read-only and VALID", 
       all(item["anchor_validation"]["status"] == "VALID" for item in candidates),
       str([item["anchor_validation"] for item in candidates]))
    ok("M4: replacement disables exactly the guard",
       all(item["replacement"].strip() == "if false:" and
           item["anchor"].strip() == "if _triggered:" for item in candidates))
    ok("M5: safety constraints cover isolation, restore and repo guard",
       all(any("require_inside" in text for text in item["safety_constraints"]) and
           any("逐字节恢复" in text for text in item["safety_constraints"]) and
           any("repo_guard" in text for text in item["safety_constraints"])
           for item in candidates))
    ok("M6: candidates are never pre-approved",
       all(item["approval_status"] in ("PENDING_APPROVAL", "EXISTING_CATALOG")
           for item in candidates))
    ok("M7: unexecuted candidate carries no verdict or knowledge id",
       all(item["execution"] == {} and not item.get("knowledge_id")
           for item in candidates))

    stable = mutation_candidates.generate()["candidates"][0]["mutation_candidate_id"]
    ok("M8: candidate id is deterministic", stable == candidates[0]["mutation_candidate_id"])

    # 非 `if ...:` 锚点、越界路径、不存在的文件都不得成为候选
    knowledge_v2.BASE = os.path.join(TMP[-1], "edge")
    for name in ("records", "candidates", "conflicts"):
        os.makedirs(os.path.join(knowledge_v2.BASE, name), exist_ok=True)
    knowledge_v2.RECORDS = os.path.join(knowledge_v2.BASE, "records")
    knowledge_v2.CANDIDATES = os.path.join(knowledge_v2.BASE, "candidates")
    knowledge_v2.CONFLICTS = os.path.join(knowledge_v2.BASE, "conflicts")
    edge = add_guard_record(conditions=[
        condition(line=1),                                   # 不是 if 守卫
        condition(file="tools/../../secrets.gd"),            # 不在 Features/
        condition(file="Features/does_not_exist.gd"),        # 文件不存在
        condition(line=9999),                                # 行号越界
    ])
    knowledge_v2.approve(edge, reviewer="phase_1_66_local_review", reason="fixture")
    edge_document = mutation_candidates.generate()
    ok("M9: non-guard, out-of-scope, missing or out-of-range anchors produce no candidate",
       edge_document["candidates"] == [], str(edge_document["summary"]))
    mutation_candidates.OUT_PATH = os.path.join(TMP[-1], "mutation_candidates.json")
    mutation_candidates.EXEC_DIR = os.path.join(TMP[-1], "mutations")

    # SURVIVED 不得入库
    isolate()
    survived_record = add_guard_record()
    knowledge_v2.approve(survived_record, reviewer="phase_1_66_local_review", reason="fixture")
    candidate_id = mutation_candidates.generate()["candidates"][0]["mutation_candidate_id"]
    before = len(knowledge_v2.all_records())
    install("SURVIVED")
    survived = mutation_candidates.execute(candidate_id)
    ok("M10: SURVIVED is recorded but never becomes knowledge",
       survived["execution"]["verdict"] == "SURVIVED" and
       len(knowledge_v2.all_records()) == before and not survived.get("knowledge_id"),
       str(survived["execution"]))
    ok("M11: SURVIVED keeps recovery evidence",
       survived["execution"]["restored_byte_for_byte"] is True and
       survived["execution"]["repo_guard"]["changed"] is False)

    # KILLED 入库，但仍 PENDING_REVIEW，且带 Run/Artifact/Control/Mutant
    isolate()
    starting = add_guard_record()
    knowledge_v2.approve(starting, reviewer="phase_1_66_local_review", reason="fixture")
    candidate = mutation_candidates.generate()["candidates"][0]
    fake = install("MUTANT_KILLED")
    killed = mutation_candidates.execute(candidate["mutation_candidate_id"])
    record = knowledge_v2.get(killed.get("knowledge_id") or "")
    ok("M12: KILLED creates a PENDING_REVIEW MUTATION_OBSERVATION",
       record is not None and record["knowledge_type"] == "MUTATION_OBSERVATION" and
       record["verification_status"] == "PENDING_REVIEW" and
       record["mutation_verdict"] == "MUTANT_KILLED",
       str(record and (record["knowledge_type"], record["verification_status"])))
    ok("M13: mutation knowledge references a real artifact with matching digest",
       bool(record) and all(reference["kind"] == "MUTATION_REFERENCE" and
                            os.path.isfile(os.path.join(paths.ROOT, reference["reference"])) and
                            reference["digest"] == hashlib.sha256(open(os.path.join(
                                paths.ROOT, reference["reference"]), "rb").read()).hexdigest()
                            for reference in record["source_references"]))
    ok("M14: mutation knowledge records run id and both observations",
       bool(record) and record["run_id"] == killed["execution"]["run_id"] and
       record["content"]["control"]["count"] == 1 and
       record["content"]["mutant"]["count"] == 2)
    ok("M15: execution goes through the existing harness with a unique run id",
       len(fake.calls) == 1 and fake.calls[0]["options"]["run_id"].startswith("p166-") and
       fake.calls[0]["entry"]["operator"] == "replace_exact")
    ok("M16: executed candidate is marked EXECUTED and keeps its report path",
       killed["approval_status"] == "EXECUTED" and
       os.path.isfile(os.path.join(paths.ROOT, killed["execution"]["report"])))

    print("\n===== test_mutation_candidates: %d checks, %d failures =====" % (checks, failures))
    return 1 if failures else 0


if __name__ == "__main__":
    raise SystemExit(main())
