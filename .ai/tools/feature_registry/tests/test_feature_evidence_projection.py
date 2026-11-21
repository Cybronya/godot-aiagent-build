#!/usr/bin/env python3
"""Phase 1.73 Batch A: Feature Evidence Projection tests.

The fixture tests use an isolated temporary project and never write to the
real Features/, Feature Index, Feature Graph, Source Analysis, or External
Analysis data.  The pilot tests only read the real pilot inputs.

Usage:
    python .ai/tools/feature_registry/tests/test_feature_evidence_projection.py
"""

from __future__ import annotations

import copy
import hashlib
import json
import os
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

HERE = Path(__file__).resolve().parent
TOOL_DIR = HERE.parent
DOTAI = TOOL_DIR.parent.parent
PROJECT_ROOT = DOTAI.parent
if str(TOOL_DIR) not in sys.path:
    sys.path.insert(0, str(TOOL_DIR))

import feature_evidence as fe  # noqa: E402


def write(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8", newline="\n")


def digest(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


FIXTURE_METADATA = """\
id: alpha
name: Alpha Fixture
category: component
summary: Fixture summary
provides: [alpha_state, alpha_event]
requires: [beta]
relations:
  works_with: [beta]
interfaces:
  methods:
    - {name: do_thing, signature: "do_thing() -> void"}
  signals:
    - {name: changed, signature: changed}
  exports: []
capabilities:
  required: [scene_alpha]
validation:
  test_path: '__TEST_PATH__'
  command: "godot --headless"
"""

FIXTURE_TEMPLATE = """\
behavior:
  - id: do_thing
  - id: ambiguous_thing
"""

FIXTURE_GDSCRIPT = """\
class_name AlphaFixture
extends Node

signal changed

@export var enabled := true

var state := false


func do_thing() -> void:
\tstate = true
\tchanged.emit()
"""

FIXTURE_COVERAGE = {
    "rows": [
        {"feature_id": "alpha", "behavior_id": "do_thing", "contract_version": 1},
        {"feature_id": "alpha", "behavior_id": "ambiguous_thing", "contract_version": 1},
    ]
}


def make_fixture(root: Path) -> dict:
    features = root / "Features"
    alpha = features / "alpha"
    beta = features / "beta"
    write(alpha / "alpha.gd", FIXTURE_GDSCRIPT)
    (alpha / "test_alpha.gd").write_text("extends SceneTree\n", encoding="utf-8")
    source = alpha / "alpha.gd"
    write(alpha / "feature.yaml",
          FIXTURE_METADATA.replace("__TEST_PATH__", str(alpha / "test_alpha.gd")))
    write(alpha / "template.yaml", FIXTURE_TEMPLATE)
    write(beta / "feature.yaml", """\
id: beta
name: Beta Fixture
category: component
summary: No behavior contract.
provides: []
requires: []
interfaces: {methods: [], signals: [], exports: []}
ownership: {state: [], rules: []}
composition: {entry_scene: null, usage: reuse}
validation: {}
""")

    source_dir = root / ".ai" / "learning" / "source_analysis" / "alpha"
    for behavior, status in (("do_thing", "PARTIAL"), ("ambiguous_thing", "SOURCE_ENTRY_AMBIGUOUS")):
        record = {
            "feature_id": "alpha",
            "behavior_id": behavior,
            "analysis_status": status,
            "contract_version": 1,
            "static_only": True,
            "scripts": [{"path": "Features/alpha/alpha.gd", "digest": digest(source)}],
            "unresolved_questions": ["fixture limitation"],
        }
        write(source_dir / (behavior + ".json"), json.dumps(record, indent=2) + "\n")

    context = root / ".ai" / "context"
    write(context / "feature_index.json", json.dumps({
        "features": [{
            "id": "alpha", "name": "Alpha Fixture", "category": "component",
            "summary": "Fixture summary", "path": "Features/alpha/feature.yaml",
            "provides": ["alpha_state", "alpha_event"], "requires": ["beta"],
            "interfaces": {
                "methods": [{"name": "do_thing", "signature": "do_thing() -> void"}],
                "signals": [{"name": "changed", "signature": "changed"}],
                "exports": [],
            },
            "validation": {"test_path": str(alpha / "test_alpha.gd"),
                           "command": "godot --headless"},
        }],
    }, indent=2) + "\n")
    graph = {
        "nodes": ["alpha", "beta"],
        "edges": [{"from": "alpha", "to": "beta", "type": "works_with"}],
    }
    write(context / "feature_graph.json", json.dumps(graph, indent=2) + "\n")
    write(context / "coverage_matrix.json", json.dumps(FIXTURE_COVERAGE, indent=2) + "\n")

    return {
        "root": root,
        "features": features,
        "index": context / "feature_index.json",
        "graph": context / "feature_graph.json",
        "coverage": context / "coverage_matrix.json",
        "source_analysis": root / ".ai" / "learning" / "source_analysis",
        "source": source,
        "alpha": alpha,
    }


def build(fx: dict, feature_id: str = "alpha") -> dict:
    return fe.build_projection(
        feature_id,
        features_dir=fx["features"],
        index_path=fx["index"],
        graph_path=fx["graph"],
        source_analysis_dir=fx["source_analysis"],
        coverage_path=fx["coverage"],
        project_root=fx["root"],
    )


def statuses(projection: dict, section: str) -> list[str]:
    return [item["extraction_status"] for item in projection[section]]


class FixtureProjectionTests(unittest.TestCase):
    def setUp(self) -> None:
        # Keep test scratch data on the project drive; do not use the system
        # %TEMP% directory (which is on C: on this machine).
        fe.DEFAULT_OUT.mkdir(parents=True, exist_ok=True)
        self.temp = tempfile.TemporaryDirectory(prefix="p173_evidence_", dir=str(fe.DEFAULT_OUT))
        self.fx = make_fixture(Path(self.temp.name))
        self.projection = build(self.fx)

    def tearDown(self) -> None:
        self.temp.cleanup()

    # --- Schema ---------------------------------------------------------
    def test_schema_accepts_built_projection(self) -> None:
        fe.validate_projection(self.projection)
        self.assertEqual(self.projection["schema"], "feature_evidence_projection")
        self.assertEqual(self.projection["schema_version"], 1)

    def test_schema_accepts_legacy_projection_without_verification_status(self) -> None:
        legacy = copy.deepcopy(self.projection)
        legacy.pop("verification_status")
        fe.validate_projection(legacy)

    def test_schema_rejects_missing_required_field(self) -> None:
        broken = copy.deepcopy(self.projection)
        broken.pop("source_identity")
        with self.assertRaises(fe.ProjectionValidationError):
            fe.validate_projection(broken)

    def test_schema_rejects_invalid_evidence_status(self) -> None:
        broken = copy.deepcopy(self.projection)
        broken["capability_evidence"][0]["extraction_status"] = "VERIFIED"
        with self.assertRaises(fe.ProjectionValidationError):
            fe.validate_projection(broken)

    def test_schema_requires_source_trace_fields(self) -> None:
        broken = copy.deepcopy(self.projection)
        broken["source_references"][0].pop("source_digest")
        with self.assertRaises(fe.ProjectionValidationError):
            fe.validate_projection(broken)

    def test_invalid_projection_is_not_written(self) -> None:
        out = Path(self.temp.name) / "out"
        target = out / "alpha.json"
        write(target, "OLD\n")
        broken = copy.deepcopy(self.projection)
        broken["evidence_counts"]["DECLARED"] += 1
        with self.assertRaises(fe.ProjectionValidationError):
            fe.write_projection(broken, out)
        self.assertEqual(target.read_text(encoding="utf-8"), "OLD\n")

    # --- Evidence -------------------------------------------------------
    def test_declared_is_not_upgraded_to_extracted(self) -> None:
        capabilities = self.projection["capability_evidence"]
        self.assertTrue(capabilities)
        self.assertTrue(all(item["extraction_status"] == "DECLARED" for item in capabilities))
        self.assertTrue(all(
            all(item["extraction_status"] != "EXTRACTED" for item in self.projection[section])
            for section in fe.EVIDENCE_SECTIONS
            if section == "capability_evidence"
        ))

    def test_extracted_symbols_are_traceable(self) -> None:
        symbols = [item for item in self.projection["symbol_evidence"]
                   if item["extraction_status"] == "EXTRACTED"]
        self.assertTrue(symbols)
        for item in symbols:
            self.assertTrue(item["source_file"])
            self.assertTrue(item["source_symbol"])
            self.assertTrue(item["provenance"].get("source_digest"))
            self.assertIn("source_line", item)

    def test_partial_status_is_preserved(self) -> None:
        behavior = {item["evidence_id"]: item for item in self.projection["behavior_evidence"]}
        self.assertEqual(behavior["behavior:alpha:do_thing"]["extraction_status"], "PARTIAL")
        self.assertEqual(behavior["behavior:alpha:do_thing"]["value"]["analysis_status"], "PARTIAL")
        self.assertIn("PARTIAL", statuses(self.projection, "behavior_evidence"))

    def test_source_entry_ambiguous_stays_ambiguous(self) -> None:
        behavior = {item["evidence_id"]: item for item in self.projection["behavior_evidence"]}
        record = behavior["behavior:alpha:ambiguous_thing"]
        self.assertEqual(record["extraction_status"], "PARTIAL")
        self.assertEqual(record["value"]["analysis_status"], "SOURCE_ENTRY_AMBIGUOUS")
        self.assertNotEqual(record["extraction_status"], "EXTRACTED")

    def test_missing_and_not_applicable_are_distinct(self) -> None:
        # beta has no behavior contract and no records.
        beta = fe.build_projection(
            "beta",
            features_dir=self.fx["features"],
            index_path=self.fx["index"],
            graph_path=self.fx["graph"],
            source_analysis_dir=self.fx["source_analysis"],
            coverage_path=self.fx["coverage"],
            project_root=self.fx["root"],
        )
        beta_behavior = beta["behavior_evidence"]
        self.assertEqual([item["extraction_status"] for item in beta_behavior], ["NOT_APPLICABLE"])
        self.assertNotIn("MISSING", statuses(beta, "behavior_evidence"))

        # alpha declares a contract without a source-analysis record.
        write(self.fx["alpha"] / "template.yaml", FIXTURE_TEMPLATE + "  - id: absent_thing\n")
        alpha = build(self.fx)
        absent = [item for item in alpha["behavior_evidence"]
                  if item["value"].get("behavior_id") == "absent_thing"]
        self.assertTrue(absent)
        self.assertEqual(absent[0]["extraction_status"], "MISSING")

    def test_graph_relation_is_declared_structure_not_extracted(self) -> None:
        dependencies = [item for item in self.projection["dependency_evidence"]
                        if item["source_type"] == "FEATURE_GRAPH"]
        self.assertTrue(dependencies)
        for item in dependencies:
            self.assertEqual(item["extraction_status"], "DECLARED")
            self.assertEqual(item["value"]["evidence_scope"], "GRAPH_STRUCTURE")
            self.assertNotEqual(item["extraction_status"], "EXTRACTED")

    # --- Paths ----------------------------------------------------------
    def test_windows_absolute_path_is_normalized(self) -> None:
        desc = fe.normalize_path(
            "F:\\Godot_v4.7-stable\\game\\Features\\health\\feature.yaml", PROJECT_ROOT)
        self.assertEqual(desc["normalization_status"], "CONVERTED")
        self.assertEqual(desc["normalized_path"], "Features/health/feature.yaml")
        self.assertTrue(desc["original_path"].startswith("F:"))

    def test_project_relative_path_is_stable(self) -> None:
        desc = fe.normalize_path("Features/health/feature.yaml", PROJECT_ROOT)
        self.assertEqual(desc["normalization_status"], "RELATIVE")
        self.assertEqual(desc["normalized_path"], "Features/health/feature.yaml")

    def test_outside_path_keeps_original_value(self) -> None:
        outside = Path(self.temp.name).parent / "outside_alpha.gd"
        desc = fe.normalize_path(str(outside), self.fx["root"])
        self.assertEqual(desc["normalization_status"], "OUTSIDE_PROJECT")
        self.assertEqual(desc["original_path"], str(outside))
        self.assertEqual(desc["normalized_path"], "")

    def test_build_does_not_modify_feature_index(self) -> None:
        before = digest(self.fx["index"])
        build(self.fx)
        self.assertEqual(digest(self.fx["index"]), before)

    # --- Freshness ------------------------------------------------------
    def test_freshness_is_fresh_for_unchanged_inputs(self) -> None:
        out = Path(self.temp.name) / "out"
        fe.build_and_write(
            "alpha", out, features_dir=self.fx["features"], index_path=self.fx["index"],
            graph_path=self.fx["graph"], source_analysis_dir=self.fx["source_analysis"],
            coverage_path=self.fx["coverage"], project_root=self.fx["root"],
        )
        result = fe.check_projection(
            "alpha", out_dir=out, features_dir=self.fx["features"],
            index_path=self.fx["index"], graph_path=self.fx["graph"],
            source_analysis_dir=self.fx["source_analysis"],
            coverage_path=self.fx["coverage"], project_root=self.fx["root"],
        )
        self.assertEqual(result["status"], "FRESH")

    def test_freshness_detects_source_digest_change(self) -> None:
        out = Path(self.temp.name) / "out"
        fe.build_and_write(
            "alpha", out, features_dir=self.fx["features"], index_path=self.fx["index"],
            graph_path=self.fx["graph"], source_analysis_dir=self.fx["source_analysis"],
            coverage_path=self.fx["coverage"], project_root=self.fx["root"],
        )
        self.fx["source"].write_text(FIXTURE_GDSCRIPT + "\n# changed\n", encoding="utf-8")
        result = fe.check_projection(
            "alpha", out_dir=out, features_dir=self.fx["features"],
            index_path=self.fx["index"], graph_path=self.fx["graph"],
            source_analysis_dir=self.fx["source_analysis"],
            coverage_path=self.fx["coverage"], project_root=self.fx["root"],
        )
        self.assertEqual(result["status"], "STALE")
        self.assertTrue(result["changed_sources"])

    def test_freshness_detects_added_and_removed_sources(self) -> None:
        out = Path(self.temp.name) / "out"
        fe.build_and_write(
            "alpha", out, features_dir=self.fx["features"], index_path=self.fx["index"],
            graph_path=self.fx["graph"], source_analysis_dir=self.fx["source_analysis"],
            coverage_path=self.fx["coverage"], project_root=self.fx["root"],
        )
        extra = self.fx["source_analysis"] / "alpha" / "extra.json"
        write(extra, json.dumps({"feature_id": "alpha", "behavior_id": "extra",
                                 "analysis_status": "PARTIAL"}, indent=2) + "\n")
        added = fe.check_projection(
            "alpha", out_dir=out, features_dir=self.fx["features"],
            index_path=self.fx["index"], graph_path=self.fx["graph"],
            source_analysis_dir=self.fx["source_analysis"],
            coverage_path=self.fx["coverage"], project_root=self.fx["root"],
        )
        self.assertEqual(added["status"], "STALE")
        # Rebuild with the added source, then remove it: the change must be
        # detected relative to that newer projection, not the original baseline.
        fe.build_and_write(
            "alpha", out, features_dir=self.fx["features"], index_path=self.fx["index"],
            graph_path=self.fx["graph"], source_analysis_dir=self.fx["source_analysis"],
            coverage_path=self.fx["coverage"], project_root=self.fx["root"],
        )
        extra.unlink()
        removed = fe.check_projection(
            "alpha", out_dir=out, features_dir=self.fx["features"],
            index_path=self.fx["index"], graph_path=self.fx["graph"],
            source_analysis_dir=self.fx["source_analysis"],
            coverage_path=self.fx["coverage"], project_root=self.fx["root"],
        )
        self.assertEqual(removed["status"], "STALE")

    def test_missing_source_is_reported(self) -> None:
        self.fx["source"].unlink()
        projection = build(self.fx)
        missing = [item for item in projection["symbol_evidence"]
                   if item["extraction_status"] == "MISSING"]
        self.assertTrue(missing)
        self.assertTrue(any("missing" in item["limitations"][0] for item in missing))

    # --- Atomic writes --------------------------------------------------
    def test_build_failure_keeps_old_projection(self) -> None:
        out = Path(self.temp.name) / "out"
        target = out / "alpha.json"
        write(target, "OLD\n")
        with self.assertRaises(fe.ProjectionError):
            fe.build_and_write("missing_feature", out, features_dir=self.fx["features"],
                               index_path=self.fx["index"], graph_path=self.fx["graph"],
                               source_analysis_dir=self.fx["source_analysis"],
                               coverage_path=self.fx["coverage"], project_root=self.fx["root"])
        self.assertEqual(target.read_text(encoding="utf-8"), "OLD\n")

    def test_json_write_failure_keeps_old_projection(self) -> None:
        out = Path(self.temp.name) / "out"
        target = out / "alpha.json"
        write(target, "OLD\n")
        with mock.patch.object(fe.json, "dump", side_effect=OSError("simulated write failure")):
            with self.assertRaises(OSError):
                fe.write_projection(self.projection, out)
        self.assertEqual(target.read_text(encoding="utf-8"), "OLD\n")

    def test_schema_failure_keeps_old_projection(self) -> None:
        out = Path(self.temp.name) / "out"
        target = out / "alpha.json"
        write(target, "OLD\n")
        broken = copy.deepcopy(self.projection)
        broken["schema"] = "not-the-schema"
        with self.assertRaises(fe.ProjectionValidationError):
            fe.write_projection(broken, out)
        self.assertEqual(target.read_text(encoding="utf-8"), "OLD\n")

    def test_replace_failure_keeps_old_projection(self) -> None:
        out = Path(self.temp.name) / "out"
        target = out / "alpha.json"
        write(target, "OLD\n")

        def fail_replace(_source: str, _target: str) -> None:
            raise OSError("simulated replace failure")

        with self.assertRaises(OSError):
            fe.write_projection(self.projection, out, replace_func=fail_replace)
        self.assertEqual(target.read_text(encoding="utf-8"), "OLD\n")

    def test_successful_replace_leaves_no_temp_file(self) -> None:
        out = Path(self.temp.name) / "out"
        fe.write_projection(self.projection, out)
        self.assertEqual(sorted(path.name for path in out.iterdir()), ["alpha.json"])


class PilotProjectionTests(unittest.TestCase):
    """Each pilot is asserted independently against the real read-only inputs."""

    @classmethod
    def setUpClass(cls) -> None:
        cls.projections = {feature: fe.build_projection(feature) for feature in fe.PILOT_FEATURES}
        cls.index_before = digest(fe.INDEX_PATH)

    def test_all_pilots_have_valid_projections(self) -> None:
        self.assertEqual(set(self.projections), set(fe.PILOT_FEATURES))
        for projection in self.projections.values():
            fe.validate_projection(projection)

    def test_health_projection(self) -> None:
        projection = self.projections["health"]
        self.assertEqual(len(projection["analysis_references"]), 5)
        self.assertEqual({item["analysis_status"] for item in projection["analysis_references"]},
                         {"PARTIAL"})
        self.assertEqual([item["extraction_status"] for item in projection["behavior_evidence"]],
                         ["PARTIAL"] * 5)
        self.assertTrue(any(item["extraction_status"] == "EXTRACTED"
                            for item in projection["symbol_evidence"]))

    def test_health_bar_projection(self) -> None:
        projection = self.projections["health_bar"]
        self.assertEqual(len(projection["analysis_references"]), 5)
        self.assertTrue(any(item["value"].get("target") == "health_state"
                            for item in projection["dependency_evidence"]))
        self.assertEqual({item["extraction_status"] for item in projection["behavior_evidence"]},
                         {"PARTIAL"})

    def test_openable_door_projection(self) -> None:
        projection = self.projections["openable_door"]
        self.assertEqual([item["analysis_status"] for item in projection["analysis_references"]],
                         ["COMPLETE"])
        self.assertEqual([item["extraction_status"] for item in projection["behavior_evidence"]],
                         ["EXTRACTED"])
        self.assertTrue(projection["analysis_references"][0]["analyzed_source_files"])

    def test_attack_emitter_projection(self) -> None:
        projection = self.projections["attack_emitter"]
        self.assertEqual(len(projection["analysis_references"]), 2)
        self.assertEqual({item["analysis_status"] for item in projection["analysis_references"]},
                         {"SOURCE_ENTRY_AMBIGUOUS"})
        self.assertEqual({item["extraction_status"] for item in projection["behavior_evidence"]},
                         {"PARTIAL"})

    def test_blackboard_projection(self) -> None:
        projection = self.projections["blackboard"]
        self.assertEqual(projection["analysis_references"], [])
        behavior = projection["behavior_evidence"]
        self.assertEqual([item["extraction_status"] for item in behavior], ["NOT_APPLICABLE"])
        self.assertTrue(any(item["extraction_status"] == "EXTRACTED"
                            for item in projection["symbol_evidence"]))
        self.assertNotIn("MISSING", statuses(projection, "behavior_evidence"))

    def test_complete_projection_is_not_feature_verified(self) -> None:
        for feature in ("openable_door", "blackboard"):
            projection = self.projections[feature]
            self.assertEqual(projection["projection_status"], "COMPLETE")
            self.assertEqual(
                projection["verification_status"]["feature_verification_status"],
                "NOT_VERIFIED",
            )

    def test_source_analysis_complete_is_not_test_execution_complete(self) -> None:
        projection = self.projections["openable_door"]
        self.assertEqual({item["analysis_status"] for item in projection["analysis_references"]},
                         {"COMPLETE"})
        self.assertEqual(projection["verification_status"]["test_execution_status"], "NOT_RUN")
        self.assertEqual(
            {item["value"]["execution_status"] for item in projection["test_evidence"]},
            {"NOT_RUN"},
        )

    def test_absent_source_analysis_is_not_source_analysis_complete(self) -> None:
        projection = self.projections["blackboard"]
        self.assertEqual(projection["analysis_references"], [])
        self.assertNotIn(
            "COMPLETE",
            {item.get("analysis_status") for item in projection["analysis_references"]},
        )
        self.assertEqual(
            projection["verification_status"]["runtime_verification_status"],
            "NOT_VERIFIED",
        )

    def test_not_applicable_is_not_verified(self) -> None:
        projection = self.projections["blackboard"]
        self.assertEqual(projection["behavior_evidence"][0]["extraction_status"],
                         "NOT_APPLICABLE")
        self.assertEqual(
            projection["verification_status"]["feature_verification_status"],
            "NOT_VERIFIED",
        )

    def test_test_execution_not_run_is_not_upgraded(self) -> None:
        for projection in self.projections.values():
            self.assertEqual(
                projection["verification_status"]["test_execution_status"],
                "NOT_RUN",
            )
            for item in projection["test_evidence"]:
                self.assertEqual(item["value"]["execution_status"], "NOT_RUN")

    def test_runtime_verification_not_verified_is_not_upgraded(self) -> None:
        for projection in self.projections.values():
            self.assertEqual(
                projection["verification_status"]["runtime_verification_status"],
                "NOT_VERIFIED",
            )

    def test_partial_source_analysis_is_not_overridden_by_projection(self) -> None:
        for feature in ("health", "health_bar"):
            projection = self.projections[feature]
            self.assertEqual(projection["projection_status"], "PARTIAL")
            self.assertEqual(
                {item["analysis_status"] for item in projection["analysis_references"]},
                {"PARTIAL"},
            )
            self.assertEqual(
                {item["extraction_status"] for item in projection["behavior_evidence"]},
                {"PARTIAL"},
            )
            self.assertEqual(
                projection["verification_status"]["feature_verification_status"],
                "NOT_VERIFIED",
            )

    def test_source_entry_ambiguous_remains_visible(self) -> None:
        projection = self.projections["attack_emitter"]
        self.assertEqual(
            {item["analysis_status"] for item in projection["analysis_references"]},
            {"SOURCE_ENTRY_AMBIGUOUS"},
        )
        self.assertEqual(
            {item["value"]["analysis_status"] for item in projection["behavior_evidence"]},
            {"SOURCE_ENTRY_AMBIGUOUS"},
        )
        self.assertEqual(
            projection["verification_status"]["feature_verification_status"],
            "NOT_VERIFIED",
        )

    def test_no_verified_status_is_generated(self) -> None:
        keys = (
            "feature_verification_status",
            "test_execution_status",
            "runtime_verification_status",
            "behavior_verification_status",
        )
        for projection in self.projections.values():
            for key in keys:
                self.assertNotEqual(projection["verification_status"][key], "VERIFIED")

    def test_pilots_do_not_modify_real_feature_index(self) -> None:
        self.assertEqual(digest(fe.INDEX_PATH), self.index_before)


if __name__ == "__main__":
    unittest.main(verbosity=2)
