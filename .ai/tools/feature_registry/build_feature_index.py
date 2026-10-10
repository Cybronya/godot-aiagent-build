#!/usr/bin/env python3
"""Feature Index Generator (v2)

扫描 Features/*/feature.yaml，生成聚合索引 feature_index.json 与 Feature Graph。

职责边界:
    - 本工具负责「数据生成」，discover_feature.py 只负责「查询」。
    - 生成结果是缓存（Generated Data），Source of Truth 永远是各 feature.yaml。

用法:
    python build_feature_index.py                     # 默认生成到 .ai/context/feature_index.json
    python build_feature_index.py --features-dir DIR --out FILE   # 测试/自定义

输出格式（索引 v2，含 relations）:
    {
      "registry_version": 2,
      "generated_at": "<ISO8601>",
      "features": [
        {
          "id": "...", "version": "...", "category": "...",
          "provides": [...], "requires": [...], "interfaces": [...],
          "signals": [...],
          "validation": {"test_path": "<test_file_path>"},
          "relations": {"works_with": [...], "commonly_used_with": [...],
                        "conflicts": [...], "entity_roles": [...]}
"""

import argparse
import io
import json
import os
import sys
from datetime import datetime, timezone

try:
    import yaml
except ImportError:
    print("FAIL: PyYAML is required. Install with: pip install pyyaml", file=sys.stderr)
    raise SystemExit(2)

# 目录定位：本文件位于 <root>/.ai/tools/feature_registry/ 下（root 是 .ai 的上级）
_TOOL_DOTAI = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))  # .ai
TOOL_ROOT = os.path.dirname(_TOOL_DOTAI)  # 项目根
FEATURES_DIR = os.path.join(TOOL_ROOT, "Features")
CONTEXT_DIR = os.path.join(_TOOL_DOTAI, "context")
INDEX_PATH = os.path.join(CONTEXT_DIR, "feature_index.json")
GRAPH_PATH = os.path.join(CONTEXT_DIR, "feature_graph.json")

RELATION_KEYS = ("works_with", "commonly_used_with", "conflicts", "entity_roles")

REQUIRED_FIELDS = ("id", "version", "category", "provides", "requires", "interfaces", "validation")
REGISTRY_VERSION = 2   # v2: relations 字段


def load_metadata(feature_dir: str) -> dict:
    """读取单个 feature.yaml；解析失败或非法映射时返回 None 并附错误信息。"""
    path = os.path.join(feature_dir, "feature.yaml")
    try:
        meta = yaml.safe_load(io.open(path, encoding="utf-8"))
    except Exception as exc:
        return {"__error__": "Invalid YAML (%s): %s" % (path, exc)}
    if not isinstance(meta, dict):
        return {"__error__": "Expected YAML mapping at root: %s" % path}
    return meta


def collect_interfaces(meta: dict) -> tuple:  # noqa: D401 - 保留原注释结构
    """从 interfaces 聚合扁平名称列表与信号名单（供 Discovery 展示用）。"""
    block = meta.get("interfaces") or {}
    names, signals = [], []
    if isinstance(block, dict):
        for key in ("methods", "exports", "signals"):
            entries = block.get(key) or []
            for entry in entries:
                if isinstance(entry, dict) and entry.get("name"):
                    names.append(str(entry["name"]))
                    if key == "signals":
                        signals.append(str(entry["name"]))
        for name in block.get("names", []):
            names.append(str(name))
    return names, signals


def resolve_test_path(feature_dir: str, base_dir: str, validation: dict) -> str:
    """把 validation.test_path（项目根相对）或 self_test（Feature 目录相对）解析为项目根相对路径字符串。"""
    if not isinstance(validation, dict):
        return ""
    test_path = str(validation.get("test_path") or "").replace("\\", "/")
    if test_path:
        return os.path.normpath(os.path.join(base_dir, test_path)).replace("\\", "/")
    self_test = str(validation.get("self_test") or "").replace("\\", "/")
    if self_test:
        return os.path.normpath(os.path.join(feature_dir, self_test)).replace("\\", "/")
    return ""


def build_index(features_dir: str) -> tuple:
    """扫描 features_dir，返回 (records, errors)。"""
    if not os.path.isdir(features_dir):
        return [], ["Features directory not found: %s" % features_dir]
    records, errors = [], []
    for name in sorted(os.listdir(features_dir)):
        feature_dir = os.path.join(features_dir, name)
        if not os.path.isdir(feature_dir):
            continue
        meta = load_metadata(feature_dir)
        if "__error__" in meta:
            errors.append("Feature %s: %s" % (name, meta["__error__"]))
            continue
        missing = [field for field in REQUIRED_FIELDS if field not in meta]
        if missing:
            errors.append("Feature %s: missing required fields: %s" % (name, ", ".join(missing)))
            continue
        if meta["id"] != name:
            errors.append("Feature id mismatch: folder=%s metadata=%s" % (name, meta["id"]))
            continue
        interfaces, signals = collect_interfaces(meta)
        relations = normalize_relations(meta.get("relations"))
        if isinstance(relations, str):   # 错误信息
            errors.append("Feature %s: %s" % (name, relations))
            relations = {}
        records.append({
            "id": meta["id"],
            "version": str(meta["version"]),
            "category": meta["category"],
            "provides": list(meta["provides"] or []),
            "requires": list(meta["requires"] or []),
            "interfaces": interfaces,
            "signals": signals,
            "validation": {"test_path": resolve_test_path(feature_dir, features_dir, meta["validation"])},
            "relations": relations,
        })
    return records, errors


def normalize_relations(raw) -> dict:
    """规整 relations 节；非法值返回错误信息字符串。"""
    if raw is None:
        return {}
    if not isinstance(raw, dict):
        return "relations must be a mapping"
    out = {}
    for key in RELATION_KEYS:
        value = raw.get(key, [])
        if value is None:
            value = []
        if not isinstance(value, list) or not all(isinstance(x, str) and x.strip() for x in value):
            return "relations.%s must be a list of strings" % key
        out[key] = list(value)
    # 关系型 requires（能力标签）随索引下发给消费方（compose_features /
    # dependency_resolver 据此做组合满足性检查）；语义 requires 仍在顶层。
    rel_requires = raw.get("requires", [])
    if rel_requires is None:
        rel_requires = []
    if not isinstance(rel_requires, list) or not all(isinstance(x, str) and x.strip() for x in rel_requires):
        return "relations.requires must be a list of strings"
    out["requires"] = list(rel_requires)
    for key in set(raw) - set(RELATION_KEYS) - {"requires"}:
        return "unknown relations key: %s" % key
    return out


def build_graph(records: list) -> dict:
    """由索引记录构建 Feature Graph：节点 = id，边 = works_with/commonly_used_with。"""
    ids = set(r["id"] for r in records)
    edges, unknown = [], []
    seen = set()
    for record in records:
        src = record["id"]
        relations = record.get("relations") or {}
        for key in ("works_with", "commonly_used_with"):
            for dst in relations.get(key, []):
                if dst not in ids:
                    unknown.append("%s -> %s" % (src, dst))
                    continue
                # 有向边（from=声明方）；同对同类型去重
                edge_key = (src, dst, key)
                if edge_key in seen:
                    continue
                seen.add(edge_key)
                edges.append({"from": src, "to": dst, "type": key})
    return {"nodes": sorted(ids), "edges": edges}, unknown


def write_index(records: list, out_path: str) -> None:
    index = {
        "registry_version": REGISTRY_VERSION,
        "generated_at": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "features": records,
    }
    parent = os.path.dirname(out_path)
    if parent and not os.path.isdir(parent):
        os.makedirs(parent)
    with io.open(out_path, "w", encoding="utf-8") as f:
        json.dump(index, f, ensure_ascii=False, indent=2)
        f.write("\n")


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description="Generate aggregated feature_index.json from Features/*/feature.yaml.")
    parser.add_argument("--features-dir", default=FEATURES_DIR, help="Features root directory")
    parser.add_argument("--out", default=INDEX_PATH, help="Output index file path")
    args = parser.parse_args(argv)

    records, errors = build_index(args.features_dir)
    if errors:
        for error in errors:
            print("FAIL: " + error, file=sys.stderr)
        return 1
    write_index(records, args.out)
    graph, unknown = build_graph(records)
    graph_path = args.out.replace("feature_index.json", "feature_graph.json") if "feature_index.json" in args.out else os.path.join(os.path.dirname(args.out), "feature_graph.json")
    if unknown:
        for item in unknown:
            print("FAIL: Unknown Feature relation: %s" % item, file=sys.stderr)
        return 1
    with io.open(graph_path, "w", encoding="utf-8") as f:
        json.dump(graph, f, ensure_ascii=False, indent=2)
        f.write("\n")
    print("OK: %d feature(s) -> %s" % (len(records), args.out))
    print("OK: %d node(s), %d edge(s) -> %s" % (len(graph["nodes"]), len(graph["edges"]), graph_path))
    return 0


if __name__ == "__main__":
    sys.exit(main())
