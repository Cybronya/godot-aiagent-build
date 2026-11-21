#!/usr/bin/env python3
"""Phase 1.71 Batch A tests: provenance and license hardening.

All writes are confined to a temporary directory. No real source, reference,
catalog, index or Feature directory is modified.
"""

from __future__ import annotations

import argparse
import contextlib
import hashlib
import io
import json
import shutil
import sys
import tarfile
import tempfile
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[4]
DOTAI = PROJECT_ROOT / ".ai"
EXT = DOTAI / "tools" / "external_code"
COLLECTOR_TOOLS = DOTAI / "skills" / "foundation" / "godot-gdscript" / "tools"
FEATURE_REGISTRY = DOTAI / "tools" / "feature_registry"
sys.path[:0] = [str(EXT), str(COLLECTOR_TOOLS), str(FEATURE_REGISTRY)]

import github_collector as collector  # noqa: E402
import provenance  # noqa: E402
import provenance_validator as validator  # noqa: E402
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


def make_source(root: Path, *, license_id: str = "MIT", full: bool = True,
                license_text: bool = True, commit: str | None = None) -> Path:
    repo = root / "sources" / "owner__repo"
    (repo / "gd").mkdir(parents=True)
    (repo / "gd" / "a.gd").write_text("extends Node\n\nfunc run() -> void:\n\tpass\n",
                                      encoding="utf-8")
    if license_text:
        (repo / "LICENSE").write_text("MIT License\n", encoding="utf-8")
    full_sha = "a" * 40
    meta = {
        "full_name": "owner/repo", "slug": "owner__repo",
        "branch": "main", "default_branch": "main",
        "commit_sha": commit or (full_sha[:12] if full else "abc123def456"),
        "commit_sha_full": full_sha if full else "",
        "license": license_id, "stars": 10, "fetched_at": "2026-11-13",
        "license_source": "github_api_spdx",
    }
    (repo / "_meta.json").write_text(json.dumps(meta), encoding="utf-8")
    return repo


def run_catalog(root: Path) -> tuple[bool, str]:
    refs = root / "references"
    catalog = root / "catalog.yaml"
    index = root / "INDEX.md"
    refs.mkdir(parents=True, exist_ok=True)
    catalog.write_text("old-catalog\n", encoding="utf-8")
    index.write_text("old-index\n", encoding="utf-8")
    try:
        with contextlib.redirect_stdout(io.StringIO()), \
                contextlib.redirect_stderr(io.StringIO()):
            collector.cmd_catalog(
                argparse.Namespace(), sources_dir=root / "sources",
                references_dir=refs, catalog_path=catalog, index_path=index,
            )
        return True, ""
    except SystemExit as exc:
        return False, str(exc)


def make_entry(entry_id: str = "owner__repo__a.gd", **overrides) -> dict:
    entry = {
        "id": entry_id, "repo": "owner/repo", "repo_slug": "owner__repo",
        "repo_path": "a.gd", "domain": "general", "license": "MIT",
        "stars": 10, "lines": 4, "sha256": "0" * 12,
        "duplicate_of": None, "commit_sha": "a" * 12,
        "commit_sha_full": "a" * 40,
        "source_url": "https://github.com/owner/repo/blob/%s/a.gd" % ("a" * 40),
        "provenance_status": "complete", "license_text_present": True,
        "license_status": "eligible", "license_source": "github_api_spdx",
        "license_basis": "spdx_allowlist_and_local_text",
        "collected_at": "2026-11-13", "parse_status": "OK",
    }
    entry.update(overrides)
    return entry


def make_catalog(root: Path, entries: list[dict]) -> Path:
    root.mkdir(parents=True, exist_ok=True)
    path = root / "catalog.yaml"
    collector._write_catalog_yaml(entries, path)
    return path


def main() -> int:
    tmp = Path(tempfile.mkdtemp(prefix="p171a_"))
    try:
        # License classification matrix.
        g = provenance.assess_license("MIT", license_text_present=True)
        ok("license: MIT with local text is eligible", g["license_status"] == "eligible" and g["copy_allowed"])
        g = provenance.assess_license("Unlicense", license_text_present=False)
        ok("license: Unlicense missing text is explicit, policy-allowed",
           g["license_status"] == "license_text_missing" and g["copy_allowed"])
        g = provenance.assess_license("GPL-3.0", license_text_present=True)
        ok("license: non-allowlist is blocked", g["license_status"] == "blocked" and not g["copy_allowed"])
        g = provenance.assess_license("unknown", license_text_present=True)
        ok("license: unknown is blocked", g["license_status"] == "unknown" and not g["copy_allowed"])
        g = provenance.assess_license("", license_text_present=True)
        ok("license: empty is blocked", g["license_status"] == "unknown" and not g["copy_allowed"])
        g = provenance.assess_license("MIT", license_text_present=False)
        ok("license: missing text preserves license ID and risk",
           g["license_id"] == "MIT" and g["license_risk"] == "local_license_text_missing")

        # Provenance matrix, including no guessing.
        p = provenance.assess_provenance(full_name="owner/repo", commit_sha="a" * 12,
                                         commit_sha_full="a" * 40, source_path="a.gd",
                                         source_url="https://github.com/owner/repo/blob/%s/a.gd" % ("a" * 40))
        ok("provenance: full SHA is complete and immutable URL valid",
           p["provenance_status"] == "complete" and p["immutable_source_url"])
        p = provenance.assess_provenance(full_name="owner/repo", commit_sha="a" * 12,
                                         commit_sha_full="", source_path="a.gd",
                                         source_url="https://github.com/owner/repo/blob/main/a.gd")
        ok("provenance: short SHA is incomplete and not upgraded",
           p["provenance_status"] == "incomplete" and p["commit_sha_full"] == "")
        p = provenance.assess_provenance(full_name="owner/repo", commit_sha="", commit_sha_full="")
        ok("provenance: missing SHA is unknown", p["provenance_status"] == "unknown")

        # Catalog generation: full SHA + immutable URL; short SHA remains incomplete.
        root = tmp / "full"
        make_source(root)
        success, error = run_catalog(root)
        ok("catalog: full-SHA source succeeds", success, error)
        entry = collector._read_catalog_entries(root / "catalog.yaml")[0]
        ok("catalog: full SHA persisted", entry.get("commit_sha_full") == "a" * 40)
        ok("catalog: source URL pinned to full SHA",
           "/blob/%s/" % ("a" * 40) in entry.get("source_url", ""))
        ok("catalog: provenance complete", entry.get("provenance_status") == "complete")
        ok("catalog: local license text present", entry.get("license_status") == "eligible")

        root = tmp / "short"
        make_source(root, full=False)
        success, error = run_catalog(root)
        ok("catalog: legacy short SHA source still works", success, error)
        entry_short = collector._read_catalog_entries(root / "catalog.yaml")[0]
        ok("catalog: short SHA marked incomplete",
           entry_short.get("provenance_status") == "incomplete")
        ok("catalog: URL uses commit, not branch",
           "/blob/abc123def456/" in entry_short.get("source_url", ""))

        root = tmp / "missing_license"
        make_source(root, license_text=False)
        success, error = run_catalog(root)
        ok("catalog: missing local license text is recorded, not hidden", success, error)
        entry_missing = collector._read_catalog_entries(root / "catalog.yaml")[0]
        ok("catalog: license_text_missing status",
           entry_missing.get("license_status") == "license_text_missing")

        # Actual fetch staging with a local in-memory tarball (no network).
        tar_src = tmp / "fetch_tar" / "repo-main"
        tar_src.mkdir(parents=True)
        (tar_src / "LICENSE").write_text("MIT License\n", encoding="utf-8")
        (tar_src / "a.gd").write_text("extends Node\n", encoding="utf-8")
        archive = tmp / "repo.tar.gz"
        with tarfile.open(archive, "w:gz") as tf:
            tf.add(tar_src, arcname="repo-main")
        class Response:
            def __init__(self, payload: bytes) -> None:
                self.payload = payload
                self.offset = 0
            def read(self, size: int = -1) -> bytes:
                if self.offset >= len(self.payload):
                    return b""
                end = len(self.payload) if size < 0 else self.offset + size
                chunk = self.payload[self.offset:end]
                self.offset = end
                return chunk
            def __enter__(self):
                return self
            def __exit__(self, *_exc):
                return False
        old_http = collector._http_get_json
        old_urlopen = collector.urllib.request.urlopen
        collector._http_get_json = lambda url, token: {"sha": "b" * 40}
        collector.urllib.request.urlopen = lambda req, timeout=120: Response(archive.read_bytes())
        try:
            dest = tmp / "fetch_dest"
            collector._fetch_one({
                "full_name": "owner/repo", "license": "MIT",
                "license_source": "github_api_spdx", "default_branch": "main",
            }, dest, token=None)
            meta = json.loads((dest / "_meta.json").read_text(encoding="utf-8"))
            ok("fetch: real staging flow installs complete source",
               (dest / "gd" / "a.gd").is_file() and (dest / "LICENSE").is_file())
            ok("fetch: full SHA and source metadata persisted",
               meta.get("commit_sha_full") == "b" * 40
               and meta.get("commit_sha") == "b" * 12
               and meta.get("provenance_status") == "complete")
            ok("fetch: local license detected",
               meta.get("license_text_present") is True
               and meta.get("license_status") == "eligible")
        finally:
            collector._http_get_json = old_http
            collector.urllib.request.urlopen = old_urlopen

        # Catalog blocks non-allowlisted code before touching references/catalog.
        root = tmp / "gpl"
        make_source(root, license_id="GPL-3.0")
        (root / "references").mkdir()
        (root / "catalog.yaml").write_text("old-catalog\n", encoding="utf-8")
        (root / "INDEX.md").write_text("old-index\n", encoding="utf-8")
        success, error = run_catalog(root)
        ok("catalog: GPL is blocked", not success and "license" in error.lower(), error)
        ok("catalog: blocked GPL leaves old catalog",
           (root / "catalog.yaml").read_text(encoding="utf-8") == "old-catalog\n")

        # Fetch --all / --repo cannot bypass the gate.
        old_sources = collector.SOURCES_DIR
        old_candidates = collector.CANDIDATES_JSON
        old_fetch = collector._fetch_one
        old_http = collector._http_get_json
        calls: list[str] = []
        collector.SOURCES_DIR = tmp / "fetch_sources"
        collector.CANDIDATES_JSON = tmp / "candidates.json"
        collector.CANDIDATES_JSON.write_text(json.dumps([
            {"full_name": "owner/ok", "license": "MIT", "license_ok": True,
             "default_branch": "main"},
            {"full_name": "owner/gpl", "license": "GPL-3.0", "license_ok": False,
             "default_branch": "main"},
        ]), encoding="utf-8")
        collector._fetch_one = lambda meta, dest, token=None: calls.append(meta["full_name"])
        try:
            with contextlib.redirect_stdout(io.StringIO()):
                try:
                    collector.cmd_fetch(argparse.Namespace(repo=None, all=True, top=10,
                                                           force=False, token=None))
                except SystemExit as exc:
                    fetch_error = str(exc)
                else:
                    fetch_error = ""
            ok("fetch: --all does not bypass blocked license",
               "owner/gpl" in fetch_error and calls == ["owner/ok"], (fetch_error, calls))

            calls.clear()
            collector._http_get_json = lambda url, token: {
                "full_name": "owner/gpl", "default_branch": "main",
                "license": {"spdx_id": "GPL-3.0"}, "stargazers_count": 1,
            }
            with contextlib.redirect_stdout(io.StringIO()):
                try:
                    collector.cmd_fetch(argparse.Namespace(repo="owner/gpl", all=False, top=1,
                                                           force=False, token=None))
                except SystemExit as exc:
                    repo_error = str(exc)
                else:
                    repo_error = ""
            ok("fetch: --repo does not bypass blocked license",
               "owner/gpl" in repo_error and calls == [], repo_error)
        finally:
            collector.SOURCES_DIR = old_sources
            collector.CANDIDATES_JSON = old_candidates
            collector._fetch_one = old_fetch
            collector._http_get_json = old_http

        # Promote gate: blocked license, no half-created Feature.
        old_feature = collector.FEATURE_ROOT
        old_refs, old_sources, old_catalog = collector.REFERENCES_DIR, collector.SOURCES_DIR, collector.CATALOG_YAML
        promo = tmp / "promote"
        (promo / "Features").mkdir(parents=True)
        (promo / "references" / "general").mkdir(parents=True)
        (promo / "references" / "general" / "owner__repo__a.gd").write_text(
            "extends Node\n", encoding="utf-8")
        collector.FEATURE_ROOT = promo / "Features"
        collector.REFERENCES_DIR = promo / "references"
        collector.SOURCES_DIR = promo / "sources"
        collector.CATALOG_YAML = promo / "catalog.yaml"
        collector._write_catalog_yaml([make_entry(license="GPL-3.0",
                                                  license_status="blocked")],
                                      collector.CATALOG_YAML)
        try:
            with contextlib.redirect_stdout(io.StringIO()):
                try:
                    collector.cmd_promote(argparse.Namespace(
                        snippet="owner__repo__a.gd", name="gated", category="component"))
                except SystemExit as exc:
                    promote_error = str(exc)
                else:
                    promote_error = ""
            ok("promote: blocked license returns explicit error",
               "BLOCKED" in promote_error, promote_error)
            ok("promote: blocked operation leaves no Feature",
               not (promo / "Features" / "gated").exists())
        finally:
            collector.FEATURE_ROOT = old_feature
            collector.REFERENCES_DIR, collector.SOURCES_DIR, collector.CATALOG_YAML = old_refs, old_sources, old_catalog

        # Search still sees pending records.
        pending_catalog = make_catalog(tmp / "pending", [make_entry(license="GPL-3.0",
                                                                   license_status="blocked")])
        pending = search.search_snippets("owner", None, 10, False, pending_catalog)
        ok("search: pending/blocked records remain discoverable", len(pending) == 1)

        # Provenance validator: valid, incomplete, invalid.
        root = tmp / "valid"
        make_source(root)
        success, error = run_catalog(root)
        ok("validator fixture catalog succeeds", success, error)
        vroot = root
        entry = collector._read_catalog_entries(vroot / "catalog.yaml")[0]
        valid = validator.validate_entry(
            entry, source_root=vroot / "sources", references_root=vroot / "references",
            catalog_ids={entry["id"]})
        ok("validator: complete entry is valid", valid["status"] == "valid", valid)

        incomplete = dict(entry)
        incomplete["commit_sha_full"] = ""
        incomplete["provenance_status"] = "incomplete"
        incomplete["source_url"] = "https://github.com/owner/repo/blob/abc123def456/a.gd"
        incomplete["commit_sha"] = "abc123def456"
        result = validator.validate_entry(incomplete, source_root=vroot / "sources",
                                          references_root=vroot / "references",
                                          catalog_ids={entry["id"]})
        ok("validator: short SHA is incomplete", result["status"] == "incomplete", result)

        bad = dict(entry)
        bad["source_url"] = "https://github.com/owner/repo/blob/main/a.gd"
        result = validator.validate_entry(bad, source_root=vroot / "sources",
                                          references_root=vroot / "references",
                                          catalog_ids={entry["id"]})
        ok("validator: branch URL with full SHA is invalid", result["status"] == "invalid", result)

        bad = dict(entry)
        bad["sha256"] = "f" * 12
        result = validator.validate_entry(bad, source_root=vroot / "sources",
                                          references_root=vroot / "references",
                                          catalog_ids={entry["id"]})
        ok("validator: source hash mismatch is invalid", result["status"] == "invalid", result)

        missing_commit = dict(entry)
        missing_commit["commit_sha"] = ""
        missing_commit["commit_sha_full"] = ""
        result = validator.validate_entry(missing_commit, source_root=vroot / "sources",
                                          references_root=vroot / "references",
                                          catalog_ids={entry["id"]})
        ok("validator: missing commit is invalid", result["status"] == "invalid", result)

        duplicate = dict(entry)
        duplicate["id"] = "owner__repo__b.gd"
        duplicate["duplicate_of"] = entry["id"]
        result = validator.validate_entry(duplicate, source_root=vroot / "sources",
                                          references_root=vroot / "references",
                                          catalog_ids={entry["id"], duplicate["id"]})
        ok("validator: resolvable duplicate relationship is not invalid",
           result["status"] in ("valid", "incomplete"), result)

        missing_ref = dict(entry)
        missing_ref["id"] = "missing_reference.gd"
        result = validator.validate_entry(missing_ref, source_root=vroot / "sources",
                                          references_root=vroot / "references",
                                          catalog_ids={missing_ref["id"]})
        ok("validator: missing reference is invalid", result["status"] == "invalid", result)

        repo_result = validator.validate_repo(vroot / "sources" / "owner__repo")
        ok("validator: repository check is read-only and complete",
           repo_result["status"] in ("valid", "incomplete"), repo_result)

        print()
        if FAILURES:
            print("FAIL: %d/%d checks failed" % (len(FAILURES), CHECKS))
            for failure in FAILURES:
                print("  -", failure)
            return 1
        print("PASS: Batch A %d checks" % CHECKS)
        return 0
    finally:
        shutil.rmtree(tmp, ignore_errors=True)


if __name__ == "__main__":
    sys.exit(main())
