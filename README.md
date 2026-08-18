# Assistant de gestion documentaire

Surveille une boîte mail, analyse les documents reçus et **propose** un classement dans Nextcloud
(et un rattachement Ricobot pour les bons de commande). L'humain valide ; l'app ne classe jamais
toute seule.

Deux parties : le **pipeline** + **PostgreSQL** tournent sur le **serveur** (Docker) ;
l'**interface** est un **exécutable Windows** sur les postes, connecté à la base du serveur.

```
  SERVEUR (Docker)                          POSTES UTILISATEURS
  ┌────────────────────────┐                ┌──────────────────────┐
  │  pipeline ──► Postgres  │◄──── LAN ──────┤  application (.exe)   │
  └────────────────────────┘                └──────────────────────┘
```

📄 Concepts détaillés : [`docs/product.md`](docs/product.md) · [`docs/architecture.md`](docs/architecture.md)

---

## Serveur (Docker) — pipeline + PostgreSQL

Pré-requis : Docker + Docker Compose. Copier à la racine `.env.docker` et `docker-compose.yaml`
(hors git, transmis séparément).

Pour lancer le serveur (PostgreSQL + pipeline)

```bash
git pull
docker compose up -d --build
```

Pour voir les logs du pipeline

```bash
docker compose logs -f assistant
```

Pour inspecter la base

```bash
docker compose exec postgres psql -U postgres -d classifier
# \dt (tables) · \x (affichage vertical) · \q (quitter)
```

Pour vider la base (tests)

```bash
docker compose exec postgres psql -U postgres -d classifier -c "TRUNCATE mails, documents RESTART IDENTITY CASCADE;"
```

> ⚠️ Ne **jamais** faire `docker compose down -v` (supprime le volume = perte des données).
> Le port `5432` doit rester ouvert **uniquement sur le LAN**.

---

## Postes utilisateurs — l'application (.exe)

Pour générer l'exécutable

```powershell
src\document_assisstant\.venv\Scripts\pyinstaller.exe DocumentAssistant.spec --noconfirm
```

On livre **2 fichiers** de `dist\` : `DocumentAssistant.exe` + `config.ini` (côte à côte).
Dans `config.ini`, pointer vers l'**IP du serveur** (pas `localhost`) :

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

> Changer de serveur = éditer `config.ini`, **sans recompiler**.

---

## Développement (local)

Pour lancer le pipeline

```powershell
cd C:\Dev\email_doc_classifier_git
$env:PYTHONPATH="src\document_assisstant"
src\document_assisstant\.venv\Scripts\python.exe -m orchestration.pipeline_v2
```

Pour lancer l'interface

```powershell
src\document_assisstant\.venv\Scripts\python.exe -m ui.app
```

> En local, l'UI lit `.env` (`DATABASE_URL` sur `localhost`).

---

## Configuration

Trois fichiers selon le contexte (`config.ini` prioritaire, sinon `.env`). Aucun secret dans le code.

| Fichier | Où | `DATABASE_URL` |
|---|---|---|
| `.env` | racine (dev local) | `@localhost` |
| `.env.docker` | serveur (Docker) | `@postgres` |
| `config.ini` | à côté de l'exe | `@IP_DU_SERVEUR` |

Clés : Exchange (`EMAIL_ADRESS`, `EMAIL_PASSWORD`, `EXCHANGE_SERVER`), `CLAUDE_API_KEY`,
Nextcloud (`NEXTCLOUD_USER`, `NEXTCLOUD_PASSWORD`), Ricobot (`RICOBOT_URL`, `RICOBOT_API`,
`RICOBOT_BO_URL`), `DATABASE_URL`.

---

## Structure

| Module | Rôle |
|---|---|
| `config/` | Configuration (`config.ini` / `.env`) |
| `emails/` | Connexion Exchange, pièces jointes |
| `extraction/` | Extraction du texte (**Docling** + OCR **RapidOCR**) |
| `nextcloud/` | Lister / déposer / créer / télécharger |
| `ricobot/` | Missions · bons de commande |
| `classification/` | Prompts + appels **Claude** (`classifier_v2`) |
| `databases/` | Schéma SQL + accès (**psycopg**, sans ORM) |
| `orchestration/` | Le **pipeline** (`pipeline_v2`) |
| `ui/` | Interface **PySide6** + `run_client.py` (entrée de l'exe) |
