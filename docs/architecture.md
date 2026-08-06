# Architecture technique

## Objet du document

Décrit l'architecture technique de l'assistant de gestion documentaire défini dans
[`product.md`](./product.md) : le rôle de chaque module, le flux de traitement, les
technologies et les principes.

```
src/document_assisstant/
├── config/          configuration (.env)
├── emails/          boîte mail Exchange + pièces jointes
├── extraction/      extraction du texte (Docling)
├── nextcloud/       dossiers Nextcloud : lister / déposer / créer / télécharger
├── ricobot/         missions + bons de commande
├── classification/  prompts + appels au LLM
├── databases/       PostgreSQL (schéma + accès, psycopg)
├── orchestration/   le pipeline (chef d'orchestre)
├── ui/              interface de bureau (PySide6)
└── utils/           fonctions transverses
```

> **Legacy (non utilisé)** : `notion/`, `vision/`, `classification/classifier.py`,
> `orchestration/pipeline.py`. La version actuelle rattache les documents à des **dossiers
> Nextcloud** (et non à des projets Notion).

---

## 1. Vue d'ensemble

L'application est un **assistant local**. Elle surveille une boîte mail, analyse les documents
reçus, et **propose** un classement dans Nextcloud (et un rattachement Ricobot pour les bons
de commande). **Aucun classement automatique** : chaque proposition est validée par un humain.

Elle se décompose en deux temps :

- **Le pipeline** (`orchestration/`) : automatique. Il lit les mails, analyse, et enregistre
  une proposition en base. Il n'écrit rien dans Nextcloud/Ricobot.
- **L'interface** (`ui/`) : humaine. Elle lit la base, l'utilisateur valide/corrige, et c'est
  seulement là que le dépôt réel a lieu.

Les modules ont une **responsabilité unique** et communiquent par des données simples
(chemins, texte, dictionnaires).

---

## 2. Rôle de chaque module

### `config/`
Configuration centralisée : charge le `.env` (identifiants Exchange, Nextcloud, Ricobot, clé
Anthropic, `DATABASE_URL`), chemins de travail et seuils. Aucun secret codé en dur ailleurs.

### `emails/`
Connexion **Exchange** et point d'entrée du flux. Filtre les nouveaux e-mails porteurs de
pièces jointes, sauvegarde les fichiers dans le dossier temporaire, et restitue les
métadonnées (expéditeur, sujet, date, `message_id`) + la liste des fichiers.

### `extraction/`
Extraction de contenu locale, unifiée autour de **Docling** (PDF texte et scanné, images,
DOCX, tableaux) avec **RapidOCR** comme moteur OCR interne. Produit un **texte unique**
(Markdown) plafonné. Aucun document brut n'est transmis au LLM.

### `nextcloud/`
Intégration **Nextcloud** (WebDAV) : lister les dossiers existants (candidats de classement),
déposer un document, créer un dossier, télécharger un fichier. N'écrit qu'après validation.

### `ricobot/`
Intégration **Ricobot** : lister les missions, créer un bon de commande. Utilisé uniquement
pour les documents de type bon de commande.

### `classification/`
Orchestration de l'**analyse par le LLM** (`classifier_v2`). Construit le prompt (objet du
mail + texte extrait + liste des dossiers), fait **un seul appel** Claude et récupère une
sortie **structurée en JSON** : type, dossier(s) proposé(s), score. Pour un bon de commande,
un second appel trouve la mission Ricobot et extrait les champs du BDC.

### `databases/`
Données de l'application dans **PostgreSQL**, en **SQL direct via psycopg** (sans ORM). Tout le
SQL est isolé dans `repository.py` (**repository pattern**) : le pipeline et l'UI n'appellent
que des fonctions.

### `orchestration/`
**Uniquement orchestrateur** (`pipeline_v2.py`) : enchaîne les étapes dans le bon ordre et fait
circuler les données, **sans logique métier**. Gère les erreurs (un document en échec est sauté).

### `ui/`
Interface de bureau (**PySide6**). Lit la base (`lister_mails`), affiche les propositions, et
déclenche les actions (dépôt Nextcloud, remplissage BDC Ricobot, changement de statut). Ne
connaît que les fonctions du `repository` — jamais de SQL.

### `utils/`
Fonctions transverses (sérialisation des dates, helpers), sans dépendance métier.

---

## 3. Flux complet

```
[1] emails/        Exchange → mails avec pièce jointe → fichiers dans data/inbox_temp/
[2] extraction/    Docling → texte
[3] nextcloud/     liste des dossiers existants
[4] classification/ Claude → type + dossier(s) + score (+ mission Ricobot si BDC)
[5] databases/     enregistrement en PostgreSQL
        │
        ▼
    ui/            l'humain valide → dépôt Nextcloud / création BDC Ricobot
```

Un seul appel LLM par document (deux pour un bon de commande).

---

## 4. Interactions entre modules

Dépendances **orientées** (sens unique), pour limiter le couplage :

```
config/  ← lu par tous les modules
utils/   ← utilitaires transverses

           ┌──────── orchestration/ (pipeline) ────────┐
           ▼                                            ▼
emails/ ─► extraction/ ─► classification/ ─► databases/ ◄─► ui/ ─► nextcloud/ + ricobot/
                              ▲                                (au moment de la validation)
                     nextcloud/ (liste) + ricobot/ (missions)
```

- `config/` et `utils/` : dépendances de bas niveau.
- `orchestration/` connaît tout le flux ; il appelle les autres et ne porte pas de logique métier.
- `databases/` est le point de passage entre le pipeline (écriture) et l'UI (lecture + statuts).
- `nextcloud/` et `ricobot/` n'écrivent **jamais** sans une action explicite de l'UI (validation).

---

## 5. Technologies

- **Python**, configuration par `.env` (`config/`).
- **Exchange** (mail), **Nextcloud** WebDAV (dépôt), **Ricobot** (bons de commande).
- **Docling** (extraction) + **RapidOCR** (OCR).
- **API Anthropic (Claude)** — analyse structurée, sortie JSON.
- **PostgreSQL** + **psycopg** (SQL direct). En développement, PostgreSQL tourne dans **Docker**.
- **PySide6** (Qt) pour l'interface.

---

## 6. Modèle de données (PostgreSQL)

Deux tables, relation un-à-plusieurs (`ON DELETE CASCADE`) :

- **`mails`** : `message_id` (unique, anti-doublon), `expediteur`, `expediteur_nom`, `objet`,
  `date_mail`, `date_analyse`.
- **`documents`** : `mail_id`, `nom_fichier`, `chemin_local`, `type_document`,
  `dossiers_candidats` (JSON), `bdc_ricobot` (JSON, bons de commande), `score_confiance`,
  `statut`, `chemin_nextcloud`, `date_decision`.

---

## 7. Principes d'architecture

- **Responsabilité unique** par module ; couplage faible, dépendances orientées.
- **Validation humaine obligatoire** : aucun dépôt sans action explicite dans l'UI.
- **Traitement local** : extraction et OCR en local ; seul le texte extrait est transmis au LLM.
- **Un seul appel LLM par document** (deux pour un BDC) ; texte plafonné pour maîtriser le coût.
- **Repository pattern** : tout le SQL isolé dans `databases/` → base remplaçable sans toucher
  au reste (SQLite → PostgreSQL a été fait ainsi).
- **PostgreSQL = source de vérité** ; les fichiers durables vivent dans **Nextcloud**.
