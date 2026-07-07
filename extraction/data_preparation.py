import logging

import fitz

from extraction.analyse_document import DocumentAnalyzer
from extraction.image_extractor import ImageExtractor
from extraction.ocr_extractor import OCRExtractor

logger = logging.getLogger(__name__)


class DataPreparation:
    def __init__(self):
        self.analyzer = DocumentAnalyzer()
        self.image_extractor = ImageExtractor()
        self.ocr_extractor = OCRExtractor()

    def prepare(self, pdf_path):
        """Texte complet du document, prêt pour le LLM (une seule chaîne)."""
        segments = self.prepare_segments(pdf_path)
        return "\n".join(s["text"] for s in segments)

    def prepare_segments(self, pdf_path):
        """Détail page par page, avec la source de chaque texte :
        - source="fitz" : texte natif extrait par PyMuPDF (page "texte")
        - source="ocr"  : texte reconstruit par RapidOCR (page "scan")
        Les pages "vide" sont ignorées.
        """
        pages = self.analyzer.analyse(pdf_path)
        doc = fitz.open(pdf_path)

        segments = []
        for p in pages:
            if p["type"] == "texte":
                segments.append({
                    "page": p["page"], "type": "texte",
                    "source": "fitz", "text": p["text"],
                })
            elif p["type"] == "scan":
                try:
                    page = doc[p["page"] - 1]
                    image = self.image_extractor.render_page(page)
                    texte_ocr = self.ocr_extractor.extract(image)
                    segments.append({
                        "page": p["page"], "type": "scan",
                        "source": "ocr", "text": texte_ocr,
                    })
                except Exception as e:
                    # Le rendu/OCR d'une page scan peut echouer (page ou image
                    # corrompue) : on logue et on continue sur les autres pages.
                    logger.warning(
                        "Echec du traitement de la page scan %d de %s : %s",
                        p["page"], pdf_path, e
                    )
            # "vide" -> on ignore

        doc.close()
        return segments
