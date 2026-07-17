import time
import subprocess
import sys
import rpyc

PORTS = [18000, 18001, 18002, 18003, 18004]
processes = []

def start_nodes():
    print("Démarrage des 5 nœuds...")
    for port in PORTS:
        p = subprocess.Popen([sys.executable, "2_gossip_n.py", str(port)])
        processes.append(p)
    time.sleep(2) # Attendre que les serveurs RPyC soient prêts

def stop_nodes():
    print("Arrêt des nœuds...")
    for p in processes:
        p.terminate()

def run_experiment():
    start_nodes()
    
    try:
        source_port = PORTS[0]
        test_key = "cle_secrete"
        test_value = "valeur_123"
        test_ts = time.time()
        
        print(f"\n[1] Écriture de la clé '{test_key}' sur le nœud {source_port}")
        conn = rpyc.connect("localhost", source_port)
        conn.root.put(test_key, test_value, test_ts)
        conn.close()
        
        print(f"[2] Mesure de la convergence de propagation (Gossip)...")
        start_time = time.time()
        
        # On vérifie chaque nœud toutes les 0.5 secondes jusqu'à ce qu'ils aient tous la clé
        while True:
            nodes_with_key = 0
            for port in PORTS:
                try:
                    c = rpyc.connect("localhost", port)
                    has_key = c.root.has_key(test_key)
                    c.close()
                    if has_key:
                        nodes_with_key += 1
                except:
                    pass
                    
            print(f"  -> Nœuds ayant la clé : {nodes_with_key}/{len(PORTS)}")
            
            if nodes_with_key == len(PORTS):
                elapsed = time.time() - start_time
                print(f"\n[SUCCESS] Convergence atteinte en {elapsed:.2f} secondes ! (Tous les nœuds ont la clé)")
                break
                
            time.sleep(0.5)
            
    finally:
        stop_nodes()

if __name__ == "__main__":
    run_experiment()
