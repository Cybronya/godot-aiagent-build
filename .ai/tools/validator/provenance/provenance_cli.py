#!/usr/bin/env python3
"""Provenance CLI：密钥管理、签名与验签（Phase 1.61）。

用法（默认信任根：~/.provenance_trust/trust_root.json，工作区外）：

    python validator/provenance/provenance_cli.py keygen \
        --subject "release-manager" --scopes approve_baseline,issue_evidence
    python validator/provenance/provenance_cli.py status
    python validator/provenance/provenance_cli.py rotate --retire PROVKEY-xxx \
        --subject "release-manager" --scopes approve_baseline
    python validator/provenance/provenance_cli.py revoke --key-id PROVKEY-xxx \
        --reason "key compromised"

    python validator/provenance/provenance_cli.py sign baseline --baseline-id waves \
        --baseline-version 2 --key-id PROVKEY-xxx
    python validator/provenance/provenance_cli.py sign evidence --bundle <path/to/bundle.json> \
        --key-id PROVKEY-xxx
    python validator/provenance/provenance_cli.py sign holdout --holdout-id EVAL160-HOLDOUT \
        --dataset-version 2 --key-id PROVKEY-xxx

    python validator/provenance/provenance_cli.py verify baseline --baseline-id waves \
        --baseline-version 2 [--require-signature]
    python validator/provenance/provenance_cli.py verify evidence --bundle <path> [--require-signature]
    python validator/provenance/provenance_cli.py verify holdout --holdout-id X --dataset-version Y

私钥安全：种子只写入 ~/.provenance_trust/keys/（工作区外，0600），
任何输出（含 --json）都不包含种子内容。
"""

from __future__ import annotations

import argparse
import json
import os
import sys

_HERE = os.path.dirname(os.path.abspath(__file__))
VALIDATOR_DIR = os.path.dirname(_HERE)
_TOOLS_DIR = os.path.dirname(VALIDATOR_DIR)
_EVALUATION_DIR = os.path.join(_TOOLS_DIR, "evaluation")
_SCENE_COMPOSER = os.path.join(_TOOLS_DIR, "scene_composer")
for _path in (VALIDATOR_DIR, _SCENE_COMPOSER, _EVALUATION_DIR):
    if _path not in sys.path:
        sys.path.insert(0, _path)

from provenance import signature_schema as schema                 # noqa: E402
from provenance import signing, verification                      # noqa: E402
from provenance.trust_store import (ENV_TRUST_ROOT, STATUS_ACTIVE,       # noqa: E402
                                    STATUS_REVOKED as STATUS_REVOKED_LOCAL,
                                    TrustStore, TrustStoreError,
                                    default_project_root, derive_key_id,
                                    is_inside_path)

import baseline_lifecycle as bl                                   # noqa: E402
import holdout_registry as hr                                     # noqa: E402

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")

EXIT_OK = 0
EXIT_REJECTED = 1
EXIT_ERROR = 2


def _store(args) -> TrustStore:
    return TrustStore(getattr(args, "trust_root", "") or "",
                      project_root=default_project_root())


def _scopes(text: str) -> list:
    items = [item.strip() for item in str(text or "").split(",") if item.strip()]
    if not items:
        raise SystemExit("--scopes must list at least one of: %s"
                         % ", ".join(schema.SCOPES))
    for item in items:
        if item not in schema.SCOPES:
            raise SystemExit("unknown scope %r (allowed: %s)"
                             % (item, ", ".join(schema.SCOPES)))
    return items


# ---------------------------------------------------------------- keygen 等

def cmd_keygen(args) -> int:
    store = _store(args)
    record = signing.generate_and_register(
        subject=args.subject, scopes=_scopes(args.scopes), trust_store=store,
        project_root=default_project_root())
    print("key_id: %s" % record["key_id"])
    print("status: %s" % record["status"])
    print("subject: %s" % record["subject"])
    print("scopes: %s" % ", ".join(record["scopes"]))
    print("trust_root: %s" % store.trust_root_path())
    print("private seed: %s (outside the workspace; never commit, never log)"
          % os.path.join(store.keys_dir(), "%s.seed" % record["key_id"]))
    return EXIT_OK


def cmd_status(args) -> int:
    store = _store(args)
    summary = store.trust_summary()
    print(json.dumps(summary, ensure_ascii=False, indent=2))
    return EXIT_OK if summary["ok"] else EXIT_ERROR


def cmd_rotate(args) -> int:
    store = _store(args)
    if is_inside_path(store.trust_dir(), default_project_root()):
        raise TrustStoreError("trust root must live outside the project workspace")
    seed_hex = signing.generate_seed_hex()
    public_b64 = signing.seed_to_public_b64(seed_hex)
    new_key_id = derive_key_id(public_b64)
    from provenance.key_metadata import write_seed               # noqa: PLC0415
    write_seed(store.trust_dir(), new_key_id, seed_hex,
               project_root=default_project_root())
    result = store.rotate(public_b64, new_subject=args.subject,
                          new_scopes=_scopes(args.scopes),
                          retiring_key_id=args.retire,
                          reason=args.reason)
    print("rotated: %s -> RETIRED" % args.retire)
    print("activated: %s" % result["activated_key_id"])
    return EXIT_OK


def cmd_revoke(args) -> int:
    store = _store(args)
    record = store.set_key_status(args.key_id, STATUS_REVOKED_LOCAL,
                                  reason=args.reason, source="cli")
    print("revoked: %s at %s" % (record["key_id"], record["status_history"][-1]["at"]))
    return EXIT_OK


# ---------------------------------------------------------------- 签发

def _resolve_baseline(args) -> tuple[dict, dict, dict]:
    registry = bl._load_registry(args.registry_path)
    entry = None
    for item in registry.get("registrations") or []:
        if (str(item.get("baseline_id")) == str(args.baseline_id)
                and str(item.get("baseline_version")) == str(args.baseline_version)):
            entry = item
            break
    if entry is None:
        raise SystemExit("no approval registry entry for %s v%s; approve and "
                         "register the baseline before signing"
                         % (args.baseline_id, args.baseline_version))
    baseline_path = os.path.join(bl.BASELINES_DIR,
                                 "%s.json" % entry["baseline_id"])
    with open(baseline_path, "r", encoding="utf-8") as handle:
        document = json.load(handle)
    computed = bl.content_digest(document)["digest"]
    return entry, document, {"digest": computed,
                             "scheme": bl.DIGEST_SCHEME,
                             "registry": registry, "path": baseline_path}


def cmd_sign_baseline(args) -> int:
    entry, _document, info = _resolve_baseline(args)
    store = _store(args)
    envelope = signing.sign_object(
        object_type=schema.OBJECT_BASELINE,
        object_id=entry["baseline_id"], object_version=entry["baseline_version"],
        content_digest=info["digest"], digest_scheme=info["scheme"],
        key_id=args.key_id, trust_store=store,
        project_root=default_project_root(),
        binding={"approver": entry.get("approver", ""),
                 "approved_at": entry.get("approved_at", ""),
                 "approval_fingerprint": entry.get("approval_fingerprint", ""),
                 "basis": entry.get("basis", "")})
    if entry.get("provenance_signature"):
        print("baseline already carries a provenance signature; refusing to "
              "overwrite silently (rotate/re-sign deliberately via a new key)")
        return EXIT_ERROR
    entry["provenance_signature"] = envelope
    bl._save_registry(info["registry"], args.registry_path)
    print("signed baseline %s v%s (digest %s...) with key %s -> %s"
          % (entry["baseline_id"], entry["baseline_version"],
             info["digest"][:12], args.key_id, bl.REGISTRY_PATH))
    return EXIT_OK


def cmd_sign_evidence(args) -> int:
    with open(args.bundle, "r", encoding="utf-8") as handle:
        document = json.load(handle)
    if document.get("schema") != "feature_behavior_evidence_bundle":
        raise SystemExit("%r is not a feature_behavior_evidence_bundle"
                         % args.bundle)
    digest = verification.recompute_evidence_digest(document)
    store = _store(args)
    envelope = signing.sign_object(
        object_type=schema.OBJECT_EVIDENCE,
        object_id=document.get("bundle_id"),
        object_version=document.get("schema_version"),
        content_digest=digest,
        digest_scheme="evidence-bundle-digest-v1",
        key_id=args.key_id, trust_store=store,
        project_root=default_project_root(),
        binding={"artifact_digests": _artifact_digests(document),
                 "git_head": str(document.get("git_head") or ""),
                 "generated_at": str(document.get("generated_at") or ""),
                 "collector": str((document.get("tool") or {}).get("module") or ""),
                 "note": "collector-run signature; does not prove execution "
                         "authenticity beyond collector honesty"})
    target = verification.write_sidecar(args.bundle, envelope)
    print("signed evidence bundle %r (digest %s...) with key %s -> %s"
          % (document.get("bundle_id"), digest[:12], args.key_id, target))
    return EXIT_OK


def _artifact_digests(document: dict) -> dict:
    digests = {}
    for block in document.get("features") or []:
        for record in block.get("behaviors") or []:
            for run_id, value in (record.get("artifact_digests") or {}).items():
                digests[str(run_id)] = {key: str(item)
                                        for key, item in dict(value).items()}
    return digests


def _resolve_holdout(args) -> tuple[dict, dict, dict]:
    registry = hr._load_registry(args.registry_path)
    record = None
    for item in registry.get("datasets") or []:
        if (str(item.get("holdout_id")) == str(args.holdout_id)
                and str(item.get("dataset_version")) == str(args.dataset_version)):
            record = item
            break
    if record is None:
        raise SystemExit("no holdout dataset %s v%s registered"
                         % (args.holdout_id, args.dataset_version))
    return record, registry, {"scheme": record.get("digest_scheme") or ""}


def cmd_sign_holdout(args) -> int:
    record, registry, info = _resolve_holdout(args)
    if not record.get("content_digest"):
        raise SystemExit("holdout %s v%s has no sealed content digest; "
                         "seal it before signing"
                         % (args.holdout_id, args.dataset_version))
    if record.get("provenance_signature"):
        print("holdout already carries a provenance signature; refusing to "
              "overwrite silently")
        return EXIT_ERROR
    store = _store(args)
    envelope = signing.sign_object(
        object_type=schema.OBJECT_HOLDOUT,
        object_id=record["holdout_id"], object_version=record["dataset_version"],
        content_digest=record["content_digest"], digest_scheme=info["scheme"],
        key_id=args.key_id, trust_store=store,
        project_root=default_project_root(),
        binding={"source": record.get("source", ""),
                 "created_at": record.get("created_at", ""),
                 "sealed_at": record.get("sealed_at", ""),
                 "feature_ids": list(record.get("feature_ids") or []),
                 "behavior_ids": list(record.get("behavior_ids") or []),
                 "dataset_files": record.get("dataset_files")})
    record["provenance_signature"] = envelope
    hr._save_registry(registry, args.registry_path)
    print("signed holdout %s v%s (digest %s...) with key %s -> %s"
          % (record["holdout_id"], record["dataset_version"],
             record["content_digest"][:12], args.key_id, hr.REGISTRY_PATH))
    return EXIT_OK


# ---------------------------------------------------------------- 验证

def cmd_verify_baseline(args) -> int:
    entry, document, info = _resolve_baseline(args)
    store = _store(args)
    policy = (verification.POLICY_REQUIRE_SIGNATURE if args.require_signature
              else verification.POLICY_ALLOW_LEGACY)
    envelope = entry.get("provenance_signature")
    evaluated = verification.evaluate_signature(
        envelope, object_type=schema.OBJECT_BASELINE,
        object_id=document.get("scenario_id"),
        object_version=document.get("baseline_version"),
        expected_digest=info["digest"],
        expected_digest_scheme=info["scheme"],
        trust_store=store, signature_policy=policy)
    print(json.dumps({"baseline_id": entry["baseline_id"],
                      "baseline_version": entry["baseline_version"],
                      "policy": policy,
                      "trust_level": evaluated["trust_level"],
                      "usable": evaluated["usable"],
                      "verification": evaluated["verification"]},
                     ensure_ascii=False, indent=2))
    return EXIT_OK if evaluated["usable"] else EXIT_REJECTED


def cmd_verify_evidence(args) -> int:
    with open(args.bundle, "r", encoding="utf-8") as handle:
        document = json.load(handle)
    store = _store(args)
    policy = (verification.POLICY_REQUIRE_SIGNATURE if args.require_signature
              else verification.POLICY_ALLOW_LEGACY)
    evaluated = verification.verify_evidence_bundle(
        args.bundle, document, trust_store=store, signature_policy=policy)
    print(json.dumps({"bundle": args.bundle,
                      "bundle_id": document.get("bundle_id"),
                      "policy": policy,
                      "trust_level": evaluated["trust_level"],
                      "usable": evaluated["usable"],
                      "verification": evaluated["verification"]},
                     ensure_ascii=False, indent=2))
    return EXIT_OK if evaluated["usable"] else EXIT_REJECTED


def cmd_verify_holdout(args) -> int:
    record, _registry, info = _resolve_holdout(args)
    store = _store(args)
    policy = (verification.POLICY_REQUIRE_SIGNATURE if args.require_signature
              else verification.POLICY_ALLOW_LEGACY)
    evaluated = verification.evaluate_signature(
        record.get("provenance_signature"),
        object_type=schema.OBJECT_HOLDOUT,
        object_id=record["holdout_id"], object_version=record["dataset_version"],
        expected_digest=record.get("content_digest") or "",
        expected_digest_scheme=info["scheme"],
        trust_store=store, signature_policy=policy)
    print(json.dumps({"holdout_id": record["holdout_id"],
                      "dataset_version": record["dataset_version"],
                      "policy": policy,
                      "trust_level": evaluated["trust_level"],
                      "usable": evaluated["usable"],
                      "verification": evaluated["verification"]},
                     ensure_ascii=False, indent=2))
    return EXIT_OK if evaluated["usable"] else EXIT_REJECTED


# ---------------------------------------------------------------- argparse

def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__,
                                     formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--trust-root", default="",
                        help="external trust root path (outside the workspace; "
                             "default: ~/.provenance_trust/trust_root.json or "
                             "$%s)" % ENV_TRUST_ROOT)
    sub = parser.add_subparsers(dest="command", required=True)

    keygen = sub.add_parser("keygen", help="generate a keypair: seed -> trust "
                                           "dir (outside workspace), public key -> trust root")
    keygen.add_argument("--subject", required=True)
    keygen.add_argument("--scopes", required=True,
                        help="comma-separated: %s" % ", ".join(schema.SCOPES))
    keygen.set_defaults(func=cmd_keygen)

    status = sub.add_parser("status", help="print trust root summary")
    status.set_defaults(func=cmd_status)

    rotate = sub.add_parser("rotate", help="add a new ACTIVE key and RETIRE the old one")
    rotate.add_argument("--retire", required=True, help="key_id to retire")
    rotate.add_argument("--subject", required=True)
    rotate.add_argument("--scopes", required=True)
    rotate.add_argument("--reason", default="rotated")
    rotate.set_defaults(func=cmd_rotate)

    revoke = sub.add_parser("revoke", help="revoke a key (REVOKED is final)")
    revoke.add_argument("--key-id", required=True)
    revoke.add_argument("--reason", default="")
    revoke.set_defaults(func=cmd_revoke)

    sign = sub.add_parser("sign", help="sign a baseline / evidence bundle / holdout dataset")
    sign_sub = sign.add_subparsers(dest="object", required=True)
    for name in ("baseline", "evidence", "holdout"):
        sub_parser = sign_sub.add_parser(name)
        sub_parser.add_argument("--key-id", required=True)
        if name == "baseline":
            sub_parser.add_argument("--baseline-id", required=True)
            sub_parser.add_argument("--baseline-version", required=True)
            sub_parser.add_argument("--registry-path", default="")
            sub_parser.set_defaults(func=cmd_sign_baseline)
        elif name == "evidence":
            sub_parser.add_argument("--bundle", required=True)
            sub_parser.set_defaults(func=cmd_sign_evidence)
        else:
            sub_parser.add_argument("--holdout-id", required=True)
            sub_parser.add_argument("--dataset-version", required=True)
            sub_parser.add_argument("--registry-path", default="")
            sub_parser.set_defaults(func=cmd_sign_holdout)

    verify = sub.add_parser("verify", help="verify a signature (exit 1 = rejected)")
    verify_sub = verify.add_subparsers(dest="object", required=True)
    for name in ("baseline", "evidence", "holdout"):
        sub_parser = verify_sub.add_parser(name)
        sub_parser.add_argument("--require-signature", action="store_true",
                                help="fail closed when no signature is present")
        if name == "baseline":
            sub_parser.add_argument("--baseline-id", required=True)
            sub_parser.add_argument("--baseline-version", required=True)
            sub_parser.add_argument("--registry-path", default="")
            sub_parser.set_defaults(func=cmd_verify_baseline)
        elif name == "evidence":
            sub_parser.add_argument("--bundle", required=True)
            sub_parser.set_defaults(func=cmd_verify_evidence)
        else:
            sub_parser.add_argument("--holdout-id", required=True)
            sub_parser.add_argument("--dataset-version", required=True)
            sub_parser.add_argument("--registry-path", default="")
            sub_parser.set_defaults(func=cmd_verify_holdout)
    return parser


def main(argv=None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    try:
        return args.func(args)
    except TrustStoreError as exc:
        print("ERROR: %s" % exc, file=sys.stderr)
        return EXIT_ERROR


if __name__ == "__main__":
    sys.exit(main())
