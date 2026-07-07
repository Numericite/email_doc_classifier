import ollama
from config.settings import settings


class QwenAnalyzer:

    def analyse(self, image_bytes):
        response = ollama.chat(
            model=settings.vision_model,
            messages=[{
                "role": "user",
               "content": "Retranscris uniquement le texte présent "
               "dans l'image. Réponds en français. "
               "Si c'est un logo ou une signature, réponds juste 'logo' ou 'signature'."
               " N'ajoute aucune explication.",
                "images": [image_bytes],
            }],
        )
        return response["message"]["content"]