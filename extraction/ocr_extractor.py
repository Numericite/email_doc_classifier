from rapidocr_onnxruntime import RapidOCR


class OCRExtractor:
    def __init__(self):
        self.engine = RapidOCR()

    def extract(self, image_bytes):
        result, _ = self.engine(image_bytes)
        if not result:
            return ""
        lignes = [ligne[1] for ligne in result]
        return "\n".join(lignes)