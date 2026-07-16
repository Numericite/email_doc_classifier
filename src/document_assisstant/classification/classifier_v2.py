import json

import anthropic

from config.settings import settings
from classification.preparation_prompt_dossier import (
    formater_dossiers_pour_prompt,
    construire_prompt_dossier,
)

# Schéma structuré : le LLM renvoie la LISTE des index de dossiers qui conviennent
# (vide si aucun, plusieurs en cas d'ambiguïté) + un score.
# output_config garantit une réponse JSON valide et conforme à ce schéma.
SCHEMA_DOSSIER = {
    "type": "object",
    "properties": {
        "dossier_ids": {"type": "array", "items": {"type": "integer"}},
        "score_confiance": {"type": "number"},
    },
    "required": ["dossier_ids", "score_confiance"],
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
            "score_confiance": data["score_confiance"],
        }
