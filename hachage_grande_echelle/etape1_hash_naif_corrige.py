import hashlib
from collections import Counter

def h(cle):
    """Hash cryptographique stable (MD5)"""
    return int(hashlib.md5(cle.encode('utf-8')).hexdigest(), 16)

def noeud_pour(cle, N):
    """Placement naif avec modulo"""
    return h(cle) % N

def demo():
    N = 4
    K = 10000
    print(f"--- Etape 1 : Hash Naif (h % N) ---")
    print(f"Placement de {K} cles sur {N} noeuds...")
    
    repartition = Counter()
    for i in range(K):
        cle = f"cle_{i}"
        noeud = noeud_pour(cle, N)
        repartition[noeud] += 1
        
    for noeud, nb_cles in sorted(repartition.items()):
        print(f"Noeud {noeud} : {nb_cles} cles ({nb_cles/K*100:.1f}%)")
        
if __name__ == "__main__":
    demo()
