import logging

import fitz

from config.settings import settings
from extraction.image_extractor import ImageExtractor

logger = logging.getLogger(__name__)


class DocumentAnalyzer:

    def __init__(self):
        self.image_extractor = ImageExtractor()


    def analyse(self, pdf_path):
        doc = fitz.open(pdf_path)
        pages = []
        for i in range(doc.page_count):
            try:
                page = doc[i]
                text = page.get_text()
                raw_images = page.get_images(full=True)
                images = []

                if raw_images:
                    images = self.image_extractor.extract(page, doc)

                page_type = self._detect_type(text, images)
                pages.append({
                    "page": i + 1,
                    "type": page_type,
                    "text": text,
                    "nb_images": len(images),
                    "images": images
                })
            except Exception as e:
                # Une page corrompue ne doit pas interrompre tout le document :
                # on la marque comme "vide" et on continue sur les suivantes.
                logger.warning(
                    "Echec de l'analyse de la page %d de %s : %s",
                    i + 1, pdf_path, e
                )
                pages.append({
                    "page": i + 1,
                    "type": "vide",
                    "text": "",
                    "nb_images": 0,
                    "images": []
                })
        doc.close()
        return pages

    def _detect_type(self, text, images):
        if len(text.strip()) >= settings.min_text_chars:
            return "texte"
        elif images:
            return "scan"
        else:
            return "vide"
