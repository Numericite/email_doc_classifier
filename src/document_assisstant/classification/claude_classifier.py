"""Analyse en lot des documents : extraction (fitz + OCR) puis analyse LLM.

Usage :
    python -m classification.classifier_qwen                      # tout le dossier inbox
    python -m classification.classifier_qwen "chemin/doc.pdf"     # un fichier
    python -m classification.classifier_qwen dossier1 doc2.pdf    # plusieurs chemins
"""
import json
import sys
from pathlib import Path

from config.settings import settings
from extraction.data_preparation import DataPreparation
from classification.classifier import Classifier

# Formats gérés par l'extraction (fitz ne lit que le PDF pour l'instant).
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


def analyser_documents(chemins):
    prep = DataPreparation()
    classifier = Classifier()

    fichiers = lister_documents(chemins)
    if not fichiers:
        print("Aucun document à analyser.")
        return

    for f in fichiers:
        print(f"\n{'='*70}\n{f.name}")
        if f.suffix.lower() not in EXTENSIONS:
            print(f"  [!] Format non géré ({f.suffix}) — ignoré.")
            continue
        try:
            texte = prep.prepare(str(f))
            print(f"  ({len(texte)} caractères extraits)")
            infos = classifier.analyser(texte)
            print(json.dumps(infos, indent=2, ensure_ascii=False))
        except Exception as e:
            print(f"  [ERREUR] {type(e).__name__}: {e}")


if __name__ == "__main__":
    chemins = sys.argv[1:] or [str(settings.inbox_temp)]
    analyser_documents(chemins)
