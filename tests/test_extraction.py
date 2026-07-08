import sys

from extraction.data_preparation import DataPreparation

# Change le chemin ici (ou passe-le en argument).
fichier = sys.argv[1] if len(sys.argv) > 1 else "data/inbox_temp/BDC DITN.pdf"

prep = DataPreparation()
contenu = prep.prepare(fichier)

print(f"--- {fichier} : {len(contenu)} caractères ---\n")
print(contenu)
