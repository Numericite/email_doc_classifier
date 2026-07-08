import sys
sys.stdout.reconfigure(encoding='utf-8')

import requests
import json

from config.settings import settings

TOKEN = settings.notion_token
database_id = settings.notion_database_id

def get_contacts(list):
    result = ""
    if len(list) == 0 :
      return ""
    else:
      for item in list:
         result+= item["plain_text"] + " "
    return result
         
def get_squad(list):
    result = []
    i = 0
    if len(list) == 0    :
       return ""
    else:
      for item in list:
         person = item.get("person") or {}
         email = person.get("email")
         # L'email est le champ de jointure (filtre Squad) : sans lui, on saute
         if not email:
            continue
         result.append({
            f"name_effectif_{i}": item.get("name", ""),
            "email": email
         })
         i += 1
    return result if result else ""


def get_pole_en_charge(list):
    result = []
    i = 0
    if len(list) == 0    :
       return ""
    else:   
      for item in list:
         result.append({
            f"Pole_name_{i}": item["name"],
         })
         i += 1
    return result


url = f"https://api.notion.com/v1/data_sources/{database_id}/query"

headers = {
    "Authorization": f"Bearer {TOKEN}",
    "Notion-Version": "2025-09-03",
    "Content-Type": "application/json"
    
 }

# Ne récupère que les projets en cours (propriété Status = "In Progress")
payload = {
    "filter": {
        "property": "Status",
        "select": {"equals": "In Progress"},
    }
}
response = requests.post(url, headers=headers, json=payload)
data = response.json()

if "results" not in data:
    print("Erreur Notion:", response.status_code)
    print(json.dumps(data, indent=2, ensure_ascii=False))
    raise SystemExit(1)
results = {}
i=0
for item in data["results"]:
  # On saute les fiches Notion sans nom de projet (titre vide)
  titre = item["properties"]["Noms des projets"]["title"]
  if not titre:
    continue

  Contact_client = get_contacts(item["properties"]["Contact client"]["rich_text"])


  results[f"Projet_{i}"] = {
    "projet_name" : titre[0]["plain_text"],
    "description": item["properties"]["Description"]["rich_text"][0]["plain_text"] if item["properties"]["Description"]["rich_text"] else "",
    "client": item["properties"]["Client"]["select"]["name"] if item["properties"]["Client"]["select"] else "",
    "Contact_Client": Contact_client,
    "nextcloud": item["properties"]["NextCloud"]["url"] or "",
  }
  i += 1

  
ProjectFinalList = [results]
#Sauvergarde dans un fichier JSON
with open(
    "data/Projets_notion.json",
    "w",
    encoding="utf-8"
) as f:

    json.dump(
        ProjectFinalList,
        f,
        indent=2,
        ensure_ascii=False
    )

print("Fichier créé.")