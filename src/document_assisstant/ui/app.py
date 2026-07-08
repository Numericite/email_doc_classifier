import sys
import shutil
from pathlib import Path

from PySide6.QtWidgets import (
    QApplication, QMainWindow, QWidget, QScrollArea, QGroupBox, QFrame,
    QVBoxLayout, QHBoxLayout, QLabel, QPushButton, QFileDialog, QMessageBox,
)
from PySide6.QtGui import QDesktopServices
from PySide6.QtCore import QUrl, Qt

from databases.repository import init_db, lister_mails, changer_statut


# statut interne -> libellé affiché
STATUTS = {
    "en_attente": "En attente",
    "a_signer": "À signer",
    "a_renvoyer": "À renvoyer",
    "classe": "Classé",
}


# Couleur du score de confiance : vert (sûr) / orange (à vérifier) / rouge (douteux).
def _couleur_score(score):
    if score is None:
        return "gray"
    if score >= 0.8:
        return "green"
    if score >= 0.5:
        return "orange"
    return "red"


class FenetrePrincipale(QMainWindow):

    def __init__(self):
        super().__init__()
        self.setWindowTitle("Assistant de gestion documentaire")
        self.resize(900, 700)

        # Zone défilable qui contiendra la liste des mails.
        zone = QScrollArea()
        zone.setWidgetResizable(True)
        self.conteneur = QWidget()
        self.liste = QVBoxLayout(self.conteneur)
        self.liste.setAlignment(Qt.AlignTop)
        zone.setWidget(self.conteneur)

        # Barre du haut : un bouton pour recharger depuis la base.
        haut = QWidget()
        h = QHBoxLayout(haut)
        titre = QLabel("Documents reçus")
        titre.setStyleSheet("font-size: 18px; font-weight: bold;")
        bouton_refresh = QPushButton("↻ Rafraîchir")
        bouton_refresh.clicked.connect(self.rafraichir)
        h.addWidget(titre)
        h.addStretch()
        h.addWidget(bouton_refresh)

        centre = QWidget()
        v = QVBoxLayout(centre)
        v.addWidget(haut)
        v.addWidget(zone)
        self.setCentralWidget(centre)

        self.rafraichir()

    # Vide la liste et la reconstruit à partir de la base (repository.lister_mails).
    def rafraichir(self):
        while self.liste.count():
            item = self.liste.takeAt(0)
            if item.widget():
                item.widget().deleteLater()

        mails = lister_mails()
        if not mails:
            self.liste.addWidget(QLabel("Aucun document. Lance le pipeline pour en récupérer."))
            return

        for mail in mails:
            self.liste.addWidget(self._carte_mail(mail))

    # Un mail = un cadre avec son en-tête (expéditeur + objet) et ses documents.
    def _carte_mail(self, mail):
        titre = f"{mail.get('expediteur_nom') or ''} <{mail.get('expediteur') or ''}> — {mail.get('objet') or '(sans objet)'}"
        boite = QGroupBox(titre)
        col = QVBoxLayout(boite)
        for doc in mail["documents"]:
            col.addWidget(self._ligne_document(doc))
        return boite

    # Une ligne = un document avec ses infos et ses boutons d'action.
    def _ligne_document(self, doc):
        cadre = QFrame()
        cadre.setFrameShape(QFrame.StyledPanel)
        ligne = QHBoxLayout(cadre)

        # Infos : nom, type, score (coloré), projet proposé.
        score = doc.get("score_confiance")
        infos = QLabel(
            f"<b>{doc['nom_fichier']}</b>  [{doc.get('type_document') or '?'}]  "
            f"<span style='color:{_couleur_score(score)}'>score {score}</span><br>"
            f"→ {doc.get('projet_nom') or '(aucun projet)'}"
        )
        infos.setTextFormat(Qt.RichText)
        ligne.addWidget(infos, stretch=1)

        # Statut courant.
        statut = QLabel(STATUTS.get(doc["statut"], doc["statut"]))
        statut.setStyleSheet("font-weight: bold;")
        ligne.addWidget(statut)

        # Boutons d'action.
        b_apercu = QPushButton("👁 Aperçu")
        b_apercu.clicked.connect(lambda: self._apercu(doc))
        b_tele = QPushButton("⬇ Télécharger")
        b_tele.clicked.connect(lambda: self._telecharger(doc))
        b_valider = QPushButton("✔ Valider")
        b_valider.clicked.connect(lambda: self._valider(doc))
        b_renvoyer = QPushButton("↩ À renvoyer")
        b_renvoyer.clicked.connect(lambda: self._changer(doc, "a_renvoyer"))
        b_signer = QPushButton("✍ À signer")
        b_signer.clicked.connect(lambda: self._changer(doc, "a_signer"))
        for b in (b_apercu, b_tele, b_valider, b_renvoyer, b_signer):
            ligne.addWidget(b)

        return cadre

    # 👁 Aperçu : ouvre le fichier avec l'application par défaut du système (approche A).
    def _apercu(self, doc):
        chemin = doc.get("chemin_local")
        if not chemin or not Path(chemin).exists():
            QMessageBox.warning(self, "Aperçu", "Fichier introuvable sur le disque.")
            return
        QDesktopServices.openUrl(QUrl.fromLocalFile(str(Path(chemin).resolve())))

    # ⬇ Télécharger : copie le fichier vers l'emplacement choisi par l'utilisateur.
    def _telecharger(self, doc):
        chemin = doc.get("chemin_local")
        if not chemin or not Path(chemin).exists():
            QMessageBox.warning(self, "Télécharger", "Fichier introuvable sur le disque.")
            return
        cible, _ = QFileDialog.getSaveFileName(self, "Enregistrer sous", doc["nom_fichier"])
        if cible:
            shutil.copy(chemin, cible)
            QMessageBox.information(self, "Télécharger", "Fichier enregistré.")

    # ✔ Valider : pour l'instant, passe le statut à "classé" dans la base.
    # Le dépôt réel dans Nextcloud sera branché ici quand le module nextcloud/ (§9) sera prêt.
    def _valider(self, doc):
        changer_statut(doc["id"], "classe")
        QMessageBox.information(
            self, "Valider",
            "Document marqué « classé ».\n(Le dépôt automatique dans Nextcloud sera ajouté en §9.)"
        )
        self.rafraichir()

    # Change le statut (À renvoyer / À signer) puis recharge l'affichage.
    def _changer(self, doc, statut):
        changer_statut(doc["id"], statut)
        self.rafraichir()


def main():
    init_db()  # au cas où la base n'existe pas encore
    app = QApplication(sys.argv)
    fenetre = FenetrePrincipale()
    fenetre.show()
    sys.exit(app.exec())


if __name__ == "__main__":
    main()
