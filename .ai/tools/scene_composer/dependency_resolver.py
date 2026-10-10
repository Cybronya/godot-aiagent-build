#!/usr/bin/env python3
"""Feature Dependency Resolver

检查 Scene Blueprint / Entity Blueprint 中 Feature 组合的依赖：
每个成员的顶层 requires（能力标签）与 relations.requires 必须由组合内
其他成员的 provides 满足。

输出消息约定（与任务规格一致）：
    Composition Error: contact_damage requires damage_receiver
    Missing dependency: damage_receiver (provider: health)
"""

import os

import yaml

_TOOL_DOTAI = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))  # .ai
PROJECT_ROOT = os.path.dirname(_TOOL_DOTAI)
FEATURES_DIR = os.path.join(PROJECT_ROOT, "Features")
INDEX_PATH = os.path.join(_TOOL_DOTAI, "context", "feature_index.json")


def load_index(path: str = INDEX_PATH) -> list:
    import io
    import json
    with io.open(path, encoding="utf-8") as f:
        return (json.load(f) or {}).get("features", [])


def _provides_of(feature_id: str, index: list, features_dir: str) -> set:
    for entry in index:
        if entry.get("id") == feature_id:
            return set(entry.get("provides") or [])
    # 索引缺失时退回直接读 metadata
    path = os.path.join(features_dir, feature_id, "feature.yaml")
    if os.path.isfile(path):
        meta = yaml.safe_load(open(path, encoding="utf-8")) or {}
        return set(meta.get("provides") or [])
    return set()


def _requires_of(feature_id: str, index: list, features_dir: str) -> tuple:
    """返回 (顶层 requires 能力标签, relations.requires 能力标签)。"""
    for entry in index:
        if entry.get("id") == feature_id:
            relations = entry.get("relations") or {}
            return (
                list(entry.get("requires") or []),
                list(relations.get("requires") or []),
            )
    path = os.path.join(features_dir, feature_id, "feature.yaml")
    if os.path.isfile(path):
        meta = yaml.safe_load(open(path, encoding="utf-8")) or {}
        relations = meta.get("relations") or {}
        return (
            list(meta.get("requires") or []),
            list(relations.get("requires") or []),
        )
    return [], []


def resolve(features: list, index: list, features_dir: str = FEATURES_DIR) -> dict:
    """组合依赖检查。

    返回:
        {
          "ok": bool,
          "errors": [str],      # Composition Error 消息
          "missing": [str],     # Missing dependency 消息
          "unknown": [str],     # 组合内不存在的 Feature id
        }
    """
    errors, missing, unknown = [], [], []
    ids = set(features)

    provides_pool = {}   # capability tag -> [provider feature id]
    for fid in features:
        if not os.path.isdir(os.path.join(features_dir, fid)):
            unknown.append(fid)
            continue
        for tag in _provides_of(fid, index, features_dir):
            provides_pool.setdefault(tag, []).append(fid)

    for fid in features:
        if fid in unknown:
            continue
        for req in _requires_of(fid, index, features_dir)[0] + _requires_of(fid, index, features_dir)[1]:
            providers = provides_pool.get(req, [])
            if fid in providers and len(providers) == 1:
                providers = []   # 只有自己能提供，视为未满足
            if not providers:
                errors.append("Composition Error: %s requires %s" % (fid, req))
                missing.append("Missing dependency: %s" % req)
            # 已满足的 requires 不输出

    return {
        "ok": not errors and not unknown,
        "errors": errors,
        "missing": missing,
        "unknown": unknown,
    }


def main(argv=None) -> int:
    import argparse
    import json
    import sys

    parser = argparse.ArgumentParser(description="Resolve feature composition dependencies.")
    parser.add_argument("features", nargs="+", help="Feature ids in the composition")
    parser.add_argument("--index", default=INDEX_PATH, help="feature_index.json path")
    args = parser.parse_args(argv)

    index = []
    if os.path.isfile(args.index):
        with open(args.index, encoding="utf-8") as f:
            index = (json.load(f) or {}).get("features", [])
    result = resolve(args.features, index)
    for line in result["errors"] + result["missing"]:
        print(line)
    for fid in result["unknown"]:
        print("Unknown Feature: %s" % fid)
    print("PASS: dependencies satisfied" if result["ok"] else "FAIL: unmet dependencies")
    return 0 if result["ok"] else 1


if __name__ == "__main__":
    import sys
    sys.exit(main())
