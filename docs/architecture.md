# UNO — V1 Architecture

## Purpose
UNO is a verifiable continuity protocol for AI agents. Its role is not to run an agent, but to make identity, key assertions, lineage, and continuity of state verifiable over time.

## V1 non-goals
- no agent runtime
- no infra/network/global consensus orchestration
- no economic layer in core protocol
- not a naive KERI copy: inspired by verifiable events, adapted to UNO’s problem

## V1 building blocks
1. **AgentID** — verifiable identifier anchored by keys, minimal taxonomy, and metadata.
2. **Assertion** — signed statement an agent makes about itself, another agent, or an artifact.
3. **LineageLink** — explicit lineage/derivation link between agents, versions, or branches.
4. **ContinuityEvent** — ordered event log preserving verifiable continuity (creation, key rotation, taxonomy updates, revocation, branch, merge).
5. **WitnessReceipt** — witness receipt proving an event was observed and timestamped.

## Taxonomy and lineage
In UNO, taxonomy and lineage are core, not auxiliary fields.
- **Taxonomy** places an agent in a class, role, capability lineage, and usage context.
- **Lineage** describes where the agent comes from, what it extends, derives from, or replaces.

In V1, continuity must remain readable across both axes:
- **what is this agent?** → taxonomy
- **where does it come from?** → lineage

## Protocol/business boundary
UNO protocol defines verifiable objects, their links, and their proofs. Business layers can use these proofs (reputation, market, scoring, monetization, governance), but they remain outside V1 core.

Structural rule: **no business requirement should deform continuity, taxonomy, or lineage semantics.**

## V1 minimal verification
A third party should be able to verify a minimal package made of an `AgentID`, relevant continuity events, referenced lineage links, available witness receipts, and base assertions when needed.

V1 output is not a business score but a minimal trust verdict: `trust`, `warning`, or `not-trusted`.
