from extraction.analyse_document import DocumentAnalyzer

analyzer = DocumentAnalyzer()
pages = analyzer.analyse("data/inbox_temp/Avenant-NUMERICITE-signé.pdf")

for p in pages:
    print(f"Page {p['page']} | {p['type']} | {p['nb_images']} image(s) | {len(p['text'])} caractères")