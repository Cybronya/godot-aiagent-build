#!/usr/bin/env python3
"""Holdout 数据集生命周期与隔离（Phase 1.60）。

定位：给评估侧 Holdout（Phase 1.58 的 E5 语义）补上**数据集身份与生命周期**，
不改变既有 `NOT_EVALUATED(holdout_unavailable)` 语义，不虚构不存在的训练系统
（任务书 §4.2：当前项目没有完整训练系统，先建立接口边界与数据分类）。

生命周期（任务书 §4.1）：

    CREATED -> VALIDATED -> SEALED -> CONSUMED
                                   -> INVALIDATED
    VALIDATED -> INVALIDATED

隔离规则（任务书 §4.2）：

    1. Holdout 不得自动进入训练数据集（is_training_data 恒 False，字段只读）。
    2. Holdout 不得参与普通参数调优（is_tuning_data 恒 False）。
    3. Holdout 不得自动生成新的正式 Baseline（本模块不提供任何基线写入口）。
    4. 已消费的 Holdout 保留 usage_history（追加式）。
    5. 内容变化后必须重新验证（SEALED 后 digest 不匹配 -> 使用被拒）。
    6. 被污染的 Holdout（与训练/调优/基线生成数据重叠）-> INVALIDATED，
       不得继续作为独立验证依据。
    7. Holdout 评估结果不自动变成训练标签（本模块无任何标签写入口）。
    8. 重复使用：每次使用必须登记 usage；重复 SEALED 后未登记的消费被拒绝。

登记表：evaluation/holdout/holdout_datasets.json（数据集记录追加式更新）。
"""

from __future__ import annotations

import hashlib
import json
import os
from datetime import datetime, timezone

_HERE = os.path.dirname(os.path.abspath(__file__))
EVALUATION_DIR = _HERE
HOLDOUT_DIRNAME = os.path.join(_HERE, "holdout")
REGISTRY_PATH = os.path.join(HOLDOUT_DIRNAME, "holdout_datasets.json")

SCHEMA = "holdout_dataset_registry"
SCHEMA_VERSION = 1

# ---------------------------------------------------------------- 生命周期
CREATED = "CREATED"
VALIDATED = "VALIDATED"
SEALED = "SEALED"
CONSUMED = "CONSUMED"
INVALIDATED = "INVALIDATED"

LIFECYCLE_STATES = (CREATED, VALIDATED, SEALED, CONSUMED, INVALIDATED)

# 只有 SEALED 状态可以用于独立评估（CONSUMED 需显式重开策略，本模块不支持）
USABLE_STATES = (SEALED,)

LEGAL_TRANSITIONS = {
    CREATED: {VALIDATED, INVALIDATED},
    # Phase 1.63 幂等修复：seal_dataset_signed 内部会先 validate_dataset，
    # 已 VALIDATED 的数据集重验必须允许（幂等），否则合法封存被拒。
    VALIDATED: {VALIDATED, SEALED, INVALIDATED},
    SEALED: {CONSUMED, INVALIDATED},
    CONSUMED: {INVALIDATED},
    INVALIDATED: set(),
}

POLLUTION_REASONS = ("overlap_with_training", "overlap_with_tuning",
                     "overlap_with_baseline_source", "manual_invalidation")


class HoldoutError(ValueError):
    """Holdout 登记非法（非法转换 / 缺字段 / 摘要缺失）。"""


def now_iso() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def dataset_digest(paths: list) -> dict:
    """对 Holdout 数据集内容（证据包文件列表）计算 SHA256 摘要。

    摘要覆盖：每个文件的相对名 + 字节内容（排序后串联），任何内容变化
    都会改变摘要。
    """
    hasher = hashlib.sha256()
    for path in sorted(paths):
        hasher.update(os.path.basename(path).encode("utf-8"))
        with open(path, "rb") as handle:
            hasher.update(handle.read())
    return {"scheme": "holdout-dataset-digest-v1",
            "digest": hasher.hexdigest(), "files": len(paths)}


# ---------------------------------------------------------------- 登记表

def _load_registry(path: str = "") -> dict:
    target = path or REGISTRY_PATH
    if not os.path.isfile(target):
        return {"schema": SCHEMA, "schema_version": SCHEMA_VERSION, "datasets": []}
    with open(target, "r", encoding="utf-8") as handle:
        document = json.load(handle)
    if not isinstance(document, dict) or not isinstance(document.get("datasets"), list):
        raise HoldoutError("holdout registry %s is malformed" % target)
    return document


def _save_registry(registry: dict, path: str = "") -> None:
    target = path or REGISTRY_PATH
    os.makedirs(os.path.dirname(target), exist_ok=True)
    tmp = target + ".tmp"
    with open(tmp, "w", encoding="utf-8", newline="\n") as handle:
        json.dump(registry, handle, ensure_ascii=False, indent=2)
        handle.write("\n")
    os.replace(tmp, target)


def _find(registry: dict, holdout_id: str, dataset_version) -> dict | None:
    for entry in registry.get("datasets") or []:
        if (str(entry.get("holdout_id")) == str(holdout_id)
                and str(entry.get("dataset_version")) == str(dataset_version)):
            return entry
    return None


def create_dataset(holdout_id: str, dataset_version, *, source: str,
                   feature_ids: list, behavior_ids: list, scenario_ids: list = None,
                   contract_versions: list = None, notes: str = "",
                   registry_path: str = "") -> dict:
    """登记一个 Holdout 数据集（CREATED）。"""
    registry = _load_registry(registry_path)
    if _find(registry, holdout_id, dataset_version) is not None:
        raise HoldoutError("holdout %s v%s already exists"
                           % (holdout_id, dataset_version))
    record = {
        "holdout_id": str(holdout_id),
        "dataset_version": str(dataset_version),
        "source": str(source),
        "created_at": now_iso(),
        "validated_at": "", "sealed_at": "", "invalidated_at": "",
        "content_digest": "", "digest_scheme": "",
        "feature_ids": [str(item) for item in feature_ids or []],
        "behavior_ids": [str(item) for item in behavior_ids or []],
        "scenario_ids": [str(item) for item in scenario_ids or []],
        "contract_versions": [str(item) for item in contract_versions or []],
        "is_training_data": False,
        "is_tuning_data": False,
        "usage_history": [],
        "pollution": [],
        "notes": str(notes or ""),
        "status": CREATED,
    }
    registry["datasets"].append(record)
    _save_registry(registry, registry_path)
    return record


def _transition(record: dict, status: str) -> None:
    current = str(record.get("status"))
    if status not in LIFECYCLE_STATES:
        raise HoldoutError("unknown holdout status %r" % status)
    if status not in LEGAL_TRANSITIONS.get(current, set()):
        raise HoldoutError("illegal holdout transition %s -> %s" % (current, status))
    record["status"] = status


def validate_dataset(holdout_id: str, dataset_version, *, evidence_paths: list,
                     registry_path: str = "") -> dict:
    """验证阶段：计算内容摘要并固定（VALIDATED）。"""
    registry = _load_registry(registry_path)
    record = _find(registry, holdout_id, dataset_version)
    if record is None:
        raise HoldoutError("unknown holdout %s v%s" % (holdout_id, dataset_version))
    _transition(record, VALIDATED)
    computed = dataset_digest(evidence_paths)
    record["content_digest"] = computed["digest"]
    record["digest_scheme"] = computed["scheme"]
    record["dataset_files"] = computed["files"]
    record["validated_at"] = now_iso()
    _save_registry(registry, registry_path)
    return dict(record)


def seal_dataset(holdout_id: str, dataset_version, *, evidence_paths: list,
                 registry_path: str = "") -> dict:
    """封存：SEALED 状态 + 封存时摘要。封存后内容变化 -> 使用被拒。"""
    registry = _load_registry(registry_path)
    record = _find(registry, holdout_id, dataset_version)
    if record is None:
        raise HoldoutError("unknown holdout %s v%s" % (holdout_id, dataset_version))
    _transition(record, SEALED)
    computed = dataset_digest(evidence_paths)
    record["content_digest"] = computed["digest"]
    record["digest_scheme"] = computed["scheme"]
    record["dataset_files"] = computed["files"]
    record["sealed_at"] = now_iso()
    _save_registry(registry, registry_path)
    return dict(record)


def seal_dataset_signed(holdout_id: str, dataset_version, *, evidence_paths: list,
                        key_id: str, trust_store=None, project_root: str = "",
                        registry_path: str = "") -> dict:
    """Phase 1.61：封存并生成来源签名（scope=seal_holdout，外部信任根验签）。

    签名绑定：holdout_id / dataset_version / 数据集摘要 / 封存时间 / 来源 /
    生成主体特征（feature_ids/behavior_ids）/ 签名密钥 ID / 数据集用途。
    签名由**封存主体**在封存时生成；消费时用外部信任根验证。
    库缺失或密钥不可签发 → HoldoutError（fail-closed，不静默降级为无签名封存）。
    （内部先 validate 后 seal，遵守 CREATED -> VALIDATED -> SEALED 状态机。）
    """
    validate_dataset(holdout_id, dataset_version, evidence_paths=evidence_paths,
                     registry_path=registry_path)
    record = seal_dataset(holdout_id, dataset_version,
                          evidence_paths=evidence_paths,
                          registry_path=registry_path)
    try:
        from provenance import signing as provenance_signing
    except ImportError as exc:
        raise HoldoutError("provenance signing unavailable: %s" % exc) from exc
    envelope = provenance_signing.sign_object(
        object_type="holdout_dataset",
        object_id=record["holdout_id"],
        object_version=record["dataset_version"],
        content_digest=record["content_digest"],
        digest_scheme=record["digest_scheme"],
        key_id=key_id,
        trust_store=trust_store,
        project_root=project_root,
        binding={"source": record.get("source", ""),
                 "created_at": record.get("created_at", ""),
                 "sealed_at": record.get("sealed_at", ""),
                 "feature_ids": list(record.get("feature_ids") or []),
                 "behavior_ids": list(record.get("behavior_ids") or []),
                 "dataset_files": record.get("dataset_files"),
                 "purpose": "independent generalization evaluation"})
    registry = _load_registry(registry_path)
    current = _find(registry, holdout_id, dataset_version)
    if current is None:
        raise HoldoutError("holdout %s v%s vanished during signing"
                           % (holdout_id, dataset_version))
    current["provenance_signature"] = envelope
    _save_registry(registry, registry_path)
    return dict(current)


def invalidate_dataset(holdout_id: str, dataset_version, *, reason: str,
                       registry_path: str = "") -> dict:
    """失效（污染 / 撤销）。INVALIDATED 是终态。"""
    registry = _load_registry(registry_path)
    record = _find(registry, holdout_id, dataset_version)
    if record is None:
        raise HoldoutError("unknown holdout %s v%s" % (holdout_id, dataset_version))
    _transition(record, INVALIDATED)
    record["invalidated_at"] = now_iso()
    record["pollution"].append({"reason": str(reason or "manual_invalidation"),
                                "at": record["invalidated_at"]})
    _save_registry(registry, registry_path)
    return dict(record)


def check_usable(record: dict, *, evidence_paths: list | None = None) -> dict:
    """使用时复核：状态 + 摘要 + 数据分类（fail-closed）。"""
    result = {"usable": False, "status": str(record.get("status")), "reason": ""}
    if result["status"] not in USABLE_STATES:
        result["reason"] = ("holdout status is %r (usable only when SEALED)"
                            % result["status"])
        return result
    if record.get("is_training_data") or record.get("is_tuning_data"):
        result["reason"] = "holdout flagged as training/tuning data (must never happen)"
        return result
    if record.get("pollution"):
        result["reason"] = "holdout has pollution records: %s" % (
            ", ".join(item.get("reason", "?") for item in record["pollution"][:3]))
        return result
    if not record.get("content_digest"):
        result["reason"] = "holdout has no sealed content digest (not sealed properly)"
        return result
    if evidence_paths is not None:
        computed = dataset_digest(evidence_paths)
        if computed["digest"] != record["content_digest"]:
            result["reason"] = ("holdout content changed after sealing: %s != %s"
                                % (computed["digest"][:12],
                                   str(record["content_digest"])[:12]))
            return result
    result["usable"] = True
    return result


def record_usage(holdout_id: str, dataset_version, *, purpose: str,
                 run_ref: str = "", registry_path: str = "") -> dict:
    """登记一次使用（追加式 usage_history；SEALED -> CONSUMED）。"""
    registry = _load_registry(registry_path)
    record = _find(registry, holdout_id, dataset_version)
    if record is None:
        raise HoldoutError("unknown holdout %s v%s" % (holdout_id, dataset_version))
    usable = check_usable(record)
    if not usable["usable"]:
        raise HoldoutError("holdout %s v%s is not usable: %s"
                           % (holdout_id, dataset_version, usable["reason"]))
    _transition(record, CONSUMED)
    record["usage_history"].append({
        "purpose": str(purpose or "evaluation"),
        "run_ref": str(run_ref or ""),
        "at": now_iso(),
    })
    _save_registry(registry, registry_path)
    return dict(record)


def reuse_policy_check(record: dict) -> dict:
    """重复使用检查：CONSUMED 后再次 SEALED 使用需要显式重新封存（本模块
    不提供「自动重开」——重复运行不得被错误计入多份独立样本）。"""
    if record.get("status") == CONSUMED and record.get("usage_history"):
        return {"allow_reuse": False,
                "reason": "holdout already consumed %d time(s); re-seal explicitly "
                          "with a new dataset_version for another independent sample"
                          % len(record["usage_history"])}
    return {"allow_reuse": True, "reason": ""}


def find_dataset(holdout_id: str, dataset_version=None,
                 registry_path: str = "") -> dict | None:
    """查找数据集记录；dataset_version 为空时取该 id 的最新一条。"""
    registry = _load_registry(registry_path)
    matches = [entry for entry in registry.get("datasets") or []
               if str(entry.get("holdout_id")) == str(holdout_id)]
    if dataset_version is not None:
        matches = [entry for entry in matches
                   if str(entry.get("dataset_version")) == str(dataset_version)]
    if not matches:
        return None
    matches.sort(key=lambda entry: str(entry.get("dataset_version")))
    return matches[-1]
