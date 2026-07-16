import sys
sys.stdout.reconfigure(encoding='utf-8')

from extraction.data_preparation import DataPreparation
from nextcloud.lister_dossiers import lister_dossiers
from classification.preparation_prompt_dossier import (
    formater_dossiers_pour_prompt,
    construire_prompt_dossier,
)
from classification.classifier_v2 import ClassifierV2

# --- À ajuster ---
DOCUMENT = sys.argv[1] if len(sys.argv) > 1 else "data/inbox_temp/D2026023 - Devis Numéricité - IF Vietnam signé.pdf"
CHEMIN_NEXTCLOUD = "2 - Projets"
OBJET_MAIL = "UGAP - Commande 25028 / 250410-6485A-004-onf-plf collaborative forestière"   # laisse vide pour un test sur un seul document


# --- Étape 1 : extraction du texte (Docling) ---
print(f"\n[1] Extraction : {DOCUMENT}")
texte = DataPreparation().prepare(DOCUMENT)
print(f"    {len(texte)} caractères extraits.")
print(f"    Aperçu : {texte[:300]!r}\n")

# --- Étape 2 : listing des dossiers Nextcloud (premier niveau, < 1 an) ---
print(f"[2] Dossiers Nextcloud : {CHEMIN_NEXTCLOUD}")
dossiers = lister_dossiers(CHEMIN_NEXTCLOUD)
for i, d in enumerate(dossiers):
    print(f"    [{i}] {d['nom']}")
print()

# --- Étape 3 : construction du prompt (AUCUN appel LLM) ---
print("[3] Prompt qui SERAIT envoyé au LLM (pas d'appel) :")
print("=" * 70)
texte_dossiers = formater_dossiers_pour_prompt(dossiers)
prompt = construire_prompt_dossier(OBJET_MAIL, texte, texte_dossiers)
print(prompt)
print("=" * 70)
print(f"\nTaille du prompt : {len(prompt)} caractères.")

# --- Étape 4 : appel LLM (Anthropic) → dossier(s) de destination ---
print("\n[4] Appel LLM (Anthropic) :")
resultat = ClassifierV2().classer_dossier(OBJET_MAIL, texte, dossiers)
proposes = resultat["dossiers"]

if not proposes:
    print("    → Aucun dossier pertinent (proposer d'en créer un).")
elif len(proposes) == 1:
    d = proposes[0]
    print(f"    → Dossier proposé : {d['nom']}")
    print(f"      Chemin : {d['chemin']}")
else:
    print(f"    → Ambiguïté : {len(proposes)} dossiers conviennent, à faire choisir :")
    for i, d in zip(resultat["dossier_ids"], proposes):
        print(f"        [{i}] {d['nom']}  ({d['chemin']})")
print(f"    Score de confiance : {resultat['score_confiance']}")
