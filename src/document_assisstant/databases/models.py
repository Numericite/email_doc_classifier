# Schéma de la base de données (PostgreSQL), en SQL pur.
# Plus d'ORM : les tables sont décrites ici et créées par repository.init_db().
#
# Chaque instruction est séparée : psycopg les exécute une par une.
# "IF NOT EXISTS" rend la création idempotente (on peut relancer sans risque).

SCHEMA_SQL = (
    # Un e-mail reçu (l'en-tête affiché : expéditeur + objet + date).
    """
    CREATE TABLE IF NOT EXISTS mails (
        id             SERIAL PRIMARY KEY,
        message_id     VARCHAR(512) UNIQUE,          -- anti-doublon
        expediteur     VARCHAR(256),
        expediteur_nom VARCHAR(256),
        objet          TEXT,
        date_mail      VARCHAR(64),                  -- date de réception (ISO)
        date_analyse   TIMESTAMPTZ NOT NULL DEFAULT NOW()
    );
    """,

    # Un document (pièce jointe) analysé, rattaché à son mail.
    # ON DELETE CASCADE : supprimer un mail supprime ses documents.
    """
    CREATE TABLE IF NOT EXISTS documents (
        id               SERIAL PRIMARY KEY,
        mail_id          INTEGER NOT NULL REFERENCES mails(id) ON DELETE CASCADE,

        nom_fichier      VARCHAR(512) NOT NULL,
        chemin_local     TEXT,                       -- aperçu + téléchargement
        texte_extrait    TEXT,

        -- Résultat de l'analyse LLM (proposition figée au moment de l'analyse)
        type_document    VARCHAR(64),
        projet_nom       TEXT,
        projet_client    VARCHAR(256),
        projet_nextcloud TEXT,                       -- URL Nextcloud du projet
        score_confiance  DOUBLE PRECISION,

        -- État / décision
        statut           VARCHAR(32) NOT NULL DEFAULT 'en_attente',
        sous_dossier     VARCHAR(64),                -- Facturation / Documents_Admin
        chemin_nextcloud TEXT,                       -- emplacement final après dépôt
        date_decision    TIMESTAMPTZ
    );
    """,

    # Index : accélèrent les requêtes de l'UI (documents d'un mail, filtre par statut).
    "CREATE INDEX IF NOT EXISTS idx_documents_mail_id ON documents(mail_id);",
    "CREATE INDEX IF NOT EXISTS idx_documents_statut  ON documents(statut);",
)
