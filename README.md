# ESGI · MASTER 2 — TRAITEMENTS DISTRIBUÉS
## ATELIER 2 : Le magasin pair-à-pair par gossip (Mini-Cassandra)

**Membres du groupe :** Sanaa Zouine, Mehdi Chedad, Anis Hammoudi

### 1. Présentation & objectifs
Ce projet vise à construire un magasin clé-valeur entièrement pair-à-pair, tolérant aux pannes, à cohérence à terme. En réutilisant l'anneau de hachage cohérent de l'atelier précédent pour placer les données, on obtient l'ossature exacte de Cassandra et de Dynamo :
- Membership et détection de panne par gossip (façon SWIM).
- Placement et réplication par anneau.
- Résolution de conflits par horodatage (last-write-wins).

L'asymétrie maître-esclave est rompue : chaque nœud y est à la fois serveur ET client — il répond aux autres et les contacte de lui-même. Il n'y a plus de maître, la communication est bidirectionnelle, et aucun nœud ne représente un point de défaillance unique (SPOF).

### 2. Organisation & mise en place
#### Prérequis techniques
- Python 3
- `pip install rpyc`
- L'anneau cohérent (réimporter la classe `Anneau` de l'atelier hachage, basé sur `hashlib` et `bisect`).

#### Format
- Un cluster local où chaque nœud est un processus sur son propre port (18000, 18001, …).
- Un script pour lancer N nœuds d'un coup.
- Un mini-client hors cluster pour faire des `put`/`get` et pour simuler des pannes (kill/Ctrl-C).

### 3. Structure du dépôt et Livrables

> [!IMPORTANT]
> L'ensemble du code a été structuré pour répondre à l'exigence "pas à pas" de l'énoncé. Vous trouverez **le code final de chaque phase dans le dossier `livrables/`**.
>
> De plus, nous avons développé des modules métier purs (`task2_state.py` et `task3_topology.py`) que les scripts de phase utilisent pour conserver un code propre et facilement testable.
> 
> Un fichier explicatif détaillé sur nos tests et nos décisions d'architecture est disponible dans **`COMPTE_RENDU.md`**.
>
> Un guide pas-à-pas expliquant comment lancer et tester chaque phase est disponible dans **`PRESENTATION.md`**.
#### Phase 0 — Le nœud symétrique
- **Fichier :** `livrables/0_noeud_symetrique.py`
- Écrire un nœud à la fois serveur RPyC et client d'autres nœuds, assurant une communication dans les deux sens sans maître.

#### Phase 1 — Store local + gossip à deux
- **Fichier :** `livrables/1_gossip_paire.py`
- Ajouter un dictionnaire clé → (valeur, horodatage) avec put/get, et des méthodes d'échange (`digest` et `merge`) pour le gossip entre deux nœuds.

#### Phase 2 — N nœuds & convergence
- **Fichiers :** `livrables/2_gossip_n.py` et `livrables/mesure_convergence.py`
- Mise en place de la boucle de gossip : toutes les T secondes, chaque nœud choisit un pair au hasard et échange son état (push puis pull) pour propager l'information.

#### Phase 3 — Conflits & cohérence à terme
- **Fichier :** `livrables/3_lww.py`
- Gérer les écritures concurrentes via Last-Write-Wins (LWW) pour permettre à tous les nœuds de converger vers la même valeur (la plus récente).

#### Phase 4 — Détection de panne par gossip
- **Fichier :** `livrables/4_membership.py`
- Propagation des compteurs de battements (heartbeats) pour déclarer un nœud mort sans aucun détecteur central, basé sur l'absence de mise à jour du compteur.

#### Phase 5 — Anneau + réplication (le mini-Cassandra)
- **Fichier :** `livrables/5_ring_replication.py`
- Réplication des données (facteur R) via l'anneau cohérent. L'écriture est envoyée aux R répliques et la lecture interroge les R répliques pour garder la valeur la plus récente (read-repair).

#### Phase 6 — Chaos & théorème CAP
- **Fichier :** `livrables/6_chaos.py`
- Tolérance aux pannes : simuler la mort de nœuds et constater la survie du système, illustrant le choix AP (Disponibilité et Tolérance au partitionnement) du théorème CAP.

#### Extension E3 — Anti-entropie par arbres de Merkle
- **Fichier :** `livrables/7_merkle.py`
- Implémentation d'un arbre binaire de hachages pour optimiser la phase de Gossip. L'arbre permet d'identifier et de ne transférer que les plages de clés qui diffèrent, réduisant massivement la charge réseau.

#### Phase 7 — Restitution & débat
- Présentation d'une décision de conception et réponses aux questions théoriques sur la convergence logarithmique, LWW, la détection de pannes et le théorème CAP.

### 4. Extensions bonus (Optionnelles)
- **E1 :** Écriture / lecture à quorum (R + W > N) pour retrouver la cohérence forte à la demande.
- **E2 :** Horloges vectorielles à la place de LWW pour détecter les vrais conflits sans perte silencieuse d'écriture.
- **E3 (IMPLÉMENTÉ) :** Anti-entropie par arbres de Merkle pour ne transférer que les plages de clés qui diffèrent (voir `livrables/7_merkle.py`).
- **E4 :** Réglage de la dissémination (fan-out & période T) et mesure de la convergence face à la charge réseau.

### Pièges à éviter
- Serveur bloquant : lancer la boucle de gossip dans un thread démon AVANT le serveur.
- Toujours utiliser des verrous lors d'accès concurrents (thread serveur et thread gossip).
- Toujours fusionner par "plus récent" pour éviter l'oscillation.
- LWW perd des écritures, à considérer en fonction du besoin.
- Détecter une panne ne la prouve pas (peut juste être un nœud lent).
