import sys
sys.stdout.reconfigure(encoding='utf-8')

import re
import json
import unicodedata
from datetime import date

import requests

from config.settings import settings


def _est_numericite(nom):
    sans_accent = unicodedata.normalize("NFKD", nom or "").encode("ascii", "ignore").decode()
    return "numeri" in re.sub(r"[^a-z0-9]", "", sans_accent.lower())


def lister_projets():
    url = f"{settings.ricobot_url.rstrip('/')}/missions"
    headers = {"Authorization": f"Bearer {settings.ricobot_token}"}

    aujourd_hui = date.today().isoformat()
    projets = []
    ecarte = {"sans_marche": 0, "sans_date": 0, "terminee": 0, "numericite": 0}
    total_lu = 0
    page = 1

    while True:
        params = {
            "pagination[page]": page,
            "pagination[pageSize]": 100,
            "populate[procurement][populate]": "*",
            "publicationState": "preview",
        }
        response = requests.get(url, headers=headers, params=params)
        response.raise_for_status()
        payload = response.json()

        for item in payload["data"]:
            mission = item["attributes"]
            total_lu += 1

            proc = mission.get("procurement", {}).get("data")
            if not proc:
                ecarte["sans_marche"] += 1
                continue
            proc = proc["attributes"]

            fin = mission.get("end_date")
            if not fin:
                ecarte["sans_date"] += 1
                continue
            if fin < aujourd_hui:
                ecarte["terminee"] += 1
                continue

            societe = proc.get("company", {}).get("data")
            company = societe["attributes"].get("name") if societe else ""
            company = company or proc.get("company_name") or ""

            if _est_numericite(company):
                ecarte["numericite"] += 1
                continue

            projets.append({
                "id": item["id"],
                "nom": (mission.get("name") or "").strip(),
                "company": company.strip(),
            })

        pagination = payload["meta"]["pagination"]
        if page >= pagination["pageCount"]:
            break
        page += 1



    return projets


# Retire TOUS les emojis / symboles, quelle que soit leur plage, en se basant sur
# les catégories Unicode (générique, pas une liste de plages) :
#   So = symbole (emoji, pictogramme…)   Sk = modificateur (teintes de peau…)
#   Cf = format (zero-width joiner…)     FE00–FE0F = variation selectors
# Ça consomme beaucoup de tokens pour zéro info utile au matching.
def _sans_emoji(texte):
    garde = []
    for c in texte:
        if unicodedata.category(c) in ("So", "Sk", "Cf"):
            continue
        if 0xFE00 <= ord(c) <= 0xFE0F:       # variation selectors
            continue
        garde.append(c)
    texte = "".join(garde).lstrip(" -–—•")   # séparateur orphelin laissé en tête
    return re.sub(r"\s+", " ", texte).strip()


def formater_projets_pour_prompt(projets):
    # JSON pour le LLM : plus structuré et sans ambiguïté que du texte à plat.
    missions = [
        {"id": p["id"], "project": _sans_emoji(p["nom"]), "company": p["company"]}
        for p in projets
    ]
    return json.dumps(missions, ensure_ascii=False, indent=2)


if __name__ == "__main__":
    projets = lister_projets()
    print(formater_projets_pour_prompt(projets))