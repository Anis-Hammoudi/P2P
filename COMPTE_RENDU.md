# Compte Rendu : Architecture et Tests du Mini-Cassandra

Ce document explique le processus de développement, les décisions d'architecture prises par le groupe (Sanaa, Mehdi, Anis), le refactoring effectué pour répondre aux exigences de l'énoncé, ainsi que les résultats des tests de validation.

## 1. Notre approche initiale : Modularité et Séparation des préoccupations
Dans un premier temps, nous avons conçu le système de manière très modulaire pour faciliter le travail en équipe et garantir un code propre. Nous avions divisé le travail en trois tâches distinctes :
* **Sanaa (Task 1)** : La couche réseau via RPyC (`0_noeud_symetrique.py`).
* **Mehdi (Task 2)** : Les fonctions "pures" de gestion d'état, de Last-Write-Wins (LWW) et de détection de panne (`task2_state.py`).
* **Anis (Task 3)** : Le coordinateur, le hachage cohérent (Ring) et le routage (`task3_topology.py`).

Cette architecture était excellente pour la séparation des responsabilités. Le nœud réseau (Sanaa) appelait les fonctions pures (Mehdi) pour fusionner son état, tandis que le Coordinateur (Anis) interrogeait le réseau pour placer les données sur l'anneau.

## 2. Le Refactoring : Création du dossier `livrables/`
L'énoncé exigeait une approche "pas à pas", où chaque phase (de 0 à 6) devait produire un fichier exécutable distinct montrant l'évolution incrémentale du système (du simple ping bidirectionnel jusqu'au cluster de test de chaos). 

Pour satisfaire cette exigence d'évaluation, nous avons créé le dossier `livrables/`. Nous avons réutilisé la logique métier robuste de `task2_state.py` et `task3_topology.py`, mais nous avons construit des scripts dédiés pour chaque phase :
* `0_noeud_symetrique.py` : Un simple nœud RPyC client/serveur sans aucun état, prouvant la bidirectionnalité.
* `1_gossip_paire.py` : Introduction du `local_store` et de la fusion LWW.
* `2_gossip_n.py` : Introduction de la boucle d'anti-entropie (Push Gossip).
* `4_membership.py` : Introduction de la détection de panne locale par battements de cœur.
* `5_ring_replication.py` : Le nœud final intégrant le système complet (Mini-Cassandra).

## 3. Résultats et Validation

Nous avons créé plusieurs scripts de tests automatisés pour prouver le bon fonctionnement de notre système distribué. Voici les résultats observés :

### Propagation Gossip (Phase 2 - `mesure_convergence.py`)
* **Test** : Nous avons lancé 5 nœuds, écrit une seule clé sur le nœud 1, et mesuré le temps nécessaire pour que tous les autres nœuds l'apprennent via Gossip (période T=1s).
* **Résultat** : La convergence totale a été atteinte en **~2.37 secondes**. Cela valide que la propagation virale est très rapide (exponentielle/logarithmique) et non linéaire, même sans que les nœuds ne se concertent.

### Résolution de Conflits LWW (Phase 3 - `3_lww.py`)
* **Test** : Nous avons simulé une partition réseau en écrivant simultanément deux valeurs différentes pour la même clé sur deux nœuds distants (`alice@old.com` vs `alice@new.com`). L'une avait un horodatage (timestamp) très légèrement supérieur.
* **Résultat** : Après quelques secondes de Gossip, les 5 nœuds ont tous convergé vers `alice@new.com`. Cela prouve que notre règle Last-Write-Wins appliquée localement sur chaque nœud garantit une cohérence à terme (Eventual Consistency) sans recourir à un consensus complexe (comme Paxos ou Raft).

### Détection de pannes décentralisée (Phase 4 - `4_membership.py`)
* **Test** : Nous avons lancé un cluster, laissé les nœuds échanger leurs heartbeats, puis nous avons brutalement "tué" (SIGTERM) un des nœuds. 
* **Résultat** : Après le délai `t_mort` (5 secondes), les nœuds survivants ont automatiquement retiré le nœud mort de leur liste locale de nœuds vivants. Aucun ping explicite n'a été nécessaire ; l'absence de mise à jour du compteur de battements relayé par les pairs a suffi.

### Routage et Réplication (Phase 5 - `5_ring_replication.py`)
* **Test** : Le Coordinateur a reçu l'ordre d'écrire une donnée avec un facteur de réplication de `R=3`.
* **Résultat** : La donnée a été hachée et routée avec succès vers exactement 3 nœuds physiques distincts sur l'anneau de hachage.
* **Mécanique d'isolation ($R=3$)** : Contrairement au protocole Gossip qui est viral (propagation à tous), la réplication de la donnée est dirigée (*Push ciblé*). Le Coordinateur calcule la "Preference List" (les 3 nœuds responsables consécutifs sur l'anneau) et leur envoie la requête d'écriture de façon explicite. Les autres nœuds ne reçoivent jamais cette requête directe et ne récupèrent donc pas la donnée.

### Résilience du Coordinateur et Tolérance aux Pannes
Dans notre architecture symétrique (sans nœud "Maître" ou SPOF), **n'importe quel nœud peut jouer le rôle de Coordinateur** pour une requête client.
* **Si le coordinateur meurt avant la réplication** : Le client subit un *timeout*. Il retente simplement sa requête auprès d'un autre nœud du cluster, qui devient le nouveau coordinateur.
* **Si le coordinateur meurt pendant la réplication (Écriture partielle)** : S'il a envoyé la donnée à 1 seule réplique sur les 3 prévues avant de crasher, le système ne perd pas la donnée. La cohérence à terme (*Eventual Consistency*) prend le relais : la boucle d'anti-entropie (Gossip) de la réplique survivante finira par propager cette nouvelle donnée aux 2 autres nœuds légitimes responsables. Le manque est ainsi réparé automatiquement en arrière-plan.

### Chaos et Théorème CAP (Phase 6 - `6_chaos.py`)
* **Test** : Le script "Chaos Monkey" tuait et redémarrait des nœuds au hasard pendant qu'un client effectuait des requêtes continues.
* **Résultat** : Tant qu'au moins 1 réplique sur les `R=3` restait en vie, le client pouvait toujours lire et écrire ses données sans blocage. Le système a parfaitement démontré le choix **AP (Disponibilité et Tolérance au partitionnement)** du théorème CAP : il a sacrifié la cohérence forte immédiate pour rester entièrement disponible même sous des conditions chaotiques.

### Extension E3 : Anti-entropie par Arbres de Merkle (`7_merkle.py`)
* **Problématique initiale** : Lors du Gossip (phases 1 à 6), les nœuds transmettaient l'intégralité de leur base de données pour se synchroniser. Sur un système de production, cela sature la bande passante.
* **Solution (Arbre de Merkle)** : Nous avons organisé les clés triées dans un arbre binaire de hachages. Lors d'un échange, les nœuds ne s'envoient que la structure des hachages (extrêmement légère, au format JSON). En descendant dans l'arbre, le nœud distant repère de manière déterministe les feuilles (clés) exactes qui diffèrent.
* **Test et Résultat** : Sur 50 clés insérées, nous avons volontairement modifié 2 clés sur un seul nœud (désynchronisation). Grâce à l'arbre, les nœuds ont détecté ces deux uniques différences et **seuls les octets de ces 2 clés ont été transférés** pour rétablir la synchronisation LWW, réduisant drastiquement le trafic réseau.

## Conclusion
Le projet démontre avec succès la création d'un système distribué résilient sans aucun Single Point of Failure (SPOF). En déléguant la gestion du cluster aux nœuds eux-mêmes (symétrie) et en assumant une cohérence à terme, le système devient capable de tolérer de lourdes pannes réseau et matérielles.
