import sys
sys.stdout.reconfigure(encoding='utf-8')

import xml.etree.ElementTree as ET
from datetime import datetime, timezone, timedelta
from email.utils import parsedate_to_datetime
from urllib.parse import quote, unquote, urlparse

import requests

from config.settings import settings

# Espace de noms WebDAV (toutes les balises sont préfixées par {DAV:} dans la réponse).
DAV = "{DAV:}"

# Préfixe WebDAV du serveur (ex. "remote.php/webdav"). Les href renvoyés par
# PROPFIND sont absolus depuis la racine du serveur et le contiennent : on le
# retire pour obtenir un chemin relatif à la racine WebDAV, réutilisable tel quel
# par nextcloud/depot.py (qui rajoute la base de son côté).
_BASE_PATH = urlparse(settings.nextcloud_url).path.strip("/")

# Corps PROPFIND : on ne demande que le type (dossier/fichier) et la date de modif.
_PROPFIND_BODY = (
    '<?xml version="1.0"?>'
    '<d:propfind xmlns:d="DAV:"><d:prop>'
    '<d:resourcetype/><d:getlastmodified/>'
    '</d:prop></d:propfind>'
)


def lister_dossiers(chemin, max_age_jours=365):
    
    base = settings.nextcloud_url.rstrip("/")
    url = f"{base}/{quote(chemin.strip('/'))}"

    response = requests.request(
        "PROPFIND", url,
        headers={"Depth": "1"},          # 1 = premier niveau seulement (non récursif)
        data=_PROPFIND_BODY,
        auth=(settings.nextcloud_user, settings.nextcloud_password),
    )
    response.raise_for_status()

    limite = datetime.now(timezone.utc) - timedelta(days=max_age_jours)
    cible = chemin.strip("/")

    dossiers = []
    racine = ET.fromstring(response.content)
    for rep in racine.findall(f"{DAV}response"):
        prop = rep.find(f"{DAV}propstat/{DAV}prop")

        # On ne garde que les collections (dossiers), pas les fichiers.
        rtype = prop.find(f"{DAV}resourcetype")
        if rtype is None or rtype.find(f"{DAV}collection") is None:
            continue

        # href = chemin absolu depuis la racine du serveur : on retire le préfixe
        # WebDAV pour obtenir un chemin relatif (ex. "2 - Projets/EGOV - ...").
        chemin_dossier = unquote(rep.find(f"{DAV}href").text).strip("/")
        if _BASE_PATH and chemin_dossier.startswith(_BASE_PATH):
            chemin_dossier = chemin_dossier[len(_BASE_PATH):].strip("/")

        # Le dossier interrogé lui-même figure dans la réponse : on le saute.
        if chemin_dossier.endswith(cible) and not chemin_dossier[:-len(cible)].strip("/"):
            continue

        lm = prop.find(f"{DAV}getlastmodified")
        date_mod = parsedate_to_datetime(lm.text) if lm is not None and lm.text else None
        if date_mod and date_mod < limite:
            continue  # trop vieux (> 1 an)

        dossiers.append({
            "nom": chemin_dossier.split("/")[-1],
            "chemin": chemin_dossier,
            "date_modification": date_mod.isoformat() if date_mod else None,
        })

    return dossiers


if __name__ == "__main__":
    chemin = sys.argv[1] if len(sys.argv) > 1 else settings.base_remote_path
    resultat = lister_dossiers(chemin)
    print(f"{len(resultat)} dossier(s) de premier niveau < 1 an dans « {chemin} » :\n")
    for d in resultat:
        print(f"  • {d['nom']:40}")
