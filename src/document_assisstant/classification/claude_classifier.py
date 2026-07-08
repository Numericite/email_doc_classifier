"""Analyse en lot de documents : extraction (Docling) puis analyse LLM (Anthropic).

Usage :
    python -m classification.claude_classifier                    # tout le dossier inbox
    python -m classification.claude_classifier "chemin/doc.pdf"   # un fichier
    python -m classification.claude_classifier dossier1 doc2.pdf  # plusieurs chemins
"""
import json
import sys
from pathlib import Path

from config.settings import settings
from extraction.data_preparation import DataPreparation
from classification.classifier import Classifier
from notion.imports_projet import get_projets_actifs

# Formats gérés par l'extraction.
EXTENSIONS = {".pdf"}


def lister_documents(chemins):
    """Transforme une liste de chemins (fichiers ou dossiers) en liste de fichiers."""
    fichiers = []
    for c in chemins:
        p = Path(c)
        if p.is_dir():
            fichiers.extend(sorted(f for f in p.iterdir() if f.suffix.lower() in EXTENSIONS))
        elif p.is_file():
            fichiers.append(p)
        else:
            print(f"[!] Chemin introuvable : {p}")
    return fichiers


# Fichier où l'on sauvegarde les analyses, pour que l'UI les affiche
# sans refaire d'appel à l'API (ni à Docling).
RESULTATS_PATH = Path("data/resultats_analyse.json")


def analyser_documents(chemins):
    prep = DataPreparation()
    classifier = Classifier()

    # Le référentiel de projets est récupéré UNE fois pour tout le lot.
    projets = get_projets_actifs()
    print(f"{len(projets)} projets actifs récupérés depuis Notion.")

    fichiers = lister_documents(chemins)
    if not fichiers:
        print("Aucun document à analyser.")
        return

    resultats = []
    for f in fichiers:
        print(f"\n{'='*70}\n{f.name}")
        if f.suffix.lower() not in EXTENSIONS:
            print(f"  [!] Format non géré ({f.suffix}) — ignoré.")
            continue
        try:
            texte = prep.prepare(str(f))
            print(f"  ({len(texte)} caractères extraits)")
            # Pas d'objet de mail dans ce test en lot : on passe une chaîne vide.
            infos = classifier.classer("", texte, projets)
            print(json.dumps(infos, indent=2, ensure_ascii=False))

            # On garde tout ce dont l'UI a besoin (aperçu, infos, proposition,
            # état de validation) — sans avoir à ré-appeler l'API ni Docling.
            resultats.append({
                "document": f.name,
                "chemin": str(f),
                "texte_extrait": texte,
                "type_document": infos["type_document"],
                "projet_id": infos["projet_id"],
                "projet": infos["projet"],
                "score_confiance": infos["score_confiance"],
                "statut": "en_attente",  # en_attente | valide | refuse
            })
        except Exception as e:
            print(f"  [ERREUR] {type(e).__name__}: {e}")

    # Sauvegarde du lot pour l'affichage.
    RESULTATS_PATH.parent.mkdir(parents=True, exist_ok=True)
    with open(RESULTATS_PATH, "w", encoding="utf-8") as fichier:
        json.dump(resultats, fichier, indent=2, ensure_ascii=False)
    print(f"\n{len(resultats)} analyse(s) sauvegardée(s) dans {RESULTATS_PATH}")


if __name__ == "__main__":
    chemins = sys.argv[1:] or [str(settings.inbox_temp)]
    analyser_documents(chemins)
