#!/usr/bin/env python3
"""Execution artifact resolver & evidence cross-validator (Phase 1.57).

Phase 1.56 让 Validator 复核**证据包**（bundle JSON）。但证据包里的
`action_executed` / `replay_count` / `replay_consistent` 仍是采集侧自报的：
只要把证据包写得自洽，Validator 就只能相信它。

本模块把证据包与**真实执行产物**（每次重放的 `result.json`，由 Godot 探针在
`evidence_paths` 指向的位置写出）连起来，由 Validator 侧独立重算：

    Evidence(record) ── evidence_paths ──> result.json ──> 重新计算
                                                        ├── 执行标识 / Feature / Behavior
                                                        ├── 重放次数与序号
                                                        ├── 动作是否真的执行
                                                        ├── 逐次观测是否与证据一致
                                                        └── 重放一致性

三条纪律：

1. **路径必须落在授权根目录内**：解析前做 realpath（跟随符号链接）再判包含关系，
   拒绝 `..` 穿越、越界绝对路径、越界符号链接、目录、以及非 `result.json` 的
   任意文件；证据目录自身也不允许被当作执行产物。
2. **矛盾 → FAIL，无法证明 → INCOMPLETE**：产物缺失、不可读、JSON 损坏、缺摘要
   都只是“无法证明”，不能因此判通过，也不升级为 FAIL。
3. **只做前两层信任**：内容完整性（摘要）与执行记录一致性。它能发现“产物被
   单独改写”，**不能**证明产物来自可信执行环境——能同时改写实现、产物、证据包
   并重算摘要的人仍可伪造。该边界不随本模块消失。

用法（由 `check_behavior_evidence.py` 调用）：

    from execution_artifacts import ArtifactResolver, cross_validate
"""

from __future__ import annotations

import hashlib
import json
import os

STATUS_PASS = "PASS"
STATUS_FAIL = "FAIL"
STATUS_INCOMPLETE = "INCOMPLETE"

#: 执行产物只认这一种文件名，避免把 bundle / contract / 任意 JSON 当作执行记录。
RESULT_BASENAME = "result.json"
MAX_RESULT_BYTES = 8 * 1024 * 1024

#: 参与重放一致性比较的 check 字段（与采集侧 BehaviorRun.fingerprint 对齐）。
FINGERPRINT_KEYS = ("check", "target", "entry", "expected", "observed", "status")


class ArtifactError(Exception):
    """产物解析失败；`kind` 是稳定的机器可读原因。"""

    def __init__(self, kind: str, detail: str, status: str = STATUS_INCOMPLETE):
        super().__init__(detail)
        self.kind = kind
        self.detail = detail
        self.status = status


def sha256_file(path: str) -> str:
    try:
        with open(path, "rb") as handle:
            return hashlib.sha256(handle.read()).hexdigest()
    except OSError:
        return ""


def _is_int(value) -> bool:
    return isinstance(value, int) and not isinstance(value, bool)


def default_roots(project_root: str) -> list:
    """授权根目录：采集器写执行产物的 `.ai/tmp/behavior`。"""
    return [os.path.join(project_root, ".ai", "tmp", "behavior")]


class ArtifactResolver:
    """evidence_paths 字符串 -> 已校验的真实产物路径。"""

    def __init__(self, roots, base_dir: str = "", forbidden=(), max_bytes: int = MAX_RESULT_BYTES):
        self.roots = [os.path.realpath(root) for root in roots or [] if root]
        self.base_dir = os.path.realpath(base_dir) if base_dir else ""
        self.forbidden = [os.path.realpath(item) for item in forbidden or [] if item]
        self.max_bytes = int(max_bytes)

    # -------------------------------------------------------------- 路径
    def _resolve_raw(self, raw) -> str:
        if not isinstance(raw, str) or not raw.strip():
            raise ArtifactError("artifact_path_missing", "evidence path is not a non-empty string")
        text = raw.strip()
        if "\x00" in text:
            raise ArtifactError("artifact_path_rejected", "evidence path contains NUL",
                                STATUS_FAIL)
        if os.path.isabs(text):
            return text
        if not self.base_dir:
            raise ArtifactError("artifact_path_rejected",
                                "relative evidence path %r without a base directory" % text,
                                STATUS_FAIL)
        return os.path.join(self.base_dir, text)

    def _inside(self, path: str, roots) -> bool:
        for root in roots:
            if path == root:
                return True
            if path.startswith(root + os.sep):
                return True
        return False

    def resolve(self, raw) -> str:
        """返回真实路径；越界 / 非法一律抛 ArtifactError。"""
        absolute = self._resolve_raw(raw)
        # realpath 跟随符号链接后再判归属：`link -> /etc/passwd` 也必须被拒绝。
        real = os.path.realpath(absolute)
        if not self.roots:
            raise ArtifactError("artifact_path_rejected",
                                "no authorized artifact root configured", STATUS_FAIL)
        if not self._inside(real, self.roots):
            raise ArtifactError(
                "artifact_path_rejected",
                "evidence path %r resolves outside the authorized roots (%s)"
                % (raw, ", ".join(self.roots)), STATUS_FAIL)
        if self.forbidden and self._inside(real, self.forbidden):
            raise ArtifactError(
                "artifact_path_rejected",
                "evidence path %r points at the evidence store itself" % raw, STATUS_FAIL)
        if os.path.basename(real) != RESULT_BASENAME:
            raise ArtifactError(
                "artifact_unsupported",
                "evidence path %r is not a %s execution artifact"
                % (os.path.basename(real), RESULT_BASENAME), STATUS_FAIL)
        if os.path.isdir(real):
            raise ArtifactError("artifact_unsupported",
                                "evidence path %r is a directory" % raw, STATUS_FAIL)
        if not os.path.isfile(real):
            raise ArtifactError("artifact_missing",
                                "execution artifact not found: %s" % raw)
        try:
            size = os.path.getsize(real)
        except OSError as exc:
            raise ArtifactError("artifact_unreadable",
                                "cannot stat %s: %s" % (raw, exc)) from exc
        if size > self.max_bytes:
            raise ArtifactError("artifact_unsupported",
                                "execution artifact %s is %d bytes (limit %d)"
                                % (raw, size, self.max_bytes), STATUS_FAIL)
        return real

    def load(self, raw) -> dict:
        """解析 -> 标准化执行记录。"""
        path = self.resolve(raw)
        try:
            with open(path, "r", encoding="utf-8") as handle:
                payload = json.load(handle)
        except OSError as exc:
            raise ArtifactError("artifact_unreadable",
                                "cannot read %s: %s" % (raw, exc)) from exc
        except ValueError as exc:
            # 文件存在但不是 JSON：产物损坏，无法据此证明任何执行事实。
            raise ArtifactError("artifact_invalid_json",
                                "%s is not valid JSON: %s" % (raw, exc)) from exc
        record = parse_execution_record(payload, path)
        record["sha256"] = sha256_file(path)
        return record


def parse_execution_record(payload, path: str = "") -> dict:
    """result.json -> 标准化执行记录（只保留交叉验证需要的字段）。"""
    if not isinstance(payload, dict):
        raise ArtifactError("artifact_invalid_schema",
                            "%s is not a JSON object" % (path or "execution artifact"))
    run_id = payload.get("run_id")
    feature = payload.get("feature")
    behavior = payload.get("behavior")
    replay_index = payload.get("replay_index")
    executed = payload.get("action_executed")
    actions = payload.get("actions")
    checks = payload.get("checks")
    problems = []
    if not isinstance(run_id, str) or not run_id.strip():
        problems.append("run_id")
    if not isinstance(feature, str) or not feature.strip():
        problems.append("feature")
    if not isinstance(behavior, str) or not behavior.strip():
        problems.append("behavior")
    if not _is_int(replay_index) or replay_index < 1:
        problems.append("replay_index")
    if not isinstance(executed, bool):
        problems.append("action_executed")
    if not isinstance(actions, list):
        problems.append("actions")
    if not isinstance(checks, list):
        problems.append("checks")
    if problems:
        raise ArtifactError(
            "artifact_invalid_schema",
            "%s lacks a usable %s" % (path or "execution artifact", ", ".join(problems)))
    return {
        "path": path,
        "run_id": run_id.strip(),
        "feature": feature.strip(),
        "behavior": behavior.strip(),
        "replay_index": int(replay_index),
        "action_executed": executed,
        "actions": actions,
        "checks": checks,
        "status": payload.get("status"),
        "scene": payload.get("scene"),
        "waited_frames": payload.get("waited_frames"),
        "window_frames": payload.get("window_frames"),
    }


def _project_checks(checks) -> list:
    projected = []
    for item in checks or []:
        if not isinstance(item, dict):
            return None
        projected.append({key: item.get(key) for key in FINGERPRINT_KEYS})
    return projected


def _canonical(value) -> str:
    return json.dumps(value, sort_keys=True, ensure_ascii=False, default=str)


def _action_types(actions) -> list:
    types = []
    for item in actions or []:
        if isinstance(item, dict):
            types.append(str(item.get("type") or ""))
        else:
            types.append("")
    return types


def _first_failure(findings) -> dict:
    for status in (STATUS_FAIL, STATUS_INCOMPLETE):
        for finding in findings:
            if finding["status"] == status:
                return finding
    return {"status": STATUS_PASS, "reason": "cross_validated",
            "detail": "execution artifacts agree with the evidence record"}


def cross_validate(record: dict, contract: dict, resolver: ArtifactResolver,
                   used: dict = None, on_use=None) -> dict:
    """证据记录 vs 执行产物 -> {status, reason, detail, artifacts}。

    `used` 用于检测跨记录复用同一份产物（旧产物冒充新执行）。
    """
    findings = []
    artifacts = []
    feature = str(record.get("feature") or "")
    behavior = str(record.get("behavior") or "")
    paths = record.get("evidence_paths")
    digests = record.get("artifact_digests")

    if not isinstance(paths, dict) or not paths:
        findings.append({"status": STATUS_INCOMPLETE, "reason": "execution_paths_missing",
                         "detail": "evidence record carries no execution artifacts "
                                   "(legacy bundle: replay facts cannot be re-derived)"})
        return {"artifacts": artifacts, **_first_failure(findings)}
    if not isinstance(digests, dict) or not digests:
        findings.append({"status": STATUS_INCOMPLETE, "reason": "artifact_digests_missing",
                         "detail": "evidence record carries no artifact digests "
                                   "(artifact content cannot be bound to the evidence)"})

    for run_id in sorted(paths):
        artifacts_block = paths.get(run_id)
        raw = (artifacts_block or {}).get("result") if isinstance(artifacts_block, dict) else None
        try:
            artifact = resolver.load(raw)
        except ArtifactError as exc:
            findings.append({"status": exc.status, "reason": exc.kind,
                             "detail": "%s: %s" % (run_id, exc.detail)})
            continue
        artifacts.append(artifact)

        expected_digest = (digests or {}).get(run_id, {}).get("result") \
            if isinstance((digests or {}).get(run_id), dict) else None
        if isinstance(expected_digest, str) and len(expected_digest) == 64:
            if artifact["sha256"] != expected_digest:
                findings.append({"status": STATUS_FAIL, "reason": "artifact_digest_mismatch",
                                 "detail": "%s: result.json sha256 %s != declared %s"
                                           % (run_id, artifact["sha256"][:16],
                                              expected_digest[:16])})

        if used is not None:
            owner = used.get(artifact["path"])
            if owner is not None and owner != (feature, behavior):
                findings.append({"status": STATUS_FAIL, "reason": "artifact_reused",
                                 "detail": "%s: artifact already cited by %s/%s"
                                           % (run_id, owner[0], owner[1])})
            else:
                used[artifact["path"]] = (feature, behavior)
        if on_use is not None:
            on_use(artifact["path"], run_id, feature, behavior)

        if run_id != artifact["run_id"]:
            findings.append({"status": STATUS_FAIL, "reason": "artifact_run_mismatch",
                             "detail": "path key %r != artifact run_id %r"
                                       % (run_id, artifact["run_id"])})
        if artifact["feature"] != feature:
            findings.append({"status": STATUS_FAIL, "reason": "artifact_feature_mismatch",
                             "detail": "%s: artifact feature %r != evidence feature %r"
                                       % (run_id, artifact["feature"], feature)})
        if artifact["behavior"] != behavior:
            findings.append({"status": STATUS_FAIL, "reason": "artifact_behavior_mismatch",
                             "detail": "%s: artifact behavior %r != evidence behavior %r"
                                       % (run_id, artifact["behavior"], behavior)})

        record_run = record.get("run_id")
        if isinstance(record_run, str) and record_run:
            expected = "%s-r%d" % (record_run, artifact["replay_index"])
            if artifact["run_id"] not in (record_run, expected):
                findings.append({"status": STATUS_FAIL, "reason": "artifact_run_mismatch",
                                 "detail": "%s: artifact run_id does not belong to evidence "
                                           "run %r (expected %r)"
                                           % (run_id, record_run, expected)})

        if not artifact["action_executed"]:
            findings.append({"status": STATUS_FAIL, "reason": "action_not_executed",
                             "detail": "%s: the artifact records action_executed=false" % run_id})
        if not artifact["actions"]:
            findings.append({"status": STATUS_FAIL, "reason": "action_not_executed",
                             "detail": "%s: the artifact logged no executed action" % run_id})
        else:
            not_executed = [item for item in artifact["actions"]
                            if isinstance(item, dict) and item.get("executed") is False]
            if not_executed:
                findings.append({"status": STATUS_FAIL, "reason": "action_not_executed",
                                 "detail": "%s: %d action(s) are logged but not executed"
                                           % (run_id, len(not_executed))})
        contract_types = _action_types(contract.get("actions"))
        if contract_types:
            artifact_types = _action_types(artifact["actions"])
            if artifact_types[:len(contract_types)] != contract_types:
                findings.append({"status": STATUS_FAIL, "reason": "action_sequence_mismatch",
                                 "detail": "%s: executed %r != contract %r"
                                           % (run_id, artifact_types, contract_types)})

        actual = _project_checks(record.get("actual"))
        observed = _project_checks(artifact["checks"])
        if observed is None or actual is None:
            findings.append({"status": STATUS_INCOMPLETE, "reason": "observation_missing",
                             "detail": "%s: artifact checks are not objects" % run_id})
        elif _canonical(observed) != _canonical(actual):
            findings.append({"status": STATUS_FAIL, "reason": "observation_mismatch",
                             "detail": "%s: artifact observations differ from the evidence "
                                       "record's actual[]" % run_id})

        if record.get("status") == STATUS_PASS and artifact["status"] != STATUS_PASS:
            findings.append({"status": STATUS_FAIL, "reason": "artifact_status_mismatch",
                             "detail": "%s: evidence claims PASS while the artifact recorded %r"
                                       % (run_id, artifact["status"])})

    # 有产物读不出来时，后续的“条数/序号/一致性”对比全部无意义：保留读取错误，
    # 不能因为少读一份就把它误报成 replay_count 矛盾。
    if len(artifacts) != len(paths):
        return {"artifacts": artifacts, **_first_failure(findings)}

    # 重放次数：证据自报 vs 真实产物条数（可数即矛盾，不是“无法证明”）。
    replay_count = record.get("replay_count")
    if not _is_int(replay_count) or replay_count != len(artifacts):
        findings.append({"status": STATUS_FAIL, "reason": "replay_count_mismatch",
                         "detail": "evidence replay_count=%r but %d execution artifact(s)"
                                   % (replay_count, len(artifacts))})
    indexes = sorted({artifact["replay_index"] for artifact in artifacts})
    if indexes != list(range(1, len(artifacts) + 1)):
        findings.append({"status": STATUS_FAIL, "reason": "replay_index_mismatch",
                         "detail": "artifact replay indexes %r are not 1..%d"
                                   % (indexes, len(artifacts))})

    # 重放一致性：用产物里的逐次观测重算，不采信自报值。
    fingerprints = [_canonical(_project_checks(artifact["checks"])) for artifact in artifacts]
    recomputed = len(set(fingerprints)) == 1
    if recomputed != bool(record.get("replay_consistent")):
        findings.append({"status": STATUS_FAIL, "reason": "replay_consistency_mismatch",
                         "detail": "artifacts say consistent=%s, evidence claims %r"
                                   % (recomputed, record.get("replay_consistent"))})

    verdict = _first_failure(findings)
    verdict["artifacts"] = artifacts
    return verdict
