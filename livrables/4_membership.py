import sys
import time
import threading
import random
import rpyc
from rpyc.utils.server import ThreadedServer
from task2_state import merge_stores, merge_heartbeats, increment_own_heartbeat, get_live_nodes

STORE_LOCK = threading.Lock()
ALL_PORTS = [18000, 18001, 18002, 18003, 18004]
GOSSIP_INTERVAL = 1.0

class NodeService(rpyc.Service):
    node_id = None
    local_store = {}
    local_heartbeats = {}

    def exposed_gossip(self, remote_store, remote_heartbeats):
        remote_store = dict(remote_store)
        remote_heartbeats = dict(remote_heartbeats)
        with STORE_LOCK:
            merge_stores(self.local_store, remote_store)
            merge_heartbeats(self.local_heartbeats, remote_heartbeats)
        return True

    def exposed_get_live_nodes(self):
        with STORE_LOCK:
            # We use t_mort = 5.0 seconds for quick testing
            return get_live_nodes(self.local_heartbeats, t_mort=5.0)

def gossip_worker(node_id, local_store, local_heartbeats, peer_ports):
    while True:
        time.sleep(GOSSIP_INTERVAL)
        with STORE_LOCK:
            increment_own_heartbeat(local_heartbeats, node_id)
            candidates = [p for p in local_heartbeats if p != node_id and p in peer_ports]
            store_snapshot = dict(local_store)
            heartbeats_snapshot = dict(local_heartbeats)

        if not candidates:
            continue

        peer_port = random.choice(candidates)
        try:
            conn = rpyc.connect("localhost", peer_port, config={"sync_request_timeout": 2})
            conn.root.gossip(tuple(store_snapshot.items()), tuple(heartbeats_snapshot.items()))
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
    
    gossip_thread = threading.Thread(
        target=gossip_worker,
        args=(node_id, local_store, local_heartbeats, peer_ports),
        daemon=True
    )
    gossip_thread.start()

    server = ThreadedServer(NodeService, port=node_id, protocol_config={"allow_public_attrs": True})
    server.start()

if __name__ == "__main__":
    if len(sys.argv) == 2:
        run_node(int(sys.argv[1]))
    else:
        # Run the experiment
        import subprocess
        processes = {}
        print("Démarrage de 5 nœuds...")
        for port in ALL_PORTS:
            p = subprocess.Popen([sys.executable, "4_membership.py", str(port)])
            processes[port] = p
            
        time.sleep(3) # Let them gossip
        
        try:
            conn = rpyc.connect("localhost", 18000)
            live = list(conn.root.get_live_nodes())
            conn.close()
            print(f"\n[1] Au dpart, le nud 18000 voit vivants : {live}")
            
            print("\n[2] On tue brusquement le nœud 18002 !")
            processes[18002].terminate()
            
            print("\n[3] Attente du délai t_mort (5s) pour que les autres s'en aperçoivent...")
            for i in range(7):
                time.sleep(1)
                try:
                    conn = rpyc.connect("localhost", 18000)
                    live = list(conn.root.get_live_nodes())
                    conn.close()
                    print(f"  t={i}s -> Vivants selon 18000 : {live}")
                except:
                    pass
                    
            print("\nConclusion : 18000 a détecté la mort de 18002 sans détecteur central, uniquement parce que son compteur de battements n'était plus propagé !")
            
        finally:
            for p in processes.values():
                p.terminate()
