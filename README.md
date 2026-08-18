# Assistant de gestion documentaire

Application qui **surveille une boîte mail**, **analyse les documents reçus** en pièce jointe, et
**propose** un classement dans **Nextcloud** — et, pour les bons de commande, un rattachement à
une mission **Ricobot**.

> **Principe fondamental** : l'application ne classe **jamais** toute seule. Elle *propose*,
> l'humain *valide*. Elle automatise le travail répétitif (lire, comprendre, ranger le bon
> document au bon endroit) tout en gardant le contrôle sur chaque décision.

📄 Voir aussi : [`docs/product.md`](docs/product.md) · [`docs/architecture.md`](docs/architecture.md).

---

## Architecture : client / serveur

Le système se répartit en deux parties :

- **Serveur** (Docker) : le **pipeline** d'analyse + la base **PostgreSQL**. Tourne en continu.
- **Postes utilisateurs** : l'**interface de bureau**, distribuée en **exécutable Windows**,
  qui se connecte à la base du serveur sur le réseau interne.

```
  SERVEUR (Docker)                          POSTES UTILISATEURS
  ┌────────────────────────┐                ┌──────────────────────┐
  │  pipeline ──► Postgres  │◄──── LAN ──────┤  application (.exe)   │
  │             (base app)  │                │  + config.ini        │
  └────────────────────────┘                └──────────────────────┘
```

---

## Comment ça marche

L'app se compose de **deux temps** :

1. **Le pipeline** (automatique, sur le serveur) : il lit les mails, analyse chaque document, et
   **prépare une proposition** qu'il enregistre en base. Il ne touche à rien dans Nextcloud/Ricobot.
2. **L'interface** (humaine, sur les postes) : elle affiche les propositions ; l'utilisateur
   **valide, corrige ou refuse**, et c'est *seulement là* que le document part réellement dans
   Nextcloud (ou que le bon de commande est créé dans Ricobot).

### Le parcours d'un document

```
   ┌── PIPELINE (serveur, automatique) ────────────────────────────────────┐
   │  1. Un mail avec pièce jointe arrive (Exchange).                       │
   │  2. Docling extrait le TEXTE (PDF, DOCX + OCR). Aucun document brut    │
   │     n'est envoyé au LLM : seul le texte l'est (confidentialité + coût).│
   │  3. On récupère la liste des dossiers Nextcloud existants.            │
   │  4. Claude analyse (objet + texte + dossiers) et répond en JSON :     │
   │       • le TYPE (facture, devis, contrat…)                            │
   │       • le/les DOSSIER(S) Nextcloud pertinents + un SCORE             │
   │     Bon de commande : un 2e appel trouve la MISSION Ricobot et        │
   │     extrait les champs (titre, référence, dates…).                    │
   │  5. Tout est enregistré dans PostgreSQL — y compris les OCTETS du     │
   │     fichier, pour que les postes puissent l'ouvrir avant classement.  │
   └────────────────────────────────────────────────────────────────────────┘
                                    │
                                    ▼
   ┌── INTERFACE (poste, l'humain décide) ─────────────────────────────────┐
   │  Pour chaque document, l'utilisateur peut :                          │
   │     • Aperçu / Télécharger (lu depuis la base, puis Nextcloud)        │
   │     • ajuster le DOSSIER (recherchable, ou nouveau nom → créé)        │
   │     • CLASSER → dépôt réel dans Nextcloud (+ statut « Classé »)       │
   │     • bon de commande : REMPLIR BDC → création dans Ricobot + lien   │
   │     • changer le STATUT (En attente / À signer / À renvoyer / Classé) │
   └────────────────────────────────────────────────────────────────────────┘
```

### Les idées clés

- **L'IA propose un index, pas un chemin en dur.** Le LLM choisit *parmi une liste* (dossiers,
  missions) — jamais un texte inventé. S'il ne trouve rien, il renvoie « aucun » et l'humain tranche.
- **Sortie JSON garantie** : la réponse de Claude est *toujours* un JSON valide, type *toujours*
  dans la liste autorisée.
- **Un seul appel LLM par document** (deux pour un BDC), texte plafonné (5 pages, 20 000 caractères).
- **Anti-doublon** : un mail déjà analysé est ignoré (clé `message_id`).
- **PostgreSQL = source de vérité** (le pipeline y écrit, l'interface y lit). Les fichiers
  finissent dans **Nextcloud** (mémoire durable) ; les octets stockés en base sont **libérés**
  une fois le document classé.

### Ce qui est stocké (2 tables)

- **`mails`** : l'e-mail reçu (expéditeur, objet, date, `message_id`).
- **`documents`** : une pièce jointe analysée — type, dossiers candidats, score, statut, données
  du bon de commande (`bdc_ricobot`), octets du fichier (`contenu`, temporaire), et l'emplacement
  final une fois déposé. `ON DELETE CASCADE` : supprimer un mail supprime ses documents.

---

## Déploiement

### 1. Serveur (pipeline + base, via Docker)

Sur le serveur (Docker + Docker Compose installés) :

```bash
git clone <url_du_repo> classifier
cd classifier
# copier les fichiers hors git (secrets) transmis séparément :
#   .env.docker  et  docker-compose.yaml
docker compose up -d --build
```

- **`.env.docker`** (secrets) et **`docker-compose.yaml`** ne sont **pas** dans git → à copier
  à la main sur le serveur.
- La base est persistée dans le volume `postgres_data` (ne jamais faire `docker compose down -v`).
- **Planifier le pipeline** (il tourne puis s'arrête) via cron, ex. toutes les heures :
  ```
  0 * * * * cd /chemin/classifier && docker compose run --rm assistant
  ```
- **Sécurité** : n'ouvrir le port `5432` que sur le **réseau interne**.

### 2. Postes utilisateurs (l'application)

Générer l'exécutable (une fois, sur une machine Windows avec l'environnement de dev) :

```powershell
src\document_assisstant\.venv\Scripts\pyinstaller.exe DocumentAssistant.spec --noconfirm
```

On distribue **2 fichiers** (dans `dist\`) : `DocumentAssistant.exe` + `config.ini`.
Dans `config.ini`, pointer vers le serveur (l'IP, **pas** `localhost`) :

```ini
[database]
url = postgresql://postgres:<mot_de_passe>@IP_DU_SERVEUR:5432/classifier

[nextcloud]
user =
password =

[ricobot]
url =
token =
```

> L'exe lit `config.ini` **à côté de lui** → changer de serveur = éditer `config.ini`,
> **sans recompiler**.

---

## Développement (en local)

Le pipeline et l'UI se lancent depuis le code source :

```powershell
cd C:\Dev\email_doc_classifier_git
$env:PYTHONPATH="src\document_assisstant"
src\document_assisstant\.venv\Scripts\python.exe -m orchestration.pipeline_v2   # pipeline
src\document_assisstant\.venv\Scripts\python.exe -m ui.app                       # interface
```

> ⚠️ **Toujours depuis la racine** avec `PYTHONPATH` : les modules vivent dans
> `src\document_assisstant`. En local, l'UI lit `.env` (`DATABASE_URL` sur `localhost`).

---

## Configuration

Trois fichiers selon le contexte (aucun secret dans le code : tout passe par `config/settings.py`,
qui lit `config.ini` en priorité puis `.env`) :

| Fichier | Où | Pour quoi |
|---|---|---|
| `.env` | racine, dev local | lancer le pipeline / l'UI depuis le code |
| `.env.docker` | serveur | secrets du pipeline en Docker (`DATABASE_URL` sur l'hôte `postgres`) |
| `config.ini` | à côté de l'exe | connexion des postes au serveur (`DATABASE_URL` sur l'IP du serveur) |

Clés attendues : Exchange (`EMAIL_ADRESS`, `EMAIL_PASSWORD`, `EXCHANGE_SERVER`), `CLAUDE_API_KEY`,
Nextcloud (`NEXTCLOUD_USER`, `NEXTCLOUD_PASSWORD`), Ricobot (`RICOBOT_URL`, `RICOBOT_API`,
`RICOBOT_BO_URL`), `DATABASE_URL`.

---

## Inspecter la base (dans Docker)

```bash
docker compose exec postgres psql -U postgres -d classifier
```
Dans `psql` : `\dt` (tables) · `\x` (affichage vertical) · `\q` (quitter).

```sql
SELECT m.objet, d.nom_fichier, d.type_document, d.statut
FROM documents d JOIN mails m ON m.id = d.mail_id;
```

---

## Structure du projet

Chaque dossier a **une seule responsabilité** et communique avec les autres par des données simples.

| Module | Rôle |
|---|---|
| `config/` | Configuration centralisée (`config.ini` / `.env`) |
| `emails/` | Connexion Exchange, récupération des pièces jointes |
| `extraction/` | Extraction du texte (**Docling** + OCR **RapidOCR**) |
| `nextcloud/` | Lister les dossiers · déposer / créer / télécharger un document |
| `ricobot/` | Lister les missions · créer un bon de commande |
| `classification/` | Prompts + appels à **Claude** (`classifier_v2` : dossier + BDC) |
| `databases/` | Schéma SQL et accès aux données (**psycopg**, sans ORM) |
| `orchestration/` | Le **pipeline** (`pipeline_v2`) — enchaîne les étapes, aucune logique métier |
| `ui/` | Interface de bureau (**PySide6**), + `run_client.py` (point d'entrée de l'exe) |
| `utils/` | Fonctions transverses |

> **Legacy (v1, plus utilisé)** : `notion/`, `classification/classifier.py`,
> `orchestration/pipeline.py`, `vision/`. La version actuelle rattache les documents à des
> **dossiers Nextcloud** (et non plus à des projets Notion).

---

## État

**Fonctionne** : mails → extraction (Docling + OCR RapidOCR) → dossiers Nextcloud → analyse Claude
(dossier + type + score, BDC Ricobot) → PostgreSQL → interface (aperçu/téléchargement via la base,
statut, dépôt Nextcloud avec création de dossier, remplissage BDC Ricobot + lien). Packaging de
l'UI en exécutable Windows (PyInstaller) et pipeline dockerisé pour le serveur.

**Pistes** :
- OCR actuellement forcé sur toutes les pages — à revoir (fiabilité / vitesse).
- LibreOffice non installé dans l'image (certains DOCX complexes) — à ajouter si besoin.
- Sortir le mot de passe de la base du `docker-compose.yaml` (le lire depuis `.env.docker`).
