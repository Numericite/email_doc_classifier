from docling.document_converter import DocumentConverter, PdfFormatOption
from docling.datamodel.base_models import InputFormat
from docling.datamodel.pipeline_options import PdfPipelineOptions, RapidOcrOptions


class DataPreparation:
    MAX_PAGES = 5      # plafond de pages traitées par Docling (borne la lenteur)
    MAX_CHARS = 20000   # plafond de caractères envoyés au LLM (borne le coût)

    def __init__(self):
        options = PdfPipelineOptions()
        options.do_ocr = True
        options.do_table_structure = True
        options.ocr_options = RapidOcrOptions(force_full_page_ocr=True)

        self.converter = DocumentConverter(
            format_options={
                InputFormat.PDF: PdfFormatOption(pipeline_options=options),
            }
        )

    def prepare(self, path):
        #Texte structuré du document (Markdown), plafonné pour le LLM.
        result = self.converter.convert(path, page_range=(1, self.MAX_PAGES))
        texte = result.document.export_to_markdown()
        return texte[:self.MAX_CHARS]
