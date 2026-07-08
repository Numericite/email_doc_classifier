import sys
sys.stdout.reconfigure(encoding='utf-8')

import json
import requests

from config.settings import settings


# Concatène les bouts de texte d'un champ 'rich_text' Notion en une chaîne.
def get_contacts(rich_text):
    return " ".join(item["plain_text"] for item in rich_text).strip()


# Récupère les projets 'In Progress' depuis Notion et renvoie une liste plate.
# Chaque projet est un dict : projet_name, description, client, Contact_Client, nextcloud.
def get_projets_actifs():
    url = f"https://api.notion.com/v1/data_sources/{settings.notion_database_id}/query"
    headers = {
        "Authorization": f"Bearer {settings.notion_token}",
        "Notion-Version": "2025-09-03",
        "Content-Type": "application/json",
    }
    payload = {
        "filter": {"property": "Status", "select": {"equals": "In Progress"}}
    }

    response = requests.post(url, headers=headers, json=payload)
    data = response.json()
    if "results" not in data:
        raise RuntimeError(f"Erreur Notion {response.status_code} : {data}")

    projets = []
    for item in data["results"]:
        props = item["properties"]

        # On saute les fiches sans nom de projet (titre vide)
        titre = props["Noms des projets"]["title"]
        if not titre:
            continue

        description = props["Description"]["rich_text"]
        client = props["Client"]["select"]

        projets.append({
            "projet_name": titre[0]["plain_text"],
            "description": description[0]["plain_text"] if description else "",
            "client": client["name"] if client else "",
            "Contact_Client": get_contacts(props["Contact client"]["rich_text"]),
            "nextcloud": props["NextCloud"]["url"] or "",
        })

    return projets


if __name__ == "__main__":
    projets = get_projets_actifs()
    print(f"{len(projets)} projets actifs récupérés.")

    # Cache local, pratique pour inspecter sans rappeler l'API Notion.
    with open("data/Projets_notion.json", "w", encoding="utf-8") as f:
        json.dump(projets, f, indent=2, ensure_ascii=False)
    print("Fichier data/Projets_notion.json créé.")
