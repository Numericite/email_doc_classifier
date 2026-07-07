from extraction.analyse_document import DocumentAnalyzer
from vision.qwen_analyzer import QwenAnalyzer

analyzer = DocumentAnalyzer()
qwen = QwenAnalyzer()

pages = analyzer.analyse("data/inbox_temp/Devis signé_202507311220.pdf")

for p in pages:
    for img in p["images"]:
        result = qwen.analyse(img)
        print(f"Page {p['page']} :", result)