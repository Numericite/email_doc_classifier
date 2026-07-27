import requests

from config.settings import settings


# Crée  un bon de commande dans Ricobot pour une mission donnée.
# Les champs proviennent de l'extraction LLM, éventuellement corrigés par
# l'utilisateur dans l'UI.
def remplir_bdc(mission_id, abbreviation="", reference="", start_date="", end_date="",
                file=None):
    # Un title vide casse l'affichage de TOUS les BDC de la mission dans Ricobot.
    # On garantit donc un titre non vide : abréviation, sinon référence, sinon défaut.
    title = (abbreviation or "").strip() or (reference or "").strip() \
        or f"BDC mission {mission_id}"

    url = f"{settings.ricobot_url.rstrip('/')}/orders"
    headers = {
        "Authorization": f"Bearer {settings.ricobot_token}",
        "Content-Type": "application/json",
    }

    # start_date = date de réception du mail (pas extraite du document).
    payload = {
        "data": {
            "title": title,
            "ref": reference or None,
            "start_date": start_date or None,
            "end_date": end_date or None,
            "mission": mission_id,
            "amount": 0,  
        }
    }
    if file:
        payload["data"]["file"] = file

    response = requests.post(url, headers=headers, json=payload)
    if not response.ok:
        raise RuntimeError(f"Ricobot {response.status_code} : {response.text}")
    return response.json()
