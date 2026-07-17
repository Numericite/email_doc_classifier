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

        "=== RÈGLES DE RAPPROCHEMENT ===\n"
        "1. Identifie d'abord le CLIENT du document : l'organisation destinataire / "
        "donneuse d'ordre. Ce n'est JAMAIS Numéricité, qui est le prestataire.\n"
        "2. Un dossier ne convient que s'il désigne le MÊME client/organisme ou le "
        "MÊME projet. Le rapprochement repose sur cette identité, rien d'autre.\n"
        "3. Ne te base JAMAIS sur une ressemblance superficielle : sigle proche, "
        "numéro de devis, référence, adresse, mot générique. Exemples de rapprochements "
        "INTERDITS : un devis pour « Kaufman Broad (KB) » n'a RIEN à voir avec un "
        "dossier « Bénin-SIG-WB » ; un devis « n° HNO20241007 » ne se rattache PAS à "
        "un dossier « Groupement HNO ».\n"
        "4. Sois LARGE sur les homonymes : si plusieurs dossiers concernent le même "
        "client, pays ou organisme, mets-les TOUS, même si leurs noms diffèrent un peu. "
        "C'est l'utilisateur qui tranchera.\n"
        "5. Sois STRICT sur la pertinence : si le client du document n'a AUCUN dossier "
        "dans la liste, réponds une liste vide. Une liste VIDE est BIEN MEILLEURE "
        "qu'une proposition hasardeuse : l'utilisateur créera le dossier lui-même. "
        "Ne force JAMAIS un rapprochement juste pour donner une réponse.\n\n"

        "=== CONSIGNE ===\n"
        "Réponds UNIQUEMENT avec un objet JSON valide, sans aucun texte autour, "
        "avec exactement ces clés :\n"
        '  - "dossier_ids" : la LISTE des numéros entre crochets des dossiers qui '
        "conviennent, du plus pertinent au moins pertinent.\n"
        "      • Un seul dossier pertinent : [3].\n"
        "      • Plusieurs dossiers du même client/organisme : mets-les TOUS : [3, 7].\n"
        "      • Aucun dossier vraiment pertinent : [].\n"
        '  - "type_document" : un seul mot parmi cette liste : '
        "facture, devis, contrat, avenant, bon_de_commande, "
        "document_administratif, autre.\n"
        '  - "score_confiance" : un nombre entre 0 et 1 indiquant ta certitude sur '
        "le rapprochement (0 si la liste est vide).\n"
    )
