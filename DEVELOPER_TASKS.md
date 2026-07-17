# P2P Distributed Key-Value Store - Detailed Developer Tasks

**Team Members:** Sanaa Zouine, Mehdi Cheddad, Anis Hammoudi

This document provides a highly detailed breakdown of the 3 main components of the Mini-Cassandra project. By adhering exactly to these interfaces and data structures, the final integration will be seamless.

---

## Task 1: Networking & Gossip Protocol (The Communication Layer)
**Owner:** Sanaa Zouine

### Goal
Build the symmetric node architecture using RPyC. Each node must run an RPC server in the main thread and a gossip client in a background daemon thread.

### Data Structures to Handle
- **Node ID:** Integer or String (e.g., `18000`, `18001`) representing the node's port or identifier.
- **State Dictionaries:** Managed by Task 2, but held and passed around by Task 1.
  - `local_store`: `{ key: (value, timestamp) }`
  - `local_heartbeats`: `{ node_id: (counter, last_updated_timestamp) }`

### Detailed Responsibilities
1. **The RPyC Server (Main Thread):**
   - Create a class `NodeService(rpyc.Service)` exposing endpoints for peers and clients:
     - `exposed_gossip(remote_store, remote_heartbeats)`: Receives state from another node. It must acquire a `threading.Lock()` and then call Task 2's `merge_stores` and `merge_heartbeats` to update local state.
     - `exposed_put(key, value, timestamp)`: Called by the Coordinator (Task 3). Acquires the lock, and updates `local_store` using Task 2's LWW logic.
     - `exposed_get(key)`: Returns `local_store.get(key)`.
2. **The Gossip Worker (Daemon Thread):**
   - Run a continuous `while True` loop that sleeps for `T` seconds (e.g., `T = 2.0`).
   - Call Task 2's logic to increment this node's own heartbeat counter.
   - Pick a random known peer (excluding self) from the `local_heartbeats` dictionary.
   - Connect to the peer using `rpyc.connect("localhost", peer_port)`.
   - Send the local state using `conn.root.gossip(local_store, local_heartbeats)` (Push anti-entropy).
   - *Crucial:* Wrap the connection attempt in a `try...except` block (catching `ConnectionRefusedError` and `socket.timeout`) so the thread doesn't crash if a peer is temporarily dead.
3. **Concurrency Control:**
   - Instantiate a `threading.Lock()` that must be acquired whenever `local_store` or `local_heartbeats` are read or modified to prevent race conditions between the Gossip worker and incoming RPC requests.

---

## Task 2: State Management, LWW & Failure Detection (The Core Logic)
**Owner:** Mehdi Cheddad

### Goal
Implement the pure logic for merging states (Last-Write-Wins) and managing the health of the cluster via heartbeats. These must be pure functions with strictly no network logic to guarantee easy unit testing.

### Detailed Responsibilities & Interfaces

1. **LWW Data Store Merge:**
```python
def merge_stores(local_store: dict, remote_store: dict) -> None:
    """
    Data format: { 'key': ('value', float_timestamp) }
    Updates local_store IN-PLACE.
    Rule: Iterate over every key in remote_store. 
    If it's not in local_store, add it.
    If it is, keep the value with the strictly higher float_timestamp.
    """
    pass
```

2. **Heartbeat Merge:**
```python
import time

def merge_heartbeats(local_heartbeats: dict, remote_heartbeats: dict) -> None:
    """
    Data format: { node_id: (int_counter, float_local_timestamp) }
    Updates local_heartbeats IN-PLACE.
    Rule: For every node_id in remote, compare int_counter. 
    If remote counter > local counter:
        Update local counter AND set float_local_timestamp to time.time()
    If node_id not in local, add it with the remote counter and time.time() as the timestamp.
    """
    pass
```

3. **Failure Detection (The Reaper):**
```python
def get_live_nodes(heartbeats: dict, t_mort: float = 10.0) -> list:
    """
    Returns a list of node_ids that are considered alive.
    Rule: A node is alive if (time.time() - float_local_timestamp) < t_mort.
    """
    pass
```

4. **Self Heartbeat:**
```python
def increment_own_heartbeat(heartbeats: dict, my_node_id) -> None:
    """
    Increments the int_counter for my_node_id and updates its float_local_timestamp to time.time().
    """
    pass
```

---

## Task 3: Placement, Routing & Chaos (The Topology Layer)
**Owner:** Anis Hammoudi

### Goal
Implement the Coordinator logic for routing client requests using the Consistent Hashing Ring, ensuring replication, and handling Read-Repairs.

### Detailed Responsibilities
1. **Consistent Hashing Integration:**
   - Import the `Anneau` class from the previous workshop (Workshop 1).
   - Before any read or write, call Task 2's `get_live_nodes(local_heartbeats)` to know who is alive.
   - Instantiate a fresh `Anneau(live_nodes)` to determine where data should go dynamically.

2. **Coordinator API (Client Facing):**
   - Implement `handle_client_put(key, value, R=3)`:
     - Hash `key` on the `Anneau` to get the `R` replica node IDs.
     - Generate a single `timestamp = time.time()`.
     - Loop through the `R` nodes. Use `rpyc.connect` to call `exposed_put(key, value, timestamp)` on each of those replica nodes. Handle connection errors if one replica fails during write.
   - Implement `handle_client_get(key, R=3)`:
     - Hash `key` to find the `R` replica nodes.
     - Call `exposed_get(key)` on all `R` nodes. Collect all responses: `[(value1, ts1), (value2, ts2), ...]`. Ignore dead nodes.
     - Find the pair with the highest `ts`. This is the freshest data.
     - **Read-Repair:** Compare all responses. For any replica node that returned an older `ts` or didn't have the key (`None`), asynchronously (or before returning) send the freshest `(value, ts)` back to them using `exposed_put`.
     - Return the freshest `value` to the client.

3. **Chaos Script (`6_chaos.py`):**
   - Write a standalone script that uses `subprocess.Popen` to spawn `N` node processes (e.g., ports 18000 to 18004).
   - Start a "chaos monkey" loop that randomly kills (`process.terminate()`) a node and restarts it a few seconds later.
   - Concurrently, have a client loop continuously sending `put` and `get` operations to any random alive node.
   - Verify that data is consistently available and converges despite the chaos, proving the AP (Availability & Partition Tolerance) characteristics of the system.

---

## The Integration Contract
To ensure everything works perfectly when combined:
1. **Sanaa (Task 1)** will define the global `STORE_LOCK = threading.Lock()` and ensure it wraps all state modifications. This prevents Task 1's Gossip from corrupting data while Task 3 is writing.
2. **Mehdi (Task 2)** will ensure his functions NEVER block, wait for network IO, or use locks internally. They must execute instantly in memory as pure Python dict manipulations.
3. **Anis (Task 3)** will not manipulate `local_store` directly when acting as a coordinator; he will route requests via RPyC (Task 1's network layer) to the correct nodes, even if the target is the local node itself. This maintains the symmetric node rule perfectly.

By strictly respecting these data schemas (especially the tuple structures: `(value, timestamp)` and `(counter, last_updated)`), the code will plug together without type mismatch errors.
