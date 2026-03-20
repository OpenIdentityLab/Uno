# UNO verify-minimal V1

## Ce qu’un tiers fournit
- un **AgentID**
- les **ContinuityEvent** nécessaires pour relier l'état présenté à l'origine connue
- les **LineageLink** invoqués
- les **WitnessReceipt** disponibles
- si utile, les **Assertion** référencées par ces liens

## Ce qui est vérifié
- intégrité des objets et des signatures
- ordre et chaînage des événements de continuité
- validité des clés au moment des signatures
- cohérence minimale de la taxonomie déclarée
- cohérence minimale de la filiation déclarée
- présence ou absence de témoignages observables

## Ce qui est renvoyé
- un **verdict** : `trust`, `warning`, ou `not-trusted`
- l'**agentId** vérifié
- l'**état** retenu (taxonomie, filiation, statut)
- les **raisons** du verdict
- les **preuves manquantes ou faibles**, le cas échéant

## Cas
### trust
Chaîne valide, signatures valides, filiation lisible, aucune contradiction bloquante.

### warning
Chaîne valide mais preuve incomplète ou faible : témoignages absents, assertion de base manquante, taxonomie/filiation partielle, ambiguïté non bloquante.

### not-trusted
Signature invalide, rupture de chaîne, clé révoquée ou incohérence majeure de continuité, de taxonomie ou de filiation.
