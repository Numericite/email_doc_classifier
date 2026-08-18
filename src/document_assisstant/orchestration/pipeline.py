import sys
sys.stdout.reconfigure(encoding='utf-8')

import json
from pathlib import Path

from emails.client import EmailClient
from notion.imports_projet import get_projets_actifs
from extraction.data_preparation import DataPreparation
from classification.classifier import Classifier
from databases.repository import (
    init_db,
    mail_deja_traite,
    enregistrer_mail_et_documents,
)

# Formats que l'extraction sait traiter (Docling).
EXTENSIONS = {".pdf", ".docx"}

# Dossier où l'on écrit ce qui circule entre les étapes, pour pouvoir l'inspecter.
ETAPES_DIR = Path("data/etapes")
# Copie lisible des résultats de classification (inspection uniquement) —
# la source de vérité reste la base PostgreSQL.
RESULTATS_PATH = Path("data/resultats_analyse.json")


# Affiche un résumé de l'étape à l'écran ET sauvegarde le résultat complet sur disque.
# C'est ce qui permet de "voir ce qui se transmet entre les étapes".
def _etape(numero, titre, donnee, resume):
    print(f"\n{'='*70}\n[Étape {numero}] {titre}\n{'-'*70}")
    print(resume)

    ETAPES_DIR.mkdir(parents=True, exist_ok=True)
    chemin = ETAPES_DIR / f"{numero}_{titre}.json"
    with open(chemin, "w", encoding="utf-8") as f:
        json.dump(donnee, f, indent=2, ensure_ascii=False)
    print(f"  → détail complet : {chemin}")


# Chef d'orchestre : enchaîne les étapes dans le bon ordre et fait circuler les données.
# Aucune logique métier ici — tout le travail est délégué aux modules dédiés.
def executer_pipeline(hours=72):

    # Base de données prête (crée les tables au premier lancement).
    init_db()

    # --- Étape 1 : surveillance de la boîte mail (emails/) ---
    emails = EmailClient().filter(hours=hours)
    _etape(
        1, "emails", emails,
        f"{len(emails)} e-mail(s) avec pièce jointe :\n" + "\n".join(
            f"  • {e['sujet']}  ({len(e['fichiers_sauvegardes'])} fichier(s))"
            for e in emails
        ) or "  (aucun)",
    )
    if not emails:
        print("\nRien à traiter.")
        return []

    # --- Étape 2 : récupération des projets actifs (notion/) ---
    projets = get_projets_actifs()
    _etape(
        2, "projets_notion", projets,
        f"{len(projets)} projet(s) actif(s) récupéré(s) depuis Notion.",
    )

    # --- Étapes 3 & 4 : extraction (extraction/) puis analyse (classification/) ---
    prep = DataPreparation()
    classifier = Classifier()

    resultats = []          # copie de debug (JSON) — la base reste la source de vérité
    nb_docs = 0
    for email in emails:
        # Anti-doublon : un mail déjà en base n'est pas ré-analysé (économie de tokens).
        if mail_deja_traite(email.get("message_id")):
            print(f"\n{'#'*70}\nMail déjà traité, ignoré : « {email['sujet']} »")
            continue

        # On regroupe les analyses des documents de CE mail (relation un-à-plusieurs).
        analyses = []
        for chemin in email["fichiers_sauvegardes"]:
            fichier = Path(chemin)
            print(f"\n{'#'*70}\nDocument : {fichier.name}  (mail : « {email['sujet']} »)")

            if fichier.suffix.lower() not in EXTENSIONS:
                print(f"  [!] Format non géré ({fichier.suffix}) — ignoré.")
                continue

            try:
                # Étape 3 : extraction du texte.
                texte = prep.prepare(chemin)
                print(f"  [3] Extraction : {len(texte)} caractères.")

                # Étape 4 : analyse LLM (un seul appel).
                infos = classifier.classer(email["sujet"], texte, projets)
                print(f"  [4] Analyse : type={infos['type_document']}, "
                      f"projet={infos['projet']['projet_name'] if infos['projet'] else '(aucun)'}, "
                      f"score={infos['score_confiance']}")

                analyses.append({
                    "nom_fichier": fichier.name,
                    "chemin_local": chemin,
                    "texte_extrait": texte,
                    "type_document": infos["type_document"],
                    "projet": infos["projet"],       # dict complet (nom, client, nextcloud)
                    "score_confiance": infos["score_confiance"],
                })
            except Exception as e:
                # L'orchestrateur décide : on saute ce document et on continue.
                print(f"  [ERREUR] {type(e).__name__}: {e} — document ignoré.")

        # Enregistrement en base : le mail + tous ses documents analysés.
        if analyses:
            enregistrer_mail_et_documents(email, analyses)
            nb_docs += len(analyses)
            print(f"  → mail + {len(analyses)} document(s) enregistrés en base.")
            resultats.append({"email": email["sujet"], "documents": analyses})

    # --- Copie lisible des résultats de classification (inspection uniquement) ---
    RESULTATS_PATH.parent.mkdir(parents=True, exist_ok=True)
    with open(RESULTATS_PATH, "w", encoding="utf-8") as f:
        json.dump(resultats, f, indent=2, ensure_ascii=False)
    print(f"\n{'='*70}\n{nb_docs} document(s) enregistré(s) dans PostgreSQL. "
          f"Résultats de classification : {RESULTATS_PATH}")
    return resultats


if __name__ == "__main__":
    executer_pipeline()
