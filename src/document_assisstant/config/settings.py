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
    base_remote_path = "2 - Projets"   # dossier racine de classement
    
    # Chemins
    inbox_temp = Path("data/inbox_temp")
    logs_dir = Path("logs")

    # Base de données de l'application (données de l'app : mails, documents, statuts).
    # SQLite en local aujourd'hui.
    #  pour passer à PostgreSQL plus tard, il suffit de définir DATABASE_URL (ex: postgresql+psycopg://user:pwd@host/db) — aucun autre

    database_url = os.getenv("DATABASE_URL")

    # Modèles Ollama
    #vision_model = "qwen2.5vl:3b" #pour analyse des images
    #vision_model = "moondream" #analyse image leger mais trop faible 
    vision_model = "granite3.2-vision:2b" #
    classification_model = "llama3.2:3b" #analyse texte ( faible au nombresue données)
    #extraction_model = "qwen3:4b" #plus rapide mais moins fiable sur les cas nuances
    extraction_model = "qwen2.5:7b" #extraction structuree (type, client, projet)
    

    #Claude API
    claude_api_key = os.getenv("CLAUDE_API_KEY")
    claude_model = "claude-haiku-4-5"

    #notion
    notion_token = os.getenv("NOTION_TOKEN")
    notion_database_id = os.getenv("NOTION_DATABASE_ID")

    
    #Analyse des document
    min_text_chars = 50


settings = Settings()