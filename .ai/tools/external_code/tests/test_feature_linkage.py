#!/usr/bin/env python3
"""Phase 1.73 Batch B tests: External Analysis <-> Feature Linkage.

Synthetic fixtures cover the classification, status-protection, freshness and
atomic-write rules. Real pilot data is only ever read; pilot builds are written
to a temporary directory inside the project.
"""

from __future__ import annotations

import contextlib
import io
import json
import os
import shutil
import sys
import unittest
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[4]
DOTAI = PROJECT_ROOT / ".ai"
sys.path[:0] = [str(DOTAI / "tools" / "external_code"),
                str(DOTAI / "tools" / "learning"),
                str(DOTAI / "tools" / "feature_registry")]

import feature_linkage as linkage  # noqa: E402

TMP_ROOT = Path(__file__).resolve().parent / ".tmp_linkage"

VERIFICATION_NOT_VERIFIED = {
    "feature_verification_status": "NOT_VERIFIED",
    "test_execution_status": "NOT_RUN",
    "runtime_verification_status": "NOT_VERIFIED",
    "behavior_verification_status": "NOT_VERIFIED",
    "basis": "NO_EXECUTION_EVIDENCE",
}


def write_json(path: Path, payload: dict) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n",
                    encoding="utf-8")
    return path


def read_json(path: Path) -> dict:
    return json.loads(Path(path).read_text(encoding="utf-8"))


def make_projection(feature_id: str, *, symbols=(), declared=(), capabilities=(),
                    status: str = "COMPLETE", verification=None,
                    analysis_references=None) -> dict:
    symbol_evidence = []
    for name, kind in symbols:
        symbol_evidence.append({
            "evidence_id": "symbol:%s:Features/%s/%s.gd:%s" % (feature_id, feature_id, name, kind),
            "evidence_type": "SYMBOL",
            "extraction_status": "EXTRACTED",
            "source_type": "GDSCRIPT_SOURCE",
            "source_file": "Features/%s/%s.gd" % (feature_id, feature_id),
            "source_symbol": name,
            "source_line": 12,
            "value": {"kind": kind, "name": name},
        })
    interface_evidence = [{
        "evidence_id": "interface:%s:%s" % (feature_id, name),
        "evidence_type": "INTERFACE",
        "extraction_status": "DECLARED",
        "source_type": "FEATURE_METADATA",
        "source_file": "Features/%s/feature.yaml" % feature_id,
        "source_symbol": "",
        "source_line": None,
        "value": {"kind": "method", "name": name, "signature": "%s() -> void" % name,
                  "source_check": "NOT_FOUND"},
    } for name in declared]
    capability_evidence = [{
        "evidence_id": "capability:%s:%s" % (feature_id, name),
        "evidence_type": "CAPABILITY",
        "extraction_status": "DECLARED",
        "source_type": "FEATURE_METADATA",
        "source_file": "Features/%s/feature.yaml" % feature_id,
        "source_symbol": "",
        "source_line": None,
        "value": {"capability": name, "scope": "FEATURE_TAG", "validation": "HUMAN_DECLARED"},
    } for name in capabilities]
    return {
        "schema": "feature_evidence_projection",
        "schema_version": 1,
        "feature_id": feature_id,
        "feature_name": feature_id,
        "feature_path": "Features/%s/feature.yaml" % feature_id,
        "projection_status": status,
        "verification_status": dict(verification or VERIFICATION_NOT_VERIFIED),
        "symbol_evidence": symbol_evidence,
        "interface_evidence": interface_evidence,
        "capability_evidence": capability_evidence,
        "analysis_references": list(analysis_references or []),
        "source_references": [{
            "source_type": "FEATURE_METADATA",
            "source_path": "Features/%s/feature.yaml" % feature_id,
            "source_digest": "",
            "source_status": "FOUND",
            "original_path": "Features/%s/feature.yaml" % feature_id,
            "normalized_path": "Features/%s/feature.yaml" % feature_id,
            "normalization_status": "RELATIVE",
        }],
    }


def make_analysis(analysis_id: str, *, status: str = "analysis_complete",
                  functions=(), signals=(), variables=(), class_name: str = "",
                  file_type: str = "gdscript", parse_status: str = "parsed",
                  snippet_id: str = "owner__repo__scripts__thing.gd",
                  source_path: str = "scripts/thing.gd",
                  limitations=("regex_parser_without_ast_or_type_inference",),
                  entry_points=()) -> dict:
    return {
        "schema": "external_code_analysis",
        "schema_version": 1,
        "analysis_id": analysis_id,
        "analysis_status": status,
        "snippet_id": snippet_id,
        "repo": "owner/repo",
        "source_path": source_path,
        "source_url": "",
        "source_digest": "",
        "commit_sha": "c" * 12,
        "commit_sha_full": "c" * 40,
        "file_type": file_type,
        "parse_status": parse_status,
        "provenance_status": "complete",
        "provenance": {"reason": "full commit SHA is recorded", "source_path": source_path},
        "limitations": list(limitations),
        "unresolved_questions": [],
        "entry_points": list(entry_points),
        "symbols": {
            "class_name": class_name,
            "extends": "",
            "functions": [{"name": name, "line": index + 3} for index, name in enumerate(functions)],
            "signals": [{"name": name} for name in signals],
            "variables": [{"name": name} for name in variables],
            "exports": [],
            "calls": [],
            "connections": [],
            "constants": [],
        },
    }


class Fixture:
    """One isolated synthetic project tree (F-drive temp inside the repo)."""

    def __init__(self, name: str) -> None:
        TMP_ROOT.mkdir(parents=True, exist_ok=True)
        self.root = TMP_ROOT / name
        if self.root.exists():
            shutil.rmtree(self.root)
        self.analysis_dir = self.root / "analysis"
        self.projection_dir = self.root / "projections"
        self.features_dir = self.root / "Features"
        self.out_dir = self.root / "feature_links"
        self.graph_path = self.root / "feature_graph.json"
        self.analysis_dir.mkdir(parents=True)
        self.projection_dir.mkdir(parents=True)
        self.features_dir.mkdir(parents=True)

    def analysis(self, record: dict) -> Path:
        return write_json(self.analysis_dir / ("%s.json" % record["analysis_id"]), record)

    def projection(self, record: dict) -> Path:
        return write_json(self.projection_dir / ("%s.json" % record["feature_id"]), record)

    def feature(self, feature_id: str, text: str = "") -> Path:
        path = self.features_dir / feature_id / "feature.yaml"
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(text or "id: %s\n" % feature_id, encoding="utf-8")
        return path

    def graph(self, edges) -> Path:
        return write_json(self.graph_path, {"nodes": [], "edges": list(edges)})

    def build(self, analysis_ids=None, feature_ids=("alpha",), **kwargs) -> dict:
        return linkage.build_linkages(
            analysis_ids, pilot=not analysis_ids,
            analysis_dir=self.analysis_dir, projection_dir=self.projection_dir,
            features_dir=self.features_dir, graph_path=self.graph_path,
            out_dir=self.out_dir, feature_ids=list(feature_ids), **kwargs)

    def records(self) -> list[dict]:
        return [read_json(path) for path in sorted(self.out_dir.glob("*.json"))]

    def record(self, analysis_id: str, feature_id: str) -> dict:
        return read_json(self.out_dir / ("%s__%s.json" % (analysis_id, feature_id)))


def temp_files(directory: Path) -> list[str]:
    return sorted(path.name for path in Path(directory).glob(".feature-link-*"))


class SchemaTests(unittest.TestCase):
    def setUp(self) -> None:
        self.fx = Fixture(self.id().split(".")[-1])
        self.fx.feature("alpha")
        self.fx.projection(make_projection("alpha", symbols=[("AlphaThing", "function")]))
        self.fx.analysis(make_analysis("ext-aaaa", functions=["AlphaThing"]))
        self.fx.graph([])
        self.fx.build(feature_ids=["alpha"])
        self.record = self.fx.record("ext-aaaa", "alpha")

    def test_schema_required_fields_present(self) -> None:
        for field in linkage.REQUIRED_RECORD_FIELDS:
            self.assertIn(field, self.record)
        self.assertEqual(self.record["schema"], linkage.SCHEMA)
        self.assertEqual(self.record["schema_version"], 1)

    def test_linkage_id_is_stable_and_not_positional(self) -> None:
        expected = linkage._linkage_id("ext-aaaa", "alpha")
        self.assertEqual(self.record["linkage_id"], expected)
        self.assertRegex(expected, r"^lnk-[0-9a-f]{16}$")
        self.assertEqual(linkage._linkage_id("ext-aaaa", "alpha"), expected)
        self.assertNotEqual(linkage._linkage_id("ext-aaaa", "beta"), expected)

    def test_evidence_items_are_complete(self) -> None:
        items = self.record["evidence_items"]
        self.assertTrue(items)
        for item in items:
            for field in linkage.REQUIRED_EVIDENCE_FIELDS:
                self.assertIn(field, item)
            self.assertTrue(item["source_path"])
            self.assertTrue(item["explanation"])

    def test_valid_record_passes_validation(self) -> None:
        linkage.validate_linkage(self.record)

    def test_invalid_classification_rejected(self) -> None:
        broken = json.loads(json.dumps(self.record))
        broken["linkage_classification"] = "SIMILAR"
        with self.assertRaises(linkage.LinkageValidationError):
            linkage.validate_linkage(broken)

    def test_outcome_must_match_classification(self) -> None:
        broken = json.loads(json.dumps(self.record))
        broken["linkage_outcome"] = "NOT_LINKED"
        with self.assertRaises(linkage.LinkageValidationError):
            linkage.validate_linkage(broken)

    def test_digest_format_enforced(self) -> None:
        broken = json.loads(json.dumps(self.record))
        broken["external_analysis"]["analysis_record_digest"] = "abc"
        with self.assertRaises(linkage.LinkageValidationError):
            linkage.validate_linkage(broken)

    def test_evidence_without_explanation_rejected(self) -> None:
        broken = json.loads(json.dumps(self.record))
        broken["evidence_items"][0]["explanation"] = "  "
        with self.assertRaises(linkage.LinkageValidationError):
            linkage.validate_linkage(broken)

    def test_evidence_without_source_path_rejected(self) -> None:
        broken = json.loads(json.dumps(self.record))
        broken["evidence_items"][0]["source_path"] = ""
        with self.assertRaises(linkage.LinkageValidationError):
            linkage.validate_linkage(broken)

    def test_forbidden_decision_keys_rejected(self) -> None:
        broken = json.loads(json.dumps(self.record))
        broken["similarity_score"] = 0.91
        with self.assertRaises(linkage.LinkageValidationError):
            linkage.validate_linkage(broken)
        broken = json.loads(json.dumps(self.record))
        broken["evidence_items"][0]["similarity_classification"] = "HIGH"
        with self.assertRaises(linkage.LinkageValidationError):
            linkage.validate_linkage(broken)

    def test_projection_status_must_be_known(self) -> None:
        broken = json.loads(json.dumps(self.record))
        broken["feature_projection"]["projection_status"] = "PROBABLY_COMPLETE"
        with self.assertRaises(linkage.LinkageValidationError):
            linkage.validate_linkage(broken)

    def test_limitations_must_match_sources(self) -> None:
        broken = json.loads(json.dumps(self.record))
        broken["evidence_limitations"]["analysis_status"] = "analysis_complete "
        with self.assertRaises(linkage.LinkageValidationError):
            linkage.validate_linkage(broken)

    def test_invalid_record_is_not_written(self) -> None:
        target = self.fx.out_dir / "ext-aaaa__alpha.json"
        before = target.read_text(encoding="utf-8")
        broken = json.loads(json.dumps(self.record))
        broken["linkage_classification"] = "BEST_MATCH"
        with self.assertRaises(linkage.LinkageValidationError):
            linkage.write_linkage(broken, self.fx.out_dir)
        self.assertEqual(target.read_text(encoding="utf-8"), before)
        self.assertEqual(temp_files(self.fx.out_dir), [])


class EvidenceTests(unittest.TestCase):
    def setUp(self) -> None:
        self.fx = Fixture(self.id().split(".")[-1])
        self.fx.feature("alpha")
        self.fx.feature("beta")
        self.fx.graph([])

    def test_exact_source_symbol_gives_direct_evidence(self) -> None:
        self.fx.projection(make_projection("alpha", symbols=[("apply_damage", "function")]))
        self.fx.analysis(make_analysis("ext-direct", functions=["apply_damage"]))
        self.fx.build(feature_ids=["alpha"])
        record = self.fx.record("ext-direct", "alpha")
        self.assertEqual(record["linkage_classification"], linkage.DIRECT_EVIDENCE)
        self.assertEqual(record["linkage_outcome"], "LINKED")
        item = record["evidence_items"][0]
        self.assertEqual(item["evidence_type"], "SYMBOL_EXACT_MATCH")
        self.assertEqual(item["evidence_status"], "EXTRACTED")
        self.assertEqual(item["symbol_name"], "apply_damage")
        self.assertEqual(item["line_reference"], 3)
        self.assertTrue(item["feature_evidence_id"])

    def test_duplicate_symbol_tables_do_not_duplicate_evidence(self) -> None:
        """A name listed as both a function and an entry point is one evidence item."""
        self.fx.projection(make_projection("alpha", symbols=[("apply_damage", "function")]))
        self.fx.analysis(make_analysis(
            "ext-duplicate-rows", functions=["apply_damage"],
            entry_points=[{"name": "apply_damage", "line": 3, "trigger": "external_entry"}]))
        self.fx.build(feature_ids=["alpha"])
        record = self.fx.record("ext-duplicate-rows", "alpha")
        self.assertEqual(record["linkage_classification"], linkage.DIRECT_EVIDENCE)
        matched = [item["matched_value"] for item in record["evidence_items"]]
        self.assertEqual(matched, ["apply_damage"])

    def test_name_similarity_alone_is_not_direct(self) -> None:
        self.fx.projection(make_projection("alpha", symbols=[("set_open", "function")]))
        self.fx.analysis(make_analysis("ext-similar", functions=["set_opened"]))
        self.fx.build(feature_ids=["alpha"])
        record = self.fx.record("ext-similar", "alpha")
        self.assertNotEqual(record["linkage_classification"], linkage.DIRECT_EVIDENCE)
        self.assertEqual(record["linkage_classification"], linkage.NO_SUPPORTED_LINK)

    def test_shared_token_is_only_potential_relevance(self) -> None:
        self.fx.projection(make_projection("alpha", symbols=[("player_health", "function")]))
        self.fx.analysis(make_analysis("ext-token", functions=["health_report"]))
        self.fx.build(feature_ids=["alpha"])
        record = self.fx.record("ext-token", "alpha")
        self.assertEqual(record["linkage_classification"], linkage.POTENTIAL_RELEVANCE)
        item = record["evidence_items"][0]
        self.assertEqual(item["evidence_type"], "SYMBOL_TOKEN_OVERLAP")
        self.assertEqual(item["matched_value"], "health")
        self.assertTrue(record["evidence_limitations"]["missing_evidence"])

    def test_potential_relevance_cannot_be_validated_as_direct(self) -> None:
        self.fx.projection(make_projection("alpha", symbols=[("health_report", "function")]))
        self.fx.analysis(make_analysis("ext-promote", functions=["health_report"]))
        self.fx.build(feature_ids=["alpha"])
        record = self.fx.record("ext-promote", "alpha")
        self.assertEqual(record["linkage_classification"], linkage.DIRECT_EVIDENCE)
        record["linkage_classification"] = linkage.POTENTIAL_RELEVANCE
        with self.assertRaises(linkage.LinkageValidationError):
            linkage.validate_linkage(record)

    def test_declared_interface_gives_declared_context(self) -> None:
        self.fx.projection(make_projection("alpha", declared=["describe_state"]))
        self.fx.analysis(make_analysis("ext-declared", functions=["describe_state"]))
        self.fx.build(feature_ids=["alpha"])
        record = self.fx.record("ext-declared", "alpha")
        self.assertEqual(record["linkage_classification"], linkage.DECLARED_CONTEXT)
        item = record["evidence_items"][0]
        self.assertEqual(item["evidence_type"], "DECLARED_SYMBOL_MATCH")
        self.assertEqual(item["evidence_status"], "DECLARED")

    def test_declared_context_cannot_carry_source_evidence(self) -> None:
        self.fx.projection(make_projection("alpha", declared=["describe_state"]))
        self.fx.analysis(make_analysis("ext-declared-2", functions=["describe_state"]))
        self.fx.build(feature_ids=["alpha"])
        record = self.fx.record("ext-declared-2", "alpha")
        record["evidence_items"][0]["evidence_type"] = "SYMBOL_EXACT_MATCH"
        record["evidence_items"][0]["evidence_status"] = "EXTRACTED"
        with self.assertRaises(linkage.LinkageValidationError):
            linkage.validate_linkage(record)

    def test_feature_metadata_snippet_declaration(self) -> None:
        self.fx.feature("alpha", "id: alpha\n#   snippet_id: owner__repo__scripts__thing.gd\n")
        self.fx.projection(make_projection("alpha", symbols=[("unrelated_symbol", "function")]))
        self.fx.analysis(make_analysis("ext-snippet", functions=["other_symbol"]))
        self.fx.build(feature_ids=["alpha"])
        record = self.fx.record("ext-snippet", "alpha")
        self.assertEqual(record["linkage_classification"], linkage.DECLARED_CONTEXT)
        self.assertEqual(record["evidence_items"][0]["evidence_type"], "DECLARED_SOURCE_SNIPPET")

    def test_indirect_evidence_keeps_intermediate_path(self) -> None:
        self.fx.projection(make_projection("alpha", symbols=[("apply_damage", "function")]))
        self.fx.projection(make_projection("beta", symbols=[("beta_only", "function")]))
        self.fx.analysis(make_analysis("ext-graph", functions=["apply_damage"]))
        self.fx.graph([{"from": "beta", "to": "alpha", "type": "works_with"}])
        self.fx.build(feature_ids=["alpha", "beta"])
        record = self.fx.record("ext-graph", "beta")
        self.assertEqual(record["linkage_classification"], linkage.INDIRECT_EVIDENCE)
        item = record["evidence_items"][0]
        self.assertEqual(item["evidence_type"], "GRAPH_RELATION")
        self.assertEqual(item["intermediate_path"], ["beta", "works_with", "alpha"])

    def test_indirect_requires_graph_evidence_in_validation(self) -> None:
        self.fx.projection(make_projection("alpha", symbols=[("apply_damage", "function")]))
        self.fx.projection(make_projection("beta", symbols=[("beta_only", "function")]))
        self.fx.analysis(make_analysis("ext-graph-2", functions=["apply_damage"]))
        self.fx.graph([{"from": "beta", "to": "alpha", "type": "works_with"}])
        self.fx.build(feature_ids=["alpha", "beta"])
        record = self.fx.record("ext-graph-2", "beta")
        record["evidence_items"] = [{
            "evidence_id": "ev-1", "evidence_type": "NONE", "evidence_status": "MISSING",
            "source_side": "BOTH", "source_path": "scripts/thing.gd", "symbol_name": "",
            "line_reference": None, "matched_value": "", "explanation": "nothing",
            "provenance_reference": "x"}]
        with self.assertRaises(linkage.LinkageValidationError):
            linkage.validate_linkage(record)

    def test_ambiguous_targets_are_recorded_not_guessed(self) -> None:
        self.fx.projection(make_projection("alpha", symbols=[("shared_symbol", "function")]))
        self.fx.projection(make_projection("beta", symbols=[("shared_symbol", "function")]))
        self.fx.analysis(make_analysis("ext-ambiguous", functions=["shared_symbol"]))
        self.fx.build(feature_ids=["alpha", "beta"])
        for feature_id in ("alpha", "beta"):
            record = self.fx.record("ext-ambiguous", feature_id)
            self.assertEqual(record["linkage_classification"], linkage.AMBIGUOUS)
            self.assertTrue(record["evidence_limitations"]["ambiguity_reasons"])

    def test_ambiguous_requires_reason(self) -> None:
        self.fx.projection(make_projection("alpha", symbols=[("shared_symbol", "function")]))
        self.fx.projection(make_projection("beta", symbols=[("shared_symbol", "function")]))
        self.fx.analysis(make_analysis("ext-ambiguous-2", functions=["shared_symbol"]))
        self.fx.build(feature_ids=["alpha", "beta"])
        record = self.fx.record("ext-ambiguous-2", "alpha")
        record["evidence_limitations"]["ambiguity_reasons"] = []
        with self.assertRaises(linkage.LinkageValidationError):
            linkage.validate_linkage(record)

    def test_no_supported_link_is_not_a_negative_similarity(self) -> None:
        self.fx.projection(make_projection("alpha", symbols=[("apply_damage", "function")]))
        self.fx.analysis(make_analysis("ext-none", functions=["total_other_thing"]))
        self.fx.build(feature_ids=["alpha"])
        record = self.fx.record("ext-none", "alpha")
        self.assertEqual(record["linkage_classification"], linkage.NO_SUPPORTED_LINK)
        self.assertEqual(record["linkage_outcome"], "NOT_LINKED")
        self.assertEqual(record["evidence_items"][0]["evidence_type"], "NONE")
        self.assertTrue(record["evidence_limitations"]["missing_evidence"])
        self.assertTrue(any("not a similarity" in text for text in record["limitations"]))

    def test_no_supported_link_items_are_pair_evaluation(self) -> None:
        self.fx.projection(make_projection("alpha", symbols=[("apply_damage", "function")]))
        self.fx.analysis(make_analysis("ext-role", functions=["total_other_thing"]))
        self.fx.build(feature_ids=["alpha"])
        record = self.fx.record("ext-role", "alpha")
        roles = {item["evidence_role"] for item in record["evidence_items"]}
        self.assertEqual(roles, {linkage.PAIR_EVALUATION_ROLE})
        self.assertEqual(record["linkage_outcome"], "NOT_LINKED")

    def test_pair_evaluation_marker_cannot_be_positive_evidence(self) -> None:
        self.fx.projection(make_projection("alpha", symbols=[("apply_damage", "function")]))
        self.fx.analysis(make_analysis("ext-role-2", functions=["apply_damage"]))
        self.fx.build(feature_ids=["alpha"])
        record = self.fx.record("ext-role-2", "alpha")
        self.assertEqual(record["linkage_classification"], linkage.DIRECT_EVIDENCE)
        self.assertTrue(all(item["evidence_role"] == linkage.LINKAGE_EVIDENCE_ROLE
                            for item in record["evidence_items"]))
        record["evidence_items"][0]["evidence_role"] = linkage.PAIR_EVALUATION_ROLE
        with self.assertRaises(linkage.LinkageValidationError):
            linkage.validate_linkage(record)

    def test_missing_role_marker_is_not_positive_evidence(self) -> None:
        self.fx.projection(make_projection("alpha", symbols=[("apply_damage", "function")]))
        self.fx.analysis(make_analysis("ext-role-3", functions=["total_other_thing"]))
        self.fx.build(feature_ids=["alpha"])
        record = self.fx.record("ext-role-3", "alpha")
        record["evidence_items"][0]["evidence_role"] = linkage.LINKAGE_EVIDENCE_ROLE
        with self.assertRaises(linkage.LinkageValidationError):
            linkage.validate_linkage(record)

    def test_records_without_role_marker_stay_compatible(self) -> None:
        """Batch B records predate evidence_role; dropping it must still validate."""
        self.fx.projection(make_projection("alpha", symbols=[("apply_damage", "function")]))
        self.fx.analysis(make_analysis("ext-role-4", functions=["total_other_thing"]))
        self.fx.build(feature_ids=["alpha"])
        record = self.fx.record("ext-role-4", "alpha")
        for item in record["evidence_items"]:
            item.pop("evidence_role", None)
        linkage.validate_linkage(record)
        self.assertEqual(linkage.evaluate_freshness(record)["status"], "FRESH")

    def test_no_supported_link_cannot_carry_clues(self) -> None:
        self.fx.projection(make_projection("alpha", symbols=[("apply_damage", "function")]))
        self.fx.analysis(make_analysis("ext-none-2", functions=["total_other_thing"]))
        self.fx.build(feature_ids=["alpha"])
        record = self.fx.record("ext-none-2", "alpha")
        record["evidence_items"][0]["evidence_type"] = "SYMBOL_TOKEN_OVERLAP"
        with self.assertRaises(linkage.LinkageValidationError):
            linkage.validate_linkage(record)

    def test_unlocatable_source_is_not_extracted(self) -> None:
        self.fx.projection(make_projection("alpha", symbols=[("apply_damage", "function")]))
        self.fx.analysis(make_analysis("ext-shader", status="unsupported_shader",
                                       file_type="gdshader", parse_status="unsupported_shader",
                                       functions=[], limitations=["shader parsing is outside"]))
        result = self.fx.build(feature_ids=["alpha"])
        self.assertEqual(result["built"], [])
        self.assertEqual(len(result["unevaluable"]), 1)
        self.assertIn("no distinctive parseable symbols", result["unevaluable"][0]["reason"])
        self.assertEqual(list(self.fx.out_dir.glob("*.json")), [])


class SeedQualificationTests(unittest.TestCase):
    """Batch B.2: which stored evidence may seed a downstream stage."""

    def setUp(self) -> None:
        self.fx = Fixture(self.id().split(".")[-1])
        self.fx.feature("alpha")
        self.fx.feature("beta")
        self.fx.graph([])

    def test_pair_evaluation_marker_is_never_seed_evidence(self) -> None:
        self.fx.projection(make_projection("alpha", symbols=[("apply_damage", "function")]))
        self.fx.analysis(make_analysis("ext-seed-none", functions=["total_other_thing"]))
        self.fx.build(feature_ids=["alpha"])
        record = self.fx.record("ext-seed-none", "alpha")
        self.assertEqual(record["evidence_items"][0]["evidence_role"],
                         linkage.PAIR_EVALUATION_ROLE)
        self.assertEqual(linkage.linkage_evidence_items(record), [])

    def test_linkage_evidence_is_available_for_qualification(self) -> None:
        self.fx.projection(make_projection("alpha", symbols=[("apply_damage", "function")]))
        self.fx.analysis(make_analysis("ext-seed-direct", functions=["apply_damage"]))
        self.fx.build(feature_ids=["alpha"])
        items = linkage.linkage_evidence_items(self.fx.record("ext-seed-direct", "alpha"))
        self.assertEqual([item["symbol_name"] for item in items], ["apply_damage"])
        self.assertTrue(all(item["evidence_role"] == linkage.LINKAGE_EVIDENCE_ROLE
                            for item in items))

    def test_legacy_record_without_role_uses_safe_default(self) -> None:
        """Batch B records have no evidence_role; the classification decides."""
        self.fx.projection(make_projection("alpha", symbols=[("apply_damage", "function")]))
        self.fx.analysis(make_analysis("ext-seed-legacy", functions=["apply_damage"]))
        self.fx.analysis(make_analysis("ext-seed-legacy-none", functions=["total_other_thing"]))
        self.fx.build(feature_ids=["alpha"])
        for analysis_id in ("ext-seed-legacy", "ext-seed-legacy-none"):
            record = self.fx.record(analysis_id, "alpha")
            for item in record["evidence_items"]:
                item.pop("evidence_role", None)
            linkage.validate_linkage(record)
        kept = linkage.linkage_evidence_items(self.fx.record("ext-seed-legacy", "alpha"))
        self.assertEqual([item["symbol_name"] for item in kept], ["apply_damage"])
        dropped = linkage.linkage_evidence_items(self.fx.record("ext-seed-legacy-none", "alpha"))
        self.assertEqual(dropped, [])

    def test_no_supported_link_is_never_positive_evidence(self) -> None:
        self.fx.projection(make_projection("alpha", symbols=[("apply_damage", "function")]))
        self.fx.analysis(make_analysis("ext-seed-absent", functions=["total_other_thing"]))
        self.fx.build(feature_ids=["alpha"])
        record = self.fx.record("ext-seed-absent", "alpha")
        self.assertEqual(record["linkage_outcome"], "NOT_LINKED")
        self.assertEqual(linkage.linkage_evidence_items(record), [])
        self.assertFalse(linkage.is_graph_derived_relation(record))

    def test_graph_derived_relation_is_not_direct_implementation(self) -> None:
        self.fx.projection(make_projection("alpha", symbols=[("apply_damage", "function")]))
        self.fx.projection(make_projection("beta", symbols=[("beta_only", "function")]))
        self.fx.analysis(make_analysis("ext-seed-graph", functions=["apply_damage"]))
        self.fx.graph([{"from": "beta", "to": "alpha", "type": "works_with"}])
        self.fx.build(feature_ids=["alpha", "beta"])
        derived = self.fx.record("ext-seed-graph", "beta")
        self.assertTrue(linkage.is_graph_derived_relation(derived))
        items = linkage.linkage_evidence_items(derived)
        self.assertEqual({item["evidence_type"] for item in items}, {"GRAPH_RELATION"})
        self.assertEqual({item["source_side"] for item in items}, {"FEATURE_GRAPH"})
        direct = self.fx.record("ext-seed-graph", "alpha")
        self.assertEqual(direct["linkage_classification"], linkage.DIRECT_EVIDENCE)
        self.assertFalse(linkage.is_graph_derived_relation(direct))


class StatusProtectionTests(unittest.TestCase):
    def setUp(self) -> None:
        self.fx = Fixture(self.id().split(".")[-1])
        self.fx.feature("alpha")
        self.fx.graph([])

    def test_partial_analysis_status_is_preserved(self) -> None:
        self.fx.projection(make_projection("alpha", symbols=[("apply_damage", "function")]))
        self.fx.analysis(make_analysis("ext-partial", status="analysis_partial",
                                       functions=["apply_damage"]))
        self.fx.build(feature_ids=["alpha"])
        record = self.fx.record("ext-partial", "alpha")
        self.assertEqual(record["external_analysis"]["analysis_status"], "analysis_partial")
        self.assertEqual(record["evidence_limitations"]["analysis_status"], "analysis_partial")
        self.assertTrue(any("not complete" in text for text in record["limitations"]))

    def test_unsupported_shader_status_is_preserved(self) -> None:
        self.fx.projection(make_projection("alpha", symbols=[("apply_damage", "function")]))
        analysis_path = self.fx.analysis(make_analysis(
            "ext-shader-status", status="unsupported_shader", file_type="gdshader",
            parse_status="unsupported_shader"))
        before = analysis_path.read_text(encoding="utf-8")
        self.fx.build(feature_ids=["alpha"])
        self.assertEqual(analysis_path.read_text(encoding="utf-8"), before)
        self.assertIn("unsupported_shader", before)

    def test_partial_projection_status_is_not_overwritten(self) -> None:
        self.fx.projection(make_projection("alpha", status="PARTIAL",
                                           symbols=[("apply_damage", "function")]))
        self.fx.analysis(make_analysis("ext-proj-partial", functions=["apply_damage"]))
        self.fx.build(feature_ids=["alpha"])
        record = self.fx.record("ext-proj-partial", "alpha")
        self.assertEqual(record["feature_projection"]["projection_status"], "PARTIAL")
        self.assertEqual(record["linkage_classification"], linkage.DIRECT_EVIDENCE)

    def test_complete_projection_does_not_verify_feature(self) -> None:
        self.fx.projection(make_projection("alpha", status="COMPLETE",
                                           symbols=[("apply_damage", "function")]))
        self.fx.analysis(make_analysis("ext-verified", functions=["apply_damage"]))
        self.fx.build(feature_ids=["alpha"])
        record = self.fx.record("ext-verified", "alpha")
        verification = record["feature_projection"]["verification_status"]
        self.assertEqual(verification["feature_verification_status"], "NOT_VERIFIED")
        self.assertEqual(verification["test_execution_status"], "NOT_RUN")
        self.assertEqual(record["evidence_limitations"]["verification_status"], verification)

    def test_verification_status_upgrade_is_rejected(self) -> None:
        self.fx.projection(make_projection("alpha", symbols=[("apply_damage", "function")]))
        self.fx.analysis(make_analysis("ext-upgrade", functions=["apply_damage"]))
        self.fx.build(feature_ids=["alpha"])
        record = self.fx.record("ext-upgrade", "alpha")
        record["feature_projection"]["verification_status"]["feature_verification_status"] = "VERIFIED"
        with self.assertRaises(linkage.LinkageValidationError):
            linkage.validate_linkage(record)

    def test_not_applicable_evidence_is_not_verified(self) -> None:
        projection = make_projection("alpha", symbols=[("apply_damage", "function")])
        projection["symbol_evidence"][0]["applicability"] = "NOT_APPLICABLE"
        self.fx.projection(projection)
        self.fx.analysis(make_analysis("ext-na", functions=["apply_damage"]))
        self.fx.build(feature_ids=["alpha"])
        record = self.fx.record("ext-na", "alpha")
        self.assertEqual(record["feature_projection"]["verification_status"]
                         ["feature_verification_status"], "NOT_VERIFIED")

    def test_source_entry_ambiguous_reference_is_preserved(self) -> None:
        self.fx.projection(make_projection(
            "alpha", symbols=[("apply_damage", "function")],
            analysis_references=[{
                "analysis_record_path": ".ai/learning/source_analysis/alpha/x.json",
                "analysis_status": "SOURCE_ENTRY_AMBIGUOUS",
                "analysis_digest": "d" * 64,
                "analyzed_source_files": ["Features/alpha/alpha.gd"],
                "limitations": ["two definitions"],
            }]))
        self.fx.analysis(make_analysis("ext-ambig-ref", functions=["apply_damage"]))
        self.fx.build(feature_ids=["alpha"])
        record = self.fx.record("ext-ambig-ref", "alpha")
        statuses = [ref["analysis_status"] for ref in record["feature_projection"]
                    ["feature_analysis_references"]]
        self.assertEqual(statuses, ["SOURCE_ENTRY_AMBIGUOUS"])
        self.assertEqual(record["feature_projection"]["verification_status"]
                         ["feature_verification_status"], "NOT_VERIFIED")


class FreshnessTests(unittest.TestCase):
    def setUp(self) -> None:
        self.fx = Fixture(self.id().split(".")[-1])
        self.fx.feature("alpha")
        self.fx.graph([])
        self.projection_path = self.fx.projection(
            make_projection("alpha", symbols=[("apply_damage", "function")]))
        self.analysis_path = self.fx.analysis(
            make_analysis("ext-fresh", functions=["apply_damage"]))
        self.fx.build(feature_ids=["alpha"])
        self.record = self.fx.record("ext-fresh", "alpha")

    def test_fresh_record(self) -> None:
        result = linkage.evaluate_freshness(self.record)
        self.assertEqual(result["status"], "FRESH")
        self.assertEqual(result["reasons"], [])

    def test_analysis_digest_change_is_stale(self) -> None:
        payload = read_json(self.analysis_path)
        payload["limitations"].append("changed after build")
        write_json(self.analysis_path, payload)
        result = linkage.evaluate_freshness(self.record)
        self.assertEqual(result["status"], "STALE")
        self.assertTrue(any("SOURCE_DIGEST_CHANGED" in reason for reason in result["reasons"]))
        self.assertTrue(result["changed_sources"])

    def test_projection_digest_change_is_stale(self) -> None:
        payload = read_json(self.projection_path)
        payload["projection_status"] = "PARTIAL"
        write_json(self.projection_path, payload)
        result = linkage.evaluate_freshness(self.record)
        self.assertEqual(result["status"], "STALE")
        self.assertTrue(any("feature_projection" in item for item in result["changed_sources"]))

    def test_missing_source(self) -> None:
        self.analysis_path.unlink()
        result = linkage.evaluate_freshness(self.record)
        self.assertEqual(result["status"], "MISSING_SOURCE")
        self.assertTrue(any("ANALYSIS_RECORD_MISSING" in reason for reason in result["reasons"]))

    def test_generator_version_change_is_stale(self) -> None:
        result = linkage.evaluate_freshness(self.record, generator_version="phase-1.73-b/2")
        self.assertEqual(result["status"], "STALE")
        self.assertTrue(any("GENERATOR_VERSION_CHANGED" in reason for reason in result["reasons"]))

    def test_schema_version_change_is_invalid(self) -> None:
        broken = json.loads(json.dumps(self.record))
        broken["schema_version"] = 2
        result = linkage.evaluate_freshness(broken)
        self.assertEqual(result["status"], "INVALID")

    def test_check_reports_coverage(self) -> None:
        result = linkage.check_linkages(
            ["ext-fresh"], pilot=False, analysis_dir=self.fx.analysis_dir,
            projection_dir=self.fx.projection_dir, features_dir=self.fx.features_dir,
            graph_path=self.fx.graph_path, out_dir=self.fx.out_dir,
            feature_ids=["alpha"])
        self.assertEqual(result["status_counts"]["FRESH"], 1)
        self.assertEqual(result["coverage"]["missing_records"], [])
        self.assertEqual(result["coverage"]["expected_records"], 1)


class AtomicWriteTests(unittest.TestCase):
    def setUp(self) -> None:
        self.fx = Fixture(self.id().split(".")[-1])
        self.fx.feature("alpha")
        self.fx.graph([])
        self.projection_path = self.fx.projection(
            make_projection("alpha", symbols=[("apply_damage", "function")]))
        self.analysis_path = self.fx.analysis(
            make_analysis("ext-atomic", functions=["apply_damage"]))
        self.fx.build(feature_ids=["alpha"])
        self.target = self.fx.out_dir / "ext-atomic__alpha.json"
        self.before = self.target.read_text(encoding="utf-8")
        self.record = read_json(self.target)

    def test_successful_write_leaves_no_temp_files(self) -> None:
        linkage.write_linkage(self.record, self.fx.out_dir)
        self.assertEqual(temp_files(self.fx.out_dir), [])

    def test_build_failure_protects_existing_record(self) -> None:
        def explode() -> None:
            raise linkage.LinkageError("build exploded")

        original = linkage.build_linkage_record
        linkage.build_linkage_record = lambda *args, **kwargs: explode()
        try:
            result = self.fx.build(feature_ids=["alpha"])
        finally:
            linkage.build_linkage_record = original
        self.assertEqual(result["built"], [])
        self.assertEqual(len(result["failed"]), 1)
        self.assertIn("build exploded", result["failed"][0]["error"])
        self.assertEqual(self.target.read_text(encoding="utf-8"), self.before)
        self.assertEqual(temp_files(self.fx.out_dir), [])

    def test_json_serialization_failure_protects_existing_record(self) -> None:
        broken = json.loads(json.dumps(self.record))
        broken["extra_unserializable"] = {1, 2, 3}
        with self.assertRaises(TypeError):
            linkage.write_linkage(broken, self.fx.out_dir)
        self.assertEqual(self.target.read_text(encoding="utf-8"), self.before)
        self.assertEqual(temp_files(self.fx.out_dir), [])

    def test_schema_failure_protects_existing_record(self) -> None:
        broken = json.loads(json.dumps(self.record))
        broken["evidence_items"] = []
        with self.assertRaises(linkage.LinkageValidationError):
            linkage.write_linkage(broken, self.fx.out_dir)
        self.assertEqual(self.target.read_text(encoding="utf-8"), self.before)
        self.assertEqual(temp_files(self.fx.out_dir), [])

    def test_digest_failure_protects_existing_record(self) -> None:
        payload = read_json(self.analysis_path)
        payload["limitations"].append("edited after linkage")
        write_json(self.analysis_path, payload)
        with self.assertRaises(linkage.LinkageValidationError):
            linkage.write_linkage(json.loads(self.before), self.fx.out_dir)
        self.assertEqual(self.target.read_text(encoding="utf-8"), self.before)
        self.assertEqual(temp_files(self.fx.out_dir), [])

    def test_replace_failure_protects_existing_record(self) -> None:
        def failing_replace(source, target) -> None:
            raise OSError("replace refused")

        with self.assertRaises(OSError):
            linkage.write_linkage(self.record, self.fx.out_dir, replace_func=failing_replace)
        self.assertEqual(self.target.read_text(encoding="utf-8"), self.before)
        self.assertEqual(temp_files(self.fx.out_dir), [])

    def test_batch_failure_identifies_failed_pair(self) -> None:
        self.fx.projection(make_projection("beta", symbols=[("beta_symbol", "function")]))
        calls = {"count": 0}
        real_replace = os.replace

        def flaky_replace(source, target) -> None:
            calls["count"] += 1
            if calls["count"] == 2:
                raise OSError("second pair failed")
            real_replace(source, target)

        result = self.fx.build(feature_ids=["alpha", "beta"], replace_func=flaky_replace)
        self.assertEqual(result["summary"]["built"], 1)
        self.assertEqual(result["summary"]["failed"], 1)
        self.assertEqual(len(result["failed"]), 1)
        self.assertTrue(result["failed"][0]["feature_id"] in ("alpha", "beta"))
        self.assertEqual(temp_files(self.fx.out_dir), [])


class PilotTests(unittest.TestCase):
    """Real 14 Analysis Records x 5 projections, read-only, temp output."""

    @classmethod
    def setUpClass(cls) -> None:
        cls.analysis_digests = {
            path.name: linkage._sha256_file(path)
            for path in sorted(linkage.ANALYSIS_DIR.glob("*.json"))
        }
        cls.projection_digests = {
            path.name: linkage._sha256_file(path)
            for path in sorted(linkage.PROJECTION_DIR.glob("*.json"))
        }
        TMP_ROOT.mkdir(parents=True, exist_ok=True)
        cls.out_dir = TMP_ROOT / "pilot"
        if cls.out_dir.exists():
            shutil.rmtree(cls.out_dir)
        cls.analyses = linkage.load_external_analyses()
        cls.projections = linkage.load_feature_projections()
        cls.result = linkage.build_linkages(pilot=True, out_dir=cls.out_dir)

    @classmethod
    def tearDownClass(cls) -> None:
        if TMP_ROOT.exists():
            shutil.rmtree(TMP_ROOT, ignore_errors=True)

    def test_real_analysis_count_and_status(self) -> None:
        # Enriched in Batch B.1: 14 original + 20 targeted records.
        self.assertEqual(len(self.analyses), 34)
        statuses = [item["record"]["analysis_status"] for item in self.analyses.values()]
        self.assertEqual(statuses.count("analysis_complete"), 11)
        self.assertEqual(statuses.count("analysis_partial"), 22)
        self.assertEqual(statuses.count("unsupported_shader"), 1)
        index = linkage.load_analysis_index()
        self.assertEqual(len(index), len(self.analyses))

    def test_real_projection_count(self) -> None:
        self.assertEqual(sorted(self.projections), sorted(linkage.PILOT_FEATURES))

    def test_pair_accounting(self) -> None:
        summary = self.result["summary"]
        expected_pairs = len(self.analyses) * len(self.projections)
        self.assertEqual(summary["total_pairs"], expected_pairs)
        self.assertEqual(summary["evaluated_pairs"], 150)
        self.assertEqual(summary["unevaluable_pairs"], expected_pairs - 150)
        self.assertEqual(summary["built"], summary["evaluated_pairs"])
        self.assertEqual(sum(summary["classifications"].values()), summary["evaluated_pairs"])
        self.assertEqual(len(list(self.out_dir.glob("*.json"))), summary["built"])

    def test_every_pilot_record_validates_and_is_fresh(self) -> None:
        records = linkage.load_linkage_records(self.out_dir)
        self.assertEqual(len(records), self.result["summary"]["built"])
        for record in records:
            linkage.validate_linkage(record)
            self.assertEqual(linkage.evaluate_freshness(record)["status"], "FRESH")

    def test_pilot_records_have_no_decision_keys(self) -> None:
        for record in linkage.load_linkage_records(self.out_dir):
            self.assertEqual(linkage._forbidden_key_paths(record), [])
            self.assertIn(record["linkage_classification"], linkage.CLASSIFICATIONS)

    def test_direct_links_are_evidence_backed(self) -> None:
        for record in linkage.load_linkage_records(self.out_dir):
            if record["linkage_classification"] != linkage.DIRECT_EVIDENCE:
                continue
            items = [item for item in record["evidence_items"]
                     if item["evidence_type"] == "SYMBOL_EXACT_MATCH"]
            self.assertTrue(items)
            for item in items:
                self.assertEqual(item["evidence_status"], "EXTRACTED")
                self.assertTrue(item["feature_evidence_id"])

    def test_pilot_verification_is_never_verified(self) -> None:
        for record in linkage.load_linkage_records(self.out_dir):
            verification = record["feature_projection"]["verification_status"]
            self.assertIn(verification["feature_verification_status"], {"NOT_VERIFIED"})
            self.assertEqual(verification["runtime_verification_status"], "NOT_VERIFIED")
            self.assertEqual(verification["test_execution_status"], "NOT_RUN")

    def test_inputs_are_untouched(self) -> None:
        self.assertEqual(self.analysis_digests, {
            path.name: linkage._sha256_file(path)
            for path in sorted(linkage.ANALYSIS_DIR.glob("*.json"))})
        self.assertEqual(self.projection_digests, {
            path.name: linkage._sha256_file(path)
            for path in sorted(linkage.PROJECTION_DIR.glob("*.json"))})

    def test_pilot_check_reports_fresh(self) -> None:
        result = linkage.check_linkages(pilot=True, out_dir=self.out_dir)
        self.assertEqual(result["status_counts"]["FRESH"], self.result["summary"]["built"])
        self.assertEqual(result["coverage"]["missing_records"], [])
        self.assertEqual(result["coverage"]["unexpected_records"], [])

    def test_analysis_index_matches_records(self) -> None:
        index = linkage.load_analysis_index()
        self.assertTrue(index)
        cross = linkage.cross_check_index(self.analyses, index)
        self.assertEqual(cross["status"], "MATCHED")
        self.assertEqual(cross["missing_in_index"], [])
        self.assertEqual(cross["missing_records"], [])

    def test_cli_build_and_check(self) -> None:
        buffer = io.StringIO()
        with contextlib.redirect_stdout(buffer):
            code = linkage.main(["build", "--analysis",
                                 sorted(self.analyses)[0], "--out", str(self.out_dir)])
        self.assertEqual(code, 0)
        self.assertIn("NO_SUPPORTED_LINK", buffer.getvalue())
        buffer = io.StringIO()
        with contextlib.redirect_stdout(buffer):
            code = linkage.main(["check", "--pilot", "--out", str(self.out_dir)])
        self.assertEqual(code, 0)
        self.assertIn("FRESH=%d" % self.result["summary"]["built"], buffer.getvalue())

    def test_cli_unknown_analysis_fails(self) -> None:
        buffer = io.StringIO()
        errors = io.StringIO()
        with contextlib.redirect_stdout(buffer), contextlib.redirect_stderr(errors):
            code = linkage.main(["build", "--analysis", "ext-does-not-exist",
                                 "--out", str(self.out_dir)])
        self.assertEqual(code, 1)
        self.assertIn("unknown analysis_id", errors.getvalue())


def tearDownModule() -> None:
    """Remove every fixture tree so the project keeps no test residue."""
    if TMP_ROOT.exists():
        shutil.rmtree(TMP_ROOT, ignore_errors=True)


if __name__ == "__main__":
    unittest.main(verbosity=2)
