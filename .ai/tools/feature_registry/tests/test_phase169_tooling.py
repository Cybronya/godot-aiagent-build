#!/usr/bin/env python3
"""Phase 1.69-A tooling hardening tests.

只使用项目内临时目录，不触碰真实 code_library、sources、references、
catalog.yaml 或 INDEX.md。

Usage:
    python .ai/tools/feature_registry/tests/test_phase169_tooling.py
"""

from __future__ import annotations

import argparse
import contextlib
import io
import json
import shutil
import sys
import tempfile
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[4]
DOTAI = PROJECT_ROOT / ".ai"
sys.path.insert(0, str(DOTAI / "skills" / "foundation" / "godot-gdscript" / "tools"))
sys.path.insert(0, str(DOTAI / "tools" / "feature_registry"))

import github_collector as collector  # noqa: E402
import search_assets as search  # noqa: E402

_FAILURES: list[str] = []
_TEMP_ROOT: Path | None = None


def ok(name: str, condition: bool, detail: str = "") -> None:
    if condition:
        print("PASS:", name)
    else:
        _FAILURES.append(name + ((" | " + detail) if detail else ""))
        print("FAIL:", name, ("| " + detail) if detail else "")


def make_lib(root: Path) -> tuple[Path, Path, Path, Path]:
    sources = root / "sources"
    references = root / "references"
    catalog = root / "catalog.yaml"
    index = root / "INDEX.md"
    sources.mkdir(parents=True, exist_ok=True)
    references.mkdir(parents=True, exist_ok=True)
    catalog.write_text("old-catalog\n", encoding="utf-8")
    index.write_text("old-index\n", encoding="utf-8")
    (references / "keep.gd").write_text("old reference\n", encoding="utf-8")
    return sources, references, catalog, index


def make_repo(sources: Path, slug: str, files: dict[str, str],
              meta: dict | None = None) -> Path:
    repo = sources / slug
    (repo / "gd").mkdir(parents=True, exist_ok=True)
    for rel, text in files.items():
        target = repo / "gd" / rel
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(text, encoding="utf-8")
    payload = {
        "full_name": slug.replace("__", "/"),
        "slug": slug,
        "branch": "main",
        "commit_sha": "abc123def456",
        "license": "MIT",
        "stars": 10,
        "fetched_at": "2026-11-12",
    }
    if meta:
        payload.update(meta)
    if meta != {"missing": True}:
        (repo / "_meta.json").write_text(
            json.dumps(payload), encoding="utf-8")
    return repo


def tree_snapshot(path: Path) -> dict[str, bytes]:
    if not path.exists():
        return {}
    return {str(p.relative_to(path)): p.read_bytes()
            for p in sorted(path.rglob("*")) if p.is_file()}


def snapshot(references: Path, catalog: Path, index: Path) -> dict:
    return {
        "refs": tree_snapshot(references),
        "catalog": catalog.read_bytes() if catalog.exists() else None,
        "index": index.read_bytes() if index.exists() else None,
    }


def run_catalog(sources: Path, references: Path, catalog: Path,
                index: Path) -> tuple[bool, str]:
    err = io.StringIO()
    try:
        with contextlib.redirect_stdout(io.StringIO()), \
                contextlib.redirect_stderr(err):
            collector.cmd_catalog(
                argparse.Namespace(),
                sources_dir=sources,
                references_dir=references,
                catalog_path=catalog,
                index_path=index,
            )
    except SystemExit as exc:
        return False, str(exc)
    except Exception as exc:  # noqa: BLE001
        return False, str(exc)
    return True, err.getvalue()


def make_catalog_entry(entry_id: str, *, duplicate_of: str | None = None,
                       domain: str = "general", status: str = "OK") -> dict:
    return {
        "id": entry_id,
        "repo": "owner/repo",
        "repo_slug": "owner__repo",
        "repo_path": "src/example.gd",
        "domain": domain,
        "license": "MIT",
        "stars": 10,
        "lines": 2,
        "sha256": "0123456789ab",
        "duplicate_of": duplicate_of,
        "commit_sha": "abc123def456",
        "source_url": f"https://github.com/owner/repo/blob/main/src/{entry_id}",
        "collected_at": "2026-11-12",
        "parse_status": status,
    }


def main() -> int:
    global _TEMP_ROOT
    temp_parent = DOTAI / "tmp"
    temp_parent.mkdir(parents=True, exist_ok=True)
    _TEMP_ROOT = Path(tempfile.mkdtemp(prefix="phase169_tooling_",
                                       dir=str(temp_parent)))
    try:
        # ---- Collector: preflight failures ----
        root = _TEMP_ROOT / "missing_sources"
        sources, refs, catalog, index = make_lib(root)
        before = snapshot(refs, catalog, index)
        shutil.rmtree(sources)
        success, _ = run_catalog(sources, refs, catalog, index)
        ok("collector: missing sources fails", not success)
        ok("collector: missing sources leaves data", snapshot(refs, catalog, index) == before)

        root = _TEMP_ROOT / "empty_sources"
        sources, refs, catalog, index = make_lib(root)
        before = snapshot(refs, catalog, index)
        success, _ = run_catalog(sources, refs, catalog, index)
        ok("collector: empty sources fails", not success)
        ok("collector: empty sources leaves data", snapshot(refs, catalog, index) == before)

        root = _TEMP_ROOT / "no_candidates"
        sources, refs, catalog, index = make_lib(root)
        make_repo(sources, "owner__empty", {"README.txt": "x"})
        before = snapshot(refs, catalog, index)
        success, _ = run_catalog(sources, refs, catalog, index)
        ok("collector: no code candidates fails", not success)
        ok("collector: no candidates leaves data", snapshot(refs, catalog, index) == before)

        root = _TEMP_ROOT / "all_filtered"
        sources, refs, catalog, index = make_lib(root)
        make_repo(sources, "owner__large", {"main.gd": "extends Node\n"})
        before = snapshot(refs, catalog, index)
        old_limit = collector.MAX_FILE_BYTES
        collector.MAX_FILE_BYTES = 1
        try:
            success, _ = run_catalog(sources, refs, catalog, index)
        finally:
            collector.MAX_FILE_BYTES = old_limit
        ok("collector: all filtered fails", not success)
        ok("collector: all filtered leaves data", snapshot(refs, catalog, index) == before)

        root = _TEMP_ROOT / "missing_meta"
        sources, refs, catalog, index = make_lib(root)
        make_repo(sources, "owner__nometa", {"main.gd": "extends Node\n"},
                  meta={"missing": True})
        before = snapshot(refs, catalog, index)
        success, _ = run_catalog(sources, refs, catalog, index)
        ok("collector: missing metadata fails", not success)
        ok("collector: missing metadata leaves data", snapshot(refs, catalog, index) == before)

        # ---- Collector: successful generation and dedup ----
        root = _TEMP_ROOT / "success"
        sources, refs, catalog, index = make_lib(root)
        make_repo(sources, "owner__repo", {
            "a.gd": "extends Node\n",
            "b.gd": "extends Node\n",       # duplicate of a
            "c.gd": "extends Node\n# unique\n",
        })
        success, _ = run_catalog(sources, refs, catalog, index)
        entries = collector._read_catalog_entries(catalog) if success else []
        unique = [e for e in entries if not e.get("duplicate_of")]
        ok("collector: normal data succeeds", success)
        ok("collector: catalog has entries", len(entries) == 3, str(len(entries)))
        ok("collector: sha dedup keeps one fragment", len(unique) == 2, str(len(unique)))
        ok("collector: duplicate points at retained id",
           any(e.get("duplicate_of") for e in entries))
        ok("collector: one reference per unique entry",
           len([p for p in refs.rglob("*") if p.is_file()]) == 2)
        ok("collector: index is non-empty",
           index.is_file() and index.stat().st_size > 0)

        # ---- Collector: generation failure preserves old data ----
        for label, patch_name in (("catalog writer", "_write_catalog_yaml"),
                                  ("index writer", "_write_index_md")):
            root = _TEMP_ROOT / ("fail_" + patch_name)
            sources, refs, catalog, index = make_lib(root)
            make_repo(sources, "owner__repo", {"main.gd": "extends Node\n"})
            before = snapshot(refs, catalog, index)
            original = getattr(collector, patch_name)
            setattr(collector, patch_name,
                    lambda *a, **k: (_ for _ in ()).throw(RuntimeError("injected")))
            try:
                success, _ = run_catalog(sources, refs, catalog, index)
            finally:
                setattr(collector, patch_name, original)
            ok(f"collector: {label} failure fails", not success)
            ok(f"collector: {label} failure leaves data",
               snapshot(refs, catalog, index) == before)

        # ---- Collector: replace failure rolls back ----
        root = _TEMP_ROOT / "replace_failure"
        sources, refs, catalog, index = make_lib(root)
        make_repo(sources, "owner__repo", {"main.gd": "extends Node\n"})
        before = snapshot(refs, catalog, index)
        real_replace = collector.os.replace
        calls = {"n": 0}

        def flaky_replace(src, dst):
            calls["n"] += 1
            if calls["n"] == 5:
                raise OSError("injected replace failure")
            return real_replace(src, dst)

        collector.os.replace = flaky_replace
        try:
            success, _ = run_catalog(sources, refs, catalog, index)
        finally:
            collector.os.replace = real_replace
        ok("collector: replace failure fails", not success)
        ok("collector: replace failure rolls back data",
           snapshot(refs, catalog, index) == before)

        # ---- Search: catalog diagnostics ----
        missing = _TEMP_ROOT / "missing_catalog.yaml"
        try:
            search.search_snippets("x", None, 10, False, missing)
            ok("search: missing catalog raises", False)
        except search.SearchSystemError as exc:
            ok("search: missing catalog raises", "Catalog Missing" in str(exc))

        empty = _TEMP_ROOT / "empty_catalog.yaml"
        empty.write_bytes(b"")
        try:
            search.search_snippets("x", None, 10, False, empty)
            ok("search: empty catalog raises", False)
        except search.SearchSystemError as exc:
            ok("search: empty catalog raises", "Catalog Empty" in str(exc))

        invalid = _TEMP_ROOT / "invalid_catalog.yaml"
        invalid.write_text("  - id: \"unterminated\n", encoding="utf-8")
        try:
            search.search_snippets("x", None, 10, False, invalid)
            ok("search: invalid catalog raises", False)
        except search.SearchSystemError as exc:
            ok("search: invalid catalog raises", "Catalog Invalid" in str(exc))

        # ---- Search: schema, no match, dedup, --all ----
        catalog = _TEMP_ROOT / "search_catalog.yaml"
        base = make_catalog_entry("owner__repo__a.gd")
        dup = make_catalog_entry("owner__repo__b.gd",
                                 duplicate_of="owner__repo__a.gd",
                                 status="duplicate")
        collector._write_catalog_yaml([base, dup], catalog)
        results = search.search_snippets("owner", None, 10, False, catalog)
        all_results = search.search_snippets("owner", None, 10, True, catalog)
        ok("search: valid no-match returns empty",
           search.search_snippets("zzzz_no_such_token", None, 10, False, catalog) == [])
        ok("search: default excludes duplicate", len(results) == 1, str(len(results)))
        ok("search: --all includes duplicate", len(all_results) == 2, str(len(all_results)))
        ok("search: duplicate has no reference path",
           any(r.get("duplicate_of") and r.get("reference_path") is None
               for r in all_results))
        if results:
            row = results[0]
            ok("search: JSON provenance complete", all(
                row.get(k) not in (None, "") for k in (
                    "id", "domain", "repo", "repo_path", "license",
                    "source_url", "commit_sha", "reference_path",
                    "parse_status")))

        schema = _TEMP_ROOT / "schema_catalog.yaml"
        broken = dict(base)
        broken["commit_sha"] = ""
        collector._write_catalog_yaml([broken], schema)
        try:
            search.search_snippets("owner", None, 10, False, schema)
            ok("search: schema error raises", False)
        except search.SearchSystemError as exc:
            ok("search: schema error raises", "Catalog Schema Error" in str(exc))

        # ---- Search: feature diagnostics and --kind ----
        missing_feature = _TEMP_ROOT / "missing_feature.json"
        try:
            search.search_features("health", 10, missing_feature)
            ok("search: missing feature index raises", False)
        except search.SearchSystemError as exc:
            ok("search: missing feature index raises", "Feature Index Missing" in str(exc))

        bad_feature = _TEMP_ROOT / "bad_feature.json"
        bad_feature.write_text("{}", encoding="utf-8")
        try:
            search.search_features("health", 10, bad_feature)
            ok("search: invalid feature index raises", False)
        except search.SearchSystemError as exc:
            ok("search: invalid feature index raises", "Feature Index Invalid" in str(exc))

        feature = _TEMP_ROOT / "feature.json"
        feature.write_text(json.dumps({"features": [
            {"id": "health", "category": "component",
             "provides": ["health_state"], "requires": [],
             "interfaces": [], "relations": {}}
        ]}), encoding="utf-8")
        ok("search: feature search works",
           len(search.search_features("health", 10, feature)) == 1)
        ok("search: feature no-match is normal",
           search.search_features("zzzz_no_such_token", 10, feature) == [])

        old_feature, old_catalog = search.FEATURE_INDEX, search.CATALOG_YAML
        search.FEATURE_INDEX, search.CATALOG_YAML = feature, catalog
        old_argv = sys.argv
        out, err = io.StringIO(), io.StringIO()
        try:
            sys.argv = ["search_assets.py", "--query", "owner",
                        "--kind", "snippet", "--json"]
            with contextlib.redirect_stdout(out), contextlib.redirect_stderr(err):
                search.main()
            payload = json.loads(out.getvalue())
            ok("search: CLI JSON contains snippets",
               len(payload.get("snippets", [])) == 1)
            ok("search: CLI JSON has commit_sha",
               payload["snippets"][0].get("commit_sha") == "abc123def456")
            sys.argv = ["search_assets.py", "--query", "owner",
                        "--kind", "snippet"]
            out, err = io.StringIO(), io.StringIO()
            with contextlib.redirect_stdout(out), contextlib.redirect_stderr(err):
                search.main()
            text = out.getvalue()
            ok("search: text output includes repo", "repo=owner/repo" in text)
            ok("search: text output includes license", "MIT" in text)
            ok("search: text output includes source URL",
               "https://github.com/owner/repo" in text)
        finally:
            sys.argv = old_argv
            search.FEATURE_INDEX, search.CATALOG_YAML = old_feature, old_catalog

        print()
        if _FAILURES:
            print(f"FAIL: {len(_FAILURES)} check(s) failed")
            for failure in _FAILURES:
                print("  -", failure)
            return 1
        print("PASS: Phase 1.69-A tooling hardening tests")
        return 0
    finally:
        if _TEMP_ROOT is not None:
            shutil.rmtree(_TEMP_ROOT, ignore_errors=True)


if __name__ == "__main__":
    sys.exit(main())
