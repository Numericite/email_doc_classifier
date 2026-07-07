import json
import sys

from extraction.data_preparation import DataPreparation
from classification.classifier import Classifier

# Pipeline complet : extraction (fitz + OCR) -> analyse LLM structuree
pdf = sys.argv[1] if len(sys.argv) > 1 else "data/inbox_temp/1406384820-PV octobre.pdf"

prep = DataPreparation()
texte = prep.prepare(pdf)
print(f"--- {pdf} : {len(texte)} caractères extraits ---")

classifier = Classifier()
infos = classifier.analyser(texte)
print(json.dumps(infos, indent=2, ensure_ascii=False))
