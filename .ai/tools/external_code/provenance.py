"""Provenance and license eligibility for external code.

This module is the single decision point shared by the collector, catalog,
promote, the External Code adapter and the read-only provenance validator.
It deliberately does not fetch, write, or modify external code.
"""

from __future__ import annotations

import re
from pathlib import Path
from urllib.parse import quote

SCHEMA_VERSION = 1

LICENSE_ALLOWLIST = frozenset({
    "MIT", "CC0-1.0", "BSD-2-Clause", "BSD-3-Clause", "Apache-2.0",
    "Unlicense", "ISC", "Zlib", "MPL-2.0",
})

LICENSE_STATUSES = (
    "eligible", "pending_review", "blocked", "unknown",
    "license_text_missing",
)
PROVENANCE_STATUSES = ("complete", "incomplete", "unknown")
COPY_ALLOWED_STATUSES = {"eligible", "license_text_missing"}

_FULL_SHA_RE = re.compile(r"^[0-9a-f]{40}$")
_SHORT_SHA_RE = re.compile(r"^[0-9a-f]{7,39}$")
_LICENSE_FILE_PREFIXES = ("LICENSE", "COPYING")


def _s(value) -> str:
    return str(value or "").strip()


def license_files(source_dir: str | Path) -> list[str]:
    """Return root-level license text files (no recursive guessing)."""
    directory = Path(source_dir)
    if not directory.is_dir():
        return []
    found = []
    for path in sorted(directory.iterdir()):
        if path.is_file() and path.name.upper().startswith(_LICENSE_FILE_PREFIXES):
            found.append(path.name)
    return found


def has_license_text(source_dir: str | Path) -> bool:
    return bool(license_files(source_dir))


def assess_license(license_id, *, license_text_present: bool | None,
                   license_source: str = "github_api_spdx",
                   declared_status: str | None = None,
                   allow_missing_text: bool = True) -> dict:
    """Classify a license without pretending missing evidence is confirmed.

    The existing project policy is an SPDX allowlist sourced from the GitHub API.
    When a local root license file is absent, allowed IDs are still usable under
    that policy, but the result is explicitly `license_text_missing` and records
    the basis/risk. Unknown and non-allowlisted IDs are never copy-allowed.
    """
    normalized = _s(license_id)
    if normalized.upper() in ("", "UNKNOWN", "NOASSERTION", "NONE"):
        normalized = normalized.upper() if normalized else ""
        return {
            "license_id": normalized or "unknown",
            "license_source": license_source or "unknown",
            "license_text_present": bool(license_text_present),
            "license_status": "unknown",
            "license_basis": "no_reliable_spdx_metadata",
            "license_risk": "unknown_license",
            "copy_allowed": False,
            "reason": "license ID is missing or unknown",
        }

    allowed = normalized in LICENSE_ALLOWLIST
    if declared_status in ("blocked", "pending_review"):
        return {
            "license_id": normalized,
            "license_source": license_source or "unknown",
            "license_text_present": bool(license_text_present),
            "license_status": declared_status,
            "license_basis": "declared_status",
            "license_risk": "declared_" + declared_status,
            "copy_allowed": False,
            "reason": "license was explicitly marked %s" % declared_status,
        }
    if not allowed:
        return {
            "license_id": normalized,
            "license_source": license_source or "unknown",
            "license_text_present": bool(license_text_present),
            "license_status": "blocked",
            "license_basis": "spdx_allowlist",
            "license_risk": "not_in_project_allowlist",
            "copy_allowed": False,
            "reason": "license %s is not in the project allowlist" % normalized,
        }

    if license_text_present is True:
        return {
            "license_id": normalized,
            "license_source": license_source or "github_api_spdx",
            "license_text_present": True,
            "license_status": "eligible",
            "license_basis": "spdx_allowlist_and_local_text",
            "license_risk": "none_known",
            "copy_allowed": True,
            "reason": "allowlisted SPDX license with local license text",
        }

    return {
        "license_id": normalized,
        "license_source": license_source or "github_api_spdx",
        "license_text_present": False,
        "license_status": "license_text_missing",
        "license_basis": "spdx_allowlist_existing_policy",
        "license_risk": "local_license_text_missing",
        "copy_allowed": bool(allow_missing_text),
        "reason": ("allowlisted SPDX metadata; local license text is missing "
                   "(existing policy permits metadata-based use, risk recorded)"
                   if allow_missing_text else
                   "allowlisted SPDX metadata but local license text is missing"),
    }


def assess_provenance(*, full_name, commit_sha, commit_sha_full="",
                      source_path="", source_url="") -> dict:
    """Classify provenance completeness without upgrading a short SHA."""
    full = _s(commit_sha_full).lower()
    short = _s(commit_sha).lower()
    if _FULL_SHA_RE.match(full):
        status = "complete"
        reason = "full commit SHA is recorded"
    elif _SHORT_SHA_RE.match(short) or _SHORT_SHA_RE.match(full):
        status = "incomplete"
        reason = "only a short commit SHA is available; full SHA was not guessed"
    else:
        status = "unknown"
        reason = "no valid commit SHA is recorded"

    path = _s(source_path).lstrip("/")
    expected_sha = full if _FULL_SHA_RE.match(full) else short
    immutable = bool(_s(full_name) and expected_sha and path and source_url
                     and "/blob/%s/" % expected_sha in source_url)
    return {
        "repo": _s(full_name),
        "source_path": path,
        "commit_sha": short or full,
        "commit_sha_full": full if _FULL_SHA_RE.match(full) else "",
        "provenance_status": status,
        "source_url": _s(source_url),
        "immutable_source_url": immutable,
        "reason": reason,
    }


def source_file_url(full_name, commit_sha, source_path) -> str:
    """Build a commit-pinned GitHub file URL, never a branch URL."""
    repo = _s(full_name)
    sha = _s(commit_sha)
    path = _s(source_path).lstrip("/")
    if not repo or not sha or not path:
        return ""
    return "https://github.com/%s/blob/%s/%s" % (
        repo, sha, quote(path, safe="/"),
    )


def metadata_for_source(meta: dict, source_dir: str | Path) -> dict:
    """Build the provenance/license fields stored beside a fetched source."""
    names = license_files(source_dir)
    present = bool(names)
    license_result = assess_license(
        meta.get("license"), license_text_present=present,
        license_source=meta.get("license_source") or "github_api_spdx",
        declared_status=meta.get("license_status_override"),
        allow_missing_text=bool(meta.get("allow_missing_license_text", True)),
    )
    provenance = assess_provenance(
        full_name=meta.get("full_name"),
        commit_sha=meta.get("commit_sha"),
        commit_sha_full=meta.get("commit_sha_full"),
        source_path="",
    )
    return {
        "commit_sha_full": _s(meta.get("commit_sha_full")),
        "commit_sha": _s(meta.get("commit_sha")),
        "license_files": names,
        "license_text_present": present,
        **{k: license_result[k] for k in (
            "license_id", "license_source", "license_status",
            "license_basis", "license_risk", "copy_allowed",
        )},
        "provenance_status": provenance["provenance_status"],
        "provenance_reason": provenance["reason"],
    }
