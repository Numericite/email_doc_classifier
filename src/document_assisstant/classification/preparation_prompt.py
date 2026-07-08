# Préparation du texte injecté dans le prompt du LLM.
# Ce fichier ne fait AUCUN appel LLM : il se contente de mettre en forme les
# données (projets Notion, etc.) pour qu'elles soient compactes et lisibles.


# Transforme la liste des projets en texte compact pour le prompt LLM.
# On ne garde que ce qui aide le LLM à reconnaître le projet (nom, client,
# description). Chaque projet est préfixé par son index [i] : le LLM renvoie
# cet index, qu'on réutilise ensuite pour retrouver le dossier Nextcloud, etc.

def formater_projets_pour_prompt(projets, max_desc=120):
    lignes = []
    for i, p in enumerate(projets):
        ligne = f"[{i}] {p['projet_name']}"
        if p["client"]:
            ligne += f" | client: {p['client']}"
        if p["description"]:
            desc = p["description"].replace("\n", " ").strip()
            if len(desc) > max_desc:
                desc = desc[:max_desc] + "…"
            ligne += f" | {desc}"
        lignes.append(ligne)
    return "\n".join(lignes)


# Construit le prompt complet envoyé au LLM.
# Il assemble 3 blocs de contexte (objet du mail, texte du document, liste des
# projets) puis la consigne : retrouver le bon projet et répondre en JSON.
# Le LLM renvoie l'INDEX du projet ([i] de la liste), pas son nom : c'est plus
# court (moins de tokens) et sans ambiguïté quand deux projets ont le même nom.
def construire_prompt(objet_mail, texte_document, texte_projets):
    return (
        "Tu es un assistant de gestion documentaire de l'entreprise Numéricité.\n"
        "À partir de l'objet du mail, du document et de la liste des projets en "
        "cours, retrouve LE projet auquel ce document se rattache.\n\n"

        "=== OBJET DU MAIL ===\n"
        "(contient parfois le nom du projet , utilise-le comme indice)\n"
        f"{objet_mail}\n\n"

        "=== DOCUMENT (texte extrait) ===\n"
        f"{texte_document}\n\n"

        "=== PROJETS EN COURS ===\n"
        "(chaque projet est préfixé par son numéro entre crochets)\n"
        f"{texte_projets}\n\n"

        "=== CONSIGNE ===\n"
        "Réponds UNIQUEMENT avec un objet JSON valide, sans aucun texte autour, "
        "avec exactement ces clés :\n"
        '  - "projet_id" : le NUMÉRO entre crochets du projet retrouvé, '
        "ou -1 si aucun projet de la liste ne correspond.\n"
        '  - "type_document" : un seul mot parmi cette liste : '
        "facture, devis, contrat, avenant, bon_de_commande, "
        "document_administratif, autre.\n"
        '  - "score_confiance" : un nombre entre 0 et 1 indiquant ta certitude.\n'
    )
