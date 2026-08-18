import json

import anthropic

from config.settings import settings
from classification.preparation_prompt_dossier import (
    formater_dossiers_pour_prompt,
    construire_prompt_dossier,
)
from classification.preparation_prompt_ricobot import construire_prompt_ricobot
from ricobot.lister_projet_ricot import formater_projets_pour_prompt

# Types de document autorisés (le LLM doit en choisir un).
TYPES_DOCUMENT = [
    "facture", "devis", "contrat", "avenant", "bon_de_commande",
    "document_administratif", "autre",
]

# Sortie garantie de l'analyse : index des dossiers retenus + type + score.
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

# Sortie garantie pour un bon de commande : mission(s) Ricobot + champs du BDC.
SCHEMA_RICOBOT = {
    "type": "object",
    "properties": {
        "mission_ids": {"type": "array", "items": {"type": "integer"}},
        "abbreviation": {"type": "string"},
        "reference": {"type": "string"},
        "end_date": {"type": "string"},
        "confidence": {"type": "number"},
    },
    "required": ["mission_ids", "abbreviation", "reference", "end_date", "confidence"],
    "additionalProperties": False,
}


class ClassifierV2:

    def __init__(self):
        self.client = anthropic.Anthropic(api_key=settings.claude_api_key)
        self.model = settings.claude_model

    # Un seul appel : type du document + dossier(s) Nextcloud retenus (index) + score.
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

        # Garde-fou : on ne garde que les index valides, et on résout les dossiers.
        dossier_ids = [i for i in data["dossier_ids"] if 0 <= i < len(dossiers)]
        dossiers_proposes = [dossiers[i] for i in dossier_ids]

        return {
            "dossier_ids": dossier_ids,
            "dossiers": dossiers_proposes,
            "type_document": data["type_document"],
            "score_confiance": data["score_confiance"],
        }

    # Un seul appel : mission(s) Ricobot rattachée(s) + champs extraits du bon de commande.
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

        # Garde-fou : on ne garde que les ID de mission qui existent vraiment.
        par_id = {p["id"]: p for p in projets}
        mission_ids = [i for i in data["mission_ids"] if i in par_id]
        missions_proposees = [par_id[i] for i in mission_ids]

        return {
            "mission_ids": mission_ids,
            "missions": missions_proposees,
            "abbreviation": data["abbreviation"],
            "reference": data["reference"],
            "end_date": data["end_date"],
            "confidence": data["confidence"],
        }
