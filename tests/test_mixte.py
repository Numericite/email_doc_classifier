import sys

from extraction.data_preparation import DataPreparation

# PDF mixte : pages texte (fitz) + page scannee (ocr)
pdf = sys.argv[1] if len(sys.argv) > 1 else "data/inbox_temp/08012024_accord_confidentialité (1).pdf"

prep = DataPreparation()
segments = prep.prepare_segments(pdf)

for s in segments:
    tag = "FITZ" if s["source"] == "fitz" else "OCR"
    print(f"\n===== page {s['page']} — source={tag} ({s['type']}) — {len(s['text'])} car =====")
    print(s["text"])
