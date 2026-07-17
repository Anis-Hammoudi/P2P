import hashlib

def h(cle):
    return int(hashlib.md5(cle.encode('utf-8')).hexdigest(), 16)

def noeud_pour(cle, N):
    return h(cle) % N

def demo():
    N_initial = 4
    N_nouveau = 5
    K = 10000
    
    print(f"--- Etape 2 : Le Rehash ---")
    print(f"Passage de {N_initial} a {N_nouveau} noeuds.")
    
    cles_deplacees = 0
    
    for i in range(K):
        cle = f"cle_{i}"
        noeud_avant = noeud_pour(cle, N_initial)
        noeud_apres = noeud_pour(cle, N_nouveau)
        
        if noeud_avant != noeud_apres:
            cles_deplacees += 1
            
    taux = (cles_deplacees / K) * 100
    print(f"Cles deplacees : {cles_deplacees} / {K}")
    print(f"Taux de rebalancement : {taux:.1f}%")
    print("Conclusion : inacceptable pour de grandes echelles (attendu ~80%) !")

if __name__ == "__main__":
    demo()
