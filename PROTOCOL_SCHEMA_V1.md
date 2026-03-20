# UNO — Protocol Schema V1

## 1. Core protocol objects

V1 core objects:
- `AgentID`
- `ContinuityEvent`
- `LineageLink`
- `WitnessReceipt`
- `Assertion` (optional when needed)

Goal: allow a third party to verify **who the agent is**, **what its continuity is**, **what its lineage is**, and **whether a blocking trust issue exists**.

---

## 2. Agent-side protocol flow

### Nominal flow
1. The agent (or its operator) creates an `AgentID`
   - identifier
   - controller
   - keys
   - minimal taxonomy (`kind / role / context`)
   - `lineageRoot`

2. It emits an inception `ContinuityEvent` (`sequence = 0`)
   - valid signature
   - `previousEventDigest = null`
   - origin `payloadDigest`

3. If the agent derives from another one, it emits a `LineageLink`
   - relation
   - source
   - lineage root

4. One or more witnesses observe the event
   - emit `WitnessReceipt`

5. For each meaningful change, the agent emits a new `ContinuityEvent`
   - key rotation
   - taxonomy update
   - assertion anchor
   - lineage update
   - branch
   - merge
   - revocation

6. Continuity is the ordered chain:
   - `AgentID`
   - `ContinuityEvent[0..n]`
   - `LineageLink[]`
   - `WitnessReceipt[]`
   - `Assertion[]` when relevant

### Mental model
```text
Agent / operator
  -> creates AgentID
  -> signs ContinuityEvent#0
  -> declares LineageLink when needed
  -> obtains WitnessReceipt(s)
  -> appends ContinuityEvent#1, #2, #3...
  -> produces a verifiable proof bundle
```

---

## 3. Third-party verification flow

### Minimal input
A verifier provides either:
- an `AgentID`, or
- a `proof bundle` containing the required objects

### What is verified
1. Object integrity
2. Signature validity
3. Key validity at signature time
4. `ContinuityEvent` ordering and chaining
5. Minimal taxonomy coherence
6. Minimal lineage coherence
7. Presence / absence of `WitnessReceipt`
8. Revocation or major contradiction

### Minimal output
The verifier gets:
- `agentId`
- retained state:
  - taxonomy
  - lineage
  - status
- verdict:
  - `trust`
  - `warning`
  - `not-trusted`
- reasons
- missing/weak evidence

### Mental model
```text
Verifier
  -> provides AgentID or proof bundle
  -> verifies signatures + chain + lineage + receipts
  -> resolves retained state
  -> returns verdict: trust / warning / not-trusted
```

---

## 4. Simple question answered by UNO V1

```text
Who am I dealing with,
what is its continuity,
where does it come from,
and is there a blocking trust issue?
```

---

## 5. Out of scope for V1

UNO V1 does not provide:
- agent runtime
- network/infra orchestration
- business scoring
- reputation systems
- business logic
- moral judgement over agents

It provides only a **minimal verifiable continuity proof**.
