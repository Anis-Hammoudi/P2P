import hashlib
import bisect
from collections import Counter
import math

def h(cle):
    return int(hashlib.md5(cle.encode('utf-8')).hexdigest(), 16) % (2**32)

class AnneauVNodes:
    def __init__(self, vnodes_par_noeud=150):
        self.vnodes_par_noeud = vnodes_par_noeud
        self.positions = []
        self.vnode_vers_noeud = {} # vnode_hash -> noeud_reel
        
    def ajouter_noeud(self, nom_noeud):
        for i in range(self.vnodes_par_noeud):
            vnode_name = f"{nom_noeud}#{i}"
            pos = h(vnode_name)
            bisect.insort(self.positions, pos)
            self.vnode_vers_noeud[pos] = nom_noeud
            
    def noeud_pour(self, cle):
        if not self.positions:
            return None
        pos_cle = h(cle)
        idx = bisect.bisect(self.positions, pos_cle)
        idx = idx % len(self.positions)
        vnode_hash = self.positions[idx]
        return self.vnode_vers_noeud[vnode_hash]

def demo():
    K = 5000000 # Plus de cles pour une meilleure distribution statistique
    V = 150
    print(f"--- Etape 4 : Noeuds Virtuels (V={V}) ---")
    
    anneau = AnneauVNodes(vnodes_par_noeud=V)
    noeuds_reels = ["Noeud_A", "Noeud_B", "Noeud_C", "Noeud_D", "Noeud_E","Noeud_F","Noeud_G","Noeud_H","Noeud_I","Noeud_J","Noeud_K","Noeud_L","Noeud_M", "Noeud_N","Noeud_O","Noeud_P"," Noeud_Q","Noeud_R","Noeud_S", "Noeud_T"]  
    for nom in noeuds_reels:
        anneau.ajouter_noeud(nom)
        
    print(f"Distribution de {K} cles sur {len(noeuds_reels)} noeuds physiques ({V} vnodes chacun)...")
    repartition = Counter()
    for i in range(K):
        cle = f"cle_{i}"
        repartition[anneau.noeud_pour(cle)] += 1
        
    moyenne = K / len(noeuds_reels)
    variance = sum((nb - moyenne)**2 for nb in repartition.values()) / len(noeuds_reels)
    ecart_type = math.sqrt(variance)
    
    for noeud in sorted(noeuds_reels):
        nb_cles = repartition[noeud]
        print(f"{noeud} : {nb_cles} cles ({nb_cles/K*100:.1f}%)")
        
    print(f"\nEcart-type de la charge : {ecart_type:.1f} (plus c'est bas, mieux c'est)")
    print("Conclusion : La charge est bien lissee grace aux noeuds virtuels !")

if __name__ == "__main__":
    demo()
