#!/usr/bin/env python3
"""统一资产搜索入口：Features 资产库 + code_library 片段库。

Agent 检索可复用代码的唯一入口。先搜本项目的 Feature 资产（可直接复用），
再搜外部收集的参考片段（需抽象简化后 Feature 化）。

用法:
  python search_assets.py --query "hit flash damage"
  python search_assets.py --query "camera follow" --kind snippet --domain movement
  python search_assets.py --query "health" --json

数据源（只读）:
  - .ai/context/feature_index.json   (Features 资产，由 build_feature_index.py 生成)
  - code_library/catalog.yaml        (外部片段，由 github_collector.py catalog 生成)
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

AI_ROOT = Path(__file__).resolve().parents[2]  # .ai/
FEATURE_INDEX = AI_ROOT / "context" / "feature_index.json"
SKILL_TOOLS = AI_ROOT / "skills" / "foundation" / "godot-gdscript" / "tools"
sys.path.insert(0, str(SKILL_TOOLS))
from github_collector import CATALOG_YAML, _read_catalog_entries  # noqa: E402


def _tokens(query: str) -> list[str]:
    return [t for t in query.lower().replace("-", "_").split() if t]


def _hit(fields: list[str], token: str) -> int:
    """返回该 token 在字段列表中的得分（id 精确/前缀命中权重更高）。"""
    score = 0
    for i, f in enumerate(fields):
        fl = f.lower()
        if fl == token:
            score += 4 - min(i, 2)
        elif token in fl:
            score += 2 - min(i, 1)
    return score


def _feature_fields(f: dict) -> list[str]:
    rel = f.get("relations") or {}
    iface = f.get("interfaces") or {}
    if isinstance(iface, list):  # 索引已展平为名字列表
        export_names = [str(x) for x in iface]
    else:
        export_names = [
            e.get("name", "") if isinstance(e, dict) else str(e)
            for e in iface.get("exports", [])]
    return [
        f.get("id", ""), f.get("category", ""),
        " ".join(f.get("provides", [])),
        " ".join(f.get("requires", [])),
        " ".join(export_names),
        " ".join(rel.get("works_with", [])) + " "
        + " ".join(rel.get("commonly_used_with", [])) + " "
        + " ".join(rel.get("entity_roles", [])),
    ]


def _snippet_fields(s: dict) -> list[str]:
    return [
        s.get("id", ""), s.get("domain", ""), s.get("repo", ""),
        s.get("repo_path", ""), s.get("license", ""),
    ]


def search_features(query: str, limit: int) -> list[dict]:
    if not FEATURE_INDEX.exists():
        return []
    data = json.loads(FEATURE_INDEX.read_text(encoding="utf-8"))
    tokens = _tokens(query)
    scored = []
    for f in data.get("features", []):
        score = sum(_hit(_feature_fields(f), t) for t in tokens)
        if score > 0:
            scored.append((score, f))
    scored.sort(key=lambda x: (-x[0], x[1].get("id", "")))
    return [
        {"score": s, "id": f.get("id"), "category": f.get("category"),
         "provides": f.get("provides", []), "path": f"Features/{f.get('id')}/"}
        for s, f in scored[:limit]
    ]


def search_snippets(query: str, domain: str | None, limit: int,
                    include_all: bool) -> list[dict]:
    if not CATALOG_YAML.exists():
        return []
    entries = _read_catalog_entries()
    tokens = _tokens(query)
    scored = []
    for s in entries:
        if s.get("duplicate_of"):
            continue
        if not include_all and s.get("parse_status") not in ("OK", "skipped_shader"):
            continue
        if domain and s.get("domain") != domain:
            continue
        score = sum(_hit(_snippet_fields(s), t) for t in tokens)
        if score > 0:
            scored.append((score + s.get("stars", 0) / 10000.0, s))
    scored.sort(key=lambda x: (-x[0], x[1].get("id", "")))
    return [
        {"score": round(s, 2), "id": e.get("id"), "domain": e.get("domain"),
         "lines": e.get("lines"), "stars": e.get("stars"),
         "license": e.get("license"), "parse_status": e.get("parse_status"),
         "file": (f".ai/skills/foundation/godot-gdscript/code_library/"
                  f"references/{e.get('domain')}/{e.get('id')}"),
         "source_url": e.get("source_url")}
        for s, e in scored[:limit]
    ]


def main() -> None:
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
    p = argparse.ArgumentParser(description="统一资产搜索（Features + 片段库）")
    p.add_argument("--query", required=True, help="空格分隔关键词")
    p.add_argument("--kind", choices=["all", "feature", "snippet"], default="all")
    p.add_argument("--domain", default=None, help="仅片段：按 domain 过滤")
    p.add_argument("--limit", type=int, default=10)
    p.add_argument("--all", action="store_true",
                   help="包含未通过 parse 检查的片段（默认只返回 OK）")
    p.add_argument("--json", action="store_true", help="机器可读输出")
    a = p.parse_args()

    feats = search_features(a.query, a.limit) if a.kind in ("all", "feature") else []
    snips = (search_snippets(a.query, a.domain, a.limit, a.all)
             if a.kind in ("all", "snippet") else [])
    if a.json:
        print(json.dumps({"features": feats, "snippets": snips},
                         ensure_ascii=False, indent=2))
        return

    print(f"== Features 资产（可直接复用）: {len(feats)} ==")
    for f in feats:
        print(f"  [{f['score']}] {f['id']:<28} ({f['category']}) "
              f"provides={','.join(f['provides'][:4])} -> {f['path']}")
    print(f"== 参考片段（需抽象 Feature 化）: {len(snips)} ==")
    for s in snips:
        print(f"  [{s['score']}] {s['id'][:70]:<70} {s['domain']}/"
              f"{s['lines']}L star={s['stars']} -> {s['file']}")
    if not feats and not snips:
        print("  (无匹配。可尝试更泛的关键词，或先 fetch 新仓库补充片段库)")


if __name__ == "__main__":
    main()
