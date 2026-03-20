#!/usr/bin/env python3
"""Minimal local UNO runtime for tranche 6.

This runtime stays fully offline/local and keeps the public-key signature flow
with Ed25519 through the Python `cryptography` (PyCA) library.

Tranche 6 adds a portable external witness path:
- the agent runtime stays separate from the witness component
- the witness has its own Ed25519 identity and key
- witness receipts can be produced offline from a file/CLI flow
- verify now distinguishes local receipts from external witness receipts
"""

from __future__ import annotations

import argparse
import base64
import copy
import getpass
import hashlib
import json
import os
import socket
import subprocess
import sys
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey
from cryptography.hazmat.primitives import serialization
from cryptography.exceptions import InvalidSignature


RUNTIME_VERSION = "0.3.0"
UNO_SPEC_VERSION = "1.0.0"
SIGNATURE_ALGORITHM = "ed25519"
DIGEST_ALGORITHM = "sha-256"
STATE_ROOT = Path("runtime/state")
DEFAULT_WITNESS = None
LOCAL_RECEIPT_TYPE = "local-inline"
EXTERNAL_RECEIPT_TYPE = "external"
EXTERNAL_WITNESS_PROOF = "portable-offline-cli"
BUILD_MANIFEST_VERSION = "uno-build-manifest-1"
BUILD_ATTESTATION_TYPE = "uno-build-attestation-1"
SIGNATURE_NOTE = "Ed25519 signatures produced locally with the cryptography (PyCA) library; no network service required."


def canonical_json(value: Any) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=True)


def sha256_hex(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def digest_object(value: Any) -> dict[str, str]:
    return {"algorithm": DIGEST_ALGORITHM, "value": sha256_hex(canonical_json(value).encode("utf-8"))}


def signed_payload(value: Any) -> bytes:
    return canonical_json(value).encode("utf-8")


def now_iso() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def bundle_now() -> str:
    return now_iso()


def ensure_dir(path: Path) -> None:
    path.mkdir(parents=True, exist_ok=True)


def write_json(path: Path, value: Any) -> None:
    ensure_dir(path.parent)
    path.write_text(json.dumps(value, indent=2, sort_keys=True, ensure_ascii=True) + "\n", encoding="utf-8")


def read_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def write_text(path: Path, value: str) -> None:
    ensure_dir(path.parent)
    path.write_text(value, encoding="utf-8")


def read_text(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def relative_display_path(path: Path) -> str:
    try:
        return path.resolve().relative_to(Path.cwd().resolve()).as_posix()
    except ValueError:
        return path.resolve().as_posix()


def slugify(value: str) -> str:
    safe = []
    for char in value.lower():
        if char.isalnum():
            safe.append(char)
        else:
            safe.append("-")
    collapsed = "".join(safe).strip("-")
    while "--" in collapsed:
        collapsed = collapsed.replace("--", "-")
    return collapsed or "agent"


def short_id(prefix: str) -> str:
    return f"{prefix}:{uuid.uuid4().hex}"


def make_taxonomy(kind: str, role: str, context: str) -> list[dict[str, Any]]:
    return [
        {"namespace": "uno.taxonomy", "path": ["kind", kind], "label": kind, "version": "v1"},
        {"namespace": "uno.taxonomy", "path": ["role", role], "label": role, "version": "v1"},
        {"namespace": "uno.taxonomy", "path": ["context", context], "label": context, "version": "v1"},
    ]


def taxonomy_state(taxonomy: list[dict[str, Any]]) -> dict[str, str]:
    state: dict[str, str] = {}
    for ref in taxonomy:
        path = ref.get("path") or []
        if len(path) >= 2 and path[0] in {"kind", "role", "context"}:
            state[path[0]] = path[1]
    return state


def object_without_signature(obj: dict[str, Any]) -> dict[str, Any]:
    payload = copy.deepcopy(obj)
    payload.pop("signature", None)
    return payload


def object_digest(obj: dict[str, Any]) -> dict[str, str]:
    return digest_object(object_without_signature(obj))


def digest_paths(paths: list[Path]) -> dict[str, Any] | None:
    if not paths:
        return None

    entries = []
    for path in sorted(paths, key=lambda item: relative_display_path(item)):
        entries.append({"path": relative_display_path(path), "sha256": sha256_hex(path.read_bytes())})
    return {
        "algorithm": DIGEST_ALGORITHM,
        "value": sha256_hex(canonical_json(entries).encode("utf-8")),
        "files": [entry["path"] for entry in entries],
    }


def default_builder() -> str:
    return f"{getpass.getuser()}@{socket.gethostname()}"


def generate_ed25519_keypair() -> tuple[str, str]:
    """Generate an Ed25519 keypair using the cryptography (PyCA) library.

    Returns a tuple of (private_key_pem, public_key_pem) as strings,
    in PKCS8/SubjectPublicKeyInfo PEM format — compatible with the prior openssl CLI output.
    """
    private_key = Ed25519PrivateKey.generate()
    private_key_pem = private_key.private_bytes(
        encoding=serialization.Encoding.PEM,
        format=serialization.PrivateFormat.PKCS8,
        encryption_algorithm=serialization.NoEncryption(),
    ).decode("utf-8")
    public_key_pem = private_key.public_key().public_bytes(
        encoding=serialization.Encoding.PEM,
        format=serialization.PublicFormat.SubjectPublicKeyInfo,
    ).decode("utf-8")
    return private_key_pem, public_key_pem


def key_fingerprint(public_key_pem: str) -> str:
    return sha256_hex(public_key_pem.encode("utf-8"))


def key_descriptor(key_id: str, public_key_pem: str, status: str = "active", valid_from: str | None = None) -> dict[str, Any]:
    descriptor = {
        "id": key_id,
        "algorithm": SIGNATURE_ALGORITHM,
        "publicKey": public_key_pem,
        "status": status,
        "fingerprint": key_fingerprint(public_key_pem),
    }
    if valid_from:
        descriptor["validFrom"] = valid_from
    return descriptor


def external_witness_key_lookup(receipt: dict[str, Any]) -> dict[str, dict[str, Any]]:
    witness_key = receipt.get("witnessPublicKey")
    if not isinstance(witness_key, dict):
        return {}
    key_id = witness_key.get("id")
    if not key_id:
        return {}
    return {key_id: witness_key}


def is_external_receipt(receipt: dict[str, Any]) -> bool:
    return receipt.get("receiptType") == EXTERNAL_RECEIPT_TYPE or isinstance(receipt.get("witnessPublicKey"), dict)


def sign_bytes(private_key_pem: str, data: bytes) -> str:
    """Sign raw bytes with an Ed25519 private key (PEM).

    Returns the base64-encoded signature string (same format as before).
    """
    private_key = serialization.load_pem_private_key(private_key_pem.encode("utf-8"), password=None)
    signature = private_key.sign(data)
    return base64.b64encode(signature).decode("ascii")


def verify_signature_with_public_key(public_key_pem: str, data: bytes, signature_b64: str) -> bool:
    """Verify an Ed25519 signature using the cryptography (PyCA) library.

    Returns True if the signature is valid, False otherwise.
    """
    try:
        signature = base64.b64decode(signature_b64.encode("ascii"), validate=True)
    except Exception:
        return False

    try:
        public_key = serialization.load_pem_public_key(public_key_pem.encode("utf-8"))
        public_key.verify(signature, data)
        return True
    except (InvalidSignature, Exception):
        return False


def sign_object(private_key_pem: str, value: Any) -> str:
    return sign_bytes(private_key_pem, signed_payload(value))


def state_paths(state_dir: Path) -> dict[str, Path]:
    return {
        "state_dir": state_dir,
        "agent": state_dir / "agent.json",
        "private_key": state_dir / "private_key.pem",
        "events": state_dir / "continuity_events.json",
        "lineage": state_dir / "lineage_links.json",
        "assertions": state_dir / "assertions.json",
        "receipts": state_dir / "witness_receipts.json",
    }


def load_state(state_dir: Path) -> dict[str, Any]:
    paths = state_paths(state_dir)
    if not paths["agent"].exists():
        raise SystemExit(f"State not found: {state_dir}")
    return {
        "agent": read_json(paths["agent"]),
        "private_key": read_text(paths["private_key"]),
        "events": read_json(paths["events"]),
        "lineage": read_json(paths["lineage"]),
        "assertions": read_json(paths["assertions"]),
        "receipts": read_json(paths["receipts"]),
        "paths": paths,
    }


def save_state(state: dict[str, Any]) -> None:
    paths = state["paths"]
    write_json(paths["agent"], state["agent"])
    write_text(paths["private_key"], state["private_key"])
    write_json(paths["events"], state["events"])
    write_json(paths["lineage"], state["lineage"])
    write_json(paths["assertions"], state["assertions"])
    write_json(paths["receipts"], state["receipts"])


def key_lookup(agent: dict[str, Any]) -> dict[str, dict[str, Any]]:
    return {key["id"]: key for key in agent.get("keys", [])}


def current_key(agent: dict[str, Any]) -> dict[str, Any]:
    for key in agent["keys"]:
        if key.get("status", "active") == "active":
            return key
    raise SystemExit("No active key on agent")


def timestamp_in_key_validity(key: dict[str, Any], timestamp: str) -> bool:
    valid_from = key.get("validFrom")
    valid_until = key.get("validUntil")
    if valid_from and timestamp < valid_from:
        return False
    if valid_until and timestamp > valid_until:
        return False
    return True


def make_signature(key_id: str, private_key_pem: str, obj: dict[str, Any]) -> dict[str, str]:
    unsigned = object_without_signature(obj)
    return {
        "keyId": key_id,
        "algorithm": SIGNATURE_ALGORITHM,
        "value": sign_object(private_key_pem, unsigned),
    }


def append_receipt(
    receipts: list[dict[str, Any]],
    agent: dict[str, Any],
    private_key_pem: str,
    event: dict[str, Any],
    witness: str,
    key_id: str | None = None,
) -> dict[str, Any]:
    signing_key_id = key_id or current_key(agent)["id"]
    receipt = {
        "id": short_id("uno:receipt"),
        "receiptType": LOCAL_RECEIPT_TYPE,
        "eventId": event["id"],
        "witness": witness,
        "observedAt": now_iso(),
        "eventDigest": object_digest(event),
        "receiptIndex": len(receipts),
    }
    receipt["signature"] = {
        "keyId": signing_key_id,
        "algorithm": SIGNATURE_ALGORITHM,
        "value": sign_object(private_key_pem, object_without_signature(receipt)),
    }
    receipts.append(receipt)
    return receipt


def build_manifest(args: argparse.Namespace) -> dict[str, Any]:
    code_paths = [Path(item) for item in (args.code_path or [__file__])]
    config_paths = [Path(item) for item in (args.config_path or [])]

    missing = [str(path) for path in code_paths + config_paths if not path.exists()]
    if missing:
        raise SystemExit(f"Missing input files for build manifest: {', '.join(missing)}")

    manifest = {
        "version": BUILD_MANIFEST_VERSION,
        "codeHash": digest_paths(code_paths),
        "built_at": args.built_at or now_iso(),
        "builder": args.builder or default_builder(),
    }
    config_hash = digest_paths(config_paths)
    if config_hash is not None:
        manifest["configHash"] = config_hash

    if args.output:
        write_json(Path(args.output), manifest)

    return {"command": "build-manifest", "output": args.output, "manifest": manifest}


def build_attestation_from_manifest(manifest: dict[str, Any]) -> dict[str, Any]:
    return {
        "type": BUILD_ATTESTATION_TYPE,
        "attestedAt": bundle_now(),
        "manifest": manifest,
        "manifestDigest": digest_object(manifest),
        "note": "Local build coherence only. No TEE or strong remote attestation.",
    }


def compare_manifests(provided: dict[str, Any], expected: dict[str, Any]) -> list[str]:
    mismatches: list[str] = []
    keys = sorted(set(provided) | set(expected))
    for key in keys:
        if provided.get(key) != expected.get(key):
            mismatches.append(key)
    return mismatches


def init_agent(args: argparse.Namespace) -> dict[str, Any]:
    created_at = now_iso()
    private_key_pem, public_key_pem = generate_ed25519_keypair()
    agent_id = f"uno:agent:{uuid.uuid4().hex}"
    key_id = f"{agent_id}#key-1"
    taxonomy = make_taxonomy(args.kind, args.role, args.context)
    agent = {
        "id": agent_id,
        "controller": args.controller,
        "displayName": args.display_name,
        "keys": [key_descriptor(key_id, public_key_pem, status="active", valid_from=created_at)],
        "taxonomy": taxonomy,
        "lineageRoot": agent_id,
        "createdAt": created_at,
        "updatedAt": created_at,
        "status": "active",
        "metadata": {
            "runtime": "uno-local-demo",
            "runtimeVersion": RUNTIME_VERSION,
            "signatureScheme": SIGNATURE_ALGORITHM,
            "signatureRuntime": "cryptography-pyca",
            "signatureNote": SIGNATURE_NOTE,
        },
    }

    event = {
        "id": short_id("uno:event"),
        "agentId": agent_id,
        "sequence": 0,
        "eventType": "inception",
        "previousEventDigest": None,
        "payloadDigest": digest_object(
            {
                "agentId": agent_id,
                "taxonomy": taxonomy,
                "lineageRoot": agent_id,
                "status": "active",
                "note": args.note or "Local inception",
            }
        ),
        "anchors": [],
        "lineageLinks": [],
        "taxonomySnapshot": taxonomy,
        "recordedAt": created_at,
    }
    event["signature"] = make_signature(key_id, private_key_pem, event)

    state_dir = Path(args.state_dir) if args.state_dir else STATE_ROOT / slugify(args.slug or args.display_name or agent_id)
    paths = state_paths(state_dir)
    ensure_dir(state_dir)
    state = {
        "agent": agent,
        "private_key": private_key_pem,
        "events": [event],
        "lineage": [],
        "assertions": [],
        "receipts": [],
        "paths": paths,
    }
    if args.witness:
        append_receipt(state["receipts"], agent, private_key_pem, event, args.witness)
    save_state(state)
    return {"command": "init-agent", "agentId": agent_id, "stateDir": str(state_dir), "eventId": event["id"]}


def append_event(args: argparse.Namespace) -> dict[str, Any]:
    state = load_state(Path(args.state_dir))
    agent = state["agent"]
    private_key_pem = state["private_key"]
    events = state["events"]
    lineage = state["lineage"]
    receipts = state["receipts"]

    if agent.get("status") == "revoked":
        raise SystemExit("Cannot append new continuity events: agent status is revoked.")

    previous = events[-1]
    active_key = current_key(agent)

    taxonomy = agent["taxonomy"]
    if args.kind or args.role or args.context:
        current = taxonomy_state(agent["taxonomy"])
        taxonomy = make_taxonomy(
            args.kind or current.get("kind", "agent"),
            args.role or current.get("role", "unknown"),
            args.context or current.get("context", "unknown"),
        )
        agent["taxonomy"] = taxonomy
        agent["updatedAt"] = now_iso()

    lineage_ids: list[str] = []
    if args.relation or args.source_agent_id:
        if not args.relation or not args.source_agent_id:
            raise SystemExit("--relation and --source-agent-id must be provided together")
        link = {
            "id": short_id("uno:lineage"),
            "sourceAgentId": args.source_agent_id,
            "targetAgentId": agent["id"],
            "relation": args.relation,
            "taxonomyInheritance": args.taxonomy_inheritance,
            "assertedAt": now_iso(),
        }
        if args.note:
            link["notes"] = args.note
        lineage.append(link)
        lineage_ids.append(link["id"])

    payload = {
        "note": args.note or "",
        "taxonomy": taxonomy,
        "lineageLinks": lineage_ids,
        "status": agent["status"],
    }
    event = {
        "id": short_id("uno:event"),
        "agentId": agent["id"],
        "sequence": previous["sequence"] + 1,
        "eventType": args.event_type,
        "previousEventDigest": object_digest(previous),
        "payloadDigest": digest_object(payload),
        "anchors": [],
        "lineageLinks": lineage_ids,
        "taxonomySnapshot": taxonomy,
        "recordedAt": now_iso(),
    }
    event["signature"] = make_signature(active_key["id"], private_key_pem, event)
    events.append(event)
    if args.witness:
        append_receipt(receipts, agent, private_key_pem, event, args.witness)
    save_state(state)
    return {
        "command": "append-event",
        "agentId": agent["id"],
        "eventId": event["id"],
        "sequence": event["sequence"],
        "stateDir": str(state["paths"]["state_dir"]),
    }


def revoke_agent(args: argparse.Namespace) -> dict[str, Any]:
    state = load_state(Path(args.state_dir))
    agent = state["agent"]
    if agent.get("status") == "revoked":
        raise SystemExit("Agent is already revoked.")

    private_key_pem = state["private_key"]
    events = state["events"]
    receipts = state["receipts"]
    previous = events[-1]
    active_key = current_key(agent)
    revoked_at = now_iso()

    payload = {
        "note": args.reason or "Local revocation",
        "status": "revoked",
        "revokedKeyId": active_key["id"],
    }
    event = {
        "id": short_id("uno:event"),
        "agentId": agent["id"],
        "sequence": previous["sequence"] + 1,
        "eventType": "revocation",
        "previousEventDigest": object_digest(previous),
        "payloadDigest": digest_object(payload),
        "anchors": [],
        "lineageLinks": [],
        "taxonomySnapshot": agent["taxonomy"],
        "recordedAt": revoked_at,
    }
    event["signature"] = make_signature(active_key["id"], private_key_pem, event)
    events.append(event)

    if args.witness:
        append_receipt(receipts, agent, private_key_pem, event, args.witness, key_id=active_key["id"])

    agent["status"] = "revoked"
    agent["updatedAt"] = revoked_at
    agent.setdefault("metadata", {})["revokedAt"] = revoked_at
    agent["metadata"]["revocationReason"] = args.reason or "Local revocation"
    active_key["status"] = "revoked"
    active_key["validUntil"] = revoked_at

    save_state(state)
    return {
        "command": "revoke-agent",
        "agentId": agent["id"],
        "eventId": event["id"],
        "sequence": event["sequence"],
        "status": agent["status"],
        "stateDir": str(state["paths"]["state_dir"]),
    }


def export_bundle(args: argparse.Namespace) -> dict[str, Any]:
    state = load_state(Path(args.state_dir))
    bundle = {
        "bundleVersion": "uno-local-demo-2",
        "exportedAt": bundle_now(),
        "runtime": {
            "name": "uno-local-demo",
            "version": RUNTIME_VERSION,
            "network": "none",
            "signatureScheme": {
                "algorithm": SIGNATURE_ALGORITHM,
                "implementation": "cryptography-pyca",
                "note": SIGNATURE_NOTE,
            },
        },
        "unoSpecVersion": UNO_SPEC_VERSION,
        "agentId": state["agent"],
        "continuityEvents": state["events"],
        "lineageLinks": state["lineage"],
        "witnessReceipts": state["receipts"],
        "assertions": state["assertions"],
    }
    if args.build_manifest:
        manifest = read_json(Path(args.build_manifest))
        bundle["buildAttestation"] = build_attestation_from_manifest(manifest)
    write_json(Path(args.output), bundle)
    return {
        "command": "export-bundle",
        "output": args.output,
        "agentId": state["agent"]["id"],
        "events": len(state["events"]),
        "receipts": len(state["receipts"]),
        "lineageLinks": len(state["lineage"]),
        "status": state["agent"].get("status"),
    }


def import_witness_receipts(args: argparse.Namespace) -> dict[str, Any]:
    state = load_state(Path(args.state_dir))
    payload = read_json(Path(args.receipt))
    imported = payload if isinstance(payload, list) else [payload]

    existing_ids = {receipt["id"] for receipt in state["receipts"]}
    added = 0
    skipped = 0
    for receipt in imported:
        if receipt.get("id") in existing_ids:
            skipped += 1
            continue
        state["receipts"].append(receipt)
        existing_ids.add(receipt["id"])
        added += 1

    save_state(state)
    return {
        "command": "import-witness-receipts",
        "stateDir": str(state["paths"]["state_dir"]),
        "added": added,
        "skipped": skipped,
        "receipts": len(state["receipts"]),
    }


def verify_signed_object(
    obj: dict[str, Any],
    timestamp_field: str,
    keys_by_id: dict[str, dict[str, Any]],
    reasons: list[str],
    label: str,
) -> bool:
    signature = obj.get("signature") or {}
    if signature.get("algorithm") != SIGNATURE_ALGORITHM:
        reasons.append(f"{label} uses unsupported signature algorithm {signature.get('algorithm')!r}.")
        return False
    key = keys_by_id.get(signature.get("keyId"))
    if key is None:
        reasons.append(f"{label} references unknown keyId {signature.get('keyId')!r}.")
        return False
    if key.get("algorithm") != SIGNATURE_ALGORITHM:
        reasons.append(f"{label} references a key with unsupported algorithm {key.get('algorithm')!r}.")
        return False
    timestamp = obj.get(timestamp_field)
    if timestamp and not timestamp_in_key_validity(key, timestamp):
        reasons.append(f"{label} is outside the validity window of key {key['id']}.")
        return False
    if key.get("status") == "revoked" and not (timestamp and key.get("validUntil") and timestamp <= key.get("validUntil")):
        reasons.append(f"{label} uses revoked key {key['id']} outside its last valid timestamp.")
        return False
    if not verify_signature_with_public_key(key["publicKey"], signed_payload(object_without_signature(obj)), signature.get("value", "")):
        reasons.append(f"Invalid public signature on {label}.")
        return False
    return True


def classify_branch_flow(events: list[dict[str, Any]], lineage_links: list[dict[str, Any]]) -> tuple[str | None, str | None]:
    branch_markers: list[str] = []
    for event in events:
        if event.get("eventType") in {"branch", "merge"}:
            branch_markers.append(event["eventType"])
    for link in lineage_links:
        if link.get("relation") in {"fork-of", "merged-from"}:
            branch_markers.append(link["relation"])

    if not branch_markers:
        return None, None

    last_type = events[-1].get("eventType") if events else None
    if branch_markers.count("branch") == 1 and last_type == "branch" and "merge" not in branch_markers and "merged-from" not in branch_markers:
        return (
            "warning",
            "V1 canonical continuity forbids branches by default; bundle declares a non-canonical branch marker but stays linearly readable.",
        )
    return (
        "not-trusted",
        "V1 canonical continuity forbids branches by default; bundle contains incompatible branch/merge markers for this flow.",
    )


def verify_bundle(args: argparse.Namespace) -> dict[str, Any]:
    bundle = read_json(Path(args.bundle))
    missing_or_weak: list[str] = []
    agent_reasons: list[str] = []
    build_reasons: list[str] = []
    build_missing_or_weak: list[str] = []
    agent_trust = "trust"
    build_trust = "warning"

    agent = bundle["agentId"]
    events = bundle.get("continuityEvents", [])
    lineage_links = bundle.get("lineageLinks", [])
    receipts = bundle.get("witnessReceipts", [])
    taxonomy = agent.get("taxonomy", [])
    taxonomy_map = taxonomy_state(taxonomy)
    keys_by_id = key_lookup(agent)

    if bundle.get("runtime", {}).get("signatureScheme", {}).get("algorithm") != SIGNATURE_ALGORITHM:
        agent_reasons.append("Bundle runtime does not declare the expected Ed25519 signature profile.")
        agent_trust = "not-trusted"

    if not agent.get("lineageRoot"):
        agent_reasons.append("AgentID is missing lineageRoot.")
        agent_trust = "not-trusted"

    for dimension in ("kind", "role", "context"):
        if not taxonomy_map.get(dimension):
            missing_or_weak.append(f"taxonomy.{dimension} missing")

    if not keys_by_id:
        agent_reasons.append("AgentID contains no public keys.")
        agent_trust = "not-trusted"

    if not events:
        agent_reasons.append("No continuity events provided.")
        agent_trust = "not-trusted"

    lineage_by_id = {link["id"]: link for link in lineage_links}
    previous_event = None
    for index, event in enumerate(events):
        if event.get("agentId") != agent.get("id"):
            agent_reasons.append(f"Event {event['id']} points to a different agent.")
            agent_trust = "not-trusted"
        if event.get("sequence") != index:
            agent_reasons.append(f"Event {event['id']} breaks sequence ordering.")
            agent_trust = "not-trusted"
        if index == 0:
            if event.get("eventType") != "inception":
                agent_reasons.append("First event is not an inception event.")
                agent_trust = "not-trusted"
            if event.get("previousEventDigest") is not None:
                agent_reasons.append("Inception event must not reference a previous digest.")
                agent_trust = "not-trusted"
        elif previous_event is not None:
            expected_previous = object_digest(previous_event)
            if event.get("previousEventDigest") != expected_previous:
                agent_reasons.append(f"Event {event['id']} has an invalid previousEventDigest.")
                agent_trust = "not-trusted"

        event_taxonomy = taxonomy_state(event.get("taxonomySnapshot", []))
        for dimension in ("kind", "role", "context"):
            if not event_taxonomy.get(dimension):
                agent_reasons.append(f"Event {event['id']} has incomplete taxonomy snapshot.")
                agent_trust = "not-trusted"

        for lineage_id in event.get("lineageLinks", []):
            link = lineage_by_id.get(lineage_id)
            if link is None:
                agent_reasons.append(f"Event {event['id']} references missing lineage link {lineage_id}.")
                agent_trust = "not-trusted"
                continue
            if link.get("targetAgentId") != agent.get("id"):
                agent_reasons.append(f"Lineage link {lineage_id} targets another agent.")
                agent_trust = "not-trusted"

        if not verify_signed_object(event, "recordedAt", keys_by_id, agent_reasons, f"event {event['id']}"):
            agent_trust = "not-trusted"

        previous_event = event

    if not lineage_links:
        missing_or_weak.append("no lineage links included")

    for link in lineage_links:
        if link.get("targetAgentId") != agent.get("id"):
            agent_reasons.append(f"Lineage link {link['id']} targets another agent.")
            agent_trust = "not-trusted"
        if not link.get("sourceAgentId"):
            agent_reasons.append(f"Lineage link {link['id']} is missing sourceAgentId.")
            agent_trust = "not-trusted"

    event_by_id = {event["id"]: event for event in events}
    valid_external_receipts = 0
    local_receipts_seen = 0
    external_witness_ids: set[str] = set()
    for receipt in receipts:
        event = event_by_id.get(receipt["eventId"])
        if event is None:
            agent_reasons.append(f"Witness receipt {receipt['id']} points to a missing event.")
            agent_trust = "not-trusted"
            continue
        if receipt.get("eventDigest") != object_digest(event):
            agent_reasons.append(f"Witness receipt {receipt['id']} has an invalid event digest.")
            agent_trust = "not-trusted"
            continue

        if is_external_receipt(receipt):
            witness_id = receipt.get("witnessId")
            if not witness_id:
                agent_reasons.append(f"External witness receipt {receipt['id']} is missing witnessId.")
                agent_trust = "not-trusted"
                continue
            if witness_id == agent.get("id"):
                agent_reasons.append(f"External witness receipt {receipt['id']} reuses the agent identity as witness.")
                agent_trust = "not-trusted"
                continue
            witness_keys = external_witness_key_lookup(receipt)
            if not witness_keys:
                agent_reasons.append(f"External witness receipt {receipt['id']} is missing a usable witness public key.")
                agent_trust = "not-trusted"
                continue
            witness_key = next(iter(witness_keys.values()))
            if witness_key.get("algorithm") != SIGNATURE_ALGORITHM:
                agent_reasons.append(f"External witness receipt {receipt['id']} uses unsupported witness key algorithm.")
                agent_trust = "not-trusted"
                continue
            if witness_key.get("fingerprint") != key_fingerprint(witness_key.get("publicKey", "")):
                agent_reasons.append(f"External witness receipt {receipt['id']} has an invalid witness key fingerprint.")
                agent_trust = "not-trusted"
                continue
            if not verify_signed_object(receipt, "observedAt", witness_keys, agent_reasons, f"external receipt {receipt['id']}"):
                agent_trust = "not-trusted"
                continue
            valid_external_receipts += 1
            external_witness_ids.add(witness_id)
        else:
            local_receipts_seen += 1
            if not verify_signed_object(receipt, "observedAt", keys_by_id, agent_reasons, f"receipt {receipt['id']}"):
                agent_trust = "not-trusted"

    if not receipts:
        missing_or_weak.append("no witness receipts provided")
    if valid_external_receipts == 0:
        missing_or_weak.append("no external witness receipts provided")
    if local_receipts_seen and valid_external_receipts == 0:
        missing_or_weak.append("only local inline witness receipts provided")

    if valid_external_receipts:
        witness_word = "witness" if len(external_witness_ids) == 1 else "witnesses"
        agent_reasons.append(
            f"Valid external witness receipts verified from {len(external_witness_ids)} distinct {witness_word}."
        )

    branch_level, branch_reason = classify_branch_flow(events, lineage_links)
    if branch_level == "warning" and agent_trust == "trust":
        agent_trust = "warning"
        agent_reasons.append(branch_reason)
    elif branch_level == "not-trusted":
        agent_trust = "not-trusted"
        agent_reasons.append(branch_reason)

    if agent.get("status") == "revoked":
        agent_trust = "not-trusted"
        agent_reasons.append("Agent status is revoked in the presented continuity state.")

    if not any(event.get("eventType") == "revocation" for event in events) and agent.get("status") == "revoked":
        agent_reasons.append("Agent is marked revoked but no revocation event is present.")
        agent_trust = "not-trusted"

    if agent_trust == "trust" and missing_or_weak:
        agent_trust = "warning"

    build_attestation = bundle.get("buildAttestation")
    expected_manifest = read_json(Path(args.expected_build_manifest)) if args.expected_build_manifest else None

    if build_attestation is None:
        build_missing_or_weak.append("no build attestation in bundle")
    else:
        manifest = build_attestation.get("manifest")
        if build_attestation.get("type") != BUILD_ATTESTATION_TYPE:
            build_reasons.append("Bundle build attestation uses an unknown type.")
            build_trust = "not-trusted"
        elif not isinstance(manifest, dict):
            build_reasons.append("Bundle build attestation is missing a manifest.")
            build_trust = "not-trusted"
        else:
            if build_attestation.get("manifestDigest") != digest_object(manifest):
                build_reasons.append("Bundle build attestation digest does not match the embedded manifest.")
                build_trust = "not-trusted"
            elif expected_manifest is None:
                build_missing_or_weak.append("no expected build manifest supplied for comparison")
            else:
                mismatches = compare_manifests(manifest, expected_manifest)
                if mismatches:
                    build_reasons.append(
                        "Expected build manifest does not match the bundle attestation: " + ", ".join(mismatches) + "."
                    )
                    build_trust = "not-trusted"
                else:
                    build_reasons.append("Build attestation matches the expected local build manifest.")
                    build_trust = "trust"
    if build_attestation is None and expected_manifest is not None:
        build_missing_or_weak.append("expected build manifest was provided but bundle has no attested manifest")

    final_taxonomy = taxonomy_state(events[-1].get("taxonomySnapshot", taxonomy)) if events else taxonomy_map
    retained_state = {
        "status": agent.get("status"),
        "taxonomy": final_taxonomy,
        "lineage": {
            "lineageRoot": agent.get("lineageRoot"),
            "links": [{"id": link["id"], "relation": link["relation"], "source": link["sourceAgentId"]} for link in lineage_links],
        },
    }

    if not agent_reasons:
        agent_reasons.append("Continuity chain is structurally coherent and signatures verify from embedded public keys.")

    verdict = "trust"
    if "not-trusted" in {agent_trust, build_trust}:
        verdict = "not-trusted"
    elif "warning" in {agent_trust, build_trust}:
        verdict = "warning"

    return {
        "verdict": verdict,
        "agentTrust": agent_trust,
        "buildTrust": build_trust,
        "agentId": agent.get("id"),
        "state": retained_state,
        "reasons": agent_reasons + build_reasons,
        "missingOrWeakProofs": missing_or_weak + build_missing_or_weak,
    }


def wipe_tree(path: Path) -> None:
    if not path.exists():
        return
    for root, dirs, files in os.walk(path, topdown=False):
        for file_name in files:
            Path(root, file_name).unlink()
        for dir_name in dirs:
            Path(root, dir_name).rmdir()
    path.rmdir()


def build_demo(args: argparse.Namespace) -> dict[str, Any]:
    state_dir = Path(args.state_dir or "examples/demo_state")
    manifest_path = Path(args.build_manifest_output or "examples/demo_build_manifest.json")
    witnessed_bundle_path = Path(args.witnessed_output or "examples/demo_bundle_witnessed.json")
    witness_state_dir = Path(args.witness_state_dir or "examples/demo_witness_state")

    wipe_tree(state_dir)
    wipe_tree(witness_state_dir)

    init_result = init_agent(
        argparse.Namespace(
            controller="local-demo-controller",
            display_name="UNO Local Demo Agent",
            kind="agent",
            role="continuity-runtime",
            context="offline-demo",
            note="Offline local inception",
            slug="demo-agent",
            state_dir=str(state_dir),
            witness=None,
        )
    )
    append_event(
        argparse.Namespace(
            state_dir=str(state_dir),
            event_type="taxonomy-update",
            note="Context clarified for local public verification replay",
            kind="agent",
            role="continuity-runtime",
            context="offline-demo",
            relation=None,
            source_agent_id=None,
            taxonomy_inheritance="partial",
            witness=None,
        )
    )
    append_event(
        argparse.Namespace(
            state_dir=str(state_dir),
            event_type="lineage-update",
            note="Spawned from the UNO foundation seed for demo lineage",
            kind=None,
            role=None,
            context=None,
            relation="spawned-by",
            source_agent_id="uno:foundation:seed",
            taxonomy_inheritance="partial",
            witness=None,
        )
    )
    build_manifest(
        argparse.Namespace(
            output=str(manifest_path),
            code_path=[str(Path(__file__)), str(Path(__file__).with_name("uno_witness.py"))],
            config_path=[],
            built_at=None,
            builder=args.builder,
        )
    )
    export_result = export_bundle(argparse.Namespace(state_dir=str(state_dir), output=args.output, build_manifest=str(manifest_path)))
    verify_without_witness = verify_bundle(argparse.Namespace(bundle=args.output, expected_build_manifest=str(manifest_path), state_dir=None))

    subprocess.run(
        [
            sys.executable,
            str(Path(__file__).with_name("uno_witness.py")),
            "init-witness",
            "--display-name",
            args.external_witness_name,
            "--state-dir",
            str(witness_state_dir),
        ],
        check=True,
        capture_output=True,
        text=True,
    )

    events = read_json(state_dir / "continuity_events.json")
    temp_receipt_dir = witness_state_dir / "receipts"
    ensure_dir(temp_receipt_dir)
    imported = 0
    for event in events:
        event_path = temp_receipt_dir / f"{event['sequence']:02d}-{event['id']}--event.json"
        receipt_path = temp_receipt_dir / f"{event['sequence']:02d}-{event['id']}--receipt.json"
        write_json(event_path, event)
        subprocess.run(
            [
                sys.executable,
                str(Path(__file__).with_name("uno_witness.py")),
                "sign-event",
                "--state-dir",
                str(witness_state_dir),
                "--event",
                str(event_path),
                "--output",
                str(receipt_path),
            ],
            check=True,
            capture_output=True,
            text=True,
        )
        import_witness_receipts(argparse.Namespace(state_dir=str(state_dir), receipt=str(receipt_path)))
        imported += 1

    export_witnessed = export_bundle(
        argparse.Namespace(state_dir=str(state_dir), output=str(witnessed_bundle_path), build_manifest=str(manifest_path))
    )
    verify_with_witness = verify_bundle(
        argparse.Namespace(bundle=str(witnessed_bundle_path), expected_build_manifest=str(manifest_path), state_dir=None)
    )

    return {
        "command": "build-demo",
        "agentId": init_result["agentId"],
        "stateDir": str(state_dir),
        "bundleWithoutExternalWitness": export_result["output"],
        "bundleWithExternalWitness": export_witnessed["output"],
        "externalWitnessStateDir": str(witness_state_dir),
        "externalWitnessReceiptsImported": imported,
        "buildManifest": str(manifest_path),
        "verifyWithoutWitnessVerdict": verify_without_witness["verdict"],
        "verifyWithWitnessVerdict": verify_with_witness["verdict"],
    }


def print_json(value: Any) -> None:
    sys.stdout.write(json.dumps(value, indent=2, sort_keys=True, ensure_ascii=True) + "\n")


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Minimal local UNO runtime")
    subparsers = parser.add_subparsers(dest="command", required=True)

    init_parser = subparsers.add_parser("init-agent", help="Create a local AgentID and inception event")
    init_parser.add_argument("--controller", required=True)
    init_parser.add_argument("--display-name", required=True)
    init_parser.add_argument("--kind", required=True)
    init_parser.add_argument("--role", required=True)
    init_parser.add_argument("--context", required=True)
    init_parser.add_argument("--note")
    init_parser.add_argument("--slug")
    init_parser.add_argument("--state-dir")
    init_parser.add_argument("--witness", default=DEFAULT_WITNESS)

    append_parser = subparsers.add_parser("append-event", help="Append a continuity event")
    append_parser.add_argument("--state-dir", required=True)
    append_parser.add_argument(
        "--event-type",
        required=True,
        choices=["inception", "key-rotation", "taxonomy-update", "assertion-anchor", "lineage-update", "branch", "merge", "revocation"],
    )
    append_parser.add_argument("--note")
    append_parser.add_argument("--kind")
    append_parser.add_argument("--role")
    append_parser.add_argument("--context")
    append_parser.add_argument("--relation", choices=["derived-from", "fork-of", "merged-from", "supersedes", "spawned-by", "trained-from"])
    append_parser.add_argument("--source-agent-id")
    append_parser.add_argument("--taxonomy-inheritance", default="partial", choices=["full", "partial", "none"])
    append_parser.add_argument("--witness", default=DEFAULT_WITNESS)

    revoke_parser = subparsers.add_parser("revoke-agent", help="Revoke an agent and append a revocation event")
    revoke_parser.add_argument("--state-dir", required=True)
    revoke_parser.add_argument("--reason")
    revoke_parser.add_argument("--witness", default=DEFAULT_WITNESS)

    export_parser = subparsers.add_parser("export-bundle", help="Export a proof bundle JSON")
    export_parser.add_argument("--state-dir", required=True)
    export_parser.add_argument("--output", required=True)
    export_parser.add_argument("--build-manifest")

    import_parser = subparsers.add_parser("import-witness-receipts", help="Import external witness receipt JSON into state")
    import_parser.add_argument("--state-dir", required=True)
    import_parser.add_argument("--receipt", required=True)

    manifest_parser = subparsers.add_parser("build-manifest", help="Write a local build manifest")
    manifest_parser.add_argument("--output", required=True)
    manifest_parser.add_argument("--code-path", action="append")
    manifest_parser.add_argument("--config-path", action="append")
    manifest_parser.add_argument("--built-at")
    manifest_parser.add_argument("--builder")

    verify_parser = subparsers.add_parser("verify", help="Verify a proof bundle")
    verify_parser.add_argument("--bundle", required=True)
    verify_parser.add_argument("--expected-build-manifest")
    verify_parser.add_argument("--state-dir")

    demo_parser = subparsers.add_parser("build-demo", help="Generate replayable demo bundles")
    demo_parser.add_argument("--output", default="examples/demo_bundle.json")
    demo_parser.add_argument("--witnessed-output", default="examples/demo_bundle_witnessed.json")
    demo_parser.add_argument("--state-dir")
    demo_parser.add_argument("--witness-state-dir")
    demo_parser.add_argument("--external-witness-name", default="UNO Portable Witness")
    demo_parser.add_argument("--build-manifest-output", default="examples/demo_build_manifest.json")
    demo_parser.add_argument("--builder")

    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)

    if args.command == "init-agent":
        print_json(init_agent(args))
        return 0
    if args.command == "append-event":
        print_json(append_event(args))
        return 0
    if args.command == "revoke-agent":
        print_json(revoke_agent(args))
        return 0
    if args.command == "build-manifest":
        print_json(build_manifest(args))
        return 0
    if args.command == "export-bundle":
        print_json(export_bundle(args))
        return 0
    if args.command == "import-witness-receipts":
        print_json(import_witness_receipts(args))
        return 0
    if args.command == "verify":
        print_json(verify_bundle(args))
        return 0
    if args.command == "build-demo":
        print_json(build_demo(args))
        return 0

    parser.error(f"Unknown command: {args.command}")
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
