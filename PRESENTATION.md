# Guide de Présentation : Démonstration Pas à Pas

Ce document explique comment lancer les différents livrables de l'atelier pour une démonstration ou une soutenance. Tous les scripts doivent être exécutés depuis le dossier `livrables/`.

Ouvrez un terminal et placez-vous dans le dossier :
```bash
cd livrables
```

> **Note :** La plupart des scripts des phases avancées (à partir de la phase 2) intègrent leur propre scénario de test automatisé. Il suffit de les lancer sans arguments pour qu'ils créent le cluster, simulent des clients, effectuent les opérations et affichent les résultats !

---

### Phase 0 : Le Nœud Symétrique (Ping bidirectionnel)
* **Objectif :** Montrer qu'un nœud est à la fois serveur et client (il n'y a pas de maître).
* **Comment tester :** Ouvrez **deux terminaux** distincts.
  * Dans le terminal 1 : `python 0_noeud_symetrique.py 18000 18001`
  * Dans le terminal 2 : `python 0_noeud_symetrique.py 18001 18000`
* **Ce qu'il se passe :** Les deux nœuds vont se "pinger" mutuellement toutes les 3 secondes, prouvant la bidirectionnalité.

### Phase 1 : Store local et Gossip à deux
* **Objectif :** Montrer la structure de base (Gossip) avec un dictionnaire `local_store`.
* **Comment tester :** Comme pour la phase 0, ouvrez **deux terminaux**.
  * Terminal 1 : `python 1_gossip_paire.py 18000 18001`
  * Terminal 2 : `python 1_gossip_paire.py 18001 18000`
* **Explication :** La base de la propagation. Vous pouvez observer les serveurs écouter et échanger.

---

### Phase 2 : Gossip à N nœuds (Mesure de convergence)
* **Objectif :** Démontrer la vitesse de la propagation virale (Anti-entropie).
* **Comment tester :** Un seul terminal suffit (le script gère tout).
  * Lancer : `python mesure_convergence.py`
* **Ce qu'il se passe :** Le script démarre 5 nœuds, injecte une clé dans un seul d'entre eux, puis mesure le temps (en secondes) nécessaire pour que l'information se propage à 100% du réseau grâce au protocole Gossip aléatoire.

### Phase 3 : Conflits et Cohérence à Terme (LWW)
* **Objectif :** Démontrer la règle du *Last-Write-Wins* pour la résolution de conflits.
* **Comment tester :** 
  * Lancer : `python 3_lww.py`
* **Ce qu'il se passe :** Le script écrit volontairement deux valeurs différentes en même temps pour la même clé sur deux nœuds distants (l'une des requêtes a un *timestamp* très légèrement supérieur). Le Gossip fait converger automatiquement tous les nœuds vers la valeur la plus récente.

### Phase 4 : Détection de Panne (Membership décentralisé)
* **Objectif :** Prouver que les nœuds peuvent détecter la mort d'un de leurs pairs sans serveur central de monitoring.
* **Comment tester :** 
  * Lancer : `python 4_membership.py`
* **Ce qu'il se passe :** 5 nœuds s'échangent des *heartbeats*. Le script tue brutalement l'un d'eux (le 18002). Après 5 secondes (le `t_mort`), les autres nœuds s'aperçoivent que son compteur n'évolue plus et le déclarent mort de manière autonome.

### Phase 5 : Le Mini-Cassandra (Anneau + Réplication)
* **Objectif :** Montrer le routage complet d'une donnée via le hachage cohérent avec un facteur $R=3$.
* **Comment tester :** 
  * Lancer : `python 5_ring_replication.py`
* **Ce qu'il se passe :** Un Coordinateur hache une clé cliente, trouve sa position sur l'anneau physique, et copie explicitement l'information sur les 3 nœuds responsables.

### Phase 6 : Chaos Monkey et Théorème CAP
* **Objectif :** Démontrer le choix **AP** (Disponibilité / Partition Tolerance).
* **Comment tester :** 
  * Lancer : `python 6_chaos.py`
* **Ce qu'il se passe :** Un client bombarde l'anneau de requêtes en boucle, pendant qu'un "Chaos Monkey" détruit et redémarre des nœuds au hasard. Tant qu'au moins 1 réplique sur 3 survit, aucune donnée n'est perdue et le client ne subit aucun blocage.

### Extension E3 : Anti-entropie optimisée par Arbres de Merkle
* **Objectif :** Démontrer l'économie de la bande passante.
* **Comment tester :** 
  * Lancer : `
  `
* **Ce qu'il se passe :** 50 clés sont écrites. Le script crée une divergence artificielle sur 2 clés. Lors du Gossip, au lieu d'envoyer la lourde base des 50 clés, les nœuds n'échangent qu'un arbre binaire léger (JSON), repèrent le delta, et ne téléchargent que les quelques octets des 2 clés manquantes.
