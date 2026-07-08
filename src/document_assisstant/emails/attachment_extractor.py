from pathlib import Path
from config.settings import settings


class AttachmentExtractor:
    def __init__(self):
        self.temp_dir = settings.inbox_temp
        self.temp_dir.mkdir(parents=True, exist_ok=True)

    def extract(self, item):
        # parcourt les PJ, les sauvegarde, retourne les chemins
        saved_files = []
        for a in item.attachments:
            if a.is_inline:
                continue
            filepath = self.temp_dir / a.name
            with open(filepath, "wb") as f:
                f.write(a.content)
            saved_files.append(filepath)
        return saved_files