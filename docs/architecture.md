# Architecture technique

## Objet du document

Décrit l'architecture de l'assistant défini dans [`product.md`](./product.md) : comment le
système est organisé (client / serveur), le flux de traitement, le déploiement et les principes.

---

## 1. Vue d'ensemble : client / serveur

Le système se répartit en deux parties :

- **Serveur** (Docker) : le **pipeline** d'analyse + la base **PostgreSQL**. Tourne en continu
  sur un serveur de l'entreprise.
- **Postes utilisateurs** : l'**interface de bureau**, distribuée en **exécutable Windows**.
  Elle se connecte à la base du serveur sur le réseau interne.

```
  SERVEUR (Docker)                          POSTES UTILISATEURS
  ┌────────────────────────┐                ┌──────────────────────┐
  │  pipeline ──► Postgres  │◄──── LAN ──────┤  application (.exe)   │
  │             (base app)  │                │  + config.ini        │
  └────────────────────────┘                └──────────────────────┘
```

Le traitement se fait en **deux temps** :

- **Le pipeline** : automatique. Il lit les mails, analyse les documents et enregistre une
  **proposition** en base. Il n'écrit **rien** dans Nextcloud/Ricobot.
- **L'interface** : humaine. Elle lit la base, l'utilisateur valide/corrige, et c'est
  **seulement là** que le dépôt réel a lieu.

La base PostgreSQL est le **point de rencontre** : le pipeline écrit, l'interface lit.

---

## 2. Le pipeline (côté serveur)

Chef d'orchestre sans logique métier : il enchaîne les étapes et fait circuler les données.

```
Exchange ─► extraction (Docling + OCR) ─► dossiers Nextcloud existants
        ─► analyse LLM (Claude) ─► enregistrement PostgreSQL
```

- **Un seul appel LLM par document** (deux pour un bon de commande).
- **Aucun document brut n'est envoyé au LLM** : seul le texte extrait (localement), plafonné.
- La sortie du LLM est un **JSON structuré** : type de document, dossier(s) proposé(s), score
  de confiance — plus, pour un bon de commande, la mission Ricobot et les champs du BDC.
- Il tourne **périodiquement** (planifié sur le serveur).

---

## 3. L'interface (côté poste)

Application de bureau (**PySide6**), organisée **par e-mail reçu**. Elle lit les propositions
en base, l'utilisateur valide ou corrige, puis déclenche les actions réelles :

- **dépôt** du document dans le dossier Nextcloud choisi (créé à la volée si besoin) ;
- **création** du bon de commande dans Ricobot ;
- **changement de statut**.

L'interface ne connaît que les fonctions d'accès aux données (**repository**) : elle ne
manipule jamais de SQL directement.

---

## 4. Flux complet

```
[serveur]  Exchange → extraction → dossiers Nextcloud → LLM → PostgreSQL
                                                              │
[poste]                                    l'humain valide ──┘→ dépôt Nextcloud / BDC Ricobot
```

---

## 5. Déploiement

- **Serveur** : `docker compose` lance **PostgreSQL** + le **pipeline**. Les secrets
  (identifiants Exchange, Nextcloud, Ricobot, clé Claude, mot de passe base) vivent dans un
  fichier d'environnement **hors dépôt**.
- **Postes** : un **exécutable** + un fichier **`config.ini`** posé à côté, contenant l'adresse
  du serveur et les identifiants. Il est **modifiable sans recompiler** l'application.
- La base est la **source de vérité partagée** ; les postes s'y connectent en **réseau interne**.

---

## 6. Modèle de données (PostgreSQL)

Deux tables, relation un-à-plusieurs (`ON DELETE CASCADE`) :

- **`mails`** : expéditeur, objet, date, `message_id` (unique, anti-doublon).
- **`documents`** : rattaché à un mail — nom, type, dossier(s) candidat(s) (JSON), infos du bon
  de commande (JSON), score, **statut**, emplacement Nextcloud final.

Tout le SQL est isolé dans un module d'accès unique (**repository pattern**), ce qui rend la
base remplaçable sans toucher au reste (le passage SQLite → PostgreSQL s'est fait ainsi).

---

## 7. Technologies

- **Python** — pipeline et interface.
- **Exchange** (mail), **Nextcloud** WebDAV (dépôt des documents), **Ricobot** (bons de commande).
- **Docling** + **RapidOCR** — extraction et OCR, en local.
- **API Anthropic (Claude)** — analyse à sortie JSON structurée.
- **PostgreSQL** + **psycopg** (SQL direct) — données de l'application, dans **Docker**.
- **PySide6** (Qt) — interface de bureau, distribuée en **exécutable Windows** (PyInstaller).

---

## 8. Principes d'architecture

- **Séparation client / serveur** : le pipeline et la base tournent côté serveur ; l'interface
  côté poste. La base est le seul lien.
- **Validation humaine obligatoire** : aucun dépôt sans action explicite dans l'interface.
- **Traitement local** : extraction et OCR en local ; seul le texte est transmis au LLM.
- **Coût maîtrisé** : un appel LLM par document, texte plafonné.
- **Repository pattern** : tout le SQL isolé → base remplaçable.
- **PostgreSQL = source de vérité** ; les fichiers durables vivent dans **Nextcloud**.

> **Legacy (non utilisé)** : le rattachement à des projets Notion et l'analyse par LLM Vision
> ont été remplacés. La version actuelle rattache les documents à des **dossiers Nextcloud**.
