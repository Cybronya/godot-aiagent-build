"""Behavior Knowledge Extraction（Phase 1.65）。

把**已有真实产物**翻译成类型化候选知识：

| 输入 | 产出知识类型 | 门禁 |
| --- | --- | --- |
| 正式契约 | `CONTRACT_FACT` | 引用 `Features/...template.yaml#behavior=` |
| 源码分析 | `SOURCE_OBSERVATION` | 引用 `file:line` + 文件 SHA256（写入时校验） |
| 依赖图 | `DEPENDENCY_KNOWLEDGE` | 引用源码或契约的边 |
| 矩阵 + 评估报告 | `TEST_OBSERVATION` | run_id + bundle digest，并校验评估归属 |
| 矩阵 attestation | `RUNTIME_OBSERVATION` | run_id + attestation_digest |
| mutation 报告 | `MUTATION_OBSERVATION` | 仅 `MUTANT_KILLED` |
| 1.64 记录里的失败模式 | `FAILURE_KNOWLEDGE` | 引用原始报告 |
| 多来源推导 | `INFERENCE` | `derivations` 指向已存在记录 |

**不制造**：没有 evidence 就不写 TEST_OBSERVATION；没有 attestation 就不写 RUNTIME_OBSERVATION；
没有 KILLED 就不写 MUTATION_OBSERVATION。缺什么就在计划里当缺口。

用法：
    python .ai/tools/learning/extract.py --matrix .ai/tmp/p164/batch1/matrix_after/coverage_matrix.json \
        --behaviors openable_door/open,i_frames/iframes_expire_and_damage_resumes
"""

from __future__ import annotations

import argparse
import glob
import json
import os

import dependencies
import knowledge_v2
import paths
import source_analysis

MUTATION_DIRS = (".ai/tmp/p164/mutation/reports", ".ai/tmp/p164/mutation2/reports")
LEGACY_STORE = ".ai/knowledge/behavior_verification"


def _load_matrix(matrix_path: str) -> dict:
    if not matrix_path:
        raise SystemExit("--matrix is required: the planner/extractor never uses a default matrix "
                         "(Phase 1.64 P2 attribution contamination)")
    with open(matrix_path, encoding="utf-8") as handle:
        return json.load(handle)


def _row(matrix: dict, feature_id: str, behavior_id: str) -> dict:
    for row in matrix["rows"]:
        if row["feature_id"] == feature_id and row["behavior_id"] == behavior_id:
            return row
    raise KeyError("behavior not in matrix: %s/%s" % (feature_id, behavior_id))


def _mutation_reports() -> dict[tuple[str, str], dict]:
    reports: dict[tuple[str, str], dict] = {}
    for directory in MUTATION_DIRS:
        for path in sorted(glob.glob(os.path.join(paths.ROOT, directory, "M*.json"))):
            with open(path, encoding="utf-8") as handle:
                report = json.load(handle)
            catalog = report.get("catalog") or {}
            key = (catalog.get("feature_id") or catalog.get("feature"),
                   catalog.get("behavior_id") or catalog.get("behavior"))
            if None in key:
                continue
            current = reports.get(key)
            if current is None or str(report.get("verdict")) == "MUTANT_KILLED":
                report["_path"] = os.path.relpath(path, paths.ROOT).replace(os.sep, "/")
                reports[key] = report
    return reports


def _verify_evaluation_attribution(report_path: str, row: dict) -> tuple[bool, str]:
    """防止 P2 归因污染：评估报告必须真的覆盖这个 Behavior 的 bundle。"""
    path = os.path.join(paths.ROOT, report_path) if not os.path.isabs(report_path) else report_path
    if not os.path.isfile(path):
        return False, "evaluation report missing: %s" % report_path
    with open(path, encoding="utf-8") as handle:
        report = json.load(handle)
    digest = str((row.get("evidence") or {}).get("bundle_digest") or "")
    bundles = ((report.get("evidence") or {}).get("bundles") or [])
    if digest and not any(str(bundle.get("digest")) == digest for bundle in bundles):
        return False, "evaluation report does not contain bundle digest %s" % digest[:12]
    behavior_id = str(row["behavior_id"])
    if behavior_id not in json.dumps(report.get("tasks") or report, ensure_ascii=False):
        return False, "evaluation report does not mention behavior %s" % behavior_id
    return True, "attribution verified"


def _legacy_failures(feature_id: str, behavior_id: str) -> list[dict]:
    path = os.path.join(paths.ROOT, LEGACY_STORE, feature_id, "%s.json" % behavior_id)
    if not os.path.isfile(path):
        return []
    with open(path, encoding="utf-8") as handle:
        record = json.load(handle)
    return record.get("failure_modes") or []


def extract_behavior(feature_id: str, behavior_id: str, *, matrix: dict, graph: dict,
                     analysis: dict | None = None, mutations: dict | None = None) -> list[dict]:
    analysis = analysis or source_analysis.analyze(feature_id, behavior_id)
    mutations = mutations if mutations is not None else _mutation_reports()
    row = _row(matrix, feature_id, behavior_id)
    version = analysis["contract_version"]
    candidates = []

    def candidate(knowledge_type: str, key: str, content, refs: list[dict], confidence: str,
                  **kwargs) -> None:
        record = knowledge_v2.make_record(
            feature_id=feature_id, behavior_id=behavior_id, knowledge_type=knowledge_type,
            key=key, content=content, source_references=refs, contract_version=version,
            confidence=confidence, **kwargs)
        candidates.append(record)

    behavior = next(item["behavior"] for item in paths.supported_behaviors()
                    if item["feature_id"] == feature_id and item["behavior_id"] == behavior_id)
    contract_ref = [{"kind": "CONTRACT_REFERENCE", "reference": analysis["contract_reference"]}]
    candidate("CONTRACT_FACT", "expected",
              {"expected": behavior.get("expected") or [],
               "preconditions": behavior.get("preconditions") or []},
              contract_ref, "VERIFIED")

    digest_by_file = {item["path"]: item["digest"] for item in analysis.get("scripts") or []}
    implementation_digest = "".join(item["digest"] for item in analysis.get("scripts") or [])
    if analysis.get("entry_points"):
        refs = []
        for entry in analysis["entry_points"]:
            refs.append({"kind": "SOURCE_REFERENCE",
                         "reference": entry["source_reference"],
                         "digest": digest_by_file.get(entry["file"], "")})
        candidate("SOURCE_OBSERVATION", "entry_points",
                  {"entry_points": analysis["entry_points"],
                   "static_only": True,
                   "note": "静态观察：入口存在不等于运行时被调用"},
                  refs, "HIGH", implementation_digest=implementation_digest)

    if analysis.get("conditions") or analysis.get("failure_paths"):
        refs = [{"kind": "SOURCE_REFERENCE",
                 "reference": "%s:%d" % (item["file"], item["line"]),
                 "digest": digest_by_file.get(item["file"], "")}
                for item in (analysis.get("conditions") or [])[:4]]
        if refs:
            candidate("SOURCE_OBSERVATION", "guards",
                      {"conditions": analysis.get("conditions"),
                       "failure_paths": analysis.get("failure_paths"),
                       "static_only": True}, refs, "MEDIUM")

    if analysis.get("events"):
        refs = [{"kind": "SOURCE_REFERENCE", "reference": "%s:%d" % (item["file"], item["line"])}
                for item in analysis["events"][:4]]
        candidate("SOURCE_OBSERVATION", "events",
                  {"events": analysis["events"], "static_only": True}, refs, "MEDIUM")

    persistence = [item for item in analysis.get("side_effects") or []
                   if item.get("kind") == "file_access"]
    if persistence:
        refs = [{"kind": "SOURCE_REFERENCE", "reference": "%s:%d" % (item["file"], item["line"])}
                for item in persistence]
        candidate("SOURCE_OBSERVATION", "persistence",
                  {"file_access": persistence, "static_only": True}, refs, "HIGH")

    edges = [edge for edge in graph.get("edges") or []
             if edge["source_behavior"] == "%s/%s" % (feature_id, behavior_id)]
    if edges:
        refs = [{"kind": "SOURCE_REFERENCE" if edge["verification_status"] == "SOURCE_OBSERVED"
                 else "CONTRACT_REFERENCE", "reference": edge["source_reference"]}
                for edge in edges[:6]]
        candidate("DEPENDENCY_KNOWLEDGE", "dependencies",
                  {"edges": edges, "count": len(edges)}, refs,
                  "HIGH" if any(edge["verification_status"] == "SOURCE_OBSERVED" for edge in edges)
                  else "MEDIUM")

    evidence = row.get("evidence") or {}
    evaluation = row.get("evaluation") or {}
    if evidence.get("status") == "EVIDENCE_VERIFIED" and evidence.get("bundle"):
        ok, why = _verify_evaluation_attribution(str(evaluation.get("report") or ""), row) \
            if evaluation.get("report") else (False, "no evaluation report")
        refs = [{"kind": "EVIDENCE_REFERENCE", "reference": evidence["bundle"],
                 "digest": evidence.get("bundle_digest", "")},
                {"kind": "CONTRACT_REFERENCE", "reference": analysis["contract_reference"]}]
        candidate("TEST_OBSERVATION", "evidence_run",
                  {"run_id": evidence.get("run_id"),
                   "bundle_digest": evidence.get("bundle_digest"),
                   "signature": (row.get("signature") or {}).get("status"),
                   "evaluation_status": evaluation.get("status"),
                   "evaluation_report": evaluation.get("report"),
                   "attribution": why,
                   "note": "证据来自真实 Godot 采集；评估归属已校验" if ok else
                           "证据真实，但评估报告归属未通过校验，因此不据此下评估结论"},
                  refs, "HIGH", run_id=str(evidence.get("run_id") or ""),
                  evidence_digest=str(evidence.get("bundle_digest") or ""))

    attestation = row.get("attestation") or {}
    if attestation.get("status") == "ATTESTATION_VERIFIED":
        refs = [{"kind": "ATTESTATION_REFERENCE",
                 "reference": str(attestation.get("run_id")),
                 "digest": attestation.get("attestation_digest", "")}]
        candidate("RUNTIME_OBSERVATION", "attestation",
                  {"run_id": attestation.get("run_id"),
                   "attestation_digest": attestation.get("attestation_digest"),
                   "note": "执行证明已验证；完整性不等于执行者身份真实（LOCAL_ISOLATED）"},
                  refs, "HIGH", run_id=str(attestation.get("run_id") or ""))

    mutation = mutations.get((feature_id, behavior_id))
    if mutation is not None:
        verdict = str(mutation.get("verdict"))
        if verdict == "MUTANT_KILLED":
            effectiveness = mutation.get("effectiveness") or {}
            mutation_id = mutation.get("mutation_id")
            refs = [{"kind": "MUTATION_REFERENCE", "reference": mutation.get("_path", "")}]
            candidate("MUTATION_OBSERVATION", "mutation:%s" % mutation_id,
                      {"mutation_id": mutation_id,
                       "mutation_type": mutation.get("mutation_type"),
                       "control": effectiveness.get("control_observation"),
                       "mutant": effectiveness.get("mutant_observation"),
                       "restored_byte_for_byte": (mutation.get("recovery") or {}).get(
                           "restored_byte_for_byte")},
                      refs, "HIGH", run_id=str(mutation.get("run_id")
                                               or mutation_id), mutation_verdict=verdict)
        else:
            refs = [{"kind": "MUTATION_REFERENCE", "reference": mutation.get("_path", "")}]
            candidate("UNKNOWN", "mutation:%s" % mutation.get("mutation_id"),
                      {"verdict": verdict,
                       "note": "mutation 未 KILLED，不能当作有效缺陷知识"},
                      refs, "UNKNOWN", reason="mutation verdict %s" % verdict)

    for index, failure in enumerate(_legacy_failures(feature_id, behavior_id)):
        reference = str(failure.get("source_ref") or failure.get("artifact") or "")
        if not reference:
            continue
        refs = [{"kind": "EVIDENCE_REFERENCE", "reference": reference}]
        candidate("FAILURE_KNOWLEDGE", "legacy_failure:%d" % index,
                  {"scenario": failure.get("scenario"), "root_cause": failure.get("root_cause"),
                   "fix": failure.get("fix"), "status": failure.get("status"),
                   "post_fix_verification": failure.get("post_fix_verification")},
                  refs, "MEDIUM")

    return candidates


def extract_many(pairs: list[tuple[str, str]], *, matrix_path: str,
                 graph_path: str = dependencies.GRAPH_PATH) -> dict:
    matrix = _load_matrix(matrix_path)
    graph = dependencies.load(graph_path) if os.path.isfile(graph_path) else dependencies.build()
    mutations = _mutation_reports()
    analyses = {}
    created = []
    for feature_id, behavior_id in pairs:
        analysis = source_analysis.analyze(feature_id, behavior_id)
        source_analysis.write(analysis)
        analyses["%s/%s" % (feature_id, behavior_id)] = analysis
        for record in extract_behavior(feature_id, behavior_id, matrix=matrix, graph=graph,
                                       analysis=analysis, mutations=mutations):
            created.append(record)
    return {"candidates": created, "analyses": analyses}


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Extract typed behavior knowledge")
    parser.add_argument("--matrix", required=False, default="")
    parser.add_argument("--behaviors", required=True,
                        help="comma separated feature/behavior")
    parser.add_argument("--graph", default=dependencies.GRAPH_PATH)
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args(argv)

    pairs = []
    for item in args.behaviors.split(","):
        feature_id, _, behavior_id = item.strip().partition("/")
        if feature_id and behavior_id:
            pairs.append((feature_id, behavior_id))
    result = extract_many(pairs, matrix_path=args.matrix, graph_path=args.graph)
    stored = 0
    for record in result["candidates"]:
        if args.dry_run:
            continue
        knowledge_v2.add_candidate(record)
        stored += 1
    print(json.dumps({"behaviors": len(pairs),
                      "candidates": len(result["candidates"]),
                      "stored": stored,
                      "dry_run": args.dry_run,
                      "types": _counts(result["candidates"])}, ensure_ascii=False))
    return 0


def _counts(records: list[dict]) -> dict:
    counts: dict[str, int] = {}
    for record in records:
        counts[record["knowledge_type"]] = counts.get(record["knowledge_type"], 0) + 1
    return counts


if __name__ == "__main__":
    raise SystemExit(main())
