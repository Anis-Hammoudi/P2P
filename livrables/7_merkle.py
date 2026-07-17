import sys
import os
import time
import threading
import random
import rpyc
import hashlib
import json
from rpyc.utils.server import ThreadedServer

# Ajouter le parent au path pour pouvoir importer task2_state et task3_topology
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from task2_state import merge_heartbeats, increment_own_heartbeat, get_live_nodes
from task3_topology import Coordinator

STORE_LOCK = threading.Lock()
ALL_PORTS = [18000, 18001, 18002, 18003, 18004]
GOSSIP_INTERVAL = 0.5

class MerkleTree:
    """
    Implémentation simplifiée d'un arbre de Merkle binaire.
    """
    def __init__(self, store: dict):
        self.store = store
        self.keys = sorted(list(store.keys()))
        self.nodes = {}
        self.root = None
        self.build_tree()

    def build_tree(self):
        if not self.keys:
            return

        # Niveau des feuilles
        current_level = []
        for k in self.keys:
            val, ts = self.store[k]
            content = f"{k}:{val}:{ts}".encode('utf-8')
            h = hashlib.sha256(content).hexdigest()
            node = {'id': k, 'hash': h, 'type': 'leaf', 'key': k}
            current_level.append(node)
        
        for n in current_level:
            self.nodes[n['id']] = n
            
        # Construction de l'arbre de bas en haut
        level_idx = 1
        while len(current_level) > 1:
            next_level = []
            for i in range(0, len(current_level), 2):
                left = current_level[i]
                right = current_level[i+1] if i+1 < len(current_level) else left
                
                combined_hash = hashlib.sha256((left['hash'] + right['hash']).encode('utf-8')).hexdigest()
                node_id = f"lvl{level_idx}_{i//2}"
                node = {'id': node_id, 'hash': combined_hash, 'type': 'internal', 'left': left['id'], 'right': right['id']}
                next_level.append(node)
                self.nodes[node_id] = node
            current_level = next_level
            level_idx += 1
            
        self.root = current_level[0]['id'] if current_level else None

    def to_dict(self):
        return {'root': self.root, 'nodes': self.nodes}

def get_all_keys(node, tree_nodes):
    if not node: return []
    if node['type'] == 'leaf': return [node['key']]
    keys = []
    keys.extend(get_all_keys(tree_nodes.get(node['left']), tree_nodes))
    if node['left'] != node['right']:
        keys.extend(get_all_keys(tree_nodes.get(node['right']), tree_nodes))
    return keys

def get_diff_keys(local_tree, remote_tree_dict):
    """
    Compare l'arbre local avec l'arbre distant et retourne la liste des clés divergentes.
    Récupère correctement toutes les clés si les structures d'arbres sont désalignées.
    """
    different_keys = set()
    
    def compare_nodes(local_id, remote_id):
        l_node = local_tree.nodes.get(local_id) if local_id else None
        r_node = remote_tree_dict['nodes'].get(remote_id) if remote_id else None
        
        if not l_node and not r_node: return
        if l_node and r_node and l_node['hash'] == r_node['hash']: return # Identique !
        
        # S'ils sont de types différents ou si l'un n'existe pas
        if not l_node or not r_node or l_node['type'] != r_node['type']:
            if l_node: different_keys.update(get_all_keys(l_node, local_tree.nodes))
            if r_node: different_keys.update(get_all_keys(r_node, remote_tree_dict['nodes']))
            return
            
        # S'ils sont tous les deux des feuilles (mais avec un hash différent)
        if l_node['type'] == 'leaf' and r_node['type'] == 'leaf':
            different_keys.add(l_node['key'])
            different_keys.add(r_node['key'])
            return
            
        # Tous les deux des noeuds internes
        l_left = l_node['left']
        l_right = l_node['right']
        r_left = r_node['left']
        r_right = r_node['right']
        
        compare_nodes(l_left, r_left)
        if l_right != l_left or r_right != r_left:
            compare_nodes(l_right, r_right)

    compare_nodes(local_tree.root, remote_tree_dict.get('root'))
    return list(different_keys)


class NodeService(rpyc.Service):
    node_id = None
    local_store = {}
    local_heartbeats = {}
    stats_bytes_received = 0

    def exposed_merkle_sync(self, remote_tree_json, remote_heartbeats):
        """
        1. Reçoit l'arbre distant (hachages)
        2. Le compare avec l'arbre local
        3. Retourne au Nœud A ce dont il a besoin (updates_for_A) 
           et demande ce qu'il lui manque (missing_for_B).
        """
        remote_heartbeats = dict(remote_heartbeats)
        remote_tree_dict = json.loads(remote_tree_json)
        
        with STORE_LOCK:
            merge_heartbeats(self.local_heartbeats, remote_heartbeats)
            local_tree = MerkleTree(self.local_store)
            
            diff_keys = get_diff_keys(local_tree, remote_tree_dict)
            
            updates_for_A = {}
            missing_for_B = []
            
            for k in diff_keys:
                if k in self.local_store:
                    updates_for_A[k] = self.local_store[k]
                # B demande toujours la version de A pour les clés divergentes 
                # afin de faire un LWW merge sur la base du timestamp
                missing_for_B.append(k)

        return (tuple(updates_for_A.items()), missing_for_B)

    def exposed_push_updates(self, updates):
        """
        Reçoit spécifiquement les données demandées et les intègre via LWW.
        """
        updates = dict(updates)
        with STORE_LOCK:
            for key, (remote_value, remote_ts) in updates.items():
                if key not in self.local_store:
                    self.local_store[key] = (remote_value, remote_ts)
                else:
                    _, local_ts = self.local_store[key]
                    if remote_ts > local_ts:
                        self.local_store[key] = (remote_value, remote_ts)
            
            # Calcul du poids des données réellement transférées pour les stats
            self.__class__.stats_bytes_received += sum(len(str(k)) + len(str(v)) for k, (v, ts) in updates.items())
        return True

    def exposed_get_stats(self):
        return self.__class__.stats_bytes_received

    def exposed_put(self, key, value, timestamp):
        with STORE_LOCK:
            current = self.local_store.get(key)
            if current is None or timestamp > current[1]:
                self.local_store[key] = (value, timestamp)
        return True

    def exposed_get(self, key):
        with STORE_LOCK:
            return self.local_store.get(key)

    def exposed_get_live_nodes(self):
        with STORE_LOCK:
            return get_live_nodes(self.local_heartbeats, t_mort=5.0)


def gossip_worker(node_id, local_store, local_heartbeats, peer_ports):
    while True:
        time.sleep(GOSSIP_INTERVAL)
        with STORE_LOCK:
            increment_own_heartbeat(local_heartbeats, node_id)
            candidates = [p for p in local_heartbeats if p != node_id and p in peer_ports]
            tree_a = MerkleTree(local_store)
            tree_a_dict = tree_a.to_dict()
            tree_a_json = json.dumps(tree_a_dict)
            heartbeats_snapshot = dict(local_heartbeats)

        if not candidates:
            continue

        peer_port = random.choice(candidates)
        try:
            conn = rpyc.connect("localhost", peer_port, config={"sync_request_timeout": 2})
            
            updates_for_A, missing_for_B = conn.root.merkle_sync(tree_a_json, tuple(heartbeats_snapshot.items()))
            
            with STORE_LOCK:
                for key, (remote_value, remote_ts) in dict(updates_for_A).items():
                    if key not in local_store:
                        local_store[key] = (remote_value, remote_ts)
                    else:
                        _, local_ts = local_store[key]
                        if remote_ts > local_ts:
                            local_store[key] = (remote_value, remote_ts)
                            
                updates_for_B = {}
                for k in missing_for_B:
                    if k in local_store:
                        updates_for_B[k] = local_store[k]
                        
            if updates_for_B:
                conn.root.push_updates(tuple(updates_for_B.items()))
                
            conn.close()
        except Exception:
            pass


def run_node(node_id):
    local_store = {}
    local_heartbeats = {}
    
    peer_ports = [p for p in ALL_PORTS if p != node_id]
    for peer in peer_ports:
        local_heartbeats[peer] = (0, time.time())
    increment_own_heartbeat(local_heartbeats, node_id)
    
    NodeService.node_id = node_id
    NodeService.local_store = local_store
    NodeService.local_heartbeats = local_heartbeats
    NodeService.stats_bytes_received = 0
    
    gossip_thread = threading.Thread(
        target=gossip_worker,
        args=(node_id, local_store, local_heartbeats, peer_ports),
        daemon=True
    )
    gossip_thread.start()

    server = ThreadedServer(NodeService, port=node_id, protocol_config={"allow_public_attrs": True})
    server.start()

def get_live_nodes_from_cluster():
    for port in ALL_PORTS:
        try:
            conn = rpyc.connect("localhost", port)
            live = list(conn.root.get_live_nodes())
            conn.close()
            return live
        except:
            continue
    return []

if __name__ == "__main__":
    if len(sys.argv) == 2:
        run_node(int(sys.argv[1]))
    else:
        import subprocess
        processes = {}
        print("Démarrage du cluster avec Merkle Tree (5 nœuds)...")
        for port in ALL_PORTS:
            p = subprocess.Popen([sys.executable, "7_merkle.py", str(port)])
            processes[port] = p
            
        time.sleep(3)
        
        try:
            coordinator = Coordinator(get_live_nodes_func=get_live_nodes_from_cluster)
            
            print("\n[1] Injection de 50 clés pour remplir l'arbre de Merkle...")
            for i in range(50):
                coordinator.handle_client_put(f"key_{i}", f"val_{i}", R=3)
                
            time.sleep(5)
            
            print("\n[2] Simulation de désynchronisation :")
            print("    On modifie les valeurs de 'key_10' et 'key_20' directement sur le nœud 18000...")
            try:
                conn = rpyc.connect("localhost", 18000)
                conn.root.put("key_10", "VAL_MODIFIEE", time.time())
                conn.root.put("key_20", "VAL_MODIFIEE", time.time())
                conn.close()
            except:
                pass
                
            print("\n[3] Attente de la boucle d'Anti-Entropie (Gossip Merkle)...")
            time.sleep(10)
            
            print("\n[4] Vérification de la synchronisation ciblée :")
            for port in ALL_PORTS:
                try:
                    conn = rpyc.connect("localhost", port)
                    val10 = conn.root.get("key_10")
                    val20 = conn.root.get("key_20")
                    stats = conn.root.get_stats()
                    conn.close()
                    print(f"Nœud {port} -> key_10: {val10[0] if val10 else None}, key_20: {val20[0] if val20 else None} (Data reçues post-Merkle: {stats} octets)")
                except:
                    pass
                    
            print("\nConclusion : L'arbre a permis de détecter les différences sans envoyer la base de données de 50 clés.")
            print("Seules les valeurs de 'key_10' et 'key_20' (quelques octets) ont été transférées lors de la phase 'push_updates' !")
            
        finally:
            for p in processes.values():
                p.terminate()
