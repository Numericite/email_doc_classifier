import sys
sys.stdout.reconfigure(encoding='utf-8')

import xml.etree.ElementTree as ET
from datetime import datetime, timezone, timedelta
from email.utils import parsedate_to_datetime
from urllib.parse import quote, unquote

import requests

from config.settings import settings

# Espace de noms WebDAV (toutes les balises sont préfixées par {DAV:} dans la réponse).
DAV = "{DAV:}"

# Corps PROPFIND : on ne demande que le type (dossier/fichier) et la date de modif.
_PROPFIND_BODY = (
    '<?xml version="1.0"?>'
    '<d:propfind xmlns:d="DAV:"><d:prop>'
    '<d:resourcetype/><d:getlastmodified/>'
    '</d:prop></d:propfind>'
)


def lister_dossiers(chemin, max_age_jours=365):
    """Dossiers de PREMIER NIVEAU dans `chemin` sur Nextcloud (pas de récursion),
    en ne gardant que ceux modifiés il y a moins d'un an.

    `Depth: 1` = uniquement les enfants directs du dossier, on ne descend pas dedans.
    Renvoie une liste de dicts : {nom, chemin, date_modification (ISO)}.
    """
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

        chemin_dossier = unquote(rep.find(f"{DAV}href").text).strip("/")
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
