import sys
import shutil
from pathlib import Path

from PySide6.QtWidgets import (
    QApplication, QMainWindow, QWidget, QScrollArea, QFrame,
    QVBoxLayout, QHBoxLayout, QLabel, QPushButton, QComboBox,
    QFileDialog, QMessageBox, QGraphicsDropShadowEffect,
)
from PySide6.QtGui import QDesktopServices, QFont, QColor
from PySide6.QtCore import QUrl, Qt

from config.settings import settings
from databases.repository import init_db, lister_mails, changer_statut
from nextcloud.depot import deposer_document, creer_dossier, generer_nom_dossier


# Les statuts, dans l'ordre du menu déroulant : (clé interne, libellé affiché).
STATUTS = [
    ("en_attente", "En attente"),
    ("a_signer", "À signer"),
    ("a_renvoyer", "À renvoyer"),
    ("classe", "Classé"),
]

# Couleur du menu de statut selon sa valeur : (fond, texte).
COULEURS_STATUT = {
    "classe":     ("#E6F7EC", "#1B9E52"),  # vert
    "en_attente": ("#FFF4E5", "#E08600"),  # orange
    "a_signer":   ("#FDECEC", "#E0342B"),  # rouge
    "a_renvoyer": ("#FDECEC", "#E0342B"),  # rouge
}


#  thème (pipé de l'app interne) 
BLEU = "#2F6BFF"
TEXTE = "#1B2559"
MUET = "#8A94A6"
BORDURE = "#E6E9F0"
FOND = "#F5F6F8"

# Feuille de style globale 
STYLE = f"""
QWidget {{ background: {FOND}; color: {TEXTE}; font-size: 14px; }}
QScrollArea {{ border: none; }}

#titre {{ font-size: 24px; font-weight: bold; color: {TEXTE}; }}

/* Carte d'un mail */
#carteMail {{
    background: white;
    border: 1px solid {BORDURE};
    border-radius: 14px;
}}
#expediteurNom {{ font-size: 16px; font-weight: bold; color: {TEXTE}; }}
#expediteurMail {{ font-size: 13px; color: {BLEU}; }}
#objet {{ font-size: 15px; font-weight: 600; color: {TEXTE}; }}
#date {{ font-size: 13px; color: {MUET}; }}
#avatar {{
    background: #EAF0FE;
    color: {BLEU};
    border-radius: 21px;
    font-size: 17px;
    font-weight: bold;
}}

/* Carte d'un document (bordurée) */
#carteDoc {{
    background: white;
    border: 1px solid {BORDURE};
    border-radius: 12px;
}}
#nomFichier {{ font-size: 15px; font-weight: bold; color: {TEXTE}; }}
#projet {{ font-size: 14px; font-weight: bold; color: {BLEU}; }}

/* Pastilles (type, score) */
QLabel[pastille="true"] {{
    border-radius: 10px;
    padding: 3px 10px;
    font-size: 12px;
    font-weight: bold;
}}

/* Boutons */
QPushButton {{
    background: #EEF2FB;
    color: {BLEU};
    border: none;
    border-radius: 10px;
    padding: 8px 14px;
    font-weight: bold;
}}
QPushButton:hover {{ background: #E1E9Fb; }}
QPushButton#primaire {{ background: {BLEU}; color: white; }}
QPushButton#primaire:hover {{ background: #2559d8; }}

/* Menu déroulant du statut */
QComboBox {{
    background: white;
    border: 1px solid {BORDURE};
    border-radius: 10px;
    padding: 6px 12px;
    min-width: 130px;
    font-weight: bold;
}}
QComboBox::drop-down {{ border: none; width: 22px; }}
QComboBox QAbstractItemView {{
    background: white;
    border: 1px solid {BORDURE};
    selection-background-color: #EEF2FB;
    selection-color: {TEXTE};
}}
"""


# Pastille colorée du score de confiance.
def _pastille_score(score):
    if score is None:
        bg, fg, txt = "#EEF0F4", MUET, "—"
    elif score >= 0.8:
        bg, fg, txt = "#E6F7EC", "#1B9E52", f"{score:.2f}"
    elif score >= 0.5:
        bg, fg, txt = "#FFF4E5", "#E08600", f"{score:.2f}"
    else:
        bg, fg, txt = "#FDECEC", "#E0342B", f"{score:.2f}"
    p = QLabel(f"score {txt}")
    p.setProperty("pastille", "true")
    p.setStyleSheet(f"background:{bg}; color:{fg};")
    return p


# Pastille du type de document.
def _pastille_type(type_doc):
    p = QLabel(type_doc or "?")
    p.setProperty("pastille", "true")
    p.setStyleSheet(f"background:#EEF2FB; color:{BLEU};")
    return p


class FenetrePrincipale(QMainWindow):

    def __init__(self):
        super().__init__()
        self.setWindowTitle("Assistant de gestion documentaire")
        self.resize(1000, 720)
        self.setStyleSheet(STYLE)

        # En-tête : titre + bouton rafraîchir.
        entete = QWidget()
        h = QHBoxLayout(entete)
        h.setContentsMargins(24, 20, 24, 8)
        titre = QLabel("Documents reçus")
        titre.setObjectName("titre")
        refresh = QPushButton("↻ Rafraîchir")
        refresh.clicked.connect(self.rafraichir)
        h.addWidget(titre)
        h.addStretch()
        h.addWidget(refresh)

        # Zone défilable contenant la liste des mails.
        zone = QScrollArea()
        zone.setWidgetResizable(True)
        self.conteneur = QWidget()
        self.liste = QVBoxLayout(self.conteneur)
        self.liste.setContentsMargins(24, 8, 24, 24)
        self.liste.setSpacing(16)
        self.liste.setAlignment(Qt.AlignTop)
        zone.setWidget(self.conteneur)

        centre = QWidget()
        v = QVBoxLayout(centre)
        v.setContentsMargins(0, 0, 0, 0)
        v.addWidget(entete)
        v.addWidget(zone)
        self.setCentralWidget(centre)

        self.rafraichir()

    # Vide et reconstruit la liste depuis la base (repository.lister_mails).
    def rafraichir(self):
        while self.liste.count():
            item = self.liste.takeAt(0)
            if item.widget():
                item.widget().deleteLater()

        mails = lister_mails()
        if not mails:
            vide = QLabel("Aucun document. Lance le pipeline pour en récupérer.")
            vide.setStyleSheet(f"color:{MUET};")
            self.liste.addWidget(vide)
            return

        for mail in mails:
            self.liste.addWidget(self._carte_mail(mail))

    # Une carte par mail : en-tête (expéditeur + email + objet) puis ses documents.
    def _carte_mail(self, mail):
        carte = QFrame()
        carte.setObjectName("carteMail")
        # Ombre portée -> chaque mail se détache nettement des autres.
        ombre = QGraphicsDropShadowEffect()
        ombre.setBlurRadius(18)
        ombre.setXOffset(0)
        ombre.setYOffset(4)
        ombre.setColor(QColor(0, 0, 0, 30))
        carte.setGraphicsEffect(ombre)

        col = QVBoxLayout(carte)
        col.setContentsMargins(18, 16, 18, 16)
        col.setSpacing(12)

        # En-tête horizontal : [avatar] [expéditeur]  [objet]  [date].
        entete = QHBoxLayout()
        entete.setSpacing(12)
        entete.addWidget(self._avatar(mail), alignment=Qt.AlignTop)

        # Bloc expéditeur (nom + email, ou email seul).
        bloc = QVBoxLayout()
        bloc.setSpacing(2)
        nom_txt = mail.get("expediteur_nom")
        email_txt = mail.get("expediteur") or ""
        if nom_txt:
            nom = QLabel(nom_txt)
            nom.setObjectName("expediteurNom")
            bloc.addWidget(nom)
            if email_txt:
                email = QLabel(email_txt)
                email.setObjectName("expediteurMail")
                bloc.addWidget(email)
        else:
            principal = QLabel(email_txt or "Expéditeur inconnu")
            principal.setObjectName("expediteurNom")
            bloc.addWidget(principal)
        entete.addLayout(bloc)

        # Objet, à côté de l'expéditeur, bien visible.
        objet = QLabel(mail.get("objet") or "(sans objet)")
        objet.setObjectName("objet")
        objet.setWordWrap(True)
        entete.addSpacing(20)
        entete.addWidget(objet, stretch=1)

        # Date de réception, à droite.
        date = QLabel(self._format_date(mail.get("date_mail")))
        date.setObjectName("date")
        entete.addWidget(date, alignment=Qt.AlignTop)

        col.addLayout(entete)

        # Ligne de séparation entre l'en-tête et les documents.
        sep = QFrame()
        sep.setFixedHeight(1)
        sep.setStyleSheet(f"background:{BORDURE}; border:none;")
        col.addWidget(sep)

        for doc in mail["documents"]:
            col.addWidget(self._carte_document(doc, mail.get("objet") or ""))
        return carte

    # Petit avatar rond avec l'initiale de l'expéditeur (aide à distinguer les mails).
    def _avatar(self, mail):
        source = (mail.get("expediteur_nom") or mail.get("expediteur") or "?").strip()
        a = QLabel(source[0].upper() if source else "?")
        a.setObjectName("avatar")
        a.setFixedSize(42, 42)
        a.setAlignment(Qt.AlignCenter)
        return a

    # Une carte bordurée par document : nom, score, dossier (select), statut, actions.
    def _carte_document(self, doc, objet_mail=""):
        carte = QFrame()
        carte.setObjectName("carteDoc")
        col = QVBoxLayout(carte)
        col.setContentsMargins(16, 12, 16, 12)
        col.setSpacing(10)

        # Ligne 1 : nom du fichier + pastille score.
        l1 = QHBoxLayout()
        nom = QLabel(doc["nom_fichier"])
        nom.setObjectName("nomFichier")
        l1.addWidget(nom)
        l1.addStretch()
        l1.addWidget(_pastille_score(doc.get("score_confiance")))
        col.addLayout(l1)

        # Ligne 2 : sélecteur du dossier Nextcloud de destination.
        # - plusieurs candidats -> menu de choix ; un seul -> présélectionné ;
        # - aucun -> une seule entrée « Créer : <nom généré> ».
        l2 = QHBoxLayout()
        l2.addWidget(QLabel("Dossier :"))
        combo_dossier = QComboBox()
        candidats = doc.get("dossiers_candidats") or []
        if candidats:
            for c in candidats:
                combo_dossier.addItem(c["nom"], userData=c["chemin"])
        else:
            nom_genere = generer_nom_dossier(objet_mail, doc["nom_fichier"])
            combo_dossier.addItem(f"➕ Créer : {nom_genere}",
                                  userData=("__create__", nom_genere))
        l2.addWidget(combo_dossier, stretch=1)
        col.addLayout(l2)

        # Ligne 3 : statut (select) + boutons + bouton Classé (= dépôt Nextcloud).
        l3 = QHBoxLayout()

        combo = QComboBox()
        for cle, libelle in STATUTS:
            combo.addItem(libelle, userData=cle)
        idx = combo.findData(doc["statut"])
        if idx >= 0:
            combo.setCurrentIndex(idx)
        self._appliquer_couleur_statut(combo, doc["statut"])
        combo.activated.connect(lambda _=0, d=doc, c=combo: self._statut_change(d, c))

        b_apercu = QPushButton("👁 Aperçu")
        b_apercu.clicked.connect(lambda _=0, d=doc: self._apercu(d))
        b_tele = QPushButton("⬇ Télécharger")
        b_tele.clicked.connect(lambda _=0, d=doc: self._telecharger(d))
        b_classe = QPushButton("✔ Classé")
        b_classe.setObjectName("primaire")
        b_classe.clicked.connect(lambda _=0, d=doc, c=combo_dossier: self._classer(d, c))

        l3.addStretch()
        l3.addWidget(combo)
        l3.addWidget(b_apercu)
        l3.addWidget(b_tele)
        l3.addWidget(b_classe)
        col.addLayout(l3)

        return carte

    # Applique au select la couleur correspondant au statut.
    def _appliquer_couleur_statut(self, combo, statut):
        bg, fg = COULEURS_STATUT.get(statut, ("white", TEXTE))
        combo.setStyleSheet(f"QComboBox {{ background:{bg}; color:{fg}; }}")

    # Le menu déroulant a changé -> on enregistre le nouveau statut dans la base.
    def _statut_change(self, doc, combo):
        statut = combo.currentData()
        changer_statut(doc["id"], statut)
        self._appliquer_couleur_statut(combo, statut)
    

    # Bouton "Classé" : dépose le document dans le dossier choisi (le crée si besoin),
    # puis enregistre le classement en base (statut="classe" + chemin distant).
    def _classer(self, doc, combo_dossier):
        chemin_local = doc.get("chemin_local")
        if not chemin_local or not Path(chemin_local).exists():
            QMessageBox.warning(self, "Classé", "Fichier introuvable sur le disque.")
            return

        data = combo_dossier.currentData()
        try:
            # Cas "aucun candidat" : on crée le dossier au même endroit que les autres.
            if isinstance(data, tuple) and data and data[0] == "__create__":
                dossier = creer_dossier(settings.base_remote_path, data[1])
            else:
                dossier = data  # chemin du dossier candidat choisi

            chemin_distant = deposer_document(chemin_local, dossier)
            changer_statut(doc["id"], "classe", chemin_nextcloud=chemin_distant)
            QMessageBox.information(self, "Classé", f"Document déposé dans :\n{dossier}")
            self.rafraichir()
        except Exception as e:
            QMessageBox.critical(self, "Erreur de dépôt", f"{type(e).__name__}: {e}")
        

    # Formate la date de réception du mail (ISO -> "JJ/MM/AAAA HH:MM").
    def _format_date(self, iso):
        if not iso:
            return ""
        try:
            from datetime import datetime
            return datetime.fromisoformat(iso).strftime("%d/%m/%Y %H:%M")
        except Exception:
            return str(iso)[:16].replace("T", " ")

    # 👁 Aperçu : ouvre le fichier avec l'application par défaut du système.
    def _apercu(self, doc):
        chemin = doc.get("chemin_local")
        if not chemin or not Path(chemin).exists():
            QMessageBox.warning(self, "Aperçu", "Fichier introuvable sur le disque.")
            return
        QDesktopServices.openUrl(QUrl.fromLocalFile(str(Path(chemin).resolve())))

    # ⬇ Télécharger : copie le fichier vers l'emplacement choisi.
    def _telecharger(self, doc):
        chemin = doc.get("chemin_local")
        if not chemin or not Path(chemin).exists():
            QMessageBox.warning(self, "Télécharger", "Fichier introuvable sur le disque.")
            return
        cible, _ = QFileDialog.getSaveFileName(self, "Enregistrer sous", doc["nom_fichier"])
        if cible:
            shutil.copy(chemin, cible)
            QMessageBox.information(self, "Télécharger", "Fichier enregistré.")


def main():
    init_db()
    app = QApplication(sys.argv)
    app.setFont(QFont("Segoe UI", 10))
    fenetre = FenetrePrincipale()
    fenetre.show()
    sys.exit(app.exec())


if __name__ == "__main__":
    main()
