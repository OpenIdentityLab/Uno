# UNO — architecture V1

## Finalité
UNO est un protocole de continuité vérifiable pour agents IA. Son rôle n'est pas de "faire tourner" un agent, mais de rendre vérifiables son identité, ses assertions clés, sa filiation et la continuité de ses états dans le temps.

## Non-goals V1
- pas de runtime d'agents
- pas d'orchestration infra, réseau ou consensus global
- pas de couche économique dans le cœur du protocole
- pas de copie naïve de KERI : inspiration sur les événements vérifiables, adaptation au problème UNO

## Briques V1
1. **AgentID** — identifiant vérifiable, ancré par clés, taxonomie et métadonnées minimales.
2. **Assertion** — énoncé signé qu'un agent porte sur lui-même, un autre agent ou un artefact.
3. **LineageLink** — lien explicite de filiation ou de dérivation entre agents, versions ou branches.
4. **ContinuityEvent** — journal d'événements ordonnés qui maintient la continuité vérifiable (création, rotation, mise à jour de taxonomie, révocation, bifurcation, fusion).
5. **WitnessReceipt** — reçu de témoin attestant qu'un événement a été observé et horodaté.

## Taxonomie et filiation
Chez UNO, la taxonomie et la filiation ne sont pas des champs annexes.
- **Taxonomie** : elle situe l'agent dans une classe, un rôle, une lignée de capacités et un contexte d'usage.
- **Filiation** : elle décrit d'où vient l'agent, ce qu'il prolonge, ce qu'il dérive ou ce qu'il remplace.

En V1, toute continuité doit rester lisible à travers ces deux axes :
- **qui est cet agent ?** → taxonomie
- **de qui / de quoi provient-il ?** → filiation

## Frontière protocole / business
Le protocole UNO décrit des objets vérifiables, leurs liens et leurs preuves. La couche business peut exploiter ces preuves (réputation, marché, scoring, monétisation, gouvernance), mais elle reste hors du noyau V1.

Règle structurante : **aucune exigence économique ne doit déformer le modèle de continuité, de taxonomie ou de filiation**.

## Vérification minimale V1
Un tiers doit pouvoir vérifier un paquet minimal composé d'un AgentID, des événements de continuité pertinents, des liens de filiation invoqués, des reçus de témoin disponibles, et si nécessaire des assertions de base.

Le résultat de V1 n'est pas un score métier mais un verdict de confiance minimal : `trust`, `warning` ou `not-trusted`.
