# Préparation du prompt pour retrouver le DOSSIER Nextcloud de destination.
# Ce fichier ne fait AUCUN appel LLM : il met en forme la liste des dossiers et
# construit le texte du prompt. Le LLM renvoie l'INDEX du dossier ([i] de la liste),
# pas son nom : c'est plus court (moins de tokens) et sans ambiguïté.


def formater_dossiers_pour_prompt(dossiers):
    return "\n".join(f"[{i}] {d['nom']}" for i, d in enumerate(dossiers))


# Construit le prompt complet envoyé au LLM.
# On lui donne l'objet du mail, le texte du document et la liste des dossiers,
# et il renvoie l'index du dossier de destination le plus pertinent (ou -1).
def construire_prompt_dossier(objet_mail, texte_document, texte_dossiers):
    return (
        "Tu es un assistant de gestion documentaire de l'entreprise Numéricité.\n"
        "À partir de l'objet du mail et du document, retrouve Le dossier de la liste "
        "dans lequel ce document doit être classé.\n\n"

        "=== OBJET DU MAIL ===\n"
        "(contient parfois un indice sur le dossier)\n"
        f"{objet_mail}\n\n"

        "=== DOCUMENT (texte extrait) ===\n"
        f"{texte_document}\n\n"

        "=== DOSSIERS DISPONIBLES ===\n"
        "(chaque dossier est préfixé par son numéro entre crochets)\n"
        f"{texte_dossiers}\n\n"

        "=== CONSIGNE ===\n"
        "Réponds UNIQUEMENT avec un objet JSON valide, sans aucun texte autour, "
        "avec exactement ces clés :\n"
        '  - "dossier_ids" : la LISTE des numéros entre crochets des dossiers qui '
        "conviennent, du plus pertinent au moins pertinent.\n"
        "      • Si un seul dossier convient, mets un seul numéro : [3].\n"
        "      • Si PLUSIEURS dossiers portent le même nom ou conviennent autant, "
        "mets-les TOUS (l'utilisateur choisira) : [3, 7].\n"
        "      • Si aucun dossier de la liste ne convient, mets une liste vide : [].\n"
        '  - "score_confiance" : un nombre entre 0 et 1 indiquant ta certitude.\n'
    )
