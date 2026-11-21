"""Read-only provenance validator for the external code library.

Checks repository metadata, source snapshots, references and Catalog entries
without modifying any file. It intentionally returns `incomplete` for legacy
short SHAs and missing local license text; it never upgrades either condition.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[3]
DOTAI = PROJECT_ROOT / ".ai"
COLLECTOR_TOOLS = DOTAI / "skills" / "foundation" / "godot-gdscript" / "tools"
if str(COLLECTOR_TOOLS) not in sys.path:
    sys.path.insert(0, str(COLLECTOR_TOOLS))

import github_collector as collector  # noqa: E402
from provenance import assess_license, assess_provenance, has_license_text  # noqa: E402

STATUS_ORDER = {"valid": 0, "incomplete": 1, "invalid": 2}


def _result(status: str, reasons: list[str], **data) -> dict:
    return {"status": status, "reasons": reasons, **data}


def _worst(items: list[dict]) -> str:
    status = "valid"
    for item in items:
        if STATUS_ORDER[item["status"]] > STATUS_ORDER[status]:
            status = item["status"]
    return status


def validate_repo(source_dir: str | Path) -> dict:
    directory = Path(source_dir)
    reasons: list[str] = []
    meta_path = directory / "_meta.json"
    if not meta_path.is_file():
        return _result("invalid", ["missing _meta.json"], repo_dir=str(directory))
    try:
        meta = json.loads(meta_path.read_text(encoding="utf-8"))
    except Exception as exc:  # noqa: BLE001
        return _result("invalid", ["invalid _meta.json: %s" % exc], repo_dir=str(directory))
    if not isinstance(meta, dict):
        return _result("invalid", ["_meta.json is not an object"], repo_dir=str(directory))
    for field in ("full_name", "slug", "commit_sha", "license"):
        if not str(meta.get(field) or "").strip():
            reasons.append("missing metadata field: %s" % field)

    gate = assess_license(
        meta.get("license"), license_text_present=has_license_text(directory),
        license_source=meta.get("license_source") or "github_api_spdx",
        declared_status=meta.get("license_status_override"),
        allow_missing_text=True,
    )
    prov = assess_provenance(
        full_name=meta.get("full_name"), commit_sha=meta.get("commit_sha"),
        commit_sha_full=meta.get("commit_sha_full") or "",
    )
    if not gate["copy_allowed"]:
        reasons.append(gate["reason"])
    if prov["provenance_status"] == "unknown":
        reasons.append(prov["reason"])
    status = "invalid" if gate["license_status"] in ("blocked", "unknown") or prov["provenance_status"] == "unknown" else "valid"
    if prov["provenance_status"] == "incomplete":
        status = "incomplete"
        reasons.append(prov["reason"])
    if gate["license_status"] == "license_text_missing":
        if status == "valid":
            status = "incomplete"
        reasons.append("local license text is missing; basis=%s" % gate["license_basis"])
    if not reasons and status == "valid":
        reasons.append("metadata, license and full provenance are complete")
    return _result(status, reasons, repo_dir=str(directory), meta=meta,
                   license=gate, provenance=prov)


def _source_path(entry: dict, source_root: Path) -> Path:
    return source_root / str(entry.get("repo_slug") or "") / "gd" / str(entry.get("repo_path") or "")


def validate_entry(entry: dict, *, source_root: Path, references_root: Path,
                   catalog_ids: set[str] | None = None) -> dict:
    reasons: list[str] = []
    eid = str(entry.get("id") or "")
    required = ("id", "repo", "repo_slug", "repo_path", "license", "commit_sha",
                "source_url", "sha256")
    for field in required:
        if not str(entry.get(field) or "").strip():
            reasons.append("missing catalog field: %s" % field)

    gate = assess_license(
        entry.get("license"),
        license_text_present=bool(entry.get("license_text_present")),
        license_source=entry.get("license_source") or "github_api_spdx",
        declared_status=(entry.get("license_status")
                         if entry.get("license_status") in ("blocked", "pending_review")
                         else None),
        allow_missing_text=True,
    )
    prov = assess_provenance(
        full_name=entry.get("repo"), commit_sha=entry.get("commit_sha"),
        commit_sha_full=entry.get("commit_sha_full") or "",
        source_path=entry.get("repo_path"), source_url=entry.get("source_url"),
    )
    if not gate["copy_allowed"]:
        reasons.append(gate["reason"])
    if prov["provenance_status"] == "unknown":
        reasons.append(prov["reason"])
    if prov["provenance_status"] == "complete" and not prov["immutable_source_url"]:
        reasons.append("full SHA is present but source_url is not commit-pinned")

    duplicate_of = entry.get("duplicate_of")
    if duplicate_of:
        ids = catalog_ids or set()
        if duplicate_of not in ids:
            reasons.append("duplicate_of target is missing: %s" % duplicate_of)
        status = "invalid" if reasons else "incomplete"
        if reasons:
            status = "invalid"
        elif prov["provenance_status"] == "incomplete" or gate["license_status"] == "license_text_missing":
            status = "incomplete"
        return _result(status, reasons or ["duplicate relationship is valid"],
                       id=eid, duplicate_of=duplicate_of)

    ref = references_root / str(entry.get("domain") or "") / eid
    src = _source_path(entry, source_root)
    if not ref.is_file():
        reasons.append("reference file is missing")
    if not src.is_file():
        reasons.append("source file is missing")
    if src.is_file() and entry.get("sha256"):
        digest = hashlib.sha256(src.read_bytes()).hexdigest()
        if not digest.startswith(str(entry["sha256"])):
            reasons.append("source sha256 does not match catalog")
    if ref.is_file() and ref.stat().st_size == 0:
        reasons.append("reference file is empty")

    invalid = bool(reasons) or gate["license_status"] in ("blocked", "unknown") \
        or prov["provenance_status"] == "unknown"
    if invalid:
        return _result("invalid", reasons or ["provenance or license is invalid"],
                       id=eid, license=gate, provenance=prov)
    if (prov["provenance_status"] == "incomplete"
            or gate["license_status"] == "license_text_missing"
            or (prov["provenance_status"] == "complete" and not prov["immutable_source_url"])):
        reasons.append("legacy provenance/license evidence is incomplete")
        return _result("incomplete", reasons, id=eid, license=gate, provenance=prov)
    return _result("valid", ["catalog/source/reference/provenance/license are consistent"],
                   id=eid, license=gate, provenance=prov)


def validate_catalog(catalog_path: str | Path | None = None, *,
                     source_root: str | Path | None = None,
                     references_root: str | Path | None = None,
                     limit: int = 0) -> dict:
    catalog_file = Path(catalog_path or collector.CATALOG_YAML)
    source_dir = Path(source_root or collector.SOURCES_DIR)
    refs_dir = Path(references_root or collector.REFERENCES_DIR)
    entries = collector._read_catalog_entries(catalog_file)
    ids = {str(e.get("id")) for e in entries}
    results = []
    for entry in entries[:limit or None]:
        results.append(validate_entry(entry, source_root=source_dir,
                                      references_root=refs_dir, catalog_ids=ids))
    counts = {key: sum(1 for r in results if r["status"] == key)
              for key in STATUS_ORDER}
    return {
        "status": _worst(results) if results else "invalid",
        "counts": counts,
        "checked": len(results),
        "catalog": str(catalog_file),
        "results": results,
    }


def _reference_entry(reference: str | Path, catalog_path: str | Path | None = None) -> dict | None:
    target = Path(reference).resolve()
    for entry in collector._read_catalog_entries(Path(catalog_path or collector.CATALOG_YAML)):
        candidate = (collector.REFERENCES_DIR / str(entry.get("domain") or "")
                     / str(entry.get("id") or "")).resolve()
        if candidate == target:
            return entry
    return None


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Read-only provenance validator")
    parser.add_argument("--catalog", nargs="?", const=str(collector.CATALOG_YAML),
                        default="", help="validate catalog (optional path)")
    parser.add_argument("--repo", default="", help="source repository directory")
    parser.add_argument("--reference", default="", help="reference file path")
    parser.add_argument("--entry", default="", help="catalog entry id")
    parser.add_argument("--json", action="store_true")
    parser.add_argument("--limit", type=int, default=0)
    args = parser.parse_args(argv)

    if args.repo:
        payload = validate_repo(args.repo)
        label = "repository"
    elif args.reference:
        entry = _reference_entry(args.reference)
        if entry is None:
            payload = _result("invalid", ["reference is not present in catalog"])
        else:
            payload = validate_entry(
                entry, source_root=collector.SOURCES_DIR,
                references_root=collector.REFERENCES_DIR,
                catalog_ids={str(e.get("id")) for e in collector._read_catalog_entries()},
            )
        label = "reference"
    elif args.entry:
        entries = {str(e.get("id")): e for e in collector._read_catalog_entries()}
        entry = entries.get(args.entry)
        if entry is None:
            payload = _result("invalid", ["unknown catalog entry"])
        else:
            payload = validate_entry(
                entry, source_root=collector.SOURCES_DIR,
                references_root=collector.REFERENCES_DIR,
                catalog_ids=set(entries),
            )
        label = "entry"
    else:
        payload = validate_catalog(args.catalog or None, limit=args.limit)
        label = "catalog"

    if args.json:
        print(json.dumps(payload, ensure_ascii=False, indent=2))
    else:
        print("Provenance validation (%s): %s" % (label, payload["status"]))
        if payload.get("counts"):
            print("checked=%d valid=%d incomplete=%d invalid=%d" % (
                payload["checked"], payload["counts"]["valid"],
                payload["counts"]["incomplete"], payload["counts"]["invalid"]))
        for reason in payload.get("reasons") or []:
            print("  - " + reason)
        for item in (payload.get("results") or [])[:10]:
            if item["status"] != "valid":
                print("  [%s] %s: %s" % (item["status"], item.get("id", "?"),
                                        "; ".join(item.get("reasons") or [])))
    return {"valid": 0, "incomplete": 1, "invalid": 2}[payload["status"]]


if __name__ == "__main__":
    sys.exit(main())
