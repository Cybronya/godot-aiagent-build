#!/usr/bin/env python3
"""Phase 1.71 Batch B tests: External Code Understanding.

All fixtures and analysis records use a temporary directory. The real Source
Library and Reference Library are only read where explicitly stated.
"""

from __future__ import annotations

import json
import shutil
import sys
import tempfile
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[4]
DOTAI = PROJECT_ROOT / ".ai"
sys.path[:0] = [str(DOTAI / "tools" / "external_code"),
                str(DOTAI / "tools" / "learning"),
                str(DOTAI / "tools" / "feature_registry"),
                str(DOTAI / "skills" / "foundation" / "godot-gdscript" / "tools")]

import github_collector as collector  # noqa: E402
import external_code_understanding as ext  # noqa: E402
import search_assets as search  # noqa: E402

FAILURES: list[str] = []
CHECKS = 0


def ok(name: str, condition: bool, detail: str = "") -> None:
    global CHECKS
    CHECKS += 1
    if condition:
        print("PASS:", name)
    else:
        FAILURES.append(name + ((" | " + str(detail)) if detail else ""))
        print("FAIL:", name, ("| " + str(detail)) if detail else "")


SAMPLE = """class_name Demo
extends Node

signal changed(value)
@export var speed := 1.0
var _state := false
const MAX_COUNT := 3

func _ready() -> void:
\tchanged.connect(_on_changed)

func run(value) -> bool:
\tif _state:
\t\treturn false
\t_state = true
\tvar node = get_node_or_null("Marker")
\tvar resource = load("res://data/demo.tres")
\tchanged.emit(value)
\treturn true

func _on_changed(_value) -> void:
\tpass
"""


def make_fixture(root: Path, *, shader: bool = False, source_text: str | None = None):
    ref = root / "references" / "general" / ("demo.gdshader" if shader else "demo.gd")
    ref.parent.mkdir(parents=True, exist_ok=True)
    body = source_text if source_text is not None else ("shader_type canvas_item;\n" if shader else SAMPLE)
    ref.write_text("# Source:  https://github.com/owner/repo/blob/%s/demo.gd\n"
                   "# Repo:    owner/repo (star 1) | License: MIT | Collected: 2026-11-13\n"
                   "# Commit:  %s\n%s" % ("a" * 40, "a" * 12, body),
                   encoding="utf-8")
    source = root / "sources" / "owner__repo" / "gd" / ("demo.gdshader" if shader else "demo.gd")
    source.parent.mkdir(parents=True, exist_ok=True)
    source.write_text(body, encoding="utf-8")
    (root / "sources" / "owner__repo" / "LICENSE").write_text("MIT License\n", encoding="utf-8")
    meta = {
        "snippet_id": "owner__repo__demo.gd", "repo": "owner/repo",
        "full_name": "owner/repo", "repo_slug": "owner__repo",
        "repo_path": "demo.gdshader" if shader else "demo.gd",
        "domain": "general", "commit_sha": "a" * 12, "commit_sha_full": "a" * 40,
        "source_url": "https://github.com/owner/repo/blob/%s/%s" % (
            "a" * 40, "demo.gdshader" if shader else "demo.gd"),
        "license": "MIT", "license_status": "eligible",
        "license_text_present": True, "license_source": "github_api_spdx",
    }
    return ref, meta, root / "sources"


def main() -> int:
    tmp = Path(tempfile.mkdtemp(prefix="p171b_"))
    try:
        ref, meta, sources = make_fixture(tmp)
        options = {"source_root": sources}
        record = ext.analyze_external_code(ref, meta, options)
        ok("adapter: normal .gd parsed", record["parse_status"] == "parsed")
        ok("adapter: structure analysis complete", record["analysis_status"] == "analysis_complete")
        ok("adapter: functions extracted", len(record["symbols"]["functions"]) == 3,
           record["symbols"]["functions"])
        ok("adapter: class/signal/export/variable/constant extracted",
           record["symbols"]["class_name"] == "Demo"
           and record["symbols"]["signals"][0]["name"] == "changed"
           and record["symbols"]["exports"][0]["name"] == "speed"
           and len(record["symbols"]["variables"]) == 1)
        ok("adapter: entry points extracted", len(record["entry_points"]) >= 2,
           record["entry_points"])
        ok("adapter: shared source analysis reports state/effects",
           any(x["variable"] == "_state" for x in record["state_changes"])
           and any(x["kind"] == "node_lookup" for x in record["side_effects"])
           and any(x["kind"] == "resource_load" for x in record["side_effects"]))
        ok("adapter: signal emission captured",
           any(x["kind"] == "emit" for x in record["signals_events"]))
        ok("adapter: source trace and consistency present",
           record["source_exists"] and record["source_consistent"])
        ok("adapter: full commit + immutable URL trace",
           record["commit_sha_full"] == "a" * 40
           and ("/blob/%s/" % ("a" * 40)) in record["source_url"])
        ok("adapter: analysis is not knowledge and not Feature",
           record["knowledge_status"] == "NOT_KNOWLEDGE"
           and record["approved_knowledge"] is False
           and record["feature_created"] is False)
        ok("adapter: license eligible", record["license_status"] == "eligible")

        # Deterministic ID / idempotent write.
        out = tmp / "analysis"
        path1 = ext.write_record(record, out)
        path2 = ext.write_record(record, out)
        ok("record: deterministic analysis id", record["analysis_id"].startswith("ext-"))
        ok("record: same input is idempotent", path1 == path2)

        # Multi-function / signal / class are covered by SAMPLE; explicit
        # partial and failure paths follow.
        broken = tmp / "broken.gd"
        broken.write_text("# S\n# R\n# C\nfunc broken(\n", encoding="utf-8")
        broken_meta = dict(meta, repo_path="broken.gd",
                           source_url="https://github.com/owner/repo/blob/%s/broken.gd" % ("a" * 40))
        broken_rec = ext.analyze_external_code(broken, broken_meta, options)
        ok("adapter: incomplete syntax is partial, not success",
           broken_rec["parse_status"] == "partial"
           and broken_rec["analysis_status"] == "analysis_partial",
           (broken_rec["parse_status"], broken_rec["analysis_status"]))

        shader_ref, shader_meta, shader_sources = make_fixture(
            tmp / "shader", shader=True)
        shader_rec = ext.analyze_external_code(
            shader_ref, shader_meta, {"source_root": shader_sources})
        ok("adapter: .gdshader is unsupported_shader",
           shader_rec["parse_status"] == "unsupported_shader"
           and shader_rec["analysis_status"] == "unsupported_shader"
           and shader_rec["symbols"] == {})

        txt = tmp / "demo.txt"
        txt.write_text("not code\n", encoding="utf-8")
        txt_meta = dict(meta, repo_path="demo.txt")
        txt_rec = ext.analyze_external_code(txt, txt_meta, options)
        ok("adapter: unsupported file type has explicit status",
           txt_rec["parse_status"] == "unsupported_file_type")

        missing_rec = ext.analyze_external_code(tmp / "missing.gd", meta, options)
        ok("adapter: missing reference is parse_failed",
           missing_rec["parse_status"] == "parse_failed"
           and missing_rec["analysis_status"] == "analysis_failed")

        # Provenance and license gates.
        no_sha = dict(meta, commit_sha="", commit_sha_full="", source_url="")
        blocked_prov = ext.analyze_external_code(ref, no_sha, options)
        ok("adapter: unknown provenance is blocked",
           blocked_prov["analysis_status"] == "blocked_provenance"
           and blocked_prov["source_analysis_status"] == "skipped")
        short = dict(meta, commit_sha_full="", commit_sha="a" * 12,
                     source_url="https://github.com/owner/repo/blob/%s/demo.gd" % ("a" * 12))
        short_rec = ext.analyze_external_code(ref, short, options)
        ok("adapter: short provenance is recorded as incomplete",
           short_rec["provenance_status"] == "incomplete")

        gpl = dict(meta, license="GPL-3.0", license_status="blocked")
        gpl_rec = ext.analyze_external_code(ref, gpl, options)
        ok("adapter: blocked license never claims analysis complete",
           gpl_rec["analysis_status"] == "blocked_license"
           and gpl_rec["copy_allowed"] is False)

        pending = dict(meta, license_status="pending_review")
        pending_rec = ext.analyze_external_code(ref, pending, options)
        ok("adapter: pending license is blocked_license",
           pending_rec["analysis_status"] == "blocked_license")

        # Source/reference mismatch and missing source are explicit.
        mismatch_root = tmp / "mismatch"
        mismatch_ref, mismatch_meta, mismatch_sources = make_fixture(mismatch_root)
        (mismatch_sources / "owner__repo" / "gd" / "demo.gd").write_text(
            "extends Node\n# changed\n", encoding="utf-8")
        mismatch = ext.analyze_external_code(
            mismatch_ref, mismatch_meta, {"source_root": mismatch_sources})
        ok("adapter: source/reference mismatch is partial",
           mismatch["source_consistent"] is False
           and mismatch["analysis_status"] == "analysis_partial")

        missing_source_meta = dict(meta, repo_path="not_in_source.gd")
        missing_source = ext.analyze_external_code(ref, missing_source_meta, options)
        ok("adapter: missing source is partial and explicit",
           missing_source["source_exists"] is False
           and missing_source["analysis_status"] == "analysis_partial")

        no_class_ref, no_class_meta, no_class_sources = make_fixture(
            tmp / "noclass", source_text="extends Node\n\nfunc run():\n\tpass\n")
        no_class = ext.analyze_external_code(
            no_class_ref, no_class_meta, {"source_root": no_class_sources})
        ok("adapter: absent class_name is parsed but analysis partial",
           no_class["parse_status"] == "parsed"
           and no_class["analysis_status"] == "analysis_partial"
           and any("class_name" in q for q in no_class["unresolved_questions"]))

        # Different commits produce different records.
        other_meta = dict(meta, commit_sha="c" * 12, commit_sha_full="c" * 40,
                          source_url="https://github.com/owner/repo/blob/%s/demo.gd" % ("c" * 40))
        other = ext.analyze_external_code(ref, other_meta, options)
        ok("record: different commit changes analysis id",
           other["analysis_id"] != record["analysis_id"])

        # Index and Search integration.
        index = tmp / "index.json"
        payload = ext.build_index(out, index)
        ok("index: analysis records indexed", len(payload["analyses"]) >= 1)
        index_data = json.loads(index.read_text(encoding="utf-8"))
        ok("index: trace fields present",
           all(k in index_data["analyses"][0] for k in (
               "analysis_id", "snippet_id", "repo", "commit_sha",
               "reference_path", "analysis_status")))

        catalog = tmp / "catalog.yaml"
        entry = {
            "id": "owner__repo__demo.gd", "repo": "owner/repo",
            "repo_slug": "owner__repo", "repo_path": "demo.gd",
            "domain": "general", "license": "MIT", "stars": 1, "lines": 20,
            "sha256": "0" * 12, "duplicate_of": None,
            "commit_sha": "a" * 12, "source_url": meta["source_url"],
            "collected_at": "2026-11-13", "parse_status": "OK",
        }
        collector._write_catalog_yaml([entry], catalog)
        found = search.search_snippets("owner", None, 10, False, catalog,
                                       analysis_index=index, symbols="run",
                                       include_analysis=True)
        ok("search: symbol search finds analyzed reference",
           len(found) == 1 and found[0]["analysis_status"] == "analysis_complete",
           found)
        ok("search: analysis record attached",
           found[0]["analysis_record"]["analysis_id"] == record["analysis_id"])
        by_status = search.search_snippets("", None, 10, False, catalog,
                                           analysis_index=index,
                                           analysis_status="analysis_complete")
        ok("search: analysis-status-only filter returns matches",
           len(by_status) == 1 and by_status[0]["analysis_status"] == "analysis_complete")
        try:
            search.search_snippets("owner", None, 10, False, catalog,
                                   analysis_index=tmp / "nope.json")
            ok("search: missing analysis index raises", False)
        except search.SearchSystemError as exc:
            ok("search: missing analysis index raises", "Analysis Index Missing" in str(exc))

        # Analysis cannot create Feature or Approved Knowledge.
        ok("boundary: no Feature directory was created", not (PROJECT_ROOT / "Features" / "owner__repo__demo").exists())
        ok("boundary: no analysis record is approved knowledge",
           all(not r.get("approved_knowledge") for r in [record, short_rec, gpl_rec]))

        print()
        if FAILURES:
            print("FAIL: %d/%d checks failed" % (len(FAILURES), CHECKS))
            for failure in FAILURES:
                print("  -", failure)
            return 1
        print("PASS: Batch B %d checks" % CHECKS)
        return 0
    finally:
        shutil.rmtree(tmp, ignore_errors=True)


if __name__ == "__main__":
    sys.exit(main())
