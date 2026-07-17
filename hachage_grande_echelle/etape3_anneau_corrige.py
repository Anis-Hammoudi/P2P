import hashlib
import bisect

def h(cle):
    # On borne le hash a 32 bits pour l'anneau [0, 2**32)
    return int(hashlib.md5(cle.encode('utf-8')).hexdigest(), 16) % (2**32)

class AnneauCoherent:
    def __init__(self):
        self.positions = [] # L'anneau trie
        self.noeuds = {}    # map position -> nom_du_noeud
        
    def ajouter_noeud(self, nom):
        pos = h(nom)
        bisect.insort(self.positions, pos)
        self.noeuds[pos] = nom
        
    def noeud_pour(self, cle):
        if not self.positions:
            return None
        pos_cle = h(cle)
        # Trouver le 1er noeud sur l'anneau >= h(cle)
        idx = bisect.bisect(self.positions, pos_cle)
        # Boucler au premier element si on depasse la fin
        idx = idx % len(self.positions)
        return self.noeuds[self.positions[idx]]

def demo():
    K = 10000
    anneau = AnneauCoherent()
    
    print("--- Etape 3 : L'Anneau Coherent ---")
    for nom in ["Noeud_A", "Noeud_B", "Noeud_C", "Noeud_D"]:
        anneau.ajouter_noeud(nom)
        
    placement_avant = {}
    for i in range(K):
        cle = f"cle_{i}"
        placement_avant[cle] = anneau.noeud_pour(cle)
        
    print("Ajout du Noeud_E...")
    anneau.ajouter_noeud("Noeud_E")
    
    cles_deplacees = 0
    for i in range(K):
        cle = f"cle_{i}"
        noeud_apres = anneau.noeud_pour(cle)
        if placement_avant[cle] != noeud_apres:
            cles_deplacees += 1
            
    taux = (cles_deplacees / K) * 100
    print(f"Cles deplacees apres ajout : {cles_deplacees} / {K}")
    print(f"Taux de rebalancement : {taux:.1f}%")
    print(f"Conclusion : Seules les cles proches de E ont bouge (attendu ~{1/5*100:.1f}%) !")

if __name__ == "__main__":
    demo()
