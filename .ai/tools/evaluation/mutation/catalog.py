#!/usr/bin/env python3
"""Mutation Catalog —— manifest 加载与静态校验（Phase 1.59）。

Catalog 只描述「打算注入什么缺陷」，**不是**执行结论。文件里没有、也不允许有
`killed: true` 之类的自报字段：Verdict 一律由 `harness.py` 用真实执行结果产生。
"""

from __future__ import annotations

import os
import sys

_HERE = os.path.dirname(os.path.abspath(__file__))
_EVALUATION = os.path.dirname(_HERE)
_TOOLS = os.path.dirname(_EVALUATION)
PROJECT_ROOT = os.path.dirname(os.path.dirname(_TOOLS))

for _path in (_EVALUATION, os.path.join(_TOOLS, "scene_composer"),
              os.path.join(_TOOLS, "validator")):
    if _path not in sys.path:
        sys.path.insert(0, _path)

import operators                                                   # noqa: E402
import workspace                                                   # noqa: E402
import check_behavior_evidence as stage                            # noqa: E402

try:
    import yaml
except ImportError:                                                # pragma: no cover
    print("FAIL: PyYAML is required. Install with: pip install pyyaml", file=sys.stderr)
    raise SystemExit(2)

SCHEMA_ID = "evaluation_mutation_catalog"
SCHEMA_VERSION = 1
DEFAULT_CATALOG = os.path.join(_HERE, "mutation_catalog.yaml")
REQUIRED_FIELDS = ("mutation_id", "feature_id", "behavior_id", "mutation_type",
                   "target_file", "target_function", "operator", "anchor",
                   "expected_behavior_change", "effectiveness", "evaluation")


class CatalogError(Exception):
    """整个 manifest 不可用（结构错误），调用方必须退出而不是"跳过几条"。"""


def load(path: str = "", defaults_from=None) -> list:
    path = path or DEFAULT_CATALOG
    try:
        with open(path, encoding="utf-8") as handle:
            document = yaml.safe_load(handle.read())
    except OSError as exc:
        raise CatalogError("cannot read %s: %s" % (path, exc))
    except yaml.YAMLError as exc:
        raise CatalogError("%s is not valid YAML: %s" % (path, exc))
    if not isinstance(document, dict):
        raise CatalogError("%s is not a mapping" % path)
    schema = document.get("schema") or {}
    if schema.get("id") != SCHEMA_ID:
        raise CatalogError("%s has unknown schema %r" % (path, schema.get("id")))
    if int(schema.get("version") or 0) != SCHEMA_VERSION:
        raise CatalogError("%s has unsupported version %r" % (path, schema.get("version")))
    raw = document.get("mutations")
    if not isinstance(raw, list) or not raw:
        raise CatalogError("%s declares no mutations" % path)
    defaults = document.get("defaults") or {}
    entries = []
    for record in raw:
        if not isinstance(record, dict):
            raise CatalogError("mutation entry is not a mapping: %r" % (record,))
        entry = dict(defaults)
        entry.update(record)
        entries.append(entry)
    problems = structural_problems(entries)
    if problems:
        raise CatalogError("; ".join(problems))
    return entries


def structural_problems(entries) -> list:
    problems = []
    ids = [str(entry.get("mutation_id") or "") for entry in entries]
    for duplicate in sorted({item for item in ids if ids.count(item) > 1}):
        problems.append("duplicate mutation_id %r" % duplicate)
    for entry in entries:
        name = str(entry.get("mutation_id") or "<unnamed>")
        if not entry.get("mutation_id"):
            problems.append("a mutation entry has no mutation_id")
        missing = [field for field in REQUIRED_FIELDS if not entry.get(field)]
        if missing:
            problems.append("%s is missing %s" % (name, ", ".join(missing)))
        if str(entry.get("operator") or "") not in operators.OPERATOR_IDS:
            problems.append("%s uses unknown operator %r" % (name, entry.get("operator")))
        effectiveness = entry.get("effectiveness")
        if isinstance(effectiveness, dict):
            if not effectiveness.get("check"):
                problems.append("%s effectiveness has no check" % name)
            if "mutant" not in effectiveness:
                problems.append("%s effectiveness has no mutant predicate" % name)
        elif effectiveness:
            problems.append("%s effectiveness is not a mapping" % name)
        evaluation = entry.get("evaluation")
        if isinstance(evaluation, dict):
            if not isinstance(evaluation.get("expect"), list) or not evaluation["expect"]:
                problems.append("%s evaluation.expect must be a non-empty list" % name)
        elif evaluation:
            problems.append("%s evaluation is not a mapping" % name)
    return problems


def supported_pairs(features_dir: str = "") -> dict:
    """动态读取正式支持集：`{feature: {behavior: True}}`（不硬编码 23/60）。"""
    import evidence_adapter as adapter
    supported = adapter.supported_set(features_dir)
    return {feature: {behavior: True for behavior in behaviors}
            for feature, behaviors in supported["features"].items()}, supported


def preconditions(entry: dict, supported: dict, root: str = PROJECT_ROOT) -> dict:
    """运行前检查（只读）。返回 `{ok, reason, detail, path, sha256}`。

    这些检查失败一律是 **NOT_RUN**：mutation 根本没有被应用，既不能算检出，
    也不能算漏检。锚点类问题（应用阶段才发现）才是 INVALID_MUTANT。
    """
    feature = str(entry.get("feature_id") or "")
    behavior = str(entry.get("behavior_id") or "")
    if feature not in supported:
        return {"ok": False, "reason": "unknown_feature",
                "detail": "%r is not in the declared support set" % feature}
    if behavior not in supported[feature]:
        return {"ok": False, "reason": "unknown_behavior",
                "detail": "%r is not declared by %s" % (behavior, feature)}
    target = str(entry.get("target_file") or "")
    path = target if os.path.isabs(target) else os.path.join(root, target)
    try:
        resolved = workspace.require_regular_file(path, root)
    except workspace.WorkspaceError as exc:
        return {"ok": False, "reason": "target_rejected", "detail": str(exc)}
    digest = workspace.sha256_file(resolved)
    declared = str(entry.get("source_sha256") or "")
    if declared and declared != digest:
        return {"ok": False, "reason": "source_hash_mismatch", "path": resolved,
                "detail": "catalog pins %s, file is %s (catalog is stale)"
                          % (declared[:12], digest[:12]), "sha256": digest}
    return {"ok": True, "path": resolved, "sha256": digest}


def stage_expected(predicate, observation):
    """用 Validator 的比较语义判断一条观测是否满足谓词（`None` = 无法判定）。

    复用 `check_behavior_evidence.expected_holds`，因此 Mutation 的「缺陷是否符合声明」
    与 Validator 的「行为是否符合契约」用的是同一套 equals / count / min / max 规则，
    不会出现两套比较语义互相打架。
    """
    if not isinstance(predicate, dict) or not isinstance(observation, dict) or not observation:
        return None
    return stage.expected_holds(predicate, observation)


def select(entries, wanted) -> list:
    if not wanted or "ALL" in [str(item).upper() for item in wanted]:
        return entries
    wanted_upper = [str(item).upper() for item in wanted]
    known = {str(entry.get("mutation_id")).upper() for entry in entries}
    unknown = [item for item in wanted_upper if item not in known]
    if unknown:
        raise CatalogError("unknown mutation ids: %s" % ", ".join(unknown))
    return [entry for entry in entries
            if str(entry.get("mutation_id")).upper() in wanted_upper]
