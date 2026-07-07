import logging

import fitz

logger = logging.getLogger(__name__)


class ImageExtractor:

    def extract(self, page, doc):
        images = []
        for img in page.get_images(full=True):
            xref = img[0]
            try:
                base = doc.extract_image(xref)
                images.append(base["image"])
            except Exception as e:
                # Une image corrompue ne doit pas faire echouer l'extraction
                # des autres images de la page.
                logger.warning(
                    "Echec de l'extraction de l'image xref=%s : %s", xref, e
                )
        return images

    def extract_by_xref(self, doc, xref):
        base = doc.extract_image(xref)
        return base["image"]

    def render_page(self, page, zoom=2.0):
        mat = fitz.Matrix(zoom, zoom)
        pix = page.get_pixmap(matrix=mat)
        return pix.tobytes("png")
