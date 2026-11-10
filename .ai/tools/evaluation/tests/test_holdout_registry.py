#!/usr/bin/env python3
"""Holdout 数据集生命周期与隔离测试（Phase 1.60，任务书 §8.3）。

被测对象：`.ai/tools/evaluation/holdout_registry.py`

覆盖矩阵：
    A. 生命周期
      A1 CREATED -> VALIDATED -> SEALED -> CONSUMED 合法
      A2 CREATED -> SEALED 跳步被拒
      A3 INVALIDATED 是终态
      A4 未知 id 被拒
    B. 使用时复核（check_usable）
      B1 SEALED 且摘要一致 -> usable
      B2 CONSUMED 不可直接复用（重复消费防护）
      B3 INVALIDATED（污染）不可用
      B4 内容被修改 -> 摘要不匹配拒绝
      B5 is_training_data / is_tuning_data 被标记 -> 拒绝（恒 False，防御字段篡改）
      B6 无摘要（未封存）拒绝
    C. 使用记录
      C1 record_usage 追加 usage_history 并转 CONSUMED
      C2 不可用时 record_usage 被拒（无记录）
      C3 reuse_policy：CONSUMED 后不允许静默重用
    D. 污染与隔离
      D1 与训练数据重叠 -> INVALIDATED 后拒绝
      D2 与 Baseline 生成数据重叠 -> 记录污染并拒绝
      D3 与 evidence_adapter.holdout_isolation 的批次隔离叠加（同一批次两边用 -> 违规）
    E. 真实数据分类边界
      E1 is_training_data / is_tuning_data 字段恒为 False（登记与复核一致）

用法：python .ai/tools/evaluation/tests/test_holdout_registry.py
"""

from __future__ import annotations

import os
import shutil
import sys
import tempfile

_HERE = os.path.dirname(os.path.abspath(__file__))
EVAL_DIR = os.path.dirname(_HERE)
PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(EVAL_DIR)))
for _path in (EVAL_DIR, os.path.join(PROJECT_ROOT, ".ai", "tools", "validator")):
    if _path not in sys.path:
        sys.path.insert(0, _path)

import holdout_registry as hr                                  # noqa: E402

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")

_checks = 0
_failures: list = []


def ok(label: str, condition: bool, detail: str = "") -> None:
    global _checks
    _checks += 1
    if condition:
        print("PASS: %s" % label)
    else:
        _failures.append(label)
        print("FAIL: %s  %s" % (label, detail[:300]))


def expect_error(label: str, fn, *args, **kwargs) -> None:
    try:
        fn(*args, **kwargs)
        ok(label, False, "expected HoldoutError, none raised")
    except hr.HoldoutError as exc:
        ok(label, True, str(exc))
    except Exception as exc:                                  # noqa: BLE001
        ok(label, False, "unexpected %s: %s" % (type(exc).__name__, exc))


_TMP_ROOT = None
_counter = 0


def new_dir(prefix: str) -> str:
    global _TMP_ROOT
    if _TMP_ROOT is None:
        _TMP_ROOT = tempfile.mkdtemp(prefix="p160-holdout-")
    return tempfile.mkdtemp(prefix=prefix, dir=_TMP_ROOT)


def dataset_files(directory: str, contents: dict) -> list:
    paths = []
    for name, text in contents.items():
        path = os.path.join(directory, name)
        with open(path, "w", encoding="utf-8") as handle:
            handle.write(text)
        paths.append(path)
    return paths


def make_dataset(registry: str, *, holdout_id: str = "H1", version: str = "1",
                 files: dict | None = None) -> tuple:
    root = new_dir("ds-")
    paths = dataset_files(root, files or {"bundle_a.json": '{"x": 1}',
                                          "bundle_b.json": '{"y": 2}'})
    hr.create_dataset(holdout_id, version, source="test fixture",
                      feature_ids=["health"], behavior_ids=["damage"],
                      registry_path=registry)
    hr.validate_dataset(holdout_id, version, evidence_paths=paths, registry_path=registry)
    hr.seal_dataset(holdout_id, version, evidence_paths=paths, registry_path=registry)
    record = hr.find_dataset(holdout_id, version, registry_path=registry)
    return record, paths, root


def test_lifecycle() -> None:
    registry = os.path.join(new_dir("lc-"), "registry.json")
    record, paths, root = make_dataset(registry)
    ok("A1: CREATED -> VALIDATED -> SEALED -> usable",
       record["status"] == hr.SEALED and record["content_digest"], str(record["status"]))

    expect_error("A2: CREATED -> SEALED skips a step",
                 hr.seal_dataset, "H2", "1", evidence_paths=paths,
                 registry_path=registry)
    hr.create_dataset("H2", "1", source="x", feature_ids=["health"], behavior_ids=["damage"],
                      registry_path=registry)
    expect_error("A2b: CREATED -> SEALED for a fresh dataset is rejected",
                 hr.seal_dataset, "H2", "1", evidence_paths=[], registry_path=registry)

    hr.invalidate_dataset("H2", "1", reason="manual_invalidation",
                          registry_path=registry)
    record = hr.find_dataset("H2", "1", registry_path=registry)
    ok("A3: INVALIDATED is terminal", record["status"] == hr.INVALIDATED)
    expect_error("A3b: INVALIDATED cannot be sealed",
                 hr.seal_dataset, "H2", "1", evidence_paths=[], registry_path=registry)

    expect_error("A4: unknown id rejected",
                 hr.seal_dataset, "NOPE", "1", evidence_paths=[], registry_path=registry)


def test_usable() -> None:
    registry = os.path.join(new_dir("us-"), "registry.json")
    record, paths, root = make_dataset(registry)
    ok("B1: SEALED + digest match -> usable",
       hr.check_usable(record, evidence_paths=paths)["usable"])

    hr.record_usage("H1", "1", purpose="evaluation", run_ref="run-1",
                    registry_path=registry)
    record = hr.find_dataset("H1", "1", registry_path=registry)
    check = hr.check_usable(record, evidence_paths=paths)
    ok("B2: CONSUMED cannot be reused directly",
       check["usable"] is False and record["status"] == hr.CONSUMED, str(check))
    ok("B2b: usage history kept", len(record["usage_history"]) == 1)

    hr.invalidate_dataset("H1", "1", reason="overlap_with_training",
                          registry_path=registry)
    record = hr.find_dataset("H1", "1", registry_path=registry)
    ok("B3: invalidated (polluted) holdout rejected",
       hr.check_usable(record)["usable"] is False)

    registry2 = os.path.join(new_dir("us2-"), "registry.json")
    record, paths, root = make_dataset(registry2)
    tampered = dataset_files(root, {"bundle_a.json": '{"x": 999}',
                                    "bundle_b.json": '{"y": 2}'})
    check = hr.check_usable(record, evidence_paths=tampered)
    ok("B4: modified content -> digest mismatch",
       check["usable"] is False and "changed after sealing" in check["reason"],
       str(check))

    forged = dict(record)
    forged["is_training_data"] = True
    ok("B5a: flagged training data rejected", hr.check_usable(forged)["usable"] is False)
    forged = dict(record)
    forged["is_tuning_data"] = True
    ok("B5b: flagged tuning data rejected", hr.check_usable(forged)["usable"] is False)

    registry3 = os.path.join(new_dir("us3-"), "registry.json")
    fresh, fresh_paths, _root3 = make_dataset(registry3)
    unsealed = dict(fresh)
    unsealed["content_digest"] = ""
    ok("B6: no sealed digest rejected", hr.check_usable(unsealed)["usable"] is False)


def test_usage() -> None:
    registry = os.path.join(new_dir("ug-"), "registry.json")
    record, paths, root = make_dataset(registry)
    hr.record_usage("H1", "1", purpose="evaluation", run_ref="run-A",
                    registry_path=registry)
    record = hr.find_dataset("H1", "1", registry_path=registry)
    ok("C1: usage appended and status -> CONSUMED",
       len(record["usage_history"]) == 1 and record["status"] == hr.CONSUMED)

    expect_error("C2: record_usage on unusable holdout rejected",
                 hr.record_usage, "H1", "1", purpose="evaluation",
                 registry_path=registry)
    policy = hr.reuse_policy_check(record)
    ok("C3: consumed holdout is not silently reusable",
       policy["allow_reuse"] is False, str(policy))


def test_pollution() -> None:
    registry = os.path.join(new_dir("pol-"), "registry.json")
    record, paths, root = make_dataset(registry)
    hr.invalidate_dataset("H1", "1", reason="overlap_with_training",
                          registry_path=registry)
    record = hr.find_dataset("H1", "1", registry_path=registry)
    ok("D1: training overlap recorded and rejected",
       record["pollution"][0]["reason"] == "overlap_with_training"
       and hr.check_usable(record)["usable"] is False)

    hr.create_dataset("H2", "1", source="x", feature_ids=["health"], behavior_ids=["damage"],
                      registry_path=registry)
    hr.validate_dataset("H2", "1", evidence_paths=paths, registry_path=registry)
    hr.seal_dataset("H2", "1", evidence_paths=paths, registry_path=registry)
    hr.invalidate_dataset("H2", "1", reason="overlap_with_baseline_source",
                          registry_path=registry)
    record = hr.find_dataset("H2", "1", registry_path=registry)
    ok("D2: baseline-source overlap recorded and rejected",
       record["pollution"][0]["reason"] == "overlap_with_baseline_source"
       and hr.check_usable(record)["usable"] is False)

    # D3: 与 evidence_adapter.holdout_isolation 的批次隔离叠加
    import evidence_adapter as adapter
    same_batch = {"bundle_index": [{"bundle_id": "b-1"}],
                  "behaviors": [{"execution": {"run_id": "r-1"}}]}
    violations = adapter.holdout_isolation(same_batch, same_batch)
    ok("D3: same batch on both sides -> isolation violation", len(violations) >= 1,
       str(violations))
    other = {"bundle_index": [{"bundle_id": "b-2"}],
             "behaviors": [{"execution": {"run_id": "r-2"}}]}
    ok("D3b: disjoint batches -> no violation",
       adapter.holdout_isolation(same_batch, other) == [])


def test_data_classification() -> None:
    registry = os.path.join(new_dir("cls-"), "registry.json")
    record, paths, root = make_dataset(registry)
    ok("E1: registered holdout is never training/tuning data",
       record["is_training_data"] is False and record["is_tuning_data"] is False)
    check = hr.check_usable(record, evidence_paths=paths)
    ok("E1b: usable holdout keeps classification False",
       check["usable"] and record["is_training_data"] is False)


def cleanup() -> None:
    if _TMP_ROOT and os.path.isdir(_TMP_ROOT):
        shutil.rmtree(_TMP_ROOT, ignore_errors=True)


def main() -> int:
    test_lifecycle()
    test_usable()
    test_usage()
    test_pollution()
    test_data_classification()
    cleanup()
    print("\n%d check(s), %d failure(s)" % (_checks, len(_failures)))
    if _failures:
        print("FAIL: " + "; ".join(_failures[:5]))
        return 1
    print("ALL PASS")
    return 0


if __name__ == "__main__":
    sys.exit(main())
