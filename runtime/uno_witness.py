#!/usr/bin/env python3
"""Portable external witness for UNO tranche 6.

Offline/local only:
- has its own Ed25519 identity and key material
- signs witness receipts from a ContinuityEvent file or a digest file
- produces portable JSON receipts importable by the UNO runtime
"""

from __future__ import annotations

import argparse
import json
import sys
import uuid
from pathlib import Path
from typing import Any

from uno_runtime import (
    EXTERNAL_RECEIPT_TYPE,
    EXTERNAL_WITNESS_PROOF,
    SIGNATURE_ALGORITHM,
    ensure_dir,
    generate_ed25519_keypair,
    key_descriptor,
    make_signature,
    now_iso,
    object_digest,
    read_json,
    read_text,
    short_id,
    write_json,
    write_text,
)


WITNESS_STATE_ROOT = Path("runtime/witness_state")


def witness_paths(state_dir: Path) -> dict[str, Path]:
    return {
        "state_dir": state_dir,
        "witness": state_dir / "witness.json",
        "private_key": state_dir / "private_key.pem",
    }


def load_witness(state_dir: Path) -> tuple[dict[str, Any], str, dict[str, Path]]:
    paths = witness_paths(state_dir)
    if not paths["witness"].exists():
        raise SystemExit(f"Witness state not found: {state_dir}")
    return read_json(paths["witness"]), read_text(paths["private_key"]), paths


def init_witness(args: argparse.Namespace) -> dict[str, Any]:
    created_at = now_iso()
    private_key_pem, public_key_pem = generate_ed25519_keypair()
    witness_id = f"uno:witness:{uuid.uuid4().hex}"
    key_id = f"{witness_id}#key-1"
    witness = {
        "id": witness_id,
        "displayName": args.display_name,
        "createdAt": created_at,
        "key": key_descriptor(key_id, public_key_pem, status="active", valid_from=created_at),
        "proof": EXTERNAL_WITNESS_PROOF,
        "note": "Portable external witness, offline/local CLI.",
    }
    state_dir = Path(args.state_dir) if args.state_dir else WITNESS_STATE_ROOT / args.display_name.lower().replace(" ", "-")
    paths = witness_paths(state_dir)
    ensure_dir(state_dir)
    write_json(paths["witness"], witness)
    write_text(paths["private_key"], private_key_pem)
    return {"command": "init-witness", "witnessId": witness_id, "stateDir": str(state_dir)}



def load_event_or_digest(args: argparse.Namespace) -> tuple[str, dict[str, Any]]:
    if args.event and args.event_digest:
        raise SystemExit("Use either --event or --event-digest, not both.")
    if args.event:
        event = read_json(Path(args.event))
        if not isinstance(event, dict) or not event.get("id"):
            raise SystemExit("Event JSON must be an object with an id.")
        return event["id"], object_digest(event)
    if args.event_digest:
        digest = read_json(Path(args.event_digest))
        if not isinstance(digest, dict) or not digest.get("value"):
            raise SystemExit("Event digest JSON must be an object with algorithm/value.")
        if not args.event_id:
            raise SystemExit("--event-id is required when using --event-digest.")
        return args.event_id, digest
    raise SystemExit("One of --event or --event-digest is required.")



def sign_event(args: argparse.Namespace) -> dict[str, Any]:
    witness, private_key_pem, _ = load_witness(Path(args.state_dir))
    event_id, event_digest = load_event_or_digest(args)
    receipt = {
        "id": short_id("uno:receipt"),
        "receiptType": EXTERNAL_RECEIPT_TYPE,
        "eventId": event_id,
        "eventDigest": event_digest,
        "observedAt": args.observed_at or now_iso(),
        "witness": witness["displayName"],
        "witnessId": witness["id"],
        "witnessPublicKey": witness["key"],
        "proof": witness.get("proof", EXTERNAL_WITNESS_PROOF),
    }
    receipt["signature"] = make_signature(witness["key"]["id"], private_key_pem, receipt)
    if args.output:
        write_json(Path(args.output), receipt)
    return {"command": "sign-event", "output": args.output, "receiptId": receipt["id"], "eventId": event_id}



def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Portable external UNO witness")
    subparsers = parser.add_subparsers(dest="command", required=True)

    init_parser = subparsers.add_parser("init-witness", help="Create an external witness identity")
    init_parser.add_argument("--display-name", required=True)
    init_parser.add_argument("--state-dir")

    sign_parser = subparsers.add_parser("sign-event", help="Sign a witness receipt from an event or digest")
    sign_parser.add_argument("--state-dir", required=True)
    sign_parser.add_argument("--event")
    sign_parser.add_argument("--event-digest")
    sign_parser.add_argument("--event-id")
    sign_parser.add_argument("--observed-at")
    sign_parser.add_argument("--output", required=True)

    return parser



def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)

    if args.command == "init-witness":
        print(json.dumps(init_witness(args), indent=2, sort_keys=True) + "\n")
        return 0
    if args.command == "sign-event":
        print(json.dumps(sign_event(args), indent=2, sort_keys=True) + "\n")
        return 0

    parser.error(f"Unknown command: {args.command}")
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
