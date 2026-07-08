from datetime import datetime, timezone

from sqlalchemy import String, Text, Float, DateTime, ForeignKey
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship


# Horodatage en UTC (comportement identique SQLite / PostgreSQL).
def maintenant():
    return datetime.now(timezone.utc)


# Base commune à tous les modèles 
class Base(DeclarativeBase):
    pass


# Un e-mail reçu (l'en-tête affiché : expéditeur + objet).
# Un mail contient PLUSIEURS documents -> relation un-à-plusieurs.
class Mail(Base):
    __tablename__ = "mails"

    id: Mapped[int] = mapped_column(primary_key=True)
    message_id: Mapped[str] = mapped_column(String(512), unique=True)  # anti-doublon
    expediteur: Mapped[str | None] = mapped_column(String(256))
    expediteur_nom: Mapped[str | None] = mapped_column(String(256))
    objet: Mapped[str | None] = mapped_column(Text)
    date_mail: Mapped[str | None] = mapped_column(String(64))  # date du mail (ISO)
    date_analyse: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=maintenant)

    documents: Mapped[list["Document"]] = relationship(
        back_populates="mail", cascade="all, delete-orphan"
    )


# Un document (pièce jointe) analysé, rattaché à son mail.
class Document(Base):
    __tablename__ = "documents"

    id: Mapped[int] = mapped_column(primary_key=True)
    mail_id: Mapped[int] = mapped_column(ForeignKey("mails.id"))

    nom_fichier: Mapped[str] = mapped_column(String(512))
    chemin_local: Mapped[str | None] = mapped_column(Text)      # aperçu + téléchargement
    texte_extrait: Mapped[str | None] = mapped_column(Text)     # aperçu texte / debug

    # Résultat de l'analyse LLM (proposition figée au moment de l'analyse).
    type_document: Mapped[str | None] = mapped_column(String(64))
    projet_nom: Mapped[str | None] = mapped_column(Text)
    projet_client: Mapped[str | None] = mapped_column(String(256))
    projet_nextcloud: Mapped[str | None] = mapped_column(Text)  # URL Nextcloud du projet
    score_confiance: Mapped[float | None] = mapped_column(Float)

    # État / décision. statut : en_attente | a_signer | a_renvoyer | classe
    statut: Mapped[str] = mapped_column(String(32), default="en_attente")
    sous_dossier: Mapped[str | None] = mapped_column(String(64))     # Facturation / Documents_Admin
    chemin_nextcloud: Mapped[str | None] = mapped_column(Text)       # emplacement final après dépôt
    date_decision: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

    mail: Mapped["Mail"] = relationship(back_populates="documents")
