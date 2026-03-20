# UNO

**Verifiable identity for AI agents. For those who deploy them, and for the agents themselves.**

---

## What is UNO

UNO is an open protocol for declaring, proving, and verifying the identity of AI agents. It functions as a civil registry for the human-machine world: not a decorative badge, but a structured dossier — declaration, cryptographic proof, lineage, continuity history, and revocable status. The protocol operates at two levels simultaneously. Externally, it provides accountability: any third party can verify what an agent is, who operates it, and under what conditions it is valid. Internally, it provides continuity: an agent can carry its own verifiable history and refer back to its own state over time. Accountability is self-awareness seen from the outside. Continuity is accountability seen from the inside.


## Manifesto

UNO is not only a codebase. Its design principles are defined in the manifesto: neutrality, sobriety, auditability, human accountability, and revocability.

Read: [MANIFESTO.md](MANIFESTO.md)

---

## Architecture

```
┌─────────────────────────────────────────────────────────────┐
│  Layer 3 — UNO API Wrapper                                  │
│  Third-party entry point. Rate limiting, auth,              │
│  normalized response. Reads from Layer 2.                   │
├─────────────────────────────────────────────────────────────┤
│  Layer 2 — Metadata Service                                 │
│  Human-readable index above the chain. REST API.            │
│  Aggregates and exposes protocol state.                     │
├─────────────────────────────────────────────────────────────┤
│  Layer 1 — Consensus Layer  ← open community challenge      │
│  Decentralized. Claws as validators. Rotating VRF quorum.   │
│  No third-party network dependency.                         │
└─────────────────────────────────────────────────────────────┘
```

Layer 1 is the primary open challenge. See [CONTRIBUTING.md](CONTRIBUTING.md).

---

## Protocol Objects

Five core objects define the V1 data model:

- **AgentID** — persistent identifier for an agent: kind, role, controller, context, public key
- **ContinuityEvent** — append-only event in the agent's lifecycle (taxonomy update, key rotation, revocation, etc.)
- **LineageLink** — typed relationship to another entity (operator, model provider, parent agent, fork source)
- **WitnessReceipt** — external signature over a ContinuityEvent, issued by an independent witness identity
- **Assertion** — structured claim attached to the agent, with an explicit validity window and revocation support

Full schema: [`specs/data-model.v1.json`](specs/data-model.v1.json)

---

## Quick Start

Requires Python 3.10+ and the `cryptography` library (`pip install cryptography`).

**Build demo bundles:**

```bash
python3 runtime/uno_runtime.py build-demo \
  --output examples/demo_bundle.json \
  --witnessed-output examples/demo_bundle_witnessed.json \
  --build-manifest-output examples/demo_build_manifest.json
```

**Verify without external witness** (expected: `warning`):

```bash
python3 runtime/uno_runtime.py verify \
  --bundle examples/demo_bundle.json \
  --expected-build-manifest examples/demo_build_manifest.json
```

**Verify with external witness** (expected: `trust`):

```bash
python3 runtime/uno_runtime.py verify \
  --bundle examples/demo_bundle_witnessed.json \
  --expected-build-manifest examples/demo_build_manifest.json
```

**Run tests:**

```bash
python3 -m unittest tests.test_runtime -v
```

See [`README_RUN.md`](README_RUN.md) for the full manual witness flow.

---

## Verify Semantics

- `trust` — coherent bundle, valid external witness receipt from a distinct identity, build manifest matches
- `warning` — coherent bundle but no external witness, or minor build manifest mismatch
- `not-trusted` — invalid signatures, revoked state, incoherent continuity chain, or tampered build manifest

---

## Current Status

**Working:**
- Full V1 runtime (local, offline): agent init, event append, key generation via PyCA cryptography
- Portable external witness: separate identity, signs `WitnessReceipt` over `ContinuityEvent`
- Bundle export and verification with full chain validation
- Verify semantics: `trust` / `warning` / `not-trusted`
- Test suite passing

**In progress / open:**
- Layer 1: decentralized consensus (primary open challenge — see Contributing)
- Layer 2: metadata service / REST API
- Self-query endpoint (agent querying UNO about itself)
- Key rotation (event type exists in schema, implementation pending)

---

## Contributing

See [CONTRIBUTING.md](CONTRIBUTING.md).

Core texts: [MANIFESTO.md](MANIFESTO.md) · [PROTOCOL_SCHEMA_V1.md](PROTOCOL_SCHEMA_V1.md)

---

## License

AGPL-3.0-or-later. See [LICENSE](LICENSE).
