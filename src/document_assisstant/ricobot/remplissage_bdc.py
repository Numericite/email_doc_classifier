import requests

from config.settings import settings


# Crée / remplit un bon de commande dans Ricobot pour une mission donnée.
# Les champs proviennent de l'extraction LLM, éventuellement corrigés par
# l'utilisateur dans l'UI. `mission_id` : l'ID de la mission Ricobot retenue
# (proposée par le LLM ou choisie manuellement).
# TODO : confirmer l'endpoint exact avec la doc (ici : POST /orders).
def remplir_bdc(mission_id, abbreviation="", reference="", start_date="", end_date="",
                amount=0, file=None):
    url = f"{settings.ricobot_url.rstrip('/')}/orders"
    headers = {
        "Authorization": f"Bearer {settings.ricobot_token}",
        "Content-Type": "application/json",
    }

    # Strapi refuse "" pour un champ date : on envoie None (null) si vide.
    # start_date = date de réception du mail (pas extraite du document).
    payload = {
        "data": {
            "name": abbreviation or None,   # champ obligatoire côté Ricobot
            "ref": reference or None,
            "amount": amount or 0,
            "start_date": start_date or None,
            "end_date": end_date or None,
            "mission": mission_id,
        }
    }
    if file:
        payload["data"]["file"] = file

    response = requests.post(url, headers=headers, json=payload)
    if not response.ok:
        # On remonte le message d'erreur de Ricobot (sinon un 400 est opaque).
        raise RuntimeError(f"Ricobot {response.status_code} : {response.text}")
    return response.json()
