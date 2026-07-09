# Couche d'accès aux données (repository pattern).
# TOUT le SQL vit ici. Le pipeline et l'UI n'utilisent que ces fonctions —
# ils ne savent pas quelle base est derrière. Passer à PostgreSQL = changer
# DATABASE_URL dans la config, rien d'autre.

from sqlalchemy import create_engine, select
from sqlalchemy.orm import sessionmaker, selectinload

from config.settings import settings
from databases.models import Base, Mail, Document, maintenant

engine = create_engine(settings.database_url)
Session = sessionmaker(bind=engine)


# Crée les tables si elles n'existent pas encore (idempotent).
def init_db():
    Base.metadata.create_all(engine)


# True si ce mail a déjà été enregistré (à vérifier AVANT d'analyser, pour ne pas
# re-dépenser des tokens sur un mail déjà traité).
def mail_deja_traite(message_id):
    if not message_id:
        return False
    with Session() as s:
        return s.scalar(select(Mail.id).where(Mail.message_id == message_id)) is not None


# Sérialise un Document en dict simple pour l'UI (évite les objets SQLAlchemy détachés).
def _document_dict(d):
    return {
        "id": d.id,
        "nom_fichier": d.nom_fichier,
        "chemin_local": d.chemin_local,
        "texte_extrait": d.texte_extrait,
        "type_document": d.type_document,
        "projet_nom": d.projet_nom,
        "projet_client": d.projet_client,
        "projet_nextcloud": d.projet_nextcloud,
        "score_confiance": d.score_confiance,
        "statut": d.statut,
        "sous_dossier": d.sous_dossier,
        "chemin_nextcloud": d.chemin_nextcloud,
    }


# Enregistre un mail et ses documents analysés.
# - email    : dict issu de emails/ (message_id, sujet, sender, nom_sender, date)
# - analyses : liste de dicts {nom_fichier, chemin_local, texte_extrait,
#              type_document, projet (dict|None), score_confiance}
# Anti-doublon : si le message_id est déjà en base, on ignore (déjà traité).
# Renvoie True si inséré, False si ignoré (déjà présent).
def enregistrer_mail_et_documents(email, analyses):
    message_id = email.get("message_id")
    with Session() as s:
        if message_id and s.scalar(select(Mail).where(Mail.message_id == message_id)):
            return False  # mail déjà traité

        mail = Mail(
            message_id=message_id,
            expediteur=email.get("sender"),
            expediteur_nom=email.get("nom_sender"),
            objet=email.get("sujet"),
            date_mail=email.get("date"),
        )
        for a in analyses:
            projet = a.get("projet") or {}
            mail.documents.append(Document(
                nom_fichier=a["nom_fichier"],
                chemin_local=a.get("chemin_local"),
                texte_extrait=a.get("texte_extrait"),
                type_document=a.get("type_document"),
                projet_nom=projet.get("projet_name"),
                projet_client=projet.get("client"),
                projet_nextcloud=projet.get("nextcloud"),
                score_confiance=a.get("score_confiance"),
            ))
        s.add(mail)
        s.commit()
        return True


# Liste les mails avec leurs documents (pour l'affichage), du plus récent au plus ancien.
# Si `statut` est fourni, ne garde que les documents ayant ce statut.
def lister_mails(statut=None):
    with Session() as s:
        mails = s.scalars(
            select(Mail).options(selectinload(Mail.documents)).order_by(Mail.date_analyse.desc())
        ).all()

        resultat = []
        for m in mails:
            docs = m.documents
            if statut:
                docs = [d for d in docs if d.statut == statut]
                if not docs:
                    continue
            resultat.append({
                "id": m.id,
                "expediteur": m.expediteur,
                "expediteur_nom": m.expediteur_nom,
                "objet": m.objet,
                "date_mail": m.date_mail,
                "documents": [_document_dict(d) for d in docs],
            })
        return resultat


# Change le statut d'un document (bouton Valider / Refuser de l'UI).
# On peut renseigner le sous-dossier et le chemin Nextcloud lors d'un classement.
# Renvoie True si le document existe, False sinon.
def changer_statut(document_id, statut, sous_dossier=None, chemin_nextcloud=None):
    with Session() as s:
        doc = s.get(Document, document_id)
        if doc is None:
            return False
        doc.statut = statut
        if sous_dossier is not None:
            doc.sous_dossier = sous_dossier
        if chemin_nextcloud is not None:
            doc.chemin_nextcloud = chemin_nextcloud
        doc.date_decision = maintenant()
        s.commit()
        return True



