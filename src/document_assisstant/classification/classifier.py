import json
import logging
import re
import unicodedata
from difflib import SequenceMatcher

import ollama

from config.settings import settings

logger = logging.getLogger(__name__)


def _norm(s):
    """Normalise un nom : sans accents, minuscules, sans ponctuation/espaces."""
    s = unicodedata.normalize("NFKD", str(s)).encode("ascii", "ignore").decode()
    return re.sub(r"[^a-z0-9]", "", s.lower())


def _est_numericite(nom):
    """True si le nom désigne Numéricité, en tolérant les déformations OCR
    (ex: 'NU[NERICITE', 'SAS NUMERI'CITE', 'numericite.fr')."""
    n = _norm(nom)
    if "numeri" in n:
        return True
    return SequenceMatcher(None, n, "numericite").ratio() >= 0.8


class Classifier:

    def analyser(self, text, model=None):
        """Analyse structurée d'un document via le LLM local.

        Renvoie un dict : {type_document, client, projet}.
        - type_document : facture, devis, contrat, avenant, bon_de_commande,
          document_administratif, autre
        - client : l'organisation qui commande/paie (jamais Numéricité, qui est
          le prestataire). "inconnu" si introuvable.
        - projet : objet / nom de la prestation. "inconnu" si introuvable.
        """
        model = model or settings.extraction_model

        prompt = (
            "Tu es un assistant de l'entreprise Numéricité (NUMERI'CITE), "
            "qui est le prestataire.\n"
            "Analyse le document ci-dessous et réponds UNIQUEMENT avec un objet JSON "
            "valide, sans aucun texte autour, avec exactement ces clés :\n"
            '  - "type_document" : un seul mot parmi : facture, devis, contrat, avenant, bon de commance, document_administratif, autre (ça dépend de titre de document). '
            "bon_de_commande, document_administratif, autre\n"
            '  - "client" : la CONTREPARTIE de Numéricité, c\'est-à-dire l\'autre '
            "organisation avec qui le document est établi (client, donneur d'ordre, "
            "pouvoir adjudicateur, destinataire, ou co-contractant / partenaire — ex: "
            "l'autre signataire d'un accord de confidentialité).\n"
            "    Ce doit être un VRAI nom d'organisation (raison sociale, nom propre : "
            "ex. « GIP Inclusion », « Expertise France »), et JAMAIS un simple rôle "
            "générique (« la Société », « le Prestataire », « la Partie », « le Client »). "
            "Dans ces documents, Numéricité est le prestataire et est souvent désignée par "
            "un tel rôle générique ou par un champ vide à remplir (« [ ] », « XXX ») : "
            "ignore ce rôle, le client est l'AUTRE organisation, celle qui est nommée "
            "explicitement. "
            'Si aucune organisation nommée autre que Numéricité n\'apparaît, mets "inconnu".\n'
            '  - "parties" : la liste des organisations parties au document '
            "(entreprises/administrations qui signent ou sont destinataires), telles qu'écrites.\n"
            '  - "projet" : l\'objet ou le nom du projet / de la prestation. '
            'Si tu ne le trouves pas, mets "inconnu".\n'
            '  - "signature" : "oui" si le document semble signé (présence de signatures, '
            'mentions "signé", "lu et approuvé", nom + fonction du signataire), sinon "non".\n\n'
            "Texte du document :\n"
            "\"\"\"\n"
            f"{text}\n"
            "\"\"\"\n"
        )

        # num_ctx élevé : sinon Ollama tronque le texte (défaut ~4096 tokens) et le
        # modèle ne "voit" pas la fin des documents longs (contrats 10+ pages).
        kwargs = {
            "model": model,
            "messages": [{"role": "user", "content": prompt}],
            "format": "json",
            "options": {"temperature": 0, "seed": 42, "num_ctx": 16384},
        }
        # Le mode "thinking" n'existe que sur les modèles raisonneurs (qwen3) ;
        # le désactiver évite les balises <think> et accélère. Sur les autres
        # modèles (qwen2.5, mistral...), on ne passe pas ce paramètre.
        if "qwen3" in model:
            kwargs["think"] = False

        response = ollama.chat(**kwargs)
        contenu = response["message"]["content"].strip()

        try:
            data = json.loads(contenu)
        except json.JSONDecodeError:
            logger.warning("Réponse LLM non-JSON : %r", contenu[:300])
            return {"type_document": "autre", "client": "inconnu",
                    "projet": "inconnu", "_raw": contenu}

        # Garde-fou "client" : le LLM confond parfois prestataire et client sur
        # les docs sans mots "client/fournisseur" (avenants, marchés publics).
        # Comme Numéricité est toujours le prestataire, si le client proposé est
        # Numéricité (ou vide), on le remplace par l'autre partie du document.
        client = data.get("client") or "inconnu"
        if client == "inconnu" or _est_numericite(client):
            autres = [p for p in (data.get("parties") or []) if not _est_numericite(p)]
            # On ne remplace que si l'autre partie est sans ambiguïté (une seule) ;
            # sinon on préfère "inconnu" à un mauvais choix dans une liste bruitée.
            if len(autres) == 1:
                client = autres[0]

        return {
            "type_document": data.get("type_document", "autre"),
            "client": client,
            "projet": data.get("projet", "inconnu"),
            "signature": data.get("signature", "inconnu"),
        }
