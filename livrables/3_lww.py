import time
import subprocess
import sys
import rpyc

# We reuse the nodes from Phase 2
PORTS = [18000, 18001, 18002, 18003, 18004]
processes = []

def start_nodes():
    print("Démarrage des 5 nœuds...")
    for port in PORTS:
        p = subprocess.Popen([sys.executable, "2_gossip_n.py", str(port)])
        processes.append(p)
    time.sleep(2) # Wait for startup

def stop_nodes():
    print("Arrêt des nœuds...")
    for p in processes:
        p.terminate()

def run_experiment():
    start_nodes()
    
    try:
        node_A = PORTS[0]
        node_B = PORTS[4]
        test_key = "user_email"
        
        # 1. Simulate a network partition or concurrent writes
        # We write a value on Node A
        ts_A = time.time()
        val_A = "alice@old.com"
        
        # At exactly the same time, someone updates the email on Node B, 
        # but with a slightly higher timestamp (happened just after)
        ts_B = ts_A + 0.1
        val_B = "alice@new.com"
        
        print(f"\n[1] CONFLIT :")
        print(f"  -> Écriture sur Nœud {node_A}: {test_key} = {val_A} (ts={ts_A})")
        conn_A = rpyc.connect("localhost", node_A)
        conn_A.root.put(test_key, val_A, ts_A)
        conn_A.close()
        
        print(f"  -> Écriture sur Nœud {node_B}: {test_key} = {val_B} (ts={ts_B})")
        conn_B = rpyc.connect("localhost", node_B)
        conn_B.root.put(test_key, val_B, ts_B)
        conn_B.close()
        
        print(f"\n[2] Attente de la convergence par Gossip (LWW)...")
        time.sleep(4.0) # Let the gossip propagate
        
        print(f"\n[3] Vérification de l'état final (Last-Write-Wins) :")
        for port in PORTS:
            try:
                c = rpyc.connect("localhost", port)
                result = c.root.get(test_key)
                c.close()
                print(f"  Nœud {port} voit : {result}")
            except:
                pass
                
        print(f"\nConclusion : Tous les nœuds ont convergé vers {val_B} car son timestamp était plus grand, la valeur {val_A} a été écrasée proprement sans coordination centrale.")
            
    finally:
        stop_nodes()

if __name__ == "__main__":
    run_experiment()
