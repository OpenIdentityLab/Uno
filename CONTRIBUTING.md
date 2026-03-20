# Contributing to UNO

UNO is an open protocol. Contributions are welcome on the open challenges below and on any part of the codebase that improves correctness, coverage, or clarity.

---

## How to contribute

1. Fork the repo, create a branch named after the work (`feature/...`, `fix/...`, `spec/...`)
2. Write tests. No contribution without tests.
3. Open a pull request with a clear description of what changed and why
4. If the change affects the protocol semantics, update the relevant spec file in `specs/`

---

## Open Challenges

### Chantier #1 — Native consensus layer

**This is the primary open challenge.**

The current runtime is local and offline. Layer 1 needs to become a decentralized consensus network where claws (validator nodes) reach quorum on the state of agent registries without depending on any external network infrastructure.

**The need:**
- Validators (claws) maintain and attest to the canonical state of the registry
- Quorum is reached via a rotating VRF (Verifiable Random Function) — no fixed committee
- No dependency on third-party chains, bridges, or external RPC providers
- The network must be self-contained and auditable

**Recommended starting points:**
- [Cosmos SDK](https://docs.cosmos.network/) — modular consensus, ABCI interface
- [KERI](https://keri.one/) — key event receipt infrastructure, directly relevant to the identity model
- [libp2p](https://libp2p.io/) — transport layer for peer-to-peer networking

**Constraints:**
- No third-party network dependency at consensus level
- Rotating VRF quorum (not static validator set)
- Must integrate cleanly with the existing V1 data model (`specs/data-model.v1.json`)

---

### Chantier #2 — Self-query endpoint

An agent should be able to interrogate UNO about itself: retrieve its own current registry state, verify its own continuity chain, and detect revocation without relying on a third party to initiate the lookup.

This requires a defined endpoint and authentication model that proves the querying agent is the registered identity (not a spoofed request).

---

### Chantier #3 — Key rotation

The `key-rotation` event type exists in the V1 schema (`specs/data-model.v1.json`) but is not yet implemented in the runtime. Key rotation is critical for long-lived agent identities.

Implementation should:
- Produce a `ContinuityEvent` of type `key-rotation`
- Update the agent's active public key without breaking the continuity chain
- Require a valid signature from the previous key (proof of prior control)
- Be reflected correctly in bundle export and verify output

---

## Rules

**Tests are mandatory.** Every functional change must include a test. The test suite must pass before merge.

**No heavy dependencies.** The runtime runs on Python 3.10+ with only `cryptography` as a core dependency. New contributions must not introduce heavy libraries, external API calls at import time, or network requirements in the core runtime.

**The manifesto governs.** When a technical choice conflicts with the protocol's design principles (neutrality, sobriety, auditability, human accountability), the manifesto wins. Read [`MANIFESTO.md`](MANIFESTO.md) before proposing structural changes.

**Specs before implementation.** Changes to protocol objects or verification semantics require a corresponding update to the spec files in `specs/` — not just code changes.

---

## Code of Conduct

Be direct. Disagree on substance. No harassment, no bad faith, no astroturfing.

UNO is an infrastructure project. The work is technical and the stakes are real. Treat it that way.
