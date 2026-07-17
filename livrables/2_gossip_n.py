import sys
import time
import threading
import random
import rpyc
from rpyc.utils.server import ThreadedServer
from task2_state import merge_stores

STORE_LOCK = threading.Lock()
ALL_PORTS = [18000, 18001, 18002, 18003, 18004]
GOSSIP_INTERVAL = 1.0

class NodeService(rpyc.Service):
    """RPyC service exposed by every node."""
    node_id = None
    local_store = {}

    def exposed_gossip(self, remote_store):
        remote_store = dict(remote_store)
        with STORE_LOCK:
            merge_stores(self.local_store, remote_store)
        return True

    def exposed_put(self, key, value, timestamp):
        with STORE_LOCK:
            current = self.local_store.get(key)
            if current is None or timestamp > current[1]:
                self.local_store[key] = (value, timestamp)
        return True

    def exposed_get(self, key):
        with STORE_LOCK:
            return self.local_store.get(key)

    def exposed_has_key(self, key):
        with STORE_LOCK:
            return key in self.local_store

def gossip_worker(node_id, local_store, peer_ports):
    """Daemon loop: push state to a random peer."""
    while True:
        time.sleep(GOSSIP_INTERVAL)
        with STORE_LOCK:
            store_snapshot = dict(local_store)
            
        peer_port = random.choice(peer_ports)
        try:
            conn = rpyc.connect("localhost", peer_port, config={"sync_request_timeout": 2})
            conn.root.gossip(tuple(store_snapshot.items()))
            conn.close()
        except Exception as e:
            pass 

def run_node(node_id):
    local_store = {}
    NodeService.node_id = node_id
    NodeService.local_store = local_store
    
    peer_ports = [p for p in ALL_PORTS if p != node_id]
    
    gossip_thread = threading.Thread(
        target=gossip_worker,
        args=(node_id, local_store, peer_ports),
        daemon=True
    )
    gossip_thread.start()

    server = ThreadedServer(NodeService, port=node_id, protocol_config={"allow_public_attrs": True})
    print(f"[Node {node_id}] RPyC server listening on port {node_id}")
    server.start()

if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: python 2_gossip_n.py <my_port>")
        sys.exit(1)
    
    run_node(int(sys.argv[1]))
