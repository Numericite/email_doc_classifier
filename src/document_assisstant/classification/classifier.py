import json
import logging

import anthropic

from config.settings import settings
from classification.preparation_prompt import (
    formater_projets_pour_prompt,
    construire_prompt,
)
from classification.preparation_prompt_dossier import (
    formater_dossiers_pour_prompt,
    construire_prompt_dossier,
)

logger = logging.getLogger(__name__)


# Schéma de la réponse attendue du LLM.
# Avec les "structured outputs" d'Anthropic, la réponse est GARANTIE conforme :
# JSON toujours valide, type_document toujours dans la liste. Pas de post-parsing fragile.
SCHEMA_REPONSE = {
    "type": "object",
    "properties": {
        "projet_id": {"type": "integer"},
        "type_document": {
            "type": "string",
            "enum": [
                "facture", "devis", "contrat", "avenant",
                "bon_de_commande", "document_administratif", "autre",
            ],
        },
        "score_confiance": {"type": "number"},
    },
    "required": ["projet_id", "type_document", "score_confiance"],
    "additionalProperties": False,
}


# Schéma pour le choix du DOSSIER Nextcloud : le LLM renvoie l'index du dossier
# (ou -1 si aucun) et un score de confiance.
SCHEMA_DOSSIER = {
    "type": "object",
    "properties": {
        "dossier_id": {"type": "integer"},
        "score_confiance": {"type": "number"},
    },
    "required": ["dossier_id", "score_confiance"],
    "additionalProperties": False,
}


class Classifier:

    def __init__(self):
        self.client = anthropic.Anthropic(api_key=settings.claude_api_key)
        self.model = settings.claude_model

    # Analyse d'un document : retrouve le projet et le type de document.
    # Un SEUL appel Anthropic par document (cf. product.md).
    # Renvoie un dict : {projet_id, projet, type_document, score_confiance}.
    def classer(self, objet_mail, texte_document, projets):
        texte_projets = formater_projets_pour_prompt(projets)
        prompt = construire_prompt(objet_mail, texte_document, texte_projets)

        response = self.client.messages.create(
            model=self.model,
            max_tokens=1024,
            output_config={"format": {"type": "json_schema", "schema": SCHEMA_REPONSE}},
            messages=[{"role": "user", "content": prompt}],
        )

        # output_config garantit un bloc texte contenant du JSON valide.
        contenu = next(b.text for b in response.content if b.type == "text")
        data = json.loads(contenu)

        # On retrouve le projet complet à partir de son index [i].
        projet_id = data["projet_id"]
        projet = projets[projet_id] if 0 <= projet_id < len(projets) else None
        if projet is None:
            projet_id = -1  # aucun projet retenu

        return {
            "projet_id": projet_id,
            "projet": projet,
            "type_document": data["type_document"],
            "score_confiance": data["score_confiance"],
        }

    # Retrouve le DOSSIER Nextcloud de destination parmi une liste.
    # Un SEUL appel Anthropic. Le LLM renvoie l'index du dossier (ou -1).
    # Renvoie un dict : {dossier_id, dossier, score_confiance}.
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

        # On retrouve le dossier complet à partir de son index [i].
        dossier_id = data["dossier_id"]
        dossier = dossiers[dossier_id] if 0 <= dossier_id < len(dossiers) else None
        if dossier is None:
            dossier_id = -1  # aucun dossier retenu → proposer d'en créer un

        return {
            "dossier_id": dossier_id,
            "dossier": dossier,
            "score_confiance": data["score_confiance"],
        }
