# Accès aux données (repository pattern) : tout le SQL vit ici ; le reste de l'app
# n'appelle que ces fonctions et ignore quelle base est derrière.

import psycopg
from psycopg.rows import dict_row
from psycopg.types.json import Jsonb

from config.settings import settings
from databases.models import SCHEMA_SQL


# Ouvre une connexion (le `with` valide/annule la transaction et ferme tout seul).
def _connexion():
    return psycopg.connect(settings.database_url)


# Crée tables et index si absents (idempotent).
def init_db():
    with _connexion() as conn, conn.cursor() as cur:
        for instruction in SCHEMA_SQL:
            cur.execute(instruction)
        conn.commit()


# True si le mail est déjà en base (à vérifier avant d'analyser → économie de tokens).
def mail_deja_traite(message_id):
    if not message_id:
        return False
    with _connexion() as conn, conn.cursor() as cur:
        cur.execute("SELECT 1 FROM mails WHERE message_id = %s", (message_id,))
        return cur.fetchone() is not None


# Insère un mail + ses documents (tout ou rien). Ignore si le message_id existe déjà.
def enregistrer_mail_et_documents(email, analyses):
    message_id = email.get("message_id")
    with _connexion() as conn, conn.cursor() as cur:
        if message_id:
            cur.execute("SELECT 1 FROM mails WHERE message_id = %s", (message_id,))
            if cur.fetchone():
                return False  # déjà traité

        # RETURNING id : récupère l'identifiant du mail créé.
        cur.execute(
            """
            INSERT INTO mails (message_id, expediteur, expediteur_nom, objet, date_mail)
            VALUES (%s, %s, %s, %s, %s)
            RETURNING id
            """,
            (message_id, email.get("sender"), email.get("nom_sender"),
             email.get("sujet"), email.get("date")),
        )
        mail_id = cur.fetchone()[0]

        for a in analyses:
            projet = a.get("projet") or {}
            cur.execute(
                """
                INSERT INTO documents (
                    mail_id, nom_fichier, chemin_local, type_document,
                    projet_nom, projet_client, projet_nextcloud, score_confiance,
                    dossiers_candidats, bdc_ricobot
                )
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                """,
                (mail_id, a["nom_fichier"], a.get("chemin_local"),
                 a.get("type_document"), projet.get("projet_name"), projet.get("client"),
                 projet.get("nextcloud"), a.get("score_confiance"),
                 Jsonb(a.get("dossiers_candidats") or []),
                 Jsonb(a["bdc_ricobot"]) if a.get("bdc_ricobot") else None),
            )

        conn.commit()
        return True


# Mails (récents d'abord) avec leurs documents groupés. `statut` filtre les documents.
def lister_mails(statut=None):
    with _connexion() as conn, conn.cursor(row_factory=dict_row) as cur:  # lignes en dict
        cur.execute(
            "SELECT id, expediteur, expediteur_nom, objet, date_mail "
            "FROM mails ORDER BY date_analyse DESC"
        )
        mails = cur.fetchall()
        if not mails:
            return []

        if statut:
            cur.execute("SELECT * FROM documents WHERE statut = %s ORDER BY id", (statut,))
        else:
            cur.execute("SELECT * FROM documents ORDER BY id")
        documents = cur.fetchall()

    # Regroupe les documents sous leur mail.
    par_mail = {}
    for d in documents:
        par_mail.setdefault(d["mail_id"], []).append(d)

    resultat = []
    for m in mails:
        docs = par_mail.get(m["id"], [])
        if statut and not docs:
            continue  # aucun document du statut demandé
        m["documents"] = docs
        resultat.append(m)
    return resultat


# Change le statut d'un document (COALESCE = garde la valeur existante si non fournie).
def changer_statut(document_id, statut, sous_dossier=None, chemin_nextcloud=None):
    with _connexion() as conn, conn.cursor() as cur:
        cur.execute(
            """
            UPDATE documents
               SET statut           = %s,
                   sous_dossier     = COALESCE(%s, sous_dossier),
                   chemin_nextcloud = COALESCE(%s, chemin_nextcloud),
                   date_decision    = NOW()
             WHERE id = %s
            """,
            (statut, sous_dossier, chemin_nextcloud, document_id),
        )
        modifie = cur.rowcount > 0
        conn.commit()
        return modifie


# Supprime un mail et ses documents (ON DELETE CASCADE). Corbeille de l'UI.
def supprimer_mail(mail_id):
    with _connexion() as conn, conn.cursor() as cur:
        cur.execute("DELETE FROM mails WHERE id = %s", (mail_id,))
        conn.commit()


# Met à jour le bloc BDC d'un document (après édition ou remplissage dans l'UI).
def maj_bdc_ricobot(document_id, bdc):
    with _connexion() as conn, conn.cursor() as cur:
        cur.execute(
            "UPDATE documents SET bdc_ricobot = %s WHERE id = %s",
            (Jsonb(bdc), document_id),
        )
        conn.commit()
