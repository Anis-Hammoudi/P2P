import time
import random
import subprocess
import sys
import threading
import rpyc
from task3_topology import Coordinator

PORTS = [18000, 18001, 18002, 18003, 18004]
processes = {}

def get_live_nodes_from_cluster():
    """Ask any node what it thinks the cluster state is."""
    for port in PORTS:
        # Don't ask a node we manually killed via Chaos
        p = processes.get(port)
        if p is None or p.poll() is not None:
            continue
            
        try:
            conn = rpyc.connect("localhost", port, config={"sync_request_timeout": 1})
            live = list(conn.root.get_live_nodes())
            conn.close()
            return live
        except:
            continue
    return []

def start_node(port):
    print(f"[CHAOS] Démarrage du nœud sur le port {port}...")
    p = subprocess.Popen([sys.executable, "5_ring_replication.py", str(port)])
    processes[port] = p

def kill_node(port):
    p = processes.get(port)
    if p is not None and p.poll() is None:
        print(f"\n[CHAOS] BOOM! Tuer le nud {port} BOOM!\n")
        p.terminate()
        processes[port] = None

def chaos_monkey_loop():
    """Tues et redémarre les nœuds aléatoirement (AP Tolerance)."""
    while True:
        time.sleep(random.uniform(5, 10))
        target = random.choice(PORTS)
        
        p = processes.get(target)
        if p is not None and p.poll() is None:
            # 50% de chance de tuer
            if random.random() < 0.5:
                kill_node(target)
        else:
            # S'il est mort, on le relance
            start_node(target)

def client_traffic_loop():
    """Simule un client qui écrit et lit des données sans arrêt."""
    coordinator = Coordinator(get_live_nodes_func=get_live_nodes_from_cluster)
    counter = 0
    
    while True:
        time.sleep(1.5)
        key = f"user_{random.randint(1, 3)}"
        val = f"data_{counter}"
        counter += 1
        
        if random.random() < 0.5:
            print(f"[CLIENT] PUT {key} -> {val} (R=3)")
            coordinator.handle_client_put(key, val, R=3)
        else:
            print(f"[CLIENT] GET {key} (R=3)")
            res = coordinator.handle_client_get(key, R=3)
            print(f"[CLIENT]  -> Résultat: {res}")

def run_chaos():
    print("=== DÉMARRAGE DU CHAOS TEST (Mini-Cassandra) ===")
    for port in PORTS:
        start_node(port)
        
    print("Attente de 5s pour l'initialisation du gossip...")
    time.sleep(5)
    
    chaos_thread = threading.Thread(target=chaos_monkey_loop, daemon=True)
    chaos_thread.start()
    
    try:
        client_traffic_loop()
    except KeyboardInterrupt:
        print("\nArrêt du Chaos Test...")
        for p in processes.values():
            if p and p.poll() is None:
                p.terminate()

if __name__ == "__main__":
    run_chaos()
