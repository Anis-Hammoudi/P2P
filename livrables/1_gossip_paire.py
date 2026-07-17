import sys
import time
import threading
import rpyc
from rpyc.utils.server import ThreadedServer
from task2_state import merge_stores

STORE_LOCK = threading.Lock()

class NodeService(rpyc.Service):
    """RPyC service exposed by every node."""
    node_id = None
    local_store = {}

    def exposed_gossip(self, remote_store):
        """Receive state pushed by a peer and merge it into our own."""
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

    def exposed_print_store(self):
        with STORE_LOCK:
            print(f"--- [Node {self.node_id}] Store: {self.local_store} ---")
        return True

def gossip_worker(node_id, peer_port, local_store):
    """Daemon loop: push state to the peer."""
    while True:
        time.sleep(3.0)
        with STORE_LOCK:
            store_snapshot = dict(local_store)
            
        try:
            conn = rpyc.connect("localhost", peer_port, config={"sync_request_timeout": 2})
            # Send as tuples for safe serialization
            conn.root.gossip(tuple(store_snapshot.items()))
            conn.close()
        except Exception as e:
            pass # Ignore connection failures for the peer if it's dead

def run_node(node_id, peer_port):
    local_store = {}
    NodeService.node_id = node_id
    NodeService.local_store = local_store
    
    gossip_thread = threading.Thread(
        target=gossip_worker,
        args=(node_id, peer_port, local_store),
        daemon=True
    )
    gossip_thread.start()

    server = ThreadedServer(NodeService, port=node_id, protocol_config={"allow_public_attrs": True})
    print(f"[Node {node_id}] RPyC server listening on port {node_id}. Gossiping with {peer_port}...")
    server.start()

if __name__ == "__main__":
    if len(sys.argv) < 3:
        print("Usage: python 1_gossip_paire.py <my_port> <peer_port>")
        sys.exit(1)
    
    run_node(int(sys.argv[1]), int(sys.argv[2]))
