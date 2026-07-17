import sys
sys.stdout.reconfigure(encoding='utf-8')

from pathlib import Path

from config.settings import settings
from emails.client import EmailClient
from extraction.data_preparation import DataPreparation
from nextcloud.lister_dossiers import lister_dossiers
from classification.classifier_v2 import ClassifierV2
from databases.repository import (
    init_db,
    mail_deja_traite,
    enregistrer_mail_et_documents,
)

# Formats que l'extraction sait traiter (Docling).
EXTENSIONS = {".pdf", ".docx"}

# Dossier racine Nextcloud dont on liste les dossiers candidats (cf. settings).
CHEMIN_NEXTCLOUD = settings.base_remote_path


# Pipeline v2 : mail → extraction → dossiers Nextcloud candidats (LLM) → base.
# La décision finale (choix du dossier / création / dépôt) se fait dans l'UI.
def executer_pipeline(hours=1000):
    init_db()

    emails = EmailClient().filter(hours=hours)
    if not emails:
        print("Rien à traiter.")
        return

    # Liste des dossiers candidats, commune à tous les documents (un seul appel réseau).
    dossiers = lister_dossiers(CHEMIN_NEXTCLOUD)
    print(f"{len(dossiers)} dossier(s) Nextcloud (< 1 an) dans « {CHEMIN_NEXTCLOUD} ».")

    prep = DataPreparation()
    classifier = ClassifierV2()

    for email in emails:
        if mail_deja_traite(email.get("message_id")):
            print(f"Mail déjà traité, ignoré : « {email['sujet']} »")
            continue

        analyses = []
        for chemin in email["fichiers_sauvegardes"]:
            fichier = Path(chemin)
            print(f"\nDocument : {fichier.name}")
            if fichier.suffix.lower() not in EXTENSIONS:
                print(f"  [!] Format non géré ({fichier.suffix}) — ignoré.")
                continue

            try:
                texte = prep.prepare(chemin)
                res = classifier.classer_dossier(email["sujet"], texte, dossiers)
                print(f"  type={res['type_document']}, "
                      f"{len(res['dossiers'])} dossier(s) candidat(s), "
                      f"score={res['score_confiance']}")

                analyses.append({
                    "nom_fichier": fichier.name,
                    "chemin_local": chemin,
                    "texte_extrait": texte,
                    "type_document": res["type_document"],
                    "score_confiance": res["score_confiance"],
                    "dossiers_candidats": res["dossiers"],   # liste {nom, chemin}
                })
            except Exception as e:
                print(f"  [ERREUR] {type(e).__name__}: {e} — document ignoré.")

        if analyses:
            enregistrer_mail_et_documents(email, analyses)
            print(f"  → mail + {len(analyses)} document(s) enregistrés en base.")


if __name__ == "__main__":
    executer_pipeline()
