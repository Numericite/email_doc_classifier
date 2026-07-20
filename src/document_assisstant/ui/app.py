import sys
import shutil
from pathlib import Path

from PySide6.QtWidgets import (
    QApplication, QMainWindow, QWidget, QScrollArea, QFrame,
    QVBoxLayout, QHBoxLayout, QLabel, QPushButton, QComboBox, QLineEdit,
    QFileDialog, QMessageBox, QGraphicsDropShadowEffect,
)
from PySide6.QtGui import QDesktopServices, QFont, QColor
from PySide6.QtCore import QUrl, Qt

from config.settings import settings
from databases.repository import init_db, lister_mails, changer_statut
from nextcloud.depot import deposer_document, creer_dossier
from ricobot.lister_projet_ricot import lister_projets
from ricobot.remplissage_bdc import remplir_bdc


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

/* Carte d'un mail : blanche sur fond gris + liseré bleu à gauche, pour que
   chaque mail se détache nettement du suivant. */
#carteMail {{
    background: white;
    border: 1px solid {BORDURE};
    border-left: 4px solid {BLEU};
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

/* Carte d'un document : gris léger, pour se détacher du blanc de la carte mail
   dans laquelle elle est imbriquée. */
#carteDoc {{
    background: {FOND};
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

        # Missions Ricobot : chargées une fois, pour le sélecteur des bons de
        # commande (permet à l'utilisateur de corriger le projet si le LLM se trompe).
        try:
            self.projets_ricobot = lister_projets()
        except Exception as e:
            print(f"[!] Missions Ricobot indisponibles : {e}")
            self.projets_ricobot = []

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
        self.liste.setSpacing(24)
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
            col.addWidget(self._carte_document(
                doc, mail.get("objet") or "", mail.get("date_mail")))
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
    def _carte_document(self, doc, objet_mail="", date_mail=None):
        carte = QFrame()
        carte.setObjectName("carteDoc")
        col = QVBoxLayout(carte)
        col.setContentsMargins(16, 12, 16, 12)
        col.setSpacing(10)

        # Ligne 1 : nom du fichier + type de document juste à sa droite,
        # puis le score poussé à l'extrémité droite.
        l1 = QHBoxLayout()
        nom = QLabel(doc["nom_fichier"])
        nom.setObjectName("nomFichier")
        l1.addWidget(nom)
        l1.addWidget(_pastille_type(doc.get("type_document")))
        l1.addStretch()
        l1.addWidget(_pastille_score(doc.get("score_confiance")))
        col.addLayout(l1)

        # Ligne 2 : destination Nextcloud.
        # - des candidats -> menu de choix (le plus pertinent en premier) ;
        # - aucun candidat -> champ de saisie du nom du dossier à créer.
        l2 = QHBoxLayout()
        combo_dossier = QComboBox()
        champ_nom = None
        candidats = doc.get("dossiers_candidats") or []
        if candidats:
            l2.addWidget(QLabel("Dossier :"))
            for c in candidats:
                combo_dossier.addItem(c["nom"], userData=c["chemin"])
            l2.addWidget(combo_dossier, stretch=1)
        else:
            l2.addWidget(QLabel("➕ Créer un nouveau dossier:"))
            champ_nom = QLineEdit("Insérer un nom de dossier pour classser ce document")
            champ_nom.setPlaceholderText(
                f"Nom du dossier à créer dans « {settings.base_remote_path} »")
            l2.addWidget(champ_nom, stretch=1)
        col.addLayout(l2)

        # Bloc BON DE COMMANDE : projet Ricobot (corrigeable) + champs extraits.
        # Affiché uniquement pour les bons de commande.
        champs_bdc = None
        if doc.get("type_document") == "bon_de_commande":
            champs_bdc = self._bloc_bdc(col, doc.get("bdc_ricobot") or {}, date_mail)

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
        b_classe = QPushButton("✔ Classer")
        b_classe.setObjectName("primaire")
        b_classe.clicked.connect(
            lambda _=0, d=doc, c=combo_dossier, ch=champ_nom: self._classer(d, c, ch))

        l3.addStretch()
        l3.addWidget(combo)
        l3.addWidget(b_apercu)
        l3.addWidget(b_tele)
        if champs_bdc is not None:
            b_bdc = QPushButton("🧾 Remplir BDC")
            b_bdc.setObjectName("primaire")
            b_bdc.clicked.connect(
                lambda _=0, d=doc, ch=champs_bdc: self._remplir_bdc(d, ch))
            l3.addWidget(b_bdc)
        l3.addWidget(b_classe)
        col.addLayout(l3)

        return carte

    # Bloc d'un bon de commande : sélecteur de mission Ricobot (pré-positionné sur
    # la proposition du LLM, mais modifiable) + champs extraits éditables.
    # Renvoie les widgets pour que le bouton « Remplir BDC » les relise.
    def _bloc_bdc(self, col, bdc, date_mail=None):
        # Ligne : mission Ricobot (toutes les missions, pour corriger le LLM).
        ligne_mission = QHBoxLayout()
        ligne_mission.addWidget(QLabel("🧾 Projet Ricobot :"))
        combo_mission = QComboBox()
        for p in self.projets_ricobot:
            combo_mission.addItem(f"{p['nom']} — {p['company']}", userData=p["id"])
        # Pré-sélection : 1re mission proposée par le LLM, si elle existe.
        proposes = bdc.get("mission_ids") or []
        if proposes:
            idx = combo_mission.findData(proposes[0])
            if idx >= 0:
                combo_mission.setCurrentIndex(idx)
        ligne_mission.addWidget(combo_mission, stretch=1)
        col.addLayout(ligne_mission)

        # Ligne : les 3 champs importants — début (= réception mail), fin, montant.
        ligne_champs = QHBoxLayout()
        champ_debut = QLineEdit(str(date_mail)[:10] if date_mail else "")
        champ_debut.setPlaceholderText("Début (AAAA-MM-JJ)")
        champ_fin = QLineEdit(bdc.get("end_date") or "")
        champ_fin.setPlaceholderText("Fin (AAAA-MM-JJ)")
        montant = bdc.get("amount")
        champ_montant = QLineEdit("" if montant in (None, 0) else str(montant))
        champ_montant.setPlaceholderText("Montant")
        for lib, w in (("Début", champ_debut), ("Fin", champ_fin), ("Montant", champ_montant)):
            ligne_champs.addWidget(QLabel(lib + " :"))
            ligne_champs.addWidget(w)
        col.addLayout(ligne_champs)

        return {
            "combo_mission": combo_mission,
            # abréviation + référence : gardées pour l'API mais non affichées.
            "abbreviation": bdc.get("abbreviation") or "",
            "reference": bdc.get("reference") or "",
            "start_date": champ_debut,
            "end_date": champ_fin,
            "amount": champ_montant,
        }

    # Bouton « Remplir BDC » : envoie le bon de commande à Ricobot pour la mission
    # retenue (celle du LLM ou celle choisie par l'utilisateur).
    def _remplir_bdc(self, doc, champs):
        mission_id = champs["combo_mission"].currentData()
        if mission_id is None:
            QMessageBox.warning(self, "Remplir BDC", "Aucune mission Ricobot sélectionnée.")
            return
        # Montant : texte -> nombre (tolère virgule, espaces, symbole €).
        brut = champs["amount"].text().replace("€", "").replace(",", ".").replace(" ", "")
        try:
            amount = float(brut) if brut else 0
        except ValueError:
            amount = 0
        try:
            remplir_bdc(
                mission_id,
                abbreviation=champs["abbreviation"],
                reference=champs["reference"],
                start_date=champs["start_date"].text().strip(),
                end_date=champs["end_date"].text().strip(),
                amount=amount,
            )
            QMessageBox.information(self, "Remplir BDC",
                                    "Bon de commande envoyé à Ricobot.")
        except Exception as e:
            QMessageBox.critical(self, "Erreur Ricobot", f"{type(e).__name__}: {e}")

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
    def _classer(self, doc, combo_dossier, champ_nom=None):
        chemin_local = doc.get("chemin_local")
        if not chemin_local or not Path(chemin_local).exists():
            QMessageBox.warning(self, "Classé", "Fichier introuvable sur le disque.")
            return

        # Aucun candidat : le nom saisi par l'utilisateur fait foi.
        nom_saisi = champ_nom.text().strip() if champ_nom is not None else ""
        if champ_nom is not None and not nom_saisi:
            QMessageBox.warning(self, "Classé", "Donne un nom au dossier à créer.")
            return

        try:
            if champ_nom is not None:
                dossier = creer_dossier(settings.base_remote_path, nom_saisi)
            else:
                dossier = combo_dossier.currentData()  # chemin du candidat choisi

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
