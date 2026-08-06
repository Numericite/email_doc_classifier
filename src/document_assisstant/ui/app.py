import sys
import html
import shutil
import tempfile
from pathlib import Path

from PySide6.QtWidgets import (
    QApplication, QMainWindow, QWidget, QScrollArea, QFrame,
    QVBoxLayout, QHBoxLayout, QLabel, QPushButton, QComboBox, QLineEdit,
    QFileDialog, QMessageBox, QGraphicsDropShadowEffect, QCompleter,
    QDialog, QFormLayout, QDialogButtonBox,
)
from PySide6.QtGui import QDesktopServices, QFont, QColor
from PySide6.QtCore import QUrl, Qt

from config.settings import settings
from databases.repository import (
    init_db, lister_mails, changer_statut, maj_bdc_ricobot, supprimer_mail,
)
from nextcloud.depot import deposer_document, creer_dossier, telecharger_document
from nextcloud.lister_dossiers import lister_dossiers
from ricobot.lister_projet_ricot import lister_projets
from ricobot.remplissage_bdc import remplir_bdc


# Statuts, dans l'ordre du menu : (clé interne, libellé affiché).
STATUTS = [
    ("en_attente", "En attente"),
    ("a_signer", "À signer"),
    ("a_renvoyer", "À renvoyer"),
    ("classe", "Classé"),
]

# Couleur du menu de statut : (fond, texte).
COULEURS_STATUT = {
    "classe":     ("#E6F7EC", "#1B9E52"),  # vert
    "en_attente": ("#FFF4E5", "#E08600"),  # orange
    "a_signer":   ("#FDECEC", "#E0342B"),  # rouge
    "a_renvoyer": ("#FDECEC", "#E0342B"),  # rouge
}


# Palette du thème.
BLEU = "#2F6BFF"
TEXTE = "#1B2559"
MUET = "#8A94A6"
BORDURE = "#E6E9F0"
FOND = "#F5F6F8"

# Feuille de style globale (Qt Style Sheet).
STYLE = f"""
QWidget {{ background: {FOND}; color: {TEXTE}; font-size: 14px; }}
QScrollArea {{ border: none; }}

#titre {{ font-size: 24px; font-weight: bold; color: {TEXTE}; }}

#boiteRecherche {{
    background: white;
    border: 1px solid {BORDURE};
    border-radius: 10px;
}}

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

#carteDoc {{
    background: {FOND};
    border: 1px solid {BORDURE};
    border-radius: 12px;
}}
#nomFichier {{ font-size: 15px; font-weight: bold; color: {TEXTE}; }}
#projet {{ font-size: 14px; font-weight: bold; color: {BLEU}; }}

QLabel[pastille="true"] {{
    border-radius: 10px;
    padding: 3px 10px;
    font-size: 12px;
    font-weight: bold;
}}

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


# Combo qui ignore la molette : évite de changer sa valeur en scrollant la page.
class ComboSansScroll(QComboBox):
    def wheelEvent(self, event):
        event.ignore()


class FenetrePrincipale(QMainWindow):

    def __init__(self):
        super().__init__()
        self.setWindowTitle("Assistant de gestion documentaire")
        self.resize(1000, 720)
        self.setStyleSheet(STYLE)

        # Missions Ricobot, chargées une fois (sélecteur des bons de commande).
        try:
            self.projets_ricobot = lister_projets()
        except Exception as e:
            print(f"[!] Missions Ricobot indisponibles : {e}")
            self.projets_ricobot = []

        # Dossiers Nextcloud, chargés une fois (champ recherchable de destination).
        try:
            self.dossiers_nextcloud = lister_dossiers(settings.base_remote_path)
        except Exception as e:
            print(f"[!] Dossiers Nextcloud indisponibles : {e}")
            self.dossiers_nextcloud = []
        # Index nom -> chemin, pour retrouver le dossier choisi.
        self._dossiers_par_nom = {d["nom"]: d["chemin"] for d in self.dossiers_nextcloud}

        # Dossier créé par mail (mail_id -> nom) : réutilisé par les documents suivants.
        self._dossier_mail = {}

        # État du filtre par statut (None = tous).
        self._filtre_statut = None
        self._boutons_filtre = {}

        # Texte de la recherche (vide = aucun filtre texte).
        self._recherche = ""

        # En-tête : titre + rafraîchir.
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

        # Zone défilable qui contient les mails.
        zone = QScrollArea()
        zone.setWidgetResizable(True)
        self.conteneur = QWidget()
        self.liste = QVBoxLayout(self.conteneur)
        self.liste.setContentsMargins(24, 8, 24, 24)
        self.liste.setSpacing(24)
        self.liste.setAlignment(Qt.AlignTop)
        zone.setWidget(self.conteneur)

        # Ligne unique : recherche (loupe + champ) à gauche, puis les filtres.
        barre = QWidget()
        bf = QHBoxLayout(barre)
        bf.setContentsMargins(24, 0, 24, 8)
        bf.setSpacing(10)

        # Boîte de recherche : loupe (Segoe MDL2 Assets) + champ sans bordure.
        loupe = QLabel(chr(0xE721))   # U+E721 = loupe
        loupe.setStyleSheet(
            f"font-family:'Segoe MDL2 Assets'; color:{MUET}; font-size:14px;")
        recherche = QLineEdit()
        recherche.setPlaceholderText("Rechercher…")
        recherche.setClearButtonEnabled(True)
        recherche.setFrame(False)
        recherche.setStyleSheet("background:transparent; border:none;")
        recherche.textChanged.connect(self._rechercher)
        boite = QFrame()
        boite.setObjectName("boiteRecherche")
        boite.setMinimumWidth(300)
        hb = QHBoxLayout(boite)
        hb.setContentsMargins(12, 4, 12, 4)
        hb.setSpacing(8)
        hb.addWidget(loupe)
        hb.addWidget(recherche)
        bf.addWidget(boite)

        # Filtres par statut.
        etiquette = QLabel("Filtrer :")
        etiquette.setStyleSheet(f"color:{MUET};")
        bf.addWidget(etiquette)
        for cle, libelle in [(None, "Tous"), *STATUTS]:
            b = QPushButton(libelle)
            b.clicked.connect(lambda _=0, c=cle: self._appliquer_filtre(c))
            self._boutons_filtre[cle] = b
            bf.addWidget(b)
        bf.addStretch()

        centre = QWidget()
        v = QVBoxLayout(centre)
        v.setContentsMargins(0, 0, 0, 0)
        v.addWidget(entete)
        v.addWidget(barre)
        v.addWidget(zone)
        self.setCentralWidget(centre)

        # Affiche tout au démarrage ("Tous" actif).
        self._appliquer_filtre(None)

    # Vide et reconstruit la liste depuis la base.
    def rafraichir(self):
        while self.liste.count():
            item = self.liste.takeAt(0)
            if item.widget():
                item.widget().deleteLater()

        mails = lister_mails(self._filtre_statut)
        if self._recherche:
            mails = [m for m in mails if self._mail_correspond(m)]
        if not mails:
            if self._recherche:
                texte = f"Aucun résultat pour « {self._recherche} »."
            else:
                libelle = dict(STATUTS).get(self._filtre_statut)
                texte = (f"Aucun document « {libelle} »." if libelle
                         else "Aucun document. Lance le pipeline pour en récupérer.")
            vide = QLabel(texte)
            vide.setStyleSheet(f"color:{MUET};")
            self.liste.addWidget(vide)
            return

        for mail in mails:
            self.liste.addWidget(self._carte_mail(mail))

    # Applique un filtre par statut et met la barre à jour.
    def _appliquer_filtre(self, statut):
        self._filtre_statut = statut
        for cle, bouton in self._boutons_filtre.items():
            actif = (cle == statut)
            bouton.setStyleSheet(f"background:{BLEU}; color:white;" if actif else "")
        self.rafraichir()

    # Recherche : mémorise le texte et rafraîchit.
    def _rechercher(self, texte):
        self._recherche = texte.strip().lower()
        self.rafraichir()

    # True si le texte cherché apparaît dans un champ du mail ou de ses documents.
    def _mail_correspond(self, mail):
        q = self._recherche
        champs = [mail.get("expediteur"), mail.get("expediteur_nom"), mail.get("objet")]
        for d in mail["documents"]:
            champs.append(d.get("nom_fichier"))
            champs.append(d.get("projet_nom"))
        return any(q in (c or "").lower() for c in champs)

    # Corbeille : supprime un mail et ses documents (les fichiers Nextcloud sont conservés).
    def _supprimer_mail(self, mail):
        nb = len(mail["documents"])
        rep = QMessageBox.question(
            self, "Supprimer",
            f"Supprimer ce mail et ses {nb} document(s) de la liste ?\n"
            "(Les fichiers déjà déposés dans Nextcloud ne sont pas supprimés.)")
        if rep != QMessageBox.StandardButton.Yes:
            return

        for d in mail["documents"]:                 # nettoie les copies locales restantes
            chemin = d.get("chemin_local")
            if chemin and Path(chemin).exists():
                try:
                    Path(chemin).unlink()
                except OSError as e:
                    print(f"[!] Copie locale non supprimée ({chemin}) : {e}")

        supprimer_mail(mail["id"])
        self.rafraichir()

    # Une carte par mail : en-tête (expéditeur + objet + date + corbeille) puis ses documents.
    def _carte_mail(self, mail):
        carte = QFrame()
        carte.setObjectName("carteMail")
        # Ombre portée : détache chaque mail du suivant.
        ombre = QGraphicsDropShadowEffect()
        ombre.setBlurRadius(18)
        ombre.setXOffset(0)
        ombre.setYOffset(4)
        ombre.setColor(QColor(0, 0, 0, 30))
        carte.setGraphicsEffect(ombre)

        col = QVBoxLayout(carte)
        col.setContentsMargins(18, 16, 18, 16)
        col.setSpacing(12)

        # En-tête : [avatar] [expéditeur] [objet — date] [corbeille].
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

        # Objet + date (en gras).
        sujet = html.escape(mail.get("objet") or "(sans objet)")
        d = self._format_date(mail.get("date_mail"))
        objet = QLabel(f"{sujet} — <b>{html.escape(d)}</b>" if d else sujet)
        objet.setObjectName("objet")
        objet.setTextFormat(Qt.RichText)
        objet.setWordWrap(True)
        entete.addSpacing(20)
        entete.addWidget(objet, stretch=1)

        # Corbeille rouge (X) à droite.
        poubelle = QPushButton("X")
        poubelle.setToolTip("Supprimer ce mail et ses documents de la liste")
        poubelle.setFixedSize(34, 34)
        poubelle.setStyleSheet(
            "background:#FDECEC; color:#E0342B; border-radius:8px;"
            " font-size:16px; font-weight:bold;")
        poubelle.clicked.connect(lambda _=0, m=mail: self._supprimer_mail(m))
        entete.addWidget(poubelle, alignment=Qt.AlignTop)

        col.addLayout(entete)

        # Séparateur en-tête / documents.
        sep = QFrame()
        sep.setFixedHeight(1)
        sep.setStyleSheet(f"background:{BORDURE}; border:none;")
        col.addWidget(sep)

        # Un mail = un dossier : on agrège les dossiers candidats de tous ses documents.
        candidats_mail, vus = [], set()
        for d in mail["documents"]:
            for c in (d.get("dossiers_candidats") or []):
                if c["chemin"] not in vus:
                    vus.add(c["chemin"])
                    candidats_mail.append(c)

        ligne = QHBoxLayout()
        ligne.addWidget(QLabel("Dossier du mail :"))

        # Champ recherchable : tous les dossiers Nextcloud, proposition IA pré-sélectionnée,
        # ou saisie d'un nouveau nom (créé au dépôt).
        dest_combo = ComboSansScroll()
        dest_combo.setEditable(True)
        dest_combo.setInsertPolicy(QComboBox.InsertPolicy.NoInsert)
        for dossier in self.dossiers_nextcloud:
            dest_combo.addItem(dossier["nom"], userData=dossier["chemin"])
        completer = dest_combo.completer()
        if completer is not None:
            completer.setCompletionMode(QCompleter.CompletionMode.PopupCompletion)
            completer.setFilterMode(Qt.MatchContains)   # recherche "contient"
        dest_combo.setMinimumWidth(360)

        # Valeur par défaut : proposition IA, sinon dossier déjà créé pour ce mail.
        if candidats_mail:
            idx = dest_combo.findData(candidats_mail[0]["chemin"])
            if idx >= 0:
                dest_combo.setCurrentIndex(idx)
            else:
                dest_combo.setEditText(candidats_mail[0]["nom"])
        else:
            dest_combo.setEditText(
                self._dossier_mail.get(mail["id"]) or self._dossier_cree_du_mail(mail))

        ligne.addWidget(dest_combo, stretch=1)

        # Meilleur score parmi les documents du mail.
        scores = [d.get("score_confiance") for d in mail["documents"]
                  if d.get("score_confiance") is not None]
        ligne.addWidget(_pastille_score(max(scores) if scores else None))
        col.addLayout(ligne)

        destination = {"combo": dest_combo}
        for doc in mail["documents"]:
            col.addWidget(self._carte_document(
                doc, mail.get("objet") or "", mail.get("date_mail"), destination))
        return carte

    # Nom du dossier déjà créé pour un mail (retrouvé via le chemin Nextcloud d'un doc classé).
    def _dossier_cree_du_mail(self, mail):
        for d in mail["documents"]:
            chemin = d.get("chemin_nextcloud")
            if chemin:
                dossier = chemin.rsplit("/", 1)[0]      # enlève le nom de fichier
                return dossier.rsplit("/", 1)[-1]        # dernier segment = nom du dossier
        return ""

    # Avatar rond avec l'initiale de l'expéditeur.
    def _avatar(self, mail):
        source = (mail.get("expediteur_nom") or mail.get("expediteur") or "?").strip()
        a = QLabel(source[0].upper() if source else "?")
        a.setObjectName("avatar")
        a.setFixedSize(42, 42)
        a.setAlignment(Qt.AlignCenter)
        return a

    # Une carte par document : nom + type, bloc BDC éventuel, statut et actions.
    def _carte_document(self, doc, objet_mail="", date_mail=None, destination=None):
        carte = QFrame()
        carte.setObjectName("carteDoc")
        col = QVBoxLayout(carte)
        col.setContentsMargins(16, 12, 16, 12)
        col.setSpacing(10)

        # Ligne 1 : nom du fichier + type.
        l1 = QHBoxLayout()
        nom = QLabel(doc["nom_fichier"])
        nom.setObjectName("nomFichier")
        l1.addWidget(nom)
        l1.addWidget(_pastille_type(doc.get("type_document")))
        l1.addStretch()
        col.addLayout(l1)

        # Bloc bon de commande (uniquement pour ce type).
        champs_bdc = None
        if doc.get("type_document") == "bon_de_commande":
            champs_bdc = self._bloc_bdc(col, doc.get("bdc_ricobot") or {}, date_mail, doc)

        # Ligne d'actions : statut + Aperçu / Télécharger / (Remplir BDC) / Classer.
        l3 = QHBoxLayout()

        combo = ComboSansScroll()
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
            lambda _=0, d=doc, dest=destination: self._classer(d, dest))

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

    # Bloc bon de commande : sélecteur de mission Ricobot + crayon d'édition + lien du BDC.
    def _bloc_bdc(self, col, bdc, date_mail, doc):
        ligne = QHBoxLayout()
        ligne.addWidget(QLabel("🧾 Projet Ricobot :"))
        combo_mission = ComboSansScroll()
        for p in self.projets_ricobot:
            combo_mission.addItem(f"{p['nom']} — {p['company']}", userData=p["id"])
        # Pré-sélection : 1re mission proposée par le LLM.
        proposes = bdc.get("mission_ids") or []
        if proposes:
            idx = combo_mission.findData(proposes[0])
            if idx >= 0:
                combo_mission.setCurrentIndex(idx)
        combo_mission.setMaximumWidth(460)
        ligne.addWidget(combo_mission)

        # Valeurs éditables du BDC (date de début = réception du mail par défaut).
        valeurs = {
            "titre": bdc.get("abbreviation") or "",
            "reference": bdc.get("reference") or "",
            "date_debut": bdc.get("date_debut") or (str(date_mail)[:10] if date_mail else ""),
            "date_fin": bdc.get("end_date") or "",
            "mission_ids": bdc.get("mission_ids") or [],
            "missions": bdc.get("missions") or [],
            "confidence": bdc.get("confidence"),
            "order_id": bdc.get("order_id"),      # BDC créé dans Ricobot
            "order_url": bdc.get("order_url"),    # lien vers ce BDC
        }

        b_edit = QPushButton("✏️")
        b_edit.setToolTip("Voir / modifier les informations du bon de commande")
        b_edit.clicked.connect(lambda _=0, d=doc, v=valeurs: self._editer_bdc(d, v))
        ligne.addWidget(b_edit)
        ligne.addStretch()

        # Lien cliquable vers le BDC créé (présent une fois « Remplir BDC » fait).
        url_bdc = bdc.get("order_url")
        if url_bdc:
            lien = QLabel(f'<a href="{url_bdc}">Voir le BDC dans Ricobot ↗</a>')
            lien.setOpenExternalLinks(True)
            lien.setStyleSheet(f"color:{BLEU}; font-weight:bold;")
            ligne.addWidget(lien)

        col.addLayout(ligne)

        return {"combo_mission": combo_mission, "valeurs": valeurs}

    # Crayon : fenêtre d'édition du BDC ; « Valider » enregistre en base (sans envoi Ricobot).
    def _editer_bdc(self, doc, valeurs):
        dlg = QDialog(self)
        dlg.setWindowTitle("Bon de commande")
        dlg.setMinimumWidth(460)
        form = QFormLayout(dlg)
        form.setContentsMargins(20, 20, 20, 20)
        form.setSpacing(12)

        e_titre = QLineEdit(valeurs["titre"])
        e_debut = QLineEdit(valeurs["date_debut"])
        e_debut.setPlaceholderText("AAAA-MM-JJ")
        e_fin = QLineEdit(valeurs["date_fin"])
        e_fin.setPlaceholderText("AAAA-MM-JJ")
        form.addRow("Titre :", e_titre)
        form.addRow("Date de début :", e_debut)
        form.addRow("Date de fin :", e_fin)

        boutons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Save | QDialogButtonBox.StandardButton.Cancel)
        boutons.button(QDialogButtonBox.StandardButton.Save).setText("Valider")
        boutons.accepted.connect(dlg.accept)
        boutons.rejected.connect(dlg.reject)
        form.addRow(boutons)

        if not dlg.exec():
            return

        # Applique en mémoire puis enregistre en base.
        valeurs["titre"] = e_titre.text().strip()
        valeurs["date_debut"] = e_debut.text().strip()
        valeurs["date_fin"] = e_fin.text().strip()
        maj_bdc_ricobot(doc["id"], {
            "mission_ids": valeurs["mission_ids"],
            "missions": valeurs["missions"],
            "abbreviation": valeurs["titre"],
            "reference": valeurs["reference"],
            "date_debut": valeurs["date_debut"],
            "end_date": valeurs["date_fin"],
            "confidence": valeurs["confidence"],
            "order_id": valeurs.get("order_id"),
            "order_url": valeurs.get("order_url"),
        })

    # « Remplir BDC » : crée le bon de commande dans Ricobot et enregistre son lien.
    def _remplir_bdc(self, doc, champs):
        mission_id = champs["combo_mission"].currentData()
        if mission_id is None:
            QMessageBox.warning(self, "Remplir BDC", "Aucune mission Ricobot sélectionnée.")
            return
        v = champs["valeurs"]
        try:
            reponse = remplir_bdc(
                mission_id,
                abbreviation=v["titre"],
                reference=v["reference"],
                start_date=v["date_debut"],
                end_date=v["date_fin"],
            )
            cree_id = (reponse or {}).get("data", {}).get("id")
            lien = (f"{settings.ricobot_bo_url.rstrip('/')}"
                    f"/bo/missions/{mission_id}/orders/{cree_id}")

            # Persiste le lien pour qu'il reste affiché après rafraîchissement.
            maj_bdc_ricobot(doc["id"], {
                "mission_ids": v["mission_ids"], "missions": v["missions"],
                "abbreviation": v["titre"], "reference": v["reference"],
                "date_debut": v["date_debut"], "end_date": v["date_fin"],
                "confidence": v["confidence"],
                "order_id": cree_id, "order_url": lien,
            })
            v["order_id"], v["order_url"] = cree_id, lien

            QMessageBox.information(
                self, "Remplir BDC",
                f"Bon de commande créé dans Ricobot (id {cree_id}).\n"
                "Le lien « Voir le BDC dans Ricobot » apparaît sur la carte.")
            self.rafraichir()
        except Exception as e:
            QMessageBox.critical(self, "Erreur Ricobot", f"{type(e).__name__}: {e}")

    # Colore le select selon le statut courant.
    def _appliquer_couleur_statut(self, combo, statut):
        bg, fg = COULEURS_STATUT.get(statut, ("white", TEXTE))
        combo.setStyleSheet(f"QComboBox {{ background:{bg}; color:{fg}; }}")

    # Changement de statut → enregistre en base et recolore.
    def _statut_change(self, doc, combo):
        statut = combo.currentData()
        changer_statut(doc["id"], statut)
        self._appliquer_couleur_statut(combo, statut)

    # « Classer » : dépose le document dans le dossier choisi (créé si besoin) puis statut=classé.
    def _classer(self, doc, destination):
        chemin_local = doc.get("chemin_local")
        if not chemin_local or not Path(chemin_local).exists():
            QMessageBox.warning(self, "Classé", "Fichier introuvable sur le disque.")
            return

        combo = (destination or {}).get("combo")
        texte = combo.currentText().strip() if combo is not None else ""
        if not texte:
            QMessageBox.warning(self, "Classé", "Choisis ou saisis un dossier.")
            return

        try:
            # Dossier existant (par son nom) ou nouveau dossier à créer.
            chemin_existant = self._dossiers_par_nom.get(texte)
            if chemin_existant:
                dossier = chemin_existant
            else:
                dossier = creer_dossier(settings.base_remote_path, texte)
                self._dossier_mail[doc["mail_id"]] = texte

            chemin_distant = deposer_document(chemin_local, dossier)
            changer_statut(doc["id"], "classe", chemin_nextcloud=chemin_distant)

            # Le fichier est sur Nextcloud : on supprime la copie locale (échec non bloquant).
            try:
                Path(chemin_local).unlink()
            except OSError as e:
                print(f"[!] Copie locale non supprimée ({chemin_local}) : {e}")

            QMessageBox.information(self, "Classé", f"Document déposé dans :\n{dossier}")
            self.rafraichir()
        except Exception as e:
            QMessageBox.critical(self, "Erreur de dépôt", f"{type(e).__name__}: {e}")

    # Formate la date de réception (ISO -> "JJ/MM/AAAA HH:MM").
    def _format_date(self, iso):
        if not iso:
            return ""
        try:
            from datetime import datetime
            return datetime.fromisoformat(iso).strftime("%d/%m/%Y %H:%M")
        except Exception:
            return str(iso)[:16].replace("T", " ")

    # Chemin ouvrable : la copie locale, sinon le fichier téléchargé depuis Nextcloud.
    def _fichier_ouvrable(self, doc):
        chemin = doc.get("chemin_local")
        if chemin and Path(chemin).exists():
            return Path(chemin)
        distant = doc.get("chemin_nextcloud")
        if distant:
            cible = Path(tempfile.gettempdir()) / doc["nom_fichier"]
            cible.write_bytes(telecharger_document(distant))
            return cible
        return None

    # Aperçu : ouvre le fichier avec l'application par défaut du système.
    def _apercu(self, doc):
        try:
            fichier = self._fichier_ouvrable(doc)
        except Exception as e:
            QMessageBox.critical(self, "Aperçu", f"Nextcloud : {e}")
            return
        if fichier is None:
            QMessageBox.warning(self, "Aperçu", "Document introuvable (ni local ni Nextcloud).")
            return
        QDesktopServices.openUrl(QUrl.fromLocalFile(str(fichier.resolve())))

    # Télécharger : enregistre une copie du fichier.
    def _telecharger(self, doc):
        cible, _ = QFileDialog.getSaveFileName(self, "Enregistrer sous", doc["nom_fichier"])
        if not cible:
            return
        try:
            fichier = self._fichier_ouvrable(doc)
        except Exception as e:
            QMessageBox.critical(self, "Télécharger", f"Nextcloud : {e}")
            return
        if fichier is None:
            QMessageBox.warning(self, "Télécharger", "Document introuvable (ni local ni Nextcloud).")
            return
        shutil.copy(fichier, cible)
        QMessageBox.information(self, "Télécharger", "Fichier enregistré.")


def main():
    app = QApplication(sys.argv)
    app.setFont(QFont("Segoe UI", 10))
    # Base injoignable → message clair (config.ini) au lieu d'un crash silencieux.
    try:
        init_db()
    except Exception as e:
        QMessageBox.critical(
            None, "Connexion à la base",
            "Impossible de se connecter à la base de données.\n"
            "Vérifiez la section [database] de config.ini.\n\n"
            f"{type(e).__name__}: {e}")
        sys.exit(1)
    fenetre = FenetrePrincipale()
    fenetre.show()
    sys.exit(app.exec())


if __name__ == "__main__":
    main()
