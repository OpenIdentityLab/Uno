# UNO verify-minimal V1

## What a verifier provides
- an **AgentID**
- the required **ContinuityEvent** chain linking presented state to known origin
- the referenced **LineageLink** objects
- available **WitnessReceipt** objects
- when needed, referenced **Assertion** objects

## What is verified
- object and signature integrity
- continuity event ordering and chaining
- key validity at signature time
- minimal coherence of declared taxonomy
- minimal coherence of declared lineage
- presence or absence of observable witness evidence

## What is returned
- a **verdict**: `trust`, `warning`, or `not-trusted`
- the verified **agentId**
- retained **state** (taxonomy, lineage, status)
- **reasons** for the verdict
- **missing or weak evidence**, when relevant

## Cases
### trust
Valid chain, valid signatures, readable lineage, no blocking contradiction.

### warning
Valid chain, but incomplete or weak evidence: missing external witness, missing base assertion, partial taxonomy/lineage, non-blocking ambiguity.

### not-trusted
Invalid signature, chain break, revoked key misuse, or major continuity/taxonomy/lineage incoherence.
