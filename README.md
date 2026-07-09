# Assistant de gestion documentaire

Application locale qui surveille une boîte mail, analyse les documents reçus en pièce
jointe, et **propose** un classement dans Nextcloud. **Rien n'est classé automatiquement** :
chaque proposition est validée par un humain.


## Le pipeline

Le cœur de l'application. Il enchaîne 4 étapes et **injecte le résultat dans PostgreSQL**.

```
[1] emails/          Exchange : récupère les mails avec pièce jointe
        │            → sauvegarde les fichiers dans data/inbox_temp/
        ▼
[2] notion/          Récupère la liste des projets actifs
        │
        ▼
[3] extraction/      Docling : transforme chaque document en texte
        │
        ▼
[4] classification/  Claude : un seul appel par document
        │            → { type de document, projet proposé, score de confiance }
        ▼
    PostgreSQL       Source de vérité, lue par l'interface
```

**Deux garde-fous économiques :**
- Un mail **déjà analysé** est ignoré (anti-doublon sur son `message_id`) → aucun token
  n'est dépensé deux fois.
- Le texte envoyé à Claude est **plafonné** (5 pages, 20 000 caractères).
---

## Lancer le pipeline

### 1. Démarrer la base

PostgreSQL tourne dans Docker. **Docker Desktop doit être lancé.**

```powershell
docker start pg-classifier    # démarrer
docker ps                     # vérifier qu'il tourne
```

<details>
<summary>Première fois : créer le conteneur</summary>

```powershell
docker run --name pg-classifier `
  -e POSTGRES_PASSWORD=<mot_de_passe> `
  -e POSTGRES_DB=classifier `
  -p 5432:5432 `
  -v pgdata:/var/lib/postgresql/data `
  -d postgres:16
```
Le volume `pgdata` conserve les données même si le conteneur est supprimé.
Les tables sont créées automatiquement au premier lancement (`init_db()`).
</details>

### 2. Lancer le pipeline

 **Toujours depuis la racine du projet**, avec `PYTHONPATH` : les chemins (`data/`) sont
relatifs à la racine, et les modules vivent dans `src\document_assisstant`.

```powershell
cd C:\Dev\email_doc_classifier_git
$env:PYTHONPATH="src\document_assisstant"

src\document_assisstant\.venv\Scripts\python.exe -m orchestration.pipeline
```

Par défaut, il regarde les mails des **72 dernières heures**.

### 3. Ouvrir l'interface

Pour afficher les propositions, changer les statuts, prévisualiser et télécharger :

```powershell
src\document_assisstant\.venv\Scripts\python.exe -m ui.app
```

---

## Configuration

Un fichier **`.env`** à la racine (non versionné) fournit tous les accès :

```ini
EMAIL_ADRESS= / EMAIL_PASSWORD= / EXCHANGE_SERVER=     # boîte mail
NOTION_TOKEN= / NOTION_DATABASE_ID=                    # projets actifs
CLAUDE_API_KEY=                                        # analyse des documents
NEXTCLOUD_USER= / NEXTCLOUD_PASSWORD=                  # dépôt (à venir)
DATABASE_URL=postgresql://postgres:<mot_de_passe>@localhost:5432/classifier
```

Aucun secret n'est écrit dans le code : tout passe par `config/settings.py`.

> ℹ️ Les dépendances (Docling, anthropic, psycopg, PySide6, exchangelib…) sont installées
> dans le venv du projet.


---

## Structure du projet

Chaque dossier a **une seule responsabilité**.

| Module | Rôle |
|---|---|
| `config/` | Configuration centralisée (lit le `.env`) |
| `emails/` | Connexion Exchange, récupération des pièces jointes |
| `extraction/` | Extraction du texte (**Docling** + OCR **RapidOCR**) |
| `notion/` | Récupération des projets actifs |
| `classification/` | Construction du prompt + appel à **Claude** |
| `databases/` | Schéma SQL et accès aux données (**psycopg**, sans ORM) |
| `orchestration/` | Le **pipeline** — enchaîne les étapes, aucune logique métier |
| `ui/` | Interface de bureau (**PySide6**) |
| `utils/` | Fonctions transverses |
| `vision/` | *En attente* (hors périmètre V1) |

-
