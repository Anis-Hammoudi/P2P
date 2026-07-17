import time
import task3_topology
from task3_topology import Coordinator

# 1. Mock the network state (What Sanaa and Mehdi would normally manage)
# Format: { port: { 'key': ('value', float_timestamp) } }
MOCK_NETWORK_STORE = {
    18000: {},
    18001: {},
    18002: {},
    18003: {},
    18004: {}
}

def mock_get_live_nodes():
    # Return all ports as "alive" for the test
    return list(MOCK_NETWORK_STORE.keys())

# 2. Mock RPyC connection
class MockRPCConnection:
    def __init__(self, port):
        self.port = port
        self.root = self # RPyC standard uses conn.root.method()
        
    def put(self, key, value, timestamp):
        # Simulate Task 2's LWW logic at the destination node
        store = MOCK_NETWORK_STORE[self.port]
        if key not in store or store[key][1] < timestamp:
            store[key] = (value, timestamp)
            
    def get(self, key):
        return MOCK_NETWORK_STORE[self.port].get(key)
        
    def close(self):
        pass

# Monkey-patch rpyc.connect in task3_topology to use our mock instead of real network
task3_topology.rpyc.connect = lambda host, port: MockRPCConnection(port)

def print_stores():
    print("\n--- Current Node Stores ---")
    for port, store in MOCK_NETWORK_STORE.items():
        # Truncate timestamp for cleaner printing
        clean_store = {k: (v, round(ts, 2)) for k, (v, ts) in store.items()}
        print(f"Node {port}: {clean_store}")
    print("---------------------------\n")

def run_tests():
    print("Initializing Coordinator with Mocked RPC...")
    coordinator = Coordinator(get_live_nodes_func=mock_get_live_nodes)
    
    key1 = "test_user_1"
    
    print(f"\n[TEST 1] Client PUT: '{key1}' -> 'v1' (R=3)")
    coordinator.handle_client_put(key1, "v1", R=3)
    print_stores()
    
    print(f"\n[TEST 2] Client GET: '{key1}' (R=3)")
    val = coordinator.handle_client_get(key1, R=3)
    print(f"-> Client received: {val}")
    
    print(f"\n[TEST 3] Simulating Stale Data for Read-Repair")
    # Manually corrupt one of the replicas so it has an old timestamp and value
    nodes_with_data = [p for p, s in MOCK_NETWORK_STORE.items() if key1 in s]
    if len(nodes_with_data) > 0:
        stale_node = nodes_with_data[0]
        # Set to old value and old timestamp (0.0)
        MOCK_NETWORK_STORE[stale_node][key1] = ("OLD_VALUE_BUG", 0.0)
        print(f"-> Manually corrupted Node {stale_node} with ('OLD_VALUE_BUG', 0.0)")
    print_stores()
    
    print(f"\n[TEST 4] Client GET (Should Trigger Read-Repair): '{key1}'")
    val = coordinator.handle_client_get(key1, R=3)
    print(f"-> Client received: {val} (Should still be 'v1' because it picks the freshest)")
    print("-> Checking if Read-Repair fixed the stale node in the background...")
    print_stores()

if __name__ == "__main__":
    run_tests()
