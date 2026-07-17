"""
Task 2 : State Management, LWW & Failure Detection
====================================================
Owner : Mehdi Cheddad

Fonctions pures pour la gestion d'état du mini-Cassandra.
Aucune logique réseau, aucun verrou — uniquement des manipulations
de dictionnaires Python en mémoire.
"""

import time


# ------------------------------------------------------------------
# 1. LWW Data Store Merge
# ------------------------------------------------------------------
def merge_stores(local_store: dict, remote_store: dict) -> None:
    """
    Fusionne le store distant dans le store local (IN-PLACE).

    Format des données : { 'key': ('value', float_timestamp) }

    Règle LWW (Last-Write-Wins) :
      - Si la clé n'est pas dans local_store → l'ajouter.
      - Si elle y est → garder la valeur avec le timestamp STRICTEMENT supérieur.
      - En cas d'égalité de timestamps → on garde le local (pas strictement >).
    """
    for key, (remote_value, remote_ts) in remote_store.items():
        if key not in local_store:
            local_store[key] = (remote_value, remote_ts)
        else:
            _, local_ts = local_store[key]
            if remote_ts > local_ts:
                local_store[key] = (remote_value, remote_ts)


# ------------------------------------------------------------------
# 2. Heartbeat Merge
# ------------------------------------------------------------------
def merge_heartbeats(local_heartbeats: dict, remote_heartbeats: dict) -> None:
    """
    Fusionne les heartbeats distants dans les heartbeats locaux (IN-PLACE).

    Format : { node_id: (int_counter, float_local_timestamp) }

    Règle :
      - Si le node_id n'est pas connu localement → l'ajouter avec
        le counter distant et time.time() comme timestamp local.
      - Si le counter distant est STRICTEMENT supérieur au counter local →
        mettre à jour le counter ET le timestamp local à time.time().
      - Sinon → ne rien faire.
    """
    for node_id, (remote_counter, _remote_ts) in remote_heartbeats.items():
        if node_id not in local_heartbeats:
            local_heartbeats[node_id] = (remote_counter, time.time())
        else:
            local_counter, _local_ts = local_heartbeats[node_id]
            if remote_counter > local_counter:
                local_heartbeats[node_id] = (remote_counter, time.time())


# ------------------------------------------------------------------
# 3. Failure Detection (The Reaper)
# ------------------------------------------------------------------
def get_live_nodes(heartbeats: dict, t_mort: float = 10.0) -> list:
    """
    Retourne la liste des node_ids considérés comme vivants.

    Règle : un nœud est vivant si
        (time.time() - float_local_timestamp) < t_mort
    """
    now = time.time()
    return [
        node_id
        for node_id, (_counter, last_updated) in heartbeats.items()
        if (now - last_updated) < t_mort
    ]


# ------------------------------------------------------------------
# 4. Self Heartbeat
# ------------------------------------------------------------------
def increment_own_heartbeat(heartbeats: dict, my_node_id) -> None:
    """
    Incrémente le counter du nœud local et met à jour son timestamp
    à time.time().

    Si le nœud n'existe pas encore dans le dict, l'initialise à
    (1, time.time()).
    """
    if my_node_id in heartbeats:
        current_counter, _ = heartbeats[my_node_id]
        heartbeats[my_node_id] = (current_counter + 1, time.time())
    else:
        heartbeats[my_node_id] = (1, time.time())
