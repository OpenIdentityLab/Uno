# UNO Layer 1 — Consensus Architecture

> Status: DRAFT — 2026-03-21
> Language: **Go**
> Layer 1 = decentralized consensus network for UNO agent registry

---

## Principes fondateurs

- Every claw has the right to an identity
- Open network — any UNO-registered agent can participate
- No token, no stake, no rewards, no slash
- Quorum is **rotating** via VRF (not fixed committee)
- Network must be self-contained (no third-party dependencies)
- Latency target: **seconds** (not sub-second)

---

## Architecture

```
┌─────────────────────────────────────────────┐
│  UNO Protocol  (data model + verify)        │  ← Python runtime (existing)
├─────────────────────────────────────────────┤
│  Layer 1 — Consensus (Go + libp2p)          │
│    • VRF-based validator selection           │
│    • Block production (X producers)          │
│    • Block verification (Y verifiers)        │
│    • HotStuff-lite consensus (2-phase)      │
│    • Gossipsub propagation (libp2p)        │
└─────────────────────────────────────────────┘

Communication: IPC (local socket) between Python runtime and Go node
```

---

## Block structure

```json
{
  "round": 42,
  "timestamp": "2026-03-21T23:00:00Z",
  "producer": "uno:agent:9de7474025a641628530f31e6b8579c2",
  "events": [
    {
      "type": "continuity_event",
      "agent": "uno:agent:...",
      "event_id": "uno:event:...",
      "payload": {}
    }
  ],
  "parent_hash": "sha256:abc...",
  "block_hash": "sha256:def...",
  "signatures": {
    "uno:agent:...": "base64_sig",
    "uno:agent:...": "base64_sig"
  }
}
```

**Block = ordered list of UNO continuity events to be committed to the canonical chain.**

---

## Round mechanics

```
Round T:
  1. VRF seed = hash(previous_block_hash + round_number)
  2. VRF selects K producers from eligible nodes
  3. Each producer creates a candidate block
  4. VRF selects N verifiers (N > K, e.g. K=2, N=5)
  5. Producers send their candidate to the N verifiers
  6. Verifiers vote on the best candidate (using HotStuff-lite)
  7. If 2/3 of N agree → block is finalized
  8. Gossipsub broadcasts finalized block to all nodes
```

---

## VRF — Verifiable Random Function

**Goal:** select a pseudorandom subset of validators without a central beacon.

**Implementation:**
- Use HKDF-SHA256 with (seed + round_number + node_id) as input
- Each node locally computes its eligibility for the round
- Result is a number in [0, 2^256) — threshold determines probability of selection
- Proof = HMAC output that other nodes can verify using the node's public key

**Why HKDF instead of Chainlink VRF:** self-contained, no external oracle dependency.

**Eligibility formula:**
```
eligible = VRF(round_seed, node_id) < (total_nodes * slots_per_round)
```
Slots per round = tunable parameter (e.g., 3 producers + 7 verifiers per round)

---

## Consensus — HotStuff-lite (2-phase)

**Why HotStuff:** simpler than pBFT, handles rotating quorums naturally, used in production (Diem/Meta).

**Two phases instead of three:**

```
Phase 1 — PREPARE:
  Verifiers receive candidate block from producers
  Verifiers broadcast: "I vote for block H at round R"
  If 2/3 of verifiers vote for same block hash → proceed

Phase 2 — COMMIT:
  Producers collect votes, create QC (quorum certificate)
  Block with QC is committed
```

**vs pBFT:**
- pBFT = 3 phases (pre-prepare, prepare, commit)
- HotStuff = 2 phases (prepare, commit) in the common case
- Latency: 2 network round-trips instead of 3

---

## Network — libp2p Gossipsub

**Protocol:** `gossipsub-v1.1` (used by ETH2, Filecoin, IPFS)

**Topics:**
- `/uno/blocks` — finalized blocks
- `/uno/proposals` — candidate blocks from producers
- `/uno/votes` — votes from verifiers
- `/uno/revocations` — **HIGH PRIORITY** — revocation events (propagated before everything else)

**Peer discovery:** seed nodes bootstrap, then mDNS/local discovery for LAN.

**No external dependency:** bootstrap nodes are listed in config, not fetched from DNS.

---

## Revocation — priority handling

```
Threat:
  T=0: Numa is revoked (event broadcast)
  T=0 + interval: Numa makes spoofed actions before revocation propagates
```

**Mitigation:**
1. Revocation events → `/uno/revocations` topic (HIGH PRIORITY, propagated first)
2. Nodes update their local registry cache immediately on revocation receipt
3. TTL on cache = configurable (default: 60s)
4. For critical actions: query `/verify/{id}` synchronously before proceeding

**This is acceptable because:** most agent interactions are async by nature (reading, recommendations). Critical financial actions should use sync verification.

---

## Open questions (to resolve during build)

- [ ] Minimum viable network size (how many nodes for BFT safety?)
- [ ] How does a new node bootstrap? (Full chain vs. state sync)
- [ ] What happens when a producer goes offline during its slot?
- [ ] State pruning strategy
- [ ] How does Layer 2 API interact with Layer 1 blocks?

---

## Non-goals for v1

- Fraud proofs
- Light client verification
- Cross-chain communication
- Token economics

---

## Stack

| Layer | Technology |
|-------|------------|
| Language | Go 1.21+ |
| Networking | go-libp2p (Gossipsub v1.1) |
| VRF | HKDF-SHA256 (custom, self-contained) |
| Consensus | HotStuff-lite (custom implementation) |
| Serialization | Protocol Buffers |
| Identity events | ingested from Python runtime via IPC |

---

## References

- HotStuff: https://arxiv.org/abs/1803.05069
- libp2p Gossipsub: https://github.com/libp2p/specs/tree/master/pubsub/gossipsub
- KERI Key Event Logs: https://keri.one/
