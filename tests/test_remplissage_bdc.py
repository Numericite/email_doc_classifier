import sys
sys.stdout.reconfigure(encoding="utf-8")

import json

from ricobot.remplissage_bdc import remplir_bdc

# --- À ajuster pour le test ---
MISSION_ID = 76                 # id d'une mission Ricobot existante
ABBREVIATION = "TEST BDC libellé"
REFERENCE = "TEST-REF-001"
START_DATE = "2026-07-20"
END_DATE = "2026-09-30"
AMOUNT = 12345


print(f"Création d'un BDC sur la mission {MISSION_ID}…\n")
reponse = remplir_bdc(
    MISSION_ID,
    abbreviation=ABBREVIATION,
    reference=REFERENCE,
    start_date=START_DATE,
    end_date=END_DATE,
    amount=AMOUNT,
)

print(json.dumps(reponse, ensure_ascii=False, indent=2))

cree = (reponse or {}).get("data", {})
# La réponse de /orders est "plate" (les champs directement sous data,
# pas sous data.attributes).
print(f"\n→ créé avec l'id {cree.get('id')}")
print("  title       :", cree.get("title"))
print("  publishedAt :", cree.get("publishedAt"))
print("  mission     :", (cree.get("mission") or {}).get("id"))
