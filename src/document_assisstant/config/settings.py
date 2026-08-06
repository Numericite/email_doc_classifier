import os
import sys
import configparser
from pathlib import Path

from dotenv import load_dotenv


# Dossier de base : à côté de l'exe (appli compilée) ou racine du projet (dev).
def _base_dir():
    if getattr(sys, "frozen", False):               # lancé depuis un .exe PyInstaller
        return Path(sys.executable).parent
    return Path(__file__).resolve().parents[3]      # .../config/settings.py -> racine projet


BASE_DIR = _base_dir()

# .env (dev / serveur) : source par défaut des paramètres.
load_dotenv(BASE_DIR / ".env")

# config.ini (poste utilisateur) : posé à côté de l'exe, éditable sans recompiler.
_ini = configparser.ConfigParser()
_ini.read(BASE_DIR / "config.ini", encoding="utf-8")


# Valeur = config.ini si renseignée, sinon variable d'environnement, sinon défaut.
def _val(section, key, env, defaut=None):
    if _ini.has_option(section, key) and _ini.get(section, key).strip():
        return _ini.get(section, key).strip()
    return os.getenv(env, defaut)


class Settings:
    # --- Poste utilisateur : config.ini (prioritaire) puis variables d'environnement ---

    # Base de l'application (PostgreSQL, sur le serveur).
    database_url = _val("database", "url", "DATABASE_URL")

    # Nextcloud WebDAV (dépôt + listing des dossiers).
    nextcloud_url = _val("nextcloud", "url", "NEXTCLOUD_URL",
                         "https://nextcloud.numericite.fr/remote.php/webdav")
    nextcloud_user = _val("nextcloud", "user", "NEXTCLOUD_USER")
    nextcloud_password = _val("nextcloud", "password", "NEXTCLOUD_PASSWORD")
    base_remote_path = _val("nextcloud", "base_remote_path", "BASE_REMOTE_PATH", "2 - Projets")

    # Ricobot (missions + bons de commande).
    ricobot_url = _val("ricobot", "url", "RICOBOT_URL")
    ricobot_token = _val("ricobot", "token", "RICOBOT_API")
    ricobot_bo_url = _val("ricobot", "bo_url", "RICOBOT_BO_URL",
                          "https://preprod.ricobot.numericite.eu")

    # --- Serveur / pipeline : via .env uniquement (non utilisé par l'UI compilée) ---

    # Email (Exchange).
    email_address = os.getenv("EMAIL_ADRESS")
    email_password = os.getenv("EMAIL_PASSWORD")
    exchange_server = os.getenv("EXCHANGE_SERVER")
    exchange_email = os.getenv("EMAIL_ADRESS")

    # Chemins de travail du pipeline.
    inbox_temp = BASE_DIR / "data" / "inbox_temp"
    logs_dir = BASE_DIR / "logs"

    # LLM Claude.
    claude_api_key = os.getenv("CLAUDE_API_KEY")
    claude_model = "claude-haiku-4-5"

    # Notion (legacy).
    notion_token = os.getenv("NOTION_TOKEN")
    notion_database_id = os.getenv("NOTION_DATABASE_ID")

    # Modèles Ollama (legacy vision).
    vision_model = "granite3.2-vision:2b"
    classification_model = "llama3.2:3b"
    extraction_model = "qwen2.5:7b"

    # Analyse des documents.
    min_text_chars = 50


settings = Settings()
