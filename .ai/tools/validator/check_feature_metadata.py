#!/usr/bin/env python3
"""Feature Metadata Validator

检查 Features/*/feature.yaml 的存在性、一致性与必填字段，并核对
聚合索引 feature_index.json 是否与 metadata 同步。

只检查，不修改项目文件。

检查项:
    1. Feature metadata 存在     —— 每个 Features/<dir>/ 必须有 feature.yaml
    2. id 一致性                 —— metadata.id 必须等于目录名
    3. 必填字段                  —— id/version/category/provides/requires/interfaces/validation
    4. Test 路径存在             —— validation.test_path / self_test 指向的文件必须存在
    5. Index 同步                —— feature_index.json 与 metadata 的 id/version 比对

用法:
    python check_feature_metadata.py                 # 独立运行，输出 PASS/FAIL
作为模块导入:
    from check_feature_metadata import check_features; results = check_features(project_root)
"""

import io
import json
import os
import sys

try:
    import yaml
except ImportError:
    print("FAIL: PyYAML is required. Install with: pip install pyyaml", file=sys.stderr)
    raise SystemExit(2)

# 目录定位：本文件位于 <root>/.ai/tools/validator/ 下
_TOOL_DOTAI = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))  # .ai
PROJECT_ROOT = os.path.dirname(_TOOL_DOTAI)
FEATURES_DIR = os.path.join(PROJECT_ROOT, "Features")
INDEX_PATH = os.path.join(_TOOL_DOTAI, "context", "feature_index.json")
GRAPH_PATH = os.path.join(_TOOL_DOTAI, "context", "feature_graph.json")

REQUIRED_FIELDS = ("id", "version", "category", "provides", "requires", "interfaces", "validation")


def check_composition(blueprint: dict, project_root: str = PROJECT_ROOT) -> dict:
    """Entity Blueprint 组合合法性检查。

    检查：成员 Feature 存在；relations.requires 与顶层 requires 是否由组合满足；
    conflicts 是否同时出现。
    返回 {"failures": [...], "warnings": [...]}。
    """
    failures, warnings = [], []
    members = []
    ids = set()
    features_dir = os.path.join(project_root, "Features")
    for fid in blueprint.get("features", []) or []:
        path = os.path.join(features_dir, fid, "feature.yaml")
        if not os.path.isfile(path):
            failures.append("Unknown feature in composition: %s" % fid)
            continue
        try:
            meta = yaml.safe_load(io.open(path, encoding="utf-8"))
        except Exception as exc:
            failures.append("Invalid YAML: %s: %s" % (path, exc))
            continue
        if isinstance(meta, dict):
            members.append(meta)
            ids.add(fid)

    capability_pool = set()
    for meta in members:
        capability_pool |= set(meta.get("provides") or [])

    for meta in members:
        fid = meta.get("id")
        unmet = [req for req in (meta.get("requires") or []) if req not in capability_pool]
        for req in unmet:
            failures.append(
                "Composition incomplete:\n%s requires %s\nMissing capability provider: %s"
                % (fid, req, req)
            )
        relations = meta.get("relations") or {}
        for req in relations.get("requires", []) or []:
            if req not in capability_pool:
                failures.append(
                    "Composition incomplete:\n%s requires %s\nMissing capability provider: %s"
                    % (fid, req, req)
                )
        for conflict in relations.get("conflicts", []) or []:
            if conflict in ids:
                failures.append("Composition conflict: %s conflicts with %s (both present)" % (fid, conflict))
            elif conflict in capability_pool:
                failures.append("Composition conflict: %s conflicts with capability %s" % (fid, conflict))

    # validation.required_tests 中的 id 必须是组合成员
    validation = blueprint.get("validation") or {}
    member_for_test = set(ids)
    for tid in validation.get("required_tests", []) or []:
        if tid not in member_for_test:
            warnings.append("Composition validation: required test '%s' is not a composition member" % tid)

    return {"failures": failures, "warnings": warnings}


def check_features(project_root: str = PROJECT_ROOT, index_path: str = INDEX_PATH) -> dict:
    """执行全部 Feature metadata 检查。

    返回 {"failures": [...], "warnings": [...], "checked": int}；
    不抛异常，所有问题以失败/警告列表返回。
    """
    failures, warnings = [], []
    features_dir = os.path.join(project_root, "Features")

    feature_dirs = []
    if not os.path.isdir(features_dir):
        failures.append("Features directory not found: %s" % features_dir)
    else:
        feature_dirs = sorted(
            os.path.join(features_dir, name) for name in os.listdir(features_dir)
            if os.path.isdir(os.path.join(features_dir, name))
        )

    known_ids = set(os.path.basename(d) for d in feature_dirs)

    metas = {}   # dir_name -> parsed metadata（成功解析且字段齐全时）
    parsed_any = 0

    for feature_dir in feature_dirs:
        name = os.path.basename(feature_dir)
        path = os.path.join(feature_dir, "feature.yaml")

        # 1. metadata 存在
        if not os.path.isfile(path):
            failures.append("Feature missing metadata: %s" % os.path.relpath(feature_dir, project_root).replace("\\", "/"))
            continue
        try:
            meta = yaml.safe_load(io.open(path, encoding="utf-8"))
        except Exception as exc:
            failures.append("Invalid YAML: %s: %s" % (path, exc))
            continue
        if not isinstance(meta, dict):
            failures.append("Expected YAML mapping at root: %s" % path)
            continue
        parsed_any += 1

        # 2. id 一致性
        meta_id = meta.get("id")
        if not meta_id:
            failures.append("Feature missing metadata id: %s" % path)
        elif meta_id != name:
            failures.append("Feature id mismatch: folder=%s metadata=%s" % (name, meta_id))

        # 3. 必填字段
        missing = [field for field in REQUIRED_FIELDS if field not in meta]
        if missing:
            failures.append("Feature %s: missing required field(s): %s" % (name, ", ".join(missing)))
            continue
        metas[name] = meta

        # 4. Test 路径存在
        validation = meta.get("validation") or {}
        test_path = ""
        if isinstance(validation, dict):
            raw = str(validation.get("test_path") or "").replace("\\", "/")
            if raw:
                test_path = os.path.normpath(os.path.join(project_root, raw))
            else:
                self_test = str(validation.get("self_test") or "").replace("\\", "/")
                if self_test:
                    test_path = os.path.normpath(os.path.join(feature_dir, self_test))
        if test_path:
            if not os.path.isfile(test_path):
                failures.append("Feature %s: validation test not found: %s" % (name, test_path))
        else:
            warnings.append("Feature %s: validation has no test_path/self_test" % name)

        # 6. Relations 引用检查：关系目标必须是已知 Feature id；能力型 requires
        #    必须有某个已知 Feature 的 provides 能提供（组合可满足性）。
        relations = meta.get("relations")
        if relations is not None:
            if not isinstance(relations, dict):
                failures.append("Feature %s: relations must be a mapping" % name)
            else:
                for key in ("works_with", "commonly_used_with", "conflicts"):
                    for dst in relations.get(key, []) or []:
                        if dst not in known_ids:
                            failures.append("Unknown Feature relation: %s -> %s" % (name, dst))
        provides_pool = {}
        for other_dir in feature_dirs:
            other_name = os.path.basename(other_dir)
            other_meta_path = os.path.join(other_dir, "feature.yaml")
            if not os.path.isfile(other_meta_path):
                continue
            try:
                other_meta = yaml.safe_load(io.open(other_meta_path, encoding="utf-8"))
            except Exception:
                continue
            if isinstance(other_meta, dict):
                provides_pool[other_name] = set(other_meta.get("provides") or [])
        for req in meta.get("requires") or []:
            if not any(req in tags for fid, tags in provides_pool.items() if fid != name):
                warnings.append(
                    "Feature %s: requires capability '%s' not provided by any known Feature"
                    % (name, req)
                )

    # 5. Index 同步
    if not os.path.isfile(index_path):
        if metas or parsed_any:
            failures.append(
                "Feature index not found: %s\nPlease run: python .ai/tools/feature_registry/build_feature_index.py" % index_path
            )
    else:
        try:
            with io.open(index_path, encoding="utf-8") as f:
                index = json.load(f)
        except Exception as exc:
            failures.append("Invalid JSON: %s: %s" % (index_path, exc))
            index = {}
        index_features = {}
        if isinstance(index.get("features"), list):
            index_features = {f.get("id"): f for f in index["features"] if isinstance(f, dict)}
        for name, meta in sorted(metas.items()):
            entry = index_features.get(name)
            if entry is None:
                failures.append("Feature index outdated: %s not in index. Please run: build_feature_index.py" % name)
                continue
            if str(entry.get("version", "")) != str(meta.get("version")):
                failures.append(
                    "Feature index outdated: %s metadata changed (index v%s, metadata v%s). Please run: build_feature_index.py"
                    % (name, entry.get("version"), meta.get("version"))
                )
        for extra_id in sorted(set(index_features) - set(metas)):
            warnings.append("Feature index stale entry: %s is in index but has no valid metadata. Please run: build_feature_index.py" % extra_id)

    return {"failures": failures, "warnings": warnings, "checked": parsed_any}


def main() -> int:
    print("Feature Metadata Validator")
    result = check_features()
    print("Checked feature metadata: %d" % result["checked"])
    if result["failures"]:
        print("\nFAILURES")
        for failure in result["failures"]:
            print("  - " + failure)
    if result["warnings"]:
        print("\nWARNINGS")
        for warning in result["warnings"]:
            print("  - " + warning)
    if result["failures"]:
        print("\nFAIL: %d error(s), %d warning(s)" % (len(result["failures"]), len(result["warnings"])))
        return 1
    if result["warnings"]:
        print("\nWARNING: 0 error(s), %d warning(s)" % len(result["warnings"]))
        return 0
    print("\nPASS: 0 error(s), 0 warning(s)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
