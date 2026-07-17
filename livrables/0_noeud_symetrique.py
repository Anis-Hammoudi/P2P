import sys
import time
import threading
import rpyc
from rpyc.utils.server import ThreadedServer

class NodeService(rpyc.Service):
    """RPyC service exposed by every node."""
    node_id = None

    def exposed_ping(self, sender_id):
        """Simple ping endpoint to prove bidirectionality."""
        print(f"[Node {self.node_id}] Received ping from Node {sender_id}!")
        return True

def client_worker(node_id, peer_port):
    """Daemon thread that acts as a client connecting to a peer."""
    while True:
        time.sleep(3.0) # Ping every 3 seconds
        try:
            conn = rpyc.connect("localhost", peer_port, config={"sync_request_timeout": 2})
            conn.root.ping(node_id)
            conn.close()
        except Exception as e:
            print(f"[Node {node_id}] Failed to connect to Node {peer_port}: {e}")

def run_node(node_id, peer_port):
    NodeService.node_id = node_id
    
    # Start the client worker in a separate thread
    client_thread = threading.Thread(
        target=client_worker,
        args=(node_id, peer_port),
        daemon=True
    )
    client_thread.start()

    # Start the server in the main thread
    server = ThreadedServer(NodeService, port=node_id, protocol_config={"allow_public_attrs": True})
    print(f"[Node {node_id}] RPyC server listening on port {node_id}. Will ping port {peer_port}...")
    server.start()

if __name__ == "__main__":
    if len(sys.argv) < 3:
        print("Usage: python 0_noeud_symetrique.py <my_port> <peer_port>")
        sys.exit(1)
    
    run_node(int(sys.argv[1]), int(sys.argv[2]))
