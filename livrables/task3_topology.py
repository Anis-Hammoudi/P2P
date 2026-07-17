import hashlib
import bisect
import time
import rpyc

# ==========================================
# 1. THE CONSISTENT HASHING RING (Adapted)
# ==========================================
def h(cle):
    return int(hashlib.md5(cle.encode('utf-8')).hexdigest(), 16) % (2**32)

class AnneauVNodes:
    def __init__(self, vnodes_par_noeud=150):
        self.vnodes_par_noeud = vnodes_par_noeud
        self.positions = []
        self.vnode_vers_noeud = {}
        
    def ajouter_noeud(self, nom_noeud):
        """Adds a physical node and its virtual nodes to the ring."""
        for i in range(self.vnodes_par_noeud):
            vnode_name = f"{nom_noeud}#{i}"
            pos = h(vnode_name)
            bisect.insort(self.positions, pos)
            self.vnode_vers_noeud[pos] = nom_noeud
            
    def noeuds_pour(self, cle, R=3):
        """
        NEW: Instead of returning 1 node, this traverses the ring
        to find the first R distinct physical nodes for a given key.
        """
        if not self.positions:
            return []
        
        pos_cle = h(cle)
        idx = bisect.bisect(self.positions, pos_cle)
        
        noeuds_trouves = []
        parcourus = 0
        
        # Traverse the ring until we find R distinct physical nodes
        # or we've checked all vnodes.
        while len(noeuds_trouves) < R and parcourus < len(self.positions):
            vnode_hash = self.positions[idx % len(self.positions)]
            noeud_reel = self.vnode_vers_noeud[vnode_hash]
            
            if noeud_reel not in noeuds_trouves:
                noeuds_trouves.append(noeud_reel)
                
            idx += 1
            parcourus += 1
            
        return noeuds_trouves


# ==========================================
# 2. THE DATA COORDINATOR
# ==========================================
class Coordinator:
    def __init__(self, get_live_nodes_func):
        """
        get_live_nodes_func: Task 2's function to get currently alive nodes.
        It should return a list of connection parameters, e.g., ports [18000, 18001, ...]
        """
        self.get_live_nodes = get_live_nodes_func
        
    def _get_current_ring(self, live_nodes):
        """Creates a fresh ring with the currently alive nodes."""
        anneau = AnneauVNodes()
        for node in live_nodes:
            anneau.ajouter_noeud(node)
        return anneau
        
    def handle_client_put(self, key, value, R=3):
        live_nodes = self.get_live_nodes()
        if not live_nodes:
            print("Coordinator Error: No live nodes available.")
            return False
            
        anneau = self._get_current_ring(live_nodes)
        target_nodes = anneau.noeuds_pour(key, R)
        
        timestamp = time.time()
        success_count = 0
        
        # Route the write to all R replicas
        for node_port in target_nodes:
            try:
                # Assuming node_port is an integer port on localhost
                conn = rpyc.connect("localhost", node_port)
                # Call Task 1's RPC endpoint (Sanaa's code)
                conn.root.put(key, value, timestamp)
                conn.close()
                success_count += 1
                print(f"Written to replica {node_port}")
            except Exception as e:
                print(f"Failed to write to replica {node_port}: {e}")
                
        print(f"Put '{key}' successful on {success_count}/{len(target_nodes)} replicas.")
        return success_count > 0

    def handle_client_get(self, key, R=3):
        live_nodes = self.get_live_nodes()
        if not live_nodes:
            print("Coordinator Error: No live nodes available.")
            return None
            
        anneau = self._get_current_ring(live_nodes)
        target_nodes = anneau.noeuds_pour(key, R)
        
        responses = {} # Format: { port: (value, timestamp) }
        
        # Read from all R replicas
        for node_port in target_nodes:
            try:
                conn = rpyc.connect("localhost", node_port)
                # Task 1's exposed_get should return a tuple (value, timestamp) or None
                result = conn.root.get(key)
                conn.close()
                if result is not None:
                    responses[node_port] = result
            except Exception as e:
                print(f"Failed to read from replica {node_port}: {e}")
                
        if not responses:
            return None
            
        # Find the freshest response based on timestamp
        freshest_port = max(responses, key=lambda p: responses[p][1])
        freshest_value, freshest_ts = responses[freshest_port]
        
        # ------------------------------------------------
        # READ-REPAIR LOGIC
        # ------------------------------------------------
        # Fix any nodes that returned stale data or didn't have the key
        for node_port in target_nodes:
            node_res = responses.get(node_port)
            if not node_res or node_res[1] < freshest_ts:
                print(f"Read-Repair: updating stale node {node_port} with freshest data.")
                try:
                    conn = rpyc.connect("localhost", node_port)
                    conn.root.put(key, freshest_value, freshest_ts)
                    conn.close()
                except Exception:
                    pass # Best effort repair, ignore failures
                    
        return freshest_value
