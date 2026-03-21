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

### Chantier #1 — Native consensus layer (Layer 1)

**This is the primary open challenge.**

The current runtime is local and offline. Layer 1 needs to become a decentralized consensus network where claws (validator nodes) reach quorum on the state of agent registries without depending on any external network infrastructure.

**Stack validated (2026-03-21):**
- **Language:** Go 1.21+
- **Networking:** [go-libp2p](https://github.com/libp2p/go-libp2p) (Gossipsub v1.1 — used in production by ETH2, Filecoin, IPFS)
- **VRF:** HKDF-SHA256 (self-contained, no external oracle)
- **Consensus:** HotStuff-lite (2-phase BFT — simpler than pBFT, handles rotating quorums)
- **Architecture doc:** [`docs/ARCHITECTURE_LAYER1.md`](docs/ARCHITECTURE_LAYER1.md)

**The design:**
- Open network — any UNO-registered claw can participate
- No token, no stake, no rewards, no slash
- Round T: VRF selects K producers + N verifiers → candidate block → 2/3 verifiers → finalized block
- Revocation events are high-priority in gossip propagation
- Layer 2 (Python API) communicates with Layer 1 (Go node) via IPC (local socket)

**The need:**
- Validators (claws) maintain and attest to the canonical state of the registry
- Quorum is reached via a rotating VRF (not fixed committee)
- No dependency on third-party chains, bridges, or external RPC providers
- The network must be self-contained and auditable

**What is NOT Cosmos SDK:**
- Cosmos/Tendermint uses a fixed validator set weighted by stake
- UNO Layer 1 uses a rotating VRF-based quorum — fundamentally different mechanism
- Cosmos SDK is not the right foundation for this design

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

**No heavy dependencies for Python runtime.** The runtime runs on Python 3.10+ with only `cryptography` as a core dependency. New contributions must not introduce heavy libraries, external API calls at import time, or network requirements in the core runtime.

**Layer 1 is Go.** Contributions to Layer 1 (consensus, networking) must be in Go. The Python runtime is for identity, events, and verification. The Go node is for consensus.

**The manifesto governs.** When a technical choice conflicts with the protocol's design principles (neutrality, sobriety, auditability, human accountability), the manifesto wins. Read [`MANIFESTO.md`](MANIFESTO.md) before proposing structural changes.

**Specs before implementation.** Changes to protocol objects or verification semantics require a corresponding update to the spec files in `specs/` — not just code changes.

---

## Code of Conduct

Be direct. Disagree on substance. No harassment, no bad faith, no astroturfing.

UNO is an infrastructure project. The work is technical and the stakes are real. Treat it that way.
