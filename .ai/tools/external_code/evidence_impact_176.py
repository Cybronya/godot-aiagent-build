#!/usr/bin/env python3
"""Phase 1.76 Batch C - Evidence Impact Review (READ-ONLY).

Derives machine-readable audit artefacts from the Batch B workspace and the
formal analysis/linkage/candidate layer. Never writes to formal data, the
Batch B workspace, the Phase 1.75 workspace, the parser or the adapter.

Modes:
    build       write the Batch C artefacts
    validate    re-derive and check the artefacts + integrity against baseline
"""
from __future__ import annotations

import hashlib
import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
B_WS = ROOT / ".ai/learning/external_code/reanalysis/parser_1.76"
P75_WS = ROOT / ".ai/learning/external_code/reanalysis/parser_1.75"
FORMAL = ROOT / ".ai/learning/external_code/analysis"
LINKS = ROOT / ".ai/learning/external_code/feature_links"
CANDS = ROOT / ".ai/learning/candidate_workspace"
OUT = ROOT / ".ai/learning/external_code/evidence_impact/phase_1.76"
BASELINE = ROOT / ".ai/tmp/phase176c_baseline.json"

AUDITED_FEATURES = ["health", "health_bar", "openable_door", "blackboard", "attack_emitter"]
PARSER_B = "gd_parse@1.75+build:6b74a6cd20a06033"

DECL_RE = re.compile(
    r"^\s*(?:@\w+(?:\([^)]*\))?\s*)*(export|onready|var|const|signal|func|enum|class_name)\b"
)


def load(path: Path):
    return json.loads(Path(path).read_text(encoding="utf-8"))


def sha(path: Path) -> str:
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def dump(name: str, payload) -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    (OUT / name).write_text(
        json.dumps(payload, indent=1, sort_keys=True, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )


def rel(path) -> str:
    return str(path).replace("\\", "/")


def rkey(path) -> str:
    """Workspace-relative key, matching the baseline snapshot's key format."""
    return Path(path).resolve().relative_to(ROOT).as_posix()


# --------------------------------------------------------------------------
# inputs
# --------------------------------------------------------------------------
def load_inputs():
    manifest = load(B_WS / "manifest.json")
    inventory = load(ROOT / ".ai/learning/external_code/reconciliation/phase_1.76/inventory.json")
    formal = {p.stem: load(p) for p in sorted(FORMAL.glob("*.json"))}
    links = [load(p) for p in sorted(LINKS.glob("*.json"))]
    cands = {p.stem: load(p) for p in sorted(CANDS.glob("candidates/*.json"))}
    policy = load(ROOT / ".ai/tools/feature_registry/candidate_seed_policy.json")
    projections = {
        f: load(ROOT / f".ai/learning/feature_evidence/{f}.json") for f in AUDITED_FEATURES
    }
    feature_graph = load(ROOT / ".ai/context/feature_graph.json")
    return manifest, inventory, formal, links, cands, policy, projections, feature_graph


def feature_symbols(projections) -> dict[str, set[str]]:
    out = {}
    for fid, proj in projections.items():
        out[fid] = {e["source_symbol"] for e in proj["symbol_evidence"] if e.get("source_symbol")}
    return out


def linkage_index(links):
    by_pair = {(l["analysis_id"], l["feature_id"]): l for l in links}
    by_analysis = {}
    for l in links:
        by_analysis.setdefault(l["analysis_id"], []).append(l)
    return by_pair, by_analysis


# --------------------------------------------------------------------------
# C1 - mapping
# --------------------------------------------------------------------------
def build_mapping(manifest, formal):
    rows = []
    for rec in sorted(manifest["records"], key=lambda r: r["analysis_id"]):
        aid = rec["analysis_id"]
        f = formal.get(aid)
        checks = {}
        if f is not None:
            checks = {
                "repository": f.get("repo") == rec["repository"],
                "commit": f.get("commit_sha_full") == rec["full_commit_sha"],
                "source_path": f.get("source_path") == rec["source_path"],
                "source_digest": f.get("source_digest") == rec["source_digest"],
                "input_digest": f.get("input_digest") == rec["input_digest"],
            }
        if f is None:
            status = "MISSING_FORMAL_RECORD"
        elif all(checks.values()):
            status = "EXACT_IDENTITY_MATCH"
        elif checks.get("source_digest") and checks.get("source_path"):
            status = "SOURCE_DIGEST_MATCH"
        elif checks.get("commit") and checks.get("source_path"):
            status = "COMMIT_MATCH"
        elif checks.get("source_path"):
            status = "PATH_MATCH"
        else:
            status = "AMBIGUOUS_MATCH"

        proc = rec["processing_status"]
        if proc == "REANALYZED_AND_VALIDATED":
            impact = "WORKSPACE_ONLY_NOT_CONSUMED"
        elif proc == "REUSED_PHASE_1_75":
            impact = "REUSED_P75_WORKSPACE_ONLY_NOT_CONSUMED"
        else:
            impact = "NOT_APPLICABLE_NOT_CONSUMED"

        rows.append(
            {
                "batch_b_record_id": aid,
                "repository": rec["repository"],
                "commit": rec["full_commit_sha"],
                "source_path": rec["source_path"],
                "source_digest": rec["source_digest"],
                "batch_b_parser_identity": rec["parser_build_identity"],
                "batch_b_processing_status": proc,
                "reanalysis_id": rec.get("reanalysis_id"),
                "reanalysis_ref": rec.get("reanalysis_ref"),
                "diff_ref": rec.get("diff_ref"),
                "formal_analysis_id": aid if f else None,
                "formal_parser_identity": (
                    f"{f.get('parser_name')}@{f.get('parser_version')}" if f else None
                ),
                "formal_analysis_status": f.get("analysis_status") if f else None,
                "formal_created_at": f.get("created_at") if f else None,
                "identity_checks": checks,
                "identity_match_status": status,
                "impact_status": impact,
                "consumed_by_formal_analysis": False,
                "notes": (
                    "Batch B result lives only in the parser_1.76 workspace; the formal "
                    "record still carries parser_version=1.71 and is byte-identical to the "
                    "Batch B preflight snapshot."
                )
                if f
                else "no formal record",
            }
        )
    return rows


# --------------------------------------------------------------------------
# C2 - symbol impact
# --------------------------------------------------------------------------
# Manual judgement per (analysis_id, symbol). Mechanical fields (old/new state,
# line, related linkage) are filled from data; only the verdict is curated.
IMPACT_PLAN = {
    ("ext-7d7933a2343f52d0", "target_value"): dict(
        classification="POTENTIAL_EVIDENCE_RECLASSIFICATION",
        severity="MEDIUM",
        confidence="HIGH",
        related_feature="openable_door",
        linkage="lnk-23addea8960377c4",
        evidence_type="SYMBOL_TOKEN_OVERLAP",
        reasoning=(
            "Formal 1.71 stores target_value as a plain variable with value '0.0:'. Parser 1.75/1.76 "
            "represents it as PROPERTY with has_setter=true, setter at record line 19 (commit 16), "
            "value '0.0', end_line 18. The symbol is not removed and not duplicated. The only linkage "
            "item referencing it is the AMBIGUOUS openable_door token link ('target' vs boolean_target), "
            "which the new representation makes less plausible (a tweened life-bar value, not a door target). "
            "No classification change is authorized by this review."
        ),
        review="YES",
    ),
    ("ext-9f0aad5e01dd71f7", "current_health"): dict(
        classification="POTENTIAL_FEATURE_MATCH",
        severity="MEDIUM",
        confidence="LOW",
        related_feature="health_bar",
        linkage="lnk-bdec07041badaf0d",
        evidence_type="NONE",
        reasoning=(
            "Lifebar.gd now exposes a current_health variable. The health_bar Feature exposes "
            "get_ratio/_draw/_health and health exposes _current_health/get_current_health; there is no "
            "exact identifier on either side. The existing health_bar linkage for this analysis is "
            "NO_SUPPORTED_LINK. A name-proximity review is warranted, but a link cannot be created "
            "from name similarity."
        ),
        review="YES",
    ),
    ("ext-9f0aad5e01dd71f7", "maximum"): dict(
        classification="POTENTIAL_FEATURE_MATCH",
        severity="LOW",
        confidence="LOW",
        related_feature="health_bar",
        linkage="lnk-bdec07041badaf0d",
        evidence_type="NONE",
        reasoning=(
            "maximum is a new local bar bound. The health_bar Feature has no symbol named maximum "
            "(health has max_health); no identifier match, so this is at most a review hint."
        ),
        review="YES",
    ),
    ("ext-51d46c1b4943a254", "is_locked"): dict(
        classification="POTENTIAL_EVIDENCE_STRENGTHENING",
        severity="MEDIUM",
        confidence="LOW",
        related_feature="openable_door",
        linkage="lnk-b382814f8bca80a5",
        evidence_type="SYMBOL_TOKEN_OVERLAP",
        reasoning=(
            "door.gd now exposes an is_locked PROPERTY that 1.71 did not record. The existing "
            "POTENTIAL_RELEVANCE linkage rests on Door/open tokens and the seed policy notes the external "
            "door API shares no identifier with set_open/is_open. is_locked still is not is_open/_is_open, "
            "so the stated limitation survives; the new declared state may strengthen the semantic claim "
            "and must be reviewed by a human."
        ),
        review="YES",
    ),
    ("ext-27ddd863881677d7", "key"): dict(
        classification="POTENTIAL_EVIDENCE_STRENGTHENING",
        severity="LOW",
        confidence="LOW",
        related_feature="blackboard",
        linkage="lnk-bb935a2c8bdbfc39",
        evidence_type="SYMBOL_TOKEN_OVERLAP",
        reasoning=(
            "blackboard_set.gd now exposes key/value exports used with blackboard.set_value. The "
            "blackboard Feature has keys (plural) but no key; the existing link is class-token "
            "POTENTIAL_RELEVANCE only, and token proximity cannot upgrade it."
        ),
        review="YES",
    ),
    ("ext-27ddd863881677d7", "value"): dict(
        classification="POTENTIAL_EVIDENCE_STRENGTHENING",
        severity="LOW",
        confidence="LOW",
        related_feature="blackboard",
        linkage="lnk-bb935a2c8bdbfc39",
        evidence_type="SYMBOL_TOKEN_OVERLAP",
        reasoning=(
            "value is the blackboard_set export written through blackboard.set_value. The blackboard Feature "
            "has set_value/get_value/has_value but no symbol named value, and the existing link is class-token "
            "POTENTIAL_RELEVANCE only."
        ),
        review="YES",
    ),
    ("ext-9e62ed2e3dec8164", "board"): dict(
        classification="REQUIRES_MANUAL_REVIEW",
        severity="LOW",
        confidence="HIGH",
        related_feature="blackboard",
        linkage="lnk-042638ff10ae0b0e",
        evidence_type="NONE",
        reasoning=(
            "board is a BoardModel reference in a Kanban UI script. The name shares the token 'board' "
            "with the blackboard Feature but is semantically unrelated; recording it prevents a future "
            "name-based matcher from treating it as blackboard evidence."
        ),
        review="YES",
    ),
    ("ext-5a8d53c7f530e4af", "door"): dict(
        classification="POTENTIAL_FEATURE_MATCH",
        severity="LOW",
        confidence="LOW",
        related_feature="openable_door",
        linkage=None,
        evidence_type="NONE",
        reasoning=(
            "door_unlock_interaction.gd now exposes a door variable. No formal linkage record exists for "
            "this analysis (see linkage coverage gap), and a variable holding a Door node is not the door "
            "API, so no evidence can be attached without human review."
        ),
        review="YES",
    ),
    ("ext-d5f7ac2db3a8c4e4", "base_damage"): dict(
        classification="POTENTIAL_FEATURE_MATCH",
        severity="LOW",
        confidence="LOW",
        related_feature="attack_emitter",
        linkage="lnk-01c9ea986153c619",
        evidence_type="SYMBOL_TOKEN_OVERLAP",
        reasoning=(
            "base_damage shares the token 'damage' with the attack_emitter variable damage. The existing "
            "link is POTENTIAL_RELEVANCE via the class token 'attack'; a token overlap is a clue only."
        ),
        review="YES",
    ),
    ("ext-1d204b35464cf388", "health"): dict(
        classification="POTENTIAL_EVIDENCE_STRENGTHENING",
        severity="MEDIUM",
        confidence="MEDIUM",
        related_feature="health",
        linkage="lnk-d2d95d8162be1592",
        evidence_type="SYMBOL_EXACT_MATCH",
        reasoning=(
            "Phase 1.75 (reused unchanged by Batch B) captured the internal health state variable that "
            "1.71 missed. The linkage is already DIRECT via take_damage/heal/health_changed and this is a "
            "candidate seed; the added state variable would strengthen the same claim, not create a new link. "
            "Formal Linkage still lists three evidence items."
        ),
        review="YES",
    ),
    ("ext-23949c1378c49203", "get_value"): dict(
        classification="POTENTIAL_EVIDENCE_STRENGTHENING",
        severity="MEDIUM",
        confidence="HIGH",
        related_feature="blackboard",
        linkage="lnk-7084dc8999c2182b",
        evidence_type="SYMBOL_EXACT_MATCH",
        reasoning=(
            "Phase 1.75 (reused) captured get_value, an exact FUNCTION name match with the blackboard "
            "Feature that 1.71 missed. The formal DIRECT linkage currently lists Blackboard/keys/set_value/"
            "has_value/erase_value; consuming the reanalysis would add a sixth exact identifier to the same "
            "linkage. Qualification is unchanged (already QUALIFIED_DIRECT, NOT_INDEPENDENT)."
        ),
        review="YES",
    ),
    ("ext-73c80a3db6d71e48", "max_hp"): dict(
        classification="POTENTIAL_EVIDENCE_STRENGTHENING",
        severity="MEDIUM",
        confidence="LOW",
        related_feature="health",
        linkage="lnk-6fff3ce176bd5813",
        evidence_type="NONE",
        reasoning=(
            "Phase 1.75 (reused) captured the @export hp/max_hp/reset_hp/reset_max_hp that 1.71 missed, "
            "which removes the seed-policy limitation 'parser captured 1 of 5 @export vars'. max_hp is not "
            "max_health, so no exact identifier match exists; the seed claim is unchanged."
        ),
        review="YES",
    ),
    ("ext-ab693f3d6ef9439c", "size"): dict(
        classification="POTENTIAL_FEATURE_MATCH",
        severity="LOW",
        confidence="LOW",
        related_feature="health_bar",
        linkage=None,
        evidence_type="SYMBOL_TOKEN_OVERLAP",
        reasoning=(
            "HealthBar exposes a size PROPERTY. The health_bar Feature has bar_size, not size, and this "
            "analysis has no formal linkage record at all, so the health_bar layer never evaluated it."
        ),
        review="YES",
    ),
}


def symbol_rows(manifest, formal, links_by_analysis, featsyms):
    rows = []
    for rec in sorted(manifest["records"], key=lambda r: r["analysis_id"]):
        aid = rec["analysis_id"]
        proc = rec["processing_status"]
        if proc == "REANALYZED_AND_VALIDATED":
            diff = load(B_WS / rec["diff_ref"])
            added = [
                {"name": a["name"], "kind": a["kind"], "group": a.get("group"), "line": a["line"]}
                for a in diff["symbols_added"]
            ]
            reclass = diff["symbols_reclassified"]
            removed = diff["symbols_removed"]
            coverage = diff["coverage"]["new"]["syntax_coverage_status"]
            source = "parser_1.76_workspace"
        elif proc == "REUSED_PHASE_1_75":
            diff = load(P75_WS / "diff" / f"{aid}.json")
            added = [
                {
                    "name": a["name"],
                    "kind": a.get("declaration_kind"),
                    "group": a.get("_group"),
                    "line": a["line"],
                }
                for a in diff["symbols_added"]
            ]
            reclass = diff.get("symbols_reclassified", [])
            removed = diff.get("symbols_removed", [])
            coverage = diff["status"]["syntax_coverage_status"]["new"]
            source = "parser_1.75_workspace_reused"
        else:
            continue

        # target_value is listed by the diff in symbols_added *and* symbols_reclassified;
        # the Batch B accounting counts it once, as a reclassification (45 = 44 + 1).
        reclass_names = {r["symbol"] for r in reclass}
        listed_added = len(added)
        added = [a for a in added if a["name"] not in reclass_names]

        for a in added:
            plan = IMPACT_PLAN.get((aid, a["name"]), {})
            rows.append(
                {
                    "source_analysis_id": aid,
                    "reanalysis_id": rec.get("reanalysis_id"),
                    "repository": rec["repository"],
                    "commit": rec["full_commit_sha"],
                    "source_path": rec["source_path"],
                    "symbol_name": a["name"],
                    "change": "ADDED",
                    "old_symbol_state": None,
                    "new_symbol_state": {
                        "declaration_kind": a["kind"],
                        "group": a["group"],
                        "record_line": a["line"],
                    },
                    "related_feature": plan.get("related_feature"),
                    "existing_linkage_id": plan.get("linkage"),
                    "evidence_type": plan.get("evidence_type", "NONE"),
                    "impact_classification": plan.get("classification", "NO_IMPACT"),
                    "severity": plan.get("severity", "INFO"),
                    "confidence": plan.get("confidence", "HIGH"),
                    "reasoning": plan.get(
                        "reasoning",
                        "Newly captured declaration; no audited Feature symbol has the same identifier and "
                        "no existing linkage for this analysis references it.",
                    ),
                    "required_human_review": plan.get("review", "NO"),
                    "data_source": source,
                }
            )
        for r in reclass:
            plan = IMPACT_PLAN[(aid, r["symbol"])]
            rows.append(
                {
                    "source_analysis_id": aid,
                    "reanalysis_id": rec.get("reanalysis_id"),
                    "repository": rec["repository"],
                    "commit": rec["full_commit_sha"],
                    "source_path": rec["source_path"],
                    "symbol_name": r["symbol"],
                    "change": "RECLASSIFIED",
                    "old_symbol_state": {
                        "declaration_kind": r["from_kind"],
                        "group": r["from_group"],
                        "value": r["old_value"],
                        "record_line": r["line"],
                    },
                    "new_symbol_state": {
                        "declaration_kind": r["to_kind"],
                        "group": r["to_group"],
                        "value": r["new_value"],
                        "has_setter": r["new_setter"],
                        "record_line": r["line"],
                    },
                    "related_feature": plan["related_feature"],
                    "existing_linkage_id": plan["linkage"],
                    "evidence_type": plan["evidence_type"],
                    "impact_classification": plan["classification"],
                    "severity": plan["severity"],
                    "confidence": plan["confidence"],
                    "reasoning": plan["reasoning"],
                    "required_human_review": plan["review"],
                    "data_source": source,
                }
            )
        for s in removed:  # none expected; recorded if it ever appears
            rows.append(
                {
                    "source_analysis_id": aid,
                    "reanalysis_id": rec.get("reanalysis_id"),
                    "repository": rec["repository"],
                    "commit": rec["full_commit_sha"],
                    "source_path": rec["source_path"],
                    "symbol_name": s.get("name"),
                    "change": "REMOVED",
                    "old_symbol_state": s,
                    "new_symbol_state": None,
                    "related_feature": None,
                    "existing_linkage_id": None,
                    "evidence_type": "NONE",
                    "impact_classification": "REQUIRES_MANUAL_REVIEW",
                    "severity": "HIGH",
                    "confidence": "LOW",
                    "reasoning": "Symbol disappearance must be explained before any consumption.",
                    "required_human_review": "YES",
                    "data_source": source,
                }
            )
        rows.append(
            {
                "source_analysis_id": aid,
                "record_summary": True,
                "coverage_status": coverage,
                "diff_listed_added": listed_added,
                "symbols_added": len(added),
                "symbols_reclassified": len(reclass),
                "symbols_removed": len(removed),
                "linked_features": sorted({l["feature_id"] for l in links_by_analysis.get(aid, [])}),
                "data_source": source,
            }
        )
    return rows


# --------------------------------------------------------------------------
# C3 - PARTIAL coverage
# --------------------------------------------------------------------------
def top_level_declarations(path: Path):
    out = []
    for i, line in enumerate(path.read_text(encoding="utf-8", errors="replace").splitlines(), 1):
        if line[:1] in (" ", "\t"):
            continue
        m = DECL_RE.match(line)
        if m:
            kind = m.group(1)
            rest = line[m.end():].strip()
            name = None
            if kind == "func":
                name = re.split(r"[\s(]", rest)[0]
            elif kind == "var":
                name = re.split(r"[\s:=]", rest)[0]
            elif kind == "const":
                name = re.split(r"[\s:=]", rest)[0]
            elif kind == "signal":
                name = re.split(r"[\s(]", rest)[0]
            elif kind == "enum":
                name = re.split(r"[\s{]", rest)[0] or "(anonymous)"
            elif kind == "class_name":
                name = re.split(r"[\s]", rest)[0]
            elif kind == "onready":
                tail = rest
                if tail.startswith("var "):
                    tail = tail[4:].strip()
                name = re.split(r"[\s:=]", tail)[0]
            elif kind == "export":
                tail = rest
                if tail.startswith("("):
                    depth, idx = 0, 0
                    for idx, ch in enumerate(tail):
                        depth += ch == "("
                        depth -= ch == ")"
                        if depth == 0:
                            break
                    tail = tail[idx + 1 :].strip()
                if tail.startswith("var"):
                    name = re.split(r"[\s:=]", tail[3:].strip())[0]
            out.append({"kind": kind, "name": name, "commit_line": i, "record_line": i + 3,
                        "line_text": line.strip()[:160]})
    return out


def parsed_symbol_names(doc):
    names = {}
    for group, items in doc["symbols"].items():
        if isinstance(items, str):
            if items:
                names[items.split()[0]] = (group, group.upper())
            continue
        if not isinstance(items, list):
            continue
        for it in items:
            if isinstance(it, dict) and it.get("name"):
                names[it["name"]] = (group, it.get("declaration_kind") or it.get("kind"))
    return names


def build_partial(manifest, formal, links_by_analysis):
    rows = []
    for rec in manifest["records"]:
        if rec["processing_status"] != "REANALYZED_AND_VALIDATED":
            continue
        diff = load(B_WS / rec["diff_ref"])
        if diff["coverage"]["new"]["syntax_coverage_status"] != "PARTIAL":
            continue
        aid = rec["analysis_id"]
        doc = load(B_WS / "reanalyzed" / f"{aid}.json")
        fdoc = formal[aid]
        src = Path(doc["source_file_path"])
        decls = top_level_declarations(src)
        parsed = parsed_symbol_names(doc)
        formal_names = parsed_symbol_names(fdoc)
        missing = []
        for d in decls:
            kind = d["kind"]
            if kind == "export":
                kind = "var"
            present = d["name"] in parsed
            if not present:
                missing.append(
                    {
                        "name": d["name"],
                        "declaration_kind": kind,
                        "record_line": d["record_line"],
                        "commit_line": d["commit_line"],
                        "flagged_by_parser": any(
                            u.get("line") == d["record_line"] for u in doc["unsupported_constructs"]
                        ),
                        "in_formal_1_71": d["name"] in formal_names,
                    }
                )
        linkage_ids = [
            {"linkage_id": l["linkage_id"], "feature_id": l["feature_id"],
             "classification": l["linkage_classification"]}
            for l in links_by_analysis.get(aid, [])
        ]
        rows.append(
            {
                "analysis_id": aid,
                "repository": rec["repository"],
                "commit": rec["full_commit_sha"],
                "source_path": rec["source_path"],
                "source_file_verified": rel(src),
                "source_read_method": "local commit copy under code_library/sources, read-only",
                "coverage_status": doc["syntax_coverage_status"],
                "analysis_completeness": doc["analysis_completeness"],
                "parse_execution_status": doc["parse_execution_status"],
                "unsupported_constructs": doc["unsupported_constructs"],
                "unrecognized_declarations": doc["unrecognized_declarations"],
                "parsed_symbol_names": sorted(parsed),
                "top_level_declarations": [
                    {"name": d["name"], "kind": d["kind"], "record_line": d["record_line"]}
                    for d in decls
                ],
                "missing_declarations": missing,
                "existing_linkages": linkage_ids,
                "affected_linkage_ids": [l["linkage_id"] for l in linkage_ids],
                "absence_is_not_evidence_of_absence": True,
                "impact": "INSUFFICIENT_COVERAGE",
                "notes": (
                    "PARTIAL coverage: absence of a parsed symbol is not evidence of source-level absence. "
                    "Declarations listed in missing_declarations were confirmed by direct read of the "
                    "commit copy; that read explains impact and does not claim parser support."
                ),
            }
        )
    return rows


# --------------------------------------------------------------------------
# C4 - target_value
# --------------------------------------------------------------------------
def build_target_value(formal, links):
    aid = "ext-7d7933a2343f52d0"
    fdoc = formal[aid]
    old_entry = next(e for e in fdoc["symbols"]["variables"] if e["name"] == "target_value")
    doc = load(B_WS / "reanalyzed" / f"{aid}.json")
    new_entry = next(e for e in doc["symbols"]["properties"] if e["name"] == "target_value")
    diff = load(B_WS / "diff" / f"{aid}.json")
    rc = next(r for r in diff["symbols_reclassified"] if r["symbol"] == "target_value")
    direct = []
    mentioned = []
    for l in links:
        item_hit = [i for i in l.get("evidence_items", []) if i.get("symbol_name") == "target_value"]
        if item_hit:
            direct.append(
                {
                    "linkage_id": l["linkage_id"],
                    "feature_id": l["feature_id"],
                    "classification": l["linkage_classification"],
                    "evidence_id": item_hit[0]["evidence_id"],
                    "evidence_type": item_hit[0]["evidence_type"],
                    "matched_feature_symbol": item_hit[0].get("feature_symbol"),
                    "matched_value": item_hit[0].get("matched_value"),
                }
            )
        elif "target_value" in json.dumps(l.get("evidence_items", [])):
            mentioned.append(
                {
                    "linkage_id": l["linkage_id"],
                    "feature_id": l["feature_id"],
                    "classification": l["linkage_classification"],
                    "context": "appears only in the pair-evaluation explanation text",
                }
            )
    return {
        "analysis_id": aid,
        "repository": "godot-open-rpg",
        "commit": fdoc["commit_sha_full"],
        "source_path": fdoc["source_path"],
        "formal_parser_identity": f"{fdoc['parser_name']}@{fdoc['parser_version']}",
        "formal_stored_state": {
            "group": "variables",
            "declaration_kind": "VARIABLE (implied by group)",
            "record_line": old_entry["line"],
            "value": old_entry["value"],
            "representation_error": "old regex swallowed the property colon into the value",
        },
        "batch_b_state": {
            "group": "properties",
            "declaration_kind": new_entry["declaration_kind"],
            "record_line": new_entry["line"],
            "value": rc["new_value"],
            "has_setter": new_entry["has_setter"],
            "has_getter": new_entry["has_getter"],
            "setter_record_line": new_entry["accessors"][0]["line"],
            "setter_commit_line": new_entry["accessors"][0]["line"] - 3,
            "property_end_line": new_entry["end_line"],
            "reclassification_explained": rc["explained"],
        },
        "source_confirmed": {
            "commit_line_property": 15,
            "commit_line_setter": 16,
            "commit_line_setter_end": 34,
            "read_from": "code_library/sources/gdquest-demos__godot-open-rpg/gd/src/combat/ui/battler_entry/ui_life_bar.gd",
        },
        "existing_linkage_references": direct,
        "explanation_only_mentions": mentioned,
        "no_existing_linkage_reference": not direct,
        "graph_symbol_dependency": False,
        "graph_note": "feature_graph edges are feature-level only; no symbol-level dependency exists",
        "is_removal": False,
        "is_two_symbols": False,
        "reclassification_impact": "EVIDENCE_INTERPRETATION_CORRECTED_NO_CLASSIFICATION_CHANGE",
        "severity": "MEDIUM",
        "required_human_review": "YES",
        "reasoning": (
            "The stored evidence item is a token overlap ('target' vs boolean_target) classified AMBIGUOUS. "
            "The 1.76 property view shows a tweened life-bar value with a setter, which further weakens the "
            "door association, but a reviewer must decide whether to re-word or re-evaluate that single item. "
            "Nothing is deleted, nothing is created, and the formal linkage must not be edited by this batch."
        ),
    }


# --------------------------------------------------------------------------
# C5 - candidates and seed policy
# --------------------------------------------------------------------------
def build_candidates(manifest, formal, links, cands, policy):
    proc = {r["analysis_id"]: r["processing_status"] for r in manifest["records"]}
    reanalysis = {r["analysis_id"]: r.get("reanalysis_id") for r in manifest["records"]}
    link_by_id = {l["linkage_id"]: l for l in links}
    impacted = {(k[0], k[1]) for k in IMPACT_PLAN}
    out = []
    for cid, c in sorted(cands.items()):
        seeds = []
        for r in c["evidence_refs"]:
            l = link_by_id.get(r["linkage_id"], {})
            fdoc = formal.get(r["analysis_id"], {})
            seeds.append(
                {
                    "linkage_id": r["linkage_id"],
                    "feature_id": r["feature_id"],
                    "classification": r["classification"],
                    "seed_eligibility": r["seed_eligibility"],
                    "independence": r["independence"],
                    "analysis_id": r["analysis_id"],
                    "batch_b_processing_status": proc.get(r["analysis_id"], "NOT_IN_BATCH_B"),
                    "batch_b_reanalysis_id": reanalysis.get(r["analysis_id"]),
                    "seed_symbols": [i.get("symbol_name") for i in r.get("evidence_item_refs", [])],
                    "parser_identity_of_seed": (
                        f"{fdoc.get('parser_name')}@{fdoc.get('parser_version')}" if fdoc else None
                    ),
                    "analysis_record_digest_matches": (
                        sha(FORMAL / f"{r['analysis_id']}.json") == r.get("analysis_record_digest")
                    ),
                    "source_digest_matches": fdoc.get("source_digest") == r.get("source_digest"),
                    "commit_matches": fdoc.get("commit_sha_full") == r.get("source_commit"),
                    "linkage_digest_matches": (
                        sha(LINKS / f"{r['analysis_id']}__{r['feature_id']}.json")
                        == r.get("linkage_record_digest")
                    ),
                    "symbols_touched_by_batch_b": sorted(
                        [s for (a, s) in impacted if a == r["analysis_id"]]
                    ),
                }
            )
        ctx = []
        for r in c.get("context_refs", []):
            ctx.append(
                {
                    "linkage_id": r["linkage_id"],
                    "feature_id": r["feature_id"],
                    "context_kind": r["context_kind"],
                    "classification": r["classification"],
                    "counts_as_seed": r.get("counts_as_seed"),
                    "counts_as_implementation_evidence": r.get("counts_as_implementation_evidence"),
                    "derivation_type": r.get("derivation_type"),
                }
            )
        out.append(
            {
                "candidate_id": cid,
                "feature_id": c["feature_id"],
                "candidate_status": c["candidate_status"],
                "policy_version": c["policy_version"],
                "seeds": seeds,
                "context_refs": ctx,
                "qualification_changed_by_batch_b": False,
                "over_optimistic": False,
                "over_conservative": False,
                "notes": (
                    "Every seed points at a Phase 1.75-reused analysis whose formal record and linkage are "
                    "byte-identical to what the candidate references. Batch B produced no new reanalysis for "
                    "these files, so candidate eligibility is untouched; only a human consumption decision on "
                    "the reused 1.75 additions could change evidence strength later."
                ),
            }
        )
    policy_review = {
        "policy_path": ".ai/tools/feature_registry/candidate_seed_policy.json",
        "policy_version": policy["policy_version"],
        "feature_scope": policy["feature_scope"],
        "context_features": policy["context_features"],
        "seed_count": len(policy["seeds"]),
        "seed_ids": [s["linkage_id"] for s in policy["seeds"]],
        "workspace_results_admissible": False,
        "workspace_admissibility_basis": (
            "No explicit parser-version rule exists, but every seed is keyed by linkage_id plus the "
            "linkage/analysis digests, and linkage records embed the formal analysis digest. An unreviewed "
            "workspace reanalysis cannot satisfy those references, so admission is prevented implicitly "
            "rather than by an explicit rule."
        ),
        "requires_formal_analysis_update": "IMPLICIT_ONLY",
        "distinguishes_complete_vs_partial_coverage": False,
        "coverage_evidence": (
            "The policy JSON has no coverage/parser_version field; the only coverage statement is free text "
            "inside one seed's limitations ('parser captured 1 of 5 @export vars')."
        ),
        "prevents_graph_derived_seed": True,
        "graph_mechanism": (
            "context_relations enumerates the graph-derived relation and candidate context_refs carry "
            "counts_as_seed=false / counts_as_implementation_evidence=false."
        ),
        "gaps": [
            "No explicit rule that only formal (non-workspace) analysis may seed a candidate.",
            "No machine-readable coverage-status gate (COMPLETE vs PARTIAL).",
        ],
    }
    return out, policy_review


# --------------------------------------------------------------------------
# linkage coverage (formal layer)
# --------------------------------------------------------------------------
def build_linkage_coverage(formal, links):
    per = {}
    for l in links:
        per.setdefault(l["analysis_id"], []).append(l["feature_id"])
    missing = []
    for aid in sorted(formal):
        if aid not in per:
            f = formal[aid]
            missing.append(
                {
                    "analysis_id": aid,
                    "file_type": f.get("file_type"),
                    "source_path": f.get("source_path"),
                    "repository": f.get("repo"),
                }
            )
    return {
        "formal_analyses": len(formal),
        "linkage_records": len(links),
        "analyses_with_linkage": len(per),
        "analyses_without_any_linkage": missing,
        "note": "Each linked analysis has exactly 5 feature linkages (one per audited feature).",
    }


# --------------------------------------------------------------------------
# integrity
# --------------------------------------------------------------------------
def current_hashes():
    import glob

    groups = {}
    groups["formal_analysis"] = {rkey(p): sha(p) for p in sorted(FORMAL.glob("*.json"))}
    groups["formal_linkage"] = {rkey(p): sha(p) for p in sorted(LINKS.glob("*.json"))}
    groups["candidates"] = {
        rkey(p): sha(p)
        for p in sorted(CANDS.rglob("*.json"))
    }
    groups["batch_b_workspace"] = {
        rkey(p): sha(p) for p in sorted(B_WS.rglob("*")) if p.is_file()
    }
    groups["p175_workspace"] = {
        rkey(p): sha(p) for p in sorted(P75_WS.rglob("*")) if p.is_file()
    }
    groups["batch_a_inventory"] = {
        rkey(p): sha(p)
        for p in [ROOT / ".ai/learning/external_code/reconciliation/phase_1.76/inventory.json"]
    }
    groups["parser_adapter"] = {
        rkey(p): sha(p)
        for p in [
            ROOT / ".ai/tools/learning/gd_parse.py",
            ROOT / ".ai/tools/external_code/external_code_understanding.py",
        ]
    }
    groups["feature_layer"] = {
        rkey(p): sha(p)
        for p in [
            ROOT / ".ai/context/feature_index.json",
            ROOT / ".ai/context/feature_graph.json",
            ROOT / ".ai/tools/feature_registry/candidate_seed_policy.json",
        ]
    }
    return groups


def check_integrity():
    if not BASELINE.exists():
        return {"status": "NOT_VERIFIED", "reason": "baseline snapshot missing"}
    base = load(BASELINE)["groups"]
    now = current_hashes()
    changed, missing, added = [], [], []
    for group, files in base.items():
        for p, h in files.items():
            if p not in now.get(group, {}):
                missing.append(p)
            elif now[group][p] != h:
                changed.append(p)
        for p in now.get(group, {}):
            if p not in files:
                added.append(p)
    return {
        "status": "PASS" if not (changed or missing or added) else "FAIL",
        "changed": changed,
        "missing": missing,
        "added": added,
        "counts": {g: len(v) for g, v in now.items()},
    }


def build():
    manifest, inventory, formal, links, cands, policy, projections, graph = load_inputs()
    by_pair, by_analysis = linkage_index(links)
    featsyms = feature_symbols(projections)

    mapping = build_mapping(manifest, formal)
    symbols = symbol_rows(manifest, formal, by_analysis, featsyms)
    partial = build_partial(manifest, formal, by_analysis)
    tv = build_target_value(formal, links)
    cand_rows, policy_review = build_candidates(manifest, formal, links, cands, policy)
    linkage_cov = build_linkage_coverage(formal, links)
    integrity = check_integrity()

    audit = {
        "phase": "1.76-C",
        "read_only": True,
        "parser_build_identity": PARSER_B,
        "checks": {
            "mapping_records_total": len(mapping),
            "mapping_records_complete": sum(1 for m in mapping if m["identity_match_status"]),
            "mapping_exact_identity": sum(
                1 for m in mapping if m["identity_match_status"] == "EXACT_IDENTITY_MATCH"
            ),
            "formal_linkage_audited": len(links),
            "formal_linkage_mutated": 0,
            "partial_records_reviewed": len(partial),
            "target_value_reviewed": True,
            "target_value_existing_linkage_references": len(tv["existing_linkage_references"]),
            "candidates_reviewed": len(cand_rows),
            "candidates_total": len(cands),
            "seed_policy_reviewed": True,
            "symbols_inventoried": sum(1 for s in symbols if not s.get("record_summary")),
            "symbols_with_potential_impact": sum(
                1
                for s in symbols
                if not s.get("record_summary") and s["impact_classification"] != "NO_IMPACT"
            ),
            "review_queue_created": False,
            "batch_d_executed": False,
            "formal_data_mutation": integrity["status"],
        },
        "verdict": "PASS_WITH_LIMITATIONS",
        "verdict_reasons": [
            "3/34 records have PARTIAL syntax coverage; absence of parsed symbols is not absence of declarations.",
            "Formal Analysis/Linkage/Candidates remain on parser 1.71 and were not consumed by this review.",
            "Two source declarations in PARTIAL files are missing from the symbol table without being flagged.",
            "Seed policy has no explicit coverage-status or formal-analysis-only rule.",
        ],
        "batch_d_readiness": "READY_FOR_BATCH_D_WITH_RESTRICTIONS",
    }

    dump(
        "manifest.json",
        {
            "phase": "1.76-C",
            "task": "evidence impact review",
            "read_only": True,
            "parser_build_identity": PARSER_B,
            "batch_b_manifest_digest": sha(B_WS / "manifest.json"),
            "batch_a_inventory_digest": sha(
                ROOT / ".ai/learning/external_code/reconciliation/phase_1.76/inventory.json"
            ),
            "inputs": {
                "batch_b_workspace": rel(B_WS),
                "formal_analysis": rel(FORMAL),
                "formal_linkage": rel(LINKS),
                "candidates": rel(CANDS),
                "seed_policy": ".ai/tools/feature_registry/candidate_seed_policy.json",
                "feature_projections": [
                    f".ai/learning/feature_evidence/{f}.json" for f in AUDITED_FEATURES
                ],
            },
            "counts": audit["checks"],
            "artefacts": [
                "analysis_mapping.json",
                "symbol_impact.json",
                "partial_coverage_impact.json",
                "target_value_reclassification.json",
                "candidate_impact.json",
                "linkage_coverage.json",
                "audit_validation.json",
            ],
        },
    )
    dump("analysis_mapping.json", {"phase": "1.76-C", "records": mapping})
    dump("symbol_impact.json", {"phase": "1.76-C", "symbols": symbols})
    dump("partial_coverage_impact.json", {"phase": "1.76-C", "records": partial})
    dump("target_value_reclassification.json", tv)
    dump(
        "candidate_impact.json",
        {"phase": "1.76-C", "candidates": cand_rows, "seed_policy_review": policy_review},
    )
    dump("linkage_coverage.json", linkage_cov)
    dump("audit_validation.json", {"phase": "1.76-C", "audit": audit, "integrity": integrity})

    print(json.dumps(audit["checks"], indent=1, sort_keys=True))
    print("integrity:", integrity["status"])
    return 0


def validate():
    required = [
        "manifest.json",
        "analysis_mapping.json",
        "symbol_impact.json",
        "partial_coverage_impact.json",
        "target_value_reclassification.json",
        "candidate_impact.json",
        "linkage_coverage.json",
        "audit_validation.json",
    ]
    problems = []
    for name in required:
        if not (OUT / name).exists():
            problems.append(f"missing artefact {name}")
    if problems:
        print(json.dumps({"result": "FAIL", "problems": problems}, indent=1))
        return 1

    mapping = load(OUT / "analysis_mapping.json")["records"]
    symbols = load(OUT / "symbol_impact.json")["symbols"]
    partial = load(OUT / "partial_coverage_impact.json")["records"]
    tv = load(OUT / "target_value_reclassification.json")
    cn = load(OUT / "candidate_impact.json")
    audit = load(OUT / "audit_validation.json")["audit"]
    integrity = check_integrity()

    manifest = load(B_WS / "manifest.json")
    links = list(LINKS.glob("*.json"))
    checks = {
        "mapping_34_of_34": len(mapping) == 34
        and {m["batch_b_record_id"] for m in mapping}
        == {r["analysis_id"] for r in manifest["records"]},
        "all_mapped_have_status": all(m["identity_match_status"] for m in mapping),
        "all_mapped_not_consumed": all(m["consumed_by_formal_analysis"] is False for m in mapping),
        "formal_linkage_150_audited": audit["checks"]["formal_linkage_audited"] == 150
        and len(links) == 150,
        "partial_3_reviewed": len(partial) == 3,
        "partial_absence_rule_recorded": all(
            r["absence_is_not_evidence_of_absence"] for r in partial
        ),
        "target_value_reviewed": tv["analysis_id"] == "ext-7d7933a2343f52d0"
        and tv["is_removal"] is False,
        "target_value_no_duplicate": tv["is_two_symbols"] is False,
        "candidates_2_reviewed": len(cn["candidates"]) == 2,
        "seed_policy_reviewed": cn["seed_policy_review"]["policy_version"] == "phase-1.74-c/1",
        "every_impact_has_source": all(
            s.get("source_analysis_id") and s.get("source_path")
            for s in symbols
            if not s.get("record_summary")
        ),
        "every_potential_impact_has_reasoning": all(
            s.get("reasoning") and s.get("impact_classification")
            for s in symbols
            if not s.get("record_summary")
            and s.get("impact_classification") != "NO_IMPACT"
        ),
        "no_review_queue_created": not (
            ROOT / ".ai/learning/external_code/review_queue/phase_1.76"
        ).exists(),
        "no_batch_d_artefacts": not any((ROOT / ".ai/context").glob("PHASE_1_76_D_*")),
        "formal_data_unmutated": integrity["status"] == "PASS",
    }
    result = "PASS" if all(checks.values()) else "FAIL"
    print(json.dumps({"result": result, "checks": checks, "integrity": integrity}, indent=1))
    return 0 if result == "PASS" else 1


if __name__ == "__main__":
    mode = sys.argv[1] if len(sys.argv) > 1 else "build"
    sys.exit(build() if mode == "build" else validate())
