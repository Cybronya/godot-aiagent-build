#!/usr/bin/env python3
"""Phase 1.74 Batch C tests: restricted candidate workspace foundation.

Two kinds of tests live here on purpose:

* synthetic fixture tests for the schema and the eligibility guard, where the
  inputs are built to exercise one rule at a time;
* real-store tests that build drafts from the actual 150 linkage records into a
  temporary directory, because the whole point of the stage is that the four
  reviewed records behave exactly as Batch B.2 says.
"""

from __future__ import annotations

import copy
import json
import shutil
import sys
import tempfile
import unittest
from pathlib import Path

TESTS_DIR = Path(__file__).resolve().parent
REGISTRY_DIR = TESTS_DIR.parent
AI_ROOT = REGISTRY_DIR.parents[1]
PROJECT_ROOT = REGISTRY_DIR.parents[2]

for path in (REGISTRY_DIR, AI_ROOT / "tools" / "external_code"):
    if str(path) not in sys.path:
        sys.path.insert(0, str(path))

import candidate_eligibility as eligibility  # noqa: E402
import candidate_workspace as workspace  # noqa: E402
import feature_linkage as linkage  # noqa: E402

TMP_ROOT = TESTS_DIR / ".tmp_candidate_workspace"

HEALTH_MAKE_PRO = "lnk-d2d95d8162be1592"
HEALTH_NEZVERS = "lnk-6fff3ce176bd5813"
BLACKBOARD_BEEHAVE = "lnk-7084dc8999c2182b"
ATTACK_GRAPH = "lnk-a099657ab3c9930c"


def tearDownModule() -> None:
    if TMP_ROOT.exists():
        shutil.rmtree(TMP_ROOT, ignore_errors=True)


def fixture_dir(name: str) -> Path:
    path = TMP_ROOT / name
    if path.exists():
        shutil.rmtree(path, ignore_errors=True)
    path.mkdir(parents=True)
    return path


# --- synthetic inputs ----------------------------------------------------------

def make_policy(**overrides) -> dict:
    policy = {
        "schema": "candidate_seed_policy",
        "schema_version": 1,
        "policy_version": "test-policy/1",
        "review_source": "synthetic",
        "feature_scope": ["alpha"],
        "context_features": ["gamma"],
        "excluded_features": {},
        "seeds": [{
            "linkage_id": "lnk-alpha",
            "feature_id": "alpha",
            "qualification_status": "QUALIFIED_DIRECT",
            "independence": "INDEPENDENT",
            "architecture": "Node + signals",
            "qualification_reason": "synthetic review",
            "limitations": [],
        }],
        "context_relations": [],
    }
    policy.update(overrides)
    return policy


def make_record(*, linkage_id="lnk-alpha", feature_id="alpha",
                classification="DIRECT_EVIDENCE",
                role="LINKAGE_EVIDENCE", evidence_type="SYMBOL_EXACT_MATCH",
                symbol="apply_damage", line=5,
                provenance="complete", digest_status="MATCHED",
                repository="owner/repo", commit="a" * 40, source_digest="b" * 64,
                url=None, source_path="scripts/thing.gd",
                references_path=None, commit_file=None,
                intermediate_path=None) -> dict:
    commit_url = url or ("https://github.com/%s/blob/%s/%s" % (repository, commit,
                                                               source_path))
    item = {
        "evidence_id": "ev:01",
        "evidence_role": role,
        "evidence_type": evidence_type,
        "evidence_status": "EXTRACTED" if evidence_type == "SYMBOL_EXACT_MATCH"
        else "DECLARED",
        "source_side": "FEATURE_GRAPH" if evidence_type == "GRAPH_RELATION" else "BOTH",
        "source_path": references_path or (".ai/skills/references/%s" % symbol),
        "symbol_name": symbol,
        "line_reference": line,
        "matched_value": symbol,
        "explanation": "synthetic",
        "provenance_reference": "analysis#x",
        "feature_evidence_id": "symbol:%s:x" % feature_id,
        "feature_source_path": "Features/%s/%s.gd" % (feature_id, feature_id),
        "feature_source_line": 3,
    }
    if intermediate_path:
        item["intermediate_path"] = intermediate_path
    return {
        "schema": "external_analysis_feature_linkage",
        "schema_version": 1,
        "linkage_id": linkage_id,
        "analysis_id": "ext-synthetic",
        "feature_id": feature_id,
        "feature_name": feature_id,
        "linkage_classification": classification,
        "linkage_outcome": "LINKED",
        "evidence_items": [item],
        "evidence_limitations": {
            "analysis_status": "analysis_complete",
            "projection_status": "COMPLETE",
            "verification_status": {"basis": "NO_EXECUTION_EVIDENCE"},
            "parser_limitations": [],
            "missing_evidence": [],
            "ambiguity_reasons": [],
            "unsupported_content": [],
            "provenance_limitations": [],
        },
        "external_analysis": {
            "source_repository": repository,
            "source_commit": commit,
            "source_digest": source_digest,
            "source_url": commit_url,
            "source_path": source_path,
            "provenance_status": provenance,
            "analysis_status": "analysis_complete",
            "analysis_record_digest": "c" * 64,
            "analysis_record_path": ".ai/learning/external_code/analysis/ext-x.json",
            "parse_status": "parsed",
            "file_type": "gdscript",
        },
        "feature_projection": {
            "feature_projection_digest": "d" * 64,
            "feature_projection_path": ".ai/learning/feature_evidence/%s.json" % feature_id,
            "projection_status": "COMPLETE",
            "verification_status": {"basis": "NO_EXECUTION_EVIDENCE"},
        },
        "source_verification": {
            "analysis_record": {"digest": "c" * 64, "digest_status": digest_status,
                                "path": ".ai/learning/external_code/analysis/ext-x.json"},
            "external_source_file": {
                "digest_status": digest_status,
                "path": commit_file or ".ai/skills/sources/thing.gd",
                "recorded_digest": source_digest},
            "feature_projection": {"digest": "d" * 64, "digest_status": "MATCHED",
                                   "path": ".ai/learning/feature_evidence/x.json"},
            "feature_sources": [],
        },
        "generator": {"name": "feature_linkage", "version": linkage.GENERATOR_VERSION},
        "limitations": ["synthetic"],
    }


def write_pair(directory: Path, *, header: int = 3) -> tuple[str, str]:
    """Create a references copy (with header) and its commit copy."""
    source = directory / "thing.gd"
    source.write_text("func apply_damage(x):\n\tpass\n\nfunc other():\n\tpass\n",
                      encoding="utf-8")
    reference = directory / "thing_ref.gd"
    header_text = "".join("# header %d\n" % index for index in range(header))
    reference.write_text(header_text + source.read_text(encoding="utf-8"),
                         encoding="utf-8")
    return str(reference), str(source)


# --- policy --------------------------------------------------------------------

class PolicyTests(unittest.TestCase):

    def test_real_policy_loads_and_scopes_two_features(self) -> None:
        policy = eligibility.load_policy()
        self.assertEqual(policy["feature_scope"], ["health", "blackboard"])
        self.assertEqual(sorted(policy["excluded_features"]),
                         ["health_bar", "openable_door"])
        self.assertEqual(len(policy["seeds"]), 3)
        self.assertEqual(len(policy["context_relations"]), 1)

    def test_policy_with_wrong_schema_is_rejected(self) -> None:
        directory = fixture_dir(self.id().split(".")[-1])
        path = directory / "policy.json"
        path.write_text(json.dumps(make_policy(schema="other")), encoding="utf-8")
        with self.assertRaises(eligibility.EligibilityError):
            eligibility.load_policy(path)

    def test_policy_with_non_seed_qualification_is_rejected(self) -> None:
        directory = fixture_dir(self.id().split(".")[-1])
        policy = make_policy()
        policy["seeds"][0]["qualification_status"] = "POTENTIAL_RELEVANCE"
        path = directory / "policy.json"
        path.write_text(json.dumps(policy), encoding="utf-8")
        with self.assertRaises(eligibility.EligibilityError):
            eligibility.load_policy(path)

    def test_policy_with_duplicate_seed_is_rejected(self) -> None:
        directory = fixture_dir(self.id().split(".")[-1])
        policy = make_policy()
        policy["seeds"].append(dict(policy["seeds"][0]))
        path = directory / "policy.json"
        path.write_text(json.dumps(policy), encoding="utf-8")
        with self.assertRaises(eligibility.EligibilityError):
            eligibility.load_policy(path)


# --- eligibility guard ---------------------------------------------------------

class EligibilityGuardTests(unittest.TestCase):

    def setUp(self) -> None:
        self.policy = make_policy()

    def evaluate(self, record: dict, policy: dict | None = None) -> dict:
        return eligibility.evaluate_seed_eligibility(record, policy or self.policy,
                                                     location=False)

    def test_qualified_direct_is_eligible(self) -> None:
        result = self.evaluate(make_record())
        self.assertTrue(result["eligible"])
        self.assertEqual(result["seed_eligibility"], "QUALIFIED_DIRECT")
        self.assertEqual(result["evidence_kind"], eligibility.EXTERNAL_DIRECT)
        self.assertEqual(result["codes"], [])

    def test_qualified_direct_with_limitations_is_eligible(self) -> None:
        policy = make_policy()
        policy["seeds"][0]["qualification_status"] = "QUALIFIED_DIRECT_WITH_LIMITATIONS"
        result = self.evaluate(make_record(), policy)
        self.assertTrue(result["eligible"])
        self.assertEqual(result["seed_eligibility"],
                         "QUALIFIED_DIRECT_WITH_LIMITATIONS")

    def test_pair_evaluation_item_is_rejected(self) -> None:
        record = make_record(classification="NO_SUPPORTED_LINK", role="PAIR_EVALUATION",
                             evidence_type="NONE")
        result = self.evaluate(record)
        self.assertFalse(result["eligible"])
        self.assertIn("CLASSIFICATION_NOT_ELIGIBLE", result["codes"])

    def test_no_supported_link_is_rejected(self) -> None:
        record = make_record(classification="NO_SUPPORTED_LINK", evidence_type="NONE",
                             role="PAIR_EVALUATION")
        self.assertFalse(self.evaluate(record)["eligible"])

    def test_potential_relevance_is_rejected(self) -> None:
        record = make_record(classification="POTENTIAL_RELEVANCE",
                             evidence_type="SYMBOL_TOKEN_OVERLAP")
        result = self.evaluate(record)
        self.assertFalse(result["eligible"])
        self.assertIn("CLASSIFICATION_NOT_ELIGIBLE", result["codes"])

    def test_ambiguous_is_rejected(self) -> None:
        record = make_record(classification="AMBIGUOUS")
        self.assertFalse(self.evaluate(record)["eligible"])

    def test_unreviewed_direct_is_rejected(self) -> None:
        record = make_record(linkage_id="lnk-unreviewed")
        result = self.evaluate(record)
        self.assertFalse(result["eligible"])
        self.assertIn("QUALIFICATION_NOT_REVIEWED", result["codes"])
        self.assertTrue(result["recoverable"])

    def test_incomplete_provenance_is_rejected(self) -> None:
        result = self.evaluate(make_record(provenance="incomplete"))
        self.assertFalse(result["eligible"])
        self.assertIn("PROVENANCE_INCOMPLETE", result["codes"])

    def test_mismatched_digest_is_rejected(self) -> None:
        result = self.evaluate(make_record(digest_status="MISMATCH"))
        self.assertFalse(result["eligible"])
        self.assertIn("SOURCE_DIGEST_UNVERIFIED", result["codes"])

    def test_missing_source_identity_is_rejected(self) -> None:
        result = self.evaluate(make_record(commit="abc123", source_digest="short"))
        self.assertFalse(result["eligible"])
        self.assertIn("SOURCE_IDENTITY_MISSING", result["codes"])
        fields = [entry["field"] for entry in result["checks"]
                  if entry["status"] == "FAIL"]
        self.assertIn("external_analysis.*", fields)

    def test_out_of_scope_feature_is_rejected(self) -> None:
        policy = make_policy(feature_scope=["alpha"])
        record = make_record(feature_id="beta")
        policy["seeds"][0]["feature_id"] = "beta"
        result = self.evaluate(record, policy)
        self.assertFalse(result["eligible"])
        self.assertIn("FEATURE_OUT_OF_SCOPE", result["codes"])

    def test_excluded_feature_is_rejected(self) -> None:
        policy = make_policy(excluded_features={"beta": {"reason_code": "NO_SEED"}})
        record = make_record(feature_id="beta")
        policy["seeds"][0]["feature_id"] = "beta"
        result = self.evaluate(record, policy)
        self.assertFalse(result["eligible"])
        self.assertIn("FEATURE_EXCLUDED", result["codes"])

    def test_graph_derived_cannot_be_a_seed(self) -> None:
        record = make_record(classification="INDIRECT_EVIDENCE",
                             evidence_type="GRAPH_RELATION", symbol="health", line=None,
                             intermediate_path=["alpha", "works_with", "health"])
        result = self.evaluate(record)
        self.assertFalse(result["eligible"])
        self.assertIn("GRAPH_DERIVED_NOT_SEED", result["codes"])

    def test_unknown_independence_never_becomes_independent(self) -> None:
        policy = make_policy()
        policy["seeds"][0]["independence"] = "UNKNOWN"
        result = self.evaluate(make_record(), policy)
        self.assertFalse(result["eligible"])
        self.assertIn("INDEPENDENCE_UNKNOWN", result["codes"])
        self.assertEqual(result["independence"], "UNKNOWN")

    def test_rejection_names_field_value_and_expectation(self) -> None:
        result = self.evaluate(make_record(classification="AMBIGUOUS"))
        failed = [check for check in result["checks"] if check["status"] == "FAIL"]
        self.assertTrue(failed)
        self.assertEqual(failed[0]["field"], "linkage_classification")
        self.assertEqual(failed[0]["value"], "AMBIGUOUS")
        self.assertIn("DIRECT_EVIDENCE", failed[0]["expected"])


# --- dual coordinates ----------------------------------------------------------

class LocationTests(unittest.TestCase):

    def setUp(self) -> None:
        self.directory = fixture_dir(self.id().split(".")[-1])
        self.reference, self.commit_file = write_pair(self.directory, header=3)

    def record(self, line=4) -> dict:
        return make_record(line=line, references_path=self.reference,
                           commit_file=self.commit_file)

    def test_record_line_and_commit_line_differ(self) -> None:
        record = self.record(line=4)  # commit line 1 holds apply_damage
        location = eligibility.build_evidence_location(record, record["evidence_items"][0])
        self.assertEqual(location["record_line"], 4)
        self.assertEqual(location["commit_line"], 1)
        self.assertEqual(location["offset_applied"], 3)
        self.assertTrue(location["offset_verified"])
        self.assertEqual(location["location_integrity"], eligibility.LOCATION_COMPLETE)
        self.assertTrue(location["source_lookup_allowed"])

    def test_offset_is_derived_from_the_files_not_assumed(self) -> None:
        self.reference2, self.commit2 = write_pair(self.directory, header=7)
        record = self.record(line=8)
        record["evidence_items"][0]["source_path"] = self.reference2
        record["source_verification"]["external_source_file"]["path"] = self.commit2
        location = eligibility.build_evidence_location(record, record["evidence_items"][0])
        self.assertEqual(location["offset_applied"], 7)
        self.assertEqual(location["commit_line"], 1)

    def test_missing_record_line_is_incomplete(self) -> None:
        record = self.record(line=None)
        location = eligibility.build_evidence_location(record, record["evidence_items"][0])
        self.assertIsNone(location["commit_line"])
        self.assertEqual(location["location_integrity"], eligibility.LOCATION_INCOMPLETE)
        self.assertFalse(location["source_lookup_allowed"])

    def test_unverifiable_offset_is_incomplete(self) -> None:
        unrelated = self.directory / "unrelated.gd"
        unrelated.write_text("func totally_different():\n\tpass\n", encoding="utf-8")
        record = self.record(line=4)
        record["source_verification"]["external_source_file"]["path"] = str(unrelated)
        location = eligibility.build_evidence_location(record, record["evidence_items"][0])
        self.assertIsNone(location["commit_line"])
        self.assertEqual(location["location_integrity"], eligibility.LOCATION_INCOMPLETE)

    def test_missing_files_do_not_produce_a_fabricated_location(self) -> None:
        record = self.record(line=4)
        record["evidence_items"][0]["source_path"] = str(self.directory / "absent.gd")
        location = eligibility.build_evidence_location(record, record["evidence_items"][0])
        self.assertIsNone(location["commit_line"])
        self.assertEqual(location["location_integrity"], eligibility.LOCATION_INCOMPLETE)
        self.assertFalse(location["offset_verified"])

    def test_graph_item_has_no_source_line(self) -> None:
        record = make_record(classification="INDIRECT_EVIDENCE",
                             evidence_type="GRAPH_RELATION", line=None,
                             intermediate_path=["alpha", "works_with", "health"])
        location = eligibility.build_evidence_location(record, record["evidence_items"][0])
        self.assertIsNone(location["commit_line"])
        self.assertEqual(location["location_integrity"], eligibility.LOCATION_INCOMPLETE)


# --- real store helpers --------------------------------------------------------

def real_records() -> dict[str, dict]:
    return {record.get("linkage_id"): record
            for record in linkage.load_linkage_records()
            if isinstance(record, dict) and record.get("linkage_id")}


def real_candidate(feature_id: str) -> dict:
    policy = eligibility.load_policy()
    return workspace.build_candidate(feature_id, policy, real_records(),
                                     workspace_id=workspace.workspace_identity(policy))


# --- schema --------------------------------------------------------------------

class SchemaTests(unittest.TestCase):

    @classmethod
    def setUpClass(cls) -> None:
        cls.policy = eligibility.load_policy()
        cls.records = real_records()
        cls.health = workspace.build_candidate(
            "health", cls.policy, cls.records,
            workspace_id=workspace.workspace_identity(cls.policy))

    def test_built_draft_is_valid(self) -> None:
        workspace.validate_candidate_draft(self.health)

    def test_missing_required_field_is_rejected(self) -> None:
        broken = copy.deepcopy(self.health)
        broken.pop("verification_status")
        with self.assertRaises(workspace.CandidateValidationError) as caught:
            workspace.validate_candidate_draft(broken)
        self.assertIn("verification_status", str(caught.exception))

    def test_decision_statuses_are_rejected(self) -> None:
        for status in ("ADMITTED", "PROMOTED", "VERIFIED", "accepted"):
            broken = copy.deepcopy(self.health)
            broken["candidate_status"] = status
            with self.assertRaises(workspace.CandidateValidationError):
                workspace.validate_candidate_draft(broken)

    def test_unknown_status_is_rejected(self) -> None:
        broken = copy.deepcopy(self.health)
        broken["candidate_status"] = "READY"
        with self.assertRaises(workspace.CandidateValidationError):
            workspace.validate_candidate_draft(broken)

    def test_non_seed_classification_in_evidence_ref_is_rejected(self) -> None:
        broken = copy.deepcopy(self.health)
        broken["evidence_refs"][0]["classification"] = "POTENTIAL_RELEVANCE"
        with self.assertRaises(workspace.CandidateValidationError) as caught:
            workspace.validate_candidate_draft(broken)
        self.assertIn("DIRECT_EVIDENCE", str(caught.exception))

    def test_missing_independence_is_rejected(self) -> None:
        broken = copy.deepcopy(self.health)
        broken["evidence_refs"][0].pop("independence")
        with self.assertRaises(workspace.CandidateValidationError):
            workspace.validate_candidate_draft(broken)

    def test_unknown_independence_in_ref_is_rejected(self) -> None:
        broken = copy.deepcopy(self.health)
        broken["evidence_refs"][0]["independence"] = "UNKNOWN"
        with self.assertRaises(workspace.CandidateValidationError):
            workspace.validate_candidate_draft(broken)

    def test_missing_source_provenance_is_rejected(self) -> None:
        broken = copy.deepcopy(self.health)
        broken["evidence_refs"][0].pop("source_commit")
        with self.assertRaises(workspace.CandidateValidationError):
            workspace.validate_candidate_draft(broken)

    def test_missing_dual_coordinate_fields_are_rejected(self) -> None:
        broken = copy.deepcopy(self.health)
        broken["evidence_refs"][0]["evidence_location"].pop("commit_line")
        with self.assertRaises(workspace.CandidateValidationError) as caught:
            workspace.validate_candidate_draft(broken)
        self.assertIn("commit_line", str(caught.exception))

    def test_silent_offset_is_rejected(self) -> None:
        broken = copy.deepcopy(self.health)
        location = broken["evidence_refs"][0]["evidence_location"]
        location["offset_applied"] = 3
        location["commit_line"] = location["record_line"]
        with self.assertRaises(workspace.CandidateValidationError) as caught:
            workspace.validate_candidate_draft(broken)
        self.assertIn("silently offsets", str(caught.exception))

    def test_lookup_allowed_while_incomplete_is_rejected(self) -> None:
        broken = copy.deepcopy(self.health)
        location = broken["evidence_refs"][0]["evidence_location"]
        location["location_integrity"] = eligibility.LOCATION_INCOMPLETE
        location["source_lookup_allowed"] = True
        with self.assertRaises(workspace.CandidateValidationError) as caught:
            workspace.validate_candidate_draft(broken)
        self.assertIn("source lookup", str(caught.exception))

    def test_context_ref_counted_as_seed_is_rejected(self) -> None:
        blackboard = real_candidate("blackboard")
        health = copy.deepcopy(self.health)
        health["context_refs"][0]["counts_as_seed"] = True
        with self.assertRaises(workspace.CandidateValidationError) as caught:
            workspace.validate_candidate_draft(health)
        self.assertIn("counts_as_seed", str(caught.exception))
        workspace.validate_candidate_draft(blackboard)

    def test_context_linkage_listed_as_seed_is_rejected(self) -> None:
        broken = copy.deepcopy(self.health)
        context_id = broken["context_refs"][0]["linkage_id"]
        extra = copy.deepcopy(broken["evidence_refs"][0])
        extra["linkage_id"] = context_id
        broken["evidence_refs"].append(extra)
        broken["eligibility_summary"]["seed_count"] = len(broken["evidence_refs"])
        broken["content_digest"] = workspace.candidate_content_digest(broken)
        with self.assertRaises(workspace.CandidateValidationError) as caught:
            workspace.validate_candidate_draft(broken)
        self.assertIn("also listed as seed", str(caught.exception))

    def test_tampered_content_digest_is_rejected(self) -> None:
        broken = copy.deepcopy(self.health)
        broken["content_digest"] = "0" * 64
        with self.assertRaises(workspace.CandidateValidationError) as caught:
            workspace.validate_candidate_draft(broken)
        self.assertIn("content_digest", str(caught.exception))

    def test_schema_version_compatibility(self) -> None:
        broken = copy.deepcopy(self.health)
        broken["schema_version"] = 2
        with self.assertRaises(workspace.CandidateValidationError):
            workspace.validate_candidate_draft(broken)

    def test_feature_verification_claim_is_rejected(self) -> None:
        broken = copy.deepcopy(self.health)
        broken["verification_status"]["feature_verification_status"] = "VERIFIED"
        with self.assertRaises(workspace.CandidateValidationError):
            workspace.validate_candidate_draft(broken)

    def test_forbidden_decision_key_is_rejected(self) -> None:
        broken = copy.deepcopy(self.health)
        broken["promoted"] = True
        with self.assertRaises(workspace.CandidateValidationError):
            workspace.validate_candidate_draft(broken)


# --- creation on the real store ------------------------------------------------

class CreationTests(unittest.TestCase):

    def setUp(self) -> None:
        self.out = fixture_dir(self.id().split(".")[-1])

    def build(self, **kwargs) -> dict:
        return workspace.build_workspace(eligibility.load_policy(), out_dir=self.out,
                                         **kwargs)

    def candidates(self) -> list[dict]:
        return workspace.load_candidates(self.out)

    def test_health_candidate_keeps_two_separate_evidences(self) -> None:
        result = self.build()
        health = workspace.find_candidate(self.out, feature_id="health")
        ids = [ref["linkage_id"] for ref in health["evidence_refs"]]
        self.assertEqual(sorted(ids), sorted([HEALTH_MAKE_PRO, HEALTH_NEZVERS]))
        repositories = {ref["source_repository"] for ref in health["evidence_refs"]}
        self.assertEqual(repositories,
                         {"gdquest-demos/godot-make-pro-2d-games",
                          "nezvers/Godot-GameTemplate"})
        self.assertEqual(health["eligibility_summary"]["seed_count"], 2)
        self.assertEqual(len({ref["linkage_id"] for ref in health["evidence_refs"]}), 2)
        self.assertEqual(len(result["built"]), 2)

    def test_health_evidences_are_not_merged_into_one_source(self) -> None:
        self.build()
        health = workspace.find_candidate(self.out, feature_id="health")
        commits = {ref["source_commit"] for ref in health["evidence_refs"]}
        digests = {ref["source_digest"] for ref in health["evidence_refs"]}
        self.assertEqual(len(commits), 2)
        self.assertEqual(len(digests), 2)
        self.assertIn("not merged", " ".join(health["limitations"]))

    def test_health_conditional_seed_is_preserved(self) -> None:
        self.build()
        health = workspace.find_candidate(self.out, feature_id="health")
        by_id = {ref["linkage_id"]: ref for ref in health["evidence_refs"]}
        self.assertEqual(by_id[HEALTH_NEZVERS]["seed_eligibility"],
                         "QUALIFIED_DIRECT_WITH_LIMITATIONS")
        self.assertEqual(by_id[HEALTH_MAKE_PRO]["seed_eligibility"], "QUALIFIED_DIRECT")
        self.assertTrue(by_id[HEALTH_NEZVERS]["symbol_notes"])
        self.assertEqual(health["candidate_status"], "NEEDS_REVIEW")

    def test_blackboard_candidate_preserves_not_independent(self) -> None:
        self.build()
        blackboard = workspace.find_candidate(self.out, feature_id="blackboard")
        ref = blackboard["evidence_refs"][0]
        self.assertEqual(ref["linkage_id"], BLACKBOARD_BEEHAVE)
        self.assertEqual(ref["independence"], "NOT_INDEPENDENT")
        self.assertTrue(ref["independence_reason"])
        self.assertEqual(blackboard["eligibility_summary"]["independent_seed_count"], 0)
        self.assertEqual(blackboard["eligibility_summary"]["not_independent_seed_count"], 1)
        self.assertIn("NOT_INDEPENDENT", " ".join(blackboard["limitations"]))

    def test_attack_emitter_gets_context_not_a_candidate(self) -> None:
        self.build()
        self.assertEqual([candidate["feature_id"] for candidate in self.candidates()],
                         ["health", "blackboard"])
        health = workspace.find_candidate(self.out, feature_id="health")
        self.assertEqual(len(health["context_refs"]), 1)
        context = health["context_refs"][0]
        self.assertEqual(context["linkage_id"], ATTACK_GRAPH)
        self.assertEqual(context["feature_id"], "attack_emitter")
        self.assertEqual(context["context_kind"], eligibility.GRAPH_DERIVED)
        self.assertEqual(context["derivation_type"], "FEATURE_GRAPH_NEIGHBOUR")
        self.assertEqual(context["intermediate_feature_ids"], ["health"])
        self.assertFalse(context["counts_as_seed"])
        self.assertNotIn(context["linkage_id"],
                         [ref["linkage_id"] for ref in health["evidence_refs"]])

    def test_excluded_features_get_no_candidate(self) -> None:
        result = self.build()
        features = [candidate["feature_id"] for candidate in self.candidates()]
        self.assertNotIn("health_bar", features)
        self.assertNotIn("openable_door", features)
        excluded = {entry["feature_id"]: entry
                    for entry in result["workspace"]["excluded_features"]}
        self.assertEqual(sorted(excluded), ["health_bar", "openable_door"])
        for entry in excluded.values():
            self.assertEqual(entry["reason_code"], "NO_QUALIFIED_SEED")
            self.assertTrue(entry["reason"])

    def test_rerun_is_idempotent(self) -> None:
        first = self.build()
        self.assertEqual(len(first["built"]), 2)
        path = workspace.candidate_paths(self.out)[0]
        before = path.read_bytes()
        second = self.build()
        self.assertEqual(second["built"], [])
        self.assertEqual(len(second["unchanged"]), 2)
        self.assertEqual(path.read_bytes(), before)
        first_candidate = workspace.load_candidates(self.out)[0]
        self.assertEqual(first_candidate["created_at"], first_candidate["updated_at"])

    def test_workspace_summary_is_stable(self) -> None:
        self.build()
        summary = (self.out / "WORKSPACE.json").read_bytes()
        self.build()
        self.assertEqual((self.out / "WORKSPACE.json").read_bytes(), summary)

    def test_no_write_into_the_feature_registry(self) -> None:
        self.build()
        self.assertFalse((PROJECT_ROOT / "Features" / "health" / "candidate.json").exists())
        prefix = workspace._relative(self.out)
        for candidate in self.candidates():
            self.assertTrue(str(candidate["__path__"]).startswith(prefix), prefix)
        feature_files = {path: path.read_bytes()
                         for path in (PROJECT_ROOT / "Features").glob("*/feature.yaml")}
        self.assertEqual(len(feature_files), 31)
        self.build()
        for path, payload in feature_files.items():
            self.assertEqual(path.read_bytes(), payload)

    def test_build_does_not_modify_linkage_records(self) -> None:
        before = {path: path.read_bytes() for path in
                  (AI_ROOT / "learning" / "external_code" / "feature_links").glob("*.json")}
        self.build()
        after = {path: path.read_bytes() for path in before}
        self.assertEqual(before, after)

    def test_atomic_write_leaves_no_partial_file_on_failure(self) -> None:
        target = self.out / "candidates" / "cand-test.json"
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text('{"previous": true}\n', encoding="utf-8")

        def explode(source, destination):
            raise OSError("injected failure")

        with self.assertRaises(OSError):
            workspace._atomic_write(target, "{}\n", replace_func=explode)
        self.assertEqual(target.read_text(encoding="utf-8"), '{"previous": true}\n')
        leftovers = list(target.parent.glob("*.tmp"))
        self.assertEqual(leftovers, [])


# --- freshness -----------------------------------------------------------------

class FreshnessTests(unittest.TestCase):

    def setUp(self) -> None:
        self.out = fixture_dir(self.id().split(".")[-1] + "_workspace")
        self.records_dir = fixture_dir(self.id().split(".")[-1] + "_records")
        self.records = real_records()
        workspace.build_workspace(eligibility.load_policy(), out_dir=self.out)

    def copy_records(self, mutate: dict[str, str] | None = None) -> Path:
        target = self.records_dir / "feature_links"
        target.mkdir(parents=True, exist_ok=True)
        for record in self.records.values():
            source = Path(record["__path__"])
            if not source.is_absolute():
                source = PROJECT_ROOT / source
            payload = source.read_bytes()
            if mutate and record["linkage_id"] in mutate:
                payload = mutate[record["linkage_id"]].encode("utf-8")
            (target / source.name).write_bytes(payload)
        return target

    def test_real_workspace_is_fresh(self) -> None:
        result = workspace.check_candidate_freshness(self.out)
        self.assertEqual(result["checked"], 2)
        self.assertEqual(result["status_counts"]["FRESH"], 2)

        validate = workspace.validate_workspace(self.out)
        self.assertEqual([item["status"] for item in validate["results"]],
                         ["VALID", "VALID"])

    def test_changed_linkage_record_is_stale(self) -> None:
        tampered = json.loads((PROJECT_ROOT / self.records[HEALTH_MAKE_PRO]["__path__"])
                              .read_text(encoding="utf-8"))
        tampered["limitations"] = ["tampered for the test"]
        directory = self.copy_records({HEALTH_MAKE_PRO: json.dumps(tampered)})
        result = workspace.check_candidate_freshness(self.out, linkage_dir=directory)
        health = next(item for item in result["results"] if item["feature_id"] == "health")
        self.assertEqual(health["status"], "STALE")
        self.assertIn("STALE_LINKAGE", [issue["status"] for issue in health["issues"]])

    def test_missing_linkage_record_is_reported(self) -> None:
        directory = self.copy_records()
        (directory / Path(self.records[HEALTH_NEZVERS]["__path__"]).name).unlink()
        result = workspace.check_candidate_freshness(self.out, linkage_dir=directory)
        health = next(item for item in result["results"] if item["feature_id"] == "health")
        self.assertEqual(health["status"], "INCOMPLETE")
        self.assertIn("MISSING_LINKAGE", [issue["status"] for issue in health["issues"]])

    def test_policy_change_makes_the_candidate_incomplete(self) -> None:
        policy = eligibility.load_policy()
        policy["policy_version"] = "phase-1.74-c/2"
        result = workspace.check_candidate_freshness(self.out, policy=policy)
        self.assertTrue(all(item["status"] == "INCOMPLETE"
                            for item in result["results"]))
        self.assertIn("POLICY_CHANGED",
                      [issue["status"] for item in result["results"]
                       for issue in item["issues"]])


class RealStoreEligibilityTests(unittest.TestCase):
    """The four reviewed records behave exactly as Batch B.2 concluded."""

    @classmethod
    def setUpClass(cls) -> None:
        cls.policy = eligibility.load_policy()
        cls.records = real_records()

    def evaluate(self, linkage_id: str) -> dict:
        return eligibility.evaluate_seed_eligibility(self.records[linkage_id], self.policy)

    def test_three_qualifications_match_b2(self) -> None:
        self.assertEqual(self.evaluate(HEALTH_MAKE_PRO)["seed_eligibility"],
                         "QUALIFIED_DIRECT")
        self.assertEqual(self.evaluate(HEALTH_NEZVERS)["seed_eligibility"],
                         "QUALIFIED_DIRECT_WITH_LIMITATIONS")
        self.assertEqual(self.evaluate(BLACKBOARD_BEEHAVE)["seed_eligibility"],
                         "QUALIFIED_DIRECT")
        for linkage_id in (HEALTH_MAKE_PRO, HEALTH_NEZVERS, BLACKBOARD_BEEHAVE):
            self.assertTrue(self.evaluate(linkage_id)["eligible"], linkage_id)

    def test_real_locations_use_verified_offsets(self) -> None:
        stats = self.evaluate(HEALTH_MAKE_PRO)
        self.assertEqual(stats["location_integrity"], eligibility.LOCATION_COMPLETE)
        commits = {location["symbol_at_commit_line"] for location in stats["locations"]}
        self.assertEqual(commits, {"VERIFIED"})
        self.assertEqual({location["offset_applied"] for location in stats["locations"]},
                         {3})
        lines = {(location["record_line"], location["commit_line"])
                 for location in stats["locations"]}
        self.assertEqual(lines, {(23, 20), (31, 28), (6, 3)})

    def test_resource_evidence_keeps_property_function_note(self) -> None:
        ref = eligibility.build_evidence_reference(self.records[HEALTH_NEZVERS],
                                                   self.policy)
        self.assertTrue(ref["symbol_notes"])
        self.assertIn("property", " ".join(ref["symbol_notes"]))
        self.assertEqual(ref["evidence_location"]["commit_line"], 16)
        self.assertEqual(ref["evidence_location"]["record_line"], 19)

    def test_blackboard_location_is_incomplete_for_the_class_item(self) -> None:
        ref = eligibility.build_evidence_reference(self.records[BLACKBOARD_BEEHAVE],
                                                   self.policy)
        self.assertEqual(ref["evidence_location"]["location_integrity"],
                         eligibility.LOCATION_INCOMPLETE)
        self.assertFalse(ref["evidence_location"]["source_lookup_allowed"])
        items = {item["symbol_name"]: item for item in ref["evidence_item_refs"]}
        self.assertIsNone(items["Blackboard"]["commit_line"])
        self.assertEqual(items["set_value"]["commit_line"], 27)

    def test_graph_record_is_never_seed_eligible(self) -> None:
        result = self.evaluate(ATTACK_GRAPH)
        self.assertFalse(result["eligible"])
        self.assertIn("CLASSIFICATION_NOT_ELIGIBLE", result["codes"])
        self.assertIn("GRAPH_DERIVED_NOT_SEED", result["codes"])

    def test_attack_emitter_is_not_in_the_seed_policy(self) -> None:
        self.assertEqual(eligibility.seed_entries(self.policy, "attack_emitter"), [])
        self.assertEqual(eligibility.context_entries(self.policy, "health")[0]["linkage_id"],
                         ATTACK_GRAPH)

    def test_linkage_evidence_helper_excludes_pair_evaluation(self) -> None:
        for record in self.records.values():
            items = linkage.linkage_evidence_items(record)
            self.assertFalse([item for item in items
                              if item.get("evidence_role") == linkage.PAIR_EVALUATION_ROLE])


if __name__ == "__main__":
    unittest.main(verbosity=2)
