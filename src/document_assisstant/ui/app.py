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

/* Boîte de recherche : cadre arrondi blanc contenant la loupe + le champ. */
#boiteRecherche {{
    background: white;
    border: 1px solid {BORDURE};
    border-radius: 10px;
}}

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

        # Tous les dossiers Nextcloud (< 1 an), chargés une fois : permettent de
        # rechercher/choisir la destination même si l'IA n'a pas proposé le bon dossier.
        try:
            self.dossiers_nextcloud = lister_dossiers(settings.base_remote_path)
        except Exception as e:
            print(f"[!] Dossiers Nextcloud indisponibles : {e}")
            self.dossiers_nextcloud = []
        # Index nom -> chemin, pour retrouver le dossier choisi dans le champ recherchable.
        self._dossiers_par_nom = {d["nom"]: d["chemin"] for d in self.dossiers_nextcloud}

        # Nom du dossier créé par mail (mail_id -> nom) : mémorisé pour que les
        # documents suivants d'un même mail réutilisent le même dossier sans
        # avoir à retaper le nom après un rafraîchissement.
        self._dossier_mail = {}

        # Filtre par statut (None = tous). Piloté par la barre de filtre.
        self._filtre_statut = None
        self._boutons_filtre = {}

        # Texte de la barre de recherche (vide = pas de filtre texte).
        self._recherche = ""

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

        # Ligne unique : boîte de recherche (loupe + champ) à gauche, puis les filtres.
        barre = QWidget()
        bf = QHBoxLayout(barre)
        bf.setContentsMargins(24, 0, 24, 8)
        bf.setSpacing(10)

        # Boîte de recherche arrondie : loupe (Segoe MDL2 Assets) + champ sans bordure.
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

        # Filtres par statut, juste après la recherche.
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

        # Affiche tout au démarrage (et marque le bouton "Tous" comme actif).
        self._appliquer_filtre(None)

    # Vide et reconstruit la liste depuis la base (repository.lister_mails).
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

    # Applique un filtre par statut (None = tous) et met la barre à jour.
    def _appliquer_filtre(self, statut):
        self._filtre_statut = statut
        for cle, bouton in self._boutons_filtre.items():
            actif = (cle == statut)
            bouton.setStyleSheet(f"background:{BLEU}; color:white;" if actif else "")
        self.rafraichir()

    # Barre de recherche : mémorise le texte saisi et rafraîchit la liste.
    def _rechercher(self, texte):
        self._recherche = texte.strip().lower()
        self.rafraichir()

    # True si le texte recherché apparaît dans un champ du mail ou de ses documents
    # (expéditeur, objet, nom de fichier, nom de projet). Recherche insensible à la casse.
    def _mail_correspond(self, mail):
        q = self._recherche
        champs = [mail.get("expediteur"), mail.get("expediteur_nom"), mail.get("objet")]
        for d in mail["documents"]:
            champs.append(d.get("nom_fichier"))
            champs.append(d.get("projet_nom"))
        return any(q in (c or "").lower() for c in champs)

    # Corbeille : supprime un mail et ses documents (après confirmation).
    # Les fichiers déjà déposés dans Nextcloud ne sont pas touchés ; on nettoie
    # seulement les copies locales encore présentes.
    def _supprimer_mail(self, mail):
        nb = len(mail["documents"])
        rep = QMessageBox.question(
            self, "Supprimer",
            f"Supprimer ce mail et ses {nb} document(s) de la liste ?\n"
            "(Les fichiers déjà déposés dans Nextcloud ne sont pas supprimés.)")
        if rep != QMessageBox.StandardButton.Yes:
            return

        for d in mail["documents"]:
            chemin = d.get("chemin_local")
            if chemin and Path(chemin).exists():
                try:
                    Path(chemin).unlink()
                except OSError as e:
                    print(f"[!] Copie locale non supprimée ({chemin}) : {e}")

        supprimer_mail(mail["id"])
        self.rafraichir()

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

        # En-tête horizontal : [avatar] [expéditeur]  [objet — date]  [poubelle].
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

        # Objet + date de réception (date en gras), à côté de l'expéditeur.
        sujet = html.escape(mail.get("objet") or "(sans objet)")
        d = self._format_date(mail.get("date_mail"))
        objet = QLabel(f"{sujet} — <b>{html.escape(d)}</b>" if d else sujet)
        objet.setObjectName("objet")
        objet.setTextFormat(Qt.RichText)
        objet.setWordWrap(True)
        entete.addSpacing(20)
        entete.addWidget(objet, stretch=1)

        poubelle = QPushButton("x")
          # croix rouge = supprimer (ASCII, toujours rendu)
        poubelle.setToolTip("Supprimer ce mail et ses documents de la liste")
        poubelle.setFixedSize(34, 34)
        poubelle.setStyleSheet(
            "background:#FDECEC; color:#E0342B; border-radius:8px;"
            " font-size:16px; font-weight:bold;")
        poubelle.clicked.connect(lambda _=0, m=mail: self._supprimer_mail(m))
        entete.addWidget(poubelle, alignment=Qt.AlignTop)

        col.addLayout(entete)

        # Ligne de séparation entre l'en-tête et les documents.
        sep = QFrame()
        sep.setFixedHeight(1)
        sep.setStyleSheet(f"background:{BORDURE}; border:none;")
        col.addWidget(sep)

        # Un mail = un projet = un dossier : UNE SEULE destination pour tout le mail.
        # On agrège les dossiers candidats trouvés pour n'importe quel document.
        # S'il y en a -> menu de choix. Sinon -> case de création (repli).
        candidats_mail, vus = [], set()
        for d in mail["documents"]:
            for c in (d.get("dossiers_candidats") or []):
                if c["chemin"] not in vus:
                    vus.add(c["chemin"])
                    candidats_mail.append(c)

        ligne = QHBoxLayout()
        ligne.addWidget(QLabel("Dossier du mail :"))

        # Champ recherchable : liste de TOUS les dossiers Nextcloud extraits, avec la
        # proposition de l'IA pré-sélectionnée. L'utilisateur peut taper pour chercher
        # un autre dossier existant, ou saisir un nouveau nom (créé au moment du dépôt).
        dest_combo = QComboBox()
        dest_combo.setEditable(True)
        dest_combo.setInsertPolicy(QComboBox.InsertPolicy.NoInsert)
        for dossier in self.dossiers_nextcloud:
            dest_combo.addItem(dossier["nom"], userData=dossier["chemin"])
        completer = dest_combo.completer()
        if completer is not None:
            completer.setCompletionMode(QCompleter.CompletionMode.PopupCompletion)
            completer.setFilterMode(Qt.MatchContains)   # cherche "contient", pas "commence par"
        dest_combo.setMinimumWidth(360)

        # Valeur par défaut : proposition IA (1er candidat), sinon dossier déjà créé
        # pour ce mail, sinon vide.
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

        # Score de rattachement du dossier, juste à droite du champ (meilleur score
        # parmi les documents du mail — un mail = un projet).
        scores = [d.get("score_confiance") for d in mail["documents"]
                  if d.get("score_confiance") is not None]
        ligne.addWidget(_pastille_score(max(scores) if scores else None))
        col.addLayout(ligne)

        destination = {"combo": dest_combo}
        for doc in mail["documents"]:
            col.addWidget(self._carte_document(
                doc, mail.get("objet") or "", mail.get("date_mail"), destination))
        return carte

    # Retrouve le nom du dossier déjà créé pour un mail, à partir d'un document
    # déjà classé (son chemin Nextcloud est en base). Persiste après redémarrage.
    def _dossier_cree_du_mail(self, mail):
        for d in mail["documents"]:
            chemin = d.get("chemin_nextcloud")
            if chemin:
                dossier = chemin.rsplit("/", 1)[0]      # enlève le nom de fichier
                return dossier.rsplit("/", 1)[-1]        # dernier segment = nom du dossier
        return ""

    # Petit avatar rond avec l'initiale de l'expéditeur (aide à distinguer les mails).
    def _avatar(self, mail):
        source = (mail.get("expediteur_nom") or mail.get("expediteur") or "?").strip()
        a = QLabel(source[0].upper() if source else "?")
        a.setObjectName("avatar")
        a.setFixedSize(42, 42)
        a.setAlignment(Qt.AlignCenter)
        return a

    # Une carte bordurée par document : nom, score, statut, actions.
    # La destination Nextcloud est commune au mail (cf. _carte_mail).
    def _carte_document(self, doc, objet_mail="", date_mail=None, destination=None):
        carte = QFrame()
        carte.setObjectName("carteDoc")
        col = QVBoxLayout(carte)
        col.setContentsMargins(16, 12, 16, 12)
        col.setSpacing(10)

        # Ligne 1 : nom du fichier + type de document juste à sa droite.
        # (Le score est affiché au niveau du mail, à côté du dossier.)
        l1 = QHBoxLayout()
        nom = QLabel(doc["nom_fichier"])
        nom.setObjectName("nomFichier")
        l1.addWidget(nom)
        l1.addWidget(_pastille_type(doc.get("type_document")))
        l1.addStretch()
        col.addLayout(l1)

        # Bloc BON DE COMMANDE : projet Ricobot (corrigeable) + champs extraits.
        # Affiché uniquement pour les bons de commande.
        champs_bdc = None
        if doc.get("type_document") == "bon_de_commande":
            champs_bdc = self._bloc_bdc(col, doc.get("bdc_ricobot") or {}, date_mail, doc)

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

    # Bloc d'un bon de commande : sélecteur de mission Ricobot (largeur réduite,
    # modifiable) + un crayon ✏️ à droite pour éditer titre / dates.
    # Les valeurs éditées sont stockées dans un dict relu par « Remplir BDC ».
    def _bloc_bdc(self, col, bdc, date_mail, doc):
        ligne = QHBoxLayout()
        ligne.addWidget(QLabel("🧾 Projet Ricobot :"))
        combo_mission = QComboBox()
        for p in self.projets_ricobot:
            combo_mission.addItem(f"{p['nom']} — {p['company']}", userData=p["id"])
        # Pré-sélection : 1re mission proposée par le LLM, si elle existe.
        proposes = bdc.get("mission_ids") or []
        if proposes:
            idx = combo_mission.findData(proposes[0])
            if idx >= 0:
                combo_mission.setCurrentIndex(idx)
        combo_mission.setMaximumWidth(460)          # largeur du menu Ricobot
        ligne.addWidget(combo_mission)

        # Valeurs éditables du BDC (date de début = réception du mail par défaut).
        valeurs = {
            "titre": bdc.get("abbreviation") or "",
            "reference": bdc.get("reference") or "",   # non édité, gardé pour l'API
            "date_debut": bdc.get("date_debut") or (str(date_mail)[:10] if date_mail else ""),
            "date_fin": bdc.get("end_date") or "",
            "mission_ids": bdc.get("mission_ids") or [],
            "missions": bdc.get("missions") or [],
            "confidence": bdc.get("confidence"),
        }

        b_edit = QPushButton("✏️")
        b_edit.setToolTip("Voir / modifier les informations du bon de commande")
        b_edit.clicked.connect(lambda _=0, d=doc, v=valeurs: self._editer_bdc(d, v))
        ligne.addWidget(b_edit)          # collé au menu
        ligne.addStretch()               # le reste de la largeur pousse à droite
        col.addLayout(ligne)

        return {"combo_mission": combo_mission, "valeurs": valeurs}

    # Crayon ✏️ : fenêtre d'édition du BDC. « Valider » enregistre en base
    # (l'envoi à Ricobot reste au bouton « Remplir BDC »).
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

        # Applique en mémoire (relu par Remplir BDC) puis enregistre en base.
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
        })

    # Bouton « Remplir BDC » : envoie le bon de commande à Ricobot pour la mission
    # retenue (celle du LLM ou celle choisie par l'utilisateur).
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
            QMessageBox.information(
                self, "Remplir BDC",
                f"Bon de commande créé dans Ricobot (id {cree_id}).")
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
            # Le texte correspond-il à un dossier Nextcloud existant (par son nom) ?
            chemin_existant = self._dossiers_par_nom.get(texte)
            if chemin_existant:
                dossier = chemin_existant                     # dossier existant choisi
            else:
                dossier = creer_dossier(settings.base_remote_path, texte)  # nouveau dossier
                self._dossier_mail[doc["mail_id"]] = texte

            chemin_distant = deposer_document(chemin_local, dossier)
            changer_statut(doc["id"], "classe", chemin_nextcloud=chemin_distant)

            # Le fichier est maintenant sur Nextcloud (source de vérité) : on
            # supprime la copie locale. Aperçu/Télécharger le reprendront depuis
            # Nextcloud via chemin_nextcloud. L'échec de suppression n'est pas bloquant.
            try:
                Path(chemin_local).unlink()
            except OSError as e:
                print(f"[!] Copie locale non supprimée ({chemin_local}) : {e}")

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

    # Renvoie un chemin local ouvrable : la copie locale si elle existe, sinon le
    # fichier téléchargé depuis Nextcloud (dans un dossier temporaire).
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

    # Aperçu : ouvre le fichier (local, ou récupéré depuis Nextcloud si supprimé).
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

    # ⬇ Télécharger : enregistre le fichier (local, ou récupéré depuis Nextcloud).
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
    init_db()
    app = QApplication(sys.argv)
    app.setFont(QFont("Segoe UI", 10))
    fenetre = FenetrePrincipale()
    fenetre.show()
    sys.exit(app.exec())


if __name__ == "__main__":
    main()
