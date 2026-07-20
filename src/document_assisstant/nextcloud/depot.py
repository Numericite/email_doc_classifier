import re
from pathlib import Path
from urllib.parse import quote

import requests

from config.settings import settings


# Génère "vite fait" un nom de dossier quand aucun candidat ne convient.
# On part de l'objet du mail (sinon du nom de fichier), nettoyé et tronqué.
def generer_nom_dossier(objet_mail, nom_fichier=""):
    source = (objet_mail or Path(nom_fichier).stem or "Nouveau dossier").strip()
    nom = re.sub(r'[\\/:*?"<>|]', " ", source)   # caractères interdits
    nom = re.sub(r"\s+", " ", nom).strip()
    return nom[:60] or "Nouveau dossier"


def _url(chemin_relatif):
    base = settings.nextcloud_url.rstrip("/")
    return f"{base}/{quote(chemin_relatif.strip('/'))}"


def _auth():
    return (settings.nextcloud_user, settings.nextcloud_password)


# Dépose (upload) un fichier local dans un dossier Nextcloud existant.
# `dossier_cible` : chemin relatif du dossier (ex. "2 - Projets/UGAP-ONF").
# Renvoie le chemin distant complet du fichier déposé.
def deposer_document(chemin_local, dossier_cible):
    nom = Path(chemin_local).name
    chemin_distant = f"{dossier_cible.strip('/')}/{nom}"

    with open(chemin_local, "rb") as f:
        response = requests.put(_url(chemin_distant), data=f, auth=_auth())
    response.raise_for_status()
    return chemin_distant


# Crée un dossier dans Nextcloud (MKCOL), sous `chemin_parent`.
def creer_dossier(chemin_parent, nom):
    chemin = f"{chemin_parent.strip('/')}/{nom.strip('/')}"

    response = requests.request("MKCOL", _url(chemin), auth=_auth())
    if response.status_code not in (201, 405):
        response.raise_for_status()
    return chemin
