#!/usr/bin/env python3
"""Behavior Evidence 验证阶段测试（Phase 1.56）

被测对象：`.ai/tools/validator/check_behavior_evidence.py`（Validator 的 L4 阶段）。

覆盖矩阵（要求来自 Phase 1.56 第六阶段）：

    P 正向
      P1 合法证据 -> PASS（exit 0）
      P2 多 Feature 合法证据 -> PASS
      P3 单 Feature 限定验证 -> PASS（未请求的 Feature 不参与判定）
      P4 同一 Feature 的多条 behavior 正确关联 -> PASS
      P5 两个 bundle 给出**完全相同**的记录 -> 不冲突，PASS
    N 负向（每条都必须被拒绝，且原因可区分）
      N1  未知 Feature（目标集）            -> FAIL unknown_feature
      N2  未知 Behavior                     -> FAIL unknown_behavior
      N3  跨 Feature 关联（把 A 的观测挂到 B）-> FAIL
      N4  证据目录不存在                    -> INCOMPLETE evidence_unavailable
      N5  证据目录为空                      -> INCOMPLETE no_evidence
      N6  非法 JSON                         -> FAIL
      N7  evidence_level = L2 / L5          -> FAIL（L2/L5 不得冒充 L4）
      N8  协议版本不兼容                    -> FAIL
      N9  协议内容已变更（sha 不符）         -> FAIL
      N10 生成后篡改内容（摘要不符）         -> FAIL integrity mismatch
      N11 证据过期                          -> INCOMPLETE
      N12 同一 bundle_id 复用但内容不同      -> FAIL
      N13 自报 PASS 但观测不满足契约         -> FAIL contract_violation
      N14 观测条数与契约不一致               -> INCOMPLETE
      N15 重放次数不足                      -> INCOMPLETE
      N16 重放不一致                        -> INCOMPLETE
      N17 动作未执行（只有状态）             -> INCOMPLETE
      N18 观测满足契约但采集侧自称非 PASS     -> INCOMPLETE（冲突不升级为 PASS）
      N19 观测不可判定（observed=None）      -> INCOMPLETE
      N20 未注册的证据来源                   -> INCOMPLETE
    E 环境异常
      E1 协议文件非法 -> ERROR（exit 3），不得伪装 PASS
      E2 Features 目录不存在 -> INCOMPLETE no_targets
    C CLI 兼容
      C1 独立 CLI 退出码：PASS=0 / FAIL=1 / INCOMPLETE=2 / ERROR=3
      C2 `validate.py` 默认运行**不执行**本阶段（无 Behavior evidence 输出）
      C3 `validate.py --behavior-evidence` 通过时 exit 0，且机器可读 JSON 可用
      C4 `validate.py --behavior-evidence` 证据被篡改时 exit 1
    D 真实行为缺陷注入（真实 Godot，隔离副本）
      D1 基线副本 -> 采集器 exit 0，证据包被 Validator 复核为 PASS
      D2 注入真实行为缺陷（set_open 不再改变状态）-> 采集器 FAIL，Validator FAIL
      D3 在缺陷证据上伪造 status=PASS 并重签摘要 -> Validator 仍 FAIL（独立复算）
      D4 恢复基线并逐字节校验 -> 采集器与 Validator 重新 PASS

除 D 段外，证据包由真实契约（template.yaml#behavior）推导出的合成观测构成：它们只检验
Validator 的判定逻辑本身；**真实行为**由 D 段与既有真实采集测试
（scene_composer/tests/test_feature_behavior_evidence.py）证明。

用法：
    python .ai/tools/validator/tests/test_behavior_evidence_stage.py
"""

import hashlib
import json
import os
import shutil
import subprocess
import sys
import tempfile
from datetime import datetime, timedelta, timezone

_HERE = os.path.dirname(os.path.abspath(__file__))
VALIDATOR_DIR = os.path.dirname(_HERE)
TOOLS_DIR = os.path.dirname(VALIDATOR_DIR)
DOTAI = os.path.dirname(TOOLS_DIR)
PROJECT_ROOT = os.path.dirname(DOTAI)
FEATURES = os.path.join(PROJECT_ROOT, "Features")
SCENE_COMPOSER = os.path.join(TOOLS_DIR, "scene_composer")

for path in (SCENE_COMPOSER, TOOLS_DIR, VALIDATOR_DIR):
    if path not in sys.path:
        sys.path.insert(0, path)

import behavior_protocol                                          # noqa: E402
import check_behavior_evidence as stage                           # noqa: E402
import execution_artifacts as xval                                # noqa: E402
import feature_behavior_evidence as fbe                           # noqa: E402
import runtime_instance_evidence as runtime_evidence              # noqa: E402

PROTOCOL = behavior_protocol.load_protocol()
PROTOCOL_SHA = fbe._sha256_file(behavior_protocol.PROTOCOL_PATH)
DECLARED = fbe.declared_features(FEATURES)
_failures = []
# Phase 1.57：合成记录必须附带**真实的执行产物**，否则 Validator 只能判
# INCOMPLETE（无法从产物重算重放事实）。这里给 fixture 一个受控的产物根目录。
_ARTIFACT_ROOT = ""


# ---------------------------------------------------------------- 断言 / 工具

def ok(name, condition, detail=""):
    if condition:
        print("PASS: " + name)
    else:
        _failures.append(name + (" | " + detail if detail else ""))
        print("FAIL: " + name + (" | " + detail if detail else ""))


def sha256_file(path):
    with open(path, "rb") as handle:
        return hashlib.sha256(handle.read()).hexdigest()


def iso(minutes_ago=0.0):
    moment = datetime.now(timezone.utc) - timedelta(minutes=minutes_ago)
    return moment.strftime("%Y-%m-%dT%H:%M:%SZ")


def make_bundle(features, bundle_id="bundle-test", level="L4",
                protocol_version=None, protocol_sha="__current__",
                generated_at="__now__", resign=True):
    document = {
        "schema": fbe.BUNDLE_SCHEMA,
        "schema_version": fbe.BUNDLE_SCHEMA_VERSION,
        "bundle_id": bundle_id,
        "generated_at": iso() if generated_at == "__now__" else generated_at,
        "git_head": "test-head",
        "tool": {"module": "feature_behavior_evidence", "module_version": 1},
        "protocol": {
            "protocol_version": PROTOCOL.version if protocol_version is None
                                else protocol_version,
            "sha256": PROTOCOL_SHA if protocol_sha == "__current__" else protocol_sha,
        },
        "evidence_level": level,
        "summary": {},
        "features": features,
    }
    if resign:
        document["integrity"] = {"algorithm": "sha256",
                                 "payload_sha256": fbe.bundle_digest(document)}
    return document


def resign(document):
    document["integrity"] = {"algorithm": "sha256",
                             "payload_sha256": fbe.bundle_digest(document)}
    return document


def write_bundle(directory, document, filename=""):
    os.makedirs(directory, exist_ok=True)
    name = filename or ("%s.json" % document.get("bundle_id", "bundle"))
    path = os.path.join(directory, name)
    with open(path, "w", encoding="utf-8", newline="\n") as handle:
        json.dump(document, handle, ensure_ascii=False, indent=2, sort_keys=True)
        handle.write("\n")
    return path


def contracts_of(feature, features_dir=FEATURES):
    contracts, reports = fbe.build_contracts(feature, features_dir, protocol=PROTOCOL)
    return contracts


def satisfying_observation(entry):
    item = {"check": entry["check"], "target": entry.get("target", "."),
            "entry": entry.get("entry", ""), "status": "PASS",
            "first_observed_frame": 0, "observed_args": []}
    if entry["check"] == "signal":
        item["observed"] = int(entry.get("count", 0))
        item["observed_args"] = list(entry.get("last_args") or [])
    elif "equals" in entry:
        item["observed"] = entry["equals"]
    elif entry.get("min") is not None:
        item["observed"] = entry["min"]
    else:
        item["observed"] = entry.get("max")
    return item


def write_execution_artifacts(record, contract):
    """为 fixture 记录写与探针结构一致的 result.json，返回 (paths, digests)。"""
    base = "%s-%s" % (record["feature"], record["behavior"])
    actions = [{"type": item.get("type"), "params": item.get("params") or {},
                "executed": True} for item in contract.get("actions") or []]
    paths, digests = {}, {}
    for index in range(1, int(record.get("replay_count") or 2) + 1):
        run_id = "%s-r%d" % (base, index)
        directory = os.path.join(_ARTIFACT_ROOT, base, run_id)
        os.makedirs(directory, exist_ok=True)
        payload = {"run_id": run_id, "replay_index": index,
                   "feature": record["feature"], "behavior": record["behavior"],
                   "status": record.get("status", "PASS"), "action_executed": True,
                   "actions": actions, "checks": record["actual"]}
        path = os.path.join(directory, "result.json")
        with open(path, "w", encoding="utf-8", newline="\n") as handle:
            json.dump(payload, handle, ensure_ascii=False, indent=2, sort_keys=True)
        paths[run_id] = {"contract": os.path.join(directory, "contract.json"),
                         "result": path}
        digests[run_id] = {"result": sha256_file(path)}
    return paths, digests


def behavior_record(feature, behavior, features_dir=FEATURES, status="PASS",
                    mutate=None):
    contract = next(item for item in contracts_of(feature, features_dir)
                    if item["behavior"] == behavior)
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
        "run_id": "%s-%s" % (feature, behavior),
        "evidence_paths": {},
        "actual": [satisfying_observation(entry) for entry in contract["expected"]],
    }
    record["evidence_paths"], record["artifact_digests"] = write_execution_artifacts(
        record, contract)
    if mutate:
        mutate(record)
    return record


def feature_block(feature, records, level="L4"):
    return {"feature": feature, "evidence_level": level, "behaviors": records}


def reasons(result):
    return {(item["feature"], item["behavior"], item["validation_reason"])
            for item in result["checks"]}


def reason_for(result, feature, behavior=""):
    for item in result["checks"]:
        if item["feature"] == feature and item["behavior"] == behavior:
            return item["validation_reason"]
    return ""


def run_stage(evidence_dir, features=None, features_dir=FEATURES, protocol_path=""):
    # 两个授权根：采集器的真实产物根（D 段的真实执行）与 fixture 产物根（P/N 段）。
    roots = list(xval.default_roots(PROJECT_ROOT))
    if _ARTIFACT_ROOT:
        roots.append(_ARTIFACT_ROOT)
    return stage.check_evidence(evidence_dir=evidence_dir, features=features,
                                features_dir=features_dir, protocol_path=protocol_path,
                                artifact_roots=roots)


def stage_cli(args):
    proc = subprocess.run([sys.executable,
                           os.path.join(VALIDATOR_DIR, "check_behavior_evidence.py")]
                          + args, capture_output=True, text=True, encoding="utf-8",
                          errors="replace", stdin=subprocess.DEVNULL, timeout=300)
    return proc.returncode, (proc.stdout or "") + (proc.stderr or "")


def validate_cli(args):
    proc = subprocess.run([sys.executable, os.path.join(VALIDATOR_DIR, "validate.py")]
                          + args, capture_output=True, text=True, encoding="utf-8",
                          errors="replace", stdin=subprocess.DEVNULL, timeout=600)
    return proc.returncode, (proc.stdout or "") + (proc.stderr or "")


# ---------------------------------------------------------------- P 正向

def case_positive(temp):
    print("\n--- P: 合法证据 ---")
    door_dir = os.path.join(temp, "pass_door")
    write_bundle(door_dir, make_bundle([feature_block("openable_door",
                                                      [behavior_record("openable_door", "open")])]))
    result = run_stage(door_dir, features=["openable_door"])
    ok("P1 合法证据 PASS", result["status"] == "PASS",
       "%s %s" % (result["status"], result["checks"]))
    ok("P1b 每条行为都有独立结论",
       any(item["validation_status"] == "PASS" and item["validation_reason"] == "verified"
           for item in result["checks"]), str(result["checks"]))
    ok("P1c 结论带等级与 Feature/Behavior 标识",
       all(item["evidence_level"] == "L4" and item["feature"] == "openable_door"
           and item["behavior"] == "open" for item in result["checks"]
           if item["validation_status"] == "PASS"), str(result["checks"]))
    ok("P1d PASS 退出码 0", stage.exit_code_for(result["status"]) == 0)

    # P2/P4：多 Feature、同一 Feature 多条 behavior
    multi = [name for name in DECLARED if len(contracts_of(name)) >= 2] or DECLARED[:2]
    chosen = []
    for name in DECLARED:
        if name not in chosen:
            chosen.append(name)
        if len(chosen) == 2:
            break
    blocks = []
    for name in chosen:
        blocks.append(feature_block(name, [behavior_record(name, contract["behavior"])
                                          for contract in contracts_of(name)]))
    multi_dir = os.path.join(temp, "pass_multi")
    write_bundle(multi_dir, make_bundle(blocks))
    result = run_stage(multi_dir, features=chosen)
    ok("P2 多 Feature 合法证据 PASS", result["status"] == "PASS",
       "%s %s" % (result["status"], [c for c in result["checks"]
                                     if c["validation_status"] != "PASS"]))
    ok("P2b 多 Feature 全部行为被覆盖",
       result["summary"]["pass"] == result["summary"]["checked"]
       and result["summary"]["checked"] >= len(chosen), str(result["summary"]))
    if multi:
        target = multi[0]
        # 单 Feature 限定：同一证据包里其他 Feature 的记录只是“未请求”，不能连坐为失败。
        result = run_stage(multi_dir, features=[target])
        ok("P4 同一 Feature 多条 behavior 关联正确（未请求的 Feature 跳过）",
           result["summary"]["pass"] == len(contracts_of(target))
           and result["status"] == "PASS"
           and set(result["summary"]["skipped_features"]) == set(chosen) - {target},
           str(result["summary"]))

    # P3：单 Feature 限定（其他已声明 Feature 不参与判定）
    result = run_stage(door_dir, features=["openable_door"])
    ok("P3 单 Feature 限定验证 PASS",
       result["status"] == "PASS" and result["summary"]["features"] == 1,
       str(result["summary"]))

    # P5：两个 bundle 给出相同记录 -> 不冲突
    duplicate_dir = os.path.join(temp, "pass_duplicate")
    document = make_bundle([feature_block("openable_door",
                                          [behavior_record("openable_door", "open")])],
                           bundle_id="dup-a")
    write_bundle(duplicate_dir, document)
    twin = json.loads(json.dumps(document))
    twin["bundle_id"] = "dup-b"
    resign(twin)
    write_bundle(duplicate_dir, twin)
    result = run_stage(duplicate_dir, features=["openable_door"])
    ok("P5 两个 bundle 的相同记录不视为冲突", result["status"] == "PASS",
       "%s %s" % (result["status"], result["checks"]))


# ---------------------------------------------------------------- N 负向

def case_negative(temp):
    print("\n--- N: 拒绝路径 ---")
    good = lambda: make_bundle([feature_block("openable_door",
                                             [behavior_record("openable_door", "open")])])

    directory = os.path.join(temp, "n1")
    write_bundle(directory, good())
    result = run_stage(directory, features=["nonexistent_feature"])
    ok("N1 未知 Feature -> FAIL unknown_feature",
       result["status"] == "FAIL"
       and reason_for(result, "nonexistent_feature") == "unknown_feature",
       str(result["checks"]))

    directory = os.path.join(temp, "n2")
    write_bundle(directory, make_bundle([feature_block(
        "openable_door", [behavior_record("openable_door", "open"),
                          behavior_record("openable_door", "open")])]))
    record = behavior_record("openable_door", "open")
    record["behavior"] = "frobnicate"
    write_bundle(directory, make_bundle([feature_block("openable_door", [record])],
                                        bundle_id="n2b"))
    result = run_stage(directory, features=["openable_door"])
    ok("N2 未知 Behavior -> FAIL unknown_behavior",
       any(reason == "unknown_behavior" for _, _, reason in reasons(result)),
       str(result["checks"]))

    directory = os.path.join(temp, "n3")
    write_bundle(directory, make_bundle([feature_block(
        "health", [behavior_record("openable_door", "open")])], bundle_id="n3"))
    result = run_stage(directory, features=["health"])
    ok("N3 跨 Feature 关联被拒绝",
       result["status"] == "FAIL"
       and any(item["feature"] == "health" and item["validation_status"] == "FAIL"
               for item in result["checks"]), str(result["checks"]))

    result = run_stage(os.path.join(temp, "n4_missing"), features=["openable_door"])
    ok("N4 证据目录不存在 -> INCOMPLETE",
       result["status"] == "INCOMPLETE" and result["reason"] == "evidence_unavailable",
       result["reason"])

    empty = os.path.join(temp, "n5_empty")
    os.makedirs(empty, exist_ok=True)
    result = run_stage(empty, features=["openable_door"])
    ok("N5 空证据目录 -> INCOMPLETE no_evidence",
       result["status"] == "INCOMPLETE" and result["reason"] == "no_evidence",
       result["reason"])
    ok("N5b INCOMPLETE 退出码 2 且不是 PASS",
       stage.exit_code_for(result["status"]) == 2)

    broken = os.path.join(temp, "n6")
    os.makedirs(broken, exist_ok=True)
    with open(os.path.join(broken, "broken.json"), "w", encoding="utf-8") as handle:
        handle.write("{not json,,,}")
    result = run_stage(broken, features=["openable_door"])
    ok("N6 非法 JSON -> FAIL", result["status"] == "FAIL", result["status"])

    for level in ("L2", "L5"):
        directory = os.path.join(temp, "n7_" + level)
        write_bundle(directory, make_bundle(
            [feature_block("openable_door", [behavior_record("openable_door", "open")],
                           level=level)], level=level, bundle_id="n7-" + level))
        result = run_stage(directory, features=["openable_door"])
        ok("N7 evidence_level=%s 不得冒充 L4 -> FAIL" % level,
           result["status"] == "FAIL"
           and any("unsupported evidence level" in " ".join(bundle["reasons"])
                   for bundle in result["bundles"]),
           str([bundle["reasons"] for bundle in result["bundles"]]))

    directory = os.path.join(temp, "n8")
    write_bundle(directory, make_bundle(
        [feature_block("openable_door", [behavior_record("openable_door", "open")])],
        protocol_version=PROTOCOL.version + 99, bundle_id="n8"))
    result = run_stage(directory, features=["openable_door"])
    ok("N8 协议版本不兼容 -> FAIL",
       result["status"] == "FAIL"
       and any("protocol version mismatch" in " ".join(bundle["reasons"])
               for bundle in result["bundles"]), str(result["bundles"]))

    directory = os.path.join(temp, "n9")
    write_bundle(directory, make_bundle(
        [feature_block("openable_door", [behavior_record("openable_door", "open")])],
        protocol_sha="0" * 64, bundle_id="n9"))
    result = run_stage(directory, features=["openable_door"])
    ok("N9 协议内容变更 -> FAIL",
       result["status"] == "FAIL"
       and any("protocol content changed" in " ".join(bundle["reasons"])
               for bundle in result["bundles"]), str(result["bundles"]))

    directory = os.path.join(temp, "n10")
    document = good()
    document["features"][0]["behaviors"][0]["actual"][0]["observed"] = False
    write_bundle(directory, document)
    result = run_stage(directory, features=["openable_door"])
    ok("N10 内容被篡改 -> FAIL integrity mismatch",
       result["status"] == "FAIL"
       and any("integrity mismatch" in " ".join(bundle["reasons"])
               for bundle in result["bundles"]), str(result["bundles"]))

    directory = os.path.join(temp, "n11")
    write_bundle(directory, make_bundle(
        [feature_block("openable_door", [behavior_record("openable_door", "open")])],
        generated_at=iso(60 * 48), bundle_id="n11"))
    result = run_stage(directory, features=["openable_door"])
    ok("N11 证据过期 -> INCOMPLETE",
       result["status"] == "INCOMPLETE" and stage.exit_code_for(result["status"]) == 2,
       "%s %s" % (result["status"], result["bundles"]))

    directory = os.path.join(temp, "n12")
    first = make_bundle([feature_block("openable_door",
                                       [behavior_record("openable_door", "open")])],
                        bundle_id="reused")
    write_bundle(directory, first, filename="a.json")
    second = good()
    second["bundle_id"] = "reused"
    second["features"][0]["behaviors"][0]["replay_count"] = 3
    resign(second)
    write_bundle(directory, second, filename="b.json")
    result = run_stage(directory, features=["openable_door"])
    ok("N12 同一 bundle_id 复用不同内容 -> FAIL",
       result["status"] == "FAIL"
       and any("reused" in " ".join(bundle["reasons"])
               for bundle in result["bundles"]), str(result["bundles"]))

    directory = os.path.join(temp, "n13")
    forged = make_bundle([feature_block("openable_door", [behavior_record(
        "openable_door", "open", status="PASS",
        mutate=lambda record: record["actual"][0].update({"observed": False}))])],
        bundle_id="n13")
    write_bundle(directory, forged)
    result = run_stage(directory, features=["openable_door"])
    ok("N13 自报 PASS 但观测不满足契约 -> FAIL contract_violation",
       result["status"] == "FAIL"
       and reason_for(result, "openable_door", "open") == "contract_violation",
       str(result["checks"]))

    def shorten(record):
        record["actual"] = record["actual"][:1]

    directory = os.path.join(temp, "n14")
    write_bundle(directory, make_bundle([feature_block("openable_door", [behavior_record(
        "openable_door", "open", mutate=shorten)])], bundle_id="n14"))
    result = run_stage(directory, features=["openable_door"])
    # Phase 1.57：记录里的 actual[] 与真实产物不符 -> 矛盾，升级为 FAIL。
    ok("N14 证据观测被删减（与产物不符）-> FAIL observation_mismatch",
       reason_for(result, "openable_door", "open") == "observation_mismatch",
       str(result["checks"]))

    directory = os.path.join(temp, "n15")
    write_bundle(directory, make_bundle([feature_block("openable_door", [behavior_record(
        "openable_door", "open",
        mutate=lambda record: record.update({"replay_count": 1}))])], bundle_id="n15"))
    result = run_stage(directory, features=["openable_door"])
    # Phase 1.57：自报 1 次但与真实产物 2 份矛盾 -> FAIL（比原来的 INCOMPLETE 更严）。
    ok("N15 自报重放次数与产物矛盾 -> FAIL replay_count_mismatch",
       reason_for(result, "openable_door", "open") == "replay_count_mismatch",
       str(result["checks"]))

    directory = os.path.join(temp, "n16")
    write_bundle(directory, make_bundle([feature_block("openable_door", [behavior_record(
        "openable_door", "open",
        mutate=lambda record: record.update({"replay_consistent": False}))])],
        bundle_id="n16"))
    result = run_stage(directory, features=["openable_door"])
    # Phase 1.57：用产物重算的一致性 ≠ 自报值 -> FAIL。
    ok("N16 自报重放一致性与产物矛盾 -> FAIL replay_consistency_mismatch",
       reason_for(result, "openable_door", "open") == "replay_consistency_mismatch",
       str(result["checks"]))

    directory = os.path.join(temp, "n17")
    write_bundle(directory, make_bundle([feature_block("openable_door", [behavior_record(
        "openable_door", "open",
        mutate=lambda record: record.update({"action_executed": False}))])],
        bundle_id="n17"))
    result = run_stage(directory, features=["openable_door"])
    ok("N17 动作未执行 -> INCOMPLETE action_not_executed",
       reason_for(result, "openable_door", "open") == "action_not_executed",
       str(result["checks"]))

    directory = os.path.join(temp, "n18")
    write_bundle(directory, make_bundle([feature_block("openable_door", [behavior_record(
        "openable_door", "open", status="MISMATCH")])], bundle_id="n18"))
    result = run_stage(directory, features=["openable_door"])
    ok("N18 观测满足但采集侧自称非 PASS -> INCOMPLETE（不升级为 PASS）",
       result["status"] == "INCOMPLETE"
       and reason_for(result, "openable_door", "open") == "evidence_self_contradiction",
       str(result["checks"]))

    directory = os.path.join(temp, "n19")
    write_bundle(directory, make_bundle([feature_block("openable_door", [behavior_record(
        "openable_door", "open",
        mutate=lambda record: record["actual"][0].update({"observed": None}))])],
        bundle_id="n19"))
    result = run_stage(directory, features=["openable_door"])
    # Phase 1.57：产物里仍有真实观测，而记录把它换成 None -> 证据与产物矛盾。
    ok("N19 记录把观测抹成 None（产物不符）-> FAIL observation_mismatch",
       reason_for(result, "openable_door", "open") == "observation_mismatch",
       str(result["checks"]))

    directory = os.path.join(temp, "n20")
    write_bundle(directory, make_bundle([feature_block("openable_door", [behavior_record(
        "openable_door", "open",
        mutate=lambda record: record.update({"evidence": "python_assert"}))])],
        bundle_id="n20"))
    result = run_stage(directory, features=["openable_door"])
    ok("N20 未注册的证据来源 -> INCOMPLETE",
       reason_for(result, "openable_door", "open") == "unsupported_evidence_source",
       str(result["checks"]))


# ---------------------------------------------------------------- E 环境

def case_environment(temp):
    print("\n--- E: 环境异常 ---")
    invalid = os.path.join(temp, "invalid_protocol.yaml")
    with open(invalid, "w", encoding="utf-8", newline="\n") as handle:
        handle.write("protocol_version: 999\nactions: []\n")
    directory = os.path.join(temp, "e1")
    write_bundle(directory, make_bundle([feature_block(
        "openable_door", [behavior_record("openable_door", "open")])], bundle_id="e1"))
    result = run_stage(directory, features=["openable_door"], protocol_path=invalid)
    ok("E1 协议非法 -> ERROR（不伪装 PASS）",
       result["status"] == "ERROR" and stage.exit_code_for(result["status"]) == 3,
       result["status"])

    no_targets = os.path.join(temp, "e2_bundles")
    os.makedirs(no_targets, exist_ok=True)
    write_bundle(no_targets, make_bundle([feature_block(
        "openable_door", [behavior_record("openable_door", "open")])], bundle_id="e2"))
    result = run_stage(no_targets, features=None,
                       features_dir=os.path.join(temp, "e2_no_features"))
    ok("E2 Features 目录不存在 -> INCOMPLETE features_unavailable",
       result["status"] == "INCOMPLETE" and result["reason"] == "features_unavailable",
       "%s %s" % (result["status"], result["reason"]))


# ---------------------------------------------------------------- C CLI

def case_cli(temp):
    print("\n--- C: CLI 与 Validator 兼容 ---")
    good_dir = os.path.join(temp, "c_pass")
    write_bundle(good_dir, make_bundle([feature_block(
        "openable_door", [behavior_record("openable_door", "open")])], bundle_id="c-pass"))
    code, output = stage_cli(["--evidence-dir", good_dir, "--feature", "openable_door",
                              "--artifact-root", _ARTIFACT_ROOT])
    ok("C1a 独立 CLI PASS -> exit 0", code == 0 and "PASS" in output,
       "code=%d out=%s" % (code, output[-400:]))

    bad_dir = os.path.join(temp, "c_fail")
    document = make_bundle([feature_block("openable_door", [behavior_record(
        "openable_door", "open", mutate=lambda record: record["actual"][0].update(
            {"observed": False}))])], bundle_id="c-fail")
    write_bundle(bad_dir, document)
    code, output = stage_cli(["--evidence-dir", bad_dir, "--feature", "openable_door",
                              "--artifact-root", _ARTIFACT_ROOT])
    ok("C1b 独立 CLI FAIL -> exit 1", code == 1, "code=%d" % code)

    code, output = stage_cli(["--evidence-dir", os.path.join(temp, "c_missing"),
                              "--feature", "openable_door"])
    ok("C1c 独立 CLI INCOMPLETE -> exit 2", code == 2, "code=%d" % code)

    report = os.path.join(temp, "c_json.json")
    code, output = stage_cli(["--evidence-dir", good_dir, "--feature", "openable_door",
                              "--artifact-root", _ARTIFACT_ROOT, "--json", report])
    payload = {}
    if os.path.isfile(report):
        with open(report, encoding="utf-8") as handle:
            payload = json.load(handle)
    ok("C1d 机器可读结果可被消费（含 feature/behavior/level/status/reason）",
       payload.get("status") == "PASS"
       and all(key in payload["checks"][0]
               for key in ("feature", "behavior", "evidence_level",
                           "validation_status", "validation_reason")), str(payload)[:300])

    code, output = validate_cli([])
    ok("C2 validate.py 默认运行不执行 Evidence 阶段",
       "Behavior evidence" not in output and code == 0,
       "code=%d behavior_lines=%d" % (code, output.count("Behavior evidence")))

    code, output = validate_cli(["--behavior-evidence", "--evidence-dir", good_dir,
                                 "--evidence-feature", "openable_door",
                                 "--evidence-artifact-root", _ARTIFACT_ROOT,
                                 "--behavior-evidence-json",
                                 os.path.join(temp, "c_validate.json")])
    ok("C3 validate.py --behavior-evidence 通过 -> exit 0",
       code == 0 and "Behavior evidence (L4): PASS" in output,
       "code=%d tail=%s" % (code, output[-500:]))

    code, output = validate_cli(["--behavior-evidence", "--evidence-dir", bad_dir,
                                 "--evidence-feature", "openable_door",
                                 "--evidence-artifact-root", _ARTIFACT_ROOT])
    ok("C4 validate.py --behavior-evidence 拒绝伪造证据 -> exit 1",
       code == 1 and "contract_violation" in output,
       "code=%d tail=%s" % (code, output[-500:]))

    # 缺证据必须 INCOMPLETE 且不被当成 PASS（验收 B3/B4 的 Validator 侧）
    code, output = validate_cli(["--behavior-evidence", "--evidence-dir",
                                 os.path.join(temp, "c_validate_missing"),
                                 "--evidence-feature", "openable_door",
                                 "--evidence-artifact-root", _ARTIFACT_ROOT])
    ok("C5 validate.py --behavior-evidence 证据缺失 -> INCOMPLETE exit 2",
       code == 2 and "Behavior evidence (L4): INCOMPLETE" in output
       and "not treated as PASS" in output,
       "code=%d tail=%s" % (code, output[-400:]))


# ---------------------------------------------------------------- D 真实缺陷注入

SET_OPEN_BLOCK = ("func set_open(value: bool) -> void:\n"
                  "\tif _is_open == value:\n"
                  "\t\treturn\n"
                  "\t_apply(value)\n")

DEFECT_BLOCK = ("func set_open(value: bool) -> void:\n"
                "\t# Phase 1.56 defect injection: 入口存在但不再改变状态\n"
                "\tif value:\n"
                "\t\treturn\n"
                "\t_apply(value)\n")


def read_text(path):
    with open(path, encoding="utf-8") as handle:
        return handle.read()


def write_text(path, text):
    with open(path, "w", encoding="utf-8", newline="\n") as handle:
        handle.write(text)


def collect(godot, features_dir, out_dir, extra=None):
    command = [sys.executable, os.path.join(SCENE_COMPOSER, "feature_behavior_evidence.py"),
               "--features-dir", features_dir, "--feature", "openable_door",
               "--evidence-out", out_dir, "--godot", godot, "--replay", "2"]
    proc = subprocess.run(command + (extra or []), capture_output=True, text=True,
                          encoding="utf-8", errors="replace",
                          stdin=subprocess.DEVNULL, timeout=600)
    return proc.returncode, (proc.stdout or "") + (proc.stderr or "")


def cleanup_artifacts(bundle, features_dir):
    """删除本次采集产生的 run 目录（只删证据包里登记过的路径）。"""
    removed = 0
    for block in bundle.get("features") or []:
        for record in block.get("behaviors") or []:
            for paths in (record.get("evidence_paths") or {}).values():
                run_dir = os.path.dirname(paths.get("result", ""))
                if run_dir and os.path.isdir(run_dir) \
                        and run_dir.startswith(fbe.EVIDENCE_ROOT):
                    shutil.rmtree(run_dir, ignore_errors=True)
                    removed += 1
    return removed


def load_bundles(directory):
    return [json.loads(read_text(os.path.join(directory, name)))
            for name in sorted(os.listdir(directory)) if name.endswith(".json")]


def case_defect_injection(temp, godot):
    print("\n--- D: 真实行为缺陷注入（隔离副本 + 真实 Godot）---")
    workspace = os.path.join(temp, "defect_workspace")
    features_dir = os.path.join(workspace, "Features")
    shutil.copytree(os.path.join(FEATURES, "openable_door"),
                    os.path.join(features_dir, "openable_door"))
    script = os.path.join(features_dir, "openable_door", "openable_door.gd")
    original = read_text(script)
    original_sha = sha256_file(script)
    ok("D0 夹具是隔离副本（不触碰真实 Features/）",
       not script.startswith(FEATURES + os.sep) and SET_OPEN_BLOCK in original)
    ok("D0b 隔离副本模板为仓库模板原文",
       sha256_file(os.path.join(features_dir, "openable_door", "template.yaml"))
       == sha256_file(os.path.join(FEATURES, "openable_door", "template.yaml")))

    baseline_dir = os.path.join(workspace, "bundles_baseline")
    code, output = collect(godot, features_dir, baseline_dir)
    ok("D1 基线副本采集 -> 采集器 exit 0", code == 0,
       "code=%d tail=%s" % (code, output[-600:]))
    baseline_bundles = load_bundles(baseline_dir) if os.path.isdir(baseline_dir) else []
    result = run_stage(baseline_dir, features=["openable_door"], features_dir=features_dir)
    ok("D1b 基线证据被 Validator 复核为 PASS", result["status"] == "PASS",
       "%s %s" % (result["status"], result["checks"]))
    ok("D1c 基线证据为两条 check（状态 + 信号带实参）",
       bool(baseline_bundles)
       and len(baseline_bundles[0]["features"][0]["behaviors"][0]["actual"]) == 2,
       str(baseline_bundles[0]["features"][0]["behaviors"][0]["actual"]
           if baseline_bundles else "no bundle"))

    defect_dir = os.path.join(workspace, "bundles_defect")
    write_text(script, original.replace(SET_OPEN_BLOCK, DEFECT_BLOCK))
    ok("D2 缺陷已注入（入口保留，状态不再改变）",
       DEFECT_BLOCK in read_text(script) and sha256_file(script) != original_sha)
    code, output = collect(godot, features_dir, defect_dir)
    ok("D2b 缺陷副本采集器判为失败（exit 1，不静默 PASS）", code == 1,
       "code=%d tail=%s" % (code, output[-600:]))
    defect_bundles = load_bundles(defect_dir) if os.path.isdir(defect_dir) else []
    defect_records = [record for bundle in defect_bundles
                      for block in bundle.get("features") or []
                      for record in block.get("behaviors") or []]
    ok("D2c 证据包记录真实观测（is_open 未改变）",
       bool(defect_records) and defect_records[0]["status"] != "PASS"
       and defect_records[0]["actual"][0]["observed"] is not True,
       str(defect_records[:1])[:400])
    result = run_stage(defect_dir, features=["openable_door"], features_dir=features_dir)
    ok("D2d Validator 拒绝缺陷行为 -> FAIL contract_violation",
       result["status"] == "FAIL"
       and reason_for(result, "openable_door", "open") == "contract_violation",
       "%s %s" % (result["status"], result["checks"]))

    forged_dir = os.path.join(workspace, "bundles_forged")
    os.makedirs(forged_dir, exist_ok=True)
    for bundle in defect_bundles:
        copy = json.loads(json.dumps(bundle))
        for block in copy.get("features") or []:
            for record in block.get("behaviors") or []:
                record["status"] = "PASS"
                record["reason"] = "forged"
        copy["bundle_id"] = copy.get("bundle_id", "d3") + "-forged"
        copy["generated_at"] = iso()
        resign(copy)
        write_bundle(forged_dir, copy)
    result = run_stage(forged_dir, features=["openable_door"], features_dir=features_dir)
    ok("D3 缺陷证据伪造 status=PASS 并重签摘要后仍被拒绝",
       result["status"] == "FAIL"
       and reason_for(result, "openable_door", "open") == "contract_violation",
       "%s %s" % (result["status"], result["checks"]))

    write_text(script, original)
    ok("D4 副本脚本逐字节恢复", sha256_file(script) == original_sha)
    restore_dir = os.path.join(workspace, "bundles_restore")
    code, output = collect(godot, features_dir, restore_dir)
    result = run_stage(restore_dir, features=["openable_door"], features_dir=features_dir)
    ok("D4b 恢复后采集器与 Validator 重新 PASS",
       code == 0 and result["status"] == "PASS",
       "code=%d status=%s %s" % (code, result["status"], result["checks"]))

    removed = 0
    for directory in (baseline_dir, defect_dir, restore_dir):
        if os.path.isdir(directory):
            for bundle in load_bundles(directory):
                removed += cleanup_artifacts(bundle, features_dir)
    ok("D5 真实 Features/ 未被修改",
       sha256_file(os.path.join(FEATURES, "openable_door", "openable_door.gd"))
       == sha256_file(os.path.join(features_dir, "openable_door", "openable_door.gd"))
       == original_sha)
    print("  采集产物 run 目录清理：%d 个" % removed)


# ---------------------------------------------------------------- main

def main():
    global _ARTIFACT_ROOT
    print("Behavior Evidence stage tests (Phase 1.56 / 1.57 cross-validation)")
    print("repo Features declaring behavior: %d (%s)"
          % (len(DECLARED), ", ".join(DECLARED[:6]) + ("..." if len(DECLARED) > 6 else "")))
    if "openable_door" not in DECLARED:
        print("SKIP: openable_door no longer declares behavior; fixtures need updating")
        return 1

    temp = tempfile.mkdtemp(prefix="bev_stage_", dir=os.path.join(DOTAI, "tmp"))
    _ARTIFACT_ROOT = os.path.join(temp, "artifacts")
    os.makedirs(_ARTIFACT_ROOT, exist_ok=True)
    try:
        case_positive(temp)
        case_negative(temp)
        case_environment(temp)
        case_cli(temp)

        godot = runtime_evidence.find_godot(PROJECT_ROOT)
        if godot:
            case_defect_injection(temp, godot)
        else:
            ok("D 真实缺陷注入（需要 Godot）", False,
               "SKIP -> 记为未执行，不作 PASS")
    finally:
        shutil.rmtree(temp, ignore_errors=True)

    print("")
    if _failures:
        print("FAILED %d check(s):" % len(_failures))
        for failure in _failures:
            print("  - " + failure)
        return 1
    print("ALL PASS")
    return 0


if __name__ == "__main__":
    sys.exit(main())
