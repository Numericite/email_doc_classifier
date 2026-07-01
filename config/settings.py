import os
from dotenv import load_dotenv
from pathlib import Path



load_dotenv()
class Settings:
    # Email
    email_address = os.getenv("EMAIL_ADRESS")
    email_password =os.getenv("EMAIL_PASSWORD")
    exchange_server =os.getenv("EXCHANGE_SERVER")
    #Email d'exportation
    exchange_email = os.getenv("EMAIL_ADRESS")

    # Nextcloud WebDAV
    nextcloud_url = "https://nextcloud.numericite.fr/remote.php/webdav"
    nextcloud_user = os.getenv("NEXTCLOUD_USER")
    nextcloud_password = os.getenv("NEXTCLOUD_PASSWORD")   
    base_remote_path = "1 - Gestion administrative/tests"   # dossier racine de classement
    
    # Chemins
    inbox_temp = Path("data/inbox_temp")
    logs_dir = Path("logs")

    # Modèles Ollama
    vision_model = "qwen2.5vl:3b"
 


settings = Settings()