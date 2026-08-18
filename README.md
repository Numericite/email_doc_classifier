# Assistant de gestion documentaire

Application locale qui **surveille une boîte mail**, **analyse les documents reçus** en pièce
jointe, et **propose** un classement dans **Nextcloud** — et, pour les bons de commande, un
rattachement à une mission **Ricobot**.

> **Principe fondamental** : l'application ne classe **jamais** toute seule. Elle *propose*,
> l'humain *valide*. Elle automatise le travail répétitif (lire, comprendre, ranger le bon
> document au bon endroit) tout en gardant le contrôle sur chaque décision.

📄 Voir aussi : [`docs/product.md`](docs/product.md) · [`docs/architecture.md`](docs/architecture.md) · [`docs/tasks.md`](docs/tasks.md).

---

## Comment ça marche

L'app se compose de **deux temps** :

1. **Le pipeline** (automatique) : il lit les mails, analyse chaque document, et **prépare une
   proposition** qu'il enregistre en base. Il ne touche à rien dans Nextcloud/Ricobot.
2. **L'interface** (humaine) : elle affiche les propositions ; l'utilisateur **valide, corrige
   ou refuse**, et c'est *seulement là* que le document part réellement dans Nextcloud (ou que
   le bon de commande est créé dans Ricobot).

### Le parcours d'un document, étape par étape

```
   ┌── PIPELINE (automatique) ─────────────────────────────────────────────┐
   │                                                                        │
   │  1. emails/       Un mail avec pièce jointe arrive (Exchange).         │
   │                   → la pièce jointe est sauvegardée dans data/inbox_temp/
   │                                                                        │
   │  2. extraction/   Docling lit le document (PDF, DOCX) et en extrait    │
   │                   le TEXTE. Aucun document brut n'est envoyé au LLM :  │
   │                   seul le texte l'est (confidentialité + coût).        │
   │                                                                        │
   │  3. nextcloud/    On récupère la liste des dossiers Nextcloud          │
   │                   existants (destinations possibles).                  │
   │                                                                        │
   │  4. classification/  Claude analyse (objet du mail + texte + liste des │
   │                   dossiers) et répond en JSON :                        │
   │                     • le TYPE du document (facture, devis, contrat…)   │
   │                     • le/les DOSSIER(S) Nextcloud les plus pertinents  │
   │                     • un SCORE de confiance                            │
   │                   Cas particulier — bon de commande : un 2e appel      │
   │                   trouve la MISSION Ricobot et extrait les champs du   │
   │                   bon de commande (titre, référence, dates…).          │
   │                                                                        │
   │  5. Tout est enregistré dans PostgreSQL (la « file d'attente »).       │
   └────────────────────────────────────────────────────────────────────────┘
                                    │
                                    ▼
   ┌── INTERFACE (l'humain décide) ────────────────────────────────────────┐
   │                                                                        │
   │  L'utilisateur voit chaque mail et ses documents, avec la proposition │
   │  de l'IA. Pour chaque document il peut :                              │
   │     • Aperçu / Télécharger le fichier                                 │
   │     • ajuster le DOSSIER (champ recherchable parmi tous les dossiers  │
   │       Nextcloud, ou saisir un NOUVEAU nom → créé à la volée)          │
   │     • CLASSER → dépôt réel dans Nextcloud (+ statut « Classé »)       │
   │     • pour un bon de commande : REMPLIR BDC → création dans Ricobot   │
   │       + un lien cliquable vers le bon de commande créé                │
   │     • changer le STATUT (En attente / À signer / À renvoyer / Classé) │
   └────────────────────────────────────────────────────────────────────────┘
```

### Les idées clés à retenir

- **L'IA propose un index, pas un chemin en dur.** Le LLM choisit *parmi une liste* (dossiers,
  missions) et renvoie l'élément retenu — jamais un texte inventé. S'il ne trouve rien, il
  renvoie « aucun » et l'utilisateur tranche.
- **Sortie JSON garantie** (structured outputs) : la réponse de Claude est *toujours* un JSON
  valide, avec un type de document *toujours* dans la liste autorisée.
- **Un seul appel LLM par document** (deux pour un bon de commande). Le texte est plafonné
  (5 pages, 20 000 caractères) pour maîtriser le coût.
- **Anti-doublon** : un mail déjà analysé est ignoré (clé `message_id`) → aucun token dépensé
  deux fois.
- **PostgreSQL est la source de vérité.** Le pipeline y écrit, l'interface y lit et met à jour
  les statuts. Les fichiers, eux, finissent dans **Nextcloud** (la mémoire durable de
  l'entreprise) ; `data/inbox_temp/` n'est qu'un dossier de travail temporaire.

### Ce qui est stocké (2 tables)

- **`mails`** : l'e-mail reçu (expéditeur, objet, date, `message_id`).
- **`documents`** : une pièce jointe analysée, rattachée à son mail — type, dossiers candidats,
  score, statut, données du bon de commande (`bdc_ricobot`), et l'emplacement final une fois
  déposé. Supprimer un mail supprime ses documents (`ON DELETE CASCADE`).

---

## Lancer

### 1. La base (PostgreSQL dans Docker — Docker Desktop doit tourner)

```powershell
docker start pg-classifier    # démarrer
docker ps                     # vérifier
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
Le volume `pgdata` conserve les données. Les tables sont créées au premier lancement.
</details>

### 2. Le pipeline (analyse les mails récents → remplit la base)

```powershell
cd C:\Dev\email_doc_classifier_git
$env:PYTHONPATH="src\document_assisstant"
src\document_assisstant\.venv\Scripts\python.exe -m orchestration.pipeline_v2
```

> ⚠️ **Toujours depuis la racine** avec `PYTHONPATH` : les chemins (`data/`) sont relatifs à la
> racine, et les modules vivent dans `src\document_assisstant`.

### 3. L'interface

```powershell
src\document_assisstant\.venv\Scripts\python.exe -m ui.app
```

---

## Configuration (`.env` à la racine, non versionné)

```ini
# Boîte mail Exchange
EMAIL_ADRESS= / EMAIL_PASSWORD= / EXCHANGE_SERVER=

# Claude (analyse des documents)
CLAUDE_API_KEY=

# Nextcloud (liste des dossiers + dépôt)
NEXTCLOUD_USER= / NEXTCLOUD_PASSWORD=

# Ricobot (bons de commande)
RICOBOT_URL=           # URL de l'API
RICOBOT_API=           # jeton
RICOBOT_BO_URL=        # (optionnel) URL du site pour les liens BDC
                       #  défaut : https://preprod.ricobot.numericite.eu

# Base de données
DATABASE_URL=postgresql://postgres:<mot_de_passe>@localhost:5432/classifier
```

Aucun secret dans le code : tout passe par `config/settings.py`.

---

## Inspecter la base

```powershell
docker exec -it pg-classifier psql -U postgres -d classifier
```
Dans `psql` : `\dt` (tables) · `\x` (affichage vertical) · `\q` (quitter).

```sql
SELECT m.objet, d.nom_fichier, d.type_document, d.statut
FROM documents d JOIN mails m ON m.id = d.mail_id;
```

---

## Structure du projet

Chaque dossier a **une seule responsabilité**, et communique avec les autres par des données
simples (un module ne connaît pas les détails des autres).

| Module | Rôle |
|---|---|
| `config/` | Configuration centralisée (lit le `.env`) |
| `emails/` | Connexion Exchange, récupération des pièces jointes |
| `extraction/` | Extraction du texte (**Docling** + OCR **RapidOCR**) |
| `nextcloud/` | Lister les dossiers · déposer / créer / télécharger un document |
| `ricobot/` | Lister les missions · créer un bon de commande |
| `classification/` | Prompts + appels à **Claude** (`classifier_v2` : dossier + BDC) |
| `databases/` | Schéma SQL et accès aux données (**psycopg**, sans ORM) |
| `orchestration/` | Le **pipeline** (`pipeline_v2`) — enchaîne les étapes, aucune logique métier |
| `ui/` | Interface de bureau (**PySide6**) |
| `utils/` | Fonctions transverses |

> **Legacy (v1, plus utilisé)** : `notion/`, `classification/classifier.py`,
> `orchestration/pipeline.py`, `vision/`. La version actuelle rattache les documents à des
> **dossiers Nextcloud** (et non plus à des projets Notion).

---

## Où on en est

**Fonctionne** : mails → extraction → dossiers Nextcloud → analyse Claude (dossier + type +
score, BDC Ricobot) → PostgreSQL → interface (aperçu, téléchargement, statut, dépôt Nextcloud
avec création de dossier, remplissage BDC Ricobot + lien).

**Reste à faire (extraits)** :
- Fiabiliser l'extraction (OCR actuellement forcé sur toutes les pages — à revoir).
- Deux pièces jointes de même nom, dans deux mails différents, s'écrasent dans
  `data/inbox_temp/` (correction prévue : un sous-dossier par mail).
- Créer un `requirements.txt` (`anthropic`, `docling`, `psycopg[binary]`, `PySide6`,
  `exchangelib`, `requests`, `python-dotenv`).
- Nettoyer la dépendance `SQLAlchemy`, devenue inutile.

Détail complet dans [`docs/tasks.md`](docs/tasks.md).
