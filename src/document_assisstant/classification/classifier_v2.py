import json

import anthropic

from config.settings import settings
from classification.preparation_prompt_dossier import (
    formater_dossiers_pour_prompt,
    construire_prompt_dossier,
)
from classification.preparation_prompt_ricobot import construire_prompt_ricobot
from ricobot.lister_projet_ricot import formater_projets_pour_prompt

# Schéma structuré : le LLM renvoie la LISTE des index de dossiers qui conviennent
# (vide si aucun, plusieurs en cas d'ambiguïté) + un score.
# output_config garantit une réponse JSON valide et conforme à ce schéma.
TYPES_DOCUMENT = [
    "facture", "devis", "contrat", "avenant", "bon_de_commande",
    "document_administratif", "autre",
]

SCHEMA_DOSSIER = {
    "type": "object",
    "properties": {
        "dossier_ids": {"type": "array", "items": {"type": "integer"}},
        "type_document": {"type": "string", "enum": TYPES_DOCUMENT},
        "score_confiance": {"type": "number"},
    },
    "required": ["dossier_ids", "type_document", "score_confiance"],
    "additionalProperties": False,
}

# Schéma de l'appel Ricobot (bons de commande) : mission(s) rattachée(s) +
# champs extraits du BDC. mission_ids contient les ID RÉELS Ricobot.
SCHEMA_RICOBOT = {
    "type": "object",
    "properties": {
        "mission_ids": {"type": "array", "items": {"type": "integer"}},
        "abbreviation": {"type": "string"},
        "reference": {"type": "string"},
        "end_date": {"type": "string"},
        "amount": {"type": "number"},
        "confidence": {"type": "number"},
    },
    "required": ["mission_ids", "abbreviation", "reference", "end_date",
                 "amount", "confidence"],
    "additionalProperties": False,
}


class ClassifierV2:

    def __init__(self):
        self.client = anthropic.Anthropic(api_key=settings.claude_api_key)
        self.model = settings.claude_model

    # Retrouve le(s) DOSSIER(S) Nextcloud de destination parmi une liste.
    # Un SEUL appel Anthropic. Le LLM renvoie la liste des index qui conviennent :
    #   - liste vide  → aucun dossier pertinent (proposer d'en créer un)
    #   - un seul     → on le propose
    #   - plusieurs   → ambiguïté, l'utilisateur choisira
    # Renvoie un dict : {dossier_ids, dossiers, score_confiance}.
    def classer_dossier(self, objet_mail, texte_document, dossiers):
        texte_dossiers = formater_dossiers_pour_prompt(dossiers)
        prompt = construire_prompt_dossier(objet_mail, texte_document, texte_dossiers)

        response = self.client.messages.create(
            model=self.model,
            max_tokens=1024,
            output_config={"format": {"type": "json_schema", "schema": SCHEMA_DOSSIER}},
            messages=[{"role": "user", "content": prompt}],
        )

        contenu = next(b.text for b in response.content if b.type == "text")
        data = json.loads(contenu)

        # On ne garde que les index valides, et on retrouve les dossiers complets.
        dossier_ids = [i for i in data["dossier_ids"] if 0 <= i < len(dossiers)]
        dossiers_proposes = [dossiers[i] for i in dossier_ids]

        return {
            "dossier_ids": dossier_ids,
            "dossiers": dossiers_proposes,
            "type_document": data["type_document"],
            "score_confiance": data["score_confiance"],
        }

    # Rattache un BON DE COMMANDE à une mission Ricobot ET extrait ses champs,
    # en UN SEUL appel Anthropic. `projets` : liste {id, nom, company} (Ricobot).
    # Renvoie : {mission_ids, missions, abbreviation, reference, end_date, confidence}.
    def classer_ricobot(self, objet_mail, texte_document, projets, dossier_valide=""):
        texte_missions = formater_projets_pour_prompt(projets)
        prompt = construire_prompt_ricobot(objet_mail, texte_document, texte_missions)

        response = self.client.messages.create(
            model=self.model,
            max_tokens=1024,
            output_config={"format": {"type": "json_schema", "schema": SCHEMA_RICOBOT}},
            messages=[{"role": "user", "content": prompt}],
        )

        contenu = next(b.text for b in response.content if b.type == "text")
        data = json.loads(contenu)

        # Le LLM renvoie des ID Ricobot réels : on ne garde que ceux qui existent
        # vraiment dans la liste (garde-fou contre un ID inventé).
        par_id = {p["id"]: p for p in projets}
        mission_ids = [i for i in data["mission_ids"] if i in par_id]
        missions_proposees = [par_id[i] for i in mission_ids]

        return {
            "mission_ids": mission_ids,
            "missions": missions_proposees,
            "abbreviation": data["abbreviation"],
            "reference": data["reference"],
            "end_date": data["end_date"],
            "amount": data["amount"],
            "confidence": data["confidence"],
        }
