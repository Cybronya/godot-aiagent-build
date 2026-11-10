#!/usr/bin/env python3
"""Phase 1.58 测试 fixture：用**真实契约**构造行为证据包与执行产物。

不是手工拼 JSON：期望项来自 `Features/*/template.yaml#behavior`（`build_contracts`），
观测值按契约要求构造，`result.json` 按探针真实结构落盘并写入内容摘要，证据包用
`fbe.bundle_digest` 计算完整性哈希。这样 Validator 的交叉验证能真正通过，测试
检验的是 Adapter / Evaluation 的判定，而不是「fixture 能不能过校验」。

被 `test_evidence_adapter.py` 与 `test_evidence_eval.py` 共用（文件名不以 test_ 开头，
`run_tests.py` 不会把它当测试执行）。
"""

from __future__ import annotations

import hashlib
import json
import os
import sys
from datetime import datetime, timedelta, timezone

_HERE = os.path.dirname(os.path.abspath(__file__))
EVAL_DIR = os.path.dirname(_HERE)
TOOLS_DIR = os.path.dirname(EVAL_DIR)
PROJECT_ROOT = os.path.dirname(os.path.dirname(TOOLS_DIR))
FEATURES = os.path.join(PROJECT_ROOT, "Features")
SCENE_COMPOSER = os.path.join(TOOLS_DIR, "scene_composer")
VALIDATOR_DIR = os.path.join(TOOLS_DIR, "validator")

for _path in (SCENE_COMPOSER, TOOLS_DIR, VALIDATOR_DIR):
    if _path not in sys.path:
        sys.path.insert(0, _path)

import behavior_protocol                                          # noqa: E402
import feature_behavior_evidence as fbe                           # noqa: E402

PROTOCOL = behavior_protocol.load_protocol()
PROTOCOL_SHA = fbe._sha256_file(behavior_protocol.PROTOCOL_PATH)


def iso(minutes_ago: float = 0.0) -> str:
    return (datetime.now(timezone.utc) - timedelta(minutes=minutes_ago)) \
        .strftime("%Y-%m-%dT%H:%M:%SZ")


def sha256_file(path: str) -> str:
    with open(path, "rb") as handle:
        return hashlib.sha256(handle.read()).hexdigest()


def contracts_of(feature: str) -> list:
    contracts, _reports = fbe.build_contracts(feature, FEATURES, protocol=PROTOCOL)
    return contracts


def feature_pairs(features) -> list:
    """[(feature, behavior), ...]：枚举这些 Feature 声明的**全部**行为。

    证据必须覆盖被测 Feature 的全部契约行为，否则 Validator 会（正确地）报
    `behavior_uncovered` → INCOMPLETE；用全部行为构造 fixture 才能拿到干净的 PASS。
    """
    return [(feature, contract["behavior"])
            for feature in features
            for contract in contracts_of(feature)]


def contract_of(feature: str, behavior: str) -> dict:
    for contract in contracts_of(feature):
        if contract["behavior"] == behavior:
            return contract
    raise KeyError("%s/%s is not a declared behavior" % (feature, behavior))


def satisfying_observation(entry: dict, observed=None) -> dict:
    item = {"check": entry["check"], "target": entry.get("target", "."),
            "entry": entry.get("entry", ""), "status": "PASS",
            "first_observed_frame": 0, "observed_args": []}
    if observed is not None:
        item["observed"] = observed
    elif entry["check"] == "signal":
        item["observed"] = int(entry.get("count", 0))
        item["observed_args"] = list(entry.get("last_args") or [])
    elif "equals" in entry:
        item["observed"] = entry["equals"]
    elif entry.get("min") is not None:
        item["observed"] = entry["min"]
    else:
        item["observed"] = entry.get("max")
    return item


def write_artifacts(record: dict, contract: dict, artifact_root: str,
                    status: str = "PASS") -> None:
    """为记录写与探针一致的 result.json（每次重放一份），回填路径与摘要。"""
    base = "%s-%s" % (record["feature"], record["behavior"])
    actions = [{"type": item.get("type"), "params": item.get("params") or {},
                "executed": True} for item in contract.get("actions") or []]
    paths, digests = {}, {}
    for index in range(1, int(record.get("replay_count") or 2) + 1):
        run_id = "%s-r%d" % (record.get("run_id") or base, index)
        directory = os.path.join(artifact_root, run_id)
        os.makedirs(directory, exist_ok=True)
        payload = {"run_id": run_id, "replay_index": index,
                   "feature": record["feature"], "behavior": record["behavior"],
                   "status": status, "action_executed": True,
                   "actions": actions, "checks": record["actual"]}
        path = os.path.join(directory, "result.json")
        with open(path, "w", encoding="utf-8", newline="\n") as handle:
            json.dump(payload, handle, ensure_ascii=False, indent=2, sort_keys=True)
        paths[run_id] = {"contract": os.path.join(directory, "contract.json"),
                         "result": path}
        digests[run_id] = {"result": sha256_file(path)}
    record["evidence_paths"] = paths
    record["artifact_digests"] = digests


def behavior_record(feature: str, behavior: str, artifact_root: str,
                    status: str = "PASS", observed_overrides=None,
                    omit_artifacts: bool = False, legacy: bool = False,
                    run_id_suffix: str = "") -> dict:
    contract = contract_of(feature, behavior)
    overrides = observed_overrides or {}
    actual = []
    for entry in contract["expected"]:
        key = (entry["check"], entry.get("target", "."))
        actual.append(satisfying_observation(entry, overrides.get(key)))
    run_id = "%s-%s%s" % (feature, behavior, run_id_suffix)
    record = {
        "feature": feature,
        "behavior": behavior,
        "action_id": (contract.get("actions") or [{}])[0].get("type", ""),
        "action_executed": True,
        "replay_count": 2,
        "replay_consistent": True,
        "status": status,
        "reason": "ok" if status == "PASS" else "stubbed",
        "detail": "",
        "evidence": "godot_behavior",
        "run_id": run_id,
        "actual": actual,
    }
    if not legacy:
        record["expected"] = [dict(entry) for entry in contract["expected"]]
        if not omit_artifacts:
            write_artifacts(record, contract, artifact_root, status=status)
        else:
            record["evidence_paths"] = {}
            record["artifact_digests"] = {}
    return record


def build_bundle(features: list, bundle_id: str = "bundle-test",
                 level: str = "L4", protocol_version=None, protocol_sha="__current__",
                 generated_at="__now__", resign: bool = True) -> dict:
    document = {
        "schema": fbe.BUNDLE_SCHEMA,
        "schema_version": fbe.BUNDLE_SCHEMA_VERSION,
        "bundle_id": bundle_id,
        "generated_at": iso() if generated_at == "__now__" else generated_at,
        "git_head": "test-head",
        "tool": {"module": "feature_behavior_evidence", "module_version": 1},
        "protocol": {"protocol_version": PROTOCOL.version if protocol_version is None
                     else protocol_version,
                     "sha256": PROTOCOL_SHA if protocol_sha == "__current__" else protocol_sha},
        "evidence_level": level,
        "summary": {},
        "features": features,
    }
    if resign:
        resign_bundle(document)
    return document


def resign_bundle(document: dict) -> dict:
    document["integrity"] = {"algorithm": "sha256",
                             "payload_sha256": fbe.bundle_digest(document)}
    return document


def write_bundle(directory: str, document: dict, filename: str = "") -> str:
    os.makedirs(directory, exist_ok=True)
    name = filename or ("%s.json" % document.get("bundle_id", "bundle"))
    path = os.path.join(directory, name)
    with open(path, "w", encoding="utf-8", newline="\n") as handle:
        json.dump(document, handle, ensure_ascii=False, indent=2, sort_keys=True)
        handle.write("\n")
    return path


def make_evidence_dir(root: str, pairs, artifact_root: str = "", bundle_id="bundle-test",
                      **record_kwargs) -> tuple:
    """[(feature, behavior), ...] -> (evidence_dir, artifact_root)。"""
    evidence_dir = os.path.join(root, "bundles")
    artifact_root = artifact_root or os.path.join(root, "artifacts")
    grouped: dict = {}
    order: list = []
    for feature, behavior in pairs:
        record = behavior_record(feature, behavior, artifact_root, **record_kwargs)
        if feature not in grouped:
            grouped[feature] = {"feature": feature, "evidence_level": "L4", "behaviors": []}
            order.append(feature)
        grouped[feature]["behaviors"].append(record)
    document = build_bundle([grouped[name] for name in order], bundle_id=bundle_id)
    write_bundle(evidence_dir, document)
    return evidence_dir, artifact_root
