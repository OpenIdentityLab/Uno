# UNO — Protocol Schema V1

## 1. Noyau protocolaire

Objets cœur V1 :
- `AgentID`
- `ContinuityEvent`
- `LineageLink`
- `WitnessReceipt`
- `Assertion` (optionnelle si nécessaire)

Finalité : permettre à un tiers de vérifier **qui est l’agent**, **quelle est sa continuité**, **quelle est sa filiation**, et **s’il existe un problème bloquant**.

---

## 2. Côté agent / couche protocolaire

### Flux nominal
1. L’agent (ou son opérateur) crée un `AgentID`
   - identifiant
   - contrôleur
   - clés
   - taxonomie minimale (`kind / role / context`)
   - `lineageRoot`

2. Il émet un `ContinuityEvent` d’**inception** (`sequence = 0`)
   - signature valide
   - `previousEventDigest = null`
   - `payloadDigest` du contenu d’origine

3. Si l’agent dérive d’un autre, il émet un `LineageLink`
   - relation
   - source
   - racine de lignée

4. Un ou plusieurs témoins observent l’événement
   - émission de `WitnessReceipt`

5. À chaque changement significatif, l’agent émet un nouveau `ContinuityEvent`
   - rotation de clé
   - update taxonomie
   - ancrage assertion
   - update filiation
   - branche
   - fusion
   - révocation

6. La continuité résulte de la chaîne ordonnée :
   - `AgentID`
   - `ContinuityEvent[0..n]`
   - `LineageLink[]`
   - `WitnessReceipt[]`
   - `Assertion[]` si utile

### Schéma mental
```text
Agent / opérateur
  -> crée AgentID
  -> signe ContinuityEvent#0
  -> déclare LineageLink si nécessaire
  -> obtient WitnessReceipt(s)
  -> append ContinuityEvent#1, #2, #3...
  -> produit un proof bundle vérifiable
```

---

## 3. Côté tiers / requêtage preuve

### Entrée minimale
Le tiers fournit soit :
- un `AgentID`
- soit un `proof bundle` contenant les objets nécessaires

### Ce que le tiers vérifie
1. Intégrité des objets
2. Validité des signatures
3. Validité des clés au moment des signatures
4. Ordre et chaînage des `ContinuityEvent`
5. Cohérence minimale de la taxonomie
6. Cohérence minimale de la filiation
7. Présence / absence de `WitnessReceipt`
8. Révocation ou contradiction majeure éventuelle

### Sortie minimale
Le tiers récupère :
- `agentId`
- état retenu
  - taxonomie
  - filiation
  - statut
- verdict
  - `trust`
  - `warning`
  - `not-trusted`
- raisons
- preuves manquantes/faibles

### Schéma mental
```text
Tiers
  -> fournit AgentID ou proof bundle
  -> vérifie signatures + chaîne + filiation + reçus
  -> résout l’état courant
  -> reçoit verdict : trust / warning / not-trusted
```

---

## 4. Question simple à laquelle UNO V1 répond

```text
À qui ai-je affaire,
quelle est sa continuité,
d’où provient-il,
et y a-t-il un problème bloquant de confiance ?
```

---

## 5. Hors scope V1

UNO V1 ne fait pas encore :
- runtime d’agent
- orchestration réseau/infra
- scoring métier
- réputation
- logique business
- jugement moral sur l’agent

Il produit uniquement une **preuve minimale de continuité vérifiable**.
