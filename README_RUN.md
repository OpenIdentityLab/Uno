# UNO Local Runtime

This directory contains the tranche 6 offline UNO runtime.

It stays local/offline, keeps public Ed25519 signatures via the `cryptography` (PyCA) library, and now adds a **portable external witness** separated from the agent runtime.

Honest limits:
- still a local demo runtime, not a production trust stack
- depends on the `cryptography` Python library (`pip install cryptography`)
- checks local build coherence only, not TEE / remote attestation / hardware-backed measurement
- V1 policy stays explicit: **one canonical continuity, no branch allowed by default**
- external witness is file/CLI based only in this tranche: no HTTP service, no network infra

## What changed in tranche 6

- agent runtime and witness are now separate components
- the witness owns its **own identity and key**
- the witness can sign a `WitnessReceipt` from:
  - a full `ContinuityEvent` JSON file
  - or an `eventDigest` JSON + `eventId`
- the runtime can import those external receipts into state, then export them in the bundle
- `verify` now distinguishes:
  - **no external witness** → at best `warning`
  - **valid external witness** → can reach `trust`
  - **invalid/incoherent external witness** → `not-trusted`

## Dependency

Install the required Python library:

```bash
pip install cryptography
```

The runtime uses `cryptography` (PyCA) for all Ed25519 operations:
- `Ed25519PrivateKey.generate()` for key generation
- `private_key.sign(data)` for signing
- `public_key.verify(signature, data)` for verification

No `openssl` CLI dependency — pure Python, fully offline.

## Demo flow

Build both demo bundles:
- `examples/demo_bundle.json` → **without external witness**
- `examples/demo_bundle_witnessed.json` → **with portable external witness**

```bash
python3 runtime/uno_runtime.py build-demo \
  --output examples/demo_bundle.json \
  --witnessed-output examples/demo_bundle_witnessed.json \
  --build-manifest-output examples/demo_build_manifest.json
```

Verify the bundle **without** external witness:

```bash
python3 runtime/uno_runtime.py verify \
  --bundle examples/demo_bundle.json \
  --expected-build-manifest examples/demo_build_manifest.json
```

Expected result: `warning`

Verify the bundle **with** external witness:

```bash
python3 runtime/uno_runtime.py verify \
  --bundle examples/demo_bundle_witnessed.json \
  --expected-build-manifest examples/demo_build_manifest.json
```

Expected result: `trust`

Run tests:

```bash
python3 -m unittest tests.test_runtime
```

## Manual portable witness flow

### 1. Create agent state

```bash
python3 runtime/uno_runtime.py init-agent \
  --controller local \
  --display-name "My Agent" \
  --kind agent \
  --role assistant \
  --context offline \
  --state-dir runtime/state/my-agent
```

### 2. Append an event

```bash
python3 runtime/uno_runtime.py append-event \
  --state-dir runtime/state/my-agent \
  --event-type taxonomy-update \
  --context audited-local
```

### 3. Create a separate witness

```bash
python3 runtime/uno_witness.py init-witness \
  --display-name "Portable Witness A" \
  --state-dir runtime/witness_state/portable-witness-a
```

### 4. Sign a receipt from a full event file

For a real flow, extract one `ContinuityEvent` object to its own JSON file first, for example `examples/event_000.json`, then sign it:

```bash
python3 runtime/uno_witness.py sign-event \
  --state-dir runtime/witness_state/portable-witness-a \
  --event examples/event_000.json \
  --output examples/witness_receipt.json
```

The CLI also supports digest-only mode:

```bash
python3 runtime/uno_witness.py sign-event \
  --state-dir runtime/witness_state/portable-witness-a \
  --event-digest examples/event_digest.json \
  --event-id uno:event:123 \
  --output examples/witness_receipt.json
```

### 5. Import the external receipt into agent state

```bash
python3 runtime/uno_runtime.py import-witness-receipts \
  --state-dir runtime/state/my-agent \
  --receipt examples/witness_receipt.json
```

### 6. Export and verify

```bash
python3 runtime/uno_runtime.py build-manifest \
  --output examples/my_agent_build_manifest.json \
  --code-path runtime/uno_runtime.py \
  --code-path runtime/uno_witness.py

python3 runtime/uno_runtime.py export-bundle \
  --state-dir runtime/state/my-agent \
  --output examples/my_agent_bundle.json \
  --build-manifest examples/my_agent_build_manifest.json

python3 runtime/uno_runtime.py verify \
  --bundle examples/my_agent_bundle.json \
  --expected-build-manifest examples/my_agent_build_manifest.json
```

## Verify semantics

- Missing expected build manifest => `buildTrust = warning`
- Mismatched build manifest => `buildTrust = not-trusted`
- Revoked agent state => `agentTrust = not-trusted`
- No external witness receipts => `agentTrust` can degrade to `warning`
- Valid external witness receipts from a distinct witness identity => `agentTrust = trust` if the rest is coherent
- Invalid / incoherent external witness receipts => `agentTrust = not-trusted`
- A single explicit terminal `branch` marker => degraded to `warning`
- Incompatible branch/merge markers under V1 canonical continuity => `not-trusted`
