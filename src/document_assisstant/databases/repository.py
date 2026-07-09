# Couche d'accès aux données (repository pattern), en SQL direct sur PostgreSQL.
# TOUT le SQL vit ici. Le pipeline et l'UI n'utilisent que ces fonctions —
# ils ne savent pas quelle base est derrière ni comment elle est interrogée.

import psycopg
from psycopg.rows import dict_row

from config.settings import settings
from databases.models import SCHEMA_SQL


# Ouvre une connexion à PostgreSQL (chaîne de connexion lue dans .env via settings).
# Utilisée avec `with` : la transaction est validée à la sortie, annulée si erreur,
# et la connexion est fermée automatiquement.
def _connexion():
    return psycopg.connect(settings.database_url)


# Crée les tables et les index s'ils n'existent pas encore (idempotent).
def init_db():
    with _connexion() as conn, conn.cursor() as cur:
        for instruction in SCHEMA_SQL:
            cur.execute(instruction)
        conn.commit()


# True si ce mail a déjà été enregistré (à vérifier AVANT d'analyser, pour ne pas
# re-dépenser des tokens sur un mail déjà traité).
def mail_deja_traite(message_id):
    if not message_id:
        return False
    with _connexion() as conn, conn.cursor() as cur:
        cur.execute("SELECT 1 FROM mails WHERE message_id = %s", (message_id,))
        return cur.fetchone() is not None


# Enregistre un mail et ses documents analysés (une transaction : tout ou rien).
# - email    : dict issu de emails/ (message_id, sujet, sender, nom_sender, date)
# - analyses : liste de dicts {nom_fichier, chemin_local, texte_extrait,
#              type_document, projet (dict|None), score_confiance}
# Anti-doublon : si le message_id est déjà en base, on ignore (déjà traité).
# Renvoie True si inséré, False si ignoré.
def enregistrer_mail_et_documents(email, analyses):
    message_id = email.get("message_id")
    with _connexion() as conn, conn.cursor() as cur:
        if message_id:
            cur.execute("SELECT 1 FROM mails WHERE message_id = %s", (message_id,))
            if cur.fetchone():
                return False  # mail déjà traité

        # RETURNING id : PostgreSQL nous rend l'identifiant du mail qu'il vient de créer.
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
                    mail_id, nom_fichier, chemin_local, texte_extrait, type_document,
                    projet_nom, projet_client, projet_nextcloud, score_confiance
                )
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)
                """,
                (mail_id, a["nom_fichier"], a.get("chemin_local"), a.get("texte_extrait"),
                 a.get("type_document"), projet.get("projet_name"), projet.get("client"),
                 projet.get("nextcloud"), a.get("score_confiance")),
            )

        conn.commit()
        return True


# Liste les mails avec leurs documents (pour l'affichage), du plus récent au plus ancien.
# Si `statut` est fourni, ne garde que les documents ayant ce statut.
def lister_mails(statut=None):
    # dict_row : chaque ligne revient sous forme de dictionnaire {colonne: valeur}.
    with _connexion() as conn, conn.cursor(row_factory=dict_row) as cur:
        cur.execute(
            """
            SELECT id, expediteur, expediteur_nom, objet, date_mail
              FROM mails
             ORDER BY date_analyse DESC
            """
        )
        mails = cur.fetchall()
        if not mails:
            return []

        if statut:
            cur.execute("SELECT * FROM documents WHERE statut = %s ORDER BY id", (statut,))
        else:
            cur.execute("SELECT * FROM documents ORDER BY id")
        documents = cur.fetchall()

    # On regroupe les documents sous leur mail (relation un-à-plusieurs).
    par_mail = {}
    for d in documents:
        par_mail.setdefault(d["mail_id"], []).append(d)

    resultat = []
    for m in mails:
        docs = par_mail.get(m["id"], [])
        if statut and not docs:
            continue  # ce mail n'a aucun document du statut demandé
        m["documents"] = docs
        resultat.append(m)
    return resultat


# Change le statut d'un document (select de statut / bouton Classé de l'UI).
# COALESCE(%s, colonne) : si on ne passe pas la valeur, on garde celle déjà en base.
# Renvoie True si le document existe, False sinon.
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
